"""Testy scripts/memory_sync.py — normalize, similarity, extract, merge, throttle."""
import json
from datetime import datetime, timedelta

import pytest

import memory_sync as ms


@pytest.fixture
def isolated_sync(tmp_path, monkeypatch):
    mem = tmp_path / "memory"
    mem.mkdir()
    profile = mem / "profile.json"
    decisions = mem / "decisions.json"
    state = mem / ".sync_state.json"
    profile.write_text(json.dumps({
        "patterns": {"preferred_solutions": []},
        "notes": [],
    }), encoding="utf-8")
    decisions.write_text(json.dumps({"decisions": []}), encoding="utf-8")
    monkeypatch.setattr(ms, "MEMORY_DIR", mem)
    monkeypatch.setattr(ms, "PROFILE_FILE", profile)
    monkeypatch.setattr(ms, "DECISIONS_FILE", decisions)
    monkeypatch.setattr(ms, "STATE_FILE", state)
    return {"mem": mem, "profile": profile, "decisions": decisions, "state": state}


# ── normalize ─────────────────────────────────────────────────────────────────

def test_normalize_lowercase():
    assert ms.normalize("FastAPI") == "fastapi"


def test_normalize_strips_whitespace():
    assert ms.normalize("  hello  ") == "hello"


def test_normalize_collapses_spaces():
    assert ms.normalize("a  b   c") == "a b c"


def test_normalize_unicode():
    # NFKD+lower: litery polskie pozostają polskie (ł nie rozkłada się na l)
    result = ms.normalize("Łódź")
    assert result == result.lower()          # zawsze lowercase
    assert result == result.strip()          # bez białych znaków na końcach


# ── similarity ────────────────────────────────────────────────────────────────

def test_similarity_identical():
    assert ms.similarity("FastAPI", "FastAPI") == 1.0


def test_similarity_different():
    assert ms.similarity("FastAPI", "Django") < 0.5


def test_similarity_near_match():
    score = ms.similarity("używamy FastAPI", "używamy FastAPI do API")
    assert score > 0.7


# ── is_duplicate ──────────────────────────────────────────────────────────────

def test_is_duplicate_exact_match():
    assert ms.is_duplicate("FastAPI", ["FastAPI", "Django"])


def test_is_duplicate_not_found():
    assert not ms.is_duplicate("Flask", ["FastAPI", "Django"])


def test_is_duplicate_near_match_above_threshold():
    existing = ["backend w Pythonie i FastAPI"]
    assert ms.is_duplicate("backend w Pythonie i FastAPI", existing)


def test_is_duplicate_empty_existing():
    assert not ms.is_duplicate("cokolwiek", [])


# ── should_sync / mark_synced ─────────────────────────────────────────────────

def test_should_sync_no_state_file(isolated_sync):
    assert ms.should_sync() is True


def test_should_sync_just_synced(isolated_sync):
    ms.mark_synced()
    assert ms.should_sync() is False


def test_should_sync_old_state(isolated_sync):
    old_time = (datetime.now() - timedelta(seconds=300)).isoformat(timespec="seconds")
    ms.save_json(isolated_sync["state"], {"last_sync": old_time})
    assert ms.should_sync() is True


def test_mark_synced_writes_state(isolated_sync):
    ms.mark_synced()
    state = json.loads(isolated_sync["state"].read_text())
    assert "last_sync" in state


# ── extract_from_transcript ───────────────────────────────────────────────────

def test_extract_decisions_from_transcript(tmp_path):
    t = tmp_path / "t.json"
    t.write_text(json.dumps([
        {"role": "user", "content": "używamy FastAPI do nowego projektu"},
        {"role": "assistant", "content": "Dobrze, Panie TireQ."},
    ]), encoding="utf-8")
    result = ms.extract_from_transcript(str(t))
    assert any("FastAPI" in d for d in result["decisions"])


def test_extract_preferences_from_transcript(tmp_path):
    t = tmp_path / "t.json"
    t.write_text(json.dumps([
        {"role": "user", "content": "preferuję TypeScript nad JavaScript"},
    ]), encoding="utf-8")
    result = ms.extract_from_transcript(str(t))
    assert any("TypeScript" in p for p in result["preferences"])


def test_extract_notes_from_transcript(tmp_path):
    t = tmp_path / "t.json"
    t.write_text(json.dumps([
        {"role": "user", "content": "deadline: projekt X do 2026-06-01"},
    ]), encoding="utf-8")
    result = ms.extract_from_transcript(str(t))
    assert any("projekt X" in n for n in result["notes"])


def test_extract_missing_file_returns_empty(tmp_path):
    result = ms.extract_from_transcript(str(tmp_path / "ghost.json"))
    assert result == {"decisions": [], "preferences": [], "notes": []}


def test_extract_messages_key_format(tmp_path):
    t = tmp_path / "t.json"
    t.write_text(json.dumps({"messages": [
        {"role": "user", "content": "używamy PostgreSQL jako baza danych"},
    ]}), encoding="utf-8")
    result = ms.extract_from_transcript(str(t))
    assert any("PostgreSQL" in d for d in result["decisions"])


def test_extract_content_blocks(tmp_path):
    t = tmp_path / "t.json"
    t.write_text(json.dumps([
        {"role": "user", "content": [
            {"type": "text", "text": "preferuję pytest nad unittest"},
        ]},
    ]), encoding="utf-8")
    result = ms.extract_from_transcript(str(t))
    assert any("pytest" in p for p in result["preferences"])


# ── merge_decisions ───────────────────────────────────────────────────────────

def test_merge_decisions_adds_new(isolated_sync):
    count = ms.merge_decisions(["backend Python"])
    assert count == 1
    data = json.loads(isolated_sync["decisions"].read_text())
    assert data["decisions"][0]["decision"] == "backend Python"


def test_merge_decisions_deduplicates(isolated_sync):
    ms.merge_decisions(["backend Python"])
    count = ms.merge_decisions(["backend Python"])
    assert count == 0
    data = json.loads(isolated_sync["decisions"].read_text())
    assert len(data["decisions"]) == 1


def test_merge_decisions_source_auto(isolated_sync):
    ms.merge_decisions(["nowa decyzja"])
    data = json.loads(isolated_sync["decisions"].read_text())
    assert data["decisions"][0]["source"] == "auto"


def test_merge_decisions_archives_overflow(isolated_sync, monkeypatch):
    monkeypatch.setattr(ms, "MAX_DECISIONS", 3)
    items = ["backend Python", "frontend React", "baza PostgreSQL", "cache Redis", "kolejka Celery"]
    ms.merge_decisions(items)
    data = json.loads(isolated_sync["decisions"].read_text())
    assert len(data["decisions"]) == 3


def test_merge_decisions_missing_decisions_key(isolated_sync):
    isolated_sync["decisions"].write_text(json.dumps({}), encoding="utf-8")
    count = ms.merge_decisions(["test"])
    assert count == 1


# ── merge_profile ─────────────────────────────────────────────────────────────

def test_merge_profile_adds_pref(isolated_sync):
    count = ms.merge_profile(["FastAPI"], [])
    assert count == 1
    profile = json.loads(isolated_sync["profile"].read_text())
    assert "FastAPI" in profile["patterns"]["preferred_solutions"]


def test_merge_profile_adds_note(isolated_sync):
    count = ms.merge_profile([], ["deadline w czerwcu"])
    assert count == 1
    profile = json.loads(isolated_sync["profile"].read_text())
    assert profile["notes"][0]["note"] == "deadline w czerwcu"


def test_merge_profile_deduplicates_pref(isolated_sync):
    ms.merge_profile(["FastAPI"], [])
    count = ms.merge_profile(["FastAPI"], [])
    assert count == 0


def test_merge_profile_caps_prefs(isolated_sync, monkeypatch):
    monkeypatch.setattr(ms, "MAX_PREFERRED", 3)
    prefs = ["FastAPI", "PostgreSQL", "Docker", "pytest", "Redis"]
    ms.merge_profile(prefs, [])
    profile = json.loads(isolated_sync["profile"].read_text())
    assert len(profile["patterns"]["preferred_solutions"]) == 3


def test_merge_profile_caps_notes(isolated_sync, monkeypatch):
    monkeypatch.setattr(ms, "MAX_NOTES", 2)
    notes = ["deadline w czerwcu", "backend w Pythonie", "frontend w React", "deploy na piątek"]
    ms.merge_profile([], notes)
    profile = json.loads(isolated_sync["profile"].read_text())
    assert len(profile["notes"]) == 2


# ── main ─────────────────────────────────────────────────────────────────────

def test_main_skips_when_throttled(isolated_sync, monkeypatch):
    ms.mark_synced()
    called = []
    monkeypatch.setattr(ms, "extract_from_transcript", lambda p: called.append(p) or {})
    ms.main()
    assert called == []


def test_main_skips_when_no_transcript(isolated_sync, monkeypatch):
    monkeypatch.delenv("CLAUDE_TRANSCRIPT_PATH", raising=False)
    # Nie powinno rzucić wyjątku
    ms.main()
    assert isolated_sync["state"].exists()


def test_main_processes_transcript(tmp_path, isolated_sync, monkeypatch):
    t = tmp_path / "t.json"
    t.write_text(json.dumps([
        {"role": "user", "content": "używamy Redis jako cache"},
    ]), encoding="utf-8")
    monkeypatch.setenv("CLAUDE_TRANSCRIPT_PATH", str(t))
    ms.main()
    data = json.loads(isolated_sync["decisions"].read_text())
    assert len(data["decisions"]) >= 1
