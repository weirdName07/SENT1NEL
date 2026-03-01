# ── Stage 1: Build frontend ───────────────────────────────
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --frozen-lockfile 2>/dev/null || npm install
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python backend ──────────────────────────────
FROM python:3.12-slim AS backend

WORKDIR /app

# System deps for asyncpg (libpq), shapely (libgeos), sgp4 (gcc)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc g++ libgeos-dev libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (cache layer)
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy application code
COPY sentinel/ ./sentinel/
RUN pip install --no-cache-dir -e .

# Copy built frontend into static dir
COPY --from=frontend-build /frontend/dist ./static/

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "sentinel"]
