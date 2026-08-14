"""Generic normalized JSON, JSONL, and CSV ingestion."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from lodestar.models import Generation

GENERATION_SCHEMA = TypeAdapter(list[Generation]).json_schema()

KNOWN_GENERATION_FIELDS = {
    "id", "text", "prompt", "prompt_id", "condition", "model_name", "language",
    "target_concept", "steering_config", "seed", "metadata", "experiment",
}


def _decode_nested(row: dict[str, Any]) -> dict[str, Any]:
    decoded = dict(row)
    for field in ("steering_config", "metadata"):
        value = decoded.get(field)
        if isinstance(value, str) and value.strip():
            decoded[field] = json.loads(value)
    if decoded.get("seed") in ("", None):
        decoded["seed"] = None
    unknown_keys = set(decoded) - KNOWN_GENERATION_FIELDS
    if unknown_keys:
        metadata = dict(decoded.get("metadata") or {})
        for key in unknown_keys:
            metadata[key] = decoded.pop(key)
        decoded["metadata"] = metadata
    return decoded


def load_generic(path: str | Path) -> list[Generation]:
    source = Path(path)
    suffix = source.suffix.casefold()
    if suffix == ".jsonl":
        records = [
            json.loads(line)
            for line in source.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    elif suffix == ".csv":
        with source.open(encoding="utf-8-sig", newline="") as handle:
            records = list(csv.DictReader(handle))
    elif suffix == ".json":
        payload = json.loads(source.read_text(encoding="utf-8"))
        records = payload.get("generations", payload) if isinstance(payload, dict) else payload
    else:
        raise ValueError(f"unsupported input extension {source.suffix!r}; use JSON, JSONL, or CSV")
    if not isinstance(records, list):
        raise ValueError("generic input must be a list or contain a 'generations' list")
    try:
        return [Generation.model_validate(_decode_nested(record)) for record in records]
    except (ValidationError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid normalized generation data in {source}: {exc}") from exc


def write_schema(path: str | Path) -> Path:
    destination = Path(path)
    destination.write_text(json.dumps(GENERATION_SCHEMA, indent=2), encoding="utf-8")
    return destination

