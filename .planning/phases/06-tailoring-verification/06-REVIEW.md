---
phase: 06-tailoring-verification
reviewed: 2026-09-24T23:45:00Z
depth: standard
files_reviewed: 44
files_reviewed_list:
  - app/api/tailoring.py
  - app/config.py
  - app/db/repositories/cv_artifact_repo.py
  - app/db/repositories/llm_call_repo.py
  - app/domain/cv.py
  - app/main.py
  - app/pipeline/tailor.py
  - app/verify/__init__.py
  - app/verify/base.py
  - app/verify/grounding.py
  - app/verify/numbers.py
  - app/verify/plan_checks.py
  - app/verify/text_checks.py
  - app/web/templates/html/_cv_findings.html
  - app/web/templates/html/_tailoring_review.html
  - app/web/templates/html/listing_detail.html
  - app/web/templates/html/tailoring.html
  - static/vendor/app.css
  - tests/api/test_cv_artifact_blocked.py
  - tests/api/test_cv_pdf_route.py
  - tests/api/test_tailoring_generate.py
  - tests/api/test_tailoring_review.py
  - tests/db/test_cv_artifact_repo.py
  - tests/domain/test_cv_ids.py
  - tests/domain/test_patch_ops.py
  - tests/fixtures/verify/base_extract.txt
  - tests/fixtures/verify/digit_skill_extract.txt
  - tests/fixtures/verify/injection_residue_extract.txt
  - tests/fixtures/verify/missing_entity_extract.txt
  - tests/fixtures/verify/missing_heading_extract.txt
  - tests/fixtures/verify/novel_metric_extract.txt
  - tests/fixtures/verify/reworded_verbatim_extract.txt
  - tests/fixtures/verify/three_page_extract.txt
  - tests/pipeline/test_tailor_stage.py
  - tests/test_auth_seam.py
  - tests/test_config.py
  - tests/verify/__init__.py
  - tests/verify/fixtures.py
  - tests/verify/test_block_no_repair.py
  - tests/verify/test_grounding.py
  - tests/verify/test_no_free_text_path.py
  - tests/verify/test_numbers.py
  - tests/verify/test_plan_checks.py
  - tests/verify/test_text_checks.py
findings:
  critical: 2
  warning: 1
  info: 7
  total: 10
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-09-24T23:45:00Z
**Depth:** standard
**Files Reviewed:** 44
**Status:** issues_found

## Summary

This is a re-review of the phase after the three gap-closure plans (06-05, 06-06,
06-07). Those three fixes are **correct for what they targeted**: the compile route now
honours `settings.tailoring_enabled` before any read (WR-01 closed); the bullet/section
ops are grounded on their own family's id set at the single validation boundary, so a
non-bullet id can no longer produce a phantom `ChangeRecord` (WR-02 closed); and the
date-like exclusion is now region-local, so one entry's year can no longer excuse a
token in another entry's region (WR-03 closed). The patch schema still carries no field
that reaches the PDF, `apply_patch` remains all-or-nothing and pure, the spend guard is
still reserve-then-call, and the `ok`-only artifact predicate is still enforced in SQL on
both accessors. No injection, traversal, secret or auth-bypass defect was found in the
phase-6 source.

However, **check 4 (`metric_containment`) still hard-fails valid CVs**, in two ways the
06-05 fix did not close and that no committed test exercises. Both are the CR-01 class:
a blocking check fails on ordinary, correct CV content, and the only recovery (D-118's
"generate a fresh tailoring") re-runs the same predicate, so preview and download are
dead for the affected CV:

- **CR-01** — `_allowed_for_entry` never includes `RenderedEntry.location`, although the
  template renders it into the region. A location carrying a digit (Eircode, UK/US postal
  code, "Dublin 2", "Remote (GMT+1)") is a surplus candidate and a **hard fail**.
- **CR-02** — `_entry_lines` anchors a region to *any* line containing `squash(entry.org)`
  as a substring. When a later entry's employer name (which is squashed, so whitespace-
  and punctuation-insensitive) also appears in an earlier entry's bullet, the later
  entry's region starts at that bullet; the earlier entry's bullets then bleed into the
  later region and their digits fail. The substring rule also misfires on short/common
  org names.

Both were reproduced against the committed stand-in fact store (transcripts below). The
one remaining Warning is a pre-existing error-handling gap (a raised backend exception
escapes as a 500 and skips the audit row the module promises). The Info items are the
still-valid carry-overs plus two minor surface/audit inconsistencies.

Severity note: `critical` here is the severity tier equivalent to a BLOCKER.

## Critical Issues

### CR-01: `metric_containment` hard-fails a valid CV whose location contains a digit

**File:** `app/verify/numbers.py:143-152` (`_allowed_for_entry`), rendered at
`app/latex/templates/cv.tex.jinja:60`, checked at `app/verify/text_checks.py:82-98`

**Issue:** The template renders `entry.location` on its own line inside the entry's
region:

```latex
\BLOCK{ if entry.location }
\noindent\textit{\VAR{entry.location}}\par
\BLOCK{ endif }
```

`region_token_report` cuts a region from the entry's org line to the next entry's org
line (`app/verify/numbers.py:236-255`), so every digit core in the location line is a
candidate. But `_allowed_for_entry` enumerates only `dates`, `org`, `title` and the
bullets' `text`/`metrics` — **not `location`** — and `non_entry_structured_strings`
(`app/verify/numbers.py:155-179`) does not carry locations either. So a location such as
`Dublin 2`, `London EC1A 4JQ`, `New York, NY 10001`, `D02 X285` or `Remote (GMT+1)`
produces a candidate that is absent from `allowed`, and `check_metric_containment` returns
`fail`. Check 4 is blocking (`app/verify/text_checks.py:92-97`); D-118's recovery is a
fresh tailor, which reproduces the same plan text.

Reproduced against the committed stand-in (only the source location and the matching
extraction line changed):

```
entry location = "Dublin 2"
region exp/northwind-labs-2021 candidates= ['2', '99', '40']
allowed                          = ['03', '09', '2021', '2024', '40', '99']
metric_containment: fail ['exp/northwind-labs-2021:2']
```

`D-113` states every region digit core must be "one of that region's source tokens";
`location` **is** a source token of the region, so this is an implementation divergence,
not a missing feature. No committed fixture exercises it — the stand-in's location is
`"Dublin, IE"` (no digit) and `grep -rn location tests/verify app/verify` returns nothing.

**Fix:** add the entry's location to its allow-set:

```python
def _allowed_for_entry(entry: RenderedEntry) -> set[str]:
    """The digit cores a region may carry: its surviving bullets, location, org/title and dates."""
    allowed: set[str] = set(digit_cores(entry.dates))
    allowed |= set(digit_cores(entry.org))
    allowed |= set(digit_cores(entry.title))
    if entry.location:
        allowed |= set(digit_cores(entry.location))
    for bullet in entry.bullets:
        allowed |= set(digit_cores(bullet.text))
        for metric in bullet.metrics:
            allowed |= set(digit_cores(metric))
    return allowed
```

Add a regression fixture: a stand-in entry whose location is `"Dublin 2"` and an
extraction whose location line is `Dublin 2` must pass `metric_containment` while
`novel_metric_extract.txt` still fails.

### CR-02: Region anchoring matches `squash(org)` as a substring, mis-locating a region and hard-failing a valid CV

**File:** `app/verify/numbers.py:120-140` (`_entry_lines`, match at line 134), consumed at
`app/verify/numbers.py:236-255`

**Issue:** `_entry_lines` finds an entry's region start with
`if needle in squashed_lines[index]` from a cursor. Because `squash` strips whitespace and
all non-alphanumerics (`app/domain/tex.py:125-134`), this is a naked substring test:
a bullet from an **earlier** entry that mentions a **later** entry's employer matches
first. The later entry's region then begins at that bullet line, which (a) truncates the
earlier entry's region so its trailing bullets are never checked there, and (b) pulls the
earlier entry's bullet digits into the later region, where they are surplus candidates
against the later entry's facts. The result is a **hard fail** on a correct CV.

Reproduced with two roles at the same employer, where entry A's bullet names the company:

```
regions: [('exp/acme-2018', []), ('exp/acme-2019', ['5'])]
check:   fail ['exp/acme-2019:5']
```

`Acme`'s squashed needle `acme` matches the bullet line `Rebuilt Acme's 5 service mesh`,
so entry B's region starts one line early. This is not exotic: a bullet referring to the
employer ("Acme's billing platform") is ordinary CV prose, and the substring rule is even
broader for short or common org names (`Meta` matching `metadata`, `Go` matching
`ongoing`, a single-letter employer name matching almost anything). Same class and same
consequence as CR-01: a blocking check fails correct content with no UI recovery.

**Fix:** anchor the region on the entry **header line**, which the template emits with
both the org and the title on the same line (`cv.tex.jinja:58`), instead of on any line
that merely contains the org. Requiring both needles also removes the substring-vs-word
fragility:

```python
def _entry_lines(entries: list[RenderedEntry], lines: list[str]) -> list[int]:
    squashed_lines = [squash(line) for line in lines]
    positions: list[int] = []
    cursor = 0
    for entry in entries:
        org_needle = squash(entry.org)
        title_needle = squash(entry.title)
        found = -1
        if org_needle and title_needle:
            for index in range(cursor, len(lines)):
                line = squashed_lines[index]
                if org_needle in line and title_needle in line:
                    found = index
                    break
        positions.append(found)
        if found >= 0:
            cursor = found + 1
    return positions
```

(Any anchor that only matches the header — e.g. requiring the `---` separator the
template emits — is equivalent; requiring org **and** title avoids depending on how the
extractor renders the em-dash.) Add a regression case: two entries at the same employer
where the first entry's bullet names the employer must keep each bullet's metrics inside
its own region.

## Warnings

### WR-01: A raised backend exception skips the audit row and escapes the route as a 500

**File:** `app/pipeline/tailor.py:217-242` (`tailor_listing`), `app/api/tailoring.py:370-384` (generate route)

**Issue:** `tailor_listing`'s docstring states it "never raises for a model failure" and the
module's contract is "every call writes exactly one `llm_calls` row". The
`complete_structured` call sits inside `try` with only `_release()` in `finally`; the
`record_llm_call` that would satisfy the audit contract is **after** the call, so a raise
(transport error) propagates with no `llm_calls` row written. The generate route does not
catch it, so the request becomes a 500. In practice `app/llm` returns values rather than
raising, so this is latent — but it is an unhandled exception path on the request surface.

**Fix:** record the attempt before surfacing the failure, then keep the value-returning
contract:

```python
try:
    parts = build_tailoring_parts(facts, listing, requirements)
    result = await backend.complete_structured(...)
    await llm_call_repo.record_llm_call(
        session, purpose="tailor", status=result.status, result=result, run_id=None, now=now
    )
except Exception as exc:  # noqa: BLE001 — an audit row is owed even when the transport raises
    await llm_call_repo.record_llm_call(
        session, purpose="tailor", status="error", error=f"{type(exc).__name__}: {exc}",
        run_id=None, now=now,
    )
    log.warning("pipeline.tailor_transport_error", error=type(exc).__name__)
    return None
finally:
    await _release()
```

## Info

### IN-01: A spend-cap refusal is surfaced as a generic 502 "tailoring failed"

**File:** `app/pipeline/tailor.py:200-215` (refusal returns `None`), `app/api/tailoring.py:379-384`

**Issue:** `tailor_listing` returns `None` both for a budget refusal and for a model
failure, and the generate route maps every `None` to `data-error="tailoring_failed"` with
HTTP 502. The operator cannot tell "the rolling-24h cap refused this" from "the model
returned garbage", even though the refusal row already carries `budget_exceeded`.
**Fix:** return a small result value (or raise a typed refusal) distinguishing the two,
and map the cap case to a 429/409 fragment naming the 24 h ceiling.

### IN-02: `verify_text` derives `verifier_version` indirectly through `model_fields`

**File:** `app/verify/text_checks.py:201`

**Issue:** `verifier_version=VerificationResult.model_fields["verifier_version"].default`
re-reads the field default where the module already exports `VERIFIER_VERSION`
(`app/verify/base.py:22`) — the constant `compile_tailored` uses for the merged result
(`app/pipeline/tailor.py:385`). The indirection breaks silently if the field is renamed.
**Fix:** `verifier_version=VERIFIER_VERSION` (imported from `app.verify.base`).

### IN-03: The "section lost all its entries" guard is unreachable dead code

**File:** `app/domain/cv.py:792-793`

**Issue:** `_build_plan` raises `InvalidPatchError("section ... lost all its entries")`
when `section.entries and not entries`, but `entries` is a 1:1 comprehension over
`section.entries`, so it can never be empty when the source is non-empty (the branch is
marked `# pragma: no cover`). No current op targets entries, so D-106's
"a section losing all entries" invariant is enforced by no reachable path, yet the
`_validate_patch` comment (lines 681-683) implies it is.
**Fix:** either delete the branch and state in `_validate_patch` that no current op can
empty a section (adding the guard with the first op that can), or keep the branch and
drop the enforcement claim. An unreachable raise plus a comment claiming enforcement is
misleading.

### IN-04: Two parallel blocked-artifact renderers

**File:** `app/api/tailoring.py:272-288` (`_findings_fragment`, Python-built HTML) vs
`app/web/templates/html/_cv_findings.html` (Jinja include)

**Issue:** the compile action's immediate blocked response and the page's blocked state
explain the same failure through two separate, independently-escaping code paths. Both
are safe today (`html.escape` on one side, Jinja autoescape on the other), but a change
to one will drift from the other.
**Fix:** have `_findings_fragment` render `_cv_findings.html` through the shared
`Jinja2Templates` env (the route already holds `templates`) and delete the hand-built
string.

### IN-05: Every "Download PDF" link in the compile history points at the newest `ok` artifact

**File:** `app/web/templates/html/tailoring.html:64`

**Issue:** each `history` row that is `ok` renders
`href="/listings/{{ listing_id }}/cv/pdf"`, but the route serves
`latest_for_listing(ok_only=True)` — the **newest** `ok` row, not the row the link sits
beside. With more than one `ok` compile, every historical "Download PDF" downloads the
same (newest) file, which is misleading in a surface whose whole point is retained
history (D-117).
**Fix:** either carry the row's artifact id into the URL and select by id via
`read_for_download(ok_only=True)`, or drop the per-row link and keep a single link on the
latest artifact.

### IN-06: The client-controlled `patch.listing_id` is never checked against the URL listing

**File:** `app/api/tailoring.py:433-439` (parse), `app/pipeline/tailor.py:271-273` (persist)

**Issue:** the round-tripped `TailoringPatch` is validated structurally but its
`listing_id` is never compared with the route's `listing_id`; the artifact row's
`listing_id` is server-derived (`listing.id`), so there is no cross-listing exposure, but
`cv_artifacts.patch_json` can be persisted with a `listing_id` that disagrees with the row
— an audit-trail inconsistency a forged POST can create at will.
**Fix:** validate `patch.listing_id == listing_id` after parsing (reject with 422), or
overwrite the field server-side before `compile_tailored`.

### IN-07: The `_allowed_for_entry` docstring understates and mislabels its fields

**File:** `app/verify/numbers.py:144`

**Issue:** the docstring says "its surviving bullets, label and org/title" — there is no
`label` field on `RenderedEntry` (the field is `dates`), and `location` is absent from
both the docstring and the set, which is what let CR-01 through review. A docstring that
enumerates the allow-set fields is a place a missed field should be impossible to hide.
**Fix:** correct it to name every source token the region legitimately carries (`dates`,
`org`, `title`, `location`, each bullet's `text` and `metrics`), and add `location` to the
set per CR-01.

---

**Reviewed:** 2026-09-24T23:45:00Z
**Reviewer:** the agent (gsd-code-reviewer)
**Depth:** standard
