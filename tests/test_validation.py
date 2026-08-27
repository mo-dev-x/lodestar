from __future__ import annotations

import pytest

from lodestar.validation import consistency_report, export_labels, human_correlation, labeling_frame


def test_consistency_reliability_and_variance(sample_run) -> None:
    report = consistency_report(sample_run, variance_threshold=0)
    assert set(report.reliability["rubric"]) == {rubric.name for rubric in sample_run.rubrics}
    ordinal = report.reliability[report.reliability["scale"] == "ordinal"]
    assert ordinal["krippendorff_alpha"].notna().all()
    assert not report.high_variance.empty


def test_stratified_export_and_perfect_human_correlation(sample_run, tmp_path) -> None:
    frame = labeling_frame(sample_run, sample_size=8, seed=7)
    assert len(frame) == 8
    assert {"condition", "language", "score_band"}.issubset(frame)
    for rubric in sample_run.rubrics:
        if rubric.scale.kind in {"ordinal", "binary"}:
            frame[f"human_{rubric.name}"] = frame[f"judge_{rubric.name}"]
    path = tmp_path / "labels.csv"
    frame.to_csv(path, index=False)
    report = human_correlation(sample_run, path, seed=7)
    coherence = report.metrics[report.metrics["rubric"] == "coherence"].iloc[0]
    assert coherence["spearman_rho"] == pytest.approx(1)
    assert any("Spearman rho" in line for line in report.result_lines)
    assert export_labels(sample_run, tmp_path / "blank.csv", sample_size=5).exists()

    assert {"rubric", "scale", "judge", "human"}.issubset(report.pairs.columns)
    coherence_pairs = report.pairs[report.pairs["rubric"] == "coherence"]
    assert not coherence_pairs.empty
    assert (coherence_pairs["judge"] == coherence_pairs["human"]).all()
    literal_pairs = report.pairs[report.pairs["rubric"] == "literal_mention"]
    assert not literal_pairs.empty
    assert literal_pairs["judge"].isin([0.0, 1.0]).all()
    assert literal_pairs["human"].isin([0.0, 1.0]).all()
    assert "degeneration_flags" not in set(report.pairs["rubric"])

