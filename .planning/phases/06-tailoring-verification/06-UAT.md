---
status: complete
phase: 06-tailoring-verification
source: [06-05-SUMMARY.md, 06-06-SUMMARY.md, 06-07-SUMMARY.md, 06-VERIFICATION.md, 06-REVIEW.md]
started: 2026-09-24T23:28:14Z
updated: 2026-10-14T13:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Real-engine tailored compile
expected: Generate + compile a tailored CV for a scored listing in an environment with Tectonic available (`.venv/bin/python -m pytest -m latex`, or `docker compose run --rm app pytest -m latex`, or the running app). A real PDF is produced and the persisted artifact carries a merged verification_json that passes. Layer-2 pypdf extraction is stubbed in the hermetic suite, so this is the only leg that exercises the real engine.
result: pass (2026-10-13) — `docker compose build` succeeded (477.5s; Tectonic 0.17.0 SHA256 verified, JobSpy pinned at `fda080a373e8226f3fd60635323f5da9af9892b1`, migrations 0001→0007 applied), then `docker compose run --rm app pytest -m latex -q` → **10 passed, 1714 deselected in 11.01s**. The real pinned Tectonic engine compiles and the real-engine verification path passes.

### 2. Fail-vs-warn legibility
expected: On the tailoring surface, a failing verification check is visually distinct from a warning, and the blocked state reads as a reviewable outcome with a clear recovery path rather than an opaque dead end.
result: pass (2026-10-14) — operator confirmed the blocked panel renders as specified against a seeded blocked artifact (listing 189, seed removed afterwards). The three rows were `pass` (green), `warn` (amber) and `fail` (red) — visibly distinct, confirmed against `.req-met/.req-partial/.req-gap` = `--color-success/--color-warning/--color-danger` in `static/vendor/app.css`. The panel names the ids and the offending values (`bullet-3`; `req-2`, `req-5`), states "The only recovery is to generate a fresh tailoring and review it again", offers no corrective control, and a blocked attempt carries no download link. Warns stayed non-blocking ("Warnings never block a download; only a failing check does.").

## Summary

total: 2
passed: 2
issues: 0
pending: 0
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
