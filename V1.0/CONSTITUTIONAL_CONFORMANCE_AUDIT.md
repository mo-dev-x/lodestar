# Constitutional Conformance Audit — Lodestar Implementation vs. `CONSTITUTION.md` v1.0

Status: **Normative audit** · Derives from: [`CONSTITUTION.md`](CONSTITUTION.md) · Scope: current `lodestar/` implementation

> Determines whether the implementation conforms to the Constitution, clause by clause and subsystem by subsystem. It does not review the architecture and proposes no alternative designs; the Constitution is assumed final.

## 1. Executive Compliance Summary

The implementation is **peripherally conformant and centrally non-conformant.** The subsystems the Constitution treats as *supporting* — Validation, Metric purity, Plugin fault-containment, Record re-stamping, aggregation locality — largely comply. The subsystem the Constitution treats as *foundational* — the **identity spine** (Subject/Instrument/Method identity, and the cache/provenance built on it) — does not.

There is exactly **one Constitutional Blocker**: the judgment cache is keyed on a strict subset of the execution coordinates, so `cache identity ≠ execution identity` — the precise failure §6/THM3 and INV-NOHIDE exist to forbid. Because a single Blocker gates release regardless of how much else conforms, the implementation is **Not Constitutionally Compliant.**

Encouragingly, the violations share **one root**: the code has no first-class notion of the execution-coordinate tuple `(S,C,I,M,T)`. Every Major violation (untyped `experiment`, no snapshot pinning, no invalidation lever for framing/schema, content-blind Generation identity, incomplete provenance) is a facet of that single absence. Fixing the identity spine collapses most of the findings at once. Estimated remediation: **~4–6 engineer-days.**

---

## 2. Per-Subsystem Audit

Findings are labelled **F1–F9** and reused across subsystems to avoid repetition.

### 2.1 Cache
- **INV-NOHIDE (§5) / THM3 (§6) — VIOLATION → CONSTITUTIONAL BLOCKER (F1).**
  - *Constitution:* the cache key MUST be an injective encoding of `(S,C,I,M,T)` excluding `R`; no answer-affecting input may be absent.
  - *Implementation:* `cache_key = sha256(text ‖ rubric.name ‖ rubric.version ‖ judge_model ‖ repeat_index)` — `judges/cache.py:13-19`. The judge’s actual input is `render_rubric(rubric, gen)` (`rubrics/base.py:21-28`), which interpolates `prompt`, `target_concept`, `language`, `aliases` (all **S**), plus the call carries `output_schema` and a hardcoded `system` (both **I**) and `max_tokens` (**M**) — `judges/anthropic.py:104-116`. **None** of these are in the key.
  - *Why it violates:* the key is coarser than `≈_E`; execution-distinct queries collide. Proven end-to-end (a `sushi` query served a `poutine` judgment).
  - *Consequence:* silent wrong scores under the marketed “re-runs are free” workflow; corrupts published reliability/correlation numbers.
  - *Smallest fix:* compute the key over the rendered prompt plus a hash of the sanitized `output_schema`, the `system` text, and `max_tokens`; canonicalize `aliases`; move `render` above `cache.get`; bump a cache-schema marker so stale entries cold-miss.
- **THM3.C / THM3.D (§6) — VIOLATION → MAJOR (F2).** No fail-closed path and no snapshot enforcement; `cache.get` will serve for any `judge_model` string including a moving alias. *Smallest fix:* refuse a hit when `M` is not a resolved snapshot.
- **INV-RESTAMP (§5) — CONFORMANT (C4).** `cache.get` re-stamps `generation_id`, sets `cached=True`, zeroes `usage`, files old usage under `metadata.cached_usage` — `judges/cache.py:68-76`.
- **Cache preflight without full materialization (§7.3) — CONFORMANT.** `count_hits` probes SQLite per key rather than loading all judgments — `judges/cache.py:106-120`.

### 2.2 Judge
- **THM3.C Snapshot obligation (§6/§7.1) — VIOLATION → MAJOR (F2).** No resolution or verification; `judge_model` is passed through verbatim (`config.py:14`, `cli.py:120`); pricing matches by loose `startswith` incl. aliases (`judges/cost.py:48-56`). Default is dated, but nothing enforces it. *Smallest fix:* a `require_snapshot(model)` guard, recorded in the manifest.
- **INV-NOHIDE (§5) — VIOLATION (F1, shared).** `system` prompt and `output_schema` are answer-affecting inputs the judge sends but that never enter any identity.
- **INV-DETTYPE (§5/§7.1) — MINOR VIOLATION (F7).** Determinacy *is* declared (`Rubric.deterministic`, `models.py:137`; set for `literal_mention`, `rubrics/steering.py:78`), but the judge branches on the **name literal** `rubric.name == "literal_mention"` (`judges/anthropic.py:169`), not the declared flag. *Smallest fix:* branch on `rubric.deterministic`.
- **INV-TRACE (§7.1) — partial (see Provenance, F6).**

### 2.3 Rubrics
- **Ontology §2.1 (Criterion vs Instrument) / INV-LEVER (§5) — VIOLATION → MAJOR (F4).** The `Rubric` model fuses Criterion and Instrument and exposes only `name`+`version`; the judge-facing `system` text lives outside the rubric (`judges/anthropic.py:108`), so a framing or schema edit has **no invalidation lever** (INV-LEVER) and no identity. *Consequence:* stale reuse after a framing/schema change with no way to signal it. *Smallest fix:* derive an Instrument content-id (hash of template+schema+system) and include it in the cache key (the `I` term of the F1 fix); no model split required.
- **INV-DETTYPE — CONFORMANT (declaration).** The `deterministic` flag exists (see F7 for the honoring gap).

### 2.4 Metrics
- **INV-TYPED (§5) — VIOLATION → MAJOR (F3).** Metrics group and Pareto-compare on `experiment`, read from untyped `generation.metadata.get("experiment","unknown")` (`models.py:269`) and grouped in `metrics/derived.py:62,69,125,147`. *Consequence:* the ablation-vs-sweep separation rests on a metadata convention; a producer that omits it silently mis-groups. *Smallest fix:* promote `experiment` to a typed field; read the typed column in `scores()`.
- **INV-PURE (§5) — CONFORMANT (C2).** Metrics are pure; `control_gap` uses a fixed-seed RNG (`metrics/derived.py:165`).
- **INV-AGG (§5) / THM4 (§6) — CONFORMANT with caveat.** Aggregation is over `repeat_index` within `(generation_id, rubric)`; comparisons hold typed coordinates equal — consistent with `≈_meas`. *Caveat:* validity inherited from Subject identity, which is content-blind (F5).

### 2.5 Plugins
- **INV-CONTAIN (§5) — CONFORMANT (C1).** *(Corrected from the stale GAPS.md.)* Custom metrics are invoked under `try/except`, degrading to a per-panel error state; built-ins are deliberately unwrapped — `report/html.py:26-46`. Matches §5 exactly.
- **INV-NOHIDE / INV-TYPED (§7.5) — LATENT RISK (F9).** Registries admit callables without a declared coordinate contract, and `Generation` uses `extra="allow"` (`models.py:65`). No current plugin exploits it. *Classify:* Minor. *Smallest fix:* `extra="forbid"` with a `metadata` catch-all.

### 2.6 Provenance
- **INV-TRACE / §7.6 — VIOLATION → MAJOR (F6).** The `Judgment` carries `rubric_name`, `rubric_version`, `judge_model`, `repeat_index` (`models.py:151-163`) — but **no Instrument content-id** (only a version proxy), **no invariance-model version**, and **no resolved snapshot**. *Consequence:* a number cannot be traced to the exact instrument or invariance regime; THM6c reproducibility is unverifiable across environments. *Smallest fix:* add `instrument_id` and `invariance_version` to the Judgment and the resolved snapshot to the manifest.
- **INV-RESTAMP — CONFORMANT (C4, see Cache).**

### 2.7 Validation
- **§7.7 / THM4 — CONFORMANT (C3, C7).** Reliability computed within `≈_meas` classes (per `generation_id`×rubric across repeats — `validation/consistency.py:25-58`); human labels paired to the aggregated Domain quantity via `labeling_frame`→`scores()` (median over repeats — `validation/human.py:30-33`), not a single trial. Validity reported, not assumed (§8.3). The cleanest subsystem in the codebase.

### 2.8 CLI
- **Propagates F1/F2/F3 — MAJOR (inherited).** A faithful driver, but defaults make the Blocker reachable: `eval` writes the cache to `output/cache.sqlite`, `output` defaulting to `run` (`cli.py:118,139`), so two `eval`s with default `-o run` and different `--target-concept`/`--aliases` share a cache under F1. It also accepts `--judge` without snapshot enforcement (F2). *Smallest fix:* none beyond F1/F2; optionally warn when a shared cache spans differing concept/alias.

### 2.9 Reporting
- **INV-CONTAIN — CONFORMANT (C1).**
- **INV-TYPED — VIOLATION (F3, shared).** The report filters on `experiment` from the untyped column (`report/html.py:460-463`). Resolved by F3.
- **INV-TRACE / §7.6 — CONFORMANT for the drill-down** (every generation traces to raw text), but inherits F6’s missing instrument/invariance fields.

### 2.10 Data Models
- **INV-DECIDE (§5) — VIOLATION → MAJOR (F5).** The Subject `S = (text, prompt, target_concept, language, aliases)` (Constitution §2.3) must have a total, decidable identity. `scores()` uses `Generation.id` as both the judgment foreign key and the aggregation key (`{g.id: g}`, `models.py:232`), so `Generation.id` must **refine** the Generation-resident Subject equality: *id-equal ⟹ S-equal*, so distinct Subjects never merge. `Generation.id = hash(prompt_id, config, condition, seed)` (`models.py:79-94`) violates this two ways: **(a)** it omits `text`, `target_concept`, and `language` outright; and **(b)** it carries `prompt` only *indirectly* via `prompt_id`, which is **not** an `S` field and is only a *conditional* surrogate — the steering adapter sets `prompt_id = hash(prompt, experiment)` (`ingest/steering_json.py:67`), but the generic adapter (`Generation.model_validate`) and direct construction admit arbitrary `(prompt, prompt_id)` pairs, so two generations with different `prompt` but equal `prompt_id` (and equal remaining fields) collide on `Generation.id` although their Subjects differ. In both cases distinct Subjects merge, `{g.id: g}` keeps one, and the survivor's attributes are mis-attributed. Reachable through the generic adapter and the cross-concept / cross-lingual studies the tool targets. *Diagnosis:* `Generation.id` must refine `S`, and every Generation-resident `S` field — `text`, `prompt`, `target_concept`, `language` — must be encoded **directly**, never through a non-`S` surrogate such as `prompt_id`. *Smallest fix:* add `text`, `prompt`, `target_concept`, and `language` to the `Generation.id` payload directly; `prompt_id` may remain as a provenance coordinate but is no longer relied on to carry the `prompt` dimension. **`aliases` is excluded from `Generation.id` by design** — it is the *Rubric-resident* component of `S` (`rubric.aliases`), not a `Generation` field; per the Constitution §2.3 coordinate–object note the alias component of `S` enters identity through the Instrument and the F1 execution key (`execution_cache_key` renders `sorted(rubric.aliases)`), never through `Generation.id`. *Acceptance:* INV-DECIDE is restored only when `Generation.id` encodes the full Generation-resident subset `{text, prompt, target_concept, language}` **directly**; encoding `prompt` via `prompt_id`, or adding `text` alone, is insufficient.
- **INV-TYPED (F3), Instrument-identity (F4), extra="allow" (F9)** — as above.
- Typed steering ontology (`SteeringConfig`, `condition`, `scale`, feature tuples) — **CONFORMANT** with §2.

### 2.11 Experiment Management
- **INV-TYPED (§5) — VIOLATION → MAJOR (F3, primary locus).** “Experiment” is the paradigm case the Constitution names: a comparison dimension that must be typed, currently a metadata string. *Smallest fix:* F3.

### 2.12 Ingestion
- **INV-TYPED downstream — MINOR (F8).** The steering adapter sets `metadata["experiment"]` (`ingest/steering_json.py:93`); the **generic adapter does not** (`ingest/generic.py:48`), so third-party data defaults to `"unknown"`. Resolved by F3.
- **Subject fidelity — CONFORMANT.** Adapters stamp `language`/`target_concept`/`model_name` from flags; correctness depends on correct flags (user contract), not a violation.

---

## 3. Compliance Matrix

| Constitutional clause | Status | Finding | Primary subsystem(s) |
|---|---|---|---|
| §2 Ontology — entities present | Conformant | — | Data Models |
| §2 Ontology — Criterion vs Instrument separated | **Major** | F4 | Rubrics |
| INV-DECIDE (decidable, content-anchored identity) | **Major** | F5 | Data Models, Cache |
| INV-NOHIDE (no hidden determinants) | **BLOCKER** | F1 | Cache, Judge, Rubrics |
| INV-TYPED (typed comparison dimensions) | **Major** | F3 | Metrics, Experiment Mgmt, Ingestion, Reporting |
| INV-LEVER (universal invalidation lever) | **Major** | F4 | Rubrics, Judge, Cache |
| INV-RESTAMP (provenance freshness) | Conformant | C4 | Cache, Provenance |
| INV-TRACE (provenance totality) | **Major** | F6 | Provenance, Data Models |
| INV-DETTYPE (determinacy honored) | Minor | F7 | Judge, Rubrics |
| INV-AGG (aggregation locality) | Conformant* | (F5 caveat) | Metrics, Validation |
| INV-PURE (metric purity) | Conformant | C2 | Metrics |
| INV-CONTAIN (fault containment) | Conformant | C1 | Plugins, Reporting |
| THM1/THM3 (cache = execution identity) | **BLOCKER** | F1 | Cache |
| THM3.C (snapshot obligation) | **Major** | F2 | Judge, Config |
| THM3.D (fail-closed) | **Major** | F2 | Cache |
| THM4 (aggregation validity) | Conformant* | (F5 caveat) | Metrics |
| THM5 (audit completeness) | Minor→Major | F6 | Provenance |
| THM6 (reproducibility bounds) | **Major** | F1+F2 | Cache, Judge |
| §7.7 Validation obligations | Conformant | C7 | Validation |

`*` conformant in mechanism; validity inherited from Subject identity (F5).

---

## 4. Prioritized Remediation Roadmap

1. **F1 — Cache key = execution identity (BLOCKER).** Key over `render_rubric(...)` + `H(output_schema)` + `system` + `max_tokens` + `name/version` + `judge_model` + `repeat`; canonicalize aliases; render before lookup; bump cache schema. *Closes F1; delivers the `I`/`M` terms that satisfy F4.*
2. **F5 — Content-anchor `Generation.id`.** Encode the full Generation-resident subset of `S` — `text`, `prompt`, `target_concept`, and `language` — **directly** in the id payload (do not carry `prompt` via the conditional `prompt_id` surrogate); `aliases` stays out (Rubric-resident, enters identity via the Instrument / F1 key). *Closes F5.*
3. **F3 — Typed `experiment`.** Promote to a typed field; set in both adapters; read in `scores()`. *Closes F3 and F8.*
4. **F2 — Snapshot pinning + fail-closed.** *Closes F2 (THM3.C/D, THM6b).*
5. **F6 — Provenance completeness.** Record `instrument_id`, `invariance_version`, resolved snapshot. *Closes F6 (THM5, THM6c).*
6. **F7 — Honor the determinacy flag.** Branch on `rubric.deterministic`. *Closes F7.*
7. **F9 — `extra="forbid"` on `Generation`.** *Closes the latent plugin risk.*

---

## 5. Estimated Implementation Effort

| Finding | Effort | Note |
|---|---|---|
| F1 (Blocker) | 1.5–2 d | key change, render move, alias canonicalization, cache-schema bump, tests |
| F5 | 0.5 d | id adds text + prompt + target_concept + language (prompt direct, not via prompt_id); migration note; collision tests |
| F3 (+F8) | 0.5–1 d | typed field, two adapters, read sites |
| F2 | 0.5–1 d | snapshot guard, fail-closed, manifest record |
| F6 | 1 d | instrument-id + invariance-version + snapshot fields |
| F7 | 0.25 d | one-line branch + generalize term source |
| F9 | 0.25 d | `extra="forbid"` + metadata catch-all |
| **Total** | **~4–6 engineer-days** | F4 absorbed by F1; findings share one root |

---

## 6. Constitutional Compliance Percentage

Across the 19 audited clauses: **8 conformant** (2 caveated), **1 minor**, **8 major**, **2 blocker** (single root). Fully-conformant ≈ **42%**; with partial credit ≈ **45%**.

**Weighting note:** the number understates (conformant clauses include the hardest — validation statistics, purity, containment) and overstates (compliance is not additive under a Blocker — one INV-NOHIDE violation invalidates the numbers every other clause helps produce). Treat 45% as the clause-level figure and the Blocker as the gate.

---

## 7. Release Recommendation

> ## ⛔ Not Constitutionally Compliant
>
> One **Constitutional Blocker** (INV-NOHIDE / THM3, finding **F1**): the cache’s identity is not its execution identity, so the framework can silently return a judgment computed for a different question. Per §9, no release may ship while an invariant is violated.
>
> The path back is short and single-rooted: **F1 clears the Blocker; F2–F6 clear the Majors**, together ~4–6 engineer-days, after which the recommendation rises to **Compliant with Minor Violations** (F7, F9 remaining) and, once those land, **Fully Compliant.** The identity spine is the whole job; the rest of the implementation already conforms.
