@echo off
setlocal

REM Run from the directory containing this script
cd /d "%~dp0"

REM Locate a usable Python executable
set "PY_CMD="
where python >nul 2>nul && set "PY_CMD=python"
if not defined PY_CMD (
    where py >nul 2>nul && set "PY_CMD=py"
)
if not defined PY_CMD (
    echo Python is not available on PATH.
    exit /b 1
)

echo Using %PY_CMD% for virtual environment management.

REM Create the virtual environment if missing
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment at .venv ...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        exit /b 1
    )
) else (
    echo Existing virtual environment detected.
)

REM Activate the virtual environment
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo Failed to activate virtual environment.
    exit /b 1
)

echo Upgrading pip ...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo Failed to upgrade pip.
    exit /b 1
)

echo Installing required packages ...
set "REQUIRED_PACKAGES=PyQt6 requests beautifulsoup4"
python -m pip install --upgrade %REQUIRED_PACKAGES%
if errorlevel 1 (
    echo Failed to install required packages.
    exit /b 1
)

echo Runtime dependencies installed successfully.
endlocal

echo.
echo Press any key to close...
pause >nul
