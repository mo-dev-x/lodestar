"""Data-driven section visibility for the Lodestar report.

Isolated from html.py on purpose: no Jinja, no pandas import at module
level, so `detect_sections()` and `apply_overrides()` are testable with
plain Python values -- a caller hands in counts and booleans it already
has lying around (or constructs for a test), not DataFrames.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields


@dataclass(frozen=True)
class ReportSections:
    frontier: bool = False
    control_gap: bool = False
    optimal: bool = False
    cross_lingual: bool = False
    cross_model: bool = False
    reliability: bool = False
    human_validation: bool = False
    custom_metrics: bool = False
    configurations: bool = False
    validation: bool = False
    generations: bool = True
    export: bool = True


def detect_sections(
    *,
    num_scale_points: int,
    conditions: set[str],
    gaps_empty: bool,
    num_languages: int,
    transfer_empty: bool,
    num_models: int,
    models_has_relevance: bool,
    n_repeats: int,
    reliability_empty: bool,
    human_labels_supplied: bool,
    has_custom_metrics: bool = False,
) -> ReportSections:
    """Inspect what's actually in a run and decide which report panels are
    worth showing. One point isn't a curve, one model isn't a comparison,
    a single repeat can't measure self-consistency -- empty sections add
    noise, not information, so they're detected and skipped, not rendered
    blank.
    """
    frontier = num_scale_points >= 2
    optimal = frontier  # the optimal-operating-points table reads the same sweep
    # Must match the filter in derived.control_gap() exactly:
    # condition.isin(["steered", "control"]), and a row is only emitted for a
    # (scale, language, model) group where BOTH sides are non-empty -- so a
    # non-empty `gaps` already implies "steered" was present too, and
    # checking for it here separately would just be redundant. "control" is
    # checked explicitly because gaps_empty alone can't distinguish "no
    # control data exists" from "no data survived pairing for any group" --
    # both look identical from outside control_gap(), and only the explicit
    # check stays correct if that internal pairing logic ever changes shape.
    control_gap = "control" in conditions and not gaps_empty
    cross_lingual = num_languages >= 2 and not transfer_empty
    cross_model = num_models >= 2 and models_has_relevance
    reliability = n_repeats >= 2 and not reliability_empty
    human_validation = human_labels_supplied
    return ReportSections(
        frontier=frontier,
        control_gap=control_gap,
        optimal=optimal,
        cross_lingual=cross_lingual,
        cross_model=cross_model,
        reliability=reliability,
        human_validation=human_validation,
        custom_metrics=has_custom_metrics,
        configurations=optimal or cross_lingual or cross_model,
        validation=reliability or human_validation,
    )


def apply_overrides(detected: ReportSections, overrides: dict[str, bool] | None) -> dict[str, bool]:
    """Merge power-user overrides onto the auto-detected sections, then
    re-derive the panel-level gates (configurations, validation) so a caller
    only ever has to set the leaf flag they care about -- the parent panel
    follows automatically. Unknown keys are dropped silently so a typo or a
    future field rename in a caller's override dict can't raise.
    """
    known = {field.name for field in fields(ReportSections)}
    merged = asdict(detected)
    if overrides:
        merged.update({key: value for key, value in overrides.items() if key in known})
    merged["configurations"] = merged["optimal"] or merged["cross_lingual"] or merged["cross_model"]
    merged["validation"] = merged["reliability"] or merged["human_validation"]
    return merged
