import os
from typing import Annotated, Literal, Optional, Union

from fastapi import APIRouter, Depends, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from backend import database
from backend.auth import get_current_user

router = APIRouter(prefix="/api/ai")

MODEL = "deepseek/deepseek-chat-v3-0324"

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise HTTPException(status_code=503, detail="AI not configured: OPENROUTER_API_KEY missing")
        _client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )
    return _client


async def chat(messages: list[dict]) -> str:
    response = await get_client().chat.completions.create(
        model=MODEL,
        messages=messages,
    )
    return response.choices[0].message.content


# --- Structured output models ---


class CreateOp(BaseModel):
    op: Literal["create"]
    column_id: int
    title: str
    details: str = ""


class UpdateOp(BaseModel):
    op: Literal["update"]
    card_id: int
    title: Optional[str] = None
    details: Optional[str] = None
    column_id: Optional[int] = None


class DeleteOp(BaseModel):
    op: Literal["delete"]
    card_id: int


CardOp = Annotated[Union[CreateOp, UpdateOp, DeleteOp], Field(discriminator="op")]


class BoardPatch(BaseModel):
    ops: list[CardOp]


class AIResponse(BaseModel):
    reply: str
    board_update: Optional[BoardPatch] = None


# --- Chat request ---


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


# --- Helpers ---


def _build_system_prompt(board: dict) -> str:
    lines = [
        "You are a helpful project management assistant.",
        "",
        "Current board:",
    ]
    for col in board["columns"]:
        lines.append(f'  Column {col["id"]} "{col["title"]}":')
        if col["cardIds"]:
            for cid in col["cardIds"]:
                card = board["cards"][cid]
                details = f' — {card["details"]}' if card["details"] else ""
                lines.append(f'    Card {cid}: "{card["title"]}"{details}')
        else:
            lines.append("    (empty)")
    lines += [
        "",
        'Respond ONLY with valid JSON matching this structure:',
        '{"reply": "your message", "board_update": null}',
        "",
        "If board changes are needed, set board_update to an object with an ops array:",
        '{"reply": "Done!", "board_update": {"ops": [...]}}',
        "",
        "Available ops:",
        '  {"op": "create", "column_id": <int>, "title": "<str>", "details": "<str>"}',
        '  {"op": "update", "card_id": <int>, "title": "<str>", "details": "<str>", "column_id": <int>}',
        '  {"op": "delete", "card_id": <int>}',
        "",
        "Use update with column_id to move a card. All fields except op and card_id are optional for update.",
        "Use integer IDs as shown in the board above.",
    ]
    return "\n".join(lines)


def _apply_patch(conn, username: str, patch: BoardPatch) -> None:
    for op in patch.ops:
        if isinstance(op, CreateOp):
            col = conn.execute(
                """
                SELECT c.id FROM columns c
                JOIN boards b ON c.board_id = b.id
                JOIN users  u ON b.user_id  = u.id
                WHERE c.id = ? AND u.username = ?
                """,
                (op.column_id, username),
            ).fetchone()
            if not col:
                raise HTTPException(status_code=400, detail=f"Column {op.column_id} not found")
            max_pos = conn.execute(
                "SELECT COALESCE(MAX(position), -1) FROM cards WHERE column_id = ?",
                (op.column_id,),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO cards (column_id, title, details, position) VALUES (?, ?, ?, ?)",
                (op.column_id, op.title, op.details, max_pos + 1),
            )

        elif isinstance(op, UpdateOp):
            card = conn.execute(
                """
                SELECT cards.id, cards.column_id, cards.position
                FROM cards
                JOIN columns c ON cards.column_id = c.id
                JOIN boards  b ON c.board_id      = b.id
                JOIN users   u ON b.user_id       = u.id
                WHERE cards.id = ? AND u.username = ?
                """,
                (op.card_id, username),
            ).fetchone()
            if not card:
                raise HTTPException(status_code=400, detail=f"Card {op.card_id} not found")
            if op.title is not None:
                conn.execute("UPDATE cards SET title = ? WHERE id = ?", (op.title, op.card_id))
            if op.details is not None:
                conn.execute("UPDATE cards SET details = ? WHERE id = ?", (op.details, op.card_id))
            if op.column_id is not None and op.column_id != card["column_id"]:
                old_col = card["column_id"]
                new_col = op.column_id
                old_pos = card["position"]
                target = conn.execute(
                    """
                    SELECT c.id FROM columns c
                    JOIN boards b ON c.board_id = b.id
                    JOIN users  u ON b.user_id  = u.id
                    WHERE c.id = ? AND u.username = ?
                    """,
                    (new_col, username),
                ).fetchone()
                if not target:
                    raise HTTPException(status_code=400, detail=f"Column {new_col} not found")
                # Compact old column
                conn.execute(
                    "UPDATE cards SET position = position - 1 WHERE column_id = ? AND position > ?",
                    (old_col, old_pos),
                )
                # Append to end of destination column
                new_pos = (
                    conn.execute(
                        "SELECT COALESCE(MAX(position), -1) FROM cards WHERE column_id = ?",
                        (new_col,),
                    ).fetchone()[0]
                    + 1
                )
                conn.execute(
                    "UPDATE cards SET position = position + 1 WHERE column_id = ? AND position >= ?",
                    (new_col, new_pos),
                )
                conn.execute(
                    "UPDATE cards SET column_id = ?, position = ? WHERE id = ?",
                    (new_col, new_pos, op.card_id),
                )

        elif isinstance(op, DeleteOp):
            card = conn.execute(
                """
                SELECT cards.column_id, cards.position
                FROM cards
                JOIN columns c ON cards.column_id = c.id
                JOIN boards  b ON c.board_id      = b.id
                JOIN users   u ON b.user_id       = u.id
                WHERE cards.id = ? AND u.username = ?
                """,
                (op.card_id, username),
            ).fetchone()
            if not card:
                raise HTTPException(status_code=400, detail=f"Card {op.card_id} not found")
            conn.execute("DELETE FROM cards WHERE id = ?", (op.card_id,))
            conn.execute(
                "UPDATE cards SET position = position - 1 WHERE column_id = ? AND position > ?",
                (card["column_id"], card["position"]),
            )


# --- Endpoints ---


@router.post("/ping")
async def ai_ping(_: str = Depends(get_current_user)):
    reply = await chat([{"role": "user", "content": "What is 2+2?"}])
    return {"reply": reply}


@router.post("/chat")
async def ai_chat(body: ChatRequest, username: str = Depends(get_current_user)):
    board = database.get_board_for_user(username)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    system_prompt = _build_system_prompt(board)
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    messages += [{"role": m.role, "content": m.content} for m in body.history]
    messages.append({"role": "user", "content": body.message})

    raw = await get_client().chat.completions.create(
        model=MODEL,
        messages=messages,
        response_format={"type": "json_object"},
    )
    content = raw.choices[0].message.content

    try:
        parsed = AIResponse.model_validate_json(content)
    except Exception:
        parsed = AIResponse(reply=content)

    if parsed.board_update and parsed.board_update.ops:
        conn = database.get_connection()
        try:
            with conn:
                _apply_patch(conn, username, parsed.board_update)
        finally:
            conn.close()
        board = database.get_board_for_user(username)

    return {"reply": parsed.reply, "board": board}
