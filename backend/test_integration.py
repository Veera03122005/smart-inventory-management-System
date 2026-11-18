"""
Comprehensive Integration & Regression Test Suite for SmartStock AI API.
Tests Authentication, RBAC, All Endpoints, Workflows, Security, and Error Handling.
"""
import sys
import unittest
import requests

BASE_URL = "http://localhost:5000"


class SmartStockIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Authenticate users
        cls.tokens = {}
        for role, user, pwd in [
            ("owner", "owner", "owner123"),
            ("manager", "manager", "manager123"),
            ("staff", "staff", "staff123"),
        ]:
            res = requests.post(f"{BASE_URL}/api/auth/login", json={"username": user, "password": pwd})
            assert res.status_code == 200, f"Login failed for {user}: {res.text}"
            cls.tokens[role] = res.json()["token"]

    def auth_header(self, role):
        return {"Authorization": f"Bearer {self.tokens[role]}"}

    # -------------------------------------------------------------
    # 1. AUTHENTICATION & TOKEN TESTS
    # -------------------------------------------------------------
    def test_01_login_invalid_password(self):
        res = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "manager", "password": "wrongpassword"})
        self.assertEqual(res.status_code, 401)
        self.assertIn("invalid username or password", res.json().get("error", ""))

    def test_02_login_nonexistent_user(self):
        res = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "fake_user", "password": "any"})
        self.assertEqual(res.status_code, 401)

    def test_03_login_empty_body(self):
        res = requests.post(f"{BASE_URL}/api/auth/login", data="", headers={"Content-Type": "application/json"})
        self.assertEqual(res.status_code, 401)

    def test_04_me_endpoint_valid_token(self):
        for role in ["owner", "manager", "staff"]:
            res = requests.get(f"{BASE_URL}/api/me", headers=self.auth_header(role))
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["role"], role)

    def test_05_me_endpoint_invalid_token(self):
        res = requests.get(f"{BASE_URL}/api/me", headers={"Authorization": "Bearer invalid.token.signature"})
        self.assertEqual(res.status_code, 401)

    def test_06_me_endpoint_missing_token(self):
        res = requests.get(f"{BASE_URL}/api/me")
        self.assertEqual(res.status_code, 401)

    # -------------------------------------------------------------
    # 2. RBAC (ROLE-BASED ACCESS CONTROL) TESTS
    # -------------------------------------------------------------
    def test_07_rbac_users_endpoint(self):
        # Staff -> 403
        res = requests.get(f"{BASE_URL}/api/users", headers=self.auth_header("staff"))
        self.assertEqual(res.status_code, 403)
        # Manager -> 403
        res = requests.get(f"{BASE_URL}/api/users", headers=self.auth_header("manager"))
        self.assertEqual(res.status_code, 403)
        # Owner -> 200
        res = requests.get(f"{BASE_URL}/api/users", headers=self.auth_header("owner"))
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)

    def test_08_rbac_simulator_controls(self):
        # Staff -> 403 on start/stop/spill
        res = requests.post(f"{BASE_URL}/api/iot/simulator/start", json={"interval": 2.0}, headers=self.auth_header("staff"))
        self.assertEqual(res.status_code, 403)
        res = requests.post(f"{BASE_URL}/api/iot/simulator/stop", headers=self.auth_header("staff"))
        self.assertEqual(res.status_code, 403)
        # Manager -> allowed
        res = requests.post(f"{BASE_URL}/api/iot/simulator/stop", headers=self.auth_header("manager"))
        self.assertEqual(res.status_code, 200)

    def test_09_rbac_reports(self):
        # Staff -> 403
        res = requests.get(f"{BASE_URL}/api/reports/stock_summary.csv", headers=self.auth_header("staff"))
        self.assertEqual(res.status_code, 403)
        # Manager -> 200
        res = requests.get(f"{BASE_URL}/api/reports/stock_summary.csv", headers=self.auth_header("manager"))
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/csv", res.headers.get("Content-Type", ""))

    def test_10_rbac_alert_acknowledgement(self):
        # Staff -> 403
        res = requests.post(f"{BASE_URL}/api/alerts/ack", json={"key": "test_key"}, headers=self.auth_header("staff"))
        self.assertEqual(res.status_code, 403)
        # Manager -> 200
        res = requests.post(f"{BASE_URL}/api/alerts/ack", json={"key": "test_key"}, headers=self.auth_header("manager"))
        self.assertEqual(res.status_code, 200)

    def test_11_rbac_forecast_retrain(self):
        # Staff -> 403
        res = requests.post(f"{BASE_URL}/api/forecast/retrain", headers=self.auth_header("staff"))
        self.assertEqual(res.status_code, 403)

    # -------------------------------------------------------------
    # 3. ENDPOINT & WORKFLOW VERIFICATION
    # -------------------------------------------------------------
    def test_12_dashboard_endpoint(self):
        res = requests.get(f"{BASE_URL}/api/dashboard", headers=self.auth_header("staff"))
        self.assertEqual(res.status_code, 200)
        d = res.json()
        self.assertIn("cards", d)
        self.assertIn("rows", d)
        self.assertIn("alerts", d)
        self.assertIn("target_date", d)
        # Verify card structure
        cards = d["cards"]
        for key in ["ingredients", "low_stock", "expiry_risk", "open_alerts", "stock_value_rs", "order_value_rs"]:
            self.assertIn(key, cards)

    def test_13_ingredients_endpoint(self):
        res = requests.get(f"{BASE_URL}/api/ingredients", headers=self.auth_header("staff"))
        self.assertEqual(res.status_code, 200)
        ings = res.json()
        self.assertGreater(len(ings), 0)
        # Check first ingredient
        i0 = ings[0]
        for f in ["ingredient_id", "name", "unit", "barcode", "shelf_life_days", "lead_time_days"]:
            self.assertIn(f, i0)

    def test_14_barcode_lookup(self):
        res = requests.get(f"{BASE_URL}/api/ingredients", headers=self.auth_header("staff"))
        barcode = res.json()[0]["barcode"]
        b_res = requests.get(f"{BASE_URL}/api/barcode/{barcode}", headers=self.auth_header("staff"))
        self.assertEqual(b_res.status_code, 200)
        self.assertEqual(b_res.json()["barcode"], barcode)

        # Invalid barcode
        b_bad = requests.get(f"{BASE_URL}/api/barcode/9999999999999", headers=self.auth_header("staff"))
        self.assertEqual(b_bad.status_code, 404)

    def test_15_stock_sheet_prefill_and_validation(self):
        # Prefill
        res = requests.get(f"{BASE_URL}/api/manual-entries/prefill?ingredient_id=ING01", headers=self.auth_header("staff"))
        self.assertEqual(res.status_code, 200)
        p = res.json()
        self.assertIn("date", p)
        self.assertIn("opening_stock", p)

        # Save with negative values -> should fail with 422
        bad_save = requests.post(f"{BASE_URL}/api/manual-entries", json={
            "ingredient_id": "ING01", "date": "2026-11-17",
            "opening_stock": -5, "used_qty": 2
        }, headers=self.auth_header("staff"))
        self.assertEqual(bad_save.status_code, 422)

        # Save with usage > stock -> should fail with 422
        excess_save = requests.post(f"{BASE_URL}/api/manual-entries", json={
            "ingredient_id": "ING01", "date": "2026-11-17",
            "opening_stock": 10, "received_qty": 0, "used_qty": 20
        }, headers=self.auth_header("staff"))
        self.assertEqual(excess_save.status_code, 422)

        # Save with received stock but missing expiry -> should fail with 422
        no_expiry = requests.post(f"{BASE_URL}/api/manual-entries", json={
            "ingredient_id": "ING01", "date": "2026-11-17",
            "opening_stock": 10, "received_qty": 5, "used_qty": 2
        }, headers=self.auth_header("staff"))
        self.assertEqual(no_expiry.status_code, 422)

    def test_16_refill_session_lifecycle(self):
        # Find IoT enabled ingredient
        res = requests.get(f"{BASE_URL}/api/ingredients", headers=self.auth_header("staff"))
        iot_ing = next(i for i in res.json() if i["iot_enabled"])
        barcode = iot_ing["barcode"]
        dev_id = iot_ing["device_id"]

        # Cancel any pre-existing open session to ensure test idempotency
        dev_res = requests.get(f"{BASE_URL}/api/iot/devices", headers=self.auth_header("staff"))
        for d in dev_res.json():
            if d["device_id"] == dev_id and d.get("open_session"):
                requests.post(f"{BASE_URL}/api/refill/{d['open_session']}/cancel", headers=self.auth_header("staff"))

        # 1. Open refill session
        open_res = requests.post(f"{BASE_URL}/api/refill/open", json={
            "barcode": barcode, "batch_no": "TEST-BATCH-1", "expiry_date": "2026-12-01"
        }, headers=self.auth_header("staff"))
        self.assertEqual(open_res.status_code, 201)
        session = open_res.json()
        sid = session["session_id"]
        self.assertIn("session_id", session)

        # 2. Duplicate open session for same device should fail with 409
        dup_res = requests.post(f"{BASE_URL}/api/refill/open", json={"barcode": barcode}, headers=self.auth_header("staff"))
        self.assertEqual(dup_res.status_code, 409)

        # 3. Cancel session
        cancel_res = requests.post(f"{BASE_URL}/api/refill/{sid}/cancel", headers=self.auth_header("staff"))
        self.assertEqual(cancel_res.status_code, 200)
        self.assertEqual(cancel_res.json()["status"], "CANCELLED")

        # 4. Open session
        open_res2 = requests.post(f"{BASE_URL}/api/refill/open", json={"barcode": barcode}, headers=self.auth_header("staff"))
        self.assertEqual(open_res2.status_code, 201)
        session2 = open_res2.json()
        sid2 = session2["session_id"]
        base_w = session2["weight_before_kg"]
        dev_id = session2["device_id"]

        # 4a. Attempting to complete with no weight added must be rejected with 422
        comp_fail = requests.post(f"{BASE_URL}/api/refill/{sid2}/complete", headers=self.auth_header("staff"))
        self.assertEqual(comp_fail.status_code, 422)
        self.assertIn("no valid refill detected", comp_fail.json().get("error", ""))

        # 4b. Re-open and simulate added weight
        open_res3 = requests.post(f"{BASE_URL}/api/refill/open", json={"barcode": barcode}, headers=self.auth_header("staff"))
        self.assertEqual(open_res3.status_code, 201)
        session3 = open_res3.json()
        sid3 = session3["session_id"]

        # Send reading from device showing weight increase (+3.0 kg)
        keys = {"ESP32-RICE-01": "rice-key-123", "ESP32-OIL-01": "oil-key-123", "ESP32-ONION-01": "onion-key-123"}
        device_key = keys.get(dev_id, "rice-key-123")
        import time
        seq = int(time.time() * 100) % 1000000
        ingest_res = requests.post(f"{BASE_URL}/api/iot/readings", headers={"X-Device-Key": device_key}, json={
            "device_id": dev_id, "weight_kg": round(base_w + 3.0, 2), "seq_no": seq, "stable": 1
        })
        self.assertIn(ingest_res.status_code, [200, 201])

        # Now complete should succeed with 200
        comp_success = requests.post(f"{BASE_URL}/api/refill/{sid3}/complete", headers=self.auth_header("staff"))
        self.assertEqual(comp_success.status_code, 200)
        self.assertEqual(comp_success.json()["status"], "COMPLETED")
        self.assertGreaterEqual(comp_success.json()["refill_kg"], 0.2)

    def test_17_iot_devices_and_readings(self):
        res = requests.get(f"{BASE_URL}/api/iot/devices", headers=self.auth_header("staff"))
        self.assertEqual(res.status_code, 200)
        devices = res.json()
        self.assertGreater(len(devices), 0)
        d0 = devices[0]
        self.assertIn("device_id", d0)
        self.assertIn("weight_kg", d0)

        # Readings query
        readings = requests.get(f"{BASE_URL}/api/iot/readings?device_id={d0['device_id']}&limit=10", headers=self.auth_header("staff"))
        self.assertEqual(readings.status_code, 200)
        self.assertIn("readings", readings.json())

    def test_18_all_reports_generation(self):
        reports = [
            "stock_summary", "forecast_reorder", "model_evaluation",
            "wastage", "manual_register", "iot_daily_usage", "refill_sessions"
        ]
        for rname in reports:
            res = requests.get(f"{BASE_URL}/api/reports/{rname}.csv", headers=self.auth_header("manager"))
            self.assertEqual(res.status_code, 200, f"Report {rname} failed")
            self.assertTrue(len(res.text) > 0, f"Report {rname} was empty")

    def test_19_user_creation_validation(self):
        # Short password (<6 chars) -> 422
        res = requests.post(f"{BASE_URL}/api/users", json={
            "username": "short_pw_user", "password": "123", "role": "staff", "full_name": "Test"
        }, headers=self.auth_header("owner"))
        self.assertEqual(res.status_code, 422)

        # Invalid role -> 422
        res = requests.post(f"{BASE_URL}/api/users", json={
            "username": "bad_role_user", "password": "password123", "role": "superadmin", "full_name": "Test"
        }, headers=self.auth_header("owner"))
        self.assertEqual(res.status_code, 422)

    def test_20_ack_input_validation(self):
        # Missing key -> 400
        res = requests.post(f"{BASE_URL}/api/alerts/ack", json={}, headers=self.auth_header("manager"))
        self.assertEqual(res.status_code, 400)
        # Non-string key -> 400
        res2 = requests.post(f"{BASE_URL}/api/alerts/ack", json={"key": 12345}, headers=self.auth_header("manager"))
        self.assertEqual(res2.status_code, 400)

    def test_21_user_empty_payload(self):
        # Empty body -> 422
        res = requests.post(f"{BASE_URL}/api/users", data="", headers={**self.auth_header("owner"), "Content-Type": "application/json"})
        self.assertEqual(res.status_code, 422)

    def test_22_report_auth_enforcement(self):
        # Unauthenticated report download -> 401
        res = requests.get(f"{BASE_URL}/api/reports/stock_summary.csv")
        self.assertEqual(res.status_code, 401)


if __name__ == "__main__":
    unittest.main()
