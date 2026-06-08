"""
OddsFlow V4 — Orphan pick reconciler (Session 23d Bundle 4)
============================================================
Picks become "orphaned" when they cannot be settled through the normal
results+settle pipeline. Two causes today:

  1. The fixture's league_id is no longer in ACTIVE_LEAGUES (e.g. USL2
     was dropped Session 23). fetch_results never queries those leagues
     again, so the fixture sits without scores forever.
  2. The fixture's kickoff was more than 48 hours ago, the fixture has
     no scores yet, and the league IS in ACTIVE_LEAGUES — Sportmonks
     simply never returned the result. Practical outcome equivalent to #1.

Both cases are written as a synthetic ``pick_results`` row with
``outcome='ORPHAN'`` and ``notes='<reason>'``. The pick drops out of the
"pending" count in the operator dashboard and the runbook stays clean,
without faking a win/loss/void.

Run nightly via the Windows scheduler (slot added by setup_scheduler.ps1
under task name ``OddsFlow_ReconcileOrphans``).

Heartbeat: writes a ``reconcile_orphans`` row to ``system_health`` with
``value`` summarising counts, picked up by ``/diagnostics/runbook``.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "oddsflow_v4.db"
# SOURCE OF TRUTH: app/engine/static_policy.ACTIVE_LEAGUE_SPORTMONKS_IDS
# Keep this in sync with that frozenset, fetch_upcoming.ACTIVE_LEAGUES, and
# fetch_results.ACTIVE_LEAGUES. If it drifts, the reconciler marks fewer picks
# than expected — visible in the runbook value.
# Active leagues are read at runtime from leagues.active (maintained by
# sync_leagues.py). Fallback snapshot used only if the column can't be read.
_ACTIVE_FALLBACK = {
    286, 289, 292, 295, 345, 351, 360, 363, 393, 396, 444, 447, 573, 579,
    585, 588, 648, 779, 791, 989, 1034, 1362, 1607, 1642, 2545, 3306, 3537, 3550,
}


def _load_active(conn: sqlite3.Connection) -> set:
    try:
        ids = {int(r[0]) for r in conn.execute(
            "SELECT sportmonks_id FROM leagues WHERE active=1 AND sportmonks_id IS NOT NULL")}
        return ids or set(_ACTIVE_FALLBACK)
    except Exception:
        return set(_ACTIVE_FALLBACK)


ORPHAN_AGE_HOURS = 48  # fixture older than this with no score + no settlement


def _write_health(conn: sqlite3.Connection, value: str) -> None:
    """Best-effort heartbeat; never raise out of the reconciler."""
    try:
        conn.execute(
            "INSERT INTO system_health (metric, value) VALUES (?, ?)",
            ("reconcile_orphans", value),
        )
        conn.commit()
    except Exception:
        pass


def _mark_orphans(conn: sqlite3.Connection, reason: str, where_sql: str, params: list) -> int:
    """Insert synthetic pick_results rows with outcome='ORPHAN'.

    Idempotent — INSERT OR IGNORE on pick_uuid will skip picks already
    settled (real WIN/LOSS/VOID) and also already-marked orphans.
    """
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        f"""
        SELECT em.pick_uuid
        FROM emit_log em
        JOIN fixtures f         ON f.id = em.fixture_id
        LEFT JOIN leagues l     ON l.id = f.league_id
        LEFT JOIN pick_results pr ON pr.pick_uuid = em.pick_uuid
        WHERE pr.pick_uuid IS NULL
          AND {where_sql}
        """,
        params,
    ).fetchall()
    if not rows:
        return 0
    inserted = 0
    for r in rows:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO pick_results
              (pick_uuid, settled_at, outcome, actual_value, notes)
            VALUES (?, ?, 'ORPHAN', NULL, ?)
            """,
            (r["pick_uuid"], now, reason),
        )
        if cur.rowcount > 0:
            inserted += 1
    return inserted


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # NOTE: fixtures.league_id is the INTERNAL DB leagues.id, while
        # ACTIVE_LEAGUES holds SPORTMONKS league ids. We therefore join the
        # leagues table and compare l.sportmonks_id (not f.league_id) against
        # ACTIVE_LEAGUES. (Fixed 2026-06-09 — the old f.league_id comparison
        # mixed the two id systems and under-counted dropped-league orphans.)
        active = _load_active(conn)
        league_placeholders = ",".join("?" * len(active))
        # Reason A — fixture's league is no longer in the active subscription.
        league_count = _mark_orphans(
            conn,
            reason="league_dropped",
            where_sql=f"COAL