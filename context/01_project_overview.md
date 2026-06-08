# OddsFlow V4 — Project Overview (v4 policy, 2026-05-30)

**What it is:** Football betting analytics engine for personal use.
Ingests pre-match fixtures and odds from Sportmonks, classifies each match
into a **(draw_zone × BTS direction)** cell, and surfaces picks for the 8 cells
in the v4 policy. The structured edge is in the partition — `draw_odd × bts(yes/no)`
reveals the layer where hit rates concentrate.

**Who:** Katlego (KK) — sole operator. Single-user system.

**One project. One folder. One repo. One DB.**

---

## How it works (plain language)

1. **Data in** — `fetch_upcoming.py` pulls upcoming fixtures with odds (1X2, BTTS, goals_over_15/25/35, corners_over_75/85/95) from Sportmonks daily. Intraday refresh via `refresh_odds.py`.
2. **Classify** — Each fixture gets a draw zone (4 active zones: strong / standard / low / one_sided) and a BTS direction (`over` when BTTS Yes is favoured, `under` otherwise). `bts_pocket` also stores the 4-pocket value (strong_over/slight_over/slight_under/strong_under) for display chips and the spread signal.
3. **v4 policy** — 8 cells, 2-key `(zone, bts)` locked from 28,571-fixture fresh test. Stored in `app/engine/static_policy.py::V3_ACTIVE`.
4. **Pick output** — 3 markets per cell, every cell:
   - `goals_nl` — Over 1.5 Goals (all zones)
   - `corners_nl` — Over 7.5 Corners (strong), Over 8.5 Corners (rest)
   - `threeway` — alpha-or-draw (a draw is a WIN; no void at ground zero)
5. **Signals** (display chips + one goals-override — NOT gates): BTS spread (strong/slight), DF (DF0/DF1/DF2), H2H-corner (over/under/none).
6. **Settle** — `fetch_results.py` writes scores + corners; `settle.py` resolves picks into pick_results (WIN / LOSS). Hit rate = wins / settled (binary). Draw = WIN for threeway.

---

## Key decisions

- **v4 is the active policy (2026-05-30).** 8 cells, 2-key `(zone, bts)` where `bts ∈ {over, under}`. Drawn from a fresh from-scratch test + adversarial feasibility workflow (GO_WITH_CONDITIONS). Zero thin cells (old 15-cell 4-pocket form had n=16/19/18 noise cells; collapsing BTS to binary removes them at equal hit-rate).
- **Zone boundaries are the raw-notes overlay** (Session 19): excluded < 2.90, strong 2.90–3.30, standard 3.30–3.80, low 3.80–4.30, one_sided ≥ 4.30.
- **Three markets per cell.** goals_nl (O1.5) + corners_nl (O7.5 strong / O8.5 rest) + threeway (alpha-or-draw).
- **BTS spread and DF are signals, not cell axes.** BTS spread adds a goals-override tilt in standard:over and low:over when spread==strong. DF is a display chip only (dead in 5/8 cells). H2H-corner is display-only.
- **No EV gates. No Wilson. No economic models in the live engine.** These are durable rules — see CLAUDE.md → Durable rules.
- **SQLite, no external services.** Runs locally on port 8083 + ngrok tunnel.

---

## Technology stack

- **Backend:** Python + FastAPI (uvicorn, port 8083)
- **Database:** SQLite (`data/oddsflow_v4.db`)
- **Frontend:** SPA — Jinja2 + vanilla JS (`engine_view.html`, `engine.js`, `engine.css`)
- **Odds source:** Sportmonks API v3
- **Scheduler:** Windows Task Scheduler — 12 jobs (`setup_scheduler.ps1`)

---

## Reference docs in this folder

| File | Contents |
|------|----------|
| `02_league_config.md` | 29 active leagues, tier assignments |
| `03_engine_rules.md` | v4 classification, 8 cells, market rules |
| `04_current_status.md` | Current state, known issues, session log |
| `05_architecture.md` | File map, API routes, DB tables |
| `06_process_flow.md` | Full fixture lifecycle |
| `07_system_language.md` | Every term defined |
| `engine_knowledge.md` | Tabs, abbreviations, operating notes |
| `archive/` | Implemented plan docs (historical audit trail) |
