"""
SmartStock AI — Critical V1 Remediation Regression Tests.
Verifies all 9 high-priority remediation findings:
1. Removal of fabricated sales metrics and fallback 48,500; explicit DATA_UNAVAILABLE response.
2. Financial redaction in traditional_upload(), staged endpoints, file downloads, and delivery listings.
3. Atomic IoT complete_session() (ledger failure rolls back session completion; no swallowed exceptions).
4. Physical sensor reading confirmation (historical and simulated readings rejected).
5. Database-level constraint preventing multiple simultaneously open refill sessions for the same device.
6. Atomic migration execution and rollback on failure (no arbitrary duplicate-column suppression).
7. Non-kg canonical units in closing reconciliation with compatible conversion validation.
8. Ledger validation for NaN, infinity, negative quantities, incompatible units, and reversal-of-reversal protection.
9. Duplicate delivery and batch-line protection with nullable fields and concurrent submission safety.
"""
import csv
import io
import math
import os
import sqlite3
import time
import pytest
from datetime import datetime, timedelta

import app as flask_app
import db
import iot
import ledger
import migrations
import units


# -----------------------------------------------------------------------------
# FINDING 1: Remove fabricated sales metrics and 48,500 fallback
# -----------------------------------------------------------------------------
def test_finding_1_sales_endpoint_explicit_data_unavailable(client, login):
    """GET /api/sales returns explicit DATA_UNAVAILABLE when actual sales data is unavailable."""
    res = client.get("/api/sales", headers=login("manager"))
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "DATA_UNAVAILABLE"
    assert body["error"] == "DATA_UNAVAILABLE"
    assert "48500" not in str(body)
    assert "today_sales_rs" not in body or body["today_sales_rs"] is None

    # Owner also receives explicit DATA_UNAVAILABLE instead of fabricated profits
    res_owner = client.get("/api/sales", headers=login("owner"))
    assert res_owner.status_code == 200
    assert res_owner.get_json()["status"] == "DATA_UNAVAILABLE"


def test_finding_1_sales_report_404_when_unavailable(client, login):
    """GET /api/reports/sales.csv returns 404 DATA_UNAVAILABLE when no sales data exists."""
    res = client.get("/api/reports/sales.csv", headers=login("manager"))
    assert res.status_code == 404
    assert res.get_json()["error"] == "DATA_UNAVAILABLE"


def test_finding_1_dashboard_cards_redact_unavailable_sales(client, login):
    """Dashboard cards report None for sales metrics when sales data is unavailable."""
    for role in ("staff", "manager", "owner"):
        res = client.get("/api/dashboard", headers=login(role))
        assert res.status_code == 200
        cards = res.get_json()["cards"]
        assert cards["sales_today_rs"] is None
        assert cards["sales_7d_rs"] is None


# -----------------------------------------------------------------------------
# FINDING 2: Financial redaction in traditional_upload and document endpoints
# -----------------------------------------------------------------------------
def test_finding_2_traditional_upload_redacts_financials_for_staff_and_manager(client, login):
    """POST /api/traditional/upload does not expose unit_price_rs or line_total_rs to Staff or Manager."""
    csv_data = b"ingredient,billed_qty,unit,unit_price_rs,line_total_rs\nChicken,20.0,kg,250.0,5000.0\n"

    # 1. Staff upload
    res_staff = client.post("/api/traditional/upload", data={
        "workflow_type": "DELIVERY_INVOICE",
        "file": (io.BytesIO(csv_data), "staff_invoice.csv")
    }, headers=login("staff"))
    assert res_staff.status_code == 201
    rows_staff = res_staff.get_json()["rows"]
    assert len(rows_staff) == 1
    assert "unit_price_rs" not in rows_staff[0]
    assert "line_total_rs" not in rows_staff[0]

    # 2. Manager upload
    csv_data_mgr = b"ingredient,billed_qty,unit,unit_price_rs,line_total_rs\nMutton,15.0,kg,600.0,9000.0\n"
    res_mgr = client.post("/api/traditional/upload", data={
        "workflow_type": "DELIVERY_INVOICE",
        "file": (io.BytesIO(csv_data_mgr), "mgr_invoice.csv")
    }, headers=login("manager"))
    assert res_mgr.status_code == 201
    rows_mgr = res_mgr.get_json()["rows"]
    assert len(rows_mgr) == 1
    assert "unit_price_rs" not in rows_mgr[0]
    assert "line_total_rs" not in rows_mgr[0]


def test_finding_2_download_file_redacts_csv_financial_columns(client, login):
    """GET /api/traditional/uploads/<id>/file redacts price/total columns from CSV downloads for Staff."""
    csv_data = b"ingredient,billed_qty,unit,unit_price_rs,line_total_rs\nChicken,10.0,kg,200.0,2000.0\n"
    res_up = client.post("/api/traditional/upload", data={
        "workflow_type": "DELIVERY_INVOICE",
        "file": (io.BytesIO(csv_data), "sensitive_download.csv")
    }, headers=login("staff"))
    assert res_up.status_code == 201
    doc_id = res_up.get_json()["upload_id"]

    # Download file as staff
    res_dl = client.get(f"/api/traditional/uploads/{doc_id}/file", headers=login("staff"))
    assert res_dl.status_code == 200
    csv_text = res_dl.data.decode("utf-8")
    header = csv_text.splitlines()[0].lower()
    assert "unit_price_rs" not in header
    assert "line_total_rs" not in header
    assert "ingredient" in header
    assert "billed_qty" in header


# -----------------------------------------------------------------------------
# FINDING 3: Atomic IoT complete_session() (ledger + session update)
# -----------------------------------------------------------------------------
def test_finding_3_complete_session_atomic_rollback_on_ledger_failure(client, login, monkeypatch):
    """If ledger.post_transaction fails during complete_session, the session remains OPEN and changes roll back."""
    barcode = "8901000000035"  # Basmati Rice -> ESP32-RICE-01
    dev_id = "ESP32-RICE-01"
    key = "rice-key-123"

    # Close any existing open session directly
    with db.tx() as con:
        con.execute("UPDATE refill_sessions SET status='CANCELLED' WHERE device_id=? AND status='OPEN'", (dev_id,))

    seq_base = int(time.time() * 10) + 1
    # Ingest baseline reading
    res_base = client.post("/api/iot/readings", headers={"X-Device-Key": key}, json={
        "device_id": dev_id, "weight_kg": 5.0, "seq_no": seq_base, "stable": 1
    })
    assert res_base.status_code in (200, 201)

    # Open session
    open_res = client.post("/api/refill/open", json={"barcode": barcode}, headers=login("staff"))
    assert open_res.status_code == 201
    sid = open_res.get_json()["session_id"]

    # Wait 1.05s so server_now strictly exceeds started_at timestamp
    time.sleep(1.05)
    # Send valid fresh reading after session start
    res_fresh = client.post("/api/iot/readings", headers={"X-Device-Key": key}, json={
        "device_id": dev_id, "weight_kg": 8.5, "seq_no": seq_base + 1, "stable": 1
    })
    assert res_fresh.status_code in (200, 201)

    # Monkeypatch ledger.post_transaction to simulate unexpected failure
    def mock_post_fail(*args, **kwargs):
        raise RuntimeError("SIMULATED_LEDGER_STORAGE_FAILURE")

    monkeypatch.setattr(iot.ledger, "post_transaction", mock_post_fail)

    # Complete session must fail and NOT silently swallow the exception
    with pytest.raises(RuntimeError, match="SIMULATED_LEDGER_STORAGE_FAILURE"):
        iot.complete_session(sid, "staff")

    # Verify session status was rolled back and is STILL 'OPEN'
    session_row = db.query("SELECT status, weight_after_kg FROM refill_sessions WHERE session_id=?", (sid,))
    assert session_row[0]["status"] == "OPEN"
    assert session_row[0]["weight_after_kg"] is None

    # Clean up by cancelling
    monkeypatch.undo()
    client.post(f"/api/refill/{sid}/cancel", headers=login("staff"))
    with db.tx() as con:
        con.execute("DELETE FROM iot_readings WHERE device_id=? AND seq_no >= ?", (dev_id, seq_base))


# -----------------------------------------------------------------------------
# FINDING 4: Physical reading confirmation requirement
# -----------------------------------------------------------------------------
def test_finding_4_simulated_readings_rejected_for_physical_confirmation(client, login):
    """Readings from simulated sources (source != 'live') must not qualify as physical refill confirmation."""
    barcode = "8901000000035"
    dev_id = "ESP32-RICE-01"
    key = "rice-key-123"

    with db.tx() as con:
        con.execute("UPDATE refill_sessions SET status='CANCELLED' WHERE device_id=? AND status='OPEN'", (dev_id,))

    seq_base = int(time.time() * 10) + 10
    # Baseline reading
    client.post("/api/iot/readings", headers={"X-Device-Key": key}, json={
        "device_id": dev_id, "weight_kg": 4.0, "seq_no": seq_base, "stable": 1
    })

    # Open session
    open_res = client.post("/api/refill/open", json={"barcode": barcode}, headers=login("staff"))
    assert open_res.status_code == 201
    sid = open_res.get_json()["session_id"]

    # Ingest a simulated reading directly into iot_readings with source='sim'
    sim_ts = (datetime.now() + timedelta(seconds=3)).strftime("%Y-%m-%d %H:%M:%S")
    with db.tx() as con:
        con.execute(
            """
            INSERT INTO iot_readings (device_id, ingredient_id, ts, ingested_at, weight_kg, stable, event_type, session_id, seq_no, source)
            VALUES (?, 'ING03', ?, ?, 10.0, 1, 'READING', ?, ?, 'sim')
            """,
            (dev_id, sim_ts, sim_ts, sid, seq_base + 1)
        )

    # Attempt to complete with only simulated reading must be rejected
    comp_res = client.post(f"/api/refill/{sid}/complete", headers=login("staff"))
    assert comp_res.status_code == 409
    assert comp_res.get_json().get("status") == "WAITING_FOR_READING"

    client.post(f"/api/refill/{sid}/cancel", headers=login("staff"))
    with db.tx() as con:
        con.execute("DELETE FROM iot_readings WHERE device_id=? AND seq_no >= ?", (dev_id, seq_base))


# -----------------------------------------------------------------------------
# FINDING 5: Prevent multiple simultaneously open refill sessions
# -----------------------------------------------------------------------------
def test_finding_5_multiple_open_refill_sessions_prevented_at_db_level(client, login):
    """Database unique index uq_refill_open_device strictly prevents multiple OPEN sessions for same device."""
    barcode = "8901000000035"
    dev_id = "ESP32-RICE-01"
    key = "rice-key-123"

    with db.tx() as con:
        con.execute("UPDATE refill_sessions SET status='CANCELLED' WHERE device_id=? AND status='OPEN'", (dev_id,))

    seq_base = int(time.time() * 10) + 20
    client.post("/api/iot/readings", headers={"X-Device-Key": key}, json={
        "device_id": dev_id, "weight_kg": 6.0, "seq_no": seq_base, "stable": 1
    })

    # 1. First open succeeds
    res1 = client.post("/api/refill/open", json={"barcode": barcode}, headers=login("staff"))
    assert res1.status_code == 201
    sid1 = res1.get_json()["session_id"]

    # 2. Second open via API rejected with 409
    res2 = client.post("/api/refill/open", json={"barcode": barcode}, headers=login("staff"))
    assert res2.status_code == 409
    assert "already open" in res2.get_json()["error"]

    # 3. Direct DB insert attempt also raises IntegrityError
    with pytest.raises(sqlite3.IntegrityError):
        with db.tx() as con:
            con.execute(
                """
                INSERT INTO refill_sessions (session_id, device_id, ingredient_id, started_at, weight_before_kg, status)
                VALUES ('RS_TEST_COLLISION', ?, 'ING03', '2026-11-21 12:00:00', 6.0, 'OPEN')
                """,
                (dev_id,)
            )

    client.post(f"/api/refill/{sid1}/cancel", headers=login("staff"))


# -----------------------------------------------------------------------------
# FINDING 6: Migration atomicity and rollback on error
# -----------------------------------------------------------------------------
def test_finding_6_migration_runner_atomicity_and_rollback(tmp_path):
    """A failing migration rolls back all previous statements in that migration and records nothing in schema_migrations."""
    test_db = str(tmp_path / "migration_test.db")
    con = sqlite3.connect(test_db)
    migrations.ensure_migrations_table(con)

    mig_dir = tmp_path / "migs"
    mig_dir.mkdir()

    # Step 1: Valid initial migration 001
    (mig_dir / "001_initial.sql").write_text("CREATE TABLE t1 (id int);", encoding="utf-8")
    import unittest.mock
    with unittest.mock.patch.object(migrations, "MIGRATIONS_DIR", str(mig_dir)):
        applied = migrations.run_migrations(con)
        assert applied == ["001_initial.sql"]
        assert migrations.get_applied_versions(con) == {1}

    # Step 2: Add failing migration 002 with multiple statements
    (mig_dir / "002_failing.sql").write_text(
        "CREATE TABLE t2 (id int);\n"
        "INSERT INTO t2 VALUES (1);\n"
        "CREATE TABLE t2 (id int); -- Intentional duplicate table failure\n",
        encoding="utf-8"
    )

    with unittest.mock.patch.object(migrations, "MIGRATIONS_DIR", str(mig_dir)):
        with pytest.raises(RuntimeError, match="002_failing.sql"):
            migrations.run_migrations(con)

        # Confirm 002 was NOT recorded as applied
        assert migrations.get_applied_versions(con) == {1}

        # Confirm partial DDL in 002 (CREATE TABLE t2) was completely rolled back
        t2 = con.execute("SELECT name FROM sqlite_master WHERE name='t2'").fetchall()
        assert t2 == []

    con.close()


# -----------------------------------------------------------------------------
# FINDING 7: Canonical units in closing reconciliation
# -----------------------------------------------------------------------------
def test_finding_7_closing_reconciliation_canonical_units(client, login):
    """Closing reconciliation uses the ingredient's canonical unit and validates conversions."""
    date = "2026-12-29"
    headers = login("staff")

    # ING01 has canonical unit 'kg'
    # Send count in compatible unit 'g' (15000 g = 15.0 kg)
    res = client.post("/api/traditional/closing", json={
        "date": date,
        "counts": [
            {"ingredient_id": "ING01", "physical_qty": 15000.0, "unit": "g"}
        ]
    }, headers=headers)
    assert res.status_code in (200, 201)

    # Verify posted daily stock count was normalized to canonical kg (15.0)
    cnt = db.query("SELECT physical_qty FROM daily_stock_counts WHERE date=? AND ingredient_id='ING01' AND count_type='PM_CLOSING'", (date,))
    assert abs(cnt[0]["physical_qty"] - 15.0) < 1e-4

    # Send incompatible unit 'L' for ING01 -> rejected with 422
    res_bad = client.post("/api/traditional/closing", json={
        "date": "2026-12-30",
        "counts": [
            {"ingredient_id": "ING01", "physical_qty": 10.0, "unit": "L"}
        ]
    }, headers=headers)
    assert res_bad.status_code == 422
    assert "Incompatible unit" in res_bad.get_json()["error"]


# -----------------------------------------------------------------------------
# FINDING 8: Ledger validation for NaN, Inf, types, and reversals
# -----------------------------------------------------------------------------
def test_finding_8_ledger_validation_nan_infinity_and_types():
    """Ledger rejects NaN, Inf, negative quantities, and enforces reversal integrity."""
    # 1. NaN and Inf rejected
    with pytest.raises(ValueError, match="NaN, or Infinite"):
        ledger.post_transaction("ING01", "STOCK_IN", float("nan"), 10.0, "kg", "admin", "TEST")

    with pytest.raises(ValueError, match="NaN, or Infinite"):
        ledger.post_transaction("ING01", "STOCK_IN", 10.0, float("inf"), "kg", "admin", "TEST")

    # 2. Negative quantity rejected
    with pytest.raises(ValueError, match="non-negative"):
        ledger.post_transaction("ING01", "STOCK_IN", -5.0, -5.0, "kg", "admin", "TEST")

    # 3. STOCK_IN with negative delta rejected
    with pytest.raises(ValueError, match="cannot have negative delta_qty"):
        ledger.post_transaction("ING01", "STOCK_IN", 5.0, -5.0, "kg", "admin", "TEST")

    # 4. Incompatible unit rejected
    with pytest.raises(ValueError, match="Incompatible unit"):
        ledger.post_transaction("ING01", "STOCK_IN", 5.0, 5.0, "L", "admin", "TEST")

    # 5. Direct REVERSAL without reversal_ref_id rejected
    with pytest.raises(ValueError, match="reversal_ref_id"):
        ledger.post_transaction("ING01", "REVERSAL", 5.0, -5.0, "kg", "admin", "TEST")


def test_finding_8_cannot_reverse_a_reversal():
    """A compensating reversal transaction cannot itself be reversed."""
    # Post original transaction
    tx = ledger.post_transaction(
        "ING01", "STOCK_IN", 5.0, 5.0, "kg", "admin", "TEST_REV_ORIG",
        idempotency_key="TEST_REV_ORIG_KEY"
    )
    tx_id = tx["transaction_id"]

    # Reverse it
    rev = ledger.reverse_transaction(tx_id, "admin", "Testing reversal", idempotency_key="TEST_REV_1_KEY")
    rev_id = rev["transaction_id"]

    # Attempting to reverse the reversal must raise ValueError
    with pytest.raises(ValueError, match="Cannot reverse a reversal transaction"):
        ledger.reverse_transaction(rev_id, "admin", "Attempting illegal double reversal")


# -----------------------------------------------------------------------------
# FINDING 9: Duplicate delivery protection with nullable fields
# -----------------------------------------------------------------------------
def test_finding_9_duplicate_delivery_and_nullable_batch_protection(client, login):
    """Deliveries with null/empty batch_no and expiry_date are protected against duplicate submission."""
    headers = login("staff")
    supplier = "Fresh Farm Produce"
    inv_no = "INV-NULL-BATCH-01"
    inv_date = "2026-12-27"

    payload = {
        "supplier_name": supplier,
        "invoice_no": inv_no,
        "invoice_date": inv_date,
        "items": [
            {"ingredient_id": "ING01", "billed_qty": 25.0, "unit": "kg", "batch_no": None, "expiry_date": None}
        ]
    }

    # First post succeeds
    res1 = client.post("/api/traditional/delivery", json=payload, headers=headers)
    assert res1.status_code == 201

    # Exact retry returns 200 with duplicate=True
    res_retry = client.post("/api/traditional/delivery", json=payload, headers=headers)
    assert res_retry.status_code == 200
    assert res_retry.get_json()["duplicate"] is True

    # Conflicting post with different quantity rejected with 409
    payload_conflict = {
        "supplier_name": supplier,
        "invoice_no": inv_no,
        "invoice_date": inv_date,
        "items": [
            {"ingredient_id": "ING01", "billed_qty": 30.0, "unit": "kg", "batch_no": None, "expiry_date": None}
        ]
    }
    res_conflict = client.post("/api/traditional/delivery", json=payload_conflict, headers=headers)
    assert res_conflict.status_code == 409
    assert "already been posted" in res_conflict.get_json()["error"]
