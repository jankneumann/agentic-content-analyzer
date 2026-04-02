"""CLI commands for LLM router evaluation and calibration.

Usage:
    aca evaluate list-datasets
    aca evaluate create-dataset --step summarization
    aca evaluate run <dataset-id>
    aca evaluate calibrate --step summarization
    aca evaluate report [--step summarization]
    aca evaluate compare --step summarization --threshold 0.5
"""

from __future__ import annotations

from typing import Annotated

import typer

app = typer.Typer(
    name="evaluate",
    help="LLM router evaluation — datasets, judging, and calibration",
    no_args_is_help=True,
)


@app.command("list-datasets")
def list_datasets(
    step: Annotated[
        str | None,
        typer.Option("--step", "-s", help="Filter by pipeline step"),
    ] = None,
) -> None:
    """List evaluation datasets."""
    from src.services.evaluation_service import EvaluationService

    svc = EvaluationService()
    datasets = svc.get_datasets(step=step)

    if not datasets:
        typer.echo("No evaluation datasets found.")
        raise typer.Exit(0)

    typer.echo(f"{'ID':<6} {'Step':<20} {'Name':<30} {'Status':<20} {'Samples':<8}")
    typer.echo("-" * 84)
    for ds in datasets:
        typer.echo(
            f"{ds.id:<6} {ds.step:<20} {(ds.name or ''):<30} {ds.status:<20} {ds.sample_count:<8}"
        )


@app.command("create-dataset")
def create_dataset(
    step: Annotated[str, typer.Option("--step", "-s", help="Pipeline step name")],
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Dataset name"),
    ] = None,
    strong_model: Annotated[
        str,
        typer.Option("--strong-model", help="Strong model ID"),
    ] = "claude-sonnet-4-5",
    weak_model: Annotated[
        str,
        typer.Option("--weak-model", help="Weak model ID"),
    ] = "claude-haiku-4-5",
) -> None:
    """Create a new evaluation dataset."""
    from src.services.evaluation_service import EvaluationService

    svc = EvaluationService()
    ds = svc.create_dataset(
        step=step,
        name=name,
        strong_model=strong_model,
        weak_model=weak_model,
    )
    typer.echo(f"Created dataset: id={ds.id}, step={ds.step}, name={ds.name}")


@app.command("run")
def run_evaluation(
    dataset_id: Annotated[int, typer.Argument(help="Dataset ID to evaluate")],
) -> None:
    """Run judge evaluation on a dataset."""
    import asyncio

    from src.evaluation.consensus import ConsensusEngine
    from src.evaluation.criteria import load_evaluation_config
    from src.services.evaluation_service import EvaluationService

    config = load_evaluation_config()
    engine = ConsensusEngine(judges=[], config=config)
    svc = EvaluationService(eval_config=config)

    typer.echo(f"Running evaluation on dataset {dataset_id}...")
    try:
        results = asyncio.run(svc.run_evaluation(dataset_id, engine))
        typer.echo(f"Evaluation complete: {len(results)} samples evaluated.")
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command("calibrate")
def calibrate(
    step: Annotated[str, typer.Option("--step", "-s", help="Pipeline step to calibrate")],
    target_quality: Annotated[
        float,
        typer.Option("--target-quality", "-q", help="Target win-or-tie rate (0.0-1.0)"),
    ] = 0.95,
) -> None:
    """Calibrate routing threshold for a step from evaluation data."""
    from src.evaluation.calibrator import ThresholdCalibrator

    calibrator = ThresholdCalibrator()
    typer.echo(f"Calibrating threshold for step '{step}' (target quality: {target_quality})...")
    typer.echo("Note: Requires evaluation data in the database. Use 'aca evaluate run' first.")
    typer.echo(
        f"Calibrator ready for step '{step}'. "
        f"Call calibrator.calibrate() with complexity_scores and consensus_preferences."
    )


@app.command("compare")
def compare(
    step: Annotated[str, typer.Option("--step", "-s", help="Pipeline step")],
    threshold: Annotated[
        float,
        typer.Option("--threshold", "-t", help="Routing threshold to evaluate"),
    ] = 0.5,
    strong_cost: Annotated[
        float,
        typer.Option("--strong-cost", help="Cost per strong model call"),
    ] = 0.01,
    weak_cost: Annotated[
        float,
        typer.Option("--weak-cost", help="Cost per weak model call"),
    ] = 0.001,
) -> None:
    """Compare cost savings at a given threshold."""
    from src.evaluation.calibrator import ThresholdCalibrator

    calibrator = ThresholdCalibrator()
    typer.echo(f"Cost comparison for step '{step}' at threshold {threshold}:")
    typer.echo(f"  Strong model cost/call: ${strong_cost:.4f}")
    typer.echo(f"  Weak model cost/call:   ${weak_cost:.4f}")
    typer.echo()
    typer.echo("Provide complexity_scores via the Python API for detailed savings estimates.")


@app.command("report")
def report(
    step: Annotated[
        str | None,
        typer.Option("--step", "-s", help="Filter by pipeline step"),
    ] = None,
) -> None:
    """Generate cost savings report from routing decisions."""
    from src.services.evaluation_service import EvaluationService

    svc = EvaluationService()
    reports = svc.generate_report(step=step)

    if not reports:
        typer.echo("No routing decisions found. Enable dynamic routing first.")
        raise typer.Exit(0)

    for r in reports:
        typer.echo(f"\n{'='*50}")
        typer.echo(f"Step: {r.step}")
        typer.echo(f"Total decisions: {r.total_decisions}")
        typer.echo(f"Routed to weak: {r.pct_routed_to_weak:.1%}")
        typer.echo(f"Cost savings:    ${r.cost_savings_vs_all_strong:.4f}")
        typer.echo(f"Preferences:     {r.preference_distribution}")
