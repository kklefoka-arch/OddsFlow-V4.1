# OddsFlow V4 — System Language (v4 policy, 2026-05-30)

Every term this system uses, defined exactly. When something is requested, reported, or questioned — this is the reference for what it means, where it lives, and what it connects to.

---

## Core Concepts

### Fixture
A single football match. Lives in `fixtures`. Upcoming if `home_score IS NULL`, settled otherwise. Classifiable if `draw_odd`, `btts_yes_odd`, `btts_no_odd` are all present.

### Odds (engine inputs)

| Field | Market |
|-------|--------|
| `home_odd` / `draw_odd` / `away_odd` | 1X2 (Sportmonks market 1) |
| `btts_yes_odd` / `btts_no_odd` | BTTS (Sportmonks market 14) |
| `goals_over_15_odd` / `goals_over_25_odd` / `goals_over_35_odd` | Goal Line (market 7) |
| `corners_over_75_odd` / `corners_over_85_odd` / `corners_over_95_odd` | Corners totals |

Over 1.5 goals and Over 7.5/8.5 corners are often NULL — Sportmonks rarely quotes trivial overs. Expected; no fallback by design.

### Alpha Team
Lower 1X2 odd. `home_odd ≤ away_odd` → alpha is home.

### Draw Zone
Fixture classification from `draw_odd`. Raw-notes overlay (Session 19): excluded < 2.90, strong 2.90–3.30, standard 3.30–3.80, low 3.80–4.30, one_sided ≥ 4.30.

### BTS Direction (cell axis)
Binary classification from BTTS odds. `over` = `yes_odd ≤ no_odd`; `under` = otherwise.
Source: `bts_yesno()` in `app/engine/classify.py`.

### BTS Pocket (display)
4-pocket classification from BTTS odds (threshold 1.50). Stored in `bts_pocket` column.
Source: `bts_of()` in `app/engine/classify.py`.

| Pocket | Condition |
|--------|-----------|
| `strong_over` | Yes favoured AND `yes_odd < 1.50` |
| `slight_over` | Yes favoured AND `yes_odd ≥ 1.50` |
| `slight_under` | No favoured AND `no_odd ≥ 1.50` |
| `strong_under` | No favoured AND `no_odd < 1.50` |

### BTS Spread (signal)
`strong` or `slight` — derived from the 4-pocket value. Source: `bts_spread()`. Used as a qualifying signal (display chip + one goals-override), NOT a cell axis.

### DF Level (signal)
Difference Factor. DF0 / DF1 / DF2 from `df_of(home_odd, draw_odd, away_odd)`. Display chip only. Dead in 5/8 cells. NOT a partition key.

### Cell
A `(zone, bts_direction)` pair where `bts_direction ∈ {over, under}`. 4 zones × 2 directions = **8 cells, all active in v4**. Partition key string: `zone:bts` (e.g. `standard:over`).

### Tier
League quality tier (1, 2, 3). Drives T1+T2 vs T3 Analysis-tab splits.

---

## v4 Policy Terms

### V3_ACTIVE
Authoritative pick policy (v4, 2026-05-30). Dict keyed `(zone, bts_yesno)` → per-market config. 8 cells. Imported by `routes_picks.py`. **This fires picks.** Source: `app/engine/static_policy.py`.

### V3_MARKETS
Full per-cell market definition: `line`, `hit` (historical reference baseline from test), `n`. `V3_ACTIVE` is derived from `V3_MARKETS`.

### PROMOTED_CELLS
Compatibility dict consumed by `routes_inspector.py` and `routes_reports.py`. Same 8 keys as `V3_ACTIVE` plus metadata (`threeway_hit`, `promote_status`).

### LOW_ZONE_SUPPRESS
Boolean flag. `False` in `static_policy.py` (low zone fires picks). `True` in `promotion.py` (foundation matrix display labels low cells `MEASURING`). Intentional split.

### Promote Status
String tag on a cell: `PASS`, `MARGINAL`, `FLAG`. Set at calibration time; surfaces in dashboards but does not gate picks.

### Compute Foundation
`compute_foundation(load_foundation(conn))` — live foundation matrix from all settled fixtures. **Display only** (Analysis tab). Independent of `V3_ACTIVE`.

---

## Pick Terms

### Pick
A market-specific recommendation for an upcoming fixture in a v4-active cell.

| Market | Label | Pick odd source |
|--------|-------|-----------------|
| `goals_nl` | `"Over 1.5 Goals"` | `fixtures.goals_over_15_odd` (often NULL by design) |
| `corners_nl` | `"Over 7.5 Corners"` (strong) / `"Over 8.5 Corners"` (rest) | `fixtures.corners_over_75_odd` / `corners_over_85_odd` (almost always NULL) |
| `threeway` | Alpha team name or draw | `min(home_odd, away_odd)` |

### Emit
The act of writing a pick to `emit_log`. Idempotent via `pick_uuid = sha256("{fixture_id}:{market}:{pick}")[:36]`.

### `write_emit_log()`
Supersede + insert helper. Before inserting, deletes stale unsettled pick on the same `(fixture_id, market)` with a different `pick_uuid` (handles alpha team changes).

### `pick_odd` NULL
Expected on most goals_nl and all corners_nl rows. SPA renders `—`. EV/breakeven are *out of scope* for the live engine (Durable Rule 2).

---

## Settlement Terms

### Settle
Resolve a pick into WIN / LOSS (or VOID for legacy dnb rows).
- Persistent: `settle.py` writes `pick_results`.
- On-the-fly: `routes_reports.py` / `routes_diagnostics.py` run `settle_pick()` in memory from emit_log + fixtures + fixture_stats.

### `pick_results`

| Field | Type | Notes |
|-------|------|-------|
| `pick_uuid` | TEXT | FK to emit_log |
| `settled_at` | TEXT | ISO |
| `outcome` | TEXT | `WIN` / `LOSS` / `VOID` (VOID only on legacy dnb) — use this for filters |
| `actual_value` | REAL | `1.0` / `0.0` / `0.5` — use this for arithmetic |

String-vs-number comparisons in SQLite return garbage — never use `outcome >= 1`.

### Outcome rules

| Market | WIN | VOID | LOSS |
|--------|-----|------|------|
| goals_nl | `total_goals > 1.5` | — | else |
| corners_nl | `total_corners > line` | — (skipped if NULL) | else |
| threeway | alpha wins OR draw | — | alpha loses |
| dnb (legacy) | alpha wins | draw | alpha loses |

---

## Drift Terms

### Drift
`gap_pp = recent_hit − baseline_hit`. Baseline = `V3_MARKETS[(zone,bts)][market]["hit"]`. Recent = rolling-window binary hit rate from settled emit_log rows.

| Flag | Condition |
|------|-----------|
| `stable` | gap > −5pp |
| `watch` | −10pp < gap ≤ −5pp |
| `drifting` | gap ≤ −10pp |
| `no_data` | recent_n < 10 |

---

## Reporting Terms

| Route | Purpose |
|-------|---------|
| `/reports/emit_performance` | Multi-window hit-rate summary (legs + events) — on-the-fly |
| `/reports/emit_recent` | Per-fixture readback with WIN/LOSS/PENDING |
| `/reports/emit_market_breakdown` | Per (zone, bts, market, pick) hit rates |
| `/reports/settle_activity` | Per-day settle counts + last pipeline heartbeat |
| `/inspector/partition_drift` | Per-cell drift across active v4 cells |
| `/inspector/recent_settled` | Fixtures with settled picks, grouped |
| `/inspector/similar` | Recent fixtures in the same (zone, bts) cell — pre-match lens |
| `/inspector/daily_calendar` | Per-day WIN/VOID/LOSS calendar |

---

## Process Terms

| Term | Where |
|------|-------|
| Fetch | `fetch_upcoming.py` daily 08:00 SAST |
| Intraday odds refresh | `refresh_odds.py` 14:30 SAST — 8h horizon |
| Score update | `fetch_results.py` 23:30 / 03:00 / 06:00 SAST |
| Corner backfill | `refresh_stats.py` 00:00 SAST — 14d adaptive lookback |
| Settlement run | `settle.py` 23:45 / 03:15 / 06:15 SAST |
| Emit pass | `emit_picks.py` 08:05 SAST — calls `/picks?days=3` |
| Orphan reconcile | `reconcile_orphans.py` nightly — marks dropped/stale picks ORPHAN |
| Recalibrate | Implicit — every `/api/foundation` re-reads settled fixtures |

---

## Tables

| Table | Purpose |
|-------|---------|
| `leagues` | League reference |
| `teams` | Team reference |
| `fixtures` | Fixture + odds + scores + `draw_zone` (raw-notes overlay) + `bts_pocket` (4-pocket display). `df_level` retained as signal metadata. `odds_updated_at` stamps freshness. |
| `fixture_stats` | Corner stats for settled fixtures. `raw_stats_json` full capture. |
| `emit_log` | Pick emission record. `zone` + `bts_pocket` stored at emit time. `df_level` stored as signal metadata. |
| `pick_results` | Settled pick outcomes |
| `system_health` | Heartbeats (`fetch_upcoming`, `fetch_results`, `settle`, `emit_picks`, `refresh_odds`, `refresh_stats`, `zone_migration`, legacy `cron_heartbeat`) |
| `h2h_meetings` | Head-to-head history (H2H corner counts signal — live on upcoming fixtures) |

---

## What Does Not Exist (by Durable Rule)

| Missing | Why |
|---------|-----|
| `bts_yesno` as a stored DB column name | Not needed — `bts_pocket` is stored; `bts_yesno` is derived at query time for cell lookup. |
| DF as partition key | Signal only (Durable Rule 1). Returns only after 6 weeks of v4 settlement. |
| BTS spread as partition key | Signal only. Cell axis is binary over/under. |
| EV / breakeven / Wilson in the live engine | Analysis-only. Durable Rule 2. |
| Hard suppression gates | Signals display; never block emission. |
| Effective-line fallback for goals_nl / corners_nl | Natural line only — `pick_odd` NULL is expected. |
| Goals/corners system-line picks | Foundation metrics only; not pick markets. |
| Team form / position / predicted-uncertainty weighting | Odds drivers (zone × bts) + H2H corner counts only. Anything else is research. |
| External cron daemon | Task Scheduler runs the 12 daily jobs. |
| Live in-play pick generation | Pre-match odds only. |
| Real-money execution | Engine recommends; KK places bets manually. |
