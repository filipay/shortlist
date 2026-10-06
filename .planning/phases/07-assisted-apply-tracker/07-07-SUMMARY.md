---
phase: 07-assisted-apply-tracker
plan: 07
subsystem: api
tags: [sqlalchemy, alembic, jinja2, screening, grounding, advisory-band, gap-closure]

# Dependency graph
requires:
  - phase: 07-assisted-apply-tracker
    provides: the screening grounding checker (07-03), the screening_draft_repo (07-03) and the apply answers region (07-05)
provides:
  - "Migration 0007: nullable screening_drafts.warnings_json (JSON) + band (String)"
  - "The checker's specific warnings and advisory band persist and survive to render"
  - "A flagged answer names its offender; a non-default band surfaces as explicitly advisory"
affects: [07-verification, 07-uat, screening, apply]

# Actuals (#2632)
actuals:
  tokens: 6596
  tasks: 2
  commits: 2
  plan_head_before: 2bbd3cc5641daa80991645ed5ec951b0861fa26a

tech-stack:
  added: []
  patterns:
    - "Persist the checker's specific finding, never re-derive it: the offender was dropped from the grounded set, so persistence is the only path that preserves it"
    - "Advisory-only band surfaced as a muted note with an explicit 'not a guarantee' clause; NULL/grounded render nothing"

key-files:
  created:
    - alembic/versions/0007_screening_draft_warnings.py
    - tests/api/test_apply_package_warnings.py
  modified:
    - app/db/models.py
    - app/db/repositories/screening_draft_repo.py
    - app/api/apply.py
    - app/web/templates/html/_screening_drafts.html
    - .planning/phases/07-assisted-apply-tracker/07-UI-SPEC.md
    - tests/db/test_migration_contract.py
    - tests/db/test_skeleton_boot.py
    - tests/db/test_no_pii_columns.py
    - tests/db/test_screening_draft_repo.py

key-decisions:
  - "G-07-3: warnings_json and band are PERSISTED on screening_drafts (migration 0007), not re-derived at render time — the unknown evidence id was deliberately dropped from the grounded evidence_json, so persistence is the only path that preserves the offender"
  - "G-07-3: the band renders only when present and non-default (grounded and NULL render nothing), as an explicitly advisory .field-note with a 'not a guarantee' clause; it never flips unsupported (D-125)"
  - "G-07-3: the specific-warning lines reuse the existing .answer-warning class and rely on Jinja autoescape alone (no |safe), so no new stylesheet token is introduced"

patterns-established:
  - "A checker finding that is computed once and dropped at persist time is lost forever; when the human needs it, store the sentence, not a re-derivation"

requirements-completed: [APPLY-01]

coverage:
  - id: D1
    description: "A flagged answer's stored warnings render one escaped line per finding, each naming its offender (the unknown evidence id and the novel number token)"
    requirement: APPLY-01
    verification:
      - kind: integration
        ref: "tests/api/test_apply_package_warnings.py#test_a_flagged_answer_names_each_specific_offender"
        status: pass
    human_judgment: false
  - id: D2
    description: "A non-default band renders as an explicitly advisory line ('not a guarantee'); a grounded band renders nothing"
    requirement: APPLY-01
    verification:
      - kind: integration
        ref: "tests/api/test_apply_package_warnings.py#test_a_flagged_answer_names_each_specific_offender"
        status: pass
      - kind: integration
        ref: "tests/api/test_apply_package_warnings.py#test_a_grounded_answer_renders_neither_warning_nor_band"
        status: pass
    human_judgment: false
  - id: D3
    description: "A NULL-specifics unsupported row still renders the generic caution (fail-closed); the repository round-trips warnings/band and degrades NULL to []/None"
    requirement: APPLY-01
    verification:
      - kind: integration
        ref: "tests/api/test_apply_package_warnings.py#test_a_null_specifics_flagged_row_still_renders_the_generic_caution"
        status: pass
      - kind: unit
        ref: "tests/db/test_screening_draft_repo.py#test_replace_round_trips_the_specific_warnings_and_band"
        status: pass
      - kind: unit
        ref: "tests/db/test_screening_draft_repo.py#test_a_draft_without_specifics_reads_back_empty_and_none"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-10-06
status: complete
---

# Phase 07 Plan 07: G-07-3 specific grounding findings + advisory band Summary

**A flagged screening answer now persists and renders the specific finding that flagged it — naming the unknown evidence id and the novel number token — and a non-default grounding band surfaces as an explicitly advisory note, leaving the generic caution as the fail-closed fallback.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-10-06T17:25:52Z
- **Completed:** 2026-10-06T17:33:30Z
- **Tasks:** 2
- **Files modified:** 11 (2 created, 9 modified)

## Accomplishments

- Migration `0007` adds two nullable columns to `screening_drafts` — `warnings_json` (the checker's human sentences, each naming its offender) and `band` (the advisory `GroundingBand`) — via `op.add_column`, with a symmetric `op.drop_column` downgrade. The head moves `0006 → 0007`; every head pin moved with it.
- `ScreeningDraft` and `screening_draft_repo` now carry the two fields through `_to_record`, `replace_for_listing` and `append_draft`; a NULL read degrades to `[]` / `None`, exactly as `evidence_json` already does.
- `draft_answers` maps each verdict's `warnings` and `band` onto the persisted input (nothing recomputed), and `_one_row` exposes `warnings` / `band` so the template never reads a repository object directly.
- `_screening_drafts.html` keeps the generic caution inside the unsupported branch and adds one escaped `.answer-warning` line per stored finding; a non-default band renders a `.field-note` "Advisory match band: … — a rough lexical signal, not a guarantee." line. Jinja autoescape remains the single escaping choke point — no `|safe`.
- `07-UI-SPEC.md` records the amendment (specific-finding lines + advisory band), stating plainly that the band is advisory and never a guarantee.

## Task Commits

Each task was committed atomically:

1. **Task 1: Persist warnings and band — migration 0007, model, repository, and the guard updates** — `455363d` (feat)
2. **Task 2: Map verdicts to the new columns and render the specific warning plus the advisory band** — `10547d0` (feat)

**Plan metadata:** (docs commit, follows this file)

## Files Created/Modified

- `alembic/versions/0007_screening_draft_warnings.py` — new: revision 0007 / down_revision 0006; adds nullable `warnings_json` + `band`; symmetric downgrade.
- `app/db/models.py` — `ScreeningDraft` gains the two nullable columns, mirroring the migration.
- `app/db/repositories/screening_draft_repo.py` — `ScreeningDraftInput`/`ScreeningDraftRecord` carry `warnings_json: list[str]` and `band: str | None`; `_to_record` coerces, both write paths persist them.
- `app/api/apply.py` — `draft_answers` passes `warnings_json=verdict.warnings` / `band=verdict.band`; `_one_row` exposes `warnings` and `band`.
- `app/web/templates/html/_screening_drafts.html` — per-finding warning lines + the advisory band line; generic caution retained.
- `.planning/phases/07-assisted-apply-tracker/07-UI-SPEC.md` — amended drafted-answers section (recorded, not silently widened).
- `tests/db/test_migration_contract.py` — head pins `0006 → 0007` (three sites) + new item 18 asserting both columns exist and are nullable.
- `tests/db/test_skeleton_boot.py` — pinned version tuple `("0006",) → ("0007",)`.
- `tests/db/test_no_pii_columns.py` — `warnings_json` added to the `screening_drafts` JSON allow-list (fact ids / digit tokens only, never PII).
- `tests/db/test_screening_draft_repo.py` — round-trip, fail-closed degradation and append-preserves-warnings coverage.
- `tests/api/test_apply_package_warnings.py` — new: both directions (named offender + non-default band vs grounded / NULL-specifics).

## Decisions Made

- **Persist, don't re-derive.** The unknown evidence id is dropped from the grounded `evidence_json` by construction, so any render-time re-derivation could never name it. The specific finding must cross the persist boundary to reach the human; migration 0007 is that path.
- **Advisory band is advisory-only.** It renders solely when present and non-default; the copy says "a rough lexical signal, not a guarantee" and the band never flips `unsupported` (D-125). `grounded` and NULL render nothing.
- **No new stylesheet token.** The specific findings reuse `.answer-warning` and the advisory line reuses `.field-note`, both already in the built stylesheet, so the stylesheet-coverage guard stays green without touching `app.css`.

## Deviations from Plan

None — the plan executed as written. (`app.css` was not modified; the plan's `files_modified` omitted it, and the chosen existing classes made that correct.)

## Issues Encountered

- The first draft of the new rendering test asserted the raw stored warning string `unsupported number '97'`. Jinja autoescape correctly renders the quotes as `&#39;`, so the assertion was updated to match the escaped output (`&#39;97&#39;`), which also documents that the finding crosses the one autoescape choke point. Test-only adjustment; no implementation change.

## Threat Flags

None — no new network endpoint, auth path, or file-access pattern. T-07-07-01 (no `|safe`; warnings render escaped), T-07-07-02 (the JSON allow-list pins `warnings_json` to fact ids / digit tokens) and T-07-07-03 (the band is labelled advisory, never a guarantee, never flips `unsupported`) are all satisfied. No packages installed (T-07-07-SC accepted).

## Verification Evidence

- Task 1 `<verify>`: `.venv/bin/python -m pytest -q tests/db/test_screening_draft_repo.py tests/db/test_migration_contract.py tests/db/test_skeleton_boot.py tests/db/test_no_pii_columns.py tests/db/test_orm_drift.py -x` → **39 passed**.
- Task 2 `<verify>`: `.venv/bin/python -m pytest -q tests/api/test_apply_package_warnings.py tests/api/test_apply_package.py tests/db/test_screening_draft_repo.py -x` → **43 passed**.
- Adjacent guards (including the stylesheet-coverage scan): `.venv/bin/python -m pytest -q tests/test_stylesheet_coverage.py tests/api/test_apply_package_warnings.py tests/api/test_apply_package.py tests/api/test_apply_draft_errors.py tests/pipeline/test_draft_stage.py tests/db/test_screening_draft_repo.py` → **60 passed**.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- G-07-3 is closed: a flagged answer names its offender, the advisory band is visible and explicitly advisory, and the generic fallback (NULL specifics) and clean-answer case both survive.
- All four Phase 07 gap-closure plans (07-06 … 07-09) are now executed; the phase re-verification can proceed.

---

*Phase: 07-assisted-apply-tracker*
*Completed: 2026-10-06*

## Self-Check: PASSED
