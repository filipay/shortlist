---
status: testing
phase: 07-assisted-apply-tracker
source: [07-VERIFICATION.md, 07-REVIEW.md]
started: 2026-10-01T10:09:02Z
updated: 2026-10-01T10:09:02Z
---

## Current Test

number: 1
name: Tracker note-fidelity on a truncated note
expected: |
  Record enough applications that at least one carries a note long enough to be
  truncated in the tracker row. Inspect the truncated cell in the browser: the visible
  text is clipped, and the full note is recoverable from the element's `title` attribute
  (or an equivalent disclosure) — the note is not silently lost by the truncation.
  The plan declared a held-out test for this that was never shipped, so this is the
  only check that covers it.
awaiting: user response

## Tests

### 1. Tracker note-fidelity on a truncated note
expected: |
  Tracker row with a long note: the cell truncates visually AND exposes the full note
  via `title=""` (or an equivalent). Related: `format_datetime(None)` renders an em-dash
  and an empty note does not collapse the row (both are code-verified; this item is the
  human half — that truncation is legible and the full text is actually reachable).
result: [pending]

### 2. Clipboard multi-paragraph copy fidelity
expected: |
  On the apply package page, click `Copy answer` for a multi-paragraph drafted answer
  and paste into a plain-text target. Paragraph breaks survive; nothing is silently
  collapsed to one line. Clicking it flips the label to `Copied`; if the clipboard API
  is unavailable the label stays `Copy answer` rather than falsely claiming success.
  The plan declared a held-out test for this that was never shipped.
result: [pending]

### 3. Tracker visual scanning and no-JS degrade
expected: |
  Load `/applications` with a handful of applications across different stages. The
  stage badges are distinguishable at a glance, the applied / next-action / latest-note
  columns scan without squinting, and the page is usable with JavaScript disabled (the
  filter and pager are real forms and links, not JS-only controls).
result: [pending]

### 4. Ready-package perceived affordance
expected: |
  Open a listing with a verified `ok` CV. The five blocks read in a sensible order and
  the page makes it obvious (a) what to do next, (b) that the tool will not submit
  anything on the user's behalf, and (c) that the outbound link leaves the app. The
  verified-PDF preview is clearly the CV the application will use.
result: [pending]

### 5. Grounding residual policy adequacy
expected: |
  Read a drafted screening answer that was flagged `unsupported` or warned about. Decide
  whether the residual policy is honest and proportionate: the flag names the specific
  unsupported evidence id / novel number, and the advisory "fuzzy" band is presented as
  advisory — it must not read as a guarantee in either direction.
result: [pending]

### 6. `#apply-answers` region reads as designed
expected: |
  With the screening question list configured and drafts stored, the answers region shows
  one block per configured question in the saved order, each with its answer (or
  `Not yet drafted.`), evidence chips and any warning line. Adding a question, drafting,
  and deleting a single draft each visibly update only that region.
result: [pending]

### 7. Real compiled `ok` PDF in the Tectonic container
expected: |
  In an environment with the real LaTeX engine available (`docker compose run --rm app
  pytest -m latex`, or the running containerised app), generate and compile a tailored CV,
  then open its apply package page. The verified-PDF block renders and downloads a real
  PDF, and the page reports `ready` rather than gated. The hermetic suite stubs the
  engine, so this is the only leg that exercises it (07-VALIDATION manual-only item).
result: [pending]

### 8. 375px phone-width usability (UI-04)
expected: |
  At 375px wide, the tracker (filter row, table, pager) and the apply package page
  (blocks, gap checklist, answers region) remain usable: the table scrolls horizontally
  inside its own container instead of breaking the layout, and no control is clipped or
  unreachable.
result: [pending]

## Summary

total: 8
passed: 0
issues: 0
pending: 8
skipped: 0
blocked: 0

## Gaps

None open. 31 of 33 `must_haves` truths were verified against the live code; every one of
the seven phase requirement IDs (APPLY-01..APPLY-06, UI-04) is accounted for, and the
phase-scoped suite (180) and the full default lane (1650 passed, 14 deselected, 2 xfailed)
are green.

- The two abstained truths are both `verification: backstop` items whose plans named a
  held-out test that was never shipped — the truncated-note fidelity (test 1) and the
  multi-paragraph clipboard fidelity (test 2). They are covered by the human checks above
  rather than by code evidence. Adding the two held-out tests is the only code-side
  follow-up the verifier recommended.
- Caveat on the source artifact: `07-VERIFICATION.md` was written against the tree BEFORE
  the seven code-review findings were fixed (commits `106f11a`, `2661b5f`, `d88df6d`,
  `c627549`, `13bf409`, `bf7bd1f`, `a79c2fd`). None of the eight human checks above is
  invalidated by those fixes — they touch the POST action routes, the artefact-ownership
  check, the empty-response guard, the persisted question text, a helper rename and the
  draft-append path, none of which change the rendering or the flows these checks exercise.
