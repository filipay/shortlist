---
status: testing
phase: 07-assisted-apply-tracker
source: [07-VERIFICATION.md]
started: 2026-10-12T15:45:00Z
updated: 2026-10-12T15:45:00Z
---

<!-- Presentation preference (user): every UAT checkpoint MUST be shown with exact, step-by-step instructions (setup + numbered actions + what to observe + how to reply). Never present the bare expected-behavior line alone. -->

## Current Test

[testing not started]

## Tests

### 1. Tracker layout re-run (G-07-5 + G-07-6)
expected: |
  Record an application with a ~300-character note and a next-action date; open `/applications`
  at 1280px and 375px; run the rendered-rect snippet from 07-11-PLAN Task 2 per row.
  Note wraps (no horizontal scrollbar); `intersects: false` for every row; `Update status`
  legible with no `dd/mm/yyyy` glyph band.
why_human: |
  Runtime layout — no layout engine in the repo. The mandated rendered-rect check was not
  performed (WINDOWS #9 open).
result: pending

### 2. Drafting round-trip + clipboard re-run (G-07-7, backstop)
expected: |
  Click `Draft answers` on a package whose provider wraps a list-typed field as `{"item": …}`;
  confirm four reviewable answers render, then click `Copy answer` and paste into a scratch
  field. The paste reproduces the full untruncated multi-paragraph answer.
why_human: |
  Depends on the live provider emission and the browser clipboard; the deterministic half is
  tested but not re-run live.
result: pending

### 3. MVP mode / goal-format (developer decision)
expected: |
  Either the `mvp` annotation is confirmed intentional (standard goal-backward verification, as
  performed here) or the developer runs `/gsd mvp-phase 7` to convert the goal.
why_human: Developer decision, not a code check.
result: pending

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps

No open gaps. The previous round's G-07-5, G-07-6 and G-07-7 were diagnosed and fixed by
07-11/07-12 and re-verified closed on 2026-10-12 (`07-VERIFICATION.md`, `status: human_needed`,
`score: 16/18`, `gaps: []`). Their diagnoses live in
`.planning/debug/DEBUG-tracker-notes-wrap-g07-5.md`,
`.planning/debug/DEBUG-tracker-control-overlap-g07-6.md` and
`.planning/debug/DEBUG-drafting-no-usable-answers-g07-7.md`, plus this file's prior revision in
git history.

Non-blocking carry-forward (not a gap): **WR-02** — `unwrap_single_key_mapping` bounds only the
direct self-reference, so a two-node mutual `{"item": …}` cycle loops while its docstring claims
self-reference "cannot hang". Not wire-reachable (JSON-derived payloads cannot be cyclic).
Recommended follow-up: visited-identity bound + honest prose (`/gsd-code-review 07 --fix`).
