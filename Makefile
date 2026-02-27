# Makefile for common development tasks

.PHONY: help install dev-install setup start stop restart logs clean test lint type-check format db-migrate db-upgrade db-downgrade api web dev dev-bg dev-logs dev-stop opik-up opik-down opik-logs supabase-up supabase-down supabase-logs langfuse-up langfuse-down langfuse-logs dev-local dev-opik dev-supabase dev-staging dev-langfuse full-up full-down verify-profile verify-opik verify-staging verify-langfuse hoverfly-up hoverfly-down hoverfly-status test-hoverfly test-langfuse neon-list neon-create neon-delete neon-clean test-neon

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

test-langfuse:  ## Run Langfuse integration tests (requires: make langfuse-up)
	@if ! curl -sf http://localhost:3100/api/public/health >/dev/null 2>&1; then \
		echo "✗ Langfuse is not running! Start with: make langfuse-up"; \
		exit 1; \
	fi
	pytest tests/integration/test_langfuse_integration.py -v

test-integration:  ## Run integration tests (requires test services)
	pytest tests/integration/ -v

test-hoverfly:  ## Run Hoverfly integration tests (requires: make hoverfly-up)
	@if ! curl -sf http://localhost:8888/api/v2/hoverfly >/dev/null 2>&1; then \
		echo "✗ Hoverfly is not running! Start with: make hoverfly-up"; \
		exit 1; \
	fi
	pytest tests/integration/ -v -m hoverfly

test-setup:  ## Start test infrastructure (PostgreSQL test DB, Neo4j test instance)
	@echo "Starting test infrastructure..."
	@TEST_DB_NAME=$$(python -c "from tests.helpers.test_db import get_test_db_name; print(get_test_db_name())") && \
		createdb "$$TEST_DB_NAME" 2>/dev/null || echo "Test database already exists: $$TEST_DB_NAME"
	docker compose up -d neo4j-test
	@echo "Waiting for Neo4j test instance to be ready..."
	@sleep 5
	@TEST_DB_NAME=$$(python -c "from tests.helpers.test_db import get_test_db_name; print(get_test_db_name())") && \
		echo "✓ Test infrastructure ready!" && \
		echo "  - PostgreSQL test DB: $$TEST_DB_NAME" && \
		echo "  - Neo4j test instance: bolt://localhost:7688 (http://localhost:7475)"

test-teardown:  ## Stop test infrastructure
	docker compose stop neo4j-test
	@echo "Test infrastructure stopped (data preserved)"

test-clean:  ## Stop and remove test infrastructure (WARNING: deletes ALL test databases)
	docker compose down neo4j-test -v
	@echo "Dropping all test databases (newsletters_test*)..."
	@docker exec newsletter-postgres psql -U newsletter_user -d postgres -tAc \
		"SELECT datname FROM pg_database WHERE datname LIKE 'newsletters_test%'" 2>/dev/null | \
		while read -r db; do \
			if [ -n "$$db" ]; then \
				docker exec newsletter-postgres psql -U newsletter_user -d postgres -c "DROP DATABASE \"$$db\"" 2>/dev/null && \
					echo "  Dropped: $$db" || echo "  Failed to drop: $$db"; \
			fi; \
		done
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
	WATCHFILES_FORCE_POLLING=true uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000 --proxy-headers

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
	WATCHFILES_FORCE_POLLING=true uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000 --proxy-headers

dev-bg:  ## Start frontend and backend in background (logs to .dev-logs/)
	@mkdir -p .dev-logs
	@echo "Starting backend API on http://localhost:8000..."
	@nohup bash -c 'source .venv/bin/activate && PROFILE=$(PROFILE) WATCHFILES_FORCE_POLLING=true uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000 --proxy-headers' > .dev-logs/api.log 2>&1 & echo $$! > .dev-logs/api.pid
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
# Local Supabase Stack
# =============================================================================

supabase-up:  ## Start local Supabase stack (database + storage)
	@echo "Starting Supabase stack..."
	@docker compose -f docker-compose.supabase.yml -p supabase up -d
	@echo "Waiting for Supabase services to be healthy..."
	@timeout=120; \
	elapsed=0; \
	while true; do \
		db_ok=$$(docker exec newsletter-supabase-db pg_isready -U postgres -d postgres >/dev/null 2>&1 && echo 1 || echo 0); \
		storage_ok=$$(wget -q --spider http://localhost:54323/status 2>/dev/null && echo 1 || echo 0); \
		kong_ok=$$(curl -sf -o /dev/null -w '' http://localhost:54321/ 2>/dev/null && echo 1 || echo 0); \
		if [ "$$db_ok" = "1" ] && [ "$$storage_ok" = "1" ] && [ "$$kong_ok" = "1" ]; then break; fi; \
		if [ $$elapsed -ge $$timeout ]; then \
			echo ""; \
			echo "Timeout waiting for Supabase services."; \
			echo "  DB: $$([ $$db_ok = 1 ] && echo OK || echo FAILED)"; \
			echo "  Storage: $$([ $$storage_ok = 1 ] && echo OK || echo FAILED)"; \
			echo "  Kong: $$([ $$kong_ok = 1 ] && echo OK || echo FAILED)"; \
			echo "Check logs with: make supabase-logs"; \
			exit 1; \
		fi; \
		sleep 2; \
		elapsed=$$((elapsed + 2)); \
		printf "."; \
	done
	@echo ""
	@echo ""
	@echo "Supabase stack is ready!"
	@echo "  Supabase API:     http://localhost:54321"
	@echo "  Supabase DB:      localhost:54322"
	@echo "  Supabase Storage: http://localhost:54323"
	@echo "  PostgREST:        http://localhost:54324"
	@echo ""
	@echo "To use Supabase as your database/storage provider:"
	@echo "  export PROFILE=local-supabase"
	@echo "  make api"
	@echo ""
	@echo "Or use: make dev-supabase"

supabase-down:  ## Stop local Supabase stack
	@echo "Stopping Supabase stack..."
	@docker compose -f docker-compose.supabase.yml -p supabase down
	@echo "✓ Supabase stack stopped"

supabase-logs:  ## Tail Supabase stack logs
	@docker compose -f docker-compose.supabase.yml -p supabase logs -f

# =============================================================================
# Langfuse Observability Stack
# =============================================================================

langfuse-up:  ## Start Langfuse observability stack (LLM tracing)
	@echo "Starting Langfuse stack..."
	@docker compose -f docker-compose.langfuse.yml -p langfuse up -d
	@echo "Waiting for Langfuse to be healthy..."
	@timeout=120; \
	elapsed=0; \
	while ! curl -sf http://localhost:3100/api/public/health >/dev/null 2>&1; do \
		if [ $$elapsed -ge $$timeout ]; then \
			echo "✗ Timeout waiting for Langfuse to start"; \
			docker compose -f docker-compose.langfuse.yml -p langfuse logs langfuse-web --tail 20; \
			exit 1; \
		fi; \
		sleep 2; \
		elapsed=$$((elapsed + 2)); \
		printf "\r  Waiting... %ds / %ds" $$elapsed $$timeout; \
	done
	@echo ""
	@echo "✓ Langfuse is running!"
	@echo ""
	@echo "  Langfuse UI:     http://localhost:3100"
	@echo "  OTLP Endpoint:   http://localhost:3100/api/public/otel"
	@echo ""
	@echo "  Create account on first visit, then get API keys from Settings → API Keys."
	@echo ""
	@echo "Or use: make dev-langfuse"

langfuse-down:  ## Stop Langfuse observability stack
	@echo "Stopping Langfuse stack..."
	@docker compose -f docker-compose.langfuse.yml -p langfuse down
	@echo "✓ Langfuse stack stopped"

langfuse-logs:  ## Tail Langfuse stack logs
	@docker compose -f docker-compose.langfuse.yml -p langfuse logs -f

# =============================================================================
# Neon Database Branching
# =============================================================================

neon-list:  ## List Neon database branches
	@source .venv/bin/activate && python -m src.cli neon list

neon-create:  ## Create a Neon branch (use NAME=claude/feature-xyz)
	@if [ -z "$(NAME)" ]; then \
		echo "Usage: make neon-create NAME=claude/feature-xyz"; \
		exit 1; \
	fi
	@source .venv/bin/activate && python -m src.cli neon create "$(NAME)"

neon-delete:  ## Delete a Neon branch (use NAME=claude/feature-xyz)
	@if [ -z "$(NAME)" ]; then \
		echo "Usage: make neon-delete NAME=claude/feature-xyz"; \
		exit 1; \
	fi
	@source .venv/bin/activate && python -m src.cli neon delete "$(NAME)"

neon-clean:  ## Clean up stale agent branches (older than 24h with claude/ prefix)
	@source .venv/bin/activate && python -m src.cli neon clean --prefix "claude/" --older-than 24

test-neon:  ## Run Neon integration tests (requires: NEON_API_KEY, NEON_PROJECT_ID)
	@if [ -z "$$NEON_API_KEY" ] || [ -z "$$NEON_PROJECT_ID" ]; then \
		echo "✗ Neon credentials not set!"; \
		echo "  Set NEON_API_KEY and NEON_PROJECT_ID in environment or .secrets.yaml"; \
		exit 1; \
	fi
	pytest tests/integration/test_neon_integration.py -v

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

dev-supabase:  ## Start dev servers with local Supabase (requires: make supabase-up)
	@echo "Checking if Supabase DB is running..."
	@if ! docker exec newsletter-supabase-db pg_isready -U postgres -d postgres >/dev/null 2>&1; then \
		echo ""; \
		echo "✗ Supabase is not running!"; \
		echo ""; \
		echo "Start Supabase first:"; \
		echo "  make supabase-up"; \
		echo ""; \
		exit 1; \
	fi
	@echo "✓ Supabase DB is healthy"
	@echo "Starting development with PROFILE=local-supabase..."
	@PROFILE=local-supabase $(MAKE) dev-bg
	@echo ""
	@echo "Using Supabase at: http://localhost:54321"

dev-staging:  ## Start dev servers with staging profile (remote backends + Braintrust)
	@echo "Validating staging profile..."
	@source .venv/bin/activate && python -m src.cli profile validate staging || { \
		echo ""; \
		echo "✗ Staging profile validation failed!"; \
		echo ""; \
		echo "Check:"; \
		echo "  1. .secrets.yaml has BRAINTRUST_API_KEY"; \
		echo "  2. STAGING_RAILWAY_DATABASE_URL or RAILWAY_DATABASE_URL is set"; \
		echo "  3. NEO4J_AURADB_URI and NEO4J_AURADB_PASSWORD are set"; \
		echo ""; \
		exit 1; \
	}
	@echo "✓ Staging profile is valid"
	@echo ""
	@echo "⚠  WARNING: Staging uses REMOTE backends (Railway, AuraDB, Braintrust)"
	@echo "   Braintrust project: AI Content Analyzer Staging"
	@echo ""
	@PROFILE=staging $(MAKE) dev-bg
	@echo ""
	@echo "Verify connectivity:"
	@echo "  make verify-staging"

dev-langfuse:  ## Start dev servers with Langfuse tracing (requires: make langfuse-up)
	@echo "Checking if Langfuse is running..."
	@if ! curl -sf http://localhost:3100/api/public/health >/dev/null 2>&1; then \
		echo ""; \
		echo "✗ Langfuse is not running!"; \
		echo ""; \
		echo "  Start it with:"; \
		echo "  make langfuse-up"; \
		echo ""; \
		exit 1; \
	fi
	@echo "✓ Langfuse is healthy"
	@echo "Starting development with PROFILE=local-langfuse..."
	PROFILE=local-langfuse $(MAKE) dev-bg

# =============================================================================
# Hoverfly API Simulation (integration tests)
# =============================================================================

hoverfly-up:  ## Start Hoverfly API simulator for integration tests
	@echo "Starting Hoverfly..."
	@docker compose --profile test up -d hoverfly
	@echo "Waiting for Hoverfly to be ready..."
	@timeout=30; \
	elapsed=0; \
	while ! curl -sf http://localhost:8888/api/v2/hoverfly >/dev/null 2>&1; do \
		if [ $$elapsed -ge $$timeout ]; then \
			echo "✗ Timeout waiting for Hoverfly"; \
			exit 1; \
		fi; \
		sleep 1; \
		elapsed=$$((elapsed + 1)); \
		printf "."; \
	done
	@echo ""
	@echo "✓ Hoverfly is ready!"
	@echo "  Webserver:  http://localhost:8500 (send requests here)"
	@echo "  Admin API:  http://localhost:8888"
	@echo ""
	@echo "Run Hoverfly tests:"
	@echo "  make test-hoverfly"

hoverfly-down:  ## Stop Hoverfly API simulator
	@echo "Stopping Hoverfly..."
	@docker compose --profile test stop hoverfly
	@echo "✓ Hoverfly stopped"

hoverfly-status:  ## Check Hoverfly status and loaded simulations
	@if curl -sf http://localhost:8888/api/v2/hoverfly >/dev/null 2>&1; then \
		echo "✓ Hoverfly is running"; \
		echo "  Mode: $$(curl -s http://localhost:8888/api/v2/hoverfly/mode | python3 -c 'import sys,json; print(json.load(sys.stdin).get(\"mode\",\"unknown\"))' 2>/dev/null || echo 'unknown')"; \
		echo "  Pairs: $$(curl -s http://localhost:8888/api/v2/simulation | python3 -c 'import sys,json; print(len(json.load(sys.stdin).get(\"data\",{}).get(\"pairs\",[])))' 2>/dev/null || echo 'unknown')"; \
	else \
		echo "✗ Hoverfly is not running"; \
		echo "  Start with: make hoverfly-up"; \
	fi

full-up:  ## Start all services (core + Opik observability)
	@echo "Starting core services..."
	@docker compose up -d
	@echo "Starting Opik stack..."
	@$(MAKE) opik-up

full-down:  ## Stop all services (Supabase + Opik + core)
	@echo "Stopping Supabase stack..."
	@docker compose -f docker-compose.supabase.yml -p supabase down 2>/dev/null || true
	@echo "Stopping Opik stack..."
	@docker compose -f docker-compose.opik.yml -p opik down 2>/dev/null || true
	@echo "Stopping Langfuse stack..."
	@docker compose -f docker-compose.langfuse.yml -p langfuse down 2>/dev/null || true
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

verify-langfuse:  ## Verify Langfuse tracing works E2E (requires: PROFILE=local-langfuse, Langfuse running)
	@echo "Verifying Langfuse tracing..."
	@echo ""
	@echo "1. Checking Langfuse is running..."
	@if ! curl -sf http://localhost:3100/api/public/health >/dev/null 2>&1; then \
		echo "✗ Langfuse is not running!"; \
		echo "  Start it with: make langfuse-up"; \
		exit 1; \
	fi
	@echo "   ✓ Langfuse is healthy"
	@echo ""
	@echo "2. Sending test trace..."
	@python scripts/send_test_trace.py --endpoint http://localhost:3100/api/public/otel/v1/traces --service verify-langfuse-test 2>&1 && \
		echo "   ✓ Test trace sent successfully" || \
		echo "   ✗ Failed to send test trace"
	@echo ""
	@echo "✓ Langfuse verification complete!"
	@echo ""
	@echo "  View traces at: http://localhost:3100"

verify-staging:  ## Verify staging profile connectivity (health + readiness)
	@echo "Verifying staging profile..."
	@echo ""
	@echo "1. Validating profile structure..."
	@source .venv/bin/activate && python -m src.cli profile validate staging || { \
		echo "✗ Staging profile validation failed"; \
		exit 1; \
	}
	@echo "   ✓ Profile is valid"
	@echo ""
	@echo "2. Checking API health..."
	@if ! curl -sf http://localhost:8000/health >/dev/null 2>&1; then \
		echo "✗ API is not running at http://localhost:8000"; \
		echo "  Start it with: make dev-staging"; \
		exit 1; \
	fi
	@echo "   ✓ API is healthy"
	@echo ""
	@echo "3. Checking API readiness (database)..."
	@if ! curl -sf http://localhost:8000/ready >/dev/null 2>&1; then \
		echo "✗ API is not ready (database connection failed)"; \
		echo "  Check RAILWAY_DATABASE_URL or STAGING_RAILWAY_DATABASE_URL"; \
		exit 1; \
	fi
	@echo "   ✓ API is ready (database connected)"
	@echo ""
	@echo "4. Showing active profile..."
	@source .venv/bin/activate && PROFILE=staging python -m src.cli profile inspect 2>/dev/null || true
	@echo ""
	@echo "✓ Staging verification passed!"
