---
status: testing
phase: 05-ranking-core-value
source: [05-VERIFICATION.md]
started: 2026-09-22T17:37:33Z
updated: 2026-09-23T16:50:49Z
---

## Current Test

number: 7
name: G-05-3 closure in a browser — two-way paging
expected: |
  Boot the app against a real DB, load a multi-page queue, click Next then Previous.
  Each control swaps the page through `GET /queue/list`; the row set changes; the
  position line ("Page X of Y (N per page)") tracks the slice; backward navigation
  returns to the prior slice; the viewport lands somewhere readable.
awaiting: user confirmation

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

### 7. G-05-3 closure in a browser — two-way paging
expected: |
  Boot the app against a real DB, load a multi-page queue, click Next then Previous.
  Each control swaps the page through `GET /queue/list`; the row set changes; the
  position line ("Page X of Y (N per page)") tracks the slice; backward navigation
  returns to the prior slice; the viewport lands somewhere readable.
  Decision also required: the round-3 UI audit flags that the swaps carry no
  `show:top` (no scroll reset after a page swap) and that boundary controls are
  omitted rather than rendered-disabled — decide whether those need fixing.
result: pending

### 8. Detail-page action feedback (UI-02 surface)
expected: |
  Open a job detail, click Save and Hide, and decide whether the current
  no-feedback behaviour is acceptable. The event is appended server-side, but the
  on-page swap never happens because the forms target `#listing-row-{id}`, which the
  detail page never renders — htmx raises `targetError`. Record a deliberate
  fix-vs-accept decision.
result: pending

## Summary

total: 8
passed: 6
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps

<!-- G-05-1 (ranking observability) and G-05-2 (CV fact-store disclosure) were closed by
     the round-2 gap-closure plans 05-08, 05-09 and 05-10 and re-verified 2026-09-23. -->

- gap_id: G-05-3
  truth: "The queue is navigable, not one-way: the user can move back to earlier listings after loading further ones, and the UI shows which page they are on and how many listings each page holds (UI-01 browse)."
  status: closed
  reason: "User reported: \"one usability issue is 'load more' loads more found jobs but then cannot go back to the previous jobs, we should have paginated responses and a ui way to show what page we're on and how many jobs per page\""
  severity: major
  test: 7
  source: ad-hoc UAT finding, reported during test 2 (not a numbered checkpoint)
  requirement: UI-01
  closed_by: "05-11 (two-way pager) + b572f93 (WR-01 is_empty gate); code-verified 2026-09-23 in 05-VERIFICATION.md"
  note: "Closed in code: `QueuePage.has_prev/prev_offset/page_index/page_count` (queue_repo.py:283-301, 14-case tests/db/test_queue_page.py), the `#queue-pager` Previous / position / Next block in queue_list.html, zero `queue-load-more` matches anywhere, page size still server-fixed. Human in-browser confirmation is still outstanding — tracked as test 7 above."

## Deferred Follow-Ups

- test: 1
  idea: "Surface visa / work-authorisation requirements when the job description states them (e.g. sponsorship availability, right-to-work). New signal, not a failure of the ranking rationale."
  deferred_at: 2026-09-23
- test: 4
  idea: "The Requirement fit list on the job detail page could be rendered as a table and would look/read better. Cosmetic legibility improvement only — user explicitly deferred it until after the core work is done."
  deferred_at: 2026-09-23
