---
phase: 05-ranking-core-value
plan: 06
subsystem: pipeline
tags: [fact-store, cv, ranking, d-94, rank-08, yaml, unicode, structlog]

# Dependency graph
requires:
  - phase: 05-ranking-core-value
    provides: "plan 05-01's rank stage and its (CvFactStoreError, OSError) skip guard; D-94's absent/unreadable fact-store posture"
  - phase: 04-cv-data-model
    provides: "load_facts and its loud, path-qualified CvFactStoreError contract (D-66)"
provides:
  - "load_facts re-raises a non-decodable or otherwise unreadable cv.yaml as one path-qualified CvFactStoreError (UnicodeError/OSError caught at the boundary)"
  - "a pinning unit test for the boundary contract and an end-to-end test for the detached ranking task's clean skip with the documented fact_store_absent log"
  - "retirement of the obsolete gap-2 strict-xfail sentinel (coverage re-homed as a first-class test)"
affects: [tailoring, ranking, cv-import, verify-work]

actuals:
  tokens: 2196
  tasks: 2
  commits: 2
plan_head_before: 889413fe3e7e57cb62869f0af7c21c2ae31ff415

tech-stack:
  added: []
  patterns:
    - "One typed failure at the shared reader: every load_facts failure mode is a path-qualified CvFactStoreError, so each caller (ranking now, tailoring later) catches one class"
    - "Skip-path observability is pinned by an event assertion, not inferred from absence of rows"

key-files:
  created: []
  modified:
    - app/cv/factstore.py
    - tests/cv/test_factstore.py
    - tests/pipeline/test_rank_adversarial.py
    - tests/pipeline/test_rank_optional.py

key-decisions:
  - "The root-cause fix belongs at the fact-store boundary, not in rank.py's guard: loading the file is the shared function every caller routes through, so a second caller (Phase 6 tailoring) inherits the contract for free and rank.py's (CvFactStoreError, OSError) guard is left unchanged"
  - "A non-decodable file is the same operator-visible situation as a missing or invalid one, so it maps to the same CvFactStoreError with the same fact_store_absent skip reason rather than a new reason"
  - "The non-UTF-8 end-to-end test wraps BOTH the run and the drain in capture_logs because run_pipeline starts the detached ranking task before _finish and keeps awaiting; capturing only the drain would be racy"

patterns-established:
  - "Boundary failure typing: catch the transport/library error classes (UnicodeError, OSError) where the I/O happens and re-raise the module's one error type"
  - "Fire-and-forget task observability: assert on a captured log event with its reason field, not merely on the absence of side-effect rows"

requirements-completed: [RANK-08]

coverage:
  - id: D1
    description: "A cv.yaml that exists but is not valid UTF-8 is a path-qualified CvFactStoreError at the fact-store boundary, with the decode failure preserved as its cause — no raw UnicodeDecodeError escapes load_facts"
    requirement: "RANK-08"
    verification:
      - kind: unit
        ref: "tests/cv/test_factstore.py#test_non_utf8_bytes_raise_the_path_qualified_fact_store_error"
        status: pass
      - kind: integration
        ref: "tests/pipeline/test_rank_optional.py#test_non_utf8_fact_store_writes_nothing_and_the_run_is_done"
        status: pass
    human_judgment: false
  - id: D2
    description: "The detached ranking task returns cleanly on an unreadable fact store: zero llm_calls rows, zero scores rows, run status done, and an emitted pipeline.rank_skipped event carrying reason=fact_store_absent"
    requirement: "RANK-08"
    verification:
      - kind: integration
        ref: "tests/pipeline/test_rank_optional.py#test_non_utf8_fact_store_writes_nothing_and_the_run_is_done"
        status: pass
    human_judgment: false
  - id: D3
    description: "The obsolete gap-2 strict-xfail sentinel is retired and the WR-05 sentinel is untouched; every existing loud-failure case still passes"
    verification:
      - kind: other
        ref: "grep -c '@pytest.mark.xfail' tests/pipeline/test_rank_adversarial.py => 1; .venv/bin/python -m pytest -q tests/cv/test_factstore.py tests/pipeline/test_rank_adversarial.py -x => 10 passed, 1 xfailed"
        status: pass
    human_judgment: false

duration: 6 min
completed: 2026-09-22
status: complete
---

# Phase 05 Plan 06: Unreadable CV fact store — one failure type and the documented D-94 skip

**A non-UTF-8 `cv.yaml` now raises one path-qualified `CvFactStoreError` at the fact-store boundary, so the detached ranking task takes D-94's documented skip path — zero rows, run `done`, and a `pipeline.rank_skipped` event with `reason="fact_store_absent"` — instead of dying with an unretrieved `UnicodeDecodeError`.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-09-22T15:42:11Z
- **Completed:** 2026-09-22T15:48:42Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `load_facts` now catches `(OSError, UnicodeError)` around `path.read_text` and re-raises `CvFactStoreError(f"{resolved}: unreadable: {exc}") from exc`, so the non-decodable case is the same typed, path-qualified failure as a missing file or invalid YAML — the decode error is preserved as `__cause__`.
- `app/pipeline/rank.py` was deliberately left untouched: its existing `except (CvFactStoreError, OSError)` guard already catches the new error, and the fix lives in the shared reader every caller routes through.
- A unit test pins the boundary contract and an end-to-end test proves the detached task returns cleanly on the unreadable fact store — zero `llm_calls`, zero `scores`, run `done`, and the documented `fact_store_absent` skip event.
- The obsolete gap-2 strict-xfail sentinel in `tests/pipeline/test_rank_adversarial.py` was retired (with its orphaned imports) and its coverage re-homed as a first-class test; the out-of-scope WR-05 sentinel is untouched.

## Task Commits

Each task was committed atomically:

1. **Task 1: One failure type at the fact-store boundary, and the obsolete sentinel retired** — `8c6754c` (fix)
2. **Task 2: Pin the boundary contract and the detached task's clean skip** — `60e7f19` (test)

**Plan metadata:** committed with this SUMMARY.

## Files Created/Modified

- `app/cv/factstore.py` — added the `except (OSError, UnicodeError)` clause re-raising a path-qualified `CvFactStoreError`; module and `load_facts` docstrings now name the non-decodable/unreadable failure mode; `yaml.safe_load` remains the only loader.
- `tests/cv/test_factstore.py` — added `test_non_utf8_bytes_raise_the_path_qualified_fact_store_error`.
- `tests/pipeline/test_rank_optional.py` — added `import structlog` and `test_non_utf8_fact_store_writes_nothing_and_the_run_is_done`.
- `tests/pipeline/test_rank_adversarial.py` — removed `test_unreadable_non_utf8_fact_store_is_a_clean_skip` and its orphaned imports; module docstring no longer claims every test is expected to fail.

## Decisions Made

- Root-cause fix at the shared reader, not the caller's guard: a second caller (Phase 6 tailoring) inherits the typed-failure contract for free.
- The non-UTF-8 case reuses the existing `fact_store_absent` skip reason rather than minting a new one — it is the same operator-visible "unreadable fact store" situation, now with an explicit log event.
- The end-to-end test captures logs across both the run and the drain, because the detached task starts before `_finish`; drain-only capture would be racy.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The plan's `actuals.tokens` (2196, chars/4 over the realized diff) is far below the plan estimate (28000) because the fix is a two-line `except` clause plus tests — recorded as measured.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- RANK-08's gap-2 truth (an absent OR unreadable fact store takes the documented skip path) is now closed end-to-end; every existing fact-store loud-failure case and the three existing D-94 skip-path tests still pass.
- No new package, no migration (alembic head stays `0004`), no schema change. `app/pipeline/rank.py` is unchanged.
- Phase 05 remains NOT complete here — the orchestrator owns phase close-out; this is a gap-closure plan.

---

*Phase: 05-ranking-core-value*
*Completed: 2026-09-22*

## Self-Check

Self-check run after writing this SUMMARY.

- **Files exist on disk:** `app/cv/factstore.py`, `tests/cv/test_factstore.py`, `tests/pipeline/test_rank_adversarial.py`, `tests/pipeline/test_rank_optional.py` — all FOUND.
- **Commits exist:** `8c6754c` (fix), `60e7f19` (test) — both FOUND in `git log`.
- **Acceptance criteria re-run:** all 9 criteria (5 for Task 1, 4 for Task 2) pass.
- **Plan verification commands:** re-run at self-check time.

## Self-Check: PASSED

- Key files present on disk; `git log` confirms `8c6754c` (fix) and `60e7f19` (test).
- Task 1 acceptance criteria: `UnicodeError` count 1 (line 68, the `except` clause); inline `pytest.raises(CvFactStoreError, load_facts, <non-utf8>)` exits 0; `@pytest.mark.xfail` count 1; deleted-def count 0; `yaml.load(` count 0.
- Task 2 acceptance criteria: both new test-name greps report 1; `import structlog` count 1; `pipeline.rank_skipped` reported inside the new test.
- Verification: `.venv/bin/python -m pytest -q tests/cv/test_factstore.py tests/pipeline/test_rank_adversarial.py -x` → **10 passed, 1 xfailed** (9 passed, 1 xfailed at the Task 1 commit, before Task 2 added a fact-store test); `.venv/bin/python -m pytest -q tests/pipeline/test_rank_optional.py tests/cv/test_factstore.py -x` → **15 passed**; full default lane `.venv/bin/python -m pytest -q` → **1046 passed, 14 deselected, 2 xfailed**.
- Deviations: none.
