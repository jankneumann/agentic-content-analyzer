"""Shared generated-resource ownership and recovery."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.models.jobs import ResourceReference


async def recover_owned_resource(
    *,
    operations: Any,
    session_factory: Callable[[], AbstractContextManager[Session]],
    model: Any,
    operation_id: str | int,
    resource_type: str,
    resource_url: Callable[[int], str],
) -> Any | None:
    """Load an attached resource or repair its projection from durable ownership."""

    handle = await operations.get(operation_id)
    if handle.resource is not None:
        if handle.resource.type != resource_type:
            raise ValueError("Operation is already attached to another resource type")
        with session_factory() as db:
            record = db.get(model, int(handle.resource.id))
            if record is None:
                raise RuntimeError(f"Attached {resource_type} resource does not exist")
            owner = record.operation_id
            if owner is None:
                claim = db.execute(
                    update(model)
                    .where(model.id == record.id, model.operation_id.is_(None))
                    .values(operation_id=int(operation_id))
                )
                db.commit()
                db.refresh(record)
                if claim.rowcount != 1 and record.operation_id is None:  # type: ignore[attr-defined]
                    raise RuntimeError(f"Could not claim attached {resource_type} resource")
                owner = record.operation_id
            if int(owner) != int(operation_id):
                raise ValueError(f"Attached {resource_type} resource belongs to operation {owner}")
            return record

    with session_factory() as db:
        record = db.execute(
            select(model).where(model.operation_id == int(operation_id))
        ).scalar_one_or_none()
        if record is None:
            return None
        record_id = int(record.id)

    await operations.attach_resource(
        operation_id,
        ResourceReference(
            type=resource_type,
            id=str(record_id),
            url=resource_url(record_id),
        ),
    )
    return record
