---
status: diagnosed
phase: 05-ranking-core-value
source: [05-VERIFICATION.md]
started: 2026-09-22T17:37:33Z
updated: 2026-09-24T09:44:06Z
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

### 7. G-05-3 closure in a browser — two-way paging
expected: |
  Boot the app against a real DB, load a multi-page queue, click Next then Previous.
  Each control swaps the page through `GET /queue/list`; the row set changes; the
  position line ("Page X of Y (N per page)") tracks the slice; backward navigation
  returns to the prior slice; the viewport lands somewhere readable.
  Decision also required: the round-3 UI audit flags that the swaps carry no
  `show:top` (no scroll reset after a page swap) and that boundary controls are
  omitted rather than rendered-disabled — decide whether those need fixing.
result: pass
note: "User: \"yup going back and forth works, pass\". The two embedded audit decisions were accepted as-is: no `show:top` scroll reset after a page swap, and boundary controls rendered-disabled-vs-omitted left at current behaviour."

### 8. Detail-page action feedback (UI-02 surface)
expected: |
  Open a job detail, click Save and Hide, and decide whether the current
  no-feedback behaviour is acceptable. The event is appended server-side, but the
  on-page swap never happens because the forms target `#listing-row-{id}`, which the
  detail page never renders — htmx raises `targetError`. Record a deliberate
  fix-vs-accept decision.
result: issue
reported: "Hmm there's no feedback, when i click save or hide nothing happens which makes it uninituative. Also where are the saved jobs going to ?"
severity: major

## Summary

total: 8
passed: 7
issues: 1
pending: 0
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

- gap_id: G-05-8
  truth: "Clicking Save or Hide on a job detail page gives visible confirmation, and saved jobs are discoverable somewhere in the UI — the controls are not silent no-ops."
  status: failed
  reason: "User reported: \"Hmm there's no feedback, when i click save or hide nothing happens which makes it uninituative. Also where are the saved jobs going to ?\""
  severity: major
  test: 8
  requirement: UI-02
  root_cause: |
    Two contributing causes. (1) No feedback: the detail page's Save/Hide forms set
    hx-target="#listing-row-{{ row.id }}" — an element rendered only by the queue row
    partial (_listing_row.html:30) and never by the detail template — so htmx raises
    targetError and never swaps; the POST still appends the event server-side and returns
    the row fragment with HTTP 200, so the button label only flips on manual reload.
    (2) Discoverability: a saved view exists only as an unlabelled `Saved` checkbox in the
    queue filter form; the detail page links to nothing, shows no saved count, and gives no
    post-save affordance pointing at it.
  artifacts:
    - path: "app/web/templates/html/listing_detail.html"
      issue: "Lines 103,114: forms target the queue-only #listing-row-{id} → htmx targetError, no swap, no feedback"
    - path: "app/web/templates/html/_listing_row.html"
      issue: "Line 30 defines <tr id=\"listing-row-{{ row.id }}\">; included only by queue_list.html:70-72, never by the detail page"
    - path: "app/api/events.py"
      issue: "Lines 76-156: write + row fragment on 200 are correct; no detail-surface target to swap into"
    - path: "app/web/templates/html/queue.html"
      issue: "Lines 86-97: the only discoverable saved view (Saved filter via routes.py:148 / queue_repo.py:509-510), unreferenced from the detail page"
    - path: "tests/api/test_listing_detail.py"
      issue: "No assertion on the detail action forms/target; tests/api/test_listing_events.py:95-130 only tests the server POST response — why it shipped"
  missing:
    - "Give the detail page a real swap target (detail-specific fragment, or point hx-target at #detail-actions/the button) so Save/Hide re-render in place with visible feedback"
    - "Add a discoverability affordance on the detail page: link/hint to the queue's Saved filter and/or a saved indicator or count"
    - "Add a regression test asserting the detail forms' target resolves within the rendered detail markup, plus a test for the saved affordance"
    - "Decide the interaction posture deliberately (inline swap vs documented reload) rather than leaving the deferred-load behaviour"
  debug_session: .planning/debug/uat-05-detail-action-feedback.md

## Deferred Follow-Ups

- test: 1
  idea: "Surface visa / work-authorisation requirements when the job description states them (e.g. sponsorship availability, right-to-work). New signal, not a failure of the ranking rationale."
  deferred_at: 2026-09-23
- test: 4
  idea: "The Requirement fit list on the job detail page could be rendered as a table and would look/read better. Cosmetic legibility improvement only — user explicitly deferred it until after the core work is done."
  deferred_at: 2026-09-23
