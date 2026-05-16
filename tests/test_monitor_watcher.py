"""Testy jarvis/monitor/watcher.py — detekcja commitów, dużych plików, sekretów."""
import json

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
    """mapping: dict fragment_komendy -> wynik (lub callable)."""
    def fake(cmd):
        for frag, result in mapping.items():
            if frag in cmd:
                return result(cmd) if callable(result) else result
        return ""
    monkeypatch.setattr(w, "_run", fake)


# ── stan i alerty ────────────────────────────────────────────────────────────

def test_load_state_missing_returns_empty(isolated_monitor):
    assert w._load_state() == {}


def test_save_and_load_state_roundtrip(isolated_monitor):
    w._save_state({"last_commit": "abc123"})
    assert w._load_state()["last_commit"] == "abc123"


def test_save_alert_appends_and_caps(isolated_monitor):
    for i in range(105):
        w._save_alert("test", f"alert {i}")
    alerts = json.loads(w.ALERT_FILE.read_text())
    assert len(alerts) == 100
    assert alerts[-1]["message"] == "alert 104"
    assert alerts[-1]["category"] == "test"


# ── check_new_commits ────────────────────────────────────────────────────────

def test_check_new_commits_first_run_sets_baseline(isolated_monitor, monkeypatch):
    mock_run(monkeypatch, {"rev-parse": "hash_v1", "fetch": ""})
    state = {}
    assert w.check_new_commits(state) == []
    assert state["last_commit"] == "hash_v1"


def test_check_new_commits_no_change(isolated_monitor, monkeypatch):
    mock_run(monkeypatch, {"rev-parse": "same", "fetch": ""})
    assert w.check_new_commits({"last_commit": "same"}) == []


def test_check_new_commits_detects_new(isolated_monitor, monkeypatch):
    mock_run(monkeypatch, {
        "rev-parse": "hash_v2",
        "fetch": "",
        "git log": "abc nowy commit\ndef drugi commit",
    })
    state = {"last_commit": "hash_v1"}
    commits = w.check_new_commits(state)
    assert len(commits) == 2
    assert state["last_commit"] == "hash_v2"


# ── check_large_files ────────────────────────────────────────────────────────

def test_check_large_files_flags_oversized(isolated_monitor):
    big = isolated_monitor / "huge.dat"
    big.write_bytes(b"x" * (11 * 1_048_576))
    alerts = w.check_large_files()
    assert any("huge.dat" in a for a in alerts)


def test_check_large_files_warns_binary_extension(isolated_monitor):
    pkl = isolated_monitor / "model.pkl"
    pkl.write_bytes(b"x" * (2 * 1_048_576))
    alerts = w.check_large_files()
    assert any("model.pkl" in a and "binarny" in a for a in alerts)


def test_check_large_files_ignores_small(isolated_monitor):
    (isolated_monitor / "tiny.txt").write_text("ok", encoding="utf-8")
    assert w.check_large_files() == []


# ── check_secrets ────────────────────────────────────────────────────────────

def test_check_secrets_detects_added_key(isolated_monitor, monkeypatch):
    diff = "+API_KEY=sk-ant-123456\n-old line\n+++ b/file"
    mock_run(monkeypatch, {"git diff --staged": diff})
    found = w.check_secrets()
    assert len(found) == 1
    assert "sekret" in found[0].lower()


def test_check_secrets_ignores_unmodified(isolated_monitor, monkeypatch):
    mock_run(monkeypatch, {"git diff --staged": "-removed secret=abc\n unchanged"})
    assert w.check_secrets() == []


def test_check_secrets_clean_diff(isolated_monitor, monkeypatch):
    mock_run(monkeypatch, {"git diff --staged": "+normalny kod bez sekretow"})
    assert w.check_secrets() == []


# ── check_branch_status ──────────────────────────────────────────────────────

def test_check_branch_status_parses_counts(isolated_monitor, monkeypatch):
    mock_run(monkeypatch, {
        "branch --show-current": "main",
        "@{u}..HEAD": "2",
        "HEAD..@{u}": "0",
    })
    st = w.check_branch_status()
    assert st == {"branch": "main", "ahead": 2, "behind": 0}


def test_check_branch_status_defaults_to_zero(isolated_monitor, monkeypatch):
    mock_run(monkeypatch, {"branch --show-current": "dev"})
    st = w.check_branch_status()
    assert st["ahead"] == 0 and st["behind"] == 0


# ── run_once ─────────────────────────────────────────────────────────────────

def test_run_once_clean_report(isolated_monitor, monkeypatch):
    mock_run(monkeypatch, {"rev-parse": "h1", "branch --show-current": "main"})
    report = w.run_once(verbose=False)
    assert report["alerts"] == []
    assert "time" in report


def test_run_once_flags_behind_branch(isolated_monitor, monkeypatch):
    mock_run(monkeypatch, {
        "rev-parse": "h1",
        "branch --show-current": "main",
        "HEAD..@{u}": "3",
    })
    report = w.run_once(verbose=False)
    assert any("za remote" in a for a in report["alerts"])


def test_run_once_persists_state(isolated_monitor, monkeypatch):
    mock_run(monkeypatch, {"rev-parse": "commitX", "branch --show-current": "main"})
    w.run_once(verbose=False)
    assert w._load_state()["last_commit"] == "commitX"
