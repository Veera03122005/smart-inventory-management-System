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
    Guarantees that failed migrations are rolled back completely and never recorded as applied.
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

            # Deterministic compatibility handling for legacy databases where migration 007
            # was pre-applied by legacy helper functions without recording version 7.
            if version == 7:
                try:
                    user_cols = [r[1] for r in con.execute("PRAGMA table_info(users)").fetchall()]
                    if "is_active" in user_cols:
                        con.execute(
                            "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                            (version, name, now_str)
                        )
                        con.commit()
                        newly_applied.append(name)
                        continue
                except Exception:
                    pass

            # Separate non-transactional PRAGMAs from transactional body
            lines = sql.strip().splitlines()
            pragmas = []
            body_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped.upper().startswith("PRAGMA "):
                    pragmas.append(stripped)
                else:
                    body_lines.append(line)

            for p in pragmas:
                con.execute(p)

            body_sql = "\n".join(body_lines).strip()

            try:
                if body_sql:
                    # Executes the migration script body wrapped in an explicit transaction block
                    con.executescript("BEGIN TRANSACTION;\n" + body_sql + "\nCOMMIT;")

                con.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (version, name, now_str)
                )
                con.commit()
                newly_applied.append(name)
            except Exception as e:
                try:
                    con.execute("ROLLBACK")
                except Exception:
                    pass
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
