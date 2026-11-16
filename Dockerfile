FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.9 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

RUN useradd --create-home app

WORKDIR /app

# 1) Dependencies only: cached until pyproject.toml or uv.lock changes
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# 2) The project itself: rebuilt when the source code changes
COPY README.md ./
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

USER app

ENTRYPOINT ["review-bot"]
