@echo off
setlocal EnableExtensions EnableDelayedExpansion
title ScriptMaker - One Click Start
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ScriptMaker is not installed yet.
    echo Run INSTALL.bat first.
    pause
    exit /b 1
)

set "LLAMA_EXE="
if exist "%~dp0llama\llama-server.exe" set "LLAMA_EXE=%~dp0llama\llama-server.exe"
if not defined LLAMA_EXE if exist "C:\AI\llama.cpp\llama-server.exe" set "LLAMA_EXE=C:\AI\llama.cpp\llama-server.exe"
if not defined LLAMA_EXE if exist "%USERPROFILE%\llama.cpp\llama-server.exe" set "LLAMA_EXE=%USERPROFILE%\llama.cpp\llama-server.exe"
if not defined LLAMA_EXE for /f "delims=" %%F in ('where llama-server.exe 2^>nul') do if not defined LLAMA_EXE set "LLAMA_EXE=%%F"

set "LLAMA_SERVER_URL=http://127.0.0.1:8080"
set "LLAMA_PORT=8080"
set "LLAMA_CONTEXT=32768"

if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        if "%%A"=="LLAMA_SERVER_URL" if not "%%B"=="" set "LLAMA_SERVER_URL=%%B"
        if "%%A"=="LLAMA_PORT" if not "%%B"=="" set "LLAMA_PORT=%%B"
        if "%%A"=="LLAMA_CONTEXT" if not "%%B"=="" set "LLAMA_CONTEXT=%%B"
        if "%%A"=="LLAMA_MODEL_PATH" if not "%%B"=="" set "LLAMA_MODEL_PATH=%%B"
        if "%%A"=="LLAMA_SERVER_EXE" if not "%%B"=="" set "LLAMA_EXE=%%B"
    )
)

if not defined LLAMA_MODEL_PATH (
    for %%F in ("%~dp0models\*.gguf") do if not defined LLAMA_MODEL_PATH set "LLAMA_MODEL_PATH=%%~fF"
)

echo.
echo Detected llama-server:
echo   %LLAMA_EXE%
echo Detected GGUF:
echo   %LLAMA_MODEL_PATH%
echo.

if not defined LLAMA_EXE (
    echo llama-server.exe not found.
    echo Put it in:
    echo   %~dp0llama\
    pause
    exit /b 1
)

if not defined LLAMA_MODEL_PATH (
    echo No GGUF model found.
    echo Put your .gguf file in:
    echo   %~dp0models\
    pause
    exit /b 1
)

.venv\Scripts\python.exe -c "import requests,sys; sys.exit(0 if requests.get('%LLAMA_SERVER_URL%/health',timeout=2).ok else 1)" >nul 2>nul
if not errorlevel 1 goto launch_app

echo Starting local AI server...
start "ScriptMaker - Local AI" /min "%LLAMA_EXE%" -m "%LLAMA_MODEL_PATH%" -ngl 99 -c %LLAMA_CONTEXT% --host 127.0.0.1 --port %LLAMA_PORT%

set /a COUNT=0
:wait
set /a COUNT+=1
.venv\Scripts\python.exe -c "import requests,sys; sys.exit(0 if requests.get('%LLAMA_SERVER_URL%/health',timeout=2).ok else 1)" >nul 2>nul
if not errorlevel 1 goto launch_app
if %COUNT% GEQ 90 (
    echo llama-server did not become ready.
    echo Check the "ScriptMaker - Local AI" window.
    pause
    exit /b 1
)
timeout /t 2 /nobreak >nul
goto wait

:launch_app
echo Local AI server is ready.
start "" ".venv\Scripts\python.exe" "app.py"
exit /b 0
