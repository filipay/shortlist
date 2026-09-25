---
phase: 06-tailoring-verification
reviewed: 2026-09-25T09:44:04Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - app/api/tailoring.py
  - app/pipeline/tailor.py
  - app/verify/base.py
  - app/verify/numbers.py
  - tests/api/test_tailoring_generate.py
  - tests/fixtures/verify/digit_location_extract.txt
  - tests/pipeline/test_tailor_stage.py
  - tests/verify/fixtures.py
  - tests/verify/test_numbers.py
  - tests/verify/test_text_checks.py
findings:
  critical: 1
  warning: 1
  info: 7
  total: 9
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-09-25T09:44:04Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

This is an incremental re-review scoped to the files changed since the prior review
commit `cea6f3e` (i.e. the 06-08 CR-01/CR-02 plan and the 06-09 WR-01 plan). The
prior review's 44-file scope is preserved by reference; findings in unchanged files
are carried forward where still valid.

**Prior findings status:**

- **Prior CR-01 (digit-bearing `location` hard-failed check 4) — CLOSED.** Verified
  independently: `_allowed_for_entry` now folds `entry.location` into that entry's
  own `allowed` set (`app/verify/numbers.py:175-176`), and `allowed`-only (never
  `excluded`) is the correct asymmetry. A reproduced entry with `location="Dublin 2"`
  yields `candidates=['2']`, `allowed=['01','2','2020','2021']`, `check_metric_containment=pass`.
- **Prior CR-02 (org-substring region anchor) — NOT CLOSED.** The *literal* original
  reproduction (an earlier bullet naming only the later employer) is fixed, but the
  defect class persists: the anchor still substring-matches org **and** title, so a
  bullet containing **both** hijacks the later entry's region start and bleeds its
  digits. Reproduced below; re-raised as **CR-01**.
- **Prior WR-01 (raised transport error escapes as a bare 500, no audit row) — CLOSED.**
  `tailor_listing`'s `except` (`app/pipeline/tailor.py:243-256`) writes one
  `purpose="tailor"`, `status="error"`, `run_id=None` row with the exception class
  only, logs the class only, returns `None`, and retains `finally: _release()`. The
  route's `patch is None` branch (`app/api/tailoring.py:387-392`) is the typed 502
  `data-error="tailoring_failed"`. Confirmed by the committed tests and by reading
  the current source.
- **Prior IN-07 (understated `_allowed_for_entry` docstring) — CLOSED.** The docstring
  and the set now both name `dates`, `org`, `title`, `location`, and each bullet's
  `text`/`metrics`.
- **Prior IN-01..IN-06 — still open** (unchanged code, carried forward below).

**New in this pass:** the residual hard-fail above (CR-01, Critical), one Warning
(check 4 silently skips regions it cannot anchor, so a fabricated digit there is not
caught), and one new Info (the new `except` scope can write an audit row for a call
that was never attempted). The focused lane is green:
`tests/verify tests/pipeline/test_tailor_stage.py tests/api/test_tailoring_generate.py
tests/api/test_tailoring_review.py tests/test_import_discipline.py` → **105 passed**.

Severity note: `critical` here is the severity tier equivalent to a BLOCKER.

## Prior Findings Resolution

| Prior ID | Status | Evidence |
|---|---|---|
| CR-01 (`location` digit hard-fail) | **Closed** | `app/verify/numbers.py:175-176`; independent repro passes |
| CR-02 (org-substring mis-anchor) | **Not closed** | residual reproduced; see CR-01 below |
| WR-01 (raise escapes, no audit row) | **Closed** | `app/pipeline/tailor.py:243-256`; `app/api/tailoring.py:387-392` |
| IN-01 (cap refusal looks like model failure) | Open | carried as IN-01 |
| IN-02 (`verify_text` indirect version) | Open | carried as IN-02 |
| IN-03 (`cv.py` unreachable "lost all entries") | Open | carried as IN-03 |
| IN-04 (two blocked-artifact renderers) | Open | carried as IN-04 |
| IN-05 (history links collide on newest `ok`) | Open | carried as IN-05 |
| IN-06 (`patch.listing_id` never checked) | Open | carried as IN-06 |
| IN-07 (allow-set docstring) | **Closed** | `app/verify/numbers.py:163-171` |

## Critical Issues

### CR-01: A bullet carrying both the next entry's org and title still hijacks that entry's region and hard-fails check 4 (residual CR-02)

**File:** `app/verify/numbers.py:151-156` (the anchor predicate), consumed at
`app/verify/numbers.py:246-270`, checked at `app/verify/text_checks.py:82-98`

**Issue:** The 06-08 fix replaced the org-only anchor with an org-**and**-title anchor
(`if org_needle in line and title_needle in line`, line 154), but both needles are
still naked squashed substrings. A bullet in an earlier entry that contains **both**
a later entry's org and its title still matches first, so `_entry_lines` returns that
bullet line as the later entry's region start. The earlier entry's trailing bullets
are then pulled into the later region as surplus candidates and `check_metric_containment`
returns `fail` on an otherwise-correct CV. This is the same class and the same
consequence as the original CR-02: a blocking check fails correct content and the only
recovery (D-118's fresh tailor) deterministically re-runs the same predicate, so the
preview/download path is dead for the affected CV.

Reproduced against the current code (two roles at the same employer, the earlier
bullet a promotion narrative):

```
entry A = exp/acme-2018  "Acme" / "Engineer" / 2018-01 -- 2018-12
  bullets: ["Partnered with Acme's Senior Engineer team to cut 5 incidents",
            "Mentored 3 juniors"]
entry B = exp/acme-2019  "Acme" / "Senior Engineer" / 2019-01 -- 2019-12
  bullets: ["Led 7 people"]

regions: exp/acme-2018 found=True  cand=[]        allowed=['01','12','2018','3','5']
         exp/acme-2019 found=True  cand=['5','3','7'] allowed=['01','12','2019','7']
check_metric_containment: fail ['exp/acme-2019:3', 'exp/acme-2019:5']
```

Entry B's region started at line 2 (A's bullet, which contains `acme` and
`seniorengineer`) instead of its real header at line 4, so A's digits `5` and `3`
became B's surplus candidates. A bullet mentioning the employer and a title word
("Acme's Senior Engineer team", "promoted to Senior Engineer at Acme") is ordinary CV
prose, and titles like `Engineer`/`Manager`/`Analyst` are common, so this is not
exotic. The authored regression test (`test_a_bullet_naming_a_later_employer_does_not_bleed_into_its_region`)
passes only because its bullet names the employer **without** the title.

**Fix:** add a third, structural discriminator that a bullet cannot satisfy. The
committed extraction places the entry's date-range on the line carrying org+title or
the line immediately after it (`tests/fixtures/verify/base_extract.txt:5-6`), while a
bullet never has the entry's own date-range adjacent. Require the dates needle on the
candidate line or its successor:

```python
def _entry_lines(entries: list[RenderedEntry], lines: list[str]) -> list[int]:
    squashed_lines = [squash(line) for line in lines]
    positions: list[int] = []
    cursor = 0
    for entry in entries:
        org_needle = squash(entry.org)
        title_needle = squash(entry.title)
        dates_needle = squash(entry.dates)
        found = -1
        if org_needle and title_needle and dates_needle:
            for index in range(cursor, len(lines)):
                line = squashed_lines[index]
                next_line = squashed_lines[index + 1] if index + 1 < len(lines) else ""
                if (
                    org_needle in line
                    and title_needle in line
                    and (dates_needle in line or dates_needle in next_line)
                ):
                    found = index
                    break
        positions.append(found)
        if found >= 0:
            cursor = found + 1
    return positions
```

This was checked against the committed `base_extract.txt` (still finds the header),
the residual reproduction above (now `[0, 4]`), and a wrapped header (still `-1`,
the accepted skip). Add a regression case: two entries at the same employer where the
first entry's bullet names both the employer and the later title must keep each
entry's metrics inside its own region, while `novel_metric_extract.txt` still fails.

## Warnings

### WR-01: Check 4 silently skips an entry whose org+title header is not on one extraction line, so a fabricated digit there is never caught

**File:** `app/verify/numbers.py:151` (the `if org_needle and title_needle` guard),
`app/verify/numbers.py:249-264` (`position < 0` → `found=False`, `candidates=[]`),
`app/verify/text_checks.py:86-88` (the `not report.found` skip)

**Issue:** The strict org-**and**-title anchor reports `found=False` whenever no single
squashed line carries both needles. In that case `region_token_report` emits an empty
candidate list and `check_metric_containment` skips the region entirely. This is the
safe direction for false positives (no more CR-02 mis-location), but it is a silent
false **negative** in the one blocking check whose job is to catch a number the
renderer introduced: a fabricated digit inside a skipped region is not reported.

Two reachable triggers reproduced against the current code (fabricated `99` in the
region, check still `pass`):

```
D) RenderedEntry(title="")            + text "Acme --- \n2020-01 -- 2021-01\nReduced latency 99%"
   -> entry found=False, candidates=[], allowed=['01','2020','2021','40'], check=pass
   (`Org.name`/`Title.name` carry no min_length, so an empty or all-punctuation
    title name yields an empty `squash(title)` needle and disables the region.)

E) org="Acme Corporation", title="Senior Software Engineer", header wraps:
   "Acme Corporation --- Senior\nSoftware Engineer\n2020-01 -- 2021-01\nReduced latency 99%"
   -> entry found=False, candidates=[], check=pass
   (a long org+title wraps in the rendered PDF; the extractor emits two lines, neither
    of which carries both needles.)
```

The committed test `test_a_split_header_entry_is_reported_not_found_not_mislocated`
pins the split-header behaviour as a deliberate trade-off, but it does not surface
that the consequence is a skipped integrity check on realistic long-title content.
This should be an explicit, documented ceiling rather than an implicit one.

**Fix:** either (a) keep the strict anchor but treat `found=False` for an entry whose
`org`/`title` are present elsewhere in the text as a `warn` (not a silent skip) in
`check_metric_containment`, so the operator sees that the entry was not metric-checked;
or (b) fall back to a weaker but still collision-resistant anchor (e.g. require
`org_needle` at the start of the squashed line and the `---` separator, or the
dates-adjacency anchor from CR-01) before declaring the region absent. Do not restore
the org-only substring anchor — that is the CR-01/CR-02 defect.

## Info

### IN-01: A spend-cap refusal is surfaced as a generic 502 "tailoring failed"

**File:** `app/pipeline/tailor.py:206-221` (refusal returns `None`),
`app/api/tailoring.py:387-392`

**Issue:** `tailor_listing` returns `None` for a budget refusal, a model failure and
(now) a transport raise, and the generate route maps every `None` to
`data-error="tailoring_failed"` / HTTP 502. The operator cannot tell "the rolling-24h
cap refused this" from "the model returned garbage", even though the refusal row
already carries `BUDGET_EXCEEDED_MARKER`. **Fix:** return a small result value
distinguishing the cases and map the cap to a 429/409 fragment naming the 24 h ceiling.

### IN-02: `verify_text` derives `verifier_version` indirectly through `model_fields`

**File:** `app/verify/text_checks.py:201`

**Issue:** `verifier_version=VerificationResult.model_fields["verifier_version"].default`
re-reads the field default where the module already exports `VERIFIER_VERSION`
(`app/verify/base.py:22`). The indirection breaks silently if the field is renamed, and
it diverges from `compile_tailored`, which uses the constant
(`app/pipeline/tailor.py:405`). **Fix:** `verifier_version=VERIFIER_VERSION`.

### IN-03: The "section lost all its entries" guard is unreachable dead code

**File:** `app/domain/cv.py:792-793`

**Issue:** `_build_plan` raises `InvalidPatchError("section ... lost all its entries")`
when `section.entries and not entries`, but `entries` is a 1:1 comprehension over
`section.entries`, so it cannot be empty when the source is non-empty (branch marked
`# pragma: no cover`). No current op targets entries, yet the `_validate_patch` comment
implies the invariant is enforced. **Fix:** delete the branch and state that no current
op can empty a section (re-add with the first op that can), or drop the enforcement
claim in the comment.

### IN-04: Two parallel blocked-artifact renderers

**File:** `app/api/tailoring.py:272-288` (`_findings_fragment`, Python-built HTML) vs
`app/web/templates/html/_cv_findings.html` (Jinja include)

**Issue:** the compile action's immediate blocked response and the page's blocked state
explain the same failure through two independently-escaping code paths. Both are safe
today (`html.escape` on one side, Jinja autoescape on the other), but a change to one
will drift from the other. **Fix:** render `_cv_findings.html` through the shared
`Jinja2Templates` env and delete the hand-built string.

### IN-05: Every "Download PDF" link in the compile history points at the newest `ok` artifact

**File:** `app/web/templates/html/tailoring.html:64`

**Issue:** each `history` row that is `ok` renders `href="/listings/{{ listing_id }}/cv/pdf"`,
but the route serves `latest_for_listing(ok_only=True)` — the newest `ok` row, not the
row the link sits beside (`app/api/tailoring.py:512`). With more than one `ok` compile,
every historical "Download PDF" downloads the same (newest) file, misleading in a
surface whose point is retained history (D-117). **Fix:** carry the row's artifact id
into the URL and select by id via `read_for_download(ok_only=True)`, or keep a single
link on the latest artifact.

### IN-06: The client-controlled `patch.listing_id` is never checked against the URL listing

**File:** `app/api/tailoring.py:444-447` (parse), `app/pipeline/tailor.py:291-292`
(persist)

**Issue:** the round-tripped `TailoringPatch` is validated structurally but its
`listing_id` is never compared with the route's `listing_id`. The artifact row's
`listing_id` is server-derived (`listing.id`), so there is no cross-listing exposure,
but `cv_artifacts.patch_json` can be persisted with a `listing_id` that disagrees with
its row — an audit-trail inconsistency a forged POST can create at will. **Fix:**
validate `patch.listing_id == listing_id` after parsing (reject 422), or overwrite the
field server-side before `compile_tailored`.

### IN-07: The new `except` scope can write an audit row for a call that was never attempted

**File:** `app/pipeline/tailor.py:223-256`

**Issue:** the `try` wraps `build_tailoring_parts(...)` as well as
`backend.complete_structured(...)`. If the pure prompt assembly raises (e.g. an
attribute access on the listing object fails), the `except` still writes a
`purpose="tailor"`, `status="error"` `llm_calls` row and logs
`tailor_transport_error`, even though no request left the process. The module's contract
is "exactly one audit row per ATTEMPTED call"; this writes one for a non-attempt and
inflates the rolling-24h cap used by the next refusal decision. It is latent (prompt
assembly is pure and the listing is loaded), but the row is indistinguishable from a
genuine transport failure. **Fix:** build `parts` before the `try`, or narrow the
`except` to the `complete_structured`/`record_llm_call` region, so only an attempted
call is audited.

---

**Reviewed:** 2026-09-25T09:44:04Z
**Reviewer:** the agent (gsd-code-reviewer)
**Depth:** standard
