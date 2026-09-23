---
status: diagnosed
phase: 05-ranking-core-value
source: [05-VERIFICATION.md]
started: 2026-09-22T17:37:33Z
updated: 2026-09-23T15:25:20Z
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
  status: diagnosed
  reason: "User reported: \"one usability issue is 'load more' loads more found jobs but then cannot go back to the previous jobs, we should have paginated responses and a ui way to show what page we're on and how many jobs per page\""
  severity: major
  test: null
  source: ad-hoc UAT finding, reported during test 2 (not a numbered checkpoint)
  requirement: UI-01
  root_cause: "The queue's paging affordance is forward-only and stateless in the DOM. The \"Load more\" button performs an `hx-swap=\"innerHTML\"` replacement of `#queue-list` with a fragment containing only the next offset's rows, so it destroys the rows already on screen instead of appending — the label promises append, the behaviour is \"go to next page\". No previous/back control exists anywhere, and no `hx-push-url`/`hx-history`/`hx-boost` is present, so browser history cannot restore a prior offset either; offset only ever increases from that one button. Compounding this, the UI renders only the grand total (`page.total`) as `N listings` and never the current offset, page size, page index, or page count, so the user cannot tell which slice they are viewing or how many rows a page holds. `QueuePage` already exposes everything needed to derive prev/next and a position indicator — only rendering is missing. Design intent drift: 02-RESEARCH.md:672 says Load more \"appends the next page's rows into `#queue-list`\"; the implementation uses innerHTML replace."
  debug_session: .planning/debug/queue-pagination-load-more.md
  artifacts:
    - path: app/web/templates/html/queue_list.html
      issue: "Lines 79-85 — Load-more control does `hx-get=\"/queue/list?...offset=page.next_offset\"` with `hx-target=\"#queue-list\"` and `hx-swap=\"innerHTML\"`; the replace discards already-rendered rows. Line 17 renders only `{{ count }} listings` (grand total), no position indicator."
    - path: app/web/templates/html/queue.html
      issue: "Lines 39-167 — filter/sort/threshold controls emit no offset (all reset to 0); no prev/back control and no page indicator markup; no htmx history (`hx-push-url`/`hx-history`/`hx-boost` absent), so browser Back cannot restore an earlier offset."
    - path: app/db/repositories/queue_repo.py
      issue: "Lines 262-277 — `QueuePage` carries rows/total/offset/limit/has_more/query + next_offset; no `has_prev`/`prev_offset`/`page_index`/`page_count`. All derivable from existing fields but not exposed."
    - path: app/web/routes.py
      issue: "Lines 132-154 — `parse_queue_query` fixes `limit` from `settings.queue_page_size` and never reads it from the request (T-02-28); offset clamped at 0. Line 168 passes `count=page.total` (grand total) to the template."
    - path: app/config.py
      issue: "Line 127 — `queue_page_size: int = 25`; the page size is server-fixed and never surfaced in the UI."
    - path: tests/api/test_queue_excluded.py
      issue: "Lines 257-278 — currently pins the forward-only behaviour (Load-more link carries `offset=4`, predicate changes carry no offset). Must be updated by any fix."
  missing:
    - "A previous/back control (or htmx history integration) — nothing can currently return to an earlier offset."
    - "Any page-position display: page index, page count, page size, or \"showing X-Y of N\" — only the grand total is rendered."
    - "Derived `QueuePage` accessors for backward navigation (`has_prev`/`prev_offset`) and position (`page_index`/`page_count`)."
    - "A swap strategy that preserves already-rendered rows (append/`beforeend`) or an explicit page model — the current `innerHTML` replace is the mechanism that discards them."

## Deferred Follow-Ups

- test: 1
  idea: "Surface visa / work-authorisation requirements when the job description states them (e.g. sponsorship availability, right-to-work). New signal, not a failure of the ranking rationale."
  deferred_at: 2026-09-23
- test: 4
  idea: "The Requirement fit list on the job detail page could be rendered as a table and would look/read better. Cosmetic legibility improvement only — user explicitly deferred it until after the core work is done."
  deferred_at: 2026-09-23
