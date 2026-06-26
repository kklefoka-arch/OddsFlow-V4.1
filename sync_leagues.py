"""Sync the active-league set from the live Sportmonks subscription.

Why this exists
---------------
The active-league set used to be hard-coded in four places (static_policy,
fetch_upcoming, fetch_results, reconcile_orphans). Every time the operator
changed their Sportmonks plan, those lists drifted from reality and fixtures
silently failed to fetch / settle / filter correctly.

This script asks Sportmonks which leagues the subscription actually covers
(the /leagues endpoint returns exactly the subscribed leagues) and records
the answer in the DB as ``leagues.active`` (1/0). Other code reads that flag
instead of a hard-coded list, so the engine always matches the real plan.

Run it whenever the subscription changes (and nightly via the scheduler).
"""
import sqlite3, urllib.request, urllib.parse, urllib.error, json, time
import os as _os

TOKEN = _os.environ.get("SPORTMONKS_TOKEN", "2AWINN4fYPiQkY2lfHee9TASZubv74uP1RIY4ILY15Mzg4bw5bH2v2SeKGAN")
DB    = r"C:\OddsFlowV4\data\oddsflow_v4.db"
BASE  = "https://api.sportmonks.com/v3/football"


def api_get(path, params):
    params["api_token"] = TOKEN
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "OddsFlowV4/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def fetch_subscribed_leagues() -> list[dict]:
    out, page = [], 1
    while True:
        d = api_get("leagues", {"per_page": 50, "page": page, "include": "country"})
        batch = d.get("data", [])
        out.extend(batch)
        if not d.get("pagination", {}).get("has_more"):
            break
        page += 1
        time.sleep(0.25)
    return out


def main():
    # SAFETY (API-downtime hardening): never let a failed or degraded API
    # response wipe the active-league set. A lapsed subscription can return a
    # network/HTTP error OR a 200 with an empty/partial list — either way we
    # must NOT run "UPDATE leagues SET active = 0" against nothing, or the whole
    # engine goes dark and stays dark. On any such case we leave leagues.active
    # exactly as it is and exit cleanly so the scheduler logs a skip, not a wipe.
    try:
        leagues = fetch_subscribed_leagues()
    except Exception as e:
        print(f"sync_leagues: API call failed ({e}). "
              f"Preserving existing leagues.active — NO changes made.")
        return
    sub_ids = {int(l["id"]) for l in leagues}
    if not sub_ids:
        print("sync_leagues: API returned 0 leagues (subscription off or degraded). "
              "Preserving existing leagues.active — NO changes made.")
        return
    # Guard against a drastic, suspicious drop (e.g. partial outage returning a
    # handful of leagues): if the new set is <50% of the current active count,
    # skip rather than gut the plan. Re-run manually once the plan is confirmed.
    try:
        _c = sqlite3.connect(DB, timeout=30)
        _cur = _c.execute("SELECT COUNT(*) FROM leagues WHERE active=1").fetchone()[0]
        _c.close()
    except Exception:
        _cur = 0
    if _cur >= 10 and len(sub_ids) < _cur * 0.5:
        print(f"sync_leagues: API returned {len(sub_ids)} leagues vs {_cur} currently active "
              f"(>50% drop). Suspicious — preserving existing set. Re-run manually to confirm.")
        return
    print(f"Sportmonks subscription returns {len(leagues)} leagues:\n")
    for l in sorted(leagues, key=lambda x: (((x.get('country') or {}).get('name') or ''), x.get('name') or '')):
        country = (l.get("country") or {}).get("name", "?")
        print(f"   {l['id']:>6}  {country:<22} {l.get('name')}")

    conn = sqlite3.connect(DB, timeout=30); conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")  # wait for the live server's locks
    cols = [r[1] for r in conn.execute("PRAGMA table_info(leagues)")]
    if "active" not in cols:
        conn.execute("ALTER TABLE leagues ADD COLUMN active INTEGER DEFAULT 0")
        cols.append("active")
        print("\n(added leagues.active column)")

    # Upsert: insert league rows for subscribed leagues missing from our table,
    # so newly-added subscription leagues are tracked (and flagged active) even
    # before fetch_upcoming first runs. Build the INSERT from columns that exist.
    have = {int(r[0]) for r in conn.execute(
        "SELECT sportmonks_id FROM leagues WHERE sportmonks_id IS NOT NULL")}
    name_col = "name" if "name" in cols else None
    country_col = next((c for c in ("country", "country_name") if c in cols), None)
    has_tier = "tier" in cols
    # tier is editorial (API has none); pull from fetch_upcoming's map, else 3.
    try:
        from fetch_upcoming import ACTIVE_LEAGUES as _TIER_MAP
    except Exception:
        _TIER_MAP = {}
    inserted_new = 0
    for l in leagues:
        smid = int(l["id"])
        if smid in have:
            continue
        fields, vals = ["sportmonks_id", "active"], [smid, 1]
        if name_col:
            fields.append(name_col); vals.append(l.get("name"))
        if country_col:
            fields.append(country_col); vals.append((l.get("country") or {}).get("name"))
        if has_tier:
            fields.append("tier"); vals.append(int(_TIER_MAP.get(smid, 3)))
        ph = ",".join("?" * len(vals))
        try:
            conn.execute(f"INSERT INTO leagues ({','.join(fields)}) VALUES ({ph})", vals)
            inserted_new += 1
        except Exception as e:
            print(f"   (could not insert league {smid}: {e})")
    if inserted_new:
        print(f"\nInserted {inserted_new} new subscription league row(s) into leagues table.")

    # Mark active flag against our local leagues table (keyed by sportmonks_id)
    conn.execute("UPDATE leagues SET active = 0")
    qmarks = ",".join("?" * len(sub_ids))
    conn.execute(f"UPDATE leagues SET active = 1 WHERE sportmonks_id IN ({qmarks})",
                 list(sub_ids))
    conn.commit()
    n_active = conn.execute("SELECT COUNT(*) FROM leagues WHERE active=1").fetchone()[0]
    print(f"\nleagues.active set: {n_active} rows flagged active in local DB")

    # Ready-to-paste literal (fallback for code that still hard-codes)
    print("\nACTIVE_SM = {")
    print("    " + ", ".join(str(i) for i in sorted(sub_ids)))
    print("}")

    # --- DEBUG: why aren't active-league finished fixtures settling? ---
    print("\n--- active-league fixtures pending (home_score NULL, past kickoff) ---")
    rows = conn.execute(f"""
        SELECT f.id, f.sportmonks_id, f.status, f.date, l.name, l.sportmonks_id sm
        FROM fixtures f JOIN leagues l ON l.id=f.league_id
        WHERE f.home_score IS NULL AND f.sportmonks_id IS NOT NULL
          AND substr(f.date,1,10) < date('now')
          AND l.sportmonks_id IN ({qmarks})
        ORDER BY f.date DESC LIMIT 15
    """, list(sub_ids)).fetchall()
    print(f"count(sample<=15): {len(rows)}")
    for r in rows:
        smid = int(r["sportmonks_id"])
        try:
            d = api_get(f"fixtures/{smid}", {"include": "scores"})
            fx = d.get("data") or {}
            sc = [(s["score"]["participant"], s["score"]["goals"]) for s in (fx.get("scores") or [])
                  if s.get("description") == "CURRENT" and s.get("score")]
            api_state = fx.get("state_id")
        except Exception as e:
            sc, api_state = f"ERR {e}", "?"
        print(f"   db.id={r['id']} sm_id={smid} status={r['status']!r} {r['date'][:10]} "
              f"{r['name']} -> state={api_state} CURRENT={sc}")
    conn.close()
    print("\nSYNC DONE")


if __name__ == "__main__":
    main()
