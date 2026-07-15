from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.models.digest import Digest
from src.models.jobs import ResourceReference
from src.workflows.resource import recover_owned_resource


@pytest.mark.asyncio
async def test_recover_owned_resource_repairs_missing_operation_projection(
    db_session, digest
) -> None:
    digest.operation_id = 17
    db_session.flush()
    operations = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(resource=None)),
        attach_resource=AsyncMock(),
    )

    @contextmanager
    def sessions():
        yield db_session

    recovered = await recover_owned_resource(
        operations=operations,
        session_factory=sessions,
        model=Digest,
        operation_id="17",
        resource_type="digest",
        resource_url=lambda record_id: f"/api/v1/digests/{record_id}",
    )

    assert recovered is digest
    operations.attach_resource.assert_awaited_once_with(
        "17",
        ResourceReference(type="digest", id=str(digest.id), url=f"/api/v1/digests/{digest.id}"),
    )


@pytest.mark.asyncio
async def test_recover_owned_resource_rejects_wrong_attached_type(db_session) -> None:
    operations = SimpleNamespace(
        get=AsyncMock(
            return_value=SimpleNamespace(
                resource=ResourceReference(type="podcast", id="1", url="/api/v1/podcasts/1")
            )
        )
    )

    @contextmanager
    def sessions():
        yield db_session

    with pytest.raises(ValueError, match="another resource type"):
        await recover_owned_resource(
            operations=operations,
            session_factory=sessions,
            model=Digest,
            operation_id=17,
            resource_type="digest",
            resource_url=lambda record_id: f"/api/v1/digests/{record_id}",
        )


@pytest.mark.asyncio
async def test_recover_owned_resource_claims_legacy_owner_and_rejects_conflict(
    db_session, digest
) -> None:
    reference = ResourceReference(
        type="digest", id=str(digest.id), url=f"/api/v1/digests/{digest.id}"
    )
    operations = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(resource=reference)))

    @contextmanager
    def sessions():
        yield db_session

    recovered = await recover_owned_resource(
        operations=operations,
        session_factory=sessions,
        model=Digest,
        operation_id=17,
        resource_type="digest",
        resource_url=lambda record_id: f"/api/v1/digests/{record_id}",
    )
    assert recovered.operation_id == 17

    digest.operation_id = 18
    db_session.flush()
    with pytest.raises(ValueError, match="belongs to operation 18"):
        await recover_owned_resource(
            operations=operations,
            session_factory=sessions,
            model=Digest,
            operation_id=17,
            resource_type="digest",
            resource_url=lambda record_id: f"/api/v1/digests/{record_id}",
        )
