@echo off
title ULTRON -- First-Time Setup
color 0A

echo ===================================================
echo    ULTRON AI Engine -- First-Time Setup
echo ===================================================
echo.

cd /d "%~dp0"

REM ── Check Python is installed ─────────────────────────────────────────
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python was not found on this PC.
    echo.
    echo Please install Python 3.10 or newer from https://python.org
    echo During install, make sure to check "Add python.exe to PATH".
    echo Then double-click this file again.
    echo.
    pause
    exit /b 1
)

echo Running ULTRON setup...
echo.
python ULTRON_SETUP.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Setup encountered an error. Check the messages above.
    pause
    exit /b %ERRORLEVEL%
)

pause
