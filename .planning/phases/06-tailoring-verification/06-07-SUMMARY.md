---
phase: 06-tailoring-verification
plan: 07
subsystem: api
tags: [fastapi, tailoring, feature-flag, d-119, route-guard]

requires:
  - phase: 06-tailoring-verification
    plan: 01
    provides: the four tailoring routes, the generate-route off-switch guard, and the shared skip vocabulary
provides:
  - "the `settings.tailoring_enabled` guard in `compile_tailored_cv` (mirrors the generate route), placed before `load_facts`"
  - "the cross-surface disabled contract pinned in both directions: page, generate and compile all refuse with `tailoring_disabled`, and re-enabling restores the route"
  - "a recorded decision (comment) that `GET .../cv/pdf` stays ungated because it serves an already-verified artifact"
affects: [07-apply-and-track]

actuals:
  tokens: 1759
  tasks: 2
  # 2 task commits + this plan's metadata commit.
  commits: 2
  plan_head_before: b780d07d8fc969b98e0943256247c948bf40de48

tech-stack:
  added: []
  patterns:
    - "a new-work route honours the operator off switch before any filesystem read, reusing the shared skip vocabulary rather than a route-local literal"
    - "the switch reads the live Settings value (never cached at import), so it is a refusal, not a latching trip"

key-files:
  created: []
  modified:
    - app/api/tailoring.py
    - tests/api/test_tailoring_review.py

key-decisions:
  - "The compile guard is byte-for-byte the generate guard and sits after the listing-exists check and before the patch parse, so an unknown listing still returns its honest 404 while a known listing with the switch off returns 409 tailoring_disabled before load_facts"
  - "GET .../cv/pdf is deliberately NOT gated: it serves an already-verified stored artifact, and gating it would strand a verified download when the operator pauses tailoring; recorded as a comment so the asymmetry is not 'fixed' later"
  - "The refusal is built from the shared vocabulary (`TAILOR_SKIP_DISABLED` / `TAILOR_SKIP_LABELS` in app/pipeline/tailor.py) via the existing escaping `_error_fragment`, so no request text selects or reaches the refusal"
  - "The guard reads the live `Settings` value, pinned by re-enabling the switch mid-test and compiling the same round-tripped fields to exactly one ok row — no import-time caching, no one-way trip"

patterns-established:
  - "An operator off switch is enforced on every surface that starts new work, from one vocabulary; surfaces that serve existing verified output are explicitly exempt with a written reason"

requirements-completed: [TAIL-01]

coverage:
  - id: D1
    description: "POST /listings/{id}/cv/compile refuses with 409 data-error=tailoring_disabled before load_facts when the switch is off, writing zero artifact rows, zero files and making zero engine calls"
    requirement: TAIL-01
    verification:
      - kind: integration
        ref: "tests/api/test_tailoring_review.py::test_the_compile_route_refuses_when_tailoring_is_disabled"
        status: pass
      - kind: unit
        ref: "tests/api/test_tailoring_review.py::test_an_intact_guard_compiles_and_writes_exactly_one_row"
        status: pass
    human_judgment: false
  - id: D2
    description: "The disabled contract holds on every new-work surface: the page shows the disabled skip label with no generate control and no download link; generate and compile both refuse; zero backend calls and zero rows"
    requirement: TAIL-01
    verification:
      - kind: integration
        ref: "tests/api/test_tailoring_review.py::test_the_disabled_switch_is_honoured_across_the_tailoring_surfaces"
        status: pass
      - kind: integration
        ref: "tests/api/test_tailoring_generate.py::test_generate_returns_the_review_fragment_and_writes_nothing"
        status: pass
    human_judgment: false
  - id: D3
    description: "The off switch is live in both directions: the same round-tripped fields compile to exactly one ok row once the live setting is restored"
    requirement: TAIL-01
    verification:
      - kind: integration
        ref: "tests/api/test_tailoring_review.py::test_the_disabled_switch_is_not_a_one_way_trip"
        status: pass
    human_judgment: false

duration: 11
completed: 2026-09-24
status: complete
---

# Phase 06 Plan 07: WR-01 Summary

**The compile route now honours `tailoring_enabled`: a round-tripped patch POSTed straight at `/cv/compile` can no longer render, compile or persist while the operator has tailoring off — and the switch stays live in both directions**

## Performance

- **Duration:** 11 min
- **Started:** 2026-09-24T22:57:00Z
- **Completed:** 2026-09-24T23:08:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `compile_tailored_cv` gained the missing `settings.tailoring_enabled` guard, placed immediately after the listing-exists check and before the `patch_json` parse — so the refusal precedes `load_facts`, the render, the engine call and the insert. It is byte-for-byte the generate route's guard, so the two cannot drift.
- The off switch now costs zero `cv_artifacts` rows, zero files under `Settings.artifacts_dir`, zero engine calls and zero backend calls on every new-work surface (page, generate, compile), all refusing with the same `tailoring_disabled` vocabulary defined once in `app/pipeline/tailor.py`.
- The switch is proven live in both directions: with the setting restored to `True`, the same round-tripped fields compile to exactly one `ok` row — the guard reads the live `Settings` value, not an import-time literal.
- `GET /listings/{id}/cv/pdf` is deliberately left ungated (it serves an already-verified artifact); a docstring comment records the decision so a later reader does not "fix" the asymmetry.

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end — the compile route refuses when tailoring is disabled** - `79d9aff` (fix)
2. **Task 2: The disabled-surface parity contract, in both directions** - `b426a67` (test)

**Plan metadata:** (this SUMMARY commit)

## Files Created/Modified

- `app/api/tailoring.py` - the `settings.tailoring_enabled` guard in `compile_tailored_cv`, an updated `compile_tailored_cv` docstring naming the D-119 contract, and a comment on `tailored_cv_pdf` recording why that route is not gated
- `tests/api/test_tailoring_review.py` - `test_the_compile_route_refuses_when_tailoring_is_disabled`, `test_the_disabled_switch_is_honoured_across_the_tailoring_surfaces`, `test_the_disabled_switch_is_not_a_one_way_trip`

## Decisions Made

- **Guard placement mirrors the generate route exactly** — after the listing-exists check (unknown listing ⇒ honest 404; known listing + switch off ⇒ 409 `tailoring_disabled`), before the client patch is even parsed. This satisfies "before any filesystem read" and keeps the two routes from drifting.
- **The PDF route stays ungated by design** — the switch gates new work; a verified artifact must remain downloadable. The verifier reports the download half of TAIL-05 SATISFIED and the probe explicitly forbids gating an existing verified download.
- **The refusal uses the shared vocabulary and the escaping `_error_fragment`** — no request-supplied text selects the reason or reaches the fragment.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The full hermetic lane passes (1231 passed, 14 deselected, 2 xfailed — up 3 from the pre-plan 1228, matching the three new tests). `.venv/bin/python -m compileall -q app` is clean and `ruff check` passes on both modified files. The targeted lanes (`tests/api/test_tailoring_review.py tests/api/test_tailoring_generate.py tests/test_config.py tests/test_auth_seam.py` → 53 passed; `tests/pipeline/test_tailor_stage.py` → 9 passed) are green.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- WR-01 is closed; TAIL-01's remaining FLAGGED edge (end-to-end generate on a supplied real fact store) is unchanged and out of this plan's scope.
- Alembic head unchanged at `0004`; no migration, setting or dependency added.
- Phase 7's attach path continues to consume the ok-only selection; the off switch does not gate an already-verified download.

---

*Phase: 06-tailoring-verification*
*Completed: 2026-09-24*

## Self-Check: PASSED

- FOUND: `79d9aff` (Task 1 commit)
- FOUND: `b426a67` (Task 2 commit)
- Confirmed: `grep -c "tailoring_enabled" app/api/tailoring.py` → 4 (generate + compile guards and docstrings); `grep -c "TAILOR_SKIP_DISABLED" app/api/tailoring.py` → 3
- Confirmed: 3 new tests exist in `tests/api/test_tailoring_review.py`
