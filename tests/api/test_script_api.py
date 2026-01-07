"""Tests for podcast script API endpoints."""

from src.models.podcast import PodcastStatus


class TestListScripts:
    """Tests for GET /api/v1/scripts/ endpoint."""

    def test_list_scripts_empty(self, client):
        """Test listing scripts when database is empty."""
        response = client.get("/api/v1/scripts/")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_list_scripts_returns_items(self, client, sample_script):
        """Test listing scripts returns all items."""
        response = client.get("/api/v1/scripts/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == sample_script.id

    def test_list_scripts_filter_by_status(self, client, sample_script):
        """Test filtering scripts by status."""
        status = sample_script.status
        response = client.get(f"/api/v1/scripts/?status={status}")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_list_scripts_filter_by_digest(self, client, sample_script, sample_digest):
        """Test filtering scripts by digest ID."""
        response = client.get(f"/api/v1/scripts/?digest_id={sample_digest.id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["digest_id"] == sample_digest.id


class TestGetScript:
    """Tests for GET /api/v1/scripts/{id} endpoint."""

    def test_get_script_returns_detail(self, client, sample_script):
        """Test getting script by ID returns full detail."""
        response = client.get(f"/api/v1/scripts/{sample_script.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_script.id
        assert data["title"] == sample_script.title
        assert "sections" in data
        assert len(data["sections"]) > 0

    def test_get_script_not_found(self, client):
        """Test getting non-existent script returns 404."""
        response = client.get("/api/v1/scripts/99999")

        assert response.status_code == 404


class TestListPendingScripts:
    """Tests for GET /api/v1/scripts/pending-review endpoint."""

    def test_list_pending_scripts_empty(self, client):
        """Test listing pending scripts when none exist."""
        response = client.get("/api/v1/scripts/pending-review")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_list_pending_scripts_returns_items(self, client, sample_script):
        """Test listing pending scripts returns pending items."""
        # sample_script has status SCRIPT_PENDING_REVIEW
        response = client.get("/api/v1/scripts/pending-review")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == sample_script.id


class TestListApprovedScripts:
    """Tests for GET /api/v1/scripts/approved endpoint."""

    def test_list_approved_scripts_empty(self, client):
        """Test listing approved scripts when none exist."""
        response = client.get("/api/v1/scripts/approved")

        assert response.status_code == 200
        data = response.json()
        assert data == []


class TestScriptStatistics:
    """Tests for GET /api/v1/scripts/statistics endpoint."""

    def test_script_statistics(self, client, sample_script):
        """Test statistics endpoint returns counts."""
        response = client.get("/api/v1/scripts/statistics")

        assert response.status_code == 200
        data = response.json()
        assert "pending_review" in data
        assert "approved_ready_for_audio" in data
        assert "total" in data


class TestScriptsForDigest:
    """Tests for GET /api/v1/scripts/digest/{id} endpoint."""

    def test_scripts_for_digest_returns_items(self, client, sample_script, sample_digest):
        """Test getting scripts for a digest."""
        response = client.get(f"/api/v1/scripts/digest/{sample_digest.id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["digest_id"] == sample_digest.id

    def test_scripts_for_digest_empty(self, client, sample_digest, db_session):
        """Test getting scripts for digest with no scripts."""
        from datetime import UTC, datetime

        from src.models.digest import Digest, DigestStatus, DigestType

        # Create a new digest with no scripts
        new_digest = Digest(
            digest_type=DigestType.DAILY,
            period_start=datetime(2025, 1, 1, tzinfo=UTC),
            period_end=datetime(2025, 1, 2, tzinfo=UTC),
            title="No Scripts Digest",
            executive_overview="Test",
            strategic_insights=[],
            technical_developments=[],
            emerging_trends=[],
            actionable_recommendations={},
            sources=[],
            newsletter_count=0,
            status=DigestStatus.PENDING_REVIEW,
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        )
        db_session.add(new_digest)
        db_session.commit()
        db_session.refresh(new_digest)

        response = client.get(f"/api/v1/scripts/digest/{new_digest.id}")

        assert response.status_code == 200
        data = response.json()
        assert data == []


class TestGetScriptSection:
    """Tests for GET /api/v1/scripts/{id}/sections/{idx} endpoint."""

    def test_get_script_section_returns_detail(self, client, sample_script):
        """Test getting script section by index."""
        response = client.get(f"/api/v1/scripts/{sample_script.id}/sections/0")

        assert response.status_code == 200
        data = response.json()
        assert "title" in data
        assert "script_title" in data

    def test_get_script_section_not_found_index(self, client, sample_script):
        """Test getting invalid section index returns 404."""
        response = client.get(f"/api/v1/scripts/{sample_script.id}/sections/99")

        assert response.status_code == 404

    def test_get_script_section_script_not_found(self, client):
        """Test getting section for non-existent script returns 404."""
        response = client.get("/api/v1/scripts/99999/sections/0")

        assert response.status_code == 404


class TestGetSectionDialogue:
    """Tests for GET /api/v1/scripts/{id}/sections/{idx}/dialogue endpoint."""

    def test_get_section_dialogue_returns_text(self, client, sample_script):
        """Test getting section dialogue text."""
        response = client.get(f"/api/v1/scripts/{sample_script.id}/sections/0/dialogue")

        assert response.status_code == 200
        data = response.json()
        assert data["section_index"] == 0
        assert "dialogue_text" in data

    def test_get_section_dialogue_invalid_index(self, client, sample_script):
        """Test getting dialogue for invalid index returns 404."""
        response = client.get(f"/api/v1/scripts/{sample_script.id}/sections/99/dialogue")

        assert response.status_code == 404


class TestGenerateScript:
    """Tests for POST /api/v1/scripts/generate endpoint."""

    def test_generate_script_returns_queued(self, client, sample_digest):
        """Test generating script returns queued status."""
        from unittest.mock import AsyncMock, patch

        # Mock the background task so it doesn't actually run
        with patch("src.api.script_routes.generate_script_task", new_callable=AsyncMock):
            response = client.post(
                "/api/v1/scripts/generate",
                json={"digest_id": sample_digest.id, "length": "standard"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert str(sample_digest.id) in data["message"]


class TestSubmitScriptReview:
    """Tests for POST /api/v1/scripts/{id}/review endpoint."""

    def test_submit_review_approve(self, client, sample_script):
        """Test submitting approval review."""
        response = client.post(
            f"/api/v1/scripts/{sample_script.id}/review",
            json={
                "action": "approve",
                "reviewer": "test@example.com",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["script_id"] == sample_script.id
        assert data["status"] == PodcastStatus.SCRIPT_APPROVED.value

    def test_submit_review_reject(self, client, sample_script):
        """Test submitting rejection review."""
        response = client.post(
            f"/api/v1/scripts/{sample_script.id}/review",
            json={
                "action": "reject",
                "reviewer": "test@example.com",
                "general_notes": "Quality issues",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == PodcastStatus.FAILED.value

    def test_submit_review_request_revision(self, client, sample_script, db_session):
        """Test requesting revision."""
        from unittest.mock import AsyncMock, patch

        # Mock the reviser to avoid AI calls
        with patch(
            "src.services.script_review_service.PodcastScriptReviser.apply_multiple_revisions",
            new_callable=AsyncMock,
            return_value=sample_script,
        ):
            response = client.post(
                f"/api/v1/scripts/{sample_script.id}/review",
                json={
                    "action": "request_revision",
                    "reviewer": "test@example.com",
                    "section_feedback": {"0": "Make introduction more engaging"},
                },
            )

        assert response.status_code == 200


class TestReviseScriptSection:
    """Tests for POST /api/v1/scripts/{id}/sections/{idx}/revise endpoint."""

    def test_revise_section_success(self, client, sample_script, db_session):
        """Test revising a section."""
        from unittest.mock import AsyncMock, patch

        # Mock the reviser to avoid AI calls
        with patch.object(
            sample_script.__class__,
            "revision_count",
            1,
            create=True,
        ):
            with patch(
                "src.services.script_review_service.PodcastScriptReviser.apply_revision",
                new_callable=AsyncMock,
                return_value=sample_script,
            ):
                response = client.post(
                    f"/api/v1/scripts/{sample_script.id}/sections/0/revise",
                    json={"feedback": "Make it more conversational"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["script_id"] == sample_script.id
        assert data["section_revised"] == 0


class TestQuickApproveScript:
    """Tests for POST /api/v1/scripts/{id}/approve endpoint."""

    def test_quick_approve_success(self, client, sample_script):
        """Test quick approval updates status."""
        response = client.post(
            f"/api/v1/scripts/{sample_script.id}/approve",
            params={"reviewer": "test@example.com"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["script_id"] == sample_script.id
        assert data["status"] == PodcastStatus.SCRIPT_APPROVED.value
        assert "approved_at" in data

    def test_quick_approve_with_notes(self, client, sample_script):
        """Test quick approval with notes."""
        response = client.post(
            f"/api/v1/scripts/{sample_script.id}/approve",
            params={"reviewer": "test@example.com", "notes": "LGTM"},
        )

        assert response.status_code == 200


class TestQuickRejectScript:
    """Tests for POST /api/v1/scripts/{id}/reject endpoint."""

    def test_quick_reject_success(self, client, sample_script):
        """Test quick rejection updates status."""
        response = client.post(
            f"/api/v1/scripts/{sample_script.id}/reject",
            params={"reviewer": "test@example.com", "reason": "Quality issues"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["script_id"] == sample_script.id
        assert data["status"] == PodcastStatus.FAILED.value
