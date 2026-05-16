@echo off
title J.A.R.V.I.S. — Setup i Start
color 0A

echo.
echo  ==========================================
echo   J.A.R.V.I.S. — Automatyczny setup
echo   Lenovo Legion 5 / RTX 5060
echo  ==========================================
echo.

:: Krok 1 — Sprawdz Ollama
echo  [1/4] Sprawdzam Ollame...
where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  UWAGA: Ollama nie jest zainstalowana.
    echo  Otwieram strone pobierania...
    start https://ollama.com/download
    echo.
    echo  Zainstaluj Ollame, a nastepnie uruchom ten plik ponownie.
    pause
    exit /b 1
)
echo  Ollama: OK

:: Krok 2 — Buduj model Jarvis jesli nie istnieje
echo  [2/4] Sprawdzam model Jarvis...
ollama list 2>nul | findstr /i "jarvis" >nul 2>&1
if %errorlevel% neq 0 (
    echo  Pierwszy start - pobieram Mistral i buduje Jarvisa (~4GB, kilka minut...
    ollama create jarvis -f "%~dp0training\Modelfile"
    if %errorlevel% neq 0 (
        echo  BLAD: Nie udalo sie zbudowac modelu.
        pause
        exit /b 1
    )
)
echo  Model Jarvis: OK

:: Krok 3 — Zainstaluj zaleznosci Python jesli brak
echo  [3/4] Sprawdzam Python i zaleznosci...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo  UWAGA: Python nie znaleziony.
    echo  Pobierz z python.org i zainstaluj z opcja "Add to PATH".
    start https://python.org/downloads
    pause
    exit /b 1
)

python -c "import ollama" >nul 2>&1
if %errorlevel% neq 0 (
    echo  Instaluje zaleznosci...
    pip install -q ollama sounddevice numpy pygame edge-tts faster-whisper
)
echo  Python i zaleznosci: OK

:: Krok 4 — Uruchom Jarvisa
echo  [4/4] Uruchamiam J.A.R.V.I.S. z pamiecia...
echo.
echo  ==========================================
echo.

python "%~dp0training\jarvis_ollama.py"
