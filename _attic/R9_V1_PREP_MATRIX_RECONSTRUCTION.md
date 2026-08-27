# R9-DOC2 — R9-V1-PREP Matrix Reconstruction and Coverage Certification

**Author:** Mohamed El Yazid — IID
**Date:** 2026-08-05
**Scope:** Durable reconstruction of the R9-V1-PREP blocking matrix; coverage certified
against R9-V3 (REJECT, `1ed3ad9`), R9-V5 (ACCEPT, `82b028e`), R9-V6 (ACCEPT, `1aca37d`).
**Mode:** Read-only. No worktree created, no branch touched, no commit. Engineer 2's
`r9-ed36-bundle-builder` / `D:\qwen-sae-interp-r9-repair` were not accessed. Code
inspection used `git grep <commit>` and `git rev-list` against the object store only.

---

## Provenance — read this before transcribing

**The original R9-V1-PREP matrix document does not exist and was not recovered.** It was
never written; R9-V3 independently confirmed its absence across all refs, filenames, and
content. I did **not** have an R9-V1-PREP preparation record in context — this session
began at R9-V6. Nothing below is recalled from that preparation.

What follows is reconstructed from three durable repository artifacts, and each column
is labelled by which one it came from:

| Element | Source | Strength |
|---|---|---|
| **Row names (13)** | `project_management/CURRENT_PLAN.md:1387` ("R9-V1-PREP result") | **Strong** — a contemporaneous enumeration of the matrix's own spans |
| Row names (11, coarser) | `project_management/COMPLETION_LEDGER.md:295` | Corroborating — reconciles to the 13 (see below) |
| **Per-row acceptance criteria** | R9-V1 `VERIFICATION_LOG.md:2165` + R9-V2 `:2307` failing-boundary enumerations | **Moderate** — the closest surviving statement of what each row demanded, but these are the *failures found*, not the criteria *as written* |
| Coverage evidence | R9-V3 / R9-V5 / R9-V6 audit records | Strong — full documents survive |

**Consequence for the release audit:** the row *set* is trustworthy; the per-row
*criteria* are a faithful but lossy reconstruction. Any V1-PREP criterion that was
satisfied at `c847e07` and therefore never appeared in a failure list is **invisible to
this reconstruction**. This matrix is adequate to drive remaining work; it is **not**
adequate to claim "every original row is accounted for."

**Reconciliation of the two row lists.** CURRENT_PLAN's 13 is the finer grain;
COMPLETION_LEDGER's 11 merges *setup* + *pip check* into "install/pip-check" and folds
*non-overwrite* into "finalization". Same matrix, two granularities. No row is unique to
the coarser list.

---

## Immutable-identity movement (Task item 4)

R9-V1-PREP was bound to an **immutable base and a five-path scope**, and required "a
stable 40-character R9-C1 commit". Verified linear ancestry (read-only, this session):

```
4bf0fd8 (accepted integration base)
  └─ c847e07  R9-V1  REJECT   5 paths
     └─ ea65a87
        └─ 490ae73  R9-V2  REJECT   6 paths  (R9-D3 added slurm/setup_env.sh)
           └─ 1ed3ad9  R9-V3  REJECT   7 paths  (R9-D4 added the acquisition schema)
              └─ 82b028e  R9-V5  ACCEPT
                 └─ 1aca37d  R9-V6  ACCEPT
```

`git merge-base --is-ancestor 4bf0fd8 1aca37d` → true. The chain is exactly the six
candidates named in the work order, with no side branches.

**Does the movement invalidate evidence? No — it re-anchors it, with one exception.**

- **Behavioural rows re-anchor.** The criteria survive the move unchanged; only the
  commit they must be demonstrated at moves forward.
- **Scope/hash rows are superseded, legitimately.** The five-path binding is void, not
  by drift but by two ratified expansions (R9-D3 path 6, R9-D4 path 7). The governing
  scope is now the seven paths re-derived at `1aca37d` by R9-V6.
- **Two rows re-anchor by proven byte-identity, which is direct evidence, not
  inference:**
  - `slurm/setup_env.sh` = `cb0aecf3d9fd6684` at V3, V5, **and** V6 — so V3's Target-7
    setup findings hold verbatim at `1aca37d`.
  - The V3-certified builder-construction set is byte-identical at `1aca37d`: R9-V6
    independently re-derived `fee1cc1d…`, `37d1e341…`, `cec269dd…`, `e135248a…`.
- **Exception — the "seven paths" referent shifted between V3 and V5/V6.** V3's
  enumerated seven included `schemas/environment_install_manifest/v1.schema.json`
  (unchanged, `430dc16f…`) and did **not** include `tests/test_slurm_setup_env.py`.
  V5/V6's seven is the inverse. V3 itself flagged this and asked the Orchestrator for the
  authoritative list; **that request was never answered.** The two sets are reconcilable
  — V3 enumerated *authorized-to-touch*, V5/V6 enumerated *actually-changed* — but the
  reconciliation is inferred, not recorded. **Open item for the release audit.**

---

## The matrix

Verdicts are strictly against R9-V3 / R9-V5 / R9-V6. A row discharged only by R9-V1 or
R9-V2 is **NOT COVERED** here — those audits are outside the certification universe the
work order set, and both returned *Needs correction* overall. Where that is the case I
name where the row was last examined, so the release audit can decide whether to accept
the older evidence or re-run it. **No row is marked covered because a neighbour was
checked or because the full suite is green.**

| # | Row | Reconstructed criterion | Covering audit | Evidence | Verdict |
|---|---|---|---|---|---|
| 1 | **Scope** | Exact authorized path set + governing hashes at the immutable base; no unauthorized path | **V6** (also V5, V3) | V6 re-derived all seven blob hashes from committed bytes at `1aca37d`; cumulative `4bf0fd8..1aca37d` exactly seven paths, no eighth; delta exactly two files. V5 identical at `82b028e`; five hashes reproduce V5's values exactly | **COVERED** *(referent caveat above)* |
| 2 | **Derivation** | Candidate derives from the accepted integration base by a clean ancestry | — | No audit in {V3,V5,V6} proved ancestry; V6 used `4bf0fd8` as a diff base, which presupposes it. V2 confirmed ancestry at `490ae73`. **Verified read-only in this document instead** (`--is-ancestor` true; exact 6-commit linear chain) | **NOT COVERED** *(but now closable — see note)* |
| 3 | **Target capture** | Target/build-host identity, real SOABI, ordered compatible tags, exact binding to manifest target | **V3**, re-anchored by **V5+V6** | V3: SOABI from `sysconfig` with hard-fail (`:234`); tags from `packaging_tags.sys_tags()` (`:246`); order-sensitive list `!=` (`:3526`); exact field binding (`:3519-3523`). Certified adequate, marked do-not-touch. V5 Item 8 + V6 item 2: `_current_target_capture_fields`, `current_target`, `marker_environment_for_target`, `validate_target_capture_report` and block `:3518-3529` byte-unchanged at `1aca37d` | **COVERED** |
| 4 | **Tooling closure** | Builder cross-binds runtime/tooling inventory to the D4 lock; exact lock identities | — | V3/V5/V6 prove only that `environment_bundle.tooling.lock.json` is byte-stable at `4df4f6e701a7562b` across all three. None exercised tooling cross-binding *enforcement*. V2 recorded "runtime/tooling/torch cross-binding" as a remaining gap; R9-V0A (tooling evidence) was itself *Needs correction* | **NOT COVERED** |
| 5 | **Derived wheels** | Build-system contract stop conditions, isolation proof, extraction inventory, derived-record provenance | **V3 + V5 + V6** | V3: all nine `_validate_build_system_contract` branches probed live; F1–F4 raised. V5: nine branch-unique negatives via the real builder path with an accepted clean baseline; F2/F3/F4 closed; real `unshare(CLONE_NEWNET)` evidence. V6: exact-key gates on both connection attempts, validated against the **real builder emission**, plus test `:1381` executed in-container with a falsification control | **COVERED** |
| 6 | **Alliance torch** | Independent Alliance torch authorization; torch receipt cross-binding; deterministic torch negatives | — | No audit in {V3,V5,V6} raised a torch item. V1 recorded "independent Alliance torch authority" as a blocking failure; V2 recorded torch cross-binding gaps and "torch negatives" among missing direct tests. Torch tests exist and pass in the battery, but a green suite is not a row certification | **NOT COVERED** |
| 7 | **Atomic finalization** | Invocation-owned staging/rollback, recursive finalization safety, atomic no-clobber promotion, atomic manifest publication, cleanup-error preservation | — | No audit in {V3,V5,V6} targeted finalization. V1 recorded all of these as blocking, **including a Windows `PermissionError` that masked the intended environment error** and explicitly "still requires deterministic rollback/error-preservation handling". V2 still listed nested finalization/substitution and cleanup paths as untested. **No record closes the masking defect** | **NOT COVERED** |
| 8 | **Setup** (R9-D3 invariant) | No stub bypass in `setup_env.sh`; real HEAD supplied; all-zeros revision rejected before mutation | **V3**, re-anchored | V3 Target 7 PASS with specifics: no `INTERPLAB_STUB_LOG` in `setup_env.sh` (stub harness confined to `test_slurm_setup_env.py`); real HEAD via `_run_git(repo,"rev-parse","HEAD")`; all-zeros only inside the rejection test. Re-anchored by `setup_env.sh` = `cb0aecf3d9fd6684`, byte-identical V3 → V5 → V6 | **COVERED** |
| 9 | **Pip check** | Private pip snapshot genuinely executed; pip bootstrap boundary verified | — | No audit in {V3,V5,V6} exercised it. V1: "private pip snapshot execution" blocking. V2: "unexercised private pip", and pip bootstrap among missing direct tests | **NOT COVERED** |
| 10 | **Non-overwrite** | Atomic no-clobber promotion; externally supplied expected revision; no silent overwrite | — | Not examined by V3/V5/V6. Last examined at **V2**, which affirmatively passed "strict external revision authority" at `490ae73`. Lower residual risk than rows 6/7/9, but the code has moved four commits since | **NOT COVERED** |
| 11 | **3.2.1 isolation** (TransformerLens separation) | Reject TransformerLens contamination; keep 3.2.1 baseline separate from 3.4.0 comparison across all TL surfaces | — | Not examined by V3/V5/V6. Mechanism confirmed present at `1aca37d` (`_R5_X2_TRANSFORMER_LENS_BASELINE = "3.2.1"`, `_R5_X2_TRANSFORMER_LENS_COMPARISON = "3.4.0"`, `_reject_transformer_lens_contamination` at `:457`, exactly-one-requirement guard at `:2075`). V1: "TransformerLens contamination rejection" blocking. V2: **"all TransformerLens surfaces"** lack direct tests | **NOT COVERED** |
| 12 | **Regression** | Full suite green; static gates green; no silent test loss | **V3 + V5 + V6** | V3: 752 passed / 1 skipped / 3 deselected. V5: 770 / 1 / 3. V6: 772 / 1 / 3, exit 0, with the sole skip (`:1381`) converted to a real in-container PASS. Exact CI Ruff, `uv lock --check` (196 pkgs), `bash -n` ×6, `git diff --check` green at all three. Counts reconcile exactly: 752 → +18 (V5) → +2 (V6) | **COVERED** |
| 13 | **Retained state** | Retained tooling-evidence root unchanged by the audit | — | V3/V5/V6 assert read-only conduct and clean *repository* status, and V6 confirmed no tracked file was touched. None affirmatively re-verified the retained evidence root outside the repository. V1 passed "clean retained state" at `c847e07` | **NOT COVERED** |

**Obsolete criteria — declared, not dropped.** No whole row is obsolete. One sub-criterion is:

| Superseded criterion | Superseded by | Reason |
|---|---|---|
| Under **row 5**: that a derived wheel's PEP 517 build requirements be declared *literally* `==` | **R9-A3** (Option 2, "Complete") | R9-V2 routed this exact ambiguity to the Architect. A3 ruled that compatible PEP 508 **ranges may map to the sole exact locked artifact**; the sdist hash remains export-authorized and the wheel is authorized only by its complete derived record. A V1-PREP row demanding literal `==` is void and must not be re-imposed at the release audit |

Also formally superseded, per item 4 above: the **five-path scope binding** in every row
that carried one, replaced by the ratified seven-path scope (R9-D3, R9-D4).

---

## NOT COVERED rows, in priority order

1. **Row 11 — TransformerLens 3.2.1 separation.** Highest. It is a *scientific
   contamination* boundary, not a mechanical one; V2 found **all** TL surfaces untested;
   the enforcement code exists at `1aca37d` but no audit has ever exercised it.
2. **Row 7 — Atomic finalization / rollback.** Carries the only known *unclosed concrete
   defect* in this list: V1's Windows `PermissionError` masking the intended environment
   error. Nothing since records it as fixed.
3. **Row 6 — Alliance torch authorization.** Blocking at V1, cross-binding gaps at V2,
   untouched by three subsequent audits.
4. **Row 9 — Pip check / private pip snapshot.** Blocking at V1, explicitly "unexercised"
   at V2.
5. **Row 4 — Tooling closure cross-binding.** Lock bytes are stable, but enforcement is
   uncertified and the upstream tooling evidence (R9-V0A) is itself *Needs correction*.
6. **Row 13 — Retained state.** Cheap to close: hash the retained evidence root and
   compare to the V1-era record.
7. **Row 10 — Non-overwrite / external revision.** Affirmatively **passed at V2**; needs
   re-anchoring to `1aca37d`, not fresh discovery.
8. **Row 2 — Derivation.** Effectively closed — ancestry verified read-only in this
   document. It needs only transcription into `VERIFICATION_LOG.md` to become covered;
   I have left it NOT COVERED because the verification is mine, not V3/V5/V6's.

**Coverage summary: 5 of 13 COVERED (rows 1, 3, 5, 8, 12); 8 NOT COVERED; 0 obsolete
rows; 1 obsolete sub-criterion.**

The five covered rows are precisely the schema/validator/regression surface the V3→V6
chain was scoped to audit. The eight uncovered rows are the builder's **runtime
behaviours** — torch, finalization, pip, tooling cross-binding, TL separation, retained
state. That is the expected shape given each audit's charter, not a new defect; but it
means **the ED-36 builder has never been certified end-to-end by any single audit**, and
the release audit must treat rows 4, 6, 7, 9, 11 as first-time work rather than re-checks.

---

## Carried forward, unchanged by this exercise

- **R9-SCHEMA-ENFORCEMENT-GAP** remains a *pre-first-write blocking condition*: the
  acquisition schema is enforced on no production read path (`environment_bundle.py`
  never imports the schema registry) — re-confirmed at `1aca37d` by R9-V6.
- The **authoritative seven-path list** requested by R9-V3 was never supplied; see the
  V3/V5 referent divergence above.
