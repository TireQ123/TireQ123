"""Testy pluginów — rejestr, kalendarz, notatki."""
from datetime import datetime, timedelta

import pytest

from jarvis.plugins import PluginRegistry, JarvisPlugin


def test_registry_loads_builtin_plugins():
    reg = PluginRegistry().load_all()
    names = reg.list_plugins()
    assert "calendar" in names
    assert "notes" in names


def test_registry_disabled_plugin_not_registered():
    reg = PluginRegistry()

    class Disabled(JarvisPlugin):
        name = "disabled_test"
        enabled = False

    reg.register(Disabled())
    assert "disabled_test" not in reg.list_plugins()


def test_calendar_add_and_list(tmp_path, monkeypatch):
    from jarvis.plugins import calendar_plugin as cp
    monkeypatch.setattr(cp, "CALENDAR_FILE", tmp_path / "calendar.json")

    future = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
    add = cp.calendar_add("Spotkanie z klientem", future)
    assert add["status"] == "ok"

    lst = cp.calendar_list(days=7)
    assert "Spotkanie z klientem" in lst["result"]


def test_calendar_add_invalid_date(tmp_path, monkeypatch):
    from jarvis.plugins import calendar_plugin as cp
    monkeypatch.setattr(cp, "CALENDAR_FILE", tmp_path / "calendar.json")
    r = cp.calendar_add("X", "nieprawidłowa-data")
    assert r["status"] == "error"


def test_calendar_delete(tmp_path, monkeypatch):
    from jarvis.plugins import calendar_plugin as cp
    monkeypatch.setattr(cp, "CALENDAR_FILE", tmp_path / "calendar.json")
    future = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
    cp.calendar_add("Do usunięcia", future)
    out = cp.calendar_delete("usunięcia")
    assert "1" in out["result"]


def test_notes_create_and_search(tmp_path, monkeypatch):
    from jarvis.plugins import notes_plugin as npl
    monkeypatch.setattr(npl, "NOTES_DIR", tmp_path / "notes")
    npl.note_create("Pomysł na projekt", "Zbudować system RAG dla TireQ")
    found = npl.note_search("RAG")
    assert len(found["result"]) == 1


def test_notes_list_empty(tmp_path, monkeypatch):
    from jarvis.plugins import notes_plugin as npl
    monkeypatch.setattr(npl, "NOTES_DIR", tmp_path / "empty_notes")
    assert npl.note_list()["result"] == []
