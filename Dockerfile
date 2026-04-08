FROM ghcr.io/astral-sh/uv:alpine
WORKDIR /miku

COPY . .

ENV UV_NO_DEV=1

CMD uv run python -m miku_framework