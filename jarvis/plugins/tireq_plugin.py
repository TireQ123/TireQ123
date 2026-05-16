#!/usr/bin/env python3
"""
J.A.R.V.I.S. Plugin — TireQ Personal Workflow
Plugin skrojony pod konkretny workflow Marcela (TireQ).

Narzędzia:
  tireq_briefing     — poranny briefing: git, kalendarz, pamięć, dane treningowe
  tireq_project_init — inicjalizuje nowy projekt wg standardów TireQ
  tireq_daily_log    — zapisuje dzienny log pracy
  tireq_quick_commit — inteligentny commit z opisem generowanym przez AI
  tireq_health_check — pełny przegląd stanu systemu Jarvisa
"""
import json
import subprocess
from datetime import datetime
from pathlib import Path
from jarvis.plugins import JarvisPlugin

ROOT = Path(__file__).parent.parent.parent


def _run(cmd: str) -> str:
    try:
        return subprocess.check_output(
            cmd, shell=True, cwd=ROOT,
            stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        return ""


def tireq_briefing() -> dict:
    lines = [f"=== BRIEFING — {datetime.now().strftime('%A, %d %B %Y %H:%M')} ===\n"]

    # Git
    git_status = _run("git status --short")
    git_log = _run("git log --oneline -3")
    branch = _run("git branch --show-current")
    lines.append(f"GIT [{branch}]:")
    if git_status:
        lines.append(f"  Zmiany: {len(git_status.splitlines())} plików")
    lines.append(f"  Ostatnie:\n" + "\n".join(f"    {l}" for l in git_log.splitlines()))

    # Pamięć
    try:
        profile = json.loads((ROOT / "memory/profile.json").read_text())
        decisions = json.loads((ROOT / "memory/decisions.json").read_text())
        prefs = profile.get("patterns", {}).get("preferred_solutions", [])
        recent_dec = decisions.get("decisions", [])[-2:]
        lines.append(f"\nPAMIĘĆ:")
        if prefs:
            lines.append(f"  Preferencja: {prefs[-1]}")
        if recent_dec:
            lines.append(f"  Ostatnia decyzja: {recent_dec[-1]['decision']}")
    except Exception:
        pass

    # Kalendarz
    try:
        from jarvis.plugins.calendar_plugin import calendar_today, calendar_remind
        today = calendar_today()["result"]
        remind = calendar_remind()["result"]
        lines.append(f"\nKALENDARZ:\n  {today}\n  {remind}")
    except Exception:
        pass

    # Dane treningowe
    raw = ROOT / "training/raw_pairs.jsonl"
    if raw.exists():
        count = sum(1 for _ in raw.open())
        needed = max(0, 100 - count)
        lines.append(f"\nDANE TRENINGOWE: {count}/100 par "
                     f"({'gotowe do fine-tuningu!' if needed == 0 else f'brakuje {needed}'})")

    lines.append("\n=== JARVIS GOTOWY DO PRACY ===")
    return {"status": "ok", "result": "\n".join(lines)}


def tireq_project_init(name: str, stack: str = "python") -> dict:
    project_dir = ROOT.parent / name
    if project_dir.exists():
        return {"status": "error", "result": f"Projekt '{name}' już istnieje."}

    structures = {
        "python": [
            f"{name}/src/{name.replace('-','_')}/__init__.py",
            f"{name}/tests/__init__.py",
            f"{name}/tests/test_main.py",
            f"{name}/.env.example",
            f"{name}/.gitignore",
            f"{name}/requirements.txt",
            f"{name}/README.md",
        ],
        "fastapi": [
            f"{name}/app/api/__init__.py",
            f"{name}/app/core/__init__.py",
            f"{name}/app/models/__init__.py",
            f"{name}/app/schemas/__init__.py",
            f"{name}/app/services/__init__.py",
            f"{name}/app/main.py",
            f"{name}/tests/__init__.py",
            f"{name}/.env.example",
            f"{name}/.gitignore",
            f"{name}/requirements.txt",
            f"{name}/Dockerfile",
            f"{name}/README.md",
        ],
        "react": [
            f"{name}/src/components/.gitkeep",
            f"{name}/src/hooks/.gitkeep",
            f"{name}/src/utils/.gitkeep",
            f"{name}/src/App.tsx",
            f"{name}/src/main.tsx",
            f"{name}/public/index.html",
            f"{name}/.gitignore",
            f"{name}/README.md",
        ]
    }

    files = structures.get(stack, structures["python"])
    created = []
    for filepath in files:
        p = ROOT.parent / filepath
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.write_text("")
            created.append(filepath)

    gitignore_content = "__pycache__/\n*.pyc\n.env\n.venv/\ndist/\nbuild/\n*.egg-info/\n.DS_Store\nnode_modules/\n"
    gi = ROOT.parent / name / ".gitignore"
    gi.write_text(gitignore_content)

    return {
        "status": "ok",
        "result": (
            f"Projekt '{name}' ({stack}) zainicjalizowany.\n"
            f"Utworzono {len(created)} plików.\n"
            f"Ścieżka: {project_dir}"
        )
    }


def tireq_daily_log(summary: str) -> dict:
    logs_dir = ROOT / "memory" / "daily_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = logs_dir / f"{today}.md"

    entry = (
        f"\n## {datetime.now().strftime('%H:%M')}\n"
        f"{summary}\n"
    )

    if not log_file.exists():
        log_file.write_text(f"# Log — {today}\n" + entry)
    else:
        log_file.write_text(log_file.read_text() + entry)

    return {"status": "ok", "result": f"Log zapisany: {log_file.name}"}


def tireq_quick_commit() -> dict:
    status = _run("git status --short")
    if not status:
        return {"status": "ok", "result": "Brak zmian do commitowania."}

    diff = _run("git diff --stat HEAD")
    files = [line.split("|")[0].strip() for line in status.splitlines()][:5]

    _run("git add -A")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"Update: {', '.join(files[:3])}{'...' if len(files) > 3 else ''}"
    result = _run(f'git commit -m "{msg}"')

    return {
        "status": "ok",
        "result": f"Commit: {msg}\n{result}"
    }


def tireq_health_check() -> dict:
    lines = ["=== JARVIS HEALTH CHECK ===\n"]

    checks = [
        ("Python", lambda: __import__("sys").version.split()[0]),
        ("ChromaDB", lambda: __import__("chromadb").__version__),
        ("FastAPI", lambda: __import__("fastapi").__version__),
        ("Pamięć profile.json", lambda: "OK" if (ROOT / "memory/profile.json").exists() else "BRAK"),
        ("Dane treningowe", lambda: f"{sum(1 for _ in open(ROOT/'training/raw_pairs.jsonl'))} par"),
        ("Pluginy", lambda: (
            __import__("jarvis.plugins", fromlist=["registry"]).registry.load_all(),
            str(__import__("jarvis.plugins", fromlist=["registry"]).registry.list_plugins())
        )[-1]),
    ]

    for name, fn in checks:
        try:
            result = fn()
            lines.append(f"  ✓ {name}: {result}")
        except Exception as e:
            lines.append(f"  ✗ {name}: {e}")

    lines.append("\n===========================")
    return {"status": "ok", "result": "\n".join(lines)}


class TireQPlugin(JarvisPlugin):
    name = "tireq"
    description = "Osobisty workflow plugin dla TireQ"
    enabled = True

    def get_tools(self):
        return [
            ("tireq_briefing", tireq_briefing,
             {"description": "Poranny briefing: git, kalendarz, pamięć, dane",
              "params": {}}),
            ("tireq_project_init", tireq_project_init,
             {"description": "Inicjalizuje nowy projekt wg standardów TireQ",
              "params": {"name": "str — nazwa projektu", "stack": "python|fastapi|react"}}),
            ("tireq_daily_log", tireq_daily_log,
             {"description": "Zapisuje dzienny log pracy",
              "params": {"summary": "str — co zrobiono"}}),
            ("tireq_quick_commit", tireq_quick_commit,
             {"description": "Commituje wszystkie zmiany z auto-opisem",
              "params": {}}),
            ("tireq_health_check", tireq_health_check,
             {"description": "Pełny przegląd stanu systemu Jarvisa",
              "params": {}}),
        ]


plugin = TireQPlugin()
