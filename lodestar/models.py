"""Serializable, provenance-preserving data models used throughout Lodestar."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator


def stable_hash(value: Any, *, length: int = 64) -> str:
    """Return a stable SHA-256 digest for JSON-serializable data."""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=False)
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:length]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DecodingParams(FrozenModel):
    temperature: float = Field(default=0.7, ge=0)
    top_p: float = Field(default=0.9, gt=0, le=1)
    repetition_penalty: float = Field(default=1.0, gt=0)
    no_repeat_ngram: int = Field(default=0, ge=0)
    max_new_tokens: int = Field(default=256, gt=0)
    do_sample: bool = True


class SteeringConfig(FrozenModel):
    sae_checkpoint_id: str
    hook_layer: int = Field(ge=0)
    feature_ids: tuple[int, ...]
    weights: tuple[float, ...]
    scale: float
    decoding: DecodingParams = Field(default_factory=DecodingParams)

    @model_validator(mode="after")
    def matching_features_and_weights(self) -> SteeringConfig:
        if not self.feature_ids:
            raise ValueError("feature_ids cannot be empty")
        if len(self.feature_ids) != len(self.weights):
            raise ValueError("feature_ids and weights must have equal lengths")
        return self

    def config_hash(self) -> str:
        return stable_hash(self)

    def sweep_hash(self) -> str:
        """Identify one sweep while deliberately excluding the swept scale."""
        payload = self.model_dump(mode="json")
        payload.pop("scale")
        return stable_hash(payload)


class Generation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = ""
    text: str
    prompt: str
    prompt_id: str
    condition: Literal["baseline", "steered", "control"]
    model_name: str
    language: str = Field(min_length=2, max_length=16)
    target_concept: str
    experiment: str = "default"
    steering_config: SteeringConfig | None = None
    seed: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def promote_experiment_from_metadata(self) -> Generation:
        if self.experiment == "default" and "experiment" in self.metadata:
            self.experiment = self.metadata["experiment"]
        return self

    @model_validator(mode="after")
    def validate_and_identify(self) -> Generation:
        if self.condition != "baseline" and self.steering_config is None:
            raise ValueError(f"{self.condition} generations require steering_config")
        if not self.id:
            config = self.steering_config.config_hash() if self.steering_config else "baseline"
            self.id = stable_hash(
                {
                    "text": self.text,
                    "prompt": self.prompt,
                    "prompt_id": self.prompt_id,
                    "target_concept": self.target_concept,
                    "language": self.language,
                    "config": config,
                    "condition": self.condition,
                    "seed": self.seed,
                },
                length=24,
            )
        return self

    @property
    def config_hash(self) -> str:
        return self.steering_config.config_hash() if self.steering_config else "baseline"

    @property
    def sweep_hash(self) -> str:
        return self.steering_config.sweep_hash() if self.steering_config else "baseline"


class ScoreScale(FrozenModel):
    kind: str


class OrdinalScale(ScoreScale):
    kind: Literal["ordinal"] = "ordinal"
    minimum: int = 1
    maximum: int = 10


class BinaryScale(ScoreScale):
    kind: Literal["binary"] = "binary"


class CategoricalScale(ScoreScale):
    kind: Literal["categorical"] = "categorical"
    categories: tuple[str, ...]
    multiple: bool = False


Scale = OrdinalScale | BinaryScale | CategoricalScale
ScoreValue = float | bool | str | list[str] | None


class Rubric(FrozenModel):
    name: str
    version: str
    description: str
    scale: Scale
    prompt_template: str
    output_schema: dict[str, Any]
    aliases: tuple[str, ...] = ()
    deterministic: bool = False


class TokenUsage(FrozenModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)
    cache_creation_tokens: int = Field(default=0, ge=0)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class Judgment(BaseModel):
    id: str = ""
    generation_id: str
    rubric_name: str
    rubric_version: str
    score: ScoreValue = None
    rationale: str
    judge_model: str
    repeat_index: int = Field(default=0, ge=0)
    raw_response: str
    usage: TokenUsage = Field(default_factory=TokenUsage)
    cached: bool = False
    instrument_id: str = ""
    invariance_version: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def identify(self) -> Judgment:
        if not self.id:
            self.id = stable_hash(
                {
                    "generation": self.generation_id,
                    "rubric": self.rubric_name,
                    "version": self.rubric_version,
                    "judge": self.judge_model,
                    "repeat": self.repeat_index,
                },
                length=24,
            )
        return self


class RunManifest(BaseModel):
    config_hash: str = ""
    tool_version: str
    started_at: datetime
    finished_at: datetime | None = None
    elapsed_seconds: float = 0.0
    total_cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_hits: int = 0
    seeds: list[int] = Field(default_factory=list)
    command: list[str] = Field(default_factory=list)
    judge_snapshot: str = ""
    invariance_version: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvalRun(BaseModel):
    id: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    generations: list[Generation]
    judgments: list[Judgment]
    rubrics: list[Rubric]
    judge_model: str
    n_repeats: int = Field(ge=1)
    manifest: RunManifest

    @model_validator(mode="after")
    def identify_and_validate(self) -> EvalRun:
        generation_ids = {generation.id for generation in self.generations}
        missing = {j.generation_id for j in self.judgments} - generation_ids
        if missing:
            raise ValueError(f"judgments reference unknown generations: {sorted(missing)}")
        if not self.id:
            self.id = stable_hash(
                {
                    "created_at": self.created_at.isoformat(),
                    "generation_ids": sorted(generation_ids),
                    "judge_model": self.judge_model,
                    "rubrics": [(r.name, r.version) for r in self.rubrics],
                },
                length=24,
            )
        return self

    def by_config(self) -> dict[str, list[Generation]]:
        grouped: dict[str, list[Generation]] = defaultdict(list)
        for generation in self.generations:
            grouped[generation.config_hash].append(generation)
        return dict(grouped)

    def scores(self, rubric: str | None = None, aggregate: str = "median") -> pd.DataFrame:
        """Return one tidy row per generation/rubric with repeat scores aggregated."""
        generations = {generation.id: generation for generation in self.generations}
        rows: list[dict[str, Any]] = []
        grouped: dict[tuple[str, str], list[Judgment]] = defaultdict(list)
        for judgment in self.judgments:
            if rubric is None or judgment.rubric_name == rubric:
                grouped[(judgment.generation_id, judgment.rubric_name)].append(judgment)
        for (generation_id, rubric_name), values in grouped.items():
            generation = generations[generation_id]
            raw_scores = [value.score for value in values if value.score is not None]
            numeric = [float(value) for value in raw_scores if isinstance(value, (int, float, bool))]
            if numeric:
                if aggregate == "median":
                    score: Any = float(np.median(numeric))
                elif aggregate == "mean":
                    score = float(np.mean(numeric))
                else:
                    raise ValueError("aggregate must be 'median' or 'mean'")
            elif raw_scores:
                normalized = [json.dumps(value, sort_keys=True) for value in raw_scores]
                score = json.loads(max(set(normalized), key=normalized.count))
            else:
                score = np.nan
            config = generation.steering_config
            rows.append(
                {
                    "generation_id": generation_id,
                    "rubric": rubric_name,
                    "score": score,
                    "condition": generation.condition,
                    "config_hash": generation.config_hash,
                    "sweep_hash": generation.sweep_hash,
                    "scale": config.scale if config else 0.0,
                    "feature_ids": list(config.feature_ids) if config else [],
                    "language": generation.language,
                    "model_name": generation.model_name,
                    "prompt_id": generation.prompt_id,
                    "target_concept": generation.target_concept,
                    "experiment": generation.experiment,
                    "n_valid": len(raw_scores),
                }
            )
        return pd.DataFrame(rows)

    def save(self, directory: str | Path) -> Path:
        destination = Path(directory)
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "run.json").write_text(
            self.model_dump_json(indent=2), encoding="utf-8"
        )
        (destination / "manifest.json").write_text(
            self.manifest.model_dump_json(indent=2), encoding="utf-8"
        )
        return destination

    @classmethod
    def load(cls, directory: str | Path) -> EvalRun:
        path = Path(directory)
        if path.is_dir():
            path = path / "run.json"
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

