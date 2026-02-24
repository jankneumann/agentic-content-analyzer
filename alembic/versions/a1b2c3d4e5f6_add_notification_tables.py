"""Add notification_events and device_registrations tables.

Revision ID: a1b2c3d4e5f6
Revises: 33072a43b224
Create Date: 2026-02-23
"""

from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "33072a43b224"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    # Check if tables already exist (idempotent)
    conn = op.get_bind()

    exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'notification_events'"
        )
    ).scalar()

    if not exists:
        op.create_table(
            "notification_events",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("event_type", sa.String(50), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column(
                "payload",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "read",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_notification_events_event_type",
            "notification_events",
            ["event_type"],
        )
        op.create_index(
            "ix_notification_events_created_at",
            "notification_events",
            ["created_at"],
        )
        op.create_index(
            "ix_notification_events_read",
            "notification_events",
            ["read"],
            postgresql_where=sa.text("read = false"),
        )

    exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'device_registrations'"
        )
    ).scalar()

    if not exists:
        op.create_table(
            "device_registrations",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("platform", sa.String(50), nullable=False),
            sa.Column("token", sa.String(500), nullable=False),
            sa.Column(
                "delivery_method",
                sa.String(50),
                nullable=False,
                server_default=sa.text("'sse'"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.Column(
                "last_seen",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token", name="uq_device_registrations_token"),
        )


def downgrade() -> None:
    op.drop_table("device_registrations")
    op.drop_table("notification_events")
