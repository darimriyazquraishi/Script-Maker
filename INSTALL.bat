@echo off
setlocal
title ScriptMaker - One Click Installer
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON=py"
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (set "PYTHON=python") else (
    echo Python 3.10+ is required.
    echo Install it from https://www.python.org/downloads/windows/
    echo Enable "Add python.exe to PATH".
    pause
    exit /b 1
  )
)

%PYTHON% -c "import sys; print('Python', sys.version.split()[0]); raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
  echo ScriptMaker requires Python 3.10 or newer.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" %PYTHON% -m venv .venv
if errorlevel 1 goto fail

.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto fail

.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail

if not exist ".env" copy /Y ".env.example" ".env" >nul
if not exist "llama" mkdir "llama"
if not exist "models" mkdir "models"

.venv\Scripts\python.exe check_install.py
if errorlevel 1 goto fail

echo.
echo Installation complete.
echo Put llama-server.exe in the llama folder.
echo Put your GGUF model in the models folder.
echo Then double-click START.bat.
pause
exit /b 0

:fail
echo.
echo Installation failed. See the error above.
pause
exit /b 1
