@echo off
cd /d C:\OddsFlowV4
set LOG=C:\OddsFlowV4\_restart2_log.txt
echo === restart %date% %time% === > "%LOG%"
echo --- killing whatever owns port 8083 --- >> "%LOG%"
powershell -ExecutionPolicy Bypass -Command "$c = Get-NetTCPConnection -LocalPort 8083 -State Listen -ErrorAction SilentlyContinue; if ($c) { $c.OwningProcess | Sort-Object -Unique | ForEach-Object { Write-Output ('killing PID ' + $_); Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } } else { Write-Output 'nothing listening on 8083' }" >> "%LOG%" 2>&1
timeout /t 3 >nul
echo --- starting fresh server (loads current code) --- >> "%LOG%"
start "OddsFlow Server" powershell -ExecutionPolicy Bypass -NoExit -File C:\OddsFlowV4\start_server.ps1
echo started >> "%LOG%"
timeout /t 10 >nul
echo --- port 8083 after --- >> "%LOG%"
powershell -ExecutionPolicy Bypass -Command "Get-NetTCPConnection -LocalPort 8083 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1 LocalPort,OwningProcess | Format-List" >> "%LOG%" 2>&1
type "%LOG%"
echo.
echo Done. Server reloading; give it ~10s more.
pause
