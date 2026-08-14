from __future__ import annotations

import json

import pytest

from lodestar.ingest import load_generations, load_generic, load_steering_json


def test_real_pipeline_fixture_normalizes(fixture_dir) -> None:
    path = fixture_dir / "generations_sample.json"
    generations = load_steering_json(
        path,
        target_concept="poutine",
        model_name="Qwen/Qwen2.5-14B",
        language="en",
        sae_checkpoint_id="checkpoint-1",
        hook_layer=24,
        random_feature_id=17,
        feature_weights=[1.0, 0.5],
    )
    assert len(generations) == 8
    assert {value.condition for value in generations} == {"baseline", "steered", "control"}
    assert any(value.experiment == "ablation" for value in generations)
    steered = next(
        value for value in generations
        if value.condition == "steered" and value.experiment == "steering"
    )
    assert steered.steering_config.feature_ids == (65223, 10413)
    assert steered.steering_config.weights == (1.0, 0.5)
    assert steered.steering_config.hook_layer == 24
    assert load_generations(path, target_concept="poutine")[0].text


def test_generic_jsonl_and_invalid_input(tmp_path, sample_generations) -> None:
    path = tmp_path / "generations.jsonl"
    path.write_text(
        "\n".join(value.model_dump_json() for value in sample_generations[:2]), encoding="utf-8"
    )
    restored = load_generic(path)
    assert [value.id for value in restored] == [value.id for value in sample_generations[:2]]
    # F3/F8: the generic adapter never sets `experiment`; INV-TYPED requires it
    # default to a typed value ("default"), never fall back to metadata-derived
    # "unknown".
    assert all(value.experiment == "default" for value in restored)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"unexpected": True}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_generic(bad)


def test_generic_adapter_routes_unknown_keys_into_metadata(tmp_path) -> None:
    # INV-NOHIDE / F9: Generation is extra="forbid" at the schema boundary, so
    # a third-party producer's unknown field must be captured under `metadata`
    # by the adapter, not silently accepted as a hidden top-level attribute.
    path = tmp_path / "generic.json"
    path.write_text(
        json.dumps(
            [
                {
                    "text": "hello", "prompt": "p", "prompt_id": "pid", "condition": "baseline",
                    "model_name": "m", "language": "en", "target_concept": "z", "foo": "bar",
                }
            ]
        ),
        encoding="utf-8",
    )
    restored = load_generic(path)
    assert restored[0].metadata["foo"] == "bar"

