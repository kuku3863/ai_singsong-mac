@echo off
cd /d "D:\Python_project\ai_singsong\so-vits-svc"
echo Starting So-VITS-SVC WebUI (Local Version)...
echo Environment: F:\anaconda3\envs\sovits_env\python.exe
echo Script: webUI_local.py
echo.
echo IMPORTANT: When you close this window, the process will automatically terminate.
echo.

"F:\anaconda3\envs\sovits_env\python.exe" webUI_local.py

REM Force kill any remaining python processes related to this session
timeout /t 2 /nobreak >nul
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *webUI_local.py*" 2>nul