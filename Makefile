.PHONY: up down logs test test-backend test-frontend lint lint-backend lint-frontend \
        fmt migrate ingest replay types shell-api web-install

up: ## Start the full stack (db, redis, api, worker, web)
	docker compose up -d --build

down: ## Stop the stack
	docker compose down

logs: ## Tail all service logs
	docker compose logs -f

# --- Backend ---

test-backend: ## Run backend unit + property + replay tests
	cd backend && uv run pytest ../tests -q

lint-backend: ## Ruff + mypy --strict on f1core
	cd backend && uv run ruff check . && uv run ruff format --check . && \
		uv run mypy --strict f1core/src/f1core

fmt: ## Auto-format backend code
	cd backend && uv run ruff format .

migrate: ## Apply Alembic migrations
	cd backend && uv run alembic -c f1api/alembic.ini upgrade head

ingest: ## make ingest SEASON=2026 ROUND=14
	cd backend && uv run python -m f1ingest.cli ingest --season $(SEASON) --round $(ROUND)

replay: ## make replay SESSION=<key> SPEED=10
	cd backend && uv run python -m f1ingest.cli replay --session $(SESSION) --speed $(SPEED)

shell-api: ## Open a shell in the running api container
	docker compose exec api bash

# --- Frontend ---

web-install: ## Install frontend deps
	cd web && npm install

test-frontend: ## Run Angular unit tests headless
	cd web && npm test -- --watch=false --browsers=ChromeHeadless

lint-frontend: ## ESLint
	cd web && npm run lint

types: ## Regenerate TS types from the FastAPI OpenAPI schema
	cd backend && uv run python -m f1api.export_openapi ../web/openapi.json
	cd web && npx openapi-typescript openapi.json -o src/app/core/api-types.ts

# --- Combined ---

test: test-backend test-frontend ## Run all tests

lint: lint-backend lint-frontend ## Run all linters
