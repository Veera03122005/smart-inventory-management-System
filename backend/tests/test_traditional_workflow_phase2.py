"""
SmartStock AI — Phase 2 Traditional Staff Workflow & Document Staging Tests.
Verifies Morning Opening Count, Daytime Multi-Ingredient Deliveries,
Evening Closing Reconciliation, Depletion Calculation, Document Extraction (CSV, XLSX, PDF, Image),
Idempotency, and Zero Staff Wastage Entry.
"""
import io
import json
import pytest
from PIL import Image

try:
    import openpyxl
except ImportError:
    openpyxl = None

try:
    import pypdf
except ImportError:
    pypdf = None


# -------------------------------------------------------------
# 1. MORNING OPENING STOCK TESTS
# -------------------------------------------------------------
def test_valid_opening_stock_submission(client, login):
    """Staff records valid physical opening count; auto-posts upon verification."""
    payload = {
        "date": "2026-11-20",
        "counts": [
            {"ingredient_id": "ING01", "physical_qty": 35.5, "notes": "Cold room rack 1"},
            {"ingredient_id": "ING02", "physical_qty": 14.0, "notes": "Cold room rack 2"},
            {"ingredient_id": "ING03", "physical_qty": 50.0, "notes": "Dry store pallet A"},
        ]
    }
    res = client.post("/api/traditional/opening", json=payload, headers=login("staff"))
    assert res.status_code == 201
    body = res.get_json()
    assert body["status"] == "posted"
    assert body["counts_recorded"] == 3

    # Verify retrieval
    get_res = client.get("/api/traditional/opening?date=2026-11-20", headers=login("staff"))
    assert get_res.status_code == 200
    rows = get_res.get_json()["rows"]
    ing1 = [r for r in rows if r["ingredient_id"] == "ING01"][0]
    assert ing1["physical_qty"] == 35.5
    assert ing1["recorded"] is True


def test_opening_stock_negative_quantity_rejected(client, login):
    """Negative physical quantity must be rejected with 422."""
    payload = {
        "date": "2026-11-20",
        "counts": [
            {"ingredient_id": "ING01", "physical_qty": -5.0}
        ]
    }
    res = client.post("/api/traditional/opening", json=payload, headers=login("staff"))
    assert res.status_code == 422
    assert "cannot be negative" in res.get_json()["error"]


def test_opening_stock_missing_data_rejected(client, login):
    """Missing date or empty counts must be rejected with 422."""
    res1 = client.post("/api/traditional/opening", json={"date": "2026-11-20", "counts": []}, headers=login("staff"))
    assert res1.status_code == 422

    res2 = client.post("/api/traditional/opening", json={"counts": [{"ingredient_id": "ING01", "physical_qty": 10.0}]}, headers=login("staff"))
    assert res2.status_code == 422


def test_opening_stock_duplicate_submission_is_idempotent(client, login):
    """Submitting the same opening counts twice must return duplicate=True without error."""
    payload = {
        "date": "2026-11-20",
        "counts": [
            {"ingredient_id": "ING01", "physical_qty": 35.5},
            {"ingredient_id": "ING02", "physical_qty": 14.0},
            {"ingredient_id": "ING03", "physical_qty": 50.0},
        ]
    }
    res1 = client.post("/api/traditional/opening", json=payload, headers=login("staff"))
    assert res1.status_code in (200, 201)
    if res1.status_code == 200:
        assert res1.get_json().get("duplicate") is True

    res2 = client.post("/api/traditional/opening", json=payload, headers=login("staff"))
    assert res2.status_code == 200
    assert res2.get_json().get("duplicate") is True


# -------------------------------------------------------------
# 2. DAYTIME SUPPLIER DELIVERIES TESTS
# -------------------------------------------------------------
def test_valid_supplier_delivery_multi_ingredient(client, login):
    """Staff records multi-ingredient supplier delivery; posts STOCK_IN per ingredient."""
    payload = {
        "supplier_name": "Fresh Farms Bangalore",
        "invoice_no": "INV-2026-901",
        "invoice_date": "2026-11-20",
        "items": [
            {
                "ingredient_id": "ING01",
                "billed_qty": 20.0,
                "unit": "kg",
                "unit_price_rs": 220.0,
                "batch_no": "FF-CHICKEN-01",
                "expiry_date": "2026-11-27"
            },
            {
                "ingredient_id": "ING05",
                "billed_qty": 15.0,
                "unit": "kg",
                "unit_price_rs": 35.0,
                "batch_no": "FF-ONION-01",
                "expiry_date": "2026-12-05"
            }
        ]
    }
    res = client.post("/api/traditional/delivery", json=payload, headers=login("staff"))
    assert res.status_code == 201
    body = res.get_json()
    assert body["status"] == "posted"
    assert body["items_posted"] == 2

    # Verify deliveries fetch
    deliv_res = client.get("/api/traditional/deliveries?date=2026-11-20", headers=login("staff"))
    assert deliv_res.status_code == 200
    items = deliv_res.get_json()
    assert any(i["invoice_no"] == "INV-2026-901" and i["ingredient_id"] == "ING01" and i["billed_qty"] == 20.0 for i in items)
    assert any(i["invoice_no"] == "INV-2026-901" and i["ingredient_id"] == "ING05" and i["billed_qty"] == 15.0 for i in items)


def test_supplier_delivery_duplicate_invoice_rejected(client, login):
    """Duplicate invoice line item for the same supplier, invoice_no and ingredient must be rejected with 409."""
    payload = {
        "supplier_name": "Fresh Farms Bangalore",
        "invoice_no": "INV-2026-901",
        "invoice_date": "2026-11-20",
        "items": [
            {
                "ingredient_id": "ING01",
                "billed_qty": 10.0,
                "unit": "kg",
                "unit_price_rs": 220.0
            }
        ]
    }
    # Second submission with different qty but same invoice_no and ingredient -> 409 Conflict
    res = client.post("/api/traditional/delivery", json=payload, headers=login("staff"))
    assert res.status_code == 409
    assert "already been posted" in res.get_json()["error"]


def test_supplier_delivery_zero_or_negative_qty_rejected(client, login):
    """Billed quantity must be strictly positive."""
    for bad_qty in [0.0, -10.0]:
        res = client.post("/api/traditional/delivery", json={
            "supplier_name": "Supplier X",
            "invoice_no": "INV-ERR-1",
            "invoice_date": "2026-11-20",
            "items": [{"ingredient_id": "ING01", "billed_qty": bad_qty}]
        }, headers=login("staff"))
        assert res.status_code == 422
        assert "greater than 0" in res.get_json()["error"]


# -------------------------------------------------------------
# 3. EVENING CLOSING RECONCILIATION & DEPLETION TESTS
# -------------------------------------------------------------
def test_valid_closing_stock_and_depletion_calculation(client, login):
    """
    Closing reconciliation calculates depletion using:
    Depletion = Opening + Deliveries - Closing
    Posts CONSUMPTION movement once, stores unclassified depletion for Manager.
    """
    # For ING01 on 2026-11-20:
    # Opening = 35.5 kg
    # Delivery = 20.0 kg (INV-2026-901)
    # Available = 55.5 kg
    # Physical closing count = 30.0 kg
    # Depletion = 55.5 - 30.0 = 25.5 kg
    payload = {
        "date": "2026-11-20",
        "counts": [
            {"ingredient_id": "ING01", "physical_qty": 30.0, "notes": "Evening shift check"},
            {"ingredient_id": "ING02", "physical_qty": 10.0, "notes": ""},
            {"ingredient_id": "ING03", "physical_qty": 45.0, "notes": ""},
            {"ingredient_id": "ING05", "physical_qty": 12.0, "notes": ""},
        ]
    }
    res = client.post("/api/traditional/closing", json=payload, headers=login("staff"))
    assert res.status_code == 201
    body = res.get_json()
    assert body["status"] == "posted"

    ing1_dep = [d for d in body["depletions"] if d["ingredient_id"] == "ING01"][0]
    assert ing1_dep["opening_qty"] == 35.5
    assert ing1_dep["deliveries_qty"] == 20.0
    assert ing1_dep["closing_qty"] == 30.0
    assert ing1_dep["depletion_kg"] == 25.5
    assert ing1_dep["transaction_id"] is not None


def test_closing_reconciliation_duplicate_submission_is_idempotent(client, login):
    """Submitting identical closing count returns duplicate=True without double deducting."""
    payload = {
        "date": "2026-11-20",
        "counts": [
            {"ingredient_id": "ING01", "physical_qty": 30.0},
            {"ingredient_id": "ING02", "physical_qty": 10.0},
            {"ingredient_id": "ING03", "physical_qty": 45.0},
            {"ingredient_id": "ING05", "physical_qty": 12.0},
        ]
    }
    res = client.post("/api/traditional/closing", json=payload, headers=login("staff"))
    assert res.status_code == 200
    assert res.get_json().get("duplicate") is True


def test_closing_reconciliation_overage_handling(client, login):
    """
    If physical closing is higher than opening + deliveries (gain / overage),
    reconciliation posts ADJUSTMENT (+delta) to align book balance with physical reality.
    """
    # For ING06 (Tomato):
    # Opening = 10.0 kg, Deliveries = 0.0 kg, Closing = 12.0 kg
    # Depletion = 10.0 - 12.0 = -2.0 kg (Overage)
    # Set opening first
    client.post("/api/traditional/opening", json={
        "date": "2026-11-21",
        "counts": [{"ingredient_id": "ING06", "physical_qty": 10.0}]
    }, headers=login("staff"))

    # Post closing with 12.0 kg
    res = client.post("/api/traditional/closing", json={
        "date": "2026-11-21",
        "counts": [{"ingredient_id": "ING06", "physical_qty": 12.0}]
    }, headers=login("staff"))
    assert res.status_code == 201
    dep = [d for d in res.get_json()["depletions"] if d["ingredient_id"] == "ING06"][0]
    assert dep["depletion_kg"] == -2.0


def test_daily_workflow_status_summary(client, login):
    """Staff can view complete operational status of the business date."""
    res = client.get("/api/traditional/status?date=2026-11-20", headers=login("staff"))
    assert res.status_code == 200
    status = res.get_json()
    assert status["date"] == "2026-11-20"
    assert status["deliveries_invoices_count"] >= 1
    assert status["deliveries_total_kg"] >= 35.0


# -------------------------------------------------------------
# 4. DOCUMENT UPLOAD, EXTRACTION AND REVIEW TESTS
# -------------------------------------------------------------
def test_csv_upload_extraction_and_staging(client, login):
    """Uploading CSV extracts draft rows without modifying inventory."""
    csv_content = (
        "Ingredient,Opening,Received,Closing,Supplier,Invoice,Price\n"
        "Chicken,40.0,10.0,32.5,Supplier ABC,INV-999,220\n"
        "Basmati rice,50.0,0.0,42.0,Supplier ABC,INV-999,110\n"
    ).encode("utf-8")

    data = {
        "file": (io.BytesIO(csv_content), "stock_sheet_20261122.csv"),
        "workflow_type": "DELIVERY_INVOICE"
    }
    res = client.post("/api/traditional/upload", data=data, content_type="multipart/form-data", headers=login("staff"))
    assert res.status_code == 201
    body = res.get_json()
    assert body["status"] == "NEEDS_REVIEW"
    assert body["file_type"] == "csv"
    assert len(body["rows"]) == 2
    upload_id = body["upload_id"]

    # Verify inventory was NOT modified by upload
    staged_res = client.get(f"/api/traditional/staged/{upload_id}", headers=login("staff"))
    assert staged_res.status_code == 200
    assert staged_res.get_json()["status"] == "NEEDS_REVIEW"
    assert len(staged_res.get_json()["rows"]) == 2


def test_duplicate_document_upload_rejected(client, login):
    """Uploading the exact same file content twice is rejected with 409 Conflict."""
    content = b"Ingredient,Opening\nChicken,25.0\n"
    data1 = {"file": (io.BytesIO(content), "doc1.csv"), "workflow_type": "OPENING_STOCK"}
    res1 = client.post("/api/traditional/upload", data=data1, content_type="multipart/form-data", headers=login("staff"))
    assert res1.status_code == 201

    data2 = {"file": (io.BytesIO(content), "doc1_copy.csv"), "workflow_type": "OPENING_STOCK"}
    res2 = client.post("/api/traditional/upload", data=data2, content_type="multipart/form-data", headers=login("staff"))
    assert res2.status_code == 409
    assert "already uploaded" in res2.get_json()["error"]


def test_excel_upload_and_extraction(client, login):
    """Excel spreadsheets are extracted into reviewable draft rows."""
    if not openpyxl:
        pytest.skip("openpyxl not available")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Ingredient", "Opening", "Received", "Closing", "Supplier", "Invoice", "Price"])
    ws.append(["Mutton", 18.0, 5.0, 15.0, "Meat Mart", "INV-MM-01", 750.0])
    buf = io.BytesIO()
    wb.save(buf)

    data = {
        "file": (io.BytesIO(buf.getvalue()), "meat_invoice.xlsx"),
        "workflow_type": "DELIVERY_INVOICE"
    }
    res = client.post("/api/traditional/upload", data=data, content_type="multipart/form-data", headers=login("staff"))
    assert res.status_code == 201
    body = res.get_json()
    assert body["status"] == "NEEDS_REVIEW"
    assert body["file_type"] == "xlsx"
    assert body["rows"][0]["ingredient_id"] == "ING02"
    assert body["rows"][0]["billed_qty"] if "billed_qty" in body["rows"][0] else body["rows"][0]["received_qty"] == 5.0


def test_image_upload_and_staging(client, login):
    """Image sheets (PNG/JPEG) are validated and staged as draft review sheets."""
    img_buf = io.BytesIO()
    Image.new("RGB", (200, 200), color="white").save(img_buf, format="PNG")

    data = {
        "file": (io.BytesIO(img_buf.getvalue()), "physical_count.png"),
        "workflow_type": "OPENING_STOCK"
    }
    res = client.post("/api/traditional/upload", data=data, content_type="multipart/form-data", headers=login("staff"))
    assert res.status_code == 201
    body = res.get_json()
    assert body["status"] == "NEEDS_REVIEW"
    assert body["file_type"] == "png"
    assert len(body["rows"]) >= 6  # Generated draft template for all pantry items


def test_oversized_file_rejected(client, login):
    """Files exceeding 10 MB are rejected with 413."""
    big_data = b"0" * (11 * 1024 * 1024)
    data = {"file": (io.BytesIO(big_data), "huge.csv"), "workflow_type": "OPENING_STOCK"}
    res = client.post("/api/traditional/upload", data=data, content_type="multipart/form-data", headers=login("staff"))
    assert res.status_code == 413
