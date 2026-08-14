# R9-V11 — Integration Candidate Audit (Byte-Identity Gate)

**Auditor:** Interlab persistent auditor
**Date:** 2026-08-05
**Candidate:** `664eda935757d1d2cf2cb332454532632d7da133` on branch `r9-integration`
**Base:** `origin/main` = `9d90ef601822c1cacad0b6aade8a1a265f2b0e39`
**Accepted source:** `a9a174f` (R9-V10)
**Worktree:** `D:\qwen-sae-interp-r9-v11-audit-664eda9`, own fresh detached LF-faithful checkout; removed and pruned at end

**Scope of this audit:** integration fidelity only. `a9a174f`'s content is accepted and closed at R9-V10 and was not re-audited.

## Verdict: **Accepted for exact 664eda9**

### The seven blob hashes (recomputed independently at `664eda9`)

| Path | sha256 | vs R9-V10 |
|---|---|---|
| `interplab/core/environment_bundle.py` | `37881566694791a9cb71661538e50c78a72e7036da0876ebf19eb44d80f9f3f6` | **MATCH** |
| `schemas/environment_acquisition_manifest/v1.schema.json` | `f60fff8d031215ef544f43de9eb2a4b4a44568f663562781f124debeaf0c644b` | **MATCH** |
| `slurm/environment_bundle.tooling.lock.json` | `4df4f6e701a7562b903ed21e70b2439e152b7cf99b2119b2c2cb981cf4507b0e` | **MATCH** |
| `slurm/setup_env.sh` | `cb0aecf3d9fd6684258fbbe691ec0accb4c0f1b1244ab44f33dbaf297799386a` | **MATCH** |
| `tests/test_environment_bundle.py` | `7dddb2ed6efce57afb5228787e861b8403a426b784aa06bbe47cb76ecdeab28f` | **MATCH** |
| `tests/test_environment_bundle_builder.py` | `543491f58fbb9e798caee89f74198ac97a91d43f89ca8738139bc6507801e049` | **MATCH** |
| `tests/test_slurm_setup_env.py` | `a81d12f31344bce0d0bf2cf87db440060e56cbccd19aac444c3f4fb5f7e4c35c` | **MATCH** |

All seven equal my own R9-V10 values exactly.

**Stronger than content equality — the same git objects.** Each of the seven resolves to an *identical blob object ID* at `a9a174f` and `664eda9` (`28ab398c7eb0`, `692317f192e1`, `69f18e821ded`, `12cb180f189c`, `996de5cd91c7`, `8a189d640691`, `1bd3c084e133`). The replay did not re-create these blobs; it reuses them. Byte identity is therefore structural, not coincidental.

**No CRLF drift.** Working-tree bytes equal blob bytes for all seven in my LF-faithful checkout.

---

## 1. Ancestry — PASS

- **Merge-base** of `a9a174f` and `9d90ef6` = `4bf0fd88f129549569ca3353ccef965a93b51395` — exactly `4bf0fd8`.
- **Chain is nine commits**, each with **exactly one parent**, in the specified order:

```
9d90ef6 -> 1e381c4 -> 2912f0a -> 44235eb -> f696254 -> ac02fcc
        -> b6ef67d -> b1629b6 -> 066c2bb -> 664eda9
```

- **Merge commits in range: 0.** No squash (9 in, 9 out), no reordering.

**One-to-one with the original nine, proved by patch-id.** Every pair has an identical `git patch-id --stable` *and* an identical subject line:

| Original | Replayed | patch-id | |
|---|---|---|---|
| `c847e07` | `1e381c4` | `ef3775421839` | patch SAME · subject SAME |
| `ea65a87` | `2912f0a` | `470ed6768201` | patch SAME · subject SAME |
| `490ae73` | `44235eb` | `739db3a5e58c` | patch SAME · subject SAME |
| `1ed3ad9` | `f696254` | `7965079e25d8` | patch SAME · subject SAME |
| `82b028e` | `ac02fcc` | `2c78d051b1d0` | patch SAME · subject SAME |
| `1aca37d` | `b6ef67d` | `053629bd698e` | patch SAME · subject SAME |
| `70c6d25` | `b1629b6` | `638646621beb` | patch SAME · subject SAME |
| `92a12f6` | `066c2bb` | `031c4bf834d0` | patch SAME · subject SAME |
| `a9a174f` | `664eda9` | `ebab3867f852` | patch SAME · subject SAME |

## 2. Byte identity — PASS

See the hash table above. This is the acceptance criterion and it is met exactly.

## 3. Scope — PASS

`git diff --name-only 9d90ef6 664eda9` returns **exactly seven paths** — the authorized set. **No eighth path.**

**Stricter check, beyond the brief.** An intermediate commit could touch an eighth path and revert it later, which an endpoint diff would hide. I therefore took the **union of paths touched by every one of the nine commits individually**: it is also **exactly seven**. No path outside the authorized set was touched at any point during the replay, even transiently.

## 4. R10 overlay survived — PASS

Byte-identical to `9d90ef6`:

| Path | base | candidate | |
|---|---|---|---|
| `slurm/launch_census.sh` | `f689698cc8428ec19e5f81d0` | `f689698cc8428ec19e5f81d0` | **IDENTICAL** |
| `docs/ablation_9056_spec.md` | `8288fa62cc85363aadf7aa2b` | `8288fa62cc85363aadf7aa2b` | **IDENTICAL** |

More generally: of 293 tracked files at the candidate, exactly 7 differ from the R10 base, so the entire R10 overlay is preserved by construction — the specific risk of replaying onto a moved base did not materialize.

## 5. Full suite — PASS

```
795 passed, 1 skipped, 3 deselected, 44 warnings in 252.30s (0:04:12)   EXIT=0
```

**795 passed / 3 deselected as required, with 1 skip — the Docker-available branch.**

**Skip line re-derived independently.** The surviving skip is `tests/test_environment_bundle_builder.py:1657` — I located it myself: the `@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="the direct child-source boundary requires a Linux /proc namespace host")` decorator sits at **line 1657**, with `def test_build_no_network_child_source_blocks_socket_dns_and_python_subprocess` at 1658. Confirmed **not** :1381, which was stale from before R9-C10.

**Host capability stated explicitly.** Docker **is** available here — 28.5.1, `desktop-linux` context, local `python:3.11-slim-bookworm` (`sha256:d29f48a31a8b…`). I verified separately that `test_real_linux_namespace_isolation_evidence_uses_unshare_and_no_network_in_docker` **runs and passes** (1.48s) rather than skipping. That is the 795/1 branch, not 794/2. The single remaining skip is the Linux-`/proc`-gated test at :1657, which always skips on win32 regardless of Docker.

## 6. Static gates — PASS

| Gate | Result |
|---|---|
| Exact CI Ruff (`ci.yml:28`: `interplab tests scripts/*.py data/concepts/*.py`) | **All checks passed** |
| `uv lock --check` | **Pass** — 196 packages |
| `bash -n` on all seven shell scripts | **All OK** |
| `git diff --check 9d90ef6 664eda9` | **Clean** |
| `git status --porcelain` | **Clean** (empty) |

*Wording note, not a defect:* the brief says "all SEVEN launchers". The tree contains **six** `slurm/launch_*.sh` (`census`, `certify`, `characterize`, `steer`, `train`, `validate`) plus `slurm/setup_env.sh` — seven shell scripts total. I ran `bash -n` on all seven; `launch_census.sh` is indeed present via the R10 base, as expected.

## Environment note

Repo-local `core.autocrlf` is `false` and global is unset, as the brief states. I passed `-c core.autocrlf=false` explicitly anyway and additionally re-read the index and re-checked out the tree, then verified LF fidelity (`configs/certify/hm03l7yz.yaml` worktree hash == blob hash == `6dfb9e35d5f17917`). The in-source repo-root assertion convention was retained; no probe read from stale main.

*Path correction:* the brief gives the Engineer's worktree as `D:\qwen-sae-integration-r9-integration`. Per `git worktree list` the actual path is **`D:\qwen-sae-interp-r9-integration`**. I did not touch it.

## Worktree state

- **Start: 15. End: 15.** I created `D:\qwen-sae-interp-r9-v11-audit-664eda9`, used it read-only, then removed and pruned it, returning the count to its starting value with the same set of entries.
- **Untouched as required:** `D:\qwen-sae-interp-r9-repair` remains at `a9a174f`; branch `r9-ed36-bundle-builder` = `a9a174f3bb8dc6dc343fef6158323dececb2c0a7`; `D:\qwen-sae-interp` remains stale main `c6ef2df5bb38791a26e4e9490243f327dc6aeb85`; `D:\qwen-sae-interp-r9-integration` (Engineer's) untouched at `664eda9`.
- Branch `r9-integration` = `664eda935757d1d2cf2cb332454532632d7da133`, unmoved.

Read-only throughout: no commit, no push, no branch mutation, no writes into any worktree.
