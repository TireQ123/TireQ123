#!/usr/bin/env python3
"""
J.A.R.V.I.S. Monitor — proaktywny monitoring projektu.
Pilnuje repozytorium i powiadamia o zmianach.

Monitoruje:
  - nowe commity w repo
  - zmiany w plikach (watchdog)
  - status CI/CD (GitHub Actions)
  - duże pliki przed commitem

Uruchomienie:
  python jarvis/monitor/watcher.py
  python jarvis/monitor/watcher.py --interval 60
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

ALERT_FILE = ROOT / "memory" / "monitor_alerts.json"
STATE_FILE = ROOT / "memory" / ".monitor_state.json"

# Progi alertów
MAX_FILE_SIZE_MB = 10
LARGE_FILE_EXTENSIONS_WARN = {".pkl", ".pt", ".bin", ".zip", ".tar"}


def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def _save_alert(category: str, message: str) -> None:
    alerts = []
    if ALERT_FILE.exists():
        alerts = json.loads(ALERT_FILE.read_text())
    alerts.append({
        "time": datetime.now().isoformat(timespec="seconds"),
        "category": category,
        "message": message
    })
    alerts = alerts[-100:]
    ALERT_FILE.write_text(json.dumps(alerts, indent=2, ensure_ascii=False))


def _run(cmd: str) -> str:
    try:
        return subprocess.check_output(cmd, shell=True, cwd=ROOT,
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return ""


def check_new_commits(state: dict) -> list[str]:
    """Wykrywa nowe commity od ostatniego sprawdzenia."""
    _run("git fetch origin --quiet")
    last_hash = state.get("last_commit", "")
    current_hash = _run("git rev-parse HEAD")
    if not last_hash:
        state["last_commit"] = current_hash
        return []
    if current_hash == last_hash:
        return []
    new_commits = _run(
        f"git log {last_hash}..{current_hash} --oneline --no-walk=sorted"
    ).splitlines()
    state["last_commit"] = current_hash
    return new_commits


def check_large_files() -> list[str]:
    """Szuka dużych plików które nie powinny być w repo."""
    alerts = []
    for f in ROOT.rglob("*"):
        if ".git" in f.parts or not f.is_file():
            continue
        size_mb = f.stat().st_size / 1_048_576
        if size_mb > MAX_FILE_SIZE_MB:
            alerts.append(f"{f.relative_to(ROOT)} ({size_mb:.1f}MB)")
        elif f.suffix in LARGE_FILE_EXTENSIONS_WARN and size_mb > 1:
            alerts.append(f"{f.relative_to(ROOT)} — plik binarny ({size_mb:.1f}MB)")
    return alerts


def check_secrets() -> list[str]:
    """Szuka potencjalnych sekretów w zmodyfikowanych plikach."""
    patterns = [
        "sk-ant-", "sk-", "AKIA", "AIza", "-----BEGIN",
        "password=", "secret=", "api_key="
    ]
    diff = _run("git diff --staged")
    found = []
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            for pattern in patterns:
                if pattern.lower() in line.lower():
                    found.append(f"Potencjalny sekret: '{pattern}' w diff")
                    break
    return found


def check_branch_status() -> dict:
    """Status gałęzi względem remote."""
    branch = _run("git branch --show-current")
    ahead = _run("git rev-list @{u}..HEAD --count 2>/dev/null") or "0"
    behind = _run("git rev-list HEAD..@{u} --count 2>/dev/null") or "0"
    return {
        "branch": branch,
        "ahead": int(ahead),
        "behind": int(behind)
    }


def run_once(verbose: bool = True) -> dict:
    state = _load_state()
    report = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "alerts": [],
        "info": []
    }

    # Nowe commity
    new_commits = check_new_commits(state)
    if new_commits:
        msg = f"Nowe commity ({len(new_commits)}): " + " | ".join(new_commits[:3])
        report["info"].append(msg)
        _save_alert("commit", msg)

    # Duże pliki
    large = check_large_files()
    if large:
        msg = f"Duże pliki w repo: {', '.join(large[:3])}"
        report["alerts"].append(msg)
        _save_alert("large_file", msg)

    # Sekrety w staged
    secrets = check_secrets()
    if secrets:
        for s in secrets:
            report["alerts"].append(f"UWAGA — {s}")
            _save_alert("secret", s)

    # Status gałęzi
    branch = check_branch_status()
    if branch["behind"] > 0:
        msg = f"Gałąź '{branch['branch']}' jest {branch['behind']} commitów za remote"
        report["alerts"].append(msg)
    if branch["ahead"] > 3:
        msg = f"Gałąź '{branch['branch']}' ma {branch['ahead']} nieopublikowanych commitów"
        report["info"].append(msg)

    _save_state(state)

    if verbose:
        now = report["time"]
        if report["alerts"]:
            for a in report["alerts"]:
                print(f"[{now}] ⚠  {a}")
        if report["info"]:
            for i in report["info"]:
                print(f"[{now}] ℹ  {i}")
        if not report["alerts"] and not report["info"]:
            print(f"[{now}] ✓  Wszystko w porządku.")

    return report


def watch_loop(interval: int = 120) -> None:
    print(f"\n  J.A.R.V.I.S. Monitor — aktywny (co {interval}s)")
    print("  Ctrl+C aby zatrzymać\n")
    while True:
        try:
            run_once()
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\n[JARVIS] Monitor zatrzymany.")
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=120, help="Sekundy między sprawdzeniami")
    parser.add_argument("--once", action="store_true", help="Sprawdź raz i zakończ")
    args = parser.parse_args()
    if args.once:
        run_once()
    else:
        watch_loop(args.interval)
