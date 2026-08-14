# R11-V1 — Prose Correction Acceptance (hash-bound)

**Author:** Mohamed El Yazid — IID
**Date:** 2026-08-06
**Candidate:** working files in `D:\qwen-sae-interp\reports\` — **no commit SHA exists**
(`reports/` is gitignored at `.gitignore:45` and untracked). Acceptance is hash-bound per the
**R6-V5B precedent** for untracked candidates.
**Reference snapshot:** `D:\interlab_evidence\r11_c00_20260804\` (`pre/`, `post/`, `post_a/`)
**Mode:** Read-only. No worktree created (it would materialize none of these files). No edit,
no commit, no staging.

## Verdict: **Accepted (hash-bound)**

### Final SHA-256 — recomputed independently from the working files

| File | SHA-256 |
|---|---|
| `reports/internship_report.md` | `d9dc88b1f9b2cfeb261a2b583815f7163a81e52f5aa57dd58f380789bbc76db7` |
| `reports/presentation/internship_report.md` | `e17ce6f6ec85443835546e781a43d5a6d46670be0999073e488578ce3e879591` |
| `reports/presentation/script_oral_detaille_interlab_lodestar.md` | `e526e8c845a23954e3d54b0135fcaa5dff174816cf07ce354510ff5e6c2b3c6c` |
| `reports/presentation/fiche_revision_composantes_scientifiques.md` | `7f16f089f57958265018083642337e60b3007b6a75c3f27840ba851423fe48c2` |

Each working file equals its **final** snapshot byte-for-byte: `post/` for the three files
untouched by the amendment, `post_a/` for the fiche (the only file the R11-C00-A amendment
re-wrote — `post_a/` contains that file and nothing else). Pre-state hashes for the record:
`f2be5ad0…`, `5e84e85f…`, `5ba7da9a…`, `92684f6d…`.

**Independence.** Every hash above was recomputed from bytes. Every diff was re-derived with
`diff` against `pre/`. I did not read `r11_c00_a.diff`, `r11_c00.diff`, the cumulative
`r11_c00_fiche_full_pre_to_post_a.diff`, `occurrence_table.txt`, or the recorded
`pre_existing_divergences.diff` — the two criteria corrections in the work order are both
confirmed from first principles below.

---

## Nine sites — independently re-derived, and nothing else changed

Changed line numbers, derived by line-level diff `pre/` → working:

| File | Changed lines | Expected |
|---|---|---|
| `reports/internship_report.md` | **92, 398, 470, 529** | ✅ |
| `reports/presentation/internship_report.md` | **92, 398, 470, 529** | ✅ |
| `.../script_oral_detaille_interlab_lodestar.md` | **171, 457** | ✅ |
| `.../fiche_revision_composantes_scientifiques.md` | **685, 690, 698** | ✅ |

Nine distinct sites (the four report lines counted once, applied identically to both copies);
**no other line in any of the four files differs from `pre/`.** Line 685 is the R11-C00-A
amendment and is present.

### What each site now says

- **92** — "The judge's own repeatability" → "The judge's **repeat-judgment agreement**";
  "its reliability statistics" → "its **determinism-check** statistics"; "no real-judge
  reliability estimate" → "no real-judge **determinism-check** estimate"; plus an appended
  temperature-0 sentence. The quoted log phrase *"Lodestar judge reliability confirmed"* is
  retained **because the sentence exists to debunk it** ("a statement about analysis grouping,
  not about the judge").
- **398** — "repeat-judging self-consistency validation" → "repeat-judging **determinism check**".
- **470** — inserts "because the judge runs at temperature 0, this is near-deterministic repeat
  agreement under fixed settings, a determinism check rather than judge reliability, stability,
  or validated repeatability".
- **529** — appends the same framing to the evidence-table cell.
- **171** (fr) — replaces the bare "ça montre que le juge est cohérent avec lui-même" with the
  temperature-0 determinism framing, retaining the human-correlation denial.
- **457** (fr) — "Lodestar est validé en self-consistency" → "**n'est pas validé au sens de la
  fiabilité ou d'une répétabilité validée**".
- **685** (fr, amendment) — "le juge est stable avec lui-même" → determinism framing,
  "**pas une preuve que le juge est stable ou fiable**".
- **690** (fr) — "Krippendorff alpha valide la repeatability du juge" → determinism framing.
- **698** (fr) — "Mesure la stabilité des scores numériques" → determinism framing.

---

## Criterion correction 1 — encoding unchanged **per file**, not "all four no-BOM"

Confirmed from bytes; the superseded criterion is correctly void.

| File | First 3 bytes pre | First 3 bytes post | State | Verdict |
|---|---|---|---|---|
| `internship_report.md` (root) | `23 20 52` | `23 20 52` | no-BOM | **UNCHANGED** |
| `presentation/internship_report.md` | `23 20 52` | `23 20 52` | no-BOM | **UNCHANGED** |
| `script_oral…md` | `23 20 53` | `23 20 53` | no-BOM | **UNCHANGED** |
| `fiche…md` | `ef bb bf` | `ef bb bf` | **genuine pre-existing BOM** | **UNCHANGED** |

The fiche's BOM is pre-existing and was correctly preserved. **It is not flagged as a defect.**

Line endings are part of encoding and are also unchanged: CR-byte counts pre → post are
`0 → 0`, `0 → 0`, `0 → 0`, and **`1346 → 1346`** — the fiche is CRLF throughout, pre and post.
All four files remain valid UTF-8. Line counts are identical pre → post: 560, 560, 489, and
**fiche 1346** as required. Byte growth is confined to the inserted text
(95529→96167, 95438→96076, 43565→43936, 44525→44982).

## Criterion correction 2 — the 14 divergences, re-derived from `pre/`

Derived by diffing the two `pre/` copies against each other, without consulting the recorded
list:

```
37 71 145 148 160 194 206 209 229 292 358 385 394 409     (14 lines)
```

This matches the corrected criterion exactly. Re-deriving the same set from the two **working**
copies yields an **identical set** — the divergences are untouched. All 28 divergent content
lines (14 pairs) carry markdown image syntax; **zero** divergent lines are non-image
(`../reports/pics/…` vs `../diagrams/…`, `../results/report_assets/…` vs `../figures/…`).

---

## Verification results

| Check | Result |
|---|---|
| All nine sites corrected | **PASS** — re-derived, exactly nine, nothing else changed |
| Four target lines byte-identical across both report copies | **PASS** — per-line SHA-256 equal at 92 (`da73d518…`), 398 (`52d24dca…`), 470 (`a1149147…`), 529 (`faf84df9…`) |
| Excluded sites unchanged | **PASS** — report 282/376/490 (both copies), script_oral 163/347/377/477, fiche 896/1243 all byte-identical to `pre/` |
| fiche §45 supporting lines 604, 674–681, 739–740 | **PASS — unchanged, and confirmed already correct, not missed.** 739 reads *"Ne pas citer ces statistiques comme preuve de fiabilité du juge."*; 740 *"Pas de fiabilité réelle mesurée…"*; 604 *"Self-consistency élevée ne prouve pas accord humain."*; 674–681 are the section header and neutral factual statements |
| Hedges at 470 preserved verbatim | **PASS** — both hedge sentences byte-present pre and post, **including the mock-judge exclusion**; line 470 is a **pure insertion** (pre text is a subsequence of post) |
| 529 HIGH/ABSENT structured labels | **PASS** — `\| HIGH (self-consistency) / ABSENT (human correlation) \|` unchanged; 529 is also a pure insertion |
| Numeric α / ICC / κ and the 0.983–0.998 range | **PASS** — token multisets identical pre vs post in all four files (15/15, 15/15, 4/4, 9/9) |
| `results/lodestar_*/reliability.csv` pointers | **PASS** — 2 in each report copy, unchanged; 0 in the French files, unchanged |
| Prohibited framing absent | **PASS** — see sweep below |
| French spells "Krippendorff alpha" in words | **PASS** — `U+03B1` occurrences in both French files: **0**; "Krippendorff alpha" ×2 (script_oral), ×3 (fiche); no other Krippendorff form |
| `git status --porcelain` unchanged | **PASS** — identical to `git_status_before.txt` / `git_status_after_a.txt` |
| Nothing under `reports/` in the index | **PASS** — 0 staged files overall; 0 tracked and 0 staged under `reports/` |

### Prohibited-framing sweep — every occurrence classified

No affirmative claim of judge reliability, stability, or validated repeatability survives in
any of the four files. Every hit falls into one of four safe categories:

**English** (identical hit sets in both copies — lines 92, 282, 364, 470, 490, 494, 529):

- *Explicit negation* (approved per the R11-D1A wording): "…a determinism check, **not** judge
  reliability, stability, or validated repeatability" — 92, 470, 529.
- *Preserved hedges / absence claims*: "a judge that is systematically biased but reliably so
  would pass this check unchanged"; "**no** reliability estimate exists at all for heavily
  degenerate extreme-scale text"; "the instrument's stability … is simply **unmeasured**" — 470.
- *Quoted phrase under rebuttal*: `"Lodestar judge reliability confirmed"` — 92.
- *Evidence pointer*: `results/lodestar_*/reliability.csv` — 92, 529 (required to remain).
- *Not about the judge*: 282 (steering behaviour base vs instruct), 364 (ED-27 checkpoint
  identity "stay stable across a training restart"), 490 (SAE transfer), 494 ("a stable
  obsessed-but-readable regime" — generation regime).

**French** (script_oral 67/117/143/163/171/263/277/279/311/327/347/377/457/477; fiche
685/690/698/739/740/844/896/1195/1243):

- *Explicit negation*: 171, 457, 685, 690, 698 — and 896 ("pas la fiabilité intrinsèque du juge").
- *Prohibition guards / absence claims*: 739, 740.
- *Not about the judge*: 263/277/327 (feature-candidate selection), 347/377/477/1243
  (generation regime), 163 (describes the pre-Lodestar practice being replaced).
- *Substring false positives*: `vérifiable` (67), `certifiables` (117), `auditables`/`vérifiables`
  (143), `falsifiable` (279, 311, 1195), `planifiables` (844).

---

## Constraint compliance

Read-only throughout. No worktree created. No file edited, no commit, no push, nothing staged.
Working tree state at the end is byte-identical to the recorded post-amendment state, and the
index is empty — the staged-report stop condition was not triggered.
