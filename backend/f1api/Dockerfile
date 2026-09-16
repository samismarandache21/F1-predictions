# Dev-oriented image: docker-compose bind-mounts ./backend over /app, so the
# `uv sync` below just needs to produce a working venv; live code comes from
# the bind mount, not this layer.
FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

# Build context is ./backend (see docker-compose.yml), i.e. the whole uv
# workspace, so uv can resolve the local path dependencies between f1core,
# f1ingest, f1state, f1track and f1api.
COPY . /app

RUN uv sync --package f1api

EXPOSE 8000

CMD ["uv", "run", "--package", "f1api", "uvicorn", "f1api.main:app", \
     "--host", "0.0.0.0", "--port", "8000", "--reload"]
