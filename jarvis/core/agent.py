#!/usr/bin/env python3
"""
J.A.R.V.I.S. Agent — pętla ReAct (Reason → Act → Observe).
Model decyduje które narzędzie wywołać, wykonuje je, obserwuje wynik,
i kontynuuje aż zadanie jest gotowe lub osiągnie limit kroków.

Użycie:
  python jarvis/core/agent.py "utwórz plik hello.py z funkcją main"
  python jarvis/core/agent.py "sprawdź status git i zrób commit"
  python jarvis/core/agent.py --interactive
"""
import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
from jarvis.core.tools import TOOLS_SCHEMA, execute_tool

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "jarvis"
MAX_STEPS = 8

AGENT_SYSTEM = """Jesteś J.A.R.V.I.S. — agent AI działający autonomicznie.
Masz dostęp do narzędzi. Wykonujesz zadania krok po kroku.

NARZĘDZIA:
{tools}

FORMAT ODPOWIEDZI:
Gdy chcesz użyć narzędzia, odpowiedz DOKŁADNIE w tym formacie:
<tool>
{{"name": "nazwa_narzedzia", "params": {{"klucz": "wartość"}}}}
</tool>

Gdy zadanie jest gotowe, odpowiedz normalnie bez tagów <tool>.
Jeden krok — jedno narzędzie. Bądź precyzyjny, Panie TireQ."""


def build_system(extra_tools: list = None) -> str:
    all_tools = TOOLS_SCHEMA + (extra_tools or [])
    tools_str = "\n".join(
        f"- {t['name']}: {t['description']} | params: {t['params']}"
        for t in all_tools
    )
    return AGENT_SYSTEM.format(tools=tools_str)


def ollama_chat(messages: list[dict], system: str) -> str:
    msgs = [{"role": "system", "content": system}] + messages
    payload = json.dumps({
        "model": MODEL, "messages": msgs,
        "stream": False, "options": {"temperature": 0.3}
    }).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=payload,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())["message"]["content"]
    except Exception as e:
        return f"[BŁĄD OLLAMA] {e}"


def parse_tool_call(text: str) -> dict | None:
    match = re.search(r"<tool>\s*(\{.*?\})\s*</tool>", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def run_agent(task: str, verbose: bool = True,
              extra_tools: list = None,
              tool_override: dict = None) -> str:
    """
    Uruchamia pętlę agenta dla danego zadania.
    extra_tools: dodatkowe schematy narzędzi (z pluginów)
    tool_override: nadpisuje/rozszerza domyślny słownik narzędzi
    """
    from jarvis.core.tools import TOOLS
    tools = {**TOOLS, **(tool_override or {})}

    system = build_system(extra_tools)
    messages = [{"role": "user", "content": f"Zadanie: {task}"}]

    if verbose:
        print(f"\n[JARVIS AGENT] Zadanie: {task}")
        print("-" * 50)

    for step in range(1, MAX_STEPS + 1):
        response = ollama_chat(messages, system)
        tool_call = parse_tool_call(response)

        if not tool_call:
            if verbose:
                print(f"\n[JARVIS] {response}")
            return response

        name = tool_call.get("name", "")
        params = tool_call.get("params", {})

        if verbose:
            print(f"[Krok {step}] Narzędzie: {name}({params})")

        fn = tools.get(name)
        if fn:
            result = fn(**params)
        else:
            result = execute_tool(name, params)

        status = result.get("status", "?")
        output = str(result.get("result", ""))[:2000]

        if verbose:
            icon = "✓" if status == "ok" else "✗"
            print(f"  {icon} {output[:200]}{'...' if len(output) > 200 else ''}")

        messages.append({"role": "assistant", "content": response})
        messages.append({
            "role": "user",
            "content": f"[Wynik {name}] status={status}\n{output}"
        })

    return "[JARVIS AGENT] Osiągnięto limit kroków."


def interactive_mode() -> None:
    print("\n" + "=" * 52)
    print("  J.A.R.V.I.S. Agent Mode — tryb interaktywny")
    print("  Zlecaj zadania — Jarvis wykona je autonomicznie")
    print("  Wpisz 'exit' aby zakończyć")
    print("=" * 52 + "\n")
    while True:
        try:
            task = input("Zadanie: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[JARVIS] Do zobaczenia, Panie TireQ.")
            break
        if not task:
            continue
        if task.lower() in ("exit", "quit"):
            print("[JARVIS] Do zobaczenia, Panie TireQ.")
            break
        run_agent(task)
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. Agent Mode")
    parser.add_argument("task", nargs="?", help="Zadanie do wykonania")
    parser.add_argument("--interactive", "-i", action="store_true")
    parser.add_argument("--quiet", "-q", action="store_true")
    args = parser.parse_args()

    if args.interactive or not args.task:
        interactive_mode()
    else:
        run_agent(args.task, verbose=not args.quiet)
