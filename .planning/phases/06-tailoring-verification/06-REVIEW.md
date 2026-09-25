---
phase: 06-tailoring-verification
reviewed: 2026-09-25T16:00:12Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - app/verify/numbers.py
  - app/verify/base.py
  - tests/verify/test_numbers.py
  - tests/fixtures/verify/org_title_dates_collision_extract.txt
  - tests/fixtures/verify/org_title_dates_merge_extract.txt
  - tests/fixtures/verify/digit_bearing_header_extract.txt
  - tests/fixtures/verify/identical_dates_extract.txt
findings:
  critical: 0
  warning: 0
  info: 3
  total: 3
status: clean
---

# Phase 6: Code Review Report (scoped re-review — plan 06-11 / criterion E)

**Reviewed:** 2026-09-25T16:00:12Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** clean
**Diff scope:** `git diff 76f270b90725d71f8c14e05f51b3587fa9f6f8c7..HEAD -- app/verify tests/verify` (+ the four committed fixtures under `tests/fixtures/verify/`)
**Baseline:** `tests/verify` 89 passed on this tree; no persisted shape changed.

## Summary

This is an independent scoped re-review of the 06-11 gap-closure fix, run to satisfy
criterion E of `06-10-PLAN.md`. The prior review's **WR-02 (Warning)** — that an earlier
entry's bullet co-locating a later entry's org, title **and** date-range could still
hijack the later region and hard-fail check 4 on a correct CV — is **CLOSED**. I did not
take the fix's claims on faith: I read the diff, traced the bound by hand, reproduced the
pre-fix failure in-process by monkeypatching the old anchor, and re-ran the suite.

Verified claims (all six hold):

1. **Org-first anchor** — `_entry_lines` now requires
   `line.startswith(squash(org))` **and** `title in line` **and** date adjacency
   (`app/verify/numbers.py:173-178`). I reconstructed the pre-fix predicate
   (`org in line or title in line`) in-process against the WR-02 repro and confirmed
   the behavioural flip: old → `exp/acme-2019` candidates `['5','7']` (the false fail);
   new → `exp/globex-2018` absorbs only its own `['2019','2019','5']` and
   `exp/acme-2019` candidates `['7']`.
2. **Region-end bound is containment** — `any(needle in line for needle in needles)`
   (`numbers.py:350`), not equality, and never below the header
   (`end = max(position + 1, min(end, candidate_index))`, `:351`). Covers own-line
   headers, merged header/date lines and digit-bearing headers.
3. **Own date excluded BY POSITION** (`excluded_indices` from `position` or
   `position + 1`, `numbers.py:319-328`); own `location`/bullets by squash equality
   (`own_value_squashes`, `:329-333`, applied at `:348`). A shared identical date-range
   therefore no longer suppresses the bound (proven by the `identical_dates` test).
4. **IN-01 removed** — the unanchored branch is now exactly
   `allowed = _allowed_for_entry(entry)` (`numbers.py:301`); `_region_structured_cores(plan, "")`
   provably returned `set()` (`:245-247`), so this is behaviour-preserving.
5. **Version** — `VERIFIER_VERSION = "1.0.4"` exactly once (`app/verify/base.py:22`);
   no `1.0.3` / `1.0.2` remains in `app/` or `tests/`; `RegionReport` and
   `VerificationResult` shapes are unchanged.
6. **Prose** — the `_entry_lines` residual is now stated explicitly rather than hidden
   (`numbers.py:135-141`); the old "a bullet never carries the entry's own date-range"
   absolute guarantee is gone. Three minor stale-prose items remain (Info, below); none
   is a safety guarantee the code fails to deliver.

Anti-weakening (no regression — all reproduced green):

| Control | Result |
|---|---|
| Anchored surplus still hard-fails | `test_a_digit_bearing_or_identical_date_neighbour...` mutated `99` → `fail ['exp/acme-2018:99']`; `test_the_region_end_bound_never_shortens...` → `fail` |
| `page_budget`, `layout_ats` remain the ONLY warn-only checks | `text_checks.py` — `metric_containment` has both `_fail` and `_warn` (`:104-115`); `page_budget` (`:138`) and `layout_ats` (`:164`) are the only checks whose sole non-pass branch is `_warn` |
| `novel_metric_extract.txt` still fails | `verify_text(...)` → `metric_containment: fail ['exp/northwind-labs-2021:3.12']` |

Conventions: **1** — org-first is a template-positional discriminator, not arbitrary
substring containment, and the remaining lexical residual is documented; **2** — an
unanchored neighbour keeps `found=False` → visible `warn`, and any region truncation is
only reachable when at least one later entry is unanchored (so a pass can never be
silent); **3** — the literal WR-02 repro strings appear byte-for-byte in the new
fixtures; **4** — a new property test parametrizes the org/title/**date** dimension over
3 phrases × 2 corpora and asserts the needles; **5** — this review owns the verdict;
**6** — see Info items; **7** — the accept side is tested (collision, merge, digit-header,
identical-dates, own-content protection) alongside the reject side.

## Structural Findings (fallow)

No structural pre-pass findings were provided for this scoped re-review.

## Narrative Findings (AI reviewer)

No Critical/Blocker or Warning findings on the changed files. Three Info items.

## Info

### IN-01: `_entry_lines` docstring claims the region-end mechanism is unchanged

**File:** `app/verify/numbers.py:147-150`
**Issue:** "Only how a region's START is found changes: `region_token_report` still ends
a region at the next found start (or end-of-text for the last)". The same commit adds
the region-end bound (`:314-352`), so "only the start changes" and "still ends … at the
next found start" are now inaccurate and could steer a future reader away from the new
end logic. The bound *is* documented in `region_token_report`'s own docstring
(`:259-271`), so this is drift rather than a safety guarantee in the wrong place.
**Fix:** replace the sentence with a pointer, e.g. "Only the START predicate changes
here; `region_token_report` additionally bounds the end against an unanchored later
neighbour (`:314-352`) before falling back to the next found start."

### IN-02: Module docstring still describes the anchor without the org-first condition

**File:** `app/verify/numbers.py:17-25`
**Issue:** The module-level "Why the region segmentation is line-based" prose says a
region "is located on the entry's own HEADER line — the line carrying both
`squash(org)` and `squash(title)` that is also gated by the entry's date-range needle
…". It predates the org-first requirement and omits it. Relatedly, the sentence "a
short or common org name ('Meta' matching 'metadata')" (`:130-131`) overstates the fix:
`startswith("meta")` still matches a line beginning `metadata…`; the adjacent residual
paragraph (`:135-141`) correctly covers it, but the claim itself is imprecise.
**Fix:** mention `startswith(org)` in the module prose, and narrow the "Meta"/"metadata"
sentence to "an org name appearing mid-line" (the case the fix actually removes).

### IN-03: The documented org-first residual is not exercised by a test

**File:** `app/verify/numbers.py:135-141`; `tests/verify/test_numbers.py`
**Issue:** The residual "a line that literally begins with the org … IS taken as the
region start" is stated but no test pins that shape (contrast the split-header and
non-adjacent-date negative controls, which are pinned). Without it, a future tightening
of the anchor could silently change the residual without a failing test.
**Fix:** add a small case whose bullet line begins with the next entry's org and carries
its title and adjacent date-range, asserting the current disposition (region starts
there; the neighbour is bounded / the check does not hard-fail the correct CV), so the
residual's ceiling is locked.

---

_Reviewed: 2026-09-25T16:00:12Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
