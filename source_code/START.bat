@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ScriptMaker] Virtual environment not found. Running INSTALL.bat first...
    call INSTALL.bat
)

echo [ScriptMaker] Launching ScriptMaker...
start "" ".venv\Scripts\pythonw.exe" app.py
