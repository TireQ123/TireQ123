#!/usr/bin/env python3
"""
J.A.R.V.I.S. Training Generate — Faza C
Generuje syntetyczne dane treningowe za pomocą Claude API.
Używa pamięci (decisions, preferences) jako seed do tworzenia
realistycznych par (user → Jarvis) w stylu TireQ.

Wymaga: ANTHROPIC_API_KEY w środowisku.

Użycie:
  export ANTHROPIC_API_KEY=sk-ant-...
  python scripts/training_generate.py --count 20
  python scripts/training_generate.py --count 50 --topic "praca z Pythonem"
"""

import argparse
import json
import os
import hashlib
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
MEMORY_DIR = ROOT / "memory"
TRAINING_DIR = ROOT / "training"
RAW_FILE = TRAINING_DIR / "raw_pairs.jsonl"

SYSTEM_PROMPT = (
    "Jesteś J.A.R.V.I.S. — osobisty asystent AI Marcela (TireQ). "
    "Odpowiadasz po polsku, elegancko i precyzyjnie. "
    "Zwracasz się 'Panie TireQ'. Nigdy nie mówisz 'nie mogę' bez alternatywy. "
    "Jesteś wszechstronny: kod, architektura, analiza, planowanie."
)

GENERATOR_PROMPT = """Na podstawie poniższego profilu użytkownika wygeneruj {count} realistycznych par konwersacyjnych w formacie JSON.

Profil użytkownika:
{profile_summary}

Zasady generowania:
- Wiadomości użytkownika: naturalne pytania lub polecenia po polsku (1-3 zdania)
- Odpowiedzi asystenta: styl Jarvisa — elegancki, po polsku, zwięzły ale kompletny
- Różnorodność tematów: kod, architektura, planowanie, debug, git, deploy, analiza
- Odpowiedzi mogą zawierać kod (markdown), listy, konkretne kroki
- NIE powtarzaj podobnych par

Temat wiodący (opcjonalny): {topic}

Zwróć TYLKO tablicę JSON w formacie:
[
  {{
    "user": "treść wiadomości użytkownika",
    "assistant": "treść odpowiedzi Jarvisa"
  }},
  ...
]"""


def load_profile_summary() -> str:
    lines = []
    profile_file = MEMORY_DIR / "profile.json"
    decisions_file = MEMORY_DIR / "decisions.json"

    if profile_file.exists():
        profile = json.loads(profile_file.read_text())
        prefs = profile.get("patterns", {}).get("preferred_solutions", [])
        if prefs:
            lines.append(f"Preferencje: {', '.join(prefs[:5])}")
        notes = profile.get("notes", [])
        if notes:
            texts = [n.get("note", "") if isinstance(n, dict) else n for n in notes[:3]]
            lines.append(f"Notatki: {'; '.join(texts)}")

    if decisions_file.exists():
        decisions = json.loads(decisions_file.read_text()).get("decisions", [])
        if decisions:
            recent = [d["decision"] for d in decisions[-5:]]
            lines.append(f"Ostatnie decyzje: {'; '.join(recent)}")

    return "\n".join(lines) if lines else "Użytkownik: Marcel (TireQ), wszechstronny developer."


def generate_pairs(count: int, topic: str = "") -> list[dict]:
    try:
        import anthropic
    except ImportError:
        print("[JARVIS C] Błąd: pip install anthropic")
        return []

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[JARVIS C] Błąd: brak ANTHROPIC_API_KEY w środowisku.")
        print("           export ANTHROPIC_API_KEY=sk-ant-...")
        return []

    client = anthropic.Anthropic(api_key=api_key)
    profile_summary = load_profile_summary()

    prompt = GENERATOR_PROMPT.format(
        count=count,
        profile_summary=profile_summary,
        topic=topic if topic else "dowolny (różnorodny)"
    )

    print(f"[JARVIS C] Generuję {count} syntetycznych par...")
    try:
        message = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = message.content[0].text

        # Wyodrębnij JSON z odpowiedzi
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start == -1 or end == 0:
            print("[JARVIS C] Błąd: nie znaleziono JSON w odpowiedzi.")
            return []

        pairs_raw = json.loads(raw[start:end])
    except Exception as e:
        print(f"[JARVIS C] Błąd API: {e}")
        return []

    formatted = []
    for p in pairs_raw:
        user = p.get("user", "").strip()
        assistant = p.get("assistant", "").strip()
        if not user or not assistant:
            continue
        pair_id = hashlib.md5(f"{user[:80]}{assistant[:80]}".encode()).hexdigest()[:12]
        formatted.append({
            "id": pair_id,
            "collected_at": datetime.now().isoformat(timespec="seconds"),
            "score": 0.75,
            "source": "synthetic",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
                {"role": "assistant", "content": assistant}
            ]
        })

    return formatted


def save_pairs(pairs: list[dict]) -> int:
    if not pairs:
        return 0
    existing_ids = set()
    if RAW_FILE.exists():
        with open(RAW_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    existing_ids.add(json.loads(line)["id"])
                except Exception:
                    pass

    new_pairs = [p for p in pairs if p["id"] not in existing_ids]
    TRAINING_DIR.mkdir(exist_ok=True)
    with open(RAW_FILE, "a", encoding="utf-8") as f:
        for p in new_pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    return len(new_pairs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=20, help="Liczba par do wygenerowania")
    parser.add_argument("--topic", default="", help="Temat wiodący (opcjonalny)")
    args = parser.parse_args()

    pairs = generate_pairs(args.count, args.topic)
    added = save_pairs(pairs)
    print(f"[JARVIS C] Dodano {added} nowych syntetycznych par do training/raw_pairs.jsonl")
