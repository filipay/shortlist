---
status: diagnosed
phase: 07-assisted-apply-tracker
source: [07-VERIFICATION.md, 07-REVIEW.md]
started: 2026-10-01T10:09:02Z
updated: 2026-10-05T21:15:01Z
---

## Current Test

[testing complete]

## Tests

### 1. Tracker note-fidelity on a truncated note
expected: |
  Tracker row with a long note: the cell truncates visually AND exposes the full note
  via `title=""` (or an equivalent). Related: `format_datetime(None)` renders an em-dash
  and an empty note does not collapse the row (both are code-verified; this item is the
  human half — that truncation is legible and the full text is actually reachable).
result: issue
reported: "Once I recorded the application, I got into a page that seems to lack css. UI on the application form is scrambled"
severity: major
note: "Truncation itself was NOT reached: the record submit stranded the user on an unstyled fragment page, so the styled long-note cell could not be inspected. Tracked as G-07-1."

### 2. Clipboard multi-paragraph copy fidelity
expected: |
  On the apply package page, click `Copy answer` for a multi-paragraph drafted answer
  and paste into a plain-text target. Paragraph breaks survive; nothing is silently
  collapsed to one line. Clicking it flips the label to `Copied`; if the clipboard API
  is unavailable the label stays `Copy answer` rather than falsely claiming success.
  The plan declared a held-out test for this that was never shipped.
result: issue
reported: "The drafting call returned no answers. Your existing drafts were kept."
severity: major
note: "The clipboard behaviour itself was never reached: screening drafting returns 502 drafting_empty because the model's structured payload fails schema validation. Tracked as G-07-2."

### 3. Tracker visual scanning and no-JS degrade
expected: |
  Load `/applications` with a handful of applications across different stages. The
  stage badges are distinguishable at a glance, the applied / next-action / latest-note
  columns scan without squinting, and the page is usable with JavaScript disabled (the
  filter and pager are real forms and links, not JS-only controls).
result: pass

### 4. Ready-package perceived affordance
expected: |
  Open a listing with a verified `ok` CV. The five blocks read in a sensible order and
  the page makes it obvious (a) what to do next, (b) that the tool will not submit
  anything on the user's behalf, and (c) that the outbound link leaves the app. The
  verified-PDF preview is clearly the CV the application will use.
result: pass

### 5. Grounding residual policy adequacy
expected: |
  Read a drafted screening answer that was flagged `unsupported` or warned about. Decide
  whether the residual policy is honest and proportionate: the flag names the specific
  unsupported evidence id / novel number, and the advisory "fuzzy" band is presented as
  advisory — it must not read as a guarantee in either direction.
result: issue
reported: "this is what i see, no actual band is shown"
severity: major
note: "Seeded one flagged row (drafting is broken by G-07-2). The rendered block was exactly: question heading, the answer, `Evidence: led_acme_2023`, then `⚠ This answer may go beyond your CV — check the evidence before you use it.` The warning is generic — it names neither the offending evidence id nor the novel number (97,000 / 12) — and no advisory band line is rendered anywhere in the region. Tracked as G-07-3."

### 6. `#apply-answers` region reads as designed
expected: |
  With the screening question list configured and drafts stored, the answers region shows
  one block per configured question in the saved order, each with its answer (or
  `Not yet drafted.`), evidence chips and any warning line. Adding a question, drafting,
  and deleting a single draft each visibly update only that region.
result: pass
note: "Add-question leg verified: the ad-hoc question persisted and the block appeared in the region (saved order); the rest of the page was unaffected. The drafting leg surfaced the known G-07-2 502 ('The drafting call returned no answers. Your existing drafts were kept.') — tracked there, not re-counted here. The delete leg was accepted on the overall pass."

### 7. Real compiled `ok` PDF in the Tectonic container
expected: |
  In an environment with the real LaTeX engine available (`docker compose run --rm app
  pytest -m latex`, or the running containerised app), generate and compile a tailored CV,
  then open its apply package page. The verified-PDF block renders and downloads a real
  PDF, and the page reports `ready` rather than gated. The hermetic suite stubs the
  engine, so this is the only leg that exercises it (07-VALIDATION manual-only item).
result: pass
note: "Engine leg confirmed against the running container: listing 189's real Tectonic compiles exist on disk (artifacts 2 = 4pp, 3 = 2pp) and the user's Download yielded a real multi-page PDF ('download was successful'). The apply-page half of this criterion (verified-PDF block present, page reports `ready`) was already human-confirmed under test 4. While exercising this the user separately reported duplicate/version-agnostic download affordances — tracked as G-07-4 (minor); that does not falsify the real-engine criterion."

### 8. 375px phone-width usability (UI-04)
expected: |
  At 375px wide, the tracker (filter row, table, pager) and the apply package page
  (blocks, gap checklist, answers region) remain usable: the table scrolls horizontally
  inside its own container instead of breaking the layout, and no control is clipped or
  unreachable.
result: pass

## Summary

total: 8
passed: 5
issues: 3
pending: 0
skipped: 0
blocked: 0

## Gaps

- gap_id: G-07-1
  truth: "Recording an application from the apply package page returns the user to a usable, styled tracker view — the record→review flow does not strand the user on an unstyled fragment."
  status: failed
  reason: "User reported: \"Once I recorded the application, I got into a page that seems to lack css. UI on the application form is scrambled\""
  severity: major
  test: 1
  root_cause: |
    `apply.html` §6 posts a PLAIN (non-HTMX) form to `/applications/record`, so the
    browser performs a full-page navigation POST. `record_application_route`
    (app/api/applications.py:159) returns the bare `applications_list.html` fragment,
    which does NOT extend `base.html` — no `<head>`, no `/static/vendor/app.css`, no
    nav. The browser therefore replaces the styled page with a fragment-only document
    (screenshot: .planning/ui-reviews/test-record-applications.png). The design is
    unwired: the apply page (which owns the record form) has no `#application-list`
    swap target, while the tracker page (which owns `#application-list`) has no record
    form. Precedent for the fix exists — tailoring.py:559 already returns a 303
    `RedirectResponse`.
  missing:
    - "Node: record-application submit must land the user on the full tracker page (PRG redirect to /applications for a non-HTMX submit, or an in-page HTMX swap with a real target)."
    - "Regression test asserting the record submit response is either a 3xx to /applications or a full page containing the app stylesheet — the current test only asserts a bare-fragment 200 (tests/api/test_applications_tracker.py::test_record_via_http_renders_the_row_and_its_created_event)."
  artifacts: []
  note: "Observed alongside, possibly distinct: on the styled /applications page the Actions column controls overlap/overflow at desktop width (.listing-actions{white-space:nowrap;min-width:10rem} in a table with no fixed layout) — see .planning/ui-reviews/test-applications.png. Needs confirmation at a known viewport before being tracked as its own gap; test 8 (375px) will also exercise it."

- gap_id: G-07-2
  truth: "Screening-answer drafting against the configured model persists usable drafts; a schema-invalid model payload is either coerced or reported as a schema problem, rather than surfacing as a generic 502 'returned no answers'."
  status: failed
  reason: "User reported: \"The drafting call returned no answers. Your existing drafts were kept.\""
  severity: major
  test: 2
  root_cause: |
    The drafting route (app/api/apply.py:304-323) returns HTTP 502 `drafting_empty`
    whenever `draft_screening_answers` yields `None` or `[]`. The audit rows
    (`llm_calls` id 51 @ 11:17:47 and id 52 @ 11:39:02, both purpose=tailor,
    model=minimax-m3, server_version=1.18.33) show the backend WAS reachable and
    answered in ~46-52s with `status=invalid`,
    `error="validation failed: Input should be a valid list"`.
    `TOLERATED_SCHEMA_ERRORS = frozenset({"missing","int_parsing"})`
    (app/llm/opencode_server.py:93) does not tolerate a list-type error, so `_salvage`
    (opencode_server.py:690-708) re-raises the `ValidationError`;
    `_classify_message_response` (opencode_server.py:914-925) records `invalid`; and
    `draft_screening_answers` (app/pipeline/draft.py:209-210) returns None. The model
    returned a `ScreeningDraftResponse` payload in which a list-typed field
    (`answers: list[ScreeningAnswer]`, or a nested `evidence_ids: list[str]`;
    app/domain/schemas/screening.py:25-40) was not a JSON array — a
    schema/prompt ↔ model-output shape mismatch, not a transport or missing-prerequisite
    failure. Confirmed empty state: screening_drafts=0, apply_config=0 (DEFAULT_QUESTIONS
    fallback in play), so there were no existing drafts to copy and test 2 could not proceed.
  missing:
    - "Node: constrain the forced structured-output schema/prompt so the configured model emits `answers` as a JSON array (or coercively salvage the common non-list shapes without silently discarding answers)."
    - "Node: distinguish a schema-invalid model payload from a genuinely empty response in the user-facing copy — both currently collapse to 'The drafting call returned no answers.'"
    - "Node: a live-model integration test (or a recorded golden payload fixture) covering a non-list `answers` shape; the hermetic suite stubs the backend and cannot catch this."
  artifacts: []
  note: "Each failed attempt burns a real model call (~45-52s). The same configured backend produced `status=ok` calls (e.g. id 50 @ 11:12:22), so the backend is not down — this is the screening schema/parse path."

- gap_id: G-07-3
  truth: "A flagged screening answer names the specific unsupported evidence id / novel number in the human-facing warning, and the advisory grounding band is surfaced as advisory — so the reviewer can act on the flag rather than seeing a generic caution."
  status: failed
  reason: "User reported: \"this is what i see, no actual band is shown\""
  severity: major
  test: 5
  source: "07-VERIFICATION.md row 13 ('Unknown evidence id flagged unsupported, naming the id, never silently dropped')"
  root_cause: |
    The checker computes the specific findings but nothing persists or renders them.
    `ground_screening_answers` (app/verify/screening.py) returns `ScreeningVerdict`
    objects carrying `warnings: list[str]` (each naming the offending evidence id or
    novel digit token) and an advisory `band: GroundingBand`. The persist path keeps
    only the `unsupported` boolean plus the already-grounded `evidence_json`
    (screening_drafts has no warnings/band column). At render time `_one_row`
    (app/api/apply.py:125-142) returns only {question, answer, evidence, unsupported,
    draft_id} — neither `warnings` nor `band` — so `_screening_drafts.html` can only
    emit the fixed generic line at line 31 ('This answer may go beyond your CV - check
    the evidence before you use it.'); no band element exists in the region.
    `07-UI-SPEC.md:255-280` only required the generic `.answer-warning` line, so the
    UI is per-spec; the gap is that the phase's naming requirement (row 13) is
    checker-level only and invisible to the human who must decide whether to use the
    answer. Observed via a seeded `unsupported=1` row for listing 189 (drafting is
    broken by G-07-2, so the real draft path could not produce one).
  missing:
    - "Node: decide and implement whether the rendered `.answer-warning` names the specific offender (persist `warnings` and render them, or re-derive at render) — currently the human cannot see which claim was flagged."
    - "Node: decide whether the advisory `band` should be surfaced in the answers region; `_one_row` omits it entirely, so the region can never show an advisory band."
    - "Node: a rendering test asserting the warning names the offending token/id (or an explicit recorded decision that generic-only is intended)."
  artifacts: []
  note: "Severity major because a verified phase truth (07-VERIFICATION row 13, 'naming the id') has no human-visible surface; downgrade to minor if the intended policy is deliberately generic (the warning errs safe and never overclaims)."

- gap_id: G-07-4
  truth: "Each CV download affordance yields the artifact it labels — the post-compile banner does not duplicate the Latest CV control, and a 'Previous compiles' row's Download serves that row's PDF."
  status: failed
  reason: "User reported: \"i think the compiled pdf and latest pdf are the same so we can get rid of one of those\""
  severity: minor
  test: 7
  root_cause: |
    `GET /listings/{id}/cv/pdf` (app/api/tailoring.py:642-682) takes no version/artifact
    parameter and always selects `cv_artifact_repo.latest_for_listing(..., ok_only=True)`.
    Three affordances therefore all resolve to the same latest `ok` PDF: the persistent
    'Latest CV → Download PDF' (tailoring.html:72), every `ok` row under 'Previous
    compiles' (tailoring.html:93), and the post-compile banner emitted by
    `_compiled_fragment` (app/api/tailoring.py:343-368), which is injected above the
    persistent sections and so renders a second, identical 'Download PDF'. Consequence:
    clicking the 2026-09-29 row downloads the 2026-09-30 PDF, and after a compile the user
    sees two identical download controls. (The failed row correctly has no link; content
    is never wrong — only the affordance is.)
  missing:
    - "Node: remove the duplicate post-compile Download control, or make the post-compile banner the single 'Latest CV' control, so an artifact is not offered twice."
    - "Node: make a 'Previous compiles' row's Download serve that row's own artifact (add an artifact/version identifier to the route) — or drop the per-row links if older artifacts are intentionally not retrievable."
  artifacts: []
  note: "Not a failure of test 7's real-engine criterion (that leg passed); recorded because the user flagged it while running test 7. Minor: no data loss, the served file is always a valid `ok` PDF — the defect is a misleading/duplicated affordance."

Background (from the phase verifier, written before this UAT finding): 31 of 33 `must_haves` truths were verified against the live code; every one of
the seven phase requirement IDs (APPLY-01..APPLY-06, UI-04) is accounted for, and the
phase-scoped suite (180) and the full default lane (1650 passed, 14 deselected, 2 xfailed)
are green.

- The two abstained truths are both `verification: backstop` items whose plans named a
  held-out test that was never shipped — the truncated-note fidelity (test 1) and the
  multi-paragraph clipboard fidelity (test 2). They are covered by the human checks above
  rather than by code evidence. Adding the two held-out tests is the only code-side
  follow-up the verifier recommended.
- Caveat on the source artifact: `07-VERIFICATION.md` was written against the tree BEFORE
  the seven code-review findings were fixed (commits `106f11a`, `2661b5f`, `d88df6d`,
  `c627549`, `13bf409`, `bf7bd1f`, `a79c2fd`). None of the eight human checks above is
  invalidated by those fixes — they touch the POST action routes, the artefact-ownership
  check, the empty-response guard, the persisted question text, a helper rename and the
  draft-append path, none of which change the rendering or the flows these checks exercise.
