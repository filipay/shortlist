---
phase: 07-assisted-apply-tracker
plan: 11
subsystem: ui
tags: [css, jinja2, tailwind, tracker, layout, gap-closure]

requires:
  - phase: 07-assisted-apply-tracker
    provides: the tracker row (`_application_row.html`) and the shared `.listing-actions` / `.listing-action` queue vocabulary it had reused (07-01, 07-04)
provides:
  - "phase-scoped `tracker-note` / `tracker-actions` / `tracker-action` cell vocabulary that wraps and stacks full-width forms"
  - "a layout-contract regression test pinning the wrapped note, the scoped action cell and the no-nowrap/block declaration set"
affects: [07-12, ui-spec]

actuals:
  tokens: 1866
  tasks: 2
  commits: 2
plan_head_before: 3041e72c6c5b585b585bcb5eb83ca18a61b020d9

tech-stack:
  added: []
  patterns:
    - "phase-scoped CSS cell vocabulary (`tracker-*`) mirroring a shared rule instead of editing it"

key-files:
  created: []
  modified:
    - app/web/templates/html/_application_row.html
    - assets/tailwind/input.css
    - static/vendor/app.css
    - .planning/phases/07-assisted-apply-tracker/07-UI-SPEC.md
    - tests/api/test_applications_tracker.py

key-decisions:
  - "The tracker's note/action cells get their own `tracker-*` classes rather than editing the shared `.listing-actions` / `.listing-action` rules, so the queue row's single-line Save/Hide layout cannot regress."
  - "`static/vendor/app.css` carries the three rules by hand-append, not by a full Tailwind rebuild: `assets/tailwind/input.css` has been out of sync with the built artefact since phase 5, so a blind rebuild would silently drop every phase 6/7 rule (badge-score, badge-stage-*, next-overdue, apply-*, answer-*, htmx-indicator, cv-delete, input[type=file])."

patterns-established:
  - "Phase-scoped cell mirror: when a new row shape reuses a shared cell class it was not sized for, add a `tracker-*` class that copies the shared rule's intent (and any inherited reset) rather than mutating the shared rule."

requirements-completed: [UI-04]

coverage:
  - id: D1
    description: "On `/applications`, a long tracker note wraps (no `white-space:nowrap`) and keeps its full untruncated string in the cell's `title` attribute."
    requirement: UI-04
    verification:
      - kind: unit
        ref: "tests/api/test_applications_tracker.py#test_a_long_note_wraps_and_keeps_its_full_string_in_the_title"
        status: pass
    human_judgment: false
  - id: D2
    description: "The tracker row's Actions column no longer forces min-content width; `Update status` is legible and clickable with no `dd/mm/yyyy` date field painted over it."
    requirement: UI-04
    verification:
      - kind: unit
        ref: "tests/api/test_applications_tracker.py#test_the_tracker_row_uses_the_scoped_action_cell"
        status: pass
      - kind: unit
        ref: "tests/api/test_applications_tracker.py#test_the_tracker_action_cell_cannot_overlap_its_controls"
        status: pass
      - kind: manual_procedural
        ref: "Task 2 <human-check>: rendered-rect non-intersection at 1280px and 375px"
        status: unknown
    human_judgment: true
    rationale: "The declaration contract is proven by test, but the rendered-rect measurement (button rect must not intersect the date-input rect) needs a layout engine; none ships in the repo, so it is the MANDATED human step harvested by the end-of-phase UAT re-run."
  - id: D3
    description: "The queue row's `.listing-actions` / `.listing-action` behaviour is unchanged — Save/Hide still sit on one line."
    requirement: UI-04
    verification:
      - kind: unit
        ref: "tests/api/test_applications_tracker.py#test_the_queue_row_still_uses_the_queue_action_cell"
        status: pass
      - kind: unit
        ref: "tests/test_stylesheet_coverage.py#test_every_template_class_has_a_stylesheet_rule"
        status: pass
    human_judgment: false

duration: 63min
completed: 2026-10-12
status: complete
---

# Phase 7 Plan 11: G-07-5/G-07-6 — tracker note wraps and its scoped action cell cannot overlap controls Summary

**The tracker row swapped the queue's nowrap `.listing-*` cell vocabulary for phase-scoped `tracker-*` cells: long notes wrap with the full string in `title=""`, and the action cell stacks block-level full-width forms so the `Update status` button and the `Next action` date input can no longer share a line box.**

## Performance

- **Duration:** ~63 min (the bulk was building a working test interpreter — see Issues Encountered; the code change itself is a 5-file, 132-line diff)
- **Started:** 2026-10-12T10:10:43Z
- **Completed:** 2026-10-12T11:13:59Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- `_application_row.html`: note `<td>` is `class="tracker-note"` (wrapping, `title="…"` kept); Actions `<td>` is `class="tracker-actions"`; both forms are `class="tracker-action"`. No `.truncate`, no `listing-*` action classes in the row.
- `assets/tailwind/input.css`: `+ .tracker-note` (`white-space:normal; overflow-wrap:anywhere; max-width:24rem`), `+ .tracker-actions` (`min-width:16rem; white-space:normal; vertical-align:top`), `+ .tracker-action` (`display:block; margin:0 0 .5rem`) — added beside the shared rules, which are byte-unchanged.
- `static/vendor/app.css`: the three committed rules (hand-appended, see deviations).
- `07-UI-SPEC.md`: the four self-contradicting rows corrected to the wrap-not-truncate truth, the three `tracker-*` tokens added to the enumerated new-token list, and the phase rule at L34 reworded to point at that list instead of a fixed wrapper-class count.
- `tests/api/test_applications_tracker.py`: four new tests (wrapped note, scoped action cell, no-overlap declaration contract, queue-cell unchanged).

## Task Commits

Each task was committed atomically:

1. **Task 1: Give the tracker row a wrapping note cell and a scoped, stackable action cell** - `2bd8df7` (fix)
2. **Task 2: Regression — wrapped note, scoped action cell, and the no-overlap layout contract** - `b3a3c37` (test)

**Plan metadata:** (docs: complete plan) — see the final metadata commit.

_Note: Task 2 is `tdd="true"`; RED was demonstrated by restoring the pre-fix markup from `HEAD~1` and observing 3 of the 4 new tests fail, then restoring and observing GREEN._

## Files Created/Modified

- `app/web/templates/html/_application_row.html` — `tracker-note` / `tracker-actions` / `tracker-action` classes replace `truncate` / `listing-actions` / `listing-action`.
- `assets/tailwind/input.css` — the three `tracker-*` rules (canonical source).
- `static/vendor/app.css` — the three rules in the hand-appended block.
- `.planning/phases/07-assisted-apply-tracker/07-UI-SPEC.md` — corrected note-cell contract + new-token list.
- `tests/api/test_applications_tracker.py` — four layout-contract / regression tests (+ `_row_markup`, `_rule_declarations` helpers, `Path` import).

## Decisions Made

- Phase-scoped `tracker-*` classes rather than editing the shared `.listing-actions` / `.listing-action` rules — the queue row's one-line Save/Hide must not regress (07-UI-SPEC L34 sanctions `tracker-*`).
- No full Tailwind rebuild (see deviations) — `input.css` is out of sync with the built artefact, so a rebuild is destructive.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Built `static/vendor/app.css` by hand-append rather than a full Tailwind CLI rebuild**

- **Found during:** Task 1
- **Issue:** The plan says to regenerate `static/vendor/app.css` with the pinned Tailwind CLI. Doing so is destructive here: `assets/tailwind/input.css` was last modified in phase 5 (`dd70585`), while the built artefact was updated through phase 7 (`b82a8e2`). Every phase 6/7 rule (`.badge-score*`, `.badge-stage-*`, `.next-overdue`, `.apply-*`, `.answer-*`, `.htmx-indicator`, `.cv-delete`, `input[type=file]`, `.badge-flagged`, `.cv-status`, …) lives only in the hand-appended block of `static/vendor/app.css` and is **not** in `input.css`. A rebuild produced a 34371-byte file missing those rules — `tests/test_stylesheet_coverage.py` would fail on `badge-flagged`, and the phase 6/7 UI would silently lose its styling.
- **Fix:** Applied the three `tracker-*` declarations to the committed `static/vendor/app.css` in the same minified shape, in the existing hand-appended block (the 05-11 precedent the plan names as the fallback). The canonical `assets/tailwind/input.css` edit WAS made (the three rules are there), so a future correct rebuild — once `input.css` is reconciled — carries them.
- **Files modified:** `assets/tailwind/input.css`, `static/vendor/app.css`
- **Verification:** `tests/test_stylesheet_coverage.py` passes (5 passed); `grep -c 'tracker-actions' static/vendor/app.css` is non-zero; the shared `.listing-actions` / `.listing-action` declarations are byte-unchanged in the diff.
- **Committed in:** `2bd8df7` (Task 1 commit)

**Out of scope (deferred, not fixed):** the `assets/tailwind/input.css` ↔ `static/vendor/app.css` drift itself. It is pre-existing, predates this plan, and fixing it (re-adding every phase 6/7 rule to `input.css`) is a much larger change than this gap-closure plan. Logged to `deferred-items.md`.

### Documented behaviour change (expected, not a failure)

`.truncate` was the note cell's only consumer. After the rewrite it has no template consumer, so a correct rebuild would drop the `.truncate` utility from `static/vendor/app.css`. Because of the hand-append above, the utility is still present in the built file — harmless (nothing references it) and explicitly allowed by Task 1's acceptance criteria.

---

**Total deviations:** 1 auto-fixed (blocking), 1 pre-existing issue deferred.
**Impact on plan:** The fix is complete and green. The deviation changes HOW the built artefact was produced, not what it contains for this fix.

## Rendered-rect check (MANDATED human-check — DEFERRED, no numbers fabricated)

The Task 2 `<human-check>` requires a `getBoundingClientRect()` measurement proving the `Update status` button rect does not intersect the `Next action` date-input rect, at 1280px and 375px, in the shipped default state (JS on, `Move to` select untouched so the CV picker stays hidden).

**Not performed by this executor.** No layout engine ships in the repo (dev deps are exactly `pytest`, `pytest-asyncio`, `ruff`; this phase adds no dependency), the environment has no browser and no Playwright/Selenium, and installing one was out of scope for the plan. Per `workflow.human_verify_mode = "end-of-phase"` this measurement is harvested by the phase UAT re-run. No rect pairs are recorded here because none were measured — CONVENTIONS 6 forbids a false guarantee in prose. This is logged to `.planning/WINDOWS.md` as an `unrun-verify` entry so it is visible at ship time.

The deterministic half of the G-07-6 evidence IS automated and passing: `test_the_tracker_action_cell_cannot_overlap_its_controls` asserts `.tracker-actions` sets `white-space:normal` with no `nowrap`, `.tracker-action` sets `display:block`, and `.tracker-note` sets `white-space:normal` + `overflow-wrap:anywhere`.

Exact console snippet for the human step (per row, replace `<id>`):

```
(() => { const r = document.querySelector('#application-row-<id>'); const b = r.querySelector('form:nth-of-type(1) button[type=submit]').getBoundingClientRect(); const d = r.querySelector('input[type=date]').getBoundingClientRect(); const hit = !(b.right <= d.left || d.right <= b.left || b.bottom <= d.top || d.bottom <= b.top); return { button:[b.x,b.y,b.width,b.height], date:[d.x,d.y,d.width,d.height], intersects: hit }; })()
```

## Issues Encountered

- **The project's `.venv` cannot run the tests in this environment.** `.venv/bin/python3` resolves to system Python **3.11** while the installed site-packages are built for **3.14** (`lib/python3.14/site-packages`, `cpython-314-*.so`), and `.venv-host/bin/pytest`'s shebang points at a stale `/mnt/data/...` path. There is no `python3.14` binary on the machine. Resolution: installed `uv`, provisioned CPython 3.13 and a throwaway venv at `/tmp/opencode/gsdvenv13`, and installed the project `[dev]` extras. All test runs below used that interpreter (Python 3.13, matching `pyproject.toml`'s `requires-python = ">=3.13"`). The repo's toolchain is untouched.
- The dev-time Tailwind CLI in the repo's `node_modules` was platform-broken (`Cannot find module '../lightningcss.linux-x64-gnu.node'`); a version-matched reinstall made it runnable, which is what surfaced the `input.css` drift above.

## Test Results

Run with `/tmp/opencode/gsdvenv13/bin/python -m pytest` (see Issues Encountered):

- **Combined gate (plan `<verification>`):** `tests/test_stylesheet_coverage.py tests/api/test_applications_tracker.py -x` → **27 passed**.
- **Full default lane:** `pytest -q` (`-m 'not live and not latex'`) → **1681 passed, 14 deselected, 2 xfailed** (5m18s).
- **`ruff check tests/api/test_applications_tracker.py`** → All checks passed.
- **TDD RED (pre-fix markup, `HEAD~1`):** 3 of the 4 new tests failed (`long_note_wraps`, `scoped_action_cell`, `cannot_overlap`); `queue_row_still` passed, as expected. **GREEN (post-fix):** 22 passed.

## Next Phase Readiness

- G-07-5 and G-07-6 are closed in code, stylesheet and tests. G-07-7 is plan 07-12 (sibling, untouched here).
- Open hand-off: the mandated rendered-rect human-check (above) must run in the phase UAT re-run; until then the overlap claim rests on the declaration contract plus the (recorded) diagnosis, not on a measured rect.
- Pre-existing `input.css` drift is deferred (see deviations) — it will bite any future full rebuild.

---

*Phase: 07-assisted-apply-tracker*
*Completed: 2026-10-12*

## Self-Check: PASSED

- SUMMARY.md: FOUND
- Commit `2bd8df7` (Task 1): FOUND
- Commit `b3a3c37` (Task 2): FOUND
- All five modified files: FOUND
