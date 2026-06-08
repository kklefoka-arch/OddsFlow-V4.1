# Engine Rules — How Fixtures Are Classified and Picks Are Made (v4, 2026-05-30)

The structured edge lives in `(draw_zone × bts_direction)` — the combination of
the bookmaker's draw price and the BTS market direction. Hit rate is the only edge
metric. No EV. No DF as a partition key. No hard suppression gates.

---

## Step 1 — Draw Zone Classification

Every fixture gets a **draw zone** based on the bookmaker's draw odd.
Source: `zone_of()` in `app/engine/classify.py`.

**Boundaries (raw-notes overlay, Session 19 — 2026-05-28):**

| Zone | Draw odd range | Notes |
|------|----------------|-------|
| (excluded) | `< 2.90` | both_sided — too draw-heavy, not in policy |
| `strong` | `2.90 ≤ x < 3.30` | Both teams evenly matched, draw very likely |
| `standard` | `3.30 ≤ x < 3.80` | Slightly favoured side, draw still plausible — the cleanest cell |
| `low` | `3.80 ≤ x < 4.30` | Clear favourite exists, draw less likely |
| `one_sided` | `≥ 4.30` | Strong favourite, draw very unlikely |

**Why these cutoffs:** the original V3 boundaries (2.70 / 3.40 / 4.10 / 4.80) let one_sided fixtures creep into the low bucket, contaminating low-zone hit rates. The raw-notes overlay tightens each band so each zone captures a structurally distinct fixture type.

---

## Step 2 — BTS Direction Classification (cell axis)

Every fixture gets a **BTS direction** — the v4 cell axis is binary.
Source: `bts_yesno()` in `app/engine/classify.py`.

| Direction | Condition |
|-----------|-----------|
| `over` | `yes_odd ≤ no_odd` (BTTS Yes is favoured) |
| `under` | `no_odd < yes_odd` (BTTS No is favoured) |

`bts_of()` also returns the legacy 4-pocket value (strong_over / slight_over / slight_under / strong_under) stored in `bts_pocket` for display chips and the spread signal computation. `bts_spread()` extracts `strong` or `slight` from this.

---

## Step 3 — Cell Assignment

Each fixture lands in exactly one cell: **(zone × bts_direction)**.
4 zones × 2 directions = 8 possible cells — **all 8 are active in v4**.
Partition key string: `zone:bts` (e.g. `standard:over`).

---

## Step 4 — v4 Active Cells (8)

Locked from 28,571-fixture fresh test + adversarial feasibility workflow (GO_WITH_CONDITIONS).
All 8 cells have n ≥ 802 — zero thin cells.
Source: `app/engine/static_policy.py::V3_ACTIVE`.

**Composite hit rates (mean of 3 market hit rates, from test):**

| Cell | Composite |
|------|-----------|
| `strong:over` | 70.3% |
| `strong:under` | 69.5% |
| `standard:over` | 71.3% |
| `standard:under` | 69.9% |
| `low:over` | 75.6% |
| `low:under` | 71.8% |
| `one_sided:over` | 80.4% |
| `one_sided:under` | 80.6% |

These baselines are from the test dataset. Live settlement under the new boundaries started 2026-05-30. Recalibrate after 6 weeks. Do not gate emission on these numbers.

---

## Step 5 — Markets per Cell

Every cell fires the same three markets. Line varies by zone.

| Market | Pick label | Line | Corners line (strong / rest) |
|--------|-----------|------|------------------------------|
| `goals_nl` | `"Over 1.5 Goals"` | O1.5 (all zones) | — |
| `corners_nl` | `"Over 7.5 Corners"` / `"Over 8.5 Corners"` | — | O7.5 strong / O8.5 rest |
| `threeway` | Alpha team or `"Draw"` | — | — |

- **goals_nl:** `pick_odd` from `fixtures.goals_over_15_odd` — often NULL (Sportmonks rarely quotes O1.5). SPA renders `—`. By design, no fallback.
- **corners_nl:** `pick_odd` from `fixtures.corners_over_75_odd` (strong) or `corners_over_85_odd` (rest) — almost always NULL. By design.
- **threeway:** alpha-or-draw — a draw is a protected **WIN** (no void). `pick_odd = min(home_odd, away_odd)` if alpha wins; draw is also a win but has no single assigned odd.

---

## Step 6 — Signals (NOT gates, NOT cell axes)

Signals add display chips and one per-market tilt. They do **not** suppress or gate picks.

| Signal | Source | Effect |
|--------|--------|--------|
| **BTS spread** | `bts_spread()` → `strong` or `slight` | Display chip. Goals-override: in `standard:over` + `low:over`, when spread==`strong`, the goals_nl pick carries the strong-spread rate (83.8% / 85.0%) instead of the blended cell rate — a per-market tilt only. |
| **DF** | `df_of()` → DF0 / DF1 / DF2 | Display chip + threeway-confidence note where monotone (strong:under, standard:over DF2). Dead in 5/8 cells. Never a partition key. |
| **H2H-corner** | `h2h_meetings` table → `over` / `under` / `none` | Display chip only. Derived local-first from our own prior meetings on upcoming fixtures. |

---

## Step 7 — Pick Generation

`GET /picks?days=N` — `app/api/routes_picks.py`.

Per upcoming fixture in window:
1. Classify → (zone, bts_yesno). Signals derived in parallel: spread, DF, H2H-corner.
2. Look up `V3_ACTIVE[(zone, bts_yesno)]`. Skip if absent (counted as `partition_not_promoted`).
3. For each of the 3 markets: build pick label + look up pick_odd (likely NULL by design).
4. Apply BTS spread goals-override if applicable.
5. Compute drift flag from recent emit_log outcomes vs baseline (`stable` / `watch` / `drifting` / `no_data`).
6. Write to `emit_log` via `write_emit_log()` — supersedes stale unsettled pick on the same `(fixture_id, market)` when alpha label changed, then `INSERT OR IGNORE` on `pick_uuid`.

`pick_uuid = sha256("{fixture_id}:{market}:{pick}")[:36]`.

Scheduler: `emit_picks.py` calls `/picks?days=3` daily at 08:05 SAST. SPA Picks tab loads also drive emits.

---

## Step 8 — Settlement

`settle.py` runs after `fetch_results.py`. For each pending emit_log row whose fixture has a score:

| Market | Rule |
|--------|------|
| `goals_nl` | `total_goals > line` — line parsed via regex `"Over (\d+\.5) Goals"` → WIN, else LOSS |
| `corners_nl` | `total_corners > line` — regex `"Over (\d+\.5) Corners"` → WIN, else LOSS (skipped if NULL) |
| `threeway` | alpha wins OR draw → **WIN**; alpha loses → LOSS (draw is WIN, no void) |
| `dnb` (legacy) | alpha wins → WIN (1.0); draw → VOID (0.5); alpha loses → LOSS (0.0) |

Writes `pick_results(outcome, actual_value)` plus a `settle` heartbeat to `system_health`.

---

## Hit-rate convention

**v4 binary:** `hit_rate = wins / settled`. Draw = WIN for threeway (no void, no 0.5).
Legacy `dnb` rows settle under old `(wins + voids) / settled` for their tail.
Wilson is retired. EV is out of scope for the engine (Durable Rule 2).

---

## Drift

Per (zone, bts, market) cell, compare recent emit_log hit rate to historical baseline.

| Flag | Condition |
|------|-----------|
| `stable` | gap > −5pp |
| `watch` | −10pp < gap ≤ −5pp |
| `drifting` | gap ≤ −10pp |
| `no_data` | recent_n < 10 |

Drift is informational. The engine never auto-demotes — operator reviews and decides.

---

## What does NOT exist (by Durable Rule)

- **DF as a partition key** — `df_of()` is a signal only. Never a cell axis in v4.
- **BTS spread as a partition key** — signal only. The 4-pocket `bts_pocket` column is for display/signal; the cell key uses binary `bts_yesno`.
- **EV / breakeven / Wilson** — analysis-only. No live engine code consults these.
- **Goals or corners effective-line fallback** — natural line only (`pick_odd` NULL is expected).
- **Team form / position / predicted-uncertainty weighting** — odds drivers + H2H corner counts only.
- **Hard suppression gates** — signals display but never block emission.
