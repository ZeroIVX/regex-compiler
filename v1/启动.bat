@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

set "PY="

REM ---- Prefer the official Python launcher, fall back to python.exe ----
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY=py -3"

if not defined PY (
    python --version >nul 2>&1
    if not errorlevel 1 set "PY=python"
)

if not defined PY (
    echo.
    echo   [X] Python 3.10+ was not found.
    echo.
    echo       Install it from: https://www.python.org/downloads/
    echo       Remember to check "Add python.exe to PATH" during setup.
    echo.
    pause
    exit /b 1
)

%PY% "%~dp0start.py" %*

if errorlevel 1 (
    echo.
    echo   [!] Startup failed - see the message above.
    pause >nul
)
