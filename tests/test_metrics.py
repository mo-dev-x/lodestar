from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from lodestar.metrics import METRIC_REGISTRY, register_metric
from lodestar.metrics.derived import (
    coherence_relevance_frontier,
    control_gap,
    cross_lingual_transfer,
    cross_model_comparison,
    optimal_operating_points,
    parse_objective,
    steering_efficacy_scores,
)
from lodestar.models import (
    DecodingParams,
    EvalRun,
    Generation,
    Judgment,
    RunManifest,
    SteeringConfig,
)
from lodestar.rubrics.steering import COHERENCE, CONCEPT_RELEVANCE


def test_ses_frontier_and_optimal(sample_run) -> None:
    ses = steering_efficacy_scores(sample_run)
    assert (ses["ses"] >= 0).all()
    frontier = coherence_relevance_frontier(sample_run)
    assert not frontier.empty
    assert frontier["pareto"].any()
    optimal = optimal_operating_points(
        sample_run, "max concept_relevance s.t. coherence >= 1 and prompt_adherence >= 1"
    )
    assert not optimal.empty
    assert (optimal["coherence"] >= 1).all()


def test_objective_parser_rejects_code() -> None:
    parsed = parse_objective("min coherence s.t. concept_relevance > 4")
    assert parsed.direction == "min"
    with pytest.raises(ValueError):
        parse_objective("max __import__('os').system('bad')")


def test_control_transfer_and_model_tables(sample_run) -> None:
    gaps = control_gap(sample_run)
    assert not gaps.empty
    assert (gaps["gap"] > 0).all()
    assert (gaps["ci_low"] <= gaps["ci_high"]).all()
    transfer = cross_lingual_transfer(sample_run)
    assert set(transfer["language"]) == {"en", "fr"}
    assert transfer.loc[transfer["language"] == "en", "transfer_ratio"].eq(1).all()
    comparison = cross_model_comparison(sample_run)
    assert not comparison.empty
    assert "concept_relevance" in comparison


def test_impossible_objective_returns_empty(sample_run) -> None:
    value = optimal_operating_points(sample_run, "max concept_relevance s.t. coherence > 99")
    assert isinstance(value, pd.DataFrame)
    assert value.empty


def test_frontier_ablation_separation_driven_by_typed_experiment() -> None:
    # INV-TYPED / F3: coherence_relevance_frontier groups by the typed
    # `experiment` column scores() now derives from Generation.experiment. Two
    # steered generations sharing sweep_hash/config_hash/scale/language/model
    # but differing only in `experiment` MUST NOT be averaged into one Pareto
    # point -- that merge is exactly the untyped-metadata-convention bug F3
    # closes (previously both would read back as the same "unknown" bucket).
    config = SteeringConfig(
        sae_checkpoint_id="sae", hook_layer=1, feature_ids=(1,), weights=(1.0,),
        scale=10.0, decoding=DecodingParams(),
    )
    shared = dict(
        prompt="p", prompt_id="pid", condition="steered", model_name="m",
        language="en", target_concept="z", steering_config=config, seed=1,
    )
    steering_gen = Generation(text="steering text", experiment="steering", **shared)
    ablation_gen = Generation(text="ablation text", experiment="ablation", **shared)

    def judgments_for(generation: Generation, coherence: float, relevance: float) -> list[Judgment]:
        return [
            Judgment(
                generation_id=generation.id, rubric_name="coherence", rubric_version="1.0",
                score=coherence, rationale="r", judge_model="mock", raw_response="{}",
            ),
            Judgment(
                generation_id=generation.id, rubric_name="concept_relevance", rubric_version="1.0",
                score=relevance, rationale="r", judge_model="mock", raw_response="{}",
            ),
        ]

    now = datetime.now(UTC)
    run = EvalRun(
        generations=[steering_gen, ablation_gen],
        judgments=[*judgments_for(steering_gen, 8.0, 9.0), *judgments_for(ablation_gen, 3.0, 2.0)],
        rubrics=[COHERENCE, CONCEPT_RELEVANCE], judge_model="mock", n_repeats=1,
        manifest=RunManifest(tool_version="test", started_at=now, finished_at=now),
    )
    frontier = coherence_relevance_frontier(run)
    assert len(frontier) == 2  # not merged into one averaged point
    by_experiment = frontier.set_index("experiment")
    assert by_experiment.loc["steering", "coherence"] == 8.0
    assert by_experiment.loc["steering", "concept_relevance"] == 9.0
    assert by_experiment.loc["ablation", "coherence"] == 3.0
    assert by_experiment.loc["ablation", "concept_relevance"] == 2.0


def test_metric_registry_has_all_built_ins_and_accepts_new_plugins(sample_run) -> None:
    assert set(METRIC_REGISTRY) == {
        "coherence_relevance_frontier",
        "control_gap",
        "cross_lingual_transfer",
        "cross_model_comparison",
        "optimal_operating_points",
        "steering_efficacy_scores",
    }
    assert METRIC_REGISTRY["coherence_relevance_frontier"] is coherence_relevance_frontier

    def custom_metric(run, **kwargs):
        return pd.DataFrame({"n_generations": [len(run.generations)]})

    register_metric("custom_metric", custom_metric)
    try:
        assert METRIC_REGISTRY["custom_metric"](sample_run)["n_generations"][0] == len(
            sample_run.generations
        )
    finally:
        del METRIC_REGISTRY["custom_metric"]

