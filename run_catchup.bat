@echo off
cd /d C:\OddsFlowV4
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set LOG=C:\OddsFlowV4\_catchup_log.txt
echo ===== CATCHUP %date% %time% ===== > "%LOG%"

echo. >> "%LOG%"
echo --- eligible report (pre-run, no API) --- >> "%LOG%"
python _eligible_report.py >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo --- fetch_results.py --- >> "%LOG%"
python fetch_results.py >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo --- settle.py --- >> "%LOG%"
python settle.py >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo --- reconcile_orphans.py --- >> "%LOG%"
python scripts\reconcile_orphans.py >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo --- new settlement state --- >> "%LOG%"
python -c "import sqlite3;c=sqlite3.connect(r'C:\OddsFlowV4\data\oddsflow_v4.db');print('max settled_at:',c.execute('SELECT MAX(settled_at) FROM pick_results').fetchone());print('pick_results total:',c.execute('SELECT COUNT(*) FROM pick_results').fetchone());print('outcomes:',c.execute('SELECT outcome,COUNT(*) FROM pick_results GROUP BY outcome').fetchall());print('unsettled picks:',c.execute('SELECT COUNT(*) FROM emit_log em LEFT JOIN pick_results pr ON pr.pick_uuid=em.pick_uuid WHERE pr.pick_uuid IS NULL').fetchone())" >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo ===== DONE ===== >> "%LOG%"
type "%LOG%"
echo.
echo Catch-up complete. Saved to _catchup_log.txt
pause
