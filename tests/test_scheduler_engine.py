"""Testy jarvis/scheduler/engine.py — execute_task, run_pending, I/O, weekly.

Uzupełnia test_scheduler.py (parse_interval + should_run podstawy)."""
import json
from datetime import datetime, timedelta

import pytest

from jarvis.scheduler import engine as eng


@pytest.fixture
def isolated_scheduler(tmp_path, monkeypatch):
    tasks_file = tmp_path / "tasks.json"
    state_file = tmp_path / "state.json"
    log_file = tmp_path / "scheduler.log"
    monkeypatch.setattr(eng, "TASKS_FILE", tasks_file)
    monkeypatch.setattr(eng, "STATE_FILE", state_file)
    monkeypatch.setattr(eng, "LOG_FILE", log_file)
    return {"tasks": tasks_file, "state": state_file, "log": log_file}


# ── I/O stanu i zadań ────────────────────────────────────────────────────────

def test_load_tasks_missing_returns_empty(isolated_scheduler):
    assert eng.load_tasks() == []


def test_load_tasks_reads_list(isolated_scheduler):
    isolated_scheduler["tasks"].write_text(
        json.dumps({"tasks": [{"id": "a"}]}), encoding="utf-8")
    assert eng.load_tasks() == [{"id": "a"}]


def test_load_state_missing_returns_empty(isolated_scheduler):
    assert eng.load_state() == {}


def test_save_and_load_state_roundtrip(isolated_scheduler):
    eng.save_state({"t1": {"last_run": "2026-05-16T10:00:00"}})
    assert eng.load_state()["t1"]["last_run"] == "2026-05-16T10:00:00"


# ── should_run — weekly (nie pokryte w test_scheduler.py) ────────────────────

def test_should_run_weekly_wrong_day():
    # 2026-05-16 to sobota
    sat = datetime(2026, 5, 16, 11, 0)
    task = {"id": "w", "schedule": "monday 10:00", "repeat": "weekly"}
    assert eng.should_run(task, {}, sat) is False


def test_should_run_weekly_correct_day_first_time():
    sat = datetime(2026, 5, 16, 11, 0)
    task = {"id": "w", "schedule": "saturday 10:00", "repeat": "weekly"}
    assert eng.should_run(task, {}, sat) is True


def test_should_run_weekly_already_ran_this_week():
    sat = datetime(2026, 5, 16, 11, 0)
    task = {"id": "w", "schedule": "saturday 10:00", "repeat": "weekly"}
    state = {"w": {"last_run": (sat - timedelta(days=2)).isoformat()}}
    assert eng.should_run(task, state, sat) is False


def test_should_run_weekly_malformed_schedule():
    now = datetime(2026, 5, 16, 11, 0)
    task = {"id": "w", "schedule": "saturday", "repeat": "weekly"}
    assert eng.should_run(task, {}, now) is False


def test_should_run_unknown_repeat():
    task = {"id": "x", "schedule": "08:00", "repeat": "monthly"}
    assert eng.should_run(task, {}, datetime.now()) is False


def test_should_run_daily_already_ran_today():
    now = datetime(2026, 5, 16, 14, 0)
    task = {"id": "d", "schedule": "08:00", "repeat": "daily"}
    state = {"d": {"last_run": datetime(2026, 5, 16, 9, 0).isoformat()}}
    assert eng.should_run(task, state, now) is False


# ── execute_task ─────────────────────────────────────────────────────────────

def test_execute_task_script(monkeypatch):
    class R:
        stdout = "ok output"
        stderr = ""
    monkeypatch.setattr(eng.subprocess, "run", lambda *a, **k: R())
    out = eng.execute_task({"type": "script", "action": "x.py",
                            "params": {"args": ["--flag"]}})
    assert "ok output" in out


def test_execute_task_shell(monkeypatch):
    class R:
        stdout = "shell ran"
        stderr = ""
    monkeypatch.setattr(eng.subprocess, "run", lambda *a, **k: R())
    out = eng.execute_task({"type": "shell", "action": "echo hi"})
    assert "shell ran" in out


def test_execute_task_unknown_type():
    out = eng.execute_task({"type": "telepathy", "action": "?"})
    assert "Nieznany typ" in out


def test_execute_task_timeout(monkeypatch):
    import subprocess

    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="x", timeout=300)
    monkeypatch.setattr(eng.subprocess, "run", boom)
    out = eng.execute_task({"type": "shell", "action": "sleep 999"})
    assert "Timeout" in out


def test_execute_task_generic_exception(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(eng.subprocess, "run", boom)
    out = eng.execute_task({"type": "script", "action": "x.py"})
    assert "Błąd" in out and "kaboom" in out


# ── run_pending ──────────────────────────────────────────────────────────────

def test_run_pending_force_id_runs_one(isolated_scheduler, monkeypatch):
    isolated_scheduler["tasks"].write_text(json.dumps({"tasks": [
        {"id": "a", "name": "A", "type": "shell", "action": "echo a"},
        {"id": "b", "name": "B", "type": "shell", "action": "echo b"},
    ]}), encoding="utf-8")
    monkeypatch.setattr(eng, "execute_task", lambda t: "done")
    n = eng.run_pending(force_id="a", verbose=False)
    assert n == 1
    state = eng.load_state()
    assert "a" in state and "b" not in state


def test_run_pending_skips_when_not_due(isolated_scheduler, monkeypatch):
    isolated_scheduler["tasks"].write_text(json.dumps({"tasks": [
        {"id": "a", "name": "A", "schedule": "every 1h",
         "repeat": "interval", "type": "shell", "action": "x"},
    ]}), encoding="utf-8")
    eng.save_state({"a": {"last_run": datetime.now().isoformat()}})
    monkeypatch.setattr(eng, "execute_task", lambda t: "done")
    assert eng.run_pending(verbose=False) == 0


def test_run_pending_records_output(isolated_scheduler, monkeypatch):
    isolated_scheduler["tasks"].write_text(json.dumps({"tasks": [
        {"id": "a", "name": "A", "type": "shell", "action": "x"},
    ]}), encoding="utf-8")
    monkeypatch.setattr(eng, "execute_task", lambda t: "wynik zadania")
    eng.run_pending(force_id="a", verbose=False)
    assert eng.load_state()["a"]["last_output"] == "wynik zadania"


# ── list_tasks ───────────────────────────────────────────────────────────────

def test_list_tasks_renders(isolated_scheduler, capsys):
    isolated_scheduler["tasks"].write_text(json.dumps({"tasks": [
        {"id": "a", "name": "Backup", "schedule": "08:00", "enabled": True},
        {"id": "b", "name": "Sync", "schedule": "every 1h", "enabled": False},
    ]}), encoding="utf-8")
    eng.list_tasks()
    out = capsys.readouterr().out
    assert "Backup" in out and "Sync" in out
    assert "nigdy" in out
