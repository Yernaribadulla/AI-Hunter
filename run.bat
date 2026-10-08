@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo AI-Hunter virtual environment was not found at .venv
  echo Create it with: python -m venv .venv
  pause
  exit /b 1
)
start "AI-Hunter" ".venv\Scripts\python.exe" "desktop.py"
