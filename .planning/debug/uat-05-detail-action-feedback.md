---
status: diagnosed
trigger: "uat-05-detail-action-feedback — Save and Hide controls on the phase-05 ranked-job detail page produce no visible feedback; user also cannot find where saved jobs go"
created: 2026-09-24T00:00:00Z
updated: 2026-09-24T00:00:00Z
---

## Current Focus
<!-- OVERWRITE on each update - reflects NOW -->

hypothesis: CONFIRMED — two contributing causes: (1) the detail page's Save/Hide forms carry the queue-row htmx target `#listing-row-{id}`, which the detail page never renders, so htmx raises targetError and no swap/feedback occurs; (2) saved jobs are reachable only via the queue's unlabelled-as-a-view "Saved" checkbox filter, with no link or hint from the detail page where Save is clicked.
test: DONE — read detail template, row partial, queue/queue_list templates, events + listings routes, queue_repo, tests.
expecting: Confirmed.
next_action: "Diagnose-only mode — return ROOT CAUSE FOUND. No fix applied."

## Symptoms
<!-- Written during gathering, then IMMUTABLE -->

expected: Open a job detail, click Save and Hide, and decide whether the current no-feedback behaviour is acceptable. The event is appended server-side, but the on-page swap never happens because the forms target `#listing-row-{id}`, which the detail page never renders — htmx raises `targetError`. Record a deliberate fix-vs-accept decision.
actual: "Hmm there's no feedback, when i click save or hide nothing happens which makes it uninituative. Also where are the saved jobs going to ?"
errors: User reported no visible error; the UAT prefill records htmx `targetError` on the Save/Hide forms (target `#listing-row-{id}` is not rendered on the detail page).
reproduction: Test 8 in UAT — boot the app, open a job detail, click Save, then click Hide.
started: Discovered during UAT

## Eliminated
<!-- APPEND only - prevents re-investigating -->

- hypothesis: "The POST fails or is rejected, so no event is persisted."
  evidence: "app/api/events.py:114-121 appends the event and commits; :148-156 returns the row fragment. tests/api/test_listing_events.py:100-109 posts directly and asserts the event is written and the row comes back. The write path is healthy — the failure is purely client-side target resolution."
  timestamp: 2026-09-24T00:00:00Z

- hypothesis: "Saved state is not persisted or not distinguishable anywhere."
  evidence: "event_repo projects saved/hidden into the row (queue_repo.py:673,735-736); _listing_row.html:39 renders a `badge-saved` and the button flips to Unsave. Saved state is real and visible on the queue."
  timestamp: 2026-09-24T00:00:00Z

## Evidence
<!-- APPEND only - facts discovered -->

- timestamp: 2026-09-24T00:00:00Z
  checked: "app/web/templates/html/listing_detail.html:94-123 (the #detail-actions block)"
  found: "Both forms declare hx-target=\"#listing-row-{{ row.id }}\" with hx-swap=\"outerHTML\" (lines 103 and 114). The detail page renders NO element with id `listing-row-{id}` — its only action anchor is `<section id=\"detail-actions\">` (line 94)."
  implication: "htmx will resolve no target and raise `htmx:targetError`; the on-page swap never runs even though the POST is sent."

- timestamp: 2026-09-24T00:00:00Z
  checked: "app/web/templates/html/_listing_row.html:30 and queue_list.html:70-72"
  found: "`<tr id=\"listing-row-{{ row.id }}\">` is defined ONLY in `_listing_row.html`, which is included by `queue_list.html` (the queue page). The detail template never includes it."
  implication: "The target id exists solely on the queue surface. Copying the queue row's action block verbatim onto the detail page carried a target that does not exist there."

- timestamp: 2026-09-24T00:00:00Z
  checked: "app/web/templates/html/listing_detail.html:96-99 (template comment) vs actual behaviour"
  found: "The comment states the POST 'still appends the event and the page reflects the new state on reload (Phase 5's documented posture, D-88)' — but it also asserts 'The htmx swap target is the queue row's id, which lives on the queue page.' The template already reads row.saved/row.hidden (:105,109,116,120), so a manual reload WOULD flip the button to Unsave/Unhide."
  implication: "The 'no feedback' is not a deliberate reload-only design — it is a broken htmx target. Feedback exists but only after a manual refresh the user was never told to perform."

- timestamp: 2026-09-24T00:00:00Z
  checked: "app/api/events.py:76-156 (POST /listings/{listing_id}/events)"
  found: "Validates event_type, appends via event_repo.append_event, commits, re-reads the row, and returns `_listing_row.html` (a <tr> fragment) with status 200. Server side is correct and complete."
  implication: "The event is persisted; the server response is fine. The failure is exactly the missing client-side target."

- timestamp: 2026-09-24T00:00:00Z
  checked: "app/web/templates/html/queue.html:86-97 (saved filter) and app/web/routes.py:146-154"
  found: "A `Saved` checkbox (`#queue-toggle-saved`, name=\"saved\") exists in the queue filter form; `parse_queue_query` reads `saved` into QueueQuery, and queue_repo.py:509-510 applies `saved_predicate()`. So a saved-jobs view DOES exist as a queue filter."
  implication: "Saved jobs are technically discoverable — but only by ticking an unlabelled-as-a-view checkbox on the queue page. The detail page (where Save is clicked) links to nothing, shows no saved count, and gives no hint."

- timestamp: 2026-09-24T00:00:00Z
  checked: "base.html:9 htmx presence; tests/api/test_listing_detail.py (whole file); tests/api/test_listing_events.py:95-130"
  found: "htmx is loaded. test_listing_detail.py exercises the score/breakdown/unscored/escaping/404 paths but NEVER asserts the action forms or their hx-target. test_listing_events.py asserts the POST response contains the row (server behaviour), not that a client can swap into it from the detail page."
  implication: "No automated gate covers the detail page's action target — the mismatch shipped undetected. This is the 'why not caught' answer: a gap in the detail-page test, not a failing existing gate."

## Resolution
<!-- OVERWRITE as understanding evolves -->

root_cause: "Two contributing causes. (1) FEEDBACK: the job detail page's Save and Hide forms (app/web/templates/html/listing_detail.html:101-104 and :112-115) set hx-target=\"#listing-row-{row.id}\", an element rendered only by the queue row partial (app/web/templates/html/_listing_row.html:30). The detail page renders no such element, so htmx cannot resolve the target and raises htmx:targetError; the POST still reaches app/api/events.py, appends the event and returns the row fragment, but the fragment is never swapped in, so the page shows no change. The button's own label/state would only update on a manual reload. (2) DISCOVERABILITY: saved jobs are reachable only via the queue page's `Saved` checkbox filter (app/web/templates/html/queue.html:86-97, wired through routes.py:148 and queue_repo.py:509-510); the detail page offers no link, hint, count or post-save affordance pointing at it, so a user who just clicked Save has no path to find them."
fix:
verification:
files_changed: []
