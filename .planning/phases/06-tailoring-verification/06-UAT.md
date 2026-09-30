---
status: testing
phase: 06-tailoring-verification
source: [06-05-SUMMARY.md, 06-06-SUMMARY.md, 06-07-SUMMARY.md, 06-VERIFICATION.md, 06-REVIEW.md]
started: 2026-09-24T23:28:14Z
updated: 2026-09-30T12:02:22Z
---

## Current Test

number: 1
name: Real-engine tailored compile
expected: |
  With the real LaTeX engine available (Tectonic), generate and compile a tailored CV
  for a scored listing. A real PDF is produced and the persisted cv_artifacts row carries
  a merged, passing verification_json written by the real engine extractor.
awaiting: user response

## Tests

### 1. Real-engine tailored compile
expected: Generate + compile a tailored CV for a scored listing in an environment with Tectonic available (`.venv/bin/python -m pytest -m latex`, or `docker compose run --rm app pytest -m latex`, or the running app). A real PDF is produced and the persisted artifact carries a merged verification_json that passes. Layer-2 pypdf extraction is stubbed in the hermetic suite, so this is the only leg that exercises the real engine.
result: [pending]

### 2. Fail-vs-warn legibility
expected: On the tailoring surface, a failing verification check is visually distinct from a warning, and the blocked state reads as a reviewable outcome with a clear recovery path rather than an opaque dead end.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps

None open. The three findings previously recorded here are all closed and independently
re-verified; only the two container-only Tectonic UAT items above remain (no LaTeX engine
in this environment by design, D-69).

- CR-01 (blocker) — a digit-bearing entry location hard-failed `metric_containment`.
  Closed by 06-08: the entry location digit core joins the region's allowed set (the
  digit stays a candidate and is grounded by membership). `VERIFIER_VERSION` 1.0.2.
- CR-02 (major) — substring org anchoring let an earlier entry's bullet bleed digits
  into a later entry's region. Closed by 06-08 (anchor requires org AND title) and
  tightened by 06-10 (org-first + date adjacency), 06-11 (org-first + region-end bound)
  and round 5 (`da06178`: the org/title separator is now required, with `_dash_fold` so
  `-`/`--`/`---`/en-dash/em-dash all satisfy). `VERIFIER_VERSION` 1.0.5.
- WR-01 (minor) — a raised `complete_structured` transport error skipped the
  `llm_calls` audit row and surfaced as a bare 500. Closed by 06-09: exactly one
  `llm_calls` row is written and the generate route returns a typed 502
  `tailoring_failed` refusal.
