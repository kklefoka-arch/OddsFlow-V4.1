@echo off
REM OddsFlow V4 - H2H-corners signal validation (read-only). Output: analysis\h2h_validation.txt
cd /d C:\OddsFlowV4
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
python scripts\validate_h2h.py
echo.
echo Done. Saved to analysis\h2h_validation.txt
pause
