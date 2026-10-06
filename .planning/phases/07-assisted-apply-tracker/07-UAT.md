---
status: partial
phase: 07-assisted-apply-tracker
source: [07-VERIFICATION.md]
started: 2026-10-06T21:16:59Z
updated: 2026-10-06T23:15:00Z
---

<!-- Presentation preference (user): every UAT checkpoint MUST be shown with exact, step-by-step instructions (setup + numbered actions + what to observe + how to reply). Never present the bare expected-behavior line alone. -->

## Current Test

[testing complete]

## Tests

### 1. Tracker note-fidelity (backstop truth, 07-04)
expected: |
  Open `/applications` and inspect a row whose note is longer than the cell; read the DOM
  `title` attribute. The note truncates to one line with an ellipsis and the complete
  untruncated string is present in `title=""`.
result: issue
reported: "I think the notes should wrap and scroll vertically rather than do a horizontal scroll, since actions are at the end of that table. Also \"Update Status\" has dd/mm/yyyy overlaying it, making it hard to read and press. I dont see it wrapping"
severity: major

### 2. Clipboard multi-paragraph copy fidelity (backstop truth, 07-05)
expected: |
  Open an apply package, draft or seed a multi-paragraph answer, click `Copy answer`, and
  paste into a scratch field. The paste equals the full untruncated multi-paragraph answer;
  the button label flips to `Copied` for ~2s (and stays `Copy answer` if the clipboard API
  is unavailable).
result: issue
reported: "The drafting call did not return a usable response. Your existing drafts were kept. So there is no answer i can copy for http://192.168.0.105:8000/listings/109/apply"
severity: major

### 3. MVP-mode / goal-format discrepancy (developer decision)
expected: |
  Either the `mvp` annotation is confirmed intentional (standard goal-backward verification,
  as performed here) or the developer runs `/gsd mvp-phase 7` to convert the goal before any
  User-Flow-Coverage report.
result: pass (2026-10-06) — the `mvp` annotation is confirmed intentional; standard goal-backward verification (as performed) is sufficient, no goal rewrite needed.

## Summary

total: 3
passed: 1
issues: 2
pending: 0
skipped: 0
blocked: 0

## Gaps

- gap_id: G-07-5
  truth: "The tracker Notes column is readable without horizontal scrolling; long notes wrap and the row's actions remain reachable."
  status: failed
  reason: "User reported: notes should wrap and scroll vertically rather than horizontal scroll, since actions are at the end of that table (and 'I dont see it wrapping')."
  severity: major
  test: 1
  root_cause: ""     # Filled by diagnosis
  artifacts: []      # Filled by diagnosis
  missing: []        # Filled by diagnosis
  debug_session: ""  # Filled by diagnosis

- gap_id: G-07-6
  truth: "The row's controls do not overlap: the 'Update status' button is legible and clickable, with no date field (dd/mm/yyyy) overlaid on it."
  status: failed
  reason: "User reported: 'Update Status' has dd/mm/yyyy overlaying it, making it hard to read and press."
  severity: major
  test: 1
  root_cause: ""     # Filled by diagnosis
  artifacts: []      # Filled by diagnosis
  missing: []        # Filled by diagnosis
  debug_session: ""  # Filled by diagnosis

- gap_id: G-07-7
  truth: "Clicking 'Draft answers' on an apply package returns usable drafted answers that the user can review and copy."
  status: failed
  reason: "User reported: 'The drafting call did not return a usable response. Your existing drafts were kept.' with no answer available to copy on /listings/109/apply."
  severity: major
  test: 2
  root_cause: |
    Likely source: the drafting model (minimax-m3 via opencode) intermittently returns a
    ScreeningDraftResponse whose `answers` value is a scalar (not list/object/null).
    ScreeningDraftResponse._coerce_answers (app/domain/schemas/screening.py:63) only tolerates
    None / a single Mapping / list / tuple, so a scalar passes through untouched and pydantic
    raises list_type ('Input should be a valid list'). draft_screening_answers then gets
    result.ok=false, returns None, and POST /listings/{id}/apply/draft maps it to 502
    drafting_failed with no rows written (drafts correctly preserved).
    Evidence (live DB data/jobsearch.db, table llm_calls): id 55 @2026-10-06T22:52:17Z
    status=invalid error='validation failed: Input should be a valid list' model=minimax-m3
    latency=41335ms; same failure ids 51,52 @2026-10-01; id 50 @2026-10-01 status=ok.
    The exact scalar shape was not captured (llm_calls stores no payload; privacy-by-design).
  artifacts:
    - path: "app/domain/schemas/screening.py"
      issue: "_coerce_answers tolerates None/Mapping/list/tuple but not a JSON-encoded string (scalar) shape for `answers`"
    - path: "app/pipeline/draft.py"
      issue: "returns None on a schema-invalid response; no invalid-payload shape is retained for diagnosis"
    - path: "app/api/apply.py"
      issue: "route maps the unusable response to 502 drafting_failed (graceful, correct) but the drafting defect leaves the user with no answer"
  missing:
    - "Reproduce one drafting call and capture the raw info.structured to confirm the exact invalid `answers` shape"
    - "Either tolerate the recorded scalar/string shape in _coerce_answers (e.g. parse a JSON-encoded string) or tighten the prompt/schema so the model reliably returns a list"
    - "Add a held-out test that fails on the current payload shape and passes after the fix"
  debug_session: ""
