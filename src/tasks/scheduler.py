"""Scheduler mutation gate backed by the shared ownership authority."""

from sqlalchemy.orm import Session

from src.services.environment_ownership import (
    EnvironmentOwnershipRecord,
    OwnershipIdentity,
    require_mutation_ownership,
)


def require_scheduler_ownership(
    session: Session,
    identity: OwnershipIdentity,
) -> EnvironmentOwnershipRecord:
    """Fail closed unless this scheduler owns the exact current epoch."""

    return require_mutation_ownership(session, identity)
