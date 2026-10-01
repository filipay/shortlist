---
phase: 07-assisted-apply-tracker
reviewed: 2026-09-30T18:34:06Z
depth: standard
files_reviewed: 38
files_reviewed_list:
  - alembic/versions/0006_screening_drafts.py
  - app/api/applications.py
  - app/api/apply.py
  - app/api/settings.py
  - app/config.py
  - app/db/models.py
  - app/db/repositories/application_repo.py
  - app/db/repositories/apply_config_repo.py
  - app/db/repositories/screening_draft_repo.py
  - app/domain/schemas/screening.py
  - app/main.py
  - app/pipeline/draft.py
  - app/verify/screening.py
  - app/web/templates/html/_application_history.html
  - app/web/templates/html/_application_row.html
  - app/web/templates/html/_screening_drafts.html
  - app/web/templates/html/applications.html
  - app/web/templates/html/applications_list.html
  - app/web/templates/html/apply.html
  - app/web/templates/html/base.html
  - app/web/templates/html/listing_detail.html
  - app/web/templates/html/settings.html
  - static/vendor/app.css
  - tests/api/test_applications_tracker.py
  - tests/api/test_apply_package.py
  - tests/db/test_application_repo.py
  - tests/db/test_application_events.py
  - tests/db/test_apply_config_repo.py
  - tests/db/test_screening_draft_repo.py
  - tests/pipeline/test_draft_stage.py
  - tests/verify/test_screening.py
  - tests/test_stylesheet_coverage.py
  - tests/test_auth_seam.py
  - tests/test_config.py
  - tests/db/test_migration_contract.py
  - tests/db/test_no_pii_columns.py
  - tests/db/test_skeleton_boot.py
  - tests/api/test_settings_reset.py
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
status: clean
---

# Phase 07: Code Review Report

**Reviewed:** 2026-09-30T18:34:06Z
**Depth:** standard
**Files Reviewed:** 38
**Status:** issues_found

## Summary

Phase 07 lands the assisted-apply package, the screening-drafting pipeline, the
grounding checker and the `/applications` tracker. The structural spine is strong
and matches the binding decisions: the `applied` gate resolves its artefact through
`cv_artifact_repo.read_for_download(ok_only=True)` at the SQL level
(`compile_status = 'ok'`), the row update and its one `application_events` append
share a single `begin_nested()` SAVEPOINT, migration `0006` installs the
append-only triggers on the real DDL, `ground_screening_answers` is structurally
anchored (byte-exact fact-id set intersection + digit-core containment) with the
advisory band never touching `unsupported`, and `apply_config_repo` correctly
distinguishes an absent row from an explicit empty list. The 71 phase-focused tests
pass and the failure-class mutation test (CONVENTIONS rule 4) is present.

One genuine security regression: the new apply page renders `listing.apply_url` as
an anchor with **no scheme gate**, while the queue/detail surfaces deliberately
gate the same untrusted URL class through `_http_url` because "Jinja autoescaping
does not block `javascript:`". The remaining findings are server-side contract
gaps around the `apply` actions (the ok-artifact gate is enforced on the page but
not on the POST routes) and a silent-draft-loss edge.

## Critical Issues

### CR-01: Untrusted `apply_url` is rendered as an anchor with no scheme gate

**File:** `app/api/apply.py:230` and `app/web/templates/html/apply.html:41`

**Issue:** The ready package builds `"apply_url": (listing.apply_url or "").strip()`
and the template emits `<a class="apply-link" href="{{ apply_url }}" target="_blank"
rel="noopener noreferrer">`. `listing.apply_url` is stored raw and is derived from
untrusted scraper output — `app/pipeline/stages.py:143` sets
`apply_url=raw.direct_url or raw.source_url or None` with no validation.

The codebase already knows this class of value is dangerous: `queue_repo._http_url`
(`app/db/repositories/queue_repo.py:592`) exists precisely to gate
`source_url`/`canonical_source_url` to `http`/`https`, and its docstring states
**"Jinja autoescaping does not block `javascript:`"**. The queue and detail pages
route every external URL through that gate (asserted by
`tests/api/test_queue_links.py:215` and `tests/db/test_queue_row_links.py:289`,
which prove a `javascript:` value renders no anchor). The apply package bypasses
that established gate, so a listing whose `direct_url`/`source_url` is
`javascript:...` (or a `data:` URL) renders as a clickable link that executes
attacker-controlled script in the app's own origin — which holds the user's CV and
job-search data. Jinja autoescape does not mitigate this; only the scheme gate does.

**Why it matters:** Stored/reflected XSS on the surface that exists specifically to
link out to untrusted job-board content. The repo treats this as a known threat on
the sibling surface; the new surface reintroduces it.

**Fix:**
```python
# app/api/apply.py — gate the untrusted URL exactly as queue_repo does
from urllib.parse import urlsplit

def _http_url(value: str | None) -> str:
    """Return value only when it is an http(s) URL, else ''."""
    if urlsplit(value or "").scheme.casefold() not in {"http", "https"}:
        return ""
    return value or ""

# in apply_package_page:
"apply_url": _http_url(listing.apply_url),
```
Add a regression test mirroring `test_queue_links.py`: seed `listing.apply_url =
"javascript:alert(1)"`, GET the ready page, and assert `"javascript:" not in
response.text` and `"Open the application form" not in response.text` (the fallback
paragraph renders instead).

## Warnings

### WR-01: The `/apply/draft` POST bypasses the ok-artifact gate

**File:** `app/api/apply.py:242-301`

**Issue:** `GET /listings/{id}/apply` gates on
`cv_artifact_repo.latest_for_listing(session, listing_id, ok_only=True)` (D-121), so
the page and its forms are unreachable without a verified CV. The three action
routes (`draft`, `question`, `draft/delete`) never re-check that gate. A direct
`POST /listings/{id}/apply/draft` therefore makes a real LLM call, writes the
`llm_calls` audit row and persists `screening_drafts` for a listing that has no
`ok` artifact (or only a `blocked`/`failed` one).

**Why it matters:** The ok-artifact precondition is the phase's core package
contract (D-121), and this bypasse it server-side. It also spends budget outside the
intended surface. The page-only gate is not an authorization boundary.

**Fix:** Resolve the gate in the draft route before spending anything:
```python
artifact = await cv_artifact_repo.latest_for_listing(session, listing_id, ok_only=True)
if artifact is None:
    return _answers_error("no-ok-artifact", "Tailor and verify a CV first.", 409)
```
(The `question`/`draft/delete` routes spend nothing, but applying the same check
keeps the package's actions consistent with the package's availability.)

### WR-02: The `applied` gate does not verify the ok artifact belongs to the listing

**File:** `app/db/repositories/application_repo.py:462-470` (`record_application`) and `:525-533` (`transition_application`)

**Issue:** Both paths resolve the artefact with
`cv_artifact_repo.read_for_download(session, cv_artifact_id, ok_only=True)`, which
filters on `id` and `compile_status == 'ok'` only. It never compares
`record.listing_id` against the application's `listing_id`. The UI picker is
listing-scoped, but a crafted POST can link an `ok` artefact belonging to a
*different* listing.

**Why it matters:** APPLY-04/D-129's contract is "the exact verified CV that was
sent" for *this* job. Linking listing B's CV to listing A violates that contract and
makes the stored `cv_artifact_id` unreliable — the one field the tracker exists to
guarantee. The SQL gate is necessary but not sufficient.

**Fix:**
```python
record = await cv_artifact_repo.read_for_download(session, cv_artifact_id, ok_only=True)
if record is None or record.listing_id != listing_id:   # or row.listing_id in transition
    return None
artifact_id = record.id
```

### WR-03: An empty model response silently clears every stored draft

**File:** `app/api/apply.py:295-317`

**Issue:** `ScreeningDraftResponse.answers` defaults to `[]` and its own docstring
calls that "a valid (if useless) response". `draft_screening_answers` therefore
returns `[]` (not `None`) for an `ok=True` call with no answers, and the route's
`if verdicts is None` guard does not catch it. It then calls
`replace_for_listing(drafts=[])`, which deletes the listing's existing drafts and
returns a 200 with "No drafted answers yet." — the user's previously generated
answers are gone with no warning.

**Why it matters:** Silent loss of user-visible work on a "successful" response.
The replace-all semantics are correct for a real regeneration; treating a useless
response as a regeneration is not.

**Fix:**
```python
if not verdicts:
    # No usable answers (including a valid-but-empty response): refuse, do not wipe.
    return _answers_error(
        "drafting_empty",
        "The drafting call returned no answers. Your existing drafts were kept.",
        502,
    )
```
(or return the current region unchanged rather than a `data-error`). Add a test
seeding a draft, stubbing an empty `ScreeningDraftResponse`, and asserting the
stored row survives.

### WR-04: The persisted question text is the model's echoed free text, used as the merge key

**File:** `app/verify/screening.py:122`, `app/api/apply.py:308`, `app/api/apply.py:151`

**Issue:** `ground_screening_answers` sets `question=answer.question`, i.e. whatever
the model put in its `ScreeningAnswer.question` field. The route persists that as
`screening_drafts.question_text` (`app/api/apply.py:308`), and `_answer_rows`
rebuilds the UI by matching config questions to stored drafts with
`by_question = {draft.question_text: draft ...}` — exact string equality over
model-produced text. If the model paraphrases a question (or answers in a different
order), the stored row no longer matches the config question, so the page renders
the config question as "Not yet drafted." plus a stray reworded block containing the
answer.

**Why it matters:** This is the lexical-anchoring smell CONVENTIONS rule 1 warns
against: a structured relationship (answer N belongs to asked question N) is keyed
on free text the model controls. The existing test stub happens to echo the question
verbatim, so the failure class is not pinned.

**Fix:** Carry the asked question structurally. Zip the verdicts with the input
questions and persist the asked text:
```python
# ground_screening_answers: take the asked questions as an ordered argument
for asked, answer in zip(questions, response.answers, strict=False):
    verdicts.append(ScreeningVerdict(question=asked, ...))
```
or persist an index/an `apply_config` question id. Add a test where the stub
returns a *reworded* question and assert it still merges with the config question.

## Info

### IN-01: Apply route reaches into another repository's private helper

**File:** `app/api/apply.py:224`

**Issue:** `apply_package_page` calls `application_repo._ok_artifacts_by_listing(...)`,
a private symbol of `application_repo`. Cross-module use of a `_`-prefixed function
couples the apply route to another module's internals and means the helper's
signature is effectively public but unmarked.

**Fix:** Promote it (e.g. `ok_artifacts_by_listing`) to the public API of
`application_repo` (and drop the underscore), or expose a thin public wrapper.

### IN-02: Adding an ad-hoc question rewrites every existing draft's id and created_at

**File:** `app/api/apply.py:343-360`

**Issue:** `add_question` re-reads all drafts, converts them back to
`ScreeningDraftInput` and re-inserts the whole set through `replace_for_listing`.
That re-issues primary keys and resets `created_at` for rows that did not change. A
page already open in another tab then holds stale `draft_id` values, so its
per-answer delete 404s.

**Fix:** Add an `append_draft(session, listing_id, input)` repository method that
inserts a single row without deleting/re-inserting the set.

---

_Reviewed: 2026-09-30T18:34:06Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_

---

## Re-review

Scoped re-review of the seven follow-up commits (`106f11a` … `a79c2fd`), verifying
each claim against the actual diff rather than the commit message. All seven
original findings are genuinely closed with evidence; two **Info-only** residual
items are recorded below. The frontmatter `findings` block now reflects the current
open set (the original 1 Critical / 4 Warning findings are closed, not deleted, in
the sections above).

### Per-finding closure

- **CR-01 — CLOSED.** `queue_repo.py:592` renames the gate to public `http_url`;
  `app/api/apply.py:59` imports the *same* function the queue uses, and `:234` sets
  `"apply_url": http_url(listing.apply_url)`. `queue_repo._enrich` still calls
  `http_url` at its three sites, so there is no duplicated gate body. The template
  branch `apply.html:40-44` renders the fallback paragraph when the gate returns
  `""`, so a non-http(s) scheme can never reach the `href`. The regression test
  `tests/api/test_apply_package.py::test_a_non_web_apply_url_renders_no_anchor` seeds
  the literal `javascript:alert(1)` onto the Listing and asserts on **rendered
  output** (`"javascript:" not in response.text`, no `class="apply-link"`, the
  fallback copy present). No `_http_url` reference remains in `app/`.

- **WR-01 — CLOSED.** All three action routes re-check
  `latest_for_listing(session, listing_id, ok_only=True)` and refuse `409`
  `no-ok-artifact` before doing any work: draft `app/api/apply.py:272` (before
  `drafting_skip_reason` and before the stage, hence before any `llm_calls` write),
  question `:355`, delete `:398`. Tests:
  `test_the_draft_action_refuses_without_an_ok_artifact` asserts `calls == []` **and**
  `screening_drafts == []` (not merely the status code);
  `test_the_question_action_refuses_without_an_ok_artifact`; and
  `test_the_delete_action_refuses_without_an_ok_artifact`, which asserts the
  pre-seeded row survives.

- **WR-02 — CLOSED.** `application_repo.py:472` (`record_application`) refuses when
  `record.listing_id != listing_id`; `:537` (`transition_application`) refuses when
  `record.listing_id != row.listing_id`. Both return `None` **before** the SAVEPOINT,
  so nothing is written. No other path can set `cv_artifact_id` (`update_application`
  never touches it), so the comparison cannot be bypassed. Test
  `tests/db/test_application_repo.py::test_applied_refuses_an_ok_artifact_from_another_listing`
  exercises both the record and the transition path.

- **WR-03 — CLOSED.** `app/api/apply.py:309` replaces the `is None` test with
  `if not verdicts:` and returns `502 drafting_empty` **before**
  `replace_for_listing` is reached. Test `test_an_empty_response_keeps_the_stored_drafts`
  seeds a stored draft, stubs `ScreeningDraftResponse(answers=[])`, and asserts the
  stored row's `question_text` **and** `answer_text` survive — the wipe, not just the
  response code, is what is pinned.

- **WR-04 — CLOSED.** `app/verify/screening.py:83` now takes the ordered `questions`
  argument; `:108` iterates `zip(questions, response.answers, strict=False)`; `:132`
  emits `question=asked`. `app/pipeline/draft.py:211` passes the route's question
  list. The `warnings` / `grounded_evidence_ids` / `unsupported` / `band` decision
  path is byte-for-byte unchanged (the diff touches only the loop binding and the
  `question=` field). `test_a_reworded_model_question_still_merges_with_the_config_question`
  genuinely returns a *different* model `question` ("Why do you want this job?") and
  asserts the persisted key and rendered output are the asked config question, with
  the reworded string absent; `test_the_verdict_question_is_the_asked_text_not_the_model_echo`
  pins it at the verifier layer. Fewer-answers alignment is `strict=False`: an
  unanswered question produces no verdict (documented positional contract), and
  extra model answers are dropped.

- **IN-01 — CLOSED.** Pure rename to `ok_artifacts_by_listing`; the three call sites
  (`application_repo.py:225`/`:400` via the `:246` definition and
  `app/api/apply.py:225`) and `__all__` (`application_repo.py:595`) are updated. No
  behaviour change; no `_ok_artifacts_by_listing` reference remains in `app/`.

- **IN-02 — CLOSED.** `append_draft` (`screening_draft_repo.py:120-147`) inserts one
  row inside a `begin_nested()` SAVEPOINT, returns `_to_record(row)`, and never
  commits; `add_question` uses it (`app/api/apply.py:367`).
  `test_append_draft_inserts_one_row_and_keeps_existing_ids` asserts the existing ids
  **and** `created_at` values survive, and `test_append_draft_never_commits` pins the
  no-commit rule.

### New findings

- **IN-03 (Info) — a zero-question draft still spends a model call.**
  `app/api/apply.py:277-281` builds `questions` from the config list plus ad-hoc
  drafts; if the user has saved an explicit empty list and has no ad-hoc drafts,
  `questions == []` and the code still calls `draft_screening_answers` (a paid
  backend call and one `llm_calls` row) before the new `if not verdicts:` refusal at
  `:309` fires with `502 drafting_empty`. The call-spend predates WR-03; only the
  refusal classification is new. Fix: return the region unchanged (a distinct
  no-op) when `not questions`, before the backend is exercised — consistent with the
  project's LLM-cost posture.

- **IN-04 (Info) — the IN-01 rename left a living doc naming the old symbol.**
  `docs/implementation-notes.md:49` still states "Only `http`/`https` URLs are ever
  rendered as links (`_http_url` in `queue_repo.py`)". The function is now
  `http_url` (`queue_repo.py:592`). Update the reference; it is a present-tense
  behaviour note, not a historical change record.

### Follow-up closure (IN-03 / IN-04)

Re-verified against the live tree on 2026-10-01 (not against the commit messages).
Both residual items are now closed; no open findings remain in this report.

- **IN-03 — CLOSED** (commit `1e6d088`). `app/api/apply.py:288-293` returns
  `_answers_error("no-questions", "Add a screening question first.", 409)` — the
  file's **existing** refusal helper (`app/api/apply.py:102`), not a new error shape —
  placed immediately after the config + ad-hoc merge (`:281-284`) and **before**
  `load_facts` (`:296`) and `draft_screening_answers` (`:304`). No backend call is
  reachable on that path, so no `llm_calls` audit row is written. Pinning test
  `tests/api/test_apply_package.py::test_the_draft_action_refuses_with_no_questions`
  seeds an `ok` artefact plus `apply_config_repo.write_questions(session, [])`, then
  asserts `409` + `data-error="no-questions"` + `calls == []` + no `ScreeningDraft`
  rows.
  - The empty list is produced by the **explicit row**, not `DEFAULT_QUESTIONS`:
    `apply_config_repo.read_questions` (`:52-56`) returns `_clean(stored)` when
    `isinstance(stored, list)` (an explicit `[]` yields `[]`), and only
    `stored is None` (absent row) falls back to `DEFAULT_QUESTIONS`.
  - The test exercises the failure class, not just the status code: with the guard
    removed the route proceeds to `draft_screening_answers`, which has no empty-list
    short-circuit — it still reaches `backend.complete_structured`
    (`app/pipeline/draft.py:175`) and the audit path. The test stub therefore records
    a non-empty `calls`, and its empty `ScreeningDraftResponse` would yield
    `502 drafting_empty`, failing both the `calls == []` and the
    `409`/`data-error="no-questions"` assertions.
  - Focused re-run: `.venv/bin/python -m pytest -q tests/api/test_apply_package.py`
    → **27 passed**. `ruff check app/api/apply.py tests/api/test_apply_package.py`
    → clean.

- **IN-04 — CLOSED** (commit `3c9b4e5`). `docs/implementation-notes.md:49` now reads
  `http_url` (was `_http_url`). Independent `grep -rn "_http_url" app/ docs/ tests/`
  returns **no matches**, so no living reference to the renamed symbol remains.

#### No new findings

Neither fix introduces a defect or weakens an existing finding. The `no-questions`
branch can only fire when the config list **and** the ad-hoc merge are both empty
(the merge appends every stored `question_text` not already present), so it cannot
suppress a legitimate draft. The `drafting_skip_reason()` check still runs first, so
the pre-existing skip vocabulary is unchanged. No existing test asserted a paid call
for an empty-and-draftless listing: the only other `write_questions(session, [])`
call site is the GET-page test
(`test_answers_region_renders_the_empty_copy_when_no_questions`), which does not hit
the POST route.

### Test + lint evidence

- `.venv/bin/python -m pytest -q` → **1650 passed, 14 deselected, 2 xfailed**
  (confirms the claimed count exactly).
- `.venv/bin/ruff check` over the six changed source files and four changed test
  files → **1 error**, `app/db/repositories/queue_repo.py:300` E501, a pre-existing
  `page_count` docstring on a line none of the seven commits touched. Confirms the
  claim.
- No fix weakened a test or narrowed a parametrized case. The only changed existing
  assertion is `test_the_draft_action_makes_one_call_and_persists_rows`'s expected
  persisted key, which now checks the *asked* question (required by WR-04 and
  strictly stronger); `tests/verify/test_screening.py`'s `_ground` helper gained an
  optional `questions` parameter defaulting to the prior behaviour, so every
  pre-existing unit test still exercises the same inputs. No assertion was deleted.
- No new false guarantee was introduced: the new docstrings (`append_draft`, the
  `ground_screening_answers` positional contract, the WR-01/02/03 comments) describe
  behaviour the code delivers (CONVENTIONS rule 6).

### Re-review verdict

All seven original findings are genuinely closed, each with a test that exercises
the failure class rather than only the status code. The two residual items recorded
by the first re-review (IN-03, IN-04) are now also closed on `master` — IN-03 by
`1e6d088` (guard before the backend, pinned by
`test_the_draft_action_refuses_with_no_questions`) and IN-04 by `3c9b4e5` (doc now
names `http_url`; no `_http_url` reference survives). No open findings remain.
In particular, CR-01's XSS is closed by reusing the queue's exact scheme gate, and
WR-02/WR-03/WR-04 close the integrity and data-loss gaps without touching the
grounded/unsupported decision path. Phase 07 is shippable pending the outstanding
human verification items in `07-VERIFICATION.md`; no code change is required before
advancing.
