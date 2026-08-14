# R9-V3-ED36-BUILDER-REACCEPTANCE — Independent Audit

**Auditor:** Interlab persistent auditor
**Date:** 2026-08-04
**Audit commit:** `1ed3ad98bad03e084a7237263ea7c9d0b69b3a4d` (branch `r9-ed36-bundle-builder`)
**Parent:** `490ae73e04cc5bfbfb814746aeab609e5e4f06fb`
**Worktree:** `D:\qwen-sae-interp-r9-v3-audit-1ed3ad98` (fresh, detached, LF-normalized)

## Verdict: **REJECT** — narrowly, on two explicit acceptance criteria

The design work is sound and the central open question resolves **in the engineer's favour**. Rejection rests on Verification Target 3 (missing negative tests) and Target 2 (strictness traded for coverage). Both are additive fixes; no schema redesign is implied.

---

## Resolution of the target-identity / SOABI question (Target 4 of the schema review)

**Genuinely captured — not absent. Not a blocking finding.**

The work order's premise ("no dedicated top-level field") is correct but incomplete. Target/build-host identity lives **per derived wheel** in `derived_wheel.builder`, which this commit widened from 4 fields to 8, all required, `additionalProperties: false`:

`os, architecture, python, abi, python_full_version, implementation, soabi, compatible_tags`

Adequacy confirmed at three levels, not merely key presence:

1. **SOABI is real SOABI** — `environment_bundle.py:234` sources it from `sysconfig.get_config_var("SOABI")` with `SO` / `cache_tag` fallbacks, and raises if unresolvable.
2. **Compatibility tags are ordered and order is enforced** — populated from `packaging_tags.sys_tags()` (canonical priority order, `environment_bundle.py:246`); the schema requires a non-empty array; validation compares with list `!=` (`environment_bundle.py:3526`), which is order-sensitive.
3. **Bound to the manifest target** — `environment_bundle.py:3519-3523` requires every `target` field to equal the corresponding `builder` field exactly.

*Observation (not a finding):* the SOABI/tags equality check is gated on `target_capture is not None`, itself gated on `enforce_current_target` (`environment_bundle.py:2905`). The fields remain **required and shape-validated unconditionally**; only the "matches this host" cross-check is skipped when validating off the build host. Correct design.

### R9-A3 category coverage — all seven mapped

| R9-A3 category | Field | Adequate |
|---|---|---|
| extraction inventory + hash | `extraction_inventory`, `extraction_inventory_sha256` | Yes, with F3 |
| PEP 508 declarations, markers, mappings | `build_requirement_mappings`, `marker_environment` | Yes |
| private build-env / tooling inventory | `build_environment` | Yes |
| target/build-host identity, SOABI, ordered tags | **`builder`** (8 fields) | **Yes — resolved** |
| backend, provider, module origin, backend-path, RECORD | `backend` | Yes, with F4 |
| kernel netns establishment + isolation proof | `isolation` | Structure yes; **F2** |
| outer/inner argv + wheel trust chain | `command`, `isolation.outer_argv`/`inner_argv` | Yes (`outer_argv == command` enforced, line 3698) |

---

## Findings, ranked by severity

### F1 — BLOCKING. Eight of nine R9-D4 §4 stop conditions have no negative test

Only `undeclared build requirement` is covered (`test_environment_bundle_builder.py:740`, deterministic, fails for the right reason).

Exact-string search across `tests/*.py` returns **zero** hits for: `direct URL`, `extras`, `does not admit approved version`, `duplicate build requirement`, `build backend mismatch`, `backend-path`, `missing backend provider`, `no approved build backend contract`.

**The enforcement itself is correct.** I exercised `_validate_build_system_contract` directly; all nine branches are live and raise the right error:

```
[raises] direct URL              -> build requirement must not use a direct URL
[raises] VCS ref                 -> build requirement must not use a direct URL
[raises] local path ref          -> build requirement must not use a direct URL
[raises] extras                  -> must not use extras for 'hatchling'
[raises] incompatible specifier  -> does not admit approved version '1.27.0'
[raises] duplicate/ambiguous     -> declares duplicate build requirement 'hatchling'
[raises] backend mismatch        -> expected 'hatchling.build', got 'setuptools.build_meta'
[raises] non-empty backend-path  -> expected [], got ['.']
[raises] missing backend provider-> missing backend provider 'hatchling'
```

So this is a **coverage gap, not a correctness defect** — but R9-D4 §4 requires a deterministic negative test per stop condition, and it does not exist. Untested enforcement is regression-prone.

### F2 — MAJOR. The isolation proof has no floor; `native_connection_attempt` accepts empty

`derived_isolation.python_connection_attempt` and `native_connection_attempt` are declared `{"type": "object"}` — no properties, no required keys, no `additionalProperties: false`. `{}` validates.

The code layer does not close it, and is **asymmetric**:

```python
if python_attempt.get("succeeded") is not False:   # missing key -> None -> raises. Correct.
if native_attempt.get("returncode") == 0:          # missing key -> None -> does NOT raise.
```

Verified: `native_connection_attempt = {}` and `{"argv": [...]}` (no `returncode`) both pass; only `returncode: 0` is rejected. A manifest can therefore omit the native network-isolation evidence entirely and still validate — the R9-A3 category 6 / R9-D4 §5 proof is unenforced at both layers.

Fix: constrain both sub-objects in schema (required `returncode`/`succeeded`), and change line 3694 to reject a missing `returncode`.

### F3 — MODERATE. `inventory_entry.sha256` / `size_bytes` optional in schema

`required: ["path", "type"]` only. A `type: "file"` entry with no `sha256` validates against the schema. Mitigated — `_validate_derived_entry_shape` (lines 4246-4248) applies the conditional requirement the schema omits. The aggregate `extraction_inventory_sha256` does **not** compensate: it hashes whatever the inventory contains, so absent per-entry hashes yield a hash that binds paths but not file contents. Schema-only consumers get no content binding. Fix with `if/then` on `type`.

### F4 — MINOR. `derived_tool_record.backend_path` optional

Not in `required`; the code also tolerates omission (`optional={"backend_path"}` line 4268, `.get("backend_path", [])` line 4278). The non-empty backend-path stop condition **is** enforced at build time (F1 probe, `backend-path mismatch`). The def is shared by `frontend` and `backend`, where it is meaningless for the frontend — the likely design reason. Low risk; note the shared-def constraint if tightening.

### F5 — INFORMATIONAL. Pre-existing looseness, not introduced here

`artifact.import_name` and the four `generator` sub-fields are optional at the parent commit too. Out of scope for this commit.

---

## Verification results

| # | Target | Result |
|---|---|---|
| 1 | Schema covers seven R9-A3 categories | **PASS** — 15 properties, all required, `additionalProperties: false`; 4th row resolved |
| 2 | Strictness not traded for coverage | **FAIL** — F2, F3, F4 |
| 3 | Deterministic negative test per stop condition | **FAIL** — F1 (8 of 9 absent) |
| 4 | Namespace proof executed, not mocked | **PASS** — executed on this host |
| 5 | Three ruff repairs did not weaken tests | **PASS** |
| 6 | Scope and identity | **PASS** on scope; hash-count discrepancy raised below |
| 7 | R9-D3 setup invariant holds | **PASS** |
| 8 | Battery reproduced | **PASS** |

### Target 4 — host-capability statement

**Docker was available and the namespace proof genuinely executed. It did not skip.**

- Host: win32, Docker **28.5.1**; `python:3.11-slim-bookworm` present locally (`sha256:b18992999dbe963a45a8a4da40ac2b1975be1a776d939d098c647482bcad5cba`).
- `test_real_linux_namespace_isolation_evidence_uses_unshare_and_no_network_in_docker` — **PASSED** in 1.59s. Timing verified legitimate: baseline `docker run` on this host is 0.565s.
- I independently replicated the container run outside pytest and captured the raw evidence. Real kernel facts, not fixtures:
  - parent netns `net:[4026532604]` → child `net:[4026532701]` — real `unshare(CLONE_NEWNET)`
  - `descendant_namespace == child_namespace` — descendants inherit the isolated netns
  - `interfaces: ["lo"]`, no non-loopback routes
  - `native_connection_attempt`: `getent hosts example.com` → `returncode 2` (real failure under `--network none`)
  - `fd_targets`: no `socket:` descriptors retained
  - `mechanism: linux-unshare-clone_newnet`

**R9-D4 §5 is genuinely satisfied on this host.**

One related test **did** skip: `test_build_no_network_child_source_blocks_socket_dns_and_python_subprocess` (`test_environment_bundle_builder.py:1119`), gated on `sys.platform.startswith("linux")`. Its substance is exercised inside the Docker test, which runs the same `_build_no_network_child_source()` under Linux — but the direct test itself was not run here.

### Target 5 — the three ruff repairs

- **F841 — restored `assert evidence_path.is_file()` (line 1329): meaningful, not trivially true.** `evidence_path` is only *assigned* at line 1205; the test never creates the file. It is written by the container to `/shared/evidence.json` through the bind mount. My independent replication confirmed the container produces it. The assertion genuinely proves the container emitted evidence to the host.
- **B007 — `_token` rename (line 1396): harmless.** The third tuple element is genuinely unused in the loop body; artifact hashes derive from `_wheel_bytes(name, version)`, so no fixture distinctness was lost.
- **F541 — rendered string is correct.** Byte-comparison to the pre-change value is **impossible**: the whole test is new in this commit, so the pre-repair state was never committed and exists in no ref. I verified equivalently and more strongly by AST-extracting both generated container-source blocks and compiling them: **both compile as valid Python with zero `{{`/`}}` occurrences.** The load-bearing braces are the `env = { **os.environ, ... }` dict literal in the launcher. The naive fix (dropping `f` while leaving `{{`/`}}`) would have emitted `env = {{ **os.environ }}`, which does not compile — so the repair demonstrably resolved the escapes correctly. The remaining f-strings in that function (lines 1298, 1300) are the volume-mount paths and legitimately carry placeholders. Separately, `--format "{{.Id}}"` (line 1193) is a plain string and correctly renders the literal Go template docker expects.

### Target 6 — scope and hashes

`git diff --name-only 490ae73e 1ed3ad98` returns **exactly four paths**, all within the seven authorized:

```
interplab/core/environment_bundle.py
schemas/environment_acquisition_manifest/v1.schema.json
tests/test_environment_bundle.py
tests/test_environment_bundle_builder.py
```

Governing hashes, re-derived from **canonical git blobs** (`git cat-file blob`, LF), sha256 truncated to 16:

| Path | Parent | Audit | |
|---|---|---|---|
| `interplab/core/environment_bundle.py` | `0af22579fa41f93c` | `6db942cc78fc047e` | changed |
| `schemas/environment_acquisition_manifest/v1.schema.json` | `0c40a17b624336e9` | **`60b1a959fc7cc7f0`** | changed ✓ as specified |
| `schemas/environment_install_manifest/v1.schema.json` | `430dc16f700a62b3` | `430dc16f700a62b3` | unchanged |
| `slurm/setup_env.sh` | `cb0aecf3d9fd6684` | `cb0aecf3d9fd6684` | unchanged |
| `slurm/environment_bundle.tooling.lock.json` | `4df4f6e701a7562b` | `4df4f6e701a7562b` | unchanged |
| `tests/test_environment_bundle.py` | `8d4c935e823fb6f5` | `bc4b3076eb0d2eac` | changed |
| `tests/test_environment_bundle_builder.py` | `212ec066554c0dea` | `85aff012856120d2` | changed |

**The acquisition schema matches the specified `60b1a959…` exactly**, which anchors the derivation method.

**Discrepancy for the Orchestrator:** the work order states "six unchanged, acquisition schema changed." Against the seven authorized paths, **four changed, three unchanged** — necessarily so, since the four changed files are themselves among the seven. If "seven governing hashes" denotes a different set (e.g. schema/lock artifacts only, excluding code and tests), that list is **not in the repository** and I cannot certify it. Please supply the authoritative list.

### Target 7 — R9-D3 setup invariant holds

- No `INTERPLAB_STUB_LOG` bypass in `slurm/setup_env.sh` (absent). It appears only in `tests/test_slurm_setup_env.py` (lines 76, 146-147, 200) — the stub harness, its legitimate home.
- Success test supplies the real HEAD: `_run_git(repo, "rev-parse", "HEAD")` (line 53).
- All-zeros appears only in a rejection test: `expected_revision="0" * 40` at line 280, inside `test_setup_env_rejects_all_zero_expected_revision_before_mutation`.

### Target 8 — battery reproduced

| Check | Result |
|---|---|
| Focused suite (both changed test files) | **104 passed, 1 skipped** |
| Full pytest | **752 passed, 1 skipped, 3 deselected** — exit 0, 251s |
| `ruff check` (3 changed .py) | **All checks passed** — identical to parent |
| `ruff format --check` | 3 files "would reformat" — **identical at parent**, no regression (108 files repo-wide; project does not enforce) |
| `uv lock --check` | **Pass** — 196 packages resolved |
| `bash -n` setup + all 5 launchers | **All OK** |
| `git diff --check` | **Clean** |

Repo-wide `ruff check .` reports 49 errors — all pre-existing, none in the changed files.

---

## Methodology note: a false reading caught and discarded

My first focused run showed **7 failures** (`certify config bytes do not match authoritative configs/certify/hm03l7yz.yaml`). This was **entirely an artifact of my own worktree**, not a defect.

`core.autocrlf=true` with no `.gitattributes` corrupted checked-out bytes: `configs/certify/hm03l7yz.yaml` hashed `6628dd29…` in the working tree versus `6dfb9e35…` as a git blob. The authoritative constant `_R5_X2_AUTHORITATIVE_CONFIG_HASH` is `sha256:6dfb9e35…` — the blob value. After setting `core.autocrlf=false` and re-checking-out, worktree bytes matched the blob and all 7 failures vanished.

This is the mechanism behind the repo's `-lf` worktree convention. **Recommendation: cut future audit worktrees with `core.autocrlf=false`, or commit a `.gitattributes`.** Any audit run on a default Windows checkout will produce these 7 spurious failures.

A second contamination trap was also avoided: running a probe script by absolute path puts the *script's* directory on `sys.path[0]`, so `import interplab` resolved to the editable install in the stale main worktree. All probes were re-run with the audit worktree pinned explicitly and `__file__` asserted.

---

## Carried items

- **R9-V1-PREP matrix — independently confirmed absent.** I searched filenames across all history and content-grepped `R9-V1-PREP` across all refs: zero hits. It exists only in the governance thread. **Row-by-row certification is blocked pending the Orchestrator supplying the document.** The engineer's schema-diff-derived mapping remains an unverified reconstruction; my Target-1 table above is derived independently from the schema and code, not from their report.
- **Three deselected tests — none is a blocking matrix row.** `test_canary_cheese.py::test_cheese_9056_within_tolerance`, `test_interventions_identity_nightly.py::test_noop_bit_identical_logits_on_real_qwen`, `::test_noop_bit_identical_generation_on_real_qwen`. All `@pytest.mark.nightly` (`pyproject.toml:80`, `-m "not nightly"` default), all pre-existing real-Qwen/cluster tests, none touching ED-36 or the bundle builder.

## Prohibited-action compliance

No network access, no Tamia, no torch acquisition, no real target capture, no bundle or venv construction, no environment publication, no equivalence runs, no scientific execution, no `git push`. The audit commit and its branch were not modified. The Docker container ran under `--network none` with `--pull never`, using only a locally cached image.

## Required to accept

1. Add deterministic negative tests for the eight uncovered R9-D4 §4 stop conditions (F1).
2. Constrain `python_connection_attempt` / `native_connection_attempt` in schema, and reject a missing `returncode` at `environment_bundle.py:3694` (F2).
3. Make `inventory_entry.sha256`/`size_bytes` conditionally required on `type: "file"` via `if/then` (F3).
4. Orchestrator to supply the R9-V1-PREP matrix and the authoritative seven-hash list.

F4 is acceptable as-is if the shared-def rationale is recorded.
