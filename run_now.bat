@echo off
cd /d C:\OddsFlowV4
echo === fetch_upcoming ===
python fetch_upcoming.py
echo.
echo === emit_picks ===
python emit_picks.py --mode emit
echo.
echo === fetch_results ===
python fetch_results.py
echo.
echo === settle ===
python settle.py
echo.
echo === Done! Press any key to close ===
pause
