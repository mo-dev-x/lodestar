"""Metric plugin protocol and registry.

A metric is a pure function from an `EvalRun` to a tidy `DataFrame` — no judge
calls, no I/O. The six built-ins in `derived.py` already had this shape
informally; `MetricPlugin` names it and `METRIC_REGISTRY` makes it
discoverable, so another lab can add a metric without editing `derived.py`.
"""

from __future__ import annotations

from typing import Any, Protocol

import pandas as pd

from lodestar.models import EvalRun


class MetricPlugin(Protocol):
    def __call__(self, run: EvalRun, **kwargs: Any) -> pd.DataFrame: ...


METRIC_REGISTRY: dict[str, MetricPlugin] = {}


def register_metric(name: str, plugin: MetricPlugin) -> None:
    METRIC_REGISTRY[name] = plugin
