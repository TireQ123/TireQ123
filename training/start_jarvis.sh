#!/usr/bin/env bash
# J.A.R.V.I.S. — Uruchamiacz dla WSL2 / Linux (Lenovo Legion 5)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo " =========================================="
echo "  J.A.R.V.I.S. — Lokalny tryb"
echo "  Lenovo Legion 5 / RTX 5060"
echo " =========================================="
echo ""

# Sprawdź Ollama
if ! command -v ollama &>/dev/null; then
    echo " [BŁĄD] Ollama nie jest zainstalowana."
    echo ""
    echo " Instalacja (jedna komenda):"
    echo "   curl -fsSL https://ollama.com/install.sh | sh"
    echo ""
    exit 1
fi

# Uruchom serwer Ollama w tle jeśli nie działa
if ! ollama list &>/dev/null; then
    echo " [INFO] Uruchamiam serwer Ollama..."
    ollama serve &>/dev/null &
    sleep 2
fi

# Zbuduj model jeśli nie istnieje
if ! ollama list | grep -q "jarvis"; then
    echo " [INFO] Pierwszy start — buduję model Jarvisa..."
    echo " [INFO] Pobieranie Mistral ~4GB — chwila cierpliwości."
    echo ""
    ollama create jarvis -f "$SCRIPT_DIR/Modelfile"
    echo ""
    echo " [OK] Model Jarvis gotowy!"
    echo ""
fi

echo " Systemy aktywne. Możesz zacząć rozmowę."
echo " =========================================="
echo ""

python3 "$SCRIPT_DIR/jarvis_ollama.py"
