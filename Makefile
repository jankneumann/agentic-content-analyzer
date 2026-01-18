# Makefile for common development tasks

.PHONY: help install dev-install setup start stop restart logs clean test lint type-check format db-migrate db-upgrade db-downgrade api web dev dev-bg dev-logs dev-stop

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	uv pip install -e .

dev-install:  ## Install dependencies including dev tools
	uv pip install -e ".[dev]"

setup: dev-install  ## Full setup (install deps, start services, init db)
	docker compose up -d
	@echo "Waiting for services to be ready..."
	@sleep 5
	alembic revision --autogenerate -m "initial schema"
	alembic upgrade head
	@echo "✓ Setup complete!"

start:  ## Start local services (PostgreSQL, Redis, Neo4j)
	docker compose up -d

stop:  ## Stop local services
	docker compose down

restart:  ## Restart local services
	docker compose restart

logs:  ## View logs from all services
	docker compose logs -f

clean:  ## Clean up Python cache files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true

test:  ## Run tests
	pytest

test-cov:  ## Run tests with coverage report
	pytest --cov=src --cov-report=term-missing --cov-report=html

test-integration:  ## Run integration tests (requires test services)
	pytest tests/integration/ -v

test-setup:  ## Start test infrastructure (PostgreSQL test DB, Neo4j test instance)
	@echo "Starting test infrastructure..."
	createdb newsletters_test 2>/dev/null || echo "Test database already exists"
	docker compose up -d neo4j-test
	@echo "Waiting for Neo4j test instance to be ready..."
	@sleep 5
	@echo "✓ Test infrastructure ready!"
	@echo "  - PostgreSQL test DB: newsletters_test"
	@echo "  - Neo4j test instance: bolt://localhost:7688 (http://localhost:7475)"

test-teardown:  ## Stop test infrastructure
	docker compose stop neo4j-test
	@echo "Test infrastructure stopped (data preserved)"

test-clean:  ## Stop and remove test infrastructure (WARNING: deletes test data)
	docker compose down neo4j-test -v
	dropdb newsletters_test 2>/dev/null || echo "Test database already removed"
	@echo "Test infrastructure cleaned"

lint:  ## Lint code with ruff
	ruff check src/ tests/

lint-fix:  ## Lint and auto-fix issues
	ruff check --fix src/ tests/

type-check:  ## Type check with mypy
	mypy src/

format:  ## Format code with ruff
	ruff format src/ tests/

db-migrate:  ## Create a new database migration (use MSG="message")
	alembic revision --autogenerate -m "$(MSG)"

db-upgrade:  ## Apply all pending migrations
	alembic upgrade head

db-downgrade:  ## Rollback one migration
	alembic downgrade -1

db-reset:  ## Reset database (WARNING: deletes all data)
	docker compose down -v
	docker compose up -d postgres
	@sleep 3
	alembic upgrade head

# Docker shortcuts
postgres:  ## Connect to PostgreSQL
	docker exec -it newsletter-postgres psql -U newsletter_user -d newsletters

redis:  ## Connect to Redis CLI
	docker exec -it newsletter-redis redis-cli

neo4j:  ## Open Neo4j browser (http://localhost:7474)
	@echo "Opening Neo4j Browser at http://localhost:7474"
	@echo "Username: neo4j"
	@echo "Password: newsletter_password"
	@open http://localhost:7474 2>/dev/null || xdg-open http://localhost:7474 2>/dev/null || echo "Please open http://localhost:7474 in your browser"

# Pipeline commands
pipeline:  ## Run full newsletter pipeline (ingest → summarize → digest)
	python -m scripts.run_pipeline

pipeline-skip-ingest:  ## Run pipeline without ingestion (process existing newsletters)
	python -m scripts.run_pipeline --skip-ingestion

pipeline-weekly:  ## Run weekly digest pipeline
	python -m scripts.run_pipeline --weekly

pipeline-auto-approve:  ## Run pipeline and auto-approve digest
	python -m scripts.run_pipeline --auto-approve

pipeline-yesterday:  ## Process yesterday's newsletters
	python -m scripts.run_pipeline --date $$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d yesterday +%Y-%m-%d)

# Development servers
api:  ## Start the backend API server (uvicorn with hot reload)
	uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000

web:  ## Start the frontend dev server (Vite)
	cd web && npm run dev

dev:  ## Start both frontend and backend for development (requires tmux or run in separate terminals)
	@echo "Starting development servers..."
	@echo ""
	@echo "Option 1: Run in separate terminals"
	@echo "  Terminal 1: make api"
	@echo "  Terminal 2: make web"
	@echo ""
	@echo "Option 2: Background mode (logs in .dev-logs/)"
	@echo "  make dev-bg"
	@echo ""
	@echo "Starting API server in foreground (Ctrl+C to stop)..."
	@echo "Run 'make web' in another terminal for frontend"
	@echo ""
	uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000

dev-bg:  ## Start frontend and backend in background (logs to .dev-logs/)
	@mkdir -p .dev-logs
	@echo "Starting backend API on http://localhost:8000..."
	@nohup uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000 > .dev-logs/api.log 2>&1 & echo $$! > .dev-logs/api.pid
	@echo "Starting frontend on http://localhost:5173..."
	@nohup sh -c 'cd web && npm run dev' > .dev-logs/web.log 2>&1 & echo $$! > .dev-logs/web.pid
	@sleep 2
	@echo ""
	@echo "✓ Development servers started!"
	@echo "  Backend API:  http://localhost:8000"
	@echo "  Frontend:     http://localhost:5173"
	@echo "  API Docs:     http://localhost:8000/docs"
	@echo ""
	@echo "View logs:"
	@echo "  make dev-logs"
	@echo ""
	@echo "Stop servers:"
	@echo "  make dev-stop"

dev-logs:  ## Tail logs from background dev servers
	@echo "=== API logs (Ctrl+C to exit) ==="
	@tail -f .dev-logs/api.log .dev-logs/web.log 2>/dev/null || echo "No logs found. Start servers with 'make dev-bg'"

dev-stop:  ## Stop background dev servers
	@echo "Stopping development servers..."
	@if [ -f .dev-logs/api.pid ]; then kill $$(cat .dev-logs/api.pid) 2>/dev/null || true; rm .dev-logs/api.pid; fi
	@if [ -f .dev-logs/web.pid ]; then kill $$(cat .dev-logs/web.pid) 2>/dev/null || true; rm .dev-logs/web.pid; fi
	@pkill -f "uvicorn src.api.app:app" 2>/dev/null || true
	@pkill -f "vite" 2>/dev/null || true
	@echo "✓ Development servers stopped"
