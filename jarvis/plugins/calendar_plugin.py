#!/usr/bin/env python3
"""
J.A.R.V.I.S. Plugin — Kalendarz.
Przechowuje terminy lokalnie w memory/calendar.json.
Opcjonalnie synchronizuje z Google Calendar (wymaga GOOGLE_CALENDAR_ID).

Użycie bez Google:
  jarvis agent "dodaj termin: spotkanie z klientem 2026-05-20 14:00"
  jarvis agent "pokaż mój plan na ten tydzień"
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from jarvis.plugins import JarvisPlugin

CALENDAR_FILE = Path(__file__).parent.parent.parent / "memory" / "calendar.json"


def _load() -> list[dict]:
    if not CALENDAR_FILE.exists():
        return []
    return json.loads(CALENDAR_FILE.read_text(encoding="utf-8"))


def _save(events: list[dict]) -> None:
    CALENDAR_FILE.parent.mkdir(exist_ok=True)
    CALENDAR_FILE.write_text(
        json.dumps(sorted(events, key=lambda e: e["datetime"]),
                   ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def calendar_add(title: str, datetime_str: str, notes: str = "") -> dict:
    try:
        dt = datetime.fromisoformat(datetime_str)
    except ValueError:
        return {"status": "error", "result": f"Zły format daty. Użyj: YYYY-MM-DD HH:MM"}
    events = _load()
    event = {
        "id": f"{dt.isoformat()}_{title[:20].replace(' ','_')}",
        "title": title,
        "datetime": dt.isoformat(),
        "notes": notes,
        "created": datetime.now().isoformat(timespec="seconds")
    }
    events = [e for e in events if e["id"] != event["id"]]
    events.append(event)
    _save(events)
    return {"status": "ok", "result": f"Dodano: {title} @ {dt.strftime('%Y-%m-%d %H:%M')}"}


def calendar_list(days: int = 7) -> dict:
    events = _load()
    now = datetime.now()
    cutoff = now + timedelta(days=days)
    upcoming = [
        e for e in events
        if now <= datetime.fromisoformat(e["datetime"]) <= cutoff
    ]
    if not upcoming:
        return {"status": "ok", "result": f"Brak wydarzeń w ciągu {days} dni."}
    lines = [f"Nadchodzące wydarzenia ({days} dni):"]
    for e in upcoming:
        dt = datetime.fromisoformat(e["datetime"])
        diff = (dt - now).days
        when = "dziś" if diff == 0 else f"za {diff} dni"
        lines.append(f"  [{dt.strftime('%m-%d %H:%M')} {when}] {e['title']}")
        if e.get("notes"):
            lines.append(f"    → {e['notes']}")
    return {"status": "ok", "result": "\n".join(lines)}


def calendar_today() -> dict:
    events = _load()
    today = datetime.now().date()
    todays = [
        e for e in events
        if datetime.fromisoformat(e["datetime"]).date() == today
    ]
    if not todays:
        return {"status": "ok", "result": "Brak wydarzeń na dziś."}
    lines = ["Plan na dziś:"]
    for e in todays:
        dt = datetime.fromisoformat(e["datetime"])
        lines.append(f"  {dt.strftime('%H:%M')} — {e['title']}")
    return {"status": "ok", "result": "\n".join(lines)}


def calendar_delete(title_fragment: str) -> dict:
    events = _load()
    before = len(events)
    events = [e for e in events if title_fragment.lower() not in e["title"].lower()]
    _save(events)
    removed = before - len(events)
    return {"status": "ok", "result": f"Usunięto {removed} wydarzeń zawierających '{title_fragment}'"}


def calendar_remind() -> dict:
    events = _load()
    now = datetime.now()
    soon = now + timedelta(hours=24)
    upcoming = [
        e for e in events
        if now <= datetime.fromisoformat(e["datetime"]) <= soon
    ]
    if not upcoming:
        return {"status": "ok", "result": "Brak przypomnień na najbliższe 24h."}
    lines = [f"⚠ Przypomnienia (24h):"]
    for e in upcoming:
        dt = datetime.fromisoformat(e["datetime"])
        mins = int((dt - now).total_seconds() / 60)
        when = f"za {mins} min" if mins < 60 else f"za {mins//60}h {mins%60}min"
        lines.append(f"  {when} — {e['title']}")
    return {"status": "ok", "result": "\n".join(lines)}


class CalendarPlugin(JarvisPlugin):
    name = "calendar"
    description = "Lokalny kalendarz — terminy, plan dnia, przypomnienia"
    enabled = True

    def get_tools(self):
        return [
            ("calendar_add", calendar_add,
             {"description": "Dodaje wydarzenie do kalendarza",
              "params": {"title": "str", "datetime_str": "YYYY-MM-DD HH:MM", "notes": "str opcjonalny"}}),
            ("calendar_list", calendar_list,
             {"description": "Lista nadchodzących wydarzeń",
              "params": {"days": "int — ile dni naprzód, domyślnie 7"}}),
            ("calendar_today", calendar_today,
             {"description": "Plan na dziś", "params": {}}),
            ("calendar_delete", calendar_delete,
             {"description": "Usuwa wydarzenie po fragmencie tytułu",
              "params": {"title_fragment": "str"}}),
            ("calendar_remind", calendar_remind,
             {"description": "Przypomnienia na najbliższe 24h", "params": {}}),
        ]


plugin = CalendarPlugin()
