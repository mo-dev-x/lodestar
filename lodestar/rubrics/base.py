"""Rubric rendering and result validation."""

from __future__ import annotations

from typing import Any

from jinja2 import Environment, StrictUndefined
from pydantic import BaseModel, Field

from lodestar.models import Generation, Rubric, ScoreValue

_JINJA = Environment(undefined=StrictUndefined, autoescape=False)

RENDER_RULES_VERSION = "1"


class RubricResult(BaseModel):
    score: ScoreValue
    rationale: str = Field(max_length=500)
    count: int | None = Field(default=None, ge=0)


def render_rubric(rubric: Rubric, generation: Generation) -> str:
    template = _JINJA.from_string(rubric.prompt_template)
    return template.render(
        generation=generation,
        target_concept=generation.target_concept,
        prompt=generation.prompt,
        aliases=sorted(rubric.aliases),
    )


def validate_result(rubric: Rubric, data: dict[str, Any]) -> RubricResult:
    """Validate the common shape and rubric-specific score semantics."""
    result = RubricResult.model_validate(data)
    score = result.score
    scale = rubric.scale
    if scale.kind == "ordinal":
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise ValueError(f"{rubric.name} requires a numeric score")
        if not scale.minimum <= float(score) <= scale.maximum:
            raise ValueError(f"{rubric.name} score is outside its scale")
    elif scale.kind == "binary" and not isinstance(score, bool):
        raise ValueError(f"{rubric.name} requires a boolean score")
    elif scale.kind == "categorical":
        values = score if isinstance(score, list) else [score]
        if not scale.multiple and len(values) != 1:
            raise ValueError(f"{rubric.name} accepts one category")
        if any(value not in scale.categories for value in values):
            raise ValueError(f"{rubric.name} contains an unknown category")
        if "none" in values and len(values) != 1:
            raise ValueError("'none' cannot be combined with another category")
    return result
