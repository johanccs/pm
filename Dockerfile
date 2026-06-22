# Stage 1: Build Next.js static export
FROM node:20-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend serving the static frontend
FROM python:3.12-slim
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Install Python dependencies — read directly from pyproject.toml so this
# step never goes stale when new packages are added.
COPY backend/pyproject.toml ./
RUN python3 -c \
      "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); print('\n'.join(d['project']['dependencies']))" \
      > /tmp/requirements.txt && \
    uv pip install --system --no-cache -r /tmp/requirements.txt

# Copy backend source and built frontend
COPY backend/ ./backend/
COPY --from=frontend-builder /frontend/out/ ./static/

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
