# Lodestar

Lodestar is a steering-native evaluation harness for sparse-autoencoder interpretability research. It turns generation sweeps into auditable coherence, concept-relevance, prompt-adherence, naturalness, degeneration, and literal-mention scores; finds Pareto-optimal operating points; quantifies controls and transfer; and validates the judge against repeated calls and human labels.

It is designed for the artifact you already have: `generations.json`. No steering-pipeline changes are required.

## Install

Python 3.11 or newer is required.

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

## Six-line quickstart

```bash
lodestar estimate results/steering/generations.json --judge claude-sonnet-4-5-20250929
export ANTHROPIC_API_KEY="..."
lodestar eval results/steering/generations.json --target-concept poutine --judge claude-sonnet-4-5-20250929 --budget 25 -o run
lodestar optimal run --objective "max concept_relevance s.t. coherence >= 7" -o run/optimal.csv
lodestar validate run --export labels.html
lodestar report run -o report.html
```

Use `--judge mock` for a deterministic, zero-cost end-to-end run. The mock scores are engineering fixtures, not research results.

## Why it exists

Lodestar replaces keyword checks with calibrated scoring, manual sweet-spot selection with a coherence–relevance Pareto frontier, and unsupported “LLM-as-a-judge” claims with reliability and human-correlation evidence. Every aggregate retains a path back to the raw generation, rubric version, judge model, repeat, token usage, and steering configuration.

## Inputs and outputs

Lodestar auto-detects:

- the project steering pipeline’s nested `generations.json`, including baseline, scale-swept steering, random controls, and ablations;
- normalized JSON arrays or `{ "generations": [...] }` documents;
- normalized JSONL and CSV.

Pipeline files omit some provenance, so pass `--model-name`, `--language`, `--sae-checkpoint-id`, `--hook-layer`, and `--random-feature-id` when evaluating them. A run directory contains `run.json`, `manifest.json`, `cache.sqlite`, `reliability.csv`, and `high_variance.csv`.

See [usage](docs/USAGE.md), [rubrics](docs/RUBRICS.md), [validation](docs/VALIDATION.md), and [extension points](docs/EXTENDING.md).

## API sketch

```python
from lodestar import EvalRun
from lodestar.metrics import coherence_relevance_frontier

run = EvalRun.load("run")
frontier = coherence_relevance_frontier(run)
print(frontier[frontier.pareto])
```

## Reproducibility and cost safety

Judge results use a content-addressed SQLite cache keyed by text, rubric name/version, judge model, and repeat. `estimate` makes no API calls. `eval --budget` refuses a predicted over-budget run. Pricing lives in one table in `lodestar/judges/cost.py`; verify that table against Anthropic’s official pricing page before paid runs because provider pricing changes.

## License and citation

MIT licensed. Citation metadata is in [`CITATION.cff`](CITATION.cff).

