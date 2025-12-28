"""Integration tests for end-to-end workflows.

These tests require:
- PostgreSQL database (test database)
- Neo4j instance (test instance)
- Real database operations
- Mock LLM API calls (to avoid costs)

Run with: pytest tests/integration/ -v
"""
