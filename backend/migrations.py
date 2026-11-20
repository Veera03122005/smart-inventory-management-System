"""
SmartStock AI — Database Migration Runner.
Applies sequential, atomic schema migrations and tracks versions in schema_migrations.
"""
import os
import re
import sqlite3
from datetime import datetime
import db

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")


def ensure_migrations_table(con):
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("""
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        applied_at TEXT NOT NULL
    );
    """)


def get_applied_versions(con):
    ensure_migrations_table(con)
    rows = con.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    return {r[0] for r in rows}


def get_available_migrations():
    if not os.path.isdir(MIGRATIONS_DIR):
        return []
    files = sorted(os.listdir(MIGRATIONS_DIR))
    migrations = []
    for f in files:
        m = re.match(r"^(\d+)_([\w\-]+)\.sql$", f)
        if m:
            version = int(m.group(1))
            name = f
            filepath = os.path.join(MIGRATIONS_DIR, f)
            migrations.append((version, name, filepath))
    return migrations


def run_migrations(con=None):
    """
    Applies all pending migrations in order inside atomic transactions.
    Preserves all existing data and enforces foreign keys.
    """
    own_connection = con is None
    if own_connection:
        con = db.connect()

    try:
        ensure_migrations_table(con)
        applied = get_applied_versions(con)
        available = get_available_migrations()
        newly_applied = []

        for version, name, filepath in available:
            if version in applied:
                continue

            with open(filepath, "r", encoding="utf-8") as f:
                sql = f.read()

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                # In SQLite, executescript issues a COMMIT if there is an open transaction.
                # To guarantee atomicity, we wrap each script in an explicit transaction block.
                con.execute("BEGIN TRANSACTION")
                con.executescript(sql)
                con.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (version, name, now_str)
                )
                con.execute("COMMIT")
                newly_applied.append(name)
            except Exception as e:
                try:
                    con.execute("ROLLBACK")
                except Exception:
                    pass
                if "duplicate column name" in str(e).lower():
                    con.execute(
                        "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                        (version, name, now_str)
                    )
                    con.commit()
                    newly_applied.append(name)
                    continue
                raise RuntimeError(f"Database migration '{name}' (v{version}) failed: {e}") from e

        return newly_applied
    finally:
        if own_connection:
            con.close()


def get_migration_status(con=None):
    own_connection = con is None
    if own_connection:
        con = db.connect()
    try:
        ensure_migrations_table(con)
        applied = {r[0]: r[1] for r in con.execute("SELECT version, applied_at FROM schema_migrations").fetchall()}
        available = get_available_migrations()
        return [
            {
                "version": v,
                "name": name,
                "applied": v in applied,
                "applied_at": applied.get(v)
            }
            for v, name, _ in available
        ]
    finally:
        if own_connection:
            con.close()
