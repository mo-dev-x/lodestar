"""Deterministic, offline judge for tests, CI, dry runs, and demos."""

from __future__ import annotations

import asyncio
import json
import re
from collections import Counter
from typing import Any

from lodestar.judges import identity
from lodestar.judges.base import (
    DEFAULT_JUDGE_MAX_TOKENS,
    INVARIANCE_MODEL_VERSION,
    JUDGE_SYSTEM_PROMPT,
    JUDGE_TEMPERATURE,
)
from lodestar.judges.cache import JudgeCache
from lodestar.judges.identity import execution_cache_key
from lodestar.models import Generation, Judgment, Rubric, TokenUsage, stable_hash
from lodestar.rubrics.base import RENDER_RULES_VERSION


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold(), flags=re.UNICODE)


class MockJudge:
    model_name = "mock-deterministic-v1"

    def __init__(self, cache: JudgeCache | None = None, *, concurrency: int = 16) -> None:
        self.cache = cache
        self.semaphore = asyncio.Semaphore(concurrency)

    def _result(self, generation: Generation, rubric: Rubric, repeat_index: int) -> dict[str, Any]:
        text_tokens = _tokens(generation.text)
        target_tokens = _tokens(generation.target_concept)
        prompt_tokens = set(_tokens(generation.prompt))
        counts = Counter(text_tokens)
        mention_count = sum(
            generation.text.casefold().count(term.casefold())
            for term in (generation.target_concept, *rubric.aliases)
            if term
        )
        target_overlap = sum(counts[token] for token in target_tokens)
        prompt_overlap = len(prompt_tokens.intersection(text_tokens)) / max(1, len(prompt_tokens))
        repeated = max(counts.values(), default=0)
        jitter = int(stable_hash([generation.id, rubric.name, repeat_index], length=2), 16) % 3 - 1

        if rubric.name == "literal_mention":
            return {
                "score": mention_count > 0,
                "count": mention_count,
                "rationale": f"Found {mention_count} literal target/alias occurrence(s).",
            }
        if rubric.name == "concept_relevance":
            base = 9 if target_overlap else 2
            score = max(1, min(10, base + jitter))
            return {"score": score, "rationale": "Deterministic lexical relevance proxy."}
        if rubric.name == "coherence":
            penalty = 5 if repeated >= 6 else 2 if repeated >= 4 else 0
            length_penalty = 3 if len(text_tokens) < 3 else 0
            score = max(1, min(10, 9 - penalty - length_penalty + jitter))
            return {"score": score, "rationale": "Deterministic fluency and repetition proxy."}
        if rubric.name == "prompt_adherence":
            score = max(1, min(10, round(1 + 9 * prompt_overlap) + jitter))
            return {"score": score, "rationale": "Deterministic prompt-token overlap proxy."}
        if rubric.name == "integration_naturalness":
            base = 2 if not target_overlap else round(5 + 4 * prompt_overlap)
            score = max(1, min(10, base + jitter))
            return {"score": score, "rationale": "Deterministic integration proxy."}
        flags: list[str] = []
        if repeated >= 6:
            flags.append("repetition_loop")
        if len(text_tokens) < 2:
            flags.append("gibberish")
        if not flags:
            flags.append("none")
        return {"score": flags, "rationale": "Deterministic degeneration heuristic."}

    async def _judge(self, gen: Generation, rubric: Rubric, repeat_index: int) -> Judgment:
        async with self.semaphore:
            key = execution_cache_key(
                gen,
                rubric,
                model_name=self.model_name,
                system_prompt=JUDGE_SYSTEM_PROMPT,
                max_tokens=DEFAULT_JUDGE_MAX_TOKENS,
                temperature=JUDGE_TEMPERATURE,
                repeat_index=repeat_index,
            )
            if self.cache:
                hit = await self.cache.get(key, gen)
                if hit:
                    return hit
            result = self._result(gen, rubric, repeat_index)
            raw = json.dumps(result, ensure_ascii=False)
            judgment = Judgment(
                generation_id=gen.id,
                rubric_name=rubric.name,
                rubric_version=rubric.version,
                score=result["score"],
                rationale=result["rationale"],
                judge_model=self.model_name,
                repeat_index=repeat_index,
                raw_response=raw,
                usage=TokenUsage(),
                instrument_id=identity.instrument_id(
                    rubric, system_prompt=JUDGE_SYSTEM_PROMPT, render_rules_version=RENDER_RULES_VERSION
                ),
                invariance_version=INVARIANCE_MODEL_VERSION,
                metadata={"count": result.get("count")},
            )
            if self.cache:
                await self.cache.put(key, judgment)
            return judgment

    async def judge_one(self, gen: Generation, rubric: Rubric) -> Judgment:
        return await self._judge(gen, rubric, 0)

    async def judge_batch(
        self, items: list[tuple[Generation, Rubric]], repeats: int
    ) -> list[Judgment]:
        if repeats < 1:
            raise ValueError("repeats must be at least one")
        if self.cache:
            await self.cache.initialize()
        tasks = [
            self._judge(generation, rubric, repeat_index)
            for generation, rubric in items
            for repeat_index in range(repeats)
        ]
        return list(await asyncio.gather(*tasks))

