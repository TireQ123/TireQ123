# J.A.R.V.I.S. — Faza C: Fine-Tuning

## Krok 1 — Zbierz dane (zrób to teraz)

```bash
# Z transkryptów sesji Claude Code
python scripts/training_collect.py --transcript ~/.claude/projects/.../transcript.json

# Z podsumowań sesji w memory/
python scripts/training_collect.py --all-sessions

# Wygeneruj syntetyczne dane (wymaga klucza API)
export ANTHROPIC_API_KEY=sk-ant-...
python scripts/training_generate.py --count 50
python scripts/training_generate.py --count 30 --topic "praca z Pythonem i FastAPI"
python scripts/training_generate.py --count 30 --topic "git, deploy, infrastruktura"

# Sprawdź statystyki
python scripts/training_collect.py --show-stats
```

**Rekomendowane minimum:** 100 par do sensownego fine-tuningu.

---

## Krok 2 — Eksportuj dane

```bash
# OpenAI (najszybszy start)
python scripts/training_format.py --format openai --min-score 0.6

# Lokalny model (LLaMA/Mistral)
python scripts/training_format.py --format alpaca --min-score 0.5

# Wszystkie formaty naraz
python scripts/training_format.py --format all
```

---

## Krok 3A — Fine-tuning przez OpenAI API

```bash
pip install openai
export OPENAI_API_KEY=sk-...

# Prześlij dane
openai api fine_tuning.jobs.create \
  -t training/openai_finetune.jsonl \
  -m gpt-4o-mini

# Sprawdź status
openai api fine_tuning.jobs.list
```

**Koszt:** ~$0.008/1K tokenów dla gpt-4o-mini. 100 par ≈ $2-5.

---

## Krok 3B — Fine-tuning lokalny z LoRA (bez kosztów)

### Wymagania
- GPU: min. 8GB VRAM (RTX 3080, RTX 4070, lub Mac M2 Pro+)
- Model bazowy: Mistral-7B lub LLaMA-3-8B

```bash
pip install transformers peft accelerate bitsandbytes trl

python - <<'EOF'
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from peft import LoraConfig, get_peft_model
from trl import SFTTrainer
import json

MODEL = "mistralai/Mistral-7B-Instruct-v0.3"
tokenizer = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, load_in_4bit=True)

lora_config = LoraConfig(r=16, lora_alpha=32, target_modules=["q_proj", "v_proj"])
model = get_peft_model(model, lora_config)

training_args = TrainingArguments(
    output_dir="training/lora_output",
    num_train_epochs=3,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    fp16=True,
)

# Wczytaj dane
dataset = []
with open("training/hf_train.jsonl") as f:
    for line in f:
        dataset.append(json.loads(line))

trainer = SFTTrainer(
    model=model,
    args=training_args,
    train_dataset=dataset,
    dataset_text_field="text",
)
trainer.train()
model.save_pretrained("training/jarvis_lora")
EOF
```

---

## Krok 3C — Ollama (lokalnie, bez GPU)

```bash
# Pobierz model bazowy
ollama pull mistral

# Stwórz Modelfile
cat > training/Modelfile <<'EOF'
FROM mistral
SYSTEM """Jesteś J.A.R.V.I.S. — osobisty asystent AI Marcela (TireQ).
Odpowiadasz po polsku, elegancko. Zwracasz się 'Panie TireQ'."""
EOF

# Zbuduj model z osobowością Jarvisa
ollama create jarvis -f training/Modelfile

# Uruchom
ollama run jarvis
```

---

## Status danych

Uruchom: `python scripts/training_collect.py --show-stats`
