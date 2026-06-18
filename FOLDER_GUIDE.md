# OddsFlow V4 — Folder Guide

Quick map so things stay findable. (Reorganised 2026-06-18.)

## Root = the live app (do not move these)
The engine scripts, launchers, and the FastAPI app live at root because Task
Scheduler, `run_daily.ps1`, and `uvicorn app.main:app` call them by this path.
Moving them breaks the running system, so root is kept clean instead.

- **OPERATOR_MANUAL.md** — how to operate everything (start here).
- **Engine scripts:** `db_healthcheck.py`, `sync_leagues.py`, `fetch_upcoming.py`,
  `emit_picks.py`, `refresh_odds.py`, `refresh_stats.py`, `fetch_results.py`, `settle.py`
- **Launchers you double-click:** `run_daily.bat` (full daily chain),
  `restart_server.bat` / `restart_server2.bat` (restart the server),
  `fix_livescores_poller.bat`, `run_now.bat`, `run_catchup.bat`, `run_syncleagues.bat`
- **PowerShell:** `run_daily.ps1`, `start_server.ps1`, `setup_scheduler.ps1`
- **Packages/data:** `app/`, `scripts/`, `data/` (the DB + backups), `context/`,
  `logs/` (per-run step logs)
- **Config:** `requirements.txt`, `Procfile`, `railway.*`, `CLAUDE.md`

## notes/  — all your notes (never auto-deleted)
Docx, pdf, and markdown notes. Includes `raw notes/` (the anchor-signals notes).

## analysis/  — test outputs & validations
e.g. `OddsFlow_Signal_Validation.xlsx`. Put future test sheets here.

## archive/  — old/unused stuff, moved here instead of deleted
Probe scripts, diagnostic logs, screenshots, one-off migrations, superseded files.
Nothing here is used by the app. Safe to delete the whole folder when you're sure
(the sandbox can't delete files, so I move them here rather than remove them).

## Daily, in one place
The things you actually run day-to-day are all at root: read **OPERATOR_MANUAL.md**,
then double-click **run_daily.bat**. The manual's §8 explains every runbook task and
its manual command.
