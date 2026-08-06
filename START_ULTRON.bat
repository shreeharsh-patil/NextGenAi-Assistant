@echo off
title ULTRON -- AI Desktop Assistant
color 0A

echo ===================================================
echo    ULTRON AI Engine -- Launcher
echo ===================================================
echo.

cd /d "%~dp0"

REM ── Check if setup has been completed ─────────────────────────────────
if not exist ".ultron_setup_complete" (
    echo First-time launch detected. Running setup...
    echo.
    
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
    
    python ULTRON_SETUP.py
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo Setup failed. Check the messages above.
        pause
        exit /b %ERRORLEVEL%
    )
)

REM ── Launch ULTRON ─────────────────────────────────────────────────────
echo Launching ULTRON...
python main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ULTRON closed with an error (code %ERRORLEVEL%).
    pause
)
