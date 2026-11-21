"""
SmartStock AI — Migration Runner Verification Tests.
Verifies fresh migrations, existing database migrations, idempotency, record preservation,
foreign-key enforcement, and transaction immutability triggers.
"""
import os
import sqlite3
import tempfile
import pytest
import migrations
import db


@pytest.fixture
def isolated_db():
    """Provides a fresh isolated temporary database path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    try:
        os.remove(path)
    except Exception:
        pass


def test_fresh_database_migration(isolated_db):
    con = sqlite3.connect(isolated_db)
    con.row_factory = sqlite3.Row
    applied = migrations.run_migrations(con=con)
    assert len(applied) >= 3
    assert "001_initial_schema.sql" in applied
    assert "002_inventory_transactions.sql" in applied
    assert "003_iot_telemetry_enhancements.sql" in applied

    # Verify schema_migrations table
    rows = con.execute("SELECT version, name FROM schema_migrations ORDER BY version").fetchall()
    assert len(rows) >= 3
    assert rows[0]["version"] == 1
    assert rows[1]["version"] == 2
    assert rows[2]["version"] == 3

    # Verify tables created
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    for expected in ["users", "ingredients", "devices", "iot_readings", "refill_sessions", "manual_entries", "inventory_transactions", "inventory_balances"]:
        assert expected in tables
    con.close()


def test_migration_idempotency(isolated_db):
    con = sqlite3.connect(isolated_db)
    con.row_factory = sqlite3.Row
    first_run = migrations.run_migrations(con=con)
    assert len(first_run) >= 3

    # Second run must be an idempotent no-op
    second_run = migrations.run_migrations(con=con)
    assert second_run == []
    con.close()


def test_existing_database_migration_preserves_records(isolated_db):
    con = sqlite3.connect(isolated_db)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")

    # Simulate an existing database with legacy 001 schema
    with open(os.path.join(migrations.MIGRATIONS_DIR, "001_initial_schema.sql")) as f:
        con.executescript(f.read())

    # Insert existing records
    con.execute("INSERT INTO users(username, password_hash, role) VALUES ('testuser', 'hash123', 'staff')")
    con.execute("INSERT INTO ingredients VALUES ('ING99', 'Spices', 'kg', 30, 2, 100.0, 'BAR99', 0, NULL, 5.0)")

    # Mark 001 as applied in schema_migrations
    migrations.ensure_migrations_table(con)
    con.execute("INSERT INTO schema_migrations VALUES (1, '001_initial_schema.sql', '2026-11-19 10:00:00')")
    con.commit()

    # Apply remaining migrations (002, 003)
    applied = migrations.run_migrations(con=con)
    assert "002_inventory_transactions.sql" in applied
    assert "003_iot_telemetry_enhancements.sql" in applied

    # Verify existing records are 100% preserved
    u = con.execute("SELECT * FROM users WHERE username='testuser'").fetchone()
    assert u is not None
    assert u["role"] == "staff"

    ing = con.execute("SELECT * FROM ingredients WHERE ingredient_id='ING99'").fetchone()
    assert ing is not None
    assert ing["name"] == "Spices"
    con.close()


def test_foreign_key_enforcement(isolated_db):
    con = sqlite3.connect(isolated_db)
    con.row_factory = sqlite3.Row
    migrations.run_migrations(con=con)

    # Attempting to insert a device for a non-existent ingredient must fail
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO devices(device_id, ingredient_id, api_key) VALUES ('DEV01', 'NONEXISTENT', 'key123')")
    con.close()


def test_journal_immutability_triggers(isolated_db):
    con = sqlite3.connect(isolated_db)
    con.row_factory = sqlite3.Row
    migrations.run_migrations(con=con)

    con.execute("INSERT INTO ingredients VALUES ('ING01', 'Chicken', 'kg', 2, 1, 200.0, 'BAR01', 0, NULL, 5.0)")
    con.execute("""
        INSERT INTO inventory_transactions (
            transaction_id, ingredient_id, quantity, delta_qty, unit, transaction_type,
            source_channel, timestamp, actor
        ) VALUES ('TX01', 'ING01', 10.0, 10.0, 'kg', 'STOCK_IN', 'MANUAL_FORM', '2026-11-19 10:00:00', 'owner')
    """)
    con.commit()

    # Prohibit UPDATE on posted transaction
    with pytest.raises(sqlite3.DatabaseError) as exc_update:
        con.execute("UPDATE inventory_transactions SET quantity = 20.0 WHERE transaction_id = 'TX01'")
    assert "Posted inventory transactions are immutable" in str(exc_update.value)

    # Prohibit DELETE on posted transaction
    with pytest.raises(sqlite3.DatabaseError) as exc_delete:
        con.execute("DELETE FROM inventory_transactions WHERE transaction_id = 'TX01'")
    assert "Posted inventory transactions are immutable" in str(exc_delete.value)

    con.close()
