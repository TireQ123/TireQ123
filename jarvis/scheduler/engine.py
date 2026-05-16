#!/usr/bin/env python3
"""
J.A.R.V.I.S. Scheduler — silnik zadań w tle.
Uruchamia zadania wg harmonogramu z tasks.json.

Formaty harmonogramu:
  "08:00"            — codziennie o 8:00 (repeat: daily)
  "sunday 10:00"     — w niedzielę o 10:00 (repeat: weekly)
  "every 1h"         — co godzinę (repeat: interval)
  "every 30m"        — co 30 minut
  "every 6h"         — co 6 godzin

Uruchomienie:
  python jarvis/scheduler/engine.py            — daemon (pętla)
  python jarvis/scheduler/engine.py --once     — wykonaj zaległe i zakończ
  python jarvis/scheduler/engine.py --list     — pokaż zadania
  python jarvis/scheduler/engine.py --run ID   — wymuś zadanie
"""
import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

TASKS_FILE = Path(__file__).parent / "tasks.json"
STATE_FILE = ROOT / "memory" / ".scheduler_state.json"
LOG_FILE = ROOT / "memory" / "scheduler.log"

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6
}


def _log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_tasks() -> list[dict]:
    if not TASKS_FILE.exists():
        return []
    return json.loads(TASKS_FILE.read_text(encoding="utf-8")).get("tasks", [])


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def parse_interval(schedule: str) -> timedelta | None:
    m = re.match(r"every\s+(\d+)\s*([hmd])", schedule.strip())
    if not m:
        return None
    num, unit = int(m.group(1)), m.group(2)
    return {
        "h": timedelta(hours=num),
        "m": timedelta(minutes=num),
        "d": timedelta(days=num)
    }[unit]


def should_run(task: dict, state: dict, now: datetime) -> bool:
    if not task.get("enabled", True):
        return False

    task_id = task["id"]
    last_run_str = state.get(task_id, {}).get("last_run", "")
    last_run = datetime.fromisoformat(last_run_str) if last_run_str else None
    schedule = task["schedule"]
    repeat = task.get("repeat", "interval")

    if repeat == "interval":
        delta = parse_interval(schedule)
        if not delta:
            return False
        return last_run is None or (now - last_run) >= delta

    if repeat == "daily":
        target = datetime.strptime(schedule, "%H:%M").time()
        if now.time() < target:
            return False
        if last_run is None:
            return True
        return last_run.date() < now.date()

    if repeat == "weekly":
        parts = schedule.lower().split()
        if len(parts) != 2:
            return False
        weekday_name, time_str = parts
        target_weekday = WEEKDAYS.get(weekday_name)
        target_time = datetime.strptime(time_str, "%H:%M").time()
        if now.weekday() != target_weekday or now.time() < target_time:
            return False
        if last_run is None:
            return True
        return (now - last_run).days >= 6

    return False


def execute_task(task: dict) -> str:
    task_type = task["type"]
    action = task["action"]
    params = task.get("params", {})

    try:
        if task_type == "script":
            args = params.get("args", [])
            result = subprocess.run(
                [sys.executable, str(ROOT / action), *args],
                cwd=ROOT, capture_output=True, text=True, timeout=300
            )
            return (result.stdout + result.stderr)[:500]

        elif task_type == "plugin":
            from jarvis.plugins import registry
            registry.load_all()
            fn = registry.tools.get(action)
            if fn:
                result = fn(**{k: v for k, v in params.items() if k != "args"})
                return str(result.get("result", ""))[:500]
            return f"Plugin tool '{action}' nie znaleziony"

        elif task_type == "agent":
            from jarvis.core.agent import run_agent
            return run_agent(action, verbose=False)[:500]

        elif task_type == "shell":
            result = subprocess.run(
                action, shell=True, cwd=ROOT,
                capture_output=True, text=True, timeout=300
            )
            return (result.stdout + result.stderr)[:500]

        return f"Nieznany typ zadania: {task_type}"
    except subprocess.TimeoutExpired:
        return "Timeout (>300s)"
    except Exception as e:
        return f"Błąd: {e}"


def run_pending(force_id: str = None, verbose: bool = True) -> int:
    tasks = load_tasks()
    state = load_state()
    now = datetime.now()
    executed = 0

    for task in tasks:
        run_it = (task["id"] == force_id) if force_id else should_run(task, state, now)
        if not run_it:
            continue

        if verbose:
            _log(f"▶ Uruchamiam: {task['name']} ({task['id']})")

        output = execute_task(task)
        state[task["id"]] = {
            "last_run": now.isoformat(timespec="seconds"),
            "last_output": output[:200]
        }
        executed += 1

        if verbose:
            _log(f"  ✓ {task['name']}: {output[:100].strip()}")

    save_state(state)
    return executed


def list_tasks() -> None:
    tasks = load_tasks()
    state = load_state()
    print("\n  ╔═══════════════════════════════════════╗")
    print("  ║  J.A.R.V.I.S. SCHEDULER — Zadania     ║")
    print("  ╚═══════════════════════════════════════╝\n")
    for t in tasks:
        status = "✓" if t.get("enabled", True) else "✗"
        last = state.get(t["id"], {}).get("last_run", "nigdy")
        print(f"  [{status}] {t['name']}")
        print(f"      id: {t['id']}  |  harmonogram: {t['schedule']}")
        print(f"      ostatnio: {last}\n")


def daemon_loop(interval: int = 60) -> None:
    _log("J.A.R.V.I.S. Scheduler — daemon uruchomiony")
    print(f"  Sprawdzanie co {interval}s. Ctrl+C aby zatrzymać.\n")
    while True:
        try:
            count = run_pending(verbose=True)
            if count == 0:
                pass
            time.sleep(interval)
        except KeyboardInterrupt:
            _log("Scheduler zatrzymany przez użytkownika")
            break
        except Exception as e:
            _log(f"Błąd w pętli: {e}")
            time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. Scheduler")
    parser.add_argument("--once", action="store_true", help="Wykonaj zaległe i zakończ")
    parser.add_argument("--list", action="store_true", help="Pokaż zadania")
    parser.add_argument("--run", metavar="ID", help="Wymuś konkretne zadanie")
    parser.add_argument("--interval", type=int, default=60, help="Sekundy między sprawdzeniami")
    args = parser.parse_args()

    if args.list:
        list_tasks()
    elif args.run:
        n = run_pending(force_id=args.run)
        print(f"[JARVIS] Wykonano {n} zadań.")
    elif args.once:
        n = run_pending()
        print(f"[JARVIS] Wykonano {n} zaległych zadań.")
    else:
        daemon_loop(args.interval)
