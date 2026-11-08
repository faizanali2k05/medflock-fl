FROM node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim@sha256:e88e9763f943ec1834f992a4b51e0f24500486803e8bc534e5767af9ea65f6ce AS backend
WORKDIR /app
RUN pip install --no-cache-dir uv==0.11.33
COPY pyproject.toml uv.lock LICENSE README.md ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project
COPY src ./src
COPY training/cardiology ./training/cardiology
COPY --from=frontend /build/src/medflock/resources/web ./src/medflock/resources/web
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev
RUN useradd --create-home --uid 10001 medflock && mkdir -p data artifacts runtime && chown medflock:medflock data artifacts runtime
USER 10001:10001
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
EXPOSE 8088
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8088/health/ready', timeout=3)"
CMD ["uvicorn", "medflock.api:app", "--host", "0.0.0.0", "--port", "8088", "--workers", "1"]
