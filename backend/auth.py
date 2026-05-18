import secrets
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth")

# In-memory session store: token -> username
_sessions: dict[str, str] = {}

USERNAME = "user"
PASSWORD = "password"


class LoginRequest(BaseModel):
    username: str
    password: str


def get_current_user(session: Optional[str] = Cookie(default=None)) -> str:
    if not session or session not in _sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return _sessions[session]


@router.post("/login")
def login(body: LoginRequest, response: Response):
    if body.username != USERNAME or body.password != PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = secrets.token_hex(32)
    _sessions[token] = body.username
    response.set_cookie("session", token, httponly=True, samesite="lax")
    return {"ok": True}


@router.post("/logout")
def logout(response: Response, session: Optional[str] = Cookie(default=None)):
    if session:
        _sessions.pop(session, None)
    response.delete_cookie("session")
    return {"ok": True}


@router.get("/me")
def me(session: Optional[str] = Cookie(default=None)):
    username = get_current_user(session)
    return {"username": username}
