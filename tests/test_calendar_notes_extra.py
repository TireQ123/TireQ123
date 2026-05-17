"""Testy calendar_plugin i notes_plugin — brakujące gałęzie."""
from datetime import datetime, timedelta

import pytest

from jarvis.plugins import calendar_plugin as cp
from jarvis.plugins import notes_plugin as npl


@pytest.fixture
def cal(tmp_path, monkeypatch):
    f = tmp_path / "calendar.json"
    monkeypatch.setattr(cp, "CALENDAR_FILE", f)
    return f


@pytest.fixture
def notes(tmp_path, monkeypatch):
    d = tmp_path / "notes"
    monkeypatch.setattr(npl, "NOTES_DIR", d)
    return d


# ── calendar: _load / _save ───────────────────────────────────────────────────

def test_load_missing_file_returns_empty(cal):
    assert cp._load() == []


def test_save_sorts_by_datetime(cal):
    events = [
        {"id": "b", "datetime": "2026-06-02T10:00:00", "title": "B", "notes": "", "created": "x"},
        {"id": "a", "datetime": "2026-06-01T10:00:00", "title": "A", "notes": "", "created": "x"},
    ]
    cp._save(events)
    loaded = cp._load()
    assert loaded[0]["id"] == "a"
    assert loaded[1]["id"] == "b"


# ── calendar_add ──────────────────────────────────────────────────────────────

def test_calendar_add_deduplicates_same_id(cal):
    future = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
    cp.calendar_add("Spotkanie", future)
    cp.calendar_add("Spotkanie", future)  # ta sama — id identyczne
    assert len(cp._load()) == 1


def test_calendar_add_with_notes(cal):
    future = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
    cp.calendar_add("Event", future, notes="Ważne notatki")
    event = cp._load()[0]
    assert event["notes"] == "Ważne notatki"


# ── calendar_list ─────────────────────────────────────────────────────────────

def test_calendar_list_no_events(cal):
    result = cp.calendar_list(days=7)
    assert result["status"] == "ok"
    assert "Brak" in result["result"]


def test_calendar_list_shows_notes_in_output(cal):
    future = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
    cp.calendar_add("Prezentacja", future, notes="Sala 3A")
    result = cp.calendar_list(days=7)
    assert "Sala 3A" in result["result"]


def test_calendar_list_past_event_not_shown(cal):
    past = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
    cp.calendar_add("Stary event", past)
    result = cp.calendar_list(days=7)
    assert "Brak" in result["result"]


def test_calendar_list_custom_days(cal):
    soon = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d %H:%M")
    far = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
    cp.calendar_add("Blisko", soon)
    cp.calendar_add("Daleko", far)
    result = cp.calendar_list(days=7)
    assert "Blisko" in result["result"]
    assert "Daleko" not in result["result"]


# ── calendar_today ────────────────────────────────────────────────────────────

def test_calendar_today_no_events(cal):
    result = cp.calendar_today()
    assert result["status"] == "ok"
    assert "Brak" in result["result"]


def test_calendar_today_with_today_event(cal):
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    cp.calendar_add("Dzisiejsze spotkanie", today_str)
    result = cp.calendar_today()
    assert "Dzisiejsze spotkanie" in result["result"]


def test_calendar_today_excludes_tomorrow(cal):
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
    cp.calendar_add("Jutrzejsze", tomorrow)
    result = cp.calendar_today()
    assert "Brak" in result["result"]


# ── calendar_delete ───────────────────────────────────────────────────────────

def test_calendar_delete_nothing_matched(cal):
    future = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
    cp.calendar_add("Spotkanie", future)
    result = cp.calendar_delete("coś nieistniejącego xyz")
    assert "0" in result["result"]
    assert len(cp._load()) == 1


# ── calendar_remind ───────────────────────────────────────────────────────────

def test_calendar_remind_no_events(cal):
    result = cp.calendar_remind()
    assert "Brak" in result["result"]


def test_calendar_remind_with_upcoming(cal):
    soon = (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
    cp.calendar_add("Pilne spotkanie", soon)
    result = cp.calendar_remind()
    assert "Pilne spotkanie" in result["result"]


def test_calendar_remind_excludes_far_future(cal):
    far = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d %H:%M")
    cp.calendar_add("Dalekie", far)
    result = cp.calendar_remind()
    assert "Brak" in result["result"]


# ── notes: note_list z plikami ────────────────────────────────────────────────

def test_note_list_with_files(notes):
    notes.mkdir()
    (notes / "20260517_test.md").write_text("# Tytuł notatki\nTreść.", encoding="utf-8")
    result = npl.note_list()
    assert result["status"] == "ok"
    assert len(result["result"]) == 1
    assert result["result"][0]["title"] == "Tytuł notatki"


def test_note_list_returns_newest_first(notes):
    notes.mkdir()
    (notes / "20260515_stara.md").write_text("# Stara\nTreść.", encoding="utf-8")
    (notes / "20260517_nowa.md").write_text("# Nowa\nTreść.", encoding="utf-8")
    result = npl.note_list()
    assert result["result"][0]["file"] == "20260517_nowa.md"


# ── notes: note_read ──────────────────────────────────────────────────────────

def test_note_read_existing(notes):
    notes.mkdir()
    (notes / "test.md").write_text("# Test\nTreść notatki.", encoding="utf-8")
    result = npl.note_read("test.md")
    assert result["status"] == "ok"
    assert "Treść notatki" in result["result"]


def test_note_read_missing_returns_error(notes):
    notes.mkdir()
    result = npl.note_read("nieistnieje.md")
    assert result["status"] == "error"
    assert "nie istnieje" in result["result"]


# ── notes: note_search bez katalogu ──────────────────────────────────────────

def test_note_search_no_dir(notes):
    # notes dir nie istnieje
    result = npl.note_search("cokolwiek")
    assert result["status"] == "ok"
    assert result["result"] == []


def test_note_search_no_match(notes):
    notes.mkdir()
    npl.note_create("Notatka o Pythonie", "FastAPI, SQLAlchemy, pytest")
    result = npl.note_search("blockchain")
    assert result["result"] == []


def test_note_search_multiple_keywords(notes):
    notes.mkdir()
    npl.note_create("Tech stack", "Python z FastAPI i PostgreSQL")
    result = npl.note_search("FastAPI PostgreSQL")
    assert len(result["result"]) == 1
