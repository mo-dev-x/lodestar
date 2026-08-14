from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from lodestar.models import (
    BinaryScale,
    DecodingParams,
    EvalRun,
    Generation,
    Judgment,
    Rubric,
    RunManifest,
    SteeringConfig,
)
from lodestar.rubrics.steering import COHERENCE


def test_config_hash_is_stable_and_scale_sensitive() -> None:
    first = SteeringConfig(
        sae_checkpoint_id="sae", hook_layer=2, feature_ids=(1, 2), weights=(1.0, 0.5),
        scale=10, decoding=DecodingParams(),
    )
    same = SteeringConfig.model_validate(first.model_dump())
    other_scale = first.model_copy(update={"scale": 11})
    assert first.config_hash() == same.config_hash()
    assert first.config_hash() != other_scale.config_hash()
    assert first.sweep_hash() == other_scale.sweep_hash()


def test_feature_weights_must_align() -> None:
    with pytest.raises(ValidationError, match="equal lengths"):
        SteeringConfig(
            sae_checkpoint_id="sae", hook_layer=2, feature_ids=(1, 2), weights=(1.0,), scale=1,
        )


def test_generation_id_and_run_round_trip(sample_run: EvalRun, tmp_path) -> None:
    assert len({generation.id for generation in sample_run.generations}) == len(sample_run.generations)
    sample_run.save(tmp_path)
    restored = EvalRun.load(tmp_path)
    assert restored.id == sample_run.id
    assert len(restored.by_config()) > 1
    assert not restored.scores("coherence").empty


@pytest.mark.parametrize(
    ("field", "changed"),
    [("text", "beta"), ("prompt", "different prompt"), ("target_concept", "other"), ("language", "fr")],
)
def test_generation_id_distinguishes_subject_fields(field: str, changed: str) -> None:
    # INV-DECIDE / F5 (amended): Generation.id MUST refine the Generation-resident
    # subset of the Subject S = {text, prompt, target_concept, language}, with
    # every field encoded DIRECTLY -- `prompt` included, not merely `prompt_id`.
    # Two generations equal on every coordinate except one of these MUST have
    # different ids; identical coordinates MUST share an id (tightness). Note
    # `prompt_id` is held equal across the `prompt` case here too, which is
    # exactly the surrogate-collision scenario the amendment closes.
    shared = dict(
        text="alpha", prompt="y", prompt_id="p", condition="baseline", model_name="m",
        language="en", target_concept="z", seed=1,
    )
    first = Generation(**shared)
    second = Generation(**{**shared, field: changed})
    same = Generation(**shared)
    assert first.id != second.id
    assert first.id == same.id


def test_generation_id_distinguishes_prompt_despite_shared_prompt_id() -> None:
    # Regression test for the residual soundness gap the architect identified:
    # `prompt_id` is a provenance field, not a Subject field, and is only a
    # *conditional* surrogate for `prompt` -- the steering adapter derives it
    # from `prompt`, but the generic adapter and direct construction admit
    # arbitrary (prompt, prompt_id) pairs. Two Generations with different
    # `prompt` but an identical caller-supplied `prompt_id` (and everything
    # else equal) MUST NOT collide on Generation.id.
    shared = dict(
        text="alpha", prompt_id="p1", condition="baseline", model_name="m",
        language="en", target_concept="z", seed=1,
    )
    a = Generation(prompt="Discuss winter travel.", **shared)
    b = Generation(prompt="Describe your favorite dessert.", **shared)
    assert a.prompt != b.prompt
    assert a.prompt_id == b.prompt_id
    assert a.id != b.id


def test_loaded_run_ids_are_content_anchored(sample_run: EvalRun, tmp_path) -> None:
    # Invariant: Generation.id refines the Generation-resident Subject -- within
    # a loaded run, no two generations share an id unless they share the full
    # tuple (text, prompt, target_concept, language). A shared id therefore
    # maps to exactly one distinct Subject.
    sample_run.save(tmp_path)
    restored = EvalRun.load(tmp_path)
    subjects_by_id: dict[str, set[tuple[str, str, str, str]]] = defaultdict(set)
    for generation in restored.generations:
        subjects_by_id[generation.id].add(
            (generation.text, generation.prompt, generation.target_concept, generation.language)
        )
    assert all(len(subjects) == 1 for subjects in subjects_by_id.values())


def test_generation_id_unaffected_by_rubric_aliases() -> None:
    # INV-DECIDE / F5 (corrected): `aliases` is the Rubric-resident component of
    # S, not a Generation field (Constitution §2.3 coordinate-object note). It
    # MUST NOT enter Generation.id -- the alias component of S is composed at
    # judging time via the Instrument, never stored on the Generation.
    assert "aliases" not in Generation.model_fields

    def rubric_with_aliases(aliases: tuple[str, ...]) -> Rubric:
        return Rubric(
            name="literal_mention", version="1.0", description="d", scale=BinaryScale(),
            prompt_template="t", output_schema={}, aliases=aliases,
        )

    shared = dict(
        text="alpha", prompt="y", prompt_id="p", condition="baseline", model_name="m",
        language="en", target_concept="z", seed=1,
    )
    baseline_id = Generation(**shared).id
    for aliases in [(), ("fries",), ("fries", "curds", "gravy")]:
        rubric_with_aliases(aliases)  # constructing distinct alias sets is a no-op on Generation.id
        assert Generation(**shared).id == baseline_id


def test_scores_reads_typed_experiment_field() -> None:
    # INV-TYPED / F3: scores() MUST read Generation.experiment directly. Before
    # this fix, a Generation with the typed field set but no matching
    # metadata["experiment"] key would incorrectly report "unknown" (the old
    # metadata.get(...) fallback default).
    generation = Generation(
        text="x", prompt="y", prompt_id="p", condition="baseline", model_name="m",
        language="en", target_concept="z", experiment="custom", seed=1,
    )
    judgment = Judgment(
        generation_id=generation.id, rubric_name="coherence", rubric_version="1.0",
        score=8, rationale="r", judge_model="mock", raw_response="{}",
    )
    now = datetime.now(UTC)
    run = EvalRun(
        generations=[generation], judgments=[judgment], rubrics=[COHERENCE],
        judge_model="mock", n_repeats=1,
        manifest=RunManifest(tool_version="test", started_at=now, finished_at=now),
    )
    table = run.scores()
    assert table.loc[0, "experiment"] == "custom"


def test_experiment_promoted_from_metadata() -> None:
    # Back-compat promotion: a Generation carrying only the legacy metadata
    # convention (no explicit `experiment` kwarg) MUST have it promoted to the
    # typed field on construction.
    generation = Generation(
        text="x", prompt="y", prompt_id="p", condition="baseline", model_name="m",
        language="en", target_concept="z", metadata={"experiment": "legacy"},
    )
    assert generation.experiment == "legacy"


def test_experiment_defaults_when_unset() -> None:
    generation = Generation(
        text="x", prompt="y", prompt_id="p", condition="baseline", model_name="m",
        language="en", target_concept="z",
    )
    assert generation.experiment == "default"


def test_generation_rejects_unknown_kwarg() -> None:
    # INV-NOHIDE / F9: Generation.model_config is extra="forbid" -- an
    # undeclared field MUST be rejected at construction, never silently
    # admitted as a hidden, un-declared coordinate.
    with pytest.raises(ValidationError):
        Generation(
            text="x", prompt="y", prompt_id="p", condition="baseline", model_name="m",
            language="en", target_concept="z", unexpected_field="oops",
        )


def test_judgments_carry_instrument_id_and_invariance_version(sample_run: EvalRun) -> None:
    # INV-TRACE / F6: every Judgment MUST record a complete path to its
    # Instrument identity and the invariance-model version in force when it
    # was produced.
    assert all(judgment.instrument_id for judgment in sample_run.judgments)
    assert all(judgment.invariance_version for judgment in sample_run.judgments)


def test_different_instruments_yield_different_instrument_id(sample_run: EvalRun) -> None:
    # Distinct rubrics (distinct template/schema => distinct Instrument) MUST
    # produce distinct instrument_id; repeats of the same rubric share one.
    by_rubric: dict[str, set[str]] = defaultdict(set)
    for judgment in sample_run.judgments:
        by_rubric[judgment.rubric_name].add(judgment.instrument_id)
    assert all(len(ids) == 1 for ids in by_rubric.values())
    distinct_ids = [next(iter(ids)) for ids in by_rubric.values()]
    assert len(set(distinct_ids)) == len(distinct_ids)


def test_nonbaseline_requires_config() -> None:
    with pytest.raises(ValidationError, match="require steering_config"):
        Generation(
            text="x", prompt="y", prompt_id="p", condition="steered", model_name="m",
            language="en", target_concept="z",
        )

