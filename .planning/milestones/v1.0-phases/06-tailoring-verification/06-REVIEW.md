---
phase: 06-tailoring-verification
reviewed: 2026-09-30T11:50:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - app/verify/numbers.py
  - app/verify/base.py
  - tests/verify/test_numbers.py
  - tests/fixtures/verify/org_first_bullet_extract.txt
  - tests/fixtures/verify/org_first_merge_extract.txt
findings:
  critical: 0
  warning: 0
  info: 5
  total: 5
status: clean
---

# Phase 6: Code Review Report (criterion E closure — final state at `3b3842b`)

**Reviewed:** 2026-09-30T11:50:00Z
**Depth:** standard
**Files Reviewed:** 5 (final reviewed surface; `3b3842b` modified 2 of them)
**Status:** clean
**Criterion E verdict:** **SATISFIED at `3b3842b`.** No unresolved critical/blocker or warning finding on the changed files.

## Summary

This closes the criterion-E loop. `3b3842b` (`docs(verify): state anchor-gate residual
honestly, pin full-header ceiling`, +58/-6 across `app/verify/numbers.py` and
`tests/verify/test_numbers.py`) applies all four Info items from the `da06178` review.
I confirmed the commit is **prose + test only** — no production predicate changed — and
independently reproduced the claimed evidence.

- `.venv/bin/python -m pytest -q tests/verify/` → **97 passed**.
- Full `.venv/bin/python -m pytest -q` → **1533 passed, 14 deselected, 2 xfailed**.
- `ruff check app/verify` → **All checks passed**.
- `git diff --name-only da06178..3b3842b` → exactly the two files named above; no
  forbidden path touched.

## Finding resolution (IN-01..IN-04 from the `da06178` review)

### IN-01 — RESOLVED. The "never a false fail" overclaim is replaced with an honest, bounded statement.

`app/verify/numbers.py:173-183` now states the three-part position, and it matches the
code and my reproduced counterexample exactly:

1. **Per-entry monotone, and no silent skip.** "The gate is per-entry MONOTONE: it can
   only refuse an anchor, so a dropped or normalised separator on a real header degrades
   that entry to `found=False` and a visible `warn` naming it - never a silent skip."
   True: the guard is an added `continue` (`:213`), so an anchor can only be refused or
   stay; `found=False` feeds `check_metric_containment`'s `unanchored` branch, which can
   only yield `warn` or `fail`, never `pass` (`app/verify/text_checks.py:95-115`).
2. **Explicitly NOT a global no-false-fail guarantee.** "It is not, however, a global
   no-false-fail guarantee: if such a header loses its separator so the cursor does not
   advance past it, AND a line before it reproduces a later entry's full header, that
   later entry anchors early and absorbs the earlier entry's digit - the compound case
   is subsumed by the residual above, not a separate class." This is precisely the
   counterexample I raised, now stated rather than hidden.
3. **No new absolute/false guarantee.** I re-read the full paragraph and found no
   unconditional safety claim the code fails to deliver. "never a silent skip" is
   delivered in the sense that matters (a `found=False` region can never silently pass);
   in the compound case the disposition is a hard `fail`, which is the documented
   residual and still not a silent pass.

### IN-02 — RESOLVED. `cv.tex.jinja:58` → `:61`.

`app/verify/numbers.py:147` now cites `cv.tex.jinja:61`. Confirmed:
`app/latex/templates/cv.tex.jinja:61` is the header line
`\noindent\textbf{\VAR{entry.org}} --- \textit{\VAR{entry.title}} \hfill \VAR{entry.dates}\\`.

### IN-03 — RESOLVED. The module docstring now names the separator conjunct.

`app/verify/numbers.py:21-22`: "the line carrying `squash(org)` first, `squash(title)`,
and the org/title separator (a dash run between them), that is also gated by the entry's
date-range needle …". Accurate and complete.

### IN-04 — RESOLVED (with one minor prose nit, IN-05). The ceiling is now pinned.

New test `test_a_bullet_reproducing_a_full_header_is_the_documented_hard_fail_ceiling`
(`tests/verify/test_numbers.py:1142`) is non-vacuous and correct:

- The injected bullet opens `Acme --- Senior Engineer 2019-01 -- 2019-12 delivered 99
  platform` — it carries org, separator, title and an adjacent date-range, so the gate
  accepts it as B's region start (this is the documented residual).
- It asserts `[report.found for report in reports] == [True, True]`, `check.status ==
  "fail"` (explicitly not `warn`), and `"exp/acme-2019:99" in check.offending`.
- I reproduced the mechanics: B's region is `found=True` with candidates `['99','7']`;
  `99` is **not** in B's `allowed` (B's fields are org/title/dates/bullet `Led 7 people`)
  while it **is** in A's `allowed` (the bullet belongs to A) — so the injection creates a
  genuinely ungrounded digit in B's region, and the hard `fail` disposition is real.
- It breaks if the disposition is downgraded to `warn`, or if the anchor is tightened to
  reject a full-header reproduction (either would make B anchor at its real header and
  leave `99` grounded in A). See IN-05 for the docstring wording.

## Scope and hygiene (verified)

| Check | Result |
|---|---|
| `tests/golden/base.rendered.tex`, render path, `app/latex/templates/cv.tex.jinja`, `app/domain/tex.py`, `alembic/` vs `da06178` | untouched (empty diff) |
| Alembic head | unchanged by this work; repo head is `0005` (pre-existing, added by the skills-grouping quick task — the 06-VERIFICATION "0004" is stale, not a regression here) |
| `ruff check app/verify` | clean |
| `ruff check app/verify tests/verify` | 5 pre-existing errors only (`I001 test_numbers.py:10`, `E501 :524/:578/:686`, `I001 test_text_checks.py:9`); none introduced by `da06178` or `3b3842b` (E501 lines exist at parent `69ecb82`; import blocks unchanged; `test_text_checks.py` untouched) |
| Focused / full test suites | 97 passed / 1533 passed, 14 deselected, 2 xfailed |

## Critical / Blocker

None.

## Warnings

None.

## Info

### IN-01 — RESOLVED (see above)
### IN-02 — RESOLVED (see above)
### IN-03 — RESOLVED (see above)
### IN-04 — RESOLVED (see above)

### IN-05: The new ceiling test's docstring says "breaks if the gate is later relaxed" — inverted

**File:** `tests/verify/test_numbers.py:1140-1141`
**Issue:** The docstring claims "This pins the discriminator's known ceiling: the test
breaks if the gate is later relaxed". Relaxing the gate (removing the separator conjunct)
does **not** break the test — I simulated a gate-less `_entry_lines` on this exact
scenario and it still returns `fail ['exp/acme-2019:99']`, because the full-header bullet
anchors either way. What the test actually pins is the **disposition** (hard `fail`, not
`warn`); it breaks if that is downgraded, or if the anchor is tightened to reject a
full-header reproduction. The claim is therefore inverted, not a production defect.
**Fix:** reword to "the test breaks if a full-header reproduction is downgraded to a
warn, or if the gate is tightened to reject it."

---

_Reviewed: 2026-09-30T11:50:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
