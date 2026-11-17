FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /workspace

ENV UV_LINK_MODE=copy
ENV PATH="/workspace/.venv/bin:$PATH"

# Устанавливаем зависимости
COPY pyproject.toml uv.lock README.md ./

RUN uv sync --locked --no-install-project

# Копируем приложение и Alembic
COPY app ./app
COPY web ./web
COPY tests ./tests
COPY migrations ./migrations
COPY alembic.ini ./

RUN uv sync --locked

# Запускаем FastAPI
CMD ["sh", "-c", "uv run --locked alembic upgrade head && uv run --locked python app/seed.py && exec uv run --locked uvicorn main:app --app-dir app --host 0.0.0.0 --port 8000"]
