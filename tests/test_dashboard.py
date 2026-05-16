"""Testy jarvis/api/dashboard.py — agregacja danych z modułów."""
import json

import pytest

from jarvis.api import dashboard as dash


@pytest.fixture
def fake_root(tmp_path, monkeypatch):
    """Buduje minimalną strukturę projektu i przekierowuje ROOT."""
    (tmp_path / "memory" / "sessions").mkdir(parents=True)
    (tmp_path / "training").mkdir()
    (tmp_path / "jarvis" / "scheduler").mkdir(parents=True)

    (tmp_path / "memory/profile.json").write_text(json.dumps({
        "patterns": {"preferred_solutions": ["FastAPI", "Docker"]},
        "notes": [{"note": "notatka A", "date": "2026-05-01T10:00:00"}],
    }), encoding="utf-8")
    (tmp_path / "memory/decisions.json").write_text(json.dumps({
        "decisions": [{"decision": "backend Python", "date": "2026-04-01T10:00:00"}]
    }), encoding="utf-8")
    (tmp_path / "jarvis/scheduler/tasks.json").write_text(json.dumps({
        "tasks": [{"id": "t1", "name": "backup", "schedule": "daily",
                   "enabled": True}]
    }), encoding="utf-8")
    monkeypatch.setattr(dash, "ROOT", tmp_path)
    return tmp_path


def test_read_json_returns_default_on_missing(tmp_path):
    assert dash._read_json(tmp_path / "x.json", {"d": 1}) == {"d": 1}


def test_read_json_returns_default_on_invalid(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid", encoding="utf-8")
    assert dash._read_json(bad, []) == []


def test_get_dashboard_data_aggregates_memory(fake_root):
    data = dash.get_dashboard_data()
    assert data["memory"]["preferences"] == ["FastAPI", "Docker"]
    assert data["memory"]["decisions"][0]["text"] == "backend Python"
    assert data["memory"]["decisions"][0]["date"] == "2026-04-01"
    assert data["memory"]["notes"][0]["text"] == "notatka A"


def test_get_dashboard_data_training_percent(fake_root):
    (fake_root / "training/raw_pairs.jsonl").write_text(
        "\n".join('{"x":1}' for _ in range(25)), encoding="utf-8")
    data = dash.get_dashboard_data()
    assert data["training"]["count"] == 25
    assert data["training"]["percent"] == 25
    assert data["training"]["target"] == 100


def test_get_dashboard_data_training_zero_when_missing(fake_root):
    data = dash.get_dashboard_data()
    assert data["training"]["count"] == 0
    assert data["training"]["percent"] == 0


def test_get_dashboard_data_scheduler_with_state(fake_root):
    (fake_root / "memory/.scheduler_state.json").write_text(
        json.dumps({"t1": {"last_run": "2026-05-10T08:00"}}), encoding="utf-8")
    data = dash.get_dashboard_data()
    assert data["scheduler"][0]["name"] == "backup"
    assert data["scheduler"][0]["last_run"] == "2026-05-10T08:00"
    assert data["scheduler"][0]["enabled"] is True


def test_get_dashboard_data_scheduler_default_last_run(fake_root):
    data = dash.get_dashboard_data()
    assert data["scheduler"][0]["last_run"] == "nigdy"


def test_get_dashboard_data_sessions_sorted_desc(fake_root):
    sdir = fake_root / "memory/sessions"
    (sdir / "a.json").write_text(json.dumps(
        {"date": "2026-05-01T10:00:00", "summary": "sesja stara"}), encoding="utf-8")
    (sdir / "b.json").write_text(json.dumps(
        {"date": "2026-05-15T10:00:00", "summary": "sesja nowa"}), encoding="utf-8")
    data = dash.get_dashboard_data()
    assert data["sessions"][0]["summary"] == "sesja nowa"


def test_get_dashboard_data_calendar_sorted_and_capped(fake_root):
    events = [{"title": f"e{i}", "datetime": f"2026-05-{20-i:02d}T10:00"}
              for i in range(8)]
    (fake_root / "memory/calendar.json").write_text(
        json.dumps(events), encoding="utf-8")
    data = dash.get_dashboard_data()
    assert len(data["calendar"]) == 5
    dates = [e["datetime"] for e in data["calendar"]]
    assert dates == sorted(dates)


def test_get_dashboard_data_alerts_reversed_and_capped(fake_root):
    alerts = [{"time": f"2026-05-16T0{i}:00", "message": f"alert{i}"}
              for i in range(12)]
    (fake_root / "memory/monitor_alerts.json").write_text(
        json.dumps(alerts), encoding="utf-8")
    data = dash.get_dashboard_data()
    assert len(data["alerts"]) == 10
    assert data["alerts"][0]["message"] == "alert11"


def test_get_dashboard_data_git_is_list(fake_root):
    data = dash.get_dashboard_data()
    assert isinstance(data["git"], list)
