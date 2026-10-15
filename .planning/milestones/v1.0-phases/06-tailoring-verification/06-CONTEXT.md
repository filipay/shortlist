# Phase 6: Tailoring + Verification - Context

**Gathered:** 2026-09-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver the tailoring + verification half of the core loop: a CV tailored to a specific listing, expressed as a typed patch over enumerated CV IDs, previewed with its change log, compiled to PDF, gated by an anti-fabrication verification stage that **blocks** rather than repairs — and exposed through a dedicated tailoring page the user can preview and download from.

In scope: `apply_patch` (the typed patch engine replacing today's stub), the `TailoringPatch` LLM contract + tailoring pipeline (`pipeline/tailor.py`), the verification stage (plan pre-check + PDF post-check), the `CvArtifact` repository/writer, the tailoring UI page + PDF-serving route, and the Settings keys that gate cost.

**Not this phase:** assisted apply / application tracker (Phase 7); cover letters (v2 TAIL-09); ATS parse check (v2 TAIL-10); artifact retention/pruning (Phase 8 ops); PDF/DOCX CV *input*; 100% ATS-match optimisation; vector-DB ranking.

**Standing blocker (inherited, not resolved by this phase):** STATE.md blocking unknown #1 — the real `.tex` is not in this repo, so `.tex → cv.yaml` import cost and Tectonic bundle coverage remain unmeasured for the real document. Trigger: place the document at `cv/base.tex`, run `bash scripts/cv-tex-spike.sh`, record counts in `docs/probes/2026-09-21-cv-tex-spike.md`. Phase 6 planning proceeds against the committed awesome-cv-style stand-in fixture (D-61) and must not assume the real document's shape.

</domain>

<decisions>
## Implementation Decisions

### Patch op semantics
- **D-103:** `reweight_bullet` (weight 0.0–2.0) means **within-entry ordering** — a bullet's resolved position in its entry sorts by weight descending. The weight number is never printed. `move_bullet` (`before_id`) remains the explicit positional override. — **Reversibility:** costly — the reweight→ordering rule ships in the tailoring prompt and in `apply_patch`; changing it re-renders every stored artifact and invalidates stored `patch_json`/golden bytes.
- **D-104:** `demote_bullet` moves the bullet to the **end of its own entry's list** (lowest prominence), text unchanged, `reason` required and shown in the change log. It is distinct from `drop_bullet` (removed entirely) and from `move_bullet` (explicit position).
- **D-105:** `suggestion` and `gap_finding` are **advisory only** — persisted in `patch_json`/`change_log_json` and surfaced in the change log / requirement-coverage panel, but they never reach the renderer (no field becomes text in the PDF, §7.3). `gap_finding` additionally feeds verification check 6. — **Reversibility:** costly — the `TailoringPatch`/`patch_json` shape is a stored contract; making gaps render later needs schema + template + migration work.
- **D-106:** An **invalid patch is rejected all-or-nothing** — any unknown/duplicate id, a section losing all entries, or a drop without a reason aborts the whole patch, writes no artifact, and surfaces the error. No partial apply, no auto-repair (§7.4 raise semantics).

### Tailoring flow
- **D-107:** The flow is **two-step**: (1) *generate* — one `complete_structured` call returning `TailoringPatch`; (2) *compile* — an explicit user action that applies the patch, renders, compiles, verifies, and persists. Matches TAIL-07 and success criterion 2 ("review … before compiling").
- **D-108:** The pre-compile review shows an **HTML preview of the tailored CV** (final section/bullet order, dropped bullets visibly struck/annotated) **beside the change log** with per-item reasons. No LaTeX/PDF is produced before the user approves.
- **D-109:** The generated patch is **not persisted at generate time**. The review page round-trips it (hidden form field) together with the captured `base_cv_version_id` + fact-store hash. On compile, `apply_patch` re-validates every id and the fact store must still match the captured version/hash or the compile is refused. This **is** the `_verify_original_matches`-style optimistic concurrency guard on `apply_patch` and artifact persistence. — **Reversibility:** costly — defines the compile-time concurrency contract and the review-page round-trip that includes the guard fields.
- **D-110:** Tailoring **requires an existing score**. The tailor affordance is only offered for listings that already have a stored requirement list (D-81); unscored listings show "rank first". Tailoring does not re-extract requirements and does not run on unscored listings.

### Verification gate
- **D-111:** The gate runs **two layers**. Layer 1 is a deterministic **RenderPlan/patch pre-check** (id containment, bullet conservation, temporal consistency, requirement→evidence integrity) that short-circuits **before compiling**. Layer 2 is an **extracted-PDF-text post-check** (metric containment, structured-field entity containment, injection residue, page budget, layout/ATS, verbatim integrity) run after compile (§10.5). PDF text is read via `extract_pdf_text` reached through `asyncio.to_thread`.
- **D-112:** Check 2 "no new named entity" is **structured-field containment only** — every org / title / section-title string in the RenderPlan must resolve to a CvFacts `orgs` / `titles` / `SECTION_TITLES` entry. `bullet.text` is human-authored, immutable, and therefore **not scanned for proper nouns** (a proper noun inside it is real CV content, not fabrication). Deterministic, no NLP, no false positives.
- **D-113:** Check 4 metric containment is **region-scoped**: numeric tokens extracted from the PDF per region, excluding date-like numbers (the entry's `start`/`end` years and months) and layout/page-number artefacts; each remaining number must appear as a token in that region's source facts (`bullet.metrics` / `bullet.text`). Unmatched ⇒ fail. This is the `_novel_numbers`-equivalent with date-like-number exclusion named in the roadmap.
- **D-114:** **All 10 §10.3 checks ship.** Checks 1–7 and 10 are **hard fail** (block); checks 8 (page budget) and 9 (layout/ATS) are **warn-only and never block**. `VerificationResult.passed` = no `fail` check. Warn findings are surfaced but do not prevent download.
- **D-115:** On any fail a **blocked `cv_artifacts` row is written either way**: a Layer 1 fail stores `patch_json` / `change_log_json` / `verification_json` with `pdf_path`/`tex_path` empty; a Layer 2 fail additionally retains the compiled PDF for diagnosis. Neither is downloadable or linkable, and the pipeline **never auto-repairs** (TAIL-06, §10.4). — **Reversibility:** costly — `pdf_path`/`tex_path` nullability may need a migration, and the blocked contract is consumed by Phase 7's attach path.

### Artifact lifecycle & UI
- **D-116:** The tailoring UI is a **dedicated page** (`/listings/{id}/cv`) owning generate → review → preview → download; the listing detail page links to it. The PDF is served from a route nested under it, inline disposition for the preview embed and `?download=1` for attachment. Every route declares `user: User = Depends(current_user)` (auth seam).
- **D-117:** **Every compile inserts a new `cv_artifacts` row**; the page shows the most recent per listing; older rows are retained as history and never overwritten. Retention/pruning is deferred to Phase 8.
- **D-118:** The "blocked artifact cannot be downloaded or attached" rule is enforced **at the repository layer** (only `ok` artifacts are returned to download/link queries), with route-level refusal as well. Recovery is a **fresh tailor** (new LLM call); the §10.4 "drop this bullet and re-render" affordance is deferred. — **Reversibility:** costly — the repository's artifact-selection contract is consumed by Phase 7's application attach.
- **D-119:** The tailor LLM call draws from the **same `llm_calls` ledger and the same per-run / rolling-24h ceilings** via the reserve-then-call lock (D-91/92/93) — no new counters — plus one new `tailoring_enabled` boolean mirroring `ranking_enabled`.

### the agent's Discretion
Left to the planner/implementer (not re-asked): the exact metric-token normalisation and date-like-number detector; the stop-list (if any) for the entity check; the mechanism that produces the fact-store version/hash carried by the review page; the exact PDF route path and filename scheme; the HTML preview template/markup; the `app/verify/` module layout and `verifier_version` string; the verifier Settings key names; the tailoring system-prompt wording; the exact `TailoringPatch` field ordering. No area was delegated "you decide".

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase definition
- `.planning/ROADMAP.md` §Phase 6 (L258–274) — goal, success criteria 1–4, and the research flag (`_novel_numbers`, `_GROUNDING_REVIEW_THRESHOLD`, `_verify_original_matches` are borrowed pattern names, not existing symbols).
- `.planning/REQUIREMENTS.md` — TAIL-01..TAIL-08 (L68–75), UI-05 (L104); out-of-scope rows (LLM emitting LaTeX/free prose; general résumé parsing; 100% ATS optimisation; vector-DB ranking); v2 TAIL-09 (cover letter) / TAIL-10 (ATS parse check).
- `.planning/PROJECT.md` — the ethical hard line (reorder / re-weight / suggest / flag, never invent) and validated key decisions (structured CV, Tectonic pinning, one ranking call per listing).
- `.planning/STATE.md` — blocking unknown #1 (real `.tex` unmeasured; stays open).

### Architecture & design contract
- `.planning/research/ARCHITECTURE.md` §4.2 Flow B (L272–336) — the tailor pipeline and the C13 verify gate.
- `.planning/research/ARCHITECTURE.md` §7.1 (L613–621) two-canonical-documents rule; §7.2 (L623–655) the `cv.yaml` shape; **§7.3 (L664–715) the patch operations** (inc. the verbatim "no field becomes text in the PDF" argument at L713); §7.4 (L717–731) `apply_patch` steps and `RenderPlan.changes` as the change log; §7.5 (L733–746) risks CV-R1..CV-R8.
- `.planning/research/ARCHITECTURE.md` §9.1 (L925–943) — `cv_artifacts` sketch and repository-level blocked enforcement.
- `.planning/research/ARCHITECTURE.md` **§10 (L997–1079)** — §10.2 result shape (L1033–1047), **§10.3 the 10 checks (L1053–1064)**, §10.4 block-don't-repair (L1066–1070), §10.5 two lines of defence (L1072–1079).
- `.planning/research/ARCHITECTURE.md` §0 A1 (two-canonical-documents rule), lines 103–106 components C9/C11/C12, lines 125–197 project structure.

### Pitfalls (anti-fabrication)
- `.planning/research/PITFALLS.md` **P6 (L164–190)** — 96.7% baseline unsupported-claim rate; typed ID patch, immutable bullet text, ship verification *with* tailoring as a gate, block-don't-repair, human checkpoint.
- `.planning/research/PITFALLS.md` P13 (L378–400) — verification-stage fixtures (`facts`, `patch`, extracted text → pass/fail, no LLM/compiler/network); P11; P14 (failure-path tests incl. "a blocked artefact is never downloadable").
- `.planning/research/PITFALLS.md` P6 recovery row (L795), reflow pitfall (L757, `page_count <= max_pages` is a warning, never auto-truncate), "Things that appear complete" (L772).

### Stack
- `.planning/research/STACK.md` §Q6 (LaTeX in Docker, Tectonic caveats, structured-CV-as-data rationale) and §Q7 (opencode structured output; `format` vs `outputFormat` — verify against `/doc`).
- `.planning/research/FEATURES.md` TS-11/TS-12 and Gap 5.

### Prior phase context (binding decisions)
- `.planning/phases/04-cv-fact-store-latex-compile-spike/04-CONTEXT.md` — D-58..D-77: D-63/D-64 (frozen hierarchical IDs), D-65 + C-1 (§7.2 shape), D-66 (factstore fails loudly, no defaults), D-67 (escape choke point), D-71 (template location), D-72 (golden must prove it can fail), D-75 (Tectonic cached-only; verify flag), D-76 (engine seam + DI), D-77 (`cv_repo.snapshot_version`).
- `.planning/phases/05-ranking-core-value/05-CONTEXT.md` — D-81 (requirements + evidence ids stored in the ranking call — Phase 6 reads them), D-83 (rubric override must route through `parts` + `sanitize`), D-88 (detached non-blocking stage precedent), D-91/92/93 (spend caps, reserve-then-call lock), D-94 (`fact_store_absent` skip + `load_facts` error inheritance), D-96 (`GET /listings/{id}` detail page).

### Code anchors
- `app/domain/cv.py` — `Bullet`/`Entry`/`Section`/`CvFacts`, `iter_fact_ids` (the grounding set), `ChangeRecord`/`RenderPlan`/`_identity_plan`, and the `apply_patch` stub (L465, raises `UnsupportedPatchOp`) to replace.
- `app/cv/factstore.py` — `CvFactStoreError`, `load_facts`, `fact_store_report`.
- `app/latex/` — `base.py` (`CompileResult`, `LatexEngine`), `compile.py` (`extract_pdf_text` L66, `TectonicEngine`, `_count_pages`), `render.py`, `env.py` (escape choke point), `templates/cv.tex.jinja`.
- `app/domain/tex.py` — `escape_tex`, `normalise_for_compare`, `facts_present_in`, `sanitise_preamble`.
- `app/db/models.py` — `CvArtifact` (L399–431, incl. `ck_cv_artifacts_compile_status`), `Score` (L351–384).
- `app/db/repositories/cv_repo.py` (CvVersion only) and `score_repo.py` (`upsert_score`, `read_score_for_listing`, `latest_for_listings`).
- `app/pipeline/rank.py` (fact-store load, skip reasons, grounding) and `app/pipeline/run.py` (stage wiring, `asyncio.to_thread` discipline).
- `app/llm/base.py` (`complete_structured`; `parts` is the only untrusted channel) and `app/llm/builders.py`.
- `app/api/listings.py` (`listing_detail`), `app/api/health.py`, `app/config.py` (one `Settings`), `tests/test_config.py` (surface + absence contracts), `tests/conftest.py` (fixtures incl. `OfflineLLMBackend`).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `apply_patch` / `_identity_plan` / `iter_fact_ids` / `ChangeRecord` / `RenderPlan` in `app/domain/cv.py` — the patch engine replaces the stub body; the ID-grounding set and change-log type already exist.
- `render_plan_to_tex` + `make_latex_env` (escape already enforced) + `TectonicEngine.compile`/`extract_pdf_text` — the whole render→compile→read-text chain is built; Phase 6 orchestrates it and does not re-implement it.
- `get_llm_backend()` and `complete_structured` — reuse for the single `TailoringPatch` call; `schema.model_json_schema()` plumbing already exists.
- `cv_repo.snapshot_version` / `current_version` — gives `base_cv_version_id` and the version guard's reference point.
- `score_repo.read_score_for_listing` — supplies the stored requirement gaps (D-110's precondition).
- `fact_store_report` / `load_facts` — the `fact_store_absent` skip and error taxonomy carry over unchanged.
- The ranking stage's reserve-then-call spend-cap machinery — reused wholesale for tailoring (D-119).

### Established Patterns
- Port + adapter + DI factory + `app.dependency_overrides` in tests (`get_llm_backend`, `get_latex_engine`) — follow for any new verifier/artifact seam.
- Repositories are the only place SQL lives, take an `AsyncSession`, and never commit — caller owns the transaction (`cv_repo`, `score_repo`).
- `app.domain.*` is pure (must not import httpx/sqlalchemy/jobspy/jinja2/subprocess); contract types are `extra="forbid"`; failures are values, not exceptions, at the port boundary.
- Every numeric ceiling is a `Settings` field, and `tests/test_config.py` surface + absence scans (`REQUIRED_SETTINGS_FIELDS`, `LIMIT_FIELDS`, `SCANNED_DIRS`) must be updated for any new Phase 6 ceiling.
- Migrations are one-way and the schema is only ever built by `alembic upgrade head` (never `create_all`); `tests/db/test_migration_contract.py` pins the head.
- Detached background task + single-flight + `coalesce`-style outcome reporting is the established pipeline-stage shape (D-88).

### Integration Points
- `app/pipeline/tailor.py` (new) — called from the tailoring page's generate/compile actions; reads FactStore + listing + score; uses `get_llm_backend()`; writes `cv_artifacts`.
- `app/verify/` (new) — invoked between render and persistence; consumes the RenderPlan (Layer 1) and `extract_pdf_text` output (Layer 2).
- `app/db/repositories/cv_repo.py` — extend with `CvArtifact` create/read + the `ok`-only selection used by download/link (D-118).
- `app/main.py` router registration + new templates under `app/web/templates/html/`.
- `app/config.py` + `tests/test_config.py` — new tailoring/verification settings.

</code_context>

<specifics>
## Specific Ideas

- The load-bearing guarantee to preserve verbatim: §7.3 L713 — *"There is no field anywhere in this schema that becomes text in the PDF."* Any new field added to `TailoringPatch` must be id-, enum-, or UI-only; a free-text field on the path to the PDF breaks the phase's core safety property.
- The verification stage must be testable **without** an LLM, compiler, or network (PITFALLS P13): fixtures of `facts` + `patch` + extracted text → expected pass/fail.
- The blocked-artifact rule needs a failure-path test asserting a blocked artifact is never downloadable (PITFALLS P14).
- The roadmap's `_GROUNDING_REVIEW_THRESHOLD`-style similarity banding is a design item for the planner to resolve while designing check 6 and confidence tiers — it is not existing code.

</specifics>

<deferred>
## Deferred Ideas

- §10.4's one-click "drop this bullet and re-render" recovery affordance — deferred; Phase 6 recovery is a fresh tailor (D-118).
- Artifact retention/pruning / a cap on historical `cv_artifacts` rows — Phase 8 (Operations + Polish).
- `_GROUNDING_REVIEW_THRESHOLD`-style similarity banding for confidence tiers — planner to design, not implement speculatively here.
- Cover letter (v2 TAIL-09) and ATS parse check (v2 TAIL-10).

</deferred>

---

*Phase: 6-Tailoring + Verification*
*Context gathered: 2026-09-24*
