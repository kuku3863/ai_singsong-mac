@echo off
setlocal
title So-VITS-SVC WebUI Launcher

echo ==========================================
echo       So-VITS-SVC WebUI Launcher
echo ==========================================

REM 0. Try global environment first (most reliable)
if exist "F:\anaconda3\envs\sovits_env\python.exe" (
    echo [INFO] Found global environment at: F:\anaconda3\envs\sovits_env
    "F:\anaconda3\envs\sovits_env\python.exe" webUI_local.py
    goto end
)

REM 1. Try local venv second
if exist ".\venv\Scripts\python.exe" (
    echo [INFO] Found local environment at: .\venv
    ".\venv\Scripts\python.exe" webUI_local.py
    goto end
)

REM 2. Fallback to conda activate
echo [INFO] Absolute path not found, trying 'conda activate sovits_env'...
call conda activate sovits_env
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate environment.
    echo Please check if Anaconda is installed and environment 'sovits_env' exists.
    pause
    exit /b
)

python webUI_local.py

:end
pause
