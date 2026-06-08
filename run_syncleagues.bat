@echo off
cd /d C:\OddsFlowV4
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set LOG=C:\OddsFlowV4\_syncleagues_log.txt
python sync_leagues.py > "%LOG%" 2>&1
type "%LOG%"
echo.
echo Sync complete. Saved to _syncleagues_log.txt
pause
