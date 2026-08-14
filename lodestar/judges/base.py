"""Judge protocol and shared orchestration helpers."""

from __future__ import annotations

from typing import Protocol

from lodestar.models import Generation, Judgment, Rubric

JUDGE_SYSTEM_PROMPT = "Return a single JSON object only. Never use markdown fences."
JUDGE_TEMPERATURE = 0
DEFAULT_JUDGE_MAX_TOKENS = 256
INVARIANCE_MODEL_VERSION = "1"


class Judge(Protocol):
    model_name: str

    async def judge_one(self, gen: Generation, rubric: Rubric) -> Judgment: ...

    async def judge_batch(
        self, items: list[tuple[Generation, Rubric]], repeats: int
    ) -> list[Judgment]: ...

