from __future__ import annotations

import pytest

from lodestar.judges.base import DEFAULT_JUDGE_MAX_TOKENS, JUDGE_SYSTEM_PROMPT, JUDGE_TEMPERATURE
from lodestar.judges.cache import JudgeCache
from lodestar.judges.identity import execution_cache_key
from lodestar.judges.mock import MockJudge
from lodestar.rubrics import get_rubric, resolve_rubrics


def _key(generation, rubric, judge_model, repeat_index=0):
    return execution_cache_key(
        generation,
        rubric,
        model_name=judge_model,
        system_prompt=JUDGE_SYSTEM_PROMPT,
        max_tokens=DEFAULT_JUDGE_MAX_TOKENS,
        temperature=JUDGE_TEMPERATURE,
        repeat_index=repeat_index,
    )


@pytest.mark.asyncio
async def test_cache_hit_miss_and_content_addressing(tmp_path, sample_generations) -> None:
    cache = JudgeCache(tmp_path / "cache.sqlite")
    await cache.initialize()
    judge = MockJudge(cache)
    rubric = get_rubric("coherence")
    generation = sample_generations[0]
    first = await judge.judge_one(generation, rubric)
    second = await judge.judge_one(generation, rubric)
    assert not first.cached
    assert second.cached
    assert second.usage.total_tokens == 0
    changed = generation.model_copy(update={"text": generation.text + " changed"})
    assert _key(generation, rubric, judge.model_name) != _key(changed, rubric, judge.model_name)


@pytest.mark.asyncio
async def test_rubric_version_and_judge_invalidate_cache(tmp_path, sample_generations) -> None:
    cache = JudgeCache(tmp_path / "cache.sqlite")
    await cache.initialize()
    rubric = get_rubric("coherence")
    generation = sample_generations[0]
    judge = MockJudge(cache)
    await judge.judge_one(generation, rubric)
    bumped = rubric.model_copy(update={"version": "1.1"})
    assert await cache.get(_key(generation, bumped, judge.model_name), generation) is None
    assert await cache.get(_key(generation, rubric, "another-model"), generation) is None


@pytest.mark.asyncio
async def test_content_cache_rebinds_identical_text_to_new_generation(tmp_path, sample_generations) -> None:
    cache = JudgeCache(tmp_path / "cache.sqlite")
    await cache.initialize()
    rubric = get_rubric("coherence")
    judge = MockJudge(cache)
    first_generation = sample_generations[0]
    await judge.judge_one(first_generation, rubric)
    second_generation = first_generation.model_copy(
        update={"id": "different-generation", "prompt_id": "different-prompt"}
    )
    cached = await judge.judge_one(second_generation, rubric)
    assert cached.cached
    assert cached.generation_id == "different-generation"


@pytest.mark.asyncio
async def test_concurrent_batch_writes_dont_lock_the_database(tmp_path, sample_generations) -> None:
    """judge_batch fans out via asyncio.gather with no concurrency cap, so many
    tasks write to the same cache file at once -- this previously raised
    sqlite3.OperationalError: database is locked without WAL mode + a busy
    timeout (see FEATURE_EXPERIMENT_LOG.md section 16 in qwen-sae-interp,
    where 2898 concurrent mock-judge writes against one file reproduced it)."""
    cache = JudgeCache(tmp_path / "cache.sqlite")
    judge = MockJudge(cache)
    rubrics = resolve_rubrics("steering")
    items = [(generation, rubric) for generation in sample_generations for rubric in rubrics]
    judgments = await judge.judge_batch(items, repeats=3)
    assert len(judgments) == len(items) * 3
    assert all(judgment.score is not None for judgment in judgments)
