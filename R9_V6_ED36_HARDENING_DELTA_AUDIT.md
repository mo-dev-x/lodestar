# R9-V6 — ED-36 Hardening Delta Audit

**Target:** `1aca37d8e437125e70ba793a4882b5aac9760f66` ("R9-C6: exact-key validation for derived-wheel isolation attempts")
**Delta audited:** `82b028e..1aca37d` only. R9-V5's acceptance of `82b028e` stands and is not reopened.
**Author:** Mohamed El Yazid — IID
**Date:** 2026-08-04

## Verdict: **Accepted**

Test `tests/test_environment_bundle_builder.py:1381` **PASSED in-container** — a real
pass, not a skip. The builder isolation boundary is not reopened; integration is not
blocked.

## Method

Fresh detached `core.autocrlf=false` worktree `D:\qwen-sae-interp-r9-v6-audit-1aca37d8`,
created / used / removed / pruned. **14 worktrees at start, 14 at end, same list.**
Branch tip `r9-ed36-bundle-builder` = `1aca37d8…`, unmoved. Read-only throughout:
`git status --porcelain --untracked-files=no` empty at end — no tracked file touched.
Every probe pinned `sys.path` to the audit worktree and asserted `__file__`, so nothing
resolved to the editable install in the stale main worktree.

## Governing hashes at `1aca37d` (sha256[:16] of committed blob bytes)

| Path | Hash | vs `82b028e` |
|---|---|---|
| `interplab/core/environment_bundle.py` | `8abdacfb3694b577` | changed |
| `schemas/environment_acquisition_manifest/v1.schema.json` | `b69e4dc83bbc9d4a` | unchanged |
| `slurm/environment_bundle.tooling.lock.json` | `4df4f6e701a7562b` | unchanged |
| `slurm/setup_env.sh` | `cb0aecf3d9fd6684` | unchanged |
| `tests/test_environment_bundle.py` | `bc4b3076eb0d2eac` | unchanged |
| `tests/test_environment_bundle_builder.py` | `59ed6c7b602cd050` | changed |
| `tests/test_slurm_setup_env.py` | `a81d12f31344bce0` | unchanged |

The five "unchanged" rows reproduce R9-V5's recorded values byte-for-byte, which
independently corroborates that the delta is confined to two files.

## Item 1 — Scope ✅

- Delta `82b028e..1aca37d`: **exactly 2 files**, both authorized —
  `interplab/core/environment_bundle.py`, `tests/test_environment_bundle_builder.py`.
- Cumulative `4bf0fd8..1aca37d`: **exactly the seven authorized paths**. No eighth path.
  Stop condition not triggered.

## Item 2 — Four do-not-touch hashes, independently re-derived ✅

The V5 record did not state its extraction convention. Rather than trust it, the
convention was **recovered by brute force** against `fee1cc1d5c08a30c` and then applied
to the remaining three. All four were computed from `1aca37d`'s **own committed bytes**,
not from `VERIFICATION_LOG.md` and not from the Engineer's work order.

Recovered convention: **sha256[:16] of the unit's full line range, UTF-8, LF, trailing
newline included** (for code); **`json.dumps(obj, sort_keys=True)`** (for the schema object).

| Unit | Location at `1aca37d` | Re-derived | Expected | Match |
|---|---|---|---|---|
| `_current_target_capture_fields` | `environment_bundle.py:233…` | `fee1cc1d5c08a30c` | `fee1cc1d…` | ✅ |
| builder cross-validation in `_validate_derived_wheels` | `:3518-3529` | `37d1e3419152854b` | `37d1e341…` | ✅ |
| builder shape gate in `_validate_derived_entry_shape` | `:4253-4263` | `cec269ddc0d4dfa3` | `cec269dd…` | ✅ |
| schema `$defs.derived_wheel.properties.builder` | `v1.schema.json:357-383` | `e135248a0473e905` | `e135248a…` | ✅ |

All four byte-identical. The V3-certified builder construction logic is untouched by
this delta. Both delta hunks land in `_validate_derived_entry_shape` **outside** the
`:4253-4263` builder shape gate.

## Item 3 — Both new negatives, and the acceptance floor ✅

Two new tests, one per attempt object, each rejecting a stray key:

- `test_validate_derived_entry_shape_rejects_stray_key_on_python_connection_attempt`
- `test_validate_derived_entry_shape_rejects_stray_key_on_native_connection_attempt`

**Attribution matrix (accepted clean baseline).** The unmutated fixture validates
clean, so each raise is attributable to its single mutation and no earlier guard
pre-empts it:

| Row | Result |
|---|---|
| 0 — clean baseline | **ACCEPTED** |
| 1 — stray key on `python_connection_attempt` | raises its **own** message |
| 2 — stray key on `native_connection_attempt` | raises its **own** message |

**The over-tightness question, verified against the builder — not the fixture.**
The concern was that an exact-key set could fail closed on a valid manifest. It does not.
The **real builder was executed** in the Linux container (`--network none --cap-add
SYS_ADMIN`, real `unshare`/`CLONE_NEWNET`, measured `net:[4026532604] → net:[4026532701]`)
and its genuine `evidence.json` was fed through the live gate:

| Object | Builder really emits | Validator requires | Verdict |
|---|---|---|---|
| `python_connection_attempt` | `{error, succeeded}` | `{error, succeeded}` | exact — **ACCEPTS** |
| `native_connection_attempt` (`:1233-1237`) | `{argv, returncode, stderr, stdout}` | `{argv, returncode, stderr, stdout}` | exact — **ACCEPTS** |

Static confirmation of why the python set is exactly two keys and cannot be otherwise:
`:1198-1205` builds `{"succeeded": True}` on the success branch but **raises at `:1204-1205`
before the evidence dict at `:1224` is ever constructed**. The only shape that can reach
a manifest is the except branch's `{"succeeded": False, "error": …}`. There is exactly
**one** emission site in the file. Both sets also still reject a stray key. Neither set
is over-tight; neither fails open.

## Item 4 — Ternary at `:4269` ✅

Line **4269** in both commits (the work order's correction away from `:4266` is right —
one-line drift from R9-V4).

```
-  required=required_keys | {"backend_path"} if field == "backend" else required_keys,
+  required=(required_keys | {"backend_path"}) if field == "backend" else required_keys,
```

`ast.dump` of both expressions is **byte-identical** — `|` already bound tighter than the
conditional, so the parenthesisation was always implicit. Evaluated both branches:
`field="backend"` → `{…, backend_path}`, `field="frontend"` → `{…}`, equal in both
versions. Cosmetic only; zero behaviour change. This closes the V5 cosmetic advisory.

## Item 5 — Residual gap CLOSED ✅ (the substantive addition)

`tests/test_environment_bundle_builder.py:1381` is `skipif`-gated on
`sys.platform.startswith("linux")`. It skipped at V5 and skips on this Windows host, so
the repository regression guarding the direct child-source boundary had **never
executed** — V5 proved the boundary by manual Docker probe instead.

Executed in the Linux container (Docker **28.5.1**, `desktop-linux`,
`python:3.11-slim-bookworm`, `--network none --pull never`, repo mounted `:ro`):

```
platform linux -- Python 3.11.15, pytest-8.4.2, pluggy-1.6.0
rootdir: /repo   configfile: pyproject.toml
tests/test_environment_bundle_builder.py::test_build_no_network_child_source_
    blocks_socket_dns_and_python_subprocess PASSED [100%]
1 passed in 2.00s
```

Environment proof captured in the same container: `sys.platform = linux` (so the skip
genuinely did not fire), `bundle.__file__ = /repo/interplab/core/environment_bundle.py`
(audit worktree, not a stale install), interfaces `lo` only, empty route table.

**Falsification control — the test is not vacuous under `--network none`.** Because the
container has no network, a naive reading is that the child would fail regardless. It
would fail, but not with the asserted message. Running the same `build.py` **without**
the guard, in the same container:

| Configuration | rc | Asserted message `"network access is forbidden during offline derived-wheel construction"` |
|---|---|---|
| **with** guard (what the test runs) | 1 | **present** — `RuntimeError` from `_deny` at `<string>:16` |
| **without** guard (control) | 1 | **absent** — plain `socket.gaierror: [Errno -3]` |

The assertion is carried by the guard, not by the absent network. The test would fail if
the boundary regressed. **Real pass.**

*Instrumentation note.* `python:3.11-slim-bookworm` has no `pytest`/`jsonschema`, and
`rpds-py` is a compiled dependency with no Linux wheel available offline on this host.
Linux deps were therefore staged into a scratchpad directory by a **separate, prior**
networked container. The **test run itself** was `--network none --pull never` with the
repository mounted read-only, exactly as specified.

## Item 6 — Regressions ✅

| Gate | Result |
|---|---|
| `python -m pytest -p no:cacheprovider -q -rs` | **772 passed, 1 skipped, 3 deselected**, exit 0, 363.07s |
| the 1 skip | exactly `:1381` — **converted to a real PASS in-container** (above) |
| `uv run ruff check interplab tests scripts/*.py data/concepts/*.py` (exact CI, `ci.yml:28`) | **All checks passed** |
| `uv lock --check` | **Pass** — 196 packages |
| `bash -n` × 6 (`setup_env` + 5 launchers) | **All OK** |
| `git diff --check` (`4bf0fd8..1aca37d` and `82b028e..1aca37d`) | **Clean** |

772 = 770 (V5 baseline) + 2 new negatives — exact, no silent loss. The 3 deselected
remain the pre-existing `@pytest.mark.nightly` rows.

## Carried forward — unchanged by this delta

- **BLOCKING, pre-first-write.** The acquisition schema is still **not enforced on any
  production read path**: `environment_bundle.py` contains no reference to
  `_schema_registry` / `validate_schema` (re-confirmed at `1aca37d`). At runtime the
  Python validators are the sole gate. They do reject every unsafe state, so this does
  not block accepting `1aca37d` — but no real acquisition manifest may be written until
  the schema is enforced. Unchanged from V5.
- **R9-V1-PREP matrix still absent from the repository.** Row-by-row certification
  remains blocked pending the Orchestrator supplying it.
- V5's Item 3b ruling (native `{succeeded: true, returncode: 1}` admitted by code,
  rejected by schema) stands as benign redundancy — and is now further narrowed, since
  the exact-key set added here rejects a stray `succeeded` on the native object outright.

## Constraint compliance

Read-only. No commit, no push, no branch mutation, no Tamia, no bundle or venv
construction inside the repository. All probe scripts written to scratchpad, never into
the worktree. Worktree removed and pruned; start/end worktree lists identical.
