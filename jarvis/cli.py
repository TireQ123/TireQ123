#!/usr/bin/env python3
"""
J.A.R.V.I.S. CLI — jedna komenda do wszystkiego.

Użycie:
  jarvis                    — czat z pamięcią
  jarvis agent "zadanie"    — Agent Mode
  jarvis voice              — tryb głosowy
  jarvis api                — uruchom serwer API
  jarvis monitor            — monitoruj repo
  jarvis memory             — pokaż pamięć
  jarvis memory add "..."   — dodaj notatkę
  jarvis status             — status systemu
  jarvis update             — git pull + aktualizacja
  jarvis plugin list        — lista pluginów
  jarvis train              — zbierz dane i eksportuj
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def cmd(args: list[str], **kwargs) -> int:
    return subprocess.run(args, cwd=ROOT, **kwargs).returncode


def python(script: str, *args) -> int:
    return cmd([sys.executable, str(ROOT / script), *args])


# ── Podkomendy ────────────────────────────────────────────────────────────────

def do_chat(_args) -> None:
    python("training/jarvis_ollama.py")


def do_agent(args) -> None:
    task = " ".join(args.task) if args.task else ""
    if task:
        python("jarvis/core/agent.py", task)
    else:
        python("jarvis/core/agent.py", "--interactive")


def do_voice(args) -> None:
    flags = []
    if getattr(args, "text_only", False):
        flags.append("--text-only")
    if getattr(args, "voice", "pl") == "en":
        flags.append("--voice en")
    python("training/jarvis_voice.py", *flags)


def do_api(_args) -> None:
    print("[JARVIS] Uruchamiam API na http://localhost:8000")
    print("[JARVIS] Docs: http://localhost:8000/docs\n")
    python("jarvis/api/server.py")


def do_monitor(args) -> None:
    interval = getattr(args, "interval", 120)
    print(f"[JARVIS] Monitor aktywny (co {interval}s). Ctrl+C aby zatrzymać.")
    python("jarvis/monitor/watcher.py", "--interval", str(interval))


def do_memory(args) -> None:
    sub = getattr(args, "sub", None)
    if sub == "add":
        value = " ".join(args.value)
        key = getattr(args, "type", "note")
        python("scripts/memory_update.py", f"--{key}", value)
    elif sub == "show":
        python("scripts/memory_update.py", "--show")
    elif sub == "update":
        python("scripts/memory_load.py", "--update-claude")
    else:
        python("scripts/memory_update.py", "--show")


def do_status(_args) -> None:
    import json

    print("\n  ╔══════════════════════════════╗")
    print("  ║  J.A.R.V.I.S. STATUS         ║")
    print("  ╚══════════════════════════════╝\n")

    # Git
    result = subprocess.run(
        ["git", "log", "--oneline", "-3"],
        cwd=ROOT, capture_output=True, text=True
    )
    print("  Git (ostatnie commity):")
    for line in result.stdout.strip().splitlines():
        print(f"    {line}")

    # Pamięć
    try:
        profile = json.loads((ROOT / "memory/profile.json").read_text())
        decisions = json.loads((ROOT / "memory/decisions.json").read_text())
        prefs = len(profile.get("patterns", {}).get("preferred_solutions", []))
        decs = len(decisions.get("decisions", []))
        notes = len(profile.get("notes", []))
        print(f"\n  Pamięć:")
        print(f"    Preferencje: {prefs}  |  Decyzje: {decs}  |  Notatki: {notes}")
    except Exception:
        print("\n  Pamięć: brak danych")

    # Dane treningowe
    raw = ROOT / "training/raw_pairs.jsonl"
    if raw.exists():
        count = sum(1 for _ in raw.open())
        print(f"\n  Dane treningowe: {count} par")

    # Pluginy
    try:
        from jarvis.plugins import registry
        registry.load_all()
        print(f"\n  Pluginy: {', '.join(registry.list_plugins()) or 'brak'}")
    except Exception:
        pass

    # Ollama
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True
        )
        has_jarvis = "jarvis" in result.stdout.lower()
        print(f"\n  Ollama model 'jarvis': {'✓' if has_jarvis else '✗ brak — uruchom: ollama create jarvis -f training/Modelfile'}")
    except FileNotFoundError:
        print("\n  Ollama: ✗ nie zainstalowana — pobierz z ollama.com")

    print()


def do_update(_args) -> None:
    print("[JARVIS] Pobieram aktualizacje...")
    cmd(["git", "pull", "origin", "main"])
    print("[JARVIS] Aktualizuję indeks RAG...")
    python("scripts/rag_index.py")
    print("[JARVIS] Aktualizuję CLAUDE.md...")
    python("scripts/memory_load.py", "--update-claude")
    print("[JARVIS] Gotowe.")


def do_plugin(args) -> None:
    from jarvis.plugins import registry
    registry.load_all()
    if getattr(args, "sub", "list") == "list":
        plugins = registry.list_plugins()
        tools = registry.schemas
        print(f"\n  Pluginy ({len(plugins)}): {', '.join(plugins) or 'brak'}")
        print(f"  Narzędzia ({len(tools)}): {', '.join(t['name'] for t in tools)}\n")


def do_multi(args) -> None:
    from jarvis.core.multi_agent import orchestrate, interactive_mode
    task = " ".join(args.task) if args.task else ""
    if task:
        orchestrate(task)
    else:
        interactive_mode()


def do_briefing(_args) -> None:
    from jarvis.plugins.tireq_plugin import tireq_briefing
    result = tireq_briefing()
    print(result["result"])


def do_telegram(_args) -> None:
    python("jarvis/integrations/telegram_bot.py")


def do_schedule(args) -> None:
    sub = getattr(args, "sub", "list")
    if sub == "list":
        python("jarvis/scheduler/engine.py", "--list")
    elif sub == "start":
        print("[JARVIS] Scheduler daemon uruchomiony. Ctrl+C aby zatrzymać.")
        python("jarvis/scheduler/engine.py")
    elif sub == "once":
        python("jarvis/scheduler/engine.py", "--once")
    elif sub == "run" and args.value:
        python("jarvis/scheduler/engine.py", "--run", args.value[0])


def do_train(_args) -> None:
    print("[JARVIS] Zbieram dane treningowe z sesji...")
    python("scripts/training_collect.py", "--all-sessions")
    print("[JARVIS] Eksportuję formaty...")
    python("scripts/training_format.py", "--format", "all")
    print("[JARVIS] Statystyki:")
    python("scripts/training_collect.py", "--show-stats")


# ── Parser ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="J.A.R.V.I.S. — Osobisty asystent AI TireQ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Przykłady:\n"
            "  jarvis                        # czat\n"
            "  jarvis agent 'napraw bug'     # agent mode\n"
            "  jarvis voice                  # głosowy\n"
            "  jarvis api                    # serwer API\n"
            "  jarvis monitor                # monitoring repo\n"
            "  jarvis memory show            # pamięć\n"
            "  jarvis status                 # status systemu\n"
        )
    )
    sub = parser.add_subparsers(dest="cmd")

    # chat (domyślna)
    sub.add_parser("chat", help="Czat z Jarvisem (domyślne)")

    # agent
    p_agent = sub.add_parser("agent", help="Agent Mode")
    p_agent.add_argument("task", nargs="*", help="Zadanie (opcjonalne)")

    # voice
    p_voice = sub.add_parser("voice", help="Tryb głosowy")
    p_voice.add_argument("--text-only", action="store_true")
    p_voice.add_argument("--voice", choices=["pl", "en"], default="pl")

    # api
    sub.add_parser("api", help="Serwer FastAPI (port 8000)")

    # monitor
    p_mon = sub.add_parser("monitor", help="Monitoring repozytorium")
    p_mon.add_argument("--interval", type=int, default=120)

    # memory
    p_mem = sub.add_parser("memory", help="Zarządzanie pamięcią")
    p_mem.add_argument("sub", nargs="?", choices=["show", "add", "update"], default="show")
    p_mem.add_argument("value", nargs="*")
    p_mem.add_argument("--type", choices=["note", "decision", "preference"], default="note")

    # status
    sub.add_parser("status", help="Status systemu Jarvisa")

    # update
    sub.add_parser("update", help="Aktualizuj repo i indeks RAG")

    # plugin
    p_plug = sub.add_parser("plugin", help="Zarządzanie pluginami")
    p_plug.add_argument("sub", nargs="?", choices=["list"], default="list")

    # multi
    p_multi = sub.add_parser("multi", help="Multi-Agent Mode — orkiestrator")
    p_multi.add_argument("task", nargs="*")

    # briefing
    sub.add_parser("briefing", help="Poranny briefing TireQ")

    # telegram
    sub.add_parser("telegram", help="Telegram Bot — zdalny dostęp z telefonu")

    # schedule
    p_sched = sub.add_parser("schedule", help="Zadania w tle (scheduler)")
    p_sched.add_argument("sub", nargs="?",
                         choices=["list", "start", "once", "run"], default="list")
    p_sched.add_argument("value", nargs="*")

    # train
    sub.add_parser("train", help="Zbierz i eksportuj dane treningowe")

    args = parser.parse_args()

    dispatch = {
        None:      do_chat,
        "chat":    do_chat,
        "agent":   do_agent,
        "voice":   do_voice,
        "api":     do_api,
        "monitor": do_monitor,
        "memory":  do_memory,
        "status":  do_status,
        "update":  do_update,
        "plugin":  do_plugin,
        "train":    do_train,
        "multi":    do_multi,
        "briefing": do_briefing,
        "schedule": do_schedule,
        "telegram": do_telegram,
    }
    dispatch.get(args.cmd, do_chat)(args)


if __name__ == "__main__":
    main()
