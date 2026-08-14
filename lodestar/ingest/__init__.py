"""Auto-detected ingestion for pipeline-native and generic generation data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lodestar.ingest.generic import GENERATION_SCHEMA, load_generic, write_schema
from lodestar.ingest.steering_json import is_steering_payload, load_steering_json
from lodestar.models import Generation


def load_generations(path: str | Path, **overrides: Any) -> list[Generation]:
    source = Path(path)
    if source.suffix.casefold() == ".json":
        payload = json.loads(source.read_text(encoding="utf-8"))
        if is_steering_payload(payload):
            return load_steering_json(source, **overrides)
    return load_generic(source)


__all__ = [
    "GENERATION_SCHEMA",
    "load_generations",
    "load_generic",
    "load_steering_json",
    "write_schema",
]

