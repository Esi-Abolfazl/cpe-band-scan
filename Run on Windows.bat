@echo off
rem First run: uv builds a private Python environment next to the app and installs into it.
cd /d "%~dp0"
set "PATH=%USERPROFILE%\.local\bin;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
where uv >nul 2>&1 || (
  rem this runs before the app's Python exists, so copy.py cannot serve these sentences
  echo CPE Band Scan needs uv, which sets up everything else for you.
  echo Install it with:  winget install astral-sh.uv
  echo Then double-click this file again.
  pause
  exit /b 1
)
uv run cpe-band-scan ui
pause
