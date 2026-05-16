#!/usr/bin/env python3
"""
J.A.R.V.I.S. RAG Index — Faza B
Indeksuje całą pamięć (profile, decisions, sessions) w lokalnej bazie wektorowej ChromaDB.
Model embeddingów: paraphrase-multilingual-MiniLM-L12-v2 (obsługuje język polski).

Użycie:
  python scripts/rag_index.py           # pełny reindeks
  python scripts/rag_index.py --delta   # tylko nowe wpisy
"""

import argparse
import json
import hashlib
from datetime import datetime
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

ROOT = Path(__file__).parent.parent
MEMORY_DIR = ROOT / "memory"
CHROMA_DIR = MEMORY_DIR / "chroma_db"

COLLECTION_NAME = "jarvis_memory"


def get_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    ef = DefaultEmbeddingFunction()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"}
    )


def stable_id(text: str, prefix: str) -> str:
    h = hashlib.md5(text.encode()).hexdigest()[:12]
    return f"{prefix}_{h}"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_documents() -> list[tuple[str, str, dict]]:
    """Zwraca listę (id, tekst, metadata) ze wszystkich plików pamięci."""
    docs = []

    # Decyzje techniczne
    decisions = load_json(MEMORY_DIR / "decisions.json").get("decisions", [])
    for d in decisions:
        text = d.get("decision", "")
        if text:
            docs.append((
                stable_id(text, "dec"),
                text,
                {"type": "decision", "date": d.get("date", ""), "source": d.get("source", "manual")}
            ))

    # Preferencje i notatki z profilu
    profile = load_json(MEMORY_DIR / "profile.json")
    for pref in profile.get("patterns", {}).get("preferred_solutions", []):
        if pref:
            docs.append((
                stable_id(pref, "pref"),
                pref,
                {"type": "preference", "date": ""}
            ))

    for note in profile.get("notes", []):
        text = note.get("note", "") if isinstance(note, dict) else note
        date = note.get("date", "") if isinstance(note, dict) else ""
        if text:
            docs.append((
                stable_id(text, "note"),
                text,
                {"type": "note", "date": date}
            ))

    # Sesje
    if (MEMORY_DIR / "sessions").exists():
        for f in sorted((MEMORY_DIR / "sessions").glob("*.json")):
            data = load_json(f)
            summary = data.get("summary", "")
            if summary:
                docs.append((
                    stable_id(summary, "sess"),
                    summary,
                    {"type": "session", "date": data.get("date", ""), "file": f.name}
                ))

    return docs


def index_all(delta: bool = False) -> int:
    collection = get_collection()
    docs = collect_documents()
    if not docs:
        print("[JARVIS RAG] Brak dokumentów do zaindeksowania.")
        return 0

    if delta:
        existing_ids = set(collection.get()["ids"])
        docs = [(id_, text, meta) for id_, text, meta in docs if id_ not in existing_ids]

    if not docs:
        print("[JARVIS RAG] Wszystkie dokumenty już zaindeksowane.")
        return 0

    ids, texts, metas = zip(*docs)
    collection.upsert(ids=list(ids), documents=list(texts), metadatas=list(metas))
    print(f"[JARVIS RAG] Zaindeksowano {len(docs)} dokumentów.")
    return len(docs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--delta", action="store_true", help="Tylko nowe wpisy")
    args = parser.parse_args()
    index_all(delta=args.delta)
