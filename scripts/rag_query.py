#!/usr/bin/env python3
"""
J.A.R.V.I.S. RAG Query — Faza B
Semantyczne wyszukiwanie w pamięci. Zwraca top-K najbardziej relevantnych wspomnień.

Użycie:
  python scripts/rag_query.py "jak budujemy backend?"
  python scripts/rag_query.py "deadline projektu" --top 5
  python scripts/rag_query.py "wszystko" --top 10 --type decision
"""

import argparse
import json
import re
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

ROOT = Path(__file__).parent.parent
CHROMA_DIR = ROOT / "memory" / "chroma_db"
COLLECTION_NAME = "jarvis_memory"

TYPE_LABELS = {
    "decision": "Decyzja",
    "preference": "Preferencja",
    "note": "Notatka",
    "session": "Sesja",
}


def get_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    ef = DefaultEmbeddingFunction()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"}
    )


def _keyword_search(text: str, top_k: int, filter_type: str | None) -> list[dict]:
    """Fallback: szukaj słów kluczowych w plikach pamięci."""
    from pathlib import Path
    import json as _json

    memory_dir = ROOT / "memory"
    keywords = [w.lower() for w in re.split(r"\W+", text) if len(w) > 2]
    hits: list[dict] = []

    def scan(items: list, type_: str, text_fn, date_fn):
        for item in items:
            t = text_fn(item).lower()
            score = sum(1 for kw in keywords if kw in t) / max(len(keywords), 1)
            if score > 0 and (filter_type is None or filter_type == type_):
                hits.append({
                    "text": text_fn(item),
                    "type": type_,
                    "date": date_fn(item),
                    "relevance": round(min(score, 1.0), 3)
                })

    decisions = _json.loads((memory_dir / "decisions.json").read_text())["decisions"] \
        if (memory_dir / "decisions.json").exists() else []
    profile = _json.loads((memory_dir / "profile.json").read_text()) \
        if (memory_dir / "profile.json").exists() else {}

    scan(decisions, "decision",
         lambda x: x.get("decision", ""), lambda x: x.get("date", "")[:10])
    scan(profile.get("patterns", {}).get("preferred_solutions", []), "preference",
         lambda x: x, lambda x: "")
    scan(profile.get("notes", []), "note",
         lambda x: x.get("note", "") if isinstance(x, dict) else x,
         lambda x: x.get("date", "")[:10] if isinstance(x, dict) else "")

    hits.sort(key=lambda x: x["relevance"], reverse=True)
    return hits[:top_k]


def query(text: str, top_k: int = 5, filter_type: str | None = None) -> list[dict]:
    collection = get_collection()

    vector_results: list[dict] = []
    if collection.count() > 0:
        where = {"type": filter_type} if filter_type else None
        results = collection.query(
            query_texts=[text],
            n_results=min(top_k, collection.count()),
            where=where,
            include=["documents", "metadatas", "distances"]
        )
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        ):
            vector_results.append({
                "text": doc,
                "type": meta.get("type", "unknown"),
                "date": meta.get("date", "")[:10],
                "relevance": round(1 - dist, 3)
            })
        vector_results = [r for r in vector_results if r["relevance"] >= 0.20]

    keyword_results = _keyword_search(text, top_k, filter_type)

    # Scal — weź unikalne teksty, wyższy score wygrywa
    seen: set[str] = set()
    merged: list[dict] = []
    for item in sorted(vector_results + keyword_results,
                       key=lambda x: x["relevance"], reverse=True):
        key = item["text"].strip().lower()[:80]
        if key not in seen:
            seen.add(key)
            merged.append(item)

    return merged[:top_k]


def format_results(items: list[dict]) -> str:
    if not items:
        return "[JARVIS RAG] Brak relevantnych wspomnień."
    lines = []
    for i in items:
        label = TYPE_LABELS.get(i["type"], i["type"])
        date = f" [{i['date']}]" if i["date"] else ""
        rel = f" ({int(i['relevance']*100)}%)"
        lines.append(f"• [{label}{date}{rel}] {i['text']}")
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="Zapytanie semantyczne")
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--type", dest="filter_type", choices=["decision", "preference", "note", "session"])
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    results = query(args.query, top_k=args.top, filter_type=args.filter_type)

    if args.as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(format_results(results))
