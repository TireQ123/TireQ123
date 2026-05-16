#!/usr/bin/env python3
"""
J.A.R.V.I.S. Plugin — Notatki lokalne (Markdown).
Przechowuje notatki w memory/notes/.
"""
import re
from datetime import datetime
from pathlib import Path
from jarvis.plugins import JarvisPlugin

NOTES_DIR = Path(__file__).parent.parent.parent / "memory" / "notes"


def _slug(title: str) -> str:
    return re.sub(r"[^\w\-]", "_", title.lower())[:50]


def note_create(title: str, content: str) -> dict:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{datetime.now().strftime('%Y%m%d')}_{_slug(title)}.md"
    path = NOTES_DIR / filename
    text = f"# {title}\n*{datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n{content}\n"
    path.write_text(text, encoding="utf-8")
    return {"status": "ok", "result": f"Notatka zapisana: {filename}"}


def note_list() -> dict:
    if not NOTES_DIR.exists():
        return {"status": "ok", "result": []}
    notes = []
    for f in sorted(NOTES_DIR.glob("*.md"), reverse=True)[:20]:
        lines = f.read_text(encoding="utf-8").splitlines()
        title = lines[0].lstrip("# ") if lines else f.stem
        notes.append({"file": f.name, "title": title})
    return {"status": "ok", "result": notes}


def note_read(filename: str) -> dict:
    path = NOTES_DIR / filename
    if not path.exists():
        return {"status": "error", "result": f"Notatka nie istnieje: {filename}"}
    return {"status": "ok", "result": path.read_text(encoding="utf-8")}


def note_search(query: str) -> dict:
    if not NOTES_DIR.exists():
        return {"status": "ok", "result": []}
    results = []
    keywords = query.lower().split()
    for f in NOTES_DIR.glob("*.md"):
        content = f.read_text(encoding="utf-8").lower()
        if all(kw in content for kw in keywords):
            lines = f.read_text(encoding="utf-8").splitlines()
            title = lines[0].lstrip("# ") if lines else f.stem
            results.append({"file": f.name, "title": title})
    return {"status": "ok", "result": results}


class NotesPlugin(JarvisPlugin):
    name = "notes"
    description = "Lokalne notatki Markdown w memory/notes/"
    enabled = True

    def get_tools(self):
        return [
            ("note_create", note_create,
             {"description": "Tworzy nową notatkę",
              "params": {"title": "str", "content": "str"}}),
            ("note_list", note_list,
             {"description": "Lista wszystkich notatek", "params": {}}),
            ("note_read", note_read,
             {"description": "Czyta notatkę po nazwie pliku",
              "params": {"filename": "str"}}),
            ("note_search", note_search,
             {"description": "Szuka notatek po słowach kluczowych",
              "params": {"query": "str"}}),
        ]


plugin = NotesPlugin()
