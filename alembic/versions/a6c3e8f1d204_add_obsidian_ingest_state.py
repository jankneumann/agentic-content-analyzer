"""Add private, recoverable Obsidian ingest state.

Revision ID: a6c3e8f1d204
Revises: 91c7d2e4f8a6
Create Date: 2026-08-02 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "a6c3e8f1d204"
down_revision: str | None = "91c7d2e4f8a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE obsidian_ingest_state (
          id BIGSERIAL PRIMARY KEY,
          configured_source_digest CHAR(64) NOT NULL,
          relative_path_digest CHAR(64) NOT NULL,
          current_file_hash CHAR(64) NOT NULL,
          observed_mtime_ns BIGINT NOT NULL,
          observed_size BIGINT NOT NULL,
          status VARCHAR(16) NOT NULL DEFAULT 'discovered',
          claim_token UUID,
          lease_expires_at TIMESTAMPTZ,
          operation_id BIGINT,
          content_id INTEGER,
          error_code VARCHAR(32),
          attempt_count SMALLINT NOT NULL DEFAULT 0,
          missing_since TIMESTAMPTZ,
          first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT uq_obsidian_ingest_state_source_path
            UNIQUE (configured_source_digest, relative_path_digest),
          CONSTRAINT fk_obsidian_ingest_state_operation
            FOREIGN KEY (operation_id) REFERENCES pgqueuer_jobs(id) ON DELETE SET NULL,
          CONSTRAINT fk_obsidian_ingest_state_content
            FOREIGN KEY (content_id) REFERENCES contents(id) ON DELETE SET NULL,
          CONSTRAINT ck_obsidian_ingest_state_digests CHECK (
            configured_source_digest ~ '^[0-9a-f]{64}$'
            AND relative_path_digest ~ '^[0-9a-f]{64}$'
            AND current_file_hash ~ '^[0-9a-f]{64}$'
          ),
          CONSTRAINT ck_obsidian_ingest_state_status CHECK (
            status IN ('discovered','claimed','ingested','failed','deferred')
          ),
          CONSTRAINT ck_obsidian_ingest_state_error_code CHECK (
            error_code IS NULL OR error_code IN (
              'invalid_encoding','note_too_large','missing_frontmatter',
              'invalid_frontmatter','frontmatter_too_large','frontmatter_not_mapping',
              'yaml_invalid','yaml_custom_tag','yaml_unsupported_type',
              'yaml_duplicate_key','yaml_node_limit','yaml_depth_limit',
              'yaml_alias_limit','yaml_string_limit','missing_required_metadata',
              'invalid_url','invalid_captured_at','invalid_capture_client',
              'invalid_content_type_hint','body_too_large','unsafe_path',
              'directory_unavailable','file_unavailable','normalization_collision',
              'scan_depth_limit','scan_entry_limit','scan_file_limit',
              'non_regular_file','file_unstable','scan_byte_limit','generated_content',
              'scan_duration_limit','source_unavailable','invalid_cursor',
              'persistence_error','file_missing',
              'retry_exhausted','claim_released','claim_lost'
            )
          ),
          CONSTRAINT ck_obsidian_ingest_state_attempt_count CHECK (
            attempt_count BETWEEN 0 AND 10
          ),
          CONSTRAINT ck_obsidian_ingest_state_observation CHECK (
            observed_mtime_ns >= 0 AND observed_size >= 0
          ),
          CONSTRAINT ck_obsidian_ingest_state_shape CHECK (
            (status = 'discovered' AND claim_token IS NULL AND lease_expires_at IS NULL
              AND error_code IS NULL)
            OR (status = 'claimed' AND claim_token IS NOT NULL AND lease_expires_at IS NOT NULL
              AND attempt_count >= 1
              AND error_code IS NULL)
            OR (status = 'ingested' AND claim_token IS NULL AND lease_expires_at IS NULL
              AND error_code IS NULL)
            OR (status = 'failed' AND claim_token IS NULL AND lease_expires_at IS NULL
              AND error_code IS NOT NULL)
            OR (status = 'deferred' AND claim_token IS NULL AND lease_expires_at IS NULL
              AND error_code IS NOT NULL)
          )
        );

        CREATE TABLE obsidian_ingest_events (
          id BIGSERIAL PRIMARY KEY,
          state_id BIGINT NOT NULL,
          configured_source_digest CHAR(64) NOT NULL,
          relative_path_digest CHAR(64) NOT NULL,
          file_hash CHAR(64) NOT NULL,
          status VARCHAR(16) NOT NULL DEFAULT 'discovered',
          claim_token UUID,
          lease_expires_at TIMESTAMPTZ,
          operation_id BIGINT,
          content_id INTEGER,
          error_code VARCHAR(32),
          attempt_count SMALLINT NOT NULL DEFAULT 0,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          completed_at TIMESTAMPTZ,
          CONSTRAINT fk_obsidian_ingest_events_state
            FOREIGN KEY (state_id) REFERENCES obsidian_ingest_state(id) ON DELETE RESTRICT,
          CONSTRAINT fk_obsidian_ingest_events_operation
            FOREIGN KEY (operation_id) REFERENCES pgqueuer_jobs(id) ON DELETE SET NULL,
          CONSTRAINT fk_obsidian_ingest_events_content
            FOREIGN KEY (content_id) REFERENCES contents(id) ON DELETE SET NULL,
          CONSTRAINT uq_obsidian_ingest_events_file_version
            UNIQUE (configured_source_digest, relative_path_digest, file_hash),
          CONSTRAINT ck_obsidian_ingest_events_digests CHECK (
            configured_source_digest ~ '^[0-9a-f]{64}$'
            AND relative_path_digest ~ '^[0-9a-f]{64}$'
            AND file_hash ~ '^[0-9a-f]{64}$'
          ),
          CONSTRAINT ck_obsidian_ingest_events_status CHECK (
            status IN ('discovered','claimed','ingested','failed','deferred')
          ),
          CONSTRAINT ck_obsidian_ingest_events_error_code CHECK (
            error_code IS NULL OR error_code IN (
              'invalid_encoding','note_too_large','missing_frontmatter',
              'invalid_frontmatter','frontmatter_too_large','frontmatter_not_mapping',
              'yaml_invalid','yaml_custom_tag','yaml_unsupported_type',
              'yaml_duplicate_key','yaml_node_limit','yaml_depth_limit',
              'yaml_alias_limit','yaml_string_limit','missing_required_metadata',
              'invalid_url','invalid_captured_at','invalid_capture_client',
              'invalid_content_type_hint','body_too_large','unsafe_path',
              'directory_unavailable','file_unavailable','normalization_collision',
              'scan_depth_limit','scan_entry_limit','scan_file_limit',
              'non_regular_file','file_unstable','scan_byte_limit','generated_content',
              'scan_duration_limit','source_unavailable','invalid_cursor',
              'persistence_error','file_missing',
              'retry_exhausted','claim_released','claim_lost'
            )
          ),
          CONSTRAINT ck_obsidian_ingest_events_attempt_count CHECK (
            attempt_count BETWEEN 0 AND 10
          ),
          CONSTRAINT ck_obsidian_ingest_events_shape CHECK (
            (status = 'discovered' AND claim_token IS NULL AND lease_expires_at IS NULL
              AND operation_id IS NULL AND content_id IS NULL AND error_code IS NULL
              AND completed_at IS NULL)
            OR (status = 'claimed' AND claim_token IS NOT NULL AND lease_expires_at IS NOT NULL
              AND content_id IS NULL AND error_code IS NULL
              AND attempt_count >= 1 AND completed_at IS NULL)
            OR (status = 'ingested' AND claim_token IS NULL AND lease_expires_at IS NULL
              AND error_code IS NULL AND completed_at IS NOT NULL)
            OR (status IN ('failed','deferred') AND claim_token IS NULL
              AND lease_expires_at IS NULL AND error_code IS NOT NULL
              AND completed_at IS NOT NULL)
          )
        );

        CREATE INDEX ix_obsidian_ingest_state_claim_expiry
          ON obsidian_ingest_state (lease_expires_at, id)
          WHERE status = 'claimed';
        CREATE INDEX ix_obsidian_ingest_state_status_updated
          ON obsidian_ingest_state (status, updated_at, id);
        CREATE INDEX ix_obsidian_ingest_events_claim_expiry
          ON obsidian_ingest_events (lease_expires_at, id)
          WHERE status = 'claimed';
        CREATE INDEX ix_obsidian_ingest_events_state_created
          ON obsidian_ingest_events (state_id, created_at, id);

        CREATE FUNCTION deny_obsidian_ingest_event_identity_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF ROW(
            NEW.id, NEW.state_id, NEW.configured_source_digest,
            NEW.relative_path_digest, NEW.file_hash, NEW.created_at
          ) IS DISTINCT FROM ROW(
            OLD.id, OLD.state_id, OLD.configured_source_digest,
            OLD.relative_path_digest, OLD.file_hash, OLD.created_at
          ) THEN
            RAISE EXCEPTION 'obsidian ingest event identity is immutable'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$;
        CREATE TRIGGER obsidian_ingest_events_identity_immutable
        BEFORE UPDATE ON obsidian_ingest_events
        FOR EACH ROW EXECUTE FUNCTION deny_obsidian_ingest_event_identity_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS obsidian_ingest_events_identity_immutable
          ON obsidian_ingest_events;
        DROP FUNCTION IF EXISTS deny_obsidian_ingest_event_identity_mutation();
        DROP TABLE obsidian_ingest_events;
        DROP TABLE obsidian_ingest_state;
        """
    )
