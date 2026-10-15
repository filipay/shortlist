---
phase: 05-ranking-core-value
plan: 09
subsystem: ui
tags: [ranking, observability, detail-page, jinja2, cv-path, gap-closure]

# Dependency graph
requires:
  - phase: 05-ranking-core-value
    provides: "05-08's persisted reason_counts_json['ranking'], RunSummary.ranking_state/ranking_reason, ranking_in_progress() and RANK_SKIP_LABELS/RANK_SKIP_FACT_STORE"
  - phase: 05-ranking-core-value
    provides: "05-03's detail-page layout, fit-score region and requirement list (unchanged here)"
provides:
  - "The detail page's unscored block names the last run's real ranking state (running / skipped+reason / nothing-to-rank / not-this-listing / not-completed)"
  - "The fact-store skip discloses the exact loader path (Settings.cv_dir + CV_FILENAME) and points at /settings"
  - "tests/api/test_listing_detail.py::_seed_run_with_ranking and three state-branch tests"
affects: [05-10, gsd-verify-work]

# Actuals (#2632) — pairs with the plan's estimate (20000 tokens / 2 tasks, confidence low).
# Same estimateTokens scale (chars/4 over the realized diff), never a harness token count.
actuals:
  tokens: 1781
  tasks: 2
  commits: 2
  plan_head_before: 98bca7971b3dec63e25159055c524340115e1f46

tech-stack:
  added: []
  patterns:
    - "Route-computed disclosure: the skip vocabulary and the CV path are resolved in Python (booleans/labels/paths) and the template branches only on those, so no reason string ever appears in markup"
    - "Reuse of 05-08's read model verbatim — the detail page calls RunSummary.ranking_state(in_progress=ranking_in_progress()) rather than re-deriving the five states"

key-files:
  created: []
  modified:
    - app/api/listings.py
    - app/web/templates/html/listing_detail.html
    - tests/api/test_listing_detail.py

key-decisions:
  - "The detail route reads the latest run with run_repo.list_runs(session, limit=1) — one bounded read, no new query, no model call, route stays read-only"
  - "cv_fact_store_skipped is computed in Python (reason == RANK_SKIP_FACT_STORE) so the template never contains a reason string, per the plan's vocabulary prohibition"
  - "The named path is str(Path(settings.cv_dir) / CV_FILENAME) — the exact path app.cv.factstore reads; the test derives the same value from settings so it does not pin the container default"
  - "The fact-store copy says NOT READABLE, never 'missing file', because one reason covers absent, unreadable and non-decodable (05-06)"

patterns-established:
  - "Cause-specific disclosure under a stable heading: one heading, one sentence chosen from precomputed state — the same shape 05-08 used for the queue strip"

requirements-completed: [UI-02, RANK-08]

coverage:
  - id: D1
    description: "The unscored detail page names the last run's actual ranking state — running / skipped + reason / nothing-to-rank / not-this-listing / not-completed — under the retained 'Not yet ranked' heading, instead of the old two-way hedge"
    requirement: UI-02
    verification:
      - kind: unit
        ref: "tests/api/test_listing_detail.py#test_unscored_detail_shows_a_running_pass"
        status: pass
      - kind: unit
        ref: "tests/api/test_listing_detail.py#test_unscored_detail_is_honest_when_no_pass_has_completed"
        status: pass
      - kind: unit
        ref: "tests/api/test_listing_detail.py#test_unscored_listing_renders_not_yet_ranked"
        status: pass
    human_judgment: false
  - id: D2
    description: "When the skip reason is the fact-store one, the page names the missing CV fact store, the exact path the loader reads, and points at /settings — the G-05-2 detail-copy item"
    requirement: UI-02
    verification:
      - kind: unit
        ref: "tests/api/test_listing_detail.py#test_unscored_detail_names_the_skipped_reason_and_the_cv_path"
        status: pass
    human_judgment: false
  - id: D3
    description: "running and never-completed render different sentences, so an interrupted pass cannot read as in progress (staleness rule)"
    requirement: RANK-08
    verification:
      - kind: unit
        ref: "tests/api/test_listing_detail.py#test_unscored_detail_shows_a_running_pass"
        status: pass
      - kind: unit
        ref: "tests/api/test_listing_detail.py#test_unscored_detail_is_honest_when_no_pass_has_completed"
        status: pass
    human_judgment: false

duration: 7min
completed: 2026-09-23
status: complete
---

# Phase 05 Plan 09: The job detail page names the last run's ranking state Summary

**The unscored job detail page now answers "why is this not scored?" with the last run's real persisted ranking state — and when the CV fact store is the cause it names the exact path the loader reads (`/cv/cv.yaml`) and points at Settings — replacing the old "may still be running, or the pass was skipped" dead end.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-09-23T10:27:44Z
- **Completed:** 2026-09-23T10:34:33Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- **Detail-page half of G-05-1 closed.** The route reads the latest run (`run_repo.list_runs(session, limit=1)`) and passes `ranking_state` (via 05-08's pure `RunSummary.ranking_state(in_progress=ranking_in_progress())`), `ranking_reason`, `ranking_reason_label`, `cv_fact_store_skipped` and `cv_path`. The template's not-yet-ranked block renders one cause-specific sentence per state, so `running` and `skipped` are finally distinguishable on this surface too.
- **G-05-2's detail-copy item closed.** A fact-store skip renders "Ranking was skipped because there is no readable CV fact store. The app reads `<code>{cv_path}</code>` — see Settings for how to supply one." The path is computed from `settings.cv_dir` + `rank.CV_FILENAME`, i.e. exactly what `app.cv.factstore` reads.
- **The staleness hazard is preserved on this surface.** `running` is the render-time probe only; with no live task the honest "The ranking pass has not completed — refresh once it finishes." renders instead, and the two are pinned as different sentences.
- **UI-02's prohibition held.** The retained "Not yet ranked." heading appears exactly once; an unscored listing still renders no fit-score region, no factor breakdown and no `0.0`.
- **Read-only and total.** One bounded `limit=1` read and pure derivations; a corrupted marker degrades to the generic not-completed sentence via 05-08's total parser. No new route, no model call, no write, no dependency.

## Task Commits

Each task was committed atomically:

1. **Task 1: The detail route reads the last run's ranking state and the page names a cause** - `8c834ed` (feat)
2. **Task 2: Pin the skipped, running and never-completed detail branches** - `0cf46b9` (test)

**Plan metadata:** committed separately after this SUMMARY (docs).

## Files Created/Modified

- `app/api/listings.py` — imports `run_repo` and `CV_FILENAME` / `RANK_SKIP_FACT_STORE` / `RANK_SKIP_LABELS` / `ranking_in_progress`; reads the latest run and computes the five context keys; docstring records the new disclosure role and that the total is still never recomputed (D-100).
- `app/web/templates/html/listing_detail.html` — the state-driven not-yet-ranked paragraph (heading once + one sentence per state); header comment updated. No `|safe`, no JS, no form, no file input.
- `tests/api/test_listing_detail.py` — `_seed_run_with_ranking` helper and three tests: `test_unscored_detail_names_the_skipped_reason_and_the_cv_path`, `test_unscored_detail_shows_a_running_pass`, `test_unscored_detail_is_honest_when_no_pass_has_completed`.

## Decisions Made

- **Reuse 05-08's read model, do not re-derive.** The route calls `RunSummary.ranking_state(...)` and `ranking_in_progress()` directly; the five states have one definition.
- **Keep the skip vocabulary out of markup.** `cv_fact_store_skipped` is a Python-computed boolean; the template branches on it and on precomputed labels, never on a literal reason string.
- **Name the loader's real path, computed, not hardcoded.** `str(Path(settings.cv_dir) / CV_FILENAME)`; the test derives the same expression so it adapts to any configured `cv_dir` rather than pinning `/cv`.
- **Say "not readable", never "missing file".** One reason covers absent, unreadable and non-decodable (05-06); "missing file" would be a lie for two of the three cases.
- **Scope held to the detail page.** G-05-2's queue-row badge and empty-state surfaces are plan 05-10's; nothing row-scoped or empty-state-scoped was added.

## Deviations from Plan

None - plan executed exactly as written. No Rule 1/2/3 auto-fix was needed; no package install, no migration (head stays `0004`), no schema change.

## Issues Encountered

- The Task 1 acceptance grep `grep -c "Not yet ranked." app/web/templates/html/listing_detail.html == 1` initially read 2: the `.` is a regex wildcard, so the header comment's reference to the heading also matched. The comment was reworded to "not-yet-ranked" (hyphenated), which is also more accurate; the markup heading still appears exactly once. Resolved within Task 1 before commit.

## User Setup Required

None - no external service configuration required. The CV fact store remains a host file by design (D-58); this plan only discloses where the loader reads it.

## Next Phase Readiness

- The detail page and the queue strip (05-08) now render the same five states from one read model, so the two surfaces cannot drift.
- Plan 05-10 owns G-05-2's remaining disclosure surfaces (the queue row badge and the queue empty state), with its scope rationale declared in that plan.
- Plan 05-10's own write-up plus `/gsd-verify-work`'s round-2 UAT re-run are the remaining Phase-05 gap-closure steps.
- Full suite green: `1056 passed, 14 deselected, 2 xfailed`; build (`compileall -q app`) clean.

---
*Phase: 05-ranking-core-value*
*Completed: 2026-09-23*

## Self-Check: PASSED

- FOUND: `.planning/phases/05-ranking-core-value/05-09-SUMMARY.md`
- FOUND commit: `8c834ed` (Task 1)
- FOUND commit: `0cf46b9` (Task 2)
- Full suite: `1056 passed, 14 deselected, 2 xfailed`; build `compileall -q app` clean.
