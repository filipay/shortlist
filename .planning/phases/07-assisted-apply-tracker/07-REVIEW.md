---
phase: 07-assisted-apply-tracker
reviewed: 2026-10-06T17:50:00Z
depth: standard
files_reviewed: 23
files_reviewed_list:
  - alembic/versions/0007_screening_draft_warnings.py
  - app/api/applications.py
  - app/api/apply.py
  - app/api/tailoring.py
  - app/db/models.py
  - app/db/repositories/screening_draft_repo.py
  - app/domain/schemas/screening.py
  - app/pipeline/draft.py
  - app/web/templates/html/_screening_drafts.html
  - app/web/templates/html/tailoring.html
  - tests/api/test_applications_tracker.py
  - tests/api/test_apply_draft_errors.py
  - tests/api/test_apply_package.py
  - tests/api/test_apply_package_warnings.py
  - tests/api/test_cv_pdf_route.py
  - tests/api/test_tailoring_generate.py
  - tests/api/test_tailoring_review.py
  - tests/db/test_migration_contract.py
  - tests/db/test_no_pii_columns.py
  - tests/db/test_screening_draft_repo.py
  - tests/db/test_skeleton_boot.py
  - tests/domain/test_screening_schema.py
  - tests/llm/test_salvage.py
findings:
  critical: 1
  warning: 2
  info: 4
  total: 7
status: issues_found
---

# Phase 07: Code Review Report

**Reviewed:** 2026-10-06T17:50:00Z
**Depth:** standard
**Files Reviewed:** 23
**Status:** issues_found

## Summary

Phase 07 (assisted apply + tracker) is broadly sound. The `ok`-artifact access
control is enforced in SQL on every read path (`cv_artifact_repo.latest_for_listing` /
`read_for_download`), the `applied` transition re-verifies both `compile_status` and
listing ownership before linking an artifact, the PDF path is built from stored paths
plus integer ids and re-checked against `artifacts_dir.resolve()`, the `apply_url`
anchor goes through the `http_url` scheme gate, and all user/model text is rendered
through Jinja autoescape (verified `autoescape` is enabled) with the one `|safe` use
in `tailoring.html` re-inserting HTML that was already server-escaped. Emptiness,
unusable-response and cap refusals are handled with honest, distinct copy, and the
four UAT gaps (G-07-1 … G-07-4) are addressed in the recent commits.

One data-loss defect in the drafting route survives the round of gap closures, plus
two robustness/UX defects. Details below.

## Critical Issues

### CR-01: A partial drafting response silently deletes the user's unanswered stored drafts

**File:** `app/api/apply.py:339-361` (with `app/verify/screening.py:108` and `app/db/repositories/screening_draft_repo.py:109-128`)

**Issue:** The route only distinguishes "zero answers" from "some answers":

```python
if not verdicts:
    return _answers_error("drafting_empty", "...Your existing drafts were kept.", 502)
await screening_draft_repo.replace_for_listing(session, ...)  # deletes EVERY row for the listing
```

`ground_screening_answers` aligns answers positionally and emits **no verdict for an
unanswered question** (`zip(questions, response.answers, strict=False)`), and
`replace_for_listing` deletes the listing's whole draft set before inserting the
verdicts. So a *valid but partial* model response (e.g. 2 answers for 7 asked
questions) passes the `if not verdicts` guard, and every row the model did not answer
is deleted — including **user-authored ad-hoc questions** created by
`POST .../apply/question`. With the default 4-question config plus 3 ad-hoc questions,
a response carrying one answer leaves exactly one row and irreversibly drops the other
six. This is silent: the user sees `Not yet drafted.`, not a warning.

Reproduced with a temporary pytest probe against the real route (stub returning a
single answer; three seeded ad-hoc rows `Ad-hoc A/B/C`): after the POST, only one
`screening_drafts` row remained. The existing suite enshrines the shallow case —
`tests/api/test_apply_package.py:542` asserts a one-answer stub persists exactly
`["Why are you interested in this role?"]`, and no test asserts the unanswered rows
survive.

**Fix:** Treat "fewer verdicts than asked questions" as its own refusal, or preserve
rows the response did not cover instead of replacing wholesale. Minimal version:

```python
if len(verdicts) < len(questions):
    return _answers_error(
        "drafting_partial",
        "The drafting call answered only some questions. "
        "Your existing drafts were kept.",
        502,
    )
```

The stronger fix is an upsert-by-question path in `screening_draft_repo` that only
rewrites rows present in `verdicts` and leaves the rest untouched. Either way add a
regression test seeding ad-hoc rows and returning a partial response, asserting the
unanswered rows (and their `question_text`) survive.

## Warnings

### WR-01: The apply-region forms return a bare fragment on a full-page submit, replacing the document

**File:** `app/api/apply.py:363, 407, 446` and `app/web/templates/html/_screening_drafts.html:54-59, 73-83, 87-97`

**Issue:** `_answers_response` returns only the `#apply-answers` region. The
add-question and draft forms carry an `hx-post`, but the **delete** form
(`_screening_drafts.html:54-59`) does not — it is a plain `method="post"` form with no
HTMX attribute. Submitting it makes the browser navigate to the POST response, so the
whole document is replaced by the fragment: no `base.html`, no `/static/vendor/app.css`,
no page chrome. This is exactly the G-07-1 failure class that was fixed for the record
route by returning a 303, and here it affects the delete action for **all** users (JS on
or off). The add-question/draft forms degrade the same way when JS is off, despite the
template comment claiming "A real form action gives the no-JS degrade".

**Fix:** Return a redirect for a non-HTMX submit (detect the `HX-Request` header) to the
apply page, or wire the delete form with `hx-post`/`hx-target="#apply-answers"` and keep
a 303 fallback for no-JS. Follow `app/api/tailoring.py:564`'s `RedirectResponse(..., 303)`.

### WR-02: `_findings_fragment` can 500 on a non-dict `verification_json`

**File:** `app/api/tailoring.py:377`

**Issue:** `verification = record.verification_json or {}` assumes the JSON column is a
mapping; a directly-seeded or legacy row holding a list/string makes
`verification.get("checks")` raise `AttributeError`, turning a blocked/failed compile
response into a 500. The sibling `_parse_findings` (`app/api/tailoring.py:158`) already
guards this with `isinstance(verification_json, dict)`, so the two readers of the same
column disagree on defensiveness.

**Fix:**

```python
verification = record.verification_json if isinstance(record.verification_json, dict) else {}
checks = verification.get("checks") or []
```

## Info

### IN-01: `screening_draft_repo` docstring promises a SAVEPOINT the delete helpers do not use

**File:** `app/db/repositories/screening_draft_repo.py:8-9, 163-184`

**Issue:** The module docstring states "every write is wrapped in a SAVEPOINT
(`session.begin_nested()`)". `replace_for_listing`, `append_draft` comply;
`delete_for_listing` and `delete_draft` do not. The prose overclaims (CONVENTIONS rule 6:
no false guarantees in prose).

**Fix:** Either wrap the two deletes in `begin_nested()` for consistency, or narrow the
docstring to name only the writes that are wrapped.

### IN-02: Tracker row action forms have no `method`/`action`, so they are JS-only no-ops

**File:** `app/web/templates/html/_application_row.html:28-46, 50-59`

**Issue:** The status and notes forms carry only `hx-post`/`hx-target`; with JavaScript
off the browser defaults to `GET` against the current URL, reloads the page and silently
performs no change. The route pair (`app/api/applications.py:225, 286`) does serve a
`<tr>` fragment for HTMX, but there is no non-HTMX path. (Not in the reviewed file list;
raised because it is the same no-JS class as WR-01.)

**Fix:** Add `method="post" action="/applications/{id}/status"` / `.../{id}"` to the
forms so a no-JS submit reaches the route (the route response is a fragment; a 303 for
non-HTMX submits would be needed to keep the page intact).

### IN-03: `_answer_rows` silently collapses drafts that share a question string

**File:** `app/api/apply.py:157`

**Issue:** `by_question = {draft.question_text: draft for draft in drafts}` keeps only
the last row for a duplicate question, and `screening_drafts` has no UNIQUE constraint on
`(listing_id, question_text)`. `add_question` checks the known set within one request,
but two concurrent submissions can create two rows with the same text; one then becomes
unreachable in the region (and undeletable from it).

**Fix:** Add `UniqueConstraint("listing_id", "question_text")` to `ScreeningDraft` (with
a migration) or make `append_draft` an upsert on `(listing_id, question_text)`.

### IN-04: Clipboard handler throws when `navigator.clipboard` is unavailable

**File:** `app/web/templates/html/_screening_drafts.html:46-49`

**Issue:** `@click="navigator.clipboard.writeText(...).then(...)"` dereferences
`navigator.clipboard` unguarded. On a non-secure context the property is `undefined`, so
the handler throws a `TypeError` rather than reaching the `.then` (the label does stay
`Copy answer`, so the user-visible outcome matches the comment, but the error is
unhandled).

**Fix:** Guard the call, e.g.
`@click="navigator.clipboard?.writeText(...).then(...) ?? null"` or a small Alpine
method with a fallback.

---

_Reviewed: 2026-10-06T17:50:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
