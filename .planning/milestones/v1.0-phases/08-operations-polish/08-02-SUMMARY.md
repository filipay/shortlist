---
phase: 08-operations-polish
plan: 02
subsystem: ui
tags: [tailwind, responsive, css, jinja2, htmx, accessibility]

# Dependency graph
requires:
  - phase: 07-assisted-apply-tracker
    provides: the 06/07 UI review's 44x44px touch-target finding and the shipped `.queue-table` / `.health-table` shells
provides:
  - "`assets/tailwind/input.css` — `.table-scroll`, `.touch-target` (+ `.queue-toggle`) and `.health-system` component rules plus the `@variant max-md` card-reflow media block"
  - "`static/vendor/app.css` — the regenerated, byte-identical build of `input.css` under the pinned Tailwind CLI"
  - "`data-label` on every queue-row, tracker-row and health-row cell (the no-JS card-reflow labels)"
  - "accessible scroll regions (`role=region tabindex=0 aria-label`) around the merges / run-history / fit-breakdown tables"
  - "`docs/runbook-responsive-ui.md` — the operator checklist for UI-06"
affects: [08-04 (consumes `.health-system`; edits the same `base.html` nav block)]

# Actuals (#2632) — chars/4 over the realized diff of the three task commits.
actuals:
  tokens: 26631
  tasks: 3
  commits: 3
  plan_head_before: e0043d63db1d3bc9794ec2b7260e68d56d21e50d

tech-stack:
  added: []
  patterns:
    - "Phone card-reflow: `data-label` on every `<td>` + a `@variant max-md` block that sets the table elements to `display:block` and renders `td[data-label]::before { content: attr(data-label) }`; the header row is clip-hidden, not `display:none`"
    - "`@variant max-md` (compiles to `@media not all and (min-width:48rem)`) as the exact complement of Tailwind's `md`, so the two regimes tile the width axis with no gap"
    - "Accessible scroll region: `<div class=\"table-scroll\" role=\"region\" tabindex=\"0\" aria-label=\"…\">` wrapped around a non-journey table"

key-files:
  created:
    - docs/runbook-responsive-ui.md
  modified:
    - assets/tailwind/input.css
    - static/vendor/app.css
    - app/web/templates/html/_listing_row.html
    - app/web/templates/html/queue_list.html
    - app/web/templates/html/_application_row.html
    - app/web/templates/html/applications_list.html
    - app/web/templates/html/_health_strip.html
    - app/web/templates/html/_screening_drafts.html
    - app/web/templates/html/_application_history.html
    - app/web/templates/html/base.html
    - app/web/templates/html/merges.html
    - app/web/templates/html/runs.html
    - app/web/templates/html/listing_detail.html

key-decisions:
  - "The whole journey reflow lives in ONE `@variant max-md` block at the end of `input.css` (authored in Task 1) — the plan split the `.touch-target` rules and the control-widths into Task 1 and Task 2, but they are one cohesive cascade block and were written once, so Task 2 needed no second rebuild"
  - "`.queue-toggle` is grouped with `.touch-target` in the source rule rather than adding the class to the filter labels: those labels live in `queue.html` / `applications.html`, which are outside the plan's file set"
  - "The `@variant md { min-height: auto; }` desktop overlay the plan mentioned conditionally was not added: the 44px floor is a standing requirement (UI-SPEC §Spacing), not a phone-only one, so there is no complement to express"

requirements-completed: [UI-06]

coverage:
  - id: D1
    description: "The committed stylesheet is the pinned CLI's byte-identical build of its source, and it defines the three new component rules"
    requirement: UI-06
    verification:
      - kind: unit
        ref: "tests/test_stylesheet_coverage.py#test_the_committed_stylesheet_is_the_build_of_its_source"
        status: pass
      - kind: unit
        ref: "tests/test_stylesheet_coverage.py#test_every_template_class_has_a_rule_in_the_source_stylesheet"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every journey-table cell carries a `data-label` equal to its desktop `<th>` text, and every admin table keeps its markup inside a `table-scroll` labelled scroll region"
    requirement: UI-06
    verification:
      - kind: integration
        ref: "pytest -q -m 'not live and not latex' (1805 passed)"
        status: pass
      - kind: unit
        ref: "tests/test_stylesheet_coverage.py + tests/test_no_cdn.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "Below the phone breakpoint the queue / tracker / health tables render as label:value cards with no horizontal scroll, and every compact journey control clears 44x44px"
    verification: []
    human_judgment: true
    rationale: "No layout engine or browser ships in the agent sandbox; the reflow's visual correctness and the rendered 44x44px boxes are only observable in a real browser. Recorded as the unrun operator checklist in docs/runbook-responsive-ui.md (D-161)."
  - id: D4
    description: "docs/runbook-responsive-ui.md exists with the 320/375/768 x journey-pages matrix and the long-name wrap case"
    requirement: UI-06
    verification:
      - kind: unit
        ref: "assertion in 08-02-PLAN.md Task 3 <verify> (names all widths, pages and the operator rationale)"
        status: pass
    human_judgment: false

# Metrics
duration: 33min
completed: 2026-10-14
status: complete
---

# Phase 08 Plan 02: The phone is a first-class journey target Summary

**The queue, tracker and health tables reflow to label:value cards below 48rem under a single CSS-only rule authored in the Tailwind source and rebuilt byte-identically, the admin tables gained keyboard-reachable labelled scroll regions, and the journey's compact controls now meet the 44x44px floor.**

## Performance

- **Duration:** ~33 min
- **Started:** 2026-10-14T17:30Z
- **Completed:** 2026-10-14T18:03Z
- **Tasks:** 3
- **Files modified:** 19 (13 production/template/doc + 1 CSS source + 1 CSS artefact + 5 test files)

## Accomplishments

- `assets/tailwind/input.css` gained `.table-scroll`, `.touch-target` (grouped with `.queue-toggle`) and `.health-system`, plus the `@variant max-md` card-reflow block (display:block reflow, `attr(data-label)` labels, clip-hidden header, `overflow-wrap:anywhere`, full-width journey controls).
- `static/vendor/app.css` is the pinned `tailwindcss@4.3.3` build of that source — the byte-identity guard passes **with the assertion run, not skipped**.
- `data-label` on all 8 queue-row cells, all 6 tracker cells and all 5 health-row cells, each matching its desktop `<th>` text verbatim.
- `.touch-target` on the `Copy answer` button, both `History (n)` summaries, the six nav links and both pagers; the `.queue-toggle` filter labels covered by the grouped rule.
- `merges.html` / `runs.html` / `listing_detail.html` wrapped in `div.table-scroll[role=region][tabindex=0][aria-label]` with their own markup unchanged.
- `docs/runbook-responsive-ui.md` ships the operator checklist (320/375/768 × queue, listing detail, `/status`, run control, applications) with the long-name wrap case.

## Task Commits

Each task was committed atomically:

1. **Task 1: One journey table reflows on a phone — source, build, artefact, guard** - `2c575a7` (feat)
2. **Task 2: The tracker and health tables reflow, and the journey's compact controls reach 44x44px** - `343b247` (feat)
3. **Task 3: The admin tables scroll, and the operator checklist ships** - `4184f2d` (feat)

**Plan metadata:** (this SUMMARY) `docs(08-02): complete …`

## Files Created/Modified

- `assets/tailwind/input.css` — three new component rules + the `@variant max-md` reflow block
- `static/vendor/app.css` — regenerated pinned-CLI build
- `app/web/templates/html/_listing_row.html` — 8 `data-label` attributes
- `app/web/templates/html/queue_list.html` — `touch-target` on the pager buttons
- `app/web/templates/html/_application_row.html` — 6 `data-label` attributes + `touch-target` on the history summary
- `app/web/templates/html/applications_list.html` — `touch-target` on its pager buttons (header row unchanged)
- `app/web/templates/html/_health_strip.html` — 5 `data-label` attributes
- `app/web/templates/html/_screening_drafts.html` — `touch-target` on the Copy-answer button
- `app/web/templates/html/_application_history.html` — `touch-target` on the summary
- `app/web/templates/html/base.html` — `touch-target` on the six nav links
- `app/web/templates/html/merges.html`, `runs.html`, `listing_detail.html` — scroll-region wrappers
- `docs/runbook-responsive-ui.md` — new operator checklist
- `tests/api/test_settings_page.py`, `test_health.py`, `test_queue_links.py`, `test_apply_package.py`, `tests/pipeline/test_ingest_e2e.py` — the assertions the plan's own markup change broke

## Decisions Made

- The reflow is one cohesive `@variant max-md` block authored in Task 1; the plan's Task-2 CSS extension (control widths / `#queue-pager`) was folded in, so the second task changed templates only and did not need a second rebuild.
- `.queue-toggle` is grouped into the `.touch-target` source rule instead of editing `queue.html` / `applications.html`, which are outside the plan's file set.
- The desktop overlay (`@variant md { min-height:auto }`) the plan offered conditionally was not added — the 44px floor is standing, not phone-only.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The plan's markup change broke five pinned test assertions**
- **Found during:** Task 1 and Task 2 (running the hermetic suite).
- **Issue:** Adding `data-label` to a `<td>` and `touch-target` to an anchor changes the exact tag text that several tests pin: `tests/pipeline/test_ingest_e2e.py:188,193` and `tests/api/test_queue_links.py:105,233` require `<td class="listing-title">` / `<td class="listing-source">`; `tests/api/test_health.py:641,642` require `class="health-source">` / `class="health-returned">`; `tests/api/test_settings_page.py:25,79` require `<a class="nav-link nav-current" href="/settings"…>`; `tests/api/test_apply_package.py:470` requires `class="button"`. The suite could not stay green while the plan's own required markup was in place.
- **Fix:** Updated each assertion to the new exact tag text (attribute added in the same order the template now renders). No test was loosened or deleted; each still pins the concrete rendered markup.
- **Files modified:** `tests/pipeline/test_ingest_e2e.py`, `tests/api/test_queue_links.py`, `tests/api/test_health.py`, `tests/api/test_settings_page.py`, `tests/api/test_apply_package.py`.
- **Verification:** `pytest -q -m 'not live and not latex'` → **1805 passed, 15 deselected, 2 xfailed** (run after Task 2 and again after Task 3).
- **Committed in:** `343b247` (Task 2) — except the Task-1 queue-row files, whose edits were picked up by the same commit.

### Plan-metadata notes (not code deviations)

- The plan's per-task acceptance says each task's `git diff --stat HEAD --` lists *exactly* its `files_modified`. Two entries are ownership-only, so the realized diffs are smaller: Task 1 lists `queue_list.html` (its change lands in Task 2) and Task 2 lists `input.css`/`app.css` (authored in Task 1). The real deltas are 3, 12 and 4 files respectively.
- The plan's `files_modified` did not include the five test files the markup change necessarily touches; they are recorded above.

## Issues Encountered

- `.venv` is unusable in this sandbox (3.14.7 musl extensions under a 3.11 interpreter). All verification ran on the known-working lane: `PYTHONPATH=/workspace/job-search:/workspace/job-search/.venv/lib/python3.11/site-packages /tmp/opencode/gsdvenv13/bin/python -m pytest`.
- `gsd-tools windows append` is blocked by a pre-existing `WINDOWS.md` counter mismatch (frontmatter 11/1/2/14 vs rows 10/1/2/13). The UI-06 unrun verify is therefore recorded here and in `deferred-items.md` instead. (The plan's expected pre-existing drift, `test_the_committed_stylesheet_is_the_build_of_its_source`, is **fixed** by this plan's rebuild.)

## Known Stubs

None.

## Threat Flags

None — the plan added no endpoint, auth path, file-access pattern or schema change.

## User Setup Required

None.

## Next Phase Readiness

- UI-06 is structurally complete and the hermetic suite is green. The **operator checklist in `docs/runbook-responsive-ui.md` is unrun** (Docker + a browser are absent from the sandbox) and must be walked at 320/375/768 before UI-06 is signed off; a cell whose page (e.g. `/status`, plan 08-04) does not exist yet is recorded as unrun, not passed.
- Plan 08-04 is unblocked: it can consume `.health-system` and the `base.html` nav block.
- Verification remainder: `/gsd-ui-review 08` (the 6-pillar audit over the responsive surfaces, D-161).

---

*Phase: 08-operations-polish*
*Completed: 2026-10-14*

## Self-Check: PASSED

- All 11 named artefacts exist on disk (`docs/runbook-responsive-ui.md`, the stylesheet source and its build, the seven edited templates, and this SUMMARY).
- All three task commits exist: `2c575a7`, `343b247`, `4184f2d`.
- `pytest -q -m 'not live and not latex'` → 1805 passed, 15 deselected, 2 xfailed.
- `pytest -q tests/test_stylesheet_coverage.py tests/test_no_cdn.py` → 17 passed, byte-identity assertion executed (not skipped).
