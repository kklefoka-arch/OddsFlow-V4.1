@echo off
cd /d C:\OddsFlowV4
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set LOG=C:\OddsFlowV4\_fixrun_log.txt
echo ===== FIX+RUN %date% %time% ===== > "%LOG%"

echo --- killing only the stuck fetch_results python (server is spared) --- >> "%LOG%"
powershell -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*fetch_results*' } | ForEach-Object { Write-Output ('Killing PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force }" >> "%LOG%" 2>&1
timeout /t 4 >nul

echo. >> "%LOG%"
echo --- fetch_results (fixed: active-only + lock-tolerant) --- >> "%LOG%"
python fetch_results.py >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo --- settle --- >> "%LOG%"
python settle.py >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo --- reconcile_orphans --- >> "%LOG%"
python scripts\reconcile_orphans.py >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo --- final state --- >> "%LOG%"
python -c "import sqlite3;c=sqlite3.connect(r'C:\OddsFlowV4\data\oddsflow_v4.db', timeout=30);c.execute('PRAGMA busy_timeout=30000');print('max settled_at:',c.execute('SELECT MAX(settled_at) FROM pick_results').fetchone());print('outcomes:',c.execute('SELECT outcome,COUNT(*) FROM pick_results GROUP BY outcome').fetchall());print('unsettled picks:',c.execute('SELECT COUNT(*) FROM emit_log em LEFT JOIN pick_results pr ON pr.pick_uuid=em.pick_uuid WHERE pr.pick_uuid IS NULL').fetchone())" >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo ===== DONE ===== >> "%LOG%"
type "%LOG%"
echo.
echo Complete. Saved to _fixrun_log.txt
pause
