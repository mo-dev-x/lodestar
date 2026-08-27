# R9-V8 — TransformerLens Separation, First-Time Certification (matrix row 11)

**Author:** Mohamed El Yazid — IID
**Date:** 2026-08-05
**Audit commit:** `1aca37d8e437125e70ba793a4882b5aac9760f66` (accepted at R9-V6)
**Worktree:** `D:\qwen-sae-interp-r9-v8-audit-1aca37d8`, fresh, detached, `core.autocrlf=false`;
removed and pruned. 14 worktrees at start, **14 at end**. `git status --porcelain
--untracked-files=no` empty — no tracked file touched. Engineer 2's branch tip
`r9-ed36-bundle-builder` = `1aca37d8…`, unmoved; `D:\qwen-sae-interp-r9-repair` never accessed.

**No container and no dependency staging were used.** This audit is pure host-local Python
over the committed bytes, so the R9-V6 networked-staging caveat does not arise here.

## Verdict: row 11 **COVERED** — with one MAJOR coverage defect (V8-F1)

The separation contract is real, it fails closed on every contamination attempt I could
construct, and no ordering bypass exists. What is **not** protected is its future: two of
the three raise-branches of the central gate have no deterministic negative test.

---

## 1. What the contract actually is

Two module constants fix it (`interplab/core/environment_bundle.py:67-68`):

```python
_R5_X2_TRANSFORMER_LENS_BASELINE = "3.2.1"
_R5_X2_TRANSFORMER_LENS_COMPARISON = "3.4.0"
```

**Admitted: exactly `transformer-lens==3.2.1`. Forbidden: `3.4.0`** — everywhere except one
place, the equivalence report's `comparison.candidate_transformer_lens` field
(`:3189-3192`), which is precisely where 3.4.0 is *supposed* to appear as the compared-against
candidate. That asymmetry is the whole point of the row: 3.4.0 may be *reported on*, never
*installed*.

The gate (`:457-479`), quoted in full because its three branches matter separately:

```python
def _reject_transformer_lens_contamination(entries, *, context, require_exact_runtime=False):
    versions = [...]                                             # entries whose distribution normalizes to transformer-lens
    if any(version == _R5_X2_TRANSFORMER_LENS_COMPARISON for version in versions):
        raise EnvironmentBundleError(f"{context} contains forbidden transformer-lens 3.4.0")     # branch 1
    if any(version != _R5_X2_TRANSFORMER_LENS_BASELINE for version in versions):
        raise EnvironmentBundleError(f"{context} contains an unexpected transformer-lens version: {versions!r}")  # branch 2
    if require_exact_runtime and versions != [_R5_X2_TRANSFORMER_LENS_BASELINE]:
        raise EnvironmentBundleError(f"{context} must contain exactly one transformer-lens==3.2.1 artifact")      # branch 3
```

On mismatch: `EnvironmentBundleError`. Branches 1 and 2 are **unconditional**; branch 3 fires
only when `require_exact_runtime` is set, which every caller derives from
`source_hashes == _real_repo_source_hashes()` — the real-repo-versus-synthetic split.

**All eight enforcement sites**, each mapped to its enclosing function by AST (not by
eyeball):

| Site | Enclosing function | `require_exact_runtime` |
|---|---|---|
| `:1795` | `_build_derived_runtime_wheel` | default `False` |
| `:2073` | `build_runtime_bundle` — *inline*, not the gate: export selection must be exactly `[3.2.1]` | n/a (real-repo gated) |
| `:2089` | `build_runtime_bundle` (tooling lock artifacts) | default `False` |
| `:2154` | `build_runtime_bundle` (runtime staging) | real-repo gated |
| `:2221` | `validate_runtime_stage_receipt` (tooling) | default `False` |
| `:2225` | `validate_runtime_stage_receipt` (runtime) | real-repo gated |
| `:2400` | `finalize_bundle` (tooling) | default `False` |
| `:2401` | `finalize_bundle` (runtime) | real-repo gated |

The `False` sites are the tooling/build contexts, where TL must be **absent**; the real-repo
sites are the runtime contexts, where it must be **present exactly once**. That split is
coherent, not an oversight.

The second, independent source of truth is `slurm/requirements.cluster.txt:2175`:

```
transformer-lens==3.2.1 \
```

— and `source_hashes_for_root` (`:215-230`) hashes that exact file as `cluster_requirements`,
alongside `pyproject.toml` and `uv.lock`. So the pin cannot be swapped without breaking
`_validate_source_hashes` (`:285-287`), which **raises**.

---

## 2. Does it fail closed? Yes — both paths

### Producer path — the gate itself

Accepted clean baseline first, so every rejection is attributable to its single mutation:

| Contamination attempt | `exact=False` | `exact=True` |
|---|---|---|
| `[]` — neither present | ADMITTED *(correct: tooling contexts must not contain TL)* | **rejected** — *must contain exactly one …* |
| `3.2.1` only | ADMITTED *(baseline)* | ADMITTED *(baseline)* |
| **`3.4.0` only** | **rejected** — *contains forbidden transformer-lens 3.4.0* | **rejected** |
| **both `3.2.1` + `3.4.0`** | **rejected** — *forbidden … 3.4.0* | **rejected** |
| duplicate `3.2.1` ×2 | ADMITTED | **rejected** — *must contain exactly one …* |
| unrelated version `3.9.9` | **rejected** — *unexpected transformer-lens version* | **rejected** |
| prerelease `3.2.1rc1` | **rejected** — *unexpected transformer-lens version* | **rejected** |

Malformed entries all fail closed: missing `distribution` → *distribution names must be
non-empty*; missing/`None`/empty `version` → *must be a non-empty string*; `"3.40"` →
*unexpected transformer-lens version*.

Name normalization (`:130-134`, `re.sub(r"[-_.]+","-",…).lower()`) catches every real alias —
`transformer_lens`, `Transformer_Lens`, `TRANSFORMER-LENS`, `transformer.lens`,
`transformer--lens`, surrounding whitespace. It does not match `transformerlens` or
`transformer-lens-extra`, but those are *different distributions*, not aliases of the real
one; PEP 503 normalization of `transformer-lens` is `transformer-lens`. **Informational, not
a defect.**

### Consumer path — carried by cross-binding, not by the gate

Using the **real** `requirements.cluster.txt` bytes (parsed: `transformer-lens`, version
`3.2.1`, 2 authorized hashes), against `_validate_runtime_manifest` (`:3319`):

| Contamination attempt | Result |
|---|---|
| declared `3.2.1`, authorized hash | **ADMITTED** *(clean baseline)* |
| **`3.4.0` where `3.2.1` required** | **rejected** — *runtime version mismatch for 'transformer-lens': expected 3.2.1, got 3.4.0* (`:3363-3366`) |
| neither present (TL absent) | **rejected** — *runtime artifacts must not be empty* / *incomplete non-torch runtime closure: missing transformer-lens* |
| both `3.2.1` and `3.4.0` | **rejected** — *normalized duplicate distribution 'transformer-lens'* |
| version-shaped string, unauthorized hash | **rejected** — *runtime hash mismatch … not authorized by the export* (`:3382-3385`) |
| alias name `transformer_lens` in a manifest | **rejected** — *must be a normalized distribution name* (`:4444`) |

The chain closes to the live environment: `_installed_distributions()` (`:4853`) enumerates
real `importlib.metadata.distributions()`, and `_validate_install_manifest_consistency`
(`:3015+`) compares those against the manifest runtime entries with **exact version
equality**. So: real repo bytes → pinned export → acquisition manifest → install manifest →
actually-installed distributions, each link exact.

---

## 3. Ordering / bypass — no bypass, but a real structural asymmetry

Transitive call-graph analysis for reachability of `_reject_transformer_lens_contamination`:

| Function | Reaches TL gate | Reaches version cross-bind |
|---|---|---|
| `load_acquisition_manifest` | **False** | False |
| `validate_acquisition_manifest` | **False** | False |
| `_validate_acquisition_manifest_semantics` | **False** | True |
| `_validate_install_manifest_consistency` | **False** | True |
| `validate_bundle` | **False** | True |
| `certification_environment_inputs` | **False** | True |
| `build_runtime_bundle` | True | False |
| `finalize_bundle` | True | True |
| `validate_runtime_stage_receipt` | True | False |

**The TL-specific gate is unreachable from every consumer function.** It is a producer-side
control only. This mirrors, and compounds, the already-recorded finding that the acquisition
schema is applied on no production read path.

It is **not** a bypass, because the consumer path enforces the same fact by exact
version + hash binding rooted in a source-hash-bound file, as demonstrated above. But
defence-in-depth is **single-layered on the consumer side**: the TL constant `3.2.1` and the
export pin `3.2.1` are two independent statements of one fact, and on the consumer path only
the export governs. Producer-side, the gate is the backstop that would catch an export
regenerated with 3.4.0 — and a bundle can only be consumed if it was first built, so the
chain does close.

**No path reaches TL usage without passing a gate**, and no import ordering issue exists —
see §4.

---

## 4. Pre/post-activation split — **does not apply here**

Reported as asked. The R9-C7 constraint does **not** transfer to row 11:

- `environment_bundle.py` contains **no import of `transformer_lens`** in any form (no
  `import`, no `import_module`, no `importlib` reference). Verified empirically: after
  importing the module, `[m for m in sys.modules if "transformer" in m.lower()]` is **empty**.
- The gate is pure stdlib logic — `dict.get`, string compare, `re.sub`. It inspects **declared
  manifest metadata**, never an installed distribution.

Therefore it faces no stdlib-only constraint and is structurally able to run at any point,
pre- or post-activation. **This is not an R9-A4-adjacent finding.**

The corollary is worth recording, though: because the gate is purely declarative, a manifest
declaring `3.2.1` is admitted **regardless of what is actually installed** — confirmed
directly (declared 3.2.1 with the gate alone → ADMITTED). That check is not the gate's job;
it is carried by `_installed_distributions()` real introspection in the install manifest, as
established in §2. The two halves together are sufficient; neither alone is.

---

## V8-F1 — MAJOR. Two of three gate branches, and five of eight call sites, have no test

R9-V2's "all TransformerLens surfaces are untested" is **outdated** — TL tests now exist and
all pass at `1aca37d` (11 passed, 21.87s):

`test_build_runtime_bundle_rejects_transformer_lens_comparison_in_tooling_lock` (:1964),
`test_finalize_bundle_rejects_transformer_lens_comparison_in_runtime_stage` (:1995),
`test_finalize_bundle_rejects_transformer_lens_comparison_in_tooling_stage` (:2014), plus the
four equivalence-report tests (`test_environment_bundle.py:1773/1818/1849`,
`test_jobs_certify.py:349`).

But every one of them exercises **branch 1 only**. Assertion counts across `tests/*.py`:

| Raise branch / context | Test assertions |
|---|---|
| branch 1 — `contains forbidden transformer-lens 3.4.0` | **3** |
| **branch 2 — `contains an unexpected transformer-lens version`** | **0** |
| **branch 3 — `must contain exactly one transformer-lens==3.2.1 artifact`** | **0** |
| context `build inputs` (`:1795`) | **0** |
| context `runtime staging runtime` (`:2154`) | **0** |
| context `runtime stage.tooling` / `runtime stage.runtime` (`:2221`/`:2225`) | **0** |
| context `acquisition manifest.tooling` / `.runtime` (`:2400`/`:2401`) | **0** |
| consumer-path TL version rejection | **0** |

**This is a coverage defect, not a correctness defect** — I proved all three branches fire
correctly (§2). It is the same finding class as R9-V3's F1, which was ruled BLOCKING under
R9-D4 §4's "deterministic negative test per stop condition". Branch 3 is the one that guards
*duplicate 3.2.1* and *TL entirely absent* in real-repo runs; branch 2 guards every version
that is neither 3.2.1 nor 3.4.0 — including a future TL 4.x, the most likely real-world drift.

### Deterministic reproduction

```python
import sys; sys.path.insert(0, r"<worktree at 1aca37d>")
from interplab.core import environment_bundle as b

E = lambda v: {"distribution": "transformer-lens", "version": v}

# branch 2 — fires, but no test asserts it:
b._reject_transformer_lens_contamination([E("4.0.0")], context="probe")
# EnvironmentBundleError: probe contains an unexpected transformer-lens version: ['4.0.0']

# branch 3 — fires, but no test asserts it:
b._reject_transformer_lens_contamination([E("3.2.1"), E("3.2.1")],
                                         context="probe", require_exact_runtime=True)
# EnvironmentBundleError: probe must contain exactly one transformer-lens==3.2.1 artifact
```

Confirm the gap: `grep -rc "unexpected transformer-lens version" tests/*.py` → 0;
`grep -rc "must contain exactly one transformer-lens" tests/*.py` → 0.

### Required to close

1. One deterministic negative per uncovered branch (2 tests minimum: an unexpected version;
   a duplicate-3.2.1 under `require_exact_runtime=True`).
2. One consumer-path negative asserting TL 3.4.0 is rejected by `_validate_runtime_manifest`,
   so the contract is regression-protected where the TL gate does not reach.
3. Optional but cheap: cover the `:1795` build-inputs site, the only enforcement site with no
   test of any kind.

---

## Constraint compliance

Read-only. No commit, no push, no branch mutation, no network, no container, no Tamia, no
bundle or venv construction. All probes written to scratchpad, never into the worktree; each
pinned `sys.path` to the audit worktree and asserted `__file__`. Accepted rows were not
re-audited. Worktree removed and pruned; residual empty directory deleted.
