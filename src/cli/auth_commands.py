"""CLI commands for OAuth credential management.

Run the OAuth flow locally for Gmail and YouTube. Optionally upload the
resulting token (and the credentials.json file) to Railway as env vars,
so headless cloud deployments don't need filesystem access for OAuth.

Usage:
    aca auth gmail                              # Local OAuth, save token.json
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

import shutil
import subprocess
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(
    name="auth",
    help="Manage OAuth credentials for Gmail/YouTube ingestion.",
    no_args_is_help=True,
)


# Per-provider configuration. Keeping all per-provider knowledge in one place
# means new providers (Drive, Calendar) can be added by extending this dict
# rather than copy-pasting two near-identical command bodies.
PROVIDERS: dict[str, dict[str, object]] = {
    "gmail": {
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
        "credentials_setting": "gmail_credentials_file",
        "token_setting": "gmail_token_file",
        "credentials_env": "GMAIL_CREDENTIALS_JSON",
        "token_env": "GMAIL_OAUTH_TOKEN_JSON",
    },
    "youtube": {
        "scopes": ["https://www.googleapis.com/auth/youtube.readonly"],
        "credentials_setting": "youtube_credentials_file",
        "token_setting": "youtube_token_file",
        "credentials_env": "YOUTUBE_CREDENTIALS_JSON",
        "token_env": "YOUTUBE_OAUTH_TOKEN_JSON",
    },
}


def _get_paths(provider: str) -> tuple[Path, Path]:
    """Resolve (credentials_path, token_path) from settings."""
    from src.config import settings  # late import — avoids loading settings at module import

    cfg = PROVIDERS[provider]
    cred_path = Path(getattr(settings, str(cfg["credentials_setting"])))
    token_path = Path(getattr(settings, str(cfg["token_setting"])))
    return cred_path, token_path


def _run_oauth_flow(provider: str) -> tuple[Path, str]:
    """Run the local OAuth flow and return (token_path, token_json).

    The OAuth flow opens a browser for the user to authorize the app, then
    receives the redirect on a local port. The resulting token (with refresh
    token) is written to disk and returned as a JSON string.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    cfg = PROVIDERS[provider]
    cred_path, token_path = _get_paths(provider)

    if not cred_path.exists():
        typer.echo(
            f"Credentials file not found at {cred_path}.\n"
            f"  1. Go to https://console.cloud.google.com/apis/credentials\n"
            f"  2. Create or download an OAuth 2.0 Client ID (Desktop type)\n"
            f"  3. Save the downloaded JSON as {cred_path}",
            err=True,
        )
        raise typer.Exit(1)

    typer.echo(
        f"Starting {provider} OAuth flow — a browser window will open. "
        "Sign in with the Google account that owns the data you want to ingest."
    )
    flow = InstalledAppFlow.from_client_secrets_file(str(cred_path), cfg["scopes"])  # type: ignore[arg-type]
    creds = flow.run_local_server(port=0)
    token_json: str = creds.to_json()
    token_path.write_text(token_json)
    typer.echo(f"Token saved to {token_path}")
    return token_path, token_json


def _railway_set_env(key: str, value: str, service: str | None = None) -> None:
    """Set a Railway env var via ``railway variables --set KEY=VALUE``.

    Requires either ``railway link`` to have been run in the current
    directory, OR ``RAILWAY_TOKEN`` to be set in the environment. The
    railway CLI itself must be installed.

    We do not echo the value back — env vars set via this path are
    typically multi-kilobyte JSON blobs that would flood the terminal.
    """
    if not shutil.which("railway"):
        typer.echo(
            "railway CLI not found in PATH. Install with:\n"
            "  brew install railway     (macOS)\n"
            "  npm install -g @railway/cli\n"
            "Or see https://docs.railway.com/guides/cli",
            err=True,
        )
        raise typer.Exit(1)

    cmd = ["railway", "variables", "--set", f"{key}={value}"]
    if service:
        cmd.extend(["--service", service])

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        typer.echo(
            f"`railway variables --set {key}=...` failed (exit {e.returncode}):\n"
            f"  stderr: {e.stderr.strip() or '(empty)'}\n"
            "Make sure you've run `railway link` in this directory or set RAILWAY_TOKEN.",
            err=True,
        )
        raise typer.Exit(1) from e

    target = f" on service {service}" if service else ""
    typer.echo(f"Railway env var {key} set{target}.")


def _railway_linked_target() -> str | None:
    """Return a short description of the currently-linked Railway target.

    Reads ``railway status --json`` (project / environment / service). Returns
    None when the railway CLI is missing, not linked, or the output can't be
    parsed. Best-effort — never raises.
    """
    if not shutil.which("railway"):
        return None
    try:
        result = subprocess.run(
            ["railway", "status", "--json"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        import json

        data = json.loads(result.stdout)
    except (ValueError, TypeError):
        return None

    def _name(value: object) -> str | None:
        if isinstance(value, dict):
            name = value.get("name")
            return str(name) if name else None
        return str(value) if value else None

    project = _name(data.get("name")) or _name(data.get("project"))
    environment = _name(data.get("environment"))
    parts = [p for p in (project, environment) if p]
    return " / ".join(parts) if parts else None


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
) -> None:
    """Shared implementation for `aca auth gmail|youtube`."""
    _token_path, token_json = _run_oauth_flow(provider)
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
) -> None:
    """Run Gmail OAuth flow locally. With --deploy, also push the token to Railway."""
    _do_auth("gmail", deploy=deploy, include_credentials=include_credentials, service=service)


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
) -> None:
    """Run YouTube OAuth flow locally. With --deploy, also push the token to Railway."""
    _do_auth("youtube", deploy=deploy, include_credentials=include_credentials, service=service)


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
