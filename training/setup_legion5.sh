#!/usr/bin/env bash
# J.A.R.V.I.S. Setup — Lenovo Legion 5, RTX 5060 8GB, Ryzen 7
# Uruchom w WSL2 (Ubuntu 22.04+) lub natywnym Linuksie

set -e

echo "=== JARVIS Setup: Legion 5 / RTX 5060 ==="

# 1. Sprawdź GPU
echo "[1/6] Sprawdzam GPU..."
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader \
  || { echo "BŁĄD: nvidia-smi niedostępne. Zainstaluj sterownik NVIDIA 570+"; exit 1; }

# 2. Sprawdź CUDA
echo "[2/6] Sprawdzam CUDA..."
nvcc --version 2>/dev/null || echo "  INFO: nvcc nie znaleziony — PyTorch użyje własnego CUDA"

# 3. Python venv
echo "[3/6] Tworzę środowisko wirtualne..."
python3 -m venv .venv_jarvis
source .venv_jarvis/bin/activate

# 4. Pip + PyTorch dla Blackwell (RTX 50xx wymaga CUDA 12.8+)
echo "[4/6] Instaluję PyTorch z CUDA 12.8..."
pip install --upgrade pip --quiet
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128 --quiet

# 5. Reszta zależności
echo "[5/6] Instaluję stack ML..."
pip install -r training/requirements_gpu.txt --quiet

# 6. Weryfikacja
echo "[6/6] Weryfikacja..."
python3 - <<'PYEOF'
import torch
print(f"  PyTorch:    {torch.__version__}")
print(f"  CUDA:       {torch.version.cuda}")
print(f"  GPU:        {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NIEDOSTĘPNE'}")
print(f"  VRAM:       {torch.cuda.get_device_properties(0).total_memory // 1024**3}GB" if torch.cuda.is_available() else "")
assert torch.cuda.is_available(), "BŁĄD: CUDA niedostępne!"
print("  Status:     OK")
PYEOF

echo ""
echo "=== Setup zakończony ==="
echo "Aktywuj środowisko: source .venv_jarvis/bin/activate"
echo "Następny krok:      python training/finetune_lora.py --dry-run"
