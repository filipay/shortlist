---
status: complete
phase: 05-ranking-core-value
source: [05-VERIFICATION.md]
started: 2026-09-22T17:37:33Z
updated: 2026-09-23T15:21:24Z
---

## Current Test

[testing complete]

## Tests

### 1. RANK-05 rationale prose quality (backstop)
expected: Open several ranked listings and read each stored rationale on the job detail page. Each reads as prose grounded in the listing's stated requirements and the CV evidence IDs actually returned — not a keyword restatement of the listing title.
result: pass

### 2. RANK-07 live-model stability tolerance
expected: Run the same listing through a live opencode backend twice and compare the stored `factor_scores_json`. Sub-scores agree to whatever tolerance the requirement intends (the stub-backed test proves the call shape is absolute — one listing per prompt; the live-model tolerance is a flagged, unclassified assumption).
result: pass

### 3. RANK-06 gap presentation
expected: Confirm a requirement the listing states but the CV has no evidence for is shown as a named gap with `evidence_id` null rather than omitted — it appears in the detail page's Requirement fit list with the `req-gap` class and no evidence id.
result: pass

### 4. UI-02 detail layout
expected: Review the two-part layout (factor table followed by requirement list) on a rendered job detail page. The grouping is legible and the right one for the fit breakdown.
result: pass

### 5. RANK-04 invalid-weight rejection presentation and UI-03 editor placement
expected: Submit an invalid weight and confirm where the editor lives. An invalid submission re-renders the settings page with an inline error (non-200) and writes nothing; the editor lives on the settings page alongside the criteria editor.
result: pass

### 6. RANK-08 refusal-audit semantics
expected: Decide whether a refused call should write an audit row at all, and record a deterministic, documented answer. The plan chose one refusal row per refused call with status=error and the cap name in the error text; the alternative (no row, rely on `runs.ranked_count`) remains a legitimate reading. Related to the open advisory on refusal-row spend accounting (05-REVIEW.md WR-04).
result: pass

## Summary

total: 6
passed: 6
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

<!-- G-05-1 (ranking observability) and G-05-2 (CV fact-store disclosure) were closed by
     the round-2 gap-closure plans 05-08, 05-09 and 05-10 and re-verified 2026-09-23
     (05-VERIFICATION.md: 42/42 observable truths verified, 0 gaps). No open gaps. -->

- gap_id: G-05-3
  truth: "The queue is navigable, not one-way: the user can move back to earlier listings after loading further ones, and the UI shows which page they are on and how many listings each page holds (UI-01 browse)."
  status: failed
  reason: "User reported: \"one usability issue is 'load more' loads more found jobs but then cannot go back to the previous jobs, we should have paginated responses and a ui way to show what page we're on and how many jobs per page\""
  severity: major
  test: null
  source: ad-hoc UAT finding, reported during test 2 (not a numbered checkpoint)
  requirement: UI-01
  artifacts: []
  missing: []

## Deferred Follow-Ups

- test: 1
  idea: "Surface visa / work-authorisation requirements when the job description states them (e.g. sponsorship availability, right-to-work). New signal, not a failure of the ranking rationale."
  deferred_at: 2026-09-23
- test: 4
  idea: "The Requirement fit list on the job detail page could be rendered as a table and would look/read better. Cosmetic legibility improvement only — user explicitly deferred it until after the core work is done."
  deferred_at: 2026-09-23
