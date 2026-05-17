"""Testy jarvis/core/tools.py — memory_read, memory_save, web_search, git_*, shell timeout."""
import json
import subprocess

import pytest

import jarvis.core.tools as tools


# ── memory_read ───────────────────────────────────────────────────────────────

def test_memory_read_success(tmp_path, monkeypatch):
    mem = tmp_path / "memory"
    mem.mkdir()
    profile = {"patterns": {"preferred_solutions": ["FastAPI", "pytest"]}}
    decisions = {"decisions": [
        {"decision": "backend Python"},
        {"decision": "frontend React"},
    ]}
    (mem / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    (mem / "decisions.json").write_text(json.dumps(decisions), encoding="utf-8")
    monkeypatch.setattr(tools, "ROOT", tmp_path)
    result = tools.memory_read()
    assert result["status"] == "ok"
    assert "FastAPI" in result["result"]["preferences"]
    assert "frontend React" in result["result"]["recent_decisions"]


def test_memory_read_missing_files_returns_error(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "ROOT", tmp_path)
    result = tools.memory_read()
    assert result["status"] == "error"


# ── memory_save ───────────────────────────────────────────────────────────────

def test_memory_save_decision(monkeypatch):
    import memory_update as mu
    calls = []
    monkeypatch.setattr(mu, "add_decision", lambda v: calls.append(v))
    result = tools.memory_save("decision", "backend Python")
    assert result["status"] == "ok"
    assert calls == ["backend Python"]


def test_memory_save_preference(monkeypatch):
    import memory_update as mu
    calls = []
    monkeypatch.setattr(mu, "add_preference", lambda v: calls.append(v))
    result = tools.memory_save("preference", "FastAPI nad Flask")
    assert result["status"] == "ok"
    assert calls == ["FastAPI nad Flask"]


def test_memory_save_note(monkeypatch):
    import memory_update as mu
    calls = []
    monkeypatch.setattr(mu, "add_note", lambda v: calls.append(v))
    result = tools.memory_save("note", "deadline w czerwcu")
    assert result["status"] == "ok"
    assert calls == ["deadline w czerwcu"]


def test_memory_save_invalid_key():
    result = tools.memory_save("invalid_key", "wartość")
    assert result["status"] == "error"
    assert "Nieznany klucz" in result["result"]


# ── web_search ────────────────────────────────────────────────────────────────

def test_web_search_always_returns_error():
    result = tools.web_search("Python FastAPI")
    assert result["status"] == "error"
    assert "API" in result["result"] or "klucz" in result["result"].lower()


# ── shell_run timeout ─────────────────────────────────────────────────────────

def test_shell_run_timeout(monkeypatch):
    def fake_run(*a, **k):
        raise subprocess.TimeoutExpired("sleep", 1)
    monkeypatch.setattr(subprocess, "run", fake_run)
    result = tools.shell_run("sleep 999", timeout=1)
    assert result["status"] == "error"
    assert "Timeout" in result["result"]


def test_shell_run_exception(monkeypatch):
    def fake_run(*a, **k):
        raise OSError("nieoczekiwany błąd")
    monkeypatch.setattr(subprocess, "run", fake_run)
    result = tools.shell_run("echo test")
    assert result["status"] == "error"


# ── file_write error ──────────────────────────────────────────────────────────

def test_file_write_error_returns_error():
    result = tools.file_write("/proc/sys/nieistniejacy/plik.txt", "treść")
    assert result["status"] == "error"


# ── file_list ─────────────────────────────────────────────────────────────────

def test_file_list_absolute_dir(tmp_path):
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "b.py").write_text("y")
    result = tools.file_list(str(tmp_path))
    assert result["status"] == "ok"
    assert len(result["result"]) >= 2


def test_file_list_nonexistent_dir():
    # rglob na nieistniejącym katalogu zwraca pustą listę — nie błąd
    result = tools.file_list("/absolutnie/nieistnieje_xyz")
    assert result["status"] == "ok"
    assert result["result"] == []


# ── git_status ────────────────────────────────────────────────────────────────

def test_git_status_returns_string():
    result = tools.git_status()
    assert result["status"] == "ok"
    assert isinstance(result["result"], str)


# ── execute_tool ──────────────────────────────────────────────────────────────

def test_execute_tool_web_search():
    result = tools.execute_tool("web_search", {"query": "test"})
    assert result["status"] == "error"


def test_execute_tool_memory_read_bad_params():
    result = tools.execute_tool("memory_read", {"nieznany": "param"})
    assert result["status"] == "error"
