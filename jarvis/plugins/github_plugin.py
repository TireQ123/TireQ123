#!/usr/bin/env python3
"""
J.A.R.V.I.S. Plugin — GitHub Integration.
Wymaga: GITHUB_TOKEN w środowisku.
"""
import json
import os
import urllib.request
from jarvis.plugins import JarvisPlugin

GITHUB_API = "https://api.github.com"


def _gh_request(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(
        f"{GITHUB_API}{endpoint}", data=body, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def github_list_repos(username: str = "") -> dict:
    if not username:
        data = _gh_request("/user/repos?per_page=10&sort=updated")
    else:
        data = _gh_request(f"/users/{username}/repos?per_page=10&sort=updated")
    if isinstance(data, list):
        return {"repos": [{"name": r["name"], "description": r.get("description", ""),
                           "stars": r["stargazers_count"]} for r in data]}
    return data


def github_list_issues(repo: str, state: str = "open") -> dict:
    data = _gh_request(f"/repos/{repo}/issues?state={state}&per_page=10")
    if isinstance(data, list):
        return {"issues": [{"number": i["number"], "title": i["title"],
                            "state": i["state"]} for i in data if "pull_request" not in i]}
    return data


def github_list_prs(repo: str, state: str = "open") -> dict:
    data = _gh_request(f"/repos/{repo}/pulls?state={state}&per_page=10")
    if isinstance(data, list):
        return {"prs": [{"number": p["number"], "title": p["title"],
                         "user": p["user"]["login"]} for p in data]}
    return data


def github_create_issue(repo: str, title: str, body: str = "") -> dict:
    return _gh_request(f"/repos/{repo}/issues", method="POST",
                       data={"title": title, "body": body})


def github_repo_info(repo: str) -> dict:
    data = _gh_request(f"/repos/{repo}")
    if "error" not in data:
        return {
            "name": data.get("name"),
            "description": data.get("description"),
            "stars": data.get("stargazers_count"),
            "forks": data.get("forks_count"),
            "language": data.get("language"),
            "open_issues": data.get("open_issues_count"),
            "last_push": data.get("pushed_at", "")[:10]
        }
    return data


class GitHubPlugin(JarvisPlugin):
    name = "github"
    description = "Integracja z GitHub — repozytoria, issues, PR"
    enabled = bool(os.environ.get("GITHUB_TOKEN"))

    def get_tools(self):
        return [
            ("github_list_repos", github_list_repos,
             {"description": "Lista repozytoriów GitHub",
              "params": {"username": "str — opcjonalny"}}),
            ("github_list_issues", github_list_issues,
             {"description": "Issues w repozytorium",
              "params": {"repo": "str — owner/repo", "state": "open|closed"}}),
            ("github_list_prs", github_list_prs,
             {"description": "Pull requesty w repo",
              "params": {"repo": "str — owner/repo", "state": "open|closed"}}),
            ("github_create_issue", github_create_issue,
             {"description": "Tworzy nowy issue",
              "params": {"repo": "str", "title": "str", "body": "str"}}),
            ("github_repo_info", github_repo_info,
             {"description": "Informacje o repozytorium",
              "params": {"repo": "str — owner/repo"}}),
        ]

    def on_load(self):
        if not os.environ.get("GITHUB_TOKEN"):
            print("[GitHub Plugin] Brak GITHUB_TOKEN — plugin wyłączony.")


plugin = GitHubPlugin()
