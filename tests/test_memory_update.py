"""Testy scripts/memory_update.py — add_decision, add_preference, add_note, add_task, save_session."""
import json

import pytest

import memory_update as mu


PROFILE_TEMPLATE = {
    "user": {"name": "Marcel", "alias": "TireQ"},
    "preferences": {"frameworks": ["FastAPI"]},
    "patterns": {"preferred_solutions": [], "common_tasks": []},
    "notes": [],
}

DECISIONS_TEMPLATE = {"decisions": []}


@pytest.fixture
def isolated_update(tmp_path, monkeypatch):
    mem = tmp_path / "memory"
    mem.mkdir()
    sessions = mem / "sessions"
    sessions.mkdir()
    profile = mem / "profile.json"
    decisions = mem / "decisions.json"
    profile.write_text(json.dumps(PROFILE_TEMPLATE), encoding="utf-8")
    decisions.write_text(json.dumps(DECISIONS_TEMPLATE), encoding="utf-8")
    monkeypatch.setattr(mu, "MEMORY_DIR", mem)
    monkeypatch.setattr(mu, "PROFILE_FILE", profile)
    monkeypatch.setattr(mu, "DECISIONS_FILE", decisions)
    monkeypatch.setattr(mu, "SESSIONS_DIR", sessions)
    return {"mem": mem, "profile": profile, "decisions": decisions, "sessions": sessions}


# ── load_json / save_json ─────────────────────────────────────────────────────

def test_save_and_load_json_roundtrip(isolated_update):
    path = isolated_update["mem"] / "test.json"
    mu.save_json(path, {"x": 42})
    assert mu.load_json(path) == {"x": 42}


# ── add_decision ──────────────────────────────────────────────────────────────

def test_add_decision_appends(isolated_update):
    mu.add_decision("backend Python")
    data = json.loads(isolated_update["decisions"].read_text())
    assert len(data["decisions"]) == 1
    assert data["decisions"][0]["decision"] == "backend Python"


def test_add_decision_has_date(isolated_update):
    mu.add_decision("backend Python")
    data = json.loads(isolated_update["decisions"].read_text())
    assert "T" in data["decisions"][0]["date"]


def test_add_decision_multiple(isolated_update):
    mu.add_decision("decyzja A")
    mu.add_decision("decyzja B")
    data = json.loads(isolated_update["decisions"].read_text())
    assert len(data["decisions"]) == 2


# ── add_preference ────────────────────────────────────────────────────────────

def test_add_preference_new(isolated_update):
    mu.add_preference("pytest nad unittest")
    profile = json.loads(isolated_update["profile"].read_text())
    assert "pytest nad unittest" in profile["patterns"]["preferred_solutions"]


def test_add_preference_not_duplicated_from_preferred(isolated_update):
    mu.add_preference("FastAPI")  # "FastAPI" jest w preferences.frameworks
    profile = json.loads(isolated_update["profile"].read_text())
    # nie powinno trafić do preferred_solutions (już jest w frameworks)
    assert profile["patterns"]["preferred_solutions"].count("FastAPI") == 0


def test_add_preference_idempotent(isolated_update):
    mu.add_preference("nowa pref")
    mu.add_preference("nowa pref")
    profile = json.loads(isolated_update["profile"].read_text())
    assert profile["patterns"]["preferred_solutions"].count("nowa pref") == 1


# ── add_note ──────────────────────────────────────────────────────────────────

def test_add_note_appends(isolated_update):
    mu.add_note("deadline w czerwcu")
    profile = json.loads(isolated_update["profile"].read_text())
    assert len(profile["notes"]) == 1
    assert profile["notes"][0]["note"] == "deadline w czerwcu"


def test_add_note_has_date(isolated_update):
    mu.add_note("ważna notatka")
    profile = json.loads(isolated_update["profile"].read_text())
    assert "T" in profile["notes"][0]["date"]


def test_add_note_multiple(isolated_update):
    mu.add_note("notatka 1")
    mu.add_note("notatka 2")
    profile = json.loads(isolated_update["profile"].read_text())
    assert len(profile["notes"]) == 2


# ── add_task ──────────────────────────────────────────────────────────────────

def test_add_task_adds_new(isolated_update):
    mu.add_task("budowanie REST API")
    profile = json.loads(isolated_update["profile"].read_text())
    assert "budowanie REST API" in profile["patterns"]["common_tasks"]


def test_add_task_not_duplicated(isolated_update):
    mu.add_task("to samo zadanie")
    mu.add_task("to samo zadanie")
    profile = json.loads(isolated_update["profile"].read_text())
    assert profile["patterns"]["common_tasks"].count("to samo zadanie") == 1


# ── save_session ──────────────────────────────────────────────────────────────

def test_save_session_creates_file(isolated_update):
    mu.save_session("praca nad testami jednostkowymi")
    files = list(isolated_update["sessions"].glob("*.json"))
    assert len(files) == 1


def test_save_session_content(isolated_update):
    mu.save_session("podsumowanie sesji RAG")
    files = list(isolated_update["sessions"].glob("*.json"))
    data = json.loads(files[0].read_text())
    assert data["summary"] == "podsumowanie sesji RAG"
    assert "date" in data


def test_save_session_filename_format(isolated_update):
    mu.save_session("test")
    files = list(isolated_update["sessions"].glob("*.json"))
    name = files[0].name
    # format: YYYY-MM-DD_HH-MM.json
    assert len(name) == len("2026-05-17_12-30.json")
    assert name[4] == "-" and name[7] == "-" and name[10] == "_"


# ── show_memory ───────────────────────────────────────────────────────────────

def test_show_memory_prints_user(isolated_update, capsys):
    mu.add_decision("decyzja testowa")
    mu.show_memory()
    out = capsys.readouterr().out
    assert "Marcel" in out
    assert "TireQ" in out


def test_show_memory_prints_decisions(isolated_update, capsys):
    mu.add_decision("backend Python")
    mu.show_memory()
    out = capsys.readouterr().out
    assert "backend Python" in out


def test_show_memory_prints_notes(isolated_update, capsys):
    mu.add_note("deadline w grudniu")
    mu.show_memory()
    out = capsys.readouterr().out
    assert "deadline w grudniu" in out
