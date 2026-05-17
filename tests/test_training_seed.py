"""Testy scripts/training_seed.py — build_pair, main, deduplication."""
import hashlib
import json

import pytest

import training_seed as ts


# ── build_pair ───────────────────────────────────────────────────────────────

def test_build_pair_structure():
    p = ts.build_pair("jak zrobić API?", "Panie TireQ, FastAPI.")
    assert p["source"] == "seed"
    assert p["score"] == 0.75
    assert len(p["messages"]) == 3
    assert p["messages"][0]["role"] == "system"
    assert p["messages"][1]["role"] == "user"
    assert p["messages"][2]["role"] == "assistant"


def test_build_pair_id_deterministic():
    p1 = ts.build_pair("pytanie", "odpowiedź")
    p2 = ts.build_pair("pytanie", "odpowiedź")
    assert p1["id"] == p2["id"]


def test_build_pair_id_differs_for_different_content():
    p1 = ts.build_pair("pytanie A", "odpowiedź A")
    p2 = ts.build_pair("pytanie B", "odpowiedź B")
    assert p1["id"] != p2["id"]


def test_build_pair_id_length():
    p = ts.build_pair("x", "y")
    assert len(p["id"]) == 12


def test_build_pair_collected_at_format():
    p = ts.build_pair("q", "a")
    # ISO format: YYYY-MM-DDTHH:MM:SS
    assert "T" in p["collected_at"]
    assert len(p["collected_at"]) == 19


# ── PAIRS content ─────────────────────────────────────────────────────────────

def test_pairs_count():
    assert len(ts.PAIRS) >= 30


def test_pairs_all_nonempty():
    for user, assistant in ts.PAIRS:
        assert user.strip(), "Pusta wiadomość użytkownika"
        assert assistant.strip(), "Pusta odpowiedź asystenta"


def test_pairs_jarvis_style():
    for _, assistant in ts.PAIRS:
        assert "Panie TireQ" in assistant, f"Brak zwrotu 'Panie TireQ' w: {assistant[:60]}"


# ── main ─────────────────────────────────────────────────────────────────────

def test_main_writes_jsonl(tmp_path, monkeypatch):
    raw = tmp_path / "raw_pairs.jsonl"
    monkeypatch.setattr(ts, "TRAINING_DIR", tmp_path)
    monkeypatch.setattr(ts, "RAW_FILE", raw)
    ts.main()
    assert raw.exists()
    lines = raw.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == len(ts.PAIRS)


def test_main_skips_duplicates(tmp_path, monkeypatch):
    raw = tmp_path / "raw_pairs.jsonl"
    monkeypatch.setattr(ts, "TRAINING_DIR", tmp_path)
    monkeypatch.setattr(ts, "RAW_FILE", raw)
    ts.main()
    first_count = len(raw.read_text().strip().splitlines())
    ts.main()  # drugi raz — nie powinno dodać
    second_count = len(raw.read_text().strip().splitlines())
    assert first_count == second_count


def test_main_creates_training_dir(tmp_path, monkeypatch):
    new_dir = tmp_path / "training_new"
    raw = new_dir / "raw_pairs.jsonl"
    monkeypatch.setattr(ts, "TRAINING_DIR", new_dir)
    monkeypatch.setattr(ts, "RAW_FILE", raw)
    ts.main()
    assert new_dir.exists()
    assert raw.exists()


def test_main_valid_jsonl(tmp_path, monkeypatch):
    raw = tmp_path / "raw_pairs.jsonl"
    monkeypatch.setattr(ts, "TRAINING_DIR", tmp_path)
    monkeypatch.setattr(ts, "RAW_FILE", raw)
    ts.main()
    for line in raw.read_text(encoding="utf-8").strip().splitlines():
        obj = json.loads(line)
        assert "id" in obj
        assert "messages" in obj
        assert obj["source"] == "seed"
