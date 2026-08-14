from __future__ import annotations

import json

import numpy as np
import pytest

from lodestar.metrics.stats import (
    bootstrap_ci, cohens_kappa, fleiss_kappa, icc_2_1, krippendorff_alpha,
    kendall_with_ci, spearman_with_ci,
)


def test_krippendorff_against_published_example(fixture_dir) -> None:
    fixture = json.loads((fixture_dir / "krippendorff_known.json").read_text())
    assert krippendorff_alpha(fixture["items"], level="nominal") == pytest.approx(
        fixture["expected_nominal"], abs=1e-9
    )
    assert krippendorff_alpha(fixture["items"], level="ordinal") == pytest.approx(
        fixture["expected_ordinal"], abs=0.02
    )


def test_fleiss_kappa_against_textbook_example() -> None:
    counts = [
        [0,0,0,0,14], [0,2,6,4,2], [0,0,3,5,6], [0,3,9,2,0], [2,2,8,1,1],
        [7,7,0,0,0], [3,2,6,3,0], [2,5,3,2,2], [6,5,2,1,0], [0,2,2,3,7],
    ]
    assignments = [[category for category, count in enumerate(row) for _ in range(count)] for row in counts]
    assert fleiss_kappa(assignments) == pytest.approx(0.20993, abs=1e-4)


def test_icc_against_shrout_fleiss_example() -> None:
    ratings = [[9,2,5,8], [6,1,3,2], [4,4,6,8], [6,2,4,7], [8,5,6,9], [7,5,2,6]]
    assert icc_2_1(ratings) == pytest.approx(0.1830065, abs=1e-6)


def test_agreement_and_bootstrap_helpers() -> None:
    assert cohens_kappa([True, True, False, False], [True, True, False, False]) == 1
    low, high = bootstrap_ci([1, 2, 3, 4], n_resamples=300, seed=1)
    assert low < 2.5 < high
    x = np.arange(12)
    assert spearman_with_ci(x, x, n_resamples=100)[0] == pytest.approx(1)
    assert kendall_with_ci(x, x, n_resamples=100)[0] == pytest.approx(1)
