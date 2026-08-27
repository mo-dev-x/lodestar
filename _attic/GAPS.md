# Architecture vs. implementation — gap audit

Originally compared every file under `lodestar/` and `tests/` against `ARCHITECTURE.md`. This revision follows a second, independent pass (`docs/ARCHITECTURE_NOTES.md`) that re-read the code directly rather than trusting this file, found two of the items below were already fixed and three new ones that weren't, and tracks the fixes made in response. Current verdict: the two real functional gaps from the first audit are resolved, the three concrete inconsistencies the second audit found are resolved, and one new caveat was introduced as a direct, known side effect of one of those fixes (see "Confirmed gaps" below) — not undiscovered, just not eliminated, because eliminating it would mean silently swallowing a third party's broken plugin instead of surfacing it.

## Resolved since the first audit

### Human-correlation calibration scatter

Previously missing. `human_correlation()` (`lodestar/validation/human.py`) now returns `HumanCorrelationReport.pairs` — the raw paired `(judge, human)` values per rubric (`human.py:183-186,197-205`). Both report generators build a chart from it: `generate_report()`'s classic path runs it through `_add_diagonal_reference(px.scatter(...))` (`report/html.py`), and `generate_atlas_report()`'s Atlas path builds `svg.human_chart(...)` from the same pairs. Covered by `tests/test_report.py::test_report_renders_human_calibration_scatter_when_labels_supplied` and the Atlas equivalent.

### Literal-mention count and judge/grep disagreement

Previously computed but never surfaced. `_drilldown()` (`report/html.py`) now threads `literal_mention_count` and `literal_mention_judge_grep_disagreement` into its per-generation rows. Separately, `consistency_report()` (`validation/consistency.py:53-58,70`) surfaces an aggregate `judge_grep_disagreement_rate` per rubric in the reliability table. Covered by `tests/test_report.py::test_drilldown_surfaces_literal_mention_count_and_grep_disagreement`.

### CLI could not produce the Atlas report

`cli.py`'s `report` command called `generate_report` directly, bypassing `render_report`/`REPORT_STYLES` entirely — `lodestar report` could never emit the Atlas style even though it's `render_report`'s default and fully tested. Fixed: `report_command` now calls `render_report(run, output, style=style, ...)` with a `--style`/`--report-style` option (default `"atlas"`, validated against `REPORT_STYLES`). Verified by actually running both: `lodestar report run/ -o report.html` (no flag) produces a document with 0 `plotly.js` references and Atlas's `data-v="overview"` tab markup; `--style classic` produces one with 5 `plotly.js` references and none of the Atlas markup. `docs/USAGE.md`'s Dashboard section updated to describe both styles instead of asserting the output "embeds Plotly" as if that were universally true.

### `METRIC_REGISTRY` was a dead extension point

Confirmed by grep before changing anything: nothing outside `metrics/base.py`/`metrics/__init__.py` and their own tests read `METRIC_REGISTRY` — both report generators and `cli.py`'s `optimal` command imported the six metric functions directly. Fixed: both `generate_report`/`generate_atlas_report` (`report/html.py`) and `cli.py`'s `optimal_command` now resolve all six built-ins through `METRIC_REGISTRY[name](...)` by name (behavior-identical by default, since `METRIC_REGISTRY[name] is <the same function>` — `tests/test_metrics.py` already asserted this). A metric registered under any *other* name is rendered generically as a "Custom metrics" table/panel in both report styles (`_custom_metric_tables()`, `report/html.py`) — verified against both `sample_run` and the real Montreal run with a registered custom metric actually appearing in both styles' output. `EXTENDING.md`'s "Add a metric" section updated to describe this.

### Rubric extension point didn't match its own docs

`EXTENDING.md` described rubrics as "a registry you add to, not edit," but `rubrics/__init__.py`'s `REGISTRY` was a one-time dict comprehension over `STEERING_RUBRICS` with no `register_*()` function — the only abstraction of the three (rubric/metric/report) without one. Fixed: `RUBRIC_REGISTRY` (renamed from `REGISTRY` for naming parity with `METRIC_REGISTRY`) plus `register_rubric(rubric)`; the six built-ins now register themselves through it at import time instead of via the dict comprehension. `EXTENDING.md` rewritten to document all three uniformly and the deliberate Judge exception.

### Dead code: `report/lodestar_charts.py`

Zero imports anywhere (confirmed by grep immediately before deletion) — a leftover Plotly-re-themed-in-Atlas-colors file from before the hand-coded-SVG rebuild; `lodestar_svg.py` was already the live one. Deleted.

## Confirmed gaps

### A broken custom metric now takes down report generation entirely

Direct consequence of the `METRIC_REGISTRY` fix above: `_custom_metric_tables()` (`report/html.py`) calls every non-built-in registered metric with no `try`/`except` around the call. A third party's metric that raises (bad data assumptions, a typo, an unhandled empty-run case) will raise out of `generate_report()`/`generate_atlas_report()` entirely, taking the whole report down rather than degrading to "this one metric's table is missing." This is a real, known trade-off, not an oversight: the alternative (swallow the exception, render an empty/error cell) would silently hide a broken plugin's bug from the person who registered it. Not changed without a product decision on which failure mode is preferred — flagging here rather than picking one unilaterally.

## Minor / polish (not functional gaps)

- `lodestar/__init__.py` exports only `DecodingParams, EvalRun, Generation, Judgment, RunManifest, SteeringConfig, TokenUsage`. `Rubric`, `OrdinalScale`/`BinaryScale`/`CategoricalScale`, and `RubricResult` are real public-facing types but aren't re-exported at the top level, so `from lodestar import Rubric` doesn't work. Still true; not addressed in this pass since it wasn't one of the flagged items.
- `cli.py`'s `estimate` command prints `"This sweep = N judge calls (M cached, K new) ≈ $X.XX."` — the spec's example text (§5.4) ends with `"… Proceed?"`. Cosmetic; unaddressed for the same reason.
- A custom metric registered via `register_metric()` is called from the report path with only `(run)` — no kwargs. `MetricPlugin`'s `**kwargs` is there for cases like the built-in `control_gap(run, *, seed=42)`, but a custom metric whose extra parameters have no defaults will fail when the report path calls it positionally-only. Document, in your own metric's docstring, that report-time invocation passes no kwargs — or give every extra parameter a default.

## Needs verification against current external docs (not confirmed broken, just unverifiable from static reading)

- `judges/cost.py`'s `MODEL_PRICING` table is exactly the kind of thing `ARCHITECTURE.md` §5.4 warns not to trust from memory. Unchanged this pass — re-verify against `docs.claude.com`/`platform.claude.com` before any paid run.
- `judges/anthropic.py`'s `_request()` still passes `output_config={"format": {"type": "json_schema", "schema": ...}}` to `client.messages.create()` (re-confirmed present at the same call site during this pass). Whether `output_config` is the current, correct Anthropic Python SDK parameter for enforced structured output should be checked against the current `anthropic` package before relying on it against the real API.

## Everything else: matches or exceeds spec

Data model, all 6 rubrics, the `Judge` protocol + both implementations, the content-addressed cache, cost preflight, all 6 derived metrics, the stats module anchored against published examples, self-consistency reporting, stratified human-labeling export, all 6 CLI commands (now including `report --style` and `optimal` resolving through the metric registry), both ingestion adapters, the published JSON schema, and all `docs/` files. Rubric, Metric, and Report are now uniformly Protocol-plus-registry (Judge remains the deliberate, documented exception) — `docs/ARCHITECTURE_NOTES.md` has the full second-pass trace, including the diagrams and the "where would they struggle" findings this file's "Resolved" section above was written to close out.
