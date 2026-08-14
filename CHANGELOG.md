# Changelog

Notable work, grouped by session. Newest first.

## 2026-06-26 — Lodestar report: real design, hand-coded SVG, data-driven sections

Driven by a real evaluation run (`qwen-sae-interp`'s Montreal/Quebec steering sweep) that surfaced several report bugs by actually being looked at, plus a from-scratch rebuild to match a hand-designed mockup.

### Fixed: ablation data was silently polluting the real steering-sweep metrics

`coherence_relevance_frontier()` and `optimal_operating_points()` (`lodestar/metrics/derived.py`) grouped only by `sweep_hash`/`config_hash`/`scale`, but `sweep_hash` deliberately excludes `scale` so one real sweep groups under one hash. An ablation experiment's "ablated" condition is ingested (`ingest/steering_json.py`) as `condition="steered", scale=0.0` with the same feature/config as the real sweep — so it shared a `sweep_hash` with the real sweep and got silently averaged/Pareto-compared into it. Compounding this, `eval_montreal.py`'s hardcoded `coherence >= 7` objective threshold was unreachable by the real sweep, so "optimal operating points" picked a degenerate row (scale=50, relevance≈1) instead of the real answer (scale=80).

Fixed at the source, not patched per-report:
- `EvalRun.scores()` (`lodestar/models.py`) now carries `generation.metadata["experiment"]` through as a column.
- `coherence_relevance_frontier()`/`optimal_operating_points()` now group by `experiment` in addition to `sweep_hash`, so an ablation point can never be averaged into a real sweep's frontier again, for any project's data.
- Lowered `eval_montreal.py`'s `OBJECTIVE` to `coherence >= 5` (achievable for the real sweep).

### Fixed: report tables were unreadable

`_table()` (`lodestar/report/html.py`) rendered every DataFrame column verbatim, including 64-character `sweep_hash`/`config_hash` identifiers that drowned out the columns a reader actually cares about, plus a stray "rubric" header cell with no data under it (`pivot_table(columns="rubric")` upstream leaves its name on `.columns`, and `to_html(index=False)` still renders it). Fixed: hash columns dropped by default, `columns.name` cleared, and any column that's constant across every row in a given table (one model/language for the whole run, or a column pre-filtered to one value like `pareto=True`) gets folded into a one-line caption instead of repeated down every row.

### Rebuilt: the report now matches the actual hand-designed mockup, not a rough draft

The first pass reused chart library figures inside the new Lodestar color theme — visually close, but the real design (`templates/report.html.j2`, a self-extracting design-tool bundle with the markup JSON-encoded inside a `<script type="__bundler/template">` tag) turned out to be a fully interactive, hand-coded-SVG dashboard: pixel-positioned charts, a persistent sidebar with switchable panels, collapsible/filterable generation rows, click-a-frontier-point-to-inspect-its-generations, CSV/manifest export. Decided (by explicit choice) to go for full fidelity rather than a cheaper approximation.

- **`lodestar/report/lodestar_svg.py`** (new) — hand-coded SVG builders (`frontier_chart`, `control_chart`, `human_chart`, `cross_lingual_grid`) with pixel math mirroring the mockup's exact viewBox/axis geometry. No chart library, no JS chart runtime to bundle, `data-tip`/`data-scale` attributes for the shared hover tooltip and click-to-highlight wiring.
- **`lodestar/report/templates/report.html.j2`** (new) — persistent sidebar nav with switchable panels (Overview / Frontier / Configurations / Validation / Generations / Export), deep-linkable via `#hash`; collapsible drill-down rows with condition-filter chips and a search box; an "inspector" that opens when you click a frontier point, filtering Generations to that scale with Prev/Next; CSV downloads and a manifest-JSON copy button via self-contained `data:` URIs (no server needed). All interactivity is plain vanilla JS, not the design tool's bespoke component framework.
- **`lodestar/report/html.py`** — `generate_report()` rewritten against the new SVG module/template; computes the overview metrics the design calls for (configs swept, peak SES, control-gap Δ, judge ρ vs human, consistency α, language count) and a `_model_table_html()` with inline SES progress bars baked into table cells.
- **`lodestar/report/html.py`** (pre-existing from this session's earlier work) — `report renderer` protocol + `generate_report` registry + `generate_report(sections=...)` dispatcher, so `generate_report` (SVG) and `generate_report` (SVG) are both just registered styles, and a third party can register their own without forking `html.py`.

### Added: data-driven section visibility

A single-language, single-model run with no human labels was still rendering an empty cross-lingual matrix, an empty cross-model table, and an empty human-validation block. Fixed by detecting what's actually in the run before rendering, rather than rendering everything and hoping there's data:

- **`lodestar/report/sections.py`** (new) — `ReportSections` (frozen dataclass of booleans) + `detect_sections()` (pure function, primitive-typed inputs, no pandas/Jinja import at module level — independently testable with plain Python values) + `apply_overrides()` for the power-user escape hatch. Rules: frontier needs ≥2 distinct scale points; control-gap needs the literal `"control"` condition present *and* a non-empty `control_gap()` result (not just "any non-steered condition" — `control_gap()` only ever reads `condition.isin(["steered","control"])`, so a `{"steered","baseline"}` run was previously a false positive; "steered" itself isn't checked separately, since `control_gap()` only emits a row when both sides are non-empty for some group, so a non-empty result already implies "steered" was present); cross-lingual needs ≥2 languages and a non-empty transfer frame; cross-model needs ≥2 models and a `concept_relevance` column; reliability needs `n_repeats >= 2` and a non-empty reliability frame; human-validation tracks whether `human_labels` was supplied at all. `configurations` and `validation` are parent panel gates, always re-derived as the OR of their children — including after overrides are applied, so setting one leaf flag (e.g. `{"cross_lingual": True}`) flips its parent panel automatically; you can't independently force a parent gate against its children.
- `generate_report()` gained a `sections: dict[str, bool] | None = None` override parameter; unknown keys are silently dropped.
- `generate_report()`/`report renderer` (`base.py`) thread `sections` through via `inspect.signature` rather than try/except, so older plugins that don't accept the kwarg (`generate_report`, or any third party's existing custom renderer) aren't forced to adopt it.
- `report.html.j2`'s sidebar nav is now rendered from a `nav_items` loop computed in Python from whichever panels are visible, so the numbering (01, 02, 03...) has no gaps when a panel is hidden.

### Tests

- `tests/test_sections.py` (new, 12 tests) — one per detection rule in both directions, plus override/re-derivation behavior, including the tightened control-gap contract.
- `tests/test_report.py` — added Lodestar-report self-containment/human-calibration tests (previously zero coverage on `generate_report`), plus 3 integration tests for the registry (`generate_report` dispatch, custom plugin registration) and the section-override hatch end to end.
- `tests/test_cache.py` — regression test for the SQLite concurrency fix below.
- Full suite: 69 passing.

### Fixed: judge cache concurrency bug

`MockJudge.judge_batch`'s uncapped `asyncio.gather()` fans out hundreds of concurrent (generation, rubric, repeat) tasks against one SQLite file with no WAL mode or busy timeout, raising `sqlite3.OperationalError: database is locked` under load (reproduced with 2898 concurrent writes from a real evaluation run). Fixed in `lodestar/judges/cache.py`: a `_connect()` helper (`aiosqlite.connect(self.path, timeout=30)`) used by every method, plus `PRAGMA journal_mode=WAL` in `initialize()`.

### Housekeeping

- `Lodestar_design_extracted.html` (repo root) is leftover scratch output from decoding `templates/report.html.j2`'s self-extracting bundle for inspection — not used by any code path, safe to delete whenever.
