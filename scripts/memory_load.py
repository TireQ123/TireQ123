#!/usr/bin/env python3
"""
J.A.R.V.I.S. Memory Load — Faza A
Generuje kontekst sesji na podstawie zapisanej pamięci.
Wynik wstrzykiwany jest do CLAUDE.md przy starcie sesji.

Użycie:
  python scripts/memory_load.py
  python scripts/memory_load.py --update-claude
"""

import json
import argparse
from pathlib import Path
from datetime import datetime

MEMORY_DIR = Path(__file__).parent.parent / "memory"
PROFILE_FILE = MEMORY_DIR / "profile.json"
DECISIONS_FILE = MEMORY_DIR / "decisions.json"
SESSIONS_DIR = MEMORY_DIR / "sessions"
CLAUDE_FILE = Path(__file__).parent.parent / "CLAUDE.md"
CONTEXT_MARKER_START = "<!-- JARVIS:MEMORY:START -->"
CONTEXT_MARKER_END = "<!-- JARVIS:MEMORY:END -->"


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_last_sessions(n: int = 3) -> list[dict]:
    if not SESSIONS_DIR.exists():
        return []
    files = sorted(SESSIONS_DIR.glob("*.json"), reverse=True)[:n]
    return [load_json(f) for f in files]


def build_context() -> str:
    profile = load_json(PROFILE_FILE)
    decisions = load_json(DECISIONS_FILE)
    sessions = get_last_sessions(3)

    lines = [
        f"{CONTEXT_MARKER_START}",
        f"## Załadowana pamięć — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    preferred = profile["patterns"]["preferred_solutions"]
    if preferred:
        lines.append("### Preferencje techniczne")
        for p in preferred:
            lines.append(f"- {p}")
        lines.append("")

    avoided = profile["patterns"]["avoided_approaches"]
    if avoided:
        lines.append("### Unikane podejścia")
        for a in avoided:
            lines.append(f"- {a}")
        lines.append("")

    recent_decisions = decisions["decisions"][-5:]
    if recent_decisions:
        lines.append("### Ostatnie decyzje techniczne")
        for d in recent_decisions:
            lines.append(f"- [{d['date'][:10]}] {d['decision']}")
        lines.append("")

    recent_notes = profile["notes"][-5:]
    if recent_notes:
        lines.append("### Aktywne notatki")
        for n in recent_notes:
            lines.append(f"- [{n['date'][:10]}] {n['note']}")
        lines.append("")

    if sessions:
        lines.append("### Ostatnie sesje")
        for s in sessions:
            lines.append(f"- [{s['date'][:10]}] {s['summary']}")
        lines.append("")

    lines.append(CONTEXT_MARKER_END)
    return "\n".join(lines)


def update_claude_md(context: str) -> None:
    content = CLAUDE_FILE.read_text(encoding="utf-8")

    if CONTEXT_MARKER_START in content:
        start = content.index(CONTEXT_MARKER_START)
        end = content.index(CONTEXT_MARKER_END) + len(CONTEXT_MARKER_END)
        content = content[:start] + context + content[end:]
    else:
        content = content.rstrip() + "\n\n" + context + "\n"

    CLAUDE_FILE.write_text(content, encoding="utf-8")
    print("[JARVIS] CLAUDE.md zaktualizowany z aktualną pamięcią.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. Memory Load")
    parser.add_argument(
        "--update-claude",
        action="store_true",
        help="Wstrzyknij pamięć do CLAUDE.md"
    )
    args = parser.parse_args()

    context = build_context()

    if args.update_claude:
        update_claude_md(context)
    else:
        print(context)
