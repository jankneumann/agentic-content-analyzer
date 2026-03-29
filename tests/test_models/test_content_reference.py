"""Tests for the ContentReference model.

Tests cover:
- ReferenceType, ExternalIdType, ResolutionStatus enum values
- ContentReference SQLAlchemy model creation
- CHECK constraint (must have external_id or external_url)
- Unique constraint on (source_content_id, external_id, external_id_type)
- Enum validation via @validates decorators
- Relationships (source_content, target_content, source_chunk)
- Pydantic schemas (ReferenceResponse, ReferenceListResponse)
"""

from datetime import UTC, datetime

import pytest

from src.models.content import Content
from src.models.content_reference import (
    ContentReference,
    ExternalIdType,
    ReferenceListResponse,
    ReferenceResponse,
    ReferenceType,
    ResolutionStatus,
)


class TestReferenceTypeEnum:
    """Tests for ReferenceType enum."""

    def test_all_values_defined(self):
        """Verify all expected reference types exist."""
        expected = {"cites", "extends", "discusses", "contradicts", "supplements"}
        actual = {rt.value for rt in ReferenceType}
        assert actual == expected

    def test_is_string_enum(self):
        """Test that ReferenceType is a string enum."""
        assert isinstance(ReferenceType.CITES, str)
        assert ReferenceType.CITES == "cites"

    def test_string_values(self):
        """Test individual enum values."""
        assert ReferenceType.CITES.value == "cites"
        assert ReferenceType.EXTENDS.value == "extends"
        assert ReferenceType.DISCUSSES.value == "discusses"
        assert ReferenceType.CONTRADICTS.value == "contradicts"
        assert ReferenceType.SUPPLEMENTS.value == "supplements"


class TestExternalIdTypeEnum:
    """Tests for ExternalIdType enum."""

    def test_all_values_defined(self):
        """Verify all expected external ID types exist."""
        expected = {"arxiv", "doi", "s2", "pmid", "url"}
        actual = {eid.value for eid in ExternalIdType}
        assert actual == expected

    def test_is_string_enum(self):
        """Test that ExternalIdType is a string enum."""
        assert isinstance(ExternalIdType.DOI, str)
        assert ExternalIdType.DOI == "doi"


class TestResolutionStatusEnum:
    """Tests for ResolutionStatus enum."""

    def test_all_values_defined(self):
        """Verify all expected resolution statuses exist."""
        expected = {"unresolved", "resolved", "external", "failed", "not_found"}
        actual = {rs.value for rs in ResolutionStatus}
        assert actual == expected

    def test_is_string_enum(self):
        """Test that ResolutionStatus is a string enum."""
        assert isinstance(ResolutionStatus.UNRESOLVED, str)
        assert ResolutionStatus.UNRESOLVED == "unresolved"


class TestContentReferenceModel:
    """Tests for ContentReference SQLAlchemy model."""

    def test_creation_with_external_id(self):
        """Test creating a ContentReference with an external ID."""
        ref = ContentReference(
            source_content_id=1,
            reference_type="cites",
            external_id="2301.07041",
            external_id_type="arxiv",
            resolution_status="unresolved",
            confidence=0.95,
        )

        assert ref.source_content_id == 1
        assert ref.reference_type == "cites"
        assert ref.external_id == "2301.07041"
        assert ref.external_id_type == "arxiv"
        assert ref.resolution_status == "unresolved"
        assert ref.confidence == 0.95
        assert ref.target_content_id is None
        assert ref.external_url is None

    def test_creation_with_external_url(self):
        """Test creating a ContentReference with an external URL."""
        ref = ContentReference(
            source_content_id=1,
            reference_type="discusses",
            external_url="https://example.com/paper",
            resolution_status="external",
        )

        assert ref.external_url == "https://example.com/paper"
        assert ref.external_id is None
        assert ref.resolution_status == "external"

    def test_creation_with_target_content(self):
        """Test creating a ContentReference with a resolved target."""
        resolved_time = datetime(2026, 3, 28, 12, 0, 0, tzinfo=UTC)
        ref = ContentReference(
            source_content_id=1,
            reference_type="extends",
            target_content_id=42,
            external_id="10.1234/example",
            external_id_type="doi",
            resolution_status="resolved",
            resolved_at=resolved_time,
            context_snippet="As shown by Smith et al. [42]...",
            confidence=0.88,
        )

        assert ref.target_content_id == 42
        assert ref.resolution_status == "resolved"
        assert ref.resolved_at == resolved_time
        assert ref.context_snippet == "As shown by Smith et al. [42]..."

    def test_creation_with_chunk_id(self):
        """Test creating a ContentReference with a source chunk."""
        ref = ContentReference(
            source_content_id=1,
            reference_type="cites",
            external_id="S2:12345",
            external_id_type="s2",
            source_chunk_id=99,
            resolution_status="unresolved",
        )

        assert ref.source_chunk_id == 99

    def test_tablename(self):
        """Test that ContentReference uses correct table name."""
        assert ContentReference.__tablename__ == "content_references"

    def test_repr(self):
        """Test ContentReference string representation."""
        ref = ContentReference(
            source_content_id=10,
            reference_type="cites",
            external_id="2301.07041",
            external_id_type="arxiv",
            resolution_status="unresolved",
        )
        ref.id = 5

        repr_str = repr(ref)
        assert "ContentReference" in repr_str
        assert "id=5" in repr_str
        assert "source=10" in repr_str
        assert "type=cites" in repr_str
        assert "status=unresolved" in repr_str


class TestContentReferenceValidation:
    """Tests for @validates decorators on ContentReference."""

    def test_valid_reference_type(self):
        """Test that valid reference types are accepted."""
        for rt in ReferenceType:
            ref = ContentReference(
                source_content_id=1,
                reference_type=rt.value,
                external_url="https://example.com",
                resolution_status="unresolved",
            )
            assert ref.reference_type == rt.value

    def test_invalid_reference_type(self):
        """Test that invalid reference_type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid reference_type"):
            ContentReference(
                source_content_id=1,
                reference_type="invalid_type",
                external_url="https://example.com",
                resolution_status="unresolved",
            )

    def test_valid_external_id_type(self):
        """Test that valid external ID types are accepted."""
        for eid in ExternalIdType:
            ref = ContentReference(
                source_content_id=1,
                reference_type="cites",
                external_id="test-id",
                external_id_type=eid.value,
                resolution_status="unresolved",
            )
            assert ref.external_id_type == eid.value

    def test_invalid_external_id_type(self):
        """Test that invalid external_id_type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid external_id_type"):
            ContentReference(
                source_content_id=1,
                reference_type="cites",
                external_id="test-id",
                external_id_type="invalid_type",
                resolution_status="unresolved",
            )

    def test_none_external_id_type_allowed(self):
        """Test that None is accepted for external_id_type."""
        ref = ContentReference(
            source_content_id=1,
            reference_type="cites",
            external_url="https://example.com",
            external_id_type=None,
            resolution_status="unresolved",
        )
        assert ref.external_id_type is None

    def test_valid_resolution_status(self):
        """Test that valid resolution statuses are accepted."""
        for rs in ResolutionStatus:
            ref = ContentReference(
                source_content_id=1,
                reference_type="cites",
                external_url="https://example.com",
                resolution_status=rs.value,
            )
            assert ref.resolution_status == rs.value

    def test_invalid_resolution_status(self):
        """Test that invalid resolution_status raises ValueError."""
        with pytest.raises(ValueError, match="Invalid resolution_status"):
            ContentReference(
                source_content_id=1,
                reference_type="cites",
                external_url="https://example.com",
                resolution_status="bogus",
            )


class TestContentReferenceRelationships:
    """Tests for ContentReference model relationships."""

    def test_has_source_content_relationship(self):
        """Test ContentReference has source_content relationship attribute."""
        assert hasattr(ContentReference, "source_content")

    def test_has_target_content_relationship(self):
        """Test ContentReference has target_content relationship attribute."""
        assert hasattr(ContentReference, "target_content")

    def test_has_source_chunk_relationship(self):
        """Test ContentReference has source_chunk relationship attribute."""
        assert hasattr(ContentReference, "source_chunk")

    def test_content_has_references_relationship(self):
        """Test Content model has references relationship attribute."""
        assert hasattr(Content, "references")

    def test_content_has_cited_by_relationship(self):
        """Test Content model has cited_by relationship attribute."""
        assert hasattr(Content, "cited_by")

    def test_source_content_back_populates(self):
        """Test ContentReference.source_content back_populates Content.references."""
        assert ContentReference.source_content.property.back_populates == "references"

    def test_target_content_back_populates(self):
        """Test ContentReference.target_content back_populates Content.cited_by."""
        assert ContentReference.target_content.property.back_populates == "cited_by"


class TestContentReferenceConstraints:
    """Tests for table constraints (CHECK, UNIQUE).

    Note: CHECK and UNIQUE constraints are enforced at the database level,
    not in-memory. These tests verify the constraint definitions exist
    on the model's __table_args__.
    """

    def test_check_constraint_defined(self):
        """Test that the CHECK constraint for identifier presence is defined."""
        table_args = ContentReference.__table_args__
        check_constraints = [
            arg for arg in table_args if hasattr(arg, "name") and arg.name == "chk_has_identifier"
        ]
        assert len(check_constraints) == 1

    def test_unique_constraint_defined(self):
        """Test that the unique constraint on (source, external_id, type) is defined."""
        table_args = ContentReference.__table_args__
        unique_constraints = [
            arg for arg in table_args if hasattr(arg, "name") and arg.name == "uq_content_reference"
        ]
        assert len(unique_constraints) == 1

    def test_indexes_defined(self):
        """Test that all expected indexes are defined."""
        table_args = ContentReference.__table_args__
        index_names = {
            arg.name
            for arg in table_args
            if isinstance(arg, type(None)) is False and hasattr(arg, "name")
        }
        expected_indexes = {
            "ix_content_refs_source",
            "ix_content_refs_target",
            "ix_content_refs_external_id",
            "ix_content_refs_unresolved",
        }
        assert expected_indexes.issubset(index_names)


class TestReferenceResponseSchema:
    """Tests for ReferenceResponse Pydantic schema."""

    def test_response_from_data(self):
        """Test creating ReferenceResponse with typical data."""
        created = datetime(2026, 3, 28, 12, 0, 0, tzinfo=UTC)
        response = ReferenceResponse(
            id=1,
            source_content_id=10,
            reference_type="cites",
            target_content_id=20,
            external_id="2301.07041",
            external_id_type="arxiv",
            resolution_status="resolved",
            resolved_at=created,
            confidence=0.95,
            created_at=created,
        )

        assert response.id == 1
        assert response.source_content_id == 10
        assert response.reference_type == "cites"
        assert response.target_content_id == 20
        assert response.external_id == "2301.07041"
        assert response.confidence == 0.95

    def test_response_minimal(self):
        """Test ReferenceResponse with only required fields."""
        created = datetime(2026, 3, 28, 12, 0, 0, tzinfo=UTC)
        response = ReferenceResponse(
            id=1,
            source_content_id=10,
            reference_type="discusses",
            resolution_status="external",
            external_url="https://example.com",
            created_at=created,
        )

        assert response.target_content_id is None
        assert response.external_id is None
        assert response.external_id_type is None
        assert response.source_chunk_id is None
        assert response.context_snippet is None


class TestReferenceListResponseSchema:
    """Tests for ReferenceListResponse Pydantic schema."""

    def test_list_response(self):
        """Test paginated reference list response."""
        created = datetime(2026, 3, 28, 12, 0, 0, tzinfo=UTC)
        items = [
            ReferenceResponse(
                id=i,
                source_content_id=10,
                reference_type="cites",
                external_id=f"10.1234/test{i}",
                external_id_type="doi",
                resolution_status="unresolved",
                created_at=created,
            )
            for i in range(1, 4)
        ]

        response = ReferenceListResponse(
            items=items,
            total=25,
            page=1,
            page_size=3,
        )

        assert len(response.items) == 3
        assert response.total == 25
        assert response.page == 1
        assert response.page_size == 3

    def test_empty_list_response(self):
        """Test empty reference list response."""
        response = ReferenceListResponse(
            items=[],
            total=0,
        )

        assert len(response.items) == 0
        assert response.total == 0
        assert response.page == 1
        assert response.page_size == 20
