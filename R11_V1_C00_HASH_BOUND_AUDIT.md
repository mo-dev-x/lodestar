# R11-V1 AMENDED — Hash-Bound Audit of R11-C00 / R11-C00-A

**Auditor:** Interlab persistent auditor
**Date:** 2026-08-04
**Subject:** Working files at `D:\qwen-sae-interp` vs immutable snapshot `D:\interlab_evidence\r11_c00_20260804\`
**Mode:** Read-only, hash-bound. No commit SHA exists (`reports/` is gitignored and untracked). No worktree created.

## Verdict: **Accepted (hash-bound)**

### The four final SHA-256 values (recomputed independently)

| File | SHA-256 |
|---|---|
| `reports/internship_report.md` | `d9dc88b1f9b2cfeb261a2b583815f7163a81e52f5aa57dd58f380789bbc76db7` |
| `reports/presentation/internship_report.md` | `e17ce6f6ec85443835546e781a43d5a6d46670be0999073e488578ce3e879591` |
| `reports/presentation/fiche_revision_composantes_scientifiques.md` | `7f16f089f57958265018083642337e60b3007b6a75c3f27840ba851423fe48c2` |
| `reports/presentation/script_oral_detaille_interlab_lodestar.md` | `e526e8c845a23954e3d54b0135fcaa5dff174816cf07ce354510ff5e6c2b3c6c` |

Three match `post/`; the fiche matches **`post_a/`** (`7f16f089…`), **not** `post/` (`71971fe2…`) — confirming the R11-C00-A amendment is the live state. `post → post_a` delta is exactly one hunk at fiche **L685**.

---

## Nine sites — all corrected

Every hunk is a 1-for-1 line replacement; line counts are unchanged in all four files (560 / 560 / 1346 / 489), so line numbers are stable and no content was inserted or deleted at file level.

| # | File | Line | Nature |
|---|---|---|---|
| 1–4 | `internship_report.md` (**both copies**) | 92, 398, 470, 529 | reliability→determinism-check reframing |
| 5 | `fiche` | **685** | **R11-C00-A** — "le juge est stable avec lui-même" → determinism-check framing |
| 6 | `fiche` | 690 | "valide la repeatability" → determinism check |
| 7 | `fiche` | 698 | "Mesure la stabilité" → determinism check |
| 8 | `script_oral` | 171 | determinism-check framing + human-agreement disclaimer |
| 9 | `script_oral` | 457 | "est validé en self-consistency" → "n'est pas validé au sens de la fiabilité" |

Independently re-derived from `pre/` with `diff -U0`. Cross-check: the vendor diffs' hunk headers (`-89, -168, -395, -454, -467, -526, -682, -687, -695`) are `-U3` context-block starts; +3 yields exactly these nine loci. Derivation and vendor record agree — the agreement is corroboration, not a dependency.

## Prohibited framing — absent

Exhaustive word-boundary scan across all four files for `reliab* | stabilit* | stable* | fiabilit* | fiable* | repeatab* | répétab*`: **63 occurrences**.

| Class | Count | Disposition |
|---|---|---|
| Negated / disclaimed | 39 | Permitted — the framing is denied, not applied |
| Evidence path (`reliability.csv`) | 4 | **Required intact** by criteria |
| Manually reviewed | 20 | All benign — see below |

All 20 reviewed occurrences were classified by hand; **none applies the prohibited framing to the judge**:

- **About feature steering / features, not the judge** — report L282 ×2 ("steering that works reliably", "produces reliable singing-obsession text"), L490 ("reliable on the base model"); oral L263, L277, L327 ("9056 est la plus fiable", "la feature de steering fiable"), L347 ("une seule feature propre, stable et isolable").
- **About a steering regime, not the judge** — report L494; fiche L1243; oral L377, L477 ("un régime stable").
- **About checkpoint identity** — report L364 ("identity needs to stay stable across a training restart").
- **Prohibitive guards that reinforce the correction** — fiche L739 ("Ne pas citer ces statistiques comme preuve de fiabilité du juge"), L740 ("Pas de fiabilité réelle mesurée…").
- **Describing the prior bad practice being replaced** — oral L163 ("sans métrique de fiabilité").

### Note on how the criterion was read

The prohibited tokens do appear literally, but exclusively inside negating constructions ("a determinism check, **not** judge reliability, stability, or validated repeatability"; "et **non** la fiabilité, la stabilité ou une répétabilité validée du juge"). I read the criterion as prohibiting the **framing** — affirmative attribution to the judge — not the literal tokens. That is the only self-consistent reading, because the same criteria simultaneously require the `results/lodestar_*/reliability.csv` pointers to remain intact and the L470 hedge ("And **no** reliability estimate exists at all…", "the instrument's stability … is simply **unmeasured**") to be preserved verbatim. Both mandates contain the tokens. Flagging them would contradict the criteria. **If a literal-token-absence reading was intended, this verdict must be revisited** — but under that reading the criteria are mutually unsatisfiable.

## Excluded sites — unchanged

All twelve byte-identical `pre` vs working:

`internship_report` **282, 490, 376** (both copies) · `script_oral` **163, 347, 377, 477** · `fiche` **896, 1243**

## Hedges at 470 / 529 — preserved verbatim

Character-level `difflib` opcodes for both lines in **both** report copies contain **only `insert`** — no `delete`, no `replace`. Reconstructing the current line minus its insertion reproduces the pre line **byte-exactly** (`True` in all four cases).

Surviving invariants confirmed present in pre **and** current:

- L470 — "but self-consistency is not validity"; "no human-correlation study was run"; "And no reliability estimate exists at all for heavily degenerate extreme-scale text"; **the mock-judge exclusion** ("produced by a deterministic mock judge during pipeline testing and are excluded from this report's evidence (Section 2.6)"); "the instrument's stability outside the coherent operating range is simply unmeasured".
- L529 — **`HIGH (self-consistency) / ABSENT (human correlation)`** structured labels unchanged; `results/lodestar_*/reliability.csv`; "α ≥ 0.91 on all rubrics across the six standard runs (coherence 0.983–0.998)"; the mock-judge placeholder exclusion; "no human-label validation was run."

## Numeric invariants — unchanged

Occurrence counts identical pre → working in every file:

| File | Invariants |
|---|---|
| `internship_report` (both) | `0.983` 2→2 · `0.998` 2→2 · `α ≥ 0.91` 3→3 · Krippendorff 2→2 · ICC 1→1 · κ 1→1 · `reliability.csv` 2→2 |
| `fiche` | `0,91` 1→1 · Krippendorff 3→3 · ICC 3→3 · κ 3→3 |
| `script_oral` | `0,983` 1→1 · `0,998` 1→1 · `0,91` 2→2 · Krippendorff 2→2 |

The 0.983–0.998 range and every alpha/ICC/kappa figure are untouched. `reliability.csv` evidence pointers intact (2 per report copy, 4 total).

## Cross-copy identity and pre-existing divergences

The four target lines are **byte-identical across both `internship_report.md` copies**:

| Line | sha256[:16] |
|---|---|
| 92 | `1c80cd8499e72ca5` |
| 398 | `a0d3f087d8ba578b` |
| 470 | `643f4af4dfe759bc` |
| 529 | `921aca0e8e9641a5` |

Pre-existing divergences re-derived from `pre/` independently (not taken from the supplied list): **exactly 14** — `37, 71, 145, 148, 160, 194, 206, 209, 229, 292, 358, 385, 394, 409`. Matches the stated list exactly; all are image paths; the divergent-line set is **identical** pre vs working; and all 14 lines are **byte-unchanged in both copies** by the edit.

## Encoding — unchanged from pre-state, per file

Per the amended criterion (the void "all four no-BOM" rule is not used):

| File | pre | working | |
|---|---|---|---|
| `reports/internship_report.md` | no-BOM | no-BOM | SAME |
| `reports/presentation/internship_report.md` | no-BOM | no-BOM | SAME |
| `reports/presentation/fiche_…md` | **BOM** (`ef bb bf`) | **BOM** | SAME |
| `reports/presentation/script_oral_…md` | no-BOM | no-BOM | SAME |

The fiche's genuine pre-existing BOM is preserved and is **not** a defect. All four decode as valid UTF-8.

## Git state — clean, no stop condition

`git status --porcelain` is byte-identical to `git_status_before.txt`, `git_status_after.txt`, and `git_status_after_a.txt`:

```
?? configs/characterize/
?? configs/steer/
?? "ssh yazid@tamia.alliancecan.ca"
?? tmp_r6c4_probe/
```

`git diff --cached --name-only` is empty (nothing staged). `git ls-files reports/` returns **0** tracked files. `reports/` is ignored (`.gitignore:45`). **No report file entered the index — the stop condition did not fire.**

## Method notes

Read-only throughout; no worktree created (correctly — it would have materialized none of these untracked files). Two defects in my own scanning were caught and corrected before they could produce false findings: a `cp1252` print crash that silently truncated the first framing scan at 3 of 63 occurrences, and an unanchored `fiabl\w*` pattern matching inside "veri**fiable**". Both were fixed with word-boundary anchoring and explicit UTF-8 output before any occurrence was classified. Console mojibake in intermediate French output is a terminal-encoding artifact only; the files themselves are valid UTF-8, verified by decode.
