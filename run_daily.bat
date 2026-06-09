@echo off
cd /d C:\OddsFlowV4
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set LOG=C:\OddsFlowV4\_rundaily_log.txt
echo Running full daily chain (db_healthcheck -^> sync_leagues -^> fetch_upcoming -^> emit -^> fetch_results -^> settle -^> reconcile)...
powershell -ExecutionPolicy Bypass -File run_daily.ps1 > "%LOG%" 2>&1
echo.
echo ===== tail of run =====
powershell -Command "Get-Content '%LOG%' -Tail 40"
echo.
echo Daily chain complete. Full output saved to _rundaily_log.txt
pause
