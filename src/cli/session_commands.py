"""``aca auth session substack|x``: capture a browser session into a secret sink.

Replaces copying cookies out of DevTools by hand. The command:

1. opens Chromium through Playwright's ``launch_persistent_context`` on a
   per-site profile under :func:`~src.config.browser_profiles.browser_profiles_dir`
   (created with mode 0700, and never copied by backup or sync);
2. returns immediately when the profile already holds the target cookies, so a
   second run needs no login; otherwise opens the site's login page and polls
   ``context.cookies()`` about once a second until the cookies appear or
   ``--timeout`` elapses;
3. proves the cookies work with ONE cheap authenticated request over httpx
   (not through the browser), and writes nothing when that request fails;
4. writes every cookie of the site in ONE ``SecretSink.write()`` call, so the X
   ``auth_token``/``ct0`` pair can never land torn.

Target cookies (the domain Playwright reports, leading dot optional):

* ``substack`` -> ``substack.sid`` on ``substack.com`` -> ``SUBSTACK_SESSION_COOKIE``
* ``x``        -> ``auth_token`` + ``ct0`` on ``x.com`` -> ``X_AUTH_TOKEN``, ``X_CT0``.
  ``twitter.com`` is accepted only when ``x.com`` does not hold the pair (a
  profile last used before the domain move), and both cookies must then come
  from ``twitter.com``: a pair is never assembled from two domains.

Default sink when ``--to`` is omitted: ``bao`` when ``BAO_ADDR`` is set, else
``secrets-file``. Railway is only ever chosen explicitly.

Security: no cookie value is printed, logged, placed in argv or put in an
exception message; output names only cookies, domains, keys and the sink target.
The command creates no timer, cron entry or scheduled job; it is re-run by hand
when an expiry alert names it.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager, suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer

from src.cli.secret_sinks import BaoSink, SecretSink, SecretSinkError, SinkName, build_sink
from src.config.browser_profiles import browser_profiles_dir
from src.config.credentials import (
    SUBSTACK_SESSION_COOKIE,
    X_AUTH_TOKEN,
    X_CT0,
    CredentialProvider,
    get_credential_provider,
)
from src.ingestion.x_web import (
    X_ACCOUNT_SETTINGS_URL,
    X_AUTH_TOKEN_COOKIE,
    X_CT0_COOKIE,
    x_web_headers,
)

__all__ = [
    "DEFAULT_TIMEOUT_S",
    "SITES",
    "SessionCaptureError",
    "SiteSpec",
    "app",
    "capture_session",
    "default_sink_name",
]

app = typer.Typer(
    name="session",
    help=(
        "Capture a browser login session (Substack, X) with Playwright and write its "
        "cookies to a secret sink."
    ),
    no_args_is_help=True,
)

DEFAULT_TIMEOUT_S = 300
POLL_INTERVAL_S = 1.0
VALIDATION_TIMEOUT_S = 15.0

#: Authenticated JSON endpoint the Substack adapter already calls
#: (``SubstackClient._fetch_subscriptions_from_http``). Anonymous or expired
#: sessions get a 401/403 or an HTML page instead of JSON.
SUBSTACK_VALIDATION_URL = "https://substack.com/api/v1/subscriptions"
SUBSTACK_SID_COOKIE = "substack.sid"


class SessionCaptureError(Exception):
    """The capture could not complete. Messages never contain cookie values."""


# ---------------------------------------------------------------------------
# Per-site configuration
# ---------------------------------------------------------------------------

Validator = Callable[[Mapping[str, str], httpx.Client], None]


def _validate_substack(values: Mapping[str, str], http: httpx.Client) -> None:
    cookie = values[SUBSTACK_SESSION_COOKIE]
    response = http.get(
        SUBSTACK_VALIDATION_URL,
        headers={"cookie": f"{SUBSTACK_SID_COOKIE}={cookie}", "accept": "application/json"},
    )
    _require_json_ok(response, "Substack", lambda data: isinstance(data, list | dict))


def _validate_x(values: Mapping[str, str], http: httpx.Client) -> None:
    response = http.get(
        X_ACCOUNT_SETTINGS_URL,
        headers=x_web_headers(values[X_AUTH_TOKEN], values[X_CT0]),
    )
    _require_json_ok(
        response, "X", lambda data: isinstance(data, dict) and bool(data.get("screen_name"))
    )


def _require_json_ok(response: httpx.Response, site: str, accept: Callable[[Any], bool]) -> None:
    """Raise unless ``response`` is a 200 carrying the expected JSON shape.

    Messages carry the status code and URL only, never headers or body.
    """
    where = f"{response.request.method} {response.request.url.copy_with(query=None)}"
    if response.status_code != 200:
        raise SessionCaptureError(
            f"{site} rejected the captured session: {where} returned HTTP {response.status_code}"
        )
    try:
        data = response.json()
    except ValueError:
        raise SessionCaptureError(
            f"{site} did not accept the captured session: {where} returned a non-JSON "
            "page (usually the login page)"
        ) from None
    if not accept(data):
        raise SessionCaptureError(
            f"{site} did not accept the captured session: {where} returned unexpected JSON"
        )


@dataclass(frozen=True)
class SiteSpec:
    """Everything the capture needs to know about one site."""

    site: str
    title: str
    login_url: str
    cookie_domains: tuple[str, ...]
    """Domains tried in order; the first holding EVERY cookie wins."""
    cookies: tuple[tuple[str, str], ...]
    """``(cookie name, credential key)`` pairs written together."""
    validate: Validator = field(repr=False)

    @property
    def cookie_names(self) -> tuple[str, ...]:
        return tuple(name for name, _key in self.cookies)


SITES: Mapping[str, SiteSpec] = {
    "substack": SiteSpec(
        site="substack",
        title="Substack",
        login_url="https://substack.com/sign-in",
        cookie_domains=("substack.com",),
        cookies=((SUBSTACK_SID_COOKIE, SUBSTACK_SESSION_COOKIE),),
        validate=_validate_substack,
    ),
    "x": SiteSpec(
        site="x",
        title="X",
        login_url="https://x.com/i/flow/login",
        cookie_domains=("x.com", "twitter.com"),
        cookies=((X_AUTH_TOKEN_COOKIE, X_AUTH_TOKEN), (X_CT0_COOKIE, X_CT0)),
        validate=_validate_x,
    ),
}


# ---------------------------------------------------------------------------
# Cookie selection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CapturedSession:
    """Cookie values keyed by credential name. ``repr`` never shows values."""

    domain: str
    values: Mapping[str, str] = field(repr=False)


def _cookie_domain(cookie: Mapping[str, Any]) -> str:
    return str(cookie.get("domain") or "").lstrip(".").lower()


def _is_live(cookie: Mapping[str, Any], now_epoch: float) -> bool:
    # Playwright reports session cookies with expires == -1.
    expires = cookie.get("expires")
    if isinstance(expires, int | float) and expires > 0 and expires <= now_epoch:
        return False
    return bool(cookie.get("value"))


def select_session(
    spec: SiteSpec, cookies: Sequence[Mapping[str, Any]], *, now_epoch: float
) -> CapturedSession | None:
    """Return the site's cookies from the first domain holding all of them."""
    for domain in spec.cookie_domains:
        found: dict[str, str] = {}
        for cookie in cookies:
            name = cookie.get("name")
            if (
                name in spec.cookie_names
                and _cookie_domain(cookie) == domain
                and _is_live(cookie, now_epoch)
            ):
                found[str(name)] = str(cookie["value"])
        if all(name in found for name in spec.cookie_names):
            return CapturedSession(
                domain=domain, values={key: found[name] for name, key in spec.cookies}
            )
    return None


# ---------------------------------------------------------------------------
# Seams: browser, sink, clock
# ---------------------------------------------------------------------------

BrowserFactory = Callable[[Path, bool], AbstractContextManager[Any]]
SinkFactory = Callable[[SinkName, Callable[[], datetime]], SecretSink]


@contextmanager
def playwright_persistent_context(user_data_dir: Path, headless: bool) -> Iterator[Any]:
    """Open Chromium on a persistent profile; close it (and Playwright) on exit."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SessionCaptureError(
            "Playwright is not installed. Install it with: pip install 'playwright==1.62.0' "
            "&& playwright install chromium"
        ) from exc
    with sync_playwright() as playwright:
        try:
            context = playwright.chromium.launch_persistent_context(
                str(user_data_dir), headless=headless
            )
        except Exception as exc:
            # No cookies exist yet at launch, so the reason is safe to show; it is
            # usually a missing browser build or no display for a headed window.
            reason = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
            raise SessionCaptureError(
                f"Could not launch Chromium ({type(exc).__name__}: {reason}). Install it with "
                "`playwright install chromium`; without a display, use a machine that has "
                "one or pass --headless for an already logged-in profile."
            ) from None
        try:
            yield context
        finally:
            # The operator may already have closed the window.
            with suppress(Exception):
                context.close()


def new_http_client() -> httpx.Client:
    """The client used for the one validation request (no redirects followed)."""
    return httpx.Client(timeout=VALIDATION_TIMEOUT_S, follow_redirects=False)


class _PinnedClock:
    """The sink's ``saved_at`` clock, pinned on first use so it can be reused.

    ``BaoSink`` stamps ``<KEY>_SAVED_AT`` from its clock inside ``write()``;
    reading :attr:`at` afterwards lets the in-process credential cache carry the
    very same timestamp.
    """

    def __init__(self) -> None:
        self.at: datetime | None = None

    def __call__(self) -> datetime:
        if self.at is None:
            self.at = datetime.now(UTC)
        return self.at


def default_sink_factory(name: SinkName, saved_at_clock: Callable[[], datetime]) -> SecretSink:
    if name is SinkName.BAO:
        return BaoSink(clock=saved_at_clock)
    return build_sink(name)


def default_sink_name(environ: Mapping[str, str] | None = None) -> SinkName:
    """``bao`` when ``BAO_ADDR`` is set, else ``secrets-file`` (never Railway)."""
    env = os.environ if environ is None else environ
    return SinkName.BAO if env.get("BAO_ADDR") else SinkName.SECRETS_FILE


def prepare_profile_dir(site: str, root: Path | None = None) -> Path:
    """Create ``<root>/<site>`` and the root with mode 0700, tightening existing ones."""
    base = root if root is not None else browser_profiles_dir()
    profile = base / site
    profile.mkdir(mode=0o700, parents=True, exist_ok=True)
    # A symlinked site directory could point outside the backup-excluded root
    # (src/config/browser_profiles.py); the root itself may be a symlink, which
    # the backup exclusion resolves.
    if profile.is_symlink() or not profile.is_dir():
        raise SessionCaptureError(f"{profile} must be a real directory, not a link or file")
    # mkdir's mode is masked by the umask and ignored for existing directories.
    for directory in (base, profile):
        os.chmod(directory, 0o700)
    return profile


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------


def _err(message: str) -> None:
    typer.echo(message, err=True)


def _read_cookies(context: Any) -> list[Mapping[str, Any]]:
    try:
        return list(context.cookies())
    except Exception as exc:
        raise SessionCaptureError(
            f"The browser closed before the session was captured ({type(exc).__name__})"
        ) from None


def _open_login_page(context: Any, url: str) -> None:
    pages = list(getattr(context, "pages", []) or [])
    page = pages[0] if pages else context.new_page()
    try:
        page.goto(url)
    except Exception as exc:
        # A slow or redirecting login page is not fatal: the operator can still
        # log in in the open window, and polling continues until the timeout.
        _err(f"Warning: opening {url} did not finish loading ({type(exc).__name__}).")


def _wait_for_session(
    spec: SiteSpec,
    context: Any,
    *,
    timeout_s: float,
    headless: bool,
    monotonic: Callable[[], float],
    sleep: Callable[[float], None],
    wall_clock: Callable[[], float],
) -> CapturedSession:
    session = select_session(spec, _read_cookies(context), now_epoch=wall_clock())
    if session is not None:
        _err(f"The saved {spec.title} profile is already logged in; no login needed.")
        return session

    wanted = " and ".join(spec.cookie_names)
    _open_login_page(context, spec.login_url)
    _err(
        f"Log in to {spec.title} in the browser window ({spec.login_url}). Waiting up to "
        f"{timeout_s:g}s for {wanted} on {spec.cookie_domains[0]} ..."
    )
    deadline = monotonic() + timeout_s
    while True:
        session = select_session(spec, _read_cookies(context), now_epoch=wall_clock())
        if session is not None:
            return session
        if monotonic() >= deadline:
            hint = (
                " --headless shows no window to log in with; re-run without it."
                if headless
                else " Re-run and finish the login in the opened window, or raise --timeout."
            )
            raise SessionCaptureError(
                f"Timed out after {timeout_s:g}s waiting for {wanted} on "
                f"{' or '.join(spec.cookie_domains)}.{hint}"
            )
        sleep(POLL_INTERVAL_S)


def capture_session(
    site: str,
    *,
    to: SinkName | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    headless: bool = False,
    browser_factory: BrowserFactory | None = None,
    sink_factory: SinkFactory | None = None,
    http_client: httpx.Client | None = None,
    credentials: CredentialProvider | None = None,
    profiles_root: Path | None = None,
    monotonic: Callable[[], float] | None = None,
    sleep: Callable[[float], None] | None = None,
    wall_clock: Callable[[], float] | None = None,
) -> list[str]:
    """Capture, validate and store one site's session. Returns the keys written.

    Raises :class:`SessionCaptureError` or :class:`SecretSinkError`; neither
    message ever contains a cookie value. The ``None`` seams resolve to the
    module-level defaults at call time (tests replace those).
    """
    spec = SITES[site]
    if timeout_s <= 0:
        raise SessionCaptureError("--timeout must be a positive number of seconds")

    sink_name = to or default_sink_name()
    saved_at_clock = _PinnedClock()
    sink = (sink_factory or default_sink_factory)(sink_name, saved_at_clock)
    # Fail fast (bad OpenBao auth, missing railway CLI, broken secrets file)
    # before the operator spends time logging in.
    sink.check()

    profile = prepare_profile_dir(spec.site, profiles_root)
    _err(f"Using {spec.title} browser profile {profile}")
    open_browser = browser_factory or playwright_persistent_context
    with open_browser(profile, headless) as context:
        session = _wait_for_session(
            spec,
            context,
            timeout_s=timeout_s,
            headless=headless,
            monotonic=monotonic or time.monotonic,
            sleep=sleep or time.sleep,
            wall_clock=wall_clock or time.time,
        )
    _err(f"Captured {', '.join(spec.cookie_names)} from {session.domain}; validating ...")

    owns_client = http_client is None
    http = http_client or new_http_client()
    try:
        spec.validate(session.values, http)
    except httpx.HTTPError as exc:
        raise SessionCaptureError(
            f"Could not reach {spec.title} to validate the session ({type(exc).__name__})"
        ) from None
    finally:
        if owns_client:
            http.close()
    _err(f"{spec.title} accepted the session; writing to {sink.target}.")

    written = sink.write(dict(session.values))

    if sink.name is SinkName.BAO:
        # Make the new values visible to anything else in this process now,
        # stamped with the saved_at the sink just wrote.
        provider = credentials or get_credential_provider()
        try:
            provider.apply_local_write(dict(session.values), saved_at=saved_at_clock.at)
        except Exception as exc:
            _err(
                f"Warning: could not refresh the in-process credential cache ({type(exc).__name__})."
            )
    return written


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

_TO_HELP = (
    "Secret sink: 'bao' (OpenBao KV v2 PATCH on BAO_MOUNT_PATH/BAO_SECRET_PATH, default "
    "secret/newsletter), 'railway' (linked Railway project) or 'secrets-file' "
    "(.secrets.yaml). Default: bao when BAO_ADDR is set, else secrets-file."
)
_TIMEOUT_HELP = "Seconds to wait for the login to produce the session cookies."
_HEADLESS_HELP = (
    "Run Chromium without a window. Only useful when the saved profile is already "
    "logged in; a fresh login needs the window."
)

ToOption = Annotated[SinkName | None, typer.Option("--to", help=_TO_HELP, case_sensitive=False)]
TimeoutOption = Annotated[int, typer.Option("--timeout", min=1, help=_TIMEOUT_HELP)]
HeadlessOption = Annotated[bool, typer.Option("--headless", help=_HEADLESS_HELP)]


def _run(site: str, *, to: SinkName | None, timeout: int, headless: bool) -> None:
    spec = SITES[site]
    try:
        written = capture_session(site, to=to, timeout_s=timeout, headless=headless)
    except (SessionCaptureError, SecretSinkError) as exc:
        _err(f"Error: {exc}")
        raise typer.Exit(1) from None
    typer.echo(f"Done: wrote {', '.join(written)} for {spec.title}.")


@app.command("substack")
def substack_session(
    to: ToOption = None,
    timeout: TimeoutOption = DEFAULT_TIMEOUT_S,
    headless: HeadlessOption = False,
) -> None:
    """Log in to Substack once and store substack.sid as SUBSTACK_SESSION_COOKIE."""
    _run("substack", to=to, timeout=timeout, headless=headless)


@app.command("x")
def x_session(
    to: ToOption = None,
    timeout: TimeoutOption = DEFAULT_TIMEOUT_S,
    headless: HeadlessOption = False,
) -> None:
    """Log in to X once and store auth_token and ct0 as X_AUTH_TOKEN and X_CT0."""
    _run("x", to=to, timeout=timeout, headless=headless)
