"""Repeated-judgment reliability and high-variance item detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from lodestar.metrics.stats import fleiss_kappa, icc_2_1, krippendorff_alpha
from lodestar.models import EvalRun


@dataclass(frozen=True)
class ConsistencyReport:
    reliability: pd.DataFrame
    high_variance: pd.DataFrame


def consistency_report(run: EvalRun, *, variance_threshold: float = 4.0) -> ConsistencyReport:
    rubric_by_name = {rubric.name: rubric for rubric in run.rubrics}
    rows: list[dict[str, Any]] = []
    flags: list[dict[str, Any]] = []
    for rubric_name, rubric in rubric_by_name.items():
        judgments = [
            judgment
            for judgment in run.judgments
            if judgment.rubric_name == rubric_name and judgment.score is not None
        ]
        generation_ids = sorted({judgment.generation_id for judgment in judgments})
        matrix: list[list[Any]] = []
        for generation_id in generation_ids:
            by_repeat = {
                judgment.repeat_index: judgment.score
                for judgment in judgments
                if judgment.generation_id == generation_id
            }
            values = [by_repeat.get(index, np.nan) for index in range(run.n_repeats)]
            matrix.append(values)
            if rubric.scale.kind == "ordinal":
                numeric = np.asarray(values, dtype=float)
                variance = float(np.nanvar(numeric))
                if variance > variance_threshold:
                    flags.append(
                        {
                            "generation_id": generation_id,
                            "rubric": rubric_name,
                            "variance": variance,
                            "scores": values,
                        }
                    )
        disagreement_flags = [
            judgment.metadata["judge_grep_disagreement"]
            for judgment in judgments
            if judgment.metadata.get("judge_grep_disagreement") is not None
        ]
        disagreement_rate = float(np.mean(disagreement_flags)) if disagreement_flags else np.nan
        if rubric.scale.kind == "ordinal":
            alpha = krippendorff_alpha(matrix, level="ordinal")
            icc = icc_2_1(matrix)
            rows.append(
                {
                    "rubric": rubric_name,
                    "scale": "ordinal",
                    "krippendorff_alpha": alpha,
                    "icc_2_1": icc,
                    "fleiss_kappa": np.nan,
                    "n_items": len(matrix),
                    "judge_grep_disagreement_rate": disagreement_rate,
                }
            )
        elif rubric.scale.kind == "binary":
            rows.append(
                {
                    "rubric": rubric_name,
                    "scale": "binary",
                    "krippendorff_alpha": krippendorff_alpha(matrix, level="nominal"),
                    "icc_2_1": np.nan,
                    "fleiss_kappa": fleiss_kappa(matrix),
                    "n_items": len(matrix),
                    "judge_grep_disagreement_rate": disagreement_rate,
                }
            )
        else:
            normalized = [
                [tuple(value) if isinstance(value, list) else value for value in item]
                for item in matrix
            ]
            rows.append(
                {
                    "rubric": rubric_name,
                    "scale": "categorical",
                    "krippendorff_alpha": krippendorff_alpha(normalized, level="nominal"),
                    "icc_2_1": np.nan,
                    "fleiss_kappa": np.nan,
                    "n_items": len(matrix),
                    "judge_grep_disagreement_rate": disagreement_rate,
                }
            )
    return ConsistencyReport(pd.DataFrame(rows), pd.DataFrame(flags))

