@echo off
REM =============================================================================
REM start.bat - Doppelklick-Start fuer Windows-Anwender
REM teRealTactTimes - technosert electronic GmbH
REM =============================================================================
cd /d "%~dp0"

if not exist ".venv" (
    echo Erstelle virtuelle Umgebung ...
    py -3 -m venv .venv
)

call .venv\Scripts\activate.bat

echo Installiere/aktualisiere Abhaengigkeiten ...
pip install -q -r requirements.txt

echo Starte teRealTactTimes ...
python main.py

pause
