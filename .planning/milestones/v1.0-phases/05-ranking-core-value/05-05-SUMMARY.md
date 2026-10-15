---
phase: 05-ranking-core-value
plan: 05
subsystem: ui
tags: [ranking-strip, queue, run-repo, jinja2, ui-01, gap-closure]

# Dependency graph
requires:
  - phase: 05-ranking-core-value
    provides: "RunSummary.ranked_count (D-89) and the refresh-only #ranking-strip surface it feeds"
provides:
  - "RunSummary.candidate_count — the run's OWN reason_counts_json['survivors'] as an optional int"
  - "_optional_int — an absent/non-numeric-tolerant int that degrades to None, not 0"
  - "_ranking_strip(session, latest_run) with no request-derived denominator"
  - "queue.html's conditional 'Ranked N of M' / 'Ranked N' strip"
affects: [05-ranking-core-value (plan 05-06), verify-work, ship]

# Actuals (#2632) — same estimateTokens scale (chars/4 over the realized diff).
actuals:
  tokens: 1591
  tasks: 2
  commits: 2
plan_head_before: 2f71ea5a9b59fce9c65d542df0e67bc4678ff4ca

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Optional-vs-coerced read helper: `_optional_int` for values a surface divides BY, `_int` for counts that must always render"
    - "One population per ratio: a progress strip's numerator and denominator must both come from the same persisted run row"

key-files:
  created: []
  modified:
    - app/db/repositories/run_repo.py
    - app/web/routes.py
    - app/web/templates/html/queue.html
    - tests/api/test_queue_ranked.py
    - tests/api/test_queue_ranking_adversarial.py

key-decisions:
  - "The strip's denominator is the run's own reason_counts_json['survivors'], never this request's page total"
  - "An absent candidate count renders the numerator alone rather than a fabricated denominator"

patterns-established:
  - "A ratio surface must draw both numbers from one population; `_optional_int` keeps an absent value absent instead of coercing it to 0"

requirements-completed: [UI-01]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "The ranking strip's two numbers both come from the latest run's own population: numerator is ranked_count, denominator is that run's reason_counts_json['survivors']"
    requirement: UI-01
    verification:
      - kind: integration
        ref: "tests/api/test_queue_ranked.py#test_ranking_strip_reports_the_runs_own_candidate_count"
        status: pass
    human_judgment: false
  - id: D2
    description: "A run that persisted no candidate count degrades to the numerator alone ('Ranked 5'), never a ratio against an absent or fabricated denominator"
    requirement: UI-01
    verification:
      - kind: integration
        ref: "tests/api/test_queue_ranked.py#test_ranking_strip_without_candidate_count_renders_no_ratio"
        status: pass
    human_judgment: false
  - id: D3
    description: "The obsolete CR-01 strict-xfail sentinel is retired; the default lane stays green with no XPASS and the WR-03 sentinel untouched"
    verification:
      - kind: other
        ref: ".venv/bin/python -m pytest -q tests/api/test_queue_ranking_adversarial.py (1 xfailed, 0 XPASS)"
        status: pass
    human_judgment: false

duration: 8 min
completed: 2026-09-22
status: complete
---

# Phase 5 Plan 05: Ranking strip — the denominator is the run's own candidate population

**The queue's "Ranked X of Y" strip now draws both numbers from one run — `ranked_count` over that run's own `reason_counts_json['survivors']` — and degrades to "Ranked X" alone when the run persisted no candidate count.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-09-22T15:30:38Z
- **Completed:** 2026-09-22T15:38:22Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- `RunSummary` gained `candidate_count: int | None`, read from the run's own `reason_counts_json['survivors']` — the survivors the hard filter handed to ranking, written by `app.pipeline.run._finish`.
- Added `_optional_int`, deliberately distinct from `_int`: an absent or non-numeric value stays `None` instead of being coerced to `0`, because `0` is exactly the false denominator this plan exists to remove.
- `_ranking_strip` dropped its request-derived `page` parameter and its `int(page.total)` denominator; the strip can no longer pair two disjoint populations into a nonsense ratio like `Ranked 30 of 5`.
- `queue.html` renders `Ranked N of M` only when a candidate count exists, else `Ranked N` alone; the `— cap reached (…)` suffix survives in both branches.
- Retired the obsolete CR-01 strict-xfail sentinel and re-homed its coverage as two first-class regression tests in the queue suite.

## Task Commits

Each task was committed atomically:

1. **Task 1: One population behind the strip** - `d5ac5c2` (fix)
2. **Task 2: Pin the strip behaviour with first-class regression tests** - `f894b4c` (test)

**Plan metadata:** committed separately by the executor close-out.

## Files Created/Modified

- `app/db/repositories/run_repo.py` - `_optional_int` helper; `RunSummary.candidate_count` field and its `_summary` assignment.
- `app/web/routes.py` - `_ranking_strip(session, latest_run)`; `candidates` sourced from `RunSummary.candidate_count`; rewritten docstring; call site updated.
- `app/web/templates/html/queue.html` - conditional ratio / numerator-only branch inside `#ranking-strip`.
- `tests/api/test_queue_ranked.py` - `_seed_run_with_coverage` helper plus the two lasting strip regression tests.
- `tests/api/test_queue_ranking_adversarial.py` - retired `test_ranking_strip_denominator_is_the_runs_own_candidates` and its helper; trimmed imports; docstring updated.

## Decisions Made

- **The denominator is the run's own population, not the page total.** `page.total` is the rows surviving this request's `q`/`excluded`/`hidden`/`saved`/`scope` predicates, the `min_score` threshold and the `SCORE_SORT_SCAN_LIMIT` truncation — a disjoint set from the run's score rows. Pairing them produced the reproduced `Ranked 30 of 5`.
- **Absent means absent.** A run that predates the counts write, or whose `reason_counts_json` is unreadable, yields `None` and renders the numerator alone. No fabricated denominator, no coerced `0`.
- **`_optional_int` is a separate helper, not a `_int` change.** `_int`'s coercion to `0` is correct for counts that must always render; widening it would have broken the sentence renderer for the same wrongly-shaped rows.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The full default lane (`.venv/bin/python -m pytest -q`) reports **1044 passed, 14 deselected, 3 xfailed** — the 3 xfailed are the retained strict sentinels (including the untouched WR-03 `?min_score=nan` probe), with no XPASS.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Gap 1 (CR-01) is closed: the strip no longer asserts a ratio the run did not produce, and both the ratio and the degrade path are pinned by first-class tests.
- No migration, no schema change, no new package, no CDN asset; Alembic head stays `0004`.
- RANK-08's authored closure remains plan 05-06 (the unreadable-fact-store skip path) — this plan does not resolve the refusal-audit semantics.

## Self-Check

**PASSED**

- Task 1 acceptance criteria: all 8 PASS — `candidate_count` grep 3 matches, `def _optional_int` 1 match, `_ranking_strip` signature has no `page` param, `RunSummary.__dataclass_fields__` contains `candidate_count`, `grep -c "int(page.total)" app/web/routes.py` = 0, `@pytest.mark.xfail` count = 1, retired sentinel name count = 0, template gates the ratio on `ranking_strip.get('candidates') is not none`.
- Task 2 acceptance criteria: all PASS — both test names 1 match each, `_seed_run_with_coverage` 2 matches, both tests pass.
- Task 1 verify: `.venv/bin/python -m pytest -q tests/api/test_queue_ranked.py tests/api/test_queue_ranking_adversarial.py tests/api/test_run_trigger.py tests/api/test_run_reason.py -x` → **20 passed, 1 xfailed**.
- Task 2 verify: `.venv/bin/python -m pytest -q tests/api/test_queue_ranked.py -x` → **11 passed**.
- Plan-level verify: `.venv/bin/python -m pytest -q` → **1044 passed, 14 deselected, 3 xfailed**.
- Files exist on disk: `app/db/repositories/run_repo.py`, `app/web/routes.py`, `app/web/templates/html/queue.html`, `tests/api/test_queue_ranked.py`, `tests/api/test_queue_ranking_adversarial.py`.
- Commits exist: `d5ac5c2` (fix), `f894b4c` (test); measured `commits: 2` from ledger `2f71ea5..HEAD`.
- Scope guard honoured: no file outside the plan's `files_modified` was touched; plan 05-06's files were left alone.

---
*Phase: 05-ranking-core-value*
*Completed: 2026-09-22*
