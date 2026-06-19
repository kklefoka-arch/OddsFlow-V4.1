@echo off
cd /d C:\OddsFlowV4
echo === Session 24 commit ===
echo --- clearing any stale git lock ---
if exist ".git\index.lock" del /f /q ".git\index.lock"
echo --- staging ---
git add -A
echo --- committing ---
git -c user.name="KK" -c user.email="kklefoka@gmail.com" commit -m "Session 24: full v4 alignment - live growing baseline, multi-market drift, corner-denominator fix, v4-only reports + per-tab TAB_REFERENCE.md"
echo --- pushing ---
git push
echo.
echo Done. If push asked for login, use GitHub Desktop to push instead.
pause
