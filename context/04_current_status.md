# Current Status — OddsFlow V4

Update this file at the end of every session.
Last updated: 2026-06-08 (Session — alignment audit: User-Agent fix + ACTIVE_LEAGUE_SPORTMONKS_IDS)

---

## State: Running ✅ — v4 policy live, all endpoints verified

| Item | Detail |
|------|--------|
| Folder | `C:\OddsFlowV4` |
| Port | 8083 (local) |
| ngrok | https://steadier-legwarmer-finlike.ngrok-free.dev |
| DB | `data/oddsflow_v4.db` |
| GitHub | `github.com/kklefoka-arch/OddsFlowV4` |
| Active policy | **v4, 8 cells, 2-key (zone × bts)** — `static_policy.V3_ACTIVE`. Goals NL O1.5 / Corners NL O7.5(strong)·O8.5 / threeway alpha-or-draw. |
| Zone boundaries | strong 2.90–3.30, standard 3.30–3.80, low 3.80–4.30, one_sided ≥4.30 (v4 overlay) |
| Fixtures (foundation) | ~29,470 settled in foundation matrix (8 cells, all n≥800) |
| Leagues active | 29 (USL League Two 797 removed 2026-05-29; Big 5 EU never in set) |
| Today | 17 fixtures kicking off, 1 promoted (KTP vs Haka, standard:over, Finland Superettan) |
| emit_log | Growing — new emits write under 2-key partition |
| Drift | All 8 cells no_data (recent_n < 10) — expected for new v4 system; grows as picks settle |

## How to start

Server runs from Task Scheduler (`OddsFlow_Server`). Manual fallback:

```powershell
Set-Location C:\OddsFlowV4
uvicorn app.main:app --host 0.0.0.0 --port 8083
```

## Daily flow (chained in `run_daily.ps1`)

```powershell
python fetch_upcoming.py    # refresh odds + kickoff datetimes
python emit_picks.py        # call /picks?days=3 -> emit_log
python fetch_results.py     # write scores + fixture_stats
python settle.py            # write pick_results
```

12 scheduler jobs handle this automatically — see CLAUDE.md → Scheduler.

---

## Dead files — flagged for manual deletion

These files are no longer referenced by any route or the SPA. They can be manually deleted from Windows Explorer when convenient. They do not affect operation — they are just stale clutter.

| File | Reason |
|------|--------|
| `app/frontend/templates/board.html` | /board route removed |
| `app/frontend/templates/base.html` | Old multi-page layout, SPA doesn't extend it |
| `app/frontend/templates/fixtures.html` | Dead page route |
| `app/frontend/templates/foundation.html` | /foundation HTML route removed; JSON /api/foundation still live |
| `app/frontend/templates/inspector.html` | Dead page route |
| `app/frontend/templates/ingest.html` | Dead page route |
| `app/frontend/templates/picks.html` | Dead page route |
| `app/frontend/templates/partials/` | All partials are for dead pages |
| `app/frontend/static/board.css` | Dead |
| `app/frontend/static/board.js` | Dead |
| `app/frontend/static/app.js` | Old pre-SPA JS |
| `app/frontend/static/style.css` | Old pre-SPA CSS |
| `bluetooth_content_share.html` | Unrelated file |
| `leagues_no_upcoming.md` | Stale notes |
| `C:Tempv3.log` | Stale log |
| `graphify-out/` | Third-party analysis output |

---

## Known issues / observations

| # | Item | Notes |
|---|------|-------|
| 1 | `static_policy.V3_MARKETS` hit rates are pre-overlay | Historical baselines (e.g., low:slight_over 84.9% n=1733) were computed against the old 4.10–4.80 low range. Treat as reference; the next 6 weeks of settlement will yield the new baseline. Don't gate emission on these numbers. |
| 2 | Old emit_log rows keep their pre-overlay `zone` value | Historical record — intentional. New emits use the new boundaries. Inspector/reports may show a small zone-boundary discontinuity around the restore date; expected. |
| 3 | `pick_odd` NULL on 100% of corners_nl and ~95% of goals_nl rows | By design — natural-line-only policy (Over 1.5 Goals / Over 8.5 Corners rarely quoted by Sportmonks). SPA renders `—`. Future EV layer (Project 3) is gated on the 6-week validation. |
| 4 | 96% of upcoming fixtures have no `draw_zone` | Not a bug — most upcoming fixtures don't yet carry a quoted `draw_odd`. Within the 7-day window, ~41% carry odds and classify. |
| 5 | `LOW_ZONE_SUPPRESS` differs between modules | `static_policy.py = False` (pick firing — low zone active). `promotion.py = True` (foundation matrix display — low cells shown as `MEASURING`). Intentional split. |
| 6 | `pick_results.outcome` stores string `WIN`/`LOSS`/`VOID` | Float lives in `actual_value`. Filter on `outcome='WIN'` or use `actual_value` — never numeric compare against `outcome`. |
| 7 | `df_level` columns on fixtures + emit_log | Retained as metadata. New emits write DF0/DF1/DF2 from classify_fixture. Not a partition axis (Durable Rule 1). |

---

## Session log (this session)

| Session | Date | Work done |
|---------|------|-----------|
| This session (alignment) | 2026-06-08 | **Alignment audit — all old roads closed.** (1) HTTP 403 fix: all 4 API scripts (fetch_upcoming, refresh_odds, refresh_stats, fetch_results) now send `User-Agent: OddsFlowV4/1.0` — Sportmonks blocks `Python-urllib/*`. (2) Single source of truth for active leagues: `ACTIVE_LEAGUE_SPORTMONKS_IDS` frozenset added to `static_policy.py` (29 leagues, 797 USL League Two excluded). (3) routes_upcoming.py + routes_picks.py now filter by `lg.sportmonks_id IN (...)` from that frozenset — 797 can no longer surface in Upcoming or Picks tabs. (4) fetch_results.py + reconcile_orphans.py ACTIVE_LEAGUES sets aligned to full 29 leagues with sync comments. (5) Diagnostic test files cleaned up. CLAUDE.md + context/04 updated. Committed + pushed. |
| This session (continued) | 2026-06-08 | **Phase B: Live app verification — all 9 SPA tabs + all API endpoints.** Verified all tabs load correctly with real data: Picks (1 fixture, standard:over, 3 markets), Picks Log (3 configs displayed), Upcoming (177 fixtures, 6 promoted, tier summary), Analysis (29,470 fixtures, 8 cells, T1+T2/T3 split), Inspector (drift table, 8 cells no_data — expected), Reports (multi-window perf, 881 settled, 71.3% legs hit), Results (settled fixtures, Live Scores button), Today (runbook + hit rate summary), Stats (DB counts, cron heartbeat). All endpoints return valid data. **Operational note surfaced:** pipeline cron jobs are stale — fetch_upcoming shows 220.6h overdue, suggesting Task Scheduler isn't running (or health records not writing). The KTP vs Haka pick IS in the DB and shows correctly, so picks exist for today's fixture. Operator should verify Task Scheduler and run `run_daily.ps1` manually if needed. No code changes this sub-session. |
| This session | 2026-06-08 | **Full pipeline audit + holistic fixes + documentation cleanup.** Phase A: read all 8 pipeline scripts + 9 route files + settings + SPA template + OPERATOR_MANUAL. Phase C issue catalogue: H1 (fetch_upcoming windows hardcoded to 2026), H2 (refresh_odds no reclassify after odds update), M1-M4 (CLAUDE.md/OPERATOR_MANUAL stale docs). Phase D fixes: (1) fetch_upcoming.py — dynamic `_build_windows()` replaces hardcoded 2026 windows list, auto-rolls into 2027. (2) refresh_odds.py — added `_zone()`/`_bts()` inline helpers + reclassifies draw_zone/bts_pocket in UPDATE after each intraday refresh. Phase E docs: CLAUDE.md key-files table + decisions section updated to v4 reality; OPERATOR_MANUAL hit-rate convention clarified (threeway binary vs legacy dnb non-loss) + webhook 503 note added; routes_upcoming.py confirmed already clean (frozenset removed in prior session). Context docs: all 6 context docs rewritten to reflect v4 accurately (8 cells, binary BTS axis, 3 markets, signals not gates). plan_group1/2/3 archived. |
| 1–8 | 2026-05-22 → 2026-05-24 | V4 built, SPA + 7 tabs, league fixes, classification + matrix wired |
| 9 | 2026-05-25 | 8-group fix plan, supersede logic, monthly fetch windows |
| 10 | 2026-05-25 | V3 policy deployed (9 cells, 4 markets) |
| 11 | 2026-05-26 | First V3 settlement (22W 8L 6V); plain-language summary screenshot captured |
| 12 | 2026-05-26 | Project 2 calibration completed — declared **reference-only, not a gate** |
| 13 | 2026-05-26 | 5 scheduler tasks activated |
| 14 | 2026-05-26 | League migration a