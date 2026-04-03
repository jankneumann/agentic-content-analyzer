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
    from src.storage.database import get_db

    with get_db() as db:
        svc = EvaluationService(db_session=db)
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
    from src.storage.database import get_db

    with get_db() as db:
        svc = EvaluationService(db_session=db)
        ds = svc.create_dataset(
            step=step,
            name=name,
            strong_model=strong_model,
            weak_model=weak_model,
        )
        db.commit()
    typer.echo(f"Created dataset: id={ds.id}, step={ds.step}, name={ds.name}")


@app.command("run")
def run_evaluation(
    dataset_id: Annotated[int, typer.Argument(help="Dataset ID to evaluate")],
    judge_model: Annotated[
        str,
        typer.Option("--judge-model", "-j", help="Model to use as judge"),
    ] = "claude-sonnet-4-5",
    num_judges: Annotated[
        int,
        typer.Option("--num-judges", "-n", help="Number of judges (1-3)"),
    ] = 1,
) -> None:
    """Run judge evaluation on a dataset.

    Requires a database connection and configured LLM provider.
    """
    import asyncio

    from src.evaluation.consensus import ConsensusEngine
    from src.evaluation.criteria import load_evaluation_config
    from src.evaluation.judge import LLMJudge
    from src.services.evaluation_service import EvaluationService

    config = load_evaluation_config()

    if num_judges < 1 or num_judges > 3:
        typer.echo("Error: num-judges must be between 1 and 3", err=True)
        raise typer.Exit(1)

    try:
        from src.config.models import ModelConfig
        from src.services.llm_router import LLMRouter
        from src.storage.database import SessionLocal

        model_config = ModelConfig()
        router = LLMRouter(model_config)
        db = SessionLocal()
    except Exception as e:
        typer.echo(f"Error: Could not initialize services: {e}", err=True)
        typer.echo("Ensure DATABASE_URL is set and LLM provider is configured.")
        raise typer.Exit(1)

    judges = [
        LLMJudge(judge_model=judge_model, router=router, eval_config=config)
        for _ in range(num_judges)
    ]
    engine = ConsensusEngine(judges=judges)
    svc = EvaluationService(db_session=db, eval_config=config)

    typer.echo(f"Running evaluation on dataset {dataset_id} with {num_judges} judge(s)...")
    try:
        results = asyncio.run(svc.run_evaluation(dataset_id, engine))
        db.commit()
        typer.echo(f"Evaluation complete: {len(results)} samples evaluated.")
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        db.rollback()
        raise typer.Exit(1)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        db.rollback()
        raise typer.Exit(1)
    finally:
        db.close()


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
    from src.models.evaluation import (
        EvaluationConsensus,
        EvaluationSample,
        RoutingConfig as RoutingConfigRecord,
        RoutingDecision,
    )
    from src.storage.database import SessionLocal

    typer.echo(f"Calibrating threshold for step '{step}' (target quality: {target_quality})...")

    try:
        db = SessionLocal()
    except Exception as e:
        typer.echo(f"Error: Could not connect to database: {e}", err=True)
        raise typer.Exit(1)

    try:
        # Get complexity scores from routing decisions
        decisions = db.query(RoutingDecision).filter_by(step=step).all()
        if not decisions:
            typer.echo(
                f"No routing decisions found for step '{step}'. Run the pipeline with dynamic routing first.",
                err=True,
            )
            raise typer.Exit(1)

        # Get consensus preferences from evaluation data
        samples_with_consensus = (
            db.query(EvaluationSample, EvaluationConsensus)
            .join(EvaluationConsensus, EvaluationSample.id == EvaluationConsensus.sample_id)
            .filter(
                EvaluationSample.dataset_id.in_(db.query(EvaluationSample.dataset_id).distinct())
            )
            .all()
        )

        if not samples_with_consensus:
            typer.echo(
                "No evaluation consensus data found. Run 'aca evaluate run' first.", err=True
            )
            raise typer.Exit(1)

        # Match decisions to consensus by prompt_hash
        consensus_by_hash = {
            s.prompt_hash: c.consensus_preference for s, c in samples_with_consensus
        }
        complexity_scores = []
        preferences = []
        for d in decisions:
            if d.prompt_hash in consensus_by_hash:
                complexity_scores.append(d.complexity_score)
                preferences.append(consensus_by_hash[d.prompt_hash])

        calibrator = ThresholdCalibrator()
        result = calibrator.calibrate(
            step=step,
            complexity_scores=complexity_scores,
            consensus_preferences=preferences,
            target_quality=target_quality,
        )

        typer.echo(f"\nCalibration result for '{step}':")
        typer.echo(f"  Optimal threshold:    {result.threshold}")
        typer.echo(f"  Win-or-tie rate:      {result.win_or_tie_rate:.1%}")
        typer.echo(f"  Samples used:         {result.total_samples}")
        typer.echo(f"  Est. cost savings:    {result.estimated_cost_savings_pct:.1%}")

        # Persist threshold to routing_configs
        record = db.query(RoutingConfigRecord).filter_by(step=step).first()
        if record:
            record.threshold = result.threshold
        else:
            record = RoutingConfigRecord(step=step, threshold=result.threshold, enabled=True)
            db.add(record)
        db.commit()
        typer.echo(f"\n  Threshold saved to routing_configs for step '{step}'.")

    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    finally:
        db.close()


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
    from src.models.evaluation import RoutingDecision
    from src.storage.database import SessionLocal

    try:
        db = SessionLocal()
    except Exception as e:
        typer.echo(f"Error: Could not connect to database: {e}", err=True)
        raise typer.Exit(1)

    try:
        decisions = db.query(RoutingDecision).filter_by(step=step).all()
        if not decisions:
            typer.echo(f"No routing decisions found for step '{step}'.", err=True)
            raise typer.Exit(1)

        complexity_scores = [d.complexity_score for d in decisions]
        calibrator = ThresholdCalibrator()
        savings = calibrator.estimate_savings(
            complexity_scores=complexity_scores,
            threshold=threshold,
            strong_cost_per_call=strong_cost,
            weak_cost_per_call=weak_cost,
        )

        typer.echo(f"Cost comparison for step '{step}' at threshold {threshold}:")
        typer.echo(f"  Total calls:          {savings['total_calls']}")
        typer.echo(f"  Routed to weak:       {savings['weak_routed']} ({savings['pct_weak']:.1%})")
        typer.echo(f"  Routed to strong:     {savings['strong_routed']}")
        typer.echo(f"  All-strong cost:      ${savings['all_strong_cost']:.4f}")
        typer.echo(f"  Routed cost:          ${savings['routed_cost']:.4f}")
        typer.echo(
            f"  Savings:              ${savings['savings']:.4f} ({savings['savings_pct']:.1%})"
        )
    finally:
        db.close()


@app.command("report")
def report(
    step: Annotated[
        str | None,
        typer.Option("--step", "-s", help="Filter by pipeline step"),
    ] = None,
) -> None:
    """Generate cost savings report from routing decisions."""
    from src.services.evaluation_service import EvaluationService
    from src.storage.database import get_db

    with get_db() as db:
        svc = EvaluationService(db_session=db)
        reports = svc.generate_report(step=step)

    if not reports:
        typer.echo("No routing decisions found. Enable dynamic routing first.")
        raise typer.Exit(0)

    for r in reports:
        typer.echo(f"\n{'=' * 50}")
        typer.echo(f"Step: {r.step}")
        typer.echo(f"Total decisions: {r.total_decisions}")
        typer.echo(f"Routed to weak: {r.pct_routed_to_weak:.1%}")
        typer.echo(f"Cost savings:    ${r.cost_savings_vs_all_strong:.4f}")
        typer.echo(f"Preferences:     {r.preference_distribution}")
