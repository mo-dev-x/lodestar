# R9-V9B — Matrix Rows 4 (tooling closure) and 9 (pip check), First-Time Certification

**Author:** Mohamed El Yazid — IID
**Date:** 2026-08-05
**Anchor:** frozen accepted **`1aca37d8e437125e70ba793a4882b5aac9760f66`** (`environment_bundle.py`, 5112 lines)
**Worktree:** `D:\qwen-sae-interp-r9-v9b2-1aca37d`, fresh, detached, `core.autocrlf=false`; removed and pruned.
**Mode:** Read-only. No commit, no push, no fix, no Tamia.

Every probe carried the in-source assertion `uris.REPO_ROOT == <this worktree>` plus
`bundle.__file__`, so a stale-main read would have aborted rather than produced numbers.
`D:\qwen-sae-interp-r9-repair` and branch `r9-ed36-bundle-builder` were never touched — the
branch advanced `92a12f6 → a9a174f` (R9-C10) during this audit, which does not affect the
frozen anchor. No tracked file touched.

## Verdicts

| Row | Verdict |
|---|---|
| **4 — tooling closure / cross-binding** | **NOT COVERED** — V9B-F1 (MAJOR) |
| **9 — pip check** | **NOT COVERED** — V9B-F2 (MAJOR), V9B-F3 (MAJOR, coverage) |

**The default hypothesis held for both.** Each row has the V9-F1 shape — a strong check that
exists but is unreachable from, or unverifiable by, the surface that needs it. This is now the
**third and fourth** occurrence of the pattern.

---

# ROW 4 — tooling closure / cross-binding

## The question: is the lock bound to what gets used?

`_TOOLING_LOCK_FILE = REPO_ROOT / "slurm" / "environment_bundle.tooling.lock.json"` (`:51`),
15 artifacts. Required tooling name sets (`:53-54`):

```python
_BASE_TOOLING          = ("pip", "setuptools", "wheel", "hatchling", "virtualenv")
_DERIVED_WHEEL_TOOLING = (*_BASE_TOOLING, "build")
```

Two independent things exist and are never joined:

| Path | What it binds | Reachable from |
|---|---|---|
| `_validated_tooling_lock_files` (`:775`) | **lock artifact → bundle file bytes**, via `_validated_artifact_bytes` (recomputes size + sha256) | **`validate_bundle` only** (`:2538`), i.e. the `preflight` subcommand (`main:5032`) |
| `_validate_tooling_entries` (`:3263`) | **manifest tooling entry → `manifest["generator"]`** | `_validate_acquisition_manifest_semantics` (`:2889`) — the cert-lane path |

In `validate_bundle` the two results are returned as separate keys — `"tooling":
validated["tooling"]` and `"tooling_closure": tooling_install_plan` — and are **never compared
to each other**. Mechanically confirmed: `_validate_tooling_entries` contains no reference to
`tooling_lock` / `load_tooling_lock` / `_TOOLING_LOCK_FILE` / `_tooling_install_plan`.

Reachability of the lock from each surface:

| Surface | `_validated_tooling_lock_files` | `tooling_lock_artifacts` |
|---|---|---|
| `validate_bundle` (preflight) | **True** | True |
| `certification_environment_inputs` | **False** | True (only via `_tooling_install_plan` for *optional* extras) |
| `_validate_acquisition_manifest_semantics` | **False** | **False** |
| `create_virtualenv` | **False** | **False** |

## V9B-F1 — MAJOR. Tooling versions bind the manifest to itself; setuptools and wheel bind to nothing

Consumer matrix, hand-crafted manifests fed to `_validate_tooling_entries` (accepted clean
baseline first):

| Hand-crafted manifest | Consumer |
|---|---|
| all versions == lock *(baseline)* | **ADMITTED** |
| `pip` 25.0 → 9.9.9 | rejected — *tooling version mismatch for 'pip': expected 25.0, got 9.9.9* |
| `hatchling` drifted | rejected — same guard |
| `virtualenv` drifted | rejected — same guard |
| **`setuptools` 83.0.0 → 70.0.0** | **ADMITTED** |
| **`wheel` 0.45.0 → 0.1.0** | **ADMITTED** |
| tooling entry omitted (`wheel`) | rejected — *missing=['wheel']* |
| extra unapproved entry (`uv`) | rejected — *unexpected=['uv']* |
| substituted distribution (`wheel`→`distlib`) | rejected — *missing=['wheel'], unexpected=['distlib']* |

Name-set closure is sound. Version binding is not, in two distinct ways:

**(a) The versions that *are* checked are checked against the manifest's own `generator` block.**

```
lock says pip == 25.0
entry 9.9.9 vs generator 25.0  (inconsistent)      -> rejected
entry 9.9.9 AND generator 9.9.9 (self-consistent)  -> ADMITTED     <-- manifest binds to itself
```

This is exactly the case the work order asked about. `_validate_tooling_entries` only asserts
that two fields of the same document agree; a hand-crafted manifest sets both.

**(b) `setuptools` and `wheel` have no version check at all** — they are in the required *name*
set but absent from the generator cross-check (which covers only pip, hatchling, virtualenv,
and build-when-derived-wheels-present). These are precisely the two pins **R9-D2 ratified with
exact artifact identity** — "inventory must be exactly `pip==25.0`, with setuptools and wheel
still absent" and "the operational pin is explicitly `wheel==0.45.0` with exact artifact
identity". The two most deliberately-pinned tooling artifacts are the two with no consumer
binding.

**Additionally:** `_validate_acquisition_manifest_semantics` takes `require_files=False` by
default, and `certification_environment_inputs` does not override it — so manifest tooling
**artifact bytes are never verified on the cert-lane path**. Only torch and derived wheels get
explicit byte checks there.

### Deterministic reproduction

```python
import sys; sys.path.insert(0, r"<worktree at 1aca37d>")
from interplab.core import environment_bundle as b
E = lambda d, v: {"distribution": d, "version": v, "filename": f"{d}-{v}.whl",
                  "relative_path": f"{d}-{v}.whl", "size_bytes": 100,
                  "sha256": "sha256:" + "a"*64, "origin": "https://x.invalid/w.whl", "type": "wheel"}
m = {"tooling": {"installers": [E("pip","9.9.9"), E("setuptools","70.0.0"), E("wheel","0.1.0"),
                                E("hatchling","1.27.0"), E("virtualenv","20.26.0")]},
     "generator": {"pip":"9.9.9","hatchling":"1.27.0","virtualenv":"20.26.0",
                   "build":"1.2.2","uv":"0.8.22"},
     "derived_wheels": []}
b._validate_tooling_entries(m)   # returns normally; lock says pip 25.0, setuptools 83.0.0, wheel 0.45.0
```

### R9-A5 classification

| Control | Class | Consumer mechanism | Holds hand-crafted? |
|---|---|---|---|
| lock artifact → bundle file bytes | recomputable | `_validated_artifact_bytes` in `validate_bundle` — **preflight only** | Yes at preflight, **absent at cert-lane** |
| required tooling name set | recomputable | `_validate_manifest_entries` vs `_BASE_TOOLING` (module constant) | **Yes** |
| pip/hatchling/virtualenv/build versions | **declarative** — self-consistency, not authority | `_validate_tooling_entries` vs `manifest["generator"]` | **No** |
| **setuptools / wheel versions** | **declarative, unchecked** | **none** | **No** |
| manifest tooling entry → lock identity | would be recomputable | **none at any surface** | **No** |

**Row 4 is NOT COVERED.** The lock is byte-bound to the bundle's *files* at preflight — real and
valuable — but the *manifest's* tooling claims are never joined to the lock anywhere, and two
required distributions have no version authority at all.

---

# ROW 9 — pip check

## What actually runs

`record_installed_environment` (`:2648`), **unconditional** (AST-confirmed: the call sits
inside no `if`):

```python
subprocess.run([sys.executable, "-m", "pip", "check"],
               capture_output=True, text=True, timeout=120, check=True)
except FileNotFoundError  -> EnvironmentBundleError("could not execute target-venv python -m pip check")
except CalledProcessError -> EnvironmentBundleError(f"python -m pip check failed: {detail}")
```

**It runs, it is mandatory, and it is fail-closed — not advisory.** `check=True` converts a
non-zero exit into an exception; the manifest write happens strictly after, so a failing check
yields no install manifest. Both existing tests pass at this anchor:

```
tests/test_environment_bundle.py::test_record_installed_environment_rejects_failing_pip_check_and_writes_no_manifest
tests/test_environment_bundle.py::test_record_installed_environment_writes_machine_readable_manifest
2 passed in 0.83s
```

A broken dependency set is therefore genuinely caught at the moment of recording, and the
detail string is propagated rather than swallowed. **That part of R9-A1's contract holds.**

## V9B-F2 — MAJOR. The pip check leaves no attestation and is never verified at the consumer

`grep -n "pip_check\|pip-check"` across `environment_bundle.py` **and**
`schemas/environment_install_manifest/v1.schema.json` → **NONE**.

The install manifest's exact-key set (`validate_install_manifest`, `:2800-2808`) is:

```
manifest_type, schema_version, created_at, acquisition_manifest_hash, repo_revision,
source_hashes, target, loaded_modules, installer_versions, torch, verified_imports,
installed_distributions
```

There is no field recording that `pip check` ran, when, or with what result. Consequently
`certification_environment_inputs` → `_validate_install_manifest_consistency` can neither
verify the check happened nor re-run it.

Live-introspection reachability at each surface makes the asymmetry precise:

| Surface | `_installed_distributions` | `_live_torch_runtime_identity` | `_measured_loaded_modules` |
|---|---|---|---|
| `record_installed_environment` | **True** | True | **True** |
| `_validate_install_manifest_consistency` | **False** | True | **False** |
| `certification_environment_inputs` | **False** | True | **False** |
| `validate_bundle` | False | False | False |

At cert-lane admission, **torch alone** is re-measured live. `installed_distributions` and
`loaded_modules` are compared document-to-document — the recorded install manifest against the
acquisition manifest.

**A5 classification: `pip check` is *recomputable*** — a property of the environment present at
consumption, re-runnable in one subprocess in the same venv at job start. A5 puts recomputable
facts at **consumer mandatory**. It is not run there, and no attestation substitutes.

**Hand-crafted test:** an install manifest that never saw `record_installed_environment` — with
internally consistent `installed_distributions`, correct `acquisition_manifest_hash`,
`repo_revision`, and `source_hashes` — carries no pip-check guarantee, and nothing at cert-lane
detects its absence.

*Stated fairly:* the consumer does pin every required distribution to an exact version and
reject extras, so a dependency-inconsistent set is hard to reach *if the manifests are honest*.
That is a real mitigation, and it is why this is a control-surface defect rather than a live
exploit. But it is precisely the "assume the producer ran" reasoning A5 forbids.

## V9B-F3 — MAJOR (coverage). The private-pip bootstrap assertion is stubbed out by every test that mentions it

R9-V2's "unexercised private pip" refers to `_bootstrap_private_pip` /
`_assert_bootstrapped_pip_only` — a different control from `pip check`. `_assert_bootstrapped_pip_only`
(`:1529`) is substantive, with four raise branches: inventory must be exactly `["pip"]`;
setuptools and wheel must remain non-importable; `pip --version` must execute; the measured
version must match. It is called at `:1790` (`_build_derived_runtime_wheel`) and `:3936`
(`create_virtualenv`) — both R9-D2 stop conditions.

All five test references disable it:

```
tests/test_environment_bundle.py:705          monkeypatch.setattr(bundle, "_assert_bootstrapped_pip_only", lambda path, expected_pip_version: None)
tests/test_environment_bundle.py:759          monkeypatch.setattr(bundle, "_assert_bootstrapped_pip_only", create_competitor)
tests/test_environment_bundle_builder.py:807  monkeypatch.setattr(bundle, "_assert_bootstrapped_pip_only", lambda *a, **k: None)
tests/test_environment_bundle_builder.py:880  monkeypatch.setattr(bundle, "_assert_bootstrapped_pip_only", lambda *a, **k: None)
tests/test_environment_bundle_builder.py:1052 monkeypatch.setattr(bundle, "_assert_bootstrapped_pip_only", lambda *a, **k: None)
```

**Zero tests exercise its logic; none of its four raise branches has a negative test.**
Reproduction: `grep -rn "bootstrapped_pip_only" tests/*.py` — every hit is a `monkeypatch.setattr`.
R9-V2's finding stands unchanged for this surface. (It is producer-side by nature — it inspects
a transient build venv the consumer never sees — so A5 classifies it **attestable-only**; the
honest consumer statement is "verifies the record, not the event," and no such record exists
either.)

### R9-A5 classification — row 9

| Control | Class | Consumer mechanism | Holds hand-crafted? |
|---|---|---|---|
| `pip check` dependency consistency | **recomputable** | **none** — not re-run, not attested | **No** |
| exact pinned versions of required distributions | recomputable-in-principle | `_validate_install_manifest_consistency`, but document-to-document (`installed_distributions` not re-measured) | Partial |
| live torch identity | declarative, closed by introspection | `_live_torch_runtime_identity` | Yes |
| private-pip bootstrap inventory | attestable-only | **none**, and no record | **No** |

**Row 9 is NOT COVERED.** The check is mandatory and fail-closed where it runs — that much is
proven — but it is unobservable to the surface that depends on it, and the adjacent private-pip
control has no test coverage at all.

---

## What would close both rows

- **Row 4:** cross-check `manifest["tooling"]["installers"]` against `tooling_lock_artifacts()`
  on distribution, version, and sha256 inside `_validate_tooling_entries`, so the authority is
  the committed lock rather than the manifest's own `generator` block; and consider whether the
  tooling lock should join `pyproject`/`uv.lock`/`requirements.cluster.txt` in
  `source_hashes_for_root` (`:215`), which today does **not** cover it.
- **Row 9:** record the `pip check` outcome in the install manifest as a first-class field and
  re-run `pip check` at `certification_environment_inputs`; it is one subprocess in the venv
  that is already active. Add negative tests for the four `_assert_bootstrapped_pip_only`
  branches without stubbing it.

Both are design items under R9-A5, not patches. Neither was re-audited from an accepted row.

## Constraint compliance

Read-only throughout. No fix, no commit, no push, no branch mutation, no Tamia. Anchor
`1aca37d` only; accepted rows not re-audited. Worktree removed and pruned — the 15th worktree
now present (`D:\qwen-sae-interp-r9-v10-audit` at `a9a174f`) is another role's, created during
this session, not residue of mine. All probes written to scratchpad, never into the worktree.
