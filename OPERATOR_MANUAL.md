# OddsFlow V4 — Operator Manual

**Operator:** Katlego (KK) | **Port:** 8083 | **Updated:** 2026-06-19

> **Companion document:** `TAB_REFERENCE.md` describes every tab in full — what each
> panel shows, how the number is computed, and exactly which endpoint + code function
> feeds it. Use it to check the app against its documentation: if a tab shows something
> that doesn't match `TAB_REFERENCE.md`, you can point to the precise endpoint/function
> and I can review the code against the doc.

---

## Quick Reference

| What | Where |
|------|-------|
| Operator view | http://localhost:8083/ |
| API docs | http://localhost:8083/docs |
| Health check | http://localhost:8083/healthz |
| ngrok URL | https://steadier-legwarmer-finlike.ngrok-free.dev |
| Database | C:\OddsFlowV4\data\oddsflow_v4.db |
| Start server | `cd C:\OddsFlowV4 && .\start_server.ps1` |
| Run full chain manually | `cd C:\OddsFlowV4 && .\run_daily.ps1` |

---

## Daily Operations Cheat Sheet

> **Morning routine (after 08:05 SAST if scheduler missed):**
> ```powershell
> cd C:\OddsFlowV4
> python fetch_upcoming.py
> python emit_picks.py --mode emit
> ```
> **Evening routine (after 23:45 SAST if scheduler missed):**
> ```powershell
> cd C:\OddsFlowV4
> python fetch_results.py
> python settle.py
> ```
> **One command to run everything:**
> ```powershell
> cd C:\OddsFlowV4
> .\run_daily.ps1
> ```
> ⚠️ Always `cd C:\OddsFlowV4` first. Do **not** type the path alone on a line — PowerShell will error.

---

## Daily Task List

Run these tasks each day to keep the system current. The Task Scheduler handles them automatically, but run manually if the Today tab shows overdue badges.

### Morning (after 08:00 SAST)

| # | Task | Command | What it does |
|---|------|---------|--------------|
| 1 | **Fetch upcoming** | `python fetch_upcoming.py` | Pulls next 7 months of fixtures + pre-match odds from Sportmonks. Classifies zone + BTS for each fixture. |
| 2 | **Emit picks** | `python emit_picks.py --mode emit` | Calls `/picks?days=3` and writes results to `emit_log`. Picks appear on the Picks tab. |

### Afternoon (after 14:30 SAST — same day)

| # | Task | Command | What it does |
|---|------|---------|--------------|
| 3 | **Refresh odds** | `python refresh_odds.py` | Re-fetches odds for fixtures kicking off in the next 30h. Updates draw_zone + bts_pocket if odds moved. Chains a re-emit automatically. |

### Evening / Night (after matches end, ~23:30 SAST)

| # | Task | Command | What it does |
|---|------|---------|--------------|
| 4 | **Fetch results** | `python fetch_results.py` | Pulls final scores + fixture_stats (corners) from Sportmonks. |
| 5 | **Settle picks** | `python settle.py` | Reads scores and writes WIN/LOSS/VOID to `pick_results`. Hit rates update. |

### Weekly (any time)

| # | Task | Command | What it does |
|---|------|---------|--------------|
| 6 | **Refresh stats** | `python refresh_stats.py` | Backfills corner stats for the last 14 days. Fixes "pending (played)" picks stuck on unsettled corners. |
| 7 | **Reconcile orphans** | `python scripts/reconcile_orphans.py` | Marks picks for dropped/expired fixtures as ORPHAN so they don't pollute hit rate. |

### How to open PowerShell in the right folder

Option A — from File Explorer:
1. Navigate to `C:\OddsFlowV4`
2. Click the address bar, type `powershell`, press Enter

Option B — from Start:
1. Open **Windows PowerShell**
2. Type `cd C:\OddsFlowV4` and press Enter
3. Run your command

Option C — double-click `run_now.bat` in `C:\OddsFlowV4` to run the full chain in a command window.

### Checking the scheduler is running

Open the Today tab at `http://localhost:8083/` → look at the **Runbook** strip. Red badges mean that task hasn't run within its expected window. If multiple tasks are red:

1. Press `Win + R` → type `taskschd.msc` → Enter
2. In Task Scheduler, expand **Task Scheduler Library**
3. Look for tasks starting with `OddsFlow_` — verify they show Status = **Ready** and Last Run Result = **0x0**
4. If any show **Disabled**, right-click → Enable
5. If the Last Run Result is not 0x0, right-click the task → Run to trigger it manually

---

## 1. Starting the Server

The server auto-starts at system boot via Task Scheduler (OddsFlow_Server task). If it's not running:

```powershell
cd C:\OddsFlowV4
.\start_server.ps1
```

This starts uvicorn on port 8083 with `--reload` (code changes auto-apply) and ngrok in a separate window.

**Verify:** open http://localhost:8083/ — you should see the Engine view with "healthy" badge in the top-right.

---

## 2. The Engine View — Tab by Tab

The operator view at `http://localhost:8083/` has 9 tabs.

### Picks
The primary daily tab. Shows all fixtures in a (zone × BTS) promoted cell within the day window (default 3 days).

- **PROMOTE chip** — fixture is in one of the 8 active v4 cells. All picks on this tab are PROMOTE-class.
- **Partition key** — e.g. `standard:over` (zone:bts). The cell the fixture fell into.
- **Zone chip** — `strong` / `standard` / `low` / `one_sided` from draw_odd.
- **Drift chip** — if the cell's recent hit rate is >5pp below historical, shows `watch` or `drifting`. Display only — does not suppress picks.
- **Market rows** — Goals NL (O1.5), Corners NL (O7.5 for strong zone, O8.5 for rest), 3-Way (Alpha or Draw).
- **Odds** — shown if present; `—` means odds weren't stored (intraday refresh may add them).
- **Click any card** → jumps to Inspector with that fixture loaded.
- **↓ CSV** — paper-trading export for the current window.

#### Signal chips (on each card)
These are display-only. None suppress or gate picks.
- **spread chip** — `strong` or `slight` (BTS yes/no spread). In `standard:over` and `low:over` cells, goals leg carries the strong-spread hit rate when spread=strong.
- **df chip** — DF0/DF1/DF2 (DF is dead as a cell axis, lives as a signal).
- **h2h chip** — derived from prior meetings in our own DB. `over`/`under`/`none`.

### Picks Log
Advanced three-picks layer built on top of the ground-zero emits. Shows Most-likely / Mean / Optimistic configs per fixture:
- **Most-likely** — natural lines, alpha-or-draw (draw protected), accumulator
- **Mean** — 1-up lines (e.g. O2.5 if natural is O1.5), system bets (6-of-9)
- **Optimistic** — 2-up lines + straight alpha-win, system bets (3-of-6)

This is legs-only (v1). EV / economic modelling lands here in a later pass.

### Upcoming
All classified fixtures in the window (not just promoted). Use this to see the full pipeline — what the engine classified, what got promoted, what's missing odds.

- **★ PROMOTE** chip on cards that are in a promoted cell
- Fixtures with `zone=—` are unclassifiable (missing draw_odd — odds not yet fetched for that fixture)
- Filter by Tier (T1/T2/T3) using the dropdown

### Analysis
Foundation Matrix — hit rates per (zone × BTS) cell from all 29,470+ settled fixtures.

- Subtabs: ALL / T1+T2 / T3 (Rule 6 tier split)
- **✓ YES** in the rightmost column = cell is live in the v4 policy (fires picks)
- Goals/Corners/3-Way hit rates per cell (Rule 5 — not blended)
- PROMOTE / PROMOTE_TOLERANCE / HOLD columns show the foundation algorithm's per-market evaluation

### Inspector
Two sections:
1. **Selected fixture** — populated when you click a pick card in the Picks tab. Shows markets, odds, partition key.
2. **Partition drift table** — for every promoted cell: historical hit rate vs recent hit rate. Green = stable, orange = watch (5–10pp below), red = drifting (>10pp below). The drift window is adjustable (7/14/30/90 days).

The inspector does not suppress anything — it's the operator's read on how cells are performing lately.

### Reports
Full engine self-evaluation. Sections:

- **Settlement activity** — picks settled per day in the window
- **Multi-window performance** — 7d / 14d / 30d / 90d leg and event hit rates vs baselines
- **Per-market summary** — goals_nl / corners_nl / threeway settled counts + hit rates vs pre-overlay baseline (Rule 5)
- **Zone × market** — structural breakdown: which zones drive which markets
- **Pending breakdown** — unsettled picks split by "upcoming" (normal) vs "played" (settlement gap = corners stats backlog)
- **Settlement status by kickoff window** — is yesterday settled? Read at a glance per market
- **Per-cell market hit rates** — live performance table per (zone × bts) cell

Filter by tier (all / T1 / T2 / T3) and time window.

### Results
Settled fixtures from the DB. Shows score, corners total, partition, and how each pick settled (WIN / LOSS / VOID / PENDING).

**Live Scores** button — polls Sportmonks for in-play fixtures. Refreshes every 60s when active. Shows the Live badge when in-play matches are found.

### Today
System health dashboard. Refreshes every 60s.

- **Cron chip** — age of last heartbeat from the daily pipeline
- **Last clean run chip** — age of last full clean pipeline run (green ≤26h, orange ≤48h, red >48h)
- **Chain chip** — verified/BROKEN — confirms fetch_upcoming → emit_picks data chain is intact
- **Drift chip** — quick partition stability summary
- **Runbook strip** — per-task overdue status for all 12 pipeline metrics (see §8 for what each one means and how to fix a red badge)

### Stats
Deep system stats: DB table counts, cron heartbeat, odds coverage per league, drift report detail.

---

## 3. Daily Pipeline

The pipeline runs automatically via Task Scheduler. All scripts are in `C:\OddsFlowV4\`.

| Time (SAST) | Task | Script | Purpose |
|-------------|------|--------|---------|
| System start | OddsFlow_Server | uvicorn | Start the API server |
| System start | OddsFlow_Ngrok | ngrok | Expose port 8083 publicly |
| 00:00 | OddsFlow_RefreshStats | refresh_stats.py | Backfill corner stats (14d lookback) |
| 03:00 | OddsFlow_FetchResults_SA | fetch_results.py | South American results window |
| 03:15 | OddsFlow_Settle_SA | settle.py | Settle SA picks |
| 06:00 | OddsFlow_FetchResults_DawnSA | fetch_results.py | Late SA catch-up |
| 06:15 | OddsFlow_Settle_DawnSA | settle.py | Settle late SA picks |
| 08:00 | OddsFlow_FetchUpcoming | fetch_upcoming.py | Daily pre-match odds refresh |
| 08:05 | OddsFlow_EmitPicks | emit_picks.py | Emit picks for next 3 days |
| 14:30 | OddsFlow_RefreshOdds | refresh_odds.py | Intraday odds refresh (next 30h) + re-emit |
| 23:30 | OddsFlow_FetchResults | fetch_results.py | European results |
| 23:45 | OddsFlow_Settle | settle.py | Settle European picks |

### Manual chain

```powershell
cd C:\OddsFlowV4
.\run_daily.ps1
# Runs (in order): db_healthcheck → sync_leagues → fetch_upcoming →
#                  emit_picks → fetch_results → settle → reconcile_orphans
```

Or double-click **`run_daily.bat`** in `C:\OddsFlowV4` — it opens a command
window, runs the same chain, and pauses on a tail of the log so you can read
the result. (A `.py` file double-clicked just opens in the editor — it does
**not** run. Always use the `.bat`, or a terminal.)

Or run individual scripts:
```powershell
python fetch_upcoming.py      # Fetch + classify upcoming fixtures
python emit_picks.py          # Emit picks (calls /picks internally)
python refresh_odds.py        # Intraday odds + chained re-emit
python refresh_stats.py       # Corner stats backfill
python fetch_results.py       # Fetch scores after matches
python settle.py              # Write pick_results from scores
```

---

## 4. The V4 Policy

### Zone boundaries (draw_odd)
| Zone | draw_odd range | Status |
|------|---------------|--------|
| excluded (both_sided) | < 2.90 | Not emitted |
| strong | 2.90 – 3.29 | Active |
| standard | 3.30 – 3.79 | Active (cleanest cell) |
| low | 3.80 – 4.29 | Active |
| one_sided | ≥ 4.30 | Active |

### 8 active cells (zone × bts)
BTS direction: `over` = BTS yes_odd ≤ no_odd (market expects goals); `under` = opposite.

| Cell | Composite hit % | n |
|------|----------------|---|
| strong:over | 70.3% | ~5k |
| strong:under | 69.5% | ~5k |
| standard:over | 71.3% | ~11k |
| standard:under | 69.9% | ~9k |
| low:over | 75.6% | ~5k |
| low:under | 71.8% | ~4k |
| one_sided:over | 80.4% | ~4k |
| one_sided:under | 80.6% | ~3k |

### Markets per cell
- **goals_nl** — Over 1.5 Goals (all zones)
- **corners_nl** — Over 7.5 Corners (strong zone) / Over 8.5 Corners (all other zones)
- **threeway** — Alpha or Draw (a draw is a WIN — no void, no stake return)

### Signals (display only — never gate emission)
- **BTS spread** (strong/slight): One goals-override in standard:over and low:over — when spread=strong, goals leg carries the strong-spread hit rate instead of the blended cell rate
- **DF** (DF0/DF1/DF2): Display chip only. Dead in 5/8 cells. Never a cell axis (Durable Rule 1)
- **H2H corner** (over/under/none): Derived from our own prior meetings in the DB

### Hit-rate convention
Threeway: binary — wins ÷ settled. A draw is a WIN (no void, stake never returned). Goals_nl / corners_nl: same binary. Legacy `dnb` rows in the DB: non-loss (wins + voids) ÷ settled. No Wilson intervals.

---

## 5. Leagues (28 active)

Full list in `context/02_league_config.md`. Tier split is the operator's
editorial call (the Sportmonks API has no tier field).

Big 5 EU (PL, Ligue 1, La Liga, Serie A, La Liga 2) are **not** in the
subscription. Dropped 2026-06-09: Bolivia, Ecuador, Canada, Lithuania,
Colombia, USL League Two, La Liga 2. Added 2026-06-09: Ireland First Division,
Kazakhstan First Division, Norway 1. Division, K League 2, Finland Ykkönen.

**Source of truth (changed 2026-06-09):** the active set now lives in the DB
column **`leagues.active`**, refreshed from the live Sportmonks `/leagues`
endpoint by **`sync_leagues.py`** (first step of the daily chain). The routes,
`fetch_results.py`, and `reconcile_orphans.py` all READ that column at runtime.
`fetch_upcoming.py` still keeps an `ACTIVE_LEAGUES` dict (id → tier) as the
discovery/fetch list and tier source. **Run `sync_leagues.py` after any plan
change** (or just run the daily chain, which calls it first).

---

## 6. Database

**File:** `C:\OddsFlowV4\data\oddsflow_v4.db` (SQLite). Not in git. Backups: `data/oddsflow_v4.db.bak.*`

Key tables:

| Table | Contents |
|-------|---------|
| fixtures | One row per match. draw_zone + bts_pocket = v4 cell. Odds frozen at settlement. |
| emit_log | One row per pick emitted (3 per fixture = goals_nl, corners_nl, threeway). |
| pick_results | Settlement outcomes. One row per emit_log row after settle.py runs. |
| leagues | League metadata. sportmonks_id is the FK. |
| teams | Team metadata. |
| fixture_stats | Corner stats from Sportmonks. Populated by refresh_stats.py + fetch_results.py. |
| system_health | Cron heartbeat log. Every pipeline script writes a row here. |

**Odds are frozen at settlement** — `refresh_odds.py` only updates fixtures where `home_score IS NULL`. The analysis always uses the odds the fixture settled on in our system.

---

## 7. Key API Endpoints

All endpoints prefixed with `http://localhost:8083`. Full list at `/docs`.

| Endpoint | Description |
|---------|-------------|
| `GET /healthz` | Quick health check |
| `GET /healthz/deep` | DB + env status |
| `GET /picks?days=N` | Active picks for next N days |
| `GET /upcoming?days=N&tier=T` | All classified upcoming fixtures |
| `GET /api/foundation` | Foundation matrix JSON (all/t1t2/t3) |
| `GET /inspector/partition_drift?recent_days=N` | Drift vs historical per promoted cell |
| `GET /inspector/similar?zone=Z&bts=B` | Past fixtures in the same cell |
| `GET /api/results?days=N` | Settled fixtures + live auto-settle |
| `GET /api/livescores` | Sportmonks in-play proxy (auto-settles finished games) |
| `GET /diagnostics/runbook` | Per-task overdue status (powers the Today strip) |
| `GET /diagnostics/today_summary` | The Today tab headline numbers |
| `GET /reports/emit_market_breakdown?days=N` | Per-market hit rates |

---

## 8. Reading the Runbook (Today tab) — every task explained

The Today tab's **Runbook strip** has one badge per pipeline task. **Green = ran
OK within its window. Red = overdue** (no successful "ok" heartbeat inside the
threshold). Each task writes a heartbeat to the `system_health` table when it
runs; the runbook reads the most recent one.

| Badge | Threshold | Runs (SAST) | What it does | If RED, run |
|-------|-----------|-------------|--------------|-------------|
| `fetch_upcoming` | 26h | 08:00 | Pull fixtures + pre-match odds | `python fetch_upcoming.py` |
| `emit_picks` | 26h | 08:05 | Emit picks for next 3 days | `python emit_picks.py --mode emit` |
| `emit_picks_reemit` | 30h | 14:30 | Re-emit after intraday odds refresh | `python emit_picks.py --mode reemit` |
| `refresh_odds` | 26h | 14:30 | Re-fetch odds for next-30h fixtures | `python refresh_odds.py` |
| `refresh_stats` | 36h | 00:00 | Backfill corner stats (14d) | `python refresh_stats.py` |
| `fetch_results` | 18h | 03:00·06:00·23:30 | Pull final scores + stats | `python fetch_results.py` |
| `settle` | 8h | 03:15·06:15·23:45 | Write WIN/LOSS to pick_results | `python settle.py` |
| `reconcile_orphans` | 30h | nightly | Mark dropped-league picks ORPHAN | `python scripts/reconcile_orphans.py` |
| `livescores_poller` | 0.5h | every 5 min | Live in-play scores → auto-settle | (scheduled task `OddsFlow_LivescoresPoller`) |
| `db_maintenance` | 8d | Sun 02:00 | Integrity check + backup | `python scripts/db_maintenance.py` |
| `emit_partition_invalid` | 7d | on each emit | Counts picks rejected by the cell-boundary guard. `ok: rejected=0` is healthy | clears on next emit |
| `sportmonks_webhook` | 6h | (disabled) | Webhook receiver — off by default; ignore unless you enable it | — |

**Reading the heartbeat value:** each badge's text is the last heartbeat, e.g.
`ok: livescores=2 auto_written=0 auto_settled=0` (poller saw 2 in-play games,
no finished ones to settle) or `ok: 13 scores, 13 stats` (fetch_results pulled
13 results). A value starting `error:` is the last failure — informational; the
badge only goes red when no `ok` beat exists inside the threshold window.

---

## 9. Troubleshooting

### A task badge is red
1. Open a terminal in the folder (`cd C:\OddsFlowV4`).
2. Run the task's command from the §8 table.
3. Re-open the Today tab — the badge should go green within ~60s.
If several are red at once, the **scheduler** likely isn't running — check
Task Scheduler (`taskschd.msc`) for the `OddsFlow_*` tasks (Status = Ready,
Last Run Result = 0x0).

### Sportmonks returns HTTP 403 Forbidden
Sportmonks **blocks the default Python user-agent**. Every script that calls the
API must send `headers={"User-Agent": "OddsFlowV4/1.0"}`. If a *new* API call is
added and it 403s, that header is missing. Fixed call sites: `fetch_upcoming`,
`refresh_odds`, `refresh_stats`, `fetch_results`, `sync_leagues`,
`routes_results.py` (livescores), `routes_webhooks.py`, `scripts/fetch_historical.py`.

### Restarting the server (and deploying code changes)
The server runs **elevated** (Task Scheduler `OddsFlow_Server`, `-RunLevel
Highest`), so a normal double-click of `restart_server.bat` can't kill it. To
restart: **right-click `restart_server.bat` → Run as administrator** → approve
the prompt. It kills the old uvicorn and relaunches via `start_server.ps1` with
`--reload`. Once it's running with `--reload`, **edits to `.py` files auto-apply
within ~1s** — no further restart needed. (A full reboot also works: the startup
task relaunches the server on current code.)

### Live scores aren't settling
Check the `livescores_poller` badge on Today. If red with an `HTTP 403` error,
it's the user-agent bug above in `routes_results.py`'s `_sm_get`. If red with
`getaddrinfo failed`, that's a transient DNS/network blip — it self-recovers.

### A `.py` file opens in VS Code instead of running
That's the file association — `.py` opens in the editor when double-clicked. To
*run* something, use the matching `.bat` (e.g. `run_daily.bat`,
`run_syncleagues.bat`) or run `python <script>.py` from a terminal.

### Git "lock file already exists" when committing
A stale `C:\OddsFlowV4\.git\index.lock` from an interrupted git command. Delete
that one file (paste `C:\OddsFlowV4\.git` into File Explorer's address bar →
delete `index.lock`) and retry.

---

## 10. Glossary — terms & abbreviations

| Term | Meaning |
|------|---------|
| **zone** | draw_odd band: strong / standard / low / one_sided (see §4) |
| **bts** | both-teams-to-score direction. `over` = market expects both to score (yes_odd ≤ no_odd); `under` = opposite |
| **cell / partition** | the `(zone, bts)` pair a fixture falls into — the 8 active cells are the engine |
| **PROMOTE** | the fixture's cell is one of the 8 live policy cells (it fires picks) |
| **goals_nl / corners_nl** | "natural line" over markets: O1.5 goals; O7.5 (strong) / O8.5 corners |
| **threeway** | the 1X2 pick, as **alpha-or-draw** — favourite OR draw both count as a WIN |
| **alpha** | the market favourite (lower of home/away odd) |
| **DF** | a draw-favouritism signal (DF0/1/2). Display-only — never a cell axis |
| **H2H corner** | over/under/none from our own prior meetings of the two teams |
| **drift** | recent cell hit rate vs its historical rate. watch = 5–10pp below, drifting = >10pp |
| **ORPHAN** | a pick whose league/fixture was dropped — excluded from hit rate |
| **emit** | the act of writing picks to `emit_log` (what `emit_picks.py` does) |
| **settle** | reading final scores and writing WIN/LOSS to `pick_results` |
| **T1 / T2 / T3** | operator tier of the league (editorial; not from the API) |

---

## 11. Session 24 alignment (2026-06-19) — what changed and why

This session removed the last places where the displayed numbers disagreed with
the live v4 engine. Four backend changes, all deploy on the next **admin reboot**
(the running server is elevated; a non-admin restart can't replace it):

**1. Live, growing baseline (`app/engine/live_baseline.py`).** The Picks tab used
to show frozen baseline hit-rates from `static_policy.V3_MARKETS` (e.g. a fixed
83.8% / n=10,996). It now reads `live_cell_hit()` — the per-cell hit rate computed
from **every settled, classifiable fixture**, recomputed every 30 minutes. The
picture **grows** as new fixtures settle instead of being pinned to the foundation
test. If a cell has fewer than 50 settled fixtures it falls back to the frozen
number so a thin cell never shows a wild rate. The goals-override (the old
hard-coded strong-spread lift) is retired — the live baseline already reflects it.

**2. Corner denominator fix (`app/engine/promotion.py`).** Corners are only
gradeable on fixtures where corner stats exist, but the Analysis matrix was
dividing corner greens by **all** fixtures (like goals), which dragged the corner
rate down to ~49% against a real ~64%. Corners now divide by `cn_n` (fixtures with
corner data) and the matrix reports `n_corners` separately from `n_fixtures`.

**3. Reports are v4-only (`app/api/routes_reports.py`).** Every report query now
filters `em.market IN ('goals_nl','corners_nl','threeway')`, so legacy `dnb` /
`alpha_win` rows from before v4 no longer inflate or distort the counts. Reports
count what the engine actually fires today.

**4. Multi-market drift (`app/api/routes_inspector.py`).** The Inspector drift
table compared **everything** against the threeway rate. It now computes drift
**per cell × market** — goals_nl, corners_nl and threeway each compared against
**their own** baseline (live baseline preferred, frozen fallback). The table gained
a Market column; the Stats-tab drift summary keys on `zone:bts:market`.

Plus the earlier fix recorded in CLAUDE.md: the odds parser was reading the wrong
Sportmonks markets (goals on a thin market with no 1.5 line, corners on odd/even).
Correct markets are **goals = market_id 80**, **corners = market_id 67**;
`scripts/rederive_odds.py` re-derives them from `raw_odds_json`. This only ever
affected *displayed odds* and the cross-signal — hit rates settle on the score and
corner count, so they were never wrong.

**Deploy note.** Frontend changes (engine.js) are live on a browser reload.
Backend changes (the four above) only take effect after the server process is
replaced — reboot from an admin session, or run `restart_server2.bat` elevated.

---

*Last updated 2026-06-19 (Session 24): live growing baseline; corner-denominator
fix; v4-only reports; multi-market drift; odds market-id correction. Added §11 and
the companion TAB_REFERENCE.md. Prior — 2026-06-09 (Session 20): runbook threshold
8h→18h; livescores 403 fix; leagues 29→28 + DB-driven active set; §8–§10 added.*