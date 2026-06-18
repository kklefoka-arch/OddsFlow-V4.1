@echo off
REM OddsFlow V4 - DF signal validation (read-only). Output: analysis\df_validation.txt
cd /d C:\OddsFlowV4
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
python scripts\validate_df.py
echo.
echo Done. Saved to analysis\df_validation.txt
pause
