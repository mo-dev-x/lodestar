# R9-V9 — Packaging Pre-Activation Probe (Part A) and Alliance Torch, Row 6 (Part B)

**Author:** Mohamed El Yazid — IID
**Date:** 2026-08-05
**Mode:** Read-only, diagnostic. No commit, no push, no branch mutation, no Tamia, no fix.

**Revision discipline.** Two separate fresh detached `core.autocrlf=false` worktrees were
cut, used, removed and pruned. Neither part read `D:\qwen-sae-interp`.

| Part | Anchor commit | Worktree | `environment_bundle.py` |
|---|---|---|---|
| A | **`92a12f6f03461bd6641b7d75713410ce5985d291`** | `D:\qwen-sae-interp-r9-v9a-92a12f6` | 5131 lines |
| B | **`1aca37d8e437125e70ba793a4882b5aac9760f66`** | `D:\qwen-sae-interp-r9-v9b-1aca37d` | 5112 lines |

Every probe asserted `uris.REPO_ROOT == <its own worktree>` and `bundle.__file__` before
running; the assertion is in the probe source, so a stale-main read would have aborted rather
than produced numbers. 14 worktrees at start, **14 at end**. No tracked file touched in either.
`92a12f6` was **not** audited as a candidate — only the two named pre-activation entry points
were exercised.

---

# PART A — packaging pre-activation probe

## Verdict: **a real, newly-introduced pre-activation dependency — not benign, and not pre-existing.** Unproven on Tamia; cheap to eliminate.

### The premise checks out

`interplab/core/environment_bundle.py` at `92a12f6` has exactly five non-stdlib module-level
import statements:

```
:33  from packaging import tags as packaging_tags
:34  from packaging.requirements import Requirement as PackagingRequirement
:35  from packaging.utils import canonicalize_name as packaging_canonicalize_name
:36  from packaging.utils import parse_wheel_filename
:42  from interplab.core import hashing
```

R9-C9's own guard test (`tests/test_environment_bundle.py:1910`) writes the exemption into
the criterion explicitly:

```python
allowed = set(sys.stdlib_module_names) | {"packaging", "interplab"}
```

and its blocking hook blocks only the jsonschema closure —
`{"jsonschema","referencing","rpds","attr","attrs","jsonschema_specifications"}`. **`packaging`
is exempted by name, not validated.** R9-A4's stated criterion was "stdlib plus
`interplab.core.hashing`"; `packaging` is neither.

Ordering in `slurm/setup_env.sh` is exactly as the work order states:
`:76 module load python/3.11 arrow` → `:78 preflight` → `:88 create-venv` → **`:97 source
"$VENV_DIR/bin/activate"`**. Both subcommands run on bare system python.

### (1) Extend the hook to `packaging` — do they still work? **No.**

A/B, same harness, same fixture, only the blocked set differs:

| Run | Blocked set | preflight rc | plan file written |
|---|---|---|---|
| **CONTROL** (reproduces R9-C9's criterion) | jsonschema closure | **0** | **True** |
| **EXPERIMENT** | jsonschema closure **+ `packaging`** | **1** | False |

Failure is at module import, before any subcommand logic runs:

```
File ".../interplab/core/environment_bundle.py", line 33, in <module>
  from packaging import tags as packaging_tags
ImportError: blocked for R9-C9 bootstrap-safety test: packaging
```

Raw module import alone: `jsonschema blocked only` → rc=0; `jsonschema + packaging blocked`
→ rc=1. So **create-venv fails identically and for the same reason** — neither subcommand can
reach its own code, because the module cannot be loaded.

### (2) Module-level uses, and whether a lazy import would be enough — **it would not**

All four imports are unconditional module scope. More importantly, the *uses* are reachable.
Probe: allow `packaging` to import, then poison each bound symbol so any actual use raises,
then run preflight:

```
RuntimeError: PACKAGING USED pre-activation: packaging_tags.sys_tags
```

`packaging_tags.sys_tags()` is called at `:246` inside `_current_target_capture_fields`,
reached from preflight via `_validate_acquisition_manifest_semantics(...,
enforce_current_target=True)`. Other uses — `parse_wheel_filename` / `canonicalize_name` at
`:1002-1003`, `PackagingRequirement` at `:1367/1396/3618` (producer-side build-requirement
normalisation) — are not what trips first.

**Consequence: converting `:33-36` to lazy imports would not fix this.** `packaging` is a
genuine runtime dependency of preflight, not merely an import-ordering artifact. The fix, if
one is ordered, has to be either vendoring/replacing the `sys_tags` use or guaranteeing
`packaging` on the bootstrap interpreter — a scope ruling, not a mechanical edit.

### (3) Latent break predating R9? **No — introduced by R9-C1.**

AST comparison of non-stdlib module-level roots along the chain:

| Commit | Lines | Non-stdlib module-level roots |
|---|---|---|
| `4bf0fd8` (pre-R9 integration base) | 2279 | `['interplab']` |
| **`c847e07`** (R9-C1, first builder commit) | 3740 | **`['interplab', 'packaging']`** |
| `490ae73` | 4474 | `['interplab', 'packaging']` |
| `1aca37d` | 5112 | `['interplab', 'packaging']` |
| `92a12f6` | 5131 | `['interplab', 'packaging']` |

The pre-activation surface was stdlib + `interplab` before R9 and has carried `packaging`
since the very first ED-36 builder commit. It does **not** predate R9 work.

### Is it actually broken on Tamia? Unresolved — and deliberately so

I did not access Tamia. Whether top-level `packaging` is importable after
`module load python/3.11 arrow` is the open question, and it is the only thing standing
between "latent break" and "works by luck". Proxy evidence only: `python:3.11-slim-bookworm`
ships `packaging 26.2` as a **top-level** site-package, so on that image the import succeeds.
That is a weak proxy — Alliance python modules are custom builds, and both pip and setuptools
vendor packaging *privately* (`pip._vendor.packaging`, `setuptools._vendor.packaging`), which
would **not** satisfy `import packaging`.

**Classification: real risk, unvalidated, newly introduced, never exercised.** The cluster
preflight has never run to completion (R9-X1: no bundle, no usable venv), so this has never
been tested in the only environment that matters. It is an Engineer item with its own scope
ruling, as the work order anticipated. The cheapest possible closure is one line on the login
node: `module load python/3.11 arrow && python -c "import packaging; print(packaging.__file__)"`.

---

# PART B — matrix row 6, Alliance torch

## Verdict: row 6 **NOT COVERED**

Every *recomputable* control is enforced consumer-side and fails closed — I could not break
one. But the row's own subject, **Alliance torch authorization**, is enforced **only on the
producer**, and R9-A5 is now binding: producer-only enforcement is a finding, not a pass.

### Torch code unchanged since `1aca37d` — confirmed

Function-level sha256[:16], `1aca37d` → `92a12f6`:

| Function | Result |
|---|---|
| `import_alliance_torch_artifact` | `19890ae6d226d8c2` **UNCHANGED** |
| `_validate_torch` | `7e79b2fed56d4a55` **UNCHANGED** |
| `_validate_torch_artifact_file` | `f840efe76c0b18e9` **UNCHANGED** |
| `_live_torch_runtime_identity` | `2f87dcc46431f4f4` **UNCHANGED** |
| `_validate_torch_runtime_identity` | `2e35a68dcfb3ffca` **UNCHANGED** |

The `1aca37d` finding therefore applies unchanged at the current tip.

### The contract as implemented

```
_ALLIANCE_TORCH_VERSION        = "2.13.0+computecanada"   :70
_ALLIANCE_TORCH_PUBLIC_VERSION = "2.13.0"                 :71
_ALLIANCE_TORCH_CUDA_VERSION   = "13.2"                   :72
_ALLIANCE_TORCH_ORIGIN_PREFIX  = "alliance:wheelhouse"    :73
```

Consumer-side surfaces: `_validate_torch` (`:3421`) and `_validate_torch_artifact_file`
(`:3451`) via `_validate_acquisition_manifest_semantics` (`:2891`, `:2898`);
`_validate_torch_runtime_identity` + `_live_torch_runtime_identity` via
`_validate_install_manifest_consistency` (`:3040-3041`).

### Adversarial matrix — every bundle hand-crafted, fed to the consumer alone

**A. Manifest and artifact controls.** Accepted clean baseline first, so each rejection is
attributable:

| Hand-crafted bundle | Consumer |
|---|---|
| sanctioned bundle *(baseline)* | **ADMITTED** |
| `2.13.0+cu121` | rejected — *must declare the sanctioned Alliance version 2.13.0+computecanada* |
| `2.13.0+rogue` (unauthorized build, same public version) | rejected — same guard |
| plain `2.13.0`, no local segment | rejected — same guard |
| artifact file missing | rejected — *bundle artifact missing* |
| arbitrary recorded hash | rejected — *bundle artifact hash mismatch* |
| bytes tampered, manifest left stale | rejected — *bundle artifact size mismatch: expected 567, got 575* |
| wrong recorded size | rejected — *size mismatch* |
| filename is `numpy-…` | rejected — *filename does not identify torch* |
| filename version ≠ manifest version | rejected — *filename version does not match the manifest* |
| METADATA `Name` ≠ torch | rejected — *metadata Name does not identify torch* |
| METADATA `Version` ≠ manifest | rejected — *metadata Version does not match the manifest* |
| origin `pypi:torch` | rejected — *origin must declare the approved Alliance wheelhouse provenance prefix* |
| `relative_path: "../escape.whl"` | rejected — *artifact path contains parent traversal* |
| lock resolves `2.12.0` | rejected — *torch lock version mismatch* |

**B. Live runtime identity** — all reject, baseline admitted:

| Case | Consumer |
|---|---|
| record and live both sanctioned *(baseline)* | **ADMITTED** |
| CPU runtime, live `cuda=None` | rejected — *did not report a CUDA build identity* |
| record claims CUDA, live is CPU | rejected — same |
| `cuda_available` false | rejected — *does not provide CUDA availability required by the production cluster profile* |
| record says available, live says not | rejected — same |
| CUDA `12.4` on both sides | rejected — *does not match the sanctioned CUDA build identity 13.2* |
| record `13.2`, live `12.4` | rejected — *executing runtime did not report the sanctioned CUDA build identity* |
| live torch version drifts | rejected — *does not match the executing torch distribution* |
| record version not sanctioned | rejected — *does not match the approved artifact* |

### V9-F1 — MAJOR. Torch authorization is producer-only; the artifact hash has no external root

The work order's last case — *"an internally consistent but unauthorized build sharing public
version 2.13.0"* — is the one that lands. Two wheels with **completely different bytes**, both
labelled `torch 2.13.0+computecanada`, both with correct METADATA, self-consistent
size/sha256, and an `alliance:wheelhouse` origin string:

```
bundle 1 sha256 = sha256:a4cb03601c11a17c255...   -> ADMITTED
bundle 2 sha256 = sha256:92aa86de889646adce0...   -> ADMITTED   (substitute build)
```

**The consumer cannot distinguish the sanctioned Alliance build from a substitute.**

Root cause, verified three ways:

1. **No authorized torch hash exists in code.** `_ALLIANCE_TORCH_*` is exactly
   `{VERSION, PUBLIC_VERSION, CUDA_VERSION, ORIGIN_PREFIX}` — no SHA constant.
2. **torch is excluded from the source-hash-bound export.** `requirements.cluster.txt` carries
   113 distributions, each with authorized hashes; `'torch' in names` → **False**. Every other
   runtime artifact is rooted by `entry["sha256"] not in requirement.hashes` (`:3382`); torch
   has no equivalent. `_validate_torch` consults `uv.lock` for the **public version only**, and
   the lock's torch rows are `2.13.0` / `2.13.0+cpu` from `download.pytorch.org` — not the
   Alliance build at all.
3. **The real external root exists, but never reaches the consumer.** `import_alliance_torch_artifact`
   (`:2233`) is genuinely strong: it requires an operator-supplied `expected_identity`
   document and matches it against *measured* `filename`, `size_bytes`, `sha256`,
   `distribution`, `version`, `public_version`, `origin` (`:2274-2296`), plus an acquisition
   transcript recording `no-index`/`no-deps`/`only-binary` (`:2267`). But every reference to
   `expected_identity` and the torch receipt lives in **`import_alliance_torch_artifact`,
   `finalize_bundle`, and `main`** — and in **no consumer function**. The consumer sees only
   `manifest["torch"]`, a plain entry. A bundle that never ran the import step is
   indistinguishable from one that did.

### R9-A5 classification of each torch control

| Control | A5 class | Consumer-side mechanism | Holds under hand-crafted-bundle test? |
|---|---|---|---|
| size, sha256 vs bytes | recomputable | `_validated_artifact_bytes` (`:3762`) recomputes both | **Yes** |
| filename ↔ version, METADATA Name/Version | recomputable | `_validate_torch_artifact_file` (`:3451`) reads the wheel | **Yes** |
| local version `+computecanada`, public version, lock cross-check | recomputable | `_validate_torch` (`:3427-3441`) vs committed lock | **Yes** |
| artifact path containment | recomputable | `_resolve_artifact_path` traversal guard | **Yes** |
| live CUDA `13.2`, availability true, version match | declarative **closed by live introspection** | `_live_torch_runtime_identity` (`:4679`) + `_validate_torch_runtime_identity` (`:4690`) | **Yes** — A5-compliant |
| `origin: alliance:wheelhouse…` | **declarative** (A5 would call it attestable-only at best) | `startswith` on a self-declared string (`:3444`) — provenance is not observable | **No** |
| **artifact authenticity — these bytes are the Alliance build** | **declarative, with no closure** | **none** — expected-identity + receipt are producer-only | **No** |

A5's corollary is explicit: *"no ED-36 control may be discharged solely by a producer-side
check."* Torch authorization currently is. This is the same shape as the TL finding, but
**worse in one respect**: TL was ruled a layering asymmetry because the consumer enforced the
same fact by a *stronger* mechanism (hash binding rooted in a committed file). For torch there
is no such root — the hash binds the manifest to itself.

### What would close it

Carry the authority across the boundary, not the check. Either (a) admit the torch receipt
into the bundle and hash-bind it into the acquisition manifest so the consumer re-verifies the
operator-supplied expected identity, or (b) commit the sanctioned torch identity
(sha256 + size + filename) into the repository so it becomes source-hash-bound like the
requirements export. (b) is the closer analogue of how every other artifact is rooted. Either
way the `origin` string's limitation must become **explicit in the design**, per A5.

This is a design item, not a patch. Row 6 stays **NOT COVERED** until a consumer-side
mechanism exists.

---

## Constraint compliance

Read-only throughout. No fix applied. No Tamia access. `92a12f6` not audited as a candidate.
No commit, push, or branch mutation; `r9-ed36-bundle-builder` tip observed at `92a12f6` and
unchanged. Both worktrees removed and pruned; 14 worktrees at start and end. All probes
written to scratchpad, never into a worktree.
