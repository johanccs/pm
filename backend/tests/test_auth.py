import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend import auth


@pytest.fixture(autouse=True)
def clear_sessions():
    """Reset session store between tests."""
    auth._sessions.clear()
    yield
    auth._sessions.clear()


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture
def authed_client(client):
    """TestClient with a valid session cookie already set."""
    resp = client.post("/api/auth/login", json={"username": "user", "password": "password"})
    assert resp.status_code == 200
    client.cookies.set("session", resp.cookies["session"])
    return client


# --- Login ---

def test_login_success(client):
    resp = client.post("/api/auth/login", json={"username": "user", "password": "password"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert "session" in resp.cookies


def test_login_wrong_password(client):
    resp = client.post("/api/auth/login", json={"username": "user", "password": "wrong"})
    assert resp.status_code == 401


def test_login_wrong_username(client):
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "password"})
    assert resp.status_code == 401


def test_login_empty_credentials(client):
    resp = client.post("/api/auth/login", json={"username": "", "password": ""})
    assert resp.status_code == 401


# --- /me ---

def test_me_authenticated(authed_client):
    resp = authed_client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json() == {"username": "user"}


def test_me_unauthenticated(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_invalid_token(client):
    client.cookies.set("session", "invalid-token")
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


# --- Logout ---

def test_logout_clears_session(authed_client):
    logout_resp = authed_client.post("/api/auth/logout")
    assert logout_resp.status_code == 200
    me_resp = authed_client.get("/api/auth/me")
    assert me_resp.status_code == 401


def test_logout_without_session(client):
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200


# --- Other routes unaffected ---

def test_ping(client):
    resp = client.get("/api/ping")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy"}
