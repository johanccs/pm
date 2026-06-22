from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel

from backend import database

router = APIRouter(prefix="/api/auth")


class LoginRequest(BaseModel):
    username: str
    password: str


def get_current_user(session: Optional[str] = Cookie(default=None)) -> str:
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    username = database.get_username_for_session(session)
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return username


def clear_sessions() -> None:
    database.clear_all_sessions()


@router.post("/login")
def login(body: LoginRequest, response: Response):
    stored_hash = database.get_user_password_hash(body.username)
    if not stored_hash or not database.verify_password(body.password, stored_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = database.create_session(body.username)
    response.set_cookie("session", token, httponly=True, samesite="strict")
    return {"ok": True}


@router.post("/logout")
def logout(response: Response, session: Optional[str] = Cookie(default=None)):
    if session:
        database.delete_session(session)
    response.delete_cookie("session")
    return {"ok": True}


@router.get("/me")
def me(session: Optional[str] = Cookie(default=None)):
    username = get_current_user(session)
    return {"username": username}
