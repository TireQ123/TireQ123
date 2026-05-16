"""Testy jarvis/plugins/github_plugin.py — z mockowaniem HTTP."""
import json
import urllib.error

import pytest

from jarvis.plugins import github_plugin as gh


class FakeResp:
    def __init__(self, payload):
        self._data = json.dumps(payload).encode()

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def mock_response(monkeypatch, payload):
    monkeypatch.setattr(gh.urllib.request, "urlopen",
                        lambda *a, **k: FakeResp(payload))


def mock_raise(monkeypatch, exc):
    def boom(*a, **k):
        raise exc
    monkeypatch.setattr(gh.urllib.request, "urlopen", boom)


# ── _gh_request ──────────────────────────────────────────────────────────────

def test_gh_request_success(monkeypatch):
    mock_response(monkeypatch, {"login": "tireq"})
    assert gh._gh_request("/user") == {"login": "tireq"}


def test_gh_request_http_error(monkeypatch):
    err = urllib.error.HTTPError("u", 404, "Not Found", {}, None)
    mock_raise(monkeypatch, err)
    out = gh._gh_request("/repos/x/y")
    assert out == {"error": "HTTP 404: Not Found"}


def test_gh_request_generic_error(monkeypatch):
    mock_raise(monkeypatch, OSError("timeout"))
    out = gh._gh_request("/user")
    assert "error" in out
    assert "timeout" in out["error"]


# ── github_list_repos ────────────────────────────────────────────────────────

def test_list_repos_authenticated(monkeypatch):
    mock_response(monkeypatch, [
        {"name": "jarvis", "description": "AI", "stargazers_count": 42},
    ])
    out = gh.github_list_repos()
    assert out["repos"][0]["name"] == "jarvis"
    assert out["repos"][0]["stars"] == 42


def test_list_repos_by_username(monkeypatch):
    captured = {}
    monkeypatch.setattr(gh, "_gh_request",
                        lambda ep, **k: captured.setdefault("ep", ep) or [])
    gh.github_list_repos("octocat")
    assert "/users/octocat/repos" in captured["ep"]


def test_list_repos_error_passthrough(monkeypatch):
    monkeypatch.setattr(gh, "_gh_request", lambda *a, **k: {"error": "HTTP 401"})
    assert gh.github_list_repos() == {"error": "HTTP 401"}


# ── github_list_issues ───────────────────────────────────────────────────────

def test_list_issues_filters_pull_requests(monkeypatch):
    mock_response(monkeypatch, [
        {"number": 1, "title": "bug", "state": "open"},
        {"number": 2, "title": "PR", "state": "open", "pull_request": {}},
    ])
    out = gh.github_list_issues("o/r")
    assert len(out["issues"]) == 1
    assert out["issues"][0]["number"] == 1


def test_list_issues_error_passthrough(monkeypatch):
    monkeypatch.setattr(gh, "_gh_request", lambda *a, **k: {"error": "x"})
    assert gh.github_list_issues("o/r") == {"error": "x"}


# ── github_list_prs ──────────────────────────────────────────────────────────

def test_list_prs_success(monkeypatch):
    mock_response(monkeypatch, [
        {"number": 7, "title": "feat", "user": {"login": "tireq"}},
    ])
    out = gh.github_list_prs("o/r")
    assert out["prs"][0]["user"] == "tireq"
    assert out["prs"][0]["number"] == 7


# ── github_create_issue ──────────────────────────────────────────────────────

def test_create_issue_posts_payload(monkeypatch):
    seen = {}

    def fake(ep, method="GET", data=None):
        seen.update(ep=ep, method=method, data=data)
        return {"number": 99}
    monkeypatch.setattr(gh, "_gh_request", fake)
    out = gh.github_create_issue("o/r", "Tytuł", "treść")
    assert seen["method"] == "POST"
    assert seen["data"] == {"title": "Tytuł", "body": "treść"}
    assert out["number"] == 99


# ── github_repo_info ─────────────────────────────────────────────────────────

def test_repo_info_success(monkeypatch):
    mock_response(monkeypatch, {
        "name": "jarvis", "description": "AI", "stargazers_count": 10,
        "forks_count": 3, "language": "Python", "open_issues_count": 2,
        "pushed_at": "2026-05-16T12:00:00Z",
    })
    out = gh.github_repo_info("tireq/jarvis")
    assert out["name"] == "jarvis"
    assert out["stars"] == 10
    assert out["last_push"] == "2026-05-16"


def test_repo_info_error_passthrough(monkeypatch):
    monkeypatch.setattr(gh, "_gh_request", lambda *a, **k: {"error": "HTTP 404"})
    assert gh.github_repo_info("x/y") == {"error": "HTTP 404"}


# ── Plugin metadata ──────────────────────────────────────────────────────────

def test_plugin_exposes_five_tools():
    names = {t[0] for t in gh.plugin.get_tools()}
    assert names == {
        "github_list_repos", "github_list_issues", "github_list_prs",
        "github_create_issue", "github_repo_info",
    }


def test_plugin_name():
    assert gh.plugin.name == "github"
