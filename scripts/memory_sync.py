#!/usr/bin/env python3
"""
J.A.R.V.I.S. Memory Sync — automatyczny, odporny na śmiecenie.

Uruchamiany przez hook Stop po każdej turze Claude Code.
Czyta transkrypt sesji, wyciąga wiedzę heurystyką,
deduplikuje i zapisuje tylko nowe, wartościowe informacje.

Env vars (ustawiane przez Claude Code):
  CLAUDE_TRANSCRIPT_PATH  — ścieżka do JSON transkryptu
  CLAUDE_SESSION_ID       — ID sesji
"""

import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).parent.parent
MEMORY_DIR = ROOT / "memory"
PROFILE_FILE = MEMORY_DIR / "profile.json"
DECISIONS_FILE = MEMORY_DIR / "decisions.json"
SESSIONS_DIR = MEMORY_DIR / "sessions"
STATE_FILE = MEMORY_DIR / ".sync_state.json"

# Minimalny odstęp między syncami (sekundy)
SYNC_INTERVAL_SECONDS = 120

# Próg podobieństwa — powyżej tego nie dodajemy duplikatu
SIMILARITY_THRESHOLD = 0.82

# Maksymalna liczba wpisów przed archiwizacją
MAX_DECISIONS = 50
MAX_NOTES = 30
MAX_PREFERRED = 20


# ── Pomocnicze ────────────────────────────────────────────────────────────────

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
    text = unicodedata.normalize("NFKD", text.lower().strip())
    text = re.sub(r"\s+", " ", text)
    return text


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def is_duplicate(candidate: str, existing: list[str]) -> bool:
    n = normalize(candidate)
    for e in existing:
        if similarity(n, normalize(e)) >= SIMILARITY_THRESHOLD:
            return True
    return False


# ── Throttle ──────────────────────────────────────────────────────────────────

def should_sync() -> bool:
    state = load_json(STATE_FILE)
    last = state.get("last_sync")
    if not last:
        return True
    delta = datetime.now() - datetime.fromisoformat(last)
    return delta.total_seconds() >= SYNC_INTERVAL_SECONDS


def mark_synced() -> None:
    save_json(STATE_FILE, {"last_sync": datetime.now().isoformat(timespec="seconds")})


# ── Ekstrakcja wiedzy z transkryptu ───────────────────────────────────────────

# Wzorce wyciągające decyzje i preferencje z naturalnego języka
DECISION_PATTERNS = [
    r"używam[y]?\s+(.{5,60}?)(?:\.|,|$)",
    r"wybieramy\s+(.{5,60}?)(?:\.|,|$)",
    r"decydujemy\s+(?:się\s+na\s+)?(.{5,60}?)(?:\.|,|$)",
    r"stack[:\s]+(.{5,80}?)(?:\.|,|\n|$)",
    r"framework[:\s]+(.{5,60}?)(?:\.|,|\n|$)",
    r"baza\s+danych[:\s]+(.{5,60}?)(?:\.|,|\n|$)",
]

PREFERENCE_PATTERNS = [
    r"preferuj[ęe]\s+(.{5,60}?)(?:\.|,|$)",
    r"wolę\s+(.{5,60}?)(?:\.|,|$)",
    r"lubię\s+(.{5,60}?)(?:\.|,|$)",
    r"lepiej\s+mi\s+z\s+(.{5,60}?)(?:\.|,|$)",
]

NOTE_PATTERNS = [
    r"deadline[:\s]+(.{5,80}?)(?:\.|,|\n|$)",
    r"termin[:\s]+(.{5,80}?)(?:\.|,|\n|$)",
    r"pamiętaj(?:cie)?,?\s+że\s+(.{10,120}?)(?:\.|$)",
    r"ważne[:\s]+(.{10,120}?)(?:\.|$)",
]


def extract_from_transcript(transcript_path: str) -> dict:
    extracted = {"decisions": [], "preferences": [], "notes": []}
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return extracted

    # Zbierz tekst z wiadomości użytkownika i asystenta
    messages = data if isinstance(data, list) else data.get("messages", [])
    texts = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role in ("user", "assistant") and isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))

    full_text = " ".join(texts)

    for pattern in DECISION_PATTERNS:
        for match in re.finditer(pattern, full_text, re.IGNORECASE):
            val = match.group(1).strip().rstrip(".,")
            if len(val) > 4:
                extracted["decisions"].append(val)

    for pattern in PREFERENCE_PATTERNS:
        for match in re.finditer(pattern, full_text, re.IGNORECASE):
            val = match.group(1).strip().rstrip(".,")
            if len(val) > 4:
                extracted["preferences"].append(val)

    for pattern in NOTE_PATTERNS:
        for match in re.finditer(pattern, full_text, re.IGNORECASE):
            val = match.group(1).strip().rstrip(".,")
            if len(val) > 4:
                extracted["notes"].append(val)

    return extracted


# ── Zapis z deduplikacją ──────────────────────────────────────────────────────

def merge_decisions(new_items: list[str]) -> int:
    data = load_json(DECISIONS_FILE)
    if "decisions" not in data:
        data["decisions"] = []

    existing_texts = [d["decision"] for d in data["decisions"]]
    added = 0

    for item in new_items:
        if not is_duplicate(item, existing_texts):
            data["decisions"].append({
                "date": datetime.now().isoformat(timespec="seconds"),
                "decision": item,
                "source": "auto"
            })
            existing_texts.append(item)
            added += 1

    # Archiwizuj jeśli za dużo wpisów
    if len(data["decisions"]) > MAX_DECISIONS:
        archive_path = MEMORY_DIR / "archive" / f"decisions_{datetime.now().strftime('%Y-%m')}.json"
        archive_path.parent.mkdir(exist_ok=True)
        old = load_json(archive_path)
        old.setdefault("decisions", []).extend(data["decisions"][:-MAX_DECISIONS])
        save_json(archive_path, old)
        data["decisions"] = data["decisions"][-MAX_DECISIONS:]

    save_json(DECISIONS_FILE, data)
    return added


def merge_profile(new_prefs: list[str], new_notes: list[str]) -> int:
    profile = load_json(PROFILE_FILE)
    profile.setdefault("patterns", {}).setdefault("preferred_solutions", [])
    profile.setdefault("notes", [])

    existing_prefs = profile["patterns"]["preferred_solutions"]
    existing_notes_texts = [n["note"] if isinstance(n, dict) else n for n in profile["notes"]]
    added = 0

    for pref in new_prefs:
        if not is_duplicate(pref, existing_prefs):
            existing_prefs.append(pref)
            added += 1

    if len(existing_prefs) > MAX_PREFERRED:
        profile["patterns"]["preferred_solutions"] = existing_prefs[-MAX_PREFERRED:]

    for note in new_notes:
        if not is_duplicate(note, existing_notes_texts):
            profile["notes"].append({
                "date": datetime.now().isoformat(timespec="seconds"),
                "note": note,
                "source": "auto"
            })
            existing_notes_texts.append(note)
            added += 1

    if len(profile["notes"]) > MAX_NOTES:
        profile["notes"] = profile["notes"][-MAX_NOTES:]

    save_json(PROFILE_FILE, profile)
    return added


# ── Główny przebieg ───────────────────────────────────────────────────────────

def main() -> None:
    if not should_sync():
        return

    transcript_path = os.environ.get("CLAUDE_TRANSCRIPT_PATH", "")
    if not transcript_path or not Path(transcript_path).exists():
        mark_synced()
        return

    extracted = extract_from_transcript(transcript_path)

    total = 0
    total += merge_decisions(extracted["decisions"])
    total += merge_profile(extracted["preferences"], extracted["notes"])

    mark_synced()

    if total > 0:
        print(f"[JARVIS] Sync: +{total} nowych wpisów w pamięci.")


if __name__ == "__main__":
    main()
