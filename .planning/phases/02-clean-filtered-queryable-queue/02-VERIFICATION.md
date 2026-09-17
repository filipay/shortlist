---
phase: 02-clean-filtered-queryable-queue
verified: 2026-09-17T15:06:06Z
status: passed
score: 61/61 must-haves verified
re_verification: true
re_verification_details:
  delta_reverification: true
  re_verification_scope: "delta only (5726cd3 → 502fae1); unchanged truths were not re-derived"
  previous_status: passed
  previous_score: 54/54 must-haves verified
  previous_verified: 2026-09-16T22:42:00Z
  previous_commit: 5726cd3
  current_commit: 502fae1
  gaps_closed: []
  gaps_remaining: []
  regressions: []
  verdicts_changed: 0
  uat: "02-UAT.md — 9/9 items pass (2026-09-16 → 2026-09-17). Items 1–5 were relabelled `satisfied`→`pass` with no result change (dates/evidence/operator quotes untouched); items 6–9 were added for the 02-11 deliverables and operator-confirmed on the live instance."
covered_files:
  - .planning/REQUIREMENTS.md
  - .planning/ROADMAP.md
  - .planning/WINDOWS.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-01-PLAN.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-01-SUMMARY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-02-PLAN.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-02-SUMMARY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-03-PLAN.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-03-SUMMARY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-04-PLAN.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-04-SUMMARY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-05-PLAN.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-05-SUMMARY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-06-PLAN.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-06-SUMMARY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-07-PLAN.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-07-SUMMARY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-08-PLAN.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-08-SUMMARY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-09-PLAN.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-09-SUMMARY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-10-PLAN.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-10-SUMMARY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-11-PLAN.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-11-SUMMARY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-REVIEW.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-SECURITY.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-UAT.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-UI-REVIEW.md
  - .planning/phases/02-clean-filtered-queryable-queue/02-VALIDATION.md
  - .planning/seeds/SEED-001-queue-filter-by-remote-and-location.md
  - alembic/env.py
  - alembic/versions/0002_queue_filter_and_run_reason.py
  - app/api/events.py
  - app/api/runs.py
  - app/api/searches.py
  - app/api/settings.py
  - app/config.py
  - app/db/models.py
  - app/db/repositories/dupe_repo.py
  - app/db/repositories/event_repo.py
  - app/db/repositories/exclusion_repo.py
  - app/db/repositories/queue_repo.py
  - app/db/repositories/run_repo.py
  - app/db/repositories/search_repo.py
  - app/db/repositories/state_repo.py
  - app/domain/criteria.py
  - app/domain/dedup.py
  - app/domain/filter.py
  - app/domain/run_reason.py
  - app/domain/sanitize.py
  - app/domain/search_query.py
  - app/main.py
  - app/pipeline/dedup_stage.py
  - app/pipeline/filter_stage.py
  - app/pipeline/run.py
  - app/web/filters.py
  - app/web/routes.py
  - app/web/template_env.py
  - app/web/templates/html/_listing_row.html
  - app/web/templates/html/base.html
  - app/web/templates/html/criteria.html
  - app/web/templates/html/merges.html
  - app/web/templates/html/queue.html
  - app/web/templates/html/queue_list.html
  - app/web/templates/html/runs.html
  - app/web/templates/html/settings.html
  - assets/tailwind/input.css
  - compose.yml
  - docs/implementation-notes.md
  - docs/superpowers/plans/2026-09-17-queue-links-dismiss-and-reset.md
  - docs/superpowers/specs/2026-09-17-queue-links-dismiss-and-reset-design.md
  - pyproject.toml
  - requirements.txt
  - static/vendor/app.css
  - tests/api/test_criteria_capabilities.py
  - tests/api/test_listing_events.py
  - tests/api/test_merges_view.py
  - tests/api/test_queue_dismiss.py
  - tests/api/test_queue_excluded.py
  - tests/api/test_queue_links.py
  - tests/api/test_queue_search.py
  - tests/api/test_queue_signals.py
  - tests/api/test_rule_form_payloads.py
  - tests/api/test_run_history.py
  - tests/api/test_run_reason.py
  - tests/api/test_searches_crud.py
  - tests/api/test_settings_page.py
  - tests/api/test_settings_reset.py
  - tests/conftest.py
  - tests/db/test_dupes.py
  - tests/db/test_exclusions.py
  - tests/db/test_listing_events.py
  - tests/db/test_migration_contract.py
  - tests/db/test_no_pii_columns.py
  - tests/db/test_orm_drift.py
  - tests/db/test_queue_row_links.py
  - tests/db/test_queue_state.py
  - tests/db/test_reset_coverage.py
  - tests/db/test_search_repo_writes.py
  - tests/db/test_skeleton_boot.py
  - tests/domain/test_criteria.py
  - tests/domain/test_dedup.py
  - tests/domain/test_filter.py
  - tests/domain/test_injection_patterns.py
  - tests/domain/test_run_reason.py
  - tests/domain/test_search_query.py
  - tests/pipeline/test_capability_surface.py
  - tests/pipeline/test_criteria_form_to_run.py
  - tests/pipeline/test_criteria_snapshot.py
  - tests/pipeline/test_dedup_merge.py
  - tests/pipeline/test_dedup_revert.py
  - tests/pipeline/test_filter_stage.py
  - tests/pipeline/test_ingest_e2e.py
  - tests/pipeline/test_single_search_run.py
  - tests/pipeline/test_union_fetch.py
  - tests/test_config.py
  - tests/test_dependency_pins.py
  - tests/test_stylesheet_coverage.py
covered_digest: "v1:sha256:fd427cbde1357054ce1fa4b9f041dc072ea2293c263e1ab12f30ee9355dc45c2"
behavior_unverified: 0
overrides_applied: 0
gaps: []
advisory:
  - finding: "The built image is not asserted to contain rapidfuzz==3.14.6 (02-SECURITY.md W-01). Dockerfile:38-39 installs requirements.txt; the only post-install assertion (Dockerfile:49-50) checks the JobSpy VCS pin, not rapidfuzz. tests/test_dependency_pins.py imports rapidfuzz from the test env, not the image."
    category: other
    reason: "The manifest layer (pyproject.toml + requirements.txt agreement) is tested, but 'the image contains the pinned dependency' is not asserted. De-risked for the Phase-2 image by the operator compose smoke (a completed run imports app.pipeline → app.domain.dedup, which imports rapidfuzz, so the image must resolve it). Recommended follow-up, not a phase-2 gap: add a Dockerfile post-install import assertion."
    evidence_status: "README-of-record (02-SECURITY.md W-01); no failing test"
  - finding: "listing_exclusions.detail_json (the matched term/field/count behind a rejection) and the firing QueueRule.rule_id have no UI consumer; the queue chip renders only rule.kind + a per-rule count."
    category: architectural
    reason: "FILT-02 ('records which rule fired and why') is satisfied — the detail is persisted and tested (tests/db/test_exclusions.py) — but FILT-03/SC2's on-screen 'why' is a product-sufficiency call. `exclusion_repo.ExclusionRecord`/`exclusions_for_run` remain uncalled. Resolved at UAT item 5: the user judged the chip sufficient for now, and the related attribute-filter ask is captured as SEED-001."
    evidence_status: "codebase observation (grep: detail_json referenced only in models/exclusion_repo); not backed by a failing test"
  - finding: "A dismissal that matches more than the 10,000-listing ceiling refuses with a 400 fragment that htmx does not swap, so the user sees no feedback (02-11-SUMMARY.md flagged assumption 4)."
    category: other
    reason: "New-scope observation from the 02-11 cycle. Unreachable at any realistic queue size and strictly safer than a partial dismissal; the documented proper fix is an app-wide htmx error handler, which is out of this phase's scope. No failing test and no reproducible defect at a real corpus size."
    evidence_status: "documented in 02-11-SUMMARY.md; no failing test"
  - finding: "The `VACUUM INTO` destination is interpolated as an escaped SQL literal rather than bound (02-11-SUMMARY.md flagged assumption 5)."
    category: security
    reason: "Safe today: the path is server-derived from `session.get_bind().url.database` plus a `strftime` timestamp, so no request-controlled component reaches it, and single quotes are doubled. It relies on that staying true — modern SQLite accepts a bound parameter, so a future change could bind it. No reproducible defect now."
    evidence_status: "documented in 02-11-SUMMARY.md and app/api/settings.py:133-138; no failing test"
---

# Phase 2: Clean, Filtered, Queryable Queue — Verification Report

**Phase Goal:** A deduplicated, deterministically filtered, searchable queue the user trusts — with every rejection explained and every run observable.
**Verified:** 2026-09-17T15:06:06Z
**Status:** passed
**Re-verification:** Yes — a **third** targeted **delta** re-verification. Baseline: the report previously certified at `5726cd3` (54/54, `passed`). This pass covers only `5726cd3 → 502fae1` (the `2026-09-17` SDD cycle, its post-completion fix arc, and the completed UAT); unchanged truths were not re-derived.
**Score:** 61/61 must-have truths verified (0 present-but-behavior-unverified). The denominator grew from 54 to 61 because plan `02-11` adds **7** must-have truths; **no truth's pass/fail verdict changed** in this delta (`verdicts_changed: 0`). Two prior advisory items carry forward; two new advisory observations are recorded — none is a blocker.

## Method — this delta (`5726cd3 → 502fae1`)

Independent, goal-backward verification against the codebase — not against the SUMMARYs or the UAT:

- True HEAD resolved with `git rev-parse --short HEAD` → **`502fae1`** (21 commits after `5726cd3`: the prior report commit `35af59d`, 2 spec commits, the plan, the 15 plan commits `9e9eb46..d436425`, `5f3a072`, `502fae1`).
- **Full suite re-run at HEAD:** `.venv/bin/python -m pytest -q` → **712 passed, 2 deselected in 162.99s** (prior baseline 660). Matches the 02-11-SUMMARY claim exactly.
- **Lint:** `.venv/bin/python -m ruff check app tests` → **All checks passed!**
- **The six 02-11 feature lanes** re-run → `tests/db/test_queue_row_links.py tests/api/test_queue_links.py tests/api/test_queue_dismiss.py tests/api/test_settings_page.py tests/api/test_settings_reset.py tests/db/test_reset_coverage.py` → **52 passed in 24.47s** (matches the SUMMARY's 52).
- **The four guard lanes** re-run → `tests/test_auth_seam.py tests/test_stylesheet_coverage.py tests/test_no_cdn.py tests/pipeline/test_ingest_e2e.py` → **21 passed in 6.97s**.
- **The truth-5 discriminator run by name:** `tests/api/test_settings_reset.py::test_a_failed_delete_rolls_back_and_re_arms_the_trigger` → **1 passed in 6.07s**.
- `verify.plan-structure` on `02-11-PLAN.md` → **`valid: true`, no errors, no warnings, 8 tasks**.
- Ancestry of all 15 plan commits `git merge-base --is-ancestor <sha> HEAD` → **all OK**.
- Each of the 21 post-`5726cd3` commits inspected; the affected code read in full (`app/db/session.py`, `app/api/settings.py`, `app/web/routes.py`, `app/db/repositories/{queue_repo,event_repo}.py`, the four changed templates, and the six new test modules).
- Digest regenerated with `gsd-tools verification fingerprint` over the updated covered-file set (**119 files**).

### Method — prior passes, preserved

- **`1bb7332 → 5726cd3`:** full suite `660 passed, 2 deselected in 91.23s`; dedup lane 55, union/run lane 50, filter/forms lane 96; the htmx fix proven fail-first (8 failures with `hx-include` removed).
- **`bcb86c2 → 1bb7332`:** full suite `605 passed, 2 deselected in 113.57s`; dedup lane 41.
- The baseline's grouped lanes (62 + 50 + 133) are subsumed by the full-suite runs and are not separately re-listed.

## Delta since the baseline report (`5726cd3 → 502fae1`)

The baseline certified `54/54` at `5726cd3`; **21 commits** have landed since. Each is listed with the must-have truth(s) it touches and the verdict after re-verification against the current tree.

| Commit | Change | Truth(s) affected | Verdict after |
| ------ | ------ | ----------------- | ------------- |
| `35af59d` | the previous report itself | none (docs) | — |
| `7c4f7c8`, `0c44047` | the cycle's spec + its self-review | none (docs) | — |
| `228fcad` | the human plan for the cycle (`plan_head_before`) | none (docs) | — |
| `9e9eb46` | `QueueRow.url` + `source_links`; one batched `listing_sources` read; `_http_url` gate | 02-11 #1 | ✓ VERIFIED |
| `484d89b` | compare board/employer URLs like-for-like (`canonical_url(board_url) != employer_url`) | 02-11 #1 | ✓ VERIFIED |
| `482e416` | render the title anchor, per-source links and the conditional `Apply` link | 02-11 #1 | ✓ VERIFIED |
| `5dde21a` | only http(s) URLs reach an `href` | 02-11 #1 | ✓ VERIFIED |
| `7590ddb` | `POST /queue/dismiss` — one `hide` per queued listing | 02-11 #2, #3 | ✓ VERIFIED |
| `f497bc1` | dismiss respects the hidden gate and the ceiling | 02-11 #2, #3 | ✓ VERIFIED |
| `e165274` | `GET /settings` — danger zone, counts, token, fifth nav link | 02-11 #4 | ✓ VERIFIED |
| `e017e00` | `POST /settings/reset` — snapshot then ordered deletes behind guards | 02-11 #4, #5 | ✓ VERIFIED |
| `b8061bb` | snapshot-failure branch test + dynamic reset-coverage guard | 02-11 #5 | ✓ VERIFIED |
| `182605a` | the cycle's change record | none (docs) | — |
| `ec19ac0` | dismiss drops **every** toggle, not a partially-selected filter row | 02-11 #2 | ✓ VERIFIED |
| `80a9b33` | change-record correction | none (docs) | — |
| `c16023a` | suspend the append-only trigger inside the reset transaction; `except Exception` + `rollback()` before re-render; **`build_engine` explicit `BEGIN`** | 02-11 #5, #6 | ✓ VERIFIED |
| `6720f1c` | log reset failures with a traceback | none (diagnostics) | — |
| `d436425` | record the engine transaction change as a deliberate decision | 02-11 #6 | ✓ VERIFIED |
| `5f3a072` | plan 02-11 + summary + ROADMAP `11/11` + reconciled `docs/implementation-notes.md` header | none (docs) | — |
| `502fae1` | completed UAT (9/9) | none (human record) | — |

### Truths whose verdict CHANGED

**None.** All 54 previously-certified truths remain `✓ VERIFIED`, and the 7 new 02-11 truths are all `✓ VERIFIED`. `verdicts_changed: 0`.

| Truth | Before | After | Why |
| ----- | ------ | ----- | --- |
| *(empty)* | — | — | no pass/fail verdict moved in `5726cd3 → 502fae1` |

## 02-11 must-have truths (7/7) — the delta's new contract

Plan `02-11-PLAN.md` is the GSD record of work that had **already shipped** when the plan was written: the operator ran the feature against the real database and the reset failed with a bare `500`, so three commits at the top of the range exist as a post-completion fix arc. Truth 5 is the discriminator; the durable evidence is the committed test `test_a_failed_delete_rolls_back_and_re_arms_the_trigger`.

### 02-11 #1 — queue rows link to the posting and to each source

- `app/db/repositories/queue_repo.py:391-403` — `_http_url` returns the URL only when `urlsplit(value).scheme.casefold() in {"http","https"}`, unchanged otherwise (a gate, not a normalisation).
- `queue_repo.py:432-466` — **one** batched `select(ListingSource...)` over the page's ids groups one `SourceLink` per `listing_sources` row; `employer_page` is set only when `employer_url and canonical_url(board_url) != employer_url` (`:455-459`), the like-for-like guard from `484d89b`.
- `queue_repo.py:523-524` — `QueueRow.url = _http_url(listing.canonical_url) or None`; `source_links=links`.
- `app/web/templates/html/_listing_row.html:37` — title is `<a ... target="_blank" rel="noopener noreferrer">` when `row.url` is truthy, else plain `{{ row.title }}`.
- `_listing_row.html:48` — one `<a class="source-link">` per `row.source_links` entry (plain text when a link URL is empty) plus an `<a class="source-apply">Apply</a>` only when `link.employer_url` is present.
- Tests: `tests/db/test_queue_row_links.py` (11 — incl. `test_employer_url_is_omitted_when_only_normalisation_differs`, `test_the_page_reads_provenance_in_one_query`, the three non-web-scheme cases) and `tests/api/test_queue_links.py` (7 — incl. `test_a_non_web_source_url_renders_the_source_name_as_plain_text`, which asserts `"javascript:" not in response.text`). **✓ VERIFIED**

### 02-11 #2 — `Dismiss all queued listings` empties the default queue

- `app/web/routes.py:174-217` — `_queued_listing_ids` rebuilds the page query with `replace(query, q=None, excluded=False, hidden=False, saved=False, scope_search_id=None, offset=0)`, pages the whole matched set, and returns `None` above `_DISMISS_LIMIT` (10,000).
- `routes.py:338-376` — the route appends the hides, commits, then **re-reads** the page (`_read_queue_page`) and returns that fragment, so the response already shows the empty queue.
- `app/web/templates/html/queue_list.html:35-42` — the `Dismiss all queued listings` button posts to `/queue/dismiss` and swaps `#queue-list`.
- Tests: `tests/api/test_queue_dismiss.py` (12) — incl. `test_dismiss_covers_the_whole_queue_not_just_the_page` (page size 25, queue 30, asserts 30 hides), `test_dismissed_listings_stay_hidden_on_a_re_read` (reload survives), `test_dismiss_ignores_the_text_filter_but_not_the_hidden_gate`, `test_dismiss_ignores_the_saved_toggle`, `test_dismiss_ignores_the_scope_toggle`, `test_dismiss_ignores_the_excluded_toggle_and_spares_excluded_rows`, `test_dismiss_refuses_when_the_queue_exceeds_the_ceiling`. **✓ VERIFIED**

### 02-11 #3 — one `hide` event per listing, tagged `queue_dismiss`

- `app/db/repositories/event_repo.py:188-218` — `hide_listings` dedupes/sorts the ids and calls `append_event(..., event_type="hide", context=context)` once per listing; `append_event` (`:148-180`) carries the SAVEPOINT, allow-list check and `data_json`/`context_json` write.
- `app/web/routes.py:63-68` — `_DISMISS_CONTEXT = MappingProxyType({"surface": "queue_dismiss"})`.
- Tests: `test_dismiss_events_record_the_bulk_surface` asserts `contexts == [{"surface": "queue_dismiss"}]`; `test_dismiss_does_not_touch_an_absorbed_twin`; `test_dismiss_with_the_hidden_toggle_does_not_rehide_hidden_rows`; the excluded-row case above. **✓ VERIFIED**

### 02-11 #4 — `GET /settings` and the four reset refusals

- `app/api/settings.py:80-119` — `_counts` (one query per `RESET_DELETE_ORDER` + `RESET_KEPT_TABLES` table), `_settings_context` (banner, counts, deleted/kept lists, backup dir, confirm token), and the `GET /settings` handler.
- `settings.py:211-291` — ordered refusals: wrong confirm → `400` (`:231-241`); run in flight (`Run.status.not_in(TERMINAL_STATUSES)`) → `409` (`:243-254`); `applications`/`cv_artifacts` row (`_blocking_row`, `RESET_BLOCKING_TABLES`) → `409` (`:256-270`); snapshot failure → `500` (`:273-291`). Every refusal returns before the first `delete()`.
- `app/web/templates/html/settings.html:29-52` — `#danger-zone` with the deleted/kept lines and the token-gated plain `POST` form.
- `app/web/templates/html/base.html:32` — a fifth `Settings` nav link with `nav-current` + `aria-current="page"`; `app/main.py:60` registers the router.
- Tests: `tests/api/test_settings_page.py` (8 — incl. `test_the_nav_marks_settings_as_the_current_page`, `test_the_reset_form_is_a_plain_post_and_not_an_htmx_swap`, `test_the_deleted_and_kept_lists_are_rendered_as_labelled_lines`); `tests/api/test_settings_reset.py` guard tests `test_a_wrong_confirm_token_changes_nothing`, `test_a_run_in_flight_blocks_the_reset`, `test_tracked_work_blocks_the_reset`, `test_a_failed_snapshot_deletes_nothing` (each asserts the corpus count is unchanged). **✓ VERIFIED**

### 02-11 #5 — the happy path, on a non-empty `listing_events`, with rollback-safe trigger suspension

- `settings.py:126-151` — `snapshot_database` writes `VACUUM INTO '<db_dir>/reset-backups/jobsearch-<YYYYmmddTHHMMSSZ>.db'` on a sync stdlib `sqlite3` connection, and raises `ResetRefused` rather than overwriting an existing file.
- `settings.py:293-303` — `_suspend_append_only_trigger` → the `RESET_DELETE_ORDER` loop → `_restore_append_only_trigger` → one `commit()`. `_suspend` (`:176-194`) reads the trigger DDL from `sqlite_master` and issues `DROP TRIGGER IF EXISTS listing_events_no_delete`; `_restore` (`:197-208`) re-executes the captured DDL via `exec_driver_sql`.
- `RESET_DELETE_ORDER` (`:58-70`) is child-first; `RESET_KEPT_TABLES` (`:73`) keeps `searches` / `filter_rules` / `sources`; `cv_versions` also survives (asserted).
- On failure, `:304-323` rolls back **before** re-rendering and returns the honest "Nothing was deleted" page at `500`.
- Tests: `test_the_snapshot_holds_the_pre_reset_rows` asserts the snapshot holds the corpus (2 listings, 1 run, **3 `listing_events`**), so the happy path genuinely runs on a non-empty event log; `test_a_correct_token_empties_the_corpus_and_keeps_configuration`; `test_the_append_only_trigger_is_re_armed_and_still_enforced` (a post-reset direct `DELETE FROM listing_events` still aborts with `IntegrityError`); and the discriminator **`test_a_failed_delete_rolls_back_and_re_arms_the_trigger`** — forces a delete failure after the `DROP TRIGGER`, asserts `500`, the "nothing was deleted" page, every pre-reset count intact, and the trigger present. **Ran in this pass: 1 passed in 6.07s.** **✓ VERIFIED**

### 02-11 #6 — `build_engine` makes DDL transactional

- `app/db/session.py:45-70` — `build_engine` keeps the PRAGMA listener (`:60`), adds a second `connect` listener setting `dbapi_connection.isolation_level = None` (`:62-64`), and a `begin` listener issuing `connection.exec_driver_sql("BEGIN")` (`:66-68`), both on `engine.sync_engine`.
- The blast radius is recorded in `02-11-SUMMARY.md` and `docs/implementation-notes.md` under `d436425`: pragmas unaffected (`:60`), `expire_on_commit=False` orthogonal (`:74`), every `begin_nested()` site now emits `BEGIN` before the SAVEPOINT, and Alembic builds its own sync engine (`alembic/env.py`) — with the locked-database caveat recorded for a future second writer.
- The truth is proven **through the app**, not by engine inspection: the trigger-suspension rollback test above fails without transactional DDL. **✓ VERIFIED**

### 02-11 #7 — HEAD-level claims

- Suite: `.venv/bin/python -m pytest -q` → **712 passed, 2 deselected in 162.99s** (run this pass).
- Lint: `.venv/bin/python -m ruff check app tests` → **All checks passed!** (run this pass).
- Ancestry: all 15 commits `228fcad..d436425` → `git merge-base --is-ancestor <sha> HEAD` **all OK** (run this pass).
- Operator confirmation of the rebuilt container: `02-UAT.md` item 9 is `pass (2026-09-17)`, recording that the operator rebuilt and confirmed the reset now succeeds where it previously returned a bare `500`. This human-recorded element is discharged (UAT complete; no outstanding human item). **✓ VERIFIED**

## Observable Truths (plan must_haves, 61 total)

Evidence key: **this delta** (`5726cd3 → 502fae1`) — **full suite 712 passed / 2 deselected**, **02-11 feature lanes 52**, **guard lanes 21**. The prior pass's lanes (55 dedup / 50 union-run / 96 filter-forms, full suite 660) are preserved below where a row still cites them; they remain exercised by the 712-test suite. Legacy lane shorthand from earlier passes: **lane B** = filter/exclusions/capability (62), **lane C** = criteria/snapshot (50), **lane D** = search/signals/events/UI/run (133).

### 02-01 — Schema spine (4/4)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | `alembic upgrade head` on a fresh database leaves exactly one revision `0002` and one Alembic head | ✓ VERIFIED | `tests/db/test_migration_contract.py:270,281` (fresh) plus the populated-upgrade case `:496-500`; migration engine `alembic/env.py:63,95` |
| 2 | Migrated DB has `filter_rules`, `queue_state`, four new `runs` columns, `listing_exclusions.criteria_version`, `listing_dupes` unique index (PRAGMA/sqlite_master) | ✓ VERIFIED | `tests/db/test_migration_contract.py` items 10–13 and the populated-path assertions `:511-549`; `tests/db/test_skeleton_boot.py` (lane D) |
| 3 | Every new JSON column is allow-listed; no new PII-shaped column | ✓ VERIFIED | `tests/db/test_no_pii_columns.py` (lane D) |
| 4 | `dedup_fuzzy_threshold`, `dedup_posted_window_days`, `stale_after_days`, `queue_page_size` readable from `Settings`; no literal under `app/pipeline` | ✓ VERIFIED | `app/config.py:81,84,87,89`; `tests/test_config.py` (lane C) |

### 02-02 — rapidfuzz dependency (3/3)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | `rapidfuzz==3.14.6` installed and importable; both fuzz functions callable | ✓ VERIFIED | `tests/test_dependency_pins.py::test_rapidfuzz_imports_at_the_pinned_version` |
| 2 | Exact pin declared once in `pyproject.toml`, mirrored verbatim in `requirements.txt`; no floating range | ✓ VERIFIED | `tests/test_dependency_pins.py::test_rapidfuzz_pin_is_declared_exactly`; `requirements.txt:18` |
| 3 | A human confirmed the pinned version/source/build before install | ✓ VERIFIED (human-recorded) | `02-02-SUMMARY.md:149` records `user_response = "approved"`; re-confirmed at `02-UAT.md` item 4 (`pass`, 2026-09-16) |

### 02-03 — Pure decision layer (6/6)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | `evaluate(rules, facts)` returns only firing rules ordered by `(position, rule_id)`; a malformed rule degrades to skipped | ✓ VERIFIED | `app/domain/filter.py:402`; `tests/domain/test_filter.py` (lane B) |
| 2 | An absent value is never a rejection reason | ✓ VERIFIED | `tests/domain/test_filter.py::test_unknown_values_are_never_a_rejection_reason` |
| 3 | An unknown rule `kind` is skipped, not pass-through | ✓ VERIFIED | `tests/domain/test_filter.py::test_an_unknown_kind_is_skipped` |
| 4 | Every `RuleOutcome.detail` carries terms/field names/counts only — no description excerpt/removed value | ✓ VERIFIED | `tests/domain/test_filter.py::test_detail_keys_are_exact_per_kind`, `::test_exclude_keyword_never_persists_the_field_text` |
| 5 | Criteria mapping assembles a `SearchQuery` and a rule list ordered by `(search_id, position)` | ✓ VERIFIED | `app/domain/criteria.py`; `tests/domain/test_criteria.py` |
| 6 | The injection catalogue flags/counts without altering text | ✓ VERIFIED | `app/domain/sanitize.py`; `tests/domain/test_injection_patterns.py` |

### 02-04 — Tier-2 dedup/merge (6/6)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Two sources → one visible listing + one absorbed twin + exactly one `listing_dupes` row | ✓ VERIFIED | `tests/pipeline/test_dedup_merge.py` (incl. the 3-way reproduction) and `tests/domain/test_dedup.py::test_the_real_corpus_yields_exactly_one_cross_source_merge` (dedup lane, 55) |
| 2 | A non-null survivor field is never overwritten; empty string counts as blank | ✓ VERIFIED | `tests/db/test_dupes.py::test_merge_fills_blanks_and_never_overwrites_a_non_null`, `::test_an_empty_string_counts_as_blank_but_a_real_value_does_not` |
| 3 | `snapshot_json` holds the survivor's pre-merge values for exactly the fields written | ✓ VERIFIED | `tests/db/test_dupes.py::test_snapshot_records_exactly_the_written_fields_and_their_prior_values`; `dupe_repo.py:202-217` |
| 4 | A pair with a reverted `listing_dupes` row in either orientation is skipped before scoring | ✓ VERIFIED | `tests/db/test_dupes.py::test_reverted_pairs_is_empty_then_returns_both_orientations`; `dedup_stage.py:112-124` |
| 5 | A grade-carrying title never merges with the same title without the grade | ✓ VERIFIED | `tests/domain/test_dedup.py::test_senior_versus_ungraded_never_merges`, `::test_two_different_grades_never_merge`, `::test_the_grade_guard_still_refuses_across_disjoint_sources`; the grade gate is `dedup.py:175-176` after the source guard at `:172-173` |
| 6 | `runs.deduped_count` equals merges written, not created count | ✓ VERIFIED | `tests/pipeline/test_dedup_merge.py` merge + zero cases; the 3-way test asserts `deduped_count == 2` |

### 02-05 — Hard filtering, snapshot, run reason (6/6)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Every rejected listing gets one `listing_exclusions` row per firing rule with `rule_id`,`rule_kind`,`detail_json`,`run_id`,`criteria_version` | ✓ VERIFIED | `app/pipeline/filter_stage.py:119-133`; `exclusion_repo`; `tests/db/test_exclusions.py`, `tests/pipeline/test_filter_stage.py` (lane B) |
| 2 | Filter stage runs after dedup, before `_finish`; no LLM client constructed/imported/called | ✓ VERIFIED | `app/pipeline/run.py:666-700`; no `llm`/`opencode` import under `app/pipeline/`; `tests/pipeline/test_filter_stage.py` asserts empty `llm_calls` |
| 3 | `runs.criteria_snapshot_json` holds the exact query/rules used; a criteria edit cannot rewrite a past run | ✓ VERIFIED | `app/pipeline/run.py:619`; `tests/pipeline/test_criteria_snapshot.py::test_editing_criteria_after_a_run_leaves_that_runs_snapshot_unchanged` |
| 4 | An unsupported filter appears in `runs.stage_log_json` (criteria_compile) and `runs.errors_json` | ✓ VERIFIED | `tests/pipeline/test_capability_surface.py::test_an_unsupported_salary_floor_is_warned_in_both_places`; `tests/pipeline/test_union_fetch.py::test_duplicate_capability_warnings_are_deduped_across_searches` |
| 5 | `runs.reason` ∈ six-value enum by documented precedence, plus `reason_counts_json` | ✓ VERIFIED | `app/domain/run_reason.py:34-41,77-138` (branch 2 has the `fetched <= 0` conjunct at `:114-119`); `tests/domain/test_run_reason.py`, `tests/api/test_run_reason.py` |
| 6 | One malformed rule is skipped and recorded; neither empties the queue nor aborts the run | ✓ VERIFIED | `filter_stage.py:88-89`; `tests/pipeline/test_filter_stage.py` |

### 02-06 — Merge audit + revert (4/4)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Merges view lists every `listing_dupes` row with both sides, method, score, time, snapshot | ✓ VERIFIED | `dupe_repo.list_merges`; `merges.html`; `tests/api/test_merges_view.py::test_merges_page_lists_the_rate_its_window_and_the_rows_behind_it` (dedup lane, 55) |
| 2 | Merge rate visible as merges over fetched for a stated window; rows reachable on the same page | ✓ VERIFIED | `dupe_repo.merge_rate` windows both operands to the latest run (`:470-515`); `MergeRate.window` reads `"this run only (#N)"`; `tests/api/test_merges_view.py::test_merge_rate_windows_both_operands_to_the_latest_run` asserts 33% not 67%; `id="merge-rate-scope"` assertion added |
| 3 | Revert restores snapshot fields + marks `reverted_at`/`reverted_by`; twin reappears with no un-hide step | ✓ VERIFIED | `dupe_repo.revert_merge` (UPDATE-only); `tests/api/test_queue_search.py::test_queue_hides_absorbed_twin_until_revert` |
| 4 | After a revert, a subsequent run does not re-merge the pair | ✓ VERIFIED | `tests/pipeline/test_dedup_revert.py::test_a_reverted_merge_is_durable_and_the_pair_stays_separate` |

### 02-07 — Searchable queue, signals, excluded toggle (7/7)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Hostile query text does not raise/500 | ✓ VERIFIED | `tests/domain/test_search_query.py::test_every_hostile_input_becomes_an_expression_the_real_parser_accepts` + `::test_the_raw_inputs_really_do_raise_untransformed`; `tests/api/test_queue_search.py::test_an_apostrophe_query_returns_200_not_500` (lane D) |
| 2 | Every FTS order ends with a unique tie-break; identical requests return identical order | ✓ VERIFIED | `queue_repo.py:329`; `tests/api/test_queue_search.py::test_identical_search_requests_return_an_identical_row_order` |
| 3 | With no query, Phase-1 order `first_seen_at desc, id desc` and no `listing_fts` join | ✓ VERIFIED | `queue_repo.py:336-344`; `tests/api/test_queue_search.py::test_no_query_keeps_the_phase_one_order` |
| 4 | Listings after `queue_state.last_queue_view_at` (or all when NULL) marked new; `Mark all as seen` advances | ✓ VERIFIED | `state_repo`; `tests/api/test_queue_signals.py::test_listings_after_the_watermark_are_new_and_before_it_are_not`, `::test_mark_all_as_seen_clears_the_badges_and_keeps_the_rows` |
| 5 | Stale when `last_seen_at` older than `stale_after_days` or `is_active` false; new and stale can co-occur | ✓ VERIFIED | `queue_repo._row_flags`; `tests/api/test_queue_signals.py::test_the_stale_boundary_is_n_minus_one_n_and_n_plus_one`, `::test_a_listing_can_be_both_new_and_stale` |
| 6 | Excluded listings out of default view, dimmed under `Show excluded`, one chip per firing rule with a per-rule count | ✓ VERIFIED | `queue_repo.py:431-440`, `_listing_row.html:42-44`; `tests/api/test_queue_excluded.py` (5). The count is run-wide by design; the chip's rule id/detail is unrendered — judged sufficient at UAT item 5 (SEED-001) |
| 7 | Listing with un-reverted merges shows `merged from N sources`; absorbed twin absent until reverted | ✓ VERIFIED | `tests/api/test_queue_search.py::test_queue_hides_absorbed_twin_until_revert`; `merge_summary_for_listings` |

### 02-08 — Criteria CRUD (7/7)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Create a named search (keywords/location/remote/salary/seniority + rules) persisted with `version == 1` | ✓ VERIFIED | `search_repo.create_search`; `tests/api/test_searches_crud.py::test_post_searches_persists_a_version_one_enabled_search` (lane C) |
| 2 | Editing criteria/rules bumps `searches.version` by exactly 1; a completed run's snapshot is not rewritten | ✓ VERIFIED | `tests/db/test_search_repo_writes.py`, `tests/pipeline/test_criteria_snapshot.py` |
| 3 | A search can be disabled/re-enabled without deletion; a disabled search contributes no rules | ✓ VERIFIED | `tests/api/test_searches_crud.py::test_toggle`, `tests/db/test_search_repo_writes.py::test_enable_disable_does_not_bump_the_version` |
| 4 | Deleting a search removes its rules and leaves no orphan `filter_rules` row | ✓ VERIFIED | `tests/db/test_search_repo_writes.py::test_delete_search_removes_it_and_all_its_rules_only` |
| 5 | Every rule editor is a purpose-built per-kind form; no raw-JSON editor; no template evaluates filter semantics | ✓ VERIFIED | `criteria.html` (per-kind blocks; 9 term textareas; no `params_json` control; no `\|safe`) |
| 6 | A filter a board cannot honour is reported on the criteria page before any run, naming board + filter | ✓ VERIFIED | `tests/api/test_criteria_capabilities.py::test_an_unsupported_filter_is_reported_per_board` |
| 7 | A single search can be run on its own without changing the one-tap main trigger | ✓ VERIFIED | `tests/pipeline/test_single_search_run.py::test_a_per_search_run_fetches_only_that_searchs_criteria` + `::test_the_union_run_still_unions_every_enabled_search`; the global trigger deliberately fetches the union and stamps `last_run_at` (G6, user-approved) |

### 02-09 — Save/hide append-only events (6/6)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Save appends one `save`; unsave appends `unsave`; state projected from the latest event, never a column | ✓ VERIFIED | `event_repo._fold_events`; `tests/api/test_listing_events.py::test_posting_save_appends_one_event_and_the_row_reads_saved` (lane D) |
| 2 | UPDATE/DELETE on `listing_events` aborts with the Phase-1 append-only trigger | ✓ VERIFIED | `tests/db/test_listing_events.py::test_the_database_aborts_an_update_and_a_delete_of_an_event`, `::test_the_orm_cannot_update_or_delete_an_event_either` |
| 3 | A hidden listing leaves the default queue, reachable via `Hidden` with one-tap undo | ✓ VERIFIED | `tests/api/test_listing_events.py::test_hiding_removes_the_listing_from_the_queue_and_the_control_becomes_undo` |
| 4 | A saved listing appears under `Saved` and carries a star | ✓ VERIFIED | `tests/api/test_listing_events.py::test_posting_save_appends_one_event_and_the_row_reads_saved`; `_listing_row.html:30` |
| 5 | Toggling twice appends two rows and returns projected state; no event updated/deleted | ✓ VERIFIED | `tests/db/test_listing_events.py::test_save_then_unsave_projects_unsaved` |
| 6 | The page projection is one query, not one per row | ✓ VERIFIED | `tests/db/test_listing_events.py::test_state_for_a_whole_page_is_one_query` |

### 02-10 — Run history (5/5)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | `GET /runs` lists one row per run, newest first, with times/trigger/duration/per-source counts/dedup/filter/errors | ✓ VERIFIED | `run_repo.list_runs`; `tests/api/test_run_history.py::test_runs_render_newest_first_and_stably` (lane D) |
| 2 | Each run row shows the persisted reason; expansion reveals counts + bounded raw stage log | ✓ VERIFIED | `tests/api/test_run_history.py::test_the_detail_fragment_carries_the_stage_log_and_the_per_rule_counts`; `runs.html:65-67` |
| 3 | Queue page carries a compact last-run strip linking to `/runs`, through the existing run-fragment renderer | ✓ VERIFIED | `app/web/routes.py` last-run strip; `queue.html`; `tests/api/test_run_reason.py::test_the_strip_links_to_the_run_history` |
| 4 | An unfinished run renders in-flight, never as completed with empty duration | ✓ VERIFIED | `run_repo._duration` returns `None`; `tests/api/test_run_history.py::test_an_unfinished_run_renders_in_flight_with_an_em_dash` |
| 5 | The history surface is read-only — no exposed route mutates a run | ✓ VERIFIED | `app/api/runs.py` history routes are `GET` only (`:125,:142,:163`); `tests/api/test_run_history.py::test_two_identical_requests_return_identical_bodies` |

### 02-11 — Queue links, dismiss-all, guarded reset (7/7)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Title links to the posting in a new tab with `rel="noopener noreferrer"`, plain text fallback; one link per `listing_sources` row + `Apply` only when the employer URL genuinely differs; only http(s) reaches `href` | ✓ VERIFIED | `queue_repo.py:391-403,432-466,523-524`; `_listing_row.html:37,48`; `tests/db/test_queue_row_links.py` (11), `tests/api/test_queue_links.py` (7) |
| 2 | `Dismiss all queued listings` hides every listing the default queue shows, reads the page back, survives a reload; `Unhide` restores one row | ✓ VERIFIED | `routes.py:174-217,338-376`; `queue_list.html:35-42`; `tests/api/test_queue_dismiss.py` (12) — whole-queue, re-read, hidden-gate, ceiling cases |
| 3 | One `hide` event per listing through `append_event` tagged `context={"surface":"queue_dismiss"}`; untouched: already-hidden, absorbed twin, latest-run-excluded | ✓ VERIFIED | `event_repo.py:188-218`; `routes.py:63-68`; `test_dismiss_events_record_the_bulk_surface`, `test_dismiss_does_not_touch_an_absorbed_twin`, `test_dismiss_with_the_hidden_toggle_does_not_rehide_hidden_rows`, `test_dismiss_ignores_the_excluded_toggle_and_spares_excluded_rows` |
| 4 | `GET /settings` renders danger zone, counts, token, fifth current `Settings` nav link; `POST /settings/reset` → 400/409/409/500 with the corpus untouched | ✓ VERIFIED | `settings.py:80-119,211-291`; `settings.html:29-52`; `base.html:32`; `tests/api/test_settings_page.py` (8), `tests/api/test_settings_reset.py` guard tests |
| 5 | Happy path: `VACUUM INTO` to `<db_dir>/reset-backups/jobsearch-<UTC timestamp>Z.db` before the first delete, child-first one transaction, keeps `searches`/`filter_rules`/`sources`, reports the filename **on a corpus whose `listing_events` is non-empty**; the `BEFORE DELETE` trigger is suspended from its `sqlite_master` DDL inside that transaction and re-armed before commit, so a delete-phase failure rolls deletes+suspension back and renders "nothing was deleted" | ✓ VERIFIED | `settings.py:126-151,293-323`; `test_the_snapshot_holds_the_pre_reset_rows` (3 events), `test_a_correct_token_empties_the_corpus_and_keeps_configuration`, `test_the_append_only_trigger_is_re_armed_and_still_enforced`, **`test_a_failed_delete_rolls_back_and_re_arms_the_trigger` (ran: 1 passed)** |
| 6 | `build_engine` disables driver transaction control (`isolation_level = None`) and issues explicit `BEGIN` on `sync_engine`, making DDL transactional; blast radius checked (pragmas, `expire_on_commit`, every `begin_nested()` site, Alembic's separate sync engine) and the locked-database caveat recorded | ✓ VERIFIED | `app/db/session.py:45-70`; blast radius in `02-11-SUMMARY.md` + `docs/implementation-notes.md` (`d436425`); proven through the app by the truth-5 rollback test |
| 7 | At HEAD the suite is 712 passed / 2 deselected and `ruff check app tests` is clean; all 15 commits in `228fcad..d436425` are ancestors of HEAD; the operator confirmed the rebuilt container runs the whole feature | ✓ VERIFIED | Ran this pass: `pytest -q` → **712 passed, 2 deselected in 162.99s**; `ruff` → **All checks passed!**; `git merge-base --is-ancestor` ×15 → all OK; `02-UAT.md` item 9 `pass (2026-09-17)` |

**Score:** 61/61 truths verified (0 present-but-behavior-unverified). **Verdicts changed from the prior report: none** (`verdicts_changed: 0`). The 7 new truths are all `✓ VERIFIED`; the 54 previously-certified truths are unchanged.

## Required Artifacts (Level 1–2: exist + substantive)

All **119** fingerprinted files exist and are substantive. The artifacts **new in this delta**:

| Artifact group | Status | Details |
| -------------- | ------ | ------- |
| Settings surface | ✓ VERIFIED | `app/api/settings.py` (333 lines — guards, snapshot, trigger suspend/restore, ordered deletes), `app/web/templates/html/settings.html` (53 lines), routes registered at `app/main.py:60` |
| Queue-row links | ✓ VERIFIED | `app/db/repositories/queue_repo.py` (`SourceLink`/`QueueRow.url`/`source_links`, `_http_url`, the batched read), `_listing_row.html` (anchor + per-source links) |
| Dismiss | ✓ VERIFIED | `app/db/repositories/event_repo.py::hide_listings`, `app/web/routes.py::queue_dismiss` + `_queued_listing_ids`, `queue_list.html` dismiss button |
| Transactional DDL | ✓ VERIFIED | `app/db/session.py:45-70` — `isolation_level=None` + explicit `BEGIN` on `sync_engine` |
| New tests | ✓ VERIFIED | `tests/db/test_queue_row_links.py` (347 lines), `tests/api/test_queue_links.py` (228), `tests/api/test_queue_dismiss.py` (353), `tests/api/test_settings_page.py` (76), `tests/api/test_settings_reset.py` (377), `tests/db/test_reset_coverage.py` (78) |
| Cycle docs | ✓ VERIFIED | `docs/superpowers/specs/2026-09-17-queue-links-dismiss-and-reset-design.md`, `docs/superpowers/plans/2026-09-17-queue-links-dismiss-and-reset.md`, `docs/implementation-notes.md` (header reconciled to `d436425`, live confirmation + `712 passed` recorded) |

Prior artifacts (migration engine, stylesheet layer, shared UI filters, the 38 test modules, the repositories/pipeline/API/templates) remain present and substantive; the full 712-test suite exercises them.

## Key Link Verification (Level 3: wired)

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| **NEW** `_listing_row.html` | `QueueRow.url` / `source_links` | the batched `listing_sources` read in `queue_repo._enrich` | ✓ WIRED | `queue_repo.py:432-466` → `:523-524`; no per-row query, and the `POST /listings/{id}/events` swap uses the same `read_row` path (`:530`) |
| **NEW** `POST /queue/dismiss` | `routes._queued_listing_ids` → `event_repo.hide_listings` → `append_event` | the repository never commits; the route owns the single `commit()` and then re-reads | ✓ WIRED | `routes.py:358-376`; `event_repo.py:188-218` |
| **NEW** `POST /settings/reset` | `snapshot_database` → `_suspend_append_only_trigger` → `RESET_DELETE_ORDER` deletes → `_restore_append_only_trigger` → one commit → banner naming `snapshot.name` | every guard returns before the first `delete()` | ✓ WIRED | `settings.py:272-332` |
| **NEW** trigger suspension | `app/db/session.build_engine` explicit `BEGIN` | the `DROP TRIGGER` rolls back with the deletes only because DDL is transactional | ✓ WIRED | `settings.py:293-303`; `session.py:62-68`; proven by `test_a_failed_delete_rolls_back_and_re_arms_the_trigger` |
| **NEW** `RESET_BLOCKING_TABLES` | `settings._blocking_row` + `tests/db/test_reset_coverage.py` | the guard enumerates `Base.metadata` children of `listings`/`runs` dynamically and fails closed for a new table | ✓ WIRED | `settings.py:160-168`; `tests/db/test_reset_coverage.py:27-66` |
| **NEW** `GET /settings` nav | `base.html:32` | fifth `nav-link` with `nav-current`/`aria-current` | ✓ WIRED | `tests/api/test_settings_page.py::test_the_nav_marks_settings_as_the_current_page` |
| `app/main.py` | searches/events/runs/web/settings routers | `include_router` | ✓ WIRED | `app/main.py:56-60` |
| `run_pipeline` | `_resolve_fetch_queries` → `_fetch_all` → `run_dedup_stage` → `run_filter_stage` → `_finish` | sequential calls | ✓ WIRED | `app/pipeline/run.py:718,761,824,841,881` |
| `filter_stage` | `criteria.rule_specs_from` → `filter.evaluate` → `exclusion_repo.record_exclusions` | repository→domain→repository | ✓ WIRED | `filter_stage.py:82,100,126` |
| `queue_repo.read_queue` | `event_repo.hidden_predicate` / `saved_predicate` | derived predicates | ✓ WIRED | `queue_repo.py:311-314` |
| `revert_merge` route | `dupe_repo.revert_merge` → queue visibility predicate | `reverted_at` flag | ✓ WIRED | `app/api/runs.py:241`; `queue_repo._not_absorbed_twin` |
| `queue` route | `render_run_fragment` (one run renderer) | `_last_run_strip` | ✓ WIRED | `app/web/routes.py`; `RunFragmentSource` Protocol |
| `POST /listings/{id}/events` | `event_repo.append_event` → `queue_repo.read_row` | same row partial | ✓ WIRED | `app/api/events.py:114,127-155` |
| Every page + HTMX fragment | `app/web/filters.py` (`human_label`, `format_datetime`) | `make_templates` factory | ✓ WIRED | `app/web/template_env.py:17-21` |

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| Queue rows | `QueuePage.rows` | `read_queue` → `listings` (+ `listing_fts` when querying) | Yes — real FTS/listings SQL, no static fallback | ✓ FLOWING |
| **NEW** Row title link | `QueueRow.url` | `listings.canonical_url` through `_http_url` | Yes — the stored posting URL, gated to http(s) | ✓ FLOWING |
| **NEW** Row source links | `QueueRow.source_links` | one batched `select(ListingSource...)` over the page ids | Yes — one `SourceLink` per `listing_sources` row; employer link only when it differs | ✓ FLOWING |
| **NEW** Settings counts | `_settings_context()["counts"]` | `select(func.count()).select_from(Base.metadata.tables[table])` per table | Yes — live row counts, no literal | ✓ FLOWING |
| **NEW** Dismiss fragment | `#queue-list` contents | `_read_queue_page` **after** the commit | Yes — re-read from the DB, not the in-memory delta | ✓ FLOWING |
| **NEW** Reset banner | `banner` | `snapshot.name` / the refusal reason | Yes — the on-disk snapshot filename | ✓ FLOWING |
| Queue company | `QueueRow.company` | `Listing` ⋈ `Company` outer-join (`queue_repo.py:385-386,447`), falling back to `company_norm` | Yes | ✓ FLOWING |
| Merge rate | `MergeRate.merged/fetched` | `count_merges_for_run` (windowed) / latest `runs.fetched_count` | Yes; `None` at zero denominator | ✓ FLOWING |
| Exclusion chips | `QueueRule.kind/count` | `rule_counts_for_listings` + `_page_rule_counts` | Yes — per latest run | ✓ FLOWING |
| Save/hidden flags | `ListingState.saved/hidden` | `state_for_listings` (one query) | Yes | ✓ FLOWING |
| Last-run strip | `RunSummary` → `render_run_fragment` | `run_repo.list_runs` | Yes | ✓ FLOWING |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| **Full suite at HEAD `502fae1`** | `.venv/bin/python -m pytest -q` | **712 passed, 2 deselected in 162.99s** | ✓ PASS |
| **02-11 feature lanes** (links, dismiss, settings page, reset, coverage) | `pytest -q tests/db/test_queue_row_links.py tests/api/test_queue_links.py tests/api/test_queue_dismiss.py tests/api/test_settings_page.py tests/api/test_settings_reset.py tests/db/test_reset_coverage.py` | **52 passed in 24.47s** | ✓ PASS |
| **Guard lanes** (auth seam, stylesheet, no-CDN, ingest e2e) | `pytest -q tests/test_auth_seam.py tests/test_stylesheet_coverage.py tests/test_no_cdn.py tests/pipeline/test_ingest_e2e.py` | **21 passed in 6.97s** | ✓ PASS |
| **Truth-5 discriminator (named)** | `pytest -q "tests/api/test_settings_reset.py::test_a_failed_delete_rolls_back_and_re_arms_the_trigger"` | **1 passed in 6.07s** | ✓ PASS |
| **Plan structure** | `gsd-tools query verify.plan-structure .../02-11-PLAN.md` | `valid: true`, 0 errors, 0 warnings, **8 tasks** | ✓ PASS |
| **Commit ancestry** | `git merge-base --is-ancestor <sha> HEAD` ×15 | all OK | ✓ PASS |
| **Lint** | `.venv/bin/python -m ruff check app tests` | **All checks passed!** | ✓ PASS |
| Full suite at HEAD `5726cd3` — *prior pass* | `.venv/bin/python -m pytest -q` | 660 passed, 2 deselected in 91.23s | ✓ PASS (baseline) |
| Dedup lane / union-run lane / filter-forms lane — *prior pass* | (see prior method) | 55 / 50 / 96 passed | ✓ PASS (baseline) |
| htmx fail-first — *prior pass* | remove both `hx-include`, run `tests/api/test_rule_form_payloads.py` | 8 failed; `git diff --stat` empty after restore | ✓ PROVEN (baseline) |
| Migration regression + fail-first — *earlier pass* | `tests/db/test_migration_contract.py::test_upgrade_populated_0001_to_head` | 1 passed; with pragma `ON`, 1 failed (`FOREIGN KEY constraint failed / [DROP TABLE runs]`) | ✓ PASS / PROVEN (baseline) |

## Probe Execution

Step 7c: **SKIPPED** — no `scripts/*/tests/probe-*.sh` exist and Phase 2 declares no probe. (The scraper-survival probe is a Phase-1 deliverable; `docs/probes/2026-09-15-scraper-survival.md` is Phase-1 evidence.)

## Requirements Coverage

**Re-verified this delta.** All 15 Phase-2 requirement IDs are claimed by the eleven PLAN frontmatters and still marked Complete in `REQUIREMENTS.md` (`- [x]` and `| <ID> | Phase 2 | Complete |`). **No orphaned IDs and no unclaimed Phase-2 IDs.** `02-11-PLAN.md` declares `requirements: [QUEUE-08]`, so QUEUE-08 now has two source plans (02-09 and 02-11); the dismiss arm genuinely advances it.

**Requirement traceability gap — deliberate and documented.** The **posting-links arm**, the **guarded-reset arm**, and the **post-completion fix arc** are **shipped but untraced**: no `REQUIREMENTS.md` ID describes them. `02-11-PLAN.md`/`02-11-SUMMARY.md` record that adding IDs retrospectively was considered and **rejected** — a requirement written after and derived from the implementation traces nothing, and retro-fitting must-haves onto a phase already certified would risk making a passed verification inconsistent. The honest consequence, stated here rather than hidden: **phase 2's coverage report does not list these arms by requirement ID.** This is a documented gap in traceability, not a gap in implementation; every arm is verified above by truth and test, not by requirement. If real IDs are wanted, that is a separate intent-level exercise.

| Requirement | Source Plan(s) | Description | Status | Evidence |
| ----------- | -------------- | ----------- | ------ | -------- |
| QUEUE-03 | 02-02, 02-04 | Same job on two sources merged, reversible audit | ✓ SATISFIED | `dedup_stage`, `dupe_repo.apply_merge`, `listing_dupes`; dedup lane (55) incl. the 3-way reproduction and the source guard |
| QUEUE-04 | 02-06 | Revert an incorrect merge | ✓ SATISFIED | `revert_merge` + revert route; dedup lane (55) |
| QUEUE-06 | 02-07 | Full-text search the queue | ✓ SATISFIED | `search_query`, `queue_repo` FTS branch; full suite (712) |
| QUEUE-07 | 02-01, 02-07 | New-since-last-visit + stale | ✓ SATISFIED | `state_repo`, `_row_flags`; full suite (712) |
| QUEUE-08 | 02-09, **02-11** | Save/hide as append-only events | ✓ SATISFIED (extended) | `event_repo.append_event`; the 02-11 dismiss arm appends one `hide` per listing tagged `surface=queue_dismiss`; feature lanes (52) |
| QUEUE-09 | 02-06 | Merge rate + rows behind it | ✓ SATISFIED | latest-run window intact; 33%/67% regression asserts the window; caveat: `fetched_count` sums fetch events (follow-up, not a gap) |
| CRIT-01 | 02-01, 02-03, 02-08 | Create/edit/delete named criteria | ✓ SATISFIED | `search_repo` write side, `searches.py`, `criteria.html`; filter/forms lane (96) |
| CRIT-02 | 02-05 | Criteria versioned for reproducibility | ✓ SATISFIED | `criteria_snapshot_json` written before the fetch (`run.py:711`); filter/forms lane (96) |
| CRIT-03 | 02-08 | Enable/disable without delete | ✓ SATISFIED | toggle route, version semantics; filter/forms lane (96) |
| FILT-01 | 02-02, 02-03, 02-05 | Deterministic reject before any LLM call | ✓ SATISFIED | `filter.evaluate`; no LLM import under `app/pipeline`; empty `llm_calls`; full suite (712) |
| FILT-02 | 02-03, 02-05 | Every rejection records rule + why | ✓ SATISFIED | `listing_exclusions(rule_id, rule_kind, detail_json)`; full suite (712) |
| FILT-03 | 02-07 | See why a specific listing was excluded | ✓ SATISFIED (chip judged sufficient at UAT item 5) | excluded toggle + chips; `detail_json` recorded, matched term not rendered; SEED-001 |
| FILT-04 | 02-01, 02-08 | Tune rules from UI without a code change | ✓ SATISFIED | DB-backed `filter_rules`, per-kind forms, no raw JSON; filter/forms lane (96) |
| RUN-03 | 02-01, 02-05, 02-10 | Run records what it did/found/why | ✓ SATISFIED | `run_reason` + stage log + `/runs` + last-run strip; union/run lane (50) |
| RUN-04 | 02-10 | Run history | ✓ SATISFIED | `run_repo.list_runs`, `runs.html`, GET-only history; full suite (712) |

## Roadmap Success Criteria

| # | Success Criterion | Status | Evidence |
| - | ----------------- | ------ | -------- |
| 1 | Deduplicated queue; same job on two sources appears once, with merge rate and rows visible, incorrect merge revertible | ✓ VERIFIED | `app/pipeline/dedup_stage.py`, `app/domain/dedup.py`, `dupe_repo.apply_merge/revert_merge/merge_rate/list_merges`, `merges.html`; dedup lane (55) |
| 2 | For any excluded listing, which rule fired and why is visible | ✓ VERIFIED | `queue_repo._enrich`, `_listing_row.html:42-44`, `tests/api/test_queue_excluded.py`; `detail_json` recorded (FILT-02); chip judged sufficient at UAT item 5 (SEED-001) |
| 3 | Create/edit/enable/disable/delete named criteria + tune rules from the UI without a code change; runs reproducible against a criteria version | ✓ VERIFIED | `app/api/searches.py`, `search_repo.py`, `criteria.html`, `runs.criteria_snapshot_json`; filter/forms lane (96) |
| 4 | Full-text searchable queue; save/hide as append-only events; new-since-last-visit and stale distinguishable | ✓ VERIFIED | `search_query.py`, `queue_repo` (bound `MATCH`), `event_repo` (append-only + projection, now also the bulk dismiss), `state_repo`; full suite (712) |
| 5 | Run history: each run records what it did, what it found, and — when the queue is empty — why | ✓ VERIFIED | `run_repo.list_runs`, `run_reason.py`, `runs.html`, queue last-run strip; union/run lane (50) |

**Note on the 02-11 arms vs the Success Criteria:** the posting-links, dismiss and reset work does not map to an SC by requirement ID. The dismiss arm strengthens **SC4**'s "save/hide as append-only events" (it appends through the same path). The links and reset are product additions that the SCs neither name nor contradict — they are covered by the 02-11 must-haves above, not by this table. No SC regressed.

## Migration defect — independently verified, not merely tested

The migration defect remains genuinely fixed in the code path:

- `alembic/env.py:37-67` defines `_apply_migration_pragmas` executing `PRAGMA foreign_keys=OFF` (`:63`), attached to the migration engine's `connect` event (`:95`). The runtime engine still enforces `PRAGMA foreign_keys=ON` (`app/db/session.py:38`) — the fix is scoped to migrations only, and the `build_engine` transaction change does not disturb the PRAGMAs (`apply_sqlite_pragmas` remains the first `connect` listener, `session.py:60`).
- The regression test is non-vacuous: the `populated_0001` fixture seeds one non-NULL `run_id` row in each of `listing_events`, `listing_exclusions`, `scores`, `llm_calls`, `source_request_log` (`tests/conftest.py` `RUN_REFERENCING_TABLES`), then asserts revision `0002`, no seeded row loss, both new tables, the four new `runs` columns, `listing_events.criteria_version`, `ck_runs_reason` and the surviving `ck_runs_trigger`/`ck_runs_status` CHECKs, and both `listing_dupes` indexes.
- Fail-first proof (earlier pass): reverting the pragma to `ON` fails `test_upgrade_populated_0001_to_head` at `:99` with `FOREIGN KEY constraint failed / [SQL: DROP TABLE runs]`.

## Nyquist Residual Skips — disposition

The Nyquist audit (`02-VALIDATION.md`) holds `nyquist_compliant: false` and names two residual skips. **Both remain accepted; neither is escalated.**

| # | Residual | Disposition | Rationale |
| - | -------- | ----------- | --------- |
| R1 | No `alembic downgrade 0001 → upgrade head` round-trip test. `0001` is the one-way door. | **ACCEPTED** | `downgrade()` exists only for tooling coherence; manually probed 2026-09-16 (both empty and populated DBs complete `head → 0001 → head` with row counts preserved). The populated **upgrade** direction now has a fail-first regression test. |
| R2 | "No route mutates a run" proven structurally rather than by a route-method inventory. | **ACCEPTED** | History routes are `GET /runs`, `GET /runs/{run_id}`, `GET /runs/{run_id}/status` (`app/api/runs.py:125,142,163`); the module's only POSTs are `POST /runs` (create) and `POST /merges/{id}/revert`. |

## Test Quality Audit

| Test File | Linked Req | Active | Skipped | Circular | Assertion Level | Verdict |
|-----------|-----------|--------|---------|----------|-----------------|---------|
| `tests/api/test_settings_reset.py` | QUEUE-08 / 02-11 #4–5 | 9 | 0 | No | Behavioral (multi-step: seed non-empty corpus → reset → count/snapshot/trigger assertions) | ✓ PROVES |
| `tests/api/test_queue_dismiss.py` | QUEUE-08 / 02-11 #2–3 | 12 | 0 | No | Behavioral (write → re-read → event-context assertions) | ✓ PROVES |
| `tests/db/test_queue_row_links.py` / `tests/api/test_queue_links.py` | 02-11 #1 | 11 + 7 | 0 | No | Value + Behavioral (exact `href`/`rel`/fallback assertions; the non-web case asserts the scheme is absent from the body) | ✓ PROVES |
| `tests/db/test_reset_coverage.py` | 02-11 #5 | 5 | 0 | No | Structural (enumerates `Base.metadata` children dynamically; fails closed for a new table) | ✓ PROVES |

**Disabled tests on requirements:** 0. **Circular patterns detected:** 0 (no test generates its expected values from the system under test; the reset tests read an independent `sqlite3` connection for the snapshot). **Insufficient assertions:** 0. The truth-5 discriminator uses `monkeypatch` to force a delete failure — a deliberate fault injection, not a mock of the behaviour under test: the trigger suspension has already executed when the injected failure fires, so the rollback assertion is meaningful.

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `app/web/routes.py` | 156-171 | A dismissed queue over the 10,000 ceiling returns a `400` fragment htmx does not swap | ℹ️ Info (follow-up) | Unreachable at realistic sizes; documented in `02-11-SUMMARY.md` flagged assumption 4. Advisory |
| `app/api/settings.py` | 133-148 | `VACUUM INTO` destination interpolated as an escaped SQL literal, not bound | ℹ️ Info (follow-up) | Safe while the path stays server-derived (it is); documented in `02-11-SUMMARY.md` flagged assumption 5. Advisory |
| `app/db/repositories/queue_repo.py` | 519-523 | `_page_rule_counts` count is run-wide | ℹ️ Info (product call) | Deliberate; judged sufficient at UAT item 5 |
| `Dockerfile` | 38-50 | No post-install assertion that `rapidfuzz` is present in the built image | ℹ️ Info (follow-up) | Manifest-level agreement tested; image-level presence not. Advisory |
| `app/domain/dedup.py` | 151 | `fuzz.token_set_ratio` used as a diagnostic only | ℹ️ Info | Non-deciding; the gate is `token_sort_ratio` |
| `app/pipeline/run.py` | 708-716,737 | `criteria_compile` prepended then `stage_log[-12:]` truncates from the same end | ℹ️ Info | Latent only with >9 sources; not reachable with 2 adapters |
| `app/db/repositories/exclusion_repo.py` | 30-40,144-177 | `ExclusionRecord`/`exclusions_for_run` uncalled | ℹ️ Info | `detail_json` has no UI consumer; closed as sufficient at UAT item 5 |
| `app/api/searches.py` etc. | — | No CSRF token on POSTs | ℹ️ Info | Accepted under "Auth: none in v1"; `app/api/settings.py:12-15` documents that this becomes a genuine gap once session auth lands |
| `app/pipeline/run.py` | 576, 515 | `fetched_count` sums fetch events while `merge_rate()` counts distinct merge rows | ℹ️ Info (follow-up) | Units diverge only with 2+ enabled searches on one board — see Follow-ups |
| `app/db/models.py` / `search_repo.py` / `api/searches.py` | 270 / 73,503 / 316 | `searches.is_default` read only into the view model | ℹ️ Info (follow-up) | Vestigial after the union design |
| `app/pipeline/run.py` | 738, 754 | Fetch dedupe keyed on the **uncompiled** `(adapter.name, SearchQuery)` | ℹ️ Info (follow-up) | Over-fetch only (safe direction) |
| `app/pipeline/run.py` | 792-799 | `errors_json` can carry several entries per source | ℹ️ Info (follow-up) | Renders fine |

Debt-marker gate: **no `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers** anywhere under `app/` (re-checked this delta with `rg`).
No stub/hollow implementations found: every rendered value traces to a real query (Level 4 above).
**No regression introduced by this delta:** the new code is additive (a new route module, a new template, new repository members) or scoped (`build_engine`'s listeners, the dismiss route). No Step 7 blocker was raised, so the convergence evidence gate has nothing to bound.

**Two pre-existing discrepancies, intentionally unfixed — recorded, not new findings:**

- `tests/api/test_queue_links.py`'s docstring labels its cases `(QUEUE-06)`, a different requirement (the file actually covers the 02-11 posting-links arm). Pre-existing, flagged in `02-11-SUMMARY.md` §Flagged assumptions 2.
- The SDD ledger's close-out line says "11 commits"; the range is 15 once the fix arc is included. Pre-existing, flagged in `02-11-SUMMARY.md` §Flagged assumptions 3.

## Manual Verification — closed (UAT)

`02-UAT.md` records **9/9 items pass** (`status: complete`, `passed: 9, pending: 0, issues: 0`), so there is **no outstanding human-verification item** and the automated `status` is `passed`. Items 1–5 were relabelled from the non-canonical `satisfied` to `pass` on 2026-09-17 with **no result change** (dates, evidence and operator quotes untouched); items 6–9 were added for the 02-11 deliverables and operator-confirmed. Phase completion itself comes from `/gsd-verify-work`, not from this report.

| # | Item | Result | Evidence |
| - | ---- | ------ | -------- |
| 1 | Tune θ against the first real corpus | **pass** (2026-09-16) — θ=88 retained | True duplicates span 89.1–100 while non-duplicates span 70–97.9; the distributions overlap and no θ separates them. θ=88 is approximately correct and not the discriminating lever |
| 2 | Merge-rate band sanity check | **pass** (2026-09-16) — band does not transfer | Defensible figure 6/104 ≈ 5.8%, below the 10–15% research band its own caveat allows; G2(a) implemented by `30a19f0` |
| 3 | Compose smoke | **pass** (2026-09-16) — operator-confirmed | `scripts/compose-smoke.sh` PASS; revision `0002`, 104 listings, `rapidfuzz 3.14.6`, `/`, `/merges`, `/runs`, `/searches` all 200 |
| 4 | `rapidfuzz` pin sign-off | **pass** (2026-09-16) | Human answered the `blocking-human` checkpoint "approved" |
| 5 | Excluded-listing chip vs SC2 | **pass** (2026-09-16) — judged sufficient for now | User decision recorded verbatim; capability present; SEED-001 captures the distinct ask |
| 6 | A queue row links to its posting and to each source | **pass** (2026-09-17) — operator confirmed on the live instance ("all pass") | Real-corpus judgement of the links and the "Apply only when different" rule |
| 7 | Dismiss the whole queue with one action | **pass** (2026-09-17) — operator confirmed ("all pass") | Scope and the above-ceiling edge judged by eye |
| 8 | The settings page renders its danger zone | **pass** (2026-09-17) — operator confirmed ("all pass") | Visual hierarchy and token discoverability |
| 9 | The guarded reset on the live database | **pass** (2026-09-17) — operator confirmed ("all pass") | **This is the case that failed with a bare `500` before `c16023a`**; the operator rebuilt the container and confirmed the reset now succeeds and the queue stays empty |

**UAT-surfaced defects and disposition (re-read against `02-UAT.md` @ HEAD):** G1 (host `.env` never reached the container) → **FIXED** by `dfb7414`. G2 (merge rate reads 0% in steady state) → **DECISION IMPLEMENTED** by `30a19f0`. G3 (one-sided NULL location depressed the Tier-2 score) → **FIXED** by `a51a133`. G4 (Tier-2 over-merged same-source pairs) → **FIXED** by `819bb9e`. G5 (browser rule form sent an empty body) → **FIXED** by `edcbe68`. G6 (global Run ignored saved searches) → **FIXED** by `d222588`/`38c3b23`/`87ff974`; "nothing new" was the correct outcome. G7 (Irish county code broke the location rule) → **FIXED** by `7d0bff5`/`f01ae1c`. The 02-11 live `500` on the reset → **FIXED** by `c16023a` (+ `6720f1c` logging, `d436425` decision), re-verified at truth 5.

**Is any human item still open?** **No.** All nine UAT items are `pass`, and every gap the real-corpus run surfaced now has a code fix with an automated test (the reset fix's durable evidence is `test_a_failed_delete_rolls_back_and_re_arms_the_trigger`, run green this pass). The only residual human-touching activity is the operator's own host/data cleanup on the live instance (`02-UAT.md:531`) — a watch item, not a code-verification truth, and it opens no human-verification item.

### Follow-ups left open — judged follow-up vs phase gap

None is a phase gap; each is a non-blocking cleanup/semantics item.

| Follow-up | Judgement | Reasoning |
| --------- | --------- | --------- |
| `fetched_count` sums fetch events, so `merge_rate()`'s units diverge | **Follow-up** | Latent (2+ enabled searches on one board); QUEUE-09 holds literally; needs a semantics decision |
| `searches.is_default` is dead | **Follow-up** | No query-resolution consumer; zero behavioural effect; a cleanup task |
| the fetch dedupe key uses the uncompiled query | **Follow-up** | Over-fetch only (safe direction) |
| `errors_json` can carry multiple entries per source | **Follow-up** | Renders correctly; the run badge uses the merged status |
| over-ceiling dismissal gives no visible feedback | **Follow-up** | Advisory; needs an app-wide htmx error handler |
| `VACUUM INTO` literal vs bound parameter | **Follow-up** | Advisory; safe while the path stays server-derived |

## Gaps Summary

**No must-have gap was found.** All **61** plan `must_haves.truths` (54 previously certified + 7 from 02-11), all five roadmap Success Criteria, all required artifacts (Levels 1–2), all key links (Level 3) and the dynamic data flows (Level 4) hold at HEAD `502fae1`. All 15 Phase-2 requirement IDs are accounted for and satisfied. `ruff` is clean; no debt markers exist; the suite is 712 passed / 2 deselected. **No truth's verdict changed in this delta** (`verdicts_changed: 0`).

The 02-11 delta is verified end to end: the http(s)-gated posting links, the whole-default-queue dismiss through the append-only event path, the settings page and its four ordered refusals, and the reset that snapshots with `VACUUM INTO`, suspends the append-only trigger inside its own transaction and re-arms it before commit. **Truth 5 — the discriminator** — is backed by a committed test that forces a delete-phase failure after the `DROP TRIGGER` and asserts the deletes and the suspension roll back together; that test is run green in this pass. The `build_engine` transaction change (truth 6) is the precondition that makes it safe, and its blast radius is recorded as a deliberate decision.

Observations that do **not** block the phase:

- **Requirement traceability gap (deliberate):** the posting-links, guarded-reset and fix-arc arms are shipped but untraced — no `REQUIREMENTS.md` ID covers them. Adding IDs was considered and rejected (`02-11-PLAN.md`/`02-11-SUMMARY.md`). Recorded honestly above; not an implementation gap.
- **Advisory (02-SECURITY W-01):** the built image is not asserted to contain `rapidfuzz`; manifest agreement is tested. Recommended follow-up.
- **Advisory (FILT-03/SC2, closed at UAT item 5):** `detail_json` and the firing rule id are not rendered.
- **Advisory (new):** the over-ceiling dismissal's 400 is not swapped by htmx; the `VACUUM INTO` literal is unbound.
- **Pre-existing, intentionally unfixed (recorded, not new):** the `(QUEUE-06)` mislabel in `tests/api/test_queue_links.py`'s docstring; the SDD ledger's stale "11 commits" line.
- **Info (follow-ups, non-blocking):** the six follow-ups tabulated above.

Status is **passed**: automated verification is complete and green at HEAD `502fae1`, the 9/9 UAT items are `pass`, the 02-11 fix arc is verified against the code and its discriminator test, and no outstanding human-verification item remains. The phase's completion is still gated on `/gsd-verify-work`.

---

_Verified: 2026-09-17T15:06:06Z_
_Verifier: the agent (gsd-verifier)_
