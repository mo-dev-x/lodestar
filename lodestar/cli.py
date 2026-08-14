"""Lodestar command-line interface."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from lodestar import TOOL_NAME, __version__
from lodestar.config import RunConfig
from lodestar.ingest import load_generations
from lodestar.judges import AnthropicJudge, Judge, JudgeCache, MockJudge
from lodestar.judges.base import (
    DEFAULT_JUDGE_MAX_TOKENS,
    INVARIANCE_MODEL_VERSION,
    JUDGE_SYSTEM_PROMPT,
    JUDGE_TEMPERATURE,
)
from lodestar.judges.cost import CostEstimate, actual_cost, estimate, is_snapshot
from lodestar.judges.identity import execution_cache_key
from lodestar.metrics import METRIC_REGISTRY
from lodestar.models import EvalRun, Generation, Rubric, RunManifest, stable_hash
from lodestar.report import generate_report
from lodestar.rubrics import resolve_rubrics
from lodestar.validation import (
    consistency_report,
    export_labeling_html,
    export_labels,
    human_correlation,
)

app = typer.Typer(
    name="lodestar",
    help="Steering-native, human-correlated evaluation for interpretability research.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)


def _load(
    path: Path,
    target_concept: str,
    model_name: str,
    language: str,
    sae_checkpoint_id: str,
    hook_layer: int,
    random_feature_id: int,
) -> list[Generation]:
    return load_generations(
        path,
        target_concept=target_concept,
        model_name=model_name,
        language=language,
        sae_checkpoint_id=sae_checkpoint_id,
        hook_layer=hook_layer,
        random_feature_id=random_feature_id,
    )


def _with_aliases(rubrics: list[Rubric], aliases: str) -> list[Rubric]:
    values = tuple(value.strip() for value in aliases.split(",") if value.strip())
    return [
        rubric.model_copy(update={"aliases": values})
        if rubric.name == "literal_mention"
        else rubric
        for rubric in rubrics
    ]


def _estimate_text(value: CostEstimate) -> str:
    return (
        f"This sweep = {value.calls:,} judge calls "
        f"({value.cached_calls:,} cached, {value.new_calls:,} new) "
        f"≈ ${value.cost_usd:,.4f}."
    )


@app.command("estimate")
def estimate_command(
    generations: Annotated[Path, typer.Argument(exists=True, readable=True)],
    rubrics: Annotated[str, typer.Option(help="'steering' or comma-separated rubric names.")] = "steering",
    repeats: Annotated[int, typer.Option(min=1)] = 3,
    judge: Annotated[str, typer.Option(help="Pinned Anthropic model ID.")] = "claude-sonnet-4-5-20250929",
    cache: Annotated[Path, typer.Option(help="Existing/shared judgment cache.")] = Path("run/cache.sqlite"),
    target_concept: Annotated[str, typer.Option()] = "poutine",
    model_name: Annotated[str, typer.Option(help="Model that produced the generations.")] = "unknown-model",
    language: Annotated[str, typer.Option()] = "en",
    sae_checkpoint_id: Annotated[str, typer.Option()] = "unknown-sae",
    hook_layer: Annotated[int, typer.Option(min=0)] = 0,
    random_feature_id: Annotated[int, typer.Option(min=0)] = 0,
    aliases: Annotated[str, typer.Option(help="Comma-separated literal aliases.")] = "",
) -> None:
    loaded = _load(
        generations,
        target_concept,
        model_name,
        language,
        sae_checkpoint_id,
        hook_layer,
        random_feature_id,
    )
    selected = _with_aliases(resolve_rubrics(rubrics), aliases)
    items = [(generation, rubric) for generation in loaded for rubric in selected]

    async def calculate() -> CostEstimate:
        judge_cache = JudgeCache(cache)
        await judge_cache.initialize()
        keys = [
            execution_cache_key(
                generation,
                rubric,
                model_name=judge,
                system_prompt=JUDGE_SYSTEM_PROMPT,
                max_tokens=DEFAULT_JUDGE_MAX_TOKENS,
                temperature=JUDGE_TEMPERATURE,
                repeat_index=repeat_index,
            )
            for generation, rubric in items
            for repeat_index in range(repeats)
        ]
        hits = await judge_cache.count_hits(keys)
        return estimate(loaded, selected, repeats, judge, cached_calls=hits)

    value = asyncio.run(calculate())
    typer.echo(_estimate_text(value) + " No API calls were made.")


@app.command("eval")
def eval_command(
    generations: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("run"),
    rubrics: Annotated[str, typer.Option()] = "steering",
    judge: Annotated[str, typer.Option(help="Anthropic model ID, or 'mock'.")] = "claude-sonnet-4-5-20250929",
    repeats: Annotated[int, typer.Option(min=1)] = 3,
    target_concept: Annotated[str, typer.Option()] = "poutine",
    budget: Annotated[float | None, typer.Option(min=0.01)] = None,
    concurrency: Annotated[int, typer.Option(min=1)] = 8,
    seed: Annotated[int, typer.Option()] = 42,
    model_name: Annotated[str, typer.Option(help="Model that produced the generations.")] = "unknown-model",
    language: Annotated[str, typer.Option()] = "en",
    sae_checkpoint_id: Annotated[str, typer.Option()] = "unknown-sae",
    hook_layer: Annotated[int, typer.Option(min=0)] = 0,
    random_feature_id: Annotated[int, typer.Option(min=0)] = 0,
    aliases: Annotated[str, typer.Option(help="Comma-separated literal aliases.")] = "",
    allow_alias: Annotated[
        bool, typer.Option("--allow-alias", help="Permit a moving model alias instead of a pinned snapshot.")
    ] = False,
) -> None:
    if judge.casefold() != "mock" and not is_snapshot(judge) and not allow_alias:
        raise typer.BadParameter(
            f"{judge!r} is not a pinned model snapshot (e.g. 'claude-sonnet-4-5-20250929'); "
            "pass --allow-alias to use a moving alias anyway.",
            param_hint="--judge",
        )
    config = RunConfig(
        judge_model=judge,
        repeats=repeats,
        concurrency=concurrency,
        seed=seed,
        budget_usd=budget,
        cache_path=output / "cache.sqlite",
    )
    config.apply_seed()
    loaded = _load(
        generations,
        target_concept,
        model_name,
        language,
        sae_checkpoint_id,
        hook_layer,
        random_feature_id,
    )
    selected = _with_aliases(resolve_rubrics(rubrics), aliases)
    items = [(generation, rubric) for generation in loaded for rubric in selected]

    async def evaluate() -> tuple[list, int, float]:
        cache = JudgeCache(config.cache_path)
        await cache.initialize()
        judge_name = MockJudge.model_name if judge.casefold() == "mock" else judge
        keys = [
            execution_cache_key(
                generation,
                rubric,
                model_name=judge_name,
                system_prompt=JUDGE_SYSTEM_PROMPT,
                max_tokens=DEFAULT_JUDGE_MAX_TOKENS,
                temperature=JUDGE_TEMPERATURE,
                repeat_index=repeat_index,
            )
            for generation, rubric in items
            for repeat_index in range(repeats)
        ]
        hits = await cache.count_hits(keys)
        predicted_cost = 0.0
        if judge.casefold() != "mock":
            prediction = estimate(loaded, selected, repeats, judge, cached_calls=hits)
            predicted_cost = prediction.cost_usd
            typer.echo(_estimate_text(prediction))
            if budget is not None and predicted_cost > budget:
                raise typer.BadParameter(
                    f"estimated cost ${predicted_cost:.4f} exceeds --budget ${budget:.4f}",
                    param_hint="--budget",
                )
            implementation: Judge = AnthropicJudge(
                judge,
                api_key=config.api_key(),
                concurrency=concurrency,
                cache=cache,
            )
        else:
            implementation = MockJudge(cache=cache)
        return await implementation.judge_batch(items, repeats), hits, predicted_cost

    started = datetime.now(UTC)
    started_clock = time.perf_counter()
    judgments, cache_hits, predicted_cost = asyncio.run(evaluate())
    finished = datetime.now(UTC)
    judge_model = MockJudge.model_name if judge.casefold() == "mock" else judge
    manifest_payload = {
        "input": str(generations.resolve()),
        "judge": judge_model,
        "rubrics": [(rubric.name, rubric.version) for rubric in selected],
        "repeats": repeats,
        "seed": seed,
    }
    manifest = RunManifest(
        config_hash=stable_hash(manifest_payload),
        tool_version=__version__,
        started_at=started,
        finished_at=finished,
        elapsed_seconds=time.perf_counter() - started_clock,
        total_cost_usd=actual_cost(judgments, judge_model),
        input_tokens=sum(value.usage.input_tokens for value in judgments),
        output_tokens=sum(value.usage.output_tokens for value in judgments),
        cache_hits=cache_hits,
        seeds=[seed],
        command=sys.argv,
        judge_snapshot=judge_model,
        invariance_version=INVARIANCE_MODEL_VERSION,
        metadata={"predicted_cost_usd": predicted_cost, "source": str(generations)},
    )
    run = EvalRun(
        generations=loaded,
        judgments=judgments,
        rubrics=selected,
        judge_model=judge_model,
        n_repeats=repeats,
        manifest=manifest,
    )
    run.save(output)
    consistency = consistency_report(run)
    consistency.reliability.to_csv(output / "reliability.csv", index=False)
    consistency.high_variance.to_csv(output / "high_variance.csv", index=False)
    typer.echo(
        f"Saved run {run.id} to {output} ({len(loaded)} generations, "
        f"{len(judgments)} judgments, ${manifest.total_cost_usd:.4f} actual cost)."
    )


@app.command("optimal")
def optimal_command(
    run_path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    objective: Annotated[str, typer.Option()] = "max concept_relevance s.t. coherence >= 7",
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    run = EvalRun.load(run_path)
    points = METRIC_REGISTRY["optimal_operating_points"](run, objective)
    if output:
        points.to_csv(output, index=False)
        typer.echo(f"Saved {len(points)} optimal operating point(s) to {output}.")
    typer.echo(points.to_string(index=False) if not points.empty else "No configuration satisfies the objective.")


@app.command("compare")
def compare_command(
    run_paths: Annotated[list[Path], typer.Argument()],
    by: Annotated[str, typer.Option(help="language, model, or config")] = "language",
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    if len(run_paths) < 2:
        raise typer.BadParameter("provide at least two run paths", param_hint="RUN_PATHS")
    group_column = {"language": "language", "model": "model_name", "config": "config_hash"}.get(by)
    if group_column is None:
        raise typer.BadParameter("must be language, model, or config", param_hint="--by")
    frames = []
    for path in run_paths:
        run = EvalRun.load(path)
        frame = run.scores()
        frame["run_id"] = run.id
        frames.append(frame)
    combined = pd.concat(frames, ignore_index=True)
    numeric = pd.to_numeric(combined["score"], errors="coerce")
    combined = combined.assign(numeric_score=numeric).dropna(subset=["numeric_score"])
    table = (
        combined.groupby(["run_id", group_column, "rubric"], dropna=False)["numeric_score"]
        .agg(["mean", "median", "std", "count"])
        .reset_index()
    )
    if output:
        table.to_csv(output, index=False)
        typer.echo(f"Saved comparison to {output}.")
    typer.echo(table.to_string(index=False))


@app.command("validate")
def validate_command(
    run_path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    export: Annotated[Path | None, typer.Option(help="Blank CSV or standalone HTML labeling page.")] = None,
    human: Annotated[Path | None, typer.Option(exists=True, readable=True)] = None,
    sample_size: Annotated[int, typer.Option(min=1)] = 100,
    seed: Annotated[int, typer.Option()] = 42,
) -> None:
    if export is not None and human is not None:
        raise typer.BadParameter("choose either --export or --human, not both")
    run = EvalRun.load(run_path)
    if export is not None:
        destination = (
            export_labeling_html(run, export, sample_size=sample_size, seed=seed)
            if export.suffix.casefold() == ".html"
            else export_labels(run, export, sample_size=sample_size, seed=seed)
        )
        typer.echo(f"Exported stratified labels to {destination}.")
        return
    if human is not None:
        report = human_correlation(run, human, seed=seed)
        typer.echo(report.metrics.to_string(index=False))
        for line in report.result_lines:
            typer.echo(line)
        serialized_metrics = json.loads(report.metrics.to_json(orient="records"))
        serialized_pairs = json.loads(report.pairs.to_json(orient="records"))
        (run_path if run_path.is_dir() else run_path.parent).joinpath("human_correlation.json").write_text(
            json.dumps(
                {
                    "metrics": serialized_metrics,
                    "result_lines": report.result_lines,
                    "pairs": serialized_pairs,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return
    report = consistency_report(run)
    typer.echo(report.reliability.to_string(index=False))
    typer.echo(f"High-variance items: {len(report.high_variance)}")


@app.command("report")
def report_command(
    run_path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("report.html"),
    objective: Annotated[str, typer.Option()] = "max concept_relevance s.t. coherence >= 7",
    human: Annotated[Path | None, typer.Option(exists=True, readable=True)] = None,
) -> None:
    destination = generate_report(EvalRun.load(run_path), output, objective=objective, human_labels=human)
    typer.echo(f"Saved self-contained report to {destination}.")


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"{TOOL_NAME} {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=version_callback, is_eager=True),
    ] = None,
) -> None:
    """Evaluate activation-steering generations with auditable, validated metrics."""


if __name__ == "__main__":
    app()
