---
phase: 07-assisted-apply-tracker
reviewed: 2026-10-06T21:22:29Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - app/api/apply.py
  - tests/api/test_apply_package.py
  - tests/api/test_apply_draft_errors.py
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 07: Code Review Report — CR-01 gap closure (plan 07-10)

**Reviewed:** 2026-10-06T21:22:29Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

> Scope note: this is a **scoped re-review of the CR-01 gap-closure change only**
> (commits `0c01ab2`, `94c3421`), replacing the earlier phase-wide review at this
> path. It covers `app/api/apply.py` and the two named test modules. It does not
> re-certify the rest of phase 07.

## Summary

The CR-01 fix is **correct and well-targeted**. The new branch
`if len(verdicts) < len(questions): return _answers_error("drafting_partial", …, 502)`
(`app/api/apply.py:356-362`) sits textually between the pre-refusal
`await session.commit()` (`:328`) and `screening_draft_repo.replace_for_listing`
(`:364`), so a short model response can no longer reach the wholesale
`DELETE`-then-`INSERT` at `screening_draft_repo.py:109-112`. The `<` comparison is
the right one: `ground_screening_answers` iterates
`zip(questions, response.answers, strict=False)` (`app/verify/screening.py:108`), so
`len(verdicts) == min(len(questions), len(answers))` and only `<=` / `==` are
attainable — `<` is exact, not off-by-one. The two updated package stubs now return
one answer per asked `DEFAULT_QUESTIONS` entry, the reworded-question test still
pins WR-04 positional merging, and the four new tests in
`test_apply_draft_errors.py` genuinely fail if the guard is removed (a one-answer
response against three seeded ad-hoc rows currently returns `200` and collapses the
set to one row without it). `tests/api` as a whole: **356 passed, 1 xfailed**.

Two defects remain. The first is the residual of the same wholesale-replace
data-loss class the fix was meant to close: the guard only defends against a short
*response*, not against a row that is added *between* the question-set snapshot and
the replace — a concurrent tab adding an ad-hoc question while the model call runs
is still silently deleted. The second is a latent order-dependence in the test
assertions that the repo's own read path avoids.

## Per-File Assessment

### `app/api/apply.py`
Guard placement, comparison, and refusal semantics are correct; the docstring's
"three distinct 502 refusals, all writing no draft rows" is accurate for the
`drafting_failed` / `drafting_empty` / `drafting_partial` paths. The `apply_url`
`http_url` gate and the `|safe`-free rendering of answers are intact. The one
substantive defect is the concurrency hole below.

### `tests/api/test_apply_package.py`
The two former one-answer stubs are now complete four-answer responses, so no test
enshrines the shallow persistence case. The remaining issue is that the new ordered
assertions read from un-ordered `select()` results.

### `tests/api/test_apply_draft_errors.py`
The regression, boundary, and idempotency tests are the right shape and would catch
removal/inversion/`<=` mutation of the guard, as well as a reordering of the
`drafting_empty` and `drafting_partial` branches. No correctness defect found.

## Critical Issues

None.

## Warnings

### WR-01: A concurrent ad-hoc question added during the drafting call is still silently deleted

**File:** `app/api/apply.py:294-298` (snapshot) and `:364-379` (replace); the delete itself is `app/db/repositories/screening_draft_repo.py:109-112`

**Issue:** The guard closes the *partial-response* path but not the underlying
wholesale-replace hazard. `draft_answers` snapshots the question set once, before the
network call:

```python
drafts = await screening_draft_repo.read_for_listing(session, listing_id)
questions = await apply_config_repo.read_questions(session)
questions += [d.question_text for d in drafts if d.question_text not in questions]
```

The model call then runs for up to a minute (`session.commit()` at `:174` releases
the transaction first, so nothing is held). If a second tab POSTs
`/listings/{id}/apply/question` in that window, its row is committed to the DB. When
the first request resumes, the answer count matches its *stale* snapshot
(`len(verdicts) == len(questions)`), the new `drafting_partial` guard passes, and
`replace_for_listing` deletes **every** row for the listing — including the new
ad-hoc question, whose text exists nowhere else. This is the same information-loss
class as CR-01 (`screening_drafts.question_text` is the only record of an ad-hoc
question) and it directly contradicts the 07-10 plan's concurrency assumption that
"the `drafting_partial` guard returns before any write, so an interrupted/partial
drafting attempt cannot half-replace the listing's rows." The codebase itself
explicitly designs for multi-tab use (`add_question`'s docstring: "a page open in
another tab keeps valid per-answer delete targets"), so this is a reachable path, not
a theoretical one.

**Fix:** Minimal — re-read after the model call and refuse if the stored set moved:

```python
current = await screening_draft_repo.read_for_listing(session, listing_id)
if {d.question_text for d in current} != set(questions):
    return _answers_error(
        "drafting_stale",
        "Your question list changed while drafting. Your existing drafts were kept.",
        409,
    )
```

Stronger (and the fix the original CR-01 review recommended) — make the repository
upsert-by-question: delete only rows whose `question_text` is in the incoming verdict
set, then upsert those, leaving unrelated rows untouched.

### WR-02: New ordered assertions compare against an un-ordered query

**File:** `tests/api/test_apply_package.py:553-567` and `:629-636`; `tests/api/test_apply_draft_errors.py:246-247`

**Issue:** The tests assert exact list equality:

```python
rows = (await session.execute(
    select(ScreeningDraft).where(ScreeningDraft.listing_id == listing_id)
)).scalars().all()
assert [r.question_text for r in rows] == list(apply_config_repo.DEFAULT_QUESTIONS)
```

`select()` has no `ORDER BY`, so the assertion depends on SQLite's incidental
rowid-scan order. It happens to hold today (no index on `screening_drafts.listing_id`,
and all rows in `replace_for_listing` share one `created_at`), but it is a latent
flaky pattern and diverges from the project's own deterministic read
(`screening_draft_repo.read_for_listing` orders by `(created_at, id)`). The same
applies to `stored == asked` in `test_a_complete_response_persists_the_full_asked_set`.

**Fix:** Order explicitly, e.g. `.order_by(ScreeningDraft.id)`, or reuse
`screening_draft_repo.read_for_listing(session, listing_id)` for the assertions.

## Info

### IN-01: Duplicate config questions inflate the guard's denominator

**File:** `app/api/apply.py:295-298`, `app/db/repositories/apply_config_repo.py:40-42`

**Issue:** `read_questions`/`_clean` preserve order and drop blanks but never dedupe,
and `_answer_rows` later collapses duplicate `question_text` values. If the user
stores the same question twice, `len(questions)` counts both while a well-behaved
model may return one answer per *distinct* question; the new `drafting_partial`
check then false-refuses a legitimate drafting attempt (and, on the success path,
`replace_for_listing` would persist two indistinguishable rows). Related to the
prior review's IN-03; the new guard adds a second symptom to it.

**Fix:** Dedupe in `_clean`/`read_questions` while preserving first-seen order, or
enforce `UniqueConstraint("listing_id", "question_text")` in the repository.

### IN-02: The answers/error fragments re-emit `id="apply-answers"` into an `innerHTML` target

**File:** `app/api/apply.py:108-112` (`_answers_error`) and `:188-190` (`_answers_response`), responding to `app/web/templates/html/_screening_drafts.html:75,89`

**Issue:** The HTMX forms target `#apply-answers` with `hx-swap="innerHTML"`, and
`base.html` forces the swap for HTML error bodies. But both server fragments return a
root element that *is* `#apply-answers` (`<section id="apply-answers">` /
`<div id="apply-answers">`), so each swap places a second element with the same id
inside the first — a stable duplicate-id document rather than an accumulation, but
invalid HTML that can confuse selection/assertive-tech references. Pre-existing and
shared with the tailoring region, so recorded as Info only.

**Fix:** Return the inner content without the region id (target stays `innerHTML`), or
change the form to `hx-swap="outerHTML"` and keep the root id.

### IN-03: The refusal discards the partial answers the model did return

**File:** `app/api/apply.py:356-362`

**Issue:** On a partial response the route returns `drafting_partial` and stores
nothing new, so the model's usable answers are thrown away and, if the model
consistently returns fewer answers than asked, the user can never draft at all. This
is the trade-off the 07-10 plan chose deliberately (refuse rather than risk the
delete), and it is strictly safer than the prior behavior — noted so the UX ceiling
is tracked rather than silently accepted.

**Fix:** The upsert-by-question path in WR-01 both removes the concurrency hole and
lets a partial response be applied without deleting unanswered rows.

---

_Reviewed: 2026-10-06T21:22:29Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
