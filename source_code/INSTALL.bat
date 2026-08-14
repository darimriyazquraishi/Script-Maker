@echo off
setlocal
cd /d "%~dp0"
echo ===================================================
echo   Installing ScriptMaker Dependencies
echo ===================================================

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found in PATH!
    echo Please install Python 3.10+ from python.org and check "Add python.exe to PATH".
    pause
    exit /b 1
)

echo [1/3] Creating virtual environment (.venv)...
if not exist ".venv" (
    python -m venv .venv
)

echo [2/3] Upgrading pip...
call .venv\Scripts\python.exe -m pip install --upgrade pip

echo [3/3] Installing requirements...
call .venv\Scripts\pip.exe install -r requirements.txt

if %errorlevel% equ 0 (
    echo ===================================================
    echo   Installation Successful!
    echo   You can now launch ScriptMaker using START.bat
    echo ===================================================
) else (
    echo [ERROR] Dependency installation failed.
)
pause
