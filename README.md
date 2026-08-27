<p align="center">
  <img src="assets/logo-wide.svg" alt="Lodestar" width="360">
</p>

<p align="center">
  <em>The star you steer by: a steering-native evaluation harness for sparse-autoencoder interpretability research.</em>
</p>

# Lodestar

Lodestar turns the output of an activation-steering sweep — a directory of `generations.json`, no pipeline changes required — into calibrated, human-correlated quality scores, a coherence/relevance Pareto frontier, and a self-contained HTML report you can attach to a paper without apologizing for it.

## What "steering-native evaluation" means

Most tools that score model text are steering-*agnostic*: text goes in, a number comes out, and every generation is treated as an independent sample. Lodestar's data model is built around what a steering experiment actually produces — a *sweep*. Every generation it scores carries its `SteeringConfig` (which SAE feature or feature combination, which layer, which clamp scale), its condition (below), its language, and its source model as first-class fields, not metadata bolted on afterward. Cross-scale, cross-language, and cross-model comparisons fall out of that data model directly instead of being a one-off script glued to a single experiment.

## The three-arm design

This is the part most steering write-ups skip, and the reason Lodestar exists as a harness rather than a scoring script.

Every generation Lodestar judges carries one of three conditions:

- **`baseline`** — the model's un-steered output for a prompt.
- **`control`** — the same prompt, the same intervention scale, but a randomly chosen feature or direction instead of the one under test.
- **`steered`** — the actual steering configuration being evaluated.

The `control` arm is the load-bearing one. Without it, "steering raised concept-relevance from 3.1 to 6.8" isn't evidence that the *feature* did anything in particular — a large enough perturbation to the residual stream can push a model off-topic and toward *something*, regardless of which direction produced it. Lodestar's `control_gap` metric computes `relevance(steered) − relevance(control)` at matched scale, language, and model, with a bootstrap 95% confidence interval (2,000 resamples) and a two-sided Mann–Whitney U test — so "the control is basically at zero" becomes a number with a confidence interval and a p-value instead of a sentence in the discussion section.

It's also where the name comes from: a lodestar is the fixed star you take a bearing from. The tool's job is to be that fixed reference for a steering result — not to be steered itself.

## Install

Python 3.11 or newer.

```bash
python -m pip install -e .
```

For development:

```bash
python -m pip install -e ".[dev]"
pytest
ruff check .
mypy lodestar
```

## Quickstart

```bash
lodestar estimate results/steering/generations.json --judge claude-sonnet-4-5-20250929
export ANTHROPIC_API_KEY="..."
lodestar eval results/steering/generations.json --target-concept poutine --judge claude-sonnet-4-5-20250929 --budget 25 -o run
lodestar optimal run --objective "max concept_relevance s.t. coherence >= 7" -o run/optimal.csv
lodestar validate run --export labels.html
lodestar report run -o report.html
```

`lodestar estimate` never makes an API call — it prices the run against your local judgment cache first. `lodestar eval --budget` refuses to start a run predicted to exceed it. Pass `--judge mock` anywhere a judge model is expected for a deterministic, zero-cost, offline run; the mock's scores are engineering fixtures, not research results.

Two more commands round out the CLI: `lodestar compare run_a/ run_b/ --by language|model|config` for a side-by-side metric table across saved runs, and `lodestar validate run --human labels_filled.csv` to turn a filled-in label export into a judge-versus-human correlation report.

## Inputs and outputs

Lodestar auto-detects, from one positional `GENERATIONS` argument:

- the steering pipeline's own nested `generations.json` (baseline, scale-swept steered, random-control, and ablation entries in one file);
- a generic normalized JSON array, or `{"generations": [...]}`;
- normalized JSONL or CSV.

The pipeline's file omits some provenance it doesn't track itself, so pass `--model-name`, `--language`, `--sae-checkpoint-id`, `--hook-layer`, and `--random-feature-id` at ingestion time if you need them recorded. A completed run directory holds `run.json`, `manifest.json`, `cache.sqlite`, `reliability.csv`, and `high_variance.csv`.

## The rubrics

Six rubrics, five judged by an LLM and one partly deterministic. Each corresponds to a failure mode that's normally caught by eyeballing outputs by hand — here it's a number with a rationale attached.

| Rubric | Scale | What it scores |
|---|---|---|
| `coherence` | 1–10 | Grammaticality and fluency, independent of topic — a fluent off-topic answer scores high here. |
| `concept_relevance` | 1–10 | How centrally the text is about the target concept. |
| `literal_mention` | binary + count | Whether the target concept (or an alias) literally appears — computed deterministically *and* judged, so judge/grep disagreement is itself reported. |
| `prompt_adherence` | 1–10 | How much the output still answers the original prompt. Low adherence with high relevance is the signature of strong, clean steering. |
| `integration_naturalness` | 1–10 | Whether the concept is woven in naturally versus bolted on. |
| `degeneration_flags` | categorical | `repetition_loop \| topic_salad \| language_drift \| gibberish \| none`. |

Every judgment keeps its rationale, judge model, rubric version, and token usage, so a headline number always traces back to a raw generation.

## Validation, not vibes

- **Self-consistency.** Each `(generation, rubric)` pair is judged `k` times (`--repeats`, default 3) at temperature 0: Krippendorff's α and ICC(2,1) for ordinal rubrics, Fleiss' κ for the binary one. This is a **determinism check** — it shows the judge agrees with itself under fixed settings, not that it is correct. Treat it as necessary, not sufficient.
- **Human correlation.** `lodestar validate run --export labels.html` produces a stratified sample (across condition, scale, language, and score band) as a self-contained local labeling page; `lodestar validate run --human labels_filled.csv` turns the filled-in labels into Spearman ρ / Kendall τ (ordinal) or Cohen's κ (binary) against the judge, plus a calibration scatter in the report.
- **Stats correctness.** The statistics module is anchored against textbook examples with published values, not just "it runs" — see `tests/test_stats.py`.

## API sketch

```python
from lodestar import EvalRun
from lodestar.metrics import coherence_relevance_frontier

run = EvalRun.load("run")
frontier = coherence_relevance_frontier(run)
print(frontier[frontier.pareto])
```

## Reproducibility and cost safety

Judge results live in a content-addressed SQLite cache keyed by `(text, rubric name/version, judge model, repeat)` — re-running an analysis after fixing a report bug costs nothing until you touch generation text, a rubric's version, or the judge model. `lodestar eval` refuses a moving model *alias* by default (pass `--allow-alias` to override), so a run's judge model can't silently drift underneath you. Pricing lives in one table in `lodestar/judges/cost.py`; it is hand-maintained and goes stale, so verify it against Anthropic's current pricing before a paid run.

## Known limitations

- **Snapshot pinning is enforced at the CLI, not inside the `Judge` classes.** `lodestar eval` refuses a moving model alias; a caller constructing `AnthropicJudge(...)` directly from Python is responsible for passing a pinned snapshot itself.
- **Self-consistency is a determinism check, not a correctness guarantee** (see above) — a judge that is systematically biased but reliably so would pass it unchanged. Report the human-correlation numbers alongside it, never instead of it.
- **The real Anthropic judge path is exercised manually, not in CI.** CI runs the full suite against the deterministic mock judge only; the live API call, including its structured-output request shape, should be spot-checked against the current `anthropic` SDK before you depend on it for a real run.
- **The generic ingestion adapter can merge generations that differ only in an `experiment` label.** Two generations identical in text, prompt, and provenance but distinguished only by an arbitrary comparison label can end up sharing an internal ID. The first-party steering adapter avoids this by folding `experiment` into its prompt hash; a custom adapter that needs to keep such runs distinct should do the same.
- **A broken custom metric fails the whole report, not just its own panel.** `register_metric()` has no error handling wrapped around a third-party metric call, by design — silently swallowing the exception would hide the plugin's bug from the person who registered it, at the cost of taking the report down when it fires.

## License and citation

MIT licensed — see [`LICENSE`](LICENSE). Citation metadata is in [`CITATION.cff`](CITATION.cff):

```bibtex
@software{el_yaakoubi_lodestar,
  author  = {El Yaakoubi, Mohamed El Yazid},
  title   = {Lodestar: Steering-native evaluation for interpretability research},
  year    = {2026},
  license = {MIT},
  url     = {https://github.com/mo-dev-x/lodestar}
}
```

---

Built by [Mohamed El Yazid El Yaakoubi](https://www.linkedin.com/in/mohamed-el-yazid-el-yaakoubi/) at IID.
