"""Runtime configuration, API-key resolution, and deterministic seed handling."""

from __future__ import annotations

import os
import random
from pathlib import Path

import numpy as np
from pydantic import BaseModel, Field


class RunConfig(BaseModel):
    judge_model: str = "claude-sonnet-4-5-20250929"
    repeats: int = Field(default=3, ge=1)
    concurrency: int = Field(default=8, ge=1)
    seed: int = 42
    budget_usd: float | None = Field(default=None, gt=0)
    cache_path: Path = Path("run/cache.sqlite")
    api_key_env: str = "ANTHROPIC_API_KEY"

    def api_key(self) -> str:
        value = os.getenv(self.api_key_env)
        if not value:
            raise RuntimeError(
                f"Missing {self.api_key_env}. Set it or use --judge mock for an offline run."
            )
        return value

    def apply_seed(self) -> None:
        random.seed(self.seed)
        np.random.seed(self.seed)

