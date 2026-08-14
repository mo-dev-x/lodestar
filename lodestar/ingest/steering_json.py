"""Adapter for the repository's existing nested steering generations.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lodestar.models import DecodingParams, Generation, SteeringConfig, stable_hash


def is_steering_payload(payload: Any) -> bool:
    return isinstance(payload, dict) and (
        isinstance(payload.get("steering", {}).get("prompts"), dict)
        or ("prompts" in payload and "feature_id" in payload)
    )


def _feature_tuple(value: Any, fallback: int = 0) -> tuple[int, ...]:
    if value is None:
        return (fallback,)
    if isinstance(value, list):
        return tuple(int(item) for item in value)
    return (int(value),)


def _text(value: Any) -> tuple[str, dict[str, Any]]:
    if isinstance(value, str):
        return value, {}
    if isinstance(value, dict) and "text" in value:
        return str(value["text"]), {key: item for key, item in value.items() if key != "text"}
    raise ValueError(f"generation entry must be text or contain 'text'; got {type(value).__name__}")


def load_steering_json(
    path: str | Path,
    *,
    target_concept: str = "poutine",
    model_name: str = "unknown-model",
    language: str = "en",
    sae_checkpoint_id: str = "unknown-sae",
    hook_layer: int = 0,
    random_feature_id: int = 0,
    feature_weights: list[float] | None = None,
    seed: int | None = None,
    decoding: DecodingParams | None = None,
) -> list[Generation]:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not is_steering_payload(payload):
        raise ValueError(f"{source} does not match the steering-pipeline schema")
    steering = payload.get("steering", payload)
    feature_ids = _feature_tuple(steering.get("feature_id"))
    weights = tuple(feature_weights or [1.0] * len(feature_ids))
    decoding = decoding or DecodingParams()
    generations: list[Generation] = []

    def add(
        prompt: str,
        entry: Any,
        condition: str,
        scale: float | None,
        features: tuple[int, ...] | None,
        experiment: str,
    ) -> None:
        text, source_metadata = _text(entry)
        prompt_id = stable_hash({"prompt": prompt, "experiment": experiment}, length=16)
        config = None
        if condition != "baseline":
            selected = features or feature_ids
            selected_weights = weights if len(selected) == len(weights) else (1.0,) * len(selected)
            config = SteeringConfig(
                sae_checkpoint_id=sae_checkpoint_id,
                hook_layer=hook_layer,
                feature_ids=selected,
                weights=selected_weights,
                scale=float(scale if scale is not None else 0.0),
                decoding=decoding,
            )
        generations.append(
            Generation(
                text=text,
                prompt=prompt,
                prompt_id=prompt_id,
                condition=condition,
                model_name=model_name,
                language=language,
                target_concept=target_concept,
                experiment=experiment,
                steering_config=config,
                seed=seed,
                metadata={
                    "source_file": str(source),
                    **source_metadata,
                },
            )
        )

    for prompt, result in steering.get("prompts", {}).items():
        if result.get("baseline") is not None:
            add(prompt, result["baseline"], "baseline", None, None, "steering")
        for scale, entry in result.get("steered", {}).items():
            add(prompt, entry, "steered", float(scale), feature_ids, "steering")
        for scale, entry in result.get("random_control", {}).items():
            add(
                prompt,
                entry,
                "control",
                float(scale),
                (int(random_feature_id),),
                "steering",
            )

    ablation = payload.get("ablation")
    if isinstance(ablation, dict):
        ablation_features = _feature_tuple(ablation.get("feature_id"), feature_ids[0])
        for prompt, result in ablation.get("prompts", {}).items():
            if result.get("baseline") is not None:
                add(prompt, result["baseline"], "baseline", None, None, "ablation")
            if result.get("ablated") is not None:
                add(prompt, result["ablated"], "steered", 0.0, ablation_features, "ablation")
            if result.get("control_ablated") is not None:
                add(
                    prompt,
                    result["control_ablated"],
                    "control",
                    0.0,
                    (int(random_feature_id),),
                    "ablation",
                )
    if not generations:
        raise ValueError(f"{source} contains no recognized generations")
    return generations

