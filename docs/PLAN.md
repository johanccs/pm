# Project Plan: PM Kanban App

---

## Part 1: Plan

Goal: Produce a detailed, approved plan before any code is written.

- [x] Explore the existing frontend codebase
- [x] Enrich this document with substeps, tests, and success criteria for all parts
- [x] Create `frontend/AGENTS.md` describing the existing frontend
- [x] Get user sign-off on the plan

**Success criteria**
- This document is complete with checkboxes for every part
- `frontend/AGENTS.md` exists and accurately describes the code
- User has approved the plan

---

## Part 2: Scaffolding

Goal: Docker infrastructure running locally, serving a hello-world page and a working API endpoint.

- [x] Create `Dockerfile` — Python 3.12-slim base, install `uv`, copy `backend/`, expose port 8000
- [x] Create `docker-compose.yml` — single service, port 8000:8000, named volume `pm_data` mounted at `/data`
- [x] Create `backend/pyproject.toml` — FastAPI, uvicorn dependencies managed by uv
- [x] Create `backend/main.py` — FastAPI app with `GET /hello` (returns static HTML) and `GET /api/ping` (returns `{"ok": true}`)
- [x] Create `scripts/start.sh` (Mac/Linux) — `docker compose up --build -d`
- [x] Create `scripts/stop.sh` (Mac/Linux) — `docker compose down`
- [x] Create `scripts/start.ps1` (Windows) — `docker compose up --build -d`
- [x] Create `scripts/stop.ps1` (Windows) — `docker compose down`
- [x] Build and run container; verify endpoints manually

**Design decisions**
- Dockerfile reads Python dependencies from `pyproject.toml` at build time using Python's built-in `tomllib`, so the install step never goes stale when new packages are added.

**Tests & success criteria**
- Container builds without errors
- `GET http://localhost:8000/hello` → 200, HTML body
- `GET http://localhost:8000/api/ping` → 200, `{"ok": true}`
- `scripts/stop.ps1` / `stop.sh` cleanly stops the container

---

## Part 3: Add in Frontend

Goal: Next.js app statically built and served from FastAPI; Kanban board visible at `/`.

- [x] Update `frontend/next.config.ts` — set `output: "export"` and `trailingSlash: true`
- [x] Add frontend build step to `Dockerfile` — install Node, run `next build`, copy `frontend/out/` into image
- [x] Mount `frontend/out/` via FastAPI `StaticFiles` at `/` with `html=True`
- [x] Ensure `/api` routes are registered before the static mount so they are not shadowed
- [x] Rebuild container; verify board loads at root

**Tests & success criteria**
- `GET http://localhost:8000/` → 200, returns Kanban board HTML
- All static assets (JS, CSS) load without 404s
- Drag-and-drop still works in the browser (in-memory only, no persistence yet)
- Unit tests (`npm run test:unit`) pass in the frontend directory

---

## Part 4: Add in a Fake Sign-in Experience

Goal: Users must log in before seeing the board; session managed via cookie.

- [x] Add `POST /api/auth/login` — accepts `{username, password}`, validates against hardcoded credentials, sets HTTP-only session cookie — accepts `{username, password}`, validates against hardcoded `user`/`password`, sets HTTP-only session cookie, returns `{"ok": true}`
- [x] Add `POST /api/auth/logout` — clears the session cookie
- [x] Add `GET /api/auth/me` — returns `{"username": "user"}` if authenticated, 401 otherwise
- [x] Create `frontend/src/app/login/page.tsx` — login form using project color scheme
- [x] Client-side auth guard in `KanbanBoard.tsx` — calls `/api/auth/me` on mount, redirects to `/login` if 401 (Next.js middleware not available with `output: "export"`)
- [x] Logout button in `KanbanBoard.tsx` header
- [x] Backend pytest tests for all auth routes (target ~80% coverage on auth logic)
- [x] Rebuild and test end-to-end

**Tests & success criteria**
- Unauthenticated visit to `/` → JS redirects to `/login`
- Login with `user`/`password` → redirected to board
- Login with wrong credentials → error message shown, no redirect
- Logout → redirected to `/login`, board inaccessible
- Session persists across browser refresh
- Pytest: all auth route happy and error paths covered

---

## Part 5: Database Modeling

Goal: Agreed SQLite schema before any DB code is written.

- [x] Design schema: `users`, `boards`, `columns`, `cards` tables
- [x] Save schema as `docs/schema.json`
- [x] Write `docs/DATABASE.md` — explains tables, columns, relationships, and design decisions
- [x] Get user sign-off before proceeding to Part 6

**Schema (draft)**
```
users(id, username, password_hash)
boards(id, user_id, title)
columns(id, board_id, title, position)
cards(id, column_id, title, details, position)
```

**Success criteria**
- `docs/schema.json` and `docs/DATABASE.md` exist
- User has approved the schema

---

## Part 6: Backend API

Goal: Full CRUD API backed by SQLite; database created automatically on first run.

- [x] Create `backend/database.py` — `init_db()` creates tables if they don't exist; seeds `user` account, default board, and 5 columns on first run; seeds 8 demo cards whenever the board has no cards (handles both fresh DB and existing DB from a prior run)
- [x] Call `init_db()` at FastAPI startup (lifespan handler)
- [x] `GET /api/board` — returns full board JSON for authenticated user
- [x] `PUT /api/board/columns/{id}` — rename a column
- [x] `POST /api/board/cards` — create a card in a column
- [x] `PUT /api/board/cards/{id}` — update card title/details and/or move to different column/position
- [x] `DELETE /api/board/cards/{id}` — remove a card
- [x] Write pytest tests for every route (fresh SQLite temp file per test)

**Design decisions**
- All API routes return numeric string IDs (`"1"`, `"2"`, …) — the frontend adds prefixes (see Part 7)
- `init_db()` is idempotent: safe to call on every startup; seed cards are only inserted when the board is empty, so user data is never wiped

**Tests & success criteria**
- All routes return correct status codes and shapes
- Moving a card updates `column_id` and `position` correctly
- Deleting a card removes it; positions of remaining cards are compacted
- Database file created at `/data/pm.db` on first run (verified in container)
- No route accessible without valid session cookie → 401

---

## Part 7: Frontend + Backend Integration

Goal: Kanban board reads and writes to the backend; state persists across page reloads.

- [x] Create `frontend/src/lib/api.ts` — typed fetch helpers for all backend routes; prefixes all IDs from the backend (`col-{n}` / `card-{n}`) and strips the prefix before writing back
- [x] Update `KanbanBoard.tsx` — load board from `GET /api/board` on mount
- [x] Column rename: call `PUT /api/board/columns/{id}` (optimistic update)
- [x] Add card: call `POST /api/board/cards` then update state with real ID
- [x] Delete card: call `DELETE /api/board/cards/{id}` (optimistic update)
- [x] Drag-and-drop: call `PUT /api/board/cards/{id}` on drag end (optimistic update, rollback on error)
- [x] Handle loading state (return null until board is fetched)

**Design decisions**
- Backend returns raw integer IDs; `api.ts` adds `col-` / `card-` prefixes before storing in React state. This prevents `isColumnId()` in `kanban.ts` from falsely matching card IDs against column IDs (SQLite autoincrement gives both sequences starting at 1).
- All board mutations use optimistic updates with rollback on API error.

**Tests & success criteria**
- Vitest: all API helpers mocked, component tests updated
- Playwright e2e: create a card → reload → card still present; rename column → reload → name persists; drag card to new column → reload → card in new column
- No regressions in existing unit tests

---

## Part 8: AI Connectivity

Goal: Backend can call OpenRouter; connectivity verified with a simple prompt.

- [x] Add `openai` package to `backend/pyproject.toml`
- [x] Create `backend/ai.py` — OpenRouter client using `openai` SDK pointed at `https://openrouter.ai/api/v1`, model `deepseek/deepseek-chat-v3-0324` (`:free` variant removed from OpenRouter)
- [x] Add `POST /api/ai/ping` — sends `"What is 2+2?"` to the model, returns `{"reply": "<model response>"}`
- [x] Load `OPENROUTER_API_KEY` from environment (passed via `docker-compose.yml` from host `.env`)

**Design decisions**
- `POST /api/ai/ping` requires authentication (same session cookie as all other API routes).
- The OpenAI client is a lazy singleton in `get_client()` — instantiated once on first request so the missing `OPENROUTER_API_KEY` at test time doesn't cause import errors.

**Tests & success criteria**
- Unit test: `ai.py` with mocked HTTP returns correctly shaped response ✓
- Integration test (manual): `POST /api/ai/ping` returns a reply containing "4" ✓
- API key is never logged or exposed in responses ✓

---

## Part 9: AI with Kanban Context and Structured Outputs

Goal: AI receives full board context and can optionally update the board via structured outputs.

- [x] Define Pydantic response schema: `AIResponse { reply: str, board_update: BoardPatch | None }`
- [x] Define `BoardPatch` — list of card create/update/delete/move operations
- [x] Create `POST /api/ai/chat` — accepts `{ message: str, history: [{role, content}] }`; loads board for user; calls AI with system prompt (board JSON + instructions) + history + message; parses structured output; applies `board_update` if present; returns `{ reply, board }` (updated board)
- [x] System prompt instructs AI to respond in the defined JSON schema
- [x] Write pytest tests: prompt construction, mock AI responses with and without `board_update`, board mutation logic

**Tests & success criteria**
- Unit test: message with no board change → `board_update` is null, board unchanged
- Unit test: message requesting card creation → `board_update` has create op, card appears in DB
- Unit test: message requesting card move → card appears in correct column in DB
- Integration test (manual): "Add a card called Deploy to column Done" → card appears on board

---

## Part 10: AI Sidebar UI

Goal: Beautiful AI chat sidebar in the UI; board updates automatically when AI changes it.

- [x] Create `frontend/src/components/AISidebar.tsx` — collapsible panel, chat history list, text input + send button
- [x] Wire to `POST /api/ai/chat`; show assistant reply in history
- [x] On response: if board changed, update `KanbanBoard` state directly (no page reload)
- [x] Style sidebar with project colors: purple send button, navy headings, yellow accent for AI messages
- [x] Toggle sidebar open/closed from a button in the board header
- [x] Handle loading state (disable input while waiting)

**Tests & success criteria**
- Playwright e2e: open sidebar, type "Add a card called Test AI to the first column", send, see reply, see card appear on board without page reload
- Sidebar closes and reopens without losing chat history
- No regressions in board functionality (drag, rename, delete)
