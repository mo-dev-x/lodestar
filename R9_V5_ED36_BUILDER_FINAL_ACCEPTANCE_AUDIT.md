# R9-V5-ED36-BUILDER-FINAL-ACCEPTANCE — Independent Audit

**Auditor:** Interlab persistent auditor
**Date:** 2026-08-04
**Audit commit:** `82b028e160e62abe6012b60965944b77413817dd` ("R9-V4: close four builder-repair gaps (F1-F4)")
**Parent:** `1ed3ad98bad03e084a7237263ea7c9d0b69b3a4d` (my R9-V3 audit commit — clean single-commit delta)
**Worktree:** `D:\qwen-sae-interp-r9-v5-audit-82b028e` (new, detached, `core.autocrlf=false`; removed at end)

## Verdict: **Accepted for exact 82b028e**

All four V3 findings are closed and independently re-derived. No regressions. One advisory (non-blocking) hardening item recorded below.

---

## Deliverable 0 — R9-V3 verdict and F1–F4, for the verification log

**R9-V3 verdict on `1ed3ad9`: REJECT**, on two acceptance criteria — Target 2 ("strictness not traded for coverage") and Target 3 ("deterministic negative test per stop condition"). Both additive fixes.

Certified adequate at V3 and marked do-not-touch: target/build-host identity, SOABI and ordered compatibility tags in `derived_wheel.builder` (widened 4→8 fields, all required); SOABI from `sysconfig.get_config_var("SOABI")` with hard failure if unresolvable (`:234`); `compatible_tags` from `packaging_tags.sys_tags()` compared with list `!=` so order is enforced (`:3526`); bound to manifest target by exact field equality (`:3519-3523`).

- **F1 — BLOCKING.** Eight of nine R9-D4 §4 stop conditions had no negative test. Only `undeclared build requirement` was covered (`test_environment_bundle_builder.py:740`). Exact-string search across `tests/*.py` returned zero hits for `direct URL`, `extras`, `does not admit approved version`, `duplicate build requirement`, `build backend mismatch`, `backend-path`, `missing backend provider`, `no approved build backend contract`. Enforcement itself was correct — all nine branches verified live. Coverage gap, not correctness defect.
- **F2 — MAJOR.** The isolation proof had no floor. `python_connection_attempt` and `native_connection_attempt` were declared bare `{"type":"object"}`; `{}` validated. Code was asymmetric: `python_attempt.get("succeeded") is not False` rejected a missing key, `native_attempt.get("returncode") == 0` did not. Verified `{}` and `{"argv":[…]}` both passed; only `returncode: 0` was rejected.
- **F3 — MODERATE.** `inventory_entry.sha256`/`size_bytes` optional in schema (`required: ["path","type"]`), so a `type:"file"` entry with no `sha256` validated. Mitigated by code at `:4246-4248`. The aggregate `extraction_inventory_sha256` did not compensate — it hashes whatever is present, binding paths but not contents.
- **F4 — MINOR.** `derived_tool_record.backend_path` optional; code also tolerated omission (`optional={"backend_path"}` `:4268`, `.get("backend_path", [])` `:4278`). Non-empty backend-path was enforced at build time. Shared `frontend`/`backend` def was the likely design reason.

---

## Item 1 — Scope: exactly seven paths ✅

`git diff --name-only 4bf0fd8 82b028e` → **7**, matching the authorized set exactly. No eighth path.

```
interplab/core/environment_bundle.py
schemas/environment_acquisition_manifest/v1.schema.json
slurm/environment_bundle.tooling.lock.json
slurm/setup_env.sh
tests/test_environment_bundle.py
tests/test_environment_bundle_builder.py
tests/test_slurm_setup_env.py
```

V4 delta (`1ed3ad9..82b028e`) touched 3: builder, acquisition schema, builder test module.

### Governing hashes at `82b028e` (canonical git blob, sha256[:16])

| Path | Hash |
|---|---|
| `interplab/core/environment_bundle.py` | `9b0d0f96203291e8` |
| `schemas/environment_acquisition_manifest/v1.schema.json` | `b69e4dc83bbc9d4a` |
| `slurm/environment_bundle.tooling.lock.json` | `4df4f6e701a7562b` |
| `slurm/setup_env.sh` | `cb0aecf3d9fd6684` |
| `tests/test_environment_bundle.py` | `bc4b3076eb0d2eac` |
| `tests/test_environment_bundle_builder.py` | `5b835ff2158af614` |
| `tests/test_slurm_setup_env.py` | `a81d12f31344bce0` |

## Item 2 — F1: nine negatives, each for its own reason ✅

18 new tests added; nine target `_validate_build_system_contract`, each asserting a **branch-unique** message. They drive the real builder path via `_build_derived_wheel_with_pyproject`, not a direct unit call.

Independent attribution matrix (direct call, so no outer guards can interfere). **Baseline control accepted**, proving each fixture is otherwise valid and the raise is attributable to its single mutation:

```
baseline clean build-system            -> ACCEPTED (fixtures otherwise valid)
direct URL                -> must not use a direct URL
VCS ref                   -> must not use a direct URL
path ref                  -> must not use a direct URL
extras                    -> must not use extras for 'hatchling'
incompatible specifier    -> does not admit approved version '1.0'
duplicate                 -> declares duplicate build requirement 'hatchling'
backend mismatch          -> expected 'hatchling.build', got 'setuptools.build_meta'
non-empty backend-path    -> backend-path mismatch: expected [], got ['src']
missing backend provider  -> requires is missing backend provider 'hatchling'
```

No shared earlier guard fires. **PASS.**

## Item 3 — F2: both layers, both attempts ✅

Fix at `environment_bundle.py:3694-3696` (`native_returncode is None or native_returncode == 0`) plus schema `required: ["succeeded"]` / `required: ["returncode"]` with `additionalProperties: false`.

| Case | `_validate_derived_wheels` | Schema |
|---|---|---|
| baseline valid (control) | ADMITTED | ADMITTED |
| `python_connection_attempt = {}` | rejected | rejected |
| `native_connection_attempt = {}` | rejected | rejected |
| native missing `returncode` | rejected | rejected |
| python missing `succeeded` | rejected | rejected |

**PASS.**

### Item 3b — ruling on the residual asymmetry: **benign redundancy, not a fail-open**

`native {succeeded: true, returncode: 1}` → **code layer ADMITTED**, schema layer rejected. `native {succeeded: true, returncode: 0}` → rejected at both.

Ruling rests on four verified facts:

1. **`succeeded` is not in the native evidence vocabulary.** The builder emits exactly `{argv, returncode, stdout, stderr}` (`:1233-1237`) — confirmed empirically in my container run, whose native payload carried no `succeeded` key.
2. **Nothing reads native `succeeded`.** The sole reader of `native_connection_attempt` is `:3693-3696`, which reads `returncode`.
3. **The safety-relevant assertion is still enforced.** `returncode: 1` is a genuine probe failure — the correct, safe conclusion. The actually-unsafe states (`returncode: 0`, missing, `None`) remain rejected.
4. **No unsafe manifest is admitted.** A stray `succeeded` cannot flip any decision; it is inert noise.

There is a real but narrow hardening gap behind it: `_validate_derived_entry_shape` applies only `_require_mapping` to the connection attempts (`:4313-4314`), no exact-key check, so extra keys ride along at runtime. This matters because **the acquisition schema is not applied in any production path** — `environment_bundle.py` never imports the schema registry, and no job validates the acquisition manifest against it; the schema binds the test suite and external consumers only. The runtime gate is the Python validators alone.

**Advisory (non-blocking):** add `_require_exact_keys` on both connection attempts in `_validate_derived_entry_shape` to bring the runtime gate level with the schema. This does not affect acceptance of `82b028e`.

## Item 4 — F3: `if`/`then` fires, non-file unaffected ✅

Schema now carries `"if": {"properties": {"type": {"const": "file"}}}, "then": {"required": ["path","type","size_bytes","sha256"]}`. Well-formed: `type` is in the outer `required`, so the `if` cannot pass vacuously.

```
file WITHOUT sha256/size_bytes  -> rejected: 'size_bytes' is a required property
file WITHOUT sha256 only        -> rejected: 'sha256' is a required property
file WITH both                  -> ADMITTED
directory WITHOUT sha256/size   -> ADMITTED
directory WITH sha256           -> ADMITTED
```

**PASS** — fires for `file`, non-file types unaffected.

## Item 5 — F4: frontend/backend split ✅

New `$defs/derived_backend_record` (requires `backend_path`, `maxItems: 0`); `derived_tool_record` no longer carries `backend_path` at all; `derived_wheel.backend` re-pointed to the new def.

Verified against `_validate_derived_entry_shape` (the real F4 gate — note `_validate_derived_wheels` does not call it; it runs at `:2220` and `:2788`):

| Case | Code | Schema |
|---|---|---|
| baseline (control) | ADMITTED | ADMITTED |
| backend without `backend_path` | rejected: *missing required field(s): backend_path* | rejected |
| backend `["src"]` | rejected: *must be an empty list* | rejected |
| backend `[]` | ADMITTED | ADMITTED |
| backend `"src"` (not a list) | rejected: *must be an empty list* | — |
| frontend with `backend_path` | rejected: *unexpected field(s): backend_path* | rejected |

**PASS.** Note `required=required_keys | {"backend_path"} if field == "backend" else required_keys` (`:4266`) is unparenthesized; Python precedence binds `|` tighter than the conditional, so it is correct — proven behaviourally above. Parenthesising would improve readability.

## Item 6 — Real positive Linux namespace evidence ✅

Host: Docker **28.5.1**, context **desktop-linux**, local image `python:3.11-slim-bookworm` `sha256:b18992999dbe…`. Run offline: `--network none --pull never`. No pull, no network, no Tamia.

`test_real_linux_namespace_isolation_evidence_uses_unshare_and_no_network_in_docker` — **PASSED** (2.25s).

Independently replicated outside pytest; real kernel facts at this commit:

```
parent_namespace          = net:[4026532604]
child_namespace           = net:[4026532701]   (netns CHANGED)
descendant_namespace      = net:[4026532701]   (descendant inherits child)
mechanism                 = linux-unshare-clone_newnet
interfaces                = ['lo']
non-header routes         = []
socket fds retained       = []
python_connection_attempt = {'succeeded': False, 'error': 'RuntimeError: network access is forbidden …'}
native_connection_attempt = {'argv': ['getent','hosts','example.com'], 'returncode': 2, 'stdout': '', 'stderr': ''}
```

The native payload keys are exactly the four the schema permits — no `succeeded` — corroborating the Item 3b ruling. (My replication used a stub `build.py` and so produced no wheel; the real test asserts the wheel and passed.)

## Item 7 — Regressions ✅

| Command | Result | Log |
|---|---|---|
| `python -m pytest -p no:cacheprovider -q -rs` | **770 passed, 1 skipped, 3 deselected**, exit 0, 301.58s | `scratchpad/v5_full.txt` |
| `uv run ruff check interplab tests scripts/*.py data/concepts/*.py` (exact CI, `.github/workflows/ci.yml:28`) | **All checks passed** | inline |
| `uv lock --check` | **Pass** — 196 packages | inline |
| `bash -n` setup_env + 5 launchers | **All OK** | inline |
| `git diff --check 4bf0fd8 82b028e` | **Clean** | inline |

770 = 752 (V3 baseline) + 18 new tests — exact, no silent loss. The single skip is `test_build_no_network_child_source_blocks_socket_dns_and_python_subprocess` (`:1381`), Linux-gated; its substance runs inside the Docker test. The 3 deselected remain the pre-existing `@pytest.mark.nightly` rows.

## Item 8 — Builder logic byte-unchanged ✅

Function-level sha256 across `1ed3ad9 → 82b028e`:

| Unit | Result |
|---|---|
| `_current_target_capture_fields` | **UNCHANGED** `fee1cc1d5c08a30c` |
| `current_target` | **UNCHANGED** `a64358f5f249eb5c` |
| `marker_environment_for_target` | **UNCHANGED** `25bf7ed173bd88d0` |
| `validate_target_capture_report` | **UNCHANGED** `748962f938eb2988` |
| `_validate_derived_wheels` | changed (F2 site only) |
| `_validate_derived_entry_shape` | changed (F4 site only) |

Within the two changed functions, the builder blocks themselves are byte-identical:

| Block | Result |
|---|---|
| builder cross-validation in `_validate_derived_wheels` | **UNCHANGED** `37d1e3419152854b` |
| builder shape gate in `_validate_derived_entry_shape` | **UNCHANGED** `cec269ddc0d4dfa3` |
| schema `derived_wheel.properties.builder` | **UNCHANGED** `e135248a0473e905` |

The V3-certified builder construction logic is untouched. The only movement is the three intended F2/F4 hunks.

## Constraint compliance

Read-only throughout. No commit, no push, no branch mutation, no external network, no Tamia, no bundle or venv construction. All probe scripts were written to scratchpad, never into the worktree. Every probe pinned `sys.path` to the audit worktree and asserted `__file__` — this matters because running a script by absolute path otherwise resolves `interplab` to the editable install in the stale main worktree.

**Start/end state identity:** 14 worktrees at start, **14 at end, same list**. `D:\qwen-sae-interp-r9-v5-audit-82b028e` created and removed; directory confirmed gone; `git worktree prune` run. Branch tip `r9-ed36-bundle-builder` = `82b028e160e62abe6012b60965944b77413817dd`, unmoved.

## Carried forward

- **R9-V1-PREP matrix still absent from the repository** (re-confirmed at V3 across all refs, filenames and content). Row-by-row certification remains blocked pending the Orchestrator supplying it.
- **Advisory:** exact-key check on connection attempts in `_validate_derived_entry_shape` (see Item 3b). Non-blocking.
- **Cosmetic:** parenthesise the ternary at `environment_bundle.py:4266`.
