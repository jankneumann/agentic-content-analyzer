# Makefile for common development tasks

.PHONY: help install dev-install setup start stop restart logs clean test lint type-check format db-migrate db-upgrade db-downgrade

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
