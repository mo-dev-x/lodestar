"""Pure derived metrics for steering runs."""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from lodestar.models import EvalRun


def _wide_scores(run: EvalRun) -> pd.DataFrame:
    scores = run.scores()
    if scores.empty:
        return scores
    index = [
        "generation_id",
        "condition",
        "config_hash",
        "sweep_hash",
        "scale",
        "language",
        "model_name",
        "prompt_id",
        "target_concept",
        "experiment",
    ]
    return scores.pivot_table(index=index, columns="rubric", values="score", aggfunc="first").reset_index()


def steering_efficacy_scores(
    run: EvalRun,
    *,
    relevance_weight: float = 1.0,
    coherence_power: float = 1.0,
) -> pd.DataFrame:
    table = _wide_scores(run)
    required = {"concept_relevance", "coherence"}
    if table.empty or not required.issubset(table.columns):
        return pd.DataFrame(columns=["generation_id", "ses"])
    table["ses"] = (
        table["concept_relevance"].astype(float) * relevance_weight
        * (table["coherence"].astype(float) / 10) ** coherence_power
    )
    return table


def coherence_relevance_frontier(run: EvalRun) -> pd.DataFrame:
    table = _wide_scores(run)
    required = {"coherence", "concept_relevance"}
    if table.empty or not required.issubset(table.columns):
        return pd.DataFrame()
    steered = table[table["condition"] == "steered"]
    # "experiment" is included in both groupings below so that generations from a
    # different experiment design (e.g. an ablation run that reuses scale=0.0 as a
    # placeholder) never get averaged or Pareto-compared against a real scale sweep
    # just because they happen to share a sweep_hash (which deliberately excludes
    # scale, so it alone can't tell two same-config experiments apart).
    group_columns = ["sweep_hash", "config_hash", "scale", "language", "model_name", "experiment"]
    points = (
        steered.groupby(group_columns, dropna=False)[["coherence", "concept_relevance"]]
        .mean()
        .reset_index()
    )
    points["pareto"] = False
    for _, group in points.groupby(["sweep_hash", "language", "model_name", "experiment"], dropna=False):
        for index, point in group.iterrows():
            dominated = (
                (group["coherence"] >= point["coherence"])
                & (group["concept_relevance"] >= point["concept_relevance"])
                & (
                    (group["coherence"] > point["coherence"])
                    | (group["concept_relevance"] > point["concept_relevance"])
                )
            ).any()
            points.loc[index, "pareto"] = not dominated
    return points.sort_values(["sweep_hash", "language", "model_name", "scale"])


_OBJECTIVE = re.compile(
    r"^\s*(max|min)\s+([A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\s+s\.t\.\s+(.+?))?\s*$",
    re.IGNORECASE,
)
_CONSTRAINT = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(>=|<=|>|<|==)\s*(-?(?:\d+(?:\.\d*)?|\.\d+))\s*$"
)


@dataclass(frozen=True)
class ParsedObjective:
    direction: str
    metric: str
    constraints: tuple[tuple[str, str, float], ...]


def parse_objective(value: str) -> ParsedObjective:
    match = _OBJECTIVE.fullmatch(value)
    if not match:
        raise ValueError("objective must look like 'max concept_relevance s.t. coherence >= 7'")
    direction, metric, raw_constraints = match.groups()
    constraints: list[tuple[str, str, float]] = []
    if raw_constraints:
        for raw in re.split(r"\s+(?:and|&)\s+", raw_constraints, flags=re.IGNORECASE):
            constraint = _CONSTRAINT.fullmatch(raw)
            if not constraint:
                raise ValueError(f"invalid objective constraint: {raw!r}")
            name, operator, threshold = constraint.groups()
            constraints.append((name, operator, float(threshold)))
    return ParsedObjective(direction.casefold(), metric, tuple(constraints))


def optimal_operating_points(run: EvalRun, objective: str) -> pd.DataFrame:
    parsed = parse_objective(objective)
    table = _wide_scores(run)
    if table.empty:
        return table
    numeric_rubrics = [rubric.name for rubric in run.rubrics if rubric.scale.kind == "ordinal"]
    points = (
        table[table["condition"] == "steered"]
        .groupby(
            ["sweep_hash", "config_hash", "scale", "language", "model_name", "experiment"],
            dropna=False,
        )[numeric_rubrics]
        .mean()
        .reset_index()
    )
    required = {parsed.metric, *(name for name, _, _ in parsed.constraints)}
    unknown = required - set(points.columns)
    if unknown:
        raise ValueError(f"objective references unavailable metrics: {sorted(unknown)}")
    selected = points
    operators = {
        ">=": lambda series, value: series >= value,
        "<=": lambda series, value: series <= value,
        ">": lambda series, value: series > value,
        "<": lambda series, value: series < value,
        "==": lambda series, value: series == value,
    }
    for name, operator, threshold in parsed.constraints:
        selected = selected[operators[operator](selected[name], threshold)]
    ascending = parsed.direction == "min"
    rows = []
    for _, group in selected.groupby(["sweep_hash", "language", "model_name", "experiment"], dropna=False):
        rows.append(group.sort_values([parsed.metric, "scale"], ascending=[ascending, True]).iloc[0])
    return pd.DataFrame(rows).reset_index(drop=True) if rows else points.iloc[0:0]


def control_gap(run: EvalRun, *, seed: int = 42) -> pd.DataFrame:
    table = _wide_scores(run)
    if table.empty or "concept_relevance" not in table:
        return pd.DataFrame()
    relevant = table[table["condition"].isin(["steered", "control"])]
    groups = ["scale", "language", "model_name"]
    rows = []
    for keys, group in relevant.groupby(groups, dropna=False):
        steered = group.loc[group["condition"] == "steered", "concept_relevance"].astype(float)
        control = group.loc[group["condition"] == "control", "concept_relevance"].astype(float)
        if steered.empty or control.empty:
            continue
        observed = float(steered.mean() - control.mean())
        generator = np.random.default_rng(seed)
        bootstrap_gaps = np.array(
            [
                generator.choice(steered.to_numpy(), size=len(steered), replace=True).mean()
                - generator.choice(control.to_numpy(), size=len(control), replace=True).mean()
                for _ in range(2_000)
            ]
        )
        low = float(np.quantile(bootstrap_gaps, 0.025))
        high = float(np.quantile(bootstrap_gaps, 0.975))
        test = stats.mannwhitneyu(steered, control, alternative="two-sided")
        rows.append(
            {
                **dict(zip(groups, keys, strict=True)),
                "steered_mean": steered.mean(),
                "control_mean": control.mean(),
                "gap": observed,
                "ci_low": low,
                "ci_high": high,
                "u_statistic": float(test.statistic),
                "p_value": float(test.pvalue),
                "n_steered": len(steered),
                "n_control": len(control),
            }
        )
    return pd.DataFrame(rows)


def cross_lingual_transfer(run: EvalRun, source_language: str = "en") -> pd.DataFrame:
    table = _wide_scores(run)
    if table.empty or "concept_relevance" not in table:
        return pd.DataFrame()
    steered = table[table["condition"] == "steered"]
    means = (
        steered.groupby(["sweep_hash", "scale", "model_name", "language"], dropna=False)[
            "concept_relevance"
        ]
        .mean()
        .reset_index()
    )
    source = means[means["language"] == source_language].rename(
        columns={"concept_relevance": "source_relevance"}
    )
    merged = means.merge(
        source[["sweep_hash", "scale", "model_name", "source_relevance"]],
        on=["sweep_hash", "scale", "model_name"],
        how="left",
    )
    merged["transfer_ratio"] = merged["concept_relevance"] / merged["source_relevance"].replace(0, np.nan)
    merged["source_language"] = source_language
    return merged


def cross_model_comparison(run: EvalRun) -> pd.DataFrame:
    table = _wide_scores(run)
    if table.empty:
        return table
    numeric = [rubric.name for rubric in run.rubrics if rubric.scale.kind == "ordinal"]
    return (
        table.groupby(["model_name", "condition", "language", "scale"], dropna=False)[numeric]
        .mean()
        .reset_index()
    )
