#!/usr/bin/env python3
"""
J.A.R.V.I.S. Tools — zestaw narzędzi dla Agent Mode.
Każde narzędzie ma schemat JSON (jak OpenAI function calling).
"""
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


def _ok(data) -> dict:
    return {"status": "ok", "result": data}


def _err(msg: str) -> dict:
    return {"status": "error", "result": msg}


# ── Narzędzia ─────────────────────────────────────────────────────────────────

def file_read(path: str) -> dict:
    try:
        p = Path(path) if Path(path).is_absolute() else ROOT / path
        return _ok(p.read_text(encoding="utf-8"))
    except Exception as e:
        return _err(str(e))


def file_write(path: str, content: str) -> dict:
    try:
        p = Path(path) if Path(path).is_absolute() else ROOT / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return _ok(f"Zapisano {len(content)} znaków do {path}")
    except Exception as e:
        return _err(str(e))


def file_list(directory: str = ".") -> dict:
    try:
        p = Path(directory) if Path(directory).is_absolute() else ROOT / directory
        files = [str(f.relative_to(ROOT)) for f in p.rglob("*")
                 if f.is_file() and ".git" not in f.parts]
        return _ok(files[:100])
    except Exception as e:
        return _err(str(e))


def shell_run(command: str, timeout: int = 30) -> dict:
    dangerous = ["rm -rf", "format", "mkfs", "dd if=", ":(){", "shutdown", "reboot"]
    if any(d in command for d in dangerous):
        return _err(f"Komenda zablokowana ze względów bezpieczeństwa: {command}")
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True,
            text=True, timeout=timeout, cwd=str(ROOT)
        )
        output = result.stdout + result.stderr
        return _ok(output[:4000] if output else "(brak wyjścia)")
    except subprocess.TimeoutExpired:
        return _err(f"Timeout po {timeout}s")
    except Exception as e:
        return _err(str(e))


def git_status() -> dict:
    return shell_run("git status --short && git log --oneline -5")


def git_commit(message: str) -> dict:
    result = shell_run("git add -A")
    if result["status"] == "error":
        return result
    return shell_run(f'git commit -m "{message}"')


def memory_read() -> dict:
    try:
        memory_dir = ROOT / "memory"
        profile = json.loads((memory_dir / "profile.json").read_text())
        decisions = json.loads((memory_dir / "decisions.json").read_text())
        prefs = profile.get("patterns", {}).get("preferred_solutions", [])
        decs = [d["decision"] for d in decisions.get("decisions", [])[-5:]]
        return _ok({"preferences": prefs, "recent_decisions": decs})
    except Exception as e:
        return _err(str(e))


def memory_save(key: str, value: str) -> dict:
    try:
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        import memory_update as mu
        if key == "decision":
            mu.add_decision(value)
        elif key == "preference":
            mu.add_preference(value)
        elif key == "note":
            mu.add_note(value)
        else:
            return _err(f"Nieznany klucz: {key}. Użyj: decision, preference, note")
        return _ok(f"Zapisano {key}: {value}")
    except Exception as e:
        return _err(str(e))


def web_search(query: str) -> dict:
    return _err(
        "Web search wymaga klucza API (SerpAPI/Brave). "
        "Ustaw SERPAPI_KEY lub BRAVE_API_KEY w środowisku."
    )


# ── Rejestr narzędzi ──────────────────────────────────────────────────────────

TOOLS = {
    "file_read":    file_read,
    "file_write":   file_write,
    "file_list":    file_list,
    "shell_run":    shell_run,
    "git_status":   git_status,
    "git_commit":   git_commit,
    "memory_read":  memory_read,
    "memory_save":  memory_save,
    "web_search":   web_search,
}

TOOLS_SCHEMA = [
    {"name": "file_read",   "description": "Czyta plik z projektu",
     "params": {"path": "str — ścieżka do pliku"}},
    {"name": "file_write",  "description": "Tworzy lub nadpisuje plik",
     "params": {"path": "str", "content": "str — treść pliku"}},
    {"name": "file_list",   "description": "Listuje pliki w katalogu",
     "params": {"directory": "str — domyślnie '.'"}},
    {"name": "shell_run",   "description": "Uruchamia komendę bash",
     "params": {"command": "str", "timeout": "int — domyślnie 30"}},
    {"name": "git_status",  "description": "Pokazuje status git i ostatnie commity",
     "params": {}},
    {"name": "git_commit",  "description": "Commituje wszystkie zmiany",
     "params": {"message": "str — treść commita"}},
    {"name": "memory_read", "description": "Czyta pamięć Jarvisa (preferencje, decyzje)",
     "params": {}},
    {"name": "memory_save", "description": "Zapisuje do pamięci Jarvisa",
     "params": {"key": "decision|preference|note", "value": "str"}},
    {"name": "web_search",  "description": "Przeszukuje internet (wymaga klucza API)",
     "params": {"query": "str"}},
]


def execute_tool(name: str, params: dict) -> dict:
    if name not in TOOLS:
        return _err(f"Nieznane narzędzie: {name}")
    try:
        return TOOLS[name](**params)
    except TypeError as e:
        return _err(f"Złe parametry dla {name}: {e}")
