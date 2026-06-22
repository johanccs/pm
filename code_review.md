# Code Review Report

Reviewed: all backend Python modules, frontend components, tests, and infrastructure files.

---

## Summary

The codebase is well-structured and mostly clean for its MVP scope. The main concerns are security issues that should be addressed before any real deployment, a few correctness bugs, and some test coverage gaps.

---

## Security

### S1 — Hardcoded credentials in `auth.py` (HIGH)
`USERNAME = "user"` and `PASSWORD = "password"` are plain-text constants. The `password_hash` column exists in the DB schema for a reason — it was designed for bcrypt but never wired up.

**Action:** Hash the password with `bcrypt` or `passlib` and validate against `users.password_hash` instead of the hardcoded constants. Remove `USERNAME` and `PASSWORD` from `auth.py`.

### S2 — Sessions lost on server restart (`auth.py`)
`_sessions` is an in-memory dict. Every container restart (or redeploy) silently logs out all users. This will confuse users with no error message — their board simply won't load and the app redirects to login.

**Action:** Store sessions in SQLite (a `sessions` table with `token TEXT PK, username TEXT, expires_at INTEGER`) or add a signed cookie (e.g., using `itsdangerous`). Either fixes the restart problem.

### S3 — No CSRF protection on state-changing API routes
The session cookie has `samesite="lax"` which provides some protection, but cross-site POST requests from a form submission are still allowed under `lax`. Board mutation routes (`POST /api/board/cards`, `PUT`, `DELETE`) and auth routes accept any same-site or navigation-originated cross-site request.

**Action:** Use `samesite="strict"`, or add a CSRF token check on all non-GET routes. `samesite="strict"` is the simpler fix for a single-domain app.

### S4 — `OPENROUTER_API_KEY` missing at startup raises `KeyError` on first AI request
`get_client()` does `os.environ["OPENROUTER_API_KEY"]` — if the key is absent (e.g., `.env` not created), the first call to any `/api/ai/*` route will crash with an unhandled `KeyError`, leaking a 500 traceback.

**Action:** Use `os.environ.get("OPENROUTER_API_KEY")` and raise an `HTTPException(503, "AI not configured")` explicitly, or validate the key at startup in the lifespan handler.

---

## Correctness

### C1 — `kanban.ts` has dead code: `initialData` and `createId` are unused
`initialData` (the hardcoded in-memory board) and `createId` are exported from `kanban.ts` but never imported anywhere in the app — the board now comes from the API.

**Action:** Delete both. They create confusion about whether the app uses static or dynamic data.

### C2 — Playwright e2e test references `card-card-1` / `column-col-review` (stale IDs)
`kanban.spec.ts` line 22 uses `getByTestId("card-card-1")` and line 23 uses `getByTestId("column-col-review")`. These are the old static IDs from `initialData`. The backend-driven board uses numeric IDs (`col-1`, `card-1`, etc.) and the columns are named differently (`col-4` is "In Review", not `col-review`). This test will always fail against a real server.

**Action:** Update the e2e drag-and-drop test to use backend-assigned IDs (e.g., `card-1`, `col-4`) or look up elements by visible text instead of test IDs.

### C3 — `AISidebar` receives `board` prop but doesn't use it
```tsx
export const AISidebar = ({ board: _board, onBoardUpdate, ... })
```
`_board` is immediately discarded. The sidebar builds its chat messages from local state and sends history to the API, but never reads the current board. The prop exists but does nothing.

**Action:** Remove the `board` prop from `AISidebarProps` and the `KanbanBoard` usage, since it's unused and adds noise.

### C4 — `handleAddCard` in `KanbanBoard.tsx` is not optimistic
All other mutations (rename, move, delete) use optimistic update + rollback. `handleAddCard` awaits the API call before updating state. On a slow connection this creates a lag where the user clicks "Add Card" and sees nothing happen for several seconds.

**Action:** Either add optimistic update with a temporary card ID (replaced with the real ID on response), or keep await but disable the form while the request is in-flight so the user has feedback.

### C5 — Position compaction after card move in `board.py` doesn't shift destination column
`PUT /api/board/cards/{id}` shifts destination-column positions up (`position + 1 WHERE position >= new_pos`) when moving cross-column, but `ai.py`'s `_apply_patch` for `UpdateOp` does **not** — it just appends to the end without shifting. This means an AI-triggered move that specifies an insertion position mid-column will produce duplicate position values.

**Action:** Apply the same shift logic in `_apply_patch` that exists in `board.py`, or (simpler) always append to the end and remove the `position` concept from `UpdateOp`.

---

## Test Coverage Gaps

### T1 — No test for `GET /api/board` column/card ordering
Tests verify that the board shape is returned but don't assert that cards appear in the correct position order (ascending by `position`). A bug in the ORDER BY clause would go undetected.

**Action:** Add a test that creates two cards, then checks they appear in insertion order, and that deleting the first card makes the second card appear first.

### T2 — No test for same-column card reorder
`test_reorder_card_same_column` covers the happy path but there's no test for reordering when `new_pos > old_pos` vs `new_pos < old_pos` (the two branches in `board.py:185–198`).

**Action:** Add two parameterised tests: move card from position 0→2 and from position 2→0.

### T3 — Frontend unit tests use raw numeric IDs in SEED_BOARD
`KanbanBoard.test.tsx` seeds `id: "1"` without the `col-` prefix. The real `prefixBoard()` in `api.ts` always adds the prefix. If a test patches `fetch` to return `SEED_BOARD` (which the `makeFetch` helper does), the component renders with `id: "1"` rather than `col-1`. This means the test's `column-1` test-id matches, but any code path that calls `colNum()` to strip the prefix would produce `1` rather than the intended empty string from stripping `col-`.

**Action:** Update `SEED_BOARD` in the test to reflect what the real API returns — raw numeric IDs without prefixes — and verify `prefixBoard` is applied through the real `fetchBoard` code path, not bypassed by the mock.

---

## Code Quality

### Q1 — `database.py:init_db()` mixes schema creation and seed in one function
The function is correct and idempotent, but it's doing three jobs: DDL, user/board seed, and card seed. It's hard to test each concern in isolation.

**Action:** (Optional / low priority) Extract `_seed_user_and_board(conn)` and `_seed_cards(conn, board_id)` as private helpers called from `init_db`.

### Q2 — `backend/main.py` imports `auth` router but `auth.py` is not listed in tests' module list
`test_auth.py` imports `from backend import auth` and directly manipulates `auth._sessions`. This works but creates tight coupling to a private implementation detail. If sessions are moved to DB (see S2), the test fixture breaks silently.

**Action:** Expose a `clear_sessions()` function in `auth.py` for test teardown rather than directly accessing `_sessions`.

### Q3 — `frontend/src/lib/kanban.ts` exports `initialData` with hard-coded column names that conflict with DB
`initialData` uses column IDs like `col-backlog` and `col-discovery`, but the DB seeds columns named `Backlog`, `To Do`, `In Progress`, `In Review`, `Done`. These two naming systems have silently diverged. There is no runtime impact (since `initialData` is unused — see C1), but it will confuse anyone reading the file.

**Action:** Delete `initialData` as noted in C1; this resolves the conflict entirely.

### Q4 — No `.env.example` file
The `docker-compose.yml` references an `.env` file (`env_file: .env`) and the app needs `OPENROUTER_API_KEY`, but there's no `.env.example` to guide setup.

**Action:** Add `.env.example` with `OPENROUTER_API_KEY=your-key-here`.

---

## Infrastructure

### I1 — `Dockerfile` does not pin `uv` version
`COPY --from=ghcr.io/astral-sh/uv:latest` uses `latest`, which can silently break builds if `uv` releases a breaking change.

**Action:** Pin to a specific digest or tag, e.g., `ghcr.io/astral-sh/uv:0.5.26`.

### I2 — No `HEALTHCHECK` in `docker-compose.yml`
The app exposes `GET /health` but `docker-compose.yml` doesn't use it. Without a healthcheck, Docker reports the container as healthy immediately after start, before FastAPI has finished initialising.

**Action:** Add to `docker-compose.yml`:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 10s
  timeout: 5s
  retries: 3
```

---

## Priority Order

| Priority | Item | Effort |
|----------|------|--------|
| 1 | S1 — Hash passwords properly | Medium |
| 2 | C2 — Fix stale e2e test IDs | Small |
| 3 | S2 — Persist sessions across restarts | Medium |
| 4 | C5 — Fix AI patch position shift | Small |
| 5 | S3 — Upgrade to samesite=strict | Trivial |
| 6 | S4 — Graceful missing API key error | Trivial |
| 7 | C1 / Q3 — Remove unused `initialData` / `createId` | Trivial |
| 8 | C3 — Remove unused `board` prop from AISidebar | Trivial |
| 9 | C4 — Loading state for add card | Small |
| 10 | Q4 — Add `.env.example` | Trivial |
| 11 | I1 — Pin uv version | Trivial |
| 12 | I2 — Add healthcheck to compose | Trivial |
| 13 | T1/T2/T3 — Test coverage gaps | Small |
