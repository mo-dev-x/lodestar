"""Content-addressed SQLite judgment cache."""

from __future__ import annotations

import hashlib
from pathlib import Path

import aiosqlite

from lodestar.models import Generation, Judgment, TokenUsage


def cache_key(
    rendered_prompt: str,
    criterion_name: str,
    criterion_version: str,
    instrument_id: str,
    method_fingerprint: str,
    repeat_index: int,
) -> str:
    payload = "‖".join(
        [
            rendered_prompt,
            criterion_name,
            criterion_version,
            instrument_id,
            method_fingerprint,
            str(repeat_index),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class JudgeCache:
    # judge_batch fans out one task per (generation, rubric, repeat) via
    # asyncio.gather with no concurrency cap (MockJudge) or up to
    # `concurrency` concurrent requests (AnthropicJudge); each call opens its
    # own SQLite connection, so without WAL mode and a busy timeout,
    # concurrent writers collide and raise "database is locked".
    BUSY_TIMEOUT_SECONDS = 30

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _connect(self) -> aiosqlite.Connection:
        return aiosqlite.connect(self.path, timeout=self.BUSY_TIMEOUT_SECONDS)

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with self._connect() as database:
            await database.execute("PRAGMA journal_mode=WAL")
            await database.execute("PRAGMA busy_timeout=30000")
            await database.execute(
                """
                CREATE TABLE IF NOT EXISTS judgments_v2 (
                    cache_key TEXT PRIMARY KEY,
                    judgment_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await database.commit()

    async def get(self, key: str, generation: Generation) -> Judgment | None:
        async with self._connect() as database:
            cursor = await database.execute(
                "SELECT judgment_json FROM judgments_v2 WHERE cache_key = ?", (key,)
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        original = Judgment.model_validate_json(row[0])
        payload = original.model_dump()
        payload.update(
            id="",
            generation_id=generation.id,
            cached=True,
            usage=TokenUsage(),
            metadata={**original.metadata, "cached_usage": original.usage.model_dump()},
        )
        return Judgment.model_validate(payload)

    async def put(self, key: str, judgment: Judgment) -> None:
        async with self._connect() as database:
            await database.execute(
                "INSERT OR REPLACE INTO judgments_v2(cache_key, judgment_json) VALUES (?, ?)",
                (key, judgment.model_dump_json()),
            )
            await database.commit()

    async def contains(self, key: str) -> bool:
        async with self._connect() as database:
            cursor = await database.execute(
                "SELECT 1 FROM judgments_v2 WHERE cache_key = ?", (key,)
            )
            return await cursor.fetchone() is not None

    async def count_hits(self, keys: list[str]) -> int:
        if not self.path.exists():
            return 0
        total = 0
        for key in keys:
            total += int(await self.contains(key))
        return total
