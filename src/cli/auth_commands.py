"""CLI commands for OAuth credential management.

Run the OAuth flow locally for Gmail and YouTube. Optionally upload the
resulting token (and the credentials.json file) to Railway as env vars,
so headless cloud deployments don't need filesystem access for OAuth.

Usage:
    aca auth gmail                              # Local OAuth, save token.json
    aca auth gmail --no-browser                 # Print URL; wait on localhost callback
    aca auth gmail --force                      # Re-consent even if a token exists
    aca auth gmail --deploy                     # + upload token to Railway
    aca auth gmail --deploy --include-credentials  # + upload credentials.json
    aca auth youtube                            # Same, for YouTube
    aca auth status                             # Show local + Railway state

The Railway upload uses the ``railway`` CLI, which must be installed and
authenticated (``railway login``) with a project linked (``railway link``).

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
from importlib import import_module
from pathlib import Path
from typing import Annotated

import typer

# The Railway CLI plumbing (set a variable, read the linked target) lives in
# src/cli/railway.py so `aca auth` and `aca deploy sync-secrets` share one
# implementation. Re-exported under the original private names to keep this
# module's existing imports and patch-targets stable.
from src.cli.railway import (
    linked_target as _railway_linked_target,
    set_variable as _railway_set_env,
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


def _hydrate_credentials_file(provider: str, cred_path: Path) -> None:
    """Write client secrets from env JSON when the file is missing."""
    from src.config import settings

    if cred_path.exists():
        return
    raw = getattr(settings, str(PROVIDERS[provider]["credentials_json_setting"]), None)
    if isinstance(raw, str) and raw.strip():
        cred_path.write_text(raw)
        typer.echo(f"Wrote {cred_path} from {PROVIDERS[provider]['credentials_env']}")


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
    return (
        f"Starting {provider} login.\n\n"
        "1. Open this URL in a browser (this machine or any other):\n"
        "   {url}\n\n"
        "2. Sign in and approve access, then return here.\n\n"
        f"SSH/headless: keep this command running and forward the callback:\n"
        f"  ssh -L {OAUTH_CALLBACK_PORT}:127.0.0.1:{OAUTH_CALLBACK_PORT} <this-host>\n"
    )


def _run_oauth_flow(
    provider: str,
    *,
    force: bool = False,
    open_browser: bool = True,
) -> tuple[Path, str]:
    """Run the local OAuth flow and return (token_path, token_json).

    Prints the authorization URL (Codex/Grok login style). The callback
    listens on a fixed localhost port so SSH users can forward it. Interactive
    browser OAuth is CLI-only — workers never call this.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    cred_path, token_path = _get_paths(provider)
    scopes = _provider_scopes(provider)
    _hydrate_credentials_file(provider, cred_path)

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
            f"  3. Save the downloaded JSON as {cred_path}\n"
            f"  Or set {PROVIDERS[provider]['credentials_env']} and re-run.",
            err=True,
        )
        raise typer.Exit(1)

    typer.echo(
        f"Starting {provider} login. "
        + (
            "A browser window will open if this host can open one."
            if open_browser
            else "Browser auto-open is off; copy the URL below."
        )
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
    try:
        creds = flow.run_local_server(port=OAUTH_CALLBACK_PORT, **server_kwargs)
    except OSError as exc:
        typer.echo(
            f"Port {OAUTH_CALLBACK_PORT} is in use ({exc}). Retrying on an ephemeral port.",
            err=True,
        )
        creds = flow.run_local_server(port=0, **server_kwargs)
    token_json: str = creds.to_json()
    token_path.write_text(token_json)
    typer.echo(f"Token saved to {token_path}")
    return token_path, token_json


def _warn_deploy_target(service: str | None) -> None:
    """Surface the two independent sources of truth before pushing secrets.

    ``--deploy`` writes to whatever Railway project ``railway link`` points at,
    which is *independent* of the active profile's ``api_base_url``. Showing
    both prevents pushing OAuth tokens to the wrong project/service.
    """
    from src.config.settings import get_active_profile_name, get_settings

    profile = get_active_profile_name() or "(none)"
    api_base_url = get_settings().api_base_url
    linked = _railway_linked_target()
    linked_desc = linked or "(unknown — railway not linked or CLI unavailable)"
    target_service = service or "(default service)"

    typer.echo(
        "\nDeploy target — please confirm before secrets are pushed:\n"
        f"  Active profile : {profile}  (api_base_url: {api_base_url})\n"
        f"  Railway link   : {linked_desc}\n"
        f"  Railway service: {target_service}\n"
        "  NOTE: --deploy pushes to the *linked Railway project* above, which is\n"
        "  independent of the profile's api_base_url. Make sure they match.\n"
    )


def _do_auth(
    provider: str,
    *,
    deploy: bool,
    include_credentials: bool,
    service: str | None,
    force: bool = False,
    open_browser: bool = True,
) -> None:
    """Shared implementation for `aca auth gmail|youtube`."""
    _token_path, token_json = _run_oauth_flow(provider, force=force, open_browser=open_browser)
    if not deploy:
        typer.echo(
            f"\nNot deploying. To upload this token to Railway, re-run with --deploy.\n"
            f"  aca auth {provider} --deploy"
        )
        return

    _warn_deploy_target(service)

    cfg = PROVIDERS[provider]
    _railway_set_env(str(cfg["token_env"]), token_json, service=service)

    if include_credentials:
        cred_path, _ = _get_paths(provider)
        cred_json = cred_path.read_text()
        _railway_set_env(str(cfg["credentials_env"]), cred_json, service=service)

    typer.echo(
        "\nDone. Restart the Railway service to pick up the new env vars "
        "(railway redeploys automatically on env-var change in most cases)."
    )


@app.command("gmail")
def gmail_auth(
    deploy: Annotated[
        bool,
        typer.Option("--deploy", help="Upload the new token to Railway as GMAIL_OAUTH_TOKEN_JSON"),
    ] = False,
    include_credentials: Annotated[
        bool,
        typer.Option(
            "--include-credentials",
            help="Also upload credentials.json as GMAIL_CREDENTIALS_JSON (needed for fresh deploys)",
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
) -> None:
    """Log in to Gmail (browser or printed URL). With --deploy, push the token to Railway."""
    _do_auth(
        "gmail",
        deploy=deploy,
        include_credentials=include_credentials,
        service=service,
        force=force,
        open_browser=not no_browser,
    )


@app.command("youtube")
def youtube_auth(
    deploy: Annotated[
        bool,
        typer.Option(
            "--deploy", help="Upload the new token to Railway as YOUTUBE_OAUTH_TOKEN_JSON"
        ),
    ] = False,
    include_credentials: Annotated[
        bool,
        typer.Option(
            "--include-credentials",
            help=(
                "Also upload youtube_credentials.json as YOUTUBE_CREDENTIALS_JSON "
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
) -> None:
    """Log in to YouTube (browser or printed URL). With --deploy, push the token to Railway."""
    _do_auth(
        "youtube",
        deploy=deploy,
        include_credentials=include_credentials,
        service=service,
        force=force,
        open_browser=not no_browser,
    )


@app.command("status")
def auth_status() -> None:
    """Show local OAuth state for each provider.

    Reports whether the credentials/token files exist locally and, if the
    railway CLI is available and a project is linked, whether the
    corresponding env vars are set on Railway.
    """
    typer.echo("OAuth credential status:\n")
    railway_vars: str | None = None
    if shutil.which("railway"):
        try:
            result = subprocess.run(
                ["railway", "variables"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if result.returncode == 0:
                railway_vars = result.stdout
        except subprocess.TimeoutExpired:
            railway_vars = None

    for provider, cfg in PROVIDERS.items():
        cred_path, token_path = _get_paths(provider)
        typer.echo(f"  {provider}:")
        typer.echo(
            f"    credentials file: {cred_path} [{'present' if cred_path.exists() else 'missing'}]"
        )
        typer.echo(
            f"    token file:       {token_path} "
            f"[{'present' if token_path.exists() else 'missing'}]"
        )
        token_detail = _describe_token_file(token_path)
        if token_detail:
            typer.echo(f"    {token_detail}")
        if railway_vars is not None:
            token_present = str(cfg["token_env"]) in railway_vars
            cred_present = str(cfg["credentials_env"]) in railway_vars
            typer.echo(f"    Railway {cfg['token_env']}: [{'set' if token_present else 'NOT set'}]")
            typer.echo(
                f"    Railway {cfg['credentials_env']}: [{'set' if cred_present else 'NOT set'}]"
            )
        else:
            typer.echo("    Railway: (not linked or railway CLI unavailable)")
        typer.echo()
