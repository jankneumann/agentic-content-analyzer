"""Typed, value-free failures for credential-gated ingestion sources.

A source that authenticates with a browser session (Substack ``substack.sid``,
X ``auth_token``/``ct0``) must fail closed when the session is unusable: the
run persists nothing and reports a stable machine code instead of silently
ingesting a thinner, logged-out corpus.

The codes below are part of the closed public diagnostic vocabulary
(:data:`src.ingestion.result_sanitizer.SAFE_INGESTION_DIAGNOSTIC_CODES`) and
double as ``ConfiguredSourceReadiness.code`` values, so the readiness listing
and the durable operation result use one word for one condition.

Exceptions here carry the credential LABEL (``substack.sid``), the source key,
and the refresh command. They never carry, format, or chain a credential value.
"""

from __future__ import annotations

from typing import ClassVar, Final

from src.ingestion.result import IngestionError

CREDENTIALS_MISSING: Final = "credentials_missing"
"""The source's credential is not configured anywhere the provider looks."""

SESSION_EXPIRED: Final = "session_expired"
"""The remote site rejected the session even after one refresh from OpenBao."""


class CredentialFailureError(Exception):
    """A credential-gated source cannot run with its current credential.

    Subclasses set :attr:`code`. The message names the source, the credential
    label, and the refresh command; never the value.
    """

    code: ClassVar[str]
    summary: ClassVar[str]

    def __init__(
        self,
        *,
        source: str,
        credential_label: str,
        refresh_command: str | None = None,
    ) -> None:
        self.source = source
        self.credential_label = credential_label
        self.refresh_command = refresh_command
        super().__init__(self._describe())

    def _describe(self) -> str:
        message = f"{self.source} {self.credential_label} {self.summary}"
        if self.refresh_command:
            message += f"; refresh it with: {self.refresh_command}"
        return message

    def to_ingestion_error(self) -> IngestionError:
        """Envelope diagnostic for a run that failed closed on this condition."""
        return IngestionError(code=self.code, message=str(self))


class CredentialsMissingError(CredentialFailureError):
    """The source's credential is not configured anywhere the provider looks."""

    code = CREDENTIALS_MISSING
    summary = "is not configured"


class SessionExpiredError(CredentialFailureError):
    """The remote site answered an authenticated request as logged out."""

    code = SESSION_EXPIRED
    summary = "session was rejected by the remote site"
