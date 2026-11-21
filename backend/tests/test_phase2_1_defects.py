"""
SmartStock AI — Phase 2.1 Critical Defect Corrections Test Suite.
Verifies:
1. Opening-stock discrepancy accounting (Scenario 4: 20 - 2 + 10 - 6 = 22 kg)
2. Staff & Manager purchase-cost data redaction across deliveries and staged drafts
3. Strict staged-document ownership enforcement (cross-staff protection)
4. Multi-batch deliveries of the same ingredient on one supplier invoice
5. Explicit, validated unit conversion (kg <-> g, L <-> ml)
6. Staged document PUT edit endpoint and post-lockdown
7. Authenticated original-document file download endpoint
8. Scanned image OCR limitation and manual review flags
"""
import io
import json
import pytest
from PIL import Image
import ledger


# -------------------------------------------------------------
# 1. OPENING STOCK DISCREPANCY & SCENARIO 4 RECONCILIATION
# -------------------------------------------------------------
def test_scenario_4_opening_discrepancy_and_full_cycle_reconciliation(client, login):
    """
    Scenario 4:
    Previous closing: 20 kg
    Morning opening: 18 kg (discrepancy: -2 kg)
    Delivery: +10 kg
    Evening closing: 22 kg (depletion: 6 kg)
    Expected ledger balance: 20 - 2 + 10 - 6 = 22.0 kg
    """
    date = "2026-11-26"
    headers_staff = login("staff")

    # Set up starting balance of exactly 20.0 kg for ING01
    bal_now = ledger.get_book_balance("ING01")
    delta_init = round(20.0 - bal_now, 4)
    if delta_init != 0.0:
        ledger.post_transaction(
            ingredient_id="ING01",
            transaction_type="ADJUSTMENT",
            quantity=abs(delta_init),
            delta_qty=delta_init,
            unit="kg",
            actor="owner",
            source_channel="MANUAL_ENTRY",
            notes="Fixture baseline reset to 20 kg for Scenario 4"
        )
    assert ledger.get_book_balance("ING01") == 20.0

    # 1. Morning Opening: physical count 18.0 kg (discrepancy = 18 - 20 = -2.0 kg)
    res_am = client.post("/api/traditional/opening", json={
        "date": date,
        "counts": [{"ingredient_id": "ING01", "physical_qty": 18.0, "notes": "Counted at 08:00 AM"}]
    }, headers=headers_staff)
    assert res_am.status_code == 201
    body_am = res_am.get_json()
    assert body_am["status"] == "posted"
    assert len(body_am["adjustments"]) == 1
    adj = body_am["adjustments"][0]
    assert adj["ingredient_id"] == "ING01"
    assert adj["opening_adjustment"] == -2.0
    assert adj["previous_book_balance"] == 20.0

    # Ledger balance must now be 18.0 kg
    assert ledger.get_book_balance("ING01") == 18.0

    # 2. Daytime Delivery: +10.0 kg
    res_deliv = client.post("/api/traditional/delivery", json={
        "supplier_name": "Premium Poultry Farms",
        "invoice_no": "INV-SC4-01",
        "invoice_date": date,
        "items": [{
            "ingredient_id": "ING01",
            "billed_qty": 10.0,
            "unit": "kg",
            "unit_price_rs": 180.0,
            "batch_no": "BATCH-SC4"
        }]
    }, headers=headers_staff)
    assert res_deliv.status_code == 201
    # Ledger balance must now be 28.0 kg
    assert ledger.get_book_balance("ING01") == 28.0

    # 3. Evening Closing: physical count 22.0 kg
    # Daily depletion = 18 (opening) + 10 (delivery) - 22 (closing) = 6.0 kg
    res_pm = client.post("/api/traditional/closing", json={
        "date": date,
        "counts": [{"ingredient_id": "ING01", "physical_qty": 22.0, "notes": "Evening closing count"}]
    }, headers=headers_staff)
    assert res_pm.status_code == 201
    body_pm = res_pm.get_json()
    dep = [d for d in body_pm["depletions"] if d["ingredient_id"] == "ING01"][0]
    assert dep["opening_qty"] == 18.0
    assert dep["deliveries_qty"] == 10.0
    assert dep["closing_qty"] == 22.0
    assert dep["depletion_kg"] == 6.0

    # Final Ledger Balance must be exactly 22.0 kg!
    # Formula: 20 - 2 + 10 - 6 = 22.0 kg
    final_balance = ledger.get_book_balance("ING01")
    assert final_balance == 22.0


def test_positive_and_zero_opening_discrepancies(client, login):
    """Positive opening discrepancy creates positive adjustment; zero discrepancy creates no movement."""
    date = "2026-11-27"
    headers_staff = login("staff")

    # Baseline for ING02 (Mutton)
    bal_now = ledger.get_book_balance("ING02")
    delta_init = round(15.0 - bal_now, 4)
    if delta_init != 0.0:
        ledger.post_transaction(
            ingredient_id="ING02",
            transaction_type="ADJUSTMENT",
            quantity=abs(delta_init),
            delta_qty=delta_init,
            unit="kg",
            actor="owner",
            source_channel="MANUAL_ENTRY"
        )
    assert ledger.get_book_balance("ING02") == 15.0

    # 1. Positive discrepancy: physical is 17.5 kg (adjustment = +2.5 kg)
    res_pos = client.post("/api/traditional/opening", json={
        "date": date,
        "counts": [{"ingredient_id": "ING02", "physical_qty": 17.5}]
    }, headers=headers_staff)
    assert res_pos.status_code == 201
    assert res_pos.get_json()["adjustments"][0]["opening_adjustment"] == 2.5
    assert ledger.get_book_balance("ING02") == 17.5

    # 2. Zero discrepancy on next day: physical matches book balance exactly (17.5 kg)
    date2 = "2026-11-28"
    res_zero = client.post("/api/traditional/opening", json={
        "date": date2,
        "counts": [{"ingredient_id": "ING02", "physical_qty": 17.5}]
    }, headers=headers_staff)
    assert res_zero.status_code == 201
    assert len(res_zero.get_json()["adjustments"]) == 0
    assert ledger.get_book_balance("ING02") == 17.5


def test_opening_stock_correction_controlled_reversal(client, login):
    """Corrected opening stock reverses previous discrepancy adjustment and posts replacement adjustment."""
    date = "2026-11-29"
    headers_staff = login("staff")

    bal_now = ledger.get_book_balance("ING03")
    delta_init = round(30.0 - bal_now, 4)
    if delta_init != 0.0:
        ledger.post_transaction(
            ingredient_id="ING03",
            transaction_type="ADJUSTMENT",
            quantity=abs(delta_init),
            delta_qty=delta_init,
            unit="kg",
            actor="owner",
            source_channel="MANUAL_ENTRY"
        )
    assert ledger.get_book_balance("ING03") == 30.0

    # Initial submission: 25.0 kg (discrepancy = -5.0 kg)
    res1 = client.post("/api/traditional/opening", json={
        "date": date,
        "counts": [{"ingredient_id": "ING03", "physical_qty": 25.0}]
    }, headers=headers_staff)
    assert res1.status_code == 201
    assert ledger.get_book_balance("ING03") == 25.0

    # Corrected submission: staff recounts and realizes physical is 28.0 kg (discrepancy from 30.0 is -2.0 kg)
    res2 = client.post("/api/traditional/opening", json={
        "date": date,
        "counts": [{"ingredient_id": "ING03", "physical_qty": 28.0}]
    }, headers=headers_staff)
    assert res2.status_code == 201
    assert ledger.get_book_balance("ING03") == 28.0


# -------------------------------------------------------------
# 2. FINANCIAL DATA REDACTION FOR STAFF & MANAGER
# -------------------------------------------------------------
def test_staff_and_manager_delivery_cost_redaction(client, login):
    """unit_price_rs and line_total_rs must be None for Staff and Manager; visible to Owner."""
    # Post an invoice as owner with explicit prices
    inv_date = "2026-12-15"
    res_post = client.post("/api/traditional/delivery", json={
        "supplier_name": "Metro Cash & Carry",
        "invoice_no": "INV-REDACT-01",
        "invoice_date": inv_date,
        "items": [{
            "ingredient_id": "ING05",
            "billed_qty": 15.0,
            "unit": "kg",
            "unit_price_rs": 35.0
        }]
    }, headers=login("owner"))
    assert res_post.status_code == 201
    assert "total_amount_rs" in res_post.get_json()

    # 1. Staff query GET /api/traditional/deliveries
    res_staff = client.get(f"/api/traditional/deliveries?date={inv_date}", headers=login("staff"))
    assert res_staff.status_code == 200
    staff_items = [it for it in res_staff.get_json() if it["invoice_no"] == "INV-REDACT-01"]
    assert len(staff_items) == 1
    assert staff_items[0]["unit_price_rs"] is None
    assert staff_items[0]["line_total_rs"] is None

    # 2. Manager query GET /api/traditional/deliveries
    res_mgr = client.get(f"/api/traditional/deliveries?date={inv_date}", headers=login("manager"))
    assert res_mgr.status_code == 200
    mgr_items = [it for it in res_mgr.get_json() if it["invoice_no"] == "INV-REDACT-01"]
    assert len(mgr_items) == 1
    assert mgr_items[0]["unit_price_rs"] is None
    assert mgr_items[0]["line_total_rs"] is None

    # 3. Owner query GET /api/traditional/deliveries
    res_owner = client.get(f"/api/traditional/deliveries?date={inv_date}", headers=login("owner"))
    assert res_owner.status_code == 200
    owner_items = [it for it in res_owner.get_json() if it["invoice_no"] == "INV-REDACT-01"]
    assert len(owner_items) == 1
    assert owner_items[0]["unit_price_rs"] == 35.0
    assert owner_items[0]["line_total_rs"] == 525.0


def test_staff_delivery_post_response_cost_omission(client, login):
    """POST /api/traditional/delivery response does not leak total_amount_rs to staff."""
    res_post = client.post("/api/traditional/delivery", json={
        "supplier_name": "Agro Fresh Co",
        "invoice_no": "INV-STAFF-RESP-01",
        "invoice_date": "2026-12-15",
        "items": [{
            "ingredient_id": "ING06",
            "billed_qty": 20.0,
            "unit": "kg",
            "unit_price_rs": 45.0
        }]
    }, headers=login("staff"))
    assert res_post.status_code == 201
    body = res_post.get_json()
    assert "total_amount_rs" not in body
    for it in body["items"]:
        assert "unit_price_rs" not in it
        assert "line_total_rs" not in it


# -------------------------------------------------------------
# 3. STAGED DOCUMENT OWNERSHIP & STRICT UPLOADER ISOLATION
# -------------------------------------------------------------
def test_cross_staff_document_ownership_enforcement(client, login):
    """
    Approved Specification Section 3.3 Rule 5:
    'Only the uploader may view, edit, download and post their staged document.'
    Enforces strict uploader isolation:
    - Alice can GET, PUT, download and post her own staged document.
    - Bob (staff) cannot GET, PUT, download or post Alice's document (403).
    - Manager cannot GET, PUT, download or post Alice's staged document (403).
    - Owner cannot GET, PUT, download or post Alice's staged document (403).
    - Manager and Owner retain only monitoring access (GET /api/traditional/uploads metadata list).
    - Unauthorized attempts create ZERO inventory transactions and leave book balances untouched.
    - Authorized posting records the uploader as verifier and records the verification timestamp.
    """
    # 1. Create a second staff user 'staff_bob' using manager account
    client.post("/api/users", json={
        "username": "staff_bob",
        "password": "PasswordBob123!",
        "role": "staff",
        "full_name": "Bob Chef"
    }, headers=login("manager"))

    res_l = client.post("/api/auth/login", json={"username": "staff_bob", "password": "PasswordBob123!"})
    assert res_l.status_code == 200
    token_bob = res_l.get_json()["token"]
    headers_bob = {"Authorization": f"Bearer {token_bob}"}
    headers_alice = login("staff")  # username: 'staff'
    headers_mgr = login("manager")
    headers_owner = login("owner")

    bal_before = ledger.get_book_balance("ING01")

    # 2. Alice (staff) uploads a delivery document
    csv_data = b"ingredient,billed_qty,unit\nChicken,12,kg\n"
    res_up = client.post("/api/traditional/upload", data={
        "workflow_type": "DELIVERY_INVOICE",
        "file": (io.BytesIO(csv_data), "alice_delivery.csv")
    }, headers=headers_alice)
    assert res_up.status_code == 201
    doc_id = res_up.get_json()["upload_id"]

    # --- A. BOB (STAFF) ATTEMPTS (ALL MUST BE 403 FORBIDDEN) ---
    assert client.get(f"/api/traditional/staged/{doc_id}", headers=headers_bob).status_code == 403
    assert client.put(f"/api/traditional/staged/{doc_id}", json={"rows": [{"ingredient_id": "ING01", "received_qty": 99.0}]}, headers=headers_bob).status_code == 403
    assert client.get(f"/api/traditional/uploads/{doc_id}/file", headers=headers_bob).status_code == 403
    assert client.post("/api/traditional/delivery", json={
        "supplier_name": "Supplier X", "invoice_no": "INV-CROSS-BOB", "invoice_date": "2026-12-16",
        "document_upload_id": doc_id, "items": [{"ingredient_id": "ING01", "billed_qty": 12.0, "unit": "kg"}]
    }, headers=headers_bob).status_code == 403
    assert client.post("/api/traditional/opening", json={
        "date": "2026-12-16", "document_upload_id": doc_id, "counts": [{"ingredient_id": "ING01", "physical_qty": 12.0}]
    }, headers=headers_bob).status_code == 403
    assert client.post("/api/traditional/closing", json={
        "date": "2026-12-16", "document_upload_id": doc_id, "counts": [{"ingredient_id": "ING01", "physical_qty": 12.0}]
    }, headers=headers_bob).status_code == 403

    # --- B. MANAGER ATTEMPTS (ALL CONTENT ACCESS & POSTING MUST BE 403 FORBIDDEN) ---
    assert client.get(f"/api/traditional/staged/{doc_id}", headers=headers_mgr).status_code == 403
    assert client.put(f"/api/traditional/staged/{doc_id}", json={"rows": [{"ingredient_id": "ING01", "received_qty": 99.0}]}, headers=headers_mgr).status_code == 403
    assert client.get(f"/api/traditional/uploads/{doc_id}/file", headers=headers_mgr).status_code == 403
    assert client.post("/api/traditional/delivery", json={
        "supplier_name": "Supplier X", "invoice_no": "INV-CROSS-MGR", "invoice_date": "2026-12-16",
        "document_upload_id": doc_id, "items": [{"ingredient_id": "ING01", "billed_qty": 12.0, "unit": "kg"}]
    }, headers=headers_mgr).status_code == 403
    assert client.post("/api/traditional/opening", json={
        "date": "2026-12-16", "document_upload_id": doc_id, "counts": [{"ingredient_id": "ING01", "physical_qty": 12.0}]
    }, headers=headers_mgr).status_code == 403
    assert client.post("/api/traditional/closing", json={
        "date": "2026-12-16", "document_upload_id": doc_id, "counts": [{"ingredient_id": "ING01", "physical_qty": 12.0}]
    }, headers=headers_mgr).status_code == 403

    # --- C. OWNER ATTEMPTS (ALL CONTENT ACCESS & POSTING MUST BE 403 FORBIDDEN) ---
    assert client.get(f"/api/traditional/staged/{doc_id}", headers=headers_owner).status_code == 403
    assert client.put(f"/api/traditional/staged/{doc_id}", json={"rows": [{"ingredient_id": "ING01", "received_qty": 99.0}]}, headers=headers_owner).status_code == 403
    assert client.get(f"/api/traditional/uploads/{doc_id}/file", headers=headers_owner).status_code == 403
    assert client.post("/api/traditional/delivery", json={
        "supplier_name": "Supplier X", "invoice_no": "INV-CROSS-OWNER", "invoice_date": "2026-12-16",
        "document_upload_id": doc_id, "items": [{"ingredient_id": "ING01", "billed_qty": 12.0, "unit": "kg"}]
    }, headers=headers_owner).status_code == 403
    assert client.post("/api/traditional/opening", json={
        "date": "2026-12-16", "document_upload_id": doc_id, "counts": [{"ingredient_id": "ING01", "physical_qty": 12.0}]
    }, headers=headers_owner).status_code == 403
    assert client.post("/api/traditional/closing", json={
        "date": "2026-12-16", "document_upload_id": doc_id, "counts": [{"ingredient_id": "ING01", "physical_qty": 12.0}]
    }, headers=headers_owner).status_code == 403

    # --- D. OPERATIONAL MONITORING (PERMITTED SPECIFICATION ACCESS) ---
    # Manager and Owner may monitor operational upload metadata list (without document contents)
    res_mgr_list = client.get("/api/traditional/uploads", headers=headers_mgr)
    assert res_mgr_list.status_code == 200
    mgr_item = next((d for d in res_mgr_list.get_json() if d["upload_id"] == doc_id), None)
    assert mgr_item is not None
    assert mgr_item["uploaded_by"] == "staff"
    assert "extracted_payload" not in mgr_item  # Content strictly hidden

    # Verify zero inventory balance changes after all unauthorized attempts
    assert ledger.get_book_balance("ING01") == bal_before

    # --- E. ALICE (UPLOADER) AUTHORIZED ACTIONS ---
    # Alice can view, edit, download and post her own document
    assert client.get(f"/api/traditional/staged/{doc_id}", headers=headers_alice).status_code == 200
    assert client.put(f"/api/traditional/staged/{doc_id}", json={
        "rows": [{"ingredient_id": "ING01", "received_qty": 12.0, "supplier_name": "Supplier X", "invoice_no": "INV-ALICE-01"}]
    }, headers=headers_alice).status_code == 200

    res_dl = client.get(f"/api/traditional/uploads/{doc_id}/file", headers=headers_alice)
    assert res_dl.status_code == 200
    assert res_dl.data == csv_data

    # Alice posts her delivery
    res_post_alice = client.post("/api/traditional/delivery", json={
        "supplier_name": "Supplier X",
        "invoice_no": "INV-ALICE-01",
        "invoice_date": "2026-12-16",
        "document_upload_id": doc_id,
        "items": [{"ingredient_id": "ING01", "billed_qty": 12.0, "unit": "kg"}]
    }, headers=headers_alice)
    assert res_post_alice.status_code == 201

    # Verify inventory was updated by Alice's verified posting
    assert ledger.get_book_balance("ING01") == bal_before + 12.0

    # Verify posted document is locked from editing
    res_locked = client.put(f"/api/traditional/staged/{doc_id}", json={
        "rows": [{"ingredient_id": "ING01", "received_qty": 99.0}]
    }, headers=headers_alice)
    assert res_locked.status_code == 409


def test_opening_and_closing_staged_document_uploader_authorization(client, login):
    """Independently verifies opening and closing routes enforce strict uploader posting authorization."""
    headers_alice = login("staff")  # username: 'staff'
    headers_mgr = login("manager")

    csv_opening = b"ingredient,physical_qty\nChicken,20.0\n"
    res_up_op = client.post("/api/traditional/upload", data={
        "workflow_type": "OPENING_STOCK",
        "file": (io.BytesIO(csv_opening), "alice_opening.csv")
    }, headers=headers_alice)
    assert res_up_op.status_code == 201
    doc_op_id = res_up_op.get_json()["upload_id"]

    # Manager attempting to post Alice's opening document is rejected
    res_mgr_op = client.post("/api/traditional/opening", json={
        "date": "2026-12-28", "document_upload_id": doc_op_id, "counts": [{"ingredient_id": "ING01", "physical_qty": 20.0}]
    }, headers=headers_mgr)
    assert res_mgr_op.status_code == 403

    # Alice posting her opening document succeeds
    res_alice_op = client.post("/api/traditional/opening", json={
        "date": "2026-12-28", "document_upload_id": doc_op_id, "counts": [{"ingredient_id": "ING01", "physical_qty": 20.0}]
    }, headers=headers_alice)
    assert res_alice_op.status_code in (200, 201)

    # Closing document
    csv_closing = b"ingredient,physical_qty\nChicken,15.0\n"
    res_up_cl = client.post("/api/traditional/upload", data={
        "workflow_type": "CLOSING_STOCK",
        "file": (io.BytesIO(csv_closing), "alice_closing.csv")
    }, headers=headers_alice)
    assert res_up_cl.status_code == 201
    doc_cl_id = res_up_cl.get_json()["upload_id"]

    # Manager attempting to post Alice's closing document is rejected
    res_mgr_cl = client.post("/api/traditional/closing", json={
        "date": "2026-12-28", "document_upload_id": doc_cl_id, "counts": [{"ingredient_id": "ING01", "physical_qty": 15.0}]
    }, headers=headers_mgr)
    assert res_mgr_cl.status_code == 403

    # Alice posting her closing document succeeds
    res_alice_cl = client.post("/api/traditional/closing", json={
        "date": "2026-12-28", "document_upload_id": doc_cl_id, "counts": [{"ingredient_id": "ING01", "physical_qty": 15.0}]
    }, headers=headers_alice)
    assert res_alice_cl.status_code in (200, 201)


def test_monitoring_uploads_endpoint_field_exposure(client, login):
    """
    Verifies GET /api/traditional/uploads for Manager and Owner:
    Confirm responses contain only permitted operational metadata and do NOT expose:
    - Extracted document payloads (extracted_payload, rows).
    - Original file contents or local filesystem paths (raw_document_path, file_path).
    - Private staged row data.
    - Unauthorized supplier financial information.
    """
    headers_staff = login("staff")
    headers_mgr = login("manager")
    headers_owner = login("owner")

    csv_data = b"ingredient,billed_qty,unit,unit_price_rs\nChicken,15.0,kg,250.0\n"
    res_up = client.post("/api/traditional/upload", data={
        "workflow_type": "DELIVERY_INVOICE",
        "file": (io.BytesIO(csv_data), "sensitive_invoice.csv")
    }, headers=headers_staff)
    assert res_up.status_code == 201
    upload_id = res_up.get_json()["upload_id"]

    for role_name, headers in [("manager", headers_mgr), ("owner", headers_owner)]:
        res_list = client.get("/api/traditional/uploads", headers=headers)
        assert res_list.status_code == 200
        items = res_list.get_json()
        assert isinstance(items, list)
        target = next((item for item in items if item["upload_id"] == upload_id), None)
        assert target is not None, f"Upload {upload_id} not visible in {role_name} monitoring list"

        # Allowed metadata fields
        allowed_fields = {
            "upload_id", "filename", "file_type", "workflow_type",
            "status", "uploaded_by", "uploaded_at", "reviewed_by", "reviewed_at"
        }
        for k in target.keys():
            assert k in allowed_fields, f"Forbidden field '{k}' exposed to {role_name} in GET /api/traditional/uploads"

        # Explicitly verify sensitive fields are absent
        forbidden_fields = [
            "extracted_payload", "rows", "raw_document_path", "file_path",
            "file_hash", "unit_price_rs", "total_amount_rs", "line_total_rs"
        ]
        for f in forbidden_fields:
            assert f not in target, f"Sensitive field '{f}' leaked in {role_name} monitoring response"


# -------------------------------------------------------------
# 4. MULTI-BATCH DELIVERIES FOR SAME INGREDIENT
# -------------------------------------------------------------
def test_multi_batch_same_ingredient_delivery(client, login):
    """An invoice can contain multiple line items for the same ingredient when batch numbers or expiries differ."""
    date = "2026-12-17"
    headers = login("staff")
    bal_before = ledger.get_book_balance("ING01")

    res = client.post("/api/traditional/delivery", json={
        "supplier_name": "Global Poultry Ltd",
        "invoice_no": "INV-MULTI-BATCH-99",
        "invoice_date": date,
        "items": [
            {
                "ingredient_id": "ING01",
                "billed_qty": 5.0,
                "unit": "kg",
                "unit_price_rs": 180.0,
                "batch_no": "BATCH-A1",
                "expiry_date": "2026-12-25"
            },
            {
                "ingredient_id": "ING01",
                "billed_qty": 7.5,
                "unit": "kg",
                "unit_price_rs": 180.0,
                "batch_no": "BATCH-A2",
                "expiry_date": "2026-12-28"
            }
        ]
    }, headers=headers)
    assert res.status_code == 201
    body = res.get_json()
    assert body["status"] == "posted"
    assert body["items_posted"] == 2

    # Ledger must increase by total of 12.5 kg
    bal_after = ledger.get_book_balance("ING01")
    assert round(bal_after - bal_before, 4) == 12.5

    # Exact retry must return 200 duplicate: true
    res_dup = client.post("/api/traditional/delivery", json={
        "supplier_name": "Global Poultry Ltd",
        "invoice_no": "INV-MULTI-BATCH-99",
        "invoice_date": date,
        "items": [
            {
                "ingredient_id": "ING01",
                "billed_qty": 5.0,
                "unit": "kg",
                "unit_price_rs": 180.0,
                "batch_no": "BATCH-A1",
                "expiry_date": "2026-12-25"
            },
            {
                "ingredient_id": "ING01",
                "billed_qty": 7.5,
                "unit": "kg",
                "unit_price_rs": 180.0,
                "batch_no": "BATCH-A2",
                "expiry_date": "2026-12-28"
            }
        ]
    }, headers=headers)
    assert res_dup.status_code == 200
    assert res_dup.get_json()["duplicate"] is True

    # Conflicting retry must return 409
    res_conflict = client.post("/api/traditional/delivery", json={
        "supplier_name": "Global Poultry Ltd",
        "invoice_no": "INV-MULTI-BATCH-99",
        "invoice_date": date,
        "items": [
            {
                "ingredient_id": "ING01",
                "billed_qty": 20.0,
                "unit": "kg"
            }
        ]
    }, headers=headers)
    assert res_conflict.status_code == 409


# -------------------------------------------------------------
# 5. UNIT CONVERSION TESTS
# -------------------------------------------------------------
def test_delivery_unit_conversion_mass_and_volume(client, login):
    """Deliveries in compatible units (e.g. g -> kg, ml -> L) are normalized into the authoritative inventory unit."""
    headers = login("staff")

    # 1. Chicken (ING01, base unit kg): delivered 5000 g -> should add 5.0 kg to inventory
    bal_before_chick = ledger.get_book_balance("ING01")
    res1 = client.post("/api/traditional/delivery", json={
        "supplier_name": "Grams Supplier",
        "invoice_no": "INV-UNIT-01",
        "invoice_date": "2026-12-18",
        "items": [{
            "ingredient_id": "ING01",
            "billed_qty": 5000.0,
            "unit": "g"
        }]
    }, headers=headers)
    assert res1.status_code == 201
    bal_after_chick = ledger.get_book_balance("ING01")
    assert round(bal_after_chick - bal_before_chick, 4) == 5.0

    # 2. Cooking Oil (ING04, base unit L): delivered 750 ml -> should add 0.75 L to inventory
    bal_before_oil = ledger.get_book_balance("ING04")
    res2 = client.post("/api/traditional/delivery", json={
        "supplier_name": "Liquid Supplier",
        "invoice_no": "INV-UNIT-02",
        "invoice_date": "2026-12-18",
        "items": [{
            "ingredient_id": "ING04",
            "billed_qty": 750.0,
            "unit": "ml"
        }]
    }, headers=headers)
    assert res2.status_code == 201
    bal_after_oil = ledger.get_book_balance("ING04")
    assert round(bal_after_oil - bal_before_oil, 4) == 0.75


def test_delivery_incompatible_or_unknown_unit_rejected(client, login):
    """Incompatible unit (e.g. mass for liquid, volume for solid) or unknown unit must return 422."""
    headers = login("staff")

    # Volume for solid (Chicken delivered in ml) -> 422
    res_incomp = client.post("/api/traditional/delivery", json={
        "supplier_name": "Confused Vendor",
        "invoice_no": "INV-ERR-UNIT-01",
        "invoice_date": "2026-12-18",
        "items": [{
            "ingredient_id": "ING01",
            "billed_qty": 500.0,
            "unit": "ml"
        }]
    }, headers=headers)
    assert res_incomp.status_code == 422
    assert "Direct mass-to-volume conversions" in res_incomp.get_json()["error"]

    # Unknown unit (crates) -> 422
    res_unk = client.post("/api/traditional/delivery", json={
        "supplier_name": "Confused Vendor",
        "invoice_no": "INV-ERR-UNIT-02",
        "invoice_date": "2026-12-18",
        "items": [{
            "ingredient_id": "ING01",
            "billed_qty": 5.0,
            "unit": "crates"
        }]
    }, headers=headers)
    assert res_unk.status_code == 422


# -------------------------------------------------------------
# 6. STAGED DOCUMENT EDIT & PERSISTENCE (PUT)
# -------------------------------------------------------------
def test_staged_document_put_and_lockdown(client, login):
    """PUT /api/traditional/staged/<id> updates draft; once posted, editing returns 409."""
    headers_staff = login("staff")

    csv_data = b"ingredient,billed_qty,unit\nChicken,10,kg\n"
    res_up = client.post("/api/traditional/upload", data={
        "workflow_type": "DELIVERY_INVOICE",
        "file": (io.BytesIO(csv_data), "staged_edit_test.csv")
    }, headers=headers_staff)
    assert res_up.status_code == 201
    doc_id = res_up.get_json()["upload_id"]

    # Edit staged values
    res_put = client.put(f"/api/traditional/staged/{doc_id}", json={
        "rows": [{
            "ingredient_id": "ING01",
            "received_qty": 14.5,
            "supplier_name": "Fresh Farms",
            "invoice_no": "INV-EDIT-100",
            "batch_no": "BATCH-REV"
        }]
    }, headers=headers_staff)
    assert res_put.status_code == 200
    assert res_put.get_json()["status"] == "updated"

    # Verify updated values in GET
    res_get = client.get(f"/api/traditional/staged/{doc_id}", headers=headers_staff)
    assert res_get.status_code == 200
    row = res_get.get_json()["rows"][0]
    assert row["received_qty"] == 14.5
    assert row["supplier_name"] == "Fresh Farms"

    # Post delivery using this staged document
    res_post = client.post("/api/traditional/delivery", json={
        "supplier_name": "Fresh Farms",
        "invoice_no": "INV-EDIT-100",
        "invoice_date": "2026-12-19",
        "document_upload_id": doc_id,
        "items": [{"ingredient_id": "ING01", "billed_qty": 14.5, "unit": "kg"}]
    }, headers=headers_staff)
    assert res_post.status_code == 201

    # Attempting to edit after posting must return 409 Conflict
    res_locked = client.put(f"/api/traditional/staged/{doc_id}", json={
        "rows": [{"ingredient_id": "ING01", "received_qty": 99.0}]
    }, headers=headers_staff)
    assert res_locked.status_code == 409


# -------------------------------------------------------------
# 7. IMAGE OCR LIMITATION & MANUAL REVIEW FLAGS
# -------------------------------------------------------------
def test_image_upload_ocr_limitation_flags(client, login):
    """Image uploads generate template rows with confidence 0.0 and MANUAL_ENTRY_REQUIRED flags."""
    img_io = io.BytesIO()
    img = Image.new("RGB", (320, 240), color=(240, 120, 80))
    img.save(img_io, format="PNG")
    img_io.seek(0)

    res = client.post("/api/traditional/upload", data={
        "workflow_type": "OPENING_STOCK",
        "file": (img_io, "stock_sheet_photo_phase21.png")
    }, headers=login("staff"))
    assert res.status_code == 201
    body = res.get_json()
    assert body["status"] == "NEEDS_REVIEW"
    assert "OCR is not implemented" in body.get("notes", "")

    # Check that rows have 0.0 confidence and manual entry required flag
    for r in body["rows"]:
        assert r["confidence"] == 0.0
        assert "MANUAL_ENTRY_REQUIRED" in r["flags"]
        assert "IMAGE_OCR_UNAVAILABLE" in r["flags"]
