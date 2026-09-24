---
phase: 06-tailoring-verification
plan: 01
subsystem: llm-pipeline
tags: [tailoring, pydantic, discriminated-union, latex, verification, htmx, fastapi, sqlalchemy]

requires:
  - phase: 04-cv-rendering
    provides: RenderPlan, the deterministic renderer with its single Jinja escape choke point, TectonicEngine, extract_pdf_text, the cv.yaml fact-store loader
  - phase: 05-ranking
    provides: stored `scores.requirements` (D-110), llm_call_repo + the reserve-then-call lock, score_repo.read_score_for_listing, the RANK_SKIP_* vocabulary pattern, cv_repo.current_version
provides:
  - the real five-operation `apply_patch` over enumerated fact IDs; `TailoringPatch`/`PatchOp`
  - `facts_hash`/`GuardResult`/`verify_original_matches`; `InvalidPatchError`; `UnsupportedPatchOp` deleted
  - `app/verify` Layer-1 `verify_plan` (the five deterministic checks)
  - `app/pipeline/tailor` — the one tailoring call, its frozen prompt, its rolling-24h spend share, and `compile_tailored`
  - `cv_artifact_repo` with the `ok`-only access control
  - the `/listings/{id}/cv` page plus generate / compile / pdf routes
affects: [06-02, 06-03, 06-04, 07-apply-and-track]

actuals:
  tokens: 30755
  tasks: 3
  # 3 task commits + 1 lint/style fix + this plan's metadata commit.
  commits: 5
  plan_head_before: c82f13657a7ca63b00ad5e3db469ec5a4775bd41

tech-stack:
  added: []
  patterns:
    - "a typed patch whose fields are enumerated ids, closed enums and bounded numbers — no field becomes PDF text"
    - "all-or-nothing patch validation before any plan is built (no partial apply, no auto-repair)"
    - "Layer-1 deterministic verification before any compile; `passed` is a value, never an exception"
    - "an `ok`-only repository predicate as the artifact-access control"

key-files:
  created:
    - app/verify/base.py
    - app/verify/plan_checks.py
    - app/verify/__init__.py
    - app/pipeline/tailor.py
    - app/db/repositories/cv_artifact_repo.py
    - app/api/tailoring.py
    - app/web/templates/html/tailoring.html
    - tests/domain/test_patch_ops.py
    - tests/verify/fixtures.py
    - tests/verify/test_plan_checks.py
    - tests/fixtures/verify/base_extract.txt
    - tests/pipeline/test_tailor_stage.py
    - tests/api/test_tailoring_generate.py
  modified:
    - app/domain/cv.py
    - app/db/repositories/llm_call_repo.py
    - app/config.py
    - app/main.py
    - static/vendor/app.css
    - tests/domain/test_cv_ids.py
    - tests/test_config.py
    - tests/test_auth_seam.py

key-decisions:
  - "The tailoring patch has NO field that becomes PDF text; the model returns ids only, so even a successful prompt injection cannot reach the renderer"
  - "An empty patch and `patch=None` are both the identity plan, so the three shipped no-argument `apply_patch(facts)` callers keep their exact behaviour"
  - "Reweight means declaration-order stable-sorted by weight DESCENDING with an unreweighted default of 1.0; demote lands after every non-demoted bullet in declaration order; a move is the explicit positional override"
  - "`extra=forbid` on every op and `TailoringPatch` (pinned A4) — deliberately diverging from RankingResponse's `extra=ignore` so `model_json_schema()` emits `additionalProperties: false` and constrains the model at the wire"
  - "The rolling-24h ceiling is read through a purpose-aware `calls_since` and the reserve-then-call lock is imported from `rank` — one process, one in-flight budget, no per-run tailoring ceiling (O1)"
  - "A Layer-1 `fail` short-circuits before the engine and writes a `blocked` row with NULL `tex_path`/`pdf_path`; the `ok`-only repository selection makes a non-ok artifact unreachable (D-115/D-118)"

patterns-established:
  - "Typed-patch tailoring: reorder/reweight/demote/drop/reorder-section over enumerated fact IDs, never free text"
  - "A verification result as a value with `extra=forbid` as the redaction control (ids, counts, short details, hashes only)"
  - "Per-hash compile workdirs so a new artifact row never overwrites an older row's PDF (D-117)"

requirements-completed: [TAIL-01, TAIL-02, TAIL-03]

coverage:
  - id: D1
    description: "The five operations are real, typed and validated all-or-nothing over enumerated fact IDs; UnsupportedPatchOp is gone"
    requirement: TAIL-02
    verification:
      - kind: unit
        ref: "tests/domain/test_patch_ops.py"
        status: pass
      - kind: unit
        ref: "tests/domain/test_cv_ids.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "Bullet.text is byte-identical through every operation; the patch only reorders/reweights/demotes/drops/reorders"
    requirement: TAIL-03
    verification:
      - kind: unit
        ref: "tests/domain/test_patch_ops.py#test_every_operation_preserves_bullet_text_byte_for_byte"
        status: pass
    human_judgment: false
  - id: D3
    description: "One listing produces one TailoringPatch from exactly one complete_structured call, recorded purpose=tailor with run_id=None and counted by the purpose-aware rolling-24h read"
    requirement: TAIL-01
    verification:
      - kind: unit
        ref: "tests/pipeline/test_tailor_stage.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "Layer 1 runs before any compile and a fail writes a blocked row with NULL paths and a non-empty verification_json"
    requirement: TAIL-02
    verification:
      - kind: unit
        ref: "tests/verify/test_plan_checks.py"
        status: pass
      - kind: integration
        ref: "tests/api/test_tailoring_generate.py#test_compile_short_circuits_a_layer_one_fail_to_a_blocked_row"
        status: pass
    human_judgment: false
  - id: D5
    description: "The end-to-end path: a scored listing generates a patch, compile persists an ok artifact row, and the pdf route serves it"
    requirement: TAIL-01
    verification:
      - kind: integration
        ref: "tests/api/test_tailoring_generate.py"
        status: pass
    human_judgment: false
  - id: D6
    description: "The dedicated tailoring page exists, is registered, and every route carries the auth seam"
    verification:
      - kind: unit
        ref: "tests/test_auth_seam.py"
        status: pass
      - kind: integration
        ref: "tests/api/test_tailoring_generate.py#test_page_renders_rank_first_for_an_unscored_listing"
        status: pass
    human_judgment: false
  - id: D7
    description: "A tailored plan compiles to a real PDF through the pinned Tectonic engine inside the container"
    verification:
      - kind: other
        ref: "docker compose run --rm app pytest -m latex"
        status: unknown
    human_judgment: true
    rationale: "The hermetic default lane overrides the engine with a stub (D-69), so the real engine compile of a tailored RenderPlan is UNRUN here. Only the container's latex lane can confirm it."

duration: 47min
completed: 2026-09-24
status: complete
---

# Phase 06 Plan 01: Tracer — one ranked listing → typed patch → verified plan → compiled PDF → download

**A typed, id-grounded tailoring patch replaces the `apply_patch` stub, runs a five-check Layer-1 verification before any compile, and carries one scored listing all the way to a served PDF through the dedicated tailoring page.**

## Performance

- **Duration:** 47 min
- **Started:** 2026-09-24T15:36:54Z
- **Completed:** 2026-09-24T16:24:01Z
- **Tasks:** 3
- **Files modified:** 22

## Accomplishments

- Replaced the `apply_patch` stub with the real five-operation engine (`move_bullet` / `reweight_bullet` / `demote_bullet` / `drop_bullet` / `reorder_section`) over a discriminated `PatchOp` union, validated all-or-nothing (unknown id, duplicate target, cross-entry move, emptied section) with byte-exact ID grounding. `UnsupportedPatchOp` is deleted; `Bullet.text` is never rebuilt.
- Stood up `app/verify` with the Layer-1 deterministic pre-check (`id_containment`, `entity_resolvable`, `bullet_conservation` both directions, `temporal_consistency`, `requirement_evidence`) — a result value, never an exception.
- Added the single tailoring call: one `complete_structured` returning one `TailoringPatch`, a frozen system prompt with no interpolation, one `llm_calls` row with `purpose="tailor"` / `run_id=None`, and a purpose-aware rolling-24h ceiling that actually counts tailor rows.
- Wired the thin end-to-end path: generate → review fragment (no artifact row), compile → re-ground → Layer-1 verify → render → compile → persist a `cv_artifacts` row, and serve the latest `ok` PDF inline.
- 1145 tests pass in the hermetic lane; `ruff` clean; `compileall` clean.

## Task Commits

Each task was committed atomically:

1. **Task 1: The real five-operation patch engine over enumerated IDs** — `3b35f28` (feat)
2. **Task 2: The one tailoring call, its frozen prompt, and its share of the spend ceiling** — `e2cafa3` (feat)
3. **Task 3: The thin end-to-end path — verify Layer 1, persist the artifact, serve the page** — `404d995` (feat)

**Plan metadata:** _(this commit)_ (docs: complete plan)

## Files Created/Modified

- `app/domain/cv.py` — the real `apply_patch`, `BulletMove`/`BulletWeight`/`DemoteBullet`/`DropBullet`/`ReorderSection`, `PatchOp`, `TailoringPatch`, `GapFinding`, `facts_hash`, `GuardResult`, `verify_original_matches`, `InvalidPatchError`; `UnsupportedPatchOp` removed
- `app/verify/base.py` — `VERIFIER_VERSION`, `CheckStatus`, `CheckResult`, `VerificationResult`
- `app/verify/plan_checks.py` — the five Layer-1 checks and `verify_plan`
- `app/verify/__init__.py` — the package barrel (its own package; may import `rapidfuzz` in 06-02)
- `app/pipeline/tailor.py` — `TAILOR_SKIP_*`/`TAILOR_SKIP_LABELS`, `TAILOR_SYSTEM_PROMPT`, `build_tailoring_parts`, `tailor_listing`, `compile_tailored`, `tailoring_skip_reason`; reuses `rank._reserve`/`_release`/`_cv_facts_text`
- `app/db/repositories/llm_call_repo.py` — purpose-aware `calls_since`; `rank_calls_since` now delegates
- `app/db/repositories/cv_artifact_repo.py` — `CvArtifactRecord`, `insert_artifact`, `latest_for_listing(ok_only=…)`, `history_for_listing`
- `app/api/tailoring.py` — the four routes
- `app/web/templates/html/tailoring.html` — the page shell
- `app/config.py` — `tailoring_enabled`
- `app/main.py` — router registration
- `static/vendor/app.css` — rules for the four new template classes
- Tests — `tests/domain/test_patch_ops.py`, rewritten `tests/domain/test_cv_ids.py`, `tests/verify/{fixtures,test_plan_checks}.py`, `tests/fixtures/verify/base_extract.txt`, `tests/pipeline/test_tailor_stage.py`, `tests/api/test_tailoring_generate.py`, `tests/test_config.py`, `tests/test_auth_seam.py`

## Decisions Made

- **No field of the patch becomes PDF text.** Every op field is an enumerated id, a closed enum, a bounded number, or UI/audit-only text; the renderer consumes only a `RenderPlan`.
- **Empty patch and `patch=None` are both the identity plan**, preserving the three shipped no-argument `apply_patch(facts)` callers byte-for-byte.
- **Ordering semantics pinned:** reweight = declaration-order stable sort by weight DESCENDING (unreweighted default 1.0); demote falls after every non-demoted bullet in declaration order; move is the explicit positional override applied after base ordering.
- **`extra="forbid"` on every patch type** (pinned A4), diverging from `RankingResponse`'s `extra="ignore"` so the JSON Schema emits `additionalProperties: false`.
- **Shared, not duplicated, spend accounting (O1):** the tailoring call reads a new purpose-aware `calls_since` and reserves through `rank._reserve`/`_release`; no per-run tailoring ceiling and no new numeric ceiling.
- **Artifact paths are unique per content hash** — a per-hash compile workdir keeps each compile's `cv.pdf` distinct, so a new row never overwrites an older row's PDF (D-117).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added stylesheet rules for the new template classes**
- **Found during:** Task 3 (the full-suite run)
- **Issue:** `tests/test_stylesheet_coverage.py` requires every literal class in a template to have a rule in `static/vendor/app.css`; the four new classes (`tailoring-review`, `tailoring-empty`, `cv-generate`, `cv-download`) had none, so the guard failed.
- **Fix:** Appended four rules to the hand-written section at the end of `static/vendor/app.css`, matching the existing `.detail-empty`/`.listing-detail-link` style.
- **Files modified:** `static/vendor/app.css`
- **Verification:** `tests/test_stylesheet_coverage.py` passes; full suite green.
- **Committed in:** `404d995` (Task 3 commit)

**2. [Rule 1 - Bug] Reworded two docstrings that broke exact-count acceptance greps**
- **Found during:** Task 3 (running the plan's acceptance greps)
- **Issue:** `grep -c "Depends(current_user)" app/api/tailoring.py` returned 5 (four routes plus a docstring mention) where the plan required 4; `grep -c "create_all" app/db/repositories/cv_artifact_repo.py` returned 1 (a docstring mention) where the plan required 0.
- **Fix:** Reworded the `app/api/tailoring.py` and `cv_artifact_repo.py` docstrings to drop the literal tokens. No code change.
- **Files modified:** `app/api/tailoring.py`, `app/db/repositories/cv_artifact_repo.py`
- **Verification:** both greps now report the required counts.
- **Committed in:** `404d995` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both are direct consequences of this plan's own files (a new template and a plan acceptance grep). No scope creep; no behavioural change.

## Issues Encountered

- **The plan's route-registration acceptance command inspects `app.routes` directly**, but FastAPI 0.141.1 wraps `include_router` in a `_IncludedRouter` and does not flatten leaf paths onto `app.routes` — the exact command reports the four routes "missing". The intent (the four routes are registered and reachable) is proven instead by the project's existing `_leaf_routes` walk, and `tests/test_auth_seam.py::test_the_walk_reaches_the_application_leaf_routes` now asserts the four paths. This is a plan-text bug, not a code bug; no code change was made to satisfy it.
- **`apply_patch` deliberately carries the SAME `Bullet` objects through from the fact store**, so an in-place mutation on a built plan also mutates the source facts. The Layer-1 failure fixtures were adjusted to mutate a deep copy, and that aliasing is now documented on the test helper.

## Known Stubs

None. The path serves a real `cv_artifacts` row and a real PDF from a stub or real engine; the only intentionally thin seam is the Layer-2 hook in `compile_tailored`, which is a named call site reserved for 06-02.

## Next Phase Readiness

- The skeleton is in place for 06-02 (Layer-2 PDF-text post-checks, the metric tokeniser, the advisory similarity band), 06-03 (the stale-patch 409 guard and the full review change log) and 06-04 (history and the inline/attachment split).
- **UNRUN:** the real Tectonic compile of a tailored plan is exercised only by the container `latex` lane; the hermetic pass uses a stub engine (D-69). See coverage D7.

---
*Phase: 06-tailoring-verification*
*Completed: 2026-09-24*

## Self-Check: PASSED

- All 13 created files exist; `06-01-SUMMARY.md` exists.
- All 3 task commits exist: `3b35f28`, `e2cafa3`, `404d995` (plus the `263e65e` lint fix and this metadata commit).
- `git rev-list --count c82f136..HEAD` = 5, matching `actuals.commits`.
