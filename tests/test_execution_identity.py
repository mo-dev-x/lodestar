from __future__ import annotations

import pytest

from lodestar.judges.base import DEFAULT_JUDGE_MAX_TOKENS, JUDGE_SYSTEM_PROMPT, JUDGE_TEMPERATURE
from lodestar.judges.cache import JudgeCache
from lodestar.judges.identity import execution_cache_key
from lodestar.models import Generation, Judgment, OrdinalScale, Rubric


def _generation(**overrides) -> Generation:
    fields = dict(
        text="alpha", prompt="Discuss winter travel.", prompt_id="pid", condition="baseline",
        model_name="m", language="en", target_concept="poutine", seed=1,
    )
    fields.update(overrides)
    return Generation(**fields)


def _rubric(**overrides) -> Rubric:
    # References every S-relevant Jinja variable render_rubric exposes, so this
    # helper is sensitive to text/target_concept/prompt/alias differences alike.
    fields = dict(
        name="coherence", version="1.0", description="d", scale=OrdinalScale(),
        prompt_template=(
            "TARGET: {{ target_concept }}\nTEXT: {{ generation.text }}\n"
            "PROMPT: {{ prompt }}\nALIASES: {{ aliases }}"
        ),
        output_schema={"type": "object"},
    )
    fields.update(overrides)
    return Rubric(**fields)


def _key(generation: Generation, rubric: Rubric, **overrides) -> str:
    params = dict(
        model_name="claude-test-20250101", system_prompt=JUDGE_SYSTEM_PROMPT,
        max_tokens=DEFAULT_JUDGE_MAX_TOKENS, temperature=JUDGE_TEMPERATURE, repeat_index=0,
    )
    params.update(overrides)
    return execution_cache_key(generation, rubric, **params)


def _judgment(generation: Generation, rubric: Rubric, *, score: float = 8.0) -> Judgment:
    return Judgment(
        generation_id=generation.id, rubric_name=rubric.name, rubric_version=rubric.version,
        score=score, rationale="r", judge_model="claude-test-20250101", raw_response="{}",
    )


# --- Before (fail) -- soundness regressions ---------------------------------


def test_same_text_different_target_concept_changes_key() -> None:
    poutine = _generation(target_concept="poutine")
    sushi = _generation(target_concept="sushi")
    assert _key(poutine, _rubric()) != _key(sushi, _rubric())


def test_same_text_different_prompt_changes_key() -> None:
    a = _generation(prompt="Discuss winter travel.")
    b = _generation(prompt="Describe your favorite dessert.")
    assert _key(a, _rubric()) != _key(b, _rubric())


def test_literal_mention_different_alias_sets_changes_key() -> None:
    generation = _generation()
    rubric_a = _rubric(name="literal_mention", aliases=("fries",))
    rubric_b = _rubric(name="literal_mention", aliases=("gravy",))
    assert _key(generation, rubric_a) != _key(generation, rubric_b)


def test_different_output_schema_same_template_changes_key() -> None:
    generation = _generation()
    rubric_a = _rubric(output_schema={"type": "object", "properties": {"score": {"type": "integer"}}})
    rubric_b = _rubric(output_schema={"type": "object", "properties": {"score": {"type": "number"}}})
    assert _key(generation, rubric_a) != _key(generation, rubric_b)


def test_different_system_prompt_changes_key() -> None:
    generation, rubric = _generation(), _rubric()
    assert _key(generation, rubric, system_prompt="A") != _key(generation, rubric, system_prompt="B")


def test_different_max_tokens_changes_key() -> None:
    generation, rubric = _generation(), _rubric()
    assert _key(generation, rubric, max_tokens=128) != _key(generation, rubric, max_tokens=256)


@pytest.mark.asyncio
async def test_end_to_end_target_concept_difference_does_not_share_cached_answer(tmp_path) -> None:
    # Regression test for the proven end-to-end defect: a `sushi` query must
    # never be served a `poutine` judgment.
    cache = JudgeCache(tmp_path / "cache.sqlite")
    await cache.initialize()
    rubric = _rubric()
    poutine_gen = _generation(target_concept="poutine")
    sushi_gen = _generation(target_concept="sushi")
    await cache.put(_key(poutine_gen, rubric), _judgment(poutine_gen, rubric))
    assert await cache.get(_key(sushi_gen, rubric), sushi_gen) is None


# --- After (also pass) -- tightness/canonicalization ------------------------


def test_alias_reorder_yields_identical_key() -> None:
    generation = _generation()
    rubric_a = _rubric(name="literal_mention", aliases=("fries", "gravy"))
    rubric_b = _rubric(name="literal_mention", aliases=("gravy", "fries"))
    assert _key(generation, rubric_a) == _key(generation, rubric_b)


def test_repeat_index_changes_key_identical_coordinates_share_key() -> None:
    generation, rubric = _generation(), _rubric()
    assert _key(generation, rubric, repeat_index=0) != _key(generation, rubric, repeat_index=1)
    assert _key(generation, rubric, repeat_index=0) == _key(generation, rubric, repeat_index=0)


@pytest.mark.asyncio
async def test_round_trip_serves_only_execution_identical_query(tmp_path) -> None:
    cache = JudgeCache(tmp_path / "cache.sqlite")
    await cache.initialize()
    generation, rubric = _generation(), _rubric()
    key = _key(generation, rubric)
    await cache.put(key, _judgment(generation, rubric))

    new_generation = generation.model_copy(update={"id": "new-id", "prompt_id": "new-prompt-id"})
    hit = await cache.get(key, new_generation)
    assert hit is not None
    assert hit.cached is True
    assert hit.generation_id == "new-id"

    # An execution-distinct query (different repeat_index) must miss.
    assert await cache.get(_key(generation, rubric, repeat_index=1), generation) is None
