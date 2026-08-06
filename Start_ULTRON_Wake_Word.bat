@echo off
title ULTRON -- Wake Word Service
color 0A

echo ==============================================
echo   ULTRON -- Starting Wake Word Listener...
echo ==============================================

cd /d "%~dp0"

REM ── Check if setup has been completed ──────────────────────────────
if not exist ".ultron_setup_complete" (
    echo First-time launch detected. Running setup first...
    echo.
    python ULTRON_SETUP.py
    if %ERRORLEVEL% NEQ 0 (
        echo Setup failed. Check the messages above.
        pause
        exit /b %ERRORLEVEL%
    )
)

echo.
echo Launching Wake Word Listener ("wake up ultron")...
python wake_service.py

echo.
pause
