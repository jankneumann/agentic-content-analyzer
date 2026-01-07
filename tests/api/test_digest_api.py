"""Tests for digest API endpoints."""


class TestListDigests:
    """Tests for GET /api/v1/digests/ endpoint."""

    def test_list_digests_empty(self, client):
        """Test listing digests when database is empty."""
        response = client.get("/api/v1/digests/")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_list_digests_returns_items(self, client, sample_digests):
        """Test listing digests returns all items."""
        response = client.get("/api/v1/digests/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_digests_pagination_limit(self, client, sample_digests):
        """Test pagination with limit parameter."""
        response = client.get("/api/v1/digests/?limit=1")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_list_digests_pagination_offset(self, client, sample_digests):
        """Test pagination with offset parameter."""
        response = client.get("/api/v1/digests/?limit=1&offset=1")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_list_digests_filter_by_status(self, client, sample_digests):
        """Test filtering digests by status."""
        response = client.get("/api/v1/digests/?status=APPROVED")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "APPROVED"

    def test_list_digests_filter_by_type(self, client, sample_digests):
        """Test filtering digests by type."""
        response = client.get("/api/v1/digests/?digest_type=daily")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["digest_type"] == "daily"


class TestGetDigest:
    """Tests for GET /api/v1/digests/{id} endpoint."""

    def test_get_digest_returns_detail(self, client, sample_digest):
        """Test getting digest by ID returns full detail."""
        response = client.get(f"/api/v1/digests/{sample_digest.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_digest.id
        assert data["title"] == sample_digest.title
        assert data["digest_type"] == "daily"
        assert "executive_overview" in data
        assert "strategic_insights" in data
        assert "technical_developments" in data
        assert "emerging_trends" in data
        assert "actionable_recommendations" in data

    def test_get_digest_not_found(self, client):
        """Test getting non-existent digest returns 404."""
        response = client.get("/api/v1/digests/99999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestDigestStatistics:
    """Tests for GET /api/v1/digests/statistics endpoint."""

    def test_digest_statistics_empty(self, client):
        """Test statistics endpoint with empty database."""
        response = client.get("/api/v1/digests/statistics")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["pending"] == 0
        assert data["approved"] == 0

    def test_digest_statistics_with_data(self, client, sample_digests):
        """Test statistics endpoint with digests in database."""
        response = client.get("/api/v1/digests/statistics")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert "by_type" in data
        assert data["pending_review"] == 1  # One pending_review
        assert data["approved"] == 1  # One approved


class TestGenerateDigest:
    """Tests for POST /api/v1/digests/generate endpoint."""

    def test_generate_digest_daily(self, client):
        """Test generating daily digest returns queued status."""
        response = client.post(
            "/api/v1/digests/generate",
            json={"digest_type": "daily"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert "daily" in data["message"].lower()

    def test_generate_digest_weekly(self, client):
        """Test generating weekly digest returns queued status."""
        response = client.post(
            "/api/v1/digests/generate",
            json={"digest_type": "weekly"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert "weekly" in data["message"].lower()

    def test_generate_digest_invalid_type(self, client):
        """Test generating with invalid type returns 400."""
        response = client.post(
            "/api/v1/digests/generate",
            json={"digest_type": "invalid"},
        )

        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()


class TestSubmitReview:
    """Tests for POST /api/v1/digests/{id}/review endpoint."""

    def test_submit_review_approve(self, client, sample_digest):
        """Test submitting approval review."""
        response = client.post(
            f"/api/v1/digests/{sample_digest.id}/review",
            json={
                "action": "approve",
                "reviewer": "test@example.com",
                "notes": "Looks good!",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["digest_id"] == sample_digest.id
        assert data["status"] == "APPROVED"
        assert data["reviewed_by"] == "test@example.com"

    def test_submit_review_reject(self, client, sample_digest):
        """Test submitting rejection review."""
        response = client.post(
            f"/api/v1/digests/{sample_digest.id}/review",
            json={
                "action": "reject",
                "reviewer": "test@example.com",
                "notes": "Needs improvement",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "REJECTED"

    def test_submit_review_request_revision(self, client, sample_digest):
        """Test requesting revision."""
        response = client.post(
            f"/api/v1/digests/{sample_digest.id}/review",
            json={
                "action": "request_revision",
                "reviewer": "test@example.com",
                "section_feedback": {"strategic_insights": "Add more context"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "PENDING_REVIEW"

    def test_submit_review_invalid_action(self, client, sample_digest):
        """Test submitting invalid review action returns 400."""
        response = client.post(
            f"/api/v1/digests/{sample_digest.id}/review",
            json={
                "action": "invalid_action",
                "reviewer": "test@example.com",
            },
        )

        assert response.status_code == 400

    def test_submit_review_not_found(self, client):
        """Test submitting review for non-existent digest returns 404."""
        response = client.post(
            "/api/v1/digests/99999/review",
            json={
                "action": "approve",
                "reviewer": "test@example.com",
            },
        )

        assert response.status_code == 404


class TestQuickApprove:
    """Tests for POST /api/v1/digests/{id}/approve endpoint."""

    def test_quick_approve_success(self, client, sample_digest):
        """Test quick approval updates status."""
        response = client.post(
            f"/api/v1/digests/{sample_digest.id}/approve",
            params={"reviewer": "test@example.com"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["digest_id"] == sample_digest.id
        assert data["status"] == "APPROVED"
        assert "approved_at" in data

    def test_quick_approve_with_notes(self, client, sample_digest):
        """Test quick approval with notes."""
        response = client.post(
            f"/api/v1/digests/{sample_digest.id}/approve",
            params={"reviewer": "test@example.com", "notes": "LGTM"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "APPROVED"

    def test_quick_approve_not_found(self, client):
        """Test quick approval for non-existent digest returns 404."""
        response = client.post(
            "/api/v1/digests/99999/approve",
            params={"reviewer": "test@example.com"},
        )

        assert response.status_code == 404


class TestQuickReject:
    """Tests for POST /api/v1/digests/{id}/reject endpoint."""

    def test_quick_reject_success(self, client, sample_digest):
        """Test quick rejection updates status."""
        response = client.post(
            f"/api/v1/digests/{sample_digest.id}/reject",
            params={"reviewer": "test@example.com", "reason": "Quality issues"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["digest_id"] == sample_digest.id
        assert data["status"] == "REJECTED"

    def test_quick_reject_not_found(self, client):
        """Test quick rejection for non-existent digest returns 404."""
        response = client.post(
            "/api/v1/digests/99999/reject",
            params={"reviewer": "test@example.com", "reason": "Bad"},
        )

        assert response.status_code == 404


class TestGetDigestSection:
    """Tests for GET /api/v1/digests/{id}/sections/{type} endpoint."""

    def test_get_strategic_insights_section(self, client, sample_digest):
        """Test getting strategic insights section."""
        response = client.get(f"/api/v1/digests/{sample_digest.id}/sections/strategic_insights")

        assert response.status_code == 200
        data = response.json()
        assert data["digest_id"] == sample_digest.id
        assert data["section_type"] == "strategic_insights"
        assert "sections" in data
        assert "count" in data

    def test_get_technical_developments_section(self, client, sample_digest):
        """Test getting technical developments section."""
        response = client.get(f"/api/v1/digests/{sample_digest.id}/sections/technical_developments")

        assert response.status_code == 200
        data = response.json()
        assert data["section_type"] == "technical_developments"

    def test_get_emerging_trends_section(self, client, sample_digest):
        """Test getting emerging trends section."""
        response = client.get(f"/api/v1/digests/{sample_digest.id}/sections/emerging_trends")

        assert response.status_code == 200
        data = response.json()
        assert data["section_type"] == "emerging_trends"

    def test_get_invalid_section_type(self, client, sample_digest):
        """Test getting invalid section type returns 400."""
        response = client.get(f"/api/v1/digests/{sample_digest.id}/sections/invalid_section")

        assert response.status_code == 400
        assert "invalid section type" in response.json()["detail"].lower()

    def test_get_section_digest_not_found(self, client):
        """Test getting section for non-existent digest returns 404."""
        response = client.get("/api/v1/digests/99999/sections/strategic_insights")

        assert response.status_code == 404


class TestReviseSection:
    """Tests for POST /api/v1/digests/{id}/sections/{type}/{idx}/revise endpoint."""

    def test_revise_section_success(self, client, sample_digest):
        """Test revising a section queues revision."""
        response = client.post(
            f"/api/v1/digests/{sample_digest.id}/sections/strategic_insights/0/revise",
            json={"feedback": "Add more detail about cost implications"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["digest_id"] == sample_digest.id
        assert data["section_type"] == "strategic_insights"
        assert data["section_index"] == 0
        assert data["status"] == "revision_queued"

    def test_revise_section_invalid_type(self, client, sample_digest):
        """Test revising invalid section type returns 400."""
        response = client.post(
            f"/api/v1/digests/{sample_digest.id}/sections/invalid_section/0/revise",
            json={"feedback": "Test"},
        )

        assert response.status_code == 400

    def test_revise_section_invalid_index(self, client, sample_digest):
        """Test revising invalid section index returns 404."""
        response = client.post(
            f"/api/v1/digests/{sample_digest.id}/sections/strategic_insights/99/revise",
            json={"feedback": "Test"},
        )

        assert response.status_code == 404

    def test_revise_section_digest_not_found(self, client):
        """Test revising section for non-existent digest returns 404."""
        response = client.post(
            "/api/v1/digests/99999/sections/strategic_insights/0/revise",
            json={"feedback": "Test"},
        )

        assert response.status_code == 404
