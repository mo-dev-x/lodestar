# The Lodestar Constitution

**A steering-native evaluation framework for sparse-autoencoder interpretability research.**

Constitutional specification · Version 1.0 (ratified draft) · Status: **Normative**

---

## 0. Preamble

This document is the highest-level specification of Lodestar. It defines *what Lodestar is about* — its entities, the assumptions it adopts, the identities it reasons with, the invariants it must never violate, and the consequences that follow. It is **implementation-independent**: it constrains every architecture Lodestar may ever have, but describes none of them.

Architecture is *derived* from this document, not invented alongside it. Any proposed design change MUST cite the axiom, invariant, theorem, or non-goal it serves. A change that requires weakening an invariant is not a design decision; it is a **constitutional amendment** (§9).

**Normative language.** MUST, MUST NOT, SHOULD, and MAY are used in the sense of RFC 2119. **Labels.** Every foundational statement is tagged: **[MT]** mathematical truth (follows from definitions and logic alone), **[EA]** engineering assumption (empirical, adopted, and falsifiable), **[INV]** invariant, **[THM]** theorem, **[CONV]** engineering convention (a choice, not a necessity), **[DC]** design consequence.

The organizing discovery behind this constitution — learned the hard way — is this: **“the same judgment” is not one relation but several, and almost every past defect came from conflating them.** The cache once returned a judgment computed for a *different question* because it identified judgments by their text alone. The fix is not a better key; it is a correct ontology from which the key is forced.

---

## 1. Purpose and Scope

Lodestar consumes the generations produced by activation-steering experiments and returns rigorous, multi-dimensional, human-correlated quality measurements: it scores generations against evaluation criteria, quantifies the reliability of those scores, correlates them with human judgment, and derives comparative metrics (frontiers, operating points, control gaps, cross-lingual and cross-model contrasts) — each traceable back to the raw generation.

Lodestar’s subject matter is inherently **steering-native**: the axes of variation an experiment sweeps (feature combinations, scale, condition, language, model) are first-class, not metadata. Its product is not scores but *trustworthy* scores — which is why measurement reliability and provenance are constitutional, not optional.

What Lodestar is **not** is stated normatively in §8.

---

## 2. Ontology

### 2.1 Primitive entities

1. **Generation** — a piece of model-produced text, together with the context that frames an evaluative question about it (the prompt shown, the concept of interest, the declared language, the steering configuration that produced it). A Generation is the *thing being evaluated*.

2. **Criterion** — a semantic evaluation dimension with a scale and a meaning (e.g., *coherence, ordinal 1–10, “grammatical fluency independent of topic”*). A Criterion is a reusable *question*, independent of any particular text or wording.

3. **Instrument** — the concrete operationalization of a Criterion: the exact prompt template, the output schema, the judge-facing framing, and the rendering rules that turn a Generation + Criterion into a posed question. Many Instruments can realize one Criterion.

4. **Judge (Method)** — the estimator that answers a posed question: a resolved model snapshot together with the decoding parameters that affect its answer. A Judge is an *instrument of measurement*, not an oracle of truth.

5. **Trial** — an index over repeated, intended-independent attempts to answer the same posed question (repeat number and/or seed). Trials exist to *measure* the estimator’s stability, not to change the question.

6. **Judgment** — the recorded event of a Judge answering one posed question on one Trial: a scored **answer** plus a **record**.

7. **Run** — a collection of Judgments over a set of Generations, Criteria, and a Judge, with a manifest.

8. **Metric** — a pure function from Judgments (and typed parameters) to a tidy result.

9. **Report** — a rendering of a Run and its Metrics for human consumption.

10. **Plugin** — an externally supplied Criterion, Judge, Metric, or Report, admitted by declared contract.

### 2.2 The answer and the record

> **Def (Answer, α).** The **answer** of a Judgment is its **score** — the value on the Criterion’s scale (ordinal number, boolean, or category set). Write `α(J)` for the answer. The `rationale`, raw response text, token usage, and timing are **not** part of the answer; they are record. *(This definition exists because free-generated rationale text is not reproducible; identifying judgments by it would make identity meaningless. Rationale is retained for audit, never for identity.)*

### 2.3 Execution coordinates

Every Judgment is located by coordinates. The **execution coordinates** are exactly those that can influence the answer:

| Symbol | Coordinate | Contents | Nature |
|---|---|---|---|
| **S** | Subject | the generation text and the per-question parameters presented to the Judge: prompt shown, target concept, language, alias set | content, canonicalized (§3, EA5) |
| **C** | Criterion | dimension + scale + **semantic revision id** (bumped only on genuine redefinition) | reusable question identity |
| **I** | Instrument | template, output schema, judge-facing framing, render-rules version | surface operationalization |
| **M** | Method | **resolved model snapshot** + answer-affecting decoding parameters | estimator |
| **T** | Trial | repeat index / seed | sampling index, *not* an answer-determinant (§3, MT3) |

The remaining data is the **Record (R)**: lineage (SAE checkpoint → steering config → generation), timestamps, cost, tokens, raw response, the cached flag, and the invoking command. **R never influences the answer** and is **never part of any answer-identity**; it is per-event (§4.4).

> **Coordinate–object note (clarification; no new normative content).** An execution coordinate is a *projection*, not a domain object: its fields may be drawn from more than one object. For example, `S` draws `text`, `prompt`, `target_concept`, and `language` from the Generation and the `alias set` from the Rubric. A coordinate's identity under INV-DECIDE MUST be computed over **all** of its fields, wherever they reside; **no single object's local identity may be substituted for a coordinate's identity.** This restates what §2.3 and INV-DECIDE already entail — it adds no obligation. `S` is a projection composed at judging time, not a stored entity, so it needs no object of its own.

> **Ontological note (deliberate, non-discriminating splits).** `S`/`C` and `M`/`T` are separated because they are *different kinds of thing that evolve independently* — Criteria are versioned and Subjects are not; Methods are pinned and Trials are enumerated — **not** because every split witnesses a distinct identity. Some splits earn their keep in the identity lattice (§3); others earn it only in the ontology and the amendment process. This is stated plainly rather than disguised as necessity.

### 2.4 Relationships

A Generation projects to a Subject `S` (what the Judge sees) and contributes lineage to `R` (where it came from). **These are independent**: the same text may arise from different checkpoints, giving equal `S` but different `R`. A Criterion `C` is realized by one or more Instruments `I`. A Judge `M` applied to a posed question `(S, C, I)` on a Trial `T` yields a Judgment. Metrics consume Judgments; Reports render them; Provenance threads `R` through all of it.

---

## 3. Axioms

### Mathematical truths

- **[MT1] Identity by coordinate equality.** For any coordinate set `X`, the relation `J ≈_X J' ⟺ (X-projection of J) = (X-projection of J')` is an equivalence relation, *provided each coordinate in `X` has a total, decidable equality*. (Follows from equality being an equivalence relation. The proviso is discharged by INV-DECIDE.)
- **[MT2] Refinement by inclusion.** If `X ⊆ Y` then `≈_Y` refines `≈_X` (i.e., `≈_Y` makes at least as many distinctions).
- **[MT3] Trials are not answer-determinants.** The Judge does not receive `T` as input; therefore, holding `(S,C,I,M)` fixed, the answer is not a function of `T`. `T` is a *label over draws*, not a cause of the answer. (Consequently the “determinant” test of §2.3 admits `S,C,I,M`; `T` is admitted separately, by role.)

### Engineering assumptions (empirical, adopted, falsifiable)

- **[EA1] Cost.** Judge calls consume money and time; recomputation is expensive relative to storage. *(Justifies caching’s existence.)*
- **[EA2] Answer determinacy is criterion-typed.** Each Criterion is either **deterministic** — its answer is a total function of `S` (e.g., literal string occurrence) — or **stochastic** — its answer is a sample drawn by the Judge given `(S,C,I,M)`. *(Deterministic and LLM criteria are different in kind; a single uniform treatment is incorrect.)*
- **[EA3] Conditional stationarity under a pinned snapshot.** For a **resolved, immutable** Method `M`, the conditional answer distribution given `(S,C,I,M)` is stable over the lifetime of a project. *(False for moving model aliases; this is why M must be pinned — see THM3.C.)*
- **[EA4] Subject sufficiency.** A Judge’s answer distribution depends only on what the Instrument presents to it — the Subject `S` — and not on lineage or any Record field. *(Justifies sharing an answer across Generations of differing lineage but equal Subject; obliges Record re-stamping, INV5.)*
- **[EA5] Declared, conservative invariance.** The set of Subject/Instrument transformations that leave the answer distribution unchanged (e.g., reordering an alias *set*) is not known a priori. Lodestar operates against an **explicitly declared, versioned invariance model** that is assumed to **under-approximate** the Judge’s true invariances. *(Under-approximation is the safe direction: fewer declared invariances → more distinctions → sound but possibly redundant, never unsound.)*

*Every [EA] is a place where Lodestar could be wrong about the world. They are collected here so that a future failure can be traced to a named assumption rather than to a buried belief.*

---

## 4. Identities

An **identity** is `≈_X` for a chosen execution-coordinate set `X` (MT1). Lodestar names the identities that have operational roles. Coarsest to finest:

### 4.1 The canonical chain

- **[Domain identity] `≈_D` = equality on `(S, C)`.**
  “The same latent quantity a researcher reasons about” — *the coherence of generation G*. Independent of wording, estimator, and trial. **Role: aggregation and reporting.** Two Judgments are Domain-equal iff they measure the same property of the same subject, even by different Judges or on different trials.

- **[Implementation identity] `≈_Impl` = equality on `(S, C, I)`.**
  Adds the exact Instrument. Distinguishes a Criterion’s revisions in wording/schema/framing. **Role: methods disclosure and cross-judge study** — cross-judge robustness varies `M` *within* an `≈_Impl` class.

- **[Measurement identity] `≈_meas` = equality on `(S, C, I, M)`.**
  Adds the Method but not the Trial. Its equivalence classes are exactly the sets of repeated draws of one measurement. **Role: self-consistency / reliability** is computed *within* an `≈_meas` class. *(This identity is why the M|T split is not inert: `≈_meas` sits strictly between `≈_Impl` and Execution.)*

- **[Execution identity] `≈_E` = equality on `(S, C, I, M, T)`.**
  The complete specification of one judging computation. **Role: reuse (caching).** Under EA3, Execution-equal queries share an answer distribution *and* a trial slot.

- **[Provenance (event) identity] `≈_P`.**
  Equality on the full event, including `R` at full resolution. **This is effectively the diagonal: every real event is Provenance-unique.** It is therefore not a grouping relation but an **event/trace identity**; its role is audit, not deduplication. It is named for completeness and honesty about typing, and it is the terminal of the chain (MT2).

> `≈_D ⊑ ≈_Impl ⊑ ≈_meas ⊑ ≈_E ⊑ ≈_P` (each refines the previous, MT2). Aggregate at `D`; disclose the instrument at `Impl`; measure reliability within `meas`; cache at `E`; trace at `P`.

### 4.2 Derived contrast relations (required by analysis)

Some analyses vary exactly one coordinate. These are not new identities but **contrasts** — the study of variation *within* a class of a coarser identity:

- **Self-consistency contrast:** vary `T` within an `≈_meas` class. (Reliability: Krippendorff α, ICC, κ.)
- **Judge-robustness contrast:** vary `M` within an `≈_Impl` class. (“results stable across judges.”)
- **Steering contrasts (the domain’s reason to exist):** vary a single Subject parameter (scale, condition, language, model, feature set) within an otherwise-fixed grouping. (Frontier, control gap, transfer ratio, cross-model.)

Contrasts are legitimate only under INV-AGG (§5): the coordinate under study varies while all other execution coordinates are held equal or explicitly marginalized.

### 4.3 What makes two Judgments the same, in one paragraph

They are the **same measurement** iff they agree on `(S,C,I,M)`; the **same computation** iff also on `T`; the **same domain quantity** iff on `(S,C)`; and the **same event** essentially never (only with themselves). They differ the instant any execution coordinate differs. Record differences — when, cost, wording of rationale, served-from-cache — make a *different event but not a different judgment*.

### 4.4 Record independence and re-stamping

Because `R` is not an execution coordinate (§2.3) and answers are subject-sufficient (EA4), two Provenance-distinct events may be Execution-equal. Therefore, when an answer is reused, its **Record MUST be recomputed for the new event**, never inherited (INV-RESTAMP). A reused answer is a *new Judgment* that happens to carry an old answer.

---

## 5. Invariants

These MUST hold in every implementation, forever, regardless of architecture.

- **[INV-DECIDE] Decidable identity.** Every execution coordinate MUST have a total, canonical, decidable equality under the declared invariance model. *(Discharges MT1’s proviso.)*
- **[INV-NOHIDE] No hidden determinants.** Every input that can change a Judgment’s answer distribution MUST be a declared execution coordinate. Nothing that affects an answer may reside in the Record or in untyped metadata. *(This is the constitutional statement of the cache-identity lesson: the system prompt, the output schema, the target concept, the alias set, the decoding parameters — all are answer-affecting and all are coordinates.)*
- **[INV-TYPED] Typed comparison dimensions.** Every dimension along which Judgments are aggregated or compared MUST be a typed, first-class coordinate. No Metric may branch on data carried through an untyped bag. *(The “experiment” dimension, and any like it, must be typed — not smuggled through `metadata`.)*
- **[INV-LEVER] Universal invalidation lever.** Every answer-affecting change MUST change some execution coordinate. No answer-affecting property may be un-versionable or un-invalidatable. *(A change to judge-facing framing changes `I`; a redefinition of a dimension changes `C`; a model change changes `M`.)*
- **[INV-RESTAMP] Provenance freshness.** A reused answer MUST carry a Record recomputed for its own event; stale lineage or cost MUST NOT be inherited (§4.4).
- **[INV-TRACE] Provenance totality.** Every Judgment MUST retain a complete path to its raw Generation, Subject, Instrument identity, Criterion revision, Method snapshot, Trial, invariance-model version, and Run. Every aggregate MUST be decomposable to the raw Judgments beneath it.
- **[INV-DETTYPE] Determinacy declaration.** Every Criterion MUST declare whether it is deterministic or stochastic (EA2). Deterministic criteria MUST be exactly reproducible from `S`; stochastic ones need only be reproducible *in distribution* under a pinned snapshot.
- **[INV-AGG] Aggregation locality.** Aggregation across trials is valid only within an `≈_meas` class; comparison across a coordinate is valid only when all other execution coordinates are held equal or explicitly marginalized.
- **[INV-PURE] Metric purity.** A Metric MUST be a pure function of its input Judgments and typed parameters: identical inputs yield identical outputs.
- **[INV-CONTAIN] Fault containment.** A fault in one extension (Plugin, Criterion, Judge, Metric, Report) MUST NOT corrupt an identity, poison the cache, or take down an unrelated subsystem. *(A broken third-party Metric may fail its own panel; it may not fail the Report.)*

---

## 6. Theorems and Conventions

Each theorem cites its dependencies. Where honesty forbids a proof, the statement is demoted to convention **[CONV]** or design consequence **[DC]**.

### [THM1] Cache soundness lower bound
**Statement.** Any cache that serves a stored answer for a query MUST satisfy: *cache-equal ⇒ Execution-equal* (the cache relation may be no coarser than `≈_E`).
**Depends on:** Def(α), §2.3, EA2, EA3, EA4, MT3, INV-NOHIDE.
**Argument.** A served answer is acceptable only if it is a valid draw from the query’s answer distribution (reuse *is* answering). By EA2+EA4 that distribution is a function of `(S,C,I,M)` alone; by EA3 it is time-stable for a pinned `M`. Two queries are guaranteed to share the distribution only if they agree on `(S,C,I,M)` — we cannot *assume* equality across any differing coordinate (EA5 forbids assuming an undeclared invariance), so any difference must be treated as potentially distribution-changing. By MT3, `T` selects which independent draw is served; preserving self-consistency semantics (INV-AGG) requires equal `T`. Hence serving requires equality on `(S,C,I,M,T) = ≈_E`. ∎
**Note.** The bound is “no coarser,” the safe direction. It does **not** claim that differing coordinates *do* change the answer (that is the unknown invariance question, EA5); it claims we may not *presume* they don’t.

### [THM2 / CONV] Tightness is a convention, not a law
**Statement.** A cache relation strictly finer than `≈_E` is **sound but wasteful** (Execution-equal queries miss each other and re-pay). Lodestar adopts **Non-Redundancy**: the cache relation equals `≈_E`.
**Depends on:** THM1 (lower bound), EA1 (cost).
**Status.** The lower bound is a theorem; the upper bound is an **[CONV]** justified by cost, *not* by correctness. This is stated explicitly because an earlier draft mistook an efficiency preference for a logical necessity.

### [THM3] The cache key is forced (in form)
**Statement.** Under THM1 + THM2, cache identity **is** Execution identity. The cache key is therefore any injective encoding of `(S, C, I, M, T)` under the declared invariance model (EA5), **excluding R**.
**Depends on:** THM1, THM2, EA5, INV-NOHIDE, §2.3.
**Corollary [THM3.C] (Snapshot obligation).** If `M` is a moving alias, EA3 fails, the distribution-stability step of THM1 fails, and reuse becomes unsound. Therefore `M` MUST resolve to an immutable snapshot before it enters an identity. *(This is derived here, once, from EA3 — not assumed in the ontology and then “re-discovered.”)*
**Corollary [THM3.D] (Fail-closed).** If any execution coordinate cannot be computed (e.g., unresolved snapshot, undeclared invariance), the cache MUST treat the query as a miss, never guess a hit. *(From THM1: absent a proof of Execution-equality, reuse is unsound.)*

### [THM4] Aggregation validity
**Statement.** Aggregating trial answers (e.g., median) estimates the Domain quantity `≈_D` **only within an `≈_meas` class**; deterministic criteria (INV-DETTYPE) require no aggregation and are reported exactly.
**Depends on:** EA2, INV-AGG, INV-DETTYPE, §4.1.

### [THM5] Audit completeness
**Statement.** Distinct events sharing an Execution identity remain individually traceable, and no aggregate can exist without a path to its raw Judgments.
**Depends on:** §2.3 (R ∉ execution coordinates), INV-RESTAMP, INV-TRACE.

### [THM6 / partly DC] Reproducibility, honestly bounded
**Statement.** A Run is reproducible as follows: **(a)** for deterministic criteria, *exactly*, from `S` [INV-DETTYPE]; **(b)** for stochastic criteria, *in distribution*, under a pinned snapshot [EA3]; **(c)** the **cache key itself** reproduces across environments **iff** the invariance model and canonicalization are versioned and shared [EA5, INV-DECIDE].
**Depends on:** EA3, EA5, INV-DETTYPE, INV-DECIDE.
**[DC] Design consequence.** Exact bitwise reproduction of a stochastic answer across time is **impossible**. Lodestar does not claim it (§8). Instead, **[CONV]** the **first observed answer per trial slot is the canonical representative**; the cache freezes a valid draw, and INV-RESTAMP guarantees the audit trail always records that a value was reused.

---

## 7. Implementation Obligations

Each obligation cites the theorem or invariant that requires it. These bind every subsystem; how they are met is architecture.

### 7.1 Judge (Method)
- MUST expose its Method as a **resolved immutable snapshot** plus answer-affecting decoding parameters. — *THM3.C*
- MUST declare, per Criterion it serves, deterministic vs stochastic answering. — *INV-DETTYPE, EA2*
- MUST NOT let an answer depend on anything outside the declared execution coordinates (retry, repair, and rate-limit handling are Record-level and MUST NOT alter Execution identity). — *INV-NOHIDE, THM1*
- MUST produce, for each `(S,C,I,M,T)`, an answer `α` and a complete Record. — *INV-TRACE*

### 7.2 Rubric (Criterion + Instrument)
- MUST separate **Criterion** (dimension, scale, semantic revision) from **Instrument** (template, output schema, judge-facing framing, render rules). — *§2, INV-LEVER*
- MUST expose an Instrument content-identity such that **any** answer-affecting surface change — including the system/framing text and the output schema — changes `I`. — *INV-LEVER, INV-NOHIDE*
- MUST bump the Criterion’s **semantic revision** only on genuine redefinition, never as a cache-busting convenience (that is the Instrument’s job). — *§2.3, keeps `≈_D` meaningful*
- MUST declare the invariances it claims for its Subject/Instrument (e.g., alias set unordered), conservatively. — *EA5, INV-DECIDE*

### 7.3 Cache
- Key MUST be an injective encoding of `(S,C,I,M,T)` under the declared invariance model, **excluding R**. — *THM3*
- MUST refuse to serve across unpinned Methods and MUST fail closed when Execution identity is uncomputable. — *THM3.C, THM3.D*
- MUST recompute Record on reuse and MUST NOT inherit lineage or cost. — *INV-RESTAMP*
- MUST invalidate exactly the slice whose coordinate changed (never more, never less). — *THM2, INV-LEVER*
- Membership and cost preflight MUST be computable without materializing all Judgments. — *EA1 (scalability), INV-PURE*

### 7.4 Metrics
- MUST be pure functions of Judgments and typed parameters. — *INV-PURE*
- MUST aggregate only within `≈_meas` classes and compare only across explicitly held-equal coordinates. — *INV-AGG, THM4*
- MUST branch only on typed coordinates, never on untyped metadata. — *INV-TYPED*
- MUST preserve decomposability of every result to its source Judgments. — *INV-TRACE, THM5*

### 7.5 Plugins
- Any extension MUST declare which coordinates it reads and produces, and MUST be admitted by declared contract, not by inheritance. — *INV-DECIDE, extensibility*
- A Plugin MUST NOT introduce a hidden determinant or an untyped comparison dimension. — *INV-NOHIDE, INV-TYPED*
- A Plugin fault MUST be contained to the Plugin’s own output. — *INV-CONTAIN*

### 7.6 Provenance
- MUST maintain the total, re-stamped lineage for every Judgment, recording Method snapshot, Instrument identity, Criterion revision, Trial, invariance-model version, and tool version. — *INV-TRACE, INV-RESTAMP*
- MUST make every aggregate, frontier, correlation, and headline number decomposable to raw Judgments and their raw Generations. — *THM5*

### 7.7 Validation (reliability & human correlation)
- Reliability MUST be computed within `≈_meas` classes; human correlation MUST pair each human label to the Judgment’s Domain quantity, not to a specific trial. — *THM4, INV-AGG*
- Validity claims (reliability, human agreement) are **reported measurements**, never assumptions of correctness (§8). — *§8*

---

## 8. Non-Goals — Guarantees vs. Assumptions

Lodestar distinguishes what it **guarantees** from what it **assumes** and from what it **explicitly does not claim**.

**Lodestar does NOT:**
1. **Produce generations.** It consumes them; it is not a steering or inference pipeline. *(Scope.)*
2. **Guarantee bitwise reproducibility of stochastic answers.** It guarantees exact reproducibility only for deterministic criteria, and distributional reproducibility for stochastic criteria under a pinned snapshot. — *THM6, [DC]*
3. **Certify that a Judge is correct or well-calibrated.** It *measures* reliability and human correlation and *reports* them. **Guarantee:** it quantifies judge trustworthiness with named statistics. **Assumption the user MUST not skip:** a high reliability coefficient is evidence, not ground truth.
4. **Know the Judge’s true invariances.** It operates against a declared, conservative invariance model (EA5) and does not claim it equals reality. Over-declaration is the only way to become unsound, and is forbidden by obligation.
5. **Preserve any guarantee across a moving model alias or an unversioned Instrument edit.** These break EA3 / INV-LEVER; behavior across them is undefined by construction, not by accident.
6. **Define ground-truth concept relevance or ground-truth anything.** The target concept and the rubric definitions are *supplied parameters*; Lodestar measures relative to them.
7. **Guarantee cost figures.** Cost is an estimate bounded by external pricing. **Assumption:** the pricing reference is current; a stale reference degrades only the estimate, never an identity or a measurement.
8. **Serve as a general evaluation harness beyond its ontology.** It is extensible (§7.5) but its guarantees are stated for the steering-native ontology of §2.

---

## 9. Amendment and Evolution

This constitution is itself versioned.

- **Adding a coordinate** (a new declared determinant) *refines* every identity (MT2): it is always sound, may reduce cache reuse, and is a **minor** amendment.
- **Removing or coarsening a coordinate**, weakening an invariant, or changing an axiom is a **major** amendment: it MUST bump the constitution’s major version, state the migration (including cache/identity invalidation), and re-derive every affected theorem and obligation.
- **Engineering assumptions [EA] may be falsified.** When one is, the amendment MUST identify every theorem and obligation that cited it and re-establish or retract them. *(This is why every [EA] is named and every [THM]/obligation cites its dependencies: the blast radius of a broken assumption is always computable from this document.)*
- **Extensibility direction.** Future capability is added by *declaring more* (coordinates, criteria, invariances, contrasts), never by *smuggling* answer-affecting or comparison-affecting information into the Record or untyped metadata (INV-NOHIDE, INV-TYPED).

---

## 10. Derivation Guide (how architecture descends from this)

To justify any architectural decision, trace it to this document:

- *Why does the cache key contain the output schema?* → INV-NOHIDE + THM3 (it is an execution coordinate `I`).
- *Why must the judge model be a dated snapshot, not `latest`?* → THM3.C via EA3.
- *Why is “experiment” a typed field and not a metadata key?* → INV-TYPED.
- *Why may a reused judgment show a fresh timestamp and cost?* → INV-RESTAMP + §4.4.
- *Why is self-consistency computed over repeats but not across judge models?* → §4.2 (self-consistency is a `T`-contrast within `≈_meas`; judge robustness is an `M`-contrast within `≈_Impl`).
- *Why doesn’t Lodestar promise identical scores on re-run?* → §8.2 + THM6[DC].

A decision that cannot be traced here is either underspecified or an amendment. That is the point: **Lodestar’s architecture is not a set of choices to be defended, but a set of consequences to be derived.**

---

*End of constitution.*
