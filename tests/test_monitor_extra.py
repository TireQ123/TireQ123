"""Testy dodatkowe jarvis/monitor/watcher.py — _run, run_once branches, watch_loop."""
import subprocess

import pytest

from jarvis.monitor import watcher as w


@pytest.fixture
def isolated_monitor(tmp_path, monkeypatch):
    (tmp_path / "memory").mkdir()
    monkeypatch.setattr(w, "ALERT_FILE", tmp_path / "memory/alerts.json")
    monkeypatch.setattr(w, "STATE_FILE", tmp_path / "memory/state.json")
    monkeypatch.setattr(w, "ROOT", tmp_path)
    return tmp_path


def mock_run(monkeypatch, mapping):
    def fake(cmd):
        for frag, result in mapping.items():
            if frag in cmd:
                return result(cmd) if callable(result) else result
        return ""
    monkeypatch.setattr(w, "_run", fake)


# ── _run ──────────────────────────────────────────────────────────────────────

def test_run_function_returns_stripped_output(monkeypatch):
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: "abc123\n")
    assert w._run("echo abc123") == "abc123"


def test_run_function_returns_empty_on_exception(monkeypatch):
    monkeypatch.setattr(subprocess, "check_output",
                        lambda *a, **k: (_ for _ in ()).throw(Exception("fail")))
    assert w._run("bad cmd") == ""


# ── run_once — gałąź nowych commitów ─────────────────────────────────────────

def test_run_once_reports_new_commits(isolated_monitor, monkeypatch):
    w._save_state({"last_commit": "hash_old"})
    mock_run(monkeypatch, {
        "rev-parse": "hash_new",
        "fetch": "",
        "git log": "abc nowy commit\ndef drugi",
        "branch --show-current": "main",
    })
    report = w.run_once(verbose=False)
    assert any("Nowe commity" in i for i in report["info"])


# ── run_once — gałąź dużych plików ───────────────────────────────────────────

def test_run_once_flags_large_files(isolated_monitor, monkeypatch):
    big = isolated_monitor / "huge.dat"
    big.write_bytes(b"x" * (11 * 1_048_576))
    mock_run(monkeypatch, {"rev-parse": "h1", "branch --show-current": "main"})
    report = w.run_once(verbose=False)
    assert any("Duże pliki" in a for a in report["alerts"])


# ── run_once — gałąź sekretów ─────────────────────────────────────────────────

def test_run_once_flags_secrets(isolated_monitor, monkeypatch):
    mock_run(monkeypatch, {
        "rev-parse": "h1",
        "branch --show-current": "main",
        "git diff --staged": "+sk-ant-abc123secret",
    })
    report = w.run_once(verbose=False)
    assert any("sekret" in a.lower() or "UWAGA" in a for a in report["alerts"])


# ── run_once — gałąź ahead > 3 ───────────────────────────────────────────────

def test_run_once_flags_branch_ahead(isolated_monitor, monkeypatch):
    mock_run(monkeypatch, {
        "rev-parse": "h1",
        "branch --show-current": "feature",
        "@{u}..HEAD": "5",
        "HEAD..@{u}": "0",
    })
    report = w.run_once(verbose=False)
    assert any("nieopublikowanych" in i for i in report["info"])


# ── run_once verbose=True ─────────────────────────────────────────────────────

def test_run_once_verbose_clean(isolated_monitor, monkeypatch, capsys):
    mock_run(monkeypatch, {"rev-parse": "h1", "branch --show-current": "main"})
    w.run_once(verbose=True)
    out = capsys.readouterr().out
    assert "✓" in out or "porządku" in out


def test_run_once_verbose_with_alert(isolated_monitor, monkeypatch, capsys):
    mock_run(monkeypatch, {
        "rev-parse": "h1",
        "branch --show-current": "main",
        "HEAD..@{u}": "2",
    })
    w.run_once(verbose=True)
    out = capsys.readouterr().out
    assert "za remote" in out


def test_run_once_verbose_with_info(isolated_monitor, monkeypatch, capsys):
    w._save_state({"last_commit": "hash_old"})
    mock_run(monkeypatch, {
        "rev-parse": "hash_new",
        "fetch": "",
        "git log": "abc commit",
        "branch --show-current": "main",
    })
    w.run_once(verbose=True)
    out = capsys.readouterr().out
    assert "ℹ" in out or "Nowe commity" in out


# ── watch_loop ────────────────────────────────────────────────────────────────

def test_watch_loop_stops_on_keyboard_interrupt(isolated_monitor, monkeypatch, capsys):
    calls = {"n": 0}

    def fake_run_once(verbose=True):
        calls["n"] += 1
        raise KeyboardInterrupt

    monkeypatch.setattr(w, "run_once", fake_run_once)
    monkeypatch.setattr(w.time, "sleep", lambda s: None)
    w.watch_loop(interval=1)
    out = capsys.readouterr().out
    assert "zatrzymany" in out.lower()
    assert calls["n"] == 1
