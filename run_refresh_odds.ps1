# OddsFlow V4 — manual refresh_odds (per-fixture fetch) + chained re-emit
Set-Location C:\OddsFlowV4
$stamp = (Get-Date -Format "yyyy-MM-dd_HH-mm")
Write-Host "=== refresh_odds (per-fixture) ===" -ForegroundColor Cyan
python refresh_odds.py 2>&1 | Tee-Object -FilePath "C:\OddsFlowV4\logs\refresh_odds_$stamp.log"
Write-Host "`n=== done ===" -ForegroundColor Green
