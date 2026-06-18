"""OddsFlow V4 — DF signal validation (within-cell separation frame).

For each (zone x bts) cell and each market, splits the hit rate by DF (DF0/DF1/DF2)
and reports, per arm: hit rate, N, SHARE of the cell, and DELTA vs the cell base.
DF is available on every classifiable fixture (derived from home/away odds), so
samples are large. Per the operator's framing: the CELL carries the weight; the
signal is judged on its ability to separate markets within the cell, not on its
own absolute N. Read-only. Writes analysis/df_validation.txt. Run via run_validate_df.bat.
"""
from __future__ import annotations
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DB = r"C:\OddsFlowV4\data\oddsflow_v4.db"
OUT = r"C:\OddsFlowV4\analysis\df_validation.txt"

def zone(d):
    if d is None or d < 2.90: return None
    if d < 3.30: return "strong"
    if d < 3.80: return "standard"
    if d < 4.30: return "low"
    return "one_sided"
def bts(y, n): return None if y is None or n is None else ("over" if y <= n else "under")
def df_of(ho, ao):
    if ho is None or ao is None: return None
    d = abs(round(ho) - round(ao)); return "DF0" if d == 0 else ("DF1" if d == 1 else "DF2")

conn = sqlite3.connect(DB, timeout=60); conn.row_factory = sqlite3.Row
rows = conn.execute("""SELECT f.draw_odd, f.btts_yes_odd y, f.btts_no_odd n, f.home_odd ho, f.away_odd ao,
 f.home_score hs, f.away_score aw, fs.home_corners hc, fs.away_corners ac
 FROM fixtures f LEFT JOIN fixture_stats fs ON fs.fixture_id=f.id
 WHERE f.home_score IS NOT NULL AND f.away_score IS NOT NULL AND f.draw_odd IS NOT NULL
 AND f.btts_yes_odd IS NOT NULL AND f.btts_no_odd IS NOT NULL
 AND f.home_odd IS NOT NULL AND f.away_odd IS NOT NULL""").fetchall()
conn.close()

MK = ["goals", "corners", "3way"]
CELLS = ["strong:over","strong:under","standard:over","standard:under",
         "low:over","low:under","one_sided:over","one_sided:under"]
arm = defaultdict(lambda: [0, 0])   # (cell, df, market) -> [win, total]
base = defaultdict(lambda: [0, 0])  # (cell, market) -> [win, total]
cellN = defaultdict(int)

for r in rows:
    z = zone(r["draw_odd"]); b = bts(r["y"], r["n"])
    if z is None or b is None: continue
    cell = f"{z}:{b}"; d = df_of(r["ho"], r["ao"]); cellN[cell] += 1
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
        arm[(cell, d, m)][0] += o[m]; arm[(cell, d, m)][1] += 1
        base[(cell, m)][0] += o[m]; base[(cell, m)][1] += 1

def pct(w, t): return (100 * w / t) if t else None

lines = [f"DF SIGNAL VALIDATION — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
         f"population: {sum(cellN.values()):,} classifiable settled fixtures", "",
         "Per cell x market: base rate, then each DF arm's hit / share-of-cell / delta-vs-base.",
         "(share = arm fixtures / cell fixtures; delta = arm hit - base hit, in pp)", ""]
for cell in CELLS:
    lines.append(f"=== {cell}   (cell N = {cellN[cell]}) ===")
    for m in MK:
        bw, bt = base[(cell, m)]
        bh = pct(bw, bt)
        if bh is None:
            lines.append(f"  {m:8} base: no data"); continue
        lines.append(f"  {m:8} base {bh:4.1f}% (n={bt})")
        for d in ("DF0", "DF1", "DF2"):
            w, t = arm[(cell, d, m)]
            if t == 0:
                lines.append(f"      {d}: -"); continue
            h = pct(w, t); share = 100 * t / max(cellN[cell], 1); delta = h - bh
            flag = "" if t >= 30 else "  (thin)"
            lines.append(f"      {d}: {h:4.1f}%  n={t:5}  share={share:4.1f}%  delta={delta:+5.1f}pp{flag}")
    lines.append("")

out = "\n".join(lines)
print(out)
Path(OUT).parent.mkdir(parents=True, exist_ok=True)
Path(OUT).write_text(out, encoding="utf-8")
print(f"saved to {OUT}")
