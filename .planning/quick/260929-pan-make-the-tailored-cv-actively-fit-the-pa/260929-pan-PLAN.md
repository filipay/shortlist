---
phase: 260929-pan
plan: "01"
type: execute
wave: 1
depends_on: []
files_modified:
  - app/domain/cv.py
  - app/pipeline/tailor.py
  - app/api/tailoring.py
  - tests/domain/test_page_trim.py
  - tests/pipeline/test_page_trim.py
  - tests/api/test_tailoring_review.py
autonomous: true
must_haves:
  truths:
    - "A tailored CV whose compiled PDF exceeds meta.max_pages is re-rendered with the lowest-value surviving bullet dropped, then recompiled, until the page count fits or the bounded pass count / candidate list is exhausted."
    - "Every dropped bullet is a real drop_bullet operation carrying a non-empty reason, so it appears in the change log (RenderPlan.changes / cv_artifacts.change_log_json) and on the compile response — the trim is never silent."
    - "The trim never invents, rewrites or reorders text: only WHOLE bullets are removed, Bullet.text is never rebuilt, and no entry's org/title/dates/location is ever orphaned."
    - "A CV that already fits compiles exactly once and stores a patch_json byte-identical to the input patch — the no-trim path is unchanged."
    - "The loop is bounded: at most MAX_PAGE_TRIM_PASSES extra compiles, a failed trim recompile falls back to the last good compile, and a CV still over budget after the bound is NOT blocked (page_budget stays WARN-only)."
  artifacts:
    - "app/domain/cv.py — a pure next_page_trim(plan, patch, *, max_pages) selector returning the lowest-value surviving bullet as a DropBullet, or None; plus a page-trim reason constant; both in __all__."
    - "app/pipeline/tailor.py — the bounded render→compile→drop loop inside compile_tailored, with a MAX_PAGE_TRIM_PASSES module constant; the final effective patch and final plan's change log are what get persisted."
    - "app/api/tailoring.py — the compile ok response (_compiled_fragment) discloses the compiled change log's drop records with their reasons."
    - "tests/domain/test_page_trim.py — the pure selector matrix."
    - "tests/pipeline/test_page_trim.py — the loop's fit, bound, identity, exhaustion and fallback behaviour with a stub engine."
    - "tests/api/test_tailoring_review.py — the compile response discloses the trim."
  key_links:
    - "next_page_trim reads only the plan's own carried order (reweight weight DESC, demoted last, moves applied by _ordered_bullets) and the effective patch's already-targeted ids — no new score, no clock, no I/O."
    - "The effective patch is the input patch plus accumulated DropBullet ops; apply_patch re-grounds and re-validates it, so a trim can never fabricate an op and a duplicate-target op is rejected."
    - "verify_plan(facts, plan, effective_patch) is re-run on the final trimmed plan+patch, so the persisted bullet_conservation check still holds."
    - "change_log_json is built from the final plan.changes, so every trim is recorded; the compile response reuses that list rather than recomputing."
---

<objective>
Make the tailored CV actively fit its page budget: after compiling, if the rendered PDF
exceeds the CV's own `meta.max_pages` budget, drop the lowest-value surviving bullets one
at a time — re-rendering and recompiling between drops — until it fits, recording a
reasoned `drop_bullet` change for every removal.

Purpose: `meta.max_pages` (default 2) already exists in the fact store and
`check_page_budget` (`app/verify/text_checks.py`) already compares against it, but that
check only emits a WARN — a four-page CV still compiles and downloads. This plan makes the
budget load-bearing without touching the never-fabricate design: the trim operates on the
structured `RenderPlan` and emits typed `DropBullet` operations over enumerated fact ids,
so text is never rewritten and every removal is auditable.

Output: a pure `next_page_trim` selector over the plan's own ordering; a bounded
render→compile→drop loop inside `compile_tailored`; and a compile response that names the
dropped bullets and their reasons.
</objective>

<context>
@.planning/STATE.md
@AGENTS.md
@app/domain/cv.py
@app/pipeline/tailor.py
@app/api/tailoring.py
@tests/verify/test_block_no_repair.py
@tests/verify/test_text_checks.py
@tests/domain/test_patch_ops.py
</context>

<tasks>

<task type="tracer" tdd="true">
  <name>Task 1: End-to-end page-budget trim — one over-budget CV drops its lowest-value bullet and recompiles to fit</name>
  <files>app/domain/cv.py, app/pipeline/tailor.py, app/api/tailoring.py, tests/domain/test_page_trim.py, tests/pipeline/test_page_trim.py</files>
  <behavior>
    - next_page_trim(plan, TailoringPatch(listing_id=1), max_pages=2) over the committed stand-in facts names the LAST bullet of the LAST entry-bearing section in the plan (for the stand-in, "bul/northwind-labs-2021/3") as a DropBullet with a non-empty reason.
    - The returned bullet id is a real fact id (`iter_fact_ids(facts)` contains it).
    - next_page_trim returns None when the entry's only candidate is excluded (its sole surviving bullet, or a bullet already named by any op).
    - A stub engine whose page counts are [3, 2] with facts.meta.max_pages == 2 is compiled exactly twice; the returned record has compile_status "ok" and page_count 2.
    - That record's patch_json carries exactly one `drop_bullet` op with a non-empty reason; its change_log_json carries exactly one record with op "drop_bullet" and that same reason as detail.
    - The compile ok response body contains the dropped bullet id and its reason.
  </behavior>
  <action>
    In app/domain/cv.py, add a module-level reason constant `PAGE_TRIM_REASON_TEMPLATE = "dropped to fit the {limit}-page budget"` beside the other module constants, and a pure function `next_page_trim(plan: RenderPlan, patch: TailoringPatch, *, max_pages: int) -> DropBullet | None`.

    The selection criterion, stated exactly (no new score is computed): the plan already carries a total value order. `_ordered_bullets` puts each entry's bullets in reweight-weight-descending order with demoted bullets at the tail and explicit moves applied afterwards, so the LAST bullet in an entry is that entry's lowest-value survivor; and `plan.sections` follows `Section.order`, so the bottom of the document is the least-relevant tail. Therefore walk `reversed(plan.sections)`, then `reversed(section.entries)`, then `reversed(entry.bullets)`, and return the first eligible bullet as `DropBullet(bullet_id=<id>, reason=PAGE_TRIM_REASON_TEMPLATE.format(limit=max_pages))`. A bullet is NOT eligible when (a) it is already named by any `BulletMove`/`BulletWeight`/`DemoteBullet`/`DropBullet` in `patch.ops` — a second op on the same bullet would be rejected by `_validate_patch` as a duplicate target — or (b) it is the entry's ONLY surviving bullet, which would leave an org/title/dates header with nothing under it. Return None when no eligible bullet exists. Add the reason constant and `next_page_trim` to `__all__`. Keep the module pure: standard library plus pydantic only, no I/O, no clock (tests/test_import_discipline.py guards this).

    In app/pipeline/tailor.py, add a module-level `MAX_PAGE_TRIM_PASSES = 6` near `_CAP_RUN_UNBOUNDED` (a loop bound, not a Settings ceiling: it caps internal compile work and needs no config surface; the upgrade path is a Settings field if it ever becomes operator-tunable). In `compile_tailored`, keep the existing Layer-1 short-circuit BEFORE the engine exactly as it is, and keep `effective_patch = patch` and `plan = apply_patch(facts, effective_patch)` for the first pass. After the FIRST `engine.compile(...)`, enter a loop: while the compile is ok and its `page_count` exceeds `facts.meta.max_pages` and fewer than `MAX_PAGE_TRIM_PASSES` trims have been applied, call `next_page_trim(plan, effective_patch, max_pages=facts.meta.max_pages)`; on a None result stop. Otherwise build a candidate patch as a new `TailoringPatch` carrying `[*effective_patch.ops, drop]`, `effective_patch.gaps` and `effective_patch.suggestions` (never mutate the input patch), re-`apply_patch` it to a candidate plan, `render_plan_to_tex` it, derive the per-hash workdir from the new tex hash, and compile it. Accept the candidate (replace effective_patch/plan/tex/compile_result) only when that recompile is ok and has a pdf_path; otherwise stop and keep the last good compile, so a failed trim never turns a valid over-budget CV into a failed artifact. Because the tex changes when a bullet is dropped, recompute tex, tex_hash, tex_path and workdir on each accepted pass and persist the FINAL values.

    Keep the stored `patch_json` as `effective_patch.model_dump(mode="json")` (identical to the input patch whenever no trim ran) and the stored `change_log_json` as `[change.model_dump(mode="json") for change in plan.changes]` from the FINAL plan, so every trim is a reasoned drop_bullet record. When at least one trim was accepted, re-run `verify_plan(facts, plan, effective_patch, now=now)` and persist THAT Layer-1 result, so the stored `bullet_conservation` check describes the plan that was actually compiled. The Layer-2 `verify_text` call already reads the final plan and the final `compile_result.page_count`.

    In app/api/tailoring.py, replace `_download_fragment(listing_id)` with `_compiled_fragment(listing_id, record)` that keeps the existing Compiled state, download link and `data-status="ok"` wrapper, and additionally renders one list item per drop record found in `record.change_log_json` (rows whose `op` is "drop_bullet"), showing the target id and its reason. Escape every value (this module already uses `html.escape` for fragments) and render nothing extra when there are no drop records. Call it from the compile route's `record.compile_status == "ok"` branch, passing the record.
  </action>
  <verify>
    <automated>/workspace/job-search/.venv/bin/python -m pytest tests/domain/test_page_trim.py tests/pipeline/test_page_trim.py -x -q</automated>
  </verify>
  <done>One over-budget CV drops its lowest-value bullet, recompiles, stores an ok record whose patch_json and change_log_json carry the reasoned drop, and the compile response names the dropped bullet and reason; the pure selector names exactly that lowest-value bullet.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Bound, identity, exhaustion and recompile-failure edges</name>
  <files>tests/pipeline/test_page_trim.py, tests/domain/test_page_trim.py, app/pipeline/tailor.py, app/domain/cv.py</files>
  <behavior>
    - A stub engine whose first compile returns page_count == max_pages is called exactly once and the stored patch_json equals the input patch's model_dump(mode="json") exactly.
    - With page counts that never fit (for example always 9) and the stand-in facts, the engine is called at most MAX_PAGE_TRIM_PASSES + 1 times and the record is still compile_status "ok" (the page_budget check warns, it never blocks).
    - next_page_trim returns None when the only remaining eligible bullets are each an entry's sole survivor; the loop stops there rather than orphaning an entry header.
    - A bullet already named by a BulletWeight/DemoteBullet/BulletMove/DropBullet in the input patch is never returned as a trim candidate, and no InvalidPatchError is raised for a duplicate target.
    - When a trim pass's recompile returns ok=False, the artifact keeps the previous good compile's page_count and is not "failed" or "blocked" because of the trim.
    - With the clean committed extraction and a trim applied, verify_plan(facts, plan, effective_patch) passes all five Layer-1 checks on the final plan.
    - tests/verify/test_block_no_repair.py and tests/verify/test_text_checks.py stay green (the blocked/failed paths and the three-page WARN are unchanged).
  </behavior>
  <action>
    Extend tests/pipeline/test_page_trim.py and tests/domain/test_page_trim.py with focused cases for every behaviour above, reusing the existing hermetic shape from tests/verify/test_block_no_repair.py: a temporary artifacts_dir, an injected fake engine whose compile returns a scripted sequence of page counts, and monkeypatch of `tailor_module.extract_pdf_text` to the committed clean extraction at `tests/fixtures/verify/three_page_extract.txt` (all checks pass there, so the assembly is exercised end to end without a LaTeX engine or a socket). Reuse `tests.verify.fixtures.load_standin_facts` and `tests.pipeline.test_rank_stage._add_listing`.

    For the pure selector cases, build facts in memory in the style of tests/domain/test_patch_ops.py and drive next_page_trim directly: assert the bottom-of-document bullet is chosen first, that a reweight/demote/move/drop target is skipped, and that an entry with a single surviving bullet is skipped so an entry header is never left empty. If any edge fails, tighten ONLY next_page_trim's eligibility rules or the loop's stop conditions in app/pipeline/tailor.py — do not add a scoring heuristic, a second selector, a new dependency, a Settings field or a config knob.

    Do NOT add any branch that reacts to a verification finding: the trim loop reads the compiled page count and facts.meta.max_pages only. The Layer-1 short-circuit and the no-repair writes for a blocked/failed row are untouched.
  </action>
  <verify>
    <automated>/workspace/job-search/.venv/bin/python -m pytest tests/pipeline/test_page_trim.py tests/domain/test_page_trim.py tests/verify/test_block_no_repair.py tests/verify/test_text_checks.py -q</automated>
  </verify>
  <done>An in-budget CV is byte-identical and compiles once; a never-fitting CV stops at the bound as an ok artifact; exhaustion, already-targeted and sole-survivor bullets are all handled; a failed trim recompile falls back to the last good compile; the final trimmed plan passes Layer 1; the no-repair and page-budget suites are green.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Persisted audit, multi-trim change log and regression pin</name>
  <files>tests/pipeline/test_page_trim.py, tests/api/test_tailoring_review.py, app/api/tailoring.py</files>
  <behavior>
    - With a stub engine whose page counts force several trims, the stored change_log_json contains one drop_bullet record per trim, each with a non-empty detail, in the order the trims were applied, and patch_json contains the same number of drop_bullet ops.
    - The stored page_count equals the final compile's page count and the final patch_json equals the effective patch (input ops followed by the trim drops).
    - The compile ok response lists every drop record with its target id and reason (not only the first).
    - _compiled_fragment returns the Compiled state, the download link and data-status="ok" when the record carries no drop records, so the no-trim response is unchanged in substance.
    - The named must-keep suites are green: tests/verify/test_text_checks.py::test_a_three_page_extract_only_warns, tests/golden/test_render_bytes.py (the committed baseline renders byte-identically), tests/domain/test_cv_ids.py and tests/cv/test_llm_extract.py.
  </behavior>
  <action>
    Extend tests/pipeline/test_page_trim.py with a multi-trim case (page counts like [5, 4, 3, 2]) asserting the persisted change_log_json and patch_json carry every drop with its own reason, and that page_count is the final value. Add a focused unit case for `_compiled_fragment` in tests/api/test_tailoring_review.py: call it directly with a fabricated `cv_artifact_repo.CvArtifactRecord` carrying a change_log_json with two drop_bullet rows and assert both ids and both reasons appear, and a second call with an empty change log still returns the download affordance and the ok status wrapper.

    Then run the named regression suites and the full hermetic pass; if the golden baseline shifts, the cause is a change outside the plan's declared files — revert it rather than regenerating the baseline (the fixture's max_pages is 2 and the fixture compiles in budget, so no trim should ever reach it).

    Do NOT change VERIFIER_VERSION, the verification schema, the cv_artifacts schema, or add an Alembic revision: the trim is persisted in the existing patch_json and change_log_json columns. Do NOT add a column, a migration, a dependency, or a Settings field.
  </action>
  <verify>
    <automated>/workspace/job-search/.venv/bin/python -m pytest tests/api/test_tailoring_review.py tests/pipeline/test_page_trim.py tests/golden/test_render_bytes.py tests/domain/test_cv_ids.py tests/cv/test_llm_extract.py tests/verify/test_text_checks.py -q</automated>
  </verify>
  <done>Multiple trims are each recorded in the change log and disclosed in the compile response; the artifact's page_count and patch_json reflect the final trimmed state; the committed golden baseline is byte-identical and every named regression suite is green.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| structured CV plan → compiled PDF | the trim removes existing facts; no free text is authored or echoed into the document |
| pipeline → persisted artifact | drops and their reasons are written to the existing change-log column and read back by the compile response |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-260929-PAN-01 | Repudiation | a silent page trim (`compile_tailored`) | medium | mitigate | Every removal is a typed `DropBullet` with a required non-empty reason; it becomes a `ChangeRecord` in `plan.changes`, is persisted in `change_log_json`, and is disclosed in the compile response. |
| T-260929-PAN-02 | Tampering | the trim editing CV content | low | mitigate | `next_page_trim` returns only a `DropBullet` over an existing graded fact id; `apply_patch`/`_validate_patch` re-ground and re-validate it; `Bullet.text` is never rebuilt and no entry's org/title/dates/location is orphaned. |
| T-260929-PAN-03 | Denial of service | an unbounded recompile loop | low | mitigate | `MAX_PAGE_TRIM_PASSES` cap plus candidate exhaustion plus a recompile-failure fallback; a CV still over budget remains an ok artifact and the page_budget check stays WARN-only. |
| T-260929-PAN-SC | Tampering | package installs | low | accept | No package install and no new dependency in this plan. |

## Non-goals (explicitly not changed)

No new DB column, no Alembic migration (head stays 0004), no new dependency, no new LLM call,
and no new Settings field or `.env` knob. `check_page_budget` stays WARN-only. The Layer-1
short-circuit, the no-repair blocked/failed writes (D-115/D-118), `TAILOR_SYSTEM_PROMPT`,
`VERIFIER_VERSION`, the `cv_artifacts` schema and the committed `tests/golden/base.rendered.tex`
baseline are unchanged.
</threat_model>

<verification>
- `/workspace/job-search/.venv/bin/python -m pytest tests/domain/test_page_trim.py tests/pipeline/test_page_trim.py tests/api/test_tailoring_review.py tests/verify/test_text_checks.py tests/verify/test_block_no_repair.py tests/golden/test_render_bytes.py tests/domain/test_cv_ids.py tests/cv/test_llm_extract.py -q`
- `/workspace/job-search/.venv/bin/python -m ruff check app/domain/cv.py app/pipeline/tailor.py app/api/tailoring.py tests/domain/test_page_trim.py tests/pipeline/test_page_trim.py`
- Full hermetic pass: `/workspace/job-search/.venv/bin/python -m pytest -q` (the `live` and `latex` lanes stay deselected by the repo's `addopts`).
- Inspect the diff: only the six declared files change; no migration file, no schema file, no config change, no golden-baseline change.
</verification>

<success_criteria>
- A compiled CV over `meta.max_pages` is dropped-to-fit one whole bullet at a time, with every removal a reasoned `drop_bullet` in the change log and named on the compile response.
- A CV already in budget compiles exactly once and stores a patch byte-identical to the input.
- The loop is bounded, never orphans an entry header, falls back to the last good compile on a failed trim recompile, and leaves a still-over-budget CV downloadable with the WARN-only page_budget check.
- No new column, migration, dependency or Settings field; the named must-keep suites are green and the golden baseline is byte-identical.
</success_criteria>

<output>
Create `.planning/quick/260929-pan-make-the-tailored-cv-actively-fit-the-pa/260929-pan-SUMMARY.md` when done.
</output>
