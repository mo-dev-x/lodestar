"""Async Anthropic judge with bounded concurrency, repair, retry, and caching."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import anthropic
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter
from tqdm.asyncio import tqdm as atqdm

from lodestar.judges import identity
from lodestar.judges.base import (
    DEFAULT_JUDGE_MAX_TOKENS,
    INVARIANCE_MODEL_VERSION,
    JUDGE_SYSTEM_PROMPT,
    JUDGE_TEMPERATURE,
)
from lodestar.judges.cache import JudgeCache
from lodestar.judges.identity import execution_cache_key
from lodestar.models import Generation, Judgment, Rubric, TokenUsage
from lodestar.rubrics.base import RENDER_RULES_VERSION, render_rubric, validate_result

RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.InternalServerError,
)

# Keywords Anthropic's structured-output API rejects with a 400 on raw (non-Pydantic-derived)
# schemas. The SDK auto-strips these for schemas built from a native type via `messages.parse()`,
# but our rubrics hand-author plain dict schemas, so we replicate that stripping here and fold the
# constraint into the description instead, matching SDK behavior.
# https://platform.claude.com/docs/en/build-with-claude/structured-outputs (verified live, 2026-06)
_UNSUPPORTED_SCHEMA_KEYWORDS = (
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "maxItems",
)


def _sanitize_schema(node: Any) -> Any:
    """Strip JSON Schema keywords the structured-output API rejects, preserving constraint
    info in the node's description so the model is still informed of the original intent."""
    if isinstance(node, list):
        return [_sanitize_schema(item) for item in node]
    if not isinstance(node, dict):
        return node
    sanitized = {key: _sanitize_schema(value) for key, value in node.items()}
    hints: list[str] = []
    for keyword in _UNSUPPORTED_SCHEMA_KEYWORDS:
        if keyword in sanitized:
            hints.append(f"{keyword}: {sanitized.pop(keyword)}")
    if sanitized.pop("uniqueItems", False):
        hints.append("items must be unique")
    min_items = sanitized.get("minItems")
    if min_items is not None and min_items not in (0, 1):
        hints.append(f"minItems: {sanitized.pop('minItems')}")
    if hints:
        suffix = f"({'; '.join(hints)})"
        existing = sanitized.get("description", "")
        sanitized["description"] = f"{existing} {suffix}".strip() if existing else suffix
    return sanitized


class AnthropicJudge:
    def __init__(
        self,
        model_name: str,
        *,
        api_key: str | None = None,
        concurrency: int = 8,
        cache: JudgeCache | None = None,
        max_tokens: int = 256,
        client: anthropic.AsyncAnthropic | None = None,
    ) -> None:
        self.model_name = model_name
        self.client = client or anthropic.AsyncAnthropic(api_key=api_key)
        self.semaphore = asyncio.Semaphore(concurrency)
        self.cache = cache
        self.max_tokens = max_tokens

    @retry(
        retry=retry_if_exception_type(RETRYABLE),
        stop=stop_after_attempt(6),
        wait=wait_exponential_jitter(initial=1, max=30),
        reraise=True,
    )
    async def _request(
        self,
        prompt: str,
        rubric: Rubric,
        *,
        repair_text: str | None = None,
    ) -> Any:
        user = prompt
        if repair_text is not None:
            user = (
                "The response below was invalid. Return only valid JSON matching the schema; "
                "preserve the intended judgment.\n\nINVALID RESPONSE:\n" + repair_text
            )
        async with self.semaphore:
            return await self.client.messages.create(
                model=self.model_name,
                max_tokens=self.max_tokens,
                temperature=JUDGE_TEMPERATURE,
                system=JUDGE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user}],
                output_config={
                    "format": {
                        "type": "json_schema",
                        "schema": _sanitize_schema(rubric.output_schema),
                    }
                },
            )

    @staticmethod
    def _response_text(message: Any) -> str:
        return "".join(
            block.text for block in message.content if getattr(block, "type", None) == "text"
        )

    @staticmethod
    def _usage(message: Any) -> TokenUsage:
        usage = message.usage
        return TokenUsage(
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
        )

    async def _judge(self, gen: Generation, rubric: Rubric, repeat_index: int) -> Judgment:
        key = execution_cache_key(
            gen,
            rubric,
            model_name=self.model_name,
            system_prompt=JUDGE_SYSTEM_PROMPT,
            max_tokens=self.max_tokens or DEFAULT_JUDGE_MAX_TOKENS,
            temperature=JUDGE_TEMPERATURE,
            repeat_index=repeat_index,
        )
        if self.cache:
            hit = await self.cache.get(key, gen)
            if hit:
                return hit
        prompt = render_rubric(rubric, gen)
        messages: list[Any] = []
        parse_error = ""
        result = None
        raw = ""
        for attempt in range(2):
            message = await self._request(
                prompt,
                rubric,
                repair_text=raw if attempt == 1 else None,
            )
            messages.append(message)
            raw = self._response_text(message)
            try:
                data = json.loads(raw)
                result = validate_result(rubric, data)
                break
            except (json.JSONDecodeError, ValueError) as exc:
                parse_error = str(exc)
        usage = TokenUsage(
            input_tokens=sum(self._usage(message).input_tokens for message in messages),
            output_tokens=sum(self._usage(message).output_tokens for message in messages),
            cache_read_tokens=sum(self._usage(message).cache_read_tokens for message in messages),
            cache_creation_tokens=sum(
                self._usage(message).cache_creation_tokens for message in messages
            ),
        )
        deterministic_score = None
        literal_count = None
        judge_crosscheck_score = result.score if result else None
        if rubric.deterministic:
            terms = (gen.target_concept, *rubric.aliases)
            literal_count = sum(
                len(re.findall(re.escape(term), gen.text, flags=re.IGNORECASE))
                for term in terms
                if term
            )
            deterministic_score = literal_count > 0
        judgment = Judgment(
            generation_id=gen.id,
            rubric_name=rubric.name,
            rubric_version=rubric.version,
            score=deterministic_score if deterministic_score is not None else (result.score if result else None),
            rationale=result.rationale if result else "Judge response could not be parsed.",
            judge_model=self.model_name,
            repeat_index=repeat_index,
            raw_response=raw,
            usage=usage,
            instrument_id=identity.instrument_id(
                rubric, system_prompt=JUDGE_SYSTEM_PROMPT, render_rules_version=RENDER_RULES_VERSION
            ),
            invariance_version=INVARIANCE_MODEL_VERSION,
            metadata={
                "count": literal_count if literal_count is not None else (result.count if result else None),
                "judge_crosscheck_score": judge_crosscheck_score if rubric.deterministic else None,
                "judge_grep_disagreement": (
                    bool(judge_crosscheck_score != deterministic_score)
                    if rubric.deterministic and result is not None
                    else None
                ),
                "degeneration": "parse_failure" if result is None else None,
                "parse_error": parse_error or None,
                "repair_attempted": len(messages) == 2,
            },
        )
        if self.cache:
            await self.cache.put(key, judgment)
        return judgment

    async def judge_one(self, gen: Generation, rubric: Rubric) -> Judgment:
        if self.cache:
            await self.cache.initialize()
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
        return list(await atqdm.gather(*tasks, desc="Judging", unit="call"))
