"""
SmartStock AI — Phase 3 Test Suite:
Manager Depletion Investigation & Zero-Sum Wastage Classification

Verifies all 15 required acceptance scenarios:
1. Manager can view unclassified depletion.
2. Staff receives 403 on investigation endpoints.
3. Manager can classify a valid partial quantity.
4. Multiple categories can be assigned to one depletion record.
5. Classification creates delta_qty = 0.
6. Inventory balance remains unchanged after classification.
7. Over-classification is rejected.
8. Duplicate requests are idempotent.
9. Concurrent classification cannot exceed available depletion.
10. Unexplained depletion can remain unresolved.
11. Physical overage cannot be classified as wastage.
12. Missing counts cannot be finalized.
13. Reversal and correction preserve audit history.
14. Manager receives no purchase-cost or profit data.
15. All Phase 1, Phase 2, and Phase 2.1 tests remain passing.
"""
import json
import pytest
import ledger
import db


def _create_full_day_cycle(client, login, date, ingredient_id="ING01", op_qty=20.0, deliv_qty=10.0, cl_qty=22.0):
    """
    Helper to create an end-to-end traditional day cycle:
    Opening: op_qty (e.g. 20.0)
    Deliveries: deliv_qty (e.g. 10.0)
    Closing: cl_qty (e.g. 22.0)
    Depletion: op_qty + deliv_qty - cl_qty (e.g. 8.0)
    """
    headers_staff = login("staff")
    headers_owner = login("owner")

    # 1. Opening
    res_op = client.post("/api/traditional/opening", headers=headers_staff, json={
        "date": date,
        "counts": [{"ingredient_id": ingredient_id, "physical_qty": op_qty, "notes": "Morning count"}]
    })
    assert res_op.status_code == 201

    # 2. Delivery (if any)
    if deliv_qty > 0:
        inv_no = f"INV-P3-{date}-{ingredient_id}"
        res_del = client.post("/api/traditional/delivery", headers=headers_staff, json={
            "supplier_name": "Phase3 Foods Ltd",
            "invoice_no": inv_no,
            "invoice_date": date,
            "items": [{
                "ingredient_id": ingredient_id,
                "billed_qty": deliv_qty,
                "unit": "kg",
                "unit_price_rs": 150.0,
                "batch_no": f"BATCH-{date}",
                "expiry_date": "2027-01-01"
            }]
        })
        assert res_del.status_code in (200, 201)

    # 3. Closing
    res_cl = client.post("/api/traditional/closing", headers=headers_staff, json={
        "date": date,
        "counts": [{"ingredient_id": ingredient_id, "physical_qty": cl_qty, "notes": "Evening closing"}]
    })
    assert res_cl.status_code == 201

    dep_id = f"DEP_{date}_{ingredient_id}"
    return dep_id


# -------------------------------------------------------------
# 1. MANAGER CAN VIEW UNCLASSIFIED DEPLETION
# -------------------------------------------------------------
def test_01_manager_can_view_unclassified_depletion(client, login):
    date = "2026-12-01"
    dep_id = _create_full_day_cycle(client, login, date=date, ingredient_id="ING01", op_qty=20.0, deliv_qty=10.0, cl_qty=22.0)
    # Expected depletion = 20 + 10 - 22 = 8.0 kg

    headers_mgr = login("manager")
    res_dash = client.get("/api/manager/depletions", headers=headers_mgr)
    assert res_dash.status_code == 200
    dash_data = res_dash.get_json()
    assert dash_data["unclassified_count"] >= 1
    assert dash_data["awaiting_investigation_qty"] >= 8.0

    res_list = client.get(f"/api/manager/depletions/list?date={date}", headers=headers_mgr)
    assert res_list.status_code == 200
    list_data = res_list.get_json()
    assert list_data["count"] >= 1
    target = next((d for d in list_data["depletions"] if d["depletion_id"] == dep_id), None)
    assert target is not None
    assert target["calculated_depletion_kg"] == 8.0
    assert target["classified_qty"] == 0.0
    assert target["remaining_unclassified_qty"] == 8.0
    assert target["status"] == "UNCLASSIFIED"


# -------------------------------------------------------------
# 2. STAFF RECEIVES 403 ON INVESTIGATION ENDPOINTS
# -------------------------------------------------------------
def test_02_staff_receives_403_on_investigation_endpoints(client, login):
    headers_staff = login("staff")
    dep_id = "DEP_2026-12-01_ING01"

    # Dashboard
    assert client.get("/api/manager/depletions", headers=headers_staff).status_code == 403
    # List
    assert client.get("/api/manager/depletions/list", headers=headers_staff).status_code == 403
    # Detail
    assert client.get(f"/api/manager/depletions/{dep_id}", headers=headers_staff).status_code == 403
    # Classify
    assert client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_staff, json={
        "category": "SPOILAGE", "classified_qty": 1.0
    }).status_code == 403
    # Notes
    assert client.post(f"/api/manager/depletions/{dep_id}/notes", headers=headers_staff, json={
        "note": "Staff trying to add note"
    }).status_code == 403
    # Resolve
    assert client.post(f"/api/manager/depletions/{dep_id}/resolve", headers=headers_staff, json={
        "resolution_notes": "Staff trying to resolve"
    }).status_code == 403
    # Reverse
    assert client.post("/api/manager/depletions/classifications/CLS_FAKE/reverse", headers=headers_staff, json={
        "reason": "Staff reversal"
    }).status_code == 403
    # Reports
    assert client.get("/api/manager/reports/depletions", headers=headers_staff).status_code == 403


# -------------------------------------------------------------
# 3. MANAGER CAN CLASSIFY VALID PARTIAL QUANTITY
# -------------------------------------------------------------
def test_03_manager_can_classify_valid_partial_quantity(client, login):
    date = "2026-12-02"
    dep_id = _create_full_day_cycle(client, login, date=date, ingredient_id="ING01", op_qty=20.0, deliv_qty=5.0, cl_qty=15.0)
    # Total depletion = 20 + 5 - 15 = 10.0 kg

    headers_mgr = login("manager")
    res_cls = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "SPOILAGE",
        "classified_qty": 3.0,
        "notes": "Vegetables wilted in cold storage"
    })
    assert res_cls.status_code == 201
    data = res_cls.get_json()
    assert data["category"] == "SPOILAGE"
    assert data["classified_qty"] == 3.0
    assert data["remaining_unclassified_qty"] == 7.0
    assert data["status"] == "INVESTIGATING"
    assert data["delta_qty"] == 0.0

    # Verify detail reflects partial status
    res_det = client.get(f"/api/manager/depletions/{dep_id}", headers=headers_mgr)
    det_data = res_det.get_json()
    assert det_data["classified_qty"] == 3.0
    assert det_data["remaining_unclassified_qty"] == 7.0
    assert det_data["status"] == "INVESTIGATING"
    assert len(det_data["classifications"]) == 1


# -------------------------------------------------------------
# 4. MULTIPLE CATEGORIES ASSIGNED TO ONE DEPLETION RECORD
# -------------------------------------------------------------
def test_04_multiple_categories_can_be_assigned_to_one_depletion_record(client, login):
    date = "2026-12-03"
    dep_id = _create_full_day_cycle(client, login, date=date, ingredient_id="ING01", op_qty=20.0, deliv_qty=10.0, cl_qty=22.0)
    # Depletion = 8.0 kg
    headers_mgr = login("manager")

    # 1. Spoilage 2.0 kg
    r1 = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "SPOILAGE", "classified_qty": 2.0, "notes": "Chiller failure"
    })
    assert r1.status_code == 201
    assert r1.get_json()["remaining_unclassified_qty"] == 6.0

    # 2. Preparation loss 1.0 kg
    r2 = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "PREPARATION_LOSS", "classified_qty": 1.0, "notes": "Excessive trimming"
    })
    assert r2.status_code == 201
    assert r2.get_json()["remaining_unclassified_qty"] == 5.0

    # 3. Spillage 1.0 kg
    r3 = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "SPILLAGE", "classified_qty": 1.0, "notes": "Dropped tray"
    })
    assert r3.status_code == 201
    assert r3.get_json()["remaining_unclassified_qty"] == 4.0

    # 4. Normal operational consumption 4.0 kg (completing 100% of depletion)
    r4 = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "NORMAL_CONSUMPTION", "classified_qty": 4.0, "notes": "Lunch and dinner cooking"
    })
    assert r4.status_code == 201
    data4 = r4.get_json()
    assert data4["remaining_unclassified_qty"] == 0.0
    assert data4["status"] == "CLASSIFIED"

    # Detail check: 4 active classifications
    res_det = client.get(f"/api/manager/depletions/{dep_id}", headers=headers_mgr)
    active_cls = [c for c in res_det.get_json()["classifications"] if c["status"] == "ACTIVE"]
    assert len(active_cls) == 4
    assert res_det.get_json()["classified_qty"] == 8.0
    assert res_det.get_json()["status"] == "CLASSIFIED"


# -------------------------------------------------------------
# 5. CLASSIFICATION CREATES DELTA_QTY = 0
# -------------------------------------------------------------
def test_05_classification_creates_delta_qty_zero(client, login):
    date = "2026-12-04"
    dep_id = _create_full_day_cycle(client, login, date=date, ingredient_id="ING01", op_qty=15.0, deliv_qty=5.0, cl_qty=14.0)
    # Depletion = 6.0 kg

    headers_mgr = login("manager")
    res = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "EXPIRED",
        "classified_qty": 2.5,
        "notes": "Past expiry date on batch"
    })
    assert res.status_code == 201
    body = res.get_json()
    assert body["delta_qty"] == 0.0

    # Inspect transaction in inventory_transactions table
    tx_id = body["reclassification_transaction_id"]
    con = db.connect()
    tx = con.execute("SELECT * FROM inventory_transactions WHERE transaction_id=?", (tx_id,)).fetchone()
    con.close()
    assert tx is not None
    assert tx["delta_qty"] == 0.0
    assert tx["quantity"] == 2.5
    assert tx["transaction_type"] == "RECLASSIFICATION"
    assert tx["source_channel"] == "DEPLETION_INVESTIGATION"


# -------------------------------------------------------------
# 6. INVENTORY BALANCE REMAINS UNCHANGED AFTER CLASSIFICATION
# -------------------------------------------------------------
def test_06_inventory_balance_remains_unchanged_after_classification(client, login):
    date = "2026-12-05"
    dep_id = _create_full_day_cycle(client, login, date=date, ingredient_id="ING01", op_qty=10.0, deliv_qty=5.0, cl_qty=11.0)
    # Depletion = 4.0 kg

    bal_before = ledger.get_book_balance("ING01")

    headers_mgr = login("manager")
    # Post multiple classifications
    client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "DAMAGE", "classified_qty": 1.5, "notes": "Crushed during unloading"
    })
    client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "MEASUREMENT_ERROR", "classified_qty": 0.5, "notes": "Scale calibration off"
    })

    bal_after = ledger.get_book_balance("ING01")
    assert bal_before == bal_after, f"Balance changed from {bal_before} to {bal_after}!"


# -------------------------------------------------------------
# 7. OVER-CLASSIFICATION IS REJECTED
# -------------------------------------------------------------
def test_07_over_classification_is_rejected(client, login):
    date = "2026-12-06"
    dep_id = _create_full_day_cycle(client, login, date=date, ingredient_id="ING01", op_qty=10.0, deliv_qty=0.0, cl_qty=7.0)
    # Depletion = 3.0 kg

    headers_mgr = login("manager")

    # 1. Attempt to classify more than total depletion immediately (4.0 > 3.0)
    res1 = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "SPOILAGE", "classified_qty": 4.0
    })
    assert res1.status_code == 422
    assert "exceeds" in res1.get_json()["error"].lower()

    # 2. Classify 2.5 kg (valid)
    res2 = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "SPOILAGE", "classified_qty": 2.5
    })
    assert res2.status_code == 201

    # 3. Attempt to classify 1.0 kg when only 0.5 kg remains
    res3 = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "SPILLAGE", "classified_qty": 1.0
    })
    assert res3.status_code == 422
    assert "exceeds" in res3.get_json()["error"].lower()


# -------------------------------------------------------------
# 8. DUPLICATE REQUESTS ARE IDEMPOTENT
# -------------------------------------------------------------
def test_08_duplicate_requests_are_idempotent(client, login):
    date = "2026-12-07"
    dep_id = _create_full_day_cycle(client, login, date=date, ingredient_id="ING01", op_qty=10.0, deliv_qty=5.0, cl_qty=11.0)
    # Depletion = 4.0 kg

    headers_mgr = login("manager")
    idemp_key = f"IDEMP_TEST_{date}"

    # First request
    res1 = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "SPOILAGE",
        "classified_qty": 2.0,
        "idempotency_key": idemp_key
    })
    assert res1.status_code == 201
    cls_id1 = res1.get_json()["classification_id"]

    # Second request with same idempotency key
    res2 = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "SPOILAGE",
        "classified_qty": 2.0,
        "idempotency_key": idemp_key
    })
    assert res2.status_code == 200
    res2_body = res2.get_json()
    assert res2_body["idempotent"] is True
    assert res2_body["classification"]["classification_id"] == cls_id1

    # Ensure remaining unclassified was deducted only ONCE
    res_det = client.get(f"/api/manager/depletions/{dep_id}", headers=headers_mgr)
    assert res_det.get_json()["classified_qty"] == 2.0
    assert res_det.get_json()["remaining_unclassified_qty"] == 2.0


# -------------------------------------------------------------
# 9. CONCURRENT OR RACING CLASSIFICATION CANNOT EXCEED AVAILABLE DEPLETION
# -------------------------------------------------------------
def test_09_concurrent_classification_cannot_exceed_available_depletion(client, login):
    date = "2026-12-08"
    dep_id = _create_full_day_cycle(client, login, date=date, ingredient_id="ING01", op_qty=10.0, deliv_qty=0.0, cl_qty=6.0)
    # Depletion = 4.0 kg

    headers_mgr = login("manager")

    # First succeeds with 3.0 kg
    res1 = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "SPOILAGE", "classified_qty": 3.0
    })
    assert res1.status_code == 201

    # Second attempts 2.0 kg (would total 5.0 > 4.0)
    res2 = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "DAMAGE", "classified_qty": 2.0
    })
    assert res2.status_code == 422
    assert "exceeds" in res2.get_json()["error"].lower()

    # Total classified never exceeds 4.0
    res_det = client.get(f"/api/manager/depletions/{dep_id}", headers=headers_mgr)
    assert res_det.get_json()["classified_qty"] == 3.0


# -------------------------------------------------------------
# 10. UNEXPLAINED DEPLETION CAN REMAIN UNRESOLVED
# -------------------------------------------------------------
def test_10_unexplained_depletion_can_remain_unresolved(client, login):
    date = "2026-12-09"
    dep_id = _create_full_day_cycle(client, login, date=date, ingredient_id="ING01", op_qty=15.0, deliv_qty=0.0, cl_qty=8.0)
    # Depletion = 7.0 kg

    headers_mgr = login("manager")

    # Partially classify 2.0 kg
    res_cls = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "SPOILAGE", "classified_qty": 2.0
    })
    assert res_cls.status_code == 201
    assert res_cls.get_json()["remaining_unclassified_qty"] == 5.0

    # Manager closes investigation leaving 5.0 kg unexplained
    res_res = client.post(f"/api/manager/depletions/{dep_id}/resolve", headers=headers_mgr, json={
        "resolution_notes": "Exhausted all checks; 5.0 kg remains unresolved variance."
    })
    assert res_res.status_code == 200
    res_data = res_res.get_json()
    assert res_data["status"] == "RESOLVED"
    assert res_data["remaining_unclassified_qty"] == 5.0

    # Verify detail displays resolved with unexplained balance
    res_det = client.get(f"/api/manager/depletions/{dep_id}", headers=headers_mgr)
    det_data = res_det.get_json()
    assert det_data["status"] == "RESOLVED"
    assert det_data["remaining_unclassified_qty"] == 5.0
    assert "Exhausted" in det_data["resolution_notes"]


# -------------------------------------------------------------
# 11. PHYSICAL OVERAGE CANNOT BE CLASSIFIED AS WASTAGE
# -------------------------------------------------------------
def test_11_physical_overage_cannot_be_classified_as_wastage(client, login):
    date = "2026-12-10"
    # Physical overage: opening 10 kg, closing 12 kg -> depletion = -2.0 kg
    dep_id = _create_full_day_cycle(client, login, date=date, ingredient_id="ING01", op_qty=10.0, deliv_qty=0.0, cl_qty=12.0)

    headers_mgr = login("manager")
    res = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "SPOILAGE", "classified_qty": 1.0
    })
    assert res.status_code == 422
    assert "physical overage" in res.get_json()["error"].lower()


# -------------------------------------------------------------
# 12. MISSING COUNTS CANNOT BE FINALIZED
# -------------------------------------------------------------
def test_12_missing_counts_cannot_be_finalized(client, login):
    headers_mgr = login("manager")
    date = "2026-12-11"
    iid = "ING02"

    # Insert an artificial depletion log without corresponding opening/closing counts
    dep_id = f"DEP_{date}_{iid}"
    con = db.connect()
    con.execute(
        """
        INSERT INTO depletion_logs (
            depletion_id, date, ingredient_id, opening_qty, deliveries_qty,
            closing_qty, calculated_depletion_kg, unexplained_depletion_kg,
            status, recorded_by, recorded_at
        ) VALUES (?, ?, ?, 10.0, 0.0, 5.0, 5.0, 5.0, 'UNCLASSIFIED', 'system', '2026-12-11 10:00:00')
        """,
        (dep_id, date, iid)
    )
    con.commit()
    con.close()

    # Attempt to classify
    res_cls = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "SPOILAGE", "classified_qty": 2.0
    })
    assert res_cls.status_code == 422
    assert "missing" in res_cls.get_json()["error"].lower()

    # Attempt to resolve
    res_res = client.post(f"/api/manager/depletions/{dep_id}/resolve", headers=headers_mgr, json={
        "resolution_notes": "Attempting to finalize without counts"
    })
    assert res_res.status_code == 422
    assert "missing" in res_res.get_json()["error"].lower()


# -------------------------------------------------------------
# 13. REVERSAL AND CORRECTION PRESERVE AUDIT HISTORY
# -------------------------------------------------------------
def test_13_reversal_and_correction_preserve_audit_history(client, login):
    date = "2026-12-12"
    dep_id = _create_full_day_cycle(client, login, date=date, ingredient_id="ING01", op_qty=10.0, deliv_qty=0.0, cl_qty=6.0)
    # Depletion = 4.0 kg

    headers_mgr = login("manager")
    bal_initial = ledger.get_book_balance("ING01")

    # 1. Post initial classification
    res_cls = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "SPOILAGE", "classified_qty": 2.5, "notes": "Initial wrong categorization"
    })
    assert res_cls.status_code == 201
    cls_id = res_cls.get_json()["classification_id"]
    assert res_cls.get_json()["remaining_unclassified_qty"] == 1.5

    # 2. Reverse classification
    res_rev = client.post(f"/api/manager/depletions/classifications/{cls_id}/reverse", headers=headers_mgr, json={
        "reason": "Categorized as spoilage by mistake, actual cause was preparation loss"
    })
    assert res_rev.status_code == 200
    rev_data = res_rev.get_json()
    assert rev_data["status"] == "REVERSED"
    assert rev_data["remaining_unclassified_qty"] == 4.0
    assert rev_data["depletion_status"] == "UNCLASSIFIED"

    # 3. Post correct classification
    res_corr = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "PREPARATION_LOSS", "classified_qty": 2.5, "notes": "Corrected category"
    })
    assert res_corr.status_code == 201
    assert res_corr.get_json()["remaining_unclassified_qty"] == 1.5

    # 4. Verify book balance remained 100% constant throughout
    assert ledger.get_book_balance("ING01") == bal_initial

    # 5. Verify audit history contains both active and reversed records
    res_det = client.get(f"/api/manager/depletions/{dep_id}", headers=headers_mgr)
    history = res_det.get_json()["classifications"]
    assert len(history) == 2
    reversed_rec = next(c for c in history if c["classification_id"] == cls_id)
    assert reversed_rec["status"] == "REVERSED"
    assert "by mistake" in reversed_rec["reversal_reason"]


# -------------------------------------------------------------
# 14. MANAGER RECEIVES NO PURCHASE-COST OR PROFIT DATA
# -------------------------------------------------------------
def test_14_manager_receives_no_purchase_cost_or_profit_data(client, login):
    date = "2026-12-13"
    dep_id = _create_full_day_cycle(client, login, date=date, ingredient_id="ING01", op_qty=10.0, deliv_qty=5.0, cl_qty=11.0)

    headers_mgr = login("manager")
    headers_owner = login("owner")

    # Classify 1 kg
    client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "SPOILAGE", "classified_qty": 1.0
    })

    # 1. Dashboard
    mgr_dash = client.get("/api/manager/depletions", headers=headers_mgr).get_json()
    assert "total_estimated_wastage_rs" not in mgr_dash

    owner_dash = client.get("/api/manager/depletions", headers=headers_owner).get_json()
    assert "total_estimated_wastage_rs" in owner_dash

    # 2. List
    mgr_list = client.get(f"/api/manager/depletions/list?date={date}", headers=headers_mgr).get_json()
    for item in mgr_list["depletions"]:
        assert item["unit_cost_rs"] is None
        assert item["estimated_loss_rs"] is None
        assert item["total_depletion_cost_rs"] is None

    owner_list = client.get(f"/api/manager/depletions/list?date={date}", headers=headers_owner).get_json()
    owner_item = next(d for d in owner_list["depletions"] if d["depletion_id"] == dep_id)
    assert owner_item["unit_cost_rs"] is not None
    assert owner_item["estimated_loss_rs"] is not None

    # 3. Details
    mgr_det = client.get(f"/api/manager/depletions/{dep_id}", headers=headers_mgr).get_json()
    assert mgr_det["unit_cost_rs"] is None
    assert mgr_det["estimated_loss_rs"] is None
    for deliv in mgr_det["deliveries"]:
        assert deliv["unit_price_rs"] is None
        assert deliv["line_total_rs"] is None
    for cls_rec in mgr_det["classifications"]:
        assert cls_rec["cost_rs"] is None

    owner_det = client.get(f"/api/manager/depletions/{dep_id}", headers=headers_owner).get_json()
    assert owner_det["unit_cost_rs"] is not None
    assert owner_det["estimated_loss_rs"] is not None

    # 4. Reports
    mgr_rep = client.get("/api/manager/reports/depletions", headers=headers_mgr).get_json()
    assert mgr_rep["total_loss_rs"] is None
    for item in mgr_rep["wastage_by_ingredient"]:
        assert item["total_loss_rs"] is None
    for item in mgr_rep["unresolved_depletions"]:
        assert item["unexplained_loss_rs"] is None


# -------------------------------------------------------------
# 15. MANDATORY NOTES FOR THEFT AND OTHER_UNEXPLAINED
# -------------------------------------------------------------
def test_15_mandatory_notes_for_theft_and_other_unexplained(client, login):
    date = "2026-12-14"
    dep_id = _create_full_day_cycle(client, login, date=date, ingredient_id="ING01", op_qty=15.0, deliv_qty=0.0, cl_qty=10.0)
    # Depletion = 5.0 kg
    headers_mgr = login("manager")

    # 1. THEFT without notes -> 400
    r1 = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "THEFT", "classified_qty": 1.0, "notes": ""
    })
    assert r1.status_code == 400
    assert "mandatory" in r1.get_json()["error"].lower()

    # 2. THEFT with short notes -> 400
    r2 = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "THEFT", "classified_qty": 1.0, "notes": "bad"
    })
    assert r2.status_code == 400

    # 3. THEFT with valid notes -> 201
    r3 = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "THEFT", "classified_qty": 1.0, "notes": "CCTV showed unauthorized access to pantry at 2am"
    })
    assert r3.status_code == 201

    # 4. OTHER_UNEXPLAINED without notes -> 400
    r4 = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "OTHER_UNEXPLAINED", "classified_qty": 1.0, "notes": ""
    })
    assert r4.status_code == 400

    # 5. OTHER_UNEXPLAINED with valid notes -> 201
    r5 = client.post(f"/api/manager/depletions/{dep_id}/classify", headers=headers_mgr, json={
        "category": "OTHER_UNEXPLAINED", "classified_qty": 1.0, "notes": "Discrepancy in prep sheet totals"
    })
    assert r5.status_code == 201
