from __future__ import annotations

import pandas as pd

import lodestar.report as report_module
from lodestar.metrics import METRIC_REGISTRY, register_metric
from lodestar.report import generate_report
from lodestar.report.html import _drilldown
from lodestar.validation.human import labeling_frame


def test_report_is_self_contained_and_complete(sample_run, tmp_path) -> None:
    output = generate_report(
        sample_run,
        tmp_path / "report.html",
        objective="max concept_relevance s.t. coherence >= 1",
    )
    document = output.read_text(encoding="utf-8")
    assert output.stat().st_size > 20_000
    assert "Coherence" in document and "relevance frontier" in document
    assert "Generations" in document
    assert 'data-v="overview"' in document and 'data-v="generations"' in document
    assert "<svg" in document
    assert "No human labels supplied" in document


def test_report_renders_human_calibration_scatter_when_labels_supplied(sample_run, tmp_path) -> None:
    frame = labeling_frame(sample_run, sample_size=8, seed=3)
    for rubric in sample_run.rubrics:
        if rubric.scale.kind in {"ordinal", "binary"}:
            frame[f"human_{rubric.name}"] = frame[f"judge_{rubric.name}"]
    labels_path = tmp_path / "labels.csv"
    frame.to_csv(labels_path, index=False)

    output = generate_report(
        sample_run,
        tmp_path / "report.html",
        objective="max concept_relevance s.t. coherence >= 1",
        human_labels=labels_path,
    )
    document = output.read_text(encoding="utf-8")
    assert "No human labels supplied" not in document
    assert "Judge versus human calibration scatter" in document
    assert "Spearman correlation, judge vs. human annotators" in document


def test_report_package_exports_only_generate_report() -> None:
    assert report_module.__all__ == ["generate_report"]


def test_drilldown_surfaces_literal_mention_count_and_grep_disagreement(sample_run) -> None:
    table = _drilldown(sample_run)
    assert "literal_mention_count" in table.columns
    assert "literal_mention_judge_grep_disagreement" in table.columns

    by_id = table.set_index("id")
    for generation in sample_run.generations:
        row = by_id.loc[generation.id]
        expected_count = generation.text.casefold().count(generation.target_concept.casefold())
        assert row["literal_mention_count"] == expected_count
        assert bool(row["literal_mention_judge_grep_disagreement"]) is False


def test_report_omits_cross_model_panel_for_a_single_model_run(sample_run, tmp_path) -> None:
    # sample_run only has one model_name ("model-a"), so a comparison table
    # with exactly one row is noise, not a comparison -- it should be hidden.
    output = generate_report(
        sample_run,
        tmp_path / "report.html",
        objective="max concept_relevance s.t. coherence >= 1",
    )
    document = output.read_text(encoding="utf-8")
    assert "Cross-model comparison" not in document


def test_report_sections_override_can_force_a_panel_on(sample_run, tmp_path) -> None:
    output = generate_report(
        sample_run,
        tmp_path / "report.html",
        objective="max concept_relevance s.t. coherence >= 1",
        sections={"cross_model": True},
    )
    document = output.read_text(encoding="utf-8")
    assert "Cross-model comparison" in document
    assert 'data-v="configurations"' in document


def test_a_registered_custom_metric_surfaces_in_the_report(sample_run, tmp_path) -> None:
    def custom_metric(run, **kwargs):
        return pd.DataFrame({"n_generations": [len(run.generations)]})

    register_metric("my_custom_metric", custom_metric)
    try:
        output = generate_report(sample_run, tmp_path / "report.html")
        document = output.read_text(encoding="utf-8")
        assert "my_custom_metric" in document
        assert 'data-v="custom"' in document
        assert "Custom metrics" in document
    finally:
        del METRIC_REGISTRY["my_custom_metric"]


def test_a_raising_custom_metric_degrades_to_an_error_panel_without_taking_down_the_report(
    sample_run, tmp_path
) -> None:
    def broken_metric(run, **kwargs):
        raise ValueError("boom")

    register_metric("broken_metric", broken_metric)
    try:
        output = generate_report(sample_run, tmp_path / "report.html")
        document = output.read_text(encoding="utf-8")
        assert "metric broken_metric raised: boom" in document
        assert "Coherence" in document and "relevance frontier" in document
        assert "Generations" in document
    finally:
        del METRIC_REGISTRY["broken_metric"]


def test_no_custom_metrics_panel_when_none_are_registered(sample_run, tmp_path) -> None:
    assert set(METRIC_REGISTRY) == {
        "coherence_relevance_frontier",
        "control_gap",
        "cross_lingual_transfer",
        "cross_model_comparison",
        "optimal_operating_points",
        "steering_efficacy_scores",
    }
    output = generate_report(sample_run, tmp_path / "report.html")
    document = output.read_text(encoding="utf-8")
    assert 'data-v="custom"' not in document
    assert "Custom metrics" not in document
