---
phase: 07-assisted-apply-tracker
reviewed: 2026-10-12T11:52:16Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - app/domain/cv.py
  - app/domain/schemas/_coerce.py
  - app/domain/schemas/ranking.py
  - app/domain/schemas/screening.py
  - app/web/templates/html/_application_row.html
  - assets/tailwind/input.css
  - static/vendor/app.css
  - tests/api/test_applications_tracker.py
  - tests/api/test_apply_draft_errors.py
  - tests/domain/test_coerce.py
  - tests/domain/test_screening_schema.py
  - tests/llm/test_salvage.py
findings:
  critical: 1
  warning: 1
  info: 2
  total: 4
status: issues_found
---

# Phase 07: Code Review Report (07-11 / 07-12 gap closure)

**Reviewed:** 2026-10-12T11:52:16Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Scope is the 07-11 tracker layout fix (G-07-5/G-07-6) and the 07-12 `{"item": ...}`
single-key-wrapper coercion (G-07-7), reviewed against base `118d8ed`.

The two functional changes themselves are sound:

- The tracker row now uses phase-scoped `tracker-note` / `tracker-actions` /
  `tracker-action` classes; the note cell wraps while retaining the full string in
  `title=`, and the action cell drops the inherited `white-space: nowrap`. The queue's
  `.listing-*` vocabulary is untouched, and the added tests are load-bearing (they
  fail on the pre-fix markup/CSS).
- The coercion helper is pure (stdlib only), the `extra="forbid"` posture and
  `TOLERATED_SCHEMA_ERRORS` are untouched, and `list_type` is correctly still not
  tolerated.

The serious finding is not in the Python logic: the committed stylesheet
`static/vendor/app.css` is **not reproducible** from its source `assets/tailwind/input.css`,
and the Docker runtime ships the freshly built stylesheet. A fresh build drops 35+
template classes that the app relies on, and the repo's own stylesheet-coverage guard
cannot see it because it reads the committed artifact. The coercion helper also carries
a prose guarantee (and a test name) that the code does not deliver.

## Critical Issues

### CR-01: `static/vendor/app.css` diverges from its Tailwind source; the Docker image ships an unstyled UI

**File:** `static/vendor/app.css:64-69` (the appended rules), `assets/tailwind/input.css` (missing rules)
**Issue:** The committed stylesheet is treated as the render of `assets/tailwind/input.css`
(`input.css` header: "every semantic class used in the templates is defined here so
Tailwind v4 emits a rule for it"), but it is not. 07-11 hand-appended the three
`tracker-*` rules into `app.css` instead of only editing the source and re-running the
CLI. Those three rules happen to also exist in `input.css`, so the tracker fix itself
survives a rebuild — but the hand-edit pattern masks a pre-existing divergence that this
change perpetuates.

Running the exact command the Dockerfile runs:

```
./node_modules/.bin/tailwindcss -i ./assets/tailwind/input.css -o /tmp/built-app.css --minify
```

proves the source does not produce the committed file. Classes used by live templates but
absent from a fresh build (all present only in the committed `app.css`):

`badge-stage-*` (all 8 tracker status badge colours, used by `_application_row.html`),
`answer-text`, `answer-warning`, `badge-score*`, `badge-flagged`, `badge-unranked`,
`listing-detail-link`, `next-overdue`, `detail-empty`, `detail-not-ranked`,
`detail-rationale`, `factor-table*`, `factor-absent`, `requirement-list`, `req-met`,
`req-partial`, `req-gap`, `ranking-strip`, `queue-sort`, `queue-threshold`,
`apply-link`, `apply-assurance`, `tailoring-empty`, `tailoring-review`, `cv-status`,
`cv-download`, `cv-generate`, `weights-form`, `weights-note`, `weight-grid`,
`weight-field`.

`Dockerfile` line 116 is `COPY --from=assets /app/static/vendor ./static/vendor`, so the
runtime image ships the **rebuilt** stylesheet, not the committed one — i.e. the deployed
UI loses the tracker status colours, the drafted-answer styling, the listing-detail /
factor / tailoring / apply / settings styling. Independently verified: the repo's own
`tests/test_stylesheet_coverage.py` (which scans every `class="..."` token in every
template and requires a selector in `static/vendor/app.css`) **fails** when pointed at the
freshly built file, for the classes listed above. It passes today only because it reads
the committed artifact, so the green suite gives false assurance.

Secondary consequence of the same root cause: the appended `tracker-*` rules sit
**unlayered** at the end of the committed file, whereas a real build emits them inside
`@layer components`. Unlayered rules outrank `@layer utilities`, so dev and prod resolve a
utility/component conflict on these cells differently (currently latent — the template
puts no utility on those elements).

**Fix:** Move every component class the templates depend on into `assets/tailwind/input.css`
(the `@layer components` blocks), then regenerate `static/vendor/app.css` with the CLI
command above and commit the regenerated file. Do not regenerate first — the source is
missing the rules, so a rebuild-before-backfill would delete them. Consider adding a test
that runs the CLI over `input.css` and asserts the committed `app.css` is byte-identical
(this is the guard that would have caught this).

## Warnings

### WR-01: The unwrap is arity-based, so the docstring's "unknown key fails loudly" guarantee is false

**File:** `app/domain/schemas/_coerce.py:1-29`, `tests/domain/test_coerce.py:43-48`, `tests/domain/test_screening_schema.py:94-99`
**Issue:** `unwrap_single_key_mapping` unwraps on `len(value) == 1` alone; the wrapper key
name is never inspected. The module docstring states the opposite:

> Every OTHER shape (a scalar, a multi-key mapping, **an unknown key**) is returned
> untouched and fails loudly at pydantic

and the plan repeats the claim ("every other shape keeps failing loudly"). In fact
`{"anything": ["bul/x/1"]}` unwraps and validates (verified against
`ScreeningAnswer.model_validate`). The two tests that appear to pin this —
`test_an_unknown_single_key_wrapper_still_fails_loudly` and
`test_an_unrecognised_mapping_evidence_ids_still_fails_loudly` — both pass a *scalar*
value (`{"nope": 1}`), so they fail on the scalar, not on the unknown key; neither
exercises an unknown key with a list value. This is a fail-open in a helper that
processes untrusted model output, hidden behind a guarantee the code does not deliver
(CONVENTIONS rule 6), and it is exactly the "test the failure class, not the instance"
trap (rule 4).

Related: `coerce_mapping_list`'s docstring says "a `Mapping` -> `[value]` (a single
item-shaped object)", but because the unwrap runs first a **single-key** item-shaped
mapping is unwrapped to its value instead (e.g. `RankingResponse(requirements={"text":
"Five years Python"})` raises rather than becoming one `RequirementFit`).

The parent task frames the invariant as "stray/unknown keys must still raise". If that
reading is intended, promote this to a blocker and check the key name; otherwise the
docstrings and the two tests are wrong.

**Fix:** Either restrict the unwrap to the literal provider wrapper key
(`return value[key] if isinstance(value, Mapping) and len(value) == 1 and (key := next(iter(value))) == "item" else value`),
or correct the docstring to say "any single-key Mapping (whatever its key)" and replace
the two scalar-value tests with `{"nope": ["bul/x/1"]}`-shaped cases that pin the real
behaviour.

## Info

### IN-01: `TailoringPatch`'s top-level list fields carry no wrapper coercion

**File:** `app/domain/cv.py:515-527`
**Issue:** `TailoringPatch.ops`, `.gaps` and `.suggestions` are list-typed fields on a
schema routed through the same salvage path (`app/pipeline/tailor.py:245` →
`opencode_server._salvage`). If the provider wraps one of them as `{"item": [...]}`, the
call fails exactly as `answers`/`evidence_ids` used to. The 07-12 plan/summary honestly
scope the fix to "the five named list-typed fields", so this is not a broken guarantee —
it is residual exposure to the same documented provider class on the tailoring call.
**Fix:** Route these three fields through `coerce_mapping_list` too, for one behaviour on
every list-typed wire field, or record the exclusion explicitly in `_coerce.py`'s
docstring.

### IN-02: `unwrap_single_key_mapping` can loop forever on a self-referential Mapping

**File:** `app/domain/schemas/_coerce.py:27-29`
**Issue:** The `while isinstance(value, Mapping) and len(value) == 1` loop never
terminates if a Mapping's single value is itself (e.g. `d = {}; d["x"] = d`). This is not
reachable from the wire (payloads are `json.loads`-derived and cannot be cyclic), but the
helper is a shared pure-function exported in `__all__` and could be called with a
caller-constructed dict.
**Fix:** Bound the loop (e.g. stop if the next value `is value`) or note the acyclic
precondition in the docstring.

---

_Reviewed: 2026-10-12T11:52:16Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
