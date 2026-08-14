from __future__ import annotations

import pytest

from lodestar.models import OrdinalScale, Rubric
from lodestar.rubrics import (
    RUBRIC_REGISTRY,
    get_rubric,
    register_rubric,
    render_rubric,
    resolve_rubrics,
    validate_result,
)


def test_registry_contains_complete_suite(sample_generations) -> None:
    assert set(RUBRIC_REGISTRY) == {
        "coherence", "concept_relevance", "literal_mention", "prompt_adherence",
        "integration_naturalness", "degeneration_flags",
    }
    rendered = render_rubric(RUBRIC_REGISTRY["concept_relevance"], sample_generations[1])
    assert sample_generations[1].text in rendered
    assert "poutine" in rendered
    assert len(resolve_rubrics("steering")) == 6


def test_register_rubric_makes_a_custom_rubric_resolvable() -> None:
    # Mirrors register_metric: a plugin author adds a rubric without editing
    # rubrics/steering.py or the STEERING_RUBRICS tuple.
    custom = Rubric(
        name="my_custom_rubric",
        version="1.0",
        description="A custom rubric registered by a third party.",
        scale=OrdinalScale(minimum=1, maximum=10),
        prompt_template="score it",
        output_schema={"type": "object"},
    )
    register_rubric(custom)
    try:
        assert get_rubric("my_custom_rubric") is custom
        assert resolve_rubrics("my_custom_rubric") == [custom]
    finally:
        del RUBRIC_REGISTRY["my_custom_rubric"]


def test_result_validation_enforces_scale() -> None:
    assert validate_result(get_rubric("coherence"), {"score": 7, "rationale": "Readable."}).score == 7
    with pytest.raises(ValueError, match="outside"):
        validate_result(get_rubric("coherence"), {"score": 11, "rationale": "No."})
    with pytest.raises(ValueError, match="boolean"):
        validate_result(get_rubric("literal_mention"), {"score": 1, "rationale": "No."})
    with pytest.raises(ValueError, match="cannot be combined"):
        validate_result(
            get_rubric("degeneration_flags"),
            {"score": ["none", "gibberish"], "rationale": "Contradiction."},
        )


def test_unknown_rubric_is_actionable() -> None:
    with pytest.raises(KeyError, match="choose from"):
        get_rubric("not-real")
