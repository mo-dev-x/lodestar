# Lodestar — Constitutional Implementation Specification (CIS) v1.0

Status: **Normative execution plan** · Derives from: [`CONSTITUTION.md`](CONSTITUTION.md) and [`CONSTITUTIONAL_CONFORMANCE_AUDIT.md`](CONSTITUTIONAL_CONFORMANCE_AUDIT.md)

**Purpose.** Translate the Conformance Audit into an execution plan requiring no architectural judgment. Every type, field, signature, constant, file, migration, and test is pre-decided. An implementer follows it top to bottom.

**Scope of change.** Seven remediation items: **F5, F3, F9, F2, F1, F7, F6** (F4 absorbed into F1; F8 into F3). Presented in **implementation order**; ordering rationale and commit plan at the end.

**Conventions.** Symbol names in `code font`; file:line anchors inline. "MUST remain untouched" means the executor may not edit that file in that item's commit. No code is written here — only the exact shape of each change.

---

## Global constants introduced (define once, reuse everywhere)

| Constant | Value | Home module | Used by |
|---|---|---|---|
| `JUDGE_SYSTEM_PROMPT` | `"Return a single JSON object only. Never use markdown fences."` (current literal at `anthropic.py:108`) | `judges/base.py` | F1, F6 |
| `JUDGE_TEMPERATURE` | `0` | `judges/base.py` | F1 |
| `DEFAULT_JUDGE_MAX_TOKENS` | `256` | `judges/base.py` | F1 (preflight/eval parity) |
| `RENDER_RULES_VERSION` | `"1"` | `rubrics/base.py` | F1, F6 |
| `INVARIANCE_MODEL_VERSION` | `"1"` | `judges/base.py` | F6 |
| SQLite table name | `judgments_v2` (was `judgments`) | `judges/cache.py` | F1 migration |

---

# Item F5 — Content-anchor Generation identity

## 1. Objective
Restore **INV-DECIDE** (§5) and the well-definedness of Domain/Measurement identity (§4). `scores()` uses `Generation.id` as the Subject's identity, so `Generation.id` MUST **refine** the Generation-resident subset of the Subject `S` (*id-equal ⟹ S-equal*), which requires every Generation-resident `S` field to be encoded **directly**. Today `Generation.id = hash(prompt_id, config, condition, seed)` omits `text`, `target_concept`, and `language`, and carries `prompt` only via `prompt_id` — a non-`S` identifier that is only a *conditional* surrogate for `prompt` (the generic adapter and direct construction admit arbitrary `(prompt, prompt_id)` pairs). Both defects let distinct Subjects collide and merge in `scores()`.

## 2. Scope
- **Changes:** `models.py` — `Generation.validate_and_identify` id payload only.
- **Affected (tests/fixtures only):** `tests/conftest.py`, `tests/test_models.py`, any fixture asserting a literal generation id.
- **MUST remain untouched:** every non-test module; **`Rubric` in particular** — `aliases` stays where it is (see §3).

## 3. Design changes
- In `Generation.validate_and_identify` (`models.py:79-94`), extend the dict passed to `stable_hash` so the id payload is `{prompt_id, config, condition, seed, text, prompt, target_concept, language}`. Concretely, **add `"text": self.text`, `"prompt": self.prompt`, `"target_concept": self.target_concept`, and `"language": self.language`.** No new types, no signature change. Length unchanged (24).
- **Which fields belong in `Generation.id`, and why:** the Subject `S = (text, prompt, target_concept, language, aliases)` (Constitution §2.3). Four of the five are *Generation-resident* — `text`, `prompt`, `target_concept`, `language` — and `Generation.id` is the value `scores()` uses to identify the Subject, so all four MUST be encoded **directly**, as fields of `S`.
- **Why `prompt` is added directly, not left to `prompt_id`:** `prompt_id` is a provenance identifier, **not** an `S` field, and is only a *conditional* surrogate for `prompt` — the steering adapter sets `prompt_id = hash(prompt, experiment)` (`ingest/steering_json.py:67`), but the generic adapter (`Generation.model_validate`) and direct construction admit arbitrary `(prompt, prompt_id)` pairs. Relying on `prompt_id` to carry `prompt` therefore fails *id-equal ⟹ S-equal*: two generations with different `prompt` but equal `prompt_id` (and equal remaining fields) would collide. Encoding `prompt` itself makes `Generation.id` a refinement of `S` unconditionally. `prompt_id` may remain in the payload as a provenance coordinate — it only makes the id finer than `S`, which is sound (it never merges distinct Subjects) — but it is no longer the carrier of the `prompt` dimension.
- **Why `aliases` is NOT in `Generation.id`:** `aliases` is the *Rubric-resident* component of `S` (`rubric.aliases`), not a `Generation` field — it cannot and must not be placed in `Generation.id`. Per the Constitution §2.3 coordinate–object note, a coordinate's identity is computed over all its fields wherever they reside; the alias component of `S` enters identity through the Instrument (`rubric.aliases`) and the F1 execution key (`execution_cache_key` renders `sorted(rubric.aliases)`), never through `Generation.id`. `Generation.id` is thus the identity of the *Generation-resident subset of `S`*; the full Subject identity is composed at judging time (render / cache key), not stored as one object.

## 4. Dependency graph
Prerequisites: none. ↓ F5. ↓ Unlocks: nothing structurally (sequenced first so fixtures regenerate once).

## 5. Migration strategy
- **run.json:** none. Stored non-empty `id` is not recomputed on load (`models.py:83` guards `if not self.id`), so old runs keep their old ids and remain internally consistent; new runs get the fuller content-anchored id.
- **cache:** none. `Generation.id` is **not** part of the F1 cache key (which is over the rendered prompt + instrument/method fingerprints), so this change does not invalidate the cache.

## 6. Test specification
- **Before (fail):** property tests — two `Generation`s equal on every field except (1) `text`, (2) `prompt` **with `prompt_id` held equal** (the surrogate-collision case), (3) `target_concept`, or (4) `language` respectively have different `.id`.
- **After (pass):** those four; plus invariant — *`Generation.id` refines the Generation-resident Subject: id-equal ⟹ equal on `text`, `prompt`, `target_concept`, `language`*; plus *changing only `rubric.aliases` does NOT change any `Generation.id`* (aliases are not a Generation field).

## 7. Risks
- Fixtures with literal ids break (expected). Migration hazard: none (ids persisted; cache untouched). Performance: negligible (two extra fields hashed).

## 8. Acceptance criteria
- INV-DECIDE conformant for the Subject: `Generation.id` encodes the full Generation-resident subset of `S` — `{text, prompt, target_concept, language}` — **directly** (not `prompt` via `prompt_id`), so *id-equal ⟹ S-equal* holds for any `(prompt, prompt_id)` pairing; `aliases` is carried in identity via the Instrument / F1 key. Finding **F5 disappears**. (Encoding `prompt` via `prompt_id`, or adding `text` alone, is insufficient.)

---

# Item F3 — Typed `experiment` dimension

## 1. Objective
Restore **INV-TYPED** (§5). Fixes audit F3 and F8.

## 2. Scope
- **Changes:** `models.py` (field + promotion validator + `scores()` read site), `ingest/steering_json.py`, `ingest/generic.py`, regenerate `docs/generation.schema.json`.
- **Affected (unchanged logic):** `metrics/derived.py`, `report/html.py:460-463` — read a column named `experiment` produced by `scores()`; the column name is preserved, so **not edited**.
- **MUST remain untouched:** derived.py, html.py, all metric grouping code.

## 3. Design changes
- Add `experiment: str = "default"` to `Generation`.
- Add `model_validator(mode="after")`: if `self.experiment == "default"` and `metadata` has `"experiment"`, set `self.experiment = self.metadata["experiment"]` (back-compat promotion).
- `EvalRun.scores` (`models.py:269`): change `generation.metadata.get("experiment","unknown")` → `generation.experiment`.
- `steering_json.add()` (`ingest/steering_json.py:80-97`): pass `experiment=experiment`; remove `"experiment"` from the `metadata` dict. Keep `prompt_id` hashing `{"prompt","experiment"}`.
- generic adapter: unspecified `experiment` defaults to `"default"` (fixes F8).

## 4. Dependency graph
Prerequisites: F5 (same file). ↓ F3. ↓ Unlocks: nothing.

## 5. Migration strategy
- **run.json:** additive; promotion validator recovers `experiment` from old `metadata` on load. Regenerate `generation.schema.json` via `write_schema`.

## 6. Test specification
- **Before (fail):** `scores()` reflects `Generation.experiment` for a gen with the typed field set but metadata lacking it.
- **After (pass):** that; plus metadata-only experiment is promoted; generic default is `"default"`; frontier ablation-separation driven by the typed column.

## 7. Risks
- None if column name preserved. Legitimate `experiment="default"` in metadata is indistinguishable from unset (acceptable).

## 8. Acceptance criteria
- INV-TYPED conformant. Findings **F3, F8 disappear**.

---

# Item F9 — Forbid untyped fields on `Generation`

## 1. Objective
Close the latent **INV-NOHIDE / §7.5** risk from `extra="allow"`.

## 2. Scope
- **Changes:** `models.py` (`Generation.model_config`), `ingest/generic.py` (route unknown keys into `metadata`).
- **MUST remain untouched:** steering adapter (already routes `source_metadata` into `metadata`).

## 3. Design changes
- `Generation.model_config`: `extra="allow"` (`models.py:65`) → `extra="forbid"`.
- `generic.load_generic` (`ingest/generic.py:47-50`): before validating, move any key not in the known field set into a nested `metadata`. Known set: `{id, text, prompt, prompt_id, condition, model_name, language, target_concept, steering_config, seed, metadata, experiment}`.

## 4. Dependency graph
Prerequisites: F3 (adds `experiment` to the known set). ↓ F9. ↓ Unlocks: nothing.

## 5. Migration strategy
- Old runs whose generations carried extra top-level fields now fail strict validation (acceptable; route to metadata). No format bump.

## 6. Test specification
- **Before (fail):** a generic record with unknown key `foo` places `foo` under `metadata`.
- **After (pass):** that; plus constructing `Generation` with an unknown kwarg raises `ValidationError`.

## 7. Risks
- Strict inputs may reject malformed data (intended). Performance: none.

## 8. Acceptance criteria
- §7.5 latent risk closed; INV-NOHIDE hardened at the model boundary.

---

# Item F2 — Method snapshot pinning + fail-closed

## 1. Objective
Restore **THM3.C** (snapshot obligation) and **THM3.D** (fail-closed), grounded in **EA3**.

## 2. Scope
- **Changes:** `judges/cost.py` (`is_snapshot`), `cli.py` (`eval` guard + `--allow-alias` + record snapshot in manifest).
- **MUST remain untouched:** cache.py, metrics, validation, models (manifest field added in F6).

## 3. Design changes
- New pure function `is_snapshot(model_name) -> bool`: True iff `model_name` ends in `-\d{8}` **or** equals `"mock-deterministic-v1"`. No network resolution — Lodestar refuses aliases, it does not auto-resolve them.
- New `eval_command` option `--allow-alias` (bool, default `False`).
- In `eval_command`, before building the judge: if `judge` is not `mock` and `not is_snapshot(judge)` and `not allow_alias`, raise `typer.BadParameter` on `--judge`.
- Record the resolved `judge` string into `manifest_payload` (F6 adds the dedicated `judge_snapshot` field).

## 4. Dependency graph
Prerequisites: none. ↓ F2. ↓ Unlocks: F1 (keys built over pinned methods), F6 (records the snapshot).

## 5. Migration strategy
- No persistent change. Behavioral: `eval` refuses bare aliases unless overridden.

## 6. Test specification
- **Before (fail):** `is_snapshot("claude-sonnet-4-5")` False; `is_snapshot("claude-sonnet-4-5-20250929")` True.
- **After (pass):** those; plus `eval` with an alias judge and no `--allow-alias` exits with a parameter error; `--judge mock` unaffected.

## 7. Risks
- Scripts passing bare aliases now error (intended; `--allow-alias` escape hatch).

## 8. Acceptance criteria
- THM3.C/D conformant at the entry point. Finding **F2 disappears** (provenance half completes in F6).

---

# Item F1 — Execution-identity cache key (BLOCKER; absorbs F4)

## 1. Objective
Restore **INV-NOHIDE** (§5), **THM1/THM3** (§6), and **INV-LEVER** (F4). The cache key MUST encode `(S,C,I,M,T)`.

## 2. Scope
- **New file:** `judges/identity.py`.
- **Changes:** `judges/base.py` (constants), `rubrics/base.py` (`render_rubric` alias-sort + `RENDER_RULES_VERSION`), `judges/cache.py` (`cache_key` signature, `get/put/contains/count_hits` key-based, table rename), `judges/anthropic.py`, `judges/mock.py` (compute key via shared helper; use `JUDGE_SYSTEM_PROMPT`), `cli.py` (`count_hits` call sites build keys).
- **MUST remain untouched:** models.py, metrics/*, validation/*, report/*, ingest/*, cost.py.

## 3. Design changes
- **Constants:** add the four `JUDGE_*` constants to `judges/base.py`; add `RENDER_RULES_VERSION` to `rubrics/base.py`.
- **`render_rubric`** (`rubrics/base.py:21-28`): render `aliases=sorted(rubric.aliases)` (S is a set; canonicalize order).
- **New helpers in `judges/identity.py`** (single source of truth, imported by both judges *and* cli):
  - `instrument_id(rubric, *, system_prompt, render_rules_version) -> str` = `stable_hash({"template": rubric.prompt_template, "schema": rubric.output_schema, "system": system_prompt, "render_rules": render_rules_version})`.
  - `method_fingerprint(model_name, *, max_tokens, temperature) -> str` = `stable_hash({"model": model_name, "max_tokens": max_tokens, "temperature": temperature})`.
  - `execution_cache_key(gen, rubric, *, model_name, system_prompt, max_tokens, temperature, repeat_index) -> str`: computes `render_rubric(rubric, gen)`, `instrument_id(...)`, `method_fingerprint(...)`, then calls `cache_key(...)`.
- **`cache_key`** (`judges/cache.py:13-19`) → `cache_key(rendered_prompt, criterion_name, criterion_version, instrument_id, method_fingerprint, repeat_index) -> str`; body = sha256 of the `‖`-joined parts. **cache.py imports nothing new.**
- **`JudgeCache` methods key-based:** `get(key: str, generation: Generation)` (generation only to re-stamp `generation_id`, preserving INV-RESTAMP at `cache.py:68-76`); `put(key: str, judgment)`; `contains(key: str)`; `count_hits(keys: list[str]) -> int`.
- **Callers:** `AnthropicJudge._judge` and `MockJudge._judge` compute `key = execution_cache_key(gen, rubric, model_name=self.model_name, system_prompt=JUDGE_SYSTEM_PROMPT, max_tokens=<self.max_tokens or DEFAULT_JUDGE_MAX_TOKENS>, temperature=JUDGE_TEMPERATURE, repeat_index=repeat_index)` before `cache.get(key, gen)`; same `key` for `put`. Mock passes `model_name="mock-deterministic-v1"`, `max_tokens=DEFAULT_JUDGE_MAX_TOKENS`.
- **`AnthropicJudge`** references `JUDGE_SYSTEM_PROMPT` instead of the hardcoded literal (`anthropic.py:108`).
- **cli `estimate`/`eval`** (`cli.py:105-111,158`): build `keys` via `execution_cache_key` for each `(gen, rubric, repeat)` with `model_name=judge_name`, `system_prompt=JUDGE_SYSTEM_PROMPT`, `max_tokens=DEFAULT_JUDGE_MAX_TOKENS`, `temperature=JUDGE_TEMPERATURE`; call `cache.count_hits(keys)`.

## 4. Dependency graph
Prerequisites: **F2** (methods pinned before keys are built over them). ↓ F1 (the blocker). ↓ Unlocks: **F6** (reuses `instrument_id`, `INVARIANCE_MODEL_VERSION`).

## 5. Migration strategy
- **Cache (breaking):** rename table `judgments` → `judgments_v2` in `initialize/get/put/contains`. Old rows left in place (dead), never read → upgrade is an automatic cold start; existing `cache.sqlite` not deleted and does not error. Document in CHANGELOG that the first post-F1 run recomputes.
- **run.json / manifests:** unaffected.

## 6. Test specification (prefer invariant/property tests)
- **Before (fail) — soundness regressions:**
  1. Same `text`, different `target_concept` → different key.
  2. Same `text`, different `prompt` → different key.
  3. `literal_mention` with different alias sets → different key.
  4. Different `output_schema` (same template) → different key.
  5. Different `system_prompt` → different key.
  6. Different `max_tokens` → different key.
  7. End-to-end: two shared-cache judgments differing only in `target_concept` do not serve each other's stored answer.
- **After (also pass) — tightness/canonicalization:**
  8. Alias reorder → identical key.
  9. Different `repeat_index` → different key; identical coordinates → identical key.
  10. Round-trip: `get(key)` returns the stored judgment only for an execution-identical query, with `cached=True` and re-stamped `generation_id`.

## 7. Risks
- **Regression:** callers of old `cache_key`/`JudgeCache` signatures break — all in-repo (two judges, cli), enumerated above.
- **Invariant hazard:** a future judge computing keys without `execution_cache_key` diverges — mitigated by the single shared helper (make it the only public key path).
- **Migration hazard:** warm-cache users lose reuse once (cold start); `eval --budget` may now predict full cost and refuse — document.
- **Performance:** `render` now runs on cache hits and per preflight probe. Acceptable at current scale; **do not** add a template-compile cache in this commit (out of scope).

## 8. Acceptance criteria
- INV-NOHIDE, THM1, THM3, INV-LEVER conformant. Findings **F1 and F4 disappear**. Blocker cleared.

---

# Item F7 — Honor the declared determinacy flag

## 1. Objective
Restore full **INV-DETTYPE** (§5/§7.1): drive the deterministic path from `Rubric.deterministic`, not a name literal.

## 2. Scope
- **Changes:** `judges/anthropic.py` (`_judge`, two conditionals).
- **MUST remain untouched:** models.py, rubrics, mock, cache.

## 3. Design changes
- Replace `if rubric.name == "literal_mention":` (`anthropic.py:169`) with `if rubric.deterministic:`.
- Replace the two `rubric.name == "literal_mention"` guards in the metadata block (`anthropic.py:189-194`) with `rubric.deterministic`.
- The regex count over `(gen.target_concept, *rubric.aliases)` remains the deterministic implementation.

## 4. Dependency graph
Prerequisites: none (co-located with F1 edits to `_judge`). ↓ Unlocks: nothing.

## 5. Migration strategy
- None (behavior identical for `literal_mention`; generalizes to future deterministic rubrics).

## 6. Test specification
- **Before (fail):** a rubric copy with `deterministic=True` and a different `name` receives the deterministic path.
- **After (pass):** that; plus existing `literal_mention` behavior unchanged.

## 7. Risks
- None, provided only `literal_mention` currently carries `deterministic=True` (verified).

## 8. Acceptance criteria
- INV-DETTYPE fully conformant. Finding **F7 disappears**.

---

# Item F6 — Provenance completeness

## 1. Objective
Restore **INV-TRACE / §7.6 / THM5**: each Judgment records Instrument identity, invariance-model version, and resolved Method snapshot; the manifest records the run-level snapshot and invariance version.

## 2. Scope
- **Changes:** `models.py` (`Judgment` two fields, `RunManifest` two fields), `judges/anthropic.py`, `judges/mock.py` (populate), `cli.py` (populate manifest).
- **MUST remain untouched:** cache.py, metrics, validation, report.

## 3. Design changes
- Add to `Judgment` (`models.py:151-163`): `instrument_id: str = ""`, `invariance_version: str = ""`. **Do not** add them to the `Judgment.id` payload (`models.py:165-178`) — identity unchanged; these are record fields.
- Add to `RunManifest` (`models.py:181-193`): `judge_snapshot: str = ""`, `invariance_version: str = ""`.
- In both judges' `_judge`, when constructing the `Judgment`, set `instrument_id=identity.instrument_id(rubric, system_prompt=JUDGE_SYSTEM_PROMPT, render_rules_version=RENDER_RULES_VERSION)` and `invariance_version=INVARIANCE_MODEL_VERSION` (reuses the F1 helper).
- In `eval_command`, set `RunManifest.judge_snapshot = judge_model` (resolved/guarded by F2) and `invariance_version = INVARIANCE_MODEL_VERSION`.

## 4. Dependency graph
Prerequisites: **F1** (provides `instrument_id`, `INVARIANCE_MODEL_VERSION`) and **F2** (guaranteed snapshot). ↓ F6 (last). ↓ Unlocks: full compliance.

## 5. Migration strategy
- **run.json / manifest:** additive fields with defaults → old runs load with empty provenance fields; new runs complete.

## 6. Test specification
- **Before (fail):** every Judgment from `judge_batch` has non-empty `instrument_id` and `invariance_version`; manifest has non-empty `judge_snapshot` and `invariance_version`.
- **After (pass):** that; plus two Judgments with different instruments have different `instrument_id`; same instrument shares it.

## 7. Risks
- Additive (no regression). Cached judgments carry the `instrument_id` from first computation; reuse only occurs for execution-identical (hence instrument-identical) queries — consistent with F1.

## 8. Acceptance criteria
- INV-TRACE, §7.6, THM5 conformant. Finding **F6 disappears**; F2 provenance half completes. **All findings resolved.**

---

# Implementation Order & Rationale

**Phase A — Data-model foundation (files: models.py, ingest/*):** F5 → F3 → F9.
*Why first:* all touch `Generation`; consecutive edits regenerate fixtures/schema **once** and establish the typed field set F9's forbid-list depends on. None touches the judge/cache cluster, so A and B rarely collide.

**Phase B — Method & identity spine (files: judges/*, cli.py, rubrics/base.py):** F2 → F1 → F7 → F6.
- **F2 before F1** so keys are only built over pinned snapshots (no window keyed on an unpinnable method).
- **F1 before F6/F7** because F6 reuses F1's `instrument_id`/`INVARIANCE_MODEL_VERSION`, and F7 edits the same `_judge` body (co-locate to avoid a second pass).
- **F6 last** — pure provenance addition depending on F2 (snapshot) and F1 (instrument id).

**Why A before B:** F1 renders generations whose identity (F5) and typed fields (F3) should be final first, so key logic is never revisited. No invariant is newly violated at any point; each phase fixes or is additive. The Blocker (F1) clears mid-sequence; F6 only upgrades Major→Conformant thereafter.

---

# Commit Plan

### Commit 1 — F5: content-anchor Generation.id
- **Purpose:** INV-DECIDE. **Files:** models.py; conftest.py, test_models.py, fixtures. **Tests:** id-distinguishes-text/prompt(same-prompt_id)/target_concept/language; id-refines-Subject; aliases-do-not-change-generation-id. **Audit improvement:** F5 resolved.

### Commit 2 — F3: typed `experiment` (+F8)
- **Purpose:** INV-TYPED. **Files:** models.py, ingest/steering_json.py, ingest/generic.py, docs/generation.schema.json. **Tests:** scores-reads-typed-field; metadata-promotion; generic-default; ablation-separation. **Audit improvement:** F3, F8 resolved.

### Commit 3 — F9: forbid untyped Generation fields
- **Purpose:** INV-NOHIDE hardening. **Files:** models.py, ingest/generic.py; test_ingest.py. **Tests:** unknown-key-routed-to-metadata; unknown-kwarg-rejected. **Audit improvement:** §7.5 latent risk closed.

### Commit 4 — F2: snapshot pinning + fail-closed
- **Purpose:** THM3.C, THM3.D. **Files:** judges/cost.py, cli.py; test_cost.py (or test_snapshot.py), test_cli.py. **Tests:** is_snapshot truth table; eval-rejects-alias; mock-unaffected. **Audit improvement:** F2 (entry-point half) resolved.

### Commit 5 — F1: execution-identity cache key (BLOCKER; +F4)
- **Purpose:** INV-NOHIDE, THM1, THM3, INV-LEVER. **Files:** NEW judges/identity.py; judges/base.py, rubrics/base.py, judges/cache.py, judges/anthropic.py, judges/mock.py, cli.py; test_cache.py + NEW test_execution_identity.py. **Tests:** the 10 key/round-trip properties. **Audit improvement:** F1, F4 resolved — **Blocker cleared**.

### Commit 6 — F7: honor determinacy flag
- **Purpose:** INV-DETTYPE. **Files:** judges/anthropic.py; test_anthropic_judge.py. **Tests:** deterministic-by-flag-not-name; literal_mention unchanged. **Audit improvement:** F7 resolved.

### Commit 7 — F6: provenance completeness
- **Purpose:** INV-TRACE, §7.6, THM5. **Files:** models.py, judges/anthropic.py, judges/mock.py, cli.py; test_models.py, test_validation.py. **Tests:** every-judgment-has-instrument-id-and-invariance-version; manifest-has-snapshot; instrument-id-discriminates. **Audit improvement:** F6 resolved, F2 provenance half completes.

**End state after Commit 7:** all findings (F1–F9) resolved; every invariant Conformant; release recommendation → **Fully Compliant**. Total effort **~4–6 engineer-days** (Commit 5 ≈ 40%; Commits 1–4, 6 ≤ half a day each; Commit 7 ≈ 1 day).
