# Lectern: one container serving the API and the built interface.
#   docker build -t lectern .
#   docker run --env-file .env -p 8000:8000 -v lectern-data:/app/data lectern

# --- 1. Build the interface ----------------------------------------------------
FROM node:22-alpine AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- 2. Runtime -----------------------------------------------------------------
FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000
WORKDIR /app

RUN groupadd --system lectern && useradd --system --gid lectern --home /app lectern

COPY backend/pyproject.toml backend/pyproject.toml
COPY backend/lectern backend/lectern
# Editable install keeps the package next to frontend/dist, which the server serves.
RUN pip install -e ./backend

COPY --from=web /app/frontend/dist frontend/dist
RUN mkdir -p /app/data && chown -R lectern:lectern /app/data
USER lectern
VOLUME ["/app/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/health', timeout=4)"

# --proxy-headers lets Lectern see https and the client address behind a host's proxy.
CMD ["sh", "-c", "cd backend && exec uvicorn lectern.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
