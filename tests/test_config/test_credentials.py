"""Tests for the live credential provider (src/config/credentials.py).

The OpenBao side runs through the REAL ``src.config.bao_secrets`` module with a
fake hvac client, so the cache swaps exercised here are the ones a worker sees.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import src.config.bao_secrets as bao_mod
from src.config.credentials import (
    BROWSER_SESSION_CREDENTIALS,
    SUBSTACK_SESSION_COOKIE,
    X_AUTH_TOKEN,
    X_CT0,
    CredentialProvider,
    UnknownCredentialError,
    get_credential_provider,
    reset_credential_provider,
)
from src.config.secrets import is_secret_key

BOOT_COOKIE = "substack-boot-cookie-value-111"
ROTATED_COOKIE = "substack-rotated-cookie-value-222"
SETTINGS_COOKIE = "substack-settings-cookie-value-333"
CT0_OLD = "ct0-old-value-444"
CT0_NEW = "ct0-new-value-555"
AUTH_TOKEN = "auth-token-value-666"
ALL_VALUES = (BOOT_COOKIE, ROTATED_COOKIE, SETTINGS_COOKIE, CT0_OLD, CT0_NEW, AUTH_TOKEN)


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def blob(self) -> str:
        parts = []
        for record in self.records:
            parts.append(record.getMessage())
            parts.append(repr(record.args))
            if record.exc_info:
                parts.append(logging.Formatter().formatException(record.exc_info))
        return "\n".join(parts)


@pytest.fixture(autouse=True)
def _isolate() -> Iterator[None]:
    bao_mod.clear_bao_cache()
    reset_credential_provider()
    yield
    bao_mod.clear_bao_cache()
    reset_credential_provider()


@pytest.fixture
def log_capture() -> Iterator[_ListHandler]:
    """Capture every record from ``src`` loggers at DEBUG.

    A handler on the logger itself, not caplog: see test_bao_secrets.py for why
    caplog is unreliable under the OpenTelemetry logging instrumentation.
    """
    handler = _ListHandler()
    root = logging.getLogger("src")
    previous = root.level
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)
    yield handler
    root.removeHandler(handler)
    root.setLevel(previous)
    blob = handler.blob()
    for value in ALL_VALUES:
        assert value not in blob, "a credential value reached the logs"


class FakeBao:
    """A fake hvac module + client whose KV v2 data can be changed mid-test."""

    def __init__(self, data: dict[str, Any], *, approle_ttl: int | None = None) -> None:
        self.data = dict(data)
        self.reads = 0
        self.logins = 0
        self.fail_next_reads = 0
        self.client = MagicMock()
        self.client.is_authenticated.return_value = True
        self.client.secrets.kv.v2.read_secret_version.side_effect = self._read
        self.client.auth.approle.login.side_effect = self._login
        self._ttl = approle_ttl
        self.hvac = MagicMock()
        self.hvac.Client.return_value = self.client

    def _read(self, **_kwargs: Any) -> dict[str, Any]:
        self.reads += 1
        if self.fail_next_reads:
            self.fail_next_reads -= 1
            raise RuntimeError("permission denied")
        return {"data": {"data": dict(self.data)}}

    def _login(self, **_kwargs: Any) -> dict[str, Any]:
        self.logins += 1
        return {"auth": {"lease_duration": self._ttl}}


def _settings(**values: Any) -> SimpleNamespace:
    fields = {spec.settings_field: None for spec in BROWSER_SESSION_CREDENTIALS.values()}
    fields.update(values)
    return SimpleNamespace(**fields)


@pytest.fixture
def token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAO_ADDR", "http://bao.test:8200")
    monkeypatch.setenv("BAO_TOKEN", "fake-root-token")
    monkeypatch.delenv("BAO_ROLE_ID", raising=False)
    monkeypatch.delenv("BAO_SECRET_ID", raising=False)


@pytest.fixture
def approle_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAO_ADDR", "http://bao.test:8200")
    monkeypatch.setenv("BAO_ROLE_ID", "newsletter-worker")
    monkeypatch.setenv("BAO_SECRET_ID", "fake-secret-id")
    monkeypatch.delenv("BAO_TOKEN", raising=False)


class TestRegistry:
    def test_explicit_env_to_settings_mapping(self) -> None:
        mapping = {n: (s.settings_field, s.label) for n, s in BROWSER_SESSION_CREDENTIALS.items()}
        assert mapping == {
            "SUBSTACK_SESSION_COOKIE": ("substack_session_cookie", "substack.sid"),
            "X_AUTH_TOKEN": ("x_auth_token", "x.auth_token"),
            "X_CT0": ("x_ct0", "x.ct0"),
        }

    def test_settings_declares_every_mapped_field_without_repr(self) -> None:
        from src.config.settings import Settings

        for spec in BROWSER_SESSION_CREDENTIALS.values():
            field = Settings.model_fields[spec.settings_field]
            assert field.repr is False, spec.settings_field

    def test_settings_repr_hides_values(self) -> None:
        from src.config.settings import Settings

        s = Settings(
            _env_file=None,
            substack_session_cookie=BOOT_COOKIE,
            x_auth_token=AUTH_TOKEN,
            x_ct0=CT0_OLD,
        )
        assert s.x_ct0 == CT0_OLD
        for value in (BOOT_COOKIE, AUTH_TOKEN, CT0_OLD):
            assert value not in repr(s)

    def test_profile_wires_the_new_fields(self) -> None:
        from pathlib import Path

        import yaml

        base_yaml = Path(__file__).resolve().parents[2] / "profiles" / "base.yaml"
        base = yaml.safe_load(base_yaml.read_text())
        api_keys = base["settings"]["api_keys"]
        assert api_keys["x_auth_token"] == "${X_AUTH_TOKEN:-}"  # noqa: RUF027
        assert api_keys["x_ct0"] == "${X_CT0:-}"  # noqa: RUF027

    def test_browser_session_names_are_masked(self) -> None:
        for name in BROWSER_SESSION_CREDENTIALS:
            assert is_secret_key(name)
            assert is_secret_key(name.lower())

    def test_unknown_name_is_rejected(self) -> None:
        provider = CredentialProvider(settings_factory=_settings, bao_reader=dict)
        with pytest.raises(UnknownCredentialError):
            provider.get("ANTHROPIC_API_KEY")


class TestSettingsFallback:
    def test_unconfigured_bao_falls_back_to_settings(
        self, monkeypatch: pytest.MonkeyPatch, log_capture: _ListHandler
    ) -> None:
        monkeypatch.delenv("BAO_ADDR", raising=False)
        provider = CredentialProvider(
            settings_factory=lambda: _settings(substack_session_cookie=SETTINGS_COOKIE)
        )
        assert provider.get(SUBSTACK_SESSION_COOKIE) == SETTINGS_COOKIE
        meta = provider.metadata(SUBSTACK_SESSION_COOKIE)
        assert meta.source == "settings"
        assert meta.present is True
        assert meta.saved_at is None
        assert provider.refresh(min_interval_s=0) is False

    def test_empty_profile_value_is_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BAO_ADDR", raising=False)
        provider = CredentialProvider(settings_factory=lambda: _settings(x_ct0=""))
        assert provider.get(X_CT0) is None
        meta = provider.metadata(X_CT0)
        assert (meta.present, meta.source, meta.saved_at, meta.last_verified_at) == (
            False,
            None,
            None,
            None,
        )

    def test_bao_value_wins_over_settings(self, token_env: None, log_capture: _ListHandler) -> None:
        fake = FakeBao({SUBSTACK_SESSION_COOKIE: BOOT_COOKIE})
        provider = CredentialProvider(
            settings_factory=lambda: _settings(substack_session_cookie=SETTINGS_COOKIE)
        )
        with patch("src.config.bao_secrets.hvac", fake.hvac):
            assert provider.get(SUBSTACK_SESSION_COOKIE) == BOOT_COOKIE
            assert provider.metadata(SUBSTACK_SESSION_COOKIE).source == "openbao"

    def test_default_provider_reads_real_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BAO_ADDR", raising=False)
        fake_settings = _settings(x_auth_token=AUTH_TOKEN)
        with patch("src.config.settings.get_settings", return_value=fake_settings):
            provider = get_credential_provider()
            assert provider is get_credential_provider()
            assert provider.get(X_AUTH_TOKEN) == AUTH_TOKEN


class TestLiveRotation:
    def test_token_manager_swap_reaches_long_lived_provider(
        self, approle_env: None, log_capture: _ListHandler
    ) -> None:
        """Acceptance: KV patch + one token-manager refresh -> new cookie, no new Settings."""
        settings_obj = _settings(substack_session_cookie=SETTINGS_COOKIE)
        settings_calls: list[object] = []

        def settings_factory() -> SimpleNamespace:
            settings_calls.append(settings_obj)
            return settings_obj

        fake = FakeBao(
            {
                SUBSTACK_SESSION_COOKIE: BOOT_COOKIE,
                f"{SUBSTACK_SESSION_COOKIE}_SAVED_AT": "2026-09-01T10:00:00+00:00",
            },
            approle_ttl=3600,
        )
        provider = CredentialProvider(settings_factory=settings_factory)
        with patch("src.config.bao_secrets.hvac", fake.hvac):
            assert provider.get(SUBSTACK_SESSION_COOKIE) == BOOT_COOKIE
            manager = bao_mod._token_manager
            assert manager is not None, "AppRole load must start the token manager"

            # Operator patches the KV secret (aca auth ... --to bao).
            fake.data[SUBSTACK_SESSION_COOKIE] = ROTATED_COOKIE
            fake.data[f"{SUBSTACK_SESSION_COOKIE}_SAVED_AT"] = "2026-09-22T08:30:00+00:00"
            # Reads between refreshes stay in memory.
            reads_before = fake.reads
            assert provider.get(SUBSTACK_SESSION_COOKIE) == BOOT_COOKIE
            assert fake.reads == reads_before

            manager._refresh()  # one scheduled token-manager refresh

            assert provider.get(SUBSTACK_SESSION_COOKIE) == ROTATED_COOKIE
            meta = provider.metadata(SUBSTACK_SESSION_COOKIE)
            assert meta.saved_at == datetime(2026, 9, 22, 8, 30, tzinfo=UTC)
        messages = [r.getMessage() for r in log_capture.records]
        assert any("bao.token_refreshed" in m for m in messages), "log capture is not wired"
        # The settings object was never rebuilt: the only instance ever served is
        # the boot-time one, and it still holds the stale value.
        assert all(obj is settings_obj for obj in settings_calls)
        assert settings_obj.substack_session_cookie == SETTINGS_COOKIE


class TestRefresh:
    def test_token_auth_refresh_reloads(self, token_env: None, log_capture: _ListHandler) -> None:
        fake = FakeBao({X_CT0: CT0_OLD})
        provider = CredentialProvider(settings_factory=_settings)
        with patch("src.config.bao_secrets.hvac", fake.hvac):
            assert provider.get(X_CT0) == CT0_OLD
            assert bao_mod._token_manager is None  # token auth: no background refresh
            fake.data[X_CT0] = CT0_NEW
            assert provider.refresh(min_interval_s=0) is True
            assert provider.get(X_CT0) == CT0_NEW
        assert fake.hvac.Client.call_count == 1, "refresh must reuse the loaded client"

    def test_refresh_is_rate_limited(
        self, token_env: None, monkeypatch: pytest.MonkeyPatch, log_capture: _ListHandler
    ) -> None:
        now = [1000.0]
        monkeypatch.setattr(bao_mod.time, "monotonic", lambda: now[0])
        fake = FakeBao({X_CT0: CT0_OLD})
        provider = CredentialProvider(settings_factory=_settings)
        with patch("src.config.bao_secrets.hvac", fake.hvac):
            provider.get(X_CT0)
            assert fake.reads == 1
            fake.data[X_CT0] = CT0_NEW

            # Right after the boot load: throttled, no read.
            assert provider.refresh(min_interval_s=60) is False
            now[0] += 30
            assert provider.refresh(min_interval_s=60) is False
            assert fake.reads == 1
            assert provider.get(X_CT0) == CT0_OLD

            now[0] += 31
            assert provider.refresh(min_interval_s=60) is True
            assert fake.reads == 2
            assert provider.get(X_CT0) == CT0_NEW

            # A burst of callers inside the window costs no further reads.
            for _ in range(20):
                assert provider.refresh(min_interval_s=60) is False
            assert fake.reads == 2

    def test_concurrent_refresh_reads_once(
        self, token_env: None, monkeypatch: pytest.MonkeyPatch, log_capture: _ListHandler
    ) -> None:
        now = [1000.0]
        monkeypatch.setattr(bao_mod.time, "monotonic", lambda: now[0])
        fake = FakeBao({X_CT0: CT0_OLD})
        provider = CredentialProvider(settings_factory=_settings)
        with patch("src.config.bao_secrets.hvac", fake.hvac):
            provider.get(X_CT0)
            now[0] += 120
            results: list[bool] = []
            threads = [
                threading.Thread(target=lambda: results.append(provider.refresh(min_interval_s=60)))
                for _ in range(10)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
        assert results.count(True) == 1
        assert fake.reads == 2

    def test_failed_refresh_counts_toward_the_bound(
        self, token_env: None, monkeypatch: pytest.MonkeyPatch, log_capture: _ListHandler
    ) -> None:
        now = [1000.0]
        monkeypatch.setattr(bao_mod.time, "monotonic", lambda: now[0])
        fake = FakeBao({X_CT0: CT0_OLD})
        provider = CredentialProvider(settings_factory=_settings)
        with patch("src.config.bao_secrets.hvac", fake.hvac):
            provider.get(X_CT0)
            now[0] += 120
            fake.fail_next_reads = 2  # read and the retry after re-auth both fail
            assert provider.refresh(min_interval_s=60) is False
            assert fake.reads == 3
            assert provider.get(X_CT0) == CT0_OLD  # cache kept on failure
            assert provider.refresh(min_interval_s=60) is False
            assert fake.reads == 3

    def test_approle_refresh_reauthenticates_once_on_failure(
        self, approle_env: None, log_capture: _ListHandler
    ) -> None:
        fake = FakeBao({X_CT0: CT0_OLD}, approle_ttl=3600)
        provider = CredentialProvider(settings_factory=_settings)
        with patch("src.config.bao_secrets.hvac", fake.hvac):
            provider.get(X_CT0)
            assert fake.logins == 1
            fake.data[X_CT0] = CT0_NEW
            fake.fail_next_reads = 1  # expired token on the first read
            assert provider.refresh(min_interval_s=0) is True
            assert fake.logins == 2
            assert provider.get(X_CT0) == CT0_NEW

    def test_refresh_recovers_from_failed_boot_load(
        self, token_env: None, log_capture: _ListHandler
    ) -> None:
        fake = FakeBao({X_CT0: CT0_NEW})
        fake.fail_next_reads = 1  # OpenBao unavailable at boot
        provider = CredentialProvider(settings_factory=lambda: _settings(x_ct0=CT0_OLD))
        with patch("src.config.bao_secrets.hvac", fake.hvac):
            assert provider.get(X_CT0) == CT0_OLD  # settings fallback
            assert provider.refresh(min_interval_s=0) is True
            assert provider.get(X_CT0) == CT0_NEW


class TestApplyLocalWrite:
    def test_local_write_visible_without_round_trip(
        self, token_env: None, log_capture: _ListHandler
    ) -> None:
        fake = FakeBao({X_AUTH_TOKEN: AUTH_TOKEN, X_CT0: CT0_OLD, "OTHER_KEY": "other"})
        stamp = datetime(2026, 9, 22, 12, 0, 5, tzinfo=UTC)
        provider = CredentialProvider(settings_factory=_settings, clock=lambda: stamp)
        with patch("src.config.bao_secrets.hvac", fake.hvac):
            old_view = bao_mod.get_bao_secrets()
            reads = fake.reads

            names = provider.apply_local_write({X_CT0: CT0_NEW})

            assert names == [X_CT0, "X_CT0_SAVED_AT"]
            assert provider.get(X_CT0) == CT0_NEW
            assert provider.get(X_AUTH_TOKEN) == AUTH_TOKEN
            assert bao_mod.get_bao_secrets()["OTHER_KEY"] == "other"
            assert provider.metadata(X_CT0).saved_at == stamp
            assert fake.reads == reads, "apply_local_write must not read OpenBao"
            # Reference swap: a snapshot taken before the write is untouched.
            assert old_view[X_CT0] == CT0_OLD

    def test_explicit_saved_at_sibling_is_kept(self, token_env: None) -> None:
        fake = FakeBao({})
        provider = CredentialProvider(settings_factory=_settings)
        with patch("src.config.bao_secrets.hvac", fake.hvac):
            provider.apply_local_write(
                {X_CT0: CT0_NEW, "X_CT0_SAVED_AT": "2026-09-20T00:00:00+00:00"}
            )
            assert provider.metadata(X_CT0).saved_at == datetime(2026, 9, 20, tzinfo=UTC)

    def test_unregistered_key_is_refused(self, token_env: None) -> None:
        fake = FakeBao({})
        provider = CredentialProvider(settings_factory=_settings)
        with patch("src.config.bao_secrets.hvac", fake.hvac):
            with pytest.raises(UnknownCredentialError):
                provider.apply_local_write({"ANTHROPIC_API_KEY": "x"})
            assert "ANTHROPIC_API_KEY" not in bao_mod.get_bao_secrets()

    def test_later_refresh_supersedes_local_write(
        self, token_env: None, log_capture: _ListHandler
    ) -> None:
        fake = FakeBao({X_CT0: CT0_OLD})
        provider = CredentialProvider(settings_factory=_settings)
        with patch("src.config.bao_secrets.hvac", fake.hvac):
            provider.get(X_CT0)
            provider.apply_local_write({X_CT0: CT0_NEW})
            fake.data[X_CT0] = CT0_NEW  # the PATCH that preceded the local write
            assert provider.refresh(min_interval_s=0) is True
            assert provider.get(X_CT0) == CT0_NEW


class TestMetadata:
    def test_all_browser_sessions_expose_metadata(self, token_env: None) -> None:
        fake = FakeBao(
            {
                SUBSTACK_SESSION_COOKIE: BOOT_COOKIE,
                "SUBSTACK_SESSION_COOKIE_SAVED_AT": "2026-09-01T10:00:00Z",
                X_AUTH_TOKEN: AUTH_TOKEN,
                "X_AUTH_TOKEN_SAVED_AT": "not-a-timestamp",
            }
        )
        provider = CredentialProvider(settings_factory=_settings)
        with patch("src.config.bao_secrets.hvac", fake.hvac):
            substack = provider.metadata(SUBSTACK_SESSION_COOKIE)
            auth = provider.metadata(X_AUTH_TOKEN)
            ct0 = provider.metadata(X_CT0)
        assert (substack.label, substack.saved_at) == (
            "substack.sid",
            datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
        )
        assert (auth.label, auth.saved_at, auth.present) == ("x.auth_token", None, True)
        assert (ct0.label, ct0.present, ct0.saved_at, ct0.last_verified_at) == (
            "x.ct0",
            False,
            None,
            None,
        )
        for meta in (substack, auth, ct0):
            assert BOOT_COOKIE not in repr(meta)
            assert AUTH_TOKEN not in repr(meta)

    def test_last_verified_at_tracks_the_current_value(
        self, token_env: None, log_capture: _ListHandler
    ) -> None:
        fake = FakeBao({SUBSTACK_SESSION_COOKIE: BOOT_COOKIE})
        verified_at = datetime(2026, 9, 22, 9, 0, tzinfo=UTC)
        provider = CredentialProvider(settings_factory=_settings)
        with patch("src.config.bao_secrets.hvac", fake.hvac):
            assert provider.metadata(SUBSTACK_SESSION_COOKIE).last_verified_at is None
            provider.mark_verified(SUBSTACK_SESSION_COOKIE, at=verified_at)
            assert provider.metadata(SUBSTACK_SESSION_COOKIE).last_verified_at == verified_at

            fake.data[SUBSTACK_SESSION_COOKIE] = ROTATED_COOKIE
            assert provider.refresh(min_interval_s=0) is True
            # The verification belonged to the previous cookie.
            assert provider.metadata(SUBSTACK_SESSION_COOKIE).last_verified_at is None
        # Nothing was written to OpenBao to record the verification.
        fake.client.adapter.request.assert_not_called()
        fake.client.secrets.kv.v2.create_or_update_secret.assert_not_called()

    def test_mark_verified_without_value_is_a_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BAO_ADDR", raising=False)
        provider = CredentialProvider(settings_factory=_settings)
        provider.mark_verified(X_CT0)
        assert provider.metadata(X_CT0).last_verified_at is None


class TestFailureIsolation:
    def test_reader_failure_falls_back_without_logging_values(
        self, log_capture: _ListHandler
    ) -> None:
        def broken_reader() -> dict[str, str]:
            raise RuntimeError("boom")

        provider = CredentialProvider(
            settings_factory=lambda: _settings(x_ct0=CT0_OLD), bao_reader=broken_reader
        )
        assert provider.get(X_CT0) == CT0_OLD
        assert any("credentials.bao_unavailable" in r.getMessage() for r in log_capture.records)
