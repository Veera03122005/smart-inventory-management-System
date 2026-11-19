import os
import sys
import tempfile
import pytest

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Set up isolated temporary database and ML cache
_tmp_dir = tempfile.TemporaryDirectory()
_tmp_db = os.path.join(_tmp_dir.name, "test_smartstock.db")
_tmp_cache = os.path.join(_tmp_dir.name, "test_model_cache.json")

os.environ["SMARTSTOCK_DB"] = _tmp_db

import db
import ml
import seed_db
from app import app as flask_app

# Force modules to use temporary paths
db.DB_PATH = _tmp_db
ml.CACHE_FILE = _tmp_cache
ml._cache = {"run_at": None, "results": {}}
seed_db.DATA = os.path.join(BACKEND_DIR, "data")

# Seed the temporary database
seed_db.seed(fresh=True)

# Pre-train models into the temporary cache so test queries are instant
ml.train_all()


def pytest_sessionfinish(session, exitstatus):
    """Cleanup temporary files after test run."""
    try:
        _tmp_dir.cleanup()
    except Exception:
        pass


@pytest.fixture(scope="session")
def app():
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture(scope="session")
def client(app):
    return app.test_client()


@pytest.fixture(scope="session")
def login(client):
    """Helper login(role) that authenticates and returns auth headers."""
    tokens = {}
    for role, pwd in [
        ("owner", "owner123"),
        ("manager", "manager123"),
        ("staff", "staff123"),
    ]:
        res = client.post("/api/auth/login", json={"username": role, "password": pwd})
        assert res.status_code == 200, f"Login failed for {role}: {res.get_data(as_text=True)}"
        tokens[role] = res.get_json()["token"]

    def _login(role: str) -> dict:
        if role not in tokens:
            raise KeyError(f"Unknown test role '{role}', expected one of {list(tokens.keys())}")
        return {"Authorization": f"Bearer {tokens[role]}"}

    return _login
