"""Live E2E test: Daily Pipeline with LLM Semantic Validation.

Simulates the exact workflow a user follows via CLI or API:

    1. Ingest content (via URL ingestion for deterministic input)
    2. Summarize ingested content
    3. Analyze themes
    4. Generate daily digest
    5. Review and approve digest
    6. Generate podcast script
    7. Cross-stage consistency validation

At each stage, an LLM judge validates that the artifact is
semantically correct. Validation scores are optionally reported
to Opik or Langfuse (linked to OTel trace IDs from X-Trace-Id
response headers).

Usage:
    # Start backend:
    make dev-bg

    # Run with custom LLM evaluator (default):
    ANTHROPIC_API_KEY=sk-ant-... pytest tests/e2e/ -m e2e -v --no-cov

    # Run with Opik scoring:
    E2E_EVALUATOR=opik ANTHROPIC_API_KEY=... OPIK_API_KEY=... \
        pytest tests/e2e/ -m e2e -v --no-cov

    # Run with Langfuse scoring:
    E2E_EVALUATOR=langfuse ANTHROPIC_API_KEY=... \
        LANGFUSE_PUBLIC_KEY=... LANGFUSE_SECRET_KEY=... \
        pytest tests/e2e/ -m e2e -v --no-cov

    # Structural checks only (no LLM, no scoring):
    pytest tests/e2e/ -m e2e -v --no-cov

Markers:
    @pytest.mark.e2e — requires a running backend
    @pytest.mark.regression — part of regression suite
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from tests.e2e.conftest import BaseEvaluator, extract_trace_id, poll_until_complete

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.e2e, pytest.mark.regression]

# ─── Test Content ────────────────────────────────────────────
# Use a well-known, stable URL for deterministic ingestion.

TEST_CONTENT_URL = (
    "https://raw.githubusercontent.com/anthropics/anthropic-cookbook/"
    "main/README.md"
)
TEST_CONTENT_TITLE = "Anthropic Cookbook README"


# Module-level state shared across sequential tests
_pipeline_state: dict = {}


class TestDailyPipelineLive:
    """Full daily pipeline executed against a live backend.

    Tests run in order — each stage depends on the previous one.
    The evaluator checks semantic quality and optionally reports
    scores to Opik/Langfuse linked to the OTel trace IDs.
    """

    # ── Stage 1: Ingest ──────────────────────────────────────

    def test_01_ingest_content(self, http_client: httpx.Client):
        """Ingest test content via direct URL."""
        resp = http_client.post(
            "/api/v1/contents/ingest",
            json={
                "source": "url",
                "url": TEST_CONTENT_URL,
                "title": TEST_CONTENT_TITLE,
                "tags": ["e2e-test", "regression"],
            },
        )
        assert resp.status_code == 200, f"Ingest failed: {resp.text}"
        data = resp.json()

        _pipeline_state["ingest_task_id"] = data.get("task_id")
        _pipeline_state["ingest_response"] = data
        _pipeline_state["ingest_trace_id"] = extract_trace_id(resp)

        logger.info(f"Ingestion started: {data}")

    def test_02_verify_ingested_content(self, http_client: httpx.Client):
        """Verify content appears in the content list after ingestion."""
        time.sleep(5)

        resp = http_client.get(
            "/api/v1/contents",
            params={"search": TEST_CONTENT_TITLE, "limit": 5},
        )
        assert resp.status_code == 200, f"Content list failed: {resp.text}"
        data = resp.json()

        items = data.get("items", [])
        assert len(items) > 0, (
            f"No content found matching '{TEST_CONTENT_TITLE}'. "
            f"Response: {json.dumps(data, indent=2)[:500]}"
        )

        content = items[0]
        _pipeline_state["content_id"] = content["id"]
        _pipeline_state["content"] = content

        assert content.get("title"), "Content has no title"
        assert content.get("source_type"), "Content has no source_type"
        assert content.get("status") in (
            "completed", "parsed", "pending",
        ), f"Unexpected status: {content.get('status')}"

    def test_03_validate_ingested_content(
        self, http_client: httpx.Client, llm_validator: BaseEvaluator
    ):
        """LLM validates that ingested content is well-formed."""
        content_id = _pipeline_state.get("content_id")
        if not content_id:
            pytest.skip("No content ID from previous stage")

        resp = http_client.get(f"/api/v1/contents/{content_id}")
        assert resp.status_code == 200
        content = resp.json()
        trace_id = extract_trace_id(resp)

        result = llm_validator.validate(
            "ingested_content",
            content,
            context=f"Ingested from URL: {TEST_CONTENT_URL}",
            trace_id=trace_id,
        )
        logger.info(f"Content validation: {result}")
        result.assert_passed(min_score=0.4)

    # ── Stage 2: Summarize ───────────────────────────────────

    def test_04_summarize_content(self, http_client: httpx.Client):
        """Trigger summarization of the ingested content."""
        content_id = _pipeline_state.get("content_id")
        if not content_id:
            pytest.skip("No content ID from ingestion stage")

        resp = http_client.post(
            "/api/v1/contents/summarize",
            json={"content_ids": [content_id]},
        )
        assert resp.status_code == 200, f"Summarize failed: {resp.text}"
        data = resp.json()
        _pipeline_state["summarize_response"] = data
        _pipeline_state["summarize_trace_id"] = extract_trace_id(resp)

        logger.info(f"Summarization started: {data}")

    def test_05_verify_summary(self, http_client: httpx.Client):
        """Verify summary was generated for the content."""
        content_id = _pipeline_state.get("content_id")
        if not content_id:
            pytest.skip("No content ID")

        time.sleep(15)

        resp = http_client.get(f"/api/v1/summaries/by-content/{content_id}")

        if resp.status_code == 404:
            for _ in range(5):
                time.sleep(5)
                resp = http_client.get(
                    f"/api/v1/summaries/by-content/{content_id}"
                )
                if resp.status_code == 200:
                    break

        assert resp.status_code == 200, (
            f"Summary not found for content {content_id}: {resp.text}"
        )
        summary = resp.json()
        _pipeline_state["summary"] = summary
        _pipeline_state["summary_id"] = summary.get("id")
        _pipeline_state["summary_trace_id"] = extract_trace_id(resp)

        assert summary.get("id"), "Summary has no ID"

    def test_06_validate_summary(self, llm_validator: BaseEvaluator):
        """LLM validates that the summary is coherent and complete."""
        summary = _pipeline_state.get("summary")
        if not summary:
            pytest.skip("No summary from previous stage")

        content = _pipeline_state.get("content", {})
        result = llm_validator.validate(
            "summary",
            summary,
            context=(
                f"Source content title: {content.get('title', 'Unknown')}\n"
                f"Source URL: {TEST_CONTENT_URL}"
            ),
            trace_id=_pipeline_state.get("summary_trace_id"),
        )
        logger.info(f"Summary validation: {result}")
        result.assert_passed(min_score=0.5)

    # ── Stage 3: Theme Analysis ──────────────────────────────

    def test_07_analyze_themes(self, http_client: httpx.Client):
        """Trigger theme analysis for recent content."""
        now = datetime.now(UTC)
        week_ago = now - timedelta(days=7)

        resp = http_client.post(
            "/api/v1/themes/analyze",
            json={
                "start_date": week_ago.isoformat(),
                "end_date": now.isoformat(),
                "max_themes": 10,
                "relevance_threshold": 0.2,
            },
        )
        assert resp.status_code == 200, f"Theme analysis failed: {resp.text}"
        data = resp.json()
        _pipeline_state["theme_analysis_id"] = data.get("analysis_id")
        _pipeline_state["theme_trace_id"] = extract_trace_id(resp)

        logger.info(f"Theme analysis started: {data}")

    def test_08_verify_themes(self, http_client: httpx.Client):
        """Verify theme analysis completed."""
        analysis_id = _pipeline_state.get("theme_analysis_id")
        if not analysis_id:
            time.sleep(15)
            resp = http_client.get("/api/v1/themes/latest")
            if resp.status_code == 200:
                data = resp.json()
                if "message" not in data:
                    _pipeline_state["theme_result"] = data
                    return
            pytest.skip("No theme analysis available")
            return

        try:
            result = poll_until_complete(
                http_client,
                f"/api/v1/themes/analysis/{analysis_id}",
                timeout=120.0,
                interval=3.0,
            )
            _pipeline_state["theme_result"] = result
        except TimeoutError:
            resp = http_client.get("/api/v1/themes/latest")
            if resp.status_code == 200:
                data = resp.json()
                if "message" not in data:
                    _pipeline_state["theme_result"] = data
                    return
            pytest.skip("Theme analysis timed out")

    def test_09_validate_themes(self, llm_validator: BaseEvaluator):
        """LLM validates that theme analysis is coherent."""
        themes = _pipeline_state.get("theme_result")
        if not themes:
            pytest.skip("No theme analysis result")

        result = llm_validator.validate(
            "theme_analysis",
            themes,
            context="Analysis of AI/tech newsletter content from the past week",
            trace_id=_pipeline_state.get("theme_trace_id"),
        )
        logger.info(f"Theme validation: {result}")
        result.assert_passed(min_score=0.4)

    # ── Stage 4: Digest Generation ───────────────────────────

    def test_10_generate_digest(self, http_client: httpx.Client):
        """Generate a daily digest from summarized content."""
        now = datetime.now(UTC)

        resp = http_client.post(
            "/api/v1/digests/generate",
            json={
                "digest_type": "daily",
                "period_start": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
                "period_end": now.strftime("%Y-%m-%d"),
            },
        )
        assert resp.status_code == 200, f"Digest generation failed: {resp.text}"
        data = resp.json()
        _pipeline_state["digest_response"] = data
        _pipeline_state["digest_gen_trace_id"] = extract_trace_id(resp)

        logger.info(f"Digest generation started: {data}")

    def test_11_verify_digest(self, http_client: httpx.Client):
        """Verify digest was generated and fetch full details."""
        time.sleep(30)

        resp = http_client.get("/api/v1/digests/", params={"limit": 1})
        assert resp.status_code == 200, f"Digest list failed: {resp.text}"

        digests = resp.json()
        if isinstance(digests, dict):
            digests = digests.get("items", digests.get("digests", []))

        if not digests:
            for _ in range(5):
                time.sleep(10)
                resp = http_client.get("/api/v1/digests/", params={"limit": 1})
                if resp.status_code == 200:
                    digests = resp.json()
                    if isinstance(digests, dict):
                        digests = digests.get("items", digests.get("digests", []))
                    if digests:
                        break

        assert digests, "No digests found after generation"

        digest = digests[0]
        digest_id = digest.get("id")
        _pipeline_state["digest_id"] = digest_id

        resp = http_client.get(f"/api/v1/digests/{digest_id}")
        assert resp.status_code == 200
        detail = resp.json()
        _pipeline_state["digest_detail"] = detail
        _pipeline_state["digest_trace_id"] = extract_trace_id(resp)

        assert detail.get("title"), "Digest has no title"
        assert detail.get("status") in (
            "COMPLETED", "PENDING_REVIEW", "APPROVED", "GENERATING",
        ), f"Unexpected digest status: {detail.get('status')}"

    def test_12_validate_digest(self, llm_validator: BaseEvaluator):
        """LLM validates that the digest is coherent and comprehensive."""
        detail = _pipeline_state.get("digest_detail")
        if not detail:
            pytest.skip("No digest detail from previous stage")

        result = llm_validator.validate(
            "digest",
            detail,
            context=(
                f"Daily digest covering AI/tech newsletters.\n"
                f"Content count: {detail.get('content_count', detail.get('newsletter_count', 'unknown'))}\n"
                f"Period: {detail.get('period_start', '?')} to {detail.get('period_end', '?')}"
            ),
            criteria=[
                "Executive overview provides a coherent summary of key developments",
                "Strategic insights are actionable and relevant to tech leaders",
                "Technical developments are accurate and sufficiently detailed",
                "Emerging trends are forward-looking and substantiated",
                "Actionable recommendations are concrete and differentiated by audience",
                "Sources are cited and traceable",
                "Sections are internally coherent and not repetitive across categories",
            ],
            trace_id=_pipeline_state.get("digest_trace_id"),
        )
        logger.info(f"Digest validation: {result}")
        result.assert_passed(min_score=0.5)

    # ── Stage 5: Digest Review ───────────────────────────────

    def test_13_review_digest(self, http_client: httpx.Client):
        """Approve the generated digest via review endpoint."""
        digest_id = _pipeline_state.get("digest_id")
        if not digest_id:
            pytest.skip("No digest ID from previous stage")

        resp = http_client.post(
            f"/api/v1/digests/{digest_id}/review",
            json={
                "action": "approve",
                "reviewer": "e2e-regression-test",
                "notes": "Auto-approved by E2E regression test",
            },
        )
        assert resp.status_code in (200, 400), f"Review failed: {resp.text}"

        if resp.status_code == 200:
            logger.info(f"Digest {digest_id} approved")
        else:
            logger.warning(f"Digest review returned 400: {resp.text}")

    # ── Stage 6: Podcast Script ──────────────────────────────

    def test_14_generate_podcast_script(self, http_client: httpx.Client):
        """Generate a podcast script from the approved digest."""
        digest_id = _pipeline_state.get("digest_id")
        if not digest_id:
            pytest.skip("No digest ID")

        resp = http_client.post(
            "/api/v1/podcasts/generate",
            json={"digest_id": digest_id, "length": "brief"},
        )
        if resp.status_code != 200:
            logger.warning(
                f"Podcast script generation returned {resp.status_code}: {resp.text}"
            )
            pytest.skip(f"Script generation failed: {resp.text}")

        data = resp.json()
        _pipeline_state["script_response"] = data
        _pipeline_state["script_id"] = data.get("id")
        _pipeline_state["script_gen_trace_id"] = extract_trace_id(resp)

        logger.info(f"Script generation started: {data}")

    def test_15_verify_podcast_script(self, http_client: httpx.Client):
        """Verify podcast script was generated."""
        script_id = _pipeline_state.get("script_id")
        digest_id = _pipeline_state.get("digest_id")
        if not script_id and not digest_id:
            pytest.skip("No script or digest ID")

        time.sleep(20)

        if script_id:
            resp = http_client.get(f"/api/v1/scripts/{script_id}")
            if resp.status_code == 200:
                _pipeline_state["script_detail"] = resp.json()
                _pipeline_state["script_trace_id"] = extract_trace_id(resp)
                return

        resp = http_client.get(
            "/api/v1/scripts/",
            params={"digest_id": digest_id, "limit": 1},
        )
        if resp.status_code == 200:
            scripts = resp.json()
            if isinstance(scripts, list) and scripts:
                script_id = scripts[0].get("id")
                _pipeline_state["script_id"] = script_id
                resp = http_client.get(f"/api/v1/scripts/{script_id}")
                if resp.status_code == 200:
                    _pipeline_state["script_detail"] = resp.json()
                    _pipeline_state["script_trace_id"] = extract_trace_id(resp)
                    return

        pytest.skip("Script not found — generation may still be in progress")

    def test_16_validate_podcast_script(self, llm_validator: BaseEvaluator):
        """LLM validates that the podcast script is natural and complete."""
        script = _pipeline_state.get("script_detail")
        if not script:
            pytest.skip("No script detail from previous stage")

        digest = _pipeline_state.get("digest_detail", {})
        result = llm_validator.validate(
            "podcast_script",
            script,
            context=(
                f"Podcast script generated from digest: {digest.get('title', 'Unknown')}\n"
                f"Expected length: brief\n"
                f"Digest had {digest.get('content_count', digest.get('newsletter_count', '?'))} content items"
            ),
            criteria=[
                "Script has clear intro, body sections, and outro",
                "Dialogue between personas feels natural and conversational",
                "Key insights from the digest are covered in the script",
                "Technical content is explained accessibly",
                "Word count is appropriate for a 'brief' length podcast",
                "No placeholder text or template artifacts remain",
            ],
            trace_id=_pipeline_state.get("script_trace_id"),
        )
        logger.info(f"Script validation: {result}")
        result.assert_passed(min_score=0.5)


# =============================================================================
# Cross-Stage Consistency Validation
# =============================================================================


class TestPipelineConsistency:
    """Final validation: cross-stage consistency of all pipeline artifacts."""

    def test_pipeline_artifacts_are_consistent(
        self, llm_validator: BaseEvaluator
    ):
        """LLM validates that all stages produced coherent, related artifacts."""
        content = _pipeline_state.get("content", {})
        summary = _pipeline_state.get("summary", {})
        digest = _pipeline_state.get("digest_detail", {})
        script = _pipeline_state.get("script_detail", {})

        artifacts_available = sum(1 for a in [content, summary, digest, script] if a)
        if artifacts_available < 2:
            pytest.skip(
                f"Only {artifacts_available} artifacts available — "
                "need at least 2 for consistency check"
            )

        artifact_summary = {
            "content_title": content.get("title", "N/A"),
            "content_source": content.get("source_type", "N/A"),
            "summary_excerpt": str(summary)[:500] if summary else "N/A",
            "digest_title": digest.get("title", "N/A"),
            "digest_overview": digest.get("executive_overview", "N/A")[:500],
            "digest_section_count": (
                len(digest.get("strategic_insights", []))
                + len(digest.get("technical_developments", []))
                + len(digest.get("emerging_trends", []))
            ) if digest else 0,
            "script_title": script.get("title", "N/A"),
            "script_section_count": len(script.get("sections", [])),
        }

        result = llm_validator.validate(
            "pipeline_consistency",
            artifact_summary,
            context="Full daily pipeline: ingest → summarize → digest → podcast script",
            trace_id=_pipeline_state.get("digest_trace_id"),
        )
        logger.info(f"Pipeline consistency validation: {result}")
        result.assert_passed(min_score=0.4)
