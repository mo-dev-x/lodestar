"""Single-file, audit-friendly HTML report generation."""

from __future__ import annotations

import base64
import html as html_lib
import json
from pathlib import Path
from typing import Any, cast

import pandas as pd
from jinja2 import Environment, PackageLoader, select_autoescape

import lodestar.report.lodestar_svg as svg
from lodestar.metrics import BUILTIN_METRIC_NAMES, METRIC_REGISTRY
from lodestar.metrics.derived import parse_objective
from lodestar.models import EvalRun
from lodestar.report.sections import apply_overrides, detect_sections
from lodestar.validation.consistency import consistency_report
from lodestar.validation.human import human_correlation


def _custom_metric_tables(run: EvalRun) -> dict[str, str]:
    """Anything registered under a name other than the six built-ins (see
    metrics.BUILTIN_METRIC_NAMES) is a third party's metric -- it has no
    dedicated chart/columns to render against, so it gets a generic table
    instead of one of the named panels below.

    A custom metric's own bug is its author's problem, not a reason to take
    the whole report down with it: computing/rendering one is wrapped so a
    raise becomes that one panel's error state, and every other panel --
    including every built-in, called elsewhere and deliberately NOT wrapped
    -- still renders. A broken built-in is Lodestar's own bug and should
    fail loud, not be silently contained alongside third-party plugins.
    """
    tables: dict[str, str] = {}
    for name in sorted(METRIC_REGISTRY):
        if name in BUILTIN_METRIC_NAMES:
            continue
        try:
            tables[name] = _table(METRIC_REGISTRY[name](run))
        except Exception as exc:
            tables[name] = (
                f'<p class="muted">metric {html_lib.escape(name)} raised: '
                f"{html_lib.escape(str(exc))}</p>"
            )
    return tables


def _table(
    frame: pd.DataFrame,
    *,
    empty: str = "No data available.",
    hide: tuple[str, ...] = ("sweep_hash", "config_hash"),
    highlight_scale: float | None = None,
) -> str:
    """Render a DataFrame as an HTML table.

    When the frame has a "scale" column, rows get a `data-scale` attribute
    (so the frontier chart's click-to-highlight can find every table row for
    a given scale across sections) and the row matching `highlight_scale`
    gets an `is-optimal` class.
    """
    if frame.empty:
        return f'<p class="muted">{empty}</p>'
    display = frame.drop(columns=[column for column in hide if column in frame.columns])
    # pivot_table(columns="rubric") upstream leaves its name on display.columns,
    # which to_html(index=False) still renders as a stray, data-less header cell.
    display.columns.name = None

    # A column that's the same value down every row (one model/language for the
    # whole run, or a column pre-filtered to a single value like "pareto=True")
    # tells a reader nothing repeated 20 times -- fold it into one caption line.
    constant_notes: list[str] = []
    if len(display) > 1:
        for column in list(display.columns):
            try:
                is_constant = display[column].nunique(dropna=False) <= 1
            except TypeError:
                continue
            if is_constant:
                constant_notes.append(f"{column}={display[column].iloc[0]}")
                display = display.drop(columns=[column])

    # Only the steering clamp-scale column is meant for this -- consistency.reliability
    # also has a "scale" column, but it holds the rubric *kind* ("ordinal"/"binary"), not
    # a clamp magnitude, so it must never be coerced into the click-to-highlight wiring.
    scale_values = (
        display["scale"].copy()
        if "scale" in display.columns and pd.api.types.is_numeric_dtype(display["scale"])
        else None
    )
    for column in display.select_dtypes(include="number").columns:
        display[column] = display[column].map(lambda value: f"{value:.4g}" if pd.notna(value) else "")
    caption = (
        f'<p class="muted" style="margin:0 0 10px">{" &#183; ".join(constant_notes)}</p>'
        if constant_notes
        else ""
    )

    if scale_values is None:
        return caption + display.to_html(index=False, escape=True, border=0, classes="dataframe")

    header = "".join(f"<th>{html_lib.escape(str(column))}</th>" for column in display.columns)
    body_rows = []
    for position, (_, record) in enumerate(display.iterrows()):
        scale = scale_values.iloc[position]
        is_optimal = highlight_scale is not None and pd.notna(scale) and float(scale) == float(highlight_scale)
        cells = "".join(f"<td>{html_lib.escape(str(record[column]))}</td>" for column in display.columns)
        # .4g matches lodestar_svg's frontier-chart points and _drilldown_rows()'s
        # scale formatting exactly, so click-to-highlight can match data-scale as strings.
        scale_attr = f"{float(scale):.4g}" if pd.notna(scale) else ""
        row_class = ' class="is-optimal"' if is_optimal else ""
        body_rows.append(f'<tr data-scale="{scale_attr}"{row_class}>{cells}</tr>')
    return (
        caption
        + '<table class="dataframe dataframe">'
        + f"<thead><tr>{header}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"
    )


def _drilldown(run: EvalRun) -> pd.DataFrame:
    scores = run.scores()
    wide = scores.pivot(index="generation_id", columns="rubric", values="score").reset_index()
    generations = {generation.id: generation for generation in run.generations}
    rationales: dict[tuple[str, str], list[str]] = {}
    metadata: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for judgment in run.judgments:
        key = (judgment.generation_id, judgment.rubric_name)
        rationales.setdefault(key, []).append(judgment.rationale)
        metadata.setdefault(key, []).append(judgment.metadata)
    rows: list[dict[str, Any]] = []
    for _, values in wide.iterrows():
        generation = generations[values["generation_id"]]
        row: dict[str, Any] = {
            "id": generation.id,
            "condition": generation.condition,
            "scale": generation.steering_config.scale if generation.steering_config else 0,
            "language": generation.language,
            "model": generation.model_name,
            "prompt": generation.prompt,
            "text": generation.text,
        }
        for rubric in run.rubrics:
            row[rubric.name] = values.get(rubric.name, "")
            row[f"{rubric.name}_rationale"] = " | ".join(
                rationales.get((generation.id, rubric.name), [])
            )
            if rubric.name == "literal_mention":
                metas = metadata.get((generation.id, rubric.name), [])
                counts = sorted({meta["count"] for meta in metas if meta.get("count") is not None})
                row["literal_mention_count"] = counts[0] if len(counts) == 1 else ", ".join(
                    str(count) for count in counts
                )
                disagreements = [
                    meta["judge_grep_disagreement"]
                    for meta in metas
                    if meta.get("judge_grep_disagreement") is not None
                ]
                row["literal_mention_judge_grep_disagreement"] = (
                    any(disagreements) if disagreements else False
                )
        rows.append(row)
    return pd.DataFrame(rows)


def _format_score(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "none"
    if isinstance(value, float):
        return f"{value:.1f}" if pd.notna(value) else "&#8212;"
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "&#8212;"
    return str(value)


def _drilldown_rows(run: EvalRun) -> tuple[list[dict[str, Any]], list[str]]:
    """Same data as _drilldown(), reshaped for the template's drill-down loop."""
    frame = _drilldown(run)
    rows: list[dict[str, Any]] = []
    for _, record in frame.iterrows():
        coherence = record.get("coherence", "")
        relevance = record.get("concept_relevance", "")
        ses = (
            float(relevance) * (float(coherence) / 10)
            if isinstance(coherence, (int, float)) and isinstance(relevance, (int, float))
            else None
        )
        rationale = record.get("concept_relevance_rationale") or next(
            (record.get(f"{rubric.name}_rationale") for rubric in run.rubrics if record.get(f"{rubric.name}_rationale")),
            "",
        )
        rows.append(
            {
                "id": record["id"],
                "id_short": f"{record['id'][:6]}&#8230;{record['id'][-4:]}",
                "condition": record["condition"],
                # .4g matches _table()'s numeric formatting exactly, so the
                # frontier chart's click-to-highlight can match data-scale
                # attributes across charts/tables/drilldown rows as strings.
                "scale": f"{float(record['scale']):.4g}" if pd.notna(record["scale"]) else "0",
                "language": record["language"],
                "model": record["model"],
                "prompt": record["prompt"],
                "text": record["text"],
                "coherence": _format_score(coherence),
                "relevance": _format_score(relevance),
                "ses": f"{ses:.2f}" if ses is not None else "&#8212;",
                "rationale": rationale or "&#8212;",
                "scores": [(rubric.name, _format_score(record.get(rubric.name, ""))) for rubric in run.rubrics],
            }
        )
    conditions = sorted({row["condition"] for row in rows})
    return rows, conditions


def _csv_data_uri(frame: pd.DataFrame) -> str | None:
    """A download link for a small table needs no server -- base64-encode the
    CSV straight into the href so the report stays a single self-contained file."""
    if frame.empty:
        return None
    payload = base64.b64encode(frame.to_csv(index=False).encode("utf-8")).decode("ascii")
    return f"data:text/csv;base64,{payload}"


def _model_table_html(models: pd.DataFrame, ses_by_model: pd.Series) -> str:
    if models.empty or "concept_relevance" not in models:
        return '<p class="muted">Not enough data to draw this chart.</p>'
    steered = models[models["condition"] == "steered"]
    if steered.empty:
        return '<p class="muted">Not enough data to draw this chart.</p>'
    rows = []
    for model_name, group in steered.groupby("model_name"):
        best = cast(pd.DataFrame, group).sort_values("concept_relevance", ascending=False).iloc[0]
        rows.append(
            (
                model_name,
                best["scale"],
                best["concept_relevance"],
                best.get("coherence", float("nan")),
                float(ses_by_model.get(model_name, 0.0)),
            )
        )
    if not rows:
        return '<p class="muted">Not enough data to draw this chart.</p>'
    max_ses = max((row[4] for row in rows), default=1.0) or 1.0
    # Gold marks the lodestar row, not a whole column -- the top-SES model
    # gets `is-optimal` (same row-level highlight every other table uses),
    # not a permanently gold "Opt. scale" cell on every row.
    best_ses = max(row[4] for row in rows)
    body_rows = []
    for name, scale, relevance, coherence, ses in rows:
        row_class = ' class="is-optimal"' if ses == best_ses else ""
        body_rows.append(
            f"<tr{row_class}><td>{name}</td>"
            f"<td>{scale:g}</td>"
            f"<td>{relevance:.1f}</td>"
            f"<td>{coherence:.1f}</td>"
            '<td style="text-align:left"><div class="ses-bar"><div class="track">'
            f'<div class="fill" style="width:{(ses / max_ses * 100):.1f}%"></div></div>'
            f'<span class="val">{ses:.2f}</span></div></td></tr>'
        )
    body = "".join(body_rows)
    return (
        "<table><thead><tr>"
        '<th style="text-align:left">Model</th><th>Opt. scale</th><th>Relevance</th><th>Coherence</th>'
        '<th style="text-align:left;width:38%">SES</th>'
        f"</tr></thead><tbody>{body}</tbody></table>"
    )


def generate_report(
    run: EvalRun,
    output: str | Path,
    *,
    objective: str = "max concept_relevance s.t. coherence >= 7",
    human_labels: str | Path | None = None,
    sections: dict[str, bool] | None = None,
) -> Path:
    """Render the canonical Lodestar report with hand-coded SVG charts.

    Sections with nothing to show (a single scale point, one language, no
    human labels, ...) are auto-detected and omitted rather than rendered
    empty -- see lodestar.report.sections. Pass `sections` to override any
    auto-detected flag; unknown keys are ignored and the configurations/
    validation panel-level gates are re-derived after your overrides apply.
    """
    destination = Path(output)
    frontier = METRIC_REGISTRY["coherence_relevance_frontier"](run)
    optimal = METRIC_REGISTRY["optimal_operating_points"](run, objective)
    gaps = METRIC_REGISTRY["control_gap"](run)
    transfer = METRIC_REGISTRY["cross_lingual_transfer"](run)
    models = METRIC_REGISTRY["cross_model_comparison"](run)
    consistency = consistency_report(run)
    ses_table = METRIC_REGISTRY["steering_efficacy_scores"](run)
    custom_metric_tables = _custom_metric_tables(run)

    no_chart = '<p class="muted">Not enough data to draw this chart.</p>'
    threshold = next(
        (value for name, op, value in parse_objective(objective).constraints if name == "coherence" and op in (">=", ">")),
        None,
    )

    # Restrict the connected frontier line to one real sweep -- an ablation
    # point can share a sweep's hash/scale=0 placeholder but isn't a point on
    # the same scale curve (see FEATURE_EXPERIMENT_LOG.md section 20 in
    # qwen-sae-interp for why that conflation is a real, previously-shipped bug).
    sweep = frontier
    if not sweep.empty and "experiment" in sweep.columns:
        real_experiments = [e for e in sweep["experiment"].unique() if e != "ablation"]
        if real_experiments:
            sweep = sweep[sweep["experiment"] == real_experiments[0]]
    num_scale_points = int(sweep["scale"].nunique()) if not sweep.empty else 0

    frontier_svg = no_chart
    optimal_scale = None
    peak_ses = None
    if not sweep.empty:
        sweep = sweep.sort_values("scale")
        scales = sweep["scale"].tolist()
        coherence = sweep["coherence"].tolist()
        relevance = sweep["concept_relevance"].tolist()
        ses_values = [r * (c / 10) for c, r in zip(coherence, relevance, strict=True)]
        peak_ses = max(ses_values)
        candidates = optimal[optimal["scale"].isin(scales)] if not optimal.empty else optimal
        best = candidates if not candidates.empty else sweep
        optimal_scale = cast(pd.DataFrame, best).sort_values("concept_relevance", ascending=False).iloc[0]["scale"]
        frontier_svg = svg.frontier_chart(scales, coherence, relevance, ses_values, optimal_scale, threshold=threshold)

    control_svg = no_chart
    control_stats = None
    if not gaps.empty:
        gap_candidates = gaps[gaps["scale"] == optimal_scale] if optimal_scale is not None else gaps
        gap_row = (gap_candidates if not gap_candidates.empty else gaps).iloc[0]
        control_svg = svg.control_chart(
            gap_row["steered_mean"], gap_row["control_mean"], gap_row["ci_low"], gap_row["ci_high"]
        )
        p_value = gap_row["p_value"]
        control_stats = {
            "delta": f"{gap_row['gap']:+.1f}",
            "ci": f"[{gap_row['ci_low']:.1f}, {gap_row['ci_high']:.1f}]",
            "p": "p &lt; 0.001" if p_value < 0.001 else f"p = {p_value:.3g}",
        }

    per_model = pd.Series(dtype=float)
    if not ses_table.empty:
        per_model = ses_table[ses_table["condition"] == "steered"].groupby("model_name")["ses"].mean()
    model_table_html = _model_table_html(models, per_model)

    # Cross-lingual grid: each language's own optimal-scale scores side by side.
    language_grid = no_chart
    if not optimal.empty:
        langs: list[str] = []
        raw_rows: list[list[float]] = []
        for _, row in optimal.sort_values("language").iterrows():
            language, scale = row["language"], row["scale"]
            transfer_row = transfer[(transfer["language"] == language) & (transfer["scale"] == scale)]
            transfer_ratio = float(transfer_row["transfer_ratio"].iloc[0]) if not transfer_row.empty else 1.0
            ses_row = ses_table[
                (ses_table["language"] == language)
                & (ses_table["scale"] == scale)
                & (ses_table["condition"] == "steered")
            ]
            mean_ses = float(ses_row["ses"].mean()) if not ses_row.empty else 0.0
            langs.append(language)
            raw_rows.append(
                [float(row.get("concept_relevance", 0.0)), float(row.get("coherence", 0.0)), mean_ses, transfer_ratio]
            )
        if langs:
            language_grid = svg.cross_lingual_grid(langs, ["Relevance", "Coherence", "SES", "Transfer"], raw_rows)

    human_table = ""
    human_chart_html = ""
    result_lines: list[str] = []
    judge_rho_headline = None
    judge_rho_display = "&#8212;"
    if human_labels is not None:
        correlation = human_correlation(run, human_labels)
        human_table = _table(correlation.metrics)
        result_lines = correlation.result_lines
        if not correlation.pairs.empty:
            human_chart_html = svg.human_chart(correlation.pairs["human"].tolist(), correlation.pairs["judge"].tolist())
        ordinal_metrics = correlation.metrics[correlation.metrics["scale"] == "ordinal"] if not correlation.metrics.empty else correlation.metrics
        if not ordinal_metrics.empty:
            headline_row = (
                ordinal_metrics[ordinal_metrics["rubric"] == "concept_relevance"].iloc[0]
                if (ordinal_metrics["rubric"] == "concept_relevance").any()
                else ordinal_metrics.iloc[0]
            )
            judge_rho_display = f"{headline_row['spearman_rho']:.2f}"
            judge_rho_headline = {
                "rho": judge_rho_display,
                "n": int(headline_row["n"]),
                "p": "p &lt; 0.001" if headline_row["spearman_p"] < 0.001 else f"p = {headline_row['spearman_p']:.3g}",
            }

    reliability = consistency.reliability.copy()
    if not reliability.empty:
        flagged_counts = (
            consistency.high_variance.groupby("rubric").size() if not consistency.high_variance.empty else pd.Series(dtype=int)
        )
        reliability["flagged"] = reliability["rubric"].map(flagged_counts).fillna(0).astype(int)
        alpha_values = cast(pd.Series, reliability.loc[reliability["scale"] == "ordinal", "krippendorff_alpha"]).dropna()
        consistency_alpha_display = f"{alpha_values.mean():.2f}" if not alpha_values.empty else "&#8212;"
    else:
        consistency_alpha_display = "&#8212;"

    drilldown_rows, drilldown_conditions = _drilldown_rows(run)

    steering_configs = [generation.steering_config for generation in run.generations if generation.steering_config]
    feature_label = None
    if steering_configs:
        config = steering_configs[0]
        feature_label = " + ".join(f"&#65283;{fid}" for fid in config.feature_ids) + f" &#183; L{config.hook_layer}"

    num_languages = len({generation.language for generation in run.generations})
    num_models = len({generation.model_name for generation in run.generations})
    detected = detect_sections(
        num_scale_points=num_scale_points,
        conditions={generation.condition for generation in run.generations},
        gaps_empty=gaps.empty,
        num_languages=num_languages,
        transfer_empty=transfer.empty,
        num_models=num_models,
        models_has_relevance=not models.empty and "concept_relevance" in models.columns,
        n_repeats=run.n_repeats,
        reliability_empty=consistency.reliability.empty,
        human_labels_supplied=human_labels is not None,
        has_custom_metrics=bool(custom_metric_tables),
    )
    section_flags = apply_overrides(detected, sections)

    nav_items = [{"id": "overview", "label": "Overview"}]
    if section_flags["frontier"] or section_flags["control_gap"]:
        nav_items.append({"id": "frontier", "label": "Frontier"})
    if section_flags["configurations"]:
        nav_items.append({"id": "configurations", "label": "Configurations"})
    if section_flags["validation"]:
        nav_items.append({"id": "validation", "label": "Validation"})
    if section_flags["custom_metrics"]:
        nav_items.append({"id": "custom", "label": "Custom metrics"})
    nav_items.append({"id": "generations", "label": "Generations"})
    nav_items.append({"id": "export", "label": "Export"})

    environment = Environment(
        loader=PackageLoader("lodestar.report", "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = environment.get_template("report.html.j2")
    html_document = template.render(
        run=run,
        generation_count=len(run.generations),
        judgment_count=len(run.judgments),
        objective=objective,
        sections=section_flags,
        nav_items=nav_items,
        target_concept=run.generations[0].target_concept if run.generations else "",
        model_name=run.generations[0].model_name if run.generations else "",
        feature_label=feature_label,
        configs_swept=len(sweep) if not sweep.empty else 0,
        optimal_scale_display=f"{optimal_scale:g}" if optimal_scale is not None else "&#8212;",
        peak_ses_display=f"{peak_ses:.2f}" if peak_ses is not None else "&#8212;",
        control_gap_display=control_stats["delta"] if control_stats else "&#8212;",
        judge_rho_display=judge_rho_display,
        consistency_alpha_display=consistency_alpha_display,
        num_languages=num_languages,
        frontier_svg=frontier_svg,
        frontier_table=_table(
            frontier[frontier["pareto"]] if not frontier.empty else frontier, highlight_scale=optimal_scale
        ),
        optimal_table=_table(optimal, highlight_scale=optimal_scale),
        control_svg=control_svg,
        control_stats=control_stats,
        language_grid=language_grid,
        model_table=model_table_html,
        reliability_table=_table(reliability, empty="No data available."),
        custom_metric_tables=custom_metric_tables,
        human_table=human_table,
        human_chart=human_chart_html,
        judge_rho_headline=judge_rho_headline,
        result_lines=result_lines,
        drilldown_rows=drilldown_rows,
        drilldown_conditions=drilldown_conditions,
        reliability_csv_href=_csv_data_uri(consistency.reliability),
        high_variance_csv_href=_csv_data_uri(consistency.high_variance),
        manifest_json=json.dumps(
            {
                "run_id": run.id,
                "judge_model": run.judge_model,
                "n_repeats": run.n_repeats,
                "tool_version": run.manifest.tool_version,
                "total_cost_usd": run.manifest.total_cost_usd,
                "elapsed_seconds": run.manifest.elapsed_seconds,
                "cache_hits": run.manifest.cache_hits,
                "input_tokens": run.manifest.input_tokens,
                "output_tokens": run.manifest.output_tokens,
            },
            indent=2,
        ),
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html_document, encoding="utf-8")
    return destination
