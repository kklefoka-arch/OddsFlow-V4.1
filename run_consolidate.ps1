# OddsFlow V4 — build the full-database consolidation workbook (file-monitored)
Set-Location C:\OddsFlowV4
$log = "C:\OddsFlowV4\analysis\_consolidate_run.log"
$st  = "C:\OddsFlowV4\analysis\_consolidate_status.txt"
New-Item -ItemType Directory -Force -Path C:\OddsFlowV4\analysis | Out-Null
"STARTED $(Get-Date -Format o)" | Out-File $st
"=== pip install openpyxl ===" | Out-File $log
python -m pip install openpyxl --quiet --disable-pip-version-check *>> $log 2>&1
"=== running consolidate.py ===" | Out-File -Append $log
python scripts\consolidate.py *>> $log 2>&1
"DONE $(Get-Date -Format o) exit=$LASTEXITCODE" | Out-File -Append $st
Write-Host "Done — see analysis\_consolidate_run.log"
