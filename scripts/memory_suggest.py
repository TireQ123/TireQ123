#!/usr/bin/env python3
"""
J.A.R.V.I.S. Memory Suggest — Faza A+
Analizuje transkrypt sesji przez Ollama i sugeruje co zapisać do pamięci.
Prezentuje propozycje użytkownikowi — nic nie zapisuje bez potwierdzenia.

Uruchamiany automatycznie przez Stop hook lub ręcznie:
  python scripts/memory_suggest.py
  python scripts/memory_suggest.py --transcript /path/to/transcript.json
  python scripts/memory_suggest.py --auto   # zapisz bez pytania (tryb hook)
"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

OLLAMA_URL = "http://localhost:11434/api/chat"
MEMORY_DIR = ROOT / "memory"

EXTRACT_PROMPT = """Jesteś analizatorem sesji J.A.R.V.I.S. Przeanalizuj tę rozmowę i wyodrębnij informacje warte zapamiętania.

ROZMOWA:
{conversation}

Zwróć TYLKO obiekt JSON (bez żadnego tekstu przed ani po):
{{
  "decisions": ["decyzja techniczna 1", "decyzja techniczna 2"],
  "preferences": ["preferencja 1", "preferencja 2"],
  "notes": ["ważna notatka 1"],
  "summary": "jedno zdanie podsumowania sesji"
}}

Zasady:
- decisions: konkretne decyzje techniczne (stack, architektura, narzędzia)
- preferences: co użytkownik lubi/preferuje/unika
- notes: terminy, deadliny, ważne fakty
- Jeśli nic wartego zapisu — zwróć puste tablice
- Maksymalnie 3 wpisy w każdej kategorii
- Krótko i konkretnie — max 80 znaków per wpis"""


def _ollama(prompt: str) -> str:
    payload = json.dumps({
        "model": "jarvis",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.1}
    }).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=payload,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())["message"]["content"]
    except Exception:
        return ""


def extract_conversation(transcript_path: str) -> str:
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        messages = data if isinstance(data, list) else data.get("messages", [])
        lines = []
        for msg in messages[-30:]:
            role = msg.get("role", "")
            if role not in ("user", "assistant"):
                continue
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    b.get("text", "") for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                )
            if content.strip():
                label = "TireQ" if role == "user" else "JARVIS"
                lines.append(f"{label}: {content.strip()[:300]}")
        return "\n".join(lines[-20:])
    except Exception:
        return ""


def parse_suggestions(raw: str) -> dict:
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1:
            return {}
        return json.loads(raw[start:end])
    except Exception:
        return {}


def save_suggestions(suggestions: dict) -> int:
    sys.path.insert(0, str(ROOT / "scripts"))
    import memory_update as mu
    count = 0
    for d in suggestions.get("decisions", []):
        if d.strip():
            mu.add_decision(d.strip())
            count += 1
    for p in suggestions.get("preferences", []):
        if p.strip():
            mu.add_preference(p.strip())
            count += 1
    for n in suggestions.get("notes", []):
        if n.strip():
            mu.add_note(n.strip())
            count += 1
    summary = suggestions.get("summary", "").strip()
    if summary:
        mu.save_session(summary)
    return count


def interactive_confirm(suggestions: dict) -> dict:
    confirmed = {"decisions": [], "preferences": [], "notes": []}
    print("\n[JARVIS] Sugestie do zapamiętania z tej sesji:\n")

    for category, items in [
        ("decisions", "Decyzje techniczne"),
        ("preferences", "Preferencje"),
        ("notes", "Notatki")
    ]:
        for item in suggestions.get(category, []):
            if not item.strip():
                continue
            answer = input(f"  [{items}] \"{item}\"\n  Zapisać? (t/n): ").strip().lower()
            if answer in ("t", "tak", "y", "yes", ""):
                confirmed[category].append(item)
    confirmed["summary"] = suggestions.get("summary", "")
    return confirmed


def run(transcript_path: str = "", auto: bool = False) -> None:
    if not transcript_path:
        transcript_path = os.environ.get("CLAUDE_TRANSCRIPT_PATH", "")
    if not transcript_path or not Path(transcript_path).exists():
        return

    conversation = extract_conversation(transcript_path)
    if len(conversation) < 100:
        return

    print("[JARVIS] Analizuję sesję...")
    raw = _ollama(EXTRACT_PROMPT.format(conversation=conversation))
    if not raw:
        print("[JARVIS] Ollama niedostępna — pomijam auto-analizę.")
        return

    suggestions = parse_suggestions(raw)
    has_content = any(suggestions.get(k) for k in ("decisions", "preferences", "notes"))
    if not has_content:
        return

    if auto:
        count = save_suggestions(suggestions)
        if count > 0:
            print(f"[JARVIS] Auto-zapisano {count} sugestii z sesji.")
    else:
        confirmed = interactive_confirm(suggestions)
        count = save_suggestions(confirmed)
        if count > 0:
            print(f"\n[JARVIS] Zapisano {count} wpisów do pamięci.")
        else:
            print("\n[JARVIS] Nic nie zapisano.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcript", default="", help="Ścieżka do transkryptu")
    parser.add_argument("--auto", action="store_true", help="Zapisz bez pytania")
    args = parser.parse_args()
    run(args.transcript, args.auto)
