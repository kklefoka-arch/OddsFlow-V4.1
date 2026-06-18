@echo off
REM OddsFlow V4 - re-derive goals(mkt80)+corners(mkt67) over/under odds from raw_odds_json.
REM Idempotent + additive (never wipes existing values). Safe; touches nothing in the daily chain.
cd /d C:\OddsFlowV4
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
python scripts\rederive_odds.py
echo.
echo Done. Summary saved to analysis\rederive_odds_summary.txt
pause
