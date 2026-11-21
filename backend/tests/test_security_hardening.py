"""
SmartStock AI — Security Hardening & Authorization Regression Tests.
Verifies production secret kill-switch, query-string token rejection,
active DB user existence and role revocation, and RBAC endpoint protection.
"""
import os
import pytest
from werkzeug.security import generate_password_hash
import db


def test_query_string_token_rejected(client, login):
    # Generating a valid token
    headers = login("owner")
    tok = headers["Authorization"].replace("Bearer ", "")

    # Passing token via URL query parameter must be rejected with 401
    res = client.get(f"/api/reports/stock_summary.csv?token={tok}")
    assert res.status_code == 401
    assert "Query string token authentication is disabled" in res.get_json().get("error", "")


def test_bearer_token_accepted(client, login):
    res = client.get("/api/me", headers=login("staff"))
    assert res.status_code == 200
    assert res.get_json()["username"] == "staff"


def test_deleted_user_token_immediately_invalidated(client, login):
    # 1. Create a temporary user via owner API
    res_create = client.post("/api/users", json={
        "username": "temp_fired_employee",
        "password": "password123",
        "role": "staff",
        "full_name": "Temporary Staff"
    }, headers=login("owner"))
    assert res_create.status_code == 201

    # 2. Authenticate as the temporary user to get a valid token
    res_login = client.post("/api/auth/login", json={
        "username": "temp_fired_employee",
        "password": "password123"
    })
    assert res_login.status_code == 200
    temp_tok = res_login.get_json()["token"]
    temp_header = {"Authorization": f"Bearer {temp_tok}"}

    # 3. Verify user can access /api/me
    res_me = client.get("/api/me", headers=temp_header)
    assert res_me.status_code == 200

    # 4. Now simulate employee termination: delete user from database
    with db.tx() as con:
        con.execute("DELETE FROM users WHERE username='temp_fired_employee'")

    # 5. Subsequent request with the previously valid token MUST be rejected with 401
    res_revoked = client.get("/api/me", headers=temp_header)
    assert res_revoked.status_code == 401
    assert "deactivated" in res_revoked.get_json().get("error", "") or "not authenticated" in res_revoked.get_json().get("error", "")


def test_changed_user_role_immediately_reflected(client, login):
    # 1. Create a temporary manager
    username = "temp_demoted_user"
    with db.tx() as con:
        con.execute("INSERT INTO users(username, password_hash, role, full_name) VALUES (?, ?, 'manager', 'Demoted User')",
                    (username, generate_password_hash("password123")))

    # 2. Log in and get token
    res_login = client.post("/api/auth/login", json={"username": username, "password": "password123"})
    assert res_login.status_code == 200
    tok_header = {"Authorization": f"Bearer {res_login.get_json()['token']}"}

    # 3. Access manager endpoint (/api/reports/stock_summary.csv) -> 200
    res_mgr = client.get("/api/reports/stock_summary.csv", headers=tok_header)
    assert res_mgr.status_code == 200

    # 4. Demote user in database from manager to staff
    with db.tx() as con:
        con.execute("UPDATE users SET role='staff' WHERE username=?", (username,))

    # 5. The existing token must now be restricted by the new database role -> 403 Forbidden!
    res_demoted = client.get("/api/reports/stock_summary.csv", headers=tok_header)
    assert res_demoted.status_code == 403
    assert "not authorised" in res_demoted.get_json().get("error", "")

    # Cleanup
    with db.tx() as con:
        con.execute("DELETE FROM users WHERE username=?", (username,))


def test_staff_restricted_from_admin_endpoints(client, login):
    staff_h = login("staff")
    # /api/users
    assert client.get("/api/users", headers=staff_h).status_code == 403
    assert client.post("/api/users", json={}, headers=staff_h).status_code == 403

    # /api/reports/*.csv
    assert client.get("/api/reports/stock_summary.csv", headers=staff_h).status_code == 403

    # /api/forecast/retrain
    assert client.post("/api/forecast/retrain", headers=staff_h).status_code == 403

    # /api/inventory/reconciliation
    assert client.get("/api/inventory/reconciliation", headers=staff_h).status_code == 403

    # /api/inventory/reconciliation/fix
    assert client.post("/api/inventory/reconciliation/fix", json={}, headers=staff_h).status_code == 403


def test_production_startup_secret_enforcement():
    """
    Validates the production startup fail-safe:
    1. Fails when secret is missing.
    2. Fails when secret is the default placeholder.
    3. Fails when secret is shorter than 32 characters.
    4. Succeeds when secret is explicitly set to 32+ characters.
    """
    import subprocess, sys

    # 1. Missing secret
    env_missing = dict(os.environ)
    env_missing["SMARTSTOCK_ENV"] = "production"
    env_missing.pop("SMARTSTOCK_SECRET", None)
    r1 = subprocess.run([sys.executable, "-c", "import app"], env=env_missing, capture_output=True, text=True)
    assert r1.returncode != 0
    assert "RuntimeError" in r1.stderr
    assert "SMARTSTOCK_SECRET must be explicitly set" in r1.stderr

    # 2. Default secret
    env_default = dict(os.environ)
    env_default["SMARTSTOCK_ENV"] = "production"
    env_default["SMARTSTOCK_SECRET"] = "change-me-in-production"
    r2 = subprocess.run([sys.executable, "-c", "import app"], env=env_default, capture_output=True, text=True)
    assert r2.returncode != 0
    assert "RuntimeError" in r2.stderr

    # 3. Short secret (< 32 chars)
    env_short = dict(os.environ)
    env_short["SMARTSTOCK_ENV"] = "production"
    env_short["SMARTSTOCK_SECRET"] = "too-short-secret"
    r3 = subprocess.run([sys.executable, "-c", "import app"], env=env_short, capture_output=True, text=True)
    assert r3.returncode != 0
    assert "RuntimeError" in r3.stderr

    # 4. Valid secure secret (>= 32 chars)
    env_valid = dict(os.environ)
    env_valid["SMARTSTOCK_ENV"] = "production"
    env_valid["SMARTSTOCK_SECRET"] = "a-cryptographically-secure-key-with-more-than-32-chars"
    r4 = subprocess.run([sys.executable, "-c", "import app"], env=env_valid, capture_output=True, text=True)
    assert r4.returncode == 0


def test_cors_trusted_and_untrusted_origins(client):
    """
    Validates CORS origin restrictions:
    - Configured trusted origin (http://localhost:5173) receives Access-Control-Allow-Origin.
    - Untrusted origin (http://malicious-origin.com) receives no CORS header.
    """
    res_trusted = client.get("/api/me", headers={"Origin": "http://localhost:5173"})
    assert res_trusted.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"

    res_untrusted = client.get("/api/me", headers={"Origin": "http://malicious-origin.com"})
    assert res_untrusted.headers.get("Access-Control-Allow-Origin") is None
