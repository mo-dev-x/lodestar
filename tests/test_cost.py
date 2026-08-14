from __future__ import annotations

import pytest

from lodestar.judges.cost import is_snapshot, pricing_for


@pytest.mark.parametrize(
    ("model_name", "input_per_million", "output_per_million"),
    [
        # CLI default judge model -- must stay priced and correct.
        ("claude-sonnet-4-5-20250929", 3.0, 15.0),
        ("claude-sonnet-4-6", 3.0, 15.0),
        ("claude-opus-4-6", 5.0, 25.0),
        ("claude-opus-4-7", 5.0, 25.0),
        ("claude-opus-4-8", 5.0, 25.0),
        ("claude-haiku-4-5-20251001", 1.0, 5.0),
        ("claude-fable-5", 10.0, 50.0),
        ("claude-mythos-5", 10.0, 50.0),
        # Deprecated but still callable (tentative retirement 2026-08-05); must stay priced.
        ("claude-opus-4-1-20250805", 15.0, 75.0),
    ],
)
def test_pricing_for_known_models(model_name, input_per_million, output_per_million) -> None:
    price = pricing_for(model_name)
    assert price.input_per_million == input_per_million
    assert price.output_per_million == output_per_million


@pytest.mark.parametrize(
    "retired_model",
    [
        # Retired 2026-06-15: requests to these now fail outright on the real API.
        "claude-opus-4-20250514",
        "claude-sonnet-4-20250514",
        # Retired 2026-02-19.
        "claude-3-7-sonnet-20250219",
        "claude-3-5-haiku-20241022",
    ],
)
def test_pricing_for_rejects_retired_models(retired_model) -> None:
    """Retired models must not silently price as if callable -- the real API call would 404/400
    rather than burn budget, and a stale price entry would mask that until the call itself fails."""
    with pytest.raises(ValueError, match="No pricing configured"):
        pricing_for(retired_model)


@pytest.mark.parametrize(
    ("model_name", "expected"),
    [
        # THM3.C: a bare alias is a moving target, not a resolved snapshot.
        ("claude-sonnet-4-5", False),
        ("claude-opus-4-8", False),
        ("latest", False),
        # A dated snapshot suffix resolves it.
        ("claude-sonnet-4-5-20250929", True),
        ("claude-opus-4-1-20250805", True),
        # The mock judge's pinned identity is exempted by name.
        ("mock-deterministic-v1", True),
        # Not a trailing 8-digit suffix -- must not be mistaken for a snapshot.
        ("claude-sonnet-4-5-2025092", False),
        ("claude-sonnet-4-5-20250929-extra", False),
    ],
)
def test_is_snapshot_truth_table(model_name, expected) -> None:
    assert is_snapshot(model_name) is expected
