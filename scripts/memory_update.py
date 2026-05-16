#!/usr/bin/env python3
"""
J.A.R.V.I.S. Memory Update — Faza A
Zapisuje nowe obserwacje do pamięci po sesji.

Użycie:
  python scripts/memory_update.py --preference "preferuje TypeScript nad JavaScript"
  python scripts/memory_update.py --decision "używamy FastAPI jako backend"
  python scripts/memory_update.py --note "projekt X ma deadline 2026-06-01"
  python scripts/memory_update.py --task "budowanie REST API"
"""

import json
import argparse
from datetime import datetime
from pathlib import Path

MEMORY_DIR = Path(__file__).parent.parent / "memory"
PROFILE_FILE = MEMORY_DIR / "profile.json"
DECISIONS_FILE = MEMORY_DIR / "decisions.json"
SESSIONS_DIR = MEMORY_DIR / "sessions"


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_preference(value: str) -> None:
    profile = load_json(PROFILE_FILE)
    if value not in profile["preferences"]["frameworks"] and \
       value not in profile["patterns"]["preferred_solutions"]:
        profile["patterns"]["preferred_solutions"].append(value)
        save_json(PROFILE_FILE, profile)
        print(f"[JARVIS] Preferencja zapisana: {value}")


def add_decision(value: str) -> None:
    decisions = load_json(DECISIONS_FILE)
    entry = {
        "date": datetime.now().isoformat(timespec="seconds"),
        "decision": value
    }
    decisions["decisions"].append(entry)
    save_json(DECISIONS_FILE, decisions)
    print(f"[JARVIS] Decyzja zapisana: {value}")


def add_note(value: str) -> None:
    profile = load_json(PROFILE_FILE)
    entry = {
        "date": datetime.now().isoformat(timespec="seconds"),
        "note": value
    }
    profile["notes"].append(entry)
    save_json(PROFILE_FILE, profile)
    print(f"[JARVIS] Notatka zapisana: {value}")


def add_task(value: str) -> None:
    profile = load_json(PROFILE_FILE)
    tasks = profile["patterns"]["common_tasks"]
    if value not in tasks:
        tasks.append(value)
        save_json(PROFILE_FILE, profile)
        print(f"[JARVIS] Zadanie dodane do wzorców: {value}")


def save_session(summary: str) -> None:
    SESSIONS_DIR.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
    session_file = SESSIONS_DIR / f"{date_str}.json"
    data = {
        "date": datetime.now().isoformat(timespec="seconds"),
        "summary": summary
    }
    save_json(session_file, data)
    print(f"[JARVIS] Sesja zapisana: {session_file.name}")


def show_memory() -> None:
    profile = load_json(PROFILE_FILE)
    decisions = load_json(DECISIONS_FILE)

    print("\n=== JARVIS MEMORY REPORT ===")
    print(f"Użytkownik: {profile['user']['name']} ({profile['user']['alias']})")
    print(f"\nPreferencje: {profile['preferences']}")
    print(f"\nWzorce:")
    for k, v in profile["patterns"].items():
        print(f"  {k}: {v}")
    print(f"\nOstatnie decyzje ({len(decisions['decisions'])}):")
    for d in decisions["decisions"][-5:]:
        print(f"  [{d['date']}] {d['decision']}")
    print(f"\nNotatki ({len(profile['notes'])}):")
    for n in profile["notes"][-5:]:
        print(f"  [{n['date']}] {n['note']}")
    print("============================\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. Memory Update")
    parser.add_argument("--preference", help="Dodaj preferencję użytkownika")
    parser.add_argument("--decision", help="Zapisz decyzję techniczną")
    parser.add_argument("--note", help="Dodaj notatkę")
    parser.add_argument("--task", help="Dodaj wzorzec zadania")
    parser.add_argument("--session", help="Zapisz podsumowanie sesji")
    parser.add_argument("--show", action="store_true", help="Pokaż całą pamięć")
    args = parser.parse_args()

    if args.preference:
        add_preference(args.preference)
    if args.decision:
        add_decision(args.decision)
    if args.note:
        add_note(args.note)
    if args.task:
        add_task(args.task)
    if args.session:
        save_session(args.session)
    if args.show:
        show_memory()
    if not any(vars(args).values()):
        parser.print_help()
