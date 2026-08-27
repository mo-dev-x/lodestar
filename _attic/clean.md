Lodestar — Repository Hygiene Audit
Scope: the publishable tree at d:\lodstar, excluding docs/ (treated as separately-managed internal material, per instruction) and dev caches (.venv, .mypy_cache, .pytest_cache, .ruff_cache — all already .gitignored). Evaluated for organization and purpose only; no architecture, features, or implementation touched.

1. Repository Verdict
🟠 Moderate Cleanup Required
The framework itself is clean: lodestar/ is well-organized with one source of truth per concept and no dead modules (the earlier lodestar_charts.py removal held), and tests/ maps cleanly to it. The problems are entirely peripheral and publication-facing: internal governance/working docs and research scripts sit in the publishable tree without exclusion, two abandoned Jinja templates are dead code, a generated HTML preview and run caches are committed, local editor config would ship, and the public README links into the docs/ tree that .gitignore excludes. None requires reorganizing the framework — but a public "source of truth" repo cannot ship as-is.

2. Directory Review (every top-level dir except docs/)
Directory	Recommendation	Rationale
lodestar/	Keep	The framework. Well-structured (ingest/ judges/ metrics/ report/ rubrics/ validation/ + models/config/cli). One dead-template pair inside (see §5), otherwise clean.
tests/	Keep	Every test_*.py maps to a module; fixtures/ and conftest.py are load-bearing.
.github/	Keep	CI workflow — legitimate build tooling.
scripts/	Move → docs/ (or delete)	Not examples: research drivers with hard-coded absolute paths into the private sibling repo D:\qwen-sae-interp\… and dropped concepts (Montreal/Golden Gate/poutine). Not referenced by the package, README, or pyproject. Not publishable as-is.
V1.0/	Move → docs/ (managed separately)	The constitutional corpus (Constitution, Audit, CIS, Certification, index) — exactly the "constitutional drafts / internal governance" class the instruction says is managed separately and not for initial publish. Currently not excluded by .gitignore, so it would ship.
run/	Delete (working-tree)	Runtime output dir; run/ and *.sqlite already .gitignored, so it won't publish — but it's clutter on disk.
run_test/	Delete (working-tree) + gitignore	Same, but run_test/ is not explicitly ignored (only its *.sqlite is). Add it to .gitignore or remove.
.claude/	Delete from publish + gitignore	settings.local.json is local editor state; must not ship.
.venv/, .mypy_cache/, .pytest_cache/, .ruff_cache/	Keep (ignored)	Already .gitignored; dev-local, won't publish. No action.
No directory needs Rename/Split/Merge. The framework layout is sound.

3. File Classification
Root files
File	Category	Action	Justification
README.md	Documentation	Keep (fix links)	Public entry point. But it links to docs/USAGE.md, RUBRICS.md, VALIDATION.md, EXTENDING.md — which .gitignore (docs) excludes → dead links in the public repo (see §4).
LICENSE	Documentation (legal)	Keep	MIT license — required for publication.
CITATION.cff	Documentation	Keep	Machine-readable citation metadata; renders on GitHub.
CHANGELOG.md	Documentation	Keep	Public change history.
pyproject.toml	Build / Tooling	Keep	Package definition + console entrypoint.
uv.lock	Build / Tooling	Keep	Lockfile — legitimate for reproducibility.
.gitignore	Build / Tooling	Keep (extend)	Add run_test/, .claude/, and the root preview HTML (§6).
ARCHITECTURE.md	Documentation (internal)	Move → docs/	The old "build blueprint"; now a second source of architectural truth alongside the Constitution, and its CONSTITUTION.md link is broken (file moved to V1.0/). Internal history.
GAPS.md	Documentation (internal)	Move → docs/ (or Delete)	Pre-remediation gap audit — superseded by the Certification/Audit corpus. Working artifact.
GENERALIZATION_BACKLOG.md	Documentation (internal)	Move → docs/ (or Delete)	A TODO list + an embedded future-audit prompt. Pure internal working doc.
lodestar_full_run_preview.html	Generated Artifact	Delete	A 46 KB rendered report from a specific research run; not .gitignored → would publish. Reproducible via lodestar report.
lodestar/ package — Core Framework / Public API (all Keep unless noted)
File	Category	Action
__init__.py	Public API	Keep — top-level exports.
cli.py	Public API (CLI)	Keep.
models.py, config.py	Core Framework	Keep.
ingest/{__init__,generic,steering_json}.py	Core Framework	Keep (both adapters live and referenced).
judges/{__init__,anthropic,base,cache,cost,identity,mock}.py	Core Framework	Keep (identity.py is the F1 key module; all wired).
metrics/{__init__,base,derived,stats}.py	Core Framework	Keep.
rubrics/{__init__,base,steering}.py	Core Framework	Keep.
validation/{__init__,consistency,human}.py	Core Framework	Keep.
report/{__init__,html,lodestar_svg,sections}.py	Core Framework	Keep (all imported).
report/templates/report.html.j2	Core Framework (asset)	Keep - loaded by the canonical report renderer.
report/templates/report(myversion).html.j2	Dead Code / Duplicate	Delete — never loaded; the (myversion) name is an abandoned working copy.
py.typed	Build / Tooling	Keep — PEP 561 typed-package marker.
tests/ — Test (all Keep)
conftest.py; test_{anthropic_judge,cache,cli,cost,execution_identity,ingest,judge_mock,metrics,models,report,rubrics,sections,stats,validation}.py; fixtures/{generations_sample,krippendorff_known}.json. Each maps to a live module; nothing orphaned. test_execution_identity.py is the F1 regression suite.

scripts/ — Experimental Script (all Move → docs/ or Delete)
File	Justification
eval_montreal.py	Hard-coded to results/steering_montreal_solo, absolute D:\qwen-sae-interp\… paths.
eval_montreal_golden_gate.py	Hard-coded feature 10413, Montreal/Quebec, absolute research paths.
eval_feature_sweep.py	"Generic" but still absolute paths + references survey_features.py/steering_experiment.py in the private repo.
V1.0/ — Documentation (internal governance) → Move → docs/
CONSTITUTION.md, CONSTITUTIONAL_CONFORMANCE_AUDIT.md, CONSTITUTIONAL_IMPLEMENTATION_SPECIFICATION.md, CONSTITUTIONAL_CERTIFICATION.md, V1.0.md.

Config / generated
File	Category	Action
.github/workflows/ci.yml	Build / Tooling	Keep.
.claude/settings.local.json	Build / Tooling (local)	Delete + gitignore .claude/.
run/cache.sqlite, run_test/cache.sqlite	Generated Artifact	Delete (working-tree).
4. Duplicate Detection
Report templates - report(myversion).html.j2 vs report.html.j2. Canonical: report.html.j2. report(myversion).html.j2 is an abandoned working copy -> delete.
Architecture source-of-truth — ARCHITECTURE.md vs V1.0/CONSTITUTION.md. Two overlapping descriptions of the same architecture. Canonical: the Constitution corpus (now governing). ARCHITECTURE.md is the older, partly-stale blueprint with a broken Constitution link → move to docs/.
Superseded audit — GAPS.md vs the Audit/Certification corpus. Same subject (implementation-vs-spec gaps), superseded. Canonical: CONSTITUTIONAL_CONFORMANCE_AUDIT.md + …_CERTIFICATION.md → move/delete GAPS.md.
README → docs/ links (broken source of truth). README.md points users to docs/USAGE.md/RUBRICS.md/VALIDATION.md/EXTENDING.md, but .gitignore excludes docs. Either those user-facing docs must be in the publish set or README must not link to them. Deferred to the separately-managed docs/ process per scope, but flagged here because the in-scope README depends on it.
5. Dead Code
lodestar/report/templates/report(myversion).html.j2 - not loaded; abandoned iteration. Delete.
lodestar/report/base.py - obsolete report-style dispatcher after consolidation. Delete.
No other dead Python modules remain in lodestar/ - every .py is imported and wired.

6. Cleanup Specification (ordered; repository-organization only)
Pure moves/deletes/gitignore — no code, no redesign, no features.

Delete dead templates. Remove lodestar/report/templates/report(myversion).html.j2.
Delete committed generated artifacts. Remove lodestar_full_run_preview.html, run/, run_test/ from the working tree.
Remove local editor config from publish. Delete .claude/settings.local.json.
Extend .gitignore to close the leaks: add .claude/, run_test/ (or generalize run/→run*/), and lodestar_full_run_preview.html (or a scoped root *.html rule — note templates are .j2, so a root-only rule is safe).
Relocate internal governance docs out of the publish set: move V1.0/ and ARCHITECTURE.md, GAPS.md, GENERALIZATION_BACKLOG.md into docs/ (the separately-managed, .gitignored area). This consolidates architectural/constitutional truth into the internal tree and de-clutters the public root.
Relocate research scripts: move scripts/ into docs/ (internal) or delete. They are not publishable examples (absolute paths, private-repo references).
Resolve the README ↔ docs/ link dependency. Decide whether the user-facing subset (USAGE/RUBRICS/VALIDATION/EXTENDING) ships publicly; if not, delink them from README. (The docs/ side is executed by the separately-managed process, per scope — this step only records the in-scope README obligation.)
Post-cleanup published surface (what remains at root): README.md, LICENSE, CITATION.cff, CHANGELOG.md, pyproject.toml, uv.lock, .gitignore, .github/, lodestar/, tests/ — a repository where every published file has a single, clear purpose and is understandable without the internal docs/ tree.

Note on scope boundary: I did not inspect, classify, or recommend changes to anything under docs/. Items moved into docs/ above are recommendations to relocate in-scope files there; managing docs/'s own contents remains the separate process you described.
