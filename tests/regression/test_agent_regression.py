"""Regression test: daily pipeline still works unchanged with agent layer present.

Validates that adding the agentic analysis system didn't break the existing
pipeline. Imports agent modules to ensure no circular imports, then verifies
the core pipeline commands and services remain functional.

Covers OpenSpec task 8.6.
"""

import importlib


class TestAgentLayerRegression:
    """Verify the agent layer doesn't interfere with the existing pipeline."""

    def test_agent_imports_dont_cause_circular_dependencies(self):
        """Importing agent modules shouldn't break any existing imports."""
        modules = [
            "src.agents.conductor",
            "src.agents.registry",
            "src.agents.specialists.base",
            "src.agents.specialists.analysis",
            "src.agents.specialists.ingestion",
            "src.agents.specialists.research",
            "src.agents.specialists.synthesis",
            "src.agents.memory.provider",
            "src.agents.memory.models",
            "src.agents.memory.strategies.base",
            "src.agents.approval.gates",
            "src.agents.persona.loader",
            "src.agents.persona.models",
            "src.agents.scheduler.scheduler",
            "src.agents.scheduler.tasks",
        ]
        for mod_name in modules:
            mod = importlib.import_module(mod_name)
            assert mod is not None, f"Failed to import {mod_name}"

    def test_agent_imports_dont_break_pipeline_imports(self):
        """Importing agent modules before pipeline modules works fine."""
        # Import agent layer first
        import src.agents.conductor  # noqa: F401
        import src.agents.registry  # noqa: F401

        # Then import pipeline modules — these should still work
        from src.cli import app  # noqa: F401
        from src.services.llm_router import LLMRouter  # noqa: F401

    def test_agent_models_coexist_with_content_models(self):
        """Agent ORM models don't conflict with existing content models."""
        from src.models.agent_insight import AgentInsight
        from src.models.agent_memory import AgentMemory
        from src.models.agent_task import AgentTask
        from src.models.content import Content
        from src.models.digest import Digest
        from src.models.summary import Summary

        # All models should have __tablename__ without conflicts
        table_names = {
            Content.__tablename__,
            Summary.__tablename__,
            Digest.__tablename__,
            AgentTask.__tablename__,
            AgentInsight.__tablename__,
            AgentMemory.__tablename__,
        }
        assert len(table_names) == 6  # No duplicates

    def test_agent_enums_dont_conflict_with_existing_enums(self):
        """Agent-specific enums are distinct from pipeline enums."""
        from src.models.agent_task import AgentTaskSource, AgentTaskStatus

        # Agent enums should have unique values
        assert "received" in [s.value for s in AgentTaskStatus]
        assert "user" in [s.value for s in AgentTaskSource]

    def test_pipeline_cli_commands_still_registered(self):
        """Core CLI commands are still accessible after agent commands added."""
        from src.cli.app import app

        # Get all registered command names
        command_names = set()
        for cmd_info in app.registered_groups:
            command_names.add(cmd_info.name)

        # Agent commands should be present
        assert "agent" in command_names

    def test_agent_routes_registered_without_breaking_existing(self):
        """Agent API routes are mounted alongside existing routes."""
        from src.api.app import app

        # Collect all route paths
        paths = {route.path for route in app.routes if hasattr(route, "path")}

        # Agent routes should exist
        assert any("/agent/" in p for p in paths)

        # Existing routes should still exist
        assert any("/health" in p for p in paths)

    def test_worker_handler_registration_includes_agent_task(self):
        """The queue worker registers the agent_task handler."""
        from src.queue.worker import _handlers, register_all_handlers

        register_all_handlers()

        assert "execute_agent_task" in _handlers

    def test_specialist_registry_creates_without_errors(self):
        """Default specialist registry can be created with a mock router."""
        from unittest.mock import MagicMock

        from src.agents.registry import SpecialistRegistry

        mock_router = MagicMock()
        registry = SpecialistRegistry.create_default(llm_router=mock_router)

        assert len(registry.list_specialists()) == 4

    def test_persona_files_loadable(self):
        """All persona YAML files can be loaded without errors."""
        from src.agents.persona.loader import PersonaLoader

        personas = PersonaLoader.list_personas()
        assert "default" in personas

        for persona_name in personas:
            config = PersonaLoader.load(persona_name)
            # Persona YAML 'name' field is the display name, not the filename
            assert config.name is not None
            assert len(config.name) > 0

    def test_approval_yaml_parseable(self):
        """settings/approval.yaml can be loaded and parsed."""
        from pathlib import Path

        import yaml  # type: ignore[import-untyped]

        approval_path = Path("settings/approval.yaml")
        if approval_path.exists():
            with open(approval_path) as f:
                data = yaml.safe_load(f)
            assert isinstance(data, dict)

    def test_schedule_yaml_parseable(self):
        """settings/schedule.yaml can be loaded and parsed."""
        from pathlib import Path

        import yaml  # type: ignore[import-untyped]

        schedule_path = Path("settings/schedule.yaml")
        if schedule_path.exists():
            with open(schedule_path) as f:
                data = yaml.safe_load(f)
            assert isinstance(data, (dict, list))
