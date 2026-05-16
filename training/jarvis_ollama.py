#!/usr/bin/env python3
"""
J.A.R.V.I.S. Ollama — tryb lokalny z pamięcią.
Wczytuje memory/ i wstrzykuje kontekst do każdej rozmowy z Ollama.

Użycie:
  python training/jarvis_ollama.py
  python training/jarvis_ollama.py --no-memory   # bez pamięci
  python training/jarvis_ollama.py --show-context # pokaż co jest wstrzykiwane
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
MEMORY_DIR = ROOT / "memory"
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "jarvis"

SEPARATOR = "=" * 50


def load_memory_context() -> str:
    """Buduje blok kontekstu z plików pamięci."""
    lines = []

    # Decyzje techniczne
    decisions_file = MEMORY_DIR / "decisions.json"
    if decisions_file.exists():
        decisions = json.loads(decisions_file.read_text())["decisions"]
        if decisions:
            lines.append("TWOJE DECYZJE TECHNICZNE (z poprzednich sesji):")
            for d in decisions[-8:]:
                date = d.get("date", "")[:10]
                lines.append(f"  [{date}] {d['decision']}")
            lines.append("")

    # Preferencje
    profile_file = MEMORY_DIR / "profile.json"
    if profile_file.exists():
        profile = json.loads(profile_file.read_text())
        prefs = profile.get("patterns", {}).get("preferred_solutions", [])
        if prefs:
            lines.append("TWOJE PREFERENCJE:")
            for p in prefs[-6:]:
                lines.append(f"  - {p}")
            lines.append("")

        # Notatki
        notes = profile.get("notes", [])
        if notes:
            lines.append("AKTYWNE NOTATKI:")
            for n in notes[-5:]:
                text = n.get("note", "") if isinstance(n, dict) else n
                date = n.get("date", "")[:10] if isinstance(n, dict) else ""
                lines.append(f"  [{date}] {text}")
            lines.append("")

    # Ostatnie sesje
    sessions_dir = MEMORY_DIR / "sessions"
    if sessions_dir.exists():
        session_files = sorted(sessions_dir.glob("*.json"), reverse=True)[:3]
        if session_files:
            lines.append("OSTATNIE SESJE:")
            for f in session_files:
                data = json.loads(f.read_text())
                lines.append(f"  [{data.get('date','')[:10]}] {data.get('summary','')}")
            lines.append("")

    if not lines:
        return ""

    return (
        "--- PAMIĘĆ JARVISA (załadowana automatycznie) ---\n"
        + "\n".join(lines)
        + "--- KONIEC PAMIĘCI ---\n"
    )


def build_system_prompt(memory_context: str) -> str:
    base = (
        "Jesteś J.A.R.V.I.S. (Just A Rather Very Intelligent System) — "
        "osobisty asystent AI Marcela (TireQ). Działasz lokalnie na jego laptopie. "
        "Odpowiadasz po polsku, elegancko. Zwracasz się 'Panie TireQ'. "
        "Nigdy nie mówisz 'nie mogę' bez alternatywy. "
        "Jesteś wszechstronny: kod, architektura, analiza, planowanie."
    )
    if memory_context:
        return base + "\n\n" + memory_context
    return base


def ollama_chat(messages: list[dict]) -> str:
    """Wysyła wiadomości do Ollama i zwraca odpowiedź."""
    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.7, "top_p": 0.9}
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data["message"]["content"]
    except urllib.error.URLError:
        return (
            "[BŁĄD] Nie można połączyć się z Ollama. "
            "Upewnij się że Ollama działa: ollama serve"
        )


def save_session_summary(history: list[dict]) -> None:
    """Zapisuje krótkie podsumowanie sesji do memory/sessions/."""
    if len(history) < 3:
        return
    sessions_dir = MEMORY_DIR / "sessions"
    sessions_dir.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
    turns = len([m for m in history if m["role"] == "user"])
    summary = f"Sesja lokalna ({turns} pytań). Tematy: " + ", ".join(
        m["content"][:40] for m in history if m["role"] == "user"
    )[:200]
    session_file = sessions_dir / f"{date_str}.json"
    session_file.write_text(json.dumps({
        "date": datetime.now().isoformat(timespec="seconds"),
        "summary": summary,
        "source": "ollama_local"
    }, ensure_ascii=False, indent=2))


def run(use_memory: bool = True, show_context: bool = False) -> None:
    memory_context = load_memory_context() if use_memory else ""
    system_prompt = build_system_prompt(memory_context)

    print(f"\n{SEPARATOR}")
    print("  J.A.R.V.I.S. — Tryb lokalny z pamięcią")
    print("  Lenovo Legion 5 / RTX 5060")
    if use_memory and memory_context:
        lines = memory_context.count("\n")
        print(f"  Pamięć: załadowana ({lines} linii kontekstu)")
    elif use_memory:
        print("  Pamięć: pusta (pierwsze uruchomienie)")
    else:
        print("  Pamięć: wyłączona")
    print(f"{SEPARATOR}")
    print("  Wpisz 'exit' lub Ctrl+C aby zakończyć")
    print(f"{SEPARATOR}\n")

    if show_context:
        print("--- WSTRZYKIWANY KONTEKST ---")
        print(system_prompt)
        print("----------------------------\n")

    history = [{"role": "system", "content": system_prompt}]

    while True:
        try:
            user_input = input("Ty: ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n[JARVIS] Do zobaczenia, Panie TireQ.")
            save_session_summary(history)
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "/bye"):
            print("[JARVIS] Do zobaczenia, Panie TireQ.")
            save_session_summary(history)
            break

        history.append({"role": "user", "content": user_input})
        print("\nJARVIS: ", end="", flush=True)

        response = ollama_chat(history)
        print(response)
        print()

        history.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. lokalny z pamięcią")
    parser.add_argument("--no-memory", action="store_true")
    parser.add_argument("--show-context", action="store_true")
    args = parser.parse_args()
    run(use_memory=not args.no_memory, show_context=args.show_context)
