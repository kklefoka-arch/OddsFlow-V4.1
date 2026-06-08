# OddsFlow V4 — Architecture & File Map (v4 policy, 2026-05-30)

## Process flow

```
Sportmonks API (v3/football/fixtures/between/{start}/{end}?include=participants;odds)
  └─ fetch_upcoming.py  (daily 08:00 SAST)         [+ refresh_odds.py @ 14:30]
       └─ fixtures table (1X2, BTTS, goals_over_*_odd, corners_over_*_odd)
            └─ classify_fixture()  [app/engine/classify.py]
                 ├─ zone_of(draw_odd)       → strong | standard | low | one_sided | NULL
                 ├─ bts_yesno(yes, no)      → over | under   ← v4 cell axis
                 ├─ bts_of(yes, no)         → strong_over | slight_over | slight_under | strong_under  ← display pocket
                 ├─ bts_spread(yes, no)     → strong | slight  ← qualifying signal
                 └─ df_of(home, draw, away) → DF0 | DF1 | DF2  ← qualifying signal
                      └─ V3_ACTIVE.get((zone, bts_yesno))  [app/engine/static_policy.py]
                           └─ per-cell picks: goals_nl (O1.5) | corners_nl (O7.5/O8.5) | threeway
                                └─ emit_log  (INSERT OR IGNORE on pick_uuid; supersede stale)

Sportmonks API (results)
  └─ fetch_results.py  (23:30 / 03:00 / 06:00 SAST)
       ├─ fixtures.home_score / away_score / total_goals
       └─ fixture_stats.home_corners / away_corners / total_corners
            └─ settle.py  (23:45 / 03:15 / 06:15 SAST)
                 └─ pick_results  (outcome, actual_value)
                      └─ Inspector + Reports tabs surface settled performance
```

## File map — `C:\OddsFlowV4`

```
app/
├── main.py                    FastAPI entry — SPA at /, registers all routers
├── settings.py                DATABASE_URL, APP_ENV, LOG_LEVEL, RUNBOOK_THRESHOLDS
├── api/
│   ├── routes_health.py         GET /health + /healthz/deep
│   ├── routes_fixtures.py       /api/fixtures JSON + settle helpers
│   ├── routes_foundation.py     GET /api/foundation (JSON) — Analysis tab matrix
│   ├── routes_picks.py          GET /picks — v4 policy lookup + emit_log write + drift
│   ├── routes_upcoming.py       GET /upcoming — fixtures with v4 cell chips
│   ├── routes_reports.py        /reports/* — emit performance, recent, settle activity, market breakdown
│   ├── routes_inspector.py      /inspector/* — partition_drift, recent_settled, similar, daily_calendar
│   ├── routes_diagnostics.py    /diagnostics/* — today_summary, db_state, cron heartbeat, drift_report
│   └── routes_results.py        /api/results + /api/livescores (livescores polling)
├── engine/
│   ├── classify.py              zone_of() (raw-notes overlay) + bts_yesno() (cell axis) +
│   │                            bts_of() (4-pocket display) + bts_spread() (signal) +
│   │                            df_of() (signal) + classify_fixture()
│   ├── static_policy.py         V3_ACTIVE / V3_MARKETS / PROMOTED_CELLS — v4 8-cell policy
│   ├── promotion.py             compute_foundation() — display matrix only (not pick firing)
│   ├── foundation.py            load_foundation(conn) — settled fixture loader
│   └── natural_lines.py         natural_line(zone, market), system_line(zone, market)
├── db/
│   ├── database.py              init_db() + get_conn() + _run_migrations() (11 indexes)
│   └── schema.sql               Full schema definition
└── frontend/
    ├── templates/engine_view.html  SPA — 8 tabs
    └── static/
        ├── engine.js
        └── engine.css

data/
├── oddsflow_v4.db                 Live SQLite DB (not in git)
├── oddsflow_v4.db.bak.*           DB backups
└── v1_calibration_readonly.db     Historical 28k fixtures (read-only reference)

fetch_upcoming.py                  Daily fetch — odds + kickoff datetimes
emit_picks.py                      Calls /picks?days=3 + emit_picks heartbeat
refresh_odds.py                    Intraday odds refresh for next-8h fixtures (M2)
refresh_stats.py                   Corner-stats backfill (14d adaptive lookback, M3)
fetch_results.py                   Scores + corner stats post-match
settle.py                          pick_results writer
reconcile_orphans.py               Synthetic ORPHAN outcome for stale/dropped-league picks
run_daily.ps1                      Operator chained pipeline
setup_scheduler.ps1                Registers 12 Task Scheduler jobs
scripts/
├── update_leagues.py              Upsert active leagues
├── seed_from_calibration.py       One-time seed from calibration DB
└── league_migration_analysis.py   Writes Excel/JSON to AI Website output folder
archive/                           Zipped retired projects
context/                           This folder
CLAUDE.md                          Session entry point
OPERATOR_MANUAL.md                 Operator reference
```

## SPA tabs → API endpoints

| Tab | Endpoint(s) |
|-----|-------------|
| Picks | `GET /picks?days=N` |
| Today | `GET /diagnostics/today_summary` |
| Upcoming | `GET /upcoming?days=N&tier=T` |
| Analysis | `GET /api/foundation` |
| Inspector | `GET /inspector/partition_drift` + `/recent_settled` + `/similar` + `/daily_calendar` |
| Reports | `GET /reports/settle_activity` + `/emit_performance` + `/emit_recent` + `/emit_market_breakdown` |
| Stats | `GET /diagnostics/db_state` + `/odds_coverage` + `/cron/heartbeat` + `/drift_report` + `/activity_by_tier` |
| Results | `GET /api/results` + `/api/livescores` |

## DB tables

| Table | Contents |
|-------|----------|
| `leagues` | Subscribed + historical leagues with `sportmonks_id` and `tier` |
| `teams` | Teams auto-added during fixture fetch |
| `fixtures` | All fixtures. Odds: `home_odd`, `draw_odd`, `away_odd`, `btts_yes_odd`, `btts_no_odd`, `goals_over_15/25/35_odd`, `corners_over_75/85/95_odd`. `draw_zone` uses v4 raw-notes overlay. `bts_pocket` stores 4-pocket for display. `df_level` retained as metadata signal. `odds_updated_at` stamps freshness. |
| `fixture_stats` | Corner stats + other per-match stats for settled fixtures. `raw_stats_json` captures full API payload. |
| `emit_log` | Every pick emitted. `zone` + `bts_pocket` store classification at emit time. `df_level` stored as signal metadata. |
| `pick_results` | Settlement outcomes (`outcome` TEXT WIN/LOSS/VOID; `actual_value` REAL 1.0/0.5/0.0) |
| `system_health` | Per-task heartbeats (`fetch_upcoming`, `fetch_results`, `settle`, `emit_picks`, `refresh_odds`, `refresh_stats`, `zone_migration`, legacy `cron_heartbeat`) |
| `h2h_meetings` | Head-to-head history (~58k rows; H2H corner-count signal, live on upcoming fixtures) |

## Performance indexes (applied via _run_migrations on startup)

`idx_fixtures_date`, `idx_fixtures_score`, `idx_fixtures_draw_zone`,
`idx_emit_emitted_at`, `idx_emit_fixture_id`, `idx_emit_zone_bts`,
`idx_pr_settled_at`, `idx_health_metric_ts`

Plus 3 unique constraints: `fixtures.sportmonks_id`, `teams.sportmonks_id`, `leagues.sportmonks_id`.
