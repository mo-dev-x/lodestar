"""Execution-identity helpers -- the single source of truth for the cache key.

Composes the (S, C, I, M, T) execution coordinates (Constitution §2.3) into one
cache key. Every caller that needs a cache key MUST go through
`execution_cache_key`; no other code path may construct one (THM3).
"""

from __future__ import annotations

from lodestar.judges.cache import cache_key
from lodestar.models import Generation, Rubric, stable_hash
from lodestar.rubrics.base import RENDER_RULES_VERSION, render_rubric


def instrument_id(rubric: Rubric, *, system_prompt: str, render_rules_version: str) -> str:
    return stable_hash(
        {
            "template": rubric.prompt_template,
            "schema": rubric.output_schema,
            "system": system_prompt,
            "render_rules": render_rules_version,
        }
    )


def method_fingerprint(model_name: str, *, max_tokens: int, temperature: float) -> str:
    return stable_hash({"model": model_name, "max_tokens": max_tokens, "temperature": temperature})


def execution_cache_key(
    generation: Generation,
    rubric: Rubric,
    *,
    model_name: str,
    system_prompt: str,
    max_tokens: int,
    temperature: float,
    repeat_index: int,
) -> str:
    rendered_prompt = render_rubric(rubric, generation)
    instrument = instrument_id(
        rubric, system_prompt=system_prompt, render_rules_version=RENDER_RULES_VERSION
    )
    method = method_fingerprint(model_name, max_tokens=max_tokens, temperature=temperature)
    return cache_key(rendered_prompt, rubric.name, rubric.version, instrument, method, repeat_index)
