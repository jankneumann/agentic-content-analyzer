"""CLI commands for OAuth credential management.

Run the OAuth flow locally for Gmail and YouTube. Optionally push the
resulting token (and the credentials.json file) to a secret sink so headless
deployments don't need filesystem access for OAuth.

Usage:
    aca auth gmail                              # Local OAuth, save token.json
    aca auth gmail --no-browser                 # Print URL; wait on localhost callback
    aca auth gmail --force                      # Re-consent even if a token exists
    aca auth gmail --to bao                     # + PATCH token into OpenBao secret/newsletter
    aca auth gmail --to railway                 # + set token as a Railway variable
    aca auth gmail --to secrets-file            # + upsert token into .secrets.yaml
    aca auth gmail --to railway --include-credentials  # + push credentials.json too
    aca auth gmail --deploy                     # DEPRECATED alias for --to railway
    aca auth youtube                            # Same, for YouTube
    aca auth status                             # OAuth + Railway + browser-session state
    aca auth status --json                      # Same, as one JSON document (no values)

Sinks live in ``src/cli/secret_sinks.py``. The Railway sink uses the
``railway`` CLI, which must be installed and authenticated (``railway login``)
with a project linked (``railway link``). The OpenBao sink needs ``BAO_ADDR``
plus AppRole or token credentials and an existing KV v2 secret.

Why these env-var names matter: the corresponding settings
(``gmail_oauth_token_json``, ``youtube_oauth_token_json``, etc.) are
consumed by ``GmailClient``/``YouTubeClient`` at startup — they hydrate
the token/credentials file on disk if it doesn't already exist. So
setting the env var on Railway makes OAuth work without ever needing to
ssh in and write a file.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from importlib import import_module
from pathlib import Path
from typing import Annotated, cast

import typer

# The Railway CLI plumbing (set a variable, read the linked target) lives in
# src/cli/railway.py so `aca auth` and `aca deploy sync-secrets` share one
# implementation. Re-exported under the original private names to keep this
# module's existing imports and patch-targets stable.
from src.cli.railway import (
    linked_target as _railway_linked_target,
    set_variable as _railway_set_env,  # noqa: F401 — stable import/patch target
)
from src.cli.secret_sinks import (
    SecretSink,
    SecretSinkError,
    SinkName,
    build_sink,
    echo_railway_target_notice,
)

app = typer.Typer(
    name="auth",
    help="Manage OAuth credentials for Gmail/YouTube ingestion.",
    no_args_is_help=True,
)


# Per-provider configuration. Keeping all per-provider knowledge in one place
# means new providers (Drive, Calendar) can be added by extending this dict
# rather than copy-pasting two near-identical command bodies.
# Fixed loopback port so SSH users can forward one well-known callback,
# the same idea as `codex login` on localhost:1455.
OAUTH_CALLBACK_PORT = 8091

PROVIDERS: dict[str, dict[str, object]] = {
    "gmail": {
        "scopes_attr": "src.ingestion.gmail.SCOPES",
        "credentials_setting": "gmail_credentials_file",
        "token_setting": "gmail_token_file",
        "credentials_json_setting": "gmail_credentials_json",
        "credentials_env": "GMAIL_CREDENTIALS_JSON",
        "token_env": "GMAIL_OAUTH_TOKEN_JSON",
    },
    "youtube": {
        "scopes_attr": "src.ingestion.youtube.SCOPES",
        "credentials_setting": "youtube_credentials_file",
        "token_setting": "youtube_token_file",
        "credentials_json_setting": "youtube_credentials_json",
        "credentials_env": "YOUTUBE_CREDENTIALS_JSON",
        "token_env": "YOUTUBE_OAUTH_TOKEN_JSON",
    },
}


def _provider_scopes(provider: str) -> list[str]:
    module_path, attr = str(PROVIDERS[provider]["scopes_attr"]).rsplit(".", 1)
    return list(getattr(import_module(module_path), attr))


def _describe_token_file(token_path: Path) -> str | None:
    """Human summary of a local OAuth token. Never prints secret values."""
    if not token_path.exists():
        return None
    try:
        data = json.loads(token_path.read_text())
    except (OSError, json.JSONDecodeError):
        return "token: unreadable"
    if not isinstance(data, dict):
        return "token: unreadable"
    refresh = "present" if data.get("refresh_token") else "missing"
    expiry = data.get("expiry")
    expiry_bit = f", expiry {expiry}" if isinstance(expiry, str) and expiry else ""
    return f"refresh token: {refresh}{expiry_bit}"


def _get_paths(provider: str) -> tuple[Path, Path]:
    """Resolve (credentials_path, token_path) from settings."""
    from src.config import settings  # late import — avoids loading settings at module import

    cfg = PROVIDERS[provider]
    cred_path = Path(getattr(settings, str(cfg["credentials_setting"])))
    token_path = Path(getattr(settings, str(cfg["token_setting"])))
    return cred_path, token_path


def _parse_oauth_client_json(raw: str) -> str:
    """Validate Google OAuth client JSON without logging secrets."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Credentials JSON is not valid JSON") from exc
    if not isinstance(data, dict) or ("installed" not in data and "web" not in data):
        raise ValueError(
            "OAuth client JSON must be a Desktop (installed) or web client download "
            "from Google Cloud Console"
        )
    return json.dumps(data)


def _read_credentials_json_arg(value: str | None) -> str | None:
    if value is None:
        return None
    if value.strip() == "-":
        return sys.stdin.read()
    return value


def _hydrate_credentials_file(
    provider: str,
    cred_path: Path,
    *,
    credentials_json: str | None = None,
) -> None:
    """Write client secrets from an explicit paste, env JSON, or an existing file."""
    from src.config import settings

    raw = _read_credentials_json_arg(credentials_json)
    source = "--credentials-json"
    if raw is None:
        if cred_path.exists():
            return
        env_raw = getattr(settings, str(PROVIDERS[provider]["credentials_json_setting"]), None)
        if isinstance(env_raw, str) and env_raw.strip():
            raw = env_raw
            source = str(PROVIDERS[provider]["credentials_env"])
    if raw is None:
        return
    try:
        normalized = _parse_oauth_client_json(raw)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    cred_path.write_text(normalized)
    typer.echo(f"Wrote {cred_path} from {source}")


def _existing_token_json(token_path: Path, scopes: list[str]) -> str | None:
    """Return a still-usable token JSON, refreshing if needed. None = must re-login."""
    if not token_path.exists():
        return None
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    try:
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)
    except (ValueError, OSError):
        return None
    if creds.valid:
        return creds.to_json()
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            return None
        token_path.write_text(creds.to_json())
        return creds.to_json()
    return None


def _login_prompt(provider: str) -> str:
    """Codex-style instructions. ``{url}`` is filled by InstalledAppFlow."""
    return f"\n=== {provider} login ===\nOpen this URL:\n{{url}}\n"


def _print_auth_message(*args: object, **kwargs: object) -> None:
    """Flush Google's login prompt to stderr so a piped/SSH TTY still shows the URL."""
    text = " ".join(str(arg) for arg in args)
    sys.stderr.write(text)
    if not text.endswith("\n"):
        sys.stderr.write("\n")
    sys.stderr.flush()
    for token in text.replace("\n", " ").split():
        if token.startswith("https://"):
            typer.echo("\nOpen this URL:\n" + token + "\n", err=True)


def _run_oauth_flow(
    provider: str,
    *,
    force: bool = False,
    open_browser: bool = True,
    credentials_json: str | None = None,
) -> tuple[Path, str]:
    """Run the local OAuth flow and return (token_path, token_json).

    Prints the authorization URL (Codex/Grok login style). The callback
    listens on a fixed localhost port so SSH users can forward it. Interactive
    browser OAuth is CLI-only — workers never call this.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    cred_path, token_path = _get_paths(provider)
    scopes = _provider_scopes(provider)
    _hydrate_credentials_file(provider, cred_path, credentials_json=credentials_json)

    if not force:
        existing = _existing_token_json(token_path, scopes)
        if existing is not None:
            typer.echo(f"{provider} already has a valid token at {token_path}")
            return token_path, existing

    if not cred_path.exists():
        typer.echo(
            f"Credentials file not found at {cred_path}.\n"
            f"  1. Go to https://console.cloud.google.com/apis/credentials\n"
            f"  2. Create or download an OAuth 2.0 Client ID (Desktop type)\n"
            f"  3. Paste it (no SCP required):\n"
            f"       aca auth {provider} --credentials-json - --no-browser\n"
            f"     then paste the JSON and press Ctrl-D\n"
            f"  Or save the downloaded JSON as {cred_path}\n"
            f"  Or set {PROVIDERS[provider]['credentials_env']} and re-run.",
            err=True,
        )
        raise typer.Exit(1)

    typer.echo(
        f"Starting {provider} login. "
        + (
            "A browser window will open if this host can open one."
            if open_browser
            else "Browser auto-open is off; the authorization URL prints next."
        ),
        err=True,
    )
    flow = InstalledAppFlow.from_client_secrets_file(str(cred_path), scopes)
    server_kwargs = {
        "host": "127.0.0.1",
        "open_browser": open_browser,
        "authorization_prompt_message": _login_prompt(provider),
        "success_message": "Authorization complete. You can close this tab.",
        "access_type": "offline",
        "prompt": "consent",
    }
    import builtins

    orig_print = builtins.print
    builtins.print = _print_auth_message  # type: ignore[assignment]
    try:
        try:
            creds = flow.run_local_server(port=OAUTH_CALLBACK_PORT, **server_kwargs)
        except OSError as exc:
            typer.echo(
                f"Port {OAUTH_CALLBACK_PORT} is in use ({exc}). "
                "Retrying on an ephemeral port — use the port in the URL, not 8091.",
                err=True,
            )
            creds = flow.run_local_server(port=0, **server_kwargs)
    finally:
        builtins.print = orig_print
    token_json: str = creds.to_json()
    token_path.write_text(token_json)
    typer.echo(f"Token saved to {token_path}")
    return token_path, token_json


def _warn_deploy_target(service: str | None) -> None:
    """Surface the linked Railway target vs. the active profile before a push.

    Kept for callers/tests; the Railway sink prints the same notice from
    ``SecretSink.check()`` before the OAuth flow starts.
    """
    echo_railway_target_notice(service, _railway_linked_target())


_DEPLOY_DEPRECATION = (
    "Warning: --deploy is deprecated and will be removed in a future release; "
    "use --to railway instead."
)


def _resolve_sink(
    to: SinkName | None,
    *,
    deploy: bool,
    service: str | None,
) -> SecretSink | None:
    """Map ``--to``/``--deploy``/``--service`` to a sink (None = local only)."""
    if deploy:
        typer.echo(_DEPLOY_DEPRECATION, err=True)
        if to is not None and to is not SinkName.RAILWAY:
            typer.echo(f"--deploy (= --to railway) conflicts with --to {to.value}.", err=True)
            raise typer.Exit(2)
        to = SinkName.RAILWAY
    if to is None:
        return None
    if service and to is not SinkName.RAILWAY:
        typer.echo(f"--service only applies to --to railway, not --to {to.value}.", err=True)
        raise typer.Exit(2)
    return build_sink(to, service=service)


def _do_auth(
    provider: str,
    *,
    include_credentials: bool,
    service: str | None,
    to: SinkName | None = None,
    deploy: bool = False,
    force: bool = False,
    open_browser: bool = True,
    credentials_json: str | None = None,
) -> None:
    """Shared implementation for `aca auth gmail|youtube`.

    Provider-agnostic: the provider only contributes env-var names from
    ``PROVIDERS``; the sink decides where the values go.
    """
    sink = _resolve_sink(to, deploy=deploy, service=service)
    if sink is not None:
        # Fail fast (missing CLI, bad OpenBao auth, unparsable secrets file)
        # before the operator clicks through a browser consent screen.
        try:
            sink.check()
        except SecretSinkError as exc:
            typer.echo(f"Cannot use --to {sink.name.value}: {exc}", err=True)
            raise typer.Exit(1) from exc

    _token_path, token_json = _run_oauth_flow(
        provider,
        force=force,
        open_browser=open_browser,
        credentials_json=credentials_json,
    )
    if sink is None:
        typer.echo(
            "\nNot pushing this token anywhere (saved locally only). To push it, re-run with\n"
            f"  aca auth {provider} --to railway|bao|secrets-file\n"
            "(--deploy is a deprecated alias for --to railway)"
        )
        return

    cfg = PROVIDERS[provider]
    try:
        sink.write({str(cfg["token_env"]): token_json})
        if include_credentials:
            cred_path, _ = _get_paths(provider)
            sink.write({str(cfg["credentials_env"]): cred_path.read_text()})
    except SecretSinkError as exc:
        typer.echo(f"Error writing to {sink.target}: {exc}", err=True)
        raise typer.Exit(1) from exc

    typer.echo(f"\nDone. {sink.next_step_hint}")


_TO_HELP = (
    "Push the token to a secret sink: 'bao' (OpenBao KV v2 PATCH on "
    "BAO_MOUNT_PATH/BAO_SECRET_PATH, default secret/newsletter), 'railway' "
    "(linked Railway project), or 'secrets-file' (.secrets.yaml). Default: local token only."
)


@app.command("gmail")
def gmail_auth(
    to: Annotated[
        SinkName | None,
        typer.Option("--to", help=_TO_HELP, case_sensitive=False),
    ] = None,
    deploy: Annotated[
        bool,
        typer.Option("--deploy", help="DEPRECATED: alias for --to railway"),
    ] = False,
    include_credentials: Annotated[
        bool,
        typer.Option(
            "--include-credentials",
            help="Also push credentials.json as GMAIL_CREDENTIALS_JSON (needed for fresh deploys)",
        ),
    ] = False,
    service: Annotated[
        str | None,
        typer.Option("--service", help="Railway service name (if your project has multiple)"),
    ] = None,
    no_browser: Annotated[
        bool,
        typer.Option(
            "--no-browser",
            help="Do not open a browser; print the URL (use with SSH port-forward of 8091)",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Re-consent even if a valid token already exists"),
    ] = False,
    credentials_json: Annotated[
        str | None,
        typer.Option(
            "--credentials-json",
            help=(
                "Google Desktop OAuth client JSON (the downloaded credentials.json). "
                "Pass '-' to read from stdin so you can paste instead of copying a file."
            ),
        ),
    ] = None,
) -> None:
    """Log in to Gmail (browser or printed URL). With --to, push the token to a secret sink."""
    _do_auth(
        "gmail",
        to=to,
        deploy=deploy,
        include_credentials=include_credentials,
        service=service,
        force=force,
        open_browser=not no_browser,
        credentials_json=credentials_json,
    )


@app.command("youtube")
def youtube_auth(
    to: Annotated[
        SinkName | None,
        typer.Option("--to", help=_TO_HELP, case_sensitive=False),
    ] = None,
    deploy: Annotated[
        bool,
        typer.Option("--deploy", help="DEPRECATED: alias for --to railway"),
    ] = False,
    include_credentials: Annotated[
        bool,
        typer.Option(
            "--include-credentials",
            help=(
                "Also push youtube_credentials.json as YOUTUBE_CREDENTIALS_JSON "
                "(needed for fresh deploys)"
            ),
        ),
    ] = False,
    service: Annotated[
        str | None,
        typer.Option("--service", help="Railway service name (if your project has multiple)"),
    ] = None,
    no_browser: Annotated[
        bool,
        typer.Option(
            "--no-browser",
            help="Do not open a browser; print the URL (use with SSH port-forward of 8091)",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Re-consent even if a valid token already exists"),
    ] = False,
    credentials_json: Annotated[
        str | None,
        typer.Option(
            "--credentials-json",
            help=(
                "Google Desktop OAuth client JSON (the downloaded credentials.json). "
                "Pass '-' to read from stdin so you can paste instead of copying a file."
            ),
        ),
    ] = None,
) -> None:
    """Log in to YouTube (browser or printed URL). With --to, push the token to a secret sink."""
    _do_auth(
        "youtube",
        to=to,
        deploy=deploy,
        include_credentials=include_credentials,
        service=service,
        force=force,
        open_browser=not no_browser,
        credentials_json=credentials_json,
    )


def _railway_variable_listing() -> str | None:
    """Raw ``railway variables`` output, or None when unavailable.

    The listing includes secret VALUES; callers may only test names against it.
    """
    if not shutil.which("railway"):
        return None
    try:
        result = subprocess.run(
            ["railway", "variables"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None
    return result.stdout if result.returncode == 0 else None


def _oauth_status_rows(railway_vars: str | None) -> list[dict[str, object]]:
    """JSON-safe OAuth rows: paths, presence flags and variable names only."""
    rows: list[dict[str, object]] = []
    for provider, cfg in PROVIDERS.items():
        cred_path, token_path = _get_paths(provider)
        railway: dict[str, object] | None = None
        if railway_vars is not None:
            token_env, cred_env = str(cfg["token_env"]), str(cfg["credentials_env"])
            railway = {
                "token_env": token_env,
                "token_set": token_env in railway_vars,
                "credentials_env": cred_env,
                "credentials_set": cred_env in railway_vars,
            }
        rows.append(
            {
                "provider": provider,
                "credentials_file": {"path": str(cred_path), "present": cred_path.exists()},
                "token_file": {"path": str(token_path), "present": token_path.exists()},
                "token_detail": _describe_token_file(token_path),
                "railway": railway,
            }
        )
    return rows


def _render_oauth_rows(rows: list[dict[str, object]]) -> None:
    typer.echo("OAuth credential status:\n")
    for row in rows:
        cred_file = cast(dict[str, object], row["credentials_file"])
        token_file = cast(dict[str, object], row["token_file"])
        typer.echo(f"  {row['provider']}:")
        typer.echo(
            f"    credentials file: {cred_file['path']} "
            f"[{'present' if cred_file['present'] else 'missing'}]"
        )
        typer.echo(
            f"    token file:       {token_file['path']} "
            f"[{'present' if token_file['present'] else 'missing'}]"
        )
        if row["token_detail"]:
            typer.echo(f"    {row['token_detail']}")
        railway = cast(dict[str, object] | None, row["railway"])
        if railway is not None:
            typer.echo(
                f"    Railway {railway['token_env']}: "
                f"[{'set' if railway['token_set'] else 'NOT set'}]"
            )
            typer.echo(
                f"    Railway {railway['credentials_env']}: "
                f"[{'set' if railway['credentials_set'] else 'NOT set'}]"
            )
        else:
            typer.echo("    Railway: (not linked or railway CLI unavailable)")
        typer.echo()


@app.command("status")
def auth_status(
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Print one JSON document (no credential values); diagnostics go to stderr.",
        ),
    ] = False,
) -> None:
    """Show OAuth and browser-session credential state.

    Reports whether the OAuth credentials/token files exist locally and, if
    the railway CLI is available and a project is linked, whether the
    corresponding env vars are set on Railway. Then one row per browser
    session (substack, x): present/missing, source, saved_at,
    last_verified_at (latest successful ingestion of the gated source) and
    the refresh command. Never prints a credential value.
    """
    from src.cli.browser_session_status import build_session_rows, render_session_rows
    from src.cli.output import is_json_mode

    as_json = json_output or is_json_mode()
    oauth_rows = _oauth_status_rows(_railway_variable_listing())
    session_rows, verification = build_session_rows()

    if as_json:
        if not verification.available:
            typer.echo(
                f"last_verified_at unavailable: {verification.reason}",
                err=True,
            )
        typer.echo(
            json.dumps(
                {
                    "oauth": oauth_rows,
                    "browser_sessions": session_rows,
                    "last_verified_lookup": {
                        "available": verification.available,
                        "via": verification.via,
                        "reason": verification.reason,
                    },
                }
            )
        )
        return

    _render_oauth_rows(oauth_rows)
    render_session_rows(session_rows, verification, typer.echo)
    if not verification.available:
        typer.echo(
            f"Note: last_verified_at is unknown ({verification.reason}).",
            err=True,
        )
