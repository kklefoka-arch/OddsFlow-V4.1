import sqlite3
from datetime import date as date_cls
DB = r"C:\OddsFlowV4\data\oddsflow_v4.db"
ACTIVE = {573,444,345,292,360,779,648,3537,1034,989,1098,696,1689,286,393,405,
          579,678,295,289,791,3550,1642,351,1607,2545,585,588,681}
conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
today = date_cls.today().isoformat()
rows = conn.execute("""
    SELECT l.name AS league, l.sportmonks_id AS sm, COUNT(*) n,
           SUM(CASE WHEN COALESCE(f.status,'')='no_result' THEN 1 ELSE 0 END) AS already_no_result
    FROM fixtures f LEFT JOIN leagues l ON l.id=f.league_id
    WHERE f.home_score IS NULL AND f.sportmonks_id IS NOT NULL
      AND substr(f.date,1,10) < ?
    GROUP BY l.name, l.sportmonks_id ORDER BY n DESC
""", (today,)).fetchall()
print("PENDING (home_score NULL, past kickoff) by league:")
act = inact = 0
for r in rows:
    flag = "ACTIVE " if r["sm"] in ACTIVE else "dropped"
    print(f"   [{flag}] {str(r['league'])[:28]:<28} sm={r['sm']}  pending={r['n']}  (no_result={r['already_no_result']})")
    if r["sm"] in ACTIVE: act += r["n"]
    else: inact += r["n"]
print(f"\n  ACTIVE-league pending (settleable): {act}")
print(f"  dropped-league pending (orphan):    {inact}")
# also: any unsettled PICKS (emit_log without pick_results)?
p = conn.execute("""SELECT COUNT(*) FROM emit_log em
    LEFT JOIN pick_results pr ON pr.pick_uuid=em.pick_uuid WHERE pr.pick_uuid IS NULL""").fetchone()[0]
print(f"  unsettled PICKS (no pick_results row): {p}")
conn.close()
print("REPORT DONE")
