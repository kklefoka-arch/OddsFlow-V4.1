@echo off
cd /d C:\OddsFlowV4
echo Stopping current uvicorn server (leaves other python alone)...
powershell -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and ($_.CommandLine -like '*uvicorn*' -or $_.CommandLine -like '*app.main*') } | ForEach-Object { Write-Output ('Stopping PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force }"
timeout /t 3 >nul
echo Starting fresh server (loads all current code)...
start "OddsFlow Server" powershell -ExecutionPolicy Bypass -NoExit -File C:\OddsFlowV4\start_server.ps1
echo.
echo Server restart triggered. Give it ~10 seconds, then refresh the board.
timeout /t 5 >nul
