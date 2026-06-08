# OddsFlow V4 — Fixture Lifecycle Process Flow (v4 policy, 2026-05-30)

Every phase a fixture moves through.

---

## Overview

```
[Sportmonks API]
       |
  Phase 1: FETCH (fetch_upcoming.py — daily)
       |
  Phase 2: LAND (fixtures table + draw_zone/bts_pocket write)
       |
  Phase 3: CLASSIFY (zone × bts_yesno + signals on-the-fly)  <──┐
       |                                                          │
  Phase 4: CALIBRATE (compute_foundation — display only)         │
       |                                                          │
  Phase 5: EMIT (V3_ACTIVE lookup → emit_log)                    │
       |                                                          │
  Phase 6: DISPLAY (Picks tab)                                    │
       |                                                          │
  Phase 7: OBSERVE (Upcoming + Inspector pre-match lens)          │
       |                                                          │
  [Match plays — external event]                                  │
       |                                                          │
  Phase 8: SCORE UPDATE (fetch_results.py — 3 daily passes)      │
       |                                                          │
  Phase 9: SETTLE (settle.py → pick_results)                     │
       |                                                          │
  Phase 10: REPORT (Reports + Inspector tabs)                     │
       |                                                          │
  Phase 11: RECALIBRATE (foundation re-reads settled) ───────────┘
       |
  Phase 12: VALIDATE (drift — recent vs baseline per cell)
       |
  [Fixture is historical data — feeds Phase 4 forever]
```

---

## Phase 1: FETCH

`fetch_upcoming.py`. Task Scheduler 08:00 SAST + intraday `refresh_odds.py` 14:30 SAST.
API: `GET /v3/football/fixtures/between/{start}/{end}?include=participants;odds`.
League filter: `ACTIVE_LEAGUES` (29 leagues).
Monthly windows; max_pages=30 (Jul–Oct), =20 elsewhere.

**Odds extracted:**

| Field | Sportmonks market_id | Notes |
|-------|---------------------|-------|
| `home_odd` / `draw_odd` / `away_odd` | 1 (1X2) | Always available for T1 |
| `btts_yes_odd` / `btts_no_odd` | 14 | Drives bts_yesno (cell axis) + bts_pocket (display) |
| `goals_over_15_odd` / `goals_over_25_odd` / `goals_over_35_odd` | 7 (Goal Line) | O1.5 rarely quoted — many NULLs expected |
| `corners_over_75_odd` / `corners_over_85_odd` / `corners_over_95_odd` | Corners totals | O7.5/O8.5 rarely quoted — almost always NULL |

**Full payload preserved:** `raw_odds_json` on fixtures stores the complete Sportmonks odds response.
**Kickoff datetime:** Stored as `"YYYY-MM-DD HH:MM:SS"` UTC.

---

## Phase 2: LAND

`fixtures` table. Idempotent — UPDATE on `sportmonks_id` match, INSERT otherwise.
`refresh_odds.py` only updates odds for fixtures where `home_score IS NULL` (odds frozen at settlement).
`fetch_upcoming.py` skips past-dated fixtures.
`odds_updated_at` stamps freshness.

---

## Phase 3: CLASSIFY

`classify_fixture(row)` → `{zone, bts_yesno, bts_pocket, bts_spread, df_level, tier}`.

- `zone_of(draw_odd)` → strong | standard | low | one_sided | None
- `bts_yesno(yes_odd, no_odd)` → over | under  ← **v4 cell axis**
- `bts_of(yes_odd, no_odd)` → strong_over | slight_over | slight_under | strong_under  ← display pocket
- `bts_spread(yes_odd, no_odd)` → strong | slight  ← qualifying signal
- `df_of(home_odd, draw_odd, away_odd)` → DF0 | DF1 | DF2  ← qualifying signal

Cell key: `(zone, bts_yesno)` — e.g. `("standard", "over")`.
Partition key string: `"standard:over"`.

---

## Phase 4: CALIBRATE (display only)

`compute_foundation(load_foundation(conn))` in `app/engine/promotion.py` on every `/api/foundation` call. Reads all settled fixtures with full odds; joins `fixture_stats` for corners. Per cell: `goals_hit`, `corners_hit`, `threeway_hit`. `LOW_ZONE_SUPPRESS = True` here — low cells display `MEASURING`. Pick firing does NOT use this matrix; that's `V3_ACTIVE`.

---

## Phase 5: EMIT

`GET /picks?days=N` — `app/api/routes_picks.py`.

Per upcoming fixture in window:
1. Classify → (zone, bts_yesno). Signals: spread, DF, H2H-corner (from h2h_meetings).
2. Look up `V3_ACTIVE[(zone, bts_yesno)]`. Skip if absent (counted as `partition_not_promoted`).
3. For each of 3 markets:
   - **goals_nl** → label `"Over 1.5 Goals"`, `pick_odd = fixtures.goals_over_15_odd` (often NULL by design).
   - **corners_nl** → label `"Over 7.5 Corners"` (strong) or `"Over 8.5 Corners"` (rest), `pick_odd` from corresponding corners_over_*_odd (almost always NULL by design).
   - **threeway** → alpha-or-draw; `pick_odd = min(home_odd, away_odd)` for the straight-win component.
4. Apply BTS spread goals-override (standard:over + low:over when spread==strong: goals carries strong-spread rate 83.8% / 85.0%).
5. Compute drift via `_compute_cell_drift()`.
6. Write to `emit_log` through `write_emit_log()` — supersedes stale unsettled pick on (fixture_id, market) with different `pick_uuid`, then `INSERT OR IGNORE` (pick_uuid = sha256("{fixture_id}:{market}:{pick}")[:36]).

Scheduler: `emit_picks.py` calls `/picks?days=3` daily at 08:05 SAST. SPA Picks tab loads also drive emits.

---

## Phase 6: DISPLAY

SPA Picks tab. `/picks?days=N` → cards with fixture, league, kickoff, partition key (`zone:bts`), market row(s), pick label, pick_odd (or `—` via `fmt.odd`), drift chip, signal chips (BTS spread, DF, H2H-corner).

---

## Phase 7: OBSERVE (pre-match)

- **Upcoming tab:** `GET /upcoming?days=7&tier=T` — every upcoming fixture with classification. v4 cell chip when (zone, bts) is promoted.
- **Inspector tab:**
  - `GET /inspector/partition_drift` — drift per v4 cell.
  - `GET /inspector/similar?fixture_id=…` — recent fixtures in same (zone, bts) cell.
  - `GET /inspector/recent_settled` and `/daily_calendar` — settled performance views.

---

## Phase 8: SCORE UPDATE

`fetch_results.py`. Triggers: 23:30 SAST (Europe), 03:00 SAST (SA), 06:00 SAST (Dawn SA catch-up — M3).
Fetches `?include=scores;statistics;participants`. Writes:
- `fixtures.home_score`, `away_score`, `total_goals`, `status='settled'`
- `fixture_stats.home_corners`, `away_corners`, `total_corners` (parsed from `type_id=34`)

`refresh_stats.py` at 00:00 SAST does adaptive-window corner-stats backfill (14d base, 60d cap).

---

## Phase 9: SETTLE

`settle.py`. Triggers: 23:45 / 03:15 / 06:15 SAST.
Reads pending emit_log rows (no `pick_results` entry, fixture has `home_score`). LEFT JOINs `fixture_stats` for corners_nl.

| Market | Rule |
|--------|------|
| `goals_nl` | `total_goals > line` (line parsed via regex `"Over (\d+\.5) Goals"`) → WIN, else LOSS |
| `corners_nl` | `total_corners > line` (regex `"Over (\d+\.5) Corners"`) → WIN, else LOSS; skipped if NULL |
| `threeway` | alpha wins OR draw → **WIN**; alpha loses → LOSS (draw is WIN — no void) |
| `dnb` (legacy rows) | alpha wins → WIN; draw → VOID; else LOSS |

Writes `pick_results(pick_uuid, settled_at, outcome, actual_value)` and `settle` heartbeat.

`reconcile_orphans.py` (run nightly before settle): marks picks from dropped leagues or >48h stale as ORPHAN.

---

## Phase 10: REPORT

| Route | Reads | Notes |
|-------|-------|-------|
| `/reports/emit_performance` | emit_log + fixtures | On-the-fly settle. 1d/3d/7d/30d/90d/180d windows |
| `/reports/emit_recent` | emit_log + fixtures | Per-fixture readback |
| `/reports/emit_market_breakdown` | emit_log (zone+bts from stored columns) | Per (zone, bts, market, pick) hit rates |
| `/reports/settle_activity` | pick_results + system_health | Per-day counts; last_clean_run from any pipeline metric |
| `/inspector/recent_settled` | pick_results JOIN emit_log JOIN fixtures | Settled picks grouped; 2-key partition_key built from stored zone+bts |
| `/inspector/daily_calendar` | pick_results | Per-day WIN/VOID/LOSS calendar |

---

## Phase 11: RECALIBRATE

`load_foundation(conn)` re-queries `WHERE home_score IS NOT NULL` on every `/api/foundation` call. New scored fixtures enter the matrix automatically. Pick firing is unaffected (V3_ACTIVE is static).

---

## Phase 12: VALIDATE

`_compute_cell_drift()` in `routes_picks.py` + `compute_drift_rows()` in `routes_inspector.py`.
Gap = `recent_hit − baseline_hit` (pp). Flags: `stable` / `watch` / `drifting` / `no_data`.
Hit-rate convention: **v4 binary** — wins / settled.

---

## Connection map

```
fetch_upcoming.py  → fixtures (incl. draw_zone, bts_pocket) + teams + leagues map
refresh_odds.py    → fixtures (odds-only update, home_score IS NULL only)
fetch_results.py   → fixtures (scores) + fixture_stats (corners)
refresh_stats.py   → fixture_stats (late corner backfill)
reconcile_orphans.py → emit_log + pick_results (ORPHAN synthetic outcome)

routes_picks.py
  ← V3_ACTIVE (static_policy.py)  — 8 cells, 2-key (zone, bts_yesno)
  ← fixtures (upcoming in window)
  ← h2h_meetings (H2H corner-count signal)
  → classify_fixture()  (zone × bts_yesno + signals)
  → _compute_cell_drift()
  → write_emit_log()  → emit_log

settle.py
  ← emit_log (pending)
  ← fixtures + fixture_stats
  → pick_results
  → system_health (heartbeat)

routes_inspector.py / routes_reports.py / routes_diagnostics.py
  ← emit_log + pick_results + fixtures + fixture_stats + system_health
```

---

## What does not exist (by Durable Rule)

| Item | Why |
|------|-----|
| DF as partition key | Signal only (Durable Rule 1). May return only after 6-week validation. |
| BTS spread as partition key | Signal only. Cell axis is binary bts_yesno. |
| EV / breakeven gates | Engine measures hit rate only (Durable Rule 2). |
| Hard suppression gates | Signals display; never block emission. |
| Effective-line fallback for goals_nl / corners_nl | Natural line only. |
| External cron daemon | Task Scheduler runs the 12 jobs. |
| Real-money execution | Engine recommends; KK places bets manually. |
| Live in-play pick generation | Pre-match odds only. |
