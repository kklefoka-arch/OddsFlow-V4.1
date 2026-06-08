"""Database integrity guard + rotating backup.

Runs at the top of the daily chain (and can be scheduled standalone). It:
  1. Runs PRAGMA quick_check / integrity_check on the live DB.
  2. If healthy, writes a dated backup via SQLite's online Backup API (safe even
     while the server holds the DB open) and prunes to the newest KEEP backups.
  3. Records the outcome in system_health so /diagnostics surfaces any problem
     to the operator instead of it going unnoticed.

This exists because a corrupt or truncated DB makes the whole app look broken
no matter how good the code is — we want that caught and flagged early, with a
known-good backup always on hand.
"""
import sqlite3, os, glob, time
from datetime import datetime, timezone

DB = r"C:\OddsFlowV4\data\oddsflow_v4.db"
BACKUP_DIR = r"C:\OddsFlowV4\data"
KEEP = 7


def _health(conn, value):
    try:
        conn.execute("INSERT INTO system_health (metric, value) VALUES (?, ?)",
                     ("db_healthcheck", value))
        conn.commit()
    except Exception:
        pass


def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn = sqlite3.connect(DB)
    except Exception as e:
        print(f"FATAL: cannot open DB: {e}")
        return
    try:
        ok = conn.execute("PRAGMA quick_check").fetchone()
        status = ok[0] if ok else "unknown"
        print(f"quick_check: {status}")
        if status != "ok":
            _health(conn, f"FAIL quick_check={status} ts={now}")
            print("Integrity problem detected — NOT overwriting backups. Investigate.")
            return

        # Online backup (safe with the server holding the DB open)
        stamp = datetime.now().strftime("%Y-%m-%d")
        dest = os.path.join(BACKUP_DIR, f"oddsflow_v4.db.bak.{stamp}-auto")
        bck = sqlite3.connect(dest)
        with bck:
            conn.backup(bck)
        bck.close()
        size_mb = os.path.getsize(dest) / 1_048_576
        print(f"backup written: {dest}  ({size_mb:.1f} MB)")

        # Prune to newest KEEP auto-backups
        autos = sorted(glob.glob(os.path.join(BACKUP_DIR, "oddsflow_v4.db.bak.*-auto")),
                       key=os.path.getmtime, reverse=True)
        for old in autos[KEEP:]:
            try:
                os.remove(old); print(f"pruned old backup: {os.path.basename(old)}")
            except Exception:
                pass

        _health(conn, f"ok quick_check=ok backup={os.path.basename(dest)} ts={now}")
        print("db_healthcheck OK")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
