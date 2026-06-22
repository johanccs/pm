import os
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend import database


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    """Give each test a fresh SQLite file."""
    db_file = str(tmp_path / "test.db")
    os.environ["DB_PATH"] = db_file
    database.init_db()
    yield
    del os.environ["DB_PATH"]



@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture
def authed(client):
    resp = client.post(
        "/api/auth/login", json={"username": "user", "password": "password"}
    )
    assert resp.status_code == 200
    client.cookies.set("session", resp.cookies["session"])
    return client


# --- GET /api/board ---

def test_get_board_structure(authed):
    resp = authed.get("/api/board")
    assert resp.status_code == 200
    data = resp.json()
    assert "columns" in data and "cards" in data
    assert len(data["columns"]) == 5
    titles = [c["title"] for c in data["columns"]]
    assert titles == ["Backlog", "To Do", "In Progress", "In Review", "Done"]
    assert len(data["cards"]) == 8


def test_get_board_unauthenticated(client):
    assert client.get("/api/board").status_code == 401


# --- PUT /api/board/columns/{id} ---

def test_rename_column(authed):
    col_id = authed.get("/api/board").json()["columns"][0]["id"]
    resp = authed.put(f"/api/board/columns/{col_id}", json={"title": "Sprint 1"})
    assert resp.status_code == 200
    board = authed.get("/api/board").json()
    assert board["columns"][0]["title"] == "Sprint 1"


def test_rename_column_not_found(authed):
    assert authed.put("/api/board/columns/9999", json={"title": "X"}).status_code == 404


def test_rename_column_unauthenticated(client):
    assert client.put("/api/board/columns/1", json={"title": "X"}).status_code == 401


# --- POST /api/board/cards ---

def test_create_card(authed):
    col_id = int(authed.get("/api/board").json()["columns"][0]["id"])
    resp = authed.post(
        "/api/board/cards",
        json={"column_id": col_id, "title": "My Card", "details": "Some details"},
    )
    assert resp.status_code == 200
    card = resp.json()
    assert card["title"] == "My Card"
    assert card["details"] == "Some details"
    board = authed.get("/api/board").json()
    assert card["id"] in board["cards"]
    assert card["id"] in board["columns"][0]["cardIds"]


def test_create_card_no_details(authed):
    col_id = int(authed.get("/api/board").json()["columns"][0]["id"])
    resp = authed.post("/api/board/cards", json={"column_id": col_id, "title": "No details"})
    assert resp.status_code == 200


def test_create_card_invalid_column(authed):
    assert authed.post("/api/board/cards", json={"column_id": 9999, "title": "X"}).status_code == 404


def test_create_card_unauthenticated(client):
    assert client.post("/api/board/cards", json={"column_id": 1, "title": "X"}).status_code == 401


# --- DELETE /api/board/cards/{id} ---

def test_delete_card(authed):
    col_id = int(authed.get("/api/board").json()["columns"][0]["id"])
    card = authed.post("/api/board/cards", json={"column_id": col_id, "title": "Gone"}).json()
    assert authed.delete(f"/api/board/cards/{card['id']}").status_code == 200
    board = authed.get("/api/board").json()
    assert card["id"] not in board["cards"]


def test_delete_card_compacts_positions(authed):
    col_id = int(authed.get("/api/board").json()["columns"][0]["id"])
    c1 = authed.post("/api/board/cards", json={"column_id": col_id, "title": "A"}).json()
    c2 = authed.post("/api/board/cards", json={"column_id": col_id, "title": "B"}).json()
    c3 = authed.post("/api/board/cards", json={"column_id": col_id, "title": "C"}).json()
    authed.delete(f"/api/board/cards/{c2['id']}")
    board = authed.get("/api/board").json()
    col_cards = board["columns"][0]["cardIds"]
    assert c2["id"] not in col_cards
    assert col_cards.index(c1["id"]) < col_cards.index(c3["id"])


def test_delete_card_not_found(authed):
    assert authed.delete("/api/board/cards/9999").status_code == 404


# --- PUT /api/board/cards/{id} ---

def test_update_card_title_and_details(authed):
    col_id = int(authed.get("/api/board").json()["columns"][0]["id"])
    card = authed.post("/api/board/cards", json={"column_id": col_id, "title": "Old"}).json()
    assert authed.put(f"/api/board/cards/{card['id']}", json={"title": "New", "details": "d"}).status_code == 200
    board = authed.get("/api/board").json()
    assert board["cards"][card["id"]]["title"] == "New"
    assert board["cards"][card["id"]]["details"] == "d"


def test_move_card_to_different_column(authed):
    cols = authed.get("/api/board").json()["columns"]
    col1_id = int(cols[0]["id"])
    col2_id = int(cols[1]["id"])
    card = authed.post("/api/board/cards", json={"column_id": col1_id, "title": "Move"}).json()
    assert authed.put(f"/api/board/cards/{card['id']}", json={"column_id": col2_id}).status_code == 200
    board = authed.get("/api/board").json()
    assert card["id"] in next(c for c in board["columns"] if c["id"] == str(col2_id))["cardIds"]
    assert card["id"] not in next(c for c in board["columns"] if c["id"] == str(col1_id))["cardIds"]


def test_reorder_card_same_column(authed):
    col_id = int(authed.get("/api/board").json()["columns"][0]["id"])
    c1 = authed.post("/api/board/cards", json={"column_id": col_id, "title": "First"}).json()
    c2 = authed.post("/api/board/cards", json={"column_id": col_id, "title": "Second"}).json()
    # Move c2 to position 0 (before c1)
    assert authed.put(f"/api/board/cards/{c2['id']}", json={"column_id": col_id, "position": 0}).status_code == 200
    board = authed.get("/api/board").json()
    col_cards = board["columns"][0]["cardIds"]
    assert col_cards.index(c2["id"]) < col_cards.index(c1["id"])


def test_update_card_not_found(authed):
    assert authed.put("/api/board/cards/9999", json={"title": "X"}).status_code == 404
