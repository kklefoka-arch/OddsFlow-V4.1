# Group 3 Plan — Automation
## Gaps: G5 (manual settle), G6 (no cron/scheduler)

**Phase connection:** Phase 8 (Score Update) → Phase 9 (Settle) → Phase 1 (Fetch, daily)
**Status:** IMPLEMENTED in Sessions 6 + 13 + 15 + 18. `run_daily.ps1` exists (4-step chain incl. emit_picks). `setup_scheduler.ps1` registers 12 Task Scheduler jobs (Europe + SA + Dawn SA windows + refresh_odds + refresh_stats + server + ngrok). All daily scripts write `system_health` heartbeats. Retained as audit trail.
**Dependency:** Group 1 livescores path is implemented; the additional Task Scheduler jobs remain to cover non-livescores windows.

---

## Scope note

If Group 1 (Display layer) implements the livescores auto-trigger hook:
- Match finish detected by livescores polling → score written inline → settle triggered inline
- **G5 is closed by Group 1 for match-day fixtures**
- Group 3 scope reduces to: scheduling fetch_upcoming.py daily only

If Group 1 does NOT implement the auto-trigger hook:
- G5 remains open — settle.py must be triggered after each match day
- Group 3 must cover: fetch_upcoming.py daily + fetch_results.py post-match + settle.py post-results

**This plan covers both scenarios.** Implement the correct path after Group 1 scope is confirmed.

---

## G5 — Manual Settle Trigger

### Scenario A: Group 1 livescores hook implemented
G5 is closed. No action required in Group 3.

### Scenario B: Group 1 livescores hook NOT implemented

**Approach: Chained daily script**

Create `run_daily.ps1` that runs the full daily operator flow in sequence:

```powershell
# run_daily.ps1
Set-Location C:\OddsFlowV4

Write-Host "=== fetch_upcoming ===" 
python fetch_upcoming.py

Write-Host "=== fetch_results ==="
python fetch_results.py

Write-Host "=== settle ==="
python settle.py

Write-Host "=== done ==="
```

---

## G6 — Scheduler

**Platform:** Windows — use Windows Task Scheduler (built-in, no additional dependencies)

### Scenario A: Group 1 livescores hook implemented

Only fetch_upcoming.py needs scheduling.

### Scenario B: Group 1 livescores hook NOT implemented

Three tasks: daily_fetch + post_match_results + daily_settle.

### system_health table
Each script run writes a heartbeat:
```sql
INSERT OR REPLACE INTO system_health (script, last_run, status)
VALUES ('fetch_upcoming', datetime('now'), 'ok');
```
This lets the Reports tab surface "last run" times and detect stale fetches.

---

## Files created/modified

| File | Change |
|------|--------|
| `run_daily.ps1` | Chained operator script |
| `fetch_upcoming.py` | system_health heartbeat write |
| `fetch_results.py` | system_health heartbeat write |
| `settle.py` | system_health heartbeat write |
| `setup_scheduler.ps1` | Creates Windows Task Scheduler tasks (run once) |

---

## Cross-cut summary across all groups

| Group 1 decision | Group 3 impact |
|-----------------|---------------|
| Livescores hook implemented | G5 closed; G6 = 1 scheduled task only |
| Livescores hook deferred | G5 open; G6 = 3 scheduled tasks + run_daily.ps1 |
