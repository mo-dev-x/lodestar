"""Versioned rubric registry."""

from lodestar.models import Rubric
from lodestar.rubrics.base import RubricResult, render_rubric, validate_result
from lodestar.rubrics.steering import STEERING_RUBRICS

RUBRIC_REGISTRY: dict[str, Rubric] = {}


def register_rubric(rubric: Rubric) -> None:
    RUBRIC_REGISTRY[rubric.name] = rubric


for rubric in STEERING_RUBRICS:
    register_rubric(rubric)


def get_rubric(name: str) -> Rubric:
    try:
        return RUBRIC_REGISTRY[name]
    except KeyError as exc:
        choices = ", ".join(sorted(RUBRIC_REGISTRY))
        raise KeyError(f"unknown rubric {name!r}; choose from: {choices}") from exc


def resolve_rubrics(value: str) -> list[Rubric]:
    if value.strip() == "steering":
        return list(STEERING_RUBRICS)
    return [get_rubric(name.strip()) for name in value.split(",") if name.strip()]


__all__ = [
    "RUBRIC_REGISTRY",
    "RubricResult",
    "get_rubric",
    "register_rubric",
    "render_rubric",
    "resolve_rubrics",
    "validate_result",
]
