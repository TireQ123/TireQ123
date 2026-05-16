#!/usr/bin/env python3
"""
J.A.R.V.I.S. Run — uruchamia wytrenowany model lokalnie.
Tryb interaktywny — rozmowa z Jarvisem przez terminal.

Użycie:
  python training/run_jarvis.py
  python training/run_jarvis.py --model mistral   # model bazowy (bez LoRA)
"""

import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent
LORA_DIR = ROOT / "training" / "jarvis_lora"

SYSTEM_PROMPT = (
    "Jesteś J.A.R.V.I.S. — osobisty asystent AI Marcela (TireQ). "
    "Odpowiadasz po polsku, elegancko i precyzyjnie. "
    "Zwracasz się 'Panie TireQ'. Nigdy nie mówisz 'nie mogę' bez alternatywy."
)


def run_local(use_lora: bool) -> None:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, pipeline

    if use_lora and LORA_DIR.exists():
        from peft import PeftModel
        base_id = (LORA_DIR / "adapter_config.json").read_text()
        import json
        base_model_id = json.loads(base_id).get("base_model_name_or_path",
                                                  "mistralai/Mistral-7B-Instruct-v0.3")
        print(f"[JARVIS] Ładuję model + LoRA: {LORA_DIR}")
        bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)
        tokenizer = AutoTokenizer.from_pretrained(str(LORA_DIR))
        model = AutoModelForCausalLM.from_pretrained(
            base_model_id, quantization_config=bnb, device_map="auto"
        )
        model = PeftModel.from_pretrained(model, str(LORA_DIR))
    else:
        model_id = "mistralai/Mistral-7B-Instruct-v0.3"
        print(f"[JARVIS] Ładuję model bazowy: {model_id}")
        bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(
            model_id, quantization_config=bnb, device_map="auto"
        )

    pipe = pipeline("text-generation", model=model, tokenizer=tokenizer)
    history = [{"role": "system", "content": SYSTEM_PROMPT}]

    print("\n" + "="*50)
    print("  J.A.R.V.I.S. — Tryb lokalny")
    print("  Wpisz 'exit' aby zakończyć")
    print("="*50 + "\n")

    while True:
        try:
            user_input = input("Ty: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[JARVIS] Do zobaczenia, Panie TireQ.")
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "bye"):
            print("[JARVIS] Do zobaczenia, Panie TireQ.")
            break

        history.append({"role": "user", "content": user_input})

        output = pipe(
            history,
            max_new_tokens=512,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id,
        )

        response = output[0]["generated_text"][-1]["content"]
        history.append({"role": "assistant", "content": response})
        print(f"\nJARVIS: {response}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["lora", "base"], default="lora")
    args = parser.parse_args()
    run_local(use_lora=(args.model == "lora"))
