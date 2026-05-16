#!/usr/bin/env python3
"""
J.A.R.V.I.S. Fine-tuning z QLoRA — Lenovo Legion 5, RTX 5060 8GB
Model bazowy: Mistral-7B-Instruct-v0.3

Optymalizacje pod 8GB VRAM:
  - 4-bit NF4 quantization (bitsandbytes)
  - LoRA r=16, alpha=32 (tylko q_proj, v_proj)
  - Gradient checkpointing
  - batch_size=1, grad_accum=8 → effective batch=8

Użycie:
  python training/finetune_lora.py --dry-run       # test konfiguracji
  python training/finetune_lora.py                 # pełny trening
  python training/finetune_lora.py --model llama   # LLaMA 3.1 8B zamiast Mistral
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
TRAINING_DIR = ROOT / "training"
RAW_FILE = TRAINING_DIR / "raw_pairs.jsonl"
OUTPUT_DIR = TRAINING_DIR / "jarvis_lora"

MODELS = {
    "mistral": "mistralai/Mistral-7B-Instruct-v0.3",
    "llama":   "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "phi":     "microsoft/Phi-3.5-mini-instruct",
}

# Konfiguracja zoptymalizowana pod RTX 5060 8GB
LORA_CONFIG = dict(
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    bias="none",
    task_type="CAUSAL_LM",
)

TRAINING_ARGS = dict(
    num_train_epochs=3,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=8,       # effective batch = 8
    gradient_checkpointing=True,         # oszczędza ~2GB VRAM
    learning_rate=2e-4,
    lr_scheduler_type="cosine",
    warmup_ratio=0.05,
    fp16=True,                           # RTX 5060 obsługuje FP16 natywnie
    logging_steps=10,
    save_steps=50,
    save_total_limit=2,
    max_grad_norm=0.3,
    optim="paged_adamw_8bit",            # 8-bit optimizer = mniej VRAM
    report_to="none",
)

QUANT_CONFIG = dict(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype="float16",
    bnb_4bit_use_double_quant=True,      # podwójna kwantyzacja = +0.4GB wolne VRAM
)


def load_dataset(min_score: float = 0.5) -> list[dict]:
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


def format_chat(messages: list[dict], tokenizer) -> str:
    return tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=False
    )


def dry_run(model_name: str) -> None:
    print(f"\n=== DRY RUN — {model_name} ===")
    print(f"Model bazowy:  {MODELS[model_name]}")
    print(f"VRAM szacowane:")
    print(f"  Model 4-bit:     ~4.5 GB")
    print(f"  LoRA adaptery:   ~0.3 GB")
    print(f"  Aktywacje:       ~1.5 GB  (grad_checkpointing)")
    print(f"  Optimizer 8-bit: ~0.8 GB")
    print(f"  Łącznie:         ~7.1 GB  (RTX 5060 8GB ✓)")
    print(f"\nLoRA config:   r={LORA_CONFIG['r']}, alpha={LORA_CONFIG['lora_alpha']}")
    print(f"Batch:         {TRAINING_ARGS['per_device_train_batch_size']} × "
          f"{TRAINING_ARGS['gradient_accumulation_steps']} = "
          f"{TRAINING_ARGS['per_device_train_batch_size'] * TRAINING_ARGS['gradient_accumulation_steps']} efektywny")
    print(f"Epoki:         {TRAINING_ARGS['num_train_epochs']}")

    dataset = load_dataset()
    if dataset:
        print(f"\nDane:          {len(dataset)} par (score ≥ 0.5)")
        est_time = len(dataset) * TRAINING_ARGS['num_train_epochs'] * 3 // 60
        print(f"Czas szacowany: ~{est_time} min na RTX 5060")
    else:
        print(f"\nDANE:          BRAK — uruchom najpierw:")
        print(f"  python scripts/training_collect.py --all-sessions")
        print(f"  python scripts/training_generate.py --count 50")

    print(f"\nOutput:        {OUTPUT_DIR}/")
    print("=============================\n")


def train(model_name: str, min_score: float) -> None:
    import torch
    from transformers import (
        AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
    )
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from trl import SFTTrainer
    from datasets import Dataset

    assert torch.cuda.is_available(), "Brak CUDA. Sprawdź sterowniki NVIDIA."
    vram_gb = torch.cuda.get_device_properties(0).total_memory // 1024**3
    print(f"[JARVIS] GPU: {torch.cuda.get_device_name(0)} ({vram_gb}GB VRAM)")

    model_id = MODELS[model_name]
    print(f"[JARVIS] Ładuję model: {model_id}")

    bnb_config = BitsAndBytesConfig(**{
        k: (eval(v) if isinstance(v, str) and v.startswith("torch.") else v)
        for k, v in {**QUANT_CONFIG,
                     "bnb_4bit_compute_dtype": torch.float16}.items()
    })

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map="auto",
        torch_dtype=torch.float16,
    )
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, LoraConfig(**LORA_CONFIG))
    model.print_trainable_parameters()

    # Przygotuj dataset
    raw = load_dataset(min_score)
    assert raw, f"Brak danych (score ≥ {min_score}). Uruchom training_collect.py."

    texts = [format_chat(p["messages"], tokenizer) for p in raw]
    dataset = Dataset.from_dict({"text": texts})
    print(f"[JARVIS] Dataset: {len(dataset)} przykładów")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    args = TrainingArguments(output_dir=str(OUTPUT_DIR), **TRAINING_ARGS)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        args=args,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=2048,
    )

    print("[JARVIS] Rozpoczynam trening...")
    trainer.train()

    model.save_pretrained(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))
    print(f"\n[JARVIS] Model zapisany: {OUTPUT_DIR}/")
    print("[JARVIS] Następny krok: python training/run_jarvis.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=list(MODELS), default="mistral")
    parser.add_argument("--min-score", type=float, default=0.5)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        dry_run(args.model)
    else:
        train(args.model, args.min_score)
