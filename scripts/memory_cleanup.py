#!/usr/bin/env python3
"""
J.A.R.V.I.S. Memory Cleanup — konsolidacja i archiwizacja.

Uruchamiaj raz w tygodniu:
  python scripts/memory_cleanup.py

Scala wpisy starsze niż 30 dni do archiwum,
usuwa duplikaty które przeszły przez sito synca,
generuje tygodniowe podsumowanie sesji.
"""

import json
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).parent.parent
MEMORY_DIR = ROOT / "memory"
PROFILE_FILE = MEMORY_DIR / "profile.json"
DECISIONS_FILE = MEMORY_DIR / "decisions.json"
SESSIONS_DIR = MEMORY_DIR / "sessions"
ARCHIVE_DIR = MEMORY_DIR / "archive"

ARCHIVE_AFTER_DAYS = 30
SIMILARITY_THRESHOLD = 0.78


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def deduplicate(items: list, key_fn) -> list:
    unique = []
    seen = []
    for item in items:
        text = normalize(key_fn(item))
        is_dup = any(
            SequenceMatcher(None, text, normalize(key_fn(u))).ratio() >= SIMILARITY_THRESHOLD
            for u in seen
        )
        if not is_dup:
            unique.append(item)
            seen.append(item)
    return unique


def cleanup_decisions() -> tuple[int, int]:
    data = load_json(DECISIONS_FILE)
    decisions = data.get("decisions", [])
    original_count = len(decisions)

    cutoff = datetime.now() - timedelta(days=ARCHIVE_AFTER_DAYS)
    fresh, old = [], []

    for d in decisions:
        try:
            dt = datetime.fromisoformat(d["date"])
            (old if dt < cutoff else fresh).append(d)
        except Exception:
            fresh.append(d)

    # Archiwizuj stare
    if old:
        month_key = datetime.now().strftime("%Y-%m")
        archive_file = ARCHIVE_DIR / f"decisions_{month_key}.json"
        archive = load_json(archive_file)
        archive.setdefault("decisions", []).extend(old)
        archive["decisions"] = deduplicate(
            archive["decisions"], lambda x: x["decision"]
        )
        save_json(archive_file, archive)

    # Deduplikuj świeże
    fresh = deduplicate(fresh, lambda x: x["decision"])
    data["decisions"] = fresh
    save_json(DECISIONS_FILE, data)

    return original_count, len(fresh)


def cleanup_profile() -> tuple[int, int]:
    profile = load_json(PROFILE_FILE)
    original_notes = len(profile.get("notes", []))

    # Deduplikuj preferencje
    prefs = profile.get("patterns", {}).get("preferred_solutions", [])
    profile["patterns"]["preferred_solutions"] = deduplicate(prefs, lambda x: x)

    # Archiwizuj stare notatki
    notes = profile.get("notes", [])
    cutoff = datetime.now() - timedelta(days=ARCHIVE_AFTER_DAYS)
    fresh_notes, old_notes = [], []

    for n in notes:
        try:
            dt = datetime.fromisoformat(n["date"] if isinstance(n, dict) else "2000-01-01")
            (old_notes if dt < cutoff else fresh_notes).append(n)
        except Exception:
            fresh_notes.append(n)

    if old_notes:
        month_key = datetime.now().strftime("%Y-%m")
        archive_file = ARCHIVE_DIR / f"notes_{month_key}.json"
        archive = load_json(archive_file)
        archive.setdefault("notes", []).extend(old_notes)
        save_json(archive_file, archive)

    profile["notes"] = deduplicate(fresh_notes, lambda x: x["note"] if isinstance(x, dict) else x)
    save_json(PROFILE_FILE, profile)

    return original_notes, len(profile["notes"])


def consolidate_sessions() -> int:
    if not SESSIONS_DIR.exists():
        return 0

    files = sorted(SESSIONS_DIR.glob("*.json"))
    cutoff = datetime.now() - timedelta(days=ARCHIVE_AFTER_DAYS)
    archived = 0

    for f in files:
        try:
            data = load_json(f)
            dt = datetime.fromisoformat(data.get("date", "2000-01-01"))
            if dt < cutoff:
                month_key = dt.strftime("%Y-%m")
                archive_file = ARCHIVE_DIR / f"sessions_{month_key}.json"
                archive = load_json(archive_file)
                archive.setdefault("sessions", []).append(data)
                save_json(archive_file, archive)
                f.unlink()
                archived += 1
        except Exception:
            pass

    return archived


def report() -> None:
    d_before, d_after = cleanup_decisions()
    n_before, n_after = cleanup_profile()
    s_archived = consolidate_sessions()

    print("\n=== JARVIS CLEANUP REPORT ===")
    print(f"Decyzje:  {d_before} → {d_after} (usunięto {d_before - d_after} duplikatów/archiwum)")
    print(f"Notatki:  {n_before} → {n_after} (usunięto {n_before - n_after})")
    print(f"Sesje archiwizowane: {s_archived}")
    print(f"Archiwum: {ARCHIVE_DIR}/")
    print("=============================\n")


if __name__ == "__main__":
    report()
