"""Testy scripts/memory_cleanup.py — konsolidacja, archiwizacja, deduplikacja."""
import json
from datetime import datetime, timedelta

import pytest

import memory_cleanup as mc


@pytest.fixture
def isolated_memory(tmp_path, monkeypatch):
    """Przekierowuje stałe modułu na izolowany katalog."""
    mem = tmp_path / "memory"
    sessions = mem / "sessions"
    archive = mem / "archive"
    sessions.mkdir(parents=True)
    monkeypatch.setattr(mc, "MEMORY_DIR", mem)
    monkeypatch.setattr(mc, "PROFILE_FILE", mem / "profile.json")
    monkeypatch.setattr(mc, "DECISIONS_FILE", mem / "decisions.json")
    monkeypatch.setattr(mc, "SESSIONS_DIR", sessions)
    monkeypatch.setattr(mc, "ARCHIVE_DIR", archive)
    return mem


def _iso(days_ago: int) -> str:
    return (datetime.now() - timedelta(days=days_ago)).isoformat()


def test_normalize_collapses_whitespace_and_lowercases():
    assert mc.normalize("  Hello   WORLD\n\t ") == "hello world"


def test_deduplicate_removes_near_identical():
    items = [
        {"decision": "backend w Pythonie z FastAPI"},
        {"decision": "Backend w  Pythonie z FastAPI"},  # near-dup
        {"decision": "frontend w React"},
    ]
    unique = mc.deduplicate(items, lambda x: x["decision"])
    assert len(unique) == 2


def test_deduplicate_keeps_distinct_items():
    items = [{"t": "alfa"}, {"t": "beta"}, {"t": "gamma"}]
    assert len(mc.deduplicate(items, lambda x: x["t"])) == 3


def test_cleanup_decisions_archives_old_and_dedups(isolated_memory):
    decisions = {
        "decisions": [
            {"decision": "stara decyzja", "date": _iso(60)},
            {"decision": "swieza decyzja", "date": _iso(2)},
            {"decision": "swieza decyzja", "date": _iso(1)},  # duplikat
        ]
    }
    mc.DECISIONS_FILE.write_text(json.dumps(decisions), encoding="utf-8")

    before, after = mc.cleanup_decisions()

    assert before == 3
    assert after == 1  # tylko jedna świeża po dedupie

    remaining = json.loads(mc.DECISIONS_FILE.read_text())["decisions"]
    assert all("swieza" in d["decision"] for d in remaining)

    archive_file = mc.ARCHIVE_DIR / f"decisions_{datetime.now():%Y-%m}.json"
    assert archive_file.exists()
    archived = json.loads(archive_file.read_text())["decisions"]
    assert archived[0]["decision"] == "stara decyzja"


def test_cleanup_decisions_keeps_unparseable_dates_fresh(isolated_memory):
    mc.DECISIONS_FILE.write_text(json.dumps({
        "decisions": [{"decision": "bez daty", "date": "niepoprawna"}]
    }), encoding="utf-8")

    before, after = mc.cleanup_decisions()
    assert before == after == 1


def test_cleanup_profile_dedups_prefs_and_archives_notes(isolated_memory):
    profile = {
        "patterns": {"preferred_solutions": ["FastAPI", "FastAPI", "Docker"]},
        "notes": [
            {"note": "stara notatka", "date": _iso(90)},
            {"note": "nowa notatka", "date": _iso(3)},
        ],
    }
    mc.PROFILE_FILE.write_text(json.dumps(profile), encoding="utf-8")

    n_before, n_after = mc.cleanup_profile()

    assert n_before == 2
    assert n_after == 1  # stara zarchiwizowana

    saved = json.loads(mc.PROFILE_FILE.read_text())
    assert saved["patterns"]["preferred_solutions"] == ["FastAPI", "Docker"]
    assert saved["notes"][0]["note"] == "nowa notatka"

    archive_file = mc.ARCHIVE_DIR / f"notes_{datetime.now():%Y-%m}.json"
    assert archive_file.exists()


def test_consolidate_sessions_archives_old_and_unlinks(isolated_memory):
    old = mc.SESSIONS_DIR / "old.json"
    fresh = mc.SESSIONS_DIR / "fresh.json"
    old.write_text(json.dumps({"date": _iso(45), "summary": "stara sesja"}),
                   encoding="utf-8")
    fresh.write_text(json.dumps({"date": _iso(1), "summary": "swieza sesja"}),
                     encoding="utf-8")

    archived = mc.consolidate_sessions()

    assert archived == 1
    assert not old.exists()
    assert fresh.exists()


def test_consolidate_sessions_no_dir_returns_zero(isolated_memory, monkeypatch):
    monkeypatch.setattr(mc, "SESSIONS_DIR", isolated_memory / "nope")
    assert mc.consolidate_sessions() == 0


def test_load_json_missing_returns_empty(tmp_path):
    assert mc.load_json(tmp_path / "ghost.json") == {}


def test_save_json_creates_parent_dirs(tmp_path):
    target = tmp_path / "deep" / "nested" / "f.json"
    mc.save_json(target, {"ok": True})
    assert json.loads(target.read_text())["ok"] is True
