"""Stratified labeling export and judge-to-human correlation reports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from lodestar.metrics.stats import (
    cohens_kappa,
    kendall_with_ci,
    krippendorff_alpha,
    spearman_with_ci,
)
from lodestar.models import EvalRun


@dataclass(frozen=True)
class HumanCorrelationReport:
    metrics: pd.DataFrame
    result_lines: list[str]
    pairs: pd.DataFrame


def labeling_frame(run: EvalRun, *, sample_size: int = 100, seed: int = 42) -> pd.DataFrame:
    generations = {generation.id: generation for generation in run.generations}
    scores = run.scores()
    wide = scores.pivot(index="generation_id", columns="rubric", values="score").reset_index()
    rows = []
    for _, score_row in wide.iterrows():
        generation = generations[score_row["generation_id"]]
        row: dict[str, Any] = {
            "generation_id": generation.id,
            "prompt": generation.prompt,
            "text": generation.text,
            "condition": generation.condition,
            "scale": generation.steering_config.scale if generation.steering_config else 0.0,
            "language": generation.language,
            "model_name": generation.model_name,
            "target_concept": generation.target_concept,
        }
        for rubric in run.rubrics:
            value = score_row.get(rubric.name, "")
            if isinstance(value, (list, dict)):
                value = json.dumps(value, ensure_ascii=False)
            row[f"judge_{rubric.name}"] = value
            row[f"human_{rubric.name}"] = ""
        rows.append(row)
    frame = pd.DataFrame(rows)
    relevance = pd.to_numeric(frame.get("judge_concept_relevance"), errors="coerce")
    frame["score_band"] = pd.cut(
        relevance,
        bins=[-np.inf, 3, 6, np.inf],
        labels=["low", "medium", "high"],
    ).astype("string").fillna("unknown")
    if len(frame) <= sample_size:
        return frame.sort_values("generation_id").reset_index(drop=True)
    strata = ["condition", "scale", "language", "score_band"]
    sampled = (
        frame.groupby(strata, dropna=False, group_keys=False)
        .sample(n=1, random_state=seed)
        .drop_duplicates("generation_id")
    )
    if len(sampled) < sample_size:
        remaining = frame[~frame["generation_id"].isin(sampled["generation_id"])]
        extra = remaining.sample(
            n=min(sample_size - len(sampled), len(remaining)), random_state=seed
        )
        sampled = pd.concat([sampled, extra])
    elif len(sampled) > sample_size:
        sampled = sampled.sample(n=sample_size, random_state=seed)
    return sampled.sort_values(strata).reset_index(drop=True)


def export_labels(
    run: EvalRun, path: str | Path, *, sample_size: int = 100, seed: int = 42
) -> Path:
    destination = Path(path)
    labeling_frame(run, sample_size=sample_size, seed=seed).to_csv(destination, index=False)
    return destination


def export_labeling_html(
    run: EvalRun, path: str | Path, *, sample_size: int = 100, seed: int = 42
) -> Path:
    destination = Path(path)
    records = labeling_frame(run, sample_size=sample_size, seed=seed).to_dict(orient="records")
    rubric_names = [rubric.name for rubric in run.rubrics]
    payload = json.dumps(records, ensure_ascii=False).replace("</", "<\\/")
    rubric_payload = json.dumps(rubric_names)
    document = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Lodestar human labeling</title>
<style>body{{font:16px system-ui;max-width:950px;margin:2rem auto;padding:0 1rem}}textarea{{width:100%;min-height:8rem}}label{{display:block;margin:.7rem 0}}input{{width:10rem}}button{{padding:.65rem 1rem;margin-right:.5rem}}.muted{{color:#666}}pre{{white-space:pre-wrap}}</style></head>
<body><h1>Lodestar human labeling</h1><p class="muted">Scores are saved in your browser until you export CSV.</p>
<div id="item"></div><button onclick="previous()">Previous</button><button onclick="next()">Save & next</button><button onclick="download()">Export CSV</button>
<script>const rows={payload}; const rubrics={rubric_payload}; let index=0;
function render(){{const r=rows[index];document.getElementById('item').innerHTML=`<p>${{index+1}} / ${{rows.length}}</p><h3>Prompt</h3><pre>${{escapeHtml(r.prompt)}}</pre><h3>Output</h3><pre>${{escapeHtml(r.text)}}</pre>`+rubrics.map(x=>`<label>${{x}} <input id="human_${{x}}" value="${{escapeHtml(String(r['human_'+x]||''))}}"></label>`).join('');}}
function escapeHtml(x){{return x.replace(/[&<>\"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}}[c]));}}
function save(){{rubrics.forEach(x=>rows[index]['human_'+x]=document.getElementById('human_'+x).value);localStorage.setItem('lodestar-labels',JSON.stringify(rows));}}
function next(){{save();index=Math.min(rows.length-1,index+1);render();}}function previous(){{save();index=Math.max(0,index-1);render();}}
function download(){{save();const keys=Object.keys(rows[0]);const quote=v=>'\"'+String(v??'').replaceAll('\"','\"\"')+'\"';const csv=[keys.map(quote).join(','),...rows.map(r=>keys.map(k=>quote(r[k])).join(','))].join('\\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{{type:'text/csv'}}));a.download='labels_filled.csv';a.click();}}
const stored=localStorage.getItem('lodestar-labels');if(stored)Object.assign(rows,JSON.parse(stored));render();</script></body></html>"""
    destination.write_text(document, encoding="utf-8")
    return destination


def _human_value(value: Any, kind: str) -> Any:
    if pd.isna(value) or str(value).strip() == "":
        return None
    if kind == "ordinal":
        return float(value)
    if kind == "binary":
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = None
        if numeric is not None and numeric in (0.0, 1.0):
            return bool(numeric)
        lowered = str(value).strip().casefold()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
        raise ValueError(f"invalid binary human label {value!r}")
    return str(value)


def human_correlation(run: EvalRun, labels_path: str | Path, *, seed: int = 42) -> HumanCorrelationReport:
    labels = pd.read_csv(labels_path)
    rows: list[dict[str, Any]] = []
    lines: list[str] = []
    pair_rows: list[dict[str, Any]] = []
    for rubric in run.rubrics:
        judge_column = f"judge_{rubric.name}"
        human_column = f"human_{rubric.name}"
        if judge_column not in labels or human_column not in labels:
            continue
        pairs = []
        for judge, human in zip(labels[judge_column], labels[human_column], strict=True):
            parsed = _human_value(human, rubric.scale.kind)
            if parsed is not None and not pd.isna(judge):
                pairs.append((judge, parsed))
        if not pairs:
            continue
        judge_values, human_values = zip(*pairs, strict=True)
        row: dict[str, Any] = {"rubric": rubric.name, "n": len(pairs), "scale": rubric.scale.kind}
        if rubric.scale.kind == "ordinal":
            judge_numeric = [float(value) for value in judge_values]
            human_numeric = [float(value) for value in human_values]
            rho, rho_p, rho_low, rho_high = spearman_with_ci(
                judge_numeric, human_numeric, seed=seed
            )
            tau, tau_p, tau_low, tau_high = kendall_with_ci(
                judge_numeric, human_numeric, seed=seed
            )
            alpha = krippendorff_alpha(
                [[judge, human] for judge, human in zip(judge_numeric, human_numeric, strict=True)],
                level="ordinal",
            )
            row.update(
                spearman_rho=rho,
                spearman_p=rho_p,
                spearman_ci_low=rho_low,
                spearman_ci_high=rho_high,
                kendall_tau=tau,
                kendall_p=tau_p,
                kendall_ci_low=tau_low,
                kendall_ci_high=tau_high,
                krippendorff_alpha=alpha,
                cohens_kappa=np.nan,
            )
            p_text = "p < 0.001" if rho_p < 0.001 else f"p = {rho_p:.3g}"
            lines.append(
                f"For {rubric.name}, our judge attains Spearman rho = {rho:.2f} "
                f"with human annotators (n = {len(pairs)}, {p_text}; 95% CI "
                f"[{rho_low:.2f}, {rho_high:.2f}])."
            )
            pair_rows.extend(
                {"rubric": rubric.name, "scale": "ordinal", "judge": judge, "human": human}
                for judge, human in zip(judge_numeric, human_numeric, strict=True)
            )
        elif rubric.scale.kind == "binary":
            kappa = cohens_kappa(judge_values, human_values)
            alpha = krippendorff_alpha(
                [[judge, human] for judge, human in zip(judge_values, human_values, strict=True)],
                level="nominal",
            )
            row.update(cohens_kappa=kappa, krippendorff_alpha=alpha)
            lines.append(
                f"For {rubric.name}, judge-human Cohen's kappa = {kappa:.2f} (n = {len(pairs)})."
            )
            pair_rows.extend(
                {
                    "rubric": rubric.name,
                    "scale": "binary",
                    "judge": float(bool(judge)),
                    "human": float(bool(human)),
                }
                for judge, human in zip(judge_values, human_values, strict=True)
            )
        rows.append(row)
    return HumanCorrelationReport(pd.DataFrame(rows), lines, pd.DataFrame(pair_rows))

