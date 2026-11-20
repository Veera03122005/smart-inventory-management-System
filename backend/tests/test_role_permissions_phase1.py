"""
SmartStock AI — Phase 1 RBAC and Financial Redaction Test Suite.
Verifies role-based access control, financial field serialization redaction,
staff account administration by managers, and authorization boundaries across all roles.
"""
import pytest
from app import signer


# ------------------------------------------------------------------
# 1. STAFF RESTRICTIONS & FINANCIAL REDACTION
# ------------------------------------------------------------------
def test_staff_cannot_access_sales_endpoint(client, login):
    """Staff must be forbidden from accessing the sales API endpoint."""
    res = client.get("/api/sales", headers=login("staff"))
    assert res.status_code == 403
    assert "not authorised" in res.get_json().get("error", "").lower()


def test_staff_cannot_access_sales_report(client, login):
    """Staff must be forbidden from downloading sales reports."""
    res = client.get("/api/reports/sales.csv", headers=login("staff"))
    assert res.status_code == 403


def test_staff_dashboard_financial_redaction(client, login):
    """Staff dashboard cards must have all financial and sales figures redacted to None."""
    res = client.get("/api/dashboard", headers=login("staff"))
    assert res.status_code == 200
    cards = res.get_json()["cards"]

    # Financial fields must be redacted to None
    assert cards["stock_value_rs"] is None
    assert cards["order_value_rs"] is None
    assert cards["wastage_7d_rs"] is None
    assert cards["usage_7d_rs"] is None
    assert cards["sales_today_rs"] is None
    assert cards["sales_7d_rs"] is None

    # Operational fields must remain accessible
    assert isinstance(cards["ingredients"], int)
    assert isinstance(cards["low_stock"], int)
    assert isinstance(cards["expiry_risk"], int)
    assert isinstance(cards["open_alerts"], int)


def test_staff_ingredients_cost_redaction(client, login):
    """Staff must not see unit_cost_rs in ingredients listing."""
    res = client.get("/api/ingredients", headers=login("staff"))
    assert res.status_code == 200
    rows = res.get_json()
    assert len(rows) > 0
    for r in rows:
        assert r["unit_cost_rs"] is None
        assert "name" in r
        assert "unit" in r


def test_staff_barcode_cost_redaction(client, login):
    """Staff barcode scan must not reveal unit_cost_rs."""
    # ING01 barcode is 8901000000011
    res = client.get("/api/barcode/8901000000011", headers=login("staff"))
    assert res.status_code == 200
    data = res.get_json()
    assert data["unit_cost_rs"] is None
    assert data["name"] == "Chicken"


def test_staff_cannot_access_manager_endpoints(client, login):
    """Staff must receive 403 on all manager/owner endpoints."""
    endpoints = [
        ("GET", "/api/users", None),
        ("POST", "/api/users", {"username": "foo", "password": "password123", "role": "staff"}),
        ("GET", "/api/reports/stock_summary.csv", None),
        ("GET", "/api/reports/wastage.csv", None),
        ("POST", "/api/forecast/retrain", {}),
        ("POST", "/api/alerts/ack", {"key": "any"}),
        ("GET", "/api/inventory/transactions", None),
        ("GET", "/api/inventory/reconciliation", None),
        ("POST", "/api/iot/simulator/start", {"interval": 2.0}),
    ]
    for method, path, body in endpoints:
        if method == "GET":
            res = client.get(path, headers=login("staff"))
        else:
            res = client.post(path, json=body or {}, headers=login("staff"))
        assert res.status_code == 403, f"Expected 403 for staff on {method} {path}, got {res.status_code}"


# ------------------------------------------------------------------
# 2. MANAGER PERMISSIONS & RESTRICTIONS
# ------------------------------------------------------------------
def test_manager_can_access_sales_data(client, login):
    """Manager can access sales figures but NOT gross/net profit or purchase costs."""
    res = client.get("/api/sales", headers=login("manager"))
    assert res.status_code == 200
    data = res.get_json()

    # Must have sales figures
    assert data["today_sales_rs"] > 0
    assert data["sales_7d_rs"] > 0
    assert data["orders_today"] > 0
    assert isinstance(data["daily"], list)

    # Must NOT have profit or food cost fields
    assert "gross_profit_rs" not in data
    assert "cost_of_food_rs" not in data
    assert "food_cost_pct" not in data


def test_manager_can_download_sales_report(client, login):
    """Manager can download daily sales CSV report."""
    res = client.get("/api/reports/sales.csv", headers=login("manager"))
    assert res.status_code == 200
    assert "text/csv" in res.headers.get("Content-Type", "")
    csv_text = res.get_data(as_text=True)
    assert "date" in csv_text
    assert "gross_sales_rs" in csv_text


def test_manager_dashboard_sales_and_cost_redaction(client, login):
    """Manager sees sales figures on dashboard, but purchase costs and stock valuation are redacted."""
    res = client.get("/api/dashboard", headers=login("manager"))
    assert res.status_code == 200
    cards = res.get_json()["cards"]

    # Sales numbers must be present
    assert cards["sales_today_rs"] is not None and cards["sales_today_rs"] > 0
    assert cards["sales_7d_rs"] is not None and cards["sales_7d_rs"] > 0

    # Purchase cost, stock valuation, and costed usage/wastage must be redacted
    assert cards["stock_value_rs"] is None
    assert cards["order_value_rs"] is None
    assert cards["wastage_7d_rs"] is None
    assert cards["usage_7d_rs"] is None


def test_manager_ingredients_cost_redaction(client, login):
    """Manager cannot access unit_cost_rs in ingredients listing."""
    res = client.get("/api/ingredients", headers=login("manager"))
    assert res.status_code == 200
    for r in res.get_json():
        assert r["unit_cost_rs"] is None


def test_manager_wastage_report_redacts_cost_values(client, login):
    """Manager wastage report contains wastage quantities and reasons but NOT rupee valuation (value_rs)."""
    res = client.get("/api/reports/wastage.csv", headers=login("manager"))
    assert res.status_code == 200
    csv_text = res.get_data(as_text=True)
    # The header must NOT contain value_rs
    assert "value_rs" not in csv_text.splitlines()[0]


# ------------------------------------------------------------------
# 3. STAFF ACCOUNT MANAGEMENT BY MANAGER
# ------------------------------------------------------------------
def test_manager_view_staff_accounts(client, login):
    """Manager can list staff accounts with status and activity indicators."""
    res = client.get("/api/users", headers=login("manager"))
    assert res.status_code == 200
    users = res.get_json()
    assert isinstance(users, list)
    # Manager must only see staff accounts
    assert all(u["role"] == "staff" for u in users)
    # Must have is_active, last_active, action_count
    for u in users:
        assert "is_active" in u
        assert "action_count" in u


def test_manager_create_staff_account(client, login):
    """Manager can successfully create a new staff account."""
    payload = {
        "username": "line_cook_1",
        "password": "cookpassword123",
        "role": "staff",
        "full_name": "Line Cook Ravi"
    }
    res = client.post("/api/users", json=payload, headers=login("manager"))
    assert res.status_code == 201
    assert res.get_json()["status"] == "created"
    assert res.get_json()["username"] == "line_cook_1"

    # Newly created staff can log in
    login_res = client.post("/api/auth/login", json={"username": "line_cook_1", "password": "cookpassword123"})
    assert login_res.status_code == 200
    assert login_res.get_json()["user"]["role"] == "staff"


def test_manager_cannot_create_owner_or_manager(client, login):
    """Manager cannot create owner or manager accounts (must return 403)."""
    # Attempting to create owner
    res_owner = client.post("/api/users", json={
        "username": "rogue_owner",
        "password": "password123",
        "role": "owner",
        "full_name": "Rogue Owner"
    }, headers=login("manager"))
    assert res_owner.status_code == 403

    # Attempting to create manager
    res_mgr = client.post("/api/users", json={
        "username": "rogue_manager",
        "password": "password123",
        "role": "manager",
        "full_name": "Rogue Manager"
    }, headers=login("manager"))
    assert res_mgr.status_code == 403


def test_manager_deactivate_and_reactivate_staff(client, login):
    """Manager can toggle staff account active/inactive status."""
    # 1. Fetch staff user id
    staff_list = client.get("/api/users", headers=login("manager")).get_json()
    target_staff = [u for u in staff_list if u["username"] == "line_cook_1"][0]
    user_id = target_staff["id"]

    # 2. Deactivate
    res_deact = client.post(f"/api/users/{user_id}/toggle-status", headers=login("manager"))
    assert res_deact.status_code == 200
    assert res_deact.get_json()["is_active"] == 0

    # 3. Deactivated staff cannot log in
    res_login = client.post("/api/auth/login", json={"username": "line_cook_1", "password": "cookpassword123"})
    assert res_login.status_code == 401
    assert "deactivated" in res_login.get_json()["error"].lower()

    # 4. Reactivate
    res_react = client.post(f"/api/users/{user_id}/toggle-status", headers=login("manager"))
    assert res_react.status_code == 200
    assert res_react.get_json()["is_active"] == 1

    # 5. Reactivated staff can log in again
    res_login_ok = client.post("/api/auth/login", json={"username": "line_cook_1", "password": "cookpassword123"})
    assert res_login_ok.status_code == 200


def test_manager_cannot_modify_or_deactivate_self_or_owner(client, login):
    """Manager cannot toggle status or role of manager or owner accounts."""
    # Manager id is 2, Owner id is 1
    # Manager trying to toggle self
    res_self = client.post("/api/users/2/toggle-status", headers=login("manager"))
    assert res_self.status_code == 403

    # Manager trying to toggle owner
    res_owner = client.post("/api/users/1/toggle-status", headers=login("manager"))
    assert res_owner.status_code == 403

    # Manager trying to promote staff to owner via PATCH
    staff_list = client.get("/api/users", headers=login("manager")).get_json()
    staff_id = staff_list[0]["id"]
    res_patch = client.patch(f"/api/users/{staff_id}", json={"role": "owner"}, headers=login("manager"))
    assert res_patch.status_code == 403


# ------------------------------------------------------------------
# 4. OWNER PRIVILEGES PRESERVATION
# ------------------------------------------------------------------
def test_owner_full_governance_and_financials(client, login):
    """Owner retains full access to financials, profit, all user accounts, and cost metrics."""
    # 1. Full dashboard financials
    dash = client.get("/api/dashboard", headers=login("owner")).get_json()
    assert dash["cards"]["stock_value_rs"] > 0
    assert dash["cards"]["order_value_rs"] >= 0
    assert dash["cards"]["wastage_7d_rs"] >= 0
    assert dash["cards"]["sales_today_rs"] > 0

    # 2. Unit costs in ingredients
    ings = client.get("/api/ingredients", headers=login("owner")).get_json()
    assert all(r["unit_cost_rs"] is not None and r["unit_cost_rs"] > 0 for r in ings)

    # 3. Profit metrics in sales endpoint
    sales = client.get("/api/sales", headers=login("owner")).get_json()
    assert "gross_profit_rs" in sales
    assert "cost_of_food_rs" in sales

    # 4. Wastage valuation in reports
    wastage_csv = client.get("/api/reports/wastage.csv", headers=login("owner")).get_data(as_text=True)
    assert "value_rs" in wastage_csv

    # 5. Full user list
    all_users = client.get("/api/users", headers=login("owner")).get_json()
    roles = {u["role"] for u in all_users}
    assert "owner" in roles
    assert "manager" in roles
    assert "staff" in roles

    # 6. Owner cannot deactivate their own account
    res_self = client.post("/api/users/1/toggle-status", headers=login("owner"))
    assert res_self.status_code == 400
    assert "cannot deactivate" in res_self.get_json()["error"].lower()
