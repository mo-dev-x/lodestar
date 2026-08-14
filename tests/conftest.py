from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from lodestar.judges.mock import MockJudge
from lodestar.models import DecodingParams, EvalRun, Generation, RunManifest, SteeringConfig
from lodestar.rubrics.steering import STEERING_RUBRICS


@pytest.fixture
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_generations() -> list[Generation]:
    decoding = DecodingParams(temperature=0.7)

    def config(scale: float, feature: int = 42) -> SteeringConfig:
        return SteeringConfig(
            sae_checkpoint_id="sae-test",
            hook_layer=12,
            feature_ids=(feature,),
            weights=(1.0,),
            scale=scale,
            decoding=decoding,
        )

    rows = [
        Generation(
            text="A calm answer about winter travel.", prompt="Discuss winter travel.", prompt_id="p-en",
            condition="baseline", model_name="model-a", language="en", target_concept="poutine", seed=1,
        )
    ]
    for language, prompt_id in [("en", "p-en"), ("fr", "p-fr")]:
        prompt = "Discuss winter travel." if language == "en" else "Parlez des voyages d'hiver."
        for scale in (1.0, 2.0, 3.0):
            rows.append(
                Generation(
                    text=f"Poutine with curds and gravy at scale {scale}.", prompt=prompt,
                    prompt_id=prompt_id, condition="steered", model_name="model-a", language=language,
                    target_concept="poutine", steering_config=config(scale), seed=1,
                )
            )
            rows.append(
                Generation(
                    text=f"Winter travel advice at scale {scale}.", prompt=prompt,
                    prompt_id=prompt_id, condition="control", model_name="model-a", language=language,
                    target_concept="poutine", steering_config=config(scale, feature=99), seed=1,
                )
            )
    return rows


@pytest.fixture
async def sample_run(sample_generations: list[Generation]) -> EvalRun:
    judge = MockJudge()
    judgments = await judge.judge_batch(
        [(generation, rubric) for generation in sample_generations for rubric in STEERING_RUBRICS],
        repeats=3,
    )
    now = datetime.now(UTC)
    return EvalRun(
        generations=sample_generations,
        judgments=judgments,
        rubrics=list(STEERING_RUBRICS),
        judge_model=judge.model_name,
        n_repeats=3,
        manifest=RunManifest(tool_version="test", started_at=now, finished_at=now),
    )

