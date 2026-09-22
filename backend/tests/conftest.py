import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp(prefix="pw-test-")
os.environ["APP_SECRET_KEY"] = "test-secret-key-that-is-long-enough"
os.environ["DATA_DIR"] = _tmp
os.environ["ADMIN_EMAIL"] = "admin@test.local"
os.environ["ADMIN_PASSWORD"] = "adminpass123"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def login(client: TestClient, email="admin@test.local", password="adminpass123") -> dict:
    from app.security import login_limiter

    login_limiter._hits.clear()  # tests log in far more often than a person would
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    csrf = client.cookies.get("pw_csrf")
    return {"x-csrf-token": csrf}


@pytest.fixture
def admin(client):
    return login(client)
