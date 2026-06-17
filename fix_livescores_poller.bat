@echo off
REM OddsFlow V4 - apply the robust livescores poller schedule.
REM Double-click this; it will request admin (UAC), then run the .ps1.
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrator rights...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
cd /d C:\OddsFlowV4
powershell -ExecutionPolicy Bypass -File "C:\OddsFlowV4\fix_livescores_poller.ps1"
