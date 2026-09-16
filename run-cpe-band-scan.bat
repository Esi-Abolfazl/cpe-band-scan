@echo off
rem First run: make a private Python environment next to the app and install into it.
cd /d "%~dp0"
rem this runs before Python exists, so copy.py cannot serve this sentence
if not exist .venv\Scripts\cpe-band-scan.exe (
  python -m venv .venv && .venv\Scripts\pip install -q . || (echo CPE Band Scan needs Python 3.10 or newer. Install it from python.org, then double-click again. & pause & exit /b 1)
)
.venv\Scripts\cpe-band-scan ui
pause
