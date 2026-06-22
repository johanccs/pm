import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from backend.main import app
from backend import database


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
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


def _mock_chat(content: str):
    """Return a context manager that stubs out the OpenAI chat completion."""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = content
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    return patch("backend.ai.get_client", return_value=mock_client)


def test_ai_ping_returns_reply(authed):
    with _mock_chat("The answer is 4."):
        resp = authed.post("/api/ai/ping")
    assert resp.status_code == 200
    assert resp.json()["reply"] == "The answer is 4."


def test_ai_ping_unauthenticated(client):
    assert client.post("/api/ai/ping").status_code == 401


def test_ai_ping_reply_not_logged(authed):
    """API key must not appear in the response."""
    os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
    with _mock_chat("4"):
        resp = authed.post("/api/ai/ping")
    assert "test-key" not in resp.text
    assert "OPENROUTER_API_KEY" not in resp.text


# --- /api/ai/chat tests ---


def _chat_response(reply: str, ops: list | None = None) -> str:
    """Build a JSON string matching AIResponse shape."""
    return json.dumps({
        "reply": reply,
        "board_update": {"ops": ops} if ops is not None else None,
    })


def test_ai_chat_unauthenticated(client):
    assert client.post("/api/ai/chat", json={"message": "hi"}).status_code == 401


def test_ai_chat_no_board_update(authed):
    """No board changes → board_update null, board returned unchanged."""
    payload = _chat_response("Here is your board summary.", ops=None)
    with _mock_chat(payload):
        resp = authed.post("/api/ai/chat", json={"message": "Summarise the board"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "Here is your board summary."
    assert "board" in data
    assert len(data["board"]["columns"]) == 5


def test_ai_chat_create_card(authed):
    """AI creates a card → card appears in the correct column."""
    board = authed.get("/api/board").json()
    first_col_id = int(board["columns"][0]["id"])
    initial_count = len(board["columns"][0]["cardIds"])

    op = {"op": "create", "column_id": first_col_id, "title": "AI card", "details": "from AI"}
    payload = _chat_response("I created a card.", ops=[op])
    with _mock_chat(payload):
        resp = authed.post("/api/ai/chat", json={"message": "Add a card"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "I created a card."
    updated_col = next(c for c in data["board"]["columns"] if int(c["id"]) == first_col_id)
    assert len(updated_col["cardIds"]) == initial_count + 1
    new_card_id = updated_col["cardIds"][-1]
    assert data["board"]["cards"][new_card_id]["title"] == "AI card"


def test_ai_chat_move_card(authed):
    """AI moves a card to another column → card appears in the new column."""
    board = authed.get("/api/board").json()
    src_col = board["columns"][0]
    dst_col = board["columns"][1]
    card_id = int(src_col["cardIds"][0])
    dst_col_id = int(dst_col["id"])
    initial_dst_count = len(dst_col["cardIds"])

    op = {"op": "update", "card_id": card_id, "column_id": dst_col_id}
    payload = _chat_response("Card moved.", ops=[op])
    with _mock_chat(payload):
        resp = authed.post("/api/ai/chat", json={"message": "Move a card"})

    assert resp.status_code == 200
    updated_board = resp.json()["board"]
    updated_src = next(c for c in updated_board["columns"] if int(c["id"]) == int(src_col["id"]))
    updated_dst = next(c for c in updated_board["columns"] if int(c["id"]) == dst_col_id)
    assert card_id not in [int(cid) for cid in updated_src["cardIds"]]
    assert card_id in [int(cid) for cid in updated_dst["cardIds"]]
    assert len(updated_dst["cardIds"]) == initial_dst_count + 1


def test_ai_chat_delete_card(authed):
    """AI deletes a card → card no longer in board."""
    board = authed.get("/api/board").json()
    first_col = board["columns"][0]
    card_id = int(first_col["cardIds"][0])

    op = {"op": "delete", "card_id": card_id}
    payload = _chat_response("Card deleted.", ops=[op])
    with _mock_chat(payload):
        resp = authed.post("/api/ai/chat", json={"message": "Delete a card"})

    assert resp.status_code == 200
    updated_board = resp.json()["board"]
    all_card_ids = [int(cid) for cid in updated_board["cards"].keys()]
    assert card_id not in all_card_ids
