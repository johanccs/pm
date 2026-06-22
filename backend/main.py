import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.ai import router as ai_router
from backend.auth import router as auth_router
from backend.board import router as board_router
from backend.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(auth_router)
app.include_router(board_router)
app.include_router(ai_router)


@app.get("/hello", response_class=HTMLResponse)
def hello():
    return "<html><body><h1>Hello from PM backend</h1></body></html>"


@app.get("/api/ping")
def ping():
    return {"ok": True}


@app.get("/health")
def health():
    return {"status": "healthy"}


# Mount static files last — API routes above take precedence
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
