FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PADDOCK_DATA_DIR=/data \
    PATH="/app/.venv/bin:$PATH"

# DejaVu fonts for the social preview images (accents and dashes in names and titles).
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.12.*

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY paddock ./paddock
# Exactly the versions in uv.lock, with the FastF1 (`paddock timing`) and MCP (`paddock mcp`) extras.
RUN uv sync --frozen --no-dev --all-extras --no-cache

RUN useradd --create-home --uid 1000 appuser && mkdir -p /data && chown appuser:appuser /data
USER appuser

EXPOSE 8020
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8020/api/health')" || exit 1
# The database is built into the /data volume by the `pipeline` service (or `docker compose run --rm api paddock update`).
CMD ["paddock", "serve", "--host", "0.0.0.0", "--port", "8020"]
