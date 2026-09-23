"""Tests for ``aca auth session substack|x`` (``src/cli/session_commands.py``).

No real browser and no network: Playwright is replaced by a fake persistent
context injected through the module-level ``playwright_persistent_context``
seam, the validation request goes to an ``httpx.MockTransport``, and sinks are
fakes (or a real ``BaoSink`` over a fake KV v2 client). Every cookie value is a
sentinel that must never appear on stdout, stderr or in logs.
"""

from __future__ import annotations

import importlib
import logging
import stat
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from src.cli import session_commands
from src.cli.secret_sinks import BaoSink, SecretSinkError, SinkName
from src.cli.session_commands import (
    SITES,
    SessionCaptureError,
    capture_session,
    default_sink_factory,
    default_sink_name,
    select_session,
)
from src.ingestion.x_web import X_ACCOUNT_SETTINGS_URL, X_WEB_BEARER_TOKEN

SUBSTACK_SENTINEL = "SENTINEL-substack-sid-do-not-print"
AUTH_TOKEN_SENTINEL = "SENTINEL-auth-token-do-not-print"
CT0_SENTINEL = "SENTINEL-ct0-do-not-print"
SENTINELS = (SUBSTACK_SENTINEL, AUTH_TOKEN_SENTINEL, CT0_SENTINEL)
FUTURE = 4_000_000_000.0  # a cookie expiry well after "now"


def _cookie(name: str, value: str, domain: str, expires: float = FUTURE) -> dict[str, Any]:
    return {"name": name, "value": value, "domain": domain, "path": "/", "expires": expires}


SUBSTACK_COOKIES = [_cookie("substack.sid", SUBSTACK_SENTINEL, ".substack.com")]
X_COOKIES = [
    _cookie("auth_token", AUTH_TOKEN_SENTINEL, ".x.com"),
    _cookie("ct0", CT0_SENTINEL, ".x.com"),
]


# ─── Fakes ────────────────────────────────────────────────────────────


class FakePage:
    def __init__(self) -> None:
        self.visited: list[str] = []

    def goto(self, url: str) -> None:
        self.visited.append(url)


class FakeContext:
    """Stands in for a Playwright BrowserContext.

    ``cookie_script`` is the list of cookie jars returned by successive
    ``cookies()`` calls; the last one repeats forever.
    """

    def __init__(self, cookie_script: list[list[dict[str, Any]]]) -> None:
        self._script = cookie_script
        self.cookie_calls = 0
        self.page = FakePage()
        self.pages: list[FakePage] = []
        self.closed = False

    def cookies(self) -> list[dict[str, Any]]:
        jar = self._script[min(self.cookie_calls, len(self._script) - 1)]
        self.cookie_calls += 1
        return [dict(c) for c in jar]

    def new_page(self) -> FakePage:
        self.pages.append(self.page)
        return self.page


class FakeBrowser:
    """The ``browser_factory`` seam: records the profile dir and headless flag."""

    def __init__(self, context: FakeContext) -> None:
        self.context = context
        self.launches: list[tuple[Path, bool]] = []

    @contextmanager
    def __call__(self, user_data_dir: Path, headless: bool) -> Iterator[FakeContext]:
        self.launches.append((user_data_dir, headless))
        try:
            yield self.context
        finally:
            self.context.closed = True


class FakeSink:
    name = SinkName.SECRETS_FILE
    target = "fake sink"
    next_step_hint = "none"

    def __init__(self) -> None:
        self.checked = 0
        self.writes: list[dict[str, str]] = []

    def check(self) -> None:
        self.checked += 1

    def write(self, values: Mapping[str, str]) -> list[str]:
        self.writes.append(dict(values))
        return list(values)


class FakeClock:
    """Monotonic clock that only advances when the command sleeps."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def time(self) -> float:
        return 1_900_000_000.0 + self.now


class FakeProvider:
    def __init__(self) -> None:
        self.applied: list[tuple[dict[str, str], datetime | None]] = []

    def apply_local_write(
        self, values: Mapping[str, str], *, saved_at: datetime | None = None
    ) -> list[str]:
        self.applied.append((dict(values), saved_at))
        return list(values)


class FakeBaoAdapter:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> None:
        self.requests.append((method, url, kwargs))


def _ok_handler(calls: list[httpx.Request]) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.host == "x.com":
            return httpx.Response(200, json={"screen_name": "operator"})
        return httpx.Response(200, json={"subscriptions": [], "publications": []})

    return handler


@pytest.fixture
def profiles_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the real ``browser_profiles_dir()`` at a temp root via settings."""
    root = tmp_path / "home" / ".aca" / "browser-profiles"
    # ``src.config.settings`` the attribute is the Settings object, not the
    # module, so patch through the module itself.
    settings_module = importlib.import_module("src.config.settings")
    monkeypatch.setattr(
        settings_module, "get_settings", lambda: SimpleNamespace(browser_profiles_dir=str(root))
    )
    return root


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch, profiles_root: Path) -> Callable[..., SimpleNamespace]:
    """Wire fakes into the module-level seams the CLI command resolves."""

    def build(
        cookie_script: list[list[dict[str, Any]]],
        *,
        handler: Callable[[httpx.Request], httpx.Response] | None = None,
        sink: Any = None,
        bao_adapter: FakeBaoAdapter | None = None,
    ) -> SimpleNamespace:
        ns = SimpleNamespace()
        ns.context = FakeContext(cookie_script)
        ns.browser = FakeBrowser(ns.context)
        ns.sink = sink if sink is not None else FakeSink()
        ns.http_calls = []
        ns.clock = FakeClock()
        ns.provider = FakeProvider()
        ns.sink_requests = []
        ns.profiles_root = profiles_root

        def sink_factory(name: SinkName, saved_at_clock: Callable[[], datetime]) -> Any:
            ns.sink_requests.append(name)
            if bao_adapter is not None:
                # A real BaoSink over a fake KV v2 transport, on the command's clock.
                ns.sink = BaoSink(
                    client=SimpleNamespace(adapter=bao_adapter),
                    mount_path="secret",
                    secret_path="newsletter",
                    clock=saved_at_clock,
                )
            return ns.sink

        transport = httpx.MockTransport(handler or _ok_handler(ns.http_calls))
        monkeypatch.setattr(session_commands, "playwright_persistent_context", ns.browser)
        monkeypatch.setattr(session_commands, "default_sink_factory", sink_factory)
        monkeypatch.setattr(
            session_commands, "new_http_client", lambda: httpx.Client(transport=transport)
        )
        monkeypatch.setattr(session_commands, "get_credential_provider", lambda: ns.provider)
        monkeypatch.setattr(session_commands, "time", ns.clock)
        return ns

    return build


def _invoke(*args: str) -> Any:
    return CliRunner().invoke(session_commands.app, list(args))


def _assert_no_sentinel(*texts: str) -> None:
    for text in texts:
        for sentinel in SENTINELS:
            assert sentinel not in text


# ─── (1) Profile already logged in: validate, then one write ──────────


def test_existing_substack_session_validates_and_writes_once(
    harness: Callable[..., SimpleNamespace], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    ns = harness([SUBSTACK_COOKIES])

    result = _invoke("substack", "--to", "secrets-file")

    assert result.exit_code == 0, result.output
    assert ns.sink.writes == [{"SUBSTACK_SESSION_COOKIE": SUBSTACK_SENTINEL}]
    assert ns.sink.checked == 1
    # Exactly one validation request, to the adapter's authenticated endpoint.
    assert [str(r.url) for r in ns.http_calls] == ["https://substack.com/api/v1/subscriptions"]
    assert ns.http_calls[0].headers["cookie"] == f"substack.sid={SUBSTACK_SENTINEL}"
    # Already logged in: no login page opened, no polling.
    assert ns.context.page.visited == []
    assert ns.clock.sleeps == []
    assert ns.context.closed
    assert "SUBSTACK_SESSION_COOKIE" in result.output
    assert "substack.com" in result.output
    _assert_no_sentinel(result.output, caplog.text)


def test_existing_x_session_patches_openbao_once_and_updates_cache(
    harness: Callable[..., SimpleNamespace], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    adapter = FakeBaoAdapter()
    ns = harness([X_COOKIES], bao_adapter=adapter)

    result = _invoke("x", "--to", "bao")

    assert result.exit_code == 0, result.output
    assert ns.sink_requests == [SinkName.BAO]
    # ONE atomic PATCH carrying both cookies and their saved_at siblings.
    assert len(adapter.requests) == 1
    method, url, kwargs = adapter.requests[0]
    assert (method, url) == ("PATCH", "/v1/secret/data/newsletter")
    data = kwargs["json"]["data"]
    assert data["X_AUTH_TOKEN"] == AUTH_TOKEN_SENTINEL
    assert data["X_CT0"] == CT0_SENTINEL
    assert data["X_AUTH_TOKEN_SAVED_AT"] == data["X_CT0_SAVED_AT"]
    # The in-process cache gets the same values stamped with the same saved_at.
    [(applied, saved_at)] = ns.provider.applied
    assert applied == {"X_AUTH_TOKEN": AUTH_TOKEN_SENTINEL, "X_CT0": CT0_SENTINEL}
    assert saved_at is not None
    assert saved_at.isoformat(timespec="seconds") == data["X_CT0_SAVED_AT"]
    # Validation used the web bearer token, the csrf header and both cookies.
    [request] = ns.http_calls
    assert str(request.url) == X_ACCOUNT_SETTINGS_URL
    assert request.headers["authorization"] == f"Bearer {X_WEB_BEARER_TOKEN}"
    assert request.headers["x-csrf-token"] == CT0_SENTINEL
    assert request.headers["cookie"] == f"auth_token={AUTH_TOKEN_SENTINEL}; ct0={CT0_SENTINEL}"
    assert "X_AUTH_TOKEN" in result.output and "X_CT0" in result.output
    _assert_no_sentinel(result.output, caplog.text)


def test_second_run_reuses_profile_without_login(
    harness: Callable[..., SimpleNamespace],
) -> None:
    ns = harness([X_COOKIES])
    assert _invoke("x", "--to", "secrets-file").exit_code == 0
    assert _invoke("x", "--to", "secrets-file").exit_code == 0

    profile = ns.profiles_root / "x"
    assert [launch[0] for launch in ns.browser.launches] == [profile, profile]
    assert ns.context.page.visited == []
    assert len(ns.sink.writes) == 2


# ─── Interactive login: cookies appear after polling ──────────────────


def test_login_page_opened_and_cookies_polled_until_present(
    harness: Callable[..., SimpleNamespace],
) -> None:
    ns = harness([[], [], [], X_COOKIES])

    result = _invoke("x", "--to", "secrets-file", "--timeout", "30")

    assert result.exit_code == 0, result.output
    assert ns.context.page.visited == ["https://x.com/i/flow/login"]
    assert ns.clock.sleeps == [1.0, 1.0]
    assert ns.browser.launches[0][1] is False  # headed by default
    assert ns.sink.writes == [{"X_AUTH_TOKEN": AUTH_TOKEN_SENTINEL, "X_CT0": CT0_SENTINEL}]


# ─── (2) Never-produced cookies: timeout ──────────────────────────────


def test_timeout_exits_nonzero_without_writing(harness: Callable[..., SimpleNamespace]) -> None:
    ns = harness([[_cookie("unrelated", "v", ".substack.com")]])

    result = _invoke("substack", "--to", "secrets-file", "--timeout", "5")

    assert result.exit_code == 1
    assert "Timed out after 5s" in result.output
    assert "substack.sid" in result.output
    assert ns.clock.now >= 5
    assert ns.clock.sleeps == [1.0] * 5
    assert ns.sink.writes == []
    assert ns.http_calls == []
    assert ns.context.closed


def test_headless_timeout_hints_at_headed_login(harness: Callable[..., SimpleNamespace]) -> None:
    ns = harness([[]])

    result = _invoke("x", "--to", "secrets-file", "--timeout", "2", "--headless")

    assert result.exit_code == 1
    assert "--headless" in result.output
    assert ns.browser.launches[0][1] is True


# ─── (3) Validation failure: nothing written ──────────────────────────


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401, json={"errors": [{"code": 32}]}),
        httpx.Response(200, text="<html><form id='LoginForm'></form></html>"),
        httpx.Response(200, json={"unexpected": True}),
    ],
    ids=["http-401", "login-page", "wrong-json"],
)
def test_validation_failure_writes_nothing(
    harness: Callable[..., SimpleNamespace],
    response: httpx.Response,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    ns = harness([X_COOKIES], handler=lambda request: response)

    result = _invoke("x", "--to", "bao")

    assert result.exit_code == 1
    assert "X rejected" in result.output or "X did not accept" in result.output
    assert ns.sink.writes == []
    assert ns.provider.applied == []
    _assert_no_sentinel(result.output, caplog.text)


def test_network_error_during_validation_writes_nothing(
    harness: Callable[..., SimpleNamespace],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    ns = harness([SUBSTACK_COOKIES], handler=handler)

    result = _invoke("substack", "--to", "secrets-file")

    assert result.exit_code == 1
    assert "ConnectError" in result.output
    assert ns.sink.writes == []


def test_sink_check_failure_stops_before_browser(
    harness: Callable[..., SimpleNamespace],
) -> None:
    class BrokenSink(FakeSink):
        def check(self) -> None:
            raise SecretSinkError("BAO_ADDR is not set")

    ns = harness([X_COOKIES], sink=BrokenSink())

    result = _invoke("x", "--to", "bao")

    assert result.exit_code == 1
    assert "BAO_ADDR is not set" in result.output
    assert ns.browser.launches == []
    assert ns.sink.writes == []


# ─── (4) Profile directory: 0700 under browser_profiles_dir() ─────────


def test_profile_dir_created_0700_under_browser_profiles_dir(
    harness: Callable[..., SimpleNamespace],
) -> None:
    ns = harness([SUBSTACK_COOKIES])
    root = ns.profiles_root
    root.mkdir(parents=True, mode=0o755)
    root.chmod(0o755)  # a pre-existing, too-open root is tightened

    assert _invoke("substack", "--to", "secrets-file").exit_code == 0

    profile = root / "substack"
    assert ns.browser.launches == [(profile, False)]
    assert profile.is_dir()
    assert stat.S_IMODE(profile.stat().st_mode) == 0o700
    assert stat.S_IMODE(root.stat().st_mode) == 0o700


def test_symlinked_profile_dir_is_refused(harness: Callable[..., SimpleNamespace]) -> None:
    ns = harness([SUBSTACK_COOKIES])
    ns.profiles_root.mkdir(parents=True)
    elsewhere = ns.profiles_root.parent / "elsewhere"
    elsewhere.mkdir()
    (ns.profiles_root / "substack").symlink_to(elsewhere)

    result = _invoke("substack", "--to", "secrets-file")

    assert result.exit_code == 1
    assert "real directory" in result.output
    assert ns.browser.launches == []


# ─── (5) X needs both cookies, from one domain ────────────────────────


def test_x_requires_both_cookies(harness: Callable[..., SimpleNamespace]) -> None:
    ns = harness([[_cookie("auth_token", AUTH_TOKEN_SENTINEL, ".x.com")]])

    result = _invoke("x", "--to", "secrets-file", "--timeout", "3")

    assert result.exit_code == 1
    assert "auth_token and ct0" in result.output
    assert ns.sink.writes == []
    _assert_no_sentinel(result.output)


def test_select_session_never_mixes_domains() -> None:
    spec = SITES["x"]
    mixed = [
        _cookie("auth_token", AUTH_TOKEN_SENTINEL, ".x.com"),
        _cookie("ct0", CT0_SENTINEL, ".twitter.com"),
    ]
    assert select_session(spec, mixed, now_epoch=0) is None


def test_select_session_prefers_x_com_over_twitter_com() -> None:
    spec = SITES["x"]
    cookies = [
        _cookie("auth_token", "old-token", ".twitter.com"),
        _cookie("ct0", "old-ct0", ".twitter.com"),
        *X_COOKIES,
    ]
    session = select_session(spec, cookies, now_epoch=0)
    assert session is not None
    assert session.domain == "x.com"
    assert session.values == {"X_AUTH_TOKEN": AUTH_TOKEN_SENTINEL, "X_CT0": CT0_SENTINEL}
    _assert_no_sentinel(repr(session))


def test_select_session_falls_back_to_twitter_com_only_when_x_com_absent() -> None:
    spec = SITES["x"]
    cookies = [
        _cookie("auth_token", AUTH_TOKEN_SENTINEL, ".twitter.com"),
        _cookie("ct0", CT0_SENTINEL, "twitter.com"),
    ]
    session = select_session(spec, cookies, now_epoch=0)
    assert session is not None and session.domain == "twitter.com"


def test_select_session_ignores_expired_and_foreign_cookies() -> None:
    spec = SITES["substack"]
    now = 1_900_000_000.0
    expired = [_cookie("substack.sid", SUBSTACK_SENTINEL, ".substack.com", expires=now - 1)]
    foreign = [_cookie("substack.sid", SUBSTACK_SENTINEL, ".example.substack.com.evil.test")]
    session_cookie = [_cookie("substack.sid", SUBSTACK_SENTINEL, "substack.com", expires=-1)]
    assert select_session(spec, expired, now_epoch=now) is None
    assert select_session(spec, foreign, now_epoch=now) is None
    assert select_session(spec, session_cookie, now_epoch=now) is not None


# ─── Default sink selection ───────────────────────────────────────────


def test_default_bao_sink_pins_saved_at_to_the_command_clock() -> None:
    fixed = datetime(2026, 9, 22, 12, 0, 0, tzinfo=UTC)
    sink = default_sink_factory(SinkName.BAO, lambda: fixed)
    assert isinstance(sink, BaoSink)
    adapter = FakeBaoAdapter()
    sink._client = SimpleNamespace(adapter=adapter)
    sink.write({"X_CT0": CT0_SENTINEL})
    assert adapter.requests[0][2]["json"]["data"]["X_CT0_SAVED_AT"] == "2026-09-22T12:00:00+00:00"


def test_default_sink_is_bao_when_bao_addr_set_else_secrets_file() -> None:
    assert default_sink_name({"BAO_ADDR": "https://gx-10.example.ts.net:8200"}) is SinkName.BAO
    assert default_sink_name({}) is SinkName.SECRETS_FILE


def test_omitted_to_uses_default_sink(
    harness: Callable[..., SimpleNamespace], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("BAO_ADDR", raising=False)
    ns = harness([SUBSTACK_COOKIES])
    assert _invoke("substack").exit_code == 0
    assert ns.sink_requests == [SinkName.SECRETS_FILE]


# ─── Real secrets-file sink end to end ────────────────────────────────


def test_secrets_file_sink_receives_x_pair(
    harness: Callable[..., SimpleNamespace], tmp_path: Path
) -> None:
    from src.cli.secret_sinks import SecretsFileSink

    path = tmp_path / ".secrets.yaml"
    path.write_text("ANTHROPIC_API_KEY: keep-me\n", encoding="utf-8")
    harness([X_COOKIES], sink=SecretsFileSink(path))

    result = _invoke("x", "--to", "secrets-file")

    assert result.exit_code == 0, result.output
    text = path.read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY: keep-me" in text
    assert AUTH_TOKEN_SENTINEL in text and CT0_SENTINEL in text
    _assert_no_sentinel(result.output)


# ─── No scheduling side effects; registration ─────────────────────────


def test_command_schedules_nothing() -> None:
    source = Path(session_commands.__file__).read_text(encoding="utf-8")
    for forbidden in ("crontab", "systemctl", "create_trigger", "schedule.yaml", "Timer("):
        assert forbidden not in source


def test_registered_under_aca_auth() -> None:
    from src.cli.app import app

    result = CliRunner().invoke(app, ["auth", "session", "--help"])
    assert result.exit_code == 0, result.output
    assert "substack" in result.output and "x" in result.output


def test_missing_playwright_is_a_clear_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("playwright"):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(SessionCaptureError, match="Playwright is not installed"):
        with session_commands.playwright_persistent_context(tmp_path, True):
            pass


def test_capture_session_rejects_nonpositive_timeout() -> None:
    with pytest.raises(SessionCaptureError, match="--timeout"):
        capture_session("x", timeout_s=0, sink_factory=lambda *_: FakeSink())


def test_substack_validation_accepts_a_json_list() -> None:
    """The legacy subscriptions endpoint shape (a bare list) is accepted too."""
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[])))
    SITES["substack"].validate({"SUBSTACK_SESSION_COOKIE": SUBSTACK_SENTINEL}, client)
