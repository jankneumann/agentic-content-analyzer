# Makefile for common development tasks

.PHONY: help install dev-install setup start stop restart logs clean test lint type-check format db-migrate db-upgrade db-downgrade api web dev dev-bg dev-logs dev-stop opik-up opik-down opik-logs dev-local dev-opik full-up full-down verify-profile verify-opik

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

test-opik:  ## Run Opik integration tests (requires: make opik-up)
	@if ! curl -sf http://localhost:8080/health-check >/dev/null 2>&1; then \
		echo "✗ Opik is not running! Start with: make opik-up"; \
		exit 1; \
	fi
	pytest tests/integration/test_opik_integration.py -v

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
# Note: WATCHFILES_FORCE_POLLING=true works around Python 3.14 multiprocessing spawn issue
api:  ## Start the backend API server (uvicorn with hot reload)
	WATCHFILES_FORCE_POLLING=true uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000

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
	WATCHFILES_FORCE_POLLING=true uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000

dev-bg:  ## Start frontend and backend in background (logs to .dev-logs/)
	@mkdir -p .dev-logs
	@echo "Starting backend API on http://localhost:8000..."
	@nohup bash -c 'source .venv/bin/activate && PROFILE=$(PROFILE) WATCHFILES_FORCE_POLLING=true uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000' > .dev-logs/api.log 2>&1 & echo $$! > .dev-logs/api.pid
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

# =============================================================================
# Opik Observability Stack
# =============================================================================

opik-up:  ## Start Opik observability stack (LLM tracing)
	@echo "Starting Opik stack..."
	@docker compose -f docker-compose.opik.yml -p opik up -d
	@echo "Waiting for Opik backend to be healthy..."
	@timeout=120; \
	elapsed=0; \
	while ! curl -sf http://localhost:8080/health-check >/dev/null 2>&1; do \
		if [ $$elapsed -ge $$timeout ]; then \
			echo "✗ Timeout waiting for Opik backend"; \
			exit 1; \
		fi; \
		sleep 2; \
		elapsed=$$((elapsed + 2)); \
		printf "."; \
	done
	@echo ""
	@echo "✓ Opik stack is ready!"
	@echo "  Opik UI:     http://localhost:5174"
	@echo "  Opik API:    http://localhost:8080"
	@echo ""
	@echo "To enable LLM tracing:"
	@echo "  export PROFILE=local-opik"
	@echo "  make api"
	@echo ""
	@echo "Or use: make dev-opik"

opik-down:  ## Stop Opik observability stack
	@echo "Stopping Opik stack..."
	@docker compose -f docker-compose.opik.yml -p opik down
	@echo "✓ Opik stack stopped"

opik-logs:  ## Tail Opik stack logs
	@docker compose -f docker-compose.opik.yml -p opik logs -f

# =============================================================================
# Profile-Based Development
# =============================================================================

dev-local:  ## Start dev servers with local profile (no observability)
	@echo "Starting development with PROFILE=local..."
	@PROFILE=local $(MAKE) dev-bg

dev-opik:  ## Start dev servers with Opik tracing (requires: make opik-up)
	@echo "Checking if Opik is running..."
	@if ! curl -sf http://localhost:8080/health-check >/dev/null 2>&1; then \
		echo ""; \
		echo "✗ Opik is not running!"; \
		echo ""; \
		echo "Start Opik first:"; \
		echo "  make opik-up"; \
		echo ""; \
		exit 1; \
	fi
	@echo "✓ Opik is healthy"
	@echo "Starting development with PROFILE=local-opik..."
	@PROFILE=local-opik $(MAKE) dev-bg
	@echo ""
	@echo "LLM traces will appear at: http://localhost:5174"

full-up:  ## Start all services (core + Opik observability)
	@echo "Starting core services..."
	@docker compose up -d
	@echo "Starting Opik stack..."
	@$(MAKE) opik-up

full-down:  ## Stop all services (Opik + core)
	@echo "Stopping Opik stack..."
	@docker compose -f docker-compose.opik.yml -p opik down 2>/dev/null || true
	@echo "Stopping core services..."
	@docker compose down
	@echo "✓ All services stopped"

# =============================================================================
# Profile Verification
# =============================================================================

verify-profile:  ## Verify current profile configuration works E2E
	@echo "Verifying profile configuration..."
	@echo ""
	@echo "1. Checking API health..."
	@if ! curl -sf http://localhost:8000/health >/dev/null 2>&1; then \
		echo "✗ API is not running at http://localhost:8000"; \
		echo "  Start it with: make api"; \
		exit 1; \
	fi
	@echo "   ✓ API is healthy"
	@echo ""
	@echo "2. Checking API readiness (database)..."
	@if ! curl -sf http://localhost:8000/ready >/dev/null 2>&1; then \
		echo "✗ API is not ready (database connection failed)"; \
		exit 1; \
	fi
	@echo "   ✓ API is ready"
	@echo ""
	@echo "3. Validating current profile..."
	@if [ -n "$$PROFILE" ]; then \
		python -m src.cli profile validate "$$PROFILE"; \
	else \
		echo "   (No PROFILE set, using .env configuration)"; \
	fi
	@echo ""
	@echo "✓ Profile verification passed!"

verify-opik:  ## Verify Opik tracing works E2E (requires: PROFILE=local-opik, Opik running)
	@echo "Verifying Opik tracing..."
	@echo ""
	@echo "1. Checking Opik is running..."
	@if ! curl -sf http://localhost:8080/health-check >/dev/null 2>&1; then \
		echo "✗ Opik is not running!"; \
		echo "  Start it with: make opik-up"; \
		exit 1; \
	fi
	@echo "   ✓ Opik backend is healthy"
	@echo ""
	@echo "2. Checking Opik UI is accessible..."
	@if ! curl -sf http://localhost:5174/health >/dev/null 2>&1; then \
		echo "✗ Opik UI is not accessible at http://localhost:5174"; \
		exit 1; \
	fi
	@echo "   ✓ Opik UI is accessible"
	@echo ""
	@echo "3. Sending test trace via OTel SDK..."
	@python scripts/send_test_trace.py --service verify-opik-test 2>&1 && \
		echo "   ✓ Test trace sent successfully" || \
		echo "   ✗ Failed to send test trace"
	@echo ""
	@echo "✓ Opik verification complete!"
	@echo ""
	@echo "View traces at: http://localhost:5174"
