@echo off
:: J.A.R.V.I.S. — Uruchamiacz dla Windows (Lenovo Legion 5)
:: Dwuklik i Jarvis gotowy.

title J.A.R.V.I.S. — TireQ
chcp 65001 >nul 2>&1

echo.
echo  ====================================================
echo   J.A.R.V.I.S. — Lokalny tryb
echo   Lenovo Legion 5 / RTX 5060
echo  ====================================================
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

:: Uruchom serwer Ollama jeśli nie działa
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    echo  [INFO] Uruchamiam serwer Ollama w tle...
    start /b ollama serve >nul 2>&1
    timeout /t 3 /nobreak >nul
)

:: Sprawdź czy model jarvis istnieje
ollama list 2>nul | findstr /i "jarvis" >nul 2>&1
if %errorlevel% neq 0 (
    echo  [INFO] Pierwszy start — buduje model Jarvisa...
    echo  [INFO] Pobieranie llama3.1:8b ~4.9GB - moze chwile potrwac.
    echo.
    ollama create jarvis -f "%~dp0Modelfile"
    if %errorlevel% neq 0 (
        echo.
        echo  [BLAD] Nie udalo sie utworzyc modelu.
        echo  Sprawdz czy plik Modelfile istnieje w folderze training/
        pause
        exit /b 1
    )
    echo.
    echo  [OK] Model Jarvis gotowy!
    echo.
)

:: Sprawdź czy Python dostępny
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo  [OSTRZEZENIE] Python niedostepny — uruchamiam bez pamieci.
    echo  Zainstaluj Python 3.11+ z python.org dla pelnej funkcjonalnosci.
    echo.
    ollama run jarvis
    pause
    exit /b 0
)

:: Uruchom Jarvisa z pamięcią i streamingiem
echo  [OK] Systemy gotowe. Uruchamiam Jarvisa...
echo.
python "%~dp0jarvis_ollama.py"

echo.
pause
