"""
SmartStock AI — Inventory Movement Journal & Balance Reconciliation Tests.
Verifies append-only transactions, idempotency, compensating reversals, rollback atomicity,
negative boundary checks, and balance reconciliation.
"""
import pytest
import ledger
import db


def test_stock_in_increases_balance():
    bal_before = ledger.get_book_balance("ING03")
    tx = ledger.post_transaction(
        ingredient_id="ING03",
        transaction_type="STOCK_IN",
        quantity=25.0,
        delta_qty=+25.0,
        unit="kg",
        actor="manager",
        source_channel="MANUAL_FORM",
        idempotency_key="TEST_STOCK_IN_01",
        notes="Fresh sack received"
    )
    assert tx["status"] == "posted"
    bal_after = ledger.get_book_balance("ING03")
    assert round(bal_after - bal_before, 4) == 25.0


def test_consumption_decreases_balance():
    bal_before = ledger.get_book_balance("ING03")
    tx = ledger.post_transaction(
        ingredient_id="ING03",
        transaction_type="CONSUMPTION",
        quantity=10.0,
        delta_qty=-10.0,
        unit="kg",
        actor="staff",
        source_channel="MANUAL_FORM",
        idempotency_key="TEST_CONSUMPTION_01",
        notes="Lunch service cooking"
    )
    assert tx["status"] == "posted"
    bal_after = ledger.get_book_balance("ING03")
    assert round(bal_before - bal_after, 4) == 10.0


def test_wastage_decreases_balance():
    bal_before = ledger.get_book_balance("ING03")
    tx = ledger.post_transaction(
        ingredient_id="ING03",
        transaction_type="WASTAGE",
        quantity=2.5,
        delta_qty=-2.5,
        unit="kg",
        actor="staff",
        source_channel="MANUAL_FORM",
        idempotency_key="TEST_WASTAGE_01",
        notes="Spilled on floor"
    )
    assert tx["status"] == "posted"
    bal_after = ledger.get_book_balance("ING03")
    assert round(bal_before - bal_after, 4) == 2.5


def test_compensating_reversal():
    bal_before = ledger.get_book_balance("ING04")
    # 1. Post a transaction
    tx = ledger.post_transaction(
        ingredient_id="ING04",
        transaction_type="STOCK_IN",
        quantity=15.0,
        delta_qty=+15.0,
        unit="L",
        actor="manager",
        source_channel="MANUAL_FORM",
        idempotency_key="TEST_REVERSAL_ORIG_01",
        notes="Invoice erroneous entry"
    )
    tx_id = tx["transaction_id"]
    assert ledger.get_book_balance("ING04") == bal_before + 15.0

    # 2. Reverse the transaction
    rev = ledger.reverse_transaction(
        original_tx_id=tx_id,
        actor="manager",
        reason="Wrong supplier invoice entered",
        idempotency_key="TEST_REV_COMPENSATE_01"
    )
    assert rev["transaction_type"] == "REVERSAL"
    assert rev["delta_qty"] == -15.0
    assert rev["reversal_ref_id"] == tx_id

    # 3. Assert balance is restored to original
    assert ledger.get_book_balance("ING04") == bal_before

    # 4. Attempting to reverse again must fail
    with pytest.raises(ValueError) as exc:
        ledger.reverse_transaction(original_tx_id=tx_id, actor="manager", reason="Double reversal")
    assert "already been reversed" in str(exc.value)


def test_duplicate_idempotency_key():
    key = "UNIQUE_IDEMP_TEST_999"
    tx1 = ledger.post_transaction(
        ingredient_id="ING05",
        transaction_type="STOCK_IN",
        quantity=5.0,
        delta_qty=+5.0,
        unit="kg",
        actor="staff",
        source_channel="MANUAL_FORM",
        idempotency_key=key
    )
    assert tx1["status"] == "posted"

    # Second call with the same idempotency key
    tx2 = ledger.post_transaction(
        ingredient_id="ING05",
        transaction_type="STOCK_IN",
        quantity=5.0,
        delta_qty=+5.0,
        unit="kg",
        actor="staff",
        source_channel="MANUAL_FORM",
        idempotency_key=key
    )
    assert tx2["status"] == "duplicate"
    assert tx2["idempotent"] is True
    assert tx2["transaction"]["transaction_id"] == tx1["transaction_id"]


def test_negative_stock_boundary_rejection():
    # Attempting to consume more than available without allow_negative must raise ValueError
    current = ledger.get_book_balance("ING02")
    excessive_qty = current + 500.0

    with pytest.raises(ValueError) as exc:
        ledger.post_transaction(
            ingredient_id="ING02",
            transaction_type="CONSUMPTION",
            quantity=excessive_qty,
            delta_qty=-excessive_qty,
            unit="kg",
            actor="staff",
            source_channel="MANUAL_FORM",
            allow_negative=False
        )
    assert "Insufficient stock" in str(exc.value)


def test_balance_reconciliation():
    # 1. Clean reconciliation check
    rec = ledger.reconcile_balances("ING03")
    assert rec["status"] == "clean"
    assert rec["discrepancy_count"] == 0

    # 2. Simulate artificial projection corruption
    with db.tx() as con:
        con.execute("UPDATE inventory_balances SET book_balance = book_balance + 99.0 WHERE ingredient_id='ING03'")

    # 3. Detect discrepancy
    rec_detect = ledger.reconcile_balances("ING03", fix=False)
    assert rec_detect["status"] == "discrepancies_detected"
    assert rec_detect["discrepancy_count"] == 1
    assert rec_detect["discrepancies"][0]["ingredient_id"] == "ING03"

    # 4. Fix discrepancy
    rec_fix = ledger.reconcile_balances("ING03", fix=True, actor="test_admin")
    assert rec_fix["status"] == "fixed"

    # 5. Verify restored
    rec_clean = ledger.reconcile_balances("ING03")
    assert rec_clean["status"] == "clean"


def test_manual_entry_workflow_posts_journal_movements(client, login):
    # Post a daily stock entry via API
    res = client.post("/api/manual-entries", json={
        "ingredient_id": "ING03",
        "date": "2026-11-20",
        "opening_stock": 100.0,
        "received_qty": 20.0,
        "used_qty": 15.0,
        "wastage_qty": 2.0,
        "expiry_date": "2027-11-20",
        "idempotency_key": "IDEMP_API_STOCK_SHEET_01"
    }, headers=login("staff"))
    assert res.status_code == 201

    # Verify transactions posted in journal
    txs = client.get("/api/inventory/transactions?ingredient_id=ING03&limit=5", headers=login("manager"))
    assert txs.status_code == 200
    tx_list = txs.get_json()
    types = [t["transaction_type"] for t in tx_list if t.get("reference_id") == "MANUAL:2026-11-20:ING03"]
    assert "STOCK_IN" in types
    assert "CONSUMPTION" in types
    assert "WASTAGE" in types


def test_manual_entry_correction_reverses_and_replaces(client, login):
    # Submit correction for the same date & ingredient
    res = client.post("/api/manual-entries", json={
        "ingredient_id": "ING03",
        "date": "2026-11-20",
        "opening_stock": 100.0,
        "received_qty": 25.0,  # Corrected from 20 to 25
        "used_qty": 10.0,      # Corrected from 15 to 10
        "wastage_qty": 0.0,    # Corrected from 2 to 0
        "expiry_date": "2027-11-20",
        "idempotency_key": "IDEMP_API_STOCK_SHEET_CORRECTION_01"
    }, headers=login("staff"))
    assert res.status_code == 201

    # Verify compensating reversals exist
    txs = client.get("/api/inventory/transactions?ingredient_id=ING03&limit=15", headers=login("manager"))
    assert txs.status_code == 200
    tx_list = txs.get_json()
    ref_txs = [t for t in tx_list if t.get("reference_id") == "MANUAL:2026-11-20:ING03"]
    reversals = [t for t in ref_txs if t["transaction_type"] == "REVERSAL"]
    assert len(reversals) >= 1
    # Check that previous stock_in was reversed
    rev_deltas = [t["delta_qty"] for t in reversals]
    assert -20.0 in rev_deltas or +15.0 in rev_deltas


def test_manual_correction_idempotency_and_mathematical_balance(client, login):
    """
    Validates:
    1. First submission posts journal movements and updates balance.
    2. Retry of identical entry returns duplicate without posting reversals or new movements.
    3. Correction reverses prior unreversed movements and posts replacement movements with unique revision keys.
    4. Retry of correction is idempotent.
    5. Resulting balance mathematically matches original + final corrected net movement.
    """
    bal_initial = client.get("/api/inventory/reconciliation", headers=login("manager")).get_json()["ingredients"]
    initial_ing04 = next(r["projected_balance"] for r in bal_initial if r["ingredient_id"] == "ING04")

    # Step 1: Initial submission
    res1 = client.post("/api/manual-entries", json={
        "ingredient_id": "ING04",
        "date": "2026-11-21",
        "opening_stock": initial_ing04,
        "received_qty": 10.0,
        "used_qty": 5.0,
        "wastage_qty": 1.0,
        "expiry_date": "2026-11-28",
        "idempotency_key": "IDEMP_CORR_TEST_01"
    }, headers=login("staff"))
    assert res1.status_code == 201

    bal1 = client.get("/api/inventory/reconciliation", headers=login("manager")).get_json()["ingredients"]
    balance_after_sub1 = next(r["projected_balance"] for r in bal1 if r["ingredient_id"] == "ING04")
    # Expected net delta = +10 - 5 - 1 = +4
    assert round(balance_after_sub1 - initial_ing04, 2) == 4.0

    # Step 2: Retry identical submission
    res2 = client.post("/api/manual-entries", json={
        "ingredient_id": "ING04",
        "date": "2026-11-21",
        "opening_stock": initial_ing04,
        "received_qty": 10.0,
        "used_qty": 5.0,
        "wastage_qty": 1.0,
        "expiry_date": "2026-11-28",
        "idempotency_key": "IDEMP_CORR_TEST_01"
    }, headers=login("staff"))
    assert res2.status_code == 200
    assert res2.get_json().get("duplicate") is True

    # Balance must remain exactly identical
    bal2 = client.get("/api/inventory/reconciliation", headers=login("manager")).get_json()["ingredients"]
    balance_after_retry = next(r["projected_balance"] for r in bal2 if r["ingredient_id"] == "ING04")
    assert balance_after_retry == balance_after_sub1

    # Step 3: Submit correction (received=15.0, used=8.0, waste=2.0 -> net delta = +5.0)
    res3 = client.post("/api/manual-entries", json={
        "ingredient_id": "ING04",
        "date": "2026-11-21",
        "opening_stock": initial_ing04,
        "received_qty": 15.0,
        "used_qty": 8.0,
        "wastage_qty": 2.0,
        "expiry_date": "2026-11-28",
    }, headers=login("staff"))
    assert res3.status_code == 201

    bal3 = client.get("/api/inventory/reconciliation", headers=login("manager")).get_json()["ingredients"]
    balance_after_corr = next(r["projected_balance"] for r in bal3 if r["ingredient_id"] == "ING04")
    # Expected net delta from initial = +15 - 8 - 2 = +5.0
    assert round(balance_after_corr - initial_ing04, 2) == 5.0

    # Step 4: Retry the correction
    res4 = client.post("/api/manual-entries", json={
        "ingredient_id": "ING04",
        "date": "2026-11-21",
        "opening_stock": initial_ing04,
        "received_qty": 15.0,
        "used_qty": 8.0,
        "wastage_qty": 2.0,
        "expiry_date": "2026-11-28",
    }, headers=login("staff"))
    assert res4.status_code == 200
    assert res4.get_json().get("duplicate") is True

    # Step 5: Verify reconciliation report is 100% clean
    rec = client.get("/api/inventory/reconciliation", headers=login("manager")).get_json()
    assert rec["status"] == "clean"
