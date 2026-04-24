"""Task 1.13: retrofit @audited on existing destructive endpoints.

The proposal (`openspec/changes/cloud-db-source-of-truth/proposal.md §4`) named
three existing destructive endpoints that should receive `@audited` operation
tags so the audit log can be filtered by operation:

- ``DELETE /api/v1/kb/topics/{slug}`` → ``operation="topics.delete"`` (EXISTS; retrofitted here)
- ``POST /api/v1/kb/purge`` → intended ``operation="kb.purge"`` (**does not exist as an HTTP route**;
  kb/purge appears only as a docstring example in src/api/middleware/audit.py)
- ``POST /api/v1/manage/switch-embeddings`` → intended ``operation="manage.switch_embeddings"``
  (**does not exist as an HTTP route**; only a CLI subcommand at
  src/cli/manage_commands.py:337 ``aca manage switch-embeddings``)

Those two phantom endpoints were plan-level assumptions that turned out to be
incorrect at implementation time. Rather than inventing new HTTP endpoints out
of scope for this proposal, we test only the endpoint that actually exists.
"""

from __future__ import annotations

from src.api.kb_routes import archive_topic


def test_archive_topic_has_topics_delete_audit_operation() -> None:
    """DELETE /api/v1/kb/topics/{slug} must be tagged with operation='topics.delete'.

    The @audited decorator stores the operation name on the handler's
    ``__audit_operation__`` attribute; AuditMiddleware reads it when the
    request completes and writes it to the audit_log row.
    """
    assert getattr(archive_topic, "__audit_operation__", None) == "topics.delete"
