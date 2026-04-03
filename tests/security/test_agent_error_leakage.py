"""Security tests for agent task error leakage.

These tests verify that internal error details are not leaked
through error responses or database status updates.
"""

import pytest
from unittest.mock import patch, AsyncMock

from src.queue.worker import _handlers, register_all_handlers

class TestAgentTaskErrorLeakage:
    """Test that agent task failure handling doesn't leak sensitive error details."""

    @pytest.mark.asyncio
    async def test_agent_task_error_leakage_mitigated(self):
        """Test that the execute_agent_task handler does NOT leak internal error details.

        This test verifies the fix that replaces raw exception strings with
        generic error messages.
        """
        # Ensure handlers are registered so execute_agent_task is available
        register_all_handlers()

        # Get the handler we want to test
        handler = _handlers.get("execute_agent_task")
        assert handler is not None, "execute_agent_task handler not found"

        sensitive_data = "SECRET_DB_CONNECTION_STRING_12345"

        # We need to mock Conductor.execute_task to raise our exception
        # and AgentTaskService.update_task_status to capture what is saved
        with patch("src.storage.database.get_db"), \
             patch("src.services.agent_service.AgentTaskService") as mock_svc_cls, \
             patch("src.agents.approval.gates.ApprovalGate"), \
             patch("src.agents.conductor.Conductor.execute_task", new_callable=AsyncMock) as mock_execute:

            mock_execute.side_effect = RuntimeError(f"Connection failed: {sensitive_data}")

            mock_svc_instance = mock_svc_cls.return_value

            payload = {
                "task_id": "test-task-123",
                "task_type": "research",
                "persona": "default",
                "prompt": "test prompt"
            }

            # The handler will raise the exception after updating the status
            with pytest.raises(RuntimeError):
                await handler(job_id=1, payload=payload)

            # Now verify what was passed to update_task_status
            # The handler calls: svc.update_task_status(task_id, "failed", error=...)
            mock_svc_instance.update_task_status.assert_called_with(
                "test-task-123", "failed", error="Failed due to an internal error"
            )

            # Additional assertion to ensure sensitive_data is absolutely not in any call args
            for call in mock_svc_instance.update_task_status.call_args_list:
                args, kwargs = call
                for arg in args:
                    if isinstance(arg, str):
                        assert sensitive_data not in arg
                for val in kwargs.values():
                    if isinstance(val, str):
                        assert sensitive_data not in val
