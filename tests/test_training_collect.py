"""Testy scripts/training_collect.py — extract_text, is_quality_pair, score_pair, extract_pairs, append_pairs."""
import json

import pytest

import training_collect as tc


@pytest.fixture
def isolated_collect(tmp_path, monkeypatch):
    training = tmp_path / "training"
    training.mkdir()
    raw = training / "raw_pairs.jsonl"
    mem = tmp_path / "memory"
    sessions = mem / "sessions"
    sessions.mkdir(parents=True)
    monkeypatch.setattr(tc, "TRAINING_DIR", training)
    monkeypatch.setattr(tc, "RAW_FILE", raw)
    monkeypatch.setattr(tc, "MEMORY_DIR", mem)
    return {"training": training, "raw": raw, "sessions": sessions}


# ── extract_text ──────────────────────────────────────────────────────────────

def test_extract_text_string():
    assert tc.extract_text("zwykły tekst") == "zwykły tekst"


def test_extract_text_list_of_blocks():
    blocks = [
        {"type": "text", "text": "pierwszy"},
        {"type": "image", "url": "x"},
        {"type": "text", "text": "drugi"},
    ]
    result = tc.extract_text(blocks)
    assert "pierwszy" in result
    assert "drugi" in result


def test_extract_text_empty_list():
    assert tc.extract_text([]) == ""


def test_extract_text_unknown_type():
    assert tc.extract_text(42) == ""


# ── is_quality_pair ───────────────────────────────────────────────────────────

def test_is_quality_pair_good():
    user = "jak zrobić API?"
    assistant = "Panie TireQ, " + "x" * 100
    assert tc.is_quality_pair(user, assistant)


def test_is_quality_pair_too_short_assistant():
    assert not tc.is_quality_pair("pytanie?", "krótka odpowiedź")


def test_is_quality_pair_too_long_total():
    user = "u" * 4001
    assistant = "a" * 4001
    assert not tc.is_quality_pair(user, assistant)


def test_is_quality_pair_only_code_block():
    user = "pokaż"
    assistant = "```\necho hello\n```"
    assert not tc.is_quality_pair(user, assistant)


def test_is_quality_pair_code_with_text():
    user = "jak?"
    assistant = "Panie TireQ, oto kod:\n```python\nprint('ok')\n```\n" + "x" * 80
    assert tc.is_quality_pair(user, assistant)


# ── score_pair ────────────────────────────────────────────────────────────────

def test_score_pair_base_is_half():
    score = tc.score_pair("q", "x" * 200)
    assert 0.0 <= score <= 1.0


def test_score_pair_longer_is_better():
    short = tc.score_pair("q", "Panie TireQ, " + "x" * 50)
    long_ = tc.score_pair("q", "Panie TireQ, " + "x" * 500)
    assert long_ >= short


def test_score_pair_code_bonus():
    without_code = tc.score_pair("q", "Panie TireQ, odpowiedź " + "x" * 80)
    with_code = tc.score_pair("q", "Panie TireQ, odpowiedź\n```python\ncode\n```\n" + "x" * 80)
    assert with_code > without_code


def test_score_pair_polish_words_boost():
    polish = tc.score_pair("q", "Panie TireQ, jest tak że nie ma " + "x" * 80)
    nonpolish = tc.score_pair("q", "hello world here " + "x" * 80)
    assert polish > nonpolish


def test_score_pair_capped_at_one():
    score = tc.score_pair("q", "Panie TireQ, " * 50 + "```python\ncode\n```")
    assert score <= 1.0


# ── extract_pairs ─────────────────────────────────────────────────────────────

def _make_messages(pairs):
    msgs = []
    for user, assistant in pairs:
        msgs.append({"role": "user", "content": user})
        msgs.append({"role": "assistant", "content": assistant})
    return msgs


def test_extract_pairs_basic():
    msgs = _make_messages([
        ("jak zrobić API?", "Panie TireQ, użyj FastAPI. " + "x" * 80),
    ])
    pairs = tc.extract_pairs(msgs)
    assert len(pairs) == 1
    assert pairs[0]["messages"][1]["content"] == "jak zrobić API?"


def test_extract_pairs_skips_low_quality():
    msgs = _make_messages([("q?", "za krótka")])
    assert tc.extract_pairs(msgs) == []


def test_extract_pairs_multiple():
    msgs = _make_messages([
        ("pytanie A?", "Panie TireQ, odpowiedź A " + "x" * 80),
        ("pytanie B?", "Panie TireQ, odpowiedź B " + "x" * 80),
    ])
    assert len(tc.extract_pairs(msgs)) == 2


def test_extract_pairs_system_message_ignored():
    msgs = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "pytanie"},
        {"role": "assistant", "content": "Panie TireQ, odpowiedź " + "x" * 80},
    ]
    pairs = tc.extract_pairs(msgs)
    assert len(pairs) == 1


def test_extract_pairs_id_deterministic():
    msgs = _make_messages([
        ("pytanie", "Panie TireQ, " + "x" * 80),
    ])
    pairs1 = tc.extract_pairs(msgs)
    pairs2 = tc.extract_pairs(msgs)
    assert pairs1[0]["id"] == pairs2[0]["id"]


def test_extract_pairs_has_score():
    msgs = _make_messages([("q?", "Panie TireQ, " + "x" * 80)])
    pairs = tc.extract_pairs(msgs)
    assert 0 <= pairs[0]["score"] <= 1.0


# ── load_existing_ids / append_pairs ─────────────────────────────────────────

def test_load_existing_ids_empty(isolated_collect):
    assert tc.load_existing_ids() == set()


def test_load_existing_ids_reads_file(isolated_collect):
    isolated_collect["raw"].write_text(
        json.dumps({"id": "abc123"}) + "\n", encoding="utf-8"
    )
    assert "abc123" in tc.load_existing_ids()


def test_load_existing_ids_skips_corrupt(isolated_collect):
    isolated_collect["raw"].write_text("nie json\n", encoding="utf-8")
    assert tc.load_existing_ids() == set()


def test_append_pairs_writes_new(isolated_collect):
    pair = {
        "id": "testid1",
        "collected_at": "2026-01-01T10:00:00",
        "score": 0.7,
        "messages": [{"role": "user", "content": "q"}]
    }
    count = tc.append_pairs([pair])
    assert count == 1
    lines = isolated_collect["raw"].read_text().strip().splitlines()
    assert len(lines) == 1


def test_append_pairs_skips_existing(isolated_collect):
    pair = {"id": "dup", "score": 0.7, "messages": []}
    tc.append_pairs([pair])
    count = tc.append_pairs([pair])
    assert count == 0


def test_append_pairs_empty_returns_zero(isolated_collect):
    assert tc.append_pairs([]) == 0


# ── collect_from_sessions ─────────────────────────────────────────────────────

def test_collect_from_sessions_no_dir(isolated_collect, monkeypatch):
    monkeypatch.setattr(tc, "MEMORY_DIR", isolated_collect["training"])  # brak sessions
    count = tc.collect_from_sessions()
    assert count == 0


def test_collect_from_sessions_with_summary(isolated_collect):
    (isolated_collect["sessions"] / "s.json").write_text(json.dumps({
        "date": "2026-05-01",
        "summary": "praca nad testami jednostkowymi — bardzo ważna sesja!"
    }), encoding="utf-8")
    count = tc.collect_from_sessions()
    assert count == 1


def test_collect_from_sessions_skips_no_summary(isolated_collect):
    (isolated_collect["sessions"] / "s.json").write_text(json.dumps({
        "date": "2026-05-01",
        "summary": ""
    }), encoding="utf-8")
    count = tc.collect_from_sessions()
    assert count == 0


# ── show_stats ────────────────────────────────────────────────────────────────

def test_show_stats_no_file(isolated_collect, capsys):
    tc.show_stats()
    assert "Brak" in capsys.readouterr().out


def test_show_stats_with_data(isolated_collect, capsys):
    pairs = [
        {"id": f"p{i}", "score": 0.7, "messages": []} for i in range(5)
    ]
    for p in pairs:
        isolated_collect["raw"].open("a", encoding="utf-8").write(
            json.dumps(p) + "\n"
        )
    tc.show_stats()
    out = capsys.readouterr().out
    assert "5" in out
    assert "score" in out.lower() or "Score" in out
