---
phase: 07-assisted-apply-tracker
plan: 05
subsystem: [api, ui, database]
tags: [fastapi, jinja2, htmx, alpine, screening-questions, apply_config, htmx-swap, copy-to-clipboard, no-submit]

# Dependency graph
requires:
  - phase: 07-assisted-apply-tracker
    provides: "07-02's GET /listings/{id}/apply ready page — the surface this plan's region extends"
  - phase: 07-assisted-apply-tracker
    provides: "07-03's app.pipeline.draft (guarded, audited drafting) + app.verify.screening grounding + screening_draft_repo + apply_drafting_enabled"
provides:
  - "app/db/repositories/apply_config_repo.py: read_questions/write_questions over the apply_config singleton with a DEFAULT_QUESTIONS fallback"
  - "GET /settings: the Screening questions editor (a plain full-page POST) — the user-defined question list (D-124)"
  - "app/web/templates/html/_screening_drafts.html: the #apply-answers region — per-question blocks, evidence chips, the unsupported warning, the Copy answer control and the confirm-guarded removal"
  - "POST /listings/{id}/apply/draft, /apply/question, /apply/draft/delete — the explicit, identity-seamed actions"
affects: [phase-8, v2-APPLY-07-export]

# Actuals (#2632) — pairs with the plan's estimate (62000 tokens, 2 tasks, low confidence).
actuals:
  tokens: 10458
  tasks: 2
  commits: 2
  plan_head_before: 95785205ef2e5230caef72fe08740ab79f697c68

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "The question list is a singleton config document (apply_config, id=1) with a code-level DEFAULT_QUESTIONS fallback for an ABSENT row; an explicit empty list is preserved as its own state"
    - "The package page stays ZERO-LLM on GET; only the explicit Draft answers action spends a call, and the stage's one audit row is committed before any refusal so an attempted call always survives"
    - "Model answers render as escaped text (never |safe, never an input value); consumption is copy-to-clipboard per answer and no submit path exists"
    - "A per-answer delete is scoped by (listing_id, draft_id); an ad-hoc question appends by reusing replace_for_listing rather than a new repository surface"

key-files:
  created:
    - app/db/repositories/apply_config_repo.py
    - app/web/templates/html/_screening_drafts.html
    - tests/db/test_apply_config_repo.py
  modified:
    - app/api/settings.py
    - app/web/templates/html/settings.html
    - app/api/apply.py
    - app/web/templates/html/apply.html
    - app/web/templates/html/base.html
    - static/vendor/app.css
    - tests/api/test_settings_page.py
    - tests/api/test_apply_package.py
    - tests/test_auth_seam.py

key-decisions:
  - "read_questions returns DEFAULT_QUESTIONS only for an ABSENT row; an explicitly stored empty list is returned unchanged, so 'no questions' is expressible and distinct from a fresh install"
  - "The Draft answers route commits the stage's audit row BEFORE checking the result, mirroring the tailor generate route, so an attempted (tokens-spent) call is never lost to a refusal"
  - "The drafting guard is drafting_skip_reason() (switch first, then fact store) so a disabled switch refuses before any filesystem read or model call"
  - "An ad-hoc question appends by reading the existing rows, converting them back to ScreeningDraftInput and appending through replace_for_listing — no new repository surface is added"
  - "The per-answer delete is scoped by (listing_id, draft_id) in the repository, so a foreign/unknown id writes nothing and is a 404 data-error refusal"
  - "Answers render inside <p class=\"answer-text\"> so Jinja autoescape is the single choke point (T-07-05-01); the Copy answer handler reads textContent, never innerHTML"

patterns-established:
  - "A non-HTMX, confirm-guarded form is the destructive-affordance pattern (works with JS off); a neutral `button` (not accent) is the copy control"
  - "The package-page GET reads stored rows only and the explicit action is the only spend path — the page/action LLM split stays pinned by a zero-call test"

requirements-completed: [APPLY-01, UI-04]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "The screening question list persists as an apply_config singleton, editable from /settings, falling back to a code-level DEFAULT_QUESTIONS on an absent row and preserving an explicit empty list"
    requirement: APPLY-01
    verification:
      - kind: unit
        ref: "tests/db/test_apply_config_repo.py#test_an_absent_row_returns_the_default_seed"
        status: pass
      - kind: unit
        ref: "tests/db/test_apply_config_repo.py#test_an_empty_write_stores_an_explicit_empty_list"
        status: pass
      - kind: integration
        ref: "tests/api/test_settings_page.py#test_a_post_persists_the_screening_question_list"
        status: pass
    human_judgment: false
  - id: D2
    description: "The #apply-answers region renders each question with its stored answer or 'Not yet drafted.', the evidence chips and the .answer-warning line when unsupported; the empty copy renders with the add-question and Draft answers controls still present"
    requirement: APPLY-01
    verification:
      - kind: integration
        ref: "tests/api/test_apply_package.py#test_answers_region_renders_the_defaults_not_yet_drafted"
        status: pass
      - kind: integration
        ref: "tests/api/test_apply_package.py#test_answers_region_renders_the_empty_copy_when_no_questions"
        status: pass
      - kind: integration
        ref: "tests/api/test_apply_package.py#test_a_stored_answer_block_renders_with_evidence_and_the_copy_control"
        status: pass
      - kind: integration
        ref: "tests/api/test_apply_package.py#test_the_unsupported_warning_renders_inside_the_block"
        status: pass
    human_judgment: false
  - id: D3
    description: "The explicit Draft answers action makes exactly one guarded backend call and persists the grounded rows; a disabled switch refuses with the shared skip vocabulary before any call and writes nothing"
    requirement: APPLY-01
    verification:
      - kind: integration
        ref: "tests/api/test_apply_package.py#test_the_draft_action_makes_one_call_and_persists_rows"
        status: pass
      - kind: integration
        ref: "tests/api/test_apply_package.py#test_a_disabled_switch_refuses_before_any_call"
        status: pass
    human_judgment: false
  - id: D4
    description: "An ad-hoc question appends a row (answer NULL); the per-answer delete removes exactly the named row and a foreign draft_id writes nothing"
    requirement: APPLY-01
    verification:
      - kind: integration
        ref: "tests/api/test_apply_package.py#test_add_question_appends_an_ad_hoc_row"
        status: pass
      - kind: integration
        ref: "tests/api/test_apply_package.py#test_per_answer_delete_removes_only_the_named_row"
        status: pass
      - kind: integration
        ref: "tests/api/test_apply_package.py#test_per_answer_delete_refuses_a_foreign_draft_id"
        status: pass
    human_judgment: false
  - id: D5
    description: "The no-submit guarantee still holds: every new form posts to a local path, the outbound action stays a plain anchor, and the three new routes carry the identity seam"
    requirement: APPLY-01
    verification:
      - kind: integration
        ref: "tests/api/test_apply_package.py#test_no_submit_surface"
        status: pass
      - kind: integration
        ref: "tests/test_auth_seam.py#test_every_route_with_a_dependant_declares_current_user"
        status: pass
      - kind: integration
        ref: "tests/test_stylesheet_coverage.py#test_every_template_class_has_a_stylesheet_rule"
        status: pass
    human_judgment: false
  - id: D6
    description: "The region reads as a designed surface (copy affordance, warning emphasis, control placement) and the clipboard handler reproduces a long multi-paragraph answer untruncated"
    requirement: UI-04
    verification: []
    human_judgment: true
    rationale: "Whether the copy control and the warning read as designed rather than as chrome, and whether the clipboard handler reproduces a wrapped multi-paragraph answer, are browser-judgement calls no server-side assertion proves (the plan marks the long-text copy truth as a backstop)."

# Metrics
duration: ~25 min
completed: 2026-09-30
status: complete
---

# Phase 7 Plan 5: The drafted-answers surface Summary

**A user-editable screening-question list (`apply_config` singleton + a `/settings` editor), the `#apply-answers` region rendering stored answers with evidence chips and the per-answer honesty warning, one explicit guarded `Draft answers` call, and copy-to-clipboard consumption with no submit path anywhere.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-09-30T17:49Z (approximately)
- **Completed:** 2026-09-30T18:13Z
- **Tasks:** 2
- **Files modified:** 12 (3 created, 9 modified)

## Accomplishments
- The screening question list is a real, user-editable document: `apply_config_repo.read_questions`/`write_questions` over the `apply_config` singleton, with a code-level `DEFAULT_QUESTIONS` fallback for an ABSENT row and an explicit empty list preserved as its own "no questions" state. The `/settings` card is a plain full-page POST (zero model calls) that saves one question per line.
- The package page's `#apply-answers` region (`_screening_drafts.html`) renders the merged question set in saved order — each block the question text, the stored answer or `Not yet drafted.`, the evidence chips and, when the grounding check flagged it, the `.answer-warning` line INSIDE the block (D-125), with copy-to-clipboard consumption only (D-127).
- `POST /listings/{id}/apply/draft` makes exactly ONE guarded, audited call through `pipeline.draft`, persists the grounded verdicts via `screening_draft_repo.replace_for_listing`, and re-renders the region; a disabled switch refuses with the shared skip vocabulary before any filesystem read or call.
- `POST .../apply/question` appends an ad-hoc row (answer NULL) and `POST .../apply/draft/delete` removes exactly one row scoped by `(listing_id, draft_id)`; a foreign id is a 404 refusal that writes nothing. Opening the page makes zero LLM calls (D-122).
- The no-submit guarantee is preserved: every new form posts to a local path, the three new routes carry the identity seam, and the new `.answer-text`/`.answer-warning` tokens have stylesheet rules.

## Task Commits

Each task was committed atomically:

1. **Task 1: The screening question list and its Settings editor** - `713fcf8` (feat)
2. **Task 2: The #apply-answers region, the draft action, and copy-to-clipboard** - `b82a8e2` (feat)

**Plan metadata:** docs commit follows.

## Files Created/Modified
- `app/db/repositories/apply_config_repo.py` - `DEFAULT_QUESTIONS`, `read_questions`, `write_questions` over the `apply_config` singleton; never commits
- `app/api/settings.py` - `SCREENING_QUESTIONS_PATH` route, the `screening_questions` context key, `apply_config_repo` import
- `app/web/templates/html/settings.html` - the `Screening questions` card
- `app/api/apply.py` - `_answers_context`/`_answers_response`/`_answers_error`/`_answer_rows`, the GET context update, and the three POST routes
- `app/web/templates/html/_screening_drafts.html` - the `#apply-answers` region
- `app/web/templates/html/apply.html` - includes the region inside the ready state
- `app/web/templates/html/base.html` - the transport-failure handler now covers the `#apply-answers` swap root
- `static/vendor/app.css` - `.answer-text` (copies `.detail-rationale`) and `.answer-warning` (copies `.capability-warning`)
- `tests/db/test_apply_config_repo.py` - the store contract
- `tests/api/test_settings_page.py` - the card render + POST persistence
- `tests/api/test_apply_package.py` - the region, draft, add-question and delete lanes
- `tests/test_auth_seam.py` - the three new routes join `EXPECTED_SEAM_ROUTES`

## Decisions Made
- **Absent vs empty:** `read_questions` falls back to `DEFAULT_QUESTIONS` only when no `apply_config` row exists; an explicitly stored empty list is returned unchanged, so "no questions" is expressible and distinct from a fresh install.
- **The page/action LLM split:** the page GET reads stored rows only (zero calls, pinned by the existing zero-call test); the explicit `Draft answers` action is the only spend path.
- **Commit before refusal:** the draft route commits the stage's single audit row before checking the result (mirrors the tailor generate route), so an attempted, tokens-spent call is never lost to a refusal.
- **No new repository surface:** an ad-hoc question appends by reading the listing's rows, mapping them back to `ScreeningDraftInput` and appending through `replace_for_listing`; per-answer removal uses the existing scoped `delete_draft`.
- **Escaped text, copy-only:** answers render as `<p class="answer-text">` (never `|safe`, never an input value) so Jinja autoescape is the single choke point; the copy handler reads `textContent`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The transport-failure handler now covers the `#apply-answers` swap root**
- **Found during:** Task 2 (wiring the region's error state)
- **Issue:** The plan requires that a transport failure on the drafting action reuses `base.html`'s `The request did not reach the server` copy (also stated in 07-UI-SPEC). `base.html`'s `showTailoringTransportError` returned early for any target whose id was not `tailoring-review`, so the copy could never render into the new `#apply-answers` region.
- **Fix:** Generalised the handler (renamed `showRegionTransportError`) to cover both model-spending swap roots (`tailoring-review`, `apply-answers`); the copy string is unchanged. `base.html` was not in the plan's `files_modified`, so this is recorded as a deviation.
- **Files modified:** `app/web/templates/html/base.html`
- **Verification:** `tests/api/test_apply_package.py` and `tests/test_stylesheet_coverage.py` pass; no test asserts the old function name or the old guard.
- **Committed in:** `b82a8e2` (Task 2)

**2. [Rule 1 - Bug] Added the missing `Not yet drafted.` branch to the region template**
- **Found during:** Task 2 (first render)
- **Issue:** The first pass at `_screening_drafts.html` left the outer `{% if row.answer %}` unclosed (no `{% else %}`/`{% endif %}`), so Jinja raised `TemplateSyntaxError: Encountered unknown tag 'endfor'` and the ready page failed to render — and the documented `Not yet drafted.` empty-answer copy was absent.
- **Fix:** Added the `{% else %}<p>Not yet drafted.</p>{% endif %}` branch that closes `{% if row.answer %}`.
- **Files modified:** `app/web/templates/html/_screening_drafts.html`
- **Verification:** `tests/api/test_apply_package.py#test_answers_region_renders_the_defaults_not_yet_drafted` passes; the ready page renders.
- **Committed in:** `b82a8e2` (Task 2)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug).
**Impact on plan:** Both are required for the plan's own documented behaviour (the region's error state and its empty-answer state). No scope creep beyond `_screening_drafts.html` and the one-line handler generalisation in `base.html`.

## Issues Encountered
None beyond the two deviations. After the template fix the full suite was green on the first complete run (1639 passed).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- APPLY-01's package content is now complete: verified PDF, outbound link, drafted screening answers and the read-only gap checklist.
- The `#apply-answers` region reuses the existing HTMX swap-root / plain-form conventions, so Phase 8's polish and the v2 export (APPLY-07) can consume the stored `screening_drafts` rows directly.
- Migration head stays `0006`; no schema or dependency change. Opening the package still makes zero LLM calls.

## Self-Check: PASSED

- Created files exist on disk: `app/db/repositories/apply_config_repo.py`, `app/web/templates/html/_screening_drafts.html`, `tests/db/test_apply_config_repo.py`.
- Both task commits exist (`713fcf8`, `b82a8e2`); plan measured 2 commits from `9578520`.
- Plan lane: `pytest -q tests/db/test_apply_config_repo.py tests/api/test_settings_page.py tests/api/test_apply_package.py tests/test_auth_seam.py tests/test_stylesheet_coverage.py` — **47 passed**.
- Full suite: `pytest -q` — **1639 passed, 14 deselected, 2 xfailed**.
- `ruff check` on `apply_config_repo.py`, `app/api/apply.py`, `app/api/settings.py`, and both touched test files — clean.
- `.venv/bin/python -m compileall -q app` — clean.

---
*Phase: 07-assisted-apply-tracker*
*Completed: 2026-09-30*
