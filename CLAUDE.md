# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A Kanban project-management app: a Next.js frontend (static export) served by a FastAPI backend, backed by SQLite, with an AI chat sidebar powered by OpenRouter (DeepSeek model). The app requires login (`user` / `password`) before the board is visible.

## Running the app

Requires Docker. Copy `.env.example` to `.env` and add your `OPENROUTER_API_KEY`.

```powershell
# Start
.\scripts\start.ps1   # Windows
# or
./scripts/start.sh    # Mac/Linux

# Stop
.\scripts\stop.ps1
```

App runs at `http://localhost:8000`. The SQLite database is stored in Docker volume `pm_data` at `/data/pm.db`.

## Backend development

The backend uses `uv` for dependency management inside a virtual environment.

```powershell
# Run tests (from repo root)
cd backend
uv run pytest

# Run a single test file
uv run pytest tests/test_board.py

# Run a single test
uv run pytest tests/test_board.py::test_create_card
```

Tests use `DB_PATH` env var to point each test at a fresh `tmp_path` SQLite file — no mocking of the database layer.

To add a dependency: edit `backend/pyproject.toml`; the Dockerfile reads it at build time automatically.

## Frontend development

```bash
cd frontend
npm install

# Dev server (proxies /api to localhost:8000 if configured)
npm run dev

# Unit tests (Vitest + Testing Library)
npm run test:unit

# Watch mode
npm run test:unit:watch

# E2E tests (Playwright — requires running app)
npm run test:e2e

# Lint
npm run lint
```

## Architecture

### Request flow

```
Browser → FastAPI (port 8000)
  /api/*     → Python route handlers (auth, board, ai routers)
  /*         → StaticFiles serving frontend/out/ (Next.js static export)
```

API routes are registered **before** the static mount so they are never shadowed.

### Backend modules

| File | Role |
|------|------|
| `backend/main.py` | FastAPI app, lifespan calls `init_db()`, mounts static files last |
| `backend/auth.py` | Session cookie auth; hardcoded `user`/`password`; `get_current_user` dependency |
| `backend/database.py` | `init_db()` (idempotent schema + seed), `get_board_for_user()`, `get_connection()` |
| `backend/board.py` | CRUD routes for columns and cards; manages `position` integer ordering |
| `backend/ai.py` | OpenRouter client (lazy singleton), `/api/ai/ping`, `/api/ai/chat` with structured outputs |

### ID prefix convention (critical)

The backend stores plain integer IDs. `database.get_board_for_user()` returns them as plain strings (`"1"`, `"2"`). `frontend/src/lib/api.ts` adds `col-` / `card-` prefixes before storing in React state, and strips them before writing back. This prevents the `isColumnId()` helper in `kanban.ts` from falsely matching card IDs against column IDs (SQLite autoincrement gives both sequences starting at 1).

### AI chat flow

`POST /api/ai/chat` → loads the user's board → builds a system prompt containing the full board JSON → calls DeepSeek via OpenRouter with `response_format: json_object` → parses into `AIResponse { reply, board_update }` → if `board_update` has ops, `_apply_patch()` mutates the DB in a transaction → returns `{ reply, board }` (refreshed board). The frontend replaces its local board state directly from the response — no page reload needed.

### Frontend state

`KanbanBoard.tsx` owns all board state. On mount it calls `fetchBoard()`, which redirects to `/login/` on 401. Board mutations use optimistic updates with rollback on API error. The `AISidebar` receives `setBoard` as a prop and calls it when the AI response includes a board change.

### Database

SQLite at `/data/pm.db` (or `DB_PATH` env var). Schema: `users → boards → columns → cards`, each with an integer `position` field maintained by the board routes. `init_db()` is idempotent: safe on every startup; demo cards are only seeded when the board is empty.
