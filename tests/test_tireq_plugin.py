"""Testy jarvis/plugins/tireq_plugin.py — briefing, project_init, daily_log, quick_commit, health_check."""
import json

import pytest

import jarvis.plugins.tireq_plugin as tp


@pytest.fixture
def isolated_tireq(tmp_path, monkeypatch):
    fake_root = tmp_path / "jarvis"
    fake_root.mkdir()
    mem = fake_root / "memory"
    mem.mkdir()
    profile = {
        "patterns": {"preferred_solutions": ["FastAPI"]},
        "notes": [],
    }
    decisions = {"decisions": [{"decision": "backend Python", "date": "2026-01-01T09:00"}]}
    (mem / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    (mem / "decisions.json").write_text(json.dumps(decisions), encoding="utf-8")
    monkeypatch.setattr(tp, "ROOT", fake_root)
    return {"root": fake_root, "mem": mem, "projects": tmp_path}


def mock_run(monkeypatch, mapping):
    def fake(cmd):
        for frag, result in mapping.items():
            if frag in cmd:
                return result() if callable(result) else result
        return ""
    monkeypatch.setattr(tp, "_run", fake)


# ── _run ──────────────────────────────────────────────────────────────────────

def test_run_returns_empty_on_error(monkeypatch):
    import subprocess
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: (_ for _ in ()).throw(OSError()))
    assert tp._run("echo test") == ""


# ── tireq_briefing ────────────────────────────────────────────────────────────

def test_briefing_returns_ok(isolated_tireq, monkeypatch):
    mock_run(monkeypatch, {
        "git status": "M file.py",
        "git log": "abc nowy commit",
        "git branch": "main",
    })
    result = tp.tireq_briefing()
    assert result["status"] == "ok"


def test_briefing_contains_git_section(isolated_tireq, monkeypatch):
    mock_run(monkeypatch, {
        "git status": "",
        "git log": "abc commit",
        "git branch": "main",
    })
    result = tp.tireq_briefing()
    assert "GIT" in result["result"]


def test_briefing_contains_memory_section(isolated_tireq, monkeypatch):
    mock_run(monkeypatch, {
        "git status": "", "git log": "", "git branch": "main",
    })
    result = tp.tireq_briefing()
    assert "PAMIĘĆ" in result["result"] or "FastAPI" in result["result"]


def test_briefing_shows_training_count(isolated_tireq, monkeypatch):
    mock_run(monkeypatch, {"git status": "", "git log": "", "git branch": "main"})
    raw = isolated_tireq["root"] / "training" / "raw_pairs.jsonl"
    raw.parent.mkdir(exist_ok=True)
    raw.write_text('{"id":"a","score":0.7,"messages":[]}\n', encoding="utf-8")
    result = tp.tireq_briefing()
    assert "1" in result["result"]


# ── tireq_project_init ────────────────────────────────────────────────────────

def test_project_init_python(isolated_tireq, tmp_path):
    result = tp.tireq_project_init("my_project", "python")
    assert result["status"] == "ok"
    assert "my_project" in result["result"]


def test_project_init_fastapi(isolated_tireq, tmp_path):
    result = tp.tireq_project_init("fast_project", "fastapi")
    assert result["status"] == "ok"


def test_project_init_react(isolated_tireq, tmp_path):
    result = tp.tireq_project_init("react_project", "react")
    assert result["status"] == "ok"


def test_project_init_unknown_stack_defaults_to_python(isolated_tireq):
    result = tp.tireq_project_init("unknown_stack_proj", "unknown")
    assert result["status"] == "ok"


def test_project_init_existing_returns_error(isolated_tireq):
    tp.tireq_project_init("duplikat", "python")
    result = tp.tireq_project_init("duplikat", "python")
    assert result["status"] == "error"
    assert "już istnieje" in result["result"]


# ── tireq_daily_log ───────────────────────────────────────────────────────────

def test_daily_log_creates_file(isolated_tireq):
    result = tp.tireq_daily_log("Pracowałem nad testami")
    assert result["status"] == "ok"
    logs = list((isolated_tireq["root"] / "memory" / "daily_logs").glob("*.md"))
    assert len(logs) == 1


def test_daily_log_creates_header(isolated_tireq):
    tp.tireq_daily_log("pierwsza notatka")
    log = list((isolated_tireq["root"] / "memory" / "daily_logs").glob("*.md"))[0]
    content = log.read_text()
    assert "# Log" in content


def test_daily_log_appends_to_existing(isolated_tireq):
    tp.tireq_daily_log("pierwsza")
    tp.tireq_daily_log("druga")
    log = list((isolated_tireq["root"] / "memory" / "daily_logs").glob("*.md"))[0]
    content = log.read_text()
    assert "pierwsza" in content
    assert "druga" in content


# ── tireq_quick_commit ────────────────────────────────────────────────────────

def test_quick_commit_no_changes(isolated_tireq, monkeypatch):
    mock_run(monkeypatch, {"git status": ""})
    result = tp.tireq_quick_commit()
    assert result["status"] == "ok"
    assert "Brak zmian" in result["result"]


def test_quick_commit_with_changes(isolated_tireq, monkeypatch):
    mock_run(monkeypatch, {
        "git status": "M file.py\nM other.py",
        "git diff": "file.py | 5 ++",
        "git add": "",
        "git commit": "[main abc1234] Update: file.py, other.py",
    })
    result = tp.tireq_quick_commit()
    assert result["status"] == "ok"
    assert "Commit" in result["result"]


# ── tireq_health_check ────────────────────────────────────────────────────────

def test_health_check_returns_ok(isolated_tireq):
    result = tp.tireq_health_check()
    assert result["status"] == "ok"
    assert "HEALTH CHECK" in result["result"]


def test_health_check_shows_python_version(isolated_tireq):
    result = tp.tireq_health_check()
    assert "Python" in result["result"]


def test_health_check_handles_missing_training(isolated_tireq):
    # Plik treningowy nie istnieje — nie powinno rzucić wyjątku
    result = tp.tireq_health_check()
    assert result["status"] == "ok"


# ── Plugin metadata ───────────────────────────────────────────────────────────

def test_plugin_name():
    assert tp.plugin.name == "tireq"


def test_plugin_enabled():
    assert tp.plugin.enabled is True


def test_plugin_has_five_tools():
    tools = tp.plugin.get_tools()
    assert len(tools) == 5
    names = [t[0] for t in tools]
    assert "tireq_briefing" in names
    assert "tireq_project_init" in names
    assert "tireq_daily_log" in names
    assert "tireq_quick_commit" in names
    assert "tireq_health_check" in names
