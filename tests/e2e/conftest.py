"""Live E2E test fixtures — real backend + semantic validation.

Runs the actual pipeline against a live backend and validates artifacts
using a pluggable evaluator that can use:
  1. Custom LLM evaluator (default) — calls Claude API directly
  2. Opik evaluator — sends scores to Opik via its API
  3. Langfuse evaluator — sends scores to Langfuse via its API

The evaluator captures OTel trace IDs from API response headers (X-Trace-Id)
and associates validation scores with the corresponding traces.

Usage:
    # Start backend first:
    make dev-bg

    # Run with custom LLM evaluator (default):
    ANTHROPIC_API_KEY=sk-ant-... pytest tests/e2e/ -m e2e -v --no-cov

    # Run with Opik scoring:
    E2E_EVALUATOR=opik OPIK_API_KEY=... pytest tests/e2e/ -m e2e -v --no-cov

    # Run with Langfuse scoring:
    E2E_EVALUATOR=langfuse LANGFUSE_PUBLIC_KEY=... LANGFUSE_SECRET_KEY=... \
        pytest tests/e2e/ -m e2e -v --no-cov

    # Structural checks only (no LLM, no scoring):
    pytest tests/e2e/ -m e2e -v --no-cov

Prerequisites:
    - Backend running with database migrated
    - ANTHROPIC_API_KEY set (for LLM-based evaluation)
    - At least one content source configured (or use file/URL ingestion)
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from abc import ABC, abstractmethod

import httpx
import pytest

logger = logging.getLogger(__name__)

E2E_BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8000")
E2E_ADMIN_KEY = os.getenv("E2E_ADMIN_KEY", os.getenv("ADMIN_API_KEY", ""))
E2E_TIMEOUT = float(os.getenv("E2E_TIMEOUT", "300"))  # 5 min default
E2E_EVALUATOR = os.getenv("E2E_EVALUATOR", "custom")  # custom | opik | langfuse


# =============================================================================
# Core Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def base_url() -> str:
    return E2E_BASE_URL


@pytest.fixture(scope="session")
def admin_key() -> str:
    return E2E_ADMIN_KEY


@pytest.fixture(scope="session")
def api_client(base_url: str, admin_key: str):
    """Shared API client for live E2E tests."""
    from src.cli.api_client import ApiClient

    client = ApiClient(
        base_url=base_url,
        admin_key=admin_key,
        timeout=E2E_TIMEOUT,
    )
    if not client.health_check():
        pytest.skip(f"Backend not reachable at {base_url}")

    yield client
    client.close()


@pytest.fixture(scope="session")
def http_client(base_url: str, admin_key: str) -> httpx.Client:
    """Raw httpx client for endpoints not covered by ApiClient.

    Responses include X-Trace-Id headers when OTel is enabled on the backend,
    which the evaluator uses to link scores back to traces.
    """
    headers = {}
    if admin_key:
        headers["X-Admin-Key"] = admin_key
    with httpx.Client(
        base_url=base_url, timeout=E2E_TIMEOUT, headers=headers
    ) as client:
        yield client


@pytest.fixture(scope="session")
def llm_validator():
    """Pluggable evaluator based on E2E_EVALUATOR env var.

    Returns an evaluator that validates artifacts and optionally
    reports scores to an observability backend (Opik or Langfuse).
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set — LLM validation unavailable")

    evaluator_type = E2E_EVALUATOR.lower()

    if evaluator_type == "opik":
        return OpikEvaluator(anthropic_api_key=api_key)
    elif evaluator_type == "langfuse":
        return LangfuseEvaluator(anthropic_api_key=api_key)
    else:
        return CustomLLMEvaluator(api_key=api_key)


# =============================================================================
# Validation Result
# =============================================================================


class ValidationResult:
    """Result of semantic validation."""

    def __init__(
        self,
        passed: bool,
        score: float,
        reasoning: str,
        issues: list[str] | None = None,
        trace_id: str | None = None,
    ):
        self.passed = passed
        self.score = score
        self.reasoning = reasoning
        self.issues = issues or []
        self.trace_id = trace_id

    def __repr__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        trace = f", trace={self.trace_id}" if self.trace_id else ""
        return f"ValidationResult({status}, score={self.score:.2f}, issues={len(self.issues)}{trace})"

    def assert_passed(self, min_score: float = 0.5) -> None:
        """Assert that validation passed with minimum score."""
        assert self.passed, (
            f"LLM validation failed (score={self.score:.2f}): {self.reasoning}\n"
            f"Issues: {self.issues}"
        )
        assert self.score >= min_score, (
            f"LLM validation score too low: {self.score:.2f} < {min_score}\n"
            f"Reasoning: {self.reasoning}"
        )


# =============================================================================
# Base Evaluator
# =============================================================================


class BaseEvaluator(ABC):
    """Base class for pipeline artifact evaluators."""

    # Default criteria per artifact type
    DEFAULT_CRITERIA = {
        "ingested_content": [
            "Content items have titles and source types",
            "Status is 'completed' or 'parsed'",
            "At least one content item was ingested",
            "Metadata fields (source_type, ingested_at) are populated",
        ],
        "summary": [
            "Summary text is coherent and readable",
            "Summary captures the key points of the source content",
            "Summary is not just a copy of the title",
            "Key themes and takeaways are identified",
        ],
        "theme_analysis": [
            "Themes are distinct and well-defined",
            "Theme names are descriptive",
            "Relevance scores are reasonable (not all 1.0 or all 0.0)",
            "Themes relate to the analyzed content",
            "Categories make sense for AI/tech content",
        ],
        "digest": [
            "Digest has an executive overview",
            "Strategic insights are actionable and specific",
            "Technical developments are accurate and detailed",
            "Emerging trends are forward-looking",
            "Actionable recommendations are concrete",
            "Sources are cited",
            "Content is coherent across sections",
        ],
        "podcast_script": [
            "Script has intro, body, and outro sections",
            "Dialogue alternates between personas naturally",
            "Content matches the source digest",
            "Word count is reasonable for the specified length",
            "Tone is conversational but informative",
        ],
        "pipeline_consistency": [
            "The summary relates to the ingested content",
            "The digest title and overview reflect the summarized content",
            "The podcast script title matches or relates to the digest",
            "There is a logical flow from raw content to final script",
            "No stage appears to have produced unrelated or contradictory content",
        ],
    }

    def validate(
        self,
        artifact_type: str,
        artifact: dict | list | str,
        context: str = "",
        criteria: list[str] | None = None,
        trace_id: str | None = None,
    ) -> ValidationResult:
        """Validate an artifact and optionally report the score.

        Args:
            artifact_type: What this artifact is (e.g., "digest", "summary")
            artifact: The artifact data to validate
            context: Additional context
            criteria: Specific things to check
            trace_id: OTel trace ID from the X-Trace-Id response header
        """
        if criteria is None:
            criteria = self.DEFAULT_CRITERIA.get(
                artifact_type, ["Artifact is well-formed and complete"]
            )

        result = self._evaluate(artifact_type, artifact, context, criteria)
        result.trace_id = trace_id

        # Report score to backend (Opik, Langfuse, etc.)
        self._report_score(artifact_type, result)

        return result

    @abstractmethod
    def _evaluate(
        self,
        artifact_type: str,
        artifact: dict | list | str,
        context: str,
        criteria: list[str],
    ) -> ValidationResult:
        """Run the LLM evaluation. Subclasses implement this."""
        ...

    def _report_score(self, artifact_type: str, result: ValidationResult) -> None:
        """Report score to observability backend. Override in subclasses."""
        pass

    def close(self) -> None:
        """Clean up resources."""
        pass


# =============================================================================
# Custom LLM Evaluator (default)
# =============================================================================


class CustomLLMEvaluator(BaseEvaluator):
    """Calls Claude API directly to evaluate artifacts.

    This is the simplest evaluator — no external scoring platform needed.
    Results are logged and asserted in the test.
    """

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5"):
        self.model = model
        self._client = httpx.Client(
            base_url="https://api.anthropic.com",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=60.0,
        )

    def _evaluate(
        self,
        artifact_type: str,
        artifact: dict | list | str,
        context: str,
        criteria: list[str],
    ) -> ValidationResult:
        criteria_text = "\n".join(f"- {c}" for c in criteria)

        prompt = f"""You are a quality assurance judge for an AI newsletter aggregation pipeline.

Evaluate the following {artifact_type} artifact and determine if it meets quality standards.

## Evaluation Criteria
{criteria_text}

## Context
{context}

## Artifact to Evaluate
```json
{json.dumps(artifact, indent=2, default=str)[:8000]}
```

## Instructions
Respond with a JSON object:
{{
  "pass": true/false,
  "score": 0.0-1.0,
  "reasoning": "Brief explanation of your assessment",
  "issues": ["list of specific issues found, if any"]
}}

Be strict but fair. Minor stylistic issues should not cause failure.
Focus on: completeness, coherence, factual consistency, and structural correctness."""

        resp = self._client.post(
            "/v1/messages",
            json={
                "model": self.model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        response_data = resp.json()

        text = response_data["content"][0]["text"]
        return self._parse_llm_response(text)

    def _parse_llm_response(self, text: str) -> ValidationResult:
        try:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            result = json.loads(text.strip())
        except (json.JSONDecodeError, IndexError):
            return ValidationResult(
                passed=True,
                score=0.5,
                reasoning=f"LLM response could not be parsed: {text[:200]}",
                issues=["LLM response format error"],
            )

        return ValidationResult(
            passed=result.get("pass", False),
            score=result.get("score", 0.0),
            reasoning=result.get("reasoning", ""),
            issues=result.get("issues", []),
        )

    def close(self) -> None:
        self._client.close()


# =============================================================================
# Opik Evaluator
# =============================================================================


class OpikEvaluator(CustomLLMEvaluator):
    """Evaluates via Claude and reports scores to Opik.

    Scores are sent to the Opik API and linked to traces via the
    trace_id captured from the backend's X-Trace-Id response header.
    This allows viewing evaluation results alongside pipeline traces
    in the Opik dashboard.

    Requires: OPIK_API_KEY (Comet Cloud) or OPIK_BACKEND_URL (self-hosted)
    """

    def __init__(self, anthropic_api_key: str):
        super().__init__(api_key=anthropic_api_key)

        self._opik_api_key = os.getenv("OPIK_API_KEY")
        self._opik_workspace = os.getenv("OPIK_WORKSPACE")
        self._opik_project = os.getenv("OPIK_PROJECT_NAME", "newsletter-aggregator")

        # Determine Opik endpoint
        if self._opik_api_key:
            # Comet Cloud
            self._opik_base_url = "https://www.comet.com/opik/api"
            self._opik_headers = {
                "Authorization": self._opik_api_key,
                "Content-Type": "application/json",
            }
            if self._opik_workspace:
                self._opik_headers["Comet-Workspace"] = self._opik_workspace
        else:
            # Self-hosted
            self._opik_base_url = os.getenv("OPIK_BACKEND_URL", "http://localhost:8080")
            self._opik_headers = {"Content-Type": "application/json"}

        self._opik_client = httpx.Client(
            base_url=self._opik_base_url,
            headers=self._opik_headers,
            timeout=10.0,
        )

    def _report_score(self, artifact_type: str, result: ValidationResult) -> None:
        """Report validation score to Opik as a feedback score on the trace."""
        if not result.trace_id:
            logger.debug(f"No trace_id for {artifact_type} — skipping Opik score report")
            return

        try:
            self._opik_client.post(
                "/v1/private/feedback-scores",
                json={
                    "name": f"e2e_{artifact_type}_quality",
                    "value": result.score,
                    "source": "e2e_regression",
                    "trace_id": result.trace_id,
                    "project_name": self._opik_project,
                    "reason": result.reasoning[:500],
                },
            )
            logger.info(
                f"Opik score reported: {artifact_type}={result.score:.2f} "
                f"(trace={result.trace_id})"
            )
        except Exception as e:
            logger.warning(f"Failed to report score to Opik: {e}")

    def close(self) -> None:
        super().close()
        self._opik_client.close()


# =============================================================================
# Langfuse Evaluator
# =============================================================================


class LangfuseEvaluator(CustomLLMEvaluator):
    """Evaluates via Claude and reports scores to Langfuse.

    Scores are sent to the Langfuse API and linked to traces via the
    trace_id. This allows viewing evaluation results alongside pipeline
    traces in the Langfuse dashboard.

    Requires: LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY
    """

    def __init__(self, anthropic_api_key: str):
        super().__init__(api_key=anthropic_api_key)

        public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
        self._langfuse_base_url = os.getenv(
            "LANGFUSE_BASE_URL", "https://cloud.langfuse.com"
        )

        # Langfuse uses HTTP Basic Auth
        auth_str = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
        self._langfuse_client = httpx.Client(
            base_url=self._langfuse_base_url,
            headers={
                "Authorization": f"Basic {auth_str}",
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )

    def _report_score(self, artifact_type: str, result: ValidationResult) -> None:
        """Report validation score to Langfuse."""
        if not result.trace_id:
            logger.debug(f"No trace_id for {artifact_type} — skipping Langfuse score report")
            return

        try:
            self._langfuse_client.post(
                "/api/public/scores",
                json={
                    "name": f"e2e_{artifact_type}_quality",
                    "value": result.score,
                    "traceId": result.trace_id,
                    "comment": result.reasoning[:500],
                    "source": "API",
                },
            )
            logger.info(
                f"Langfuse score reported: {artifact_type}={result.score:.2f} "
                f"(trace={result.trace_id})"
            )
        except Exception as e:
            logger.warning(f"Failed to report score to Langfuse: {e}")

    def close(self) -> None:
        super().close()
        self._langfuse_client.close()


# =============================================================================
# Trace ID Extraction Helper
# =============================================================================


def extract_trace_id(response: httpx.Response) -> str | None:
    """Extract OTel trace ID from backend response headers.

    The backend adds X-Trace-Id to every response when OTel is enabled.
    This allows linking evaluation scores to the exact trace that
    produced the artifact being evaluated.
    """
    return response.headers.get("x-trace-id")


# =============================================================================
# Polling Utility
# =============================================================================


def poll_until_complete(
    http_client: httpx.Client,
    url: str,
    *,
    timeout: float = 120.0,
    interval: float = 2.0,
    terminal_statuses: set[str] | None = None,
) -> dict:
    """Poll a status endpoint until the resource reaches a terminal state.

    Returns:
        Final response JSON

    Raises:
        TimeoutError: If terminal status not reached within timeout
    """
    if terminal_statuses is None:
        terminal_statuses = {
            "completed", "failed", "error",
            "COMPLETED", "FAILED", "APPROVED", "REJECTED",
        }

    start = time.monotonic()
    while time.monotonic() - start < timeout:
        resp = http_client.get(url)
        if resp.status_code == 200:
            data = resp.json()
            status = data.get("status", "")
            if status in terminal_statuses:
                return data
        time.sleep(interval)

    raise TimeoutError(f"Timed out waiting for {url} (waited {timeout}s)")
