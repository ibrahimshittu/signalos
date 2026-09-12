FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY pyproject.toml uv.lock README.md alembic.ini ./
COPY src ./src
COPY scripts ./scripts
COPY migrations ./migrations
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

EXPOSE 8001
CMD ["uvicorn", "signalos_backend.main:app", "--host", "0.0.0.0", "--port", "8001"]
