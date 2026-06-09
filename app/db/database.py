"""OddsFlow V3 — Database helpers.

Provides init_db (schema creation + migrations) and get_conn (connection factory).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def init_db(db_path: str) -> None:
    """Create all tables and run additive migrations.

    Safe to call on both fresh and existing databases — all DDL is
    idempotent (CREATE IF NOT EXISTS / ALTER IF missing column).
    """
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema_sql)
        _run_migrations(conn)
        conn.commit()
    finally:
        conn.close()


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Additive ALTER TABLE migrations for existing databases.

    Each statement is wrapped in try/except so that columns already
    present (fresh DB or re-run) are silently skipped.
    """
    additive = [
        "ALTER TABLE leagues ADD COLUMN sportmonks_id INTEGER",
        "ALTER TABLE teams   ADD COLUMN sportmonks_id INTEGER",
        "ALTER TABLE teams   ADD COLUMN short_name    TEXT",
        "ALTER TABLE fixtures ADD COLUMN sportmonks_id INTEGER",
        # emit_log additions for V4
        "ALTER TABLE emit_log ADD COLUMN partition_key TEXT",
        "ALTER TABLE emit_log ADD COLUMN strategy      TEXT",
        # V3.1 (2026-05-27) — DF-aware partition
        "ALTER TABLE fixtures ADD COLUMN df_level TEXT",
        "ALTER TABLE emit_log ADD COLUMN df_level TEXT",
        # v4 data-foundation (2026-05-30) — odds freshness stamp (no-stale-odds)
        "ALTER TABLE fixtures ADD COLUMN odds_updated_at TEXT",
        # v4 full-capture landing (DATA_LANDING_PRINCIPLE) — land the whole payload
        # so nothing the API returns leaks unaccounted; extract more fields later.
        "ALTER TABLE fixtures      ADD COLUMN raw_odds_json  TEXT",
        "ALTER TABLE fixture_stats ADD COLUMN raw_stats_json TEXT",
        # system_health table (if not in schema.sql)
        # pick_results outcome column (ensure it exists)
    ]
    for ddl in additive:
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError:
            pass  # column already exists

    indexes = [
        # Uniqueness constraints
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_leagues_smid  ON leagues(sportmonks_id)  WHERE sportmonks_id IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_teams_smid    ON teams(sportmonks_id)    WHERE sportmonks_id IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_fixtures_smid ON fixtures(sportmonks_id) WHERE sportmonks_id IS NOT NULL",
        # Performance indexes — added v4 (2026-06-08) for 10k+ fixture scale
        # fixtures.date — picks/upcoming window queries (WHERE date >= ? AND date <= ?)
        "CREATE INDEX IF NOT EXISTS idx_fixtures_date        ON fixtures(date)",
        # fixtures.home_score — unsettled checks (WHERE home_score IS NULL)
        "CREATE INDEX IF NOT EXISTS idx_fixtures_score       ON fixtures(home_score)",
        # fixtures.draw_zone — inspector/similar (WHERE draw_zone = ?)
        "CREATE INDEX IF NOT EXISTS idx_fixtures_draw_zone   ON fixtures(draw_zone)",
        # emit_log.emitted_at — all report/drift queries (WHERE emitted_at >= ?)
        "CREATE INDEX IF NOT EXISTS idx_emit_emitted_at      ON emit_log(emitted_at)",
        # emit_log.fixture_id — JOINs from reports/inspector
        "CREATE INDEX IF NOT EXISTS idx_emit_fixture_id      ON emit_log(fixture_id)",
        # emit_log.(zone, bts_pocket) — drift computation (WHERE zone=? AND bts_pocket=?)
        "CREATE INDEX IF NOT EXISTS idx_emit_zone_bts        ON emit_log(zone, bts_pocket)",
        # pick_results.settled_at — settle_activity window queries
        "CREATE INDEX IF NOT EXISTS idx_pr_settled_at        ON pick_results(settled_at)",
        # system_health.(metric, recorded_at) — runbook/chain checks
        "CREATE INDEX IF NOT EXISTS idx_health_metric_ts     ON system_health(metric, recorded_at)",
    ]
    for ddl in indexes:
        conn.execute(ddl)


def get_conn(db_path: str) -> sqlite3.Connection:
    """Return a sqlite3 connection with Row factory enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
