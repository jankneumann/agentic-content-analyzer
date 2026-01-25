"""Tests for Neon branch management."""

import json
import os
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.storage.providers.neon_branch import (
    NEON_API_BASE_URL,
    NeonAPIError,
    NeonBranch,
    NeonBranchManager,
    NeonRateLimitError,
)


class TestNeonBranch:
    """Tests for NeonBranch model."""

    def test_neon_branch_model_required_fields(self):
        """NeonBranch should require id, name, and created_at fields."""
        branch = NeonBranch(
            id="br-test-123",
            name="test-branch",
            created_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
        )

        assert branch.id == "br-test-123"
        assert branch.name == "test-branch"
        assert branch.created_at == datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)

    def test_neon_branch_model_optional_fields(self):
        """NeonBranch should have optional parent_id and connection_string fields."""
        # Without optional fields
        branch_minimal = NeonBranch(
            id="br-test-123",
            name="test-branch",
            created_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
        )
        assert branch_minimal.parent_id is None
        assert branch_minimal.connection_string is None

        # With optional fields
        branch_full = NeonBranch(
            id="br-test-456",
            name="feature-branch",
            parent_id="br-main-789",
            created_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
            connection_string="postgresql://user:pass@host/db",
        )
        assert branch_full.parent_id == "br-main-789"
        assert branch_full.connection_string == "postgresql://user:pass@host/db"


class TestNeonAPIError:
    """Tests for NeonAPIError exception."""

    def test_neon_api_error_with_status_code(self):
        """NeonAPIError should include message and status code."""
        error = NeonAPIError("Branch not found", status_code=404)

        assert error.message == "Branch not found"
        assert error.status_code == 404
        assert "Branch not found" in str(error)
        assert "404" in str(error)

    def test_neon_rate_limit_error(self):
        """NeonRateLimitError should have status code 429 and optional retry_after."""
        # Without retry_after
        error_no_retry = NeonRateLimitError()
        assert error_no_retry.status_code == 429
        assert error_no_retry.retry_after is None
        assert "Rate limit exceeded" in str(error_no_retry)

        # With retry_after
        error_with_retry = NeonRateLimitError(retry_after=30.0)
        assert error_with_retry.status_code == 429
        assert error_with_retry.retry_after == 30.0


class TestNeonBranchManager:
    """Tests for NeonBranchManager initialization."""

    def test_init_from_env_vars(self):
        """NeonBranchManager should fall back to environment variables."""
        with patch.dict(
            os.environ,
            {
                "NEON_API_KEY": "test-api-key",
                "NEON_PROJECT_ID": "test-project-id",
                "NEON_DEFAULT_BRANCH": "development",
            },
        ):
            manager = NeonBranchManager()

            assert manager._api_key == "test-api-key"
            assert manager._project_id == "test-project-id"
            assert manager._default_branch == "development"

    def test_init_validates_api_key(self):
        """NeonBranchManager should raise ValueError if no API key is provided."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove any existing env vars
            os.environ.pop("NEON_API_KEY", None)
            os.environ.pop("NEON_PROJECT_ID", None)

            manager = NeonBranchManager(project_id="test-project")

            with pytest.raises(ValueError, match="Neon API key is required"):
                manager._validate_config()

    def test_init_validates_project_id(self):
        """NeonBranchManager should raise ValueError if no project ID is provided."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("NEON_API_KEY", None)
            os.environ.pop("NEON_PROJECT_ID", None)

            manager = NeonBranchManager(api_key="test-api-key")

            with pytest.raises(ValueError, match="Neon project ID is required"):
                manager._validate_config()


def create_mock_transport(responses: dict[str, Any]) -> httpx.MockTransport:
    """Create a mock transport that returns predefined responses based on URL patterns.

    Args:
        responses: Dict mapping (method, url_pattern) tuples to response data.
                  Response data can be a dict with 'status_code', 'json', 'headers',
                  or a list of such dicts for sequential responses.
    """
    call_counts: dict[tuple[str, str], int] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.method
        url = str(request.url)

        # Find matching response
        for (resp_method, url_pattern), response_data in responses.items():
            if method == resp_method and url_pattern in url:
                key = (resp_method, url_pattern)
                call_counts.setdefault(key, 0)

                # Handle sequential responses
                if isinstance(response_data, list):
                    idx = min(call_counts[key], len(response_data) - 1)
                    data = response_data[idx]
                else:
                    data = response_data

                call_counts[key] += 1

                return httpx.Response(
                    status_code=data.get("status_code", 200),
                    json=data.get("json"),
                    headers=data.get("headers", {}),
                )

        # Default: return 404 for unmatched requests
        return httpx.Response(404, json={"error": "Not found"})

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
class TestNeonBranchManagerRequests:
    """Tests for NeonBranchManager API requests with mocked httpx."""

    @pytest.fixture
    def manager(self):
        """Create a NeonBranchManager with test credentials."""
        return NeonBranchManager(
            api_key="test-api-key",
            project_id="test-project-id",
            default_branch="main",
        )

    async def test_create_branch_success(self, manager):
        """Test successful branch creation."""
        responses = {
            ("GET", "/projects/test-project-id/branches"): {
                "status_code": 200,
                "json": {
                    "branches": [
                        {
                            "id": "br-main-123",
                            "name": "main",
                            "parent_id": None,
                            "created_at": "2024-01-15T12:00:00Z",
                        }
                    ]
                },
            },
            ("POST", "/projects/test-project-id/branches"): {
                "status_code": 201,
                "json": {
                    "branch": {
                        "id": "br-feature-456",
                        "name": "feature-branch",
                        "parent_id": "br-main-123",
                        "created_at": "2024-01-15T14:00:00Z",
                    },
                    "endpoints": [{"id": "ep-test-789", "type": "read_write"}],
                    "connection_uris": [
                        {"connection_uri": "postgresql://user:pass@host.neon.tech/neondb"}
                    ],
                },
            },
            ("GET", "/projects/test-project-id/endpoints/ep-test-789"): {
                "status_code": 200,
                "json": {"endpoint": {"id": "ep-test-789", "current_state": "active"}},
            },
        }

        transport = create_mock_transport(responses)
        manager._client = httpx.AsyncClient(
            base_url=NEON_API_BASE_URL,
            transport=transport,
            headers={"Authorization": "Bearer test-api-key"},
        )

        try:
            branch = await manager.create_branch("feature-branch", parent="main")

            assert branch.id == "br-feature-456"
            assert branch.name == "feature-branch"
            assert branch.parent_id == "br-main-123"
            assert branch.connection_string == "postgresql://user:pass@host.neon.tech/neondb"
        finally:
            await manager.close()

    async def test_create_branch_with_timestamp(self, manager):
        """Test branch creation with point-in-time recovery timestamp."""
        captured_requests: list[httpx.Request] = []

        def capture_handler(request: httpx.Request) -> httpx.Response:
            captured_requests.append(request)
            url = str(request.url)

            if request.method == "GET" and "/branches" in url:
                return httpx.Response(
                    200,
                    json={
                        "branches": [
                            {
                                "id": "br-main-123",
                                "name": "main",
                                "parent_id": None,
                                "created_at": "2024-01-15T12:00:00Z",
                            }
                        ]
                    },
                )
            elif request.method == "POST" and "/branches" in url:
                return httpx.Response(
                    201,
                    json={
                        "branch": {
                            "id": "br-pitr-789",
                            "name": "pitr-branch",
                            "parent_id": "br-main-123",
                            "created_at": "2024-01-15T14:00:00Z",
                        },
                        "endpoints": [],
                    },
                )

            return httpx.Response(404)

        transport = httpx.MockTransport(capture_handler)
        manager._client = httpx.AsyncClient(
            base_url=NEON_API_BASE_URL,
            transport=transport,
            headers={"Authorization": "Bearer test-api-key"},
        )

        pitr_timestamp = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)

        try:
            branch = await manager.create_branch(
                "pitr-branch", parent="main", from_timestamp=pitr_timestamp
            )

            assert branch.id == "br-pitr-789"
            assert branch.name == "pitr-branch"

            # Verify the request included the timestamp
            post_requests = [r for r in captured_requests if r.method == "POST"]
            assert len(post_requests) == 1
            request_body = json.loads(post_requests[0].content.decode())
            assert "parent_timestamp" in request_body["branch"]
        finally:
            await manager.close()

    async def test_create_branch_rate_limited(self, manager):
        """Test exponential backoff on 429 rate limit response."""
        call_count = 0

        def rate_limit_handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            url = str(request.url)

            if request.method == "GET" and "/branches" in url:
                return httpx.Response(
                    200,
                    json={
                        "branches": [
                            {
                                "id": "br-main-123",
                                "name": "main",
                                "parent_id": None,
                                "created_at": "2024-01-15T12:00:00Z",
                            }
                        ]
                    },
                )
            elif request.method == "POST" and "/branches" in url:
                call_count += 1
                return httpx.Response(429, headers={"Retry-After": "5"})

            return httpx.Response(404)

        transport = httpx.MockTransport(rate_limit_handler)
        manager._client = httpx.AsyncClient(
            base_url=NEON_API_BASE_URL,
            transport=transport,
            headers={"Authorization": "Bearer test-api-key"},
        )

        try:
            with pytest.raises(NeonRateLimitError) as exc_info:
                # Patch sleep to avoid waiting in tests
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    await manager.create_branch("feature-branch", parent="main")

            assert exc_info.value.status_code == 429
            assert exc_info.value.retry_after == 5.0
            # Should have retried 3 times (MAX_RETRIES)
            assert call_count == 3
        finally:
            await manager.close()

    async def test_delete_branch_success(self, manager):
        """Test successful branch deletion."""
        delete_called = False

        def delete_handler(request: httpx.Request) -> httpx.Response:
            nonlocal delete_called
            url = str(request.url)

            if request.method == "GET" and "/branches" in url and "/endpoints" not in url:
                return httpx.Response(
                    200,
                    json={
                        "branches": [
                            {
                                "id": "br-feature-456",
                                "name": "feature-branch",
                                "parent_id": "br-main-123",
                                "created_at": "2024-01-15T12:00:00Z",
                            }
                        ]
                    },
                )
            elif request.method == "DELETE" and "br-feature-456" in url:
                delete_called = True
                return httpx.Response(204)

            return httpx.Response(404)

        transport = httpx.MockTransport(delete_handler)
        manager._client = httpx.AsyncClient(
            base_url=NEON_API_BASE_URL,
            transport=transport,
            headers={"Authorization": "Bearer test-api-key"},
        )

        try:
            await manager.delete_branch("feature-branch")
            assert delete_called
        finally:
            await manager.close()

    async def test_delete_branch_not_found(self, manager):
        """Test 404 error handling when branch is not found."""

        def not_found_handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)

            if request.method == "GET" and "/branches" in url:
                return httpx.Response(200, json={"branches": []})

            return httpx.Response(404)

        transport = httpx.MockTransport(not_found_handler)
        manager._client = httpx.AsyncClient(
            base_url=NEON_API_BASE_URL,
            transport=transport,
            headers={"Authorization": "Bearer test-api-key"},
        )

        try:
            with pytest.raises(NeonAPIError) as exc_info:
                await manager.delete_branch("nonexistent-branch")

            assert exc_info.value.status_code == 404
            assert "not found" in exc_info.value.message.lower()
        finally:
            await manager.close()

    async def test_list_branches_success(self, manager):
        """Test successful branch listing."""
        responses = {
            ("GET", "/projects/test-project-id/branches"): {
                "status_code": 200,
                "json": {
                    "branches": [
                        {
                            "id": "br-main-123",
                            "name": "main",
                            "parent_id": None,
                            "created_at": "2024-01-15T12:00:00Z",
                        },
                        {
                            "id": "br-dev-456",
                            "name": "development",
                            "parent_id": "br-main-123",
                            "created_at": "2024-01-16T10:00:00Z",
                        },
                        {
                            "id": "br-feature-789",
                            "name": "feature-x",
                            "parent_id": "br-dev-456",
                            "created_at": "2024-01-17T08:00:00Z",
                        },
                    ]
                },
            },
        }

        transport = create_mock_transport(responses)
        manager._client = httpx.AsyncClient(
            base_url=NEON_API_BASE_URL,
            transport=transport,
            headers={"Authorization": "Bearer test-api-key"},
        )

        try:
            branches = await manager.list_branches()

            assert len(branches) == 3
            assert branches[0].name == "main"
            assert branches[1].name == "development"
            assert branches[2].name == "feature-x"

            # Verify parent relationships
            assert branches[0].parent_id is None
            assert branches[1].parent_id == "br-main-123"
            assert branches[2].parent_id == "br-dev-456"
        finally:
            await manager.close()

    async def test_get_connection_string_success(self, manager):
        """Test successful connection string retrieval."""

        def conn_string_handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)

            if request.method == "GET":
                if "/branches" in url and "/endpoints" not in url:
                    return httpx.Response(
                        200,
                        json={
                            "branches": [
                                {
                                    "id": "br-feature-456",
                                    "name": "feature-branch",
                                    "parent_id": "br-main-123",
                                    "created_at": "2024-01-15T12:00:00Z",
                                }
                            ]
                        },
                    )
                elif "/endpoints/ep-test-123" in url:
                    # Endpoint status check
                    return httpx.Response(
                        200,
                        json={"endpoint": {"id": "ep-test-123", "current_state": "active"}},
                    )
                elif "/endpoints" in url:
                    return httpx.Response(
                        200,
                        json={"endpoints": [{"id": "ep-test-123", "type": "read_write"}]},
                    )
                elif "/connection_uri" in url:
                    return httpx.Response(
                        200,
                        json={
                            "uri": "postgresql://user:pass@host.neon.tech/neondb?sslmode=require"
                        },
                    )

            return httpx.Response(404)

        transport = httpx.MockTransport(conn_string_handler)
        manager._client = httpx.AsyncClient(
            base_url=NEON_API_BASE_URL,
            transport=transport,
            headers={"Authorization": "Bearer test-api-key"},
        )

        try:
            conn_str = await manager.get_connection_string("feature-branch")
            assert conn_str == "postgresql://user:pass@host.neon.tech/neondb?sslmode=require"
        finally:
            await manager.close()


@pytest.mark.asyncio
class TestBranchContext:
    """Tests for branch_context context manager."""

    @pytest.fixture
    def manager(self):
        """Create a NeonBranchManager with test credentials."""
        return NeonBranchManager(
            api_key="test-api-key",
            project_id="test-project-id",
            default_branch="main",
        )

    async def test_branch_context_creates_and_deletes(self, manager):
        """Test that branch_context creates branch on entry and deletes on exit."""
        create_called = False
        delete_called = False
        list_call_count = 0

        def context_handler(request: httpx.Request) -> httpx.Response:
            nonlocal create_called, delete_called, list_call_count
            url = str(request.url)

            if request.method == "GET" and "/branches" in url and "/endpoints" not in url:
                list_call_count += 1
                if list_call_count == 1:
                    # First call: for create_branch to find parent
                    return httpx.Response(
                        200,
                        json={
                            "branches": [
                                {
                                    "id": "br-main-123",
                                    "name": "main",
                                    "parent_id": None,
                                    "created_at": "2024-01-15T12:00:00Z",
                                }
                            ]
                        },
                    )
                else:
                    # Second call: for delete_branch to find branch ID
                    return httpx.Response(
                        200,
                        json={
                            "branches": [
                                {
                                    "id": "br-main-123",
                                    "name": "main",
                                    "parent_id": None,
                                    "created_at": "2024-01-15T12:00:00Z",
                                },
                                {
                                    "id": "br-temp-999",
                                    "name": "temp-branch",
                                    "parent_id": "br-main-123",
                                    "created_at": "2024-01-15T14:00:00Z",
                                },
                            ]
                        },
                    )
            elif request.method == "POST" and "/branches" in url:
                create_called = True
                return httpx.Response(
                    201,
                    json={
                        "branch": {
                            "id": "br-temp-999",
                            "name": "temp-branch",
                            "parent_id": "br-main-123",
                            "created_at": "2024-01-15T14:00:00Z",
                        },
                        "endpoints": [{"id": "ep-temp-111", "type": "read_write"}],
                        "connection_uris": [
                            {"connection_uri": "postgresql://user:pass@temp.neon.tech/neondb"}
                        ],
                    },
                )
            elif request.method == "GET" and "/endpoints/ep-temp-111" in url:
                # Endpoint status check
                return httpx.Response(
                    200,
                    json={"endpoint": {"id": "ep-temp-111", "current_state": "active"}},
                )
            elif request.method == "GET" and "/connection_uri" in url:
                return httpx.Response(
                    200,
                    json={"uri": "postgresql://user:pass@temp.neon.tech/neondb"},
                )
            elif request.method == "DELETE" and "br-temp-999" in url:
                delete_called = True
                return httpx.Response(204)

            return httpx.Response(404)

        transport = httpx.MockTransport(context_handler)
        manager._client = httpx.AsyncClient(
            base_url=NEON_API_BASE_URL,
            transport=transport,
            headers={"Authorization": "Bearer test-api-key"},
        )

        try:
            async with manager.branch_context("temp-branch") as conn_str:
                # Connection string comes from connection_uris in create response now
                assert conn_str is not None
                assert (
                    "neon.tech" in conn_str
                    or conn_str == "postgresql://user:pass@temp.neon.tech/neondb"
                )
                assert create_called

            # After context exit, delete should have been called
            assert delete_called
        finally:
            await manager.close()

    async def test_branch_context_cleanup_on_error(self, manager):
        """Test that branch_context cleans up branch even when exception occurs."""
        delete_called = False
        list_call_count = 0

        def error_context_handler(request: httpx.Request) -> httpx.Response:
            nonlocal delete_called, list_call_count
            url = str(request.url)

            if request.method == "GET" and "/branches" in url and "/endpoints" not in url:
                list_call_count += 1
                if list_call_count == 1:
                    return httpx.Response(
                        200,
                        json={
                            "branches": [
                                {
                                    "id": "br-main-123",
                                    "name": "main",
                                    "parent_id": None,
                                    "created_at": "2024-01-15T12:00:00Z",
                                }
                            ]
                        },
                    )
                else:
                    return httpx.Response(
                        200,
                        json={
                            "branches": [
                                {
                                    "id": "br-error-888",
                                    "name": "error-branch",
                                    "parent_id": "br-main-123",
                                    "created_at": "2024-01-15T14:00:00Z",
                                }
                            ]
                        },
                    )
            elif request.method == "POST" and "/branches" in url:
                return httpx.Response(
                    201,
                    json={
                        "branch": {
                            "id": "br-error-888",
                            "name": "error-branch",
                            "parent_id": "br-main-123",
                            "created_at": "2024-01-15T14:00:00Z",
                        },
                        "endpoints": [{"id": "ep-error-222", "type": "read_write"}],
                        "connection_uris": [
                            {"connection_uri": "postgresql://user:pass@error.neon.tech/neondb"}
                        ],
                    },
                )
            elif request.method == "GET" and "/endpoints/ep-error-222" in url:
                # Endpoint status check
                return httpx.Response(
                    200,
                    json={"endpoint": {"id": "ep-error-222", "current_state": "active"}},
                )
            elif request.method == "GET" and "/connection_uri" in url:
                return httpx.Response(
                    200,
                    json={"uri": "postgresql://user:pass@error.neon.tech/neondb"},
                )
            elif request.method == "DELETE" and "br-error-888" in url:
                delete_called = True
                return httpx.Response(204)

            return httpx.Response(404)

        transport = httpx.MockTransport(error_context_handler)
        manager._client = httpx.AsyncClient(
            base_url=NEON_API_BASE_URL,
            transport=transport,
            headers={"Authorization": "Bearer test-api-key"},
        )

        try:
            with pytest.raises(RuntimeError, match="Simulated error"):
                async with manager.branch_context("error-branch"):
                    raise RuntimeError("Simulated error during test")

            # Even after exception, delete should have been called
            assert delete_called
        finally:
            await manager.close()
