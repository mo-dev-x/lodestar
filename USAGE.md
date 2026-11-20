# Lodestar usage guide

This guide covers every command, the input formats, the output files, the rubrics, the judge-validation workflow and the HTML report. Start with the [README](README.md) for a quick overview. For the full design specification, see [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Commands

Run `lodestar <command> --help` for the authoritative list of flags.

| Command | What it does |
|---|---|
| `lodestar estimate GENERATIONS --judge MODEL` | Prices a run against the local judgment cache. It **never makes an API call**. `MODEL` must have an entry in `lodestar/judges/cost.py`, and `mock` does not. |
| `lodestar eval GENERATIONS -o RUN_DIR` | Ingests generations, judges them on every rubric, and saves a run directory. Useful flags are `--judge` (an Anthropic model ID, or `mock`), `--repeats` (default 3), `--target-concept`, `--aliases`, `--budget`, `--concurrency`, `--seed` and `--allow-alias`. |
| `lodestar optimal RUN_DIR --objective "..."` | Finds the best operating points for an objective such as `"max concept_relevance s.t. coherence >= 7"`. `-o file.csv` saves the result. |
| `lodestar compare RUN_A RUN_B ... --by language\|model\|config` | Prints a side-by-side metric table across saved runs. |
| `lodestar validate RUN_DIR --export labels.html` | Exports a stratified sample as a self-contained local labelling page. The sample is spread across condition, scale, language and score band. |
| `lodestar validate RUN_DIR --human labels_filled.csv` | Turns filled-in human labels into a report on how well the judge agrees with the humans. |
| `lodestar report RUN_DIR -o report.html` | Renders the self-contained HTML report. |

`--judge mock` makes `eval` deterministic, offline and free. Use it for tests, CI and dry runs. Its scores are not research results.

## Inputs

`eval` and `estimate` take one positional `GENERATIONS` argument and detect its format automatically:

- the steering pipeline's own nested `generations.json`, which holds baseline, scale-swept steered, random-control and ablation entries in one file;
- a generic normalized JSON array, or `{"generations": [...]}`;
- normalized JSONL or CSV.

The pipeline's file leaves out some provenance that the pipeline does not track itself. Pass `--model-name`, `--language`, `--sae-checkpoint-id`, `--hook-layer` and `--random-feature-id` when you ingest it if you need those recorded.

## Outputs

A completed run directory contains:

| File | Contents |
|---|---|
| `run.json` | The full `EvalRun`: generations, judgments and manifest. |
| `manifest.json` | Run metadata: tool version, judge snapshot, seeds, the command line, timing, token usage, cache hits and total cost. |
| `cache.sqlite` | The content-addressed judgment cache. Keep it to make re-runs free. |
| `reliability.csv` | Self-consistency statistics for each rubric. |
| `high_variance.csv` | Generations on which the judge disagreed with itself across repeats. |

## The three-arm design

Every generation has one of three conditions:

- **`baseline`**: the model's un-steered output for a prompt.
- **`control`**: the same prompt and the same intervention scale, with a randomly chosen feature or direction in place of the one under test.
- **`steered`**: the steering configuration being evaluated.

The `control` arm is what makes a result evidence. A large enough perturbation to the residual stream can push a model toward *some* topic whatever direction caused it. `control_gap` reports `relevance(steered) − relevance(control)` at matched scale, language and model, with a bootstrap 95% CI and a Mann–Whitney U test.

## Rubrics

| Rubric | Scale | What it scores |
|---|---|---|
| `coherence` | 1–10 | Grammar and fluency, independent of topic. A fluent off-topic answer scores high. |
| `concept_relevance` | 1–10 | How central the target concept is to the text. |
| `literal_mention` | binary + count | Whether the target concept, or one of its aliases, appears literally. This is computed deterministically *and* judged, and any disagreement between the two is reported. |
| `prompt_adherence` | 1–10 | How well the output still answers the original prompt. |
| `integration_naturalness` | 1–10 | Whether the concept is woven in naturally or bolted on. |
| `degeneration_flags` | categorical | `repetition_loop`, `topic_salad`, `language_drift`, `gibberish` or `none`. |

## Judge validation

- **Self-consistency.** Each `(generation, rubric)` pair is judged `k` times (`--repeats`) at temperature 0. Ordinal rubrics are summarised with Krippendorff's α and ICC(2,1), and the binary rubric with Fleiss' κ. This is a determinism check, not a correctness check.
- **Human correlation.** Export with `validate --export`, label the sample, then import with `validate --human`. You get Spearman ρ / Kendall τ (ordinal) or Cohen's κ (binary), and the report shows a calibration scatter.

## The report

The report is one HTML page with seven tabs. You can link to each tab with a `#hash`.

| Tab | Contents |
|---|---|
| **Overview** | Run identity and stat cards. The headline is the optimal clamp scale, labelled *the lodestar*, shown beside the peak steering-efficacy score. |
| **Frontier** | The coherence/relevance frontier across the scale sweep, and the control gap. |
| **Configurations** | Optimal operating points, the cross-lingual matrix and the cross-model comparison. |
| **Validation** | Self-consistency results, plus the judge-vs-human calibration scatter when labels were supplied. |
| **Generations** | Every generation with its rubric scores and the judge's rationale. |
| **Custom** | Tables from anything registered through `register_metric()`. |
| **Export** | The underlying data as CSV, embedded as data URIs. |

Panels are shown only when the data supports them. The frontier needs at least two scale points, the cross-lingual view at least two languages, the cross-model view at least two models and reliability at least two repeats. The control gap needs a `control` arm paired with a `steered` one. To force a panel on or off, call `generate_report(run, output, sections={...})` from Python. The CLI has no option for it.
