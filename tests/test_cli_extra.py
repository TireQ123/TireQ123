"""Testy dodatkowe jarvis/cli.py — do_status, do_plugin, do_multi, do_briefing, do_schedule."""
import json

import pytest

from jarvis import cli


@pytest.fixture
def capture_calls(monkeypatch):
    calls = {"python": [], "cmd": []}
    monkeypatch.setattr(cli, "python",
                        lambda script, *a: calls["python"].append((script, a)) or 0)
    monkeypatch.setattr(cli, "cmd",
                        lambda args, **kw: calls["cmd"].append(args) or 0)
    return calls


class _R:
    def __init__(self, out=""):
        self.stdout = out
        self.returncode = 0


# ── do_memory else branch ─────────────────────────────────────────────────────

def test_do_memory_else_branch_calls_show(monkeypatch, capture_calls):
    class Args:
        sub = None
    cli.do_memory(Args())
    assert capture_calls["python"][0][0] == "scripts/memory_update.py"
    assert "--show" in capture_calls["python"][0][1]


# ── do_status ────────────────────────────────────────────────────────────────

def test_do_status_basic(monkeypatch, tmp_path, capsys):
    mem = tmp_path / "memory"
    mem.mkdir()
    (mem / "profile.json").write_text(json.dumps({
        "patterns": {"preferred_solutions": ["FastAPI"]},
        "notes": ["deadline"],
    }), encoding="utf-8")
    (mem / "decisions.json").write_text(json.dumps({
        "decisions": [{"decision": "backend Python"}]
    }), encoding="utf-8")
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **kw: _R("abc nowy commit"))
    cli.do_status(None)
    out = capsys.readouterr().out
    assert "STATUS" in out


def test_do_status_no_memory(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **kw: _R(""))
    cli.do_status(None)
    out = capsys.readouterr().out
    assert "brak danych" in out or "Pamięć" in out


def test_do_status_with_training_file(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **kw: _R(""))
    training = tmp_path / "training"
    training.mkdir()
    (training / "raw_pairs.jsonl").write_text(
        '{"id":"1"}\n{"id":"2"}\n{"id":"3"}\n', encoding="utf-8")
    cli.do_status(None)
    out = capsys.readouterr().out
    assert "3" in out


def test_do_status_ollama_not_found(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "ROOT", tmp_path)

    def fake_run(args, *a, **kw):
        if isinstance(args, list) and args and args[0] == "ollama":
            raise FileNotFoundError
        return _R("")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    cli.do_status(None)
    out = capsys.readouterr().out
    assert "Ollama" in out


def test_do_status_ollama_has_model(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **kw: _R("jarvis:latest"))
    cli.do_status(None)
    out = capsys.readouterr().out
    assert "✓" in out


# ── do_plugin ────────────────────────────────────────────────────────────────

def test_do_plugin_list(monkeypatch, capsys):
    import jarvis.plugins as jp

    class _FakeReg:
        schemas = [{"name": "tireq_briefing"}, {"name": "weather_get"}]
        def load_all(self): return self
        def list_plugins(self): return ["tireq", "weather"]

    monkeypatch.setattr(jp, "registry", _FakeReg())

    class Args:
        sub = "list"

    cli.do_plugin(Args())
    out = capsys.readouterr().out
    assert "tireq" in out
    assert "weather" in out


# ── do_multi ─────────────────────────────────────────────────────────────────

def test_do_multi_with_task(monkeypatch):
    import jarvis.core.multi_agent as ma
    results = []
    monkeypatch.setattr(ma, "orchestrate", lambda task, **kw: results.append(task))

    class Args:
        task = ["napraw", "błąd"]

    cli.do_multi(Args())
    assert results == ["napraw błąd"]


def test_do_multi_interactive(monkeypatch):
    import jarvis.core.multi_agent as ma
    called = []
    monkeypatch.setattr(ma, "interactive_mode", lambda: called.append(True))

    class Args:
        task = []

    cli.do_multi(Args())
    assert called


# ── do_briefing ───────────────────────────────────────────────────────────────

def test_do_briefing(monkeypatch, capsys):
    import jarvis.plugins.tireq_plugin as tp
    monkeypatch.setattr(tp, "tireq_briefing",
                        lambda: {"status": "ok", "result": "BRIEFING CONTENT OK"})
    cli.do_briefing(None)
    out = capsys.readouterr().out
    assert "BRIEFING CONTENT OK" in out


# ── do_schedule ──────────────────────────────────────────────────────────────

def test_do_schedule_start(monkeypatch, capture_calls, capsys):
    class Args:
        sub = "start"
        value = []

    cli.do_schedule(Args())
    scripts = [c[0] for c in capture_calls["python"]]
    assert "jarvis/scheduler/engine.py" in scripts


def test_do_schedule_once(monkeypatch, capture_calls):
    class Args:
        sub = "once"
        value = []

    cli.do_schedule(Args())
    assert ("jarvis/scheduler/engine.py", ("--once",)) in capture_calls["python"]
