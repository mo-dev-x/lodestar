"""Derived steering metrics and statistical primitives."""

from lodestar.metrics.base import METRIC_REGISTRY, MetricPlugin, register_metric
from lodestar.metrics.derived import (
    coherence_relevance_frontier,
    control_gap,
    cross_lingual_transfer,
    cross_model_comparison,
    optimal_operating_points,
    parse_objective,
    steering_efficacy_scores,
)

register_metric("coherence_relevance_frontier", coherence_relevance_frontier)
register_metric("optimal_operating_points", optimal_operating_points)
register_metric("control_gap", control_gap)
register_metric("cross_lingual_transfer", cross_lingual_transfer)
register_metric("cross_model_comparison", cross_model_comparison)
register_metric("steering_efficacy_scores", steering_efficacy_scores)

# The report generators resolve exactly these six through METRIC_REGISTRY by
# name (see report/html.py) -- anything registered under a different name is
# a third party's custom metric and gets a generic "Custom metrics" table
# instead of one of the six built-in panels, which are each wired to a
# specific known column shape and can't generically absorb an unknown one.
BUILTIN_METRIC_NAMES = frozenset(
    {
        "coherence_relevance_frontier",
        "optimal_operating_points",
        "control_gap",
        "cross_lingual_transfer",
        "cross_model_comparison",
        "steering_efficacy_scores",
    }
)

__all__ = [
    "BUILTIN_METRIC_NAMES",
    "METRIC_REGISTRY",
    "MetricPlugin",
    "coherence_relevance_frontier",
    "control_gap",
    "cross_lingual_transfer",
    "cross_model_comparison",
    "optimal_operating_points",
    "parse_objective",
    "register_metric",
    "steering_efficacy_scores",
]

