"""Testy scripts/training_generate.py — load_profile_summary, save_pairs."""
import json

import pytest

import training_generate as tg


@pytest.fixture
def isolated_gen(tmp_path, monkeypatch):
    mem = tmp_path / "memory"
    mem.mkdir()
    training = tmp_path / "training"
    training.mkdir()
    raw = training / "raw_pairs.jsonl"
    monkeypatch.setattr(tg, "MEMORY_DIR", mem)
    monkeypatch.setattr(tg, "TRAINING_DIR", training)
    monkeypatch.setattr(tg, "RAW_FILE", raw)
    return {"mem": mem, "training": training, "raw": raw}


# ── load_profile_summary ──────────────────────────────────────────────────────

def test_load_profile_summary_empty_returns_default(isolated_gen):
    summary = tg.load_profile_summary()
    assert "Marcel" in summary or "TireQ" in summary


def test_load_profile_summary_with_preferences(isolated_gen):
    profile = {
        "patterns": {"preferred_solutions": ["FastAPI", "Python"], "avoided_approaches": []},
        "notes": []
    }
    (isolated_gen["mem"] / "profile.json").write_text(
        json.dumps(profile), encoding="utf-8"
    )
    summary = tg.load_profile_summary()
    assert "FastAPI" in summary
    assert "Preferencje" in summary


def test_load_profile_summary_with_notes(isolated_gen):
    profile = {
        "patterns": {"preferred_solutions": [], "avoided_approaches": []},
        "notes": [{"date": "2026-01-01T10:00", "note": "deadline w czerwcu"}]
    }
    (isolated_gen["mem"] / "profile.json").write_text(
        json.dumps(profile), encoding="utf-8"
    )
    summary = tg.load_profile_summary()
    assert "deadline" in summary


def test_load_profile_summary_with_decisions(isolated_gen):
    decisions = {
        "decisions": [
            {"date": "2026-01-01T09:00", "decision": "backend Python"},
            {"date": "2026-01-02T09:00", "decision": "frontend React"},
        ]
    }
    (isolated_gen["mem"] / "decisions.json").write_text(
        json.dumps(decisions), encoding="utf-8"
    )
    summary = tg.load_profile_summary()
    assert "backend Python" in summary or "frontend React" in summary


def test_load_profile_summary_caps_at_five_prefs(isolated_gen):
    prefs = [f"pref_{i}" for i in range(10)]
    profile = {
        "patterns": {"preferred_solutions": prefs, "avoided_approaches": []},
        "notes": []
    }
    (isolated_gen["mem"] / "profile.json").write_text(
        json.dumps(profile), encoding="utf-8"
    )
    summary = tg.load_profile_summary()
    assert "pref_5" not in summary  # max 5 preferencji


# ── save_pairs ────────────────────────────────────────────────────────────────

def _make_pair(uid: str) -> dict:
    return {
        "id": uid,
        "collected_at": "2026-01-01T12:00:00",
        "score": 0.75,
        "source": "synthetic",
        "messages": [
            {"role": "user", "content": "pytanie"},
            {"role": "assistant", "content": "odpowiedź"}
        ]
    }


def test_save_pairs_empty_returns_zero(isolated_gen):
    assert tg.save_pairs([]) == 0


def test_save_pairs_writes_new(isolated_gen):
    pairs = [_make_pair("abc123"), _make_pair("def456")]
    count = tg.save_pairs(pairs)
    assert count == 2
    lines = isolated_gen["raw"].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_save_pairs_deduplicates(isolated_gen):
    pairs = [_make_pair("abc123")]
    tg.save_pairs(pairs)
    count = tg.save_pairs(pairs)  # te same
    assert count == 0
    lines = isolated_gen["raw"].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1


def test_save_pairs_appends_new_only(isolated_gen):
    tg.save_pairs([_make_pair("aaa")])
    count = tg.save_pairs([_make_pair("aaa"), _make_pair("bbb")])
    assert count == 1
    lines = isolated_gen["raw"].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_save_pairs_creates_dir_if_needed(tmp_path, monkeypatch):
    new_dir = tmp_path / "new_training"
    raw = new_dir / "raw_pairs.jsonl"
    monkeypatch.setattr(tg, "TRAINING_DIR", new_dir)
    monkeypatch.setattr(tg, "RAW_FILE", raw)
    count = tg.save_pairs([_make_pair("xyz")])
    assert count == 1
    assert raw.exists()


def test_save_pairs_handles_corrupt_existing_line(isolated_gen):
    isolated_gen["raw"].write_text("not json\n", encoding="utf-8")
    count = tg.save_pairs([_make_pair("fresh")])
    assert count == 1


# ── generate_pairs fallbacks ──────────────────────────────────────────────────

def test_generate_pairs_missing_anthropic(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "anthropic":
            raise ImportError("no anthropic")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    result = tg.generate_pairs(5)
    assert result == []


def test_generate_pairs_missing_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = tg.generate_pairs(5)
    assert result == []
