#!/usr/bin/env python3
"""
J.A.R.V.I.S. RAG Inject — Faza B
Pobiera ostatnią wiadomość użytkownika z transkryptu,
odpytuje bazę wektorową i wstrzykuje relevantny kontekst do CLAUDE.md.

Uruchamiany automatycznie przez Stop hook po memory_sync.
Env vars:
  CLAUDE_TRANSCRIPT_PATH
"""

import json
import os
from datetime import datetime
from pathlib import Path

from rag_query import query, format_results

ROOT = Path(__file__).parent.parent
CLAUDE_FILE = ROOT / "CLAUDE.md"
MARKER_START = "<!-- JARVIS:RAG:START -->"
MARKER_END = "<!-- JARVIS:RAG:END -->"

TOP_K = 6
MIN_RELEVANCE = 0.25


def get_last_user_message(transcript_path: str) -> str | None:
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        messages = data if isinstance(data, list) else data.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content[:500]
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            return block.get("text", "")[:500]
    except Exception:
        pass
    return None


def build_rag_block(items: list[dict]) -> str:
    if not items:
        return ""
    lines = [
        MARKER_START,
        f"## Relevantna pamięć — {datetime.now().strftime('%H:%M')}",
        "",
    ]
    for i in items:
        from rag_query import TYPE_LABELS
        label = TYPE_LABELS.get(i["type"], i["type"])
        date = f" [{i['date']}]" if i["date"] else ""
        lines.append(f"- **{label}{date}:** {i['text']}")
    lines += ["", MARKER_END]
    return "\n".join(lines)


def inject_to_claude(block: str) -> None:
    content = CLAUDE_FILE.read_text(encoding="utf-8")
    if MARKER_START in content:
        start = content.index(MARKER_START)
        end = content.index(MARKER_END) + len(MARKER_END)
        content = content[:start] + block + content[end:]
    else:
        content = content.rstrip() + "\n\n" + block + "\n"
    CLAUDE_FILE.write_text(content, encoding="utf-8")


def main() -> None:
    transcript_path = os.environ.get("CLAUDE_TRANSCRIPT_PATH", "")
    if not transcript_path or not Path(transcript_path).exists():
        return

    last_msg = get_last_user_message(transcript_path)
    if not last_msg:
        return

    results = query(last_msg, top_k=TOP_K)
    results = [r for r in results if r["relevance"] >= MIN_RELEVANCE]

    if not results:
        return

    block = build_rag_block(results)
    inject_to_claude(block)
    print(f"[JARVIS RAG] Wstrzyknięto {len(results)} relevantnych wspomnień.")


if __name__ == "__main__":
    main()
