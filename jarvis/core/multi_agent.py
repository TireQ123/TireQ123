#!/usr/bin/env python3
"""
J.A.R.V.I.S. Multi-Agent — orkiestrator delegujący zadania do wyspecjalizowanych agentów.

Architektura:
  Orchestrator → analizuje zadanie → deleguje do sub-agentów → scala wyniki

Sub-agenci:
  code_agent    — pisanie, refaktoryzacja, debugowanie kodu
  git_agent     — operacje git, commit, analiza historii
  research_agent — przeszukiwanie plików, analiza projektu
  memory_agent  — operacje na pamięci Jarvisa
  file_agent    — zarządzanie plikami i strukturą projektu

Użycie:
  python jarvis/core/multi_agent.py "zrefaktoryzuj kod i zrób commit"
  python jarvis/core/multi_agent.py --interactive
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
from jarvis.core.tools import execute_tool, TOOLS_SCHEMA

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "jarvis"

# ── Definicje sub-agentów ────────────────────────────────────────────────────

AGENTS = {
    "code_agent": {
        "description": "Specjalista od pisania, refaktoryzacji i debugowania kodu",
        "tools": ["file_read", "file_write", "file_list", "shell_run"],
        "system": (
            "Jesteś agentem wyspecjalizowanym w kodzie. Piszesz czysty, elegancki kod. "
            "Analizujesz istniejący kod przed zmianami. Informujesz o skutkach ubocznych. "
            "Używasz dostępnych narzędzi. Odpowiadasz po polsku."
        )
    },
    "git_agent": {
        "description": "Specjalista od operacji git i zarządzania kodem",
        "tools": ["git_status", "git_commit", "shell_run"],
        "system": (
            "Jesteś agentem wyspecjalizowanym w git. Sprawdzasz status przed każdą operacją. "
            "Piszesz precyzyjne komunikaty commitów. Ostrzegasz przed ryzykowymi operacjami. "
            "Odpowiadasz po polsku."
        )
    },
    "research_agent": {
        "description": "Specjalista od analizy projektu i wyszukiwania informacji",
        "tools": ["file_read", "file_list", "shell_run", "memory_read"],
        "system": (
            "Jesteś agentem wyspecjalizowanym w analizie. Przeszukujesz pliki, "
            "analizujesz strukturę projektu, zbierasz informacje. Dajesz precyzyjne raporty. "
            "Odpowiadasz po polsku."
        )
    },
    "memory_agent": {
        "description": "Specjalista od pamięci i kontekstu Jarvisa",
        "tools": ["memory_read", "memory_save"],
        "system": (
            "Jesteś agentem zarządzającym pamięcią Jarvisa. "
            "Zapisujesz ważne decyzje i preferencje. Odczytujesz kontekst. "
            "Odpowiadasz po polsku."
        )
    },
    "file_agent": {
        "description": "Specjalista od struktury plików i projektu",
        "tools": ["file_read", "file_write", "file_list", "shell_run"],
        "system": (
            "Jesteś agentem zarządzającym plikami. Tworzysz i organizujesz strukturę projektu. "
            "Dbasz o porządek i konwencje nazewnictwa. Odpowiadasz po polsku."
        )
    }
}

ORCHESTRATOR_SYSTEM = """Jesteś orkiestratorem J.A.R.V.I.S. Analizujesz złożone zadania i delegują je do wyspecjalizowanych agentów.

DOSTĘPNI AGENCI:
{agents}

Dla każdego zadania:
1. Podziel je na podzadania
2. Przypisz każde podzadanie do odpowiedniego agenta
3. Zbierz wyniki i przedstaw podsumowanie

Odpowiedź w formacie JSON:
{{
  "plan": "krótki opis planu",
  "subtasks": [
    {{"agent": "nazwa_agenta", "task": "konkretne podzadanie"}},
    ...
  ]
}}"""


def _ollama(messages: list[dict], system: str, temperature: float = 0.3) -> str:
    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": system}] + messages,
        "stream": False,
        "options": {"temperature": temperature}
    }).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=payload,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())["message"]["content"]
    except Exception as e:
        return f"[BŁĄD] {e}"


def _parse_json(text: str) -> dict:
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end]) if start != -1 else {}
    except Exception:
        return {}


def run_sub_agent(agent_name: str, task: str, verbose: bool = True) -> str:
    agent = AGENTS.get(agent_name)
    if not agent:
        return f"Nieznany agent: {agent_name}"

    tools_schema = [t for t in TOOLS_SCHEMA if t["name"] in agent["tools"]]
    tools_str = "\n".join(
        f"- {t['name']}: {t['description']} | params: {t['params']}"
        for t in tools_schema
    )
    system = (
        agent["system"] + f"\n\nDOSTĘPNE NARZĘDZIA:\n{tools_str}\n\n"
        "Gdy używasz narzędzia:\n"
        "<tool>\n{{\"name\": \"...\", \"params\": {{...}}}}\n</tool>"
    )

    messages = [{"role": "user", "content": task}]
    if verbose:
        print(f"\n  [{agent_name}] {task[:80]}")

    for step in range(6):
        response = _ollama(messages, system)
        match = re.search(r"<tool>\s*(\{.*?\})\s*</tool>", response, re.DOTALL)
        if not match:
            if verbose:
                print(f"  [{agent_name}] ✓ Gotowe")
            return response

        try:
            call = json.loads(match.group(1))
            result = execute_tool(call["name"], call.get("params", {}))
            output = str(result.get("result", ""))[:1500]
            if verbose:
                print(f"  [{agent_name}] → {call['name']}() {result['status']}")
            messages += [
                {"role": "assistant", "content": response},
                {"role": "user", "content": f"[Wynik] {output}"}
            ]
        except Exception as e:
            return f"Błąd agenta: {e}"

    return "[Agent osiągnął limit kroków]"


def orchestrate(task: str, verbose: bool = True) -> str:
    if verbose:
        print(f"\n[JARVIS ORCHESTRATOR] Zadanie: {task}")
        print("─" * 52)

    agents_desc = "\n".join(
        f"- {name}: {cfg['description']}"
        for name, cfg in AGENTS.items()
    )
    system = ORCHESTRATOR_SYSTEM.format(agents=agents_desc)
    raw = _ollama([{"role": "user", "content": task}], system, temperature=0.2)
    plan = _parse_json(raw)

    if not plan or "subtasks" not in plan:
        if verbose:
            print("[JARVIS] Proste zadanie — jeden agent wystarczy.")
        return run_sub_agent("code_agent", task, verbose)

    if verbose:
        print(f"[Plan] {plan.get('plan', '')}")

    results = []
    for subtask in plan.get("subtasks", []):
        agent_name = subtask.get("agent", "code_agent")
        sub_task = subtask.get("task", "")
        if sub_task:
            result = run_sub_agent(agent_name, sub_task, verbose)
            results.append(f"[{agent_name}]\n{result}")

    combined = "\n\n".join(results)
    summary_prompt = (
        f"Zadanie: {task}\n\nWyniki sub-agentów:\n{combined[:3000]}\n\n"
        "Napisz zwięzłe podsumowanie co zostało wykonane, Panie TireQ."
    )
    summary = _ollama(
        [{"role": "user", "content": summary_prompt}],
        "Jesteś J.A.R.V.I.S. Podsumowujesz wyniki pracy agentów. Odpowiadasz po polsku.",
        temperature=0.5
    )

    if verbose:
        print(f"\n[JARVIS] {summary}")
    return summary


def interactive_mode() -> None:
    print("\n" + "=" * 52)
    print("  J.A.R.V.I.S. Multi-Agent — tryb interaktywny")
    print("  Złożone zadania delegowane do wyspecjalizowanych agentów")
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
            break
        orchestrate(task)
        print()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. Multi-Agent")
    parser.add_argument("task", nargs="?", help="Zadanie do wykonania")
    parser.add_argument("--interactive", "-i", action="store_true")
    args = parser.parse_args()
    if args.interactive or not args.task:
        interactive_mode()
    else:
        orchestrate(args.task)
