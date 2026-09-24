---
status: testing
phase: 06-tailoring-verification
source: [06-05-SUMMARY.md, 06-06-SUMMARY.md, 06-07-SUMMARY.md, 06-VERIFICATION.md, 06-REVIEW.md]
started: 2026-09-24T23:28:14Z
updated: 2026-09-24T23:28:14Z
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

- truth: "A tailored CV whose rendered region contains a digit-bearing entry location (eg Dublin 2, Eircode D02 X285, a US/UK postal code, Remote (GMT+1)) verifies and is previewable/downloadable."
  status: failed
  reason: "Code review CR-01 (critical), independently reproduced by the orchestrator. `_allowed_for_entry` (app/verify/numbers.py:143-152) enumerates the entry's dates, org, title and bullet text/metrics but NOT entry.location, while the LaTeX template renders entry.location inside that entry's own region (app/latex/templates/cv.tex.jinja:59-60). Any digit in the location therefore becomes a surplus candidate and check 4 `metric_containment` HARD FAILS. The D-118 recovery path (fresh tailor) re-runs the same predicate, so preview/download is dead for an entirely ordinary CV shape."
  severity: blocker
  source: 06-REVIEW.md CR-01
  requirement: TAIL-04
  root_cause: "_allowed_for_entry omits entry.location; RenderedEntry.location (app/domain/cv.py:347-355) is never folded into the region allowed set, while region_token_report (app/verify/numbers.py:203-256) computes allowed = _allowed_for_entry(entry) | structured_cores against a region whose extracted text includes the location line."
  artifacts:
    - path: "app/verify/numbers.py"
      issue: "Lines 143-152: _allowed_for_entry does not include entry.location cores; no fixture or test covers a digit-bearing location (grep of tests/verify and app/verify returns nothing)"
    - path: "app/latex/templates/cv.tex.jinja"
      issue: "Lines 59-60: renders entry.location into the region the check scopes to"
  missing:
    - "Fold entry.location digit cores into the region allowed set in _allowed_for_entry"
    - "Add a regression fixture + test with a digit-bearing location that must PASS metric_containment"
    - "Bump VERIFIER_VERSION (currently 1.0.1, app/verify/base.py:22)"
  debug_session: ""

- truth: "Each experience region is anchored to its own header, so an earlier entry's bullets can never contribute digits to a later entry's region."
  status: failed
  reason: "Code review CR-02 (critical). `_entry_lines` (app/verify/numbers.py:120-140) anchors a region to any line merely CONTAINING squash(entry.org) as a substring (if needle in squashed_lines[index]), with the cursor advancing past the match. A later entry's employer named inside an earlier entry's bullet mis-locates the later region and pulls the earlier bullets' digits in, producing a hard fail. Reproduced with regions [(exp/acme-2018, []), (exp/acme-2019, [5])] -> fail [exp/acme-2019:5]. Misfires on short or common org names."
  severity: major
  source: 06-REVIEW.md CR-02
  requirement: TAIL-04
  root_cause: "Substring-based org anchoring in _entry_lines instead of anchoring on the actual entry header line."
  artifacts:
    - path: "app/verify/numbers.py"
      issue: "Lines 120-140: `needle in squashed_lines[index]` matches a bullet that mentions another entry's org"
  missing:
    - "Anchor each region on the entry header line (a line that is primarily the org/date) rather than a bare substring match"
    - "Add a regression fixture with a bullet naming a later employer and assert no cross-region digit bleed"
    - "Bump VERIFIER_VERSION"
  debug_session: ""

- truth: "Every LLM call attempted through the tailoring generate path records exactly one llm_calls row, and a backend failure surfaces as a typed error rather than a 500."
  status: failed
  reason: "Code review WR-01 (warning). A raised complete_structured exception (app/pipeline/tailor.py:217-242) skips the promised one-per-call llm_calls row and escapes the generate route (app/api/tailoring.py:370-384) as an unhandled 500."
  severity: minor
  source: 06-REVIEW.md WR-01
  requirement: TAIL-02
  root_cause: "The audit row is written on the success path only; the exception path returns early without recording or translating the failure."
  artifacts:
    - path: "app/pipeline/tailor.py"
      issue: "Lines 217-242: exception path skips the llm_calls row"
    - path: "app/api/tailoring.py"
      issue: "Lines 370-384: unhandled exception becomes a 500"
  missing:
    - "Record one llm_calls row per attempted call even when complete_structured raises"
    - "Translate the backend failure into a typed error response instead of a 500"
  debug_session: ""
