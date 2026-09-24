---
phase: 06-tailoring-verification
reviewed: 2026-09-24T18:20:00Z
depth: standard
files_reviewed: 43
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
  critical: 1
  warning: 3
  info: 5
  total: 9
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-09-24T18:20:00Z
**Depth:** standard
**Files Reviewed:** 43
**Status:** issues_found

## Summary

Phase 6 lands the tailoring + verification half of the core loop and does the hard
architectural things right: the patch schema genuinely carries no field that reaches
the PDF, `apply_patch` is all-or-nothing and pure, the spend guard is reserve-then-call,
the `ok`-only artifact predicate is enforced in SQL on both accessors and again at the
route, and every route carries the auth seam. The security posture (no path from request
text to a filesystem path, Pydantic `extra="forbid"` on the round-tripped patch, frozen
system prompt, Jinja autoescape as the only escaping) held up under direct attempts to
break it.

The defects found are concentrated in the Layer-2 metric-containment check and in the
tailoring control surface:

- **One Critical**: `metric_containment` scores every digit that follows the last
  experience entry — which includes the whole Skills block and any footer — against that
  entry's facts. A digit-bearing skill label is therefore a hard **fail**, permanently
  blocking an otherwise valid CV (recovery is a fresh tailor, which reproduces it). This
  is reproduced below with a one-line mutation of the committed fixture.
- **Three Warnings**: the compile route ignores the `tailoring_enabled` off switch
  (contradicting its own Settings contract); bullet-targeting ops accept *any* fact id,
  so a `drop_bullet` on a skill id silently no-ops while writing a change-log entry that
  claims it happened; and the date-like exclusion is document-wide rather than
  region-scoped, diverging from D-113 and weakening check 4.

No Critical security vulnerability (injection, traversal, secret, auth bypass) was
found. `critical` here is used as the severity tier; it is equivalent to a BLOCKER.

## Critical Issues

### CR-01: `metric_containment` blocks valid CVs whose Skills block contains a digit

**File:** `app/verify/numbers.py:170-172` (region end), `app/verify/numbers.py:123-132`
(`_allowed_for_entry`), `app/verify/text_checks.py:82-98` (the check)

**Issue:** Regions are cut only at the *next entry's* org line, and the last entry's
region runs to end-of-text (`end = min(later) if later else len(lines)`). The extracted
text after the final entry contains the entire Skills section (`skill.group` / `skill.label`
are rendered by `app/latex/templates/cv.tex.jinja`), the section heading, and any footer.
`_allowed_for_entry` only enumerates that entry's own bullets/dates/org/title, never the
section's skills. Any digit in that trailing content is therefore a candidate whose token
is absent from `allowed`, producing a **hard fail** on `metric_containment` (check 4 is a
blocking check, `app/verify/text_checks.py:82-98`).

Reproduced against the committed stand-in fixture — changing one skill label to a
digit-bearing, extremely common value:

```
$ python -c "... base.replace('infrastructure Terraform','cloud AWS S3') ..."
entity_present      pass []
metric_containment  fail ['exp/northwind-labs-2021:3']   # <-- the '3' in 'AWS S3'
...
passed: False
```

`AWS S3`, `Python 3`, `C++17`, `ISO 27001`, `EC2` are ordinary CV content, so this is not
a corner case. The failure is fail-closed and unrecoverable via the UI (D-118's recovery
is "generate a fresh tailoring", which re-runs the same check), so the phase's core
deliverable — preview and download the verified CV — is dead for any such CV. The
committed fixtures do not exercise it because the stand-in's Skills block has no digits.

**Fix:** exclude the plan's non-entry structured content from candidates the same way
dates are excluded, so only entry-owned numbers are ever scored. Compute a global
structured-token set once and union it into every region's `allowed`:

```python
# app/verify/numbers.py
def _structured_cores(plan: RenderPlan) -> set[str]:
    cores: set[str] = set()
    for section in plan.sections:
        cores |= set(digit_cores(section.title))
        for skill in section.skills:
            cores |= set(digit_cores(skill.group))
            cores |= set(digit_cores(skill.label))
    return cores

# inside region_token_report, when building each report:
allowed = _allowed_for_entry(entry) | _structured_cores(plan)
```

(Alternatively, bound the final region at the start of the next section heading. The
`allowed` union is the smaller, more robust change and keeps the "novel metric inside an
entry's own bullets" property intact.)

## Warnings

### WR-01: `POST /cv/compile` ignores `tailoring_enabled`

**File:** `app/api/tailoring.py:406-474` (compile route); contract at `app/config.py:193-201`

**Issue:** The Settings field's own contract is explicit: *"`False` makes the tailoring
surface refuse before any model call or filesystem read — zero `llm_calls` rows, zero
`cv_artifacts` rows."* The page (`tailoring_skip_reason`), the generate route
(`app/api/tailoring.py:356-357`) and `tailoring_skip_reason()` all honour the switch, but
the compile route does not check it anywhere. A round-tripped `patch_json` POSTed directly
to `/listings/{id}/cv/compile` still renders, compiles and **writes a `cv_artifacts`
row** while the operator has turned tailoring off.

**Fix:** after the listing lookup, before parsing the patch, add:

```python
if not settings.tailoring_enabled:
    return _error_fragment(
        TAILOR_SKIP_DISABLED, TAILOR_SKIP_LABELS[TAILOR_SKIP_DISABLED], 409
    )
```

### WR-02: Bullet-targeting ops accept any fact id, silently no-op, and record a phantom change

**File:** `app/domain/cv.py:607-627` (`_validate_patch` step 1), effect at
`app/domain/cv.py:737-793` (`_build_plan` / `_ordered_bullets`)

**Issue:** Step 1 grounds every referenced id against `set(iter_fact_ids(facts))`
(`app/domain/cv.py:307-322`), which also yields section, entry, **skill**, org, title and
gap ids. So `drop_bullet(bullet_id="skill.python", reason=...)`,
`reweight_bullet(bullet_id="sec.skills", ...)` and `move_bullet(bullet_id="exp/...")`
validate cleanly, then no-op in `_build_plan` — while still emitting a `ChangeRecord`
(`app/domain/cv.py:721-734`). Reproduced:

```
accepted drop of a skill id; changes: [ChangeRecord(op='drop_bullet', target_id='skill.python', detail='x')]
bullet count unchanged: 3
accepted reweight of a section id; changes: [ChangeRecord(op='reweight_bullet', target_id='sec.skills', detail='2.0')]
```

`check_bullet_conservation` (`app/verify/plan_checks.py:105-130`) cannot catch it because
the id is neither a fact bullet nor a plan bullet. The change log TAIL-08 relies on for
honesty therefore reports a drop/reweight that never occurred.

**Fix:** for the four bullet ops, ground `bullet_id`/`before_id` against the bullet-id set,
not the full fact-id set:

```python
bullet_ids = {b.id for e in facts.all_entries() for b in e.bullets}
...
for op in patch.ops:
    for name in ("bullet_id", "before_id"):
        value = getattr(op, name, None)
        if isinstance(value, str) and value not in bullet_ids:
            raise UnknownIdError(f"{name} {value!r} is not a bullet id")
```

### WR-03: The date-like exclusion is document-wide, not region-scoped (D-113 divergence)

**File:** `app/verify/numbers.py:148-153` (build `excluded`), applied at
`app/verify/numbers.py:173`

**Issue:** The docstring (and D-113) promise that an entry's region excludes *that entry's*
date cores. The implementation unions **every** entry's date cores and every page-number
line into one global `excluded` set and subtracts it from every region. A token that is a
novel artefact in region A but happens to equal any other entry's year or month is silently
excluded. Reproduced with two entries (A: 2021-03..2024-09, B: 2019-01..2020-12) and a
text in which region A emits `2019` (not in A's source facts):

```
metric_containment pass offending: []
```

That is a false negative in the exact check whose job is to catch a number the renderer
introduced, so the defence-in-depth guarantee is weaker than documented.

**Fix:** keep the union for *page-number lines* (genuinely document-wide), but subtract
date cores per region:

```python
date_excluded = date_like_cores_for_entry(entry)
candidates = [
    core for core in digit_cores(region_text)
    if core not in date_excluded and core not in layout_excluded
]
```

## Info

### IN-01: The "section lost all entries" guard is unreachable dead code

**File:** `app/domain/cv.py:664-666`, `app/domain/cv.py:775-776`

**Issue:** `_build_plan` raises `InvalidPatchError("section ... lost all its entries")`
when `section.entries and not entries`, but `entries` is a 1:1 comprehension over
`section.entries`, so it can never be empty when the source is non-empty (the branch is
marked `# pragma: no cover`). No op targets entries, so D-106's "a section losing all
entries" invariant is not actually enforced by any reachable path — it is only asserted in
a comment.

**Fix:** either delete the branch and state in `_validate_patch` that no current op can
empty a section (with the guard to be added alongside the first op that can), or keep the
branch and drop the dead-code claim. Leaving both an unreachable raise and a comment
claiming enforcement is misleading.

### IN-02: A spend-cap refusal is surfaced as a generic 502 "tailoring failed"

**File:** `app/pipeline/tailor.py:200-215` (refusal returns `None`), `app/api/tailoring.py:379-384`

**Issue:** `tailor_listing` returns `None` both for a budget refusal and for a model
failure, and the generate route maps every `None` to `data-error="tailoring_failed"` with
HTTP 502. The operator cannot tell "the daily cap refused this" from "the model returned
garbage", even though the refusal is already recorded with the `budget_exceeded` marker.

**Fix:** return a small result value (or raise a typed refusal) distinguishing the two, and
map the cap case to a 429/409 fragment naming the 24 h ceiling.

### IN-03: `verify_text` derives `verifier_version` through `model_fields`

**File:** `app/verify/text_checks.py:201`

**Issue:** `verifier_version=VerificationResult.model_fields["verifier_version"].default`
re-reads the field default where the module already exports the constant
`VERIFIER_VERSION` (`app/verify/base.py:22`) that `compile_tailored` uses for the merged
result (`app/pipeline/tailor.py:385`). The roundabout lookup breaks if the field is ever
renamed.

**Fix:** `verifier_version=VERIFIER_VERSION` (importing it from `app.verify.base`).

### IN-04: A raised backend exception skips the audit row and escapes as a 500

**File:** `app/pipeline/tailor.py:217-242`, `app/api/tailoring.py:370-378`

**Issue:** `tailor_listing`'s docstring says it "never raises for a model failure", but the
`complete_structured` call sits inside the `try` with only `_release()` in `finally`; a
raise (transport error) propagates to the route, which does not catch it — yielding a 500
and, contrary to the module's "every call writes exactly one audit row" contract, no
`llm_calls` row for the attempt. In practice `app/llm` returns values, so this is latent.

**Fix:** wrap the call so any exception is recorded as one `llm_calls` row with
`status="error"` and surfaced as a value, then re-raise or return `None` per the route's
handling.

### IN-05: Two parallel blocked-artifact renderers

**File:** `app/api/tailoring.py:272-288` (`_findings_fragment`, Python-built HTML) vs
`app/web/templates/html/_cv_findings.html` (Jinja include)

**Issue:** the compile action's immediate blocked response and the page's blocked state
explain the same failure through two separate, independently-escaping code paths. Both are
safe today (Python uses `html.escape`, Jinja autoescapes), but a change to one will drift
from the other.

**Fix:** have `_findings_fragment` render `_cv_findings.html` through the shared
`Jinja2Templates` env (the route already has `templates`), deleting the hand-built string.

---

**Reviewed:** 2026-09-24T18:20:00Z
**Reviewer:** the agent (gsd-code-reviewer)
**Depth:** standard
