from __future__ import annotations

import pytest

from lodestar.judges.mock import MockJudge
from lodestar.rubrics import resolve_rubrics


@pytest.mark.asyncio
async def test_full_offline_eval_is_deterministic(sample_generations) -> None:
    judge = MockJudge()
    rubrics = resolve_rubrics("steering")
    items = [(generation, rubric) for generation in sample_generations for rubric in rubrics]
    first = await judge.judge_batch(items, repeats=3)
    second = await judge.judge_batch(items, repeats=3)
    assert [value.score for value in first] == [value.score for value in second]
    assert len(first) == len(sample_generations) * 6 * 3
    assert all(value.judge_model == "mock-deterministic-v1" for value in first)


@pytest.mark.asyncio
async def test_literal_mention_has_count(sample_generations) -> None:
    judgment = await MockJudge().judge_one(
        sample_generations[1], resolve_rubrics("literal_mention")[0]
    )
    assert judgment.score is True
    assert judgment.metadata["count"] == 1

