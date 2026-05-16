@echo off
:: J.A.R.V.I.S. Scheduler — Autostart dla Windows
:: Skopiuj skrot tego pliku do:
::   shell:startup
:: (Win+R -> wpisz: shell:startup -> Enter -> wklej skrot)
::
:: Scheduler bedzie dzialal w tle przy kazdym starcie Legiona.

title J.A.R.V.I.S. Scheduler
cd /d "%~dp0..\.."

:: Uruchom scheduler w tle (bez okna)
start /min "" python -m jarvis.scheduler.engine

echo J.A.R.V.I.S. Scheduler uruchomiony w tle.
echo Logi: memory\scheduler.log
timeout /t 3 >nul
