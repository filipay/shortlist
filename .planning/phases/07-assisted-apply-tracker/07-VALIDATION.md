---
phase: "07"
slug: "assisted-apply-tracker"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-30"
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `07-RESEARCH.md` §Validation Architecture (L658–705). Task IDs in the
> Per-Task Verification Map are filled in by the planner once `07-*-PLAN.md` exists.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest==9.1.1` + `pytest-asyncio==1.4.0` (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `pythonpath = ["."]`) |
| **Quick run command** | `.venv/bin/python -m pytest tests/db/test_application_repo.py tests/verify/test_screening.py -x` |
| **Full suite command** | `.venv/bin/python -m pytest -q` (default lane is `-m 'not live and not latex'` per `pyproject.toml` `addopts`) |
| **Estimated runtime** | not separately timed; the feedback bound is the narrow `-x` file runs (seconds) |

---

## Sampling Rate

- **After every task commit:** run the narrow file(s) for the changed unit with `-x`
- **After every plan wave:** run the full suite (`.venv/bin/python -m pytest -q`)
- **Before `/gsd-verify-work`:** the full default lane must be green
- **Max feedback latency:** the narrow `-x` run (seconds), not the full suite
- **Not required for this phase:** the `latex` lane — Phase 7 adds no LaTeX work and the container-only Tectonic legs stay Phase 6's

---

## Per-Task Verification Map

Task IDs are placeholders until `07-*-PLAN.md` is written; each row is a requirement-level
contract the planner must place on a task, not a free-standing check.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-02-T1 | 07-02 | 2 | APPLY-01 | — | Apply page renders the ok artefact, apply link, stored gaps and stored drafts; no LLM call on GET | API | `.venv/bin/python -m pytest tests/api/test_apply_package.py -x` | ❌ W0 | ⬜ pending |
| 07-02-T1 | 07-02 | 2 | APPLY-01 | — | Page shows the "tailor first" gated (`package_state=gated`) state when no `ok` artefact exists | API | same file | ❌ W0 | ⬜ pending |
| 07-02-T2 | 07-02 | 2 | APPLY-02 | E-legal / Elevation | No submit route exists and no outbound POST form points at a portal | Static/API | `.venv/bin/python -m pytest tests/api/test_apply_package.py::test_no_submit_surface -x` | ❌ W0 | ⬜ pending |
| 07-01-T1 | 07-01 | 1 | APPLY-03 | V5 Input Validation | Record an application with a stage and notes; status validated against `APPLICATION_STATUSES` | Repository + API | `.venv/bin/python -m pytest tests/db/test_application_repo.py tests/api/test_applications_tracker.py -x` | ❌ W0 | ⬜ pending |
| 07-01-T2 | 07-01 | 1 | APPLY-04 | V4 Access Control | The `applied` transition refuses a non-`ok` artefact, stores `cv_artifact_id`, and the **display** read does not filter on `ok` | Repository | `.venv/bin/python -m pytest tests/db/test_application_repo.py::test_applied_requires_ok_artifact -x` | ❌ W0 | ⬜ pending |
| 07-01-T1 | 07-01 | 1 | APPLY-05 | Tampering | Every status change appends exactly one event in the same transaction; triggers abort UPDATE/DELETE | Repository + migration | `.venv/bin/python -m pytest tests/db/test_application_events.py tests/db/test_migration_contract.py -x` | ❌ W0 | ⬜ pending |
| 07-04-T2 | 07-04 | 2 | APPLY-06 | V5 Input Validation | Set/clear `next_action_at` (07-01-T3); needs-action orders overdue first, then upcoming, NULLs last | Repository + API | `.venv/bin/python -m pytest tests/db/test_application_repo.py::test_needs_action_ordering -x` | ❌ W0 | ⬜ pending |
| 07-01-T1 / 07-04-T1,-T2 | 07-01, 07-04 | 1, 2 | UI-04 | — | Tracker table renders; stage filter, needs-action view, search, inline history partial | API | `.venv/bin/python -m pytest tests/api/test_applications_tracker.py -x` | ❌ W0 | ⬜ pending |
| 07-03-T1 | 07-03 | 2 | D-125 | Prompt injection | Grounded answer passes; unknown evidence id warns; fabricated metric digit warns; valid paraphrase passes | Unit (pure) | `.venv/bin/python -m pytest tests/verify/test_screening.py -x` | ❌ W0 | ⬜ pending |
| 07-01-T1 | 07-01 | 1 | D-126 / Q7 | — | Migration 0006 creates `screening_drafts` + `apply_config` + triggers; head pinned | Migration | `.venv/bin/python -m pytest tests/db/test_migration_contract.py tests/db/test_orm_drift.py tests/db/test_no_pii_columns.py tests/db/test_reset_coverage.py -x` | ✅ exists (extend) | ⬜ pending |
| 07-03-T3 | 07-03 | 2 | D-119 / Q6 | — | The drafting call writes one `llm_calls` row, refuses at cap **before** the call, and returns transport errors as values | Unit/pipeline | `.venv/bin/python -m pytest tests/pipeline/test_draft_stage.py -x` | ❌ W0 | ⬜ pending |
| 07-05-T1 | 07-05 | 3 | APPLY-01 | — | The screening question list is user-editable from `/settings` and persists (`apply_config` singleton) | Repository + API | `.venv/bin/python -m pytest tests/db/test_apply_config_repo.py tests/api/test_settings_page.py -x` | ❌ W0 | ⬜ pending |
| 07-05-T2 | 07-05 | 3 | APPLY-01 / D-127 | XSS / Elevation | Drafted answers render with evidence and the unsupported warning; copy-only consumption; the confirm-guarded per-answer delete removes exactly one row | API | `.venv/bin/python -m pytest tests/api/test_apply_package.py -x` | ❌ W0 | ⬜ pending |
| 07-01-T1 / 07-02-T2 / 07-05-T2 | all | 1–3 | PLAT-03 | V4 Access Control | Every new route carries the `current_user` auth seam | Static | `.venv/bin/python -m pytest tests/test_auth_seam.py -x` | ✅ exists (extend) | ⬜ pending |
| 07-02-T1 / 07-05-T2 | 07-02, 07-05 | 2, 3 | UI guard | — | Every new template class has a CSS rule | Static | `.venv/bin/python -m pytest tests/test_stylesheet_coverage.py -x` | ✅ exists (extend) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/db/test_application_repo.py` — insert, transition, the applied gate, needs-action ordering, tracker read
- [ ] `tests/db/test_application_events.py` — append-only: exactly one event per transition in the same transaction; direct UPDATE/DELETE abort (mirror `tests/db/test_listing_events.py:124-163`)
- [ ] `tests/db/test_screening_draft_repo.py` — replace-all per listing in one SAVEPOINT; unknown listing; empty list clears
- [ ] `tests/verify/test_screening.py` — grounding: grounded passes; unknown id warns; fabricated digit warns; valid paraphrase passes; plus the CONVENTIONS rule-4 property test that mutates other entities' identifiers in
- [ ] `tests/pipeline/test_draft_stage.py` — stub backend; one call; one `llm_calls` row; cap refusal before the call; transport error records the class name only
- [ ] `tests/api/test_apply_package.py` — page states (ok / gated / no-artefact); draft action persists rows; no LLM on GET; no submit surface
- [ ] `tests/api/test_applications_tracker.py` — tracker table, stage filter, needs-action order, search, inline history partial, stage-transition refusals
- [ ] Extend `tests/db/test_migration_contract.py` (new item for `screening_drafts` + the `application_events` triggers; head → `0006`), `tests/db/test_orm_drift.py`, `tests/db/test_no_pii_columns.py` (JSON allow-list), `tests/db/test_reset_coverage.py` (`RESET_DELETE_ORDER` — `screening_drafts` is a child of `listings` and **must** be added or the guard fails), `tests/db/test_skeleton_boot.py` (head), `tests/test_auth_seam.py` (`EXPECTED_SEAM_ROUTES`), `tests/test_config.py` (the new drafting switch)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Apply package renders and downloads a **real compiled** ok PDF | APPLY-01 | No LaTeX engine in this environment (D-69); latex-marked tests are deselected | In the Tectonic container: tailor + compile a listing, then open `/listings/{id}/apply` and confirm the PDF block embeds and downloads |
| The copy-to-clipboard affordance and the "paste it yourself" posture read correctly | APPLY-02 / D-127 | Clipboard and perceived affordance are browser-only | Open the apply page, copy an answer, paste it into a scratch field, confirm nothing was auto-inserted anywhere |
| Tracker usability at phone width (375px) | UI-04 | Visual judgement | Load `/applications`, confirm the table degrades legibly, the stage filter and needs-action view are reachable, and the inline history expands without horizontal scroll |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < the narrow `-x` run
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
