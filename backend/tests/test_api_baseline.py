"""
SmartStock AI - Baseline API and Regression Test Suite.
Verifies Authentication, RBAC, Core Endpoints, Ledger & Refill Workflows, and Validation Errors.
"""
from datetime import datetime, timedelta
import time
import pytest


# -------------------------------------------------------------
# 1. AUTHENTICATION & TOKEN TESTS
# -------------------------------------------------------------
def test_01_login_invalid_password(client):
    res = client.post("/api/auth/login", json={"username": "manager", "password": "wrongpassword"})
    assert res.status_code == 401
    assert "invalid username or password" in res.get_json().get("error", "")


def test_02_login_nonexistent_user(client):
    res = client.post("/api/auth/login", json={"username": "fake_user", "password": "any"})
    assert res.status_code == 401


def test_03_login_empty_body(client):
    res = client.post("/api/auth/login", data="", content_type="application/json")
    assert res.status_code == 401


def test_04_me_endpoint_valid_token(client, login):
    for role in ["owner", "manager", "staff"]:
        res = client.get("/api/me", headers=login(role))
        assert res.status_code == 200
        assert res.get_json()["role"] == role


def test_05_me_endpoint_invalid_token(client):
    res = client.get("/api/me", headers={"Authorization": "Bearer invalid.token.signature"})
    assert res.status_code == 401


def test_06_me_endpoint_missing_token(client):
    res = client.get("/api/me")
    assert res.status_code == 401


# -------------------------------------------------------------
# 2. RBAC (ROLE-BASED ACCESS CONTROL) TESTS
# -------------------------------------------------------------
def test_07_rbac_users_endpoint(client, login):
    # Staff -> 403 Forbidden
    res_staff = client.get("/api/users", headers=login("staff"))
    assert res_staff.status_code == 403

    # Manager -> 200 OK (access to staff account management)
    res_mgr = client.get("/api/users", headers=login("manager"))
    assert res_mgr.status_code == 200
    mgr_users = res_mgr.get_json()
    assert isinstance(mgr_users, list)
    # Manager only sees staff accounts
    assert all(u["role"] == "staff" for u in mgr_users)

    # Owner -> 200 OK (access to all user accounts)
    res_owner = client.get("/api/users", headers=login("owner"))
    assert res_owner.status_code == 200
    assert isinstance(res_owner.get_json(), list)


def test_08_rbac_simulator_controls(client, login):
    # Staff -> 403 on start/stop
    res_start = client.post("/api/iot/simulator/start", json={"interval": 2.0}, headers=login("staff"))
    assert res_start.status_code == 403
    res_stop = client.post("/api/iot/simulator/stop", headers=login("staff"))
    assert res_stop.status_code == 403

    # Manager -> allowed
    res_mgr_stop = client.post("/api/iot/simulator/stop", headers=login("manager"))
    assert res_mgr_stop.status_code == 200


def test_09_rbac_reports(client, login):
    # Staff -> 403
    res_staff = client.get("/api/reports/stock_summary.csv", headers=login("staff"))
    assert res_staff.status_code == 403

    # Manager -> 200
    res_mgr = client.get("/api/reports/stock_summary.csv", headers=login("manager"))
    assert res_mgr.status_code == 200
    assert "text/csv" in res_mgr.headers.get("Content-Type", "")


def test_10_rbac_alert_acknowledgement(client, login):
    # Staff -> 403
    res_staff = client.post("/api/alerts/ack", json={"key": "test_key"}, headers=login("staff"))
    assert res_staff.status_code == 403

    # Manager -> 200
    res_mgr = client.post("/api/alerts/ack", json={"key": "test_key"}, headers=login("manager"))
    assert res_mgr.status_code == 200


def test_11_rbac_forecast_retrain(client, login):
    # Staff -> 403
    res_staff = client.post("/api/forecast/retrain", headers=login("staff"))
    assert res_staff.status_code == 403


# -------------------------------------------------------------
# 3. ENDPOINT & WORKFLOW VERIFICATION
# -------------------------------------------------------------
def test_12_dashboard_endpoint(client, login):
    res = client.get("/api/dashboard", headers=login("staff"))
    assert res.status_code == 200
    d = res.get_json()
    assert "cards" in d
    assert "rows" in d
    assert "alerts" in d
    assert "target_date" in d

    cards = d["cards"]
    for key in ["ingredients", "low_stock", "expiry_risk", "open_alerts", "stock_value_rs", "order_value_rs"]:
        assert key in cards


def test_13_ingredients_endpoint(client, login):
    res = client.get("/api/ingredients", headers=login("staff"))
    assert res.status_code == 200
    ings = res.get_json()
    assert len(ings) > 0
    i0 = ings[0]
    for f in ["ingredient_id", "name", "unit", "barcode", "shelf_life_days", "lead_time_days"]:
        assert f in i0


def test_14_barcode_lookup(client, login):
    res = client.get("/api/ingredients", headers=login("staff"))
    barcode = res.get_json()[0]["barcode"]

    b_res = client.get(f"/api/barcode/{barcode}", headers=login("staff"))
    assert b_res.status_code == 200
    assert b_res.get_json()["barcode"] == barcode

    # Invalid barcode
    b_bad = client.get("/api/barcode/9999999999999", headers=login("staff"))
    assert b_bad.status_code == 404


def test_15_stock_sheet_prefill_and_validation(client, login):
    # Prefill
    res = client.get("/api/manual-entries/prefill?ingredient_id=ING01", headers=login("staff"))
    assert res.status_code == 200
    p = res.get_json()
    assert "date" in p
    assert "opening_stock" in p

    # Save with negative values -> 422
    bad_save = client.post("/api/manual-entries", json={
        "ingredient_id": "ING01", "date": "2026-11-17",
        "opening_stock": -5, "used_qty": 2
    }, headers=login("staff"))
    assert bad_save.status_code == 422

    # Save with usage > stock -> 422
    excess_save = client.post("/api/manual-entries", json={
        "ingredient_id": "ING01", "date": "2026-11-17",
        "opening_stock": 10, "received_qty": 0, "used_qty": 20
    }, headers=login("staff"))
    assert excess_save.status_code == 422

    # Save with received stock but missing expiry -> 422
    no_expiry = client.post("/api/manual-entries", json={
        "ingredient_id": "ING01", "date": "2026-11-17",
        "opening_stock": 10, "received_qty": 5, "used_qty": 2
    }, headers=login("staff"))
    assert no_expiry.status_code == 422


def test_16_refill_session_lifecycle(client, login):
    # Find IoT-enabled ingredient
    res = client.get("/api/ingredients", headers=login("staff"))
    iot_ing = next(i for i in res.get_json() if i["iot_enabled"])
    barcode = iot_ing["barcode"]
    dev_id = iot_ing["device_id"]

    # Cancel any pre-existing open session for idempotency
    dev_res = client.get("/api/iot/devices", headers=login("staff"))
    for d in dev_res.get_json():
        if d["device_id"] == dev_id and d.get("open_session"):
            client.post(f"/api/refill/{d['open_session']}/cancel", headers=login("staff"))

    # 1. Open refill session
    open_res = client.post("/api/refill/open", json={
        "barcode": barcode, "batch_no": "TEST-BATCH-1", "expiry_date": "2026-12-01"
    }, headers=login("staff"))
    assert open_res.status_code == 201
    session = open_res.get_json()
    sid = session["session_id"]
    assert "session_id" in session

    # 2. Duplicate open session for same device should fail with 409
    dup_res = client.post("/api/refill/open", json={"barcode": barcode}, headers=login("staff"))
    assert dup_res.status_code == 409

    # 3. Cancel session
    cancel_res = client.post(f"/api/refill/{sid}/cancel", headers=login("staff"))
    assert cancel_res.status_code == 200
    assert cancel_res.get_json()["status"] == "CANCELLED"

    # Wait for the next second so session_id timestamp (resolution: 1s) changes
    time.sleep(1.1)

    # 4. Open session
    open_res2 = client.post("/api/refill/open", json={"barcode": barcode}, headers=login("staff"))
    assert open_res2.status_code == 201
    session2 = open_res2.get_json()
    sid2 = session2["session_id"]
    base_w2 = session2["weight_before_kg"]

    # 4a. Attempting to complete with no weight added must be rejected with 422
    keys = {"ESP32-RICE-01": "rice-key-123", "ESP32-OIL-01": "oil-key-123", "ESP32-ONION-01": "onion-key-123"}
    device_key = keys.get(dev_id, "rice-key-123")
    time.sleep(1.05)
    seq0 = int(time.time() * 10) % 1000000
    fresh_time0 = (datetime.now() + timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
    client.post("/api/iot/readings", headers={"X-Device-Key": device_key}, json={
        "device_id": dev_id, "weight_kg": base_w2, "seq_no": seq0, "stable": 1, "measured_at": fresh_time0
    })
    comp_fail = client.post(f"/api/refill/{sid2}/complete", headers=login("staff"))
    assert comp_fail.status_code == 422
    assert "no valid refill detected" in comp_fail.get_json().get("error", "")

    # Wait for the next second so session_id timestamp changes
    time.sleep(1.1)

    # 4b. Re-open and simulate added weight
    open_res3 = client.post("/api/refill/open", json={"barcode": barcode}, headers=login("staff"))
    assert open_res3.status_code == 201
    session3 = open_res3.get_json()
    sid3 = session3["session_id"]
    base_w = session3["weight_before_kg"]

    # Send reading from device showing weight increase (+3.0 kg)
    seq = int(time.time() * 10 + 5) % 1000000
    time.sleep(1.05)
    fresh_time = (datetime.now() + timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
    ingest_res = client.post("/api/iot/readings", headers={"X-Device-Key": device_key}, json={
        "device_id": dev_id, "weight_kg": round(base_w + 3.0, 2), "seq_no": seq, "stable": 1,
        "measured_at": fresh_time
    })
    assert ingest_res.status_code in [200, 201]

    # Now complete should succeed with 200
    comp_success = client.post(f"/api/refill/{sid3}/complete", headers=login("staff"))
    assert comp_success.status_code == 200
    assert comp_success.get_json()["status"] == "COMPLETED"
    assert comp_success.get_json()["refill_kg"] >= 0.2


def test_17_iot_devices_and_readings(client, login):
    res = client.get("/api/iot/devices", headers=login("staff"))
    assert res.status_code == 200
    devices = res.get_json()
    assert len(devices) > 0
    d0 = devices[0]
    assert "device_id" in d0
    assert "weight_kg" in d0

    # Readings query
    readings = client.get(f"/api/iot/readings?device_id={d0['device_id']}&limit=10", headers=login("staff"))
    assert readings.status_code == 200
    assert "readings" in readings.get_json()


def test_18_all_reports_generation(client, login):
    reports = [
        "stock_summary", "forecast_reorder", "model_evaluation",
        "wastage", "manual_register", "iot_daily_usage", "refill_sessions"
    ]
    for rname in reports:
        res = client.get(f"/api/reports/{rname}.csv", headers=login("manager"))
        assert res.status_code == 200, f"Report {rname} failed"
        assert len(res.get_data(as_text=True)) > 0, f"Report {rname} was empty"


def test_19_user_creation_validation(client, login):
    # Short password (<6 chars) -> 422
    res_short = client.post("/api/users", json={
        "username": "short_pw_user", "password": "123", "role": "staff", "full_name": "Test"
    }, headers=login("owner"))
    assert res_short.status_code == 422

    # Invalid role -> 422
    res_role = client.post("/api/users", json={
        "username": "bad_role_user", "password": "password123", "role": "superadmin", "full_name": "Test"
    }, headers=login("owner"))
    assert res_role.status_code == 422


def test_20_ack_input_validation(client, login):
    # Missing key -> 400
    res = client.post("/api/alerts/ack", json={}, headers=login("manager"))
    assert res.status_code == 400

    # Non-string key -> 400
    res2 = client.post("/api/alerts/ack", json={"key": 12345}, headers=login("manager"))
    assert res2.status_code == 400


def test_21_user_empty_payload(client, login):
    # Empty body -> 422
    res = client.post("/api/users", data="", headers=login("owner"), content_type="application/json")
    assert res.status_code == 422


def test_22_report_auth_enforcement(client):
    # Unauthenticated report download -> 401
    res = client.get("/api/reports/stock_summary.csv")
    assert res.status_code == 401
