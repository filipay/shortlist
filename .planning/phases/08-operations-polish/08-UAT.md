---
status: testing
phase: 08-operations-polish
source: [08-VERIFICATION.md]
started: 2026-10-14T22:28:03Z
updated: 2026-10-14T22:28:03Z
---

<!-- Presentation preference (user): every UAT checkpoint MUST be shown with exact, step-by-step instructions (setup + numbered actions + what to observe + how to reply). Never present the bare expected-behavior line alone. -->

## Current Test

number: 1
name: Operator responsive walk (320/375/768 px)
expected: |
  Card reflow below the breakpoint; admin tables inside labelled keyboard-reachable scroll
  regions at/above it; 44px tap floor holds; no horizontal scroll.
awaiting: user response

## Tests

### 1. Operator responsive walk (320/375/768 px)
expected: |
  Run the full operator responsive walk (`docs/runbook-responsive-ui.md`) at 320/375/768 px
  across the queue, listing detail, `/status`, the run control and `/applications`.
  Card reflow below the breakpoint; admin tables inside labelled keyboard-reachable scroll
  regions at/above it; 44px tap floor holds; no horizontal scroll.
why_human: rendered-pixel claim — no browser and no Docker in the executor sandbox (WINDOWS #15).
result: [pending]

### 2. Docker build tz proof
expected: |
  `docker compose build` — the Dockerfile's build-time `ZoneInfo('Europe/Dublin')` assertion
  runs and passes. Build succeeds (tzdata is the documented remedy if it fails).
why_human: Docker absent from the executor sandbox (WINDOWS #14).
result: [pending]

### 3. PLAT-06 compose-restart persistence (operator half)
expected: |
  Set a daily time, run `docker compose restart`, confirm the schedule survives and exactly one
  run with `trigger='schedule'` fires — never two, never an overlap.
why_human: the hermetic test proves the persisted job survives a fresh scheduler with a past-due
  fire time; the `docker compose restart` path itself is operator-only (WINDOWS #16).
result: [pending]

### 4. Prune history browser walk
expected: |
  Walk the Prune history control once per category: pick a category and an age, read the preview
  counts and the protected line, confirm, then verify the audit banner. The preview matches the
  delete; the audit line names the category/age/count; no protected row is removed.
why_human: Docker and a browser are absent; automated coverage exists (`test_retention_repo.py`,
  `test_settings_prune.py`) but the rendered walk is unrun (WINDOWS #17).
result: [pending]

### 5. 13 judgment-tier prohibitions
expected: |
  Resolve the 13 judgment-tier prohibitions listed in the Prohibitions section of
  `08-VERIFICATION.md` — confirm none is violated in the shipped code.
why_human: judgment-tier; the LLM-judge verdict of "not violated" is recorded as
  NON-AUTHORITATIVE and needs explicit human resolution per item.
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps

none yet — no test has been run.
