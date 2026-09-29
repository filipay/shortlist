---
phase: 260929-m1j
plan: "01"
status: complete
subsystem: cv
tags: [cv, extraction, rendering, skills]
completed: 2026-09-29
key-files:
  created: []
  modified:
    - app/cv/llm_extract.py
    - app/domain/cv.py
    - app/latex/templates/cv.tex.jinja
    - tests/cv/test_llm_extract.py
    - tests/domain/test_cv_ids.py
commits:
  - 49d8098
  - 3dbaecd
---

# Quick Task 260929-m1j: Grouped skills extraction + render

## One-liner

The CV extractor now carries a document-grounded `group` per skill, and the
Skills section renders one labelled line per group instead of one row per skill —
with the committed golden byte-identical.

## What changed

**Task 1 — wire schema (`app/cv/llm_extract.py`, `tests/cv/test_llm_extract.py`)** (commit `49d8098`)

- Added `DEFAULT_SKILL_GROUP = "skills"` as the single honest fallback group.
- Added `_ExtractedSkill(BaseModel)` (`label`, `group`, `extra="forbid"`) and widened
  `_ExtractedSection.skills` from `list[str]` to `list[_ExtractedSkill]`.
- Added a `@field_validator("skills", mode="before")` so every existing bare-string
  literal (`skills=["Python"]`) keeps validating and compiles to the default group.
- Added `_normalise_skills()` and used it in `_normalise_sections`, so the captured
  wire shapes (strings and `{label, group}` dicts) normalise uniformly.
- The prompt example is now the object shape and instructs the model to copy the
  document's own group labels verbatim, defaulting to a single `'skills'` group only
  when the document gives none.
- `_to_facts_dict` now grounds each emitted group with `_appears(...)`; an ungrounded
  group is dropped, reported, and replaced by `DEFAULT_SKILL_GROUP`. The default
  itself is never "dropped" (it is not a model claim), so an honest bare-string skill
  produces no spurious drop line.
- Tests: the real-shaped store now asserts every bare-string skill carries
  `DEFAULT_SKILL_GROUP`; a new grounded/ungrounded grouped fixture asserts
  `Languages` reaches the store and `Invented Group` is reported and falls back.

**Task 2 — grouped render (`app/domain/cv.py`, `cv.tex.jinja`, `tests/domain/test_cv_ids.py`)** (commit `3dbaecd`)

- Added the read-only `RenderedSection.skills_by_group` property (first-seen group
  order, skills in declaration order). It is a pure derivation over the carried-through
  `Skill` list, so `extra="forbid"` and every `skills=list(section.skills)` site are
  untouched, as is `apply_patch`.
- Replaced the template's skills block with an iteration over `skills_by_group` that
  emits one tabularx row per group: group label in column one, its labels joined by
  `", "` in column two (joined output still flows through the one `finalize` escape
  choke point).
- Added a targeted accessor + rendered-bytes test in `tests/domain/test_cv_ids.py`
  (the fact-equivalence lane does not cover skills).

## Deviations

None from the plan's behavior — with one deliberate refinement recorded for honesty:
the grounding check is skipped when the group already equals `DEFAULT_SKILL_GROUP`,
so the designated fallback is not reported as a fabricated value. Emitted groups that
differ from the fallback are still grounded and reported when ungrounded.

## Golden baseline

`tests/golden/base.rendered.tex` is **byte-identical** (git shows no modification).
The fixture has three groups with one skill each, so one-row-per-group renders exactly
as before; `tests/golden/test_render_bytes.py` passes, including the bytes read.

## Verification

Command:

    /workspace/job-search/.venv/bin/python -m pytest tests/cv/test_llm_extract.py tests/api/test_settings_cv_upload.py tests/domain/test_cv_ids.py tests/golden/test_render_bytes.py tests/verify/test_text_checks.py tests/verify/test_numbers.py -q

Result:

    174 passed in 6.41s

Lint (`/workspace/job-search/.venv/bin/python -m ruff check` on the changed Python
files): `All checks passed!`

No database column, migration, or dependency added; the `Skill.group` fact-store model
is unchanged.

## Self-Check: PASSED

- `app/cv/llm_extract.py`, `app/domain/cv.py`, `app/latex/templates/cv.tex.jinja`,
  `tests/cv/test_llm_extract.py`, `tests/domain/test_cv_ids.py` — present and modified.
- Commits `49d8098` and `3dbaecd` exist on `master`.
- Golden baseline unmodified.
