#!/usr/bin/env python3
"""
J.A.R.V.I.S. Ollama — tryb lokalny z pamięcią i streamingiem.

Użycie:
  python training/jarvis_ollama.py
  python training/jarvis_ollama.py --no-memory
  python training/jarvis_ollama.py --show-context
  python training/jarvis_ollama.py --host http://192.168.1.10:11434
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
DEFAULT_HOST = "http://localhost:11434"
MODEL = "jarvis"
SEPARATOR = "=" * 52


# ── Pamięć ────────────────────────────────────────────────────────────────────

def load_memory_context() -> str:
    lines = []

    decisions_file = MEMORY_DIR / "decisions.json"
    if decisions_file.exists():
        decisions = json.loads(decisions_file.read_text(encoding="utf-8"))["decisions"]
        if decisions:
            lines.append("TWOJE DECYZJE TECHNICZNE (z poprzednich sesji):")
            for d in decisions[-8:]:
                date = d.get("date", "")[:10]
                lines.append(f"  [{date}] {d['decision']}")
            lines.append("")

    profile_file = MEMORY_DIR / "profile.json"
    if profile_file.exists():
        profile = json.loads(profile_file.read_text(encoding="utf-8"))
        prefs = profile.get("patterns", {}).get("preferred_solutions", [])
        if prefs:
            lines.append("TWOJE PREFERENCJE:")
            for p in prefs[-6:]:
                lines.append(f"  - {p}")
            lines.append("")

        notes = profile.get("notes", [])
        if notes:
            lines.append("AKTYWNE NOTATKI:")
            for n in notes[-5:]:
                text = n.get("note", "") if isinstance(n, dict) else n
                date = n.get("date", "")[:10] if isinstance(n, dict) else ""
                lines.append(f"  [{date}] {text}")
            lines.append("")

    sessions_dir = MEMORY_DIR / "sessions"
    if sessions_dir.exists():
        session_files = sorted(sessions_dir.glob("*.json"), reverse=True)[:3]
        if session_files:
            lines.append("OSTATNIE SESJE:")
            for f in session_files:
                data = json.loads(f.read_text(encoding="utf-8"))
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
        "Odpowiadasz po polsku, elegancko i precyzyjnie. Zwracasz się 'Panie TireQ'. "
        "Nigdy nie mówisz 'nie mogę' bez alternatywy. "
        "Jesteś wszechstronny: kod, architektura, analiza, planowanie. "
        "Doza suchego brytyjskiego humoru gdy stosowne."
    )
    if memory_context:
        return base + "\n\n" + memory_context
    return base


def save_session_summary(history: list[dict]) -> None:
    if len(history) < 3:
        return
    sessions_dir = MEMORY_DIR / "sessions"
    sessions_dir.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
    turns = len([m for m in history if m["role"] == "user"])
    topics = ", ".join(m["content"][:40] for m in history if m["role"] == "user")[:200]
    summary = f"Sesja lokalna ({turns} pytań). Tematy: {topics}"
    session_file = sessions_dir / f"{date_str}.json"
    session_file.write_text(json.dumps({
        "date": datetime.now().isoformat(timespec="seconds"),
        "summary": summary,
        "source": "ollama_local"
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  [Pamięć zapisana → {session_file.name}]")


# ── Ollama API ────────────────────────────────────────────────────────────────

def check_connection(host: str) -> bool:
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def check_model_exists(host: str) -> bool:
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=5) as r:
            data = json.loads(r.read())
            return any(m["name"].startswith(MODEL) for m in data.get("models", []))
    except Exception:
        return False


def ollama_stream(messages: list[dict], host: str) -> str:
    """Strumieniuje odpowiedź z Ollama — znaki pojawiają się na bieżąco."""
    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "stream": True,
        "options": {"temperature": 0.7, "top_p": 0.9}
    }).encode()

    req = urllib.request.Request(
        f"{host}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    full_response = []
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            for line in resp:
                if not line.strip():
                    continue
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                if token:
                    print(token, end="", flush=True)
                    full_response.append(token)
                if chunk.get("done"):
                    break
    except urllib.error.URLError as e:
        msg = f"\n[BŁĄD połączenia] {e.reason}"
        print(msg)
        return msg
    except Exception as e:
        msg = f"\n[BŁĄD] {e}"
        print(msg)
        return msg

    print()  # nowa linia po odpowiedzi
    return "".join(full_response)


# ── Komendy inline ────────────────────────────────────────────────────────────

HELP_TEXT = """
  Dostępne komendy:
    /help      — ta pomoc
    /memory    — pokaż załadowany kontekst pamięci
    /save      — zapisz sesję do pamięci teraz
    /clear     — wyczyść historię rozmowy (zachowaj system prompt)
    exit / /bye — zakończ sesję
"""


def handle_command(cmd: str, history: list[dict], system_prompt: str,
                   memory_context: str) -> str | None:
    """Zwraca None jeśli komenda obsłużona, 'clear' jeśli reset historii."""
    cmd = cmd.strip().lower()

    if cmd == "/help":
        print(HELP_TEXT)
        return "handled"

    if cmd == "/memory":
        if memory_context:
            print(f"\n{memory_context}")
        else:
            print("\n  [Pamięć jest pusta]\n")
        return "handled"

    if cmd == "/save":
        save_session_summary(history)
        return "handled"

    if cmd == "/clear":
        history.clear()
        history.append({"role": "system", "content": system_prompt})
        print("\n  [Historia wyczyszczona. Kontekst pamięci zachowany.]\n")
        return "handled"

    return None


# ── Główna pętla ──────────────────────────────────────────────────────────────

def run(use_memory: bool = True, show_context: bool = False, host: str = DEFAULT_HOST) -> None:
    # Sprawdź połączenie
    print(f"\n  Łączę z Ollama ({host})...", end=" ", flush=True)
    if not check_connection(host):
        print("BŁĄD")
        print(f"\n  Nie można połączyć z Ollama.")
        print(f"  Upewnij się że Ollama działa: ollama serve")
        print(f"  Lub podaj inny host: --host http://ADRES:11434\n")
        sys.exit(1)
    print("OK")

    # Sprawdź model
    if not check_model_exists(host):
        print(f"\n  Model '{MODEL}' nie istnieje.")
        print(f"  Zbuduj go: ollama create {MODEL} -f training/Modelfile\n")
        sys.exit(1)

    memory_context = load_memory_context() if use_memory else ""
    system_prompt = build_system_prompt(memory_context)

    print(f"\n{SEPARATOR}")
    print("   J.A.R.V.I.S. — Tryb lokalny z pamięcią")
    print("   Lenovo Legion 5 / RTX 5060")
    if use_memory and memory_context:
        lines = memory_context.count("\n")
        print(f"   Pamięć: załadowana ({lines} linii kontekstu)")
    elif use_memory:
        print("   Pamięć: pusta (pierwsze uruchomienie)")
    else:
        print("   Pamięć: wyłączona")
    print(f"   Model: {MODEL} @ {host}")
    print(f"{SEPARATOR}")
    print("   Wpisz /help po listę komend | exit aby wyjść")
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

        if user_input.startswith("/"):
            result = handle_command(user_input, history, system_prompt, memory_context)
            if result is not None:
                continue

        history.append({"role": "user", "content": user_input})
        print("\nJARVIS: ", end="", flush=True)

        response = ollama_stream(history, host)
        if response:
            history.append({"role": "assistant", "content": response})
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. lokalny z pamięcią")
    parser.add_argument("--no-memory", action="store_true", help="Wyłącz pamięć")
    parser.add_argument("--show-context", action="store_true", help="Pokaż system prompt")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Adres Ollama (domyślnie: localhost:11434)")
    args = parser.parse_args()
    run(use_memory=not args.no_memory, show_context=args.show_context, host=args.host)
