#!/usr/bin/env python3
"""
J.A.R.V.I.S. Training Collect — Faza C
Zbiera surowe dane z transkryptów sesji Claude Code.
Wyciąga pary (user → assistant) które nadają się do treningu.

Użycie:
  python scripts/training_collect.py --transcript /path/to/transcript.json
  python scripts/training_collect.py --all-sessions
  python scripts/training_collect.py --show-stats
"""

import argparse
import json
import re
import hashlib
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
MEMORY_DIR = ROOT / "memory"
TRAINING_DIR = ROOT / "training"
RAW_FILE = TRAINING_DIR / "raw_pairs.jsonl"
STATS_FILE = TRAINING_DIR / "stats.json"

SYSTEM_PROMPT = (
    "Jesteś J.A.R.V.I.S. — osobisty asystent AI Marcela (TireQ). "
    "Odpowiadasz po polsku, elegancko i precyzyjnie. "
    "Zwracasz się 'Panie TireQ'. Nigdy nie mówisz 'nie mogę' bez alternatywy. "
    "Jesteś wszechstronny: kod, architektura, analiza, planowanie."
)

# Minimalna długość odpowiedzi asystenta (chars) — odfiltruj śmieciowe pary
MIN_ASSISTANT_LENGTH = 80
# Maksymalna długość wiadomości do treningu (tokeny ~4 chars)
MAX_CHARS = 8000


def load_transcript(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("messages", [])


def extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return " ".join(parts)
    return ""


def is_quality_pair(user_text: str, assistant_text: str) -> bool:
    if len(assistant_text) < MIN_ASSISTANT_LENGTH:
        return False
    if len(user_text) + len(assistant_text) > MAX_CHARS:
        return False
    # Odfiltruj czysto techniczne wiadomości (same komendy bash)
    if assistant_text.strip().startswith("```") and "\n" not in assistant_text[:50]:
        return False
    return True


def score_pair(user_text: str, assistant_text: str) -> float:
    """Ocena jakości pary 0-1."""
    score = 0.5

    # Długość odpowiedzi — im dłuższa tym lepsza (do pewnego limitu)
    length_score = min(len(assistant_text) / 500, 1.0) * 0.2
    score += length_score

    # Polskie słowa w odpowiedzi
    polish_words = ["Panie", "TireQ", "jest", "się", "nie", "tak", "jak", "że"]
    polish_count = sum(1 for w in polish_words if w in assistant_text)
    score += min(polish_count / len(polish_words), 1.0) * 0.2

    # Zawiera kod (wartościowe dla fine-tuningu)
    if "```" in assistant_text:
        score += 0.1

    return round(min(score, 1.0), 3)


def extract_pairs(messages: list[dict]) -> list[dict]:
    pairs = []
    i = 0
    while i < len(messages) - 1:
        msg = messages[i]
        next_msg = messages[i + 1]

        if msg.get("role") == "user" and next_msg.get("role") == "assistant":
            user_text = extract_text(msg.get("content", "")).strip()
            assistant_text = extract_text(next_msg.get("content", "")).strip()

            if is_quality_pair(user_text, assistant_text):
                pair_id = hashlib.md5(
                    f"{user_text[:100]}{assistant_text[:100]}".encode()
                ).hexdigest()[:12]

                pairs.append({
                    "id": pair_id,
                    "collected_at": datetime.now().isoformat(timespec="seconds"),
                    "score": score_pair(user_text, assistant_text),
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_text},
                        {"role": "assistant", "content": assistant_text}
                    ]
                })
        i += 1

    return pairs


def load_existing_ids() -> set[str]:
    if not RAW_FILE.exists():
        return set()
    ids = set()
    with open(RAW_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                ids.add(json.loads(line)["id"])
            except Exception:
                pass
    return ids


def append_pairs(pairs: list[dict]) -> int:
    if not pairs:
        return 0
    existing = load_existing_ids()
    new_pairs = [p for p in pairs if p["id"] not in existing]

    TRAINING_DIR.mkdir(exist_ok=True)
    with open(RAW_FILE, "a", encoding="utf-8") as f:
        for p in new_pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    return len(new_pairs)


def collect_from_transcript(transcript_path: str) -> int:
    messages = load_transcript(Path(transcript_path))
    pairs = extract_pairs(messages)
    added = append_pairs(pairs)
    print(f"[JARVIS C] Transkrypt: {len(pairs)} par znalezionych, {added} nowych.")
    return added


def collect_from_sessions() -> int:
    sessions_dir = MEMORY_DIR / "sessions"
    if not sessions_dir.exists():
        print("[JARVIS C] Brak sesji w memory/sessions/")
        return 0
    total = 0
    for f in sessions_dir.glob("*.json"):
        data = json.loads(f.read_text(encoding="utf-8"))
        summary = data.get("summary", "")
        if summary:
            pair = {
                "id": hashlib.md5(summary.encode()).hexdigest()[:12],
                "collected_at": data.get("date", datetime.now().isoformat()),
                "score": 0.5,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": "Podsumuj ostatnią sesję pracy."},
                    {"role": "assistant", "content": summary}
                ]
            }
            total += append_pairs([pair])
    print(f"[JARVIS C] Sesje: {total} nowych par z podsumowań.")
    return total


def show_stats() -> None:
    if not RAW_FILE.exists():
        print("[JARVIS C] Brak danych treningowych. Uruchom --transcript lub --all-sessions.")
        return
    pairs = []
    with open(RAW_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                pairs.append(json.loads(line))
            except Exception:
                pass
    if not pairs:
        print("[JARVIS C] Plik pusty.")
        return
    scores = [p["score"] for p in pairs]
    print(f"\n=== JARVIS TRAINING STATS ===")
    print(f"Łączne pary:       {len(pairs)}")
    print(f"Średni score:      {sum(scores)/len(scores):.3f}")
    print(f"Wysokiej jakości:  {sum(1 for s in scores if s >= 0.7)} (score ≥ 0.7)")
    print(f"Do fine-tuningu:   {sum(1 for s in scores if s >= 0.5)} (score ≥ 0.5)")
    print(f"Plik:              {RAW_FILE}")
    print(f"==============================\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcript", help="Ścieżka do pliku transkryptu")
    parser.add_argument("--all-sessions", action="store_true", help="Zbierz z sesji memory/")
    parser.add_argument("--show-stats", action="store_true", help="Statystyki danych")
    args = parser.parse_args()

    if args.transcript:
        collect_from_transcript(args.transcript)
    if args.all_sessions:
        collect_from_sessions()
    if args.show_stats:
        show_stats()
    if not any(vars(args).values()):
        parser.print_help()
