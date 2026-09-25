---
phase: 06-tailoring-verification
reviewed: 2026-09-25T12:03:18Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - app/verify/numbers.py
  - app/verify/text_checks.py
  - app/verify/base.py
  - tests/verify/test_numbers.py
  - tests/verify/test_text_checks.py
  - tests/fixtures/verify/org_title_collision_extract.txt
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 6: Code Review Report (scoped re-review — plan 06-10 / commits `c841b52`, `165d6c2`)

**Reviewed:** 2026-09-25T12:03:18Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found
**Diff scope:** `git diff 03b6fda3055ef053e2506f99c9a6303d0ee1f3ce..HEAD -- <six files>`
**Baseline:** full hermetic lane `1250 passed, 14 deselected, 2 xfailed` on this tree; `tests/verify` 74 passed.

## Summary

I independently reproduced the pre-fix failures and the post-fix passes rather than
trusting the SUMMARY. The two committed fixes are materially real:

- `_entry_lines` now gates a region start on **org AND title AND date-range adjacency**
  (`app/verify/numbers.py:159-178`) with a non-empty guard on all three needles.
- `check_metric_containment` collects every `report.found is False` region and returns a
  visible `warn` naming the entry, with `fail` precedence retained
  (`app/verify/text_checks.py:93-116`).

Pre-fix empirical check (old `app/verify/*.py` restored into a throwaway worktree, new
tests kept): `10 failed, 39 passed` — exactly the claimed Task-1 `8 failed, 1 passed`
and Task-2 `2 failed, 1 passed`. `novel_metric_extract.txt` still fails with
`exp/northwind-labs-2021:3.12`; the happy path, declared-drop, warn-only and version
controls are all intact.

However, the region anchor is **still lexical substring containment**, not a
discriminator free text cannot accidentally satisfy. I demonstrated a residual of the
CR-01 / ESC-06-A class: when an earlier entry's bullet line co-locates the later
entry's org, title **and** date-range (same line, or an extractor line-merge of a
bullet with the next header), the bullet still hijacks the later region and hard-fails
check 4 on a correct CV. The `_entry_lines` docstring's absolute claim
("a bullet never carries the entry's own date-range") and the property test's
"the whole lexical-collision class" claim are both overstated. This is raised as
**WR-02** (Warning), not as a re-open of the literal finding — the literal repro and
the common org+title-only class are genuinely fixed.

Per binding convention 5 ("no false guarantees in prose") and convention 4 ("test the
failure class"), the residual `warn`-only status means **the scoped fix is not fully
closed**; see the verdict table.

## Verification Asks (explicit)

### A. Does the three-needle guard make the collision class impossible?

**No — it narrows the class; it does not make it impossible.** A body bullet can still
satisfy all three needles if it co-locates the later entry's date-range on the same
line (or is merged/adjacent to the dates line). Reproduced against the current tree:

```
entry A = exp/globex-2018 "Globex Inc"/"Engineer"/2018-01 -- 2018-12
  bullet: "Partnered with Acme Senior Engineer 2019-01 -- 2019-12 to cut 5 incidents"
entry B = exp/acme-2019   "Acme"/"Senior Engineer"/2019-01 -- 2019-12
  bullet: "Led 7 people"

regions: exp/globex-2018 found=True candidates=[]
         exp/acme-2019  found=True candidates=['5','7']
metric_containment: fail ['exp/acme-2019:5']     <-- hard fail on a correct CV
```

Variant 2 needs no adversarial date prose at all — only an extractor line-merge of A's
last bullet with B's header line (the dual of the split-header case already accepted):

```
"Liaised with the Globex Inc Manager on 5 projects Acme Senior Engineer"
"2019-01 -- 2019-12"
-> exp/acme-2019 found=True candidates=['5','7'] -> fail ['exp/acme-2019:5']
```

So the answer to "is there still a lexical path where an earlier bullet naming a later
entry's org AND title hijacks that later region?" is **yes, with the additional
condition that the date-range is co-located**. That extra condition is what keeps this a
Warning rather than a Blocker: an org+title-only bullet no longer hijacks (the literal
finding), and the date-range string is a much narrower accidental match. It is still
not a discriminator that free text "cannot accidentally satisfy" (convention 1).

**Trade-off assessment (wrapped/split headers, non-adjacent dates → `found=False`):**
safe in the blocking direction — `found=False` is no longer a silent skip; check 4 emits
a `warn` and `passed` stays `True`, so a valid CV still renders/downloads. The cost is
detection strength: for a wrapped header, a fabricated digit now only warns and is not
blocked. This is strictly better than the pre-fix silent-pass and is the convention-2
disposition, so it is acceptable.

### B. Fail-closed behaviour of `check_metric_containment`

**Correct.** On an unanchorable region the entry id is collected into `unanchored`
(`app/verify/text_checks.py:95-99`) and the check returns
`_warn(..., offending=sorted(set(unanchored)))` (`:110-115`) — never a silent
`candidates=[]` pass. `fail` precedence is preserved: the surplus branch is evaluated
first (`:104-109`), so an anchored surplus still hard-fails and an unanchored region
cannot mask it. Verified by
`test_an_unanchorable_region_is_a_visible_warn_not_a_silent_skip`,
`test_a_fabricated_digit_in_an_unanchorable_region_is_not_reported_pass`, and
`test_an_unanchored_region_does_not_hide_an_anchored_surplus`.

### C. No check weakened / deleted / downgraded

**Correct.** `metric_containment` still hard-fails an anchored surplus
(`text_checks.py:104-109`); `novel_metric_extract.txt` still returns
`fail` with `exp/northwind-labs-2021:3.12` (unchanged test, green). `page_budget` and
`layout_ats` remain the only warn-only checks. `verify_text`'s
`passed = all(check.status != "fail" ...)` (`:212`) is unchanged, so a `warn` never sets
`passed=False` — confirmed by the `result.passed is True` assertion on the warn case and
by the unchanged `compile_tailored` call site (`app/pipeline/tailor.py:325, 409-412`).

### D. Tests genuinely test the failure class

**Mostly yes; the literal pre-fix counts are verified.** Restoring the old
`app/verify/*.py` against the new tests yields `10 failed`: Task-1 tests `8 failed,
1 passed` and Task-2 tests `2 failed, 1 passed`, matching the SUMMARY exactly. Negative
controls (`base_extract` happy path, `novel_metric_extract`, split-header, declared
drop, page-budget/layout warns) remain green. The committed fixture carries both repro
strings byte-for-byte (`grep -c` = 1 each;
`tests/fixtures/verify/org_title_collision_extract.txt:7-8`), and the first bullet line
provably contains both `squash("Acme")` and `squash("Senior Engineer")`
(`tests/verify/test_numbers.py:423-426`). **Gap:** the property test mutates only the
org+title dimension, never the date-range needle the discriminator actually depends on,
so it does not cover the discriminator's true failure class — see WR-02.

### E. Version provenance

**Correct — exactly one bump.** `VERIFIER_VERSION = "1.0.3"` at
`app/verify/base.py:22`; no `1.0.2` remains anywhere in `app/` or `tests/`, and Task 2
did not add a second bump.

### F. Other bugs / security / quality

No security issue in the changed files: `offending` carries ids and digit cores only,
`VerificationResult` keeps `extra="forbid"`, and the extraction is still persisted as a
sha256 only. No new findings at Blocker level. Two Info items below.

## Prior Findings Resolution

| Finding | Verdict | Evidence |
|---|---|---|
| **CR-01 / ESC-06-A** (bullet carrying a later entry's org AND title hijacks its region) | **CLOSED** (literal repro + common class); residual class raised as WR-02 | Old code restored + new tests → `test_a_bullet_embedding_a_later_entrys_org_and_title_does_not_bleed_into_its_region` fails; new code → `metric_containment == pass`. The 6 parametrized property cases fail pre-fix, pass post-fix. |
| **WR-01 / ESC-06-B** (unanchorable region silently skipped, fabricated digit invisible) | **CLOSED** | `app/verify/text_checks.py:95-115`; three new tests green; pre-fix both fail-closed tests returned `pass` (verified). |
| **Version (criterion E)** | **CLOSED** | `app/verify/base.py:22`; single bump. |
| **Literal fixture (criterion C/D)** | **CLOSED** | `tests/fixtures/verify/org_title_collision_extract.txt:7-8`; both strings byte-for-byte. |

## Critical Issues

None.

## Warnings

### WR-02: The region anchor is still lexical — a bullet can co-locate all three needles and hijack a later region (residual ESC-06-A class)

**File:** `app/verify/numbers.py:159-178` (anchor), `:128-131` (false guarantee);
`tests/verify/test_numbers.py:517-541` (overstated class claim)

**Issue:** The third needle is matched with the same naked substring test as the first
two — `dates_adjacent = dates_needle in line or (... dates_needle in squashed_lines[index + 1])`
(`numbers.py:169-171`). `squash` strips spaces/hyphens, so a bullet containing
`2019-01 -- 2019-12` squashes to `201901201912` and satisfies the discriminator. An
earlier bullet that names a later entry's org AND title AND carries its date-range
(same line, or a bullet line merged by the extractor with the next header, with the
dates line as successor) still starts the later region one line early and donates its
digit as a surplus candidate. This hard-fails check 4 on a correct CV; because D-118's
only recovery is a fresh tailor that re-runs the same predicate, preview/download stay
dead for that CV. Reproduced above (criterion A). This violates:

- convention 1 — the discriminator is substring containment over extracted text, not a
  structural boundary free text cannot accidentally satisfy;
- convention 5 — the `_entry_lines` docstring asserts "a bullet never carries the
  entry's own date-range on itself or its successor" (`numbers.py:129-131`), an absolute
  guarantee the code does not deliver;
- convention 4 — the property test is documented as covering "the whole lexical-collision
  class" (`test_numbers.py:524`) but never mutates the dates dimension, so the chosen
  discriminator's boundary is untested.

**Fix (either):**

1. Tighten the anchor to a structural boundary, e.g. require the squashed candidate
   line to **start** with `org_needle` (the template emits org first; a bullet embeds
   the org mid-line) in addition to the dates adjacency:

   ```python
   if (line.startswith(org_needle) and title_needle in line
           and (dates_needle in line
                or (index + 1 < len(lines) and dates_needle in squashed_lines[index + 1]))):
   ```

   or require the `---` header separator; or
2. If the dates-adjacency trade-off is to stand, (a) soften the docstring to state the
   residual explicitly (no absolute "never"), and (b) add a property case that mutates
   the bullet to embed org+title+**dates** and pins the (documented) disposition, so the
   ceiling is a tested, runtime-visible trade-off rather than an unstated one.

Note the residual is narrow and requires the extra date co-location; the literal
org+title-only class the finding named is genuinely fixed.

## Info

### IN-01: Dead operand in the unanchored branch of `region_token_report`

**File:** `app/verify/numbers.py:273`

**Issue:** `allowed = _allowed_for_entry(entry) | _region_structured_cores(plan, "")`.
`_region_structured_cores` squashes its argument and returns `set()` for the empty
string (`:239-241`), so the second operand is always empty — the call is dead and reads
as though structured content were being scoped to a region that does not exist.
**Fix:** `allowed = _allowed_for_entry(entry)`, or keep a one-line comment that no
region text exists to scope against.

### IN-02: Property-test per-region assertion uses substring membership

**File:** `tests/verify/test_numbers.py:530-532`

**Issue:** `assert str(earlier[2]) not in report.candidates` is a substring test over a
list, so a candidate `"141"` would satisfy `"41" not in ...` incorrectly and a candidate
`"41"` would fail it even when grounded. Use an exact membership test
(`str(earlier[2]) not in set(report.candidates)`). Minor; the surrounding
`check_metric_containment == "pass"` assertion carries the real signal.

---

_Reviewed: 2026-09-25T12:03:18Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
