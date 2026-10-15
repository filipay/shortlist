---
status: testing
phase: 08-operations-polish
source: [08-VERIFICATION.md]
started: 2026-10-14T22:28:03Z
updated: 2026-10-15T01:30:00Z
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
result: pass
reported: "okay looks good" (2026-10-15) — the operator re-walked the prune preview after the 08-06 fix and accepted it.
retest: the defect below is fixed by 08-06 (`2783c65`, `1df348a`); re-walk the preview and
  confirm a sane figure — and, if anything could not be measured, the `· N path(s) not measured`
  clause. A live re-walk is still unrun (WINDOWS #18).
reported: "This will delete 4 artifacts · 117043.0 GB." (2026-10-14) — the freed-size figure is
  impossible (~117 TB for four CVs; the whole `artifacts/` tree is 460 KB), so the preview
  misreports its own impact. `_human_size` is provably correct, so `size_bytes` ≈ 1.2567e14 must
  come from the only `st_size` site, `retention_repo._size_inside` (no `S_ISREG` gate, no
  plausibility bound). Also raised in the same walk: the panel never lists the four prunable
  categories, there is no all-categories action, and the `Kept regardless` guards cannot be
  overridden. Follow-ups recorded as todos: `2026-10-14-prune-preview-misreports-freed-size`,
  `2026-10-14-add-prune-all-action`, `2026-10-14-allow-explicit-prune-guard-override`.
severity: major

### 5. 13 judgment-tier prohibitions
expected: |
  Resolve the 13 judgment-tier prohibitions listed in the Prohibitions section of
  `08-VERIFICATION.md` — confirm none is violated in the shipped code.
why_human: judgment-tier; the LLM-judge verdict of "not violated" is recorded as
  NON-AUTHORITATIVE and needs explicit human resolution per item.
result: [pending]

## Summary

total: 5
passed: 1
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps

- gap_id: G-08-1
  truth: "The prune preview truthfully reports the disk space the deletion will free."
  status: resolved
  resolved_by: 08-06-PLAN.md
  resolved_at: 2026-10-15T01:00:00Z
  reason: |
    Observed `117043.0 GB` for four artifacts during the operator walk (2026-10-14). The
    formatter is correct; the only `st_size` site (`retention_repo._size_inside`) accepted any
    resolved path without an `S_ISREG` gate, so a directory or special file was summed and
    presented as a fact.
    Closed by 08-06: `_size_inside` now returns a size only for `stat.S_ISREG`, non-regular
    entries increment `missing_files` instead, the summary appends `· N path(s) not measured`
    whenever the total is partial, and a structlog trail names every not-measured path and
    reason. No plausibility cap was added (deliberate), so a bind mount reporting a bogus
    `st_size` for a genuinely regular file would still be summed — the DEBUG trail is the
    identifier. The post-fix live re-walk is unrun (WINDOWS #18).
