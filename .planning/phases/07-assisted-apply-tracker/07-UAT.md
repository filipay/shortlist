---
status: testing
phase: 07-assisted-apply-tracker
source: [07-VERIFICATION.md]
started: 2026-10-06T21:16:59Z
updated: 2026-10-06T21:16:59Z
---

## Current Test

number: 1
name: Tracker note-fidelity (backstop truth, 07-04)
expected: |
  The note truncates to one line with an ellipsis and the complete untruncated string is present in `title=""`.
awaiting: user response

## Tests

### 1. Tracker note-fidelity (backstop truth, 07-04)
expected: |
  Open `/applications` and inspect a row whose note is longer than the cell; read the DOM
  `title` attribute. The note truncates to one line with an ellipsis and the complete
  untruncated string is present in `title=""`.
result: [pending]

### 2. Clipboard multi-paragraph copy fidelity (backstop truth, 07-05)
expected: |
  Open an apply package, draft or seed a multi-paragraph answer, click `Copy answer`, and
  paste into a scratch field. The paste equals the full untruncated multi-paragraph answer;
  the button label flips to `Copied` for ~2s (and stays `Copy answer` if the clipboard API
  is unavailable).
result: [pending]

### 3. MVP-mode / goal-format discrepancy (developer decision)
expected: |
  Either the `mvp` annotation is confirmed intentional (standard goal-backward verification,
  as performed here) or the developer runs `/gsd mvp-phase 7` to convert the goal before any
  User-Flow-Coverage report.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
