---
phase: 03-llm-port-structured-output
plan: 07
subsystem: pipeline
tags: [prompt-injection, finding, queue, d-49, telemetry, tdd, phase-final]

# Dependency graph
requires:
  - phase: 03-llm-port-structured-output
    provides: "plans 03-01/03-04's llm_call_repo.llm_totals_for_run (the read the seam will be fed by) and the quality_signals_json column already in listing_repo"
provides:
  - "NormalisedListing.quality_signals / .quality_signals_json — a counts-only finding that cannot carry prose"
  - "normalise_listing(raw, *, quality_signals=…), still pure"
  - "The pipeline persists the sanitize report's instruction_like / patterns_matched onto listings.quality_signals_json; a clean listing stays NULL"
  - "QueueRow.instruction_like + the conditional 'flagged' badge on the queue row"
  - "The _finish(llm_calls=…, llm_tokens=…) writer seam, proven with no caller (D-49 intact)"
affects: [05-ranking, 06-tailoring, 07-...]

# Actuals (#2632) — same estimateTokens scale (chars/4) as the plan's estimate.
actuals:
  tokens: 20743
  tasks: 3
  commits: 5

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A finding is counts-only BY TYPE: the payload has no field that could carry prose"
    - "Absent signal is None, never {} — the nullable guard is what prevents clobbering"
    - "Ship the writer seam, not a caller: D-49 keeps the pipeline LLM-free and the seam is proven directly"
    - "A new badge class ships with its CSS rule, because the stylesheet-coverage guard is the UI's contract"

key-files:
  created:
    - tests/pipeline/test_injection_finding.py
    - tests/pipeline/test_finish_llm_counters.py
  modified:
    - app/domain/models.py
    - app/pipeline/stages.py
    - app/pipeline/run.py
    - app/db/repositories/queue_repo.py
    - app/web/templates/html/_listing_row.html
    - static/vendor/app.css

key-decisions:
  - "The finding is a bool plus an int, normalised to None when there is nothing to record, so `listing_repo`'s `if value is not None` guard never lets a clean listing clobber a recorded signal."
  - "The badge SHIPS. The plan made it conditional on not breaking the pinned queue markup; the three queue tests assert badge substrings additively, so an extra badge is safe — but the stylesheet-coverage guard requires a rule for every literal class, so `.badge-flagged` was added to the hand-maintained app.css rather than dropping the UI half of §6.3 or weakening the guard."
  - "`_finish` assigns the LLM counters only when supplied, and `ranked_count` is untouched: an omitted counter preserves the recorded value, and Phase 5 owns the ranking count."
  - "No caller is wired for the counters. A Phase-3 caller would violate D-49 and break `tests/pipeline/test_filter_stage.py:197`'s `LlmCall == 0` guard."

patterns-established:
  - "A UI badge is added with its stylesheet rule in the same change, so the class-coverage guard stays meaningful"
  - "A pipeline seam is proven by a direct unit test when the real caller belongs to a later phase"

requirements-completed: [PLAT-02]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "The normalised listing carries a counts-only quality signal; an absent or empty signal is None (never {}), and normalise_listing stays pure and non-mutating."
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "tests/pipeline/test_injection_finding.py#test_a_counts_only_finding_round_trips"
        status: pass
      - kind: unit
        ref: "tests/pipeline/test_injection_finding.py#test_an_empty_signal_is_none_never_an_empty_dict"
        status: pass
      - kind: unit
        ref: "tests/pipeline/test_injection_finding.py#test_normalise_listing_is_pure_and_does_not_mutate_the_caller"
        status: pass
    human_judgment: false
  - id: D2
    description: "A run persists the instruction-like finding on listings.quality_signals_json as counts only, and a clean listing leaves the column NULL."
    requirement: PLAT-02
    verification:
      - kind: integration
        ref: "tests/pipeline/test_injection_finding.py#test_an_instruction_like_listing_stores_a_counts_only_finding"
        status: pass
      - kind: integration
        ref: "tests/pipeline/test_injection_finding.py#test_a_clean_listing_leaves_the_column_null"
        status: pass
      - kind: guard
        ref: "tests/db/test_no_pii_columns.py (no edit)"
        status: pass
    human_judgment: false
  - id: D3
    description: "The queue row shows a 'flagged' badge exactly when the finding is recorded, and no badge otherwise."
    requirement: PLAT-02
    verification:
      - kind: integration
        ref: "tests/pipeline/test_injection_finding.py#test_the_queue_row_shows_the_flagged_badge"
        status: pass
      - kind: integration
        ref: "tests/pipeline/test_injection_finding.py#test_a_clean_queue_row_shows_no_flagged_badge"
        status: pass
      - kind: guard
        ref: "tests/test_stylesheet_coverage.py (green with the new .badge-flagged rule)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The _finish LLM-counter seam persists supplied values and preserves omitted ones; ranked_count is never written."
    requirement: PLAT-02
    verification:
      - kind: integration
        ref: "tests/pipeline/test_finish_llm_counters.py#test_finish_persists_the_llm_counters_when_supplied"
        status: pass
      - kind: integration
        ref: "tests/pipeline/test_finish_llm_counters.py#test_an_omitted_counter_preserves_the_recorded_value"
        status: pass
      - kind: integration
        ref: "tests/pipeline/test_finish_llm_counters.py#test_finish_never_writes_ranked_count"
        status: pass
    human_judgment: false
  - id: D5
    description: "D-49 still holds: a pipeline run writes zero llm_calls rows, through both this harness and the existing filter-stage guard."
    requirement: PLAT-02
    verification:
      - kind: guard
        ref: "tests/pipeline/test_finish_llm_counters.py#test_a_pipeline_run_writes_zero_llm_calls"
        status: pass
      - kind: guard
        ref: "tests/pipeline/test_filter_stage.py (unchanged, green)"
        status: pass
    human_judgment: false

# Metrics
duration: 10 min
completed: 2026-09-17
status: complete
---

# Phase 3 Plan 07: LLM Port + Structured Output Summary

**An instruction-like listing is now recorded as counts-only evidence on the listing and flagged in the queue, a clean listing stays NULL, and `_finish` can record the LLM counters Phase 5 will supply — while the pipeline remains completely LLM-free (D-49).**

## Performance

- **Duration:** 10 min
- **Tasks:** 3 (Tasks 1 and 3 TDD; Task 2 auto)
- **Files created/modified:** 8 (2 created, 6 modified)
- **Full suite:** 826 passed, 3 deselected (~101 s; plan 03-06 baseline was 811 passed, 3 deselected)

## Accomplishments

- **The discarded report is now a recorded finding.** `_persist_result` captures the `SanitizeReport` and writes `{"instruction_like": bool, "patterns_matched": int}` to `listings.quality_signals_json` — the column was already in `_LISTING_FIELDS` and the PII allow-list, so no schema change and no guard edit.
- **The finding cannot carry prose, by type.** `NormalisedListing.quality_signals` is a tiny mapping and `normalise_listing` takes it as a pure argument; a sentinel phrase from the description is asserted absent from the stored JSON.
- **A clean listing stays clean.** The payload is `None` (never `{}`) when there is nothing to record, so `listing_repo`'s `if value is not None` guard never clobbers a signal recorded earlier (T-3-21).
- **The operator can see it.** `QueueRow.instruction_like` reads the JSON column through a tolerant accessor and the row renders a `flagged` badge with a unique id — shipped properly, with its `.badge-flagged` CSS rule, because the plan's condition (do not break the pinned queue markup) held.
- **The Phase-5 seam exists and is proven.** `_finish(llm_calls=…, llm_tokens=…)` assigns only when supplied and never touches `ranked_count`; `run_pipeline()` still writes zero `llm_calls` rows.
- **No redaction was added.** The sanitizer flags and counts; the sanitised text and `content_hash` are byte-identical, and `tests/pipeline/test_filter_stage.py` stays green.

## Task Commits

1. **Task 1: The pure half** — `e791b43` (test, RED) → `c49f7e7` (feat, GREEN)
2. **Task 2: Persist the finding and flag the row** — `6e867f8` (feat)
3. **Task 3: The `_finish` counter seam** — `d81566f` (test, RED) → `f61f8cb` (feat, GREEN)

**Plan metadata:** the `docs(03-07)` commit immediately following this file (SUMMARY + STATE + ROADMAP + REQUIREMENTS).

## Files Created/Modified

- `tests/pipeline/test_injection_finding.py` — **created**; the pure half plus the persistence/render half (10 tests)
- `tests/pipeline/test_finish_llm_counters.py` — **created**; the counter seam and the D-49 guard (5 tests)
- `app/domain/models.py` — `quality_signals` field + `quality_signals_json` property
- `app/pipeline/stages.py` — the keyword-only `quality_signals` parameter, still pure
- `app/pipeline/run.py` — `_persist_result` records the finding; `_finish` gains `llm_calls`/`llm_tokens`
- `app/db/repositories/queue_repo.py` — `QueueRow.instruction_like` + the tolerant `_instruction_like` accessor
- `app/web/templates/html/_listing_row.html` — the conditional `flagged` badge
- `static/vendor/app.css` — the `.badge-flagged` rule (deviation; see below)

## Decisions Made

- **Badge shipped.** The plan made it conditional on the pinned queue markup. The three queue tests assert badge presence/absence by substring, so an additive badge is safe; the only real obstacle was the stylesheet-coverage guard, resolved by adding the one CSS rule the repo's own conventions expect.
- **Counts only, by construction.** There is no field on `SanitizeReport` or on the stored payload that can carry matched text, an excerpt or a position — the invariant is structural, not a promise.
- **Seam, not caller.** D-49 is explicit; the seam is proven by a direct unit test so Phase 5 can wire `llm_totals_for_run` without touching this phase's behaviour.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `static/vendor/app.css` gained the `.badge-flagged` rule**
- **Found during:** Task 2, when deciding whether the badge could ship
- **Issue:** `tests/test_stylesheet_coverage.py` requires every literal `class="…"` token in a template to have a rule in the committed stylesheet. A new `badge-flagged` class therefore could not ship without CSS, and the plan's `files_modified` did not list `app.css`.
- **Fix:** added one component rule (`.badge-flagged`) to the hand-maintained `app.css` — the same pattern prior commits used (e.g. the settings plan added its card rules directly), because the repo has no Tailwind build source. Dropping the badge was the alternative the plan authorised, but the badge is §6.3's UI half and the guard was satisfiable without weakening anything.
- **Files modified:** `static/vendor/app.css`, `app/web/templates/html/_listing_row.html`
- **Verification:** `tests/test_stylesheet_coverage.py` 5 passed; the three queue tests (30 passed with the PII guard) unchanged.
- **Committed in:** `6e867f8` (Task 2)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The finding is now both persisted and visible, which is §6.3's full requirement. No guard was weakened and no queue assertion was touched.

## TDD Gate Compliance

| Task | RED | GREEN | REFACTOR | Notes |
|------|-----|-------|----------|-------|
| 1 | `e791b43` (test) | `c49f7e7` (feat) | — | RED was 6 failures: the field, the property and the builder parameter did not exist (AttributeError/TypeError rather than assertion failures — the new API is what is under test). |
| 2 | n/a (not TDD) | `6e867f8` (feat) | — | Pipeline + repository + template; its proof is the persistence and render tests plus the untouched guards. |
| 3 | `d81566f` (test) | `f61f8cb` (feat) | — | RED was 3 `TypeError`s for the absent keyword seam; the 2 already-true behaviours (preservation companion, D-49 guard) passed. |

## Issues Encountered

- **Task 1's RED is necessarily attribute-level.** A brand-new field and parameter cannot fail on an assertion before they exist; the tests are otherwise natural and all six pass unchanged after GREEN. Recorded rather than papered over.
- **The badge decision needed the full guard picture.** The plan warned about three queue tests; the actual constraint turned out to be the stylesheet-coverage guard plus the absence of a CSS build step. Resolved by adding the rule, not by dropping the feature.
- **No live LLM call.** The finding is produced by the sanitizer at ingest; nothing in this plan touches the opencode server.

## Known Stubs

None. Every deliverable is implemented and asserted in the default lane. The `_finish` counters have no caller by design (D-49), and that is a documented Phase-5 integration point rather than a stub: the seam is complete and tested.

## Threat Flags

None — no new surface. This plan mitigates T-3-01 (the flag is recorded, never obeyed or stripped; counts only), T-3-05 (the JSON allow-list is unchanged and the payload is counts-only, asserted with a sentinel), T-3-21 (a clean listing passes `None` and never clobbers), T-3-22 (the seam ships without a caller) and T-3-23 (the badge shipped additively; `run_repo`/`runs.html` untouched), all already in the plan's threat register.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- **Phase 3 is complete.** All seven plans have shipped: the LLM port and structured-output contract, the `/doc` contract test, the failure taxonomy and salvage, migration 0003 with the `llm_calls` writer and reads, the Settings ceilings and compose passthrough, the trust boundary, and now the finding + counter seam.
- **Phase 5 has everything it needs:** `complete_structured` with a classified outcome, `llm_totals_for_run` for the totals, the `_finish(llm_calls=…, llm_tokens=…)` seam to write them, and a default-deny tool posture that travels with any ranking call.
- **The instruction-like finding is visible to the operator** on the queue row, so a listing that tried to instruct the model is distinguishable from one that did not.
- **Operator-run checks remain** (recorded in `.planning/WINDOWS.md` and `03-VALIDATION.md`): the live `/doc` diff, the live selftest real call, and the live trust-boundary observation.
- **`PLAT-02` should now be eligible** for the shared-ID gate: all six declaring siblings have SUMMARYs.

---
*Phase: 03-llm-port-structured-output*
*Completed: 2026-09-17*

## Self-Check: PASSED

- All eight plan files exist on disk (`tests/pipeline/test_injection_finding.py`, `tests/pipeline/test_finish_llm_counters.py`, `app/domain/models.py`, `app/pipeline/stages.py`, `app/pipeline/run.py`, `app/db/repositories/queue_repo.py`, `app/web/templates/html/_listing_row.html`, `static/vendor/app.css`).
- All five plan commits are present (`e791b43`, `c49f7e7`, `6e867f8`, `d81566f`, `f61f8cb`).
- Measured commit count from the plan ledger: 5 (`git rev-list --count 2011d6d..HEAD`).
