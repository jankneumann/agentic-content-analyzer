"""CLI commands for prompt management.

Usage:
    aca prompts list
    aca prompts show <key>
    aca prompts set <key> --value "..."
    aca prompts set <key> --file prompt.txt
    aca prompts reset <key>
    aca prompts export --output prompts.yaml
    aca prompts import --file prompts.yaml
    aca prompts test <key> --var title=Test --var period=daily
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from src.cli.output import is_json_mode, output_result

app = typer.Typer(
    name="prompts",
    help="Manage LLM prompt templates and overrides.",
    no_args_is_help=True,
)


@app.command("list")
def list_prompts(
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="Filter by category (chat, pipeline)"),
    ] = None,
    overrides_only: Annotated[
        bool,
        typer.Option("--overrides-only", "-o", help="Show only prompts with overrides"),
    ] = False,
) -> None:
    """List all prompts with their override status.

    Shows prompt keys, categories, and whether they have user overrides.
    """
    from src.services.prompt_service import PromptService
    from src.storage.database import get_db

    with get_db() as db:
        service = PromptService(db)
        all_prompts = service.list_all_prompts()

    # Apply filters
    if category:
        all_prompts = [p for p in all_prompts if p["category"] == category]
    if overrides_only:
        all_prompts = [p for p in all_prompts if p["has_override"]]

    if is_json_mode():
        output_result({"prompts": all_prompts, "count": len(all_prompts)})
        return

    if not all_prompts:
        typer.echo("No prompts found matching filters.")
        return

    # Group by category and step
    current_category = ""
    current_step = ""

    for p in all_prompts:
        # Print category header
        if p["category"] != current_category:
            current_category = p["category"]
            typer.echo()
            typer.echo(typer.style(f"  {current_category.upper()}", bold=True))

        # Print step header
        if p["step"] != current_step:
            current_step = p["step"]
            display_step = current_step.replace("_", " ").title()
            typer.echo(typer.style(f"    {display_step}:", dim=True))

        # Build status indicator
        if p["has_override"]:
            badge = typer.style(" [override]", fg=typer.colors.YELLOW)
            version_str = f" v{p['version']}" if p["version"] else ""
        else:
            badge = ""
            version_str = ""

        # Truncate default for display
        preview = p["default"][:60].replace("\n", " ")
        if len(p["default"]) > 60:
            preview += "..."

        typer.echo(f"      {p['key']}{badge}{version_str}")
        typer.echo(typer.style(f"        {preview}", dim=True))

    typer.echo()
    typer.echo(f"Total: {len(all_prompts)} prompts")


@app.command("show")
def show_prompt(
    key: Annotated[str, typer.Argument(help="Prompt key (e.g., pipeline.summarization.system)")],
    default: Annotated[
        bool,
        typer.Option("--default", "-d", help="Show default value even if override exists"),
    ] = False,
) -> None:
    """Show the full value of a prompt.

    Displays the current effective value, or the default if --default is used.
    """
    from src.services.prompt_service import PromptService
    from src.storage.database import get_db

    with get_db() as db:
        service = PromptService(db)
        override = service.get_override(key)
        default_value = service.get_default(key)

    if not default_value:
        typer.echo(typer.style(f"Prompt not found: {key}", fg=typer.colors.RED))
        raise typer.Exit(1)

    if is_json_mode():
        output_result(
            {
                "key": key,
                "default_value": default_value,
                "override_value": override.value if override else None,
                "has_override": override is not None,
                "version": override.version if override else None,
                "description": override.description if override else None,
            }
        )
        return

    typer.echo(typer.style(f"Key: {key}", bold=True))

    if override and not default:
        typer.echo(typer.style("Status: override active", fg=typer.colors.YELLOW))
        typer.echo(f"Version: {override.version}")
        if override.description:
            typer.echo(f"Description: {override.description}")
        typer.echo()
        typer.echo(override.value)
    else:
        if override:
            typer.echo(typer.style("Status: showing default (override exists)", dim=True))
        else:
            typer.echo(typer.style("Status: default (no override)", dim=True))
        typer.echo()
        typer.echo(default_value)


@app.command("set")
def set_prompt(
    key: Annotated[str, typer.Argument(help="Prompt key to override")],
    value: Annotated[
        str | None,
        typer.Option("--value", "-v", help="New prompt value"),
    ] = None,
    file: Annotated[
        Path | None,
        typer.Option("--file", "-f", help="Read prompt value from file"),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--desc", "-d", help="Description of the change"),
    ] = None,
) -> None:
    """Set a prompt override.

    Provide the value inline with --value or from a file with --file.
    """
    from src.services.prompt_service import PromptService
    from src.storage.database import get_db

    if value is None and file is None:
        typer.echo(typer.style("Error: provide --value or --file", fg=typer.colors.RED))
        raise typer.Exit(1)

    if value is not None and file is not None:
        typer.echo(typer.style("Error: provide --value or --file, not both", fg=typer.colors.RED))
        raise typer.Exit(1)

    if file is not None:
        if not file.exists():
            typer.echo(typer.style(f"File not found: {file}", fg=typer.colors.RED))
            raise typer.Exit(1)
        value = file.read_text()

    with get_db() as db:
        service = PromptService(db)

        # Validate key exists
        default_value = service.get_default(key)
        if not default_value:
            typer.echo(typer.style(f"Prompt not found: {key}", fg=typer.colors.RED))
            raise typer.Exit(1)

        service.set_override(key, value, description=description)  # type: ignore[arg-type]
        override = service.get_override(key)

    if is_json_mode():
        output_result(
            {
                "key": key,
                "has_override": True,
                "version": override.version if override else 1,
            }
        )
        return

    version = override.version if override else 1
    typer.echo(typer.style(f"Override set for {key} (v{version})", fg=typer.colors.GREEN))


@app.command("reset")
def reset_prompt(
    key: Annotated[str, typer.Argument(help="Prompt key to reset")],
) -> None:
    """Reset a prompt override, reverting to the default value."""
    from src.services.prompt_service import PromptService
    from src.storage.database import get_db

    with get_db() as db:
        service = PromptService(db)
        service.clear_override(key)

    if is_json_mode():
        output_result({"key": key, "has_override": False})
        return

    typer.echo(typer.style(f"Override cleared for {key}", fg=typer.colors.GREEN))


@app.command("export")
def export_prompts(
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output file path"),
    ] = Path("prompts-export.yaml"),
    overrides_only: Annotated[
        bool,
        typer.Option("--overrides-only", help="Export only overridden prompts"),
    ] = False,
) -> None:
    """Export prompts to a YAML file.

    Exports all prompts (or only overrides) for backup or migration.
    """
    import yaml  # type: ignore[import-untyped]

    from src.services.prompt_service import PromptService
    from src.storage.database import get_db

    with get_db() as db:
        service = PromptService(db)
        all_prompts = service.list_all_prompts()

    if overrides_only:
        all_prompts = [p for p in all_prompts if p["has_override"]]

    # Build export structure
    export_data: dict[str, dict] = {}
    for p in all_prompts:
        value = p["override"] if p["has_override"] else p["default"]
        parts = p["key"].split(".")
        category, step, name = parts[0], parts[1], ".".join(parts[2:])

        if category not in export_data:
            export_data[category] = {}
        if step not in export_data[category]:
            export_data[category][step] = {}
        export_data[category][step][name] = value

    output.write_text(yaml.dump(export_data, default_flow_style=False, sort_keys=False))

    if is_json_mode():
        output_result({"file": str(output), "count": len(all_prompts)})
        return

    typer.echo(
        typer.style(f"Exported {len(all_prompts)} prompts to {output}", fg=typer.colors.GREEN)
    )


@app.command("import")
def import_prompts(
    file: Annotated[
        Path,
        typer.Option("--file", "-f", help="YAML file to import"),
    ],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Show what would be imported without saving"),
    ] = False,
) -> None:
    """Import prompt overrides from a YAML file.

    The file should have the same structure as prompts.yaml (category.step.name).
    Only values that differ from defaults are saved as overrides.
    """
    import yaml  # type: ignore[import-untyped]

    from src.services.prompt_service import PromptService
    from src.storage.database import get_db

    if not file.exists():
        typer.echo(typer.style(f"File not found: {file}", fg=typer.colors.RED))
        raise typer.Exit(1)

    import_data = yaml.safe_load(file.read_text()) or {}

    # Flatten the nested structure to key-value pairs
    overrides_to_set: list[tuple[str, str]] = []
    for category, steps in import_data.items():
        if not isinstance(steps, dict):
            continue
        for step, prompts in steps.items():
            if not isinstance(prompts, dict):
                continue
            for name, value in prompts.items():
                key = f"{category}.{step}.{name}"
                overrides_to_set.append((key, str(value)))

    if dry_run:
        if is_json_mode():
            output_result(
                {"would_import": [{"key": k, "preview": v[:80]} for k, v in overrides_to_set]}
            )
            return

        typer.echo("Would import the following overrides:")
        for key, value in overrides_to_set:
            preview = value[:60].replace("\n", " ")
            typer.echo(f"  {key}: {preview}...")
        typer.echo(f"\nTotal: {len(overrides_to_set)} overrides (dry run, nothing saved)")
        return

    with get_db() as db:
        service = PromptService(db)
        imported = 0
        skipped = 0

        for key, value in overrides_to_set:
            default = service.get_default(key)
            if not default:
                typer.echo(typer.style(f"  Skipping unknown key: {key}", dim=True))
                skipped += 1
                continue

            # Only save as override if different from default
            if value != default:
                service.set_override(key, value, description="Imported from file")
                imported += 1
            else:
                skipped += 1

    if is_json_mode():
        output_result({"imported": imported, "skipped": skipped})
        return

    typer.echo(
        typer.style(f"Imported {imported} overrides ({skipped} skipped)", fg=typer.colors.GREEN)
    )


@app.command("test")
def test_prompt(
    key: Annotated[str, typer.Argument(help="Prompt key to test")],
    var: Annotated[
        list[str] | None,
        typer.Option("--var", "-v", help="Variable in key=value format (repeatable)"),
    ] = None,
) -> None:
    """Test a prompt template by rendering it with variables.

    Variables are provided as --var key=value pairs. Unset variables
    are left as {placeholder} in the output.
    """
    from src.services.prompt_service import PromptService
    from src.storage.database import get_db

    # Parse variables
    variables: dict[str, str] = {}
    if var:
        for v in var:
            if "=" not in v:
                typer.echo(
                    typer.style(
                        f"Invalid variable format: {v} (expected key=value)", fg=typer.colors.RED
                    )
                )
                raise typer.Exit(1)
            k, _, val = v.partition("=")
            variables[k] = val

    with get_db() as db:
        service = PromptService(db)
        template = service._get_prompt(key, key.split("."))

    if not template:
        typer.echo(typer.style(f"Prompt not found: {key}", fg=typer.colors.RED))
        raise typer.Exit(1)

    # Render
    from src.services.prompt_service import SafeDict

    rendered = template.format_map(SafeDict(variables))

    if is_json_mode():
        output_result({"key": key, "rendered": rendered, "variables_used": variables})
        return

    typer.echo(typer.style(f"Rendered prompt for {key}:", bold=True))
    typer.echo()
    typer.echo(rendered)
