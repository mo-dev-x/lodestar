"""Statistical primitives used for judge and human validation."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, cast

import numpy as np
from scipy import stats


def _missing(value: object) -> bool:
    return value is None or (isinstance(value, (float, np.floating)) and np.isnan(value))


def krippendorff_alpha(
    ratings: Sequence[Sequence[object]],
    *,
    level: str = "ordinal",
    distance: Callable[[object, object], float] | None = None,
) -> float:
    """Krippendorff's alpha for rows=items and columns=raters, with missing values."""
    rows = [[value for value in row if not _missing(value)] for row in ratings]
    pooled = [value for row in rows for value in row]
    if len(pooled) < 2:
        return float("nan")
    categories = sorted(set(pooled), key=lambda value: (str(type(value)), value))
    positions = {value: index for index, value in enumerate(categories)}
    frequencies = {value: pooled.count(value) for value in categories}

    def default_distance(left: object, right: object) -> float:
        if level == "nominal":
            return float(left != right)
        if level == "ordinal":
            low, high = sorted((positions[left], positions[right]))
            cumulative = sum(frequencies[value] for value in categories[low : high + 1])
            midpoint_correction = (frequencies[left] + frequencies[right]) / 2
            return (cumulative - midpoint_correction) ** 2
        if level in {"interval", "ratio"}:
            return (float(cast(Any, left)) - float(cast(Any, right))) ** 2
        raise ValueError("level must be nominal, ordinal, interval, or ratio")

    delta = distance or default_distance
    observed_numerator = 0.0
    observed_units = 0
    for row in rows:
        count = len(row)
        if count < 2:
            continue
        observed_numerator += sum(
            delta(row[left], row[right])
            for left in range(count)
            for right in range(count)
            if left != right
        ) / (count - 1)
        observed_units += count
    if observed_units == 0:
        return float("nan")
    observed = observed_numerator / observed_units
    total = len(pooled)
    expected = sum(
        delta(pooled[left], pooled[right])
        for left in range(total)
        for right in range(total)
        if left != right
    ) / (total * (total - 1))
    if expected == 0:
        return 1.0 if observed == 0 else float("nan")
    return float(1 - observed / expected)


def icc_2_1(ratings: Sequence[Sequence[float]]) -> float:
    """Two-way random-effects, absolute-agreement, single-measure ICC(2,1)."""
    values = np.asarray(ratings, dtype=float)
    if values.ndim != 2 or values.shape[0] < 2 or values.shape[1] < 2:
        return float("nan")
    if np.isnan(values).any():
        values = values[~np.isnan(values).any(axis=1)]
    n, k = values.shape
    if n < 2:
        return float("nan")
    grand = values.mean()
    row_means = values.mean(axis=1)
    column_means = values.mean(axis=0)
    ms_rows = k * np.sum((row_means - grand) ** 2) / (n - 1)
    ms_columns = n * np.sum((column_means - grand) ** 2) / (k - 1)
    residual = values - row_means[:, None] - column_means[None, :] + grand
    ms_error = np.sum(residual**2) / ((n - 1) * (k - 1))
    denominator = ms_rows + (k - 1) * ms_error + k * (ms_columns - ms_error) / n
    return float((ms_rows - ms_error) / denominator) if denominator else float("nan")


def fleiss_kappa(ratings: Sequence[Sequence[object]]) -> float:
    """Fleiss' kappa from rows=items, columns=raters categorical assignments."""
    values = np.asarray(ratings, dtype=object)
    if values.ndim != 2 or values.shape[0] == 0 or values.shape[1] < 2:
        return float("nan")
    if any(_missing(value) for value in values.flat):
        values = values[[not any(_missing(value) for value in row) for row in values]]
    n_items, n_raters = values.shape
    if n_items == 0:
        return float("nan")
    categories = sorted(set(values.flat), key=str)
    counts = np.array(
        [[np.sum(row == category) for category in categories] for row in values], dtype=float
    )
    agreement_by_item = (np.sum(counts**2, axis=1) - n_raters) / (
        n_raters * (n_raters - 1)
    )
    observed = agreement_by_item.mean()
    proportions = counts.sum(axis=0) / (n_items * n_raters)
    expected = np.sum(proportions**2)
    return float((observed - expected) / (1 - expected)) if expected != 1 else 1.0


def cohens_kappa(left: Sequence[object], right: Sequence[object]) -> float:
    pairs = [(a, b) for a, b in zip(left, right, strict=True) if not _missing(a) and not _missing(b)]
    if not pairs:
        return float("nan")
    left_values, right_values = zip(*pairs, strict=True)
    categories = set(left_values) | set(right_values)
    observed = np.mean([a == b for a, b in pairs])
    expected = sum(
        (left_values.count(category) / len(pairs))
        * (right_values.count(category) / len(pairs))
        for category in categories
    )
    return float((observed - expected) / (1 - expected)) if expected != 1 else 1.0


def bootstrap_ci(
    values: Sequence[float],
    statistic: Callable[[np.ndarray], float] = np.mean,
    *,
    confidence: float = 0.95,
    n_resamples: int = 2_000,
    seed: int = 42,
) -> tuple[float, float]:
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if array.size == 0:
        return float("nan"), float("nan")
    generator = np.random.default_rng(seed)
    estimates = np.array(
        [statistic(generator.choice(array, size=array.size, replace=True)) for _ in range(n_resamples)]
    )
    tail = (1 - confidence) / 2
    return float(np.quantile(estimates, tail)), float(np.quantile(estimates, 1 - tail))


def paired_bootstrap_correlation(
    left: Sequence[float],
    right: Sequence[float],
    *,
    method: str,
    confidence: float = 0.95,
    n_resamples: int = 2_000,
    seed: int = 42,
) -> tuple[float, float, float, float]:
    x = np.asarray(left, dtype=float)
    y = np.asarray(right, dtype=float)
    valid = np.isfinite(x) & np.isfinite(y)
    x, y = x[valid], y[valid]
    if len(x) < 3:
        return (float("nan"),) * 4
    function = stats.spearmanr if method == "spearman" else stats.kendalltau
    result = function(x, y)
    coefficient, p_value = float(result.statistic), float(result.pvalue)
    generator = np.random.default_rng(seed)
    bootstrapped = []
    for _ in range(n_resamples):
        indices = generator.integers(0, len(x), size=len(x))
        sample = function(x[indices], y[indices]).statistic
        if np.isfinite(sample):
            bootstrapped.append(float(sample))
    if not bootstrapped:
        return coefficient, p_value, float("nan"), float("nan")
    tail = (1 - confidence) / 2
    return (
        coefficient,
        p_value,
        float(np.quantile(bootstrapped, tail)),
        float(np.quantile(bootstrapped, 1 - tail)),
    )


def spearman_with_ci(
    left: Sequence[float],
    right: Sequence[float],
    *,
    confidence: float = 0.95,
    n_resamples: int = 2_000,
    seed: int = 42,
) -> tuple[float, float, float, float]:
    return paired_bootstrap_correlation(
        left,
        right,
        method="spearman",
        confidence=confidence,
        n_resamples=n_resamples,
        seed=seed,
    )


def kendall_with_ci(
    left: Sequence[float],
    right: Sequence[float],
    *,
    confidence: float = 0.95,
    n_resamples: int = 2_000,
    seed: int = 42,
) -> tuple[float, float, float, float]:
    return paired_bootstrap_correlation(
        left,
        right,
        method="kendall",
        confidence=confidence,
        n_resamples=n_resamples,
        seed=seed,
    )
