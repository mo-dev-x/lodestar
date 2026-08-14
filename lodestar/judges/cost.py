"""Preflight token and dollar estimates plus actual-cost accounting."""

from __future__ import annotations

import re
from dataclasses import dataclass

from lodestar.models import Generation, Judgment, Rubric
from lodestar.rubrics.base import render_rubric


@dataclass(frozen=True)
class ModelPricing:
    input_per_million: float
    output_per_million: float


# Centralized by design. Values are standard (non-batch, non-cached) API rates in USD per
# million tokens. Verified live against https://platform.claude.com/docs/en/about-claude/pricing
# and https://platform.claude.com/docs/en/about-claude/model-deprecations on 2026-06-23.
# `claude-opus-4`, `claude-sonnet-4`, `claude-3-7-sonnet`, and `claude-3-5-haiku` were retired
# (the first two on 2026-06-15) and removed: requests to them now fail outright, so a price
# entry would be misleading. `claude-opus-4-1` is deprecated but still callable (tentative
# retirement 2026-08-05) and kept. Re-verify before any paid run -- this list goes stale fast.
MODEL_PRICING: dict[str, ModelPricing] = {
    "claude-fable-5": ModelPricing(10.0, 50.0),
    "claude-mythos-5": ModelPricing(10.0, 50.0),
    "claude-opus-4-8": ModelPricing(5.0, 25.0),
    "claude-opus-4-7": ModelPricing(5.0, 25.0),
    "claude-opus-4-6": ModelPricing(5.0, 25.0),
    "claude-opus-4-5": ModelPricing(5.0, 25.0),
    "claude-sonnet-4-6": ModelPricing(3.0, 15.0),
    "claude-sonnet-4-5": ModelPricing(3.0, 15.0),
    "claude-haiku-4-5": ModelPricing(1.0, 5.0),
    "claude-opus-4-1": ModelPricing(15.0, 75.0),  # deprecated, retiring no sooner than 2026-08-05
}


@dataclass(frozen=True)
class CostEstimate:
    calls: int
    cached_calls: int
    new_calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


def pricing_for(model_name: str) -> ModelPricing:
    matches = [(prefix, price) for prefix, price in MODEL_PRICING.items() if model_name.startswith(prefix)]
    if not matches:
        supported = ", ".join(sorted(MODEL_PRICING))
        raise ValueError(
            f"No pricing configured for {model_name!r}. Add it to MODEL_PRICING after "
            f"checking Anthropic's pricing page. Known prefixes: {supported}"
        )
    return max(matches, key=lambda item: len(item[0]))[1]


_SNAPSHOT_SUFFIX = re.compile(r"-\d{8}$")


def is_snapshot(model_name: str) -> bool:
    """True iff `model_name` is a resolved, immutable snapshot (THM3.C).

    No network resolution is performed -- Lodestar refuses moving aliases, it
    does not auto-resolve them.
    """
    return model_name == "mock-deterministic-v1" or bool(_SNAPSHOT_SUFFIX.search(model_name))


def estimate_tokens(text: str) -> int:
    """Conservative provider-independent approximation for preflight only."""
    return max(1, (len(text.encode("utf-8")) + 2) // 3)


def estimate(
    generations: list[Generation],
    rubrics: list[Rubric],
    repeats: int,
    judge_model: str,
    *,
    cached_calls: int = 0,
    expected_output_tokens: int = 96,
) -> CostEstimate:
    price = pricing_for(judge_model)
    prompts = [render_rubric(rubric, generation) for generation in generations for rubric in rubrics]
    calls = len(prompts) * repeats
    new_calls = max(0, calls - cached_calls)
    if calls:
        average_input = sum(estimate_tokens(prompt) for prompt in prompts) / len(prompts)
    else:
        average_input = 0
    input_tokens = round(average_input * new_calls)
    output_tokens = expected_output_tokens * new_calls
    cost = (
        input_tokens * price.input_per_million + output_tokens * price.output_per_million
    ) / 1_000_000
    return CostEstimate(calls, cached_calls, new_calls, input_tokens, output_tokens, cost)


def actual_cost(judgments: list[Judgment], judge_model: str) -> float:
    if judge_model.startswith("mock"):
        return 0.0
    price = pricing_for(judge_model)
    input_tokens = sum(judgment.usage.input_tokens for judgment in judgments)
    output_tokens = sum(judgment.usage.output_tokens for judgment in judgments)
    return (
        input_tokens * price.input_per_million + output_tokens * price.output_per_million
    ) / 1_000_000

