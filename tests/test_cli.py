"""Testy jarvis/cli.py — dispatch komend i budowanie wywołań."""
import sys

import pytest

from jarvis import cli


@pytest.fixture
def capture_calls(monkeypatch):
    """Przechwytuje wywołania python() i cmd() zamiast uruchamiać procesy."""
    calls = {"python": [], "cmd": []}
    monkeypatch.setattr(cli, "python",
                        lambda script, *a: calls["python"].append((script, a)) or 0)
    monkeypatch.setattr(cli, "cmd",
                        lambda args, **kw: calls["cmd"].append(args) or 0)
    return calls


def run_main(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["jarvis", *argv])
    cli.main()


# ── helpers ───────────────────────────────────────────────────────────────────

def test_cmd_invokes_subprocess(monkeypatch):
    seen = {}

    class R:
        returncode = 0

    def fake_run(args, cwd=None, **kw):
        seen["args"] = args
        seen["cwd"] = cwd
        return R()

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    rc = cli.cmd(["echo", "hi"])
    assert rc == 0
    assert seen["args"] == ["echo", "hi"]
    assert seen["cwd"] == cli.ROOT


def test_python_builds_script_path(monkeypatch):
    seen = {}
    monkeypatch.setattr(cli, "cmd", lambda args, **kw: seen.setdefault("a", args) or 0)
    cli.python("scripts/foo.py", "--flag")
    assert seen["a"][0] == sys.executable
    assert seen["a"][-1] == "--flag"
    assert "scripts/foo.py" in seen["a"][1]


# ── dispatch routing ──────────────────────────────────────────────────────────

def test_no_command_defaults_to_chat(monkeypatch, capture_calls):
    run_main(monkeypatch, [])
    assert capture_calls["python"][0][0] == "training/jarvis_ollama.py"


def test_chat_command(monkeypatch, capture_calls):
    run_main(monkeypatch, ["chat"])
    assert capture_calls["python"][0][0] == "training/jarvis_ollama.py"


def test_agent_with_task(monkeypatch, capture_calls):
    run_main(monkeypatch, ["agent", "napraw", "bug"])
    script, args = capture_calls["python"][0]
    assert script == "jarvis/core/agent.py"
    assert args == ("napraw bug",)


def test_agent_without_task_is_interactive(monkeypatch, capture_calls):
    run_main(monkeypatch, ["agent"])
    assert capture_calls["python"][0][1] == ("--interactive",)


def test_memory_show_default(monkeypatch, capture_calls):
    run_main(monkeypatch, ["memory"])
    script, args = capture_calls["python"][0]
    assert script == "scripts/memory_update.py"
    assert args == ("--show",)


def test_memory_add_with_type(monkeypatch, capture_calls):
    run_main(monkeypatch, ["memory", "add", "lubie", "Rust", "--type", "preference"])
    script, args = capture_calls["python"][0]
    assert script == "scripts/memory_update.py"
    assert args == ("--preference", "lubie Rust")


def test_memory_update_calls_memory_load(monkeypatch, capture_calls):
    run_main(monkeypatch, ["memory", "update"])
    assert capture_calls["python"][0] == (
        "scripts/memory_load.py", ("--update-claude",))


def test_voice_text_only_and_en(monkeypatch, capture_calls):
    run_main(monkeypatch, ["voice", "--text-only", "--voice", "en"])
    script, args = capture_calls["python"][0]
    assert script == "training/jarvis_voice.py"
    assert "--text-only" in args
    assert "--voice en" in args


def test_monitor_passes_interval(monkeypatch, capture_calls, capsys):
    run_main(monkeypatch, ["monitor", "--interval", "30"])
    script, args = capture_calls["python"][0]
    assert script == "jarvis/monitor/watcher.py"
    assert args == ("--interval", "30")


def test_schedule_list_default(monkeypatch, capture_calls):
    run_main(monkeypatch, ["schedule"])
    assert capture_calls["python"][0] == (
        "jarvis/scheduler/engine.py", ("--list",))


def test_schedule_run_with_value(monkeypatch, capture_calls):
    run_main(monkeypatch, ["schedule", "run", "backup"])
    assert capture_calls["python"][0] == (
        "jarvis/scheduler/engine.py", ("--run", "backup"))


def test_api_prints_and_runs(monkeypatch, capture_calls, capsys):
    run_main(monkeypatch, ["api"])
    out = capsys.readouterr().out
    assert "8000" in out
    assert capture_calls["python"][0][0] == "jarvis/api/server.py"


def test_update_runs_pipeline(monkeypatch, capture_calls):
    run_main(monkeypatch, ["update"])
    assert ["git", "pull", "origin", "main"] in capture_calls["cmd"]
    scripts = [c[0] for c in capture_calls["python"]]
    assert "scripts/rag_index.py" in scripts
    assert "scripts/memory_load.py" in scripts


def test_train_runs_collect_and_format(monkeypatch, capture_calls):
    run_main(monkeypatch, ["train"])
    scripts = [c[0] for c in capture_calls["python"]]
    assert "scripts/training_collect.py" in scripts
    assert "scripts/training_format.py" in scripts


def test_telegram_dispatch(monkeypatch, capture_calls):
    run_main(monkeypatch, ["telegram"])
    assert capture_calls["python"][0][0] == "jarvis/integrations/telegram_bot.py"


def test_dashboard_dispatch(monkeypatch, capture_calls, capsys):
    run_main(monkeypatch, ["dashboard"])
    assert capture_calls["python"][0][0] == "jarvis/api/server.py"
    assert "dashboard" in capsys.readouterr().out.lower()
