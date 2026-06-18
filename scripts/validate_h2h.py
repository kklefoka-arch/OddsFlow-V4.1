"""OddsFlow V4 — H2H-corners signal validation (within-cell separation frame).

Signal = the team-pair's MOST RECENT prior meeting (we only store league fixtures,
so 'league-only' is automatic), within 15 months, that has corner data. Its total
corners are banded two ways and tested per cell x market:
    Band A : >=10 'over'  | <=9 'under'
    Band B : >=10 'high'  | <=5 'low' | 6-9 'neutral'
Read-only. Writes analysis/h2h_validation.txt. Run via run_validate_h2h.bat.
"""
from __future__ import annotations
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

DB = r"C:\OddsFlowV4\data\oddsflow_v4.db"
OUT = r"C:\OddsFlowV4\analysis\h2h_validation.txt"
WINDOW = timedelta(days=456)   # ~15 months

def zone(d):
    if d is None or d < 2.90: return None
    if d < 3.30: return "strong"
    if d < 3.80: return "standard"
    if d < 4.30: return "low"
    return "one_sided"
def bts(y, n): return None if y is None or n is None else ("over" if y <= n else "under")
def pdate(s):
    if not s: return None
    s = str(s).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try: return datetime.strptime(s[:19], fmt)
        except ValueError: continue
    return None

conn = sqlite3.connect(DB, timeout=60); conn.row_factory = sqlite3.Row
rows = conn.execute("""SELECT f.id, f.date, f.home_team_id ht, f.away_team_id at,
 f.draw_odd, f.btts_yes_odd y, f.btts_no_odd n, f.home_odd ho, f.away_odd ao,
 f.home_score hs, f.away_score aw, fs.home_corners hc, fs.away_corners ac
 FROM fixtures f LEFT JOIN fixture_stats fs ON fs.fixture_id=f.id
 WHERE f.home_team_id IS NOT NULL AND f.away_team_id IS NOT NULL""").fetchall()
conn.close()

# pair -> sorted [(date, total_corners)] for meetings WITH corner data
pair = defaultdict(list)
parsed = []
for r in rows:
    d = pdate(r["date"]); tc = (r["hc"] + r["ac"]) if (r["hc"] is not None and r["ac"] is not None) else None
    parsed.append((r, d, tc))
    if d and tc is not None:
        key = tuple(sorted((r["ht"], r["at"])))
        pair[key].append((d, tc))
for k in pair: pair[k].sort()

def prior_corners(ht, at, d):
    """Most recent prior meeting's total corners within the window, else None."""
    key = tuple(sorted((ht, at)))
    best = None
    for (md, tc) in pair.get(key, []):
        if md >= d: break
        if d - md <= WINDOW: best = tc
    return best

MK = ["goals", "corners", "3way"]
CELLS = ["strong:over","strong:under","standard:over","standard:under",
         "low:over","low:under","one_sided:over","one_sided:under"]
bandA = defaultdict(lambda: [0, 0])  # (cell, a, market)
bandB = defaultdict(lambda: [0, 0])  # (cell, b, market)
base = defaultdict(lambda: [0, 0])
cellN = defaultdict(int)

for (r, d, tc) in parsed:
    if r["hs"] is None or r["aw"] is None: continue
    z = zone(r["draw_odd"]); b = bts(r["y"], r["n"])
    if z is None or b is None or d is None: continue
    cell = f"{z}:{b}"; cellN[cell] += 1
    pc = prior_corners(r["ht"], r["at"], d)
    a_band = "none" if pc is None else ("over" if pc >= 10 else "under")
    b_band = "none" if pc is None else ("high" if pc >= 10 else ("low" if pc <= 5 else "neutral"))
    o = {}
    o["goals"] = 1 if (r["hs"] + r["aw"]) >= 2 else 0
    ah = r["ho"] < r["ao"] if r["ho"] != r["ao"] else True
    o["3way"] = 1 if ((r["hs"] >= r["aw"]) if ah else (r["aw"] >= r["hs"])) else 0
    has_c = r["hc"] is not None and r["ac"] is not None
    if has_c:
        line = 7.5 if z == "strong" else 8.5
        o["corners"] = 1 if (r["hc"] + r["ac"]) > line else 0
    for m in MK:
        if m == "corners" and not has_c: continue
        base[(cell, m)][0] += o[m]; base[(cell, m)][1] += 1
        bandA[(cell, a_band, m)][0] += o[m]; bandA[(cell, a_band, m)][1] += 1
        bandB[(cell, b_band, m)][0] += o[m]; bandB[(cell, b_band, m)][1] += 1

def pct(w, t): return (100 * w / t) if t else None

lines = [f"H2H-CORNERS VALIDATION — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
         f"population: {sum(cellN.values()):,} classifiable settled fixtures", ""]
for cell in CELLS:
    lines.append(f"=== {cell}   (cell N = {cellN[cell]}) ===")
    for m in MK:
        bw, bt = base[(cell, m)]; bh = pct(bw, bt)
        if bh is None: continue
        lines.append(f"  {m:8} base {bh:4.1f}% (n={bt})")
        for label, store, arms in [("A", bandA, ["over","under","none"]),
                                    ("B", bandB, ["high","low","neutral","none"])]:
            parts = []
            for arm in arms:
                w, t = store[(cell, arm, m)]
                if t == 0: continue
                h = pct(w, t); share = 100 * t / max(cellN[cell], 1)
                thin = "*" if t < 30 else ""
                parts.append(f"{arm}={h:.0f}%(n{t},{share:.0f}%,{h-bh:+.0f}){thin}")
            lines.append(f"      band{label}: " + "  ".join(parts))
    lines.append("")
lines.append("legend: arm=hit%(n=N, share-of-cell, delta-vs-base pp)  * = thin (<30)")

out = "\n".join(lines)
print(out)
Path(OUT).parent.mkdir(parents=True, exist_ok=True)
Path(OUT).write_text(out, encoding="utf-8")
print(f"saved to {OUT}")
