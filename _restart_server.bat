@echo off
cd /d C:\OddsFlowV4
taskkill /F /IM uvicorn.exe 2>nul
taskkill /F /IM python.exe 2>nul
timeout /t 3 /nobreak >nul
start "" powershell -ExecutionPolicy Bypass -File "C:\OddsFlowV4\start_server.ps1"
