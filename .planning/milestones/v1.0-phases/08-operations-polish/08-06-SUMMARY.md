---
phase: 08-operations-polish
plan: 06
subsystem: database
tags: [retention, prune, sqlite, sqlalchemy, structlog, jinja2]

# Dependency graph
requires:
  - phase: 08-operations-polish
    provides: the prune preview surface (08-05) whose freed-size figure this plan corrects
provides:
  - a regular-file gate on the only `st_size` site, so a non-regular stored path is never summed into the prune preview's freed-size total
  - a structlog diagnostic trail naming every measured path with its size and every not-measurable path with its mode
  - the unmeasured count surfaced in the preview summary sentence, with the reason line naming the non-regular class
  - the amended UI-SPEC copy rows declaring the unmeasured clause
affects: [retention, prune, settings-ui]

# Actuals (#2632) — pairs with the plan's `estimate` (tokens 26000) to calibrate future estimates.
# Same estimateTokens scale (chars/4 over the realized diff), never a harness token count.
actuals:
  tokens: 5295
  tasks: 2
  # MEASURED at SUMMARY write: `git rev-list --count 216d38c..HEAD` = 2 task commits.
  # The plan's own metadata commits (this SUMMARY, the WINDOWS ledger) follow it.
  commits: 2
plan_head_before: 216d38c

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A repository module owns a `structlog.get_logger(__name__)` and emits one diagnostic event per measurement outcome (source_repo precedent)"

key-files:
  created: []
  modified:
    - app/db/repositories/retention_repo.py
    - app/web/templates/html/settings.html
    - tests/db/test_retention_repo.py
    - tests/api/test_settings_prune.py
    - .planning/phases/08-operations-polish/08-UI-SPEC.md

key-decisions:
  - "Gate on `stat.S_ISREG`, not a plausibility bound: a cap would silently rewrite a genuinely large regular file's true size, and the plan's prohibitions forbid inventing one"
  - "Reuse `PrunePreview.missing_files` rather than add a second counter, so the preview and the route cannot disagree about how much was measured"
  - "Log the resolve-failure branch as well (`reason=\"unresolvable\"`), closing a silent skip (CONVENTIONS rule 2)"

patterns-established:
  - "A measurement that cannot measure something says so in the same sentence as the number (fail closed, visibly)"

requirements-completed: [RUN-07]

# Coverage metadata (#1602) — one entry per shipped deliverable.
coverage:
  - id: D1
    description: "The prune preview's freed-size figure sums regular files only; a directory, FIFO, socket or symlink-to-directory resolving inside the artifacts root contributes 0 and is counted as unmeasured"
    requirement: RUN-07
    verification:
      - kind: unit
        ref: "tests/db/test_retention_repo.py#test_a_not_regular_stored_path_is_never_measured (directory, fifo, socket, symlink_to_dir)"
        status: pass
      - kind: unit
        ref: "tests/db/test_retention_repo.py#test_a_directory_stored_as_an_artifact_path_is_not_summed"
        status: pass
    human_judgment: false
  - id: D2
    description: "The preview summary states how many paths could not be measured, in the same sentence as the size, and omits the clause when nothing was unmeasured"
    requirement: RUN-07
    verification:
      - kind: integration
        ref: "tests/api/test_settings_prune.py#test_a_directory_path_makes_the_summary_say_not_measured"
        status: pass
      - kind: integration
        ref: "tests/api/test_settings_prune.py#test_not_measured_paths_render_the_clause_for_every_non_regular_kind"
        status: pass
      - kind: integration
        ref: "tests/api/test_settings_prune.py#test_a_regular_file_preview_renders_without_the_not_measured_clause (negative control)"
        status: pass
    human_judgment: false
  - id: D3
    description: "No size cap was introduced: a genuinely large regular file is still reported at its exact size"
    requirement: RUN-07
    verification:
      - kind: unit
        ref: "tests/db/test_retention_repo.py#test_a_large_regular_file_is_measured_at_its_exact_size (1<<34 sparse file)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The declared UI copy (UI-SPEC preview-panel row, zero-one-many row, §D preview bullet) declares the unmeasured clause at all three touch points"
    requirement: RUN-07
    verification:
      - kind: other
        ref: "python assertion over .planning/phases/08-operations-polish/08-UI-SPEC.md: the three named rows/bullets each contain 'not measured'"
        status: pass
    human_judgment: false

# Metrics
duration: 34min
completed: 2026-10-15
status: complete
---

# Phase 8 Plan 06: Prune preview measures regular files, and says so Summary

**The prune preview now sums only regular files — gating `_size_inside` on `stat.S_ISREG` — and appends `· N path(s) not measured` to the summary sentence whenever any selected path could not be measured, with a structlog trail naming every path.**

## Performance

- **Duration:** 34 min
- **Started:** 2026-10-15T00:23:00Z
- **Completed:** 2026-10-15T00:57:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- `retention_repo._size_inside` stats once and returns a size **only** for a regular file (`stat.S_ISREG`); a directory, a device, a FIFO, a socket or a symlink-to-directory resolving inside the artifacts root now contributes 0 and increments the existing `missing_files` counter instead of being summed. This is the fault behind the operator's `This will delete 4 artifacts · 117043.0 GB.`
- A diagnostic trail was added: a DEBUG event per measured path (resolved path, mode, size), a WARNING with a reason (`missing` / `not_regular` / `unresolvable`) per not-measurable path, and a WARNING for an outside-root path with **no `stat`** — preserving 08-05's T-08-23 property that the preview cannot leak file existence.
- The preview summary keeps its declared shape and appends `· N path(s) not measured` exactly when `missing_files` is non-zero, so the freed-size figure can never read as complete when part of it was unmeasured. The reason line names the non-regular class alongside missing and outside-root paths and no longer restates the count.
- The UI-SPEC's preview-panel row, `zero-one-many` row and §D preview bullet were amended to declare the unmeasured clause as part of the contract.
- **No size cap or plausibility threshold was introduced** (the plan's prohibition); a rule-7 test asserts a `1<<34` sparse regular file is reported at its exact size.

## Task Commits

Each task was committed atomically:

1. **Task 1: Measure only regular files, and leave a trail naming every path** — `2783c65` (fix)
2. **Task 2: Say in the preview summary how much could not be measured** — `1df348a` (fix)

**Plan metadata:** see the `docs(08-06)` SUMMARY commit (this file).

_Note: both tasks are single commits (no TDD red/green split was required by the plan)._

## Files Created/Modified

- `app/db/repositories/retention_repo.py` — `import stat` + `import structlog`; module `log`; `_size_inside` gated on `stat.S_ISREG` with the four-outcome diagnostic trail; `PrunePreview.missing_files` docstring names the non-regular class.
- `app/web/templates/html/settings.html` — the `#prune-preview-summary` line gains the conditional `· N path(s) not measured` clause; `#prune-preview-missing` becomes a reason line naming the non-regular class.
- `tests/db/test_retention_repo.py` — parametrized non-regular-path failure class (`directory`/`fifo`/`socket`/`symlink_to_dir`), the literal-repro directory test, and the rule-7 large-regular-file test.
- `tests/api/test_settings_prune.py` — literal-repro rendered-summary test, parametrized non-regular-kind rendering test, and the regular-file negative control.
- `.planning/phases/08-operations-polish/08-UI-SPEC.md` — the three declared-copy touch points amended.

## Decisions Made

- **Gate on `stat.S_ISREG`, never a plausibility bound.** A cap is a second guess layered on a guess and would silently rewrite a genuinely large regular file's true size. A regular file's `st_size` is the size the unlink will free; a directory's is not.
- **Reuse the existing `missing_files` field** rather than add a second counter — the preview and the route cannot then disagree about how much was measured.
- **Log the resolve-failure branch too.** The plan enumerated four events and did not mention the pre-existing `resolve()` failure branch; leaving it silent would be a silent skip on a measurement (CONVENTIONS rule 2), so it logs `prune.size_not_measured` with `reason="unresolvable"`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Closed the resolve-failure silent skip in `_size_inside`**
- **Found during:** Task 1
- **Issue:** `Path(raw).resolve()` can raise `OSError`/`ValueError` (a symlink loop, a null byte in a legacy row). The plan's four-event enumeration did not cover this branch, and the pre-existing code returned `None` with no trail — a silent skip on a measurement.
- **Fix:** Log `prune.size_not_measured` with `reason="unresolvable"` and the stored path before returning `None`. The `missing_files` docstring was extended to name this class.
- **Files modified:** `app/db/repositories/retention_repo.py`
- **Verification:** `tests/db/test_retention_repo.py` green; the module's diagnostic-trail assertions pass.
- **Committed in:** `2783c65` (Task 1 commit)

**2. [Rule 3 - Blocking] `Path.truncate` does not exist; used `os.truncate`**
- **Found during:** Task 1
- **Issue:** The plan's Task 1 text specifies `Path.truncate(1 << 34)` for the large-file test, but `pathlib.Path` has no `truncate` method (verified: `'truncate' in dir(pathlib.Path)` is `False`).
- **Fix:** Used `os.truncate(big, 1 << 34)` — the same logical operation, one line.
- **Files modified:** `tests/db/test_retention_repo.py`
- **Verification:** The sparse file reports `17179869184` bytes and the test asserts `size_bytes == 1 << 34`.
- **Committed in:** `2783c65` (Task 1 commit)

### Plan-checker amendments folded in (binding)

- **WARNING (CONVENTIONS rule 6).** `PrunePreview.missing_files`'s docstring now names the non-regular class alongside missing/unresolvable and outside-root paths, and `_size_inside`'s docstring is consistent with it — no enumeration omits a reason the code now produces.
- **INFO.** Task 2's UI-SPEC check was strengthened from a single substring to an assertion that **all three** declared touch points (the preview-panel row, the `zero-one-many` row and §D's preview bullet) carry the unmeasured clause.

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 blocking) + 2 plan-checker amendments folded in
**Impact on plan:** Both auto-fixes are correctness/consistency; no scope creep. No category, route, migration, dependency or configuration knob was added.

## Issues Encountered

- The project `.venv` is unusable in this sandbox (Python 3.11.2, no pytest). All verification used the documented lane `PYTHONPATH=/workspace/job-search:/workspace/job-search/.venv/lib/python3.11/site-packages /tmp/opencode/gsdvenv13/bin/python -m pytest` (Python 3.13.16, pytest 9.1.1).
- `ruff` is not on `PATH`; used `/tmp/opencode/gsdvenv13/bin/ruff` (0.16.7). `ruff check` and `ruff format --check` both pass on the three changed Python files.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The automated suites are green: the full hermetic suite reports **1967 passed, 15 deselected, 2 xfailed, 0 failed** (baseline 1955 passed + 12 new tests).
- The operator's next live prune walk (a browser with the stack up) remains **unrun** — Docker and a browser are absent from the sandbox. Recorded as WINDOWS entry #18: the next live preview must show the unmeasured clause and must never show an impossible size, and must log `prune.size_measured` / `prune.size_not_measured` naming each path and its mode/size. This is a non-blocking verification of the fix, not a defect.
- Residual risk (accepted by the plan): a bind mount that reports a bogus `st_size` for a path that genuinely IS a regular file cannot be detected without a cap, and a cap is deliberately rejected. The DEBUG event is what makes that case identifiable on the next live walk.

---

*Phase: 08-operations-polish*
*Completed: 2026-10-15*

## Self-Check: PASSED

- All five modified files exist on disk; the SUMMARY file exists.
- Both task commits (`2783c65`, `1df348a`) exist in history.
- No tracked-file deletions in either commit; no untracked files left behind.
- Full hermetic suite: 1967 passed, 15 deselected, 2 xfailed, 0 failed.
