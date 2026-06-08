# OddsFlow V4 — Engine Knowledge (v4 policy, 2026-05-30)

> Living document. Updated at the end of each session.
> Last updated: 2026-06-08

---

## Engine Architecture

V4 is a football betting analytics engine. Ingests pre-match fixtures and odds from Sportmonks, classifies each fixture into a `(draw_zone × bts_direction)` cell, and emits picks for all 8 cells in the v4 policy. The structured edge is in the `(draw_odd × bts_yes/no)` combination. Hit rate is the only edge metric.

### Process Flow

```
[Sportmonks API]
      |
      | fetch_upcoming.py (daily 08:00 SAST) + refresh_odds.py (intraday 14:30)
      v
[fixtures table]  ←── teams, leagues
      |
      | classify_fixture()
      v
[zone_of(draw_odd)] + [bts_yesno(yes, no)]  ← v4 cell axis
[bts_of(yes, no)]  ← display pocket          [bts_spread]  ← signal
[df_of(home, draw, away)]  ← signal          [h2h_meetings]  ← signal
      |
      v
[V3_ACTIVE lookup] (static_policy.py — 8 cells, 2-key (zone, bts_yesno))
      |
      ├── cell not active → skip (partition_not_promoted)
      ├── draw_odd missing → skip (unclassifiable)
      └── cell active → 3 markets emit
                         |
                         ├ goals_nl  (Over 1.5 Goals)  — all zones
                         ├ corners_nl (Over 7.5 Corners / Over 8.5 Corners)  — all zones
                         └ threeway   (alpha-or-draw)   — all zones
                              |
                         [emit_log table]
                              |
                  pick_uuid = sha256(fixture:market:pick)[:36]
                  write_emit_log() supersedes stale unsettled rows
```

### Key Files

| File | Role |
|------|------|
| `fetch_upcoming.py` | Daily fetch — fixtures + 1X2/BTTS/goals_over_*/corners_over_* odds |
| `emit_picks.py` | Calls `/picks?days=3` + writes `emit_picks` heartbeat |
| `refresh_odds.py` | Intraday odds refresh for next-8h fixtures (M2) |
| `refresh_stats.py` | Adaptive corner-stats backfill (14d base, 60d cap — M3) |
| `fetch_results.py` | Scores + `fixture_stats` after match windows |
| `settle.py` | Writes `pick_results` |
| `reconcile_orphans.py` | Synthetic ORPHAN for stale/dropped-league picks |
| `app/engine/classify.py` | `zone_of()` + `bts_yesno()` (cell axis) + `bts_of()` (display) + `bts_spread()` + `df_of()` |
| `app/engine/static_policy.py` | `V3_ACTIVE` / `V3_MARKETS` / `PROMOTED_CELLS` — v4 8-cell policy |
| `app/engine/promotion.py` | `compute_foundation()` — display only |
| `app/api/routes_picks.py` | `/picks` — v4 lookup + emit_log + drift + signals |
| `app/api/routes_diagnostics.py` | today_summary + multi-metric cron heartbeat + chain verification |
| `data/oddsflow_v4.db` | Live SQLite DB (not in git) |

### Database Tables

| Table | Purpose |
|-------|---------|
| `fixtures` | Fixture + odds + scores + `draw_zone` (raw-notes overlay) + `bts_pocket` (display). `df_level` signal metadata. |
| `teams` | Team registry |
| `leagues` | League registry + tier |
| `emit_log` | Pick emission log. `zone` + `bts_pocket` stored at emit time. `df_level` signal metadata. |
| `pick_results` | Settled outcomes |
| `system_health` | Heartbeats: `fetch_upcoming`, `fetch_results`, `settle`, `emit_picks`, `refresh_odds`, `refresh_stats`, `zone_migration`, legacy `cron_heartbeat` |
| `fixture_stats` | Corners + stats. `raw_stats_json` full capture. |
| `h2h_meetings` | ~58k rows; H2H corner-count signal on upcoming fixtures |

---

## Classification (two axes — v4)

### Draw Zone (`zone_of(draw_odd)`) — raw-notes overlay (Session 19)

| Zone | Draw odd range |
|------|----------------|
| (excluded) | `< 2.90` |
| `strong` | `2.90 ≤ x < 3.30` |
| `standard` | `3.30 ≤ x < 3.80` |
| `low` | `3.80 ≤ x < 4.30` |
| `one_sided` | `≥ 4.30` |

### BTS Direction — v4 cell axis (`bts_yesno(yes, no)`)

| Direction | Condition |
|-----------|-----------|
| `over` | `yes_odd ≤ no_odd` (BTTS Yes favoured) |
| `under` | `no_odd < yes_odd` (BTTS No favoured) |

### BTS Pocket — display (`bts_of(yes, no)`, threshold 1.50)

| Pocket | Condition |
|--------|-----------|
| `strong_over` | Yes favoured AND `yes_odd < 1.50` |
| `slight_over` | Yes favoured AND `yes_odd ≥ 1.50` |
| `strong_under` | No favoured AND `no_odd < 1.50` |
| `slight_under` | No favoured AND `no_odd ≥ 1.50` |

### Partition Key
`zone:bts_direction` — e.g. `standard:over`.

---

## v4 Active Cells (8)

Source: `app/engine/static_policy.py::V3_ACTIVE`. All 8 cells have n ≥ 802 from test dataset.

**Composite hit rates (from 28,571-fixture test, 2026-05-30):**

| Cell | Composite | n |
|------|-----------|---|
| `strong:over` | 70.3% | ≥802 |
| `strong:under` | 69.5% | ≥802 |
| `standard:over` | 71.3% | ≥802 |
| `standard:under` | 69.9% | ≥802 |
| `low:over` | 75.6% | ≥802 |
| `low:under` | 71.8% | ≥802 |
| `one_sided:over` | 80.4% | ≥802 |
| `one_sided:under` | 80.6% | ≥802 |

**Baselines are from the test dataset.** Live settlement started 2026-05-30. Recalibrate at 6 weeks.

---

## Markets (3 per cell, every cell)

| Market | When fired | Pick label | Pick odd source |
|--------|------------|-----------|-----------------|
| `goals_nl` | All cells | `"Over 1.5 Goals"` | `fixtures.goals_over_15_odd` (often NULL) |
| `corners_nl` | All cells | `"Over 7.5 Corners"` (strong) / `"Over 8.5 Corners"` (rest) | `fixtures.corners_over_75_odd` / `corners_over_85_odd` (almost always NULL) |
| `threeway` | All cells | Alpha team name or draw | `min(home_odd, away_odd)` |

**Why `pick_odd` is often NULL on goals_nl / corners_nl:**
Sportmonks rarely quotes Over 1.5 / Over 7.5 / Over 8.5. Natural-line only — no fallback. SPA renders `—`. EV / breakeven layer is not in the live engine (Durable Rule).

---

## Signals (NOT gates, NOT cell axes)

| Signal | Source | Effect |
|--------|--------|--------|
| **BTS spread** | `bts_spread()` | Display chip. Goals-override in `standard:over` + `low:over` when spread==`strong`: goals_nl carries strong-spread rate (83.8% / 85.0%) instead of blended cell rate. |
| **DF** | `df_of()` | Display chip only. Dead in 5/8 cells. |
| **H2H-corner** | `h2h_meetings` table | Display chip. `over` / `under` / `none` derived local-first from our own prior meetings. |

---

## Pick Settlement

| Outcome | `actual_value` | Markets |
|---------|---------------|---------|
| WIN | 1.0 | goals_nl, corners_nl, threeway (alpha wins OR draw) |
| LOSS | 0.0 | goals_nl, corners_nl, threeway (alpha loses) |
| VOID | 0.5 | legacy dnb rows only |

**v4 hit-rate convention:** binary — `wins / settled`. Draw = WIN for threeway. No void at ground zero.
Legacy dnb rows: `(wins + voids) / settled`.

`pick_results.outcome` is the **string** label; `actual_value` is the **float**. Never numeric compare against `outcome` in SQLite.

---

## Drift

| Flag | Condition |
|------|-----------|
| `stable` | gap > −5pp |
| `watch` | −10pp < gap ≤ −5pp |
| `drifting` | gap ≤ −10pp |
| `no_data` | recent_n < 10 |

Drift is informational. Engine never auto-suppresses — operator reviews.

---

## SPA Tabs — What Each Shows

### Tab 1: Picks
`GET /picks?days={n}` (default 7d). Per pick: fixture, kickoff, partition key (`zone:bts`), market row(s), pick label, pick_odd (or `—`), drift chip, signal chips. Summary bar: count, fixtures, by market, skip reasons. CSV → `paper_trading.csv`.

### Tab 2: Upcoming
`GET /upcoming?days={n}&tier={t}` (default 7d). Every classified fixture with v4 cell chip.

### Tab 3: Analysis
`GET /api/foundation`. Foundation matrix — `compute_foundation()` output. ALL / T1+T2 / T3 sub-tabs.

### Tab 4: Inspector
- `GET /inspector/partition_drift` — drift table per active cell
- `GET /inspector/recent_settled` — recent settled picks
- `GET /inspector/similar?fixture_id=…` — cell history (pre-match lens)
- `GET /inspector/daily_calendar` — WIN/VOID/LOSS calendar

### Tab 5: Reports
- `/reports/emit_performance` — multi-window hit rates
- `/reports/emit_recent` — per-fixture readback
- `/reports/emit_market_breakdown` — per (zone, bts, market, pick) hit rates
- `/reports/settle_activity` — daily settlement + last pipeline heartbeat

### Tab 6: Today
`GET /diagnostics/today_summary`. Chain verification (checks fetch_upcoming + emit_picks ran today). Cron chip uses any of the 7 pipeline metrics.

### Tab 7: Stats
`/diagnostics/db_state` + `/odds_coverage` + `/cron/heartbeat` + `/drift_report` + `/activity_by_tier`.

### Tab 8: Results
`GET /api/results?days={n}` + `GET /api/livescores` — DB history + Sportmonks live overlay (server-side proxy, ACTIVE_LEAGUES filter, 60s polling).

---

## League Tiers

| Tier | Description | Examples |
|------|-------------|----------|
| T1 | Top-flight | PL, Ligue 1, La Liga, Serie A, Allsvenskan, Eliteserien, Besta deild, Veikkausliiga, Ireland PD, MLS, Brazil A, J1, K League 1 |
| T2 | Second-tier / strong regional | La Liga 2, Superettan, Ettan N/S, Copa Colombia, Primera B, Liga Pro Ecuador, Canada PL, Ykköseliga, Meistriliiga, Esiliiga A, USL Championship, J2/J3, China Super |
| T3 | Development / lower | USL League One, MLS Next Pro, Bolivia Liga |

29 active leagues in ACTIVE_LEAGUES; 62 in DB (incl. historical).
Foundation matrix tier split: **T1+T2 vs T3** (not T1 vs T2+T3).

---

## Abbreviations Reference

| Abbrev | Full form |
|--------|-----------|
| BTTS / BTS | Both Teams To Score |
| NL / SL | Natural line / System line |
| pp | Percentage points |
| SM | Sportmonks |
| T1 / T2 / T3 | League tier |
| FK | Foreign key |
| emit | Engine generating + logging a pick |
| leg | A single market pick within a fixture emission |
| event | A (fixture, market) pair — collapses multi-leg picks |
| 1X2 | Home Win / Draw / Away Win |
| alpha team | Favoured side (lower odd) |
| PROMOTE | Cell in V3_ACTIVE that emits picks |
| MEASURING | Foundation matrix tag for low-zone cells (display only) |
| cron | Scheduler — 12 Task Scheduler jobs |
| partition | A (zone, bts) cell |
| paper trading | CSV export for manual bookmaker tracking |
| DF | Difference Factor — analysis-only signal, NOT a partition key |
| both_sided | draw_odd < 2.90 — excluded from v4 policy |
| ORPHAN | Synthetic outcome for picks that cannot settle naturally |

---

## How to Operate

### Daily — run scheduler or chained script

```powershell
Set-Location C:\OddsFlowV4
.\run_daily.ps1
```

Or each step individually:
```powershell
python fetch_upcoming.py
python emit_picks.py
python fetch_results.py
python settle.py
```

### Server
Task Scheduler (`OddsFlow_Server`). Manual:
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8083 --reload
```

### Ngrok
Task Scheduler (`OddsFlow_Ngrok`). Manual:
```powershell
ngrok http 8083
```

### Access
- Local SPA: http://localhost:8083
- Public: https://steadier-legwarmer-finlike.ngrok-free.dev
- Health: /health and /healthz/deep
- API docs: /docs
