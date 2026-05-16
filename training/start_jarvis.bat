@echo off
:: J.A.R.V.I.S. — Uruchamiacz dla Windows (Lenovo Legion 5)
:: Dwuklik i Jarvis gotowy.

title J.A.R.V.I.S. — TireQ

echo.
echo  ==========================================
echo   J.A.R.V.I.S. — Lokalny tryb
echo   Lenovo Legion 5 / RTX 5060
echo  ==========================================
echo.

:: Sprawdź czy Ollama jest zainstalowana
where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo  [BLAD] Ollama nie jest zainstalowana.
    echo.
    echo  Pobierz z: https://ollama.com/download
    echo  Zainstaluj, a nastepnie uruchom ten plik ponownie.
    echo.
    pause
    exit /b 1
)

:: Sprawdź czy model jarvis istnieje
ollama list | findstr "jarvis" >nul 2>&1
if %errorlevel% neq 0 (
    echo  [INFO] Pierwszy start — buduje model Jarvisa...
    echo  [INFO] Pobieranie Mistral ~4GB - moze chwile potrwac.
    echo.
    ollama create jarvis -f "%~dp0Modelfile"
    if %errorlevel% neq 0 (
        echo  [BLAD] Nie udalo sie utworzyc modelu.
        pause
        exit /b 1
    )
    echo.
    echo  [OK] Model Jarvis gotowy!
    echo.
)

:: Uruchom Jarvisa z pamięcią
echo  Systemy aktywne. Mozesz zaczac rozmowe.
echo  ==========================================
echo.

:: Sprawdź czy Python dostępny
where python >nul 2>&1
if %errorlevel% equ 0 (
    python "%~dp0jarvis_ollama.py"
) else (
    echo  [INFO] Python niedostepny - uruchamiam bez pamieci
    ollama run jarvis
)
