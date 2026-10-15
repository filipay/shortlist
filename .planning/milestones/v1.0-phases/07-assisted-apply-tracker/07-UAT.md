---
status: diagnosed
phase: 07-assisted-apply-tracker
source: [07-VERIFICATION.md]
started: 2026-10-12T15:45:00Z
updated: 2026-10-12T16:30:00Z
audit_acknowledged:
  milestone: v1.0
  at: 2026-10-15
  gap_snapshot: "diagnosed::scenarios=0"
---

<!-- Presentation preference (user): every UAT checkpoint MUST be shown with exact, step-by-step instructions (setup + numbered actions + what to observe + how to reply). Never present the bare expected-behavior line alone. -->

## Current Test

[testing complete]

## Tests

### 1. Tracker layout re-run (G-07-5 + G-07-6)

expected: |
  Record an application with a ~300-character note and a next-action date; open `/applications`
  at 1280px and 375px; run the rendered-rect snippet from 07-11-PLAN Task 2 per row.
  Note wraps (no horizontal scrollbar); `intersects: false` for every row; `Update status`
  legible with no `dd/mm/yyyy` glyph band.
result: pass
reported: "pass" (2026-10-12) — G-07-5 and G-07-6 confirmed fixed in the live UI.

### 2. Drafting round-trip + clipboard re-run (G-07-7, backstop)

expected: |
  Click `Draft answers` on a package whose provider wraps a list-typed field as `{"item": …}`;
  confirm four reviewable answers render, then click `Copy answer` and paste into a scratch
  field. The paste reproduces the full untruncated multi-paragraph answer.
result: issue
reported: "The drafting call did not return a usable response. Your existing drafts were kept." (2026-10-12)
severity: major

### 3. MVP mode / goal-format (developer decision)

expected: |
  Either the `mvp` annotation is confirmed intentional (standard goal-backward verification, as
  performed here) or the developer runs `/gsd mvp-phase 7` to convert the goal.
result: pass (2026-10-12) — the `mvp` annotation is confirmed intentional; standard
  goal-backward verification (as performed) is sufficient, no goal rewrite needed.

## Summary

total: 3
passed: 2
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- gap_id: G-07-7
  truth: "Clicking 'Draft answers' on an apply package returns usable drafted answers that the user can review and copy."
  status: deferred
  reason: |
    Re-run failed on 2026-10-12 with the same refusal copy. The live provider is still emitting a
    list-typed field in a shape the coercion layer does not recognise, so `drafting_failed` is
    returned and no answers render. The deterministic unwrap is tested (07-06, 07-14); the live
    provider emission is not fully pinned.
  severity: major
  test: 2
  deferred_by: user decision (2026-10-12) — "I think at this point I want to just move on as we've iterated so many times"
  carry_forward: |
    Recorded as a known limitation in `.planning/phases/07-assisted-apply-tracker/deferred-items.md`
    and in `README.md` → Known limitations. Diagnoses: `.planning/debug/DEBUG-drafting-no-usable-answers-g07-7.md`.
    Fix path: capture the raw provider payload for a failing call, widen the key-restricted unwrap to
    the observed shape, add the literal payload as a fixture.

No other gaps. The previous round's G-07-5 and G-07-6 are closed and confirmed pass above.

Non-blocking carry-forward (not a gap): **WR-02** — `unwrap_single_key_mapping` bounds only the
direct self-reference, so a two-node mutual `{"item": …}` cycle loops while its docstring claims
self-reference "cannot hang". Not wire-reachable (JSON-derived payloads cannot be cyclic).
Recommended follow-up: visited-identity bound + honest prose (`/gsd-code-review 07 --fix`).
