"""Testy dodatkowe jarvis/scheduler/engine.py — _log, plugin/agent tasks, verbose, daemon_loop."""
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


# ── _log ──────────────────────────────────────────────────────────────────────

def test_log_prints_and_writes_file(isolated_scheduler, capsys):
    eng._log("test message hello")
    out = capsys.readouterr().out
    assert "test message hello" in out
    assert isolated_scheduler["log"].exists()
    content = isolated_scheduler["log"].read_text(encoding="utf-8")
    assert "test message hello" in content


# ── should_run — interval z istniejącym last_run ─────────────────────────────

def test_should_run_interval_past_due(isolated_scheduler):
    now = datetime.now()
    old = now - timedelta(hours=2)
    task = {"id": "t", "schedule": "every 1h", "repeat": "interval", "enabled": True}
    state = {"t": {"last_run": old.isoformat()}}
    assert eng.should_run(task, state, now) is True


def test_should_run_interval_not_yet_due(isolated_scheduler):
    now = datetime.now()
    recent = now - timedelta(minutes=30)
    task = {"id": "t", "schedule": "every 1h", "repeat": "interval", "enabled": True}
    state = {"t": {"last_run": recent.isoformat()}}
    assert eng.should_run(task, state, now) is False


# ── execute_task — typ "plugin" ───────────────────────────────────────────────

class _FakeReg:
    def __init__(self, tools_dict):
        self.tools = tools_dict
    def load_all(self): return self


def test_execute_task_plugin_found(monkeypatch):
    import jarvis.plugins as jp
    monkeypatch.setattr(jp, "registry",
                        _FakeReg({"my_tool": lambda: {"status": "ok", "result": "plugin ran ok"}}))
    out = eng.execute_task({"type": "plugin", "action": "my_tool", "params": {}})
    assert "plugin ran ok" in out


def test_execute_task_plugin_not_found(monkeypatch):
    import jarvis.plugins as jp
    monkeypatch.setattr(jp, "registry", _FakeReg({}))
    out = eng.execute_task({"type": "plugin", "action": "missing_tool", "params": {}})
    assert "nie znaleziony" in out


def test_execute_task_plugin_with_params(monkeypatch):
    import jarvis.plugins as jp
    received = {}
    monkeypatch.setattr(jp, "registry", _FakeReg({
        "param_tool": lambda days=7: received.update({"days": days}) or {"status": "ok", "result": "ok"}
    }))
    eng.execute_task({"type": "plugin", "action": "param_tool", "params": {"days": 3}})
    assert received.get("days") == 3


# ── execute_task — typ "agent" ────────────────────────────────────────────────

def test_execute_task_agent(monkeypatch):
    from jarvis.core import agent as ag
    monkeypatch.setattr(ag, "run_agent", lambda task, verbose=False: "agent result xyz")
    out = eng.execute_task({"type": "agent", "action": "sprawdź status"})
    assert "agent result xyz" in out


# ── run_pending verbose=True ──────────────────────────────────────────────────

def test_run_pending_verbose_logs_task_name(isolated_scheduler, monkeypatch, capsys):
    isolated_scheduler["tasks"].write_text(json.dumps({"tasks": [
        {"id": "bkp", "name": "Backup dzienny", "type": "shell", "action": "echo bkp"},
    ]}), encoding="utf-8")
    monkeypatch.setattr(eng, "execute_task", lambda t: "done")
    eng.run_pending(force_id="bkp", verbose=True)
    out = capsys.readouterr().out
    assert "Backup dzienny" in out


# ── daemon_loop ───────────────────────────────────────────────────────────────

def test_daemon_loop_stops_on_keyboard_interrupt(isolated_scheduler, monkeypatch, capsys):
    calls = {"n": 0}

    def fake_run_pending(verbose=True):
        calls["n"] += 1
        raise KeyboardInterrupt

    monkeypatch.setattr(eng, "run_pending", fake_run_pending)
    monkeypatch.setattr(eng.time, "sleep", lambda s: None)
    eng.daemon_loop(interval=1)
    out = capsys.readouterr().out
    assert "zatrzymany" in out.lower() or "daemon" in out.lower()


def test_daemon_loop_handles_exception_then_stops(isolated_scheduler, monkeypatch):
    calls = {"n": 0}

    def fake_run_pending(verbose=True):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("test error")
        raise KeyboardInterrupt

    monkeypatch.setattr(eng, "run_pending", fake_run_pending)
    monkeypatch.setattr(eng.time, "sleep", lambda s: None)
    eng.daemon_loop(interval=1)
    assert calls["n"] == 2
