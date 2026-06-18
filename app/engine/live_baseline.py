"""OddsFlow V4 — LIVE per-cell hit-rate baseline (added 2026-06-18).

Replaces the frozen static_policy.V3_MARKETS["hit"]/["n"] constants with a
baseline computed live from the ACTUAL v4 pick definitions over ALL settled +
classifiable fixtures. This means:
  - the picture GROWS: every newly settled fixture feeds the baseline,
  - it is v4-only by construction (legacy dnb/alpha_win markets are not computed),
  - corners use the real pick line (O7.5 strong / O8.5 rest) — reconciled with live.

Cached for 30 min. Fully defensive: any failure returns None so callers fall
back to the frozen baseline and picks never break.
"""
from __future__ import annotations
import sqlite3
import time

from app.engine.classify import zone_of, bts_yesno

_TTL = 1800.0
_CACHE: dict = {"ts": 0.0, "data": None}

_QUERY = """
SELECT f.draw_odd, f.btts_yes_odd y, f.btts_no_odd n, f.home_odd ho, f.away_odd ao,
       f.home_score hs, f.away_score aw, fs.home_corners hc, fs.away_corners ac
FROM fixtures f LEFT JOIN fixture_stats fs ON fs.fixture_id = f.id
WHERE f.home_score IS NOT NULL AND f.away_score IS NOT NULL AND f.draw_odd IS NOT NULL
  AND f.btts_yes_odd IS NOT NULL AND f.btts_no_odd IS NOT NULL
  AND f.home_odd IS NOT NULL AND f.away_odd IS NOT NULL
"""


def _compute(db_path: str) -> dict:
    conn = sqlite3.connect(db_path, timeout=20)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(_QUERY).fetchall()
    finally:
        conn.close()
    acc: dict = {}
    for r in rows:
        z = zone_of(r["draw_odd"]); b = bts_yesno(r["y"], r["n"])
        if z is None or b is None:
            continue
        cell = acc.setdefault((z, b), {"goals_nl": [0, 0], "corners_nl": [0, 0], "threeway": [0, 0]})
        cell["goals_nl"][1] += 1
        cell["goals_nl"][0] += 1 if (r["hs"] + r["aw"]) >= 2 else 0
        ah = r["ho"] < r["ao"] if r["ho"] != r["ao"] else True
        win = (r["hs"] >= r["aw"]) if ah else (r["aw"] >= r["hs"])
        cell["threeway"][1] += 1
        cell["threeway"][0] += 1 if win else 0
        if r["hc"] is not None and r["ac"] is not None:
            line = 7.5 if z == "strong" else 8.5
            cell["corners_nl"][1] += 1
            cell["corners_nl"][0] += 1 if (r["hc"] + r["ac"]) > line else 0
    return {ck: {m: {"hit": round(100 * h / t, 1) if t else None, "n": t}
                 for m, (h, t) in mk.items()} for ck, mk in acc.items()}


def live_cell_hit(db_path: str, zone: str, bts: str, market: str):
    """Return (hit_pct, n) computed live, or None to signal 'use frozen fallback'.

    None when: cache build fails, the cell/market is absent, or n < 50 (too thin
    to trust over the frozen baseline).
    """
    try:
        now = time.time()
        if _CACHE["data"] is None or (now - _CACHE["ts"]) > _TTL:
            _CACHE["data"] = _compute(db_path)
            _CACHE["ts"] = now
        cell = (_CACHE["data"] or {}).get((zone, bts))
        if not cell:
            return None
        mc = cell.get(market)
        if not mc or mc["hit"] is None or mc["n"] < 50:
            return None
        return mc["hit"], mc["n"]
    except Exception:
        return None
