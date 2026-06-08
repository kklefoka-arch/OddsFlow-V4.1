# OddsFlow V4 — Operator Manual

**Operator:** Katlego (KK) | **Port:** 8083 | **Updated:** 2026-06-08

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
- **Runbook strip** — per-task overdue status for all 8 scheduled tasks

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
# Runs: fetch_upcoming → emit_picks → fetch_results → settle
```

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

## 5. Leagues (29 active)

Full list in `context/02_league_config.md`. Summary:

- **T1** (16 leagues) — top flight of each country: Allsvenskan, Eliteserien, MLS, Brazil Serie A, J1, K League 1, etc.
- **T2** (6 leagues) — Superettan, USL Championship, Colombia Primera B, Ykköseliga, Esiliiga A, J2/J3
- **T3** (7 leagues) — Reserve leagues, cups, lower tiers

Big 5 EU (PL, Ligue 1, La Liga, Serie A, La Liga 2) are **not** in the subscription. USL League Two (797) removed 2026-05-29.

Source of truth: `ACTIVE_LEAGUES` dict in `fetch_upcoming.py`.

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
| `GET /inspector/similar?zone=Z&bts=B` | Historical fixtures in same cell |
| `GET /reports/emit_performance?tier=T` | Multi-window engine performance |
| `GET /reports/emit_market_breakdown?days=N&tier=T` | Per-cell, per-market hit rates |
| `GET /reports/emit_recent?days=N&tier=T` | Recent fixtures with settled picks |
| `GET /reports/settle_activity?days=N` | Settlements per day |
| `GET /reports/paper_trading.csv?days=N` | CSV export of picks |
| `GET /api/results?days=N` | Settled fixtures from DB |
| `GET /diagnostics/today_summary` | System summary for Today tab |
| `GET /diagnostics/runbook` | Per-task overdue status |
| `GET /diagnostics/db_state` | Table counts |
| `GET /diagnostics/odds_coverage` | Odds coverage per league |
| `GET /api/livescores` | In-play fixtures (Sportmonks live) |

---

## 8. Troubleshooting

### "Board shows no picks" / "Upcoming shows zone=—"
Fixtures are missing odds (draw_odd is NULL). Cause: fetch_upcoming.py hasn't run since the fixtures were added, or Sportmonks had no odds for those matches. Fix: run `python fetch_upcoming.py` manually.

### "Reports show pending (played) picks"
Corner stats are missing — settle.py needs fixture_stats to settle corners_nl. Fix: run `python refresh_stats.py` then `python settle.py`.

### "Runbook shows 8 overdue"
Normal after a gap in scheduler operation. The runbook uses per-task thresholds; green = task has run within its threshold. After the chain runs, overdue count drops.

### "Server is down"
```powershell
cd C:\OddsFlowV4
uvicorn app.main:app --host 0.0.0.0 --port 8083 --reload
```
Or use Task Scheduler → OddsFlow_Server → Run.

### "503 on /api/webhooks/sportmonks"
Expected. The Sportmonks Push webhook receiver is scaffolding — it is disabled by default.
It returns 503 until `SPORTMONKS_WEBHOOK_SECRET` is set in `.env`.
The polling pipeline (fetch_results at 23:30 / 03:00 / 06:00 SAST) is the primary settlement path — no action needed.

### "DB is locked / malformed"
The DB is never malformed — the "malformed" error from tools is a write-lock from the running server. Connect via the API (`/docs`) or stop the server first for direct SQLite access.

### "pick_odd shows —"
Expected for corners_nl and goals_nl (natural-line odds aren't always stored separately). The pick is still emitted correctly; the `—` is the UI rendering `null` pick_odd. Odds may populate after `refresh_odds.py` runs at 14:30.

---

## 9. Six-Week Settlement Watch (from 2026-05-30)

The v4 policy (8-cell, 2-key) is under a 6-week live validation. Until 2026-07-11:

- Monitor hit rates in Reports → Multi-window performance and Per-cell market hit rates
- Target: all 8 cells tracking ≥ their historical composite rate (within noise)
- If a cell shows persistent drift (>10pp below baseline for 30+ picks), raise for operator review
- After 6 weeks, decide: recalibrate baselines, re-evaluate DF as a partition refinement, or proceed as-is

---

## 10. End-of-Session Checklist

1. Update `context/04_current_status.md` with what changed
2. Update `CLAUDE.md` if any durable decisions were made
3. `git add -A && git commit -m "session N: <summary>" && git push`

---

*OddsFlow V4 — ground-zero engine. The edge is in the partition. Trust the hit rate.*
