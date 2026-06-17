# OddsFlow V4 — Re-register the livescores poller with a robust trigger.
# RUN THIS AS ADMINISTRATOR (the task runs at RunLevel Highest).
#
# Why: the old task used a single -Once trigger whose 5-min repetition did not
# resume after the PC was off for a day (poller went dark 2026-06-13 -> 06-15).
# This re-registers it to re-arm daily + run at startup, with StartWhenAvailable,
# and kicks it off immediately so live auto-settlement resumes now.

$ErrorActionPreference = "Stop"
$python  = (Get-Command python).Source
$workdir = "C:\OddsFlowV4"

$action = New-ScheduledTaskAction -Execute $python `
            -Argument "scripts/livescores_poller.py" -WorkingDirectory $workdir

# Daily re-arm: every day at 00:02, repeat every 5 min for ~24h.
$daily = New-ScheduledTaskTrigger -Daily -At 00:02
$daily.Repetition = (New-ScheduledTaskTrigger -Once -At 00:02 `
            -RepetitionInterval (New-TimeSpan -Minutes 5) `
            -RepetitionDuration (New-TimeSpan -Hours 23 -Minutes 58)).Repetition
$boot  = New-ScheduledTaskTrigger -AtStartup

$settings = New-ScheduledTaskSettingsSet `
            -ExecutionTimeLimit (New-TimeSpan -Minutes 4) `
            -MultipleInstances IgnoreNew -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
            -LogonType S4U -RunLevel Highest

Register-ScheduledTask -TaskName "OddsFlow_LivescoresPoller" -Action $action `
            -Trigger @($daily, $boot) -Settings $settings -Principal $principal -Force

Start-ScheduledTask -TaskName "OddsFlow_LivescoresPoller"

Write-Host ""
Write-Host "OddsFlow_LivescoresPoller re-registered (daily re-arm + at-startup) and started." -ForegroundColor Green
Write-Host "Check the Today tab in ~6 min: the livescores_poller badge should be green." -ForegroundColor Green
Write-Host ""
pause
