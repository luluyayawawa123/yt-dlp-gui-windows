@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m pip install --upgrade pip pyinstaller
".venv\Scripts\python.exe" "build.py"
echo.
echo Press any key to close...
pause >nul
