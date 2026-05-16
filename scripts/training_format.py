#!/usr/bin/env python3
"""
J.A.R.V.I.S. Training Format — Faza C
Konwertuje zebrane pary na formaty gotowe do fine-tuningu.

Obsługiwane formaty:
  - openai   → JSONL dla OpenAI fine-tuning API (gpt-3.5-turbo, gpt-4o-mini)
  - alpaca   → JSON dla lokalnych modeli (LLaMA, Mistral via LoRA)
  - huggingface → JSONL dla HuggingFace Trainer

Użycie:
  python scripts/training_format.py --format openai --min-score 0.6
  python scripts/training_format.py --format alpaca --min-score 0.5
  python scripts/training_format.py --format all
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
TRAINING_DIR = ROOT / "training"
RAW_FILE = TRAINING_DIR / "raw_pairs.jsonl"


def load_raw(min_score: float = 0.5) -> list[dict]:
    if not RAW_FILE.exists():
        return []
    pairs = []
    with open(RAW_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                p = json.loads(line)
                if p.get("score", 0) >= min_score:
                    pairs.append(p)
            except Exception:
                pass
    return pairs


def format_openai(pairs: list[dict], output: Path) -> int:
    """Format: OpenAI fine-tuning JSONL (messages array)"""
    with open(output, "w", encoding="utf-8") as f:
        for p in pairs:
            entry = {"messages": p["messages"]}
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return len(pairs)


def format_alpaca(pairs: list[dict], output: Path) -> int:
    """Format: Alpaca instruction-following JSON (dla LLaMA/Mistral)"""
    entries = []
    for p in pairs:
        msgs = p["messages"]
        system = next((m["content"] for m in msgs if m["role"] == "system"), "")
        user = next((m["content"] for m in msgs if m["role"] == "user"), "")
        assistant = next((m["content"] for m in msgs if m["role"] == "assistant"), "")
        entries.append({
            "instruction": system,
            "input": user,
            "output": assistant
        })
    with open(output, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    return len(entries)


def format_huggingface(pairs: list[dict], output: Path) -> int:
    """Format: HuggingFace datasets JSONL (text field z formatowaniem chat)"""
    with open(output, "w", encoding="utf-8") as f:
        for p in pairs:
            msgs = p["messages"]
            system = next((m["content"] for m in msgs if m["role"] == "system"), "")
            user = next((m["content"] for m in msgs if m["role"] == "user"), "")
            assistant = next((m["content"] for m in msgs if m["role"] == "assistant"), "")
            text = (
                f"<|system|>\n{system}\n"
                f"<|user|>\n{user}\n"
                f"<|assistant|>\n{assistant}"
            )
            f.write(json.dumps({"text": text}, ensure_ascii=False) + "\n")
    return len(pairs)


FORMATS = {
    "openai": (format_openai, "openai_finetune.jsonl"),
    "alpaca": (format_alpaca, "alpaca_train.json"),
    "huggingface": (format_huggingface, "hf_train.jsonl"),
}


def export(fmt: str, min_score: float) -> None:
    pairs = load_raw(min_score)
    if not pairs:
        print(f"[JARVIS C] Brak danych (score ≥ {min_score}). Uruchom training_collect.py.")
        return

    targets = list(FORMATS.items()) if fmt == "all" else [(fmt, FORMATS[fmt])]
    for name, (fn, filename) in targets:
        output = TRAINING_DIR / filename
        count = fn(pairs, output)
        print(f"[JARVIS C] {name:12s} → {output.name} ({count} przykładów)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=["openai", "alpaca", "huggingface", "all"],
                        default="openai")
    parser.add_argument("--min-score", type=float, default=0.5,
                        help="Minimalny score jakości (0-1)")
    args = parser.parse_args()
    export(args.format, args.min_score)
