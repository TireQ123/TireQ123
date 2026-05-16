"""Testy scripts/memory_suggest.py — ekstrakcja, parsowanie, zapis sugestii."""
import json

import pytest

import memory_suggest as ms


# ── extract_conversation ─────────────────────────────────────────────────────

def test_extract_conversation_plain_list(tmp_path):
    t = tmp_path / "t.json"
    t.write_text(json.dumps([
        {"role": "user", "content": "preferuję FastAPI"},
        {"role": "assistant", "content": "Notuję, Panie TireQ."},
        {"role": "system", "content": "ignoruj to"},
    ]), encoding="utf-8")
    out = ms.extract_conversation(str(t))
    assert "TireQ: preferuję FastAPI" in out
    assert "JARVIS: Notuję" in out
    assert "ignoruj to" not in out


def test_extract_conversation_messages_key(tmp_path):
    t = tmp_path / "t.json"
    t.write_text(json.dumps({"messages": [
        {"role": "user", "content": "deadline w czerwcu"},
    ]}), encoding="utf-8")
    assert "deadline w czerwcu" in ms.extract_conversation(str(t))


def test_extract_conversation_content_blocks(tmp_path):
    t = tmp_path / "t.json"
    t.write_text(json.dumps([
        {"role": "user", "content": [
            {"type": "text", "text": "blok tekstowy"},
            {"type": "image", "url": "x"},
        ]},
    ]), encoding="utf-8")
    assert "blok tekstowy" in ms.extract_conversation(str(t))


def test_extract_conversation_missing_file_returns_empty():
    assert ms.extract_conversation("/nope/ghost.json") == ""


def test_extract_conversation_skips_empty_content(tmp_path):
    t = tmp_path / "t.json"
    t.write_text(json.dumps([
        {"role": "user", "content": "   "},
        {"role": "assistant", "content": "realna odpowiedź"},
    ]), encoding="utf-8")
    out = ms.extract_conversation(str(t))
    assert "realna odpowiedź" in out
    assert out.count("\n") == 0


# ── parse_suggestions ────────────────────────────────────────────────────────

def test_parse_suggestions_clean_json():
    raw = '{"decisions": ["x"], "preferences": [], "notes": [], "summary": "s"}'
    assert ms.parse_suggestions(raw)["decisions"] == ["x"]


def test_parse_suggestions_with_surrounding_text():
    raw = 'Oto wynik:\n{"decisions": ["a"]}\nKoniec.'
    assert ms.parse_suggestions(raw) == {"decisions": ["a"]}


def test_parse_suggestions_no_json_returns_empty():
    assert ms.parse_suggestions("brak jakiegokolwiek json") == {}


def test_parse_suggestions_malformed_returns_empty():
    assert ms.parse_suggestions("{nie: poprawny json,,,}") == {}


# ── save_suggestions ─────────────────────────────────────────────────────────

def test_save_suggestions_calls_memory_update(monkeypatch):
    import memory_update as mu
    calls = {"dec": [], "pref": [], "note": [], "sess": []}
    monkeypatch.setattr(mu, "add_decision", lambda v: calls["dec"].append(v))
    monkeypatch.setattr(mu, "add_preference", lambda v: calls["pref"].append(v))
    monkeypatch.setattr(mu, "add_note", lambda v: calls["note"].append(v))
    monkeypatch.setattr(mu, "save_session", lambda v: calls["sess"].append(v))

    count = ms.save_suggestions({
        "decisions": ["backend Python", "  "],  # pusty pomijany
        "preferences": ["FastAPI"],
        "notes": ["deadline"],
        "summary": "sesja o RAG",
    })

    assert count == 3
    assert calls["dec"] == ["backend Python"]
    assert calls["pref"] == ["FastAPI"]
    assert calls["note"] == ["deadline"]
    assert calls["sess"] == ["sesja o RAG"]


def test_save_suggestions_empty_returns_zero(monkeypatch):
    import memory_update as mu
    monkeypatch.setattr(mu, "save_session", lambda v: None)
    assert ms.save_suggestions({}) == 0


# ── interactive_confirm ──────────────────────────────────────────────────────

def test_interactive_confirm_accepts_and_rejects(monkeypatch):
    answers = iter(["t", "n"])
    monkeypatch.setattr("builtins.input", lambda *a: next(answers))
    out = ms.interactive_confirm({
        "decisions": ["zachowaj to"],
        "preferences": ["odrzuć to"],
        "notes": [],
        "summary": "podsumowanie",
    })
    assert out["decisions"] == ["zachowaj to"]
    assert out["preferences"] == []
    assert out["summary"] == "podsumowanie"


def test_interactive_confirm_empty_answer_means_yes(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *a: "")
    out = ms.interactive_confirm({"notes": ["domyślnie tak"]})
    assert out["notes"] == ["domyślnie tak"]


# ── _ollama (ścieżka błędu) ──────────────────────────────────────────────────

def test_ollama_returns_empty_on_error(monkeypatch):
    def boom(*a, **k):
        raise OSError("brak Ollama")
    monkeypatch.setattr(ms.urllib.request, "urlopen", boom)
    assert ms._ollama("cokolwiek") == ""


# ── run (ścieżki wczesnego wyjścia) ──────────────────────────────────────────

def test_run_no_transcript_returns_silently(monkeypatch):
    monkeypatch.delenv("CLAUDE_TRANSCRIPT_PATH", raising=False)
    ms.run(transcript_path="")  # brak wyjątku = OK


def test_run_short_conversation_skipped(tmp_path, monkeypatch):
    t = tmp_path / "t.json"
    t.write_text(json.dumps([{"role": "user", "content": "hej"}]),
                 encoding="utf-8")
    called = []
    monkeypatch.setattr(ms, "_ollama", lambda p: called.append(p) or "")
    ms.run(transcript_path=str(t))
    assert called == []  # za krótka rozmowa, Ollama nie wywołana
