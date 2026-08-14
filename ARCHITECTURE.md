# Lodestar — Architecture Specification

**A steering-native evaluation harness for sparse-autoencoder interpretability research.**

> *Lodestar* (n.): a star used to guide the course of a ship. The tool you steer by.
> Package name `lodestar-eval`, import `lodestar`. (Name is one constant in `__init__.py`; change freely if PyPI collides.)

This document is the build blueprint. Every design decision is made here. Implementing it should be mechanical. Building against the cluster (where the API key and generations live); this spec is the contract.

> **Constitutional foundation.** This blueprint is *derived from* [`CONSTITUTION.md`](CONSTITUTION.md) — Lodestar's highest-level specification (ontology, axioms, identities, invariants, theorems, obligations). Where this document and the constitution disagree, **the constitution governs**; new architectural decisions should cite the axiom, invariant, or theorem they serve.

---

## 0. The one-sentence pitch

Lodestar takes the generations produced by a steering experiment — across any sweep of features, scales, weights, prompts, languages, and models — and returns rigorous, multi-dimensional, **human-correlated** quality metrics, automatically finding the optimal operating point and quantifying the coherence/relevance tradeoff that researchers currently eyeball by hand.

It replaces three things every steering paper rebuilds from scratch:
1. The ad-hoc keyword check (`mentions_poutine()`) → real, validated scoring.
2. The manual "read the outputs and decide which scale is best" → a Pareto frontier + objective-driven optimizer.
3. The appendix that says "we used GPT-4-mini as a judge, trust us" → a built-in self-consistency + human-correlation report that produces the exact sentence reviewers want: *"our judge attains Spearman ρ = 0.8X with human annotators (n = Y, p < 0.001)."*

---

## 1. Design principles (non-negotiable)

1. **Steering-native data model.** `SteeringConfig`, `condition` (baseline / steered / control), scale sweeps, and feature *combinations* are first-class — not bolted on.
2. **Language and model are dimensions, not afterthoughts.** Every `Generation` carries `language` and `model_name`; cross-lingual and cross-model comparison fall out of the data model for free.
3. **Rigor is the product.** Self-consistency and human-correlation aren't optional add-ons; they're core modules, because they're what make results publishable.
4. **Re-runs are free.** Content-addressed judge caching means you never pay for the same `(text, rubric, judge)` twice. This is essential because researchers iterate.
5. **Plugs into what you already produce.** An ingestion adapter reads the existing `generations.json` / `metrics.json` from the steering script. **Zero changes to the steering pipeline.**
6. **Judge-agnostic, Claude-first.** A `Judge` protocol lets OpenAI / local models be swapped in for robustness checks ("results stable across judge models"). Anthropic is the reference implementation.
7. **Full provenance.** Every number traces back through judgment → judge model + rubric version → raw generation → steering config. Every run is a versioned, hashed artifact.
8. **No dangling threads.** Cost preflight, rate-limit handling, parse-failure repair, deterministic seeds, CI — all in scope.

---

## 2. Package structure

```
lodestar-eval/
├── pyproject.toml                  # hatchling build, deps pinned, console_scripts entrypoint
├── LICENSE                         # MIT (permissive → maximizes citation/reuse)
├── README.md                       # quickstart, the pitch, a 6-line example
├── CITATION.cff                    # machine-readable citation (GitHub renders "Cite this repo")
├── .github/workflows/ci.yml        # lint + type-check + tests on push (mocked judge → free CI)
├── lodestar/
│   ├── __init__.py                 # __version__, TOOL_NAME, top-level exports
│   ├── models.py                   # pydantic v2 models: the whole data model (§3)
│   ├── config.py                   # RunConfig, env/API-key resolution, seed management
│   ├── rubrics/
│   │   ├── __init__.py             # registry: name → Rubric
│   │   ├── base.py                 # Rubric model + RubricResult schema
│   │   └── steering.py             # the 6 steering rubrics, full prompt templates (§4)
│   ├── judges/
│   │   ├── __init__.py
│   │   ├── base.py                 # Judge protocol (async judge_one / judge_batch)
│   │   ├── anthropic.py            # Claude judge: async, batched, retry, structured JSON
│   │   ├── mock.py                 # deterministic mock judge (tests + CI + dry runs)
│   │   ├── cache.py                # content-addressed SQLite cache (§5.3)
│   │   └── cost.py                 # token accounting + pre-flight estimator (§5.4)
│   ├── metrics/
│   │   ├── __init__.py
│   │   ├── derived.py              # SES, frontier, optimal config, control gap, transfer ratio (§6)
│   │   └── stats.py                # Krippendorff α, ICC, κ, Spearman, Kendall, bootstrap CIs (§7)
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── consistency.py          # self-consistency over k judge repeats (§7.1)
│   │   └── human.py                # labeling export/import + correlation report (§7.2)
│   ├── ingest/
│   │   ├── __init__.py
│   │   ├── steering_json.py        # adapter for the existing pipeline's output
│   │   └── generic.py              # generic JSONL/CSV adapter + schema validator
│   ├── report/
│   │   ├── __init__.py
│   │   ├── html.py                 # self-contained dashboard generator (§8)
│   │   └── templates/              # jinja2 templates + embedded CSS
│   └── cli.py                      # typer CLI: eval / compare / optimal / validate / report / estimate (§9)
├── tests/
│   ├── conftest.py                 # fixtures: sample EvalRun, mock judge, real generations.json sample
│   ├── fixtures/
│   │   ├── generations_sample.json # a trimmed real sample from the steering pipeline
│   │   └── krippendorff_known.json # textbook example with the published α value
│   ├── test_models.py
│   ├── test_rubrics.py             # template renders, schema parses, registry resolves
│   ├── test_stats.py               # α/ICC/κ vs hand-computed known values (the correctness anchor)
│   ├── test_metrics.py             # frontier, optimal-config objective parsing, control gap
│   ├── test_judge_mock.py          # full eval loop with mock judge (no network)
│   ├── test_cache.py               # cache hit/miss, content addressing, invalidation on rubric bump
│   ├── test_ingest.py              # the real fixture round-trips into normalized models
│   ├── test_validation.py          # consistency variance + human-correlation on synthetic data
│   └── test_cli.py                 # CLI smoke tests via typer.testing.CliRunner
└── docs/
    ├── USAGE.md                    # every command, every flag, worked examples
    ├── RUBRICS.md                  # scientific justification of each rubric (→ paper methods)
    ├── VALIDATION.md               # the validation methodology (→ paper appendix, copy-paste-able)
    └── EXTENDING.md                # how to add a rubric / judge / ingest adapter
```

**Stack:** Python 3.11+, `pydantic` v2 (models/validation), `anthropic` (judge), `typer` (CLI), `jinja2` (report), `numpy`/`scipy` (stats), `tenacity` (retry), `aiosqlite` (cache). Dev: `pytest`, `pytest-asyncio`, `ruff`, `mypy`.

---

## 3. Data model (`models.py`)

The heart of the tool. All pydantic v2, all serializable to/from JSON, all hashable where it matters.

```python
class SteeringConfig:
    sae_checkpoint_id: str          # provenance: which SAE produced these features
    hook_layer: int
    feature_ids: list[int]          # [65223, 10413] — combinations are native
    weights: list[float]            # [1.0, 1.0] — per-feature clamp weighting
    scale: float                    # the clamp value α
    decoding: DecodingParams        # temperature, top_p, repetition_penalty, no_repeat_ngram, max_new_tokens, do_sample
    def config_hash(self) -> str    # stable hash over all fields → groups generations into a "config"

class Generation:
    id: str                         # stable: hash(prompt_id + config_hash + condition + seed)
    text: str                       # the model output being judged
    prompt: str
    prompt_id: str
    condition: Literal["baseline", "steered", "control"]
    model_name: str                 # "Qwen/Qwen2.5-14B" — cross-model dimension
    language: str                   # ISO 639-1: "en","fr","zh","ar" — cross-lingual dimension
    target_concept: str             # "poutine" — what relevance is scored against
    steering_config: SteeringConfig | None   # None for baseline
    seed: int | None
    metadata: dict

class Rubric:
    name: str                       # "coherence"
    version: str                    # "1.0" — bumping invalidates cache for this rubric only
    description: str
    scale: ScoreScale               # OrdinalScale(1,10) | BinaryScale() | CategoricalScale([...])
    prompt_template: str            # jinja2; sees generation + target_concept + prompt
    output_schema: dict             # JSON schema the judge must satisfy

class Judgment:
    id: str
    generation_id: str
    rubric_name: str
    rubric_version: str
    score: float | bool | str       # ordinal/binary/categorical
    rationale: str                  # judge's one-line justification (auditability)
    judge_model: str
    repeat_index: int               # 0..k-1 for self-consistency
    raw_response: str               # full judge output, for debugging
    usage: TokenUsage
    cached: bool

class EvalRun:
    id: str
    created_at: datetime
    generations: list[Generation]
    judgments: list[Judgment]
    rubrics: list[Rubric]
    judge_model: str
    n_repeats: int
    manifest: RunManifest           # config hash, tool version, total cost, timing, seeds
    # indexed accessors:
    def by_config(self) -> dict[str, list[Generation]]
    def scores(self, rubric, aggregate="median") -> pandas.DataFrame  # tidy: one row per (gen, rubric)
```

`EvalRun` is the unit that gets saved (`run/` directory: `run.json` + `cache.sqlite` + `manifest.json`) and is the input to metrics, validation, comparison, and reporting.

---

## 4. Rubrics (`rubrics/steering.py`) — written out, not hand-waved

Six rubrics. The first five are LLM-judged; the sixth is partly deterministic. Each maps onto a failure mode the team already discovered *by hand* in the experiment log — now structured and scored.

| # | Rubric | Scale | What it captures | Replaces (manual finding) |
|---|--------|-------|------------------|---------------------------|
| 1 | `coherence` | 1–10 | grammaticality, fluency, no repetition loops / gibberish — **topic-independent** | "total gibberish", "repetition loops" |
| 2 | `concept_relevance` | 1–10 | degree the text expresses `target_concept` | the keyword `mentions_poutine` heuristic |
| 3 | `literal_mention` | binary + count | does `target_concept` (+ aliases) actually appear | the grep for "poutine" |
| 4 | `prompt_adherence` | 1–10 | how much the output still answers the original prompt | (new — the steering-specific axis) |
| 5 | `integration_naturalness` | 1–10 | concept woven in naturally vs. bolted-on/forced | "word-salad", "menu-speak", "bolted on" |
| 6 | `degeneration_flags` | categorical (multi) | `repetition_loop \| topic_salad \| language_drift \| gibberish \| none` | "drift into pizza/pesto/beignets" |

**Why #4 matters and is novel:** *low* `prompt_adherence` + *high* `concept_relevance` = strong, clean steering (the model abandoned the prompt to talk about the concept). This is the exact signal the team read by hand ("generated from a completely unrelated prompt") — now a number. It's also what the operating-point papers call the recovery gap, but packaged.

**Rubric prompt template (coherence, v1.0)** — the actual text:

```
You are a rigorous evaluator for a mechanistic-interpretability experiment on
LLM activation steering. You will score ONE piece of model-generated text on a
SINGLE dimension. Judge only what is asked. Be strict and calibrated.

DIMENSION: Coherence (grammatical fluency and readability)
- 10: flawless, fluent, natural prose.
- 7–9: minor awkwardness; fully readable.
- 4–6: degraded grammar or mild repetition; meaning still recoverable.
- 2–3: heavy repetition, broken syntax, or fragmentary.
- 1: gibberish / repeated tokens / no recoverable meaning.
IMPORTANT: Judge coherence ONLY. A perfectly fluent off-topic text scores high.
Do NOT reward or penalize topic.

TEXT TO EVALUATE:
"""{{ generation.text }}"""

Respond with JSON only, no preamble:
{"score": <int 1-10>, "rationale": "<=20 words"}
```

**Rubric prompt template (concept_relevance, v1.0):**

```
... DIMENSION: Concept relevance to "{{ target_concept }}"
- 10: centrally about {{ target_concept }} with accurate specifics.
- 7–9: clearly about {{ target_concept }} or its defining attributes.
- 4–6: related domain but not {{ target_concept }} specifically.
- 2–3: only tangential association.
- 1: unrelated.
Score relevance ONLY; ignore grammar/fluency.
TEXT: """{{ generation.text }}"""
{"score": <int 1-10>, "rationale": "<=20 words"}
```

(`prompt_adherence` sees `{{ generation.prompt }}` too; `degeneration_flags` returns a list; `literal_mention` is computed deterministically from `target_concept` + an alias list, but is *also* sent to the judge as a sanity cross-check so judge/grep disagreement is itself reportable.)

`RUBRICS.md` documents the scientific rationale for each — drop-in for the paper's methods section.

---

## 5. Judge layer (`judges/`)

### 5.1 `Judge` protocol (`base.py`)
```python
class Judge(Protocol):
    model_name: str
    async def judge_one(self, gen: Generation, rubric: Rubric) -> Judgment: ...
    async def judge_batch(self, items: list[tuple[Generation, Rubric]],
                          repeats: int) -> list[Judgment]: ...
```

### 5.2 `AnthropicJudge` (`anthropic.py`)
- Async via the official `anthropic` AsyncClient; bounded concurrency (semaphore, configurable, default 8).
- **Structured output:** rubric `output_schema` enforced; on JSON parse failure → one repair retry that re-sends the model's own output with "return valid JSON only"; on second failure → record a `Judgment` with `score=None`, `degeneration: parse_failure`, never crash the run.
- Retry with exponential backoff (`tenacity`) on 429 / 5xx / timeouts.
- Every call records `TokenUsage` and is wrapped by the cache (§5.3).
- Model pinned in the run manifest (e.g. `claude-...`); the judge model string is part of every `Judgment` and every cache key.

### 5.3 Cache (`cache.py`) — re-runs are free
- SQLite, content-addressed. Key = `sha256(text ‖ rubric.name ‖ rubric.version ‖ judge_model ‖ repeat_index)`.
- Hit → return stored `Judgment` (marked `cached=True`), zero API cost.
- Bumping a rubric's `version` invalidates only that rubric's entries. Changing judge model → new keys. Editing a generation's text → new key. **Nothing stale ever returns.**
- Lives in `run/cache.sqlite`; portable; can be shared across runs in the same project dir.

### 5.4 Cost accounting + preflight (`cost.py`)
- `estimate(generations, rubrics, repeats, judge_model)` → token + dollar estimate using current per-model pricing (pricing table in one constant, easy to update), **before** spending anything.
- CLI `lodestar estimate` prints: "This sweep = N judge calls (M cached, K new) ≈ \$X.XX. Proceed?" — and `eval` refuses to exceed an optional `--budget` ceiling.
- Post-run, the manifest records actual tokens and cost.

> **Product-fact note for the implementer:** pricing, model strings, rate limits, and batch-API availability change. Do **not** hardcode these from memory — read them from Anthropic's current docs at build time (the `product-self-knowledge` skill + docs.claude.com), and keep them in `cost.py`'s single pricing constant so they're trivially updatable.

---

## 6. Derived metrics (`metrics/derived.py`) — no LLM, pure computation

All computed from `Judgment`s, all returned as tidy DataFrames + typed summaries.

- **SES — Steering Efficacy Score** (per generation): a transparent composite, default
  `SES = concept_relevance × (coherence / 10)` — i.e. relevance discounted by incoherence, so a gibberish mention scores low. Weighting configurable; definition documented and reported, never a black box.
- **Coherence–Relevance frontier** (per config = per `config_hash`): across the scale sweep, the Pareto frontier of (coherence, relevance). This is the principled replacement for the team's manual "scale ≈ 150–200 is the sweet spot."
- **Optimal operating point** (per config): `argmax` over a user objective string, e.g.
  `"max concept_relevance s.t. coherence >= 7"` (parsed by a tiny safe expression grammar). Mirrors the "operating point" methodology from the steering literature, generalized.
- **Control gap / effect size**: `relevance(steered) − relevance(random control)` at matched scale, with a bootstrap 95% CI and a Mann–Whitney U test (their control is already 0 % — this quantifies *how* significant, properly).
- **Cross-lingual transfer ratio**: per config, `relevance(lang) / relevance(source_lang)` — the headline number for the multilingual paper, computed automatically across the language dimension.
- **Cross-model comparison**: same rubrics, grouped by `model_name`, aligned by config where comparable — the headline for the cross-architecture paper.

---

## 7. Validation subsystem (`validation/`) — the publishability core

### 7.1 Self-consistency (`consistency.py`)
- Each `(generation, rubric)` judged `k` times (`--repeats k`, default 3).
- Per-rubric judge reliability:
  - ordinal rubrics → **Krippendorff's α** (ordinal weighting) and **ICC(2,1)**;
  - binary rubric → **Fleiss' κ**.
- Per-generation score variance flagged; high-variance items surfaced in the report.
- Point estimate per `(generation, rubric)` = **median** across repeats (robust to outlier judge calls).
- Output: a reliability table + flags, embedded in the report.

### 7.2 Human correlation (`human.py`) — the sentence reviewers want
- `lodestar validate <run> --export labels_blank.csv` → a **stratified** sample (across conditions, scales, languages, score bands) in a flat CSV (or a tiny self-contained local HTML labeling page that writes the same CSV — no server).
- Human fills `score` columns; `lodestar validate <run> --human labels_filled.csv` computes judge↔human agreement per rubric:
  - ordinal → **Spearman ρ** and **Kendall τ** (+ bootstrap CIs);
  - binary → **Cohen's κ**;
  - plus **Krippendorff's α** treating judge + human as two raters.
- Emits a ready-to-paste results line and a calibration scatter (judge vs human) in the report.

### 7.3 Stats correctness (`metrics/stats.py`)
- Hand-rolled where it matters (Krippendorff's α with configurable distance metric), `scipy` for the standard tests, bootstrap CIs via resampling.
- **Anchored by tests:** `test_stats.py` checks α/κ/ICC against textbook examples with published values (`fixtures/krippendorff_known.json`). The numbers are *verified correct*, not just "they run."

---

## 8. Report / dashboard (`report/html.py`)

A **single self-contained HTML file** (data embedded; hand-coded SVG charts and inline interactions) generated from an `EvalRun`. Opens locally, no server, emailable, attachable to the paper as supplementary material. Sections:

1. **Overview** — config sweep summary, judge model, n_repeats, total cost, timing.
2. **Coherence–Relevance frontier** — interactive scatter per config; Pareto points highlighted; the manual "sweet spot" hunt, now a chart.
3. **Optimal operating points** — table per config for the chosen objective.
4. **Control gap** — steered vs control with CI + significance.
5. **Cross-lingual matrix** — heatmap: relevance & coherence × language × config; transfer ratios.
6. **Cross-model comparison** — same, grouped by model.
7. **Judge validation panel** — self-consistency reliability + (if labeled) human-correlation scatter and the citable ρ/κ/α line.
8. **Drill-down table** — every generation with prompt, condition, scale, all rubric scores, and the judge's rationales; filterable. Full auditability from headline number to raw text.

---

## 9. CLI (`cli.py`) — typer

```
lodestar estimate GENERATIONS [--rubrics steering] [--repeats 3] [--judge MODEL]
        → print judge-call count, cache hits, cost estimate. Spend nothing.

lodestar eval GENERATIONS [--rubrics steering] [--judge MODEL] [--repeats 3]
        [--target-concept poutine] [--budget 25.00] -o run/
        → ingest, judge (cached), self-consistency, write run/.

lodestar optimal run/ --objective "max concept_relevance s.t. coherence>=7"
        → best operating point per config, printed + CSV.

lodestar compare run_a/ run_b/ ... [--by language|model|config]
        → side-by-side metric table across runs (cross-lingual / cross-model).

lodestar validate run/ [--export labels.csv | --human labels.csv]
        → export stratified sample, or compute human-correlation report.

lodestar report run/ -o report.html
        → the dashboard.
```

`GENERATIONS` accepts the existing pipeline's `generations.json` directly (auto-detected by `ingest/steering_json.py`) or a generic JSONL/CSV.

---

## 10. Ingestion (`ingest/`) — zero pipeline changes

`steering_json.py` maps the steering script's existing output (the `generations.json` with baseline/steered/control text per prompt × scale, plus `metrics.json`) into normalized `Generation` objects, inferring `condition`, `scale`, `feature_ids`, `weights`, `language`, `model_name` from the file + CLI flags. A fixture of the *real* file (`tests/fixtures/generations_sample.json`) is round-trip tested so the adapter provably matches reality. `generic.py` + a published JSON schema lets anyone else feed their own data.

---

## 11. Test & CI plan

- **Stats anchored to known values** (`test_stats.py`) — correctness, not just execution.
- **Full eval loop runs offline** via `MockJudge` (`test_judge_mock.py`) — deterministic, free, CI-able.
- **Cache semantics** (`test_cache.py`) — hits, content addressing, rubric-version invalidation.
- **Real-data ingestion** (`test_ingest.py`) — the actual fixture normalizes correctly.
- **Validation math** (`test_validation.py`) — consistency variance + human-correlation on synthetic data with known correlation.
- **CLI smoke** (`test_cli.py`) — every command via `CliRunner`.
- **CI** (`.github/workflows/ci.yml`) — `ruff` + `mypy` + `pytest`, all on the mock judge so CI needs no API key and costs nothing.

The only thing tests can't exercise without the cluster + key is a live Claude call — and that's exactly the boundary where Claude Code on the cluster takes over: swap `MockJudge` → `AnthropicJudge`, point at the real `generations.json`, run.

---

## 12. Build order (so the first runnable result comes fast)

1. `models.py` + `rubrics/` + `ingest/steering_json.py` + `MockJudge` → **`lodestar eval` runs end-to-end on real generations, offline.** (First light.)
2. `metrics/stats.py` (+ tests vs known values) → `validation/consistency.py` → `metrics/derived.py`.
3. `judges/anthropic.py` + `cache.py` + `cost.py` → real scoring on the cluster.
4. `validation/human.py` → the correlation report.
5. `report/html.py` → the dashboard.
6. `cli.py` wiring, `docs/`, `CITATION.cff`, CI.

Each step ends on something that runs and is tested. No step leaves a stub behind.

---

## 13. What this gives the papers

- **Multilingual paper:** cross-lingual transfer ratios + the language heatmap, with a validated judge (ρ/α reported) → reviewers trust every downstream number.
- **Cross-architecture work:** `compare --by model` produces the comparison table directly.
- **The tool itself:** a clean, tested, documented, MIT-licensed, `CITATION.cff`-equipped repo other interp researchers can `pip install lodestar-eval` and cite — a contribution in its own right, not just internal scaffolding.

---

## 14. Scalability

**The cost model is exactly `O(N × R × J)` judge calls** — `N` generations × `R` rubrics × `J` repeats (`--repeats k`, default 3). `eval_montreal.py`'s real run is the concrete anchor: `N=161, R=6, J=3 → 2,898 judge calls`, which is precisely the judgment count the saved `run.json` carries. A 100k-generation sweep at the same `R`/`J` is `1.8M` calls — the formula is what tells you that *before* you run it, via `lodestar estimate` / `cost.estimate()` (§5.4), which walks the same `N × R × J` product to print an exact preflight dollar figure.

Three things keep that product from being three separate scaling problems:

1. **Bounded concurrency, not unbounded fan-out.** `judge_batch()` builds all `N × R × J` tasks up front and hands them to `asyncio.gather()`, but every actual network call passes through `AnthropicJudge`'s `asyncio.Semaphore(concurrency)` (default 8) inside `_request()`. Wall-clock time scales as `⌈(N×R×J) / concurrency⌉ × latency`, not `(N×R×J) × latency` — and the cap means a 100k-generation sweep can't thundering-herd the API or trip provider rate limits, regardless of how large `N` gets. Raising `concurrency` is a pure wall-clock/cost trade against rate-limit risk, with no correctness change.
2. **Caching makes repeated passes over the same `N × R × J` nearly free.** `JudgeCache` keys on `sha256(text ‖ rubric.name ‖ rubric.version ‖ judge_model ‖ repeat_index)` (§5.3) — content-addressed, not run-addressed. This is not theoretical: regenerating the Montreal report after fixing the ablation/scale-0 confound (§6, frontier grouping) re-ran the full metrics pipeline over the same 2,898 judgments at **zero additional API cost**, because every `(generation, rubric, repeat)` triple was an unchanged cache hit. The practical consequence for a 100k-generation experiment: iterating on rubric prompts, objective thresholds, or report layout after the first full pass costs nothing until you touch generation text, a rubric's `version`, or the judge model string — each of which invalidates only its own slice of the key space, never the whole cache.
3. **`J` (repeats) is the cheapest lever to cut for self-consistency specifically.** Today `judge_batch()` applies `repeats` uniformly across every item — there's no built-in way to ask for `k=3` on a stratified subsample and `k=1` everywhere else, even though `validation/human.py`'s `labeling_frame()` already does exactly this kind of stratified subsampling (by condition/scale/language/score-band) for human labeling. For a 100k-generation run, computing self-consistency (Krippendorff's α / ICC) on the same stratified few hundred rather than literally every row would cut the `J` term's cost by orders of magnitude with no loss of statistical signal — this isn't implemented yet (tracked as a real, scoped follow-up, not a hidden assumption: the fix is reusing `labeling_frame()`'s stratification to choose which items get `repeats > 1`, defaulting the rest to `repeats=1`).

The one cost dimension this doesn't shrink is `R`: every rubric judges every generation by design (§4) — that's what makes the drill-down (§8) fully auditable, score-by-score, for every row. If `R` itself becomes the bottleneck at very large `N`, the right lever is the same one as #3: judge the full rubric set on a stratified sample and a reduced rubric set (e.g. just `concept_relevance` + `literal_mention`) on the rest, rather than collapsing rubrics together.

---

## 15. Plugin architecture

Judges are designed against a `Protocol`, not a base class (�5.1, design principle #6), so a new judge only needs to expose `model_name`, `judge_one`, and `judge_batch`. Metrics use the same structural style through `MetricPlugin` plus `METRIC_REGISTRY`. Reports are intentionally not a plugin family: Lodestar has one report renderer, `lodestar.report.generate_report`, backed by `report/html.py`, `report/lodestar_svg.py`, `report/sections.py`, and `templates/report.html.j2`.

```python
# lodestar/judges/base.py
class Judge(Protocol):
    model_name: str
    async def judge_one(self, gen: Generation, rubric: Rubric) -> Judgment: ...
    async def judge_batch(self, items: list[tuple[Generation, Rubric]], repeats: int) -> list[Judgment]: ...

# lodestar/metrics/base.py
class MetricPlugin(Protocol):
    def __call__(self, run: EvalRun, **kwargs: Any) -> pd.DataFrame: ...
```

Rubrics and metrics get lightweight, discoverable registries:

- `lodestar.metrics.METRIC_REGISTRY` � the six built-in metrics (�6) register themselves; `register_metric(name, fn)` lets another lab add `my_custom_metric` without touching `derived.py`.
- `lodestar.rubrics.RUBRIC_REGISTRY` � the built-in rubrics register themselves; `register_rubric(rubric)` lets another lab add a rubric without touching `rubrics/steering.py`.
- Judges have no registry because judge selection is already a constructor call (`AnthropicJudge(model_name=...)` / `MockJudge()`), not a string lookup; adding one would be an abstraction with no current call site that needs it.

This is deliberately **Protocol-plus-registry where it earns its keep, not an ABC hierarchy everywhere**. A plugin author never has to import a Lodestar base class, inherit from it, or fight Python's MRO to extend judges, metrics, or rubrics. The report stays singular so the public reporting surface remains simple: call `generate_report(...)`.