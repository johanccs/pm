import hashlib
import hmac
import os
import secrets
import sqlite3

DEFAULT_COLUMNS = ["Backlog", "To Do", "In Progress", "In Review", "Done"]


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return f"{salt}:{dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, dk_hex = stored.split(":", 1)
    except ValueError:
        return False
    new_dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return hmac.compare_digest(new_dk.hex(), dk_hex)

DEFAULT_CARDS = [
    # (column_index, title, details)
    (0, "Align roadmap themes", "Draft quarterly themes with impact statements and metrics."),
    (0, "Gather customer signals", "Review support tags, sales notes, and churn feedback."),
    (1, "Prototype analytics view", "Sketch initial dashboard layout and key drill-downs."),
    (2, "Refine status language", "Standardize column labels and tone across the board."),
    (2, "Design card layout", "Add hierarchy and spacing for scanning dense lists."),
    (3, "QA micro-interactions", "Verify hover, focus, and loading states."),
    (4, "Ship marketing page", "Final copy approved and asset pack delivered."),
    (4, "Close onboarding sprint", "Document release notes and share internally."),
]


def _db_path() -> str:
    return os.environ.get("DB_PATH", "/data/pm.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_session(username: str) -> str:
    token = secrets.token_hex(32)
    conn = get_connection()
    try:
        with conn:
            conn.execute("INSERT INTO sessions (token, username) VALUES (?, ?)", (token, username))
    finally:
        conn.close()
    return token


def get_username_for_session(token: str) -> str | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT username FROM sessions WHERE token = ?", (token,)).fetchone()
        return row["username"] if row else None
    finally:
        conn.close()


def delete_session(token: str) -> None:
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    finally:
        conn.close()


def clear_all_sessions() -> None:
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM sessions")
    finally:
        conn.close()


def get_user_password_hash(username: str) -> str | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT password_hash FROM users WHERE username = ?", (username,)).fetchone()
        return row["password_hash"] if row else None
    finally:
        conn.close()


def init_db() -> None:
    conn = get_connection()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token    TEXT PRIMARY KEY,
                username TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS boards (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                title   TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS columns (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                board_id INTEGER NOT NULL REFERENCES boards(id),
                title    TEXT NOT NULL,
                position INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cards (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                column_id INTEGER NOT NULL REFERENCES columns(id),
                title     TEXT NOT NULL,
                details   TEXT DEFAULT '',
                position  INTEGER NOT NULL
            );
        """)

        # Create user + board + columns if this is a fresh database.
        user_row = conn.execute(
            "SELECT id, password_hash FROM users WHERE username = 'user'"
        ).fetchone()
        if not user_row:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("user", hash_password("password")),
            )
            user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO boards (user_id, title) VALUES (?, ?)",
                (user_id, "My Board"),
            )
            board_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            for i, title in enumerate(DEFAULT_COLUMNS):
                conn.execute(
                    "INSERT INTO columns (board_id, title, position) VALUES (?, ?, ?)",
                    (board_id, title, i),
                )
        else:
            user_id = user_row["id"]
            # Migrate old plaintext/stub hash to a real pbkdf2 hash.
            if ":" not in user_row["password_hash"]:
                conn.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (hash_password("password"), user_id),
                )
            board_row = conn.execute(
                "SELECT id FROM boards WHERE user_id = ?", (user_id,)
            ).fetchone()
            board_id = board_row["id"]

        # Seed demo cards whenever the board is empty (fresh DB or wiped board).
        card_count = conn.execute(
            """
            SELECT COUNT(*) FROM cards
            JOIN columns ON cards.column_id = columns.id
            WHERE columns.board_id = ?
            """,
            (board_id,),
        ).fetchone()[0]
        if card_count == 0:
            col_ids = [
                row["id"]
                for row in conn.execute(
                    "SELECT id FROM columns WHERE board_id = ? ORDER BY position",
                    (board_id,),
                ).fetchall()
            ]
            col_positions: dict[int, int] = {col_id: 0 for col_id in col_ids}
            for col_index, title, details in DEFAULT_CARDS:
                col_id = col_ids[col_index]
                pos = col_positions[col_id]
                conn.execute(
                    "INSERT INTO cards (column_id, title, details, position) VALUES (?, ?, ?, ?)",
                    (col_id, title, details, pos),
                )
                col_positions[col_id] = pos + 1
    conn.close()


def get_board_for_user(username: str) -> dict | None:
    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not user:
            return None

        board = conn.execute(
            "SELECT id FROM boards WHERE user_id = ?", (user["id"],)
        ).fetchone()
        if not board:
            return None

        cols = conn.execute(
            "SELECT id, title FROM columns WHERE board_id = ? ORDER BY position",
            (board["id"],),
        ).fetchall()

        result_columns = []
        result_cards: dict = {}

        for col in cols:
            cards = conn.execute(
                "SELECT id, title, details FROM cards WHERE column_id = ? ORDER BY position",
                (col["id"],),
            ).fetchall()
            card_ids = []
            for card in cards:
                cid = str(card["id"])
                result_cards[cid] = {
                    "id": cid,
                    "title": card["title"],
                    "details": card["details"] or "",
                }
                card_ids.append(cid)
            result_columns.append(
                {"id": str(col["id"]), "title": col["title"], "cardIds": card_ids}
            )

        return {"columns": result_columns, "cards": result_cards}
    finally:
        conn.close()
