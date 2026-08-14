from __future__ import annotations

from lodestar.report.sections import ReportSections, apply_overrides, detect_sections


def _base_kwargs() -> dict[str, object]:
    """A clean single-language, single-model, no-human-labels run: every
    detected section except frontier/control_gap/reliability should be off."""
    return dict(
        num_scale_points=3,
        conditions={"baseline", "steered", "control"},
        gaps_empty=False,
        num_languages=1,
        transfer_empty=True,
        num_models=1,
        models_has_relevance=True,
        n_repeats=3,
        reliability_empty=False,
        human_labels_supplied=False,
    )


def test_focused_run_gets_a_focused_report() -> None:
    sections = detect_sections(**_base_kwargs())
    assert sections.frontier is True
    assert sections.optimal is True
    assert sections.control_gap is True
    assert sections.cross_lingual is False
    assert sections.cross_model is False
    assert sections.reliability is True
    assert sections.human_validation is False
    assert sections.configurations is True  # optimal alone is enough
    assert sections.validation is True  # reliability alone is enough
    assert sections.generations is True
    assert sections.export is True


def test_single_scale_point_hides_frontier_and_optimal() -> None:
    kwargs = _base_kwargs()
    kwargs["num_scale_points"] = 1
    sections = detect_sections(**kwargs)
    assert sections.frontier is False
    assert sections.optimal is False


def test_control_gap_requires_the_literal_control_condition_with_data() -> None:
    # control_gap() (lodestar/metrics/derived.py) only ever reads
    # condition.isin(["steered", "control"]) -- a "baseline" condition does
    # not satisfy it, no matter how loosely you read "non-steered exists".
    # "steered" itself isn't checked separately: a non-empty `gaps` already
    # implies it was present (control_gap() only emits a row when both sides
    # are non-empty for some group), so there's no realistic combination
    # where conditions lacks "steered" but gaps_empty is False.
    kwargs = _base_kwargs()
    kwargs["conditions"] = {"steered", "baseline"}
    assert detect_sections(**kwargs).control_gap is False  # baseline isn't control

    kwargs["conditions"] = {"steered", "control"}
    kwargs["gaps_empty"] = True
    assert detect_sections(**kwargs).control_gap is False  # labels present, but no rows survived pairing

    kwargs["gaps_empty"] = False
    assert detect_sections(**kwargs).control_gap is True


def test_cross_lingual_requires_two_languages_and_nonempty_transfer() -> None:
    kwargs = _base_kwargs()
    kwargs["num_languages"] = 2
    kwargs["transfer_empty"] = True
    assert detect_sections(**kwargs).cross_lingual is False  # empty transfer frame

    kwargs["transfer_empty"] = False
    assert detect_sections(**kwargs).cross_lingual is True

    kwargs["num_languages"] = 1
    assert detect_sections(**kwargs).cross_lingual is False  # one language


def test_cross_model_requires_two_models_and_relevance_column() -> None:
    kwargs = _base_kwargs()
    kwargs["num_models"] = 2
    kwargs["models_has_relevance"] = False
    assert detect_sections(**kwargs).cross_model is False

    kwargs["models_has_relevance"] = True
    assert detect_sections(**kwargs).cross_model is True

    kwargs["num_models"] = 1
    assert detect_sections(**kwargs).cross_model is False


def test_reliability_requires_at_least_two_repeats() -> None:
    kwargs = _base_kwargs()
    kwargs["n_repeats"] = 1
    assert detect_sections(**kwargs).reliability is False

    kwargs["n_repeats"] = 2
    kwargs["reliability_empty"] = True
    assert detect_sections(**kwargs).reliability is False

    kwargs["reliability_empty"] = False
    assert detect_sections(**kwargs).reliability is True


def test_human_validation_tracks_whether_labels_were_supplied() -> None:
    kwargs = _base_kwargs()
    assert detect_sections(**kwargs).human_validation is False
    kwargs["human_labels_supplied"] = True
    assert detect_sections(**kwargs).human_validation is True


def test_custom_metrics_defaults_off_and_tracks_the_flag() -> None:
    # has_custom_metrics defaults to False so existing callers that don't pass
    # it (or don't have any third-party metrics registered) are unaffected.
    kwargs = _base_kwargs()
    assert detect_sections(**kwargs).custom_metrics is False
    kwargs["has_custom_metrics"] = True
    assert detect_sections(**kwargs).custom_metrics is True


def test_configurations_and_validation_are_derived_from_their_children() -> None:
    kwargs = _base_kwargs()
    kwargs["num_scale_points"] = 1  # kills frontier/optimal
    kwargs["n_repeats"] = 1  # kills reliability
    sections = detect_sections(**kwargs)
    assert sections.optimal is False
    assert sections.cross_lingual is False
    assert sections.cross_model is False
    assert sections.configurations is False
    assert sections.reliability is False
    assert sections.human_validation is False
    assert sections.validation is False


def test_apply_overrides_with_no_overrides_round_trips() -> None:
    detected = detect_sections(**_base_kwargs())
    merged = apply_overrides(detected, None)
    assert merged == {
        "frontier": True,
        "control_gap": True,
        "optimal": True,
        "cross_lingual": False,
        "cross_model": False,
        "reliability": True,
        "human_validation": False,
        "custom_metrics": False,
        "configurations": True,
        "validation": True,
        "generations": True,
        "export": True,
    }


def test_apply_overrides_lets_a_leaf_flag_drive_its_parent_panel() -> None:
    # All-off baseline: a researcher who knows their cross-lingual data is
    # meaningful (even though auto-detection said no) only has to flip the
    # one leaf flag -- the configurations panel gate should follow it.
    off = ReportSections()
    merged = apply_overrides(off, {"cross_lingual": True})
    assert merged["cross_lingual"] is True
    assert merged["configurations"] is True  # re-derived, not left stale
    assert merged["optimal"] is False
    assert merged["cross_model"] is False


def test_panel_level_gates_cannot_be_overridden_directly() -> None:
    # Only leaf flags are meaningful overrides -- a direct override of the
    # derived parent gate is overwritten by re-derivation, by design, so a
    # caller can never end up with e.g. validation=False while reliability=True.
    detected = detect_sections(**_base_kwargs())  # reliability=True -> validation=True
    merged = apply_overrides(detected, {"validation": False})
    assert merged["validation"] is True


def test_apply_overrides_silently_drops_unknown_keys() -> None:
    detected = detect_sections(**_base_kwargs())
    merged = apply_overrides(detected, {"not_a_real_section": True, "frontier": False})
    assert "not_a_real_section" not in merged
    assert merged["frontier"] is False
    assert merged["optimal"] is True  # untouched leaf, derived from detection not the override
