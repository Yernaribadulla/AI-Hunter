@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "desktop.py"
  exit /b %errorlevel%
)

where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 "desktop.py"
  if %errorlevel% neq 0 pause
  exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel% equ 0 (
  python "desktop.py"
  if %errorlevel% neq 0 pause
  exit /b %errorlevel%
)

echo Python was not found.
echo Install Python 3.11+ or create .venv with: python -m venv .venv
pause
exit /b 1
