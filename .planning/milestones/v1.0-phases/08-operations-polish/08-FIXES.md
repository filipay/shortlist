---
phase: "08"
slug: "operations-polish"
status: complete
created: "2026-10-14"
sources:
  - 08-REVIEW.md
  - 08-UI-REVIEW.md
test_lane: "PYTHONPATH=/workspace/job-search:/workspace/job-search/.venv/lib/python3.11/site-packages /tmp/opencode/gsdvenv13/bin/python -m pytest -m 'not live and not latex'"
suite_result: "1955 passed, 15 deselected, 2 xfailed, 0 failed"
---

# Phase 08 — Review Fixes

One row per finding from `08-REVIEW.md` (code review) and `08-UI-REVIEW.md` (UI
audit), with the change, the files, the commit and the test that carries the
finding's literal repro (CONVENTIONS rule 3). Commits are normal commits (hooks
enabled, never `--no-verify`), one per finding group.

## Fix register

| Finding | Severity | Change | Files | Commit | Test |
|---------|----------|--------|-------|--------|------|
| **CR-01** — cross-site destructive POST exposure + false docstring | Critical | Added `_same_origin_guard` middleware + `_is_cross_site()` to `create_app()`: a non-GET/HEAD/OPTIONS request whose `Sec-Fetch-Site` is not `same-origin`/`none`, or whose `Origin` does not match the request's own, is refused `403`. Header-less callers and same-origin requests pass. Corrected the `app/api/settings.py` module docstring to state the routes *are* cross-site reachable and name the guard + its residual limit (not a CSRF token). | `app/main.py`, `app/api/settings.py` | `91ede57` | `tests/api/test_same_origin_guard.py` (literal `<form … action="/settings/reset">` with a foreign `Origin`; parametrised over all nine mutating routes; same-origin/absent still 200; cross-site GET allowed) |
| **WR-01** — retention field never pre-fills the stored threshold | Warning | `_settings_context` now passes `prune_age_default` (the stored threshold for the select's default category, else 30); `settings.html` pre-fills from it. The docstring no longer claims the field "cannot disagree" — it states the real behaviour (a different category follows only after its own preview). | `app/api/settings.py`, `app/web/templates/html/settings.html` | `91ede57`, `05a07cd` | `tests/api/test_settings_prune.py::test_the_age_field_prefills_from_the_stored_threshold` + `…falls_back_to_thirty_with_no_stored_threshold` |
| **WR-02** — `reconcile()` cannot see a timezone change | Warning | Compare the trigger's own identity (`existing.trigger.fields`, `str(timezone)`) instead of `str(CronTrigger)` (which omits the timezone), so a `schedule_timezone` change reschedules. | `app/jobs/scheduler.py` | `c8b8ce5` | `tests/jobs/test_scheduler.py::test_a_timezone_change_is_detected_with_identical_cron_fields` (same cron fields, UTC vs Europe/Dublin) |
| **WR-03** — `STOP_SIGNAL_PREFIX` fail-open | Warning | Structural parse (`prefix` + matched quote pair, single or double) so a `repr`-double-quoted signal is not missed; a prefix-carrying but unparseable note is surfaced as a warn and treated as recorded (`?`), never a silent `None`. | `app/db/repositories/source_repo.py` | `f81fde5` | `tests/db/test_stop_signal_parse.py` (literal `fetch-side: stop signal "it's"; …`) |
| **IN-01** — unreachable `listings` artefact branch | Info | Documented that `_paths_for_listings` is `[]` by construction and the `CvArtifact` child-delete is defensive, so a later guard relaxation cannot silently orphan files. | `app/db/repositories/retention_repo.py` | `0eff7e3` | (docstring; existing `test_retention_repo.py` selection tests still pin the behaviour) |
| **IN-02** — NULL-`listing_id` ok artefacts unprunable | Info | Added `CvArtifact.listing_id.is_(None)` to guard 4's disjunction: an orphan `ok` row has no listing to protect and is now eligible on age. | `app/db/repositories/retention_repo.py` | `0eff7e3` | `tests/db/test_retention_repo.py::test_an_ok_artifact_with_a_null_listing_id_is_prunable` |
| **IN-03** — `errors_json` overwritten on boot reconcile | Info | `reconcile_stale_runs` appends its entry to `errors_json` instead of replacing existing entries. | `app/jobs/scheduler.py` | `c8b8ce5` | `tests/jobs/test_scheduler.py::test_reconcile_stale_runs_preserves_existing_errors` |
| **IN-04** — ruff violations + unused `corpus` | Info | Cleared all ruff `check`/`format` violations in the phase-added files (UP032 f-string, E501, I001, F841). The unused `corpus` is now used to assert the *selected listing identities*, not just the count. | `app/db/repositories/retention_repo.py`, `tests/api/test_health_page.py`, `tests/api/test_settings_prune.py`, `tests/db/test_retention_repo.py`, `tests/jobs/test_scheduler.py` | `0eff7e3` | the strengthened `test_the_listing_selection_excludes_applications_artifacts_and_both_dupe_sides` asserts `{clean, eventful}` |
| **IN-05** — arbitrary retention keys survive the read | Info | `_parse_retention` narrows keys to `retention_repo.PRUNE_CATEGORIES`; `write_retention` rejects an unknown category before any SQL. | `app/db/repositories/operations_config_repo.py` | `0eff7e3` | `tests/api/test_settings_prune.py::test_an_unknown_retention_key_is_dropped_on_read` + `…unknown_retention_category_is_refused_before_any_sql` |
| **UI-1** — prune/schedule submits under the 44px tap floor | Warning | Added `class="touch-target"` to `#prune-preview-submit`, `#prune-confirm-submit`, `#schedule-submit`; rebuilt the committed stylesheet with the pinned `tailwindcss@4.3.3` CLI. | `app/web/templates/html/settings.html`, `static/vendor/app.css` | `05a07cd`, `3de81e9` | `tests/test_responsive_contract.py::test_the_prune_and_schedule_submits_carry_the_tap_floor`; `tests/test_stylesheet_coverage.py` byte-identity guard stays green |
| **UI-2** — `.listing-error` undefined | Warning | Defined `.listing-error` in `input.css` from the existing danger tokens (mirroring `.health-unreachable`); rebuilt the stylesheet. | `assets/tailwind/input.css`, `static/vendor/app.css` | `3de81e9` | `tests/test_stylesheet_coverage.py::test_runtime_emitted_classes_are_defined_in_both_stylesheets` |
| **UI-3** — two declared `/status` strings diverge | Warning | Amended `08-UI-SPEC.md` to the shipped, honest strings: the verdict label is per board (`Indeed hedge:` / `Linkedin hedge:`) because P-1 is computed per board; the schedule helper is `Times are read in this timezone, not the container's UTC.` Code unchanged (it is the honest reading and is test-locked). | `.planning/phases/08-operations-polish/08-UI-SPEC.md` | `docs(08): reconcile security register + spec, record review fixes` | `tests/api/test_health_page.py` (existing per-board verdict assertions) |

## Not fixed (with reason)

- **`#application-filters` has no stylesheet rule** (UI review Pillar 2 / Minor Rec 2) — not in the fix list. The spec names only `#queue-filters`, so the tracker filter shell is out of the phase's declared contract; left as a documented UI-review follow-up rather than an unrequested design change.
- **`#settings-banner` missing `role="status" aria-live="polite"`** (UI review Pillar 6 / Minor Rec 1) — not in the fix list. Both writes are full-page POSTs, so the region is replaced on load; noted for a later pass.
- **`Saved` tracker confirmation + drafting-failure copy** (carried from 07) — explicitly out of phase 08's contract and not in this fix list.
- **Health-page compact links tap floor** (UI review Pillar 5) — the review itself records this clause as **unimplementable as written** (`min-height`/`min-width` are inert on a non-replaced inline `<a>`); a spec defect, not an implementation one, and not in the fix list.
- **`timezone` select offers one option** (Minor Rec 4) — a design change, not a review finding in the fix list.
- **Duplicate empty-preview sentence** (Minor Rec 3) — cosmetic; not in the fix list.
- **Rendered-pixel claims** (44px boxes, 320/375/768 walk, long-token backstop) — only observable in a real browser; remain the operator's `docs/runbook-responsive-ui.md` walk and are recorded as unverified, not passed.

## Verification

Full hermetic suite (`-m 'not live and not latex'`), after all fixes:

```
1955 passed, 15 deselected, 2 xfailed in 487.26s
```

Baseline before this work was **1918 passed, 15 deselected, 2 xfailed, 0 failed**
(the +37 are the new and strengthened tests). `tests/test_stylesheet_coverage.py`
(byte-identity guard, CLI present and executed) and `tests/test_no_cdn.py` are
green. `ruff check` and `ruff format --check` are clean on every changed file.
