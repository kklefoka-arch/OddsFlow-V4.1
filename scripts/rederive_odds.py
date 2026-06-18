"""OddsFlow V4 — re-derive goals & corners odds (over+under) from raw_odds_json
using the CORRECT market_ids discovered 2026-06-18:
    goals  total = market_id 80   (has the 1.5 line; mkt 7 did not)
    corners total = market_id 67  (mkt 45 is corners odd/even, not totals)

Idempotent + additive: adds any missing columns, and only writes a column when a
value is found (never nulls existing data). Re-parses the raw_odds_json already
stored on each fixture. Touches nothing in the live chain. Run via run_rederive_odds.bat.
"""
from __future__ import annotations
import json, sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB = r"C:\OddsFlowV4\data\oddsflow_v4.db"
OUT = r"C:\OddsFlowV4\analysis\rederive_odds_summary.txt"

GOALS_MID, CORNERS_MID = 80, 67
GOAL_LINES = {1.5: "15", 2.5: "25", 3.5: "35"}
CORNER_LINES = {7.5: "75", 8.5: "85", 9.5: "95"}

COLS = ([f"goals_over_{s}_odd" for s in GOAL_LINES.values()] +
        [f"goals_under_{s}_odd" for s in GOAL_LINES.values()] +
        [f"corners_over_{s}_odd" for s in CORNER_LINES.values()] +
        [f"corners_under_{s}_odd" for s in CORNER_LINES.values()])

def first_num(s):
    if s is None: return None
    s = str(s).replace(",", " ").replace("/", " ").replace(";", " ")
    for tok in s.split():
        try: return float(tok)
        except ValueError: continue
    return None

def parse(odds_list):
    buckets = {c: [] for c in COLS}
    for o in (odds_list or []):
        mid = o.get("market_id"); lab = (o.get("label") or "").lower().strip()
        if lab not in ("over", "under"): continue
        try: val = float(o.get("value"))
        except (TypeError, ValueError): continue
        line = first_num(o.get("total"))
        if mid == GOALS_MID and line in GOAL_LINES:
            buckets[f"goals_{lab}_{GOAL_LINES[line]}_odd"].append(val)
        elif mid == CORNERS_MID and line in CORNER_LINES:
            buckets[f"corners_{lab}_{CORNER_LINES[line]}_odd"].append(val)
    return {c: (max(v) if v else None) for c, v in buckets.items()}

conn = sqlite3.connect(DB, timeout=60); conn.row_factory = sqlite3.Row
existing = {r[1] for r in conn.execute("PRAGMA table_info(fixtures)")}
for c in COLS:
    if c not in existing:
        conn.execute(f"ALTER TABLE fixtures ADD COLUMN {c} REAL")
conn.commit()

rows = conn.execute("SELECT id, raw_odds_json FROM fixtures WHERE raw_odds_json IS NOT NULL").fetchall()
processed = 0
colfill = {c: 0 for c in COLS}
for i, r in enumerate(rows):
    processed += 1
    try: odds = json.loads(r["raw_odds_json"])
    except Exception: continue
    vals = parse(odds)
    sets = {c: v for c, v in vals.items() if v is not None}   # only write found values
    if sets:
        assign = ",".join(f"{c}=?" for c in sets)
        conn.execute(f"UPDATE fixtures SET {assign} WHERE id=?", (*sets.values(), r["id"]))
        for c in sets: colfill[c] += 1
    if i % 2000 == 0: conn.commit()
conn.commit()

sample = conn.execute(
    """SELECT id, goals_over_15_odd, goals_over_25_odd, goals_under_25_odd,
              corners_over_85_odd, corners_under_85_odd
       FROM fixtures WHERE goals_over_15_odd IS NOT NULL OR corners_over_85_odd IS NOT NULL LIMIT 6"""
).fetchall()
conn.close()

lines = [f"RE-DERIVE ODDS (goals mkt80, corners mkt67) — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
         f"fixtures with raw_odds_json: {processed}", "", "per-column fill counts:"]
for c in COLS:
    lines.append(f"  {c:24} {colfill[c]:7}  ({100*colfill[c]/max(processed,1):.1f}%)")
lines.append("\nsample:")
for s in sample:
    lines.append(f"  fx {s['id']}: G1.5 over={s['goals_over_15_odd']}  G2.5 over={s['goals_over_25_odd']}/under={s['goals_under_25_odd']}  "
                 f"C8.5 over={s['corners_over_85_odd']}/under={s['corners_under_85_odd']}")
out = "\n".join(lines)
print(out)
Path(OUT).parent.mkdir(parents=True, exist_ok=True)
Path(OUT).write_text(out, encoding="utf-8")
print(f"\nsaved to {OUT}")
