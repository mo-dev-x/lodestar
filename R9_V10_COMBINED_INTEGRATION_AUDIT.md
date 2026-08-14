# R9-V10 — Combined Integration Audit (Major Milestone Gate)

**Auditor:** Interlab persistent auditor (fresh on this branch by design)
**Date:** 2026-08-05
**Candidate:** `a9a174f3bb8dc6dc343fef6158323dececb2c0a7`
**Last independently accepted:** `1aca37d` (R9-V6)
**Delta:** 3 commits — `70c6d25` (R9-C8) → `92a12f6` (R9-C9) → `a9a174f` (R9-C10); 4 files, **+827/−17** (matches the brief exactly)
**Worktree:** `D:\qwen-sae-interp-r9-v10-audit`, detached, `core.autocrlf=false`, removed and pruned at end

## Verdict: **Accepted for exact a9a174f**

All eight priority checks pass. One genuinely new observation is recorded as a non-blocking advisory; it is **pre-existing**, not introduced by this candidate.

### The seven blob hashes (computed independently, canonical LF blobs)

| Path | sha256 |
|---|---|
| `interplab/core/environment_bundle.py` | `37881566694791a9cb71661538e50c78a72e7036da0876ebf19eb44d80f9f3f6` |
| `schemas/environment_acquisition_manifest/v1.schema.json` | `f60fff8d031215ef544f43de9eb2a4b4a44568f663562781f124debeaf0c644b` |
| `slurm/environment_bundle.tooling.lock.json` | `4df4f6e701a7562b903ed21e70b2439e152b7cf99b2119b2c2cb981cf4507b0e` |
| `slurm/setup_env.sh` | `cb0aecf3d9fd6684258fbbe691ec0accb4c0f1b1244ab44f33dbaf297799386a` |
| `tests/test_environment_bundle.py` | `7dddb2ed6efce57afb5228787e861b8403a426b784aa06bbe47cb76ecdeab28f` |
| `tests/test_environment_bundle_builder.py` | `543491f58fbb9e798caee89f74198ac97a91d43f89ca8738139bc6507801e049` |
| `tests/test_slurm_setup_env.py` | `a81d12f31344bce0d0bf2cf87db440060e56cbccd19aac444c3f4fb5f7e4c35c` |

---

## Revision discipline

Cut my own detached worktree at `a9a174f`; asserted the repo root **in-source** in every probe (`assert "r9-v10-audit" in module.__file__` plus `len(lines) > 5000`), so a stale read aborts rather than producing numbers. Observed `environment_bundle.py` = **5148 lines** (stale main is 2279).

*Brief discrepancy, not a defect:* the brief states 5131 lines on the branch; the actual count at `a9a174f` is **5148**. The discriminating property (not-2279) holds decisively.

Every probe ran with `sys.path` pinned to the audit worktree. This matters: running a script by absolute path otherwise puts the script's own directory on `sys.path[0]` and resolves `interplab` to the editable install in stale main — the exact trap that has already misled three roles.

## 1. Scope and the four certified units — PASS

Cumulative `4bf0fd8..a9a174f` = **exactly seven paths**, matching the authorized set. **No eighth path.** Delta touches 4 files; per-commit: C8 tests-only, C9 = bundle + schema + tests, C10 = bundle + tests.

All four certified units re-derived at their **current** (shifted) coordinates:

| Unit | Location now | sha256[:16] | |
|---|---|---|---|
| `_current_target_capture_fields` | L233–247 | `fee1cc1d5c08a30c` | **UNCHANGED** |
| builder block in `_validate_derived_wheels` | L3554–3565 | `37d1e3419152854b` | **UNCHANGED** |
| builder block in `_validate_derived_entry_shape` | L4289–4299 | `cec269ddc0d4dfa3` | **UNCHANGED** |
| schema `$defs.derived_wheel.properties.builder` | schema object | `e135248a0473e905` | **UNCHANGED** |

## 2. Pre-activation isolation — PASS, **by execution**

Built a real `sys.meta_path` finder blocking the jsonschema closure (`jsonschema`, `jsonschema_specifications`, `referencing`, `rpds`, `_rpds`), purging any cached copies first. `packaging` deliberately **not** blocked.

A first attempt blocked at the *test module's* own module-level `_schema_registry` import (`tests/test_environment_bundle.py:19`) — a harness artifact, not the production path. Corrected by building fixtures first, then dropping the cached `interplab.core._schema_registry` so the lazy import must genuinely re-execute, then arming the block.

| Path | Result |
|---|---|
| preflight (`validate_bundle`) | **COMPLETED** under a live block |
| create-venv (`create_virtualenv`) | **COMPLETED** under a live block |
| `record_installed_environment` (**negative control**) | **BLOCKED-ON-JSONSCHEMA** |

The negative control is what makes this conclusive: the blocker was provably live at that moment, so the two completions are real isolation, not a no-op. Positive controls also confirmed `import jsonschema` and `import interplab.core._schema_registry` both raise while armed, and that importing `environment_bundle` leaves `jsonschema` out of `sys.modules`.

The lazy helper `_validate_acquisition_manifest_against_schema` (L2736) has **exactly two** call sites, both post-activation: `certification_environment_inputs` L869 and `record_installed_environment` L2627 (the brief's :862/:2601, line-shifted). Consistent with R9-A4.

*Out of scope as instructed:* `packaging` is imported at module level (L33–36); blocking it fails the bootstrap. Known R9-C1 item, not re-reported as new.

## 3. Anti-drift corpus — PASS, and it can fail

Three classes present and correctly framed:

- **Class 1 (valid)** — untouched fixture accepted by shape, semantics, and schema.
- **Class 2 (shape)** — 5 structural mutations rejected by **both**.
- **Class 3 (semantic-only)** — 3 cross-artifact mutations rejected by Python, **accepted by the schema, documented as EXPECTED**, with an explicit instruction not to "fix" it by tightening the schema. **No equivalence assertion anywhere** — the invariant is stated and implemented as directional, exactly per R9-A4.

**Mutation test** (the corpus must be falsifiable — perturbations written to scratchpad; the worktree was never modified):

| Perturbation | Corpus result | |
|---|---|---|
| control, unmutated | PASS | expected |
| **LOOSEN** `target.required` drops `os` | **FAIL** | detects loosening |
| **LOOSEN** `additionalProperties: true` | **FAIL** | detects loosening |
| control, unmutated (class 1) | PASS | expected |
| **TIGHTEN** bogus required key | **FAIL** | detects over-tightening |

The corpus detects drift in **both** directions and passes clean. It is not a test that cannot fail.

## 4. Schema ↔ validator key-set parity — PASS

Extracted all 26 `_require_exact_keys` call sites by AST and compared field-for-field with the schema objects. Every mappable pair matches exactly: top-level manifest, `target`, `generator` (incl. its four optionals), `artifact` (incl. optional `import_name`), `derived_wheel`, `builder`, `derived_isolation`, `derived_isolation_side`, `build_requirement_mapping`, `marker_environment`, `distribution_version`, `inventory_entry` (incl. optional `sha256`/`size_bytes`). The single `<dynamic>` site (L4303) is the frontend/backend conditional mapping to `derived_tool_record` / `derived_backend_record`.

**The tightening went to the schema; no validator was relaxed.** Confirmed three ways:

1. The schema diff is the *only* change: `python_connection_attempt.required` `["succeeded"]` → `["succeeded","error"]`; `native_connection_attempt.required` `["returncode"]` → `["argv","returncode","stdout","stderr"]`.
2. The delta contains **zero** changes to any `required=` / `optional=` / `_require_exact_keys` in Python.
3. `git log -S` shows the Python exact-key checks were added by **R9-C6 (1aca37d)** — the last accepted revision. That created a genuine mismatch; R9-C9 raised the schema to meet the already-stricter validator.

Both objects now have `required == properties` with `additionalProperties: false`, and the directional invariant (Python ⊇ schema) holds.

## 5. Rollback — PASS, including the fourth claim

`_rethrow_primary_with_cleanup` (L384) is correctly built: cleanup failures are collected, attached via `add_note`, and the **primary** error is always re-raised.

**Regressions against pre-fix code.** A first harness that relocated the package tree produced `FileNotFoundError: pyproject.toml` — environmental noise that could have been misread as regression failures. Discarded in favour of a precise function-level revert: the three C10-fixed functions were rebound in place from `1aca37d` via AST extraction, leaving `REPO_ROOT` and everything else intact.

| Test | vs pre-fix | Meaning |
|---|---|---|
| `..._extract_sdist_..._invalid_member` | **FAIL** | fix required |
| `..._extract_sdist_..._multiple_roots` | **FAIL** | fix required |
| `..._bootstrap_private_pip_...` | **FAIL** | fix required |
| `..._build_runtime_bundle_...` | **FAIL** | fix required |
| `..._build_derived_runtime_wheel_does_not_mask...` | **PASS** | **already safe — 4th claim** |
| `..._finalize_bundle_...` (R9-C8) | **PASS** | **reproduction was NEGATIVE, as stated** |

All four failures are the masking bug reproducing verbatim: `PermissionError: locked cleanup path` escaping in place of the primary error.

**The fourth claim, verified independently rather than accepted.** `_build_derived_runtime_wheel` (L1759–1971) contains three `try` blocks, all narrowly handling `subprocess.CalledProcessError`; each handler body extracts `detail` and raises — **no cleanup call in any handler**. There are **no `finally` blocks**. The only `_rollback_partial_path(unpack_root)` is L1966, the last statement before `return` — success path only. And `unpack_root = evidence_root / "src"` with `evidence_root = staging_dir / "evidence" / …` (L1772), so failure cleanup is the caller's: `build_runtime_bundle` rolls back `staging_path` through `_rethrow_primary_with_cleanup`. There is no error-path cleanup to mask anything and no leak. **Correctly skipped.**

## 6. TransformerLens coverage — PASS

The gate has three branches: forbidden `3.4.0`; version `!= 3.2.1`; and `require_exact_runtime` demanding exactly `[3.2.1]`.

- **Branch 2** — `4.0.0` cannot trip branch 1 and must trip branch 2; asserted on `"contains an unexpected transformer-lens version: ['4.0.0']"`.
- **Branch 3** — two `3.2.1` entries individually pass branches 1 and 2, so only branch 3 can fire; asserted on `"must contain exactly one transformer-lens==3.2.1 artifact"`.

Both are correctly isolated — each fixture can reach only its intended branch.

**Consumer-path negative — caught by a generic check, as expected.** The assertion is `runtime version mismatch for 'transformer-lens': expected 3.2.1, got 3.4.0`, which comes from L3401: `f"runtime version mismatch for {requirement.distribution!r}: expected {requirement.version}, got {entry['version']}"` — a fully parameterized template. TL appears only as substituted **data**; there is no TL-specific wording in the check.

Corroborated structurally: `_validate_runtime_manifest` (L3355–3423) never calls `_reject_transformer_lens_contamination` and contains **no** `transformer` literal anywhere in its body. All seven gate call sites are producer-side. Per R9-A5 this is the correct shape — the producer-side TL gate is fail-fast ergonomics, while the consumer boundary holds independently via generic version authorization. No control is discharged solely producer-side.

## 7. No validator weakened — PASS

Zero tests removed (`^-def test_` = 0), zero `assert`/`pytest.raises` lines removed, net **+17** tests in the two modules (90 → 107). Full suite green, so every pre-existing negative test still passes.

## 8. Regressions — PASS

| Check | Result |
|---|---|
| Full suite | **795 passed, 1 skipped, 3 deselected** — exit 0, 277.72s |
| Exact CI Ruff (`ci.yml:28`: `interplab tests scripts/*.py data/concepts/*.py`) | **All checks passed** |
| `uv lock --check` | **Pass** — 196 packages |
| `bash -n` ×6 (setup_env + 5 launchers) | **All OK** |
| `git diff --check 4bf0fd8 a9a174f` | **Clean** |

Matches the expected `795 / 1 / 3` exactly. The single skip is the Linux `/proc`-namespace test, now at `test_environment_bundle_builder.py:1657` (brief said :1381 — line-shifted); skipping on Windows is expected and was closed in-container at R9-V6.

## Advisory (NEW, non-blocking, pre-existing)

**The private-pip identity assertions at `environment_bundle.py:1749-1750` are not covered by any test.** Neutralising both (`private pip snapshot`, `retained original pip artifact`) while leaving every other `_assert_artifact_identity` call site intact produces **147 passed, 0 failed** — the suite cannot detect their removal.

**Pre-existing, not introduced here:** re-running the same mutation on top of the pre-fix function shapes yields exactly the four masking-regression failures and **no additional** ones, so the gap predates `a9a174f`.

Related and deliberate: R9-C10 narrowed *when* those assertions run. Pre-fix, a `finally` executed them on both success and failure paths; now they run on the success path only. That change is **correct and necessary** — you cannot both preserve a primary error and run a check that may itself raise — and it does not weaken the security outcome, because the failure path rolls back `private_root`, raises, and produces no consumable bundle. Recommend a positive test asserting the success-path identity checks still fire, so a future refactor cannot silently drop them.

## Out-of-scope items (not re-derived, as instructed)

Matrix rows 4, 6, 7, 9, 10, 13; V9-F1 torch authenticity (Architect, R9-A6); the `packaging` pre-activation question (observed at L33–36, R9-C1, confirmed still present, not re-reported as new); the consumer-only adversarial matrix (R9-C12). Nothing genuinely new was found in these areas.

## Worktree state

**Start: 15 records. End: 14 records.** The difference is fully accounted for and no live working tree was removed by me.

- I created `D:\qwen-sae-interp-r9-v10-audit`, used it read-only, then removed it — directory confirmed gone.
- `D:\qwen-sae-interp-r9-v9b2-1aca37d` appeared in the start listing but **its directory was already deleted before this audit began**; only a stale git admin record remained. The `git worktree prune` I was instructed to run cleared that stale record. Verified: the path is absent from disk, and every one of the 14 remaining records now points at a live directory.
- **Engineer 2's `D:\qwen-sae-interp-r9-repair` was not touched** and remains checked out at `a9a174f`.
- **Branch tip unmoved:** `r9-ed36-bundle-builder` = `a9a174f3bb8dc6dc343fef6158323dececb2c0a7`.

Read-only throughout: no commit, no push, no branch mutation, no writes into any worktree. All probes, mutated schemas, and pre-fix harnesses were written to scratchpad.
