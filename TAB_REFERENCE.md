# OddsFlow V4 — Tab Reference (what each tab shows, how it works, what feeds it)

**Operator:** Katlego (KK) | **Port:** 8083 | **Written:** 2026-06-19 (Session 24)
**Companion to:** `OPERATOR_MANUAL.md` (operations) and `CLAUDE.md` (engine rules)

---

## Why this document exists

This is the contract between **what you see on screen** and **what the code does**.
For every tab it tells you three things:

1. **What's in it** — the panels and the numbers they show.
2. **How it works** — what each number means and how it is computed.
3. **What feeds it** — the exact HTTP endpoint and the code function behind it.

Use it like this: if a tab shows something that looks wrong or behaves unlike this
document says, find the panel below, read its **Feed** row, and point me at that
endpoint/function. I can then open that code and check it against this description.
**Quality = how closely the app matches this document.** If they disagree, one of
the two is wrong and we fix it — either the code (a bug) or this doc (drift in the
spec). Nothing is left to interpretation.

The frontend is a single static file (`app/frontend/static/engine.js`) rendered
into `app/frontend/templates/engine_view.html`. Every tab is one JavaScript
`load*()` function that calls one or more JSON endpoints and renders the result.
**Frontend changes go live on a browser reload; backend (endpoint) changes only
take effect after the server is restarted from an admin session.**

---

## The nine tabs at a glance

| Tab | Purpose | Loader function | Primary endpoint(s) |
|-----|---------|-----------------|---------------------|
| **Picks** | Today's live engine picks (ground zero) | `loadPicks()` | `/picks`, `/picks/prx9` |
| **Picks Log** | Advanced 3-config layer (Most-likely / Standard / Optimistic) | `loadPicksLog()` | `/picks` (+ client-side overlay) |
| **Upcoming** | Fixtures + odds we've ingested, ahead of kickoff | `loadUpcoming()` | `/upcoming` |
| **Analysis** | Foundation matrix — every cell's hit rate by market | `loadAnalysis()` | `/api/foundation` |
| **Inspector** | Drift (recent vs baseline) + cell deep-dive | `loadInspector()` | `/inspector/partition_drift`, `/inspector/similar`, `/inspector/recent_settled` |
| **Reports** | Settlement + emit performance over a window | `loadReports()` | `/reports/settle_activity`, `/reports/emit_performance`, `/reports/emit_market_breakdown`, `/reports/emit_recent` |
| **Results** | Settled results + live scores | `loadResults()`, `loadLivescores()` | `/api/results`, `/api/livescores` |
| **Today** | Operations runbook — did each daily task run? | `loadToday()`, `loadRunbookStrip()` | `/diagnostics/today_summary`, `/diagnostics/runbook` |
| **Stats** | System health, odds coverage, drift summary, activity | `loadStats()` | `/diagnostics/db_state`, `/odds_coverage`, `/cron/heartbeat`, `/drift_report`, `/activity_by_tier` |

Shared building blocks (cells, markets, settlement, the live baseline) are defined
once in the **Appendix** at the bottom and referenced from each tab.

---

## 1. Picks

**What it is.** The ground-zero engine output: for each upcoming fixture that lands
in one of the 8 active cells, the picks it fires. This is the engine in Rule terms —
no EV, no economic modelling, just the cell's markets and their historical hit rate.

**What's in it.**
- A day selector (`days=` — how far ahead to look).
- One card per fixture. Each card shows: the teams, kickoff, the **partition chip**
  (`zone:bts`, e.g. `standard:over`), the signal chips (spread, DF, H2H-corner —
  display only), a **promote/hit chip** (the cell's baseline hit% and n), a **drift
  chip** (how the cell is doing recently vs that baseline), and one **leg per market**
  (goals_nl, corners_nl, threeway) with that market's pick label, hit% and n.

**How it works.**
- A fixture is classified into a cell by `zone_of(draw_odd)` × `bts_yesno(yes,no)`
  (see Appendix → Cells). Only the 8 cells in `V3_ACTIVE` fire.
- Each market's hit% / n now comes from the **live growing baseline**
  (`live_cell_hit`) — every newly settled fixture moves it. If a cell has <50
  settled fixtures it falls back to the frozen `V3_MARKETS` number. (Changed
  Session 24; before this the card showed a frozen baseline that never moved.)
- The threeway pick is **alpha-or-draw** (favourite **or** draw = WIN, no void).
- Signals (spread strong/slight, DF0/1/2, H2H over/under/none) are **display
  chips only** — they do not gate or change which picks fire. (The old
  goals-override was retired Session 24.)

**What feeds it.**

| Panel | Endpoint | Code | Notes |
|-------|----------|------|-------|
| Pick cards | `GET /picks?days=N` | `app/api/routes_picks.py` → `picks()` | Iterates `V3_ACTIVE`; baseline via `live_cell_hit` with frozen fallback. Fields: `cell_historical_hit`, `cell_historical_n`, `cell_drift_*`, `partition_key`. |
| Proximity view | `GET /picks/prx9?days=N` | `routes_picks.py` | Secondary "near-miss" feed used by the card detail. |

**How to verify.** Pick a card, read its `partition_key`, then open the Analysis
tab and find the same cell — the baseline hit% should match (both read the same
live baseline / `V3_MARKETS`). The drift chip should match the same cell+market
row on the Inspector tab.

---

## 2. Picks Log

**What it is.** The advanced layer built **on the back of** the engine. It does not
re-run the engine; it takes the same `/picks` emits and groups them into three
practical configs. **Legs only — no EV yet, by design** (EV is introduced only
after the build is validated in full; see CLAUDE.md Rule 2 and 4).

**What's in it.**
- The three configs: **Most-likely**, **Standard**, **Optimistic** (a confidence
  ladder over the same fixtures).
- For each qualifying fixture: the cell + tier + signal chips, and **every market
  that clears the bar** — not just one. The strongest market is starred (★). The
  bar is **72%** (`PL_BAR`). Multiple markets can show for one fixture whenever
  more than one clears 72%.

**How it works.**
- Starts from each fixture's per-market baseline hit (from `/picks`).
- Applies **signal overlay deltas** (`PL_DELTAS`): a cell base **plus** stacked
  signal adjustments. The spread overlay (when `spread==strong`) lifts
  goals/corners and trims threeway in over-cells; the DF overlay lifts threeway by
  DF level where it varies. These are *additive deltas on top of* the cell base —
  an overlay, not a replacement. The exact deltas live in `PL_DELTAS` at the top of
  the Picks Log section of `engine.js`, validated in `analysis/` (spread + DF
  validation, 2026-06-18).
- A market is listed only if its **signal-adjusted** hit clears `PL_BAR` (72%). If
  several clear, all are shown (top starred). Nothing is forced to a single market.
- bts:over **and** bts:under cells both appear wherever the data supports them.
- No golden-rule text, no long descriptions — list form only.

**What feeds it.**

| Panel | Endpoint | Code | Notes |
|-------|----------|------|-------|
| All three configs | `GET /picks?days=N` | `engine.js` → `loadPicksLog()` | Same emits as the Picks tab; the config grouping, `PL_DELTAS` overlay and `PL_BAR` filter are **client-side** in `engine.js`. |

**How to verify.** A fixture's market here should equal its Picks-tab baseline
**plus** the matching `PL_DELTAS` value when the spread/DF signal is present, and
only appear if the result is ≥72%. If a market you expect is missing, check whether
its adjusted hit fell below 72% — that's the bar doing its job, not a bug.

---

## 3. Upcoming

**What it is.** Everything we've ingested for fixtures **ahead of kickoff** — the
raw input the engine reads. Confirms fetch_upcoming actually pulled odds and
classified each fixture.

**What's in it.** A day + tier filter, a summary line (counts), and a list of
fixtures with their odds (1X2, BTTS, goals/corners lines), their classified
`zone`/`bts`, and kickoff time.

**How it works.** Reads stored fixtures whose kickoff is in the future. Odds shown
are the **frozen** pre-match odds we captured (refresh only touches fixtures with
no score yet; see CLAUDE.md "odds frozen at settlement"). Zone/bts are recomputed
from the stored odds.

**What feeds it.**

| Panel | Endpoint | Code | Notes |
|-------|----------|------|-------|
| Summary + list | `GET /upcoming?days=N&tier=T` | `routes_*` upcoming handler | `tier` optional. `body.summary` drives the count line, `body.data` the list. |

**How to verify.** A fixture here should appear on the Picks tab if and only if its
`zone:bts` is one of the 8 active cells. If it's in an active cell but shows no
pick, its odds are probably incomplete (missing a market the pick needs).

---

## 4. Analysis (Foundation matrix)

**What it is.** The full per-cell hit-rate matrix across **all settled fixtures** —
the evidence base. Every `(zone × bts)` cell, every market, with tier splits.

**What's in it.** A tier sub-tab (ALL / T1+T2 / T3) and a table: one row per cell,
columns for goals (natural + system line), corners (natural + system), threeway,
the drop between natural and system lines, promotion status, **n_fixtures** and
(Session 24) **n_corners**.

**How it works.**
- `compute_foundation(rows)` buckets every settled fixture into its `(zone, bts)`
  cell and counts greens per market.
- **Goals & threeway** divide by `n_fixtures` (all fixtures in the cell).
- **Corners** divide by `n_corners` — fixtures that actually have corner stats
  (Session 24 fix). Before this, corners were divided by all fixtures and read
  ~49% instead of the true ~64%.
- Tier splits: ALL, T1+T2, T3 (CLAUDE.md Rule 6 — tiers grouped T1+T2 vs T3).
- Promotion status is **display metadata** (which cells would promote at the
  thresholds); it does not itself fire picks — `V3_ACTIVE` does.

**What feeds it.**

| Panel | Endpoint | Code | Notes |
|-------|----------|------|-------|
| Matrix (3 tier tables) | `GET /api/foundation` | `routes_foundation.py` → `compute_foundation()` in `app/engine/promotion.py` | Returns `all` / `t1t2` / `t3` cell lists + `summary`. Each cell: `gn_hit`, `gs_hit`, `cn_hit`, `cs_hit`, `threeway_hit`, `n_fixtures`, `n_corners`, promote statuses. |

**How to verify.** The corner hit% here should be in the same ballpark as the
corner leg on the Picks tab for the same cell (both grade corners on corner-available
fixtures). If Analysis shows ~49% corners again, the `cn_n` denominator regressed.

---

## 5. Inspector

**What it is.** The watchdog. It answers "is a cell still performing like its
baseline?" (drift) and lets you drill into a cell's recent history.

**What's in it.**
- **Drift table** — one row per **cell × market** (Session 24; was per-cell,
  threeway-only). Columns: Zone, BTS, **Market**, Historical n, Hist hit%, Recent
  n, Recent hit%, Gap pp, Flag. A day selector sets the recent window.
- **Cell deep-dive** ("similar") — recent settled fixtures for a chosen cell.

**How it works.**
- `compute_drift_rows()` pulls recently settled emits, settles each with
  `settle_pick`, and buckets hits per `(zone, bts, market)` across adaptive windows
  (30→90 days; it widens until a cell has enough sample, `min_sample_n`).
- Each market is compared against **its own** baseline — **live baseline preferred**
  (`live_cell_hit`), frozen `V3_MARKETS` as fallback. (Before Session 24 every
  market was compared to the threeway rate, which made goals/corners drift
  meaningless.)
- **Flag** = `_drift_flag(gap_pp, n)`: `stable` within 5pp, `watch` 5–10pp below,
  `drifting` >10pp below, `no_data` if sample < `min_sample_n`. Drift is a
  **signal, not a gate** — it never auto-suppresses a cell (CLAUDE.md: no hard
  suppression in v4).

**What feeds it.**

| Panel | Endpoint | Code | Notes |
|-------|----------|------|-------|
| Drift table | `GET /inspector/partition_drift?recent_days=N` | `routes_inspector.py` → `compute_drift_rows()` | Rows keyed `zone:bts:market` (`partition_key`). |
| Cell deep-dive | `GET /inspector/similar?zone=&bts=&df=&limit=` | `routes_inspector.py` | Recent settled fixtures for one cell. |
| Recent settled | `GET /inspector/recent_settled?days=N` | `routes_inspector.py` → `recent_settled()` | Settled pick_results grouped by fixture. |

**How to verify.** Each drift row's "Hist hit%" should match that cell+market's
baseline on the Picks/Analysis tabs. "Recent hit%" over a long window should
converge toward it. A `drifting` flag means recent is >10pp below baseline — worth
watching, but the cell still fires (by design).

---

## 6. Reports

**What it is.** Performance over a chosen window — both **settlement activity** (did
results land?) and **emit performance** (are the picks winning?). **v4-only**
(Session 24): legacy `dnb`/`alpha_win` rows are filtered out everywhere.

**What's in it.**
- A day + tier filter.
- **Settle activity** — settlements per window/state.
- **Emit performance** — per window (7d/30d/etc.): fixtures, legs total/settled/hit%,
  events settled/hit%, wins/voids/losses.
- **Market breakdown** — per market hit% vs baseline (drives the markets-summary,
  zone-market and pending tables).
- **Recent emits** — the actual recent picks with outcomes + a totals line.

**How it works.** Each query reads `emit_log` joined to fixtures (+ corner stats),
settles each leg with `settle_pick`, and aggregates. **Every query filters
`em.market IN ('goals_nl','corners_nl','threeway')`** so pre-v4 markets can't
distort the counts. The tier filter narrows by league tier.

**What feeds it.**

| Panel | Endpoint | Code | Notes |
|-------|----------|------|-------|
| Settle activity | `GET /reports/settle_activity?days=N` | `routes_reports.py` | Settlement windows; v4-market filtered. |
| Emit performance | `GET /reports/emit_performance?tier=T` | `routes_reports.py` | Per-window legs + events. |
| Market breakdown | `GET /reports/emit_market_breakdown?days=N&tier=T` | `routes_reports.py` | Per-market hit% + `vs_baseline_pp`. |
| Recent emits | `GET /reports/emit_recent?days=N&tier=T` | `routes_reports.py` | Recent picks + outcomes + totals. |

**How to verify.** "Emit performance" event hit% for a window should be consistent
with the cell baselines weighted by how many picks fired in each cell. If you ever
see a market other than goals_nl/corners_nl/threeway here, the v4 filter regressed.

---

## 7. Results

**What it is.** The settled record and live in-progress scores.

**What's in it.**
- **Results list** — settled fixtures over a day window, with scores, the picks
  that fired, and WIN/LOSS/VOID/ORPHAN outcomes.
- **Livescores** — fixtures in progress, auto-settling as finals land.

**How it works.** Results read `pick_results` joined to fixtures and leagues.
Livescores polls Sportmonks in-process (the poller is a background thread in the
app lifespan — Session 23 fix; it no longer dies on off-days) and auto-settles
finished matches. An un-returnable fixture becomes `no_result` after 5 days and its
picks settle as **ORPHAN** (excluded from hit rate).

**What feeds it.**

| Panel | Endpoint | Code | Notes |
|-------|----------|------|-------|
| Results list | `GET /api/results?days=N` | `routes_results.py` | Settled pick_results by fixture. |
| Livescores | `GET /api/livescores` | `routes_results.py` → `_sm_get()` | In-process poller; requires `User-Agent: OddsFlowV4/1.0` (no-UA → 403). |

**How to verify.** A fixture marked settled here should also appear in the Reports
window counts and feed the Inspector drift. ORPHAN outcomes should never count
toward any hit rate.

---

## 8. Today

**What it is.** The operations runbook — did each scheduled daily task actually run,
and is the data current? This is where you look first each morning.

**What's in it.** A per-task strip with heartbeat badges (green = ran on time, red =
overdue/failed), the chain verification, and a drift summary chip.

**How it works.** Each daily script writes a heartbeat; `today_summary` reads the
heartbeats, compares against expected schedule, and flags overdue tasks. The
runbook strip explains each task and its freshness threshold (see OPERATOR_MANUAL §8).

**What feeds it.**

| Panel | Endpoint | Code | Notes |
|-------|----------|------|-------|
| Task badges | `GET /diagnostics/today_summary` | `routes_diagnostics.py` → `today_summary()` | Per-task heartbeat + drift summary (counts stable/watch/drifting). |
| Runbook strip | `GET /diagnostics/runbook` | `routes_diagnostics.py` | Task definitions + freshness thresholds. |

**How to verify.** If a badge is red, the matching script in OPERATOR_MANUAL's daily
task list hasn't run within its threshold — run it manually. The drift chip here is
the same data as the Inspector drift table, summarized to counts.

---

## 9. Stats

**What it is.** System-wide health and coverage — the "is the whole machine
healthy?" view.

**What's in it.**
- **DB state** — fixture/pick counts, last backup, integrity.
- **Odds coverage** — how many fixtures have complete odds (after the market-id
  correction, goals=80 / corners=67).
- **Cron heartbeat** — last run of each scheduled job.
- **Drift report** — partition drift summarized (now per `zone:bts:market`).
- **Activity by tier** — emit/settlement volume by league tier over 7 days.

**How it works.** Aggregates the diagnostics endpoints. The drift report reuses
`compute_drift_rows` (so it inherits the Session 24 multi-market shape and the
v4-only / live-baseline behaviour).

**What feeds it.**

| Panel | Endpoint | Code | Notes |
|-------|----------|------|-------|
| DB state | `GET /diagnostics/db_state` | `routes_diagnostics.py` | Counts + backup + integrity. |
| Odds coverage | `GET /diagnostics/odds_coverage` | `routes_diagnostics.py` | Completeness of stored odds. |
| Cron heartbeat | `GET /diagnostics/cron/heartbeat` | `routes_diagnostics.py` | Last-run per scheduled job. |
| Drift report | `GET /diagnostics/drift_report` | `routes_diagnostics.py` → `compute_drift_rows()` | `partition_key` = `zone:bts:market`. |
| Activity by tier | `GET /diagnostics/activity_by_tier?days=7` | `routes_diagnostics.py` | Volume by T1/T2/T3. |

**How to verify.** Odds coverage should be high for recent dates (since ~2026-06-08
when `raw_odds_json` capture began and the re-derive runs). Drift report counts
should equal the Inspector summary for the same window.

---

# Appendix — shared building blocks

These are referenced by the tabs above. They live in the engine, not in any one
tab, so they're defined once here.

## A. Cells (the partition)

A fixture's cell is `(zone, bts)` — **8 active cells**, the whole engine.

- **zone** = `zone_of(draw_odd)` (`app/engine/classify.py`):
  `strong` 2.90–3.30 · `standard` 3.30–3.80 · `low` 3.80–4.30 · `one_sided` ≥4.30 ·
  excluded `<2.90`.
- **bts** = `bts_yesno(yes_odd, no_odd)`: `over` when `btts_yes_odd ≤ btts_no_odd`,
  else `under`.
- Active cells live in `static_policy.V3_ACTIVE`; display metadata in
  `PROMOTED_CELLS`; frozen baselines in `V3_MARKETS`.
- **Signals are not axes**: spread (strong/slight), DF (DF0/1/2), H2H-corner
  (over/under/none) are display chips + the Picks-Log overlay only. They never
  change which cell a fixture is in or which picks fire (CLAUDE.md Rule 1, 7).

## B. Markets (per cell)

`MARKET_KEYS = ('goals_nl', 'corners_nl', 'threeway')`.

- **goals_nl** — Over 1.5 goals (all zones).
- **corners_nl** — Over 7.5 corners (strong) / Over 8.5 (all other zones).
- **threeway** — alpha-or-draw: favourite **or** draw = WIN, no void.

## C. Settlement & hit rate

- `settle_pick(market, home_score, away_score, home_odd, away_odd, pick, total_corners)`
  grades one leg; `is_hit()` reduces it to win/not.
- Hit rate = wins / settled (binary). Threeway draw = WIN (no 0.5 void). Legacy
  `dnb` rows still use the old `(wins+voids)/settled`. Wilson is out (CLAUDE.md
  Rule 3).
- Corners only grade where corner stats exist — graded on the corner-available
  denominator, never all fixtures.

## D. Baseline — live vs frozen

- **Live (preferred):** `app/engine/live_baseline.py` → `live_cell_hit()` computes
  each cell × market hit% from every settled, classifiable fixture; cached 30 min;
  returns `None` (→ frozen fallback) if a cell has <50 settled. **This is what makes
  the picture grow.**
- **Frozen (fallback):** `static_policy.V3_MARKETS` — the 2026-05-30 foundation-test
  constants. Used only when the live cell is too thin to trust.

## E. Endpoint → file map (for code review)

| Prefix | File |
|--------|------|
| `/picks*` | `app/api/routes_picks.py` |
| `/upcoming` | upcoming route handler |
| `/api/foundation` | `app/api/routes_foundation.py` (+ `app/engine/promotion.py`) |
| `/inspector/*` | `app/api/routes_inspector.py` |
| `/reports/*` | `app/api/routes_reports.py` |
| `/api/results`, `/api/livescores` | `app/api/routes_results.py` |
| `/diagnostics/*` | `app/api/routes_diagnostics.py` |
| Frontend (all tabs) | `app/frontend/static/engine.js` + `templates/engine_view.html` |
| Cell classification | `app/engine/classify.py` |
| Policy constants | `app/engine/static_policy.py` |
| Live baseline | `app/engine/live_baseline.py` |
| Foundation matrix | `app/engine/promotion.py` |

## F. Deploy reality

- **Frontend** (anything in `engine.js`/templates) → live on a browser reload.
- **Backend** (any endpoint/engine `.py`) → only after the server process is
  replaced. The running server is **elevated**, so a non-admin restart can't kill
  it — reboot from an admin session, or run `restart_server2.bat` elevated.

---

*Written 2026-06-19 (Session 24). Keep this in sync with the code: when a tab's
behaviour changes, update its section here in the same commit. If the app and this
document disagree, that's the bug report — name the panel and its Feed row.*
