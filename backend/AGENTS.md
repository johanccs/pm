# Backend

Python FastAPI application. Managed with `uv`. Runs inside Docker on port 8000.

## Structure

```
backend/
├── __init__.py
├── main.py          # FastAPI app entrypoint
└── pyproject.toml   # Python project config and dependencies
```

## Endpoints (current)

- `GET /hello` — returns a simple HTML page (smoke test)
- `GET /api/ping` — returns `{"ok": true}`
- `GET /health` — returns `{"status": "healthy"}`

## Running locally (via Docker)

Use the scripts in `scripts/`:
- Windows: `scripts/start.ps1` / `scripts/stop.ps1`
- Mac/Linux: `scripts/start.sh` / `scripts/stop.sh`

## Dependencies

Managed by `uv` in `pyproject.toml`. Add new packages there.
