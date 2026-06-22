from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth import get_current_user
from backend import database

router = APIRouter(prefix="/api/board")


def _board_or_404(username: str) -> dict:
    board = database.get_board_for_user(username)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    return board


@router.get("")
def get_board(username: str = Depends(get_current_user)):
    return _board_or_404(username)


# --- Columns ---

class RenameColumn(BaseModel):
    title: str


@router.put("/columns/{column_id}")
def rename_column(
    column_id: int,
    body: RenameColumn,
    username: str = Depends(get_current_user),
):
    conn = database.get_connection()
    try:
        with conn:
            col = conn.execute(
                """
                SELECT c.id FROM columns c
                JOIN boards b ON c.board_id = b.id
                JOIN users  u ON b.user_id  = u.id
                WHERE c.id = ? AND u.username = ?
                """,
                (column_id, username),
            ).fetchone()
            if not col:
                raise HTTPException(status_code=404, detail="Column not found")
            conn.execute(
                "UPDATE columns SET title = ? WHERE id = ?", (body.title, column_id)
            )
    finally:
        conn.close()
    return {"ok": True}


# --- Cards ---

class CreateCard(BaseModel):
    column_id: int
    title: str
    details: str = ""


@router.post("/cards")
def create_card(body: CreateCard, username: str = Depends(get_current_user)):
    conn = database.get_connection()
    try:
        with conn:
            col = conn.execute(
                """
                SELECT c.id FROM columns c
                JOIN boards b ON c.board_id = b.id
                JOIN users  u ON b.user_id  = u.id
                WHERE c.id = ? AND u.username = ?
                """,
                (body.column_id, username),
            ).fetchone()
            if not col:
                raise HTTPException(status_code=404, detail="Column not found")

            max_pos = conn.execute(
                "SELECT COALESCE(MAX(position), -1) FROM cards WHERE column_id = ?",
                (body.column_id,),
            ).fetchone()[0]

            conn.execute(
                "INSERT INTO cards (column_id, title, details, position) VALUES (?, ?, ?, ?)",
                (body.column_id, body.title, body.details, max_pos + 1),
            )
            card_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()
    return {"id": str(card_id), "title": body.title, "details": body.details}


class UpdateCard(BaseModel):
    title: Optional[str] = None
    details: Optional[str] = None
    column_id: Optional[int] = None
    position: Optional[int] = None


@router.put("/cards/{card_id}")
def update_card(
    card_id: int,
    body: UpdateCard,
    username: str = Depends(get_current_user),
):
    conn = database.get_connection()
    try:
        with conn:
            card = conn.execute(
                """
                SELECT cards.id, cards.column_id, cards.position
                FROM cards
                JOIN columns c ON cards.column_id = c.id
                JOIN boards  b ON c.board_id      = b.id
                JOIN users   u ON b.user_id       = u.id
                WHERE cards.id = ? AND u.username = ?
                """,
                (card_id, username),
            ).fetchone()
            if not card:
                raise HTTPException(status_code=404, detail="Card not found")

            if body.title is not None:
                conn.execute(
                    "UPDATE cards SET title = ? WHERE id = ?", (body.title, card_id)
                )
            if body.details is not None:
                conn.execute(
                    "UPDATE cards SET details = ? WHERE id = ?",
                    (body.details, card_id),
                )

            if body.column_id is not None:
                old_col = card["column_id"]
                new_col = body.column_id
                old_pos = card["position"]

                if old_col != new_col:
                    # Verify target column belongs to user
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
                        raise HTTPException(
                            status_code=404, detail="Target column not found"
                        )
                    # Compact old column
                    conn.execute(
                        "UPDATE cards SET position = position - 1 WHERE column_id = ? AND position > ?",
                        (old_col, old_pos),
                    )
                    # Determine insertion position
                    new_pos = (
                        body.position
                        if body.position is not None
                        else conn.execute(
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
                        (new_col, new_pos, card_id),
                    )
                elif body.position is not None:
                    # Same column reorder
                    new_pos = body.position
                    if new_pos != old_pos:
                        if new_pos > old_pos:
                            conn.execute(
                                "UPDATE cards SET position = position - 1 WHERE column_id = ? AND position > ? AND position <= ?",
                                (old_col, old_pos, new_pos),
                            )
                        else:
                            conn.execute(
                                "UPDATE cards SET position = position + 1 WHERE column_id = ? AND position >= ? AND position < ?",
                                (old_col, new_pos, old_pos),
                            )
                        conn.execute(
                            "UPDATE cards SET position = ? WHERE id = ?",
                            (new_pos, card_id),
                        )
    finally:
        conn.close()
    return {"ok": True}


@router.delete("/cards/{card_id}")
def delete_card(card_id: int, username: str = Depends(get_current_user)):
    conn = database.get_connection()
    try:
        with conn:
            card = conn.execute(
                """
                SELECT cards.column_id, cards.position
                FROM cards
                JOIN columns c ON cards.column_id = c.id
                JOIN boards  b ON c.board_id      = b.id
                JOIN users   u ON b.user_id       = u.id
                WHERE cards.id = ? AND u.username = ?
                """,
                (card_id, username),
            ).fetchone()
            if not card:
                raise HTTPException(status_code=404, detail="Card not found")

            conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
            conn.execute(
                "UPDATE cards SET position = position - 1 WHERE column_id = ? AND position > ?",
                (card["column_id"], card["position"]),
            )
    finally:
        conn.close()
    return {"ok": True}
