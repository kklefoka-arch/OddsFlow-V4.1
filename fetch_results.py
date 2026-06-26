"""Fetch match results from Sportmonks and write to fixtures + fixture_stats.

Run after match days to update home_score, away_score, and corner stats
for fixtures that have been played but not yet settled in the DB.
After running this, run settle.py to write pick_results from emit_log.

--------------------------------------------------------------------------
2026-06-09 rewrite — fetch results BY FIXTURE ID, one fixture per call.
--------------------------------------------------------------------------
History of the bug this fixes:
  * The original version fetched a whole week window then kept only fixtures
    whose league was in a hard-coded ACTIVE_LEAGUES set. That set had drifted
    from the live subscription (USL League Two / 797 was wrongly marked
    dropped), so real fixtures were filtered out and never settled.
  * A first rewrite batched ids via fixtures/multi/{ids}. Sportmonks fails the
    WHOLE batch if any single id is outside the subscription, so one dead id
    sank every good fixture sharing its chunk.

This version queries fixtures/{id} individually. One bad id can no longer
affect any other. Fixtures the API cannot return (genuinely removed leagues,
e.g. La Liga 2 / 567) come back empty; once older than RESULT_GIVEUP_DAYS they
are marked status='no_result' so they stop re-appearing, and reconcile_orphans
settles their picks as synthetic ORPHANs.

Active-league source of truth: app/engine/static_policy.ACTIVE_LEAGUE_SPORTMONKS_IDS
(mirrored below). On startup we clear any 'no_result' flag on fixtures whose
league is active again, so re-adding a league (like 797) automatically re-opens
its fixtures for fetching.
"""
import sqlite3, urllib.request, urllib.parse, urllib.error, json, time
from datetime import datetime, timezone, date as date_cls

import os as _os
TOKEN = _os.environ.get("SPORTMONKS_TOKEN", "2AWINN4fYPiQkY2lfHee9TASZubv74uP1RIY4ILY15Mzg4bw5bH2v2SeKGAN")
DB    = r"C:\OddsFlowV4\data\oddsflow_v4.db"
BASE  = "https://api.sportmonks.com/v3/football"

CORNERS_TYPE_ID = 34          # verified 2026-05-23
RESULT_GIVEUP_DAYS = 5        # after this, an un-returnable fixture is marked no_result

# Active leagues are read at runtime from leagues.active (maintained by
# sync_leagues.py from the live Sportmonks subscription). Fallback snapshot
# below is only used if that column can't be read. (2026-06-09)
_ACTIVE_FALLBACK = {
    286, 289, 292, 295, 345, 351, 360, 363, 393, 396, 444, 447, 573, 579,
    585, 588, 648, 779, 791, 989, 1034, 1362, 1607, 1642, 2545, 3306, 3537, 3550,
}


def load_active_sm(conn) -> set[int]:
    try:
        ids = {int(r[0]) for r in conn.execute(
            "SELECT sportmonks_id FROM leagues WHERE active=1 AND sportmonks_id IS NOT NULL")}
        return ids or set(_ACTIVE_FALLBACK)
    except Exception:
        return set(_ACTIVE_FALLBACK)


def api_get(path: str, params: dict, retries: int = 3) -> dict | None:
    """GET with retry. Returns parsed json, or None on HTTP 404/empty fixture."""
    params["api_token"] = TOKEN
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "OddsFlowV4/1.0"})
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (404, 403):      # fixture not in subscription / not found
                return None
            last_err = e
        except Exception as e:
            last_err = e
        if attempt < retries - 1:
            time.sleep(8 * (2 ** attempt))
    if last_err:
        raise last_err
    return None


def extract_scores(scores_list: list) -> tuple[int | None, int | None]:
    home_score = away_score = None
    for s in (scores_list or []):
        if s.get("description") != "CURRENT":
            continue
        sd = s.get("score") or {}
        goals, participant = sd.get("goals"), sd.get("participant")
        if goals is None:
            continue
        try:
            goals = int(goals)
        except (TypeError, ValueError):
            continue
        if participant == "home":
            home_score = goals
        elif participant == "away":
            away_score = goals
    return home_score, away_score


def extract_corners(stats_list: list, home_p_id, away_p_id) -> tuple[int | None, int | None]:
    home_corners = away_corners = None
    for s in (stats_list or []):
        if s.get("type_id") != CORNERS_TYPE_ID:
            continue
        val = (s.get("data") or {}).get("value")
        if val is None:
            continue
        try:
            val = int(val)
        except (TypeError, ValueError):
            continue
        pid = s.get("participant_id")
        if pid == home_p_id:
            home_corners = val
        elif pid == away_p_id:
            away_corners = val
    return home_corners, away_corners


def main() -> None:
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")  # wait for the live server's locks
    conn.row_factory = sqlite3.Row
    now_utc = datetime.now(timezone.utc)
    today   = now_utc.strftime("%Y-%m-%d")
    now_ts  = now_utc.strftime("%Y-%m-%d %H:%M:%S")
    active = load_active_sm(conn)
    active_csv = ",".join(str(i) for i in active)

    # Self-heal: re-open fixtures previously given up on whose league is active
    # again (e.g. 797 re-added). Removed leagues stay no_result.
    reopened = conn.execute(f"""
        UPDATE fixtures SET status=NULL
        WHERE COALESCE(status,'')='no_result'
          AND league_id IN (SELECT id FROM leagues WHERE sportmonks_id IN ({active_csv}))
    """).rowcount
    conn.commit()
    if reopened:
        print(f"Re-opened {reopened} fixture(s) in re-activated leagues.\n")

    unsettled = conn.execute("""
        SELECT f.id, f.sportmonks_id, f.date, f.home_team_name, f.away_team_name,
               l.sportmonks_id AS sm_league, l.name AS league_name
        FROM fixtures f
        LEFT JOIN leagues l ON l.id = f.league_id
        WHERE f.home_score IS NULL
          AND f.sportmonks_id IS NOT NULL
          AND substr(f.date, 1, 10) < ?
          AND COALESCE(f.status, '') <> 'no_result'
          AND l.sportmonks_id IN ({active_csv})
        ORDER BY f.date ASC
    """.format(active_csv=active_csv), (today,)).fetchall()

    print(f"Unsettled fixtures eligible for result fetch: {len(unsettled)}")
    if not unsettled:
        conn.close()
        print("Nothing to fetch — run again after match days.")
        return

    # API-downtime guard: probe once before processing. If the API is
    # unreachable (e.g. the subscription has lapsed), skip the ENTIRE run so we
    # never mark perfectly-reachable fixtures 'no_result' (which would ORPHAN
    # their picks and corrupt the hit-rate record). Requires non-empty data so a
    # 200-with-empty-body lapse also counts as down. Resumes automatically when
    # the API is back — nothing is lost, the fixtures stay unsettled and queued.
    try:
        _probe = api_get("leagues", {"per_page": 1})
        _api_ok = bool(_probe and _probe.get("data"))
    except Exception as _e:
        _api_ok = False
        print(f"  api probe error: {_e}")
    if not _api_ok:
        print("API unreachable (subscription off?) — skipping run; "
              "no fixtures fetched or aged to no_result.")
        try:
            conn.execute("INSERT INTO system_health (metric, value) VALUES (?, ?)",
                         ("fetch_results", "skip: api_unreachable (no aging while API down)"))
            conn.commit()
        except Exception:
            pass
        conn.close()
        return

    updated = inserted_stats = not_finished = no_data = giveup = 0
    # per-league tally: name -> [settled, no_data]
    by_league: dict[str, list[int]] = {}

    for i, row in enumerate(unsettled, 1):
        lname = row["league_name"] or f"league_id={row['sm_league']}"
        by_league.setdefault(lname, [0, 0])
        smid = int(row["sportmonks_id"])
        try:
            data = api_get(f"fixtures/{smid}", {"include": "scores;statistics;participants"})
        except Exception as e:
            print(f"    API error id={smid}: {e}")
            data = None

        fx = (data or {}).get("data") if data else None
        if not fx:
            no_data += 1
            by_league[lname][1] += 1
            date_str = (row["date"] or "")[:10]
            try:
                age = (now_utc.date() - date_cls.fromisoformat(date_str)).days
            except Exception:
                age = 999
            if age >= RESULT_GIVEUP_DAYS:
                conn.execute("UPDATE fixtures SET status='no_result', updated_at=? WHERE id=?",
                             (now_ts, row["id"]))
                giveup += 1
            time.sleep(0.12)
            continue

        home_score, away_score = extract_scores(fx.get("scores") or [])
        if home_score is None or away_score is None:
            not_finished += 1
            time.sleep(0.12)
            continue

        total_goals = home_score + away_score
        participants = fx.get("participants") or []
        home_p_id = next((int(p["id"]) for p in participants
                          if p.get("meta", {}).get("location") == "home"), None)
        away_p_id = next((int(p["id"]) for p in participants
                          if p.get("meta", {}).get("location") == "away"), None)
        home_corners, away_corners = (None, None)
        if home_p_id and away_p_id:
            home_corners, away_corners = extract_corners(fx.get("statistics") or [],
                                                         home_p_id, away_p_id)

        conn.execute("""
            UPDATE fixtures SET home_score=?, away_score=?, total_goals=?,
                   status='settled', updated_at=? WHERE id=?
        """, (home_score, away_score, total_goals, now_ts, row["id"]))
        updated += 1
        by_league[lname][0] += 1

        if home_corners is not None and away_corners is not None:
            conn.execute("""
                INSERT OR REPLACE INTO fixture_stats
                    (fixture_id, home_corners, away_corners, total_corners, raw_stats_json)
                VALUES (?, ?, ?, ?, ?)
            """, (row["id"], home_corners, away_corners, home_corners + away_corners,
                  json.dumps(fx.get("statistics") or [])))
            inserted_stats += 1

        if updated <= 40 or updated % 25 == 0:
            print(f"    OK {row['home_team_name']} {home_score}-{away_score} "
                  f"{row['away_team_name']}  [{lname}]")
        if i % 25 == 0:
            conn.commit()
        time.sleep(0.12)

    conn.execute("INSERT INTO system_health (metric, value) VALUES (?, ?)",
                 ("fetch_results",
                  f"ok: {updated} scores, {inserted_stats} stats, "
                  f"{not_finished} not_finished, {no_data} no_data, {giveup} no_result"))
    conn.commit()
    conn.close()

    print("\nDone")
    print(f"  Scores written:            {updated}")
    print(f"  Corner stats written:      {inserted_stats}")
    print(f"  Played, not finished yet:  {not_finished}")
    print(f"  API returned no fixture:   {no_data}  (marked no_result: {giveup})")
    print("\n  By league (settled / no_data):")
    for name in sorted(by_league):
        s, n = by_league[name]
        print(f"    {name:<32} settled={s:<4} no_data={n}")
    if updated > 0:
        print("\nNext step: run  python settle.py  to write pick_results from emit_log.")


if __name__ == "__main__":
    main()
