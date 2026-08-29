"""`aca manage restore-from-cloud` — target resolution, safety, decryption.

Two testing choices here are deliberate and worth stating, because the previous
version of this file made the opposite ones:

**The settings fixture is an explicit fake, not a `MagicMock`.** A `MagicMock`
answers every attribute, so a test passes just as happily when the command reads a
setting that does not exist — which is exactly how you fail to notice that a
rename left a reader behind. `FakeSettings` declares the fields the command may
read and nothing else; touching an undeclared one raises.

**Assertions match on invoked argv, never on `call_args_list[N]`.** Positional
indices assert an ORDERING, not a behavior: they break when a stage is added and,
worse, silently assert the wrong call when one is removed. `_invocation("age")`
finds the age call wherever it happens to be.

No subprocess runs and no store is contacted.
"""

from __future__ import annotations

import json
import subprocess
from contextlib import contextmanager
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from src.cli.app import app
from src.cli.restore_commands import (
    DatabaseIdentity,
    _addresses_same_database,
    mask_database_url,
    mask_text,
    split_database_credentials,
)
from src.clients import operational_observability
from src.contracts.operation_context import OperationContext, bind_operation_context

runner = CliRunner()

PROD_URL = "postgresql://aca:prodpass@prod.db.internal:5432/newsletters"
LOCAL_URL = "postgresql://aca:localpass@localhost:5432/newsletters_scratch"


class FakeSettings:
    """Explicit stand-in exposing only the fields the command is allowed to read."""

    _DECLARED = frozenset(
        {
            "backup_s3_endpoint",
            "backup_s3_bucket",
            "backup_s3_region",
            "backup_s3_prefix",
            "backup_s3_access_key_id",
            "backup_s3_secret_access_key",
            "backup_age_identity_path",
            "database_url",
            "railway_database_url",
        }
    )

    def __init__(self, **overrides: Any) -> None:
        values: dict[str, Any] = {
            "backup_s3_endpoint": "https://acct.r2.cloudflarestorage.com",
            "backup_s3_bucket": "aca-backups",
            "backup_s3_region": "auto",
            "backup_s3_prefix": "aca",
            "backup_s3_access_key_id": "AKIAEXAMPLE",
            "backup_s3_secret_access_key": "r2-secret-key",
            "backup_age_identity_path": "/etc/aca/identity.txt",
            "database_url": LOCAL_URL,
            "railway_database_url": None,
        }
        values.update(overrides)
        unknown = set(values) - self._DECLARED
        if unknown:
            raise AssertionError(f"test declared undeclared settings: {sorted(unknown)}")
        self.__dict__.update(values)

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(
            f"restore-from-cloud read undeclared setting {name!r}. "
            "A MagicMock would have returned a Mock and hidden this."
        )


def listing(*keys: str) -> str:
    return json.dumps([{"Path": key, "Name": key.rsplit("/", 1)[-1]} for key in keys])


DEFAULT_LISTING = listing(
    "daily/2026-08-19T030000Z/postgres.dump.age",
    "daily/2026-08-21T030000Z/postgres.dump.age",
)


class Runs:
    """Records subprocess invocations, keyed by program rather than by position."""

    def __init__(self, *, ls_stdout: str = DEFAULT_LISTING, failures: dict[str, int] | None = None):
        self.calls: list[dict[str, Any]] = []
        self._ls_stdout = ls_stdout
        self._failures = failures or {}

    def __call__(self, argv: Any, **kwargs: Any) -> subprocess.CompletedProcess:
        argv = list(argv)
        self.calls.append({"argv": argv, "env": kwargs.get("env") or {}})
        program = argv[0]
        subcommand = argv[1] if len(argv) > 1 else ""
        code = self._failures.get(f"{program} {subcommand}", self._failures.get(program, 0))
        stdout = self._ls_stdout if (program, subcommand) == ("rclone", "lsjson") else ""
        return subprocess.CompletedProcess(args=argv, returncode=code, stdout=stdout, stderr="")

    def invocation(self, program: str, subcommand: str | None = None) -> dict[str, Any] | None:
        for call in self.calls:
            if call["argv"][0] != program:
                continue
            if subcommand is None or (len(call["argv"]) > 1 and call["argv"][1] == subcommand):
                return call
        return None

    @property
    def programs(self) -> list[str]:
        return [call["argv"][0] for call in self.calls]

    def all_argv_text(self) -> str:
        return " ".join(" ".join(map(str, call["argv"])) for call in self.calls)


def invoke(
    args: list[str],
    *,
    settings: FakeSettings | None = None,
    runs: Runs | None = None,
) -> tuple[Any, Runs]:
    runs = runs or Runs()
    with (
        patch("src.cli.restore_commands.get_settings", return_value=settings or FakeSettings()),
        patch("src.cli.restore_commands.subprocess.run", runs),
    ):
        result = runner.invoke(app, args)
    return result, runs


# ---------------------------------------------------------- endpoint-agnostic


class TestEndpointAgnosticRestore:
    def test_it_resolves_the_target_from_the_provider_neutral_settings(self) -> None:
        result, runs = invoke(["manage", "restore-from-cloud", "--yes"])
        assert result.exit_code == 0, result.output
        ls = runs.invocation("rclone", "lsjson")
        assert ls is not None
        assert "aca-backups" in " ".join(ls["argv"])

    @pytest.mark.parametrize(
        ("endpoint", "region"),
        [
            ("https://acct.r2.cloudflarestorage.com", "auto"),
            (None, "us-east-1"),
            ("http://minio.internal:9000", "us-east-1"),
        ],
        ids=["r2", "aws", "minio"],
    )
    def test_every_provider_takes_the_same_code_path(
        self, endpoint: str | None, region: str
    ) -> None:
        """Providers differ in the VALUES of these settings, never in a branch."""
        settings = FakeSettings(backup_s3_endpoint=endpoint, backup_s3_region=region)
        result, runs = invoke(["manage", "restore-from-cloud", "--yes"], settings=settings)
        assert result.exit_code == 0, result.output
        assert runs.programs == ["rclone", "rclone", "age", "pg_restore"]

    def test_it_no_longer_shells_out_to_mc(self) -> None:
        _, runs = invoke(["manage", "restore-from-cloud", "--yes"])
        assert "mc" not in runs.programs

    def test_a_missing_bucket_is_a_named_error(self) -> None:
        settings = FakeSettings(backup_s3_bucket=None)
        result, _ = invoke(["--json", "manage", "restore-from-cloud", "--yes"], settings=settings)
        assert result.exit_code != 0
        assert "BACKUP_S3_BUCKET" in json.loads(result.stdout)["error"]


class TestDiscoveryIsIndependentOfLegacyNaming:
    def test_artifacts_are_found_by_prefix_and_timestamp(self) -> None:
        """No artifact this project writes carries a `railway-` filename prefix."""
        result, runs = invoke(["manage", "restore-from-cloud", "--yes"])
        assert result.exit_code == 0, result.output
        copy = runs.invocation("rclone", "copyto")
        assert copy is not None
        assert "postgres.dump.age" in " ".join(copy["argv"])

    def test_the_latest_backup_is_chosen_by_default(self) -> None:
        _, runs = invoke(["manage", "restore-from-cloud", "--yes"])
        copy = runs.invocation("rclone", "copyto")
        assert copy is not None
        assert "2026-08-21T030000Z" in " ".join(copy["argv"])

    def test_an_explicit_date_selects_that_backup(self) -> None:
        _, runs = invoke(["manage", "restore-from-cloud", "--yes", "--backup-date", "2026-08-19"])
        copy = runs.invocation("rclone", "copyto")
        assert copy is not None
        assert "2026-08-19T030000Z" in " ".join(copy["argv"])

    def test_legacy_railway_named_dumps_are_still_discoverable(self) -> None:
        runs = Runs(ls_stdout=listing("daily/2026-08-20T030000Z/railway-legacy.dump"))
        result, runs = invoke(["manage", "restore-from-cloud", "--yes"], runs=runs)
        assert result.exit_code == 0, result.output

    def test_an_unknown_date_lists_what_is_available(self) -> None:
        result, _ = invoke(
            ["--json", "manage", "restore-from-cloud", "--yes", "--backup-date", "1999-01-01"]
        )
        assert result.exit_code != 0
        assert "2026-08-21" in json.loads(result.stdout)["error"]

    def test_an_empty_target_is_a_named_error(self) -> None:
        runs = Runs(ls_stdout="[]")
        result, _ = invoke(["--json", "manage", "restore-from-cloud", "--yes"], runs=runs)
        assert result.exit_code != 0
        assert "No backup dumps found" in json.loads(result.stdout)["error"]


# ------------------------------------------------------------- security fixes


class TestCredentialsNeverReachArgv:
    def test_no_credential_appears_in_any_invocation(self) -> None:
        """`mc alias set <endpoint> <user> <password>` put the secret in argv,
        which every local user can read out of /proc for the life of the process."""
        _, runs = invoke(["manage", "restore-from-cloud", "--yes"])
        text = runs.all_argv_text()
        for secret in ("r2-secret-key", "AKIAEXAMPLE"):
            assert secret not in text

    def test_the_target_credentials_travel_by_environment(self) -> None:
        _, runs = invoke(["manage", "restore-from-cloud", "--yes"])
        ls = runs.invocation("rclone", "lsjson")
        assert ls is not None
        assert ls["env"]["RCLONE_CONFIG_BACKUP_SECRET_ACCESS_KEY"] == "r2-secret-key"

    def test_the_database_password_never_reaches_any_invocation_at_all(self) -> None:
        """Including `pg_restore`, which this test used to exempt.

        The exemption was the leak: `--dbname <url-with-password>` is argv, and argv
        is world-readable in /proc — the exact defect the `mc alias set` fix removed
        one subprocess earlier in the same command. libpq reads PGPASSWORD from the
        environment instead, which only the process owner can read.
        """
        _, runs = invoke(["manage", "restore-from-cloud", "--yes"])
        assert "localpass" not in runs.all_argv_text()

    def test_pg_restore_still_receives_the_target_database(self) -> None:
        """Moving the password out must not move the TARGET out with it."""
        _, runs = invoke(["manage", "restore-from-cloud", "--yes"])
        restore = runs.invocation("pg_restore")
        assert restore is not None
        argv = " ".join(map(str, restore["argv"]))
        assert "postgresql://aca@localhost:5432/newsletters_scratch" in argv
        assert "--clean" in argv and "--if-exists" in argv

    def test_the_database_password_travels_by_environment(self) -> None:
        _, runs = invoke(["manage", "restore-from-cloud", "--yes"])
        restore = runs.invocation("pg_restore")
        assert restore is not None
        assert restore["env"]["PGPASSWORD"] == "localpass"

    @pytest.mark.parametrize(
        ("url", "expected_argv", "expected_env"),
        [
            (
                "postgresql://u:p@h:5432/d",
                "postgresql://u@h:5432/d",
                {"PGPASSWORD": "p"},
            ),
            ("postgresql://u@h/d", "postgresql://u@h/d", {}),
            ("postgresql://h/d", "postgresql://h/d", {}),
            (
                "postgresql://u:p%40ss@h/d?sslmode=require",
                "postgresql://u@h/d?sslmode=require",
                {"PGPASSWORD": "p@ss"},
            ),
        ],
    )
    def test_splitting_preserves_the_target_and_decodes_the_password(
        self, url: str, expected_argv: str, expected_env: dict[str, str]
    ) -> None:
        """A percent-encoded password must reach libpq DECODED — passing the raw
        `%40` form through PGPASSWORD would authenticate with the wrong string."""
        assert split_database_credentials(url) == (expected_argv, expected_env)

    def test_a_failure_message_cannot_echo_the_password_back(self) -> None:
        """pg_restore quotes its connection string on failure; we quote pg_restore."""
        assert (
            mask_text("could not connect: localpass rejected", LOCAL_URL)
            == "could not connect: *** rejected"
        )


class TestOutputMasksTheTargetDatabase:
    def test_json_output_masks_the_password(self) -> None:
        """A JSON log of a SUCCESSFUL restore previously carried the password."""
        result, _ = invoke(["--json", "manage", "restore-from-cloud", "--yes"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert "localpass" not in json.dumps(payload)
        assert payload["target_db"] == "postgresql://aca:***@localhost:5432/newsletters_scratch"

    def test_human_output_masks_the_password(self) -> None:
        result, _ = invoke(["manage", "restore-from-cloud", "--yes"])
        assert "localpass" not in result.output

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("postgresql://u:p@h:5432/d", "postgresql://u:***@h:5432/d"),
            ("postgresql://u@h/d", "postgresql://u@h/d"),
            ("postgresql://h/d", "postgresql://h/d"),
            ("postgresql://u:p@h/d?sslmode=require", "postgresql://u:***@h/d?sslmode=require"),
        ],
    )
    def test_masking_preserves_everything_but_the_password(self, url: str, expected: str) -> None:
        """The URL is how an operator confirms the restore went where they meant.
        Masking the whole thing would remove the confirmation along with the risk."""
        assert mask_database_url(url) == expected


class TestLiveDatabaseGuardResistsUrlVariation:
    @pytest.mark.parametrize(
        "variant",
        [
            PROD_URL,
            PROD_URL + "/",
            PROD_URL.replace(":5432", ""),
            PROD_URL + "?sslmode=require",
            PROD_URL.replace("prod.db.internal", "PROD.DB.INTERNAL"),
            PROD_URL.replace("prodpass", "different-password"),
            PROD_URL.replace("aca:prodpass@", ""),
        ],
        ids=[
            "identical",
            "trailing-slash",
            "implicit-default-port",
            "extra-query-param",
            "different-host-case",
            "different-password",
            "no-credentials",
        ],
    )
    def test_every_spelling_of_the_production_database_is_refused(self, variant: str) -> None:
        """Each of these defeated `str.strip()` equality while still addressing
        production — and the guarded operation drops objects in the target."""
        settings = FakeSettings(railway_database_url=PROD_URL)
        result, runs = invoke(
            ["--json", "manage", "restore-from-cloud", "--yes", "--target-db", variant],
            settings=settings,
        )
        assert result.exit_code != 0, f"{variant} was NOT refused"
        assert "--allow-remote-target" in json.loads(result.stdout)["error"]
        assert runs.calls == [], "the guard fired after contacting the target"

    def test_a_genuinely_different_database_is_allowed(self) -> None:
        """Over-matching is its own failure: refusing every restore is not safety."""
        settings = FakeSettings(railway_database_url=PROD_URL)
        result, _ = invoke(
            [
                "manage",
                "restore-from-cloud",
                "--yes",
                "--target-db",
                "postgresql://aca:x@localhost:5432/scratch",
            ],
            settings=settings,
        )
        assert result.exit_code == 0, result.output

    def test_a_different_database_on_the_same_host_is_allowed(self) -> None:
        settings = FakeSettings(railway_database_url=PROD_URL)
        result, _ = invoke(
            [
                "manage",
                "restore-from-cloud",
                "--yes",
                "--target-db",
                "postgresql://aca:prodpass@prod.db.internal:5432/scratch",
            ],
            settings=settings,
        )
        assert result.exit_code == 0, result.output

    def test_the_explicit_opt_in_still_works(self) -> None:
        settings = FakeSettings(railway_database_url=PROD_URL)
        result, _ = invoke(
            [
                "manage",
                "restore-from-cloud",
                "--yes",
                "--allow-remote-target",
                "--target-db",
                PROD_URL,
            ],
            settings=settings,
        )
        assert result.exit_code == 0, result.output

    def test_a_local_url_that_points_at_production_is_refused(self) -> None:
        settings = FakeSettings(railway_database_url=PROD_URL, database_url=PROD_URL + "/")
        result, _ = invoke(["--json", "manage", "restore-from-cloud", "--yes"], settings=settings)
        assert result.exit_code != 0
        assert "overwrite production" in json.loads(result.stdout)["error"]

    def test_identity_ignores_everything_that_does_not_select_a_database(self) -> None:
        assert DatabaseIdentity.parse("postgresql://u:p@h:5432/d") == DatabaseIdentity.parse(
            "postgresql://other:secret@h/d?sslmode=require"
        )

    def test_unparseable_urls_never_compare_equal(self) -> None:
        """Two things we cannot identify are not thereby the same thing."""
        assert _addresses_same_database(None, None) is False
        assert _addresses_same_database("", "") is False
        assert _addresses_same_database("not-a-url", "not-a-url") is False


# ------------------------------------------------------------------ decryption


class TestDecryption:
    def test_an_encrypted_artifact_is_decrypted_before_replay(self) -> None:
        _, runs = invoke(["manage", "restore-from-cloud", "--yes"])
        age = runs.invocation("age")
        assert age is not None
        assert "--decrypt" in age["argv"]
        assert "/etc/aca/identity.txt" in age["argv"]

    def test_pg_restore_reads_the_decrypted_file_not_the_ciphertext(self) -> None:
        _, runs = invoke(["manage", "restore-from-cloud", "--yes"])
        pg = runs.invocation("pg_restore")
        assert pg is not None
        assert not any(str(arg).endswith(".age") for arg in pg["argv"])

    def test_a_missing_identity_aborts_naming_the_setting(self) -> None:
        settings = FakeSettings(backup_age_identity_path=None)
        result, runs = invoke(
            ["--json", "manage", "restore-from-cloud", "--yes"], settings=settings
        )
        assert result.exit_code != 0
        assert "BACKUP_AGE_IDENTITY_PATH" in json.loads(result.stdout)["error"]
        assert "pg_restore" not in runs.programs

    def test_a_failed_decryption_aborts_before_pg_restore(self) -> None:
        """Replaying a file that did not decrypt would corrupt the target."""
        runs = Runs(failures={"age": 1})
        result, runs = invoke(["manage", "restore-from-cloud", "--yes"], runs=runs)
        assert result.exit_code != 0
        assert "pg_restore" not in runs.programs

    def test_an_unencrypted_artifact_skips_decryption(self) -> None:
        runs = Runs(ls_stdout=listing("daily/2026-08-20T030000Z/postgres.dump"))
        result, runs = invoke(["manage", "restore-from-cloud", "--yes"], runs=runs)
        assert result.exit_code == 0, result.output
        assert "age" not in runs.programs


# -------------------------------------------------------- retained safeguards


class TestDestructiveRestoreSafeguardsAreRetained:
    def test_pg_restore_still_runs_with_clean_and_if_exists(self) -> None:
        """Retained deliberately. A restore into a database holding stale objects
        produces a silently mixed state, which is worse than a loud one."""
        _, runs = invoke(["manage", "restore-from-cloud", "--yes"])
        pg = runs.invocation("pg_restore")
        assert pg is not None
        assert "--clean" in pg["argv"]
        assert "--if-exists" in pg["argv"]

    def test_interactive_mode_requires_confirmation(self) -> None:
        runs = Runs()
        with (
            patch("src.cli.restore_commands.get_settings", return_value=FakeSettings()),
            patch("src.cli.restore_commands.subprocess.run", runs),
        ):
            result = runner.invoke(app, ["manage", "restore-from-cloud"], input="n\n")
        assert result.exit_code == 0
        assert runs.calls == []

    def test_declining_the_prompt_runs_nothing(self) -> None:
        runs = Runs()
        with (
            patch("src.cli.restore_commands.get_settings", return_value=FakeSettings()),
            patch("src.cli.restore_commands.subprocess.run", runs),
        ):
            runner.invoke(app, ["manage", "restore-from-cloud"], input="n\n")
        assert "pg_restore" not in runs.programs

    def test_the_confirmation_prompt_names_the_destructive_operation(self) -> None:
        with (
            patch("src.cli.restore_commands.get_settings", return_value=FakeSettings()),
            patch("src.cli.restore_commands.subprocess.run", Runs()),
        ):
            result = runner.invoke(app, ["manage", "restore-from-cloud"], input="n\n")
        assert "pg_restore --clean --if-exists" in result.output

    def test_the_confirmation_prompt_masks_the_target_password(self) -> None:
        with (
            patch("src.cli.restore_commands.get_settings", return_value=FakeSettings()),
            patch("src.cli.restore_commands.subprocess.run", Runs()),
        ):
            result = runner.invoke(app, ["manage", "restore-from-cloud"], input="n\n")
        assert "localpass" not in result.output


class TestSubprocessFailuresPropagate:
    @pytest.mark.parametrize("failing", ["rclone lsjson", "rclone copyto", "pg_restore"])
    def test_a_nonzero_exit_fails_the_command(self, failing: str) -> None:
        runs = Runs(failures={failing: 2})
        result, _ = invoke(["manage", "restore-from-cloud", "--yes"], runs=runs)
        assert result.exit_code != 0


class _TraceSpan:
    def __init__(self, name: str, parent: str, attributes: dict[str, Any]) -> None:
        self.name = name
        self.span_id = f"{len(name):016x}"
        self.parent = parent
        self.attributes = attributes


class _TraceProvider:
    def __init__(self) -> None:
        self.stack: list[_TraceSpan] = []
        self.spans: list[_TraceSpan] = []

    @contextmanager
    def start_span(self, name: str, attributes: dict[str, Any] | None = None):
        parent = self.stack[-1].span_id if self.stack else "2222222222222222"
        span = _TraceSpan(name, parent, attributes or {})
        self.spans.append(span)
        self.stack.append(span)
        try:
            yield span
        finally:
            self.stack.pop()


def _restore_context() -> OperationContext:
    return OperationContext(
        schema_version=1,
        operation_id="61",
        root_operation_id="61",
        parent_operation_id=None,
        traceparent="00-11111111111111111111111111111111-2222222222222222-01",
        tracestate=None,
        trace_id="11111111111111111111111111111111",
        span_id="2222222222222222",
        claim_generation="0",
        attempt_number="1",
        entrypoint="cli.manage",
        service_name="aca-cli",
        service_instance_id="cli-1",
        environment="test",
        release_revision="revision",
        stage="restore",
        resource_kind=None,
        resource_key=None,
    )


@pytest.fixture(autouse=True)
def _bind_durable_cli_context():
    """Keep subprocess unit tests isolated without weakening production roots."""
    with bind_operation_context(_restore_context()):
        yield


@pytest.mark.parametrize(
    ("failures", "expected_outcomes"),
    [
        ({}, ["succeeded", "succeeded", "succeeded"]),
        ({"pg_restore": 2}, ["succeeded", "succeeded", "permanent_failure"]),
    ],
)
def test_restore_real_phases_emit_masked_nested_topology(
    monkeypatch: pytest.MonkeyPatch,
    failures: dict[str, int],
    expected_outcomes: list[str],
) -> None:
    provider = _TraceProvider()
    monkeypatch.setattr(operational_observability, "get_provider", lambda: provider)
    with bind_operation_context(_restore_context()):
        result, _ = invoke(
            ["manage", "restore-from-cloud", "--yes"],
            runs=Runs(failures=failures),
        )

    assert result.exit_code == (1 if failures else 0)
    phase_names = {"restore.download", "restore.decrypt", "restore.apply"}
    phases = [span for span in provider.spans if span.name in phase_names]
    outcomes = [span for span in provider.spans if span.name.endswith(".outcome")]
    assert [span.name for span in phases] == [
        "restore.download",
        "restore.decrypt",
        "restore.apply",
    ]
    assert [span.attributes["operation.outcome"] for span in outcomes] == expected_outcomes
    assert [span.parent for span in outcomes] == [span.span_id for span in phases]
    attributes = repr([span.attributes for span in provider.spans])
    assert "localpass" not in attributes
    assert "r2-secret-key" not in attributes
    assert "/etc/aca/identity.txt" not in attributes
