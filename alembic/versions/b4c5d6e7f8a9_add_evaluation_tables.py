"""Add evaluation and routing tables for LLM Router Evaluation.

Creates tables: routing_configs, evaluation_datasets, evaluation_samples,
evaluation_results, evaluation_consensus, routing_decisions.

Uses VARCHAR columns (not native PG enums) for all status/type fields.
Python StrEnum is the source of truth; DB uses plain strings.

Revision ID: b4c5d6e7f8a9
Revises: f9a8b7c6d5e5
Create Date: 2026-04-02 14:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, None] = "f9a8b7c6d5e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()

    # --- routing_configs ---
    if "routing_configs" not in existing_tables:
        op.create_table(
            "routing_configs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("step", sa.String(50), nullable=False, unique=True),
            sa.Column("mode", sa.String(10), nullable=False, server_default="fixed"),
            sa.Column("strong_model", sa.String(100), nullable=True),
            sa.Column("weak_model", sa.String(100), nullable=True),
            sa.Column("threshold", sa.Float(), server_default="0.5"),
            sa.Column("enabled", sa.Boolean(), server_default="false"),
            sa.Column("classifier_version", sa.String(50), nullable=True),
            sa.Column("calibrated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # --- evaluation_datasets ---
    if "evaluation_datasets" not in existing_tables:
        op.create_table(
            "evaluation_datasets",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("step", sa.String(50), nullable=False),
            sa.Column("name", sa.String(200), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending_evaluation"),
            sa.Column("sample_count", sa.Integer(), nullable=False),
            sa.Column("strong_model", sa.String(100), nullable=False),
            sa.Column("weak_model", sa.String(100), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # --- evaluation_samples ---
    if "evaluation_samples" not in existing_tables:
        op.create_table(
            "evaluation_samples",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "dataset_id",
                sa.Integer(),
                sa.ForeignKey("evaluation_datasets.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("prompt_text", sa.Text(), nullable=False),
            sa.Column("prompt_hash", sa.String(64), nullable=False),
            sa.Column("strong_output", sa.Text(), nullable=True),
            sa.Column("weak_output", sa.Text(), nullable=True),
            sa.Column("strong_tokens", sa.Integer(), nullable=True),
            sa.Column("weak_tokens", sa.Integer(), nullable=True),
            sa.Column("strong_cost", sa.Float(), nullable=True),
            sa.Column("weak_cost", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # --- evaluation_results ---
    if "evaluation_results" not in existing_tables:
        op.create_table(
            "evaluation_results",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "sample_id",
                sa.Integer(),
                sa.ForeignKey("evaluation_samples.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("judge_model", sa.String(100), nullable=False),
            sa.Column("judge_type", sa.String(10), nullable=False),
            sa.Column("preference", sa.String(20), nullable=False),
            sa.Column("critiques", JSONB(), nullable=False),
            sa.Column("reasoning", sa.Text(), nullable=True),
            sa.Column("position_order", sa.String(20), nullable=True),
            sa.Column("weight", sa.Float(), server_default="1.0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # --- evaluation_consensus ---
    if "evaluation_consensus" not in existing_tables:
        op.create_table(
            "evaluation_consensus",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "sample_id",
                sa.Integer(),
                sa.ForeignKey("evaluation_samples.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column("consensus_preference", sa.String(20), nullable=False),
            sa.Column("agreement_rate", sa.Float(), nullable=True),
            sa.Column("dimension_verdicts", JSONB(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # --- routing_decisions ---
    if "routing_decisions" not in existing_tables:
        op.create_table(
            "routing_decisions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("step", sa.String(50), nullable=False),
            sa.Column("prompt_hash", sa.String(64), nullable=False),
            sa.Column("complexity_score", sa.Float(), nullable=False),
            sa.Column("threshold", sa.Float(), nullable=False),
            sa.Column("model_selected", sa.String(100), nullable=False),
            sa.Column("strong_model", sa.String(100), nullable=False),
            sa.Column("weak_model", sa.String(100), nullable=False),
            sa.Column("cost_actual", sa.Float(), nullable=True),
            sa.Column("tokens_input", sa.Integer(), nullable=True),
            sa.Column("tokens_output", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index(
            "idx_routing_decisions_step_created",
            "routing_decisions",
            ["step", "created_at"],
        )


def downgrade() -> None:
    op.drop_table("routing_decisions")
    op.drop_table("evaluation_consensus")
    op.drop_table("evaluation_results")
    op.drop_table("evaluation_samples")
    op.drop_table("evaluation_datasets")
    op.drop_table("routing_configs")
