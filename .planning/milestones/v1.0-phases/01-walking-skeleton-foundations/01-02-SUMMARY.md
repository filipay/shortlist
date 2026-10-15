---
phase: 01-walking-skeleton-foundations
plan: 02
subsystem: testing
tags: [pytest, sqlite, fts5, alembic, schema-contract, migration, pii, append-only]

# Dependency graph
requires:
  - phase: 01-walking-skeleton-foundations (plan 01)
    provides: "migration 0001; alembic upgrade head runnable against a temp file; the tests/conftest.py fixtures (migrated_db, db_engine, session_factory, db_session, client)"
provides:
  - "the 9-item ROADMAP migration-0001 acceptance checklist as executable assertions"
  - "a negative schema test proving no email/phone-shaped column exists and the JSON-column set is a closed allow-list"
  - "FTS5 external-content + three-trigger maintenance proof (insert / update / delete round-trip through MATCH)"
affects: ["Phase 1 plans 01-03..01-07", "Phase 2 (dedup + FTS search rely on these indexes and triggers)"]

# Actuals (#2632) — pairs with the plan's estimate (34000 tokens / 2 tasks, confidence: low).
# Same estimateTokens scale: chars/4 over the realized diff (20303 chars).
actuals:
  tokens: 5076
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns: ["migration-as-schema-test", "negative schema assertion (PII unrepresentable)", "FTS5 trigger round-trip proof", "closed allow-list for whole-of-DB property"]

key-files:
  created:
    - tests/db/test_migration_contract.py
    - tests/db/test_no_pii_columns.py
    - tests/db/test_fts_triggers.py
  modified: []

key-decisions:
  - "Introspection uses PRAGMA table_info / PRAGMA index_list / PRAGMA index_info / sqlite_master only — never the ORM metadata — so model/DDL drift fails the contract test."
  - "The JSON-column check asserts exact equality against a per-table allow-list rather than a subset, so any new free-form blob (the realistic PII vector) fails the test until it is added deliberately."
  - "The append-only test asserts sqlite3.IntegrityError plus the 'append-only' message (RAISE(ABORT) maps to SQLITE_CONSTRAINT in Python), which distinguishes a real trigger from a silently-absent one."
  - "FTS5 MATCH terms are bound parameters, never string-interpolated — the same discipline Phase 2's search port must keep."
  - "The contract test was strengthened beyond the plan's literal nine actions to back the must_haves truths: content_hash is VARCHAR(64), an INSERT omitting the timestamps/hash must fail, and applications.cv_artifact_id is verified as a FK via PRAGMA foreign_key_list."

patterns-established:
  - "Schema regressions are caught by executing `alembic upgrade head` on a temp file and introspecting the result, never by reading model definitions."
  - "Whole-of-database invariants (no PII column, closed JSON set) are asserted by enumerating sqlite_master and iterating every table."
  - "An index's *shape* is asserted, not just its presence: uniqueness, partiality, column order, and the WHERE clause text."

# Declared by this plan (frontmatter `requirements`):
#   QUEUE-05, SRC-10
# Only QUEUE-05 is marked complete: `requirements.ready-ids` reports SRC-10 as
# blocked because plan 01-05 also declares it and has produced no SUMMARY yet.
requirements-completed: [QUEUE-05]

coverage:
  - id: D1
    description: "All 9 ROADMAP migration-0001 checklist items are executable assertions that pass against a freshly migrated temp database"
    requirement: "QUEUE-05"
    verification:
      - kind: integration
        ref: "tests/db/test_migration_contract.py#test_listings_timestamps_not_null"
        status: pass
      - kind: integration
        ref: "tests/db/test_migration_contract.py#test_listing_events_append_only"
        status: pass
      - kind: integration
        ref: "tests/db/test_migration_contract.py#test_scores_decomposition"
        status: pass
      - kind: integration
        ref: "tests/db/test_migration_contract.py#test_cv_artifacts_verification_and_blocked"
        status: pass
      - kind: integration
        ref: "tests/db/test_migration_contract.py#test_applications_cv_artifact_id"
        status: pass
      - kind: integration
        ref: "tests/db/test_migration_contract.py#test_dedup_indexes"
        status: pass
      - kind: integration
        ref: "tests/db/test_migration_contract.py#test_sources_capabilities_and_tos"
        status: pass
      - kind: integration
        ref: "tests/db/test_migration_contract.py#test_blocking_key_indexed"
        status: pass
      - kind: integration
        ref: "tests/db/test_migration_contract.py#test_alembic_at_revision_0001"
        status: pass
    human_judgment: false
  - id: D2
    description: "PII is unrepresentable in the Phase 1 schema: no email/phone-shaped column on any table, and the JSON-column set is a closed allow-list"
    requirement: "SRC-10"
    verification:
      - kind: unit
        ref: "tests/db/test_no_pii_columns.py#test_no_email_or_phone_columns"
        status: pass
      - kind: unit
        ref: "tests/db/test_no_pii_columns.py#test_json_columns_are_allow_listed"
        status: pass
    human_judgment: false
  - id: D3
    description: "listing_fts is FTS5 external-content over listings and its three triggers keep the index in sync across insert, update and delete"
    requirement: null
    verification:
      - kind: integration
        ref: "tests/db/test_fts_triggers.py#test_listing_fts_is_external_content"
        status: pass
      - kind: integration
        ref: "tests/db/test_fts_triggers.py#test_all_three_triggers_exist"
        status: pass
      - kind: integration
        ref: "tests/db/test_fts_triggers.py#test_orm_insert_is_searchable"
        status: pass
      - kind: integration
        ref: "tests/db/test_fts_triggers.py#test_update_and_delete_keep_index_in_sync"
        status: pass
    human_judgment: false
  - id: D4
    description: "When two listings share a first_seen_at the queue order is still deterministic (id descending as the tie-break)"
    requirement: "QUEUE-05"
    verification: []
    human_judgment: true
    rationale: "This is a backstop truth about the queue READ, which does not exist in this plan. The plan frontmatter explicitly delegates it: 'asserted by the queue read in plan 01-03'. Plan 01-03 must assert it (and does not inherit a test for it from here)."
  - id: D5
    description: "content_hash is stable for identical sanitised inputs and differs when title, company_name, location_raw or description differs"
    requirement: "QUEUE-05"
    verification: []
    human_judgment: true
    rationale: "The property belongs to the domain function (app/domain/listing.py, a plan 01-03 deliverable) which does not exist yet. This plan asserts only the schema half — content_hash is NOT NULL and VARCHAR(64), and an INSERT cannot omit it — so the behavioural half needs a plan 01-03 assertion."

# Metrics
duration: 5min
completed: 2026-09-15
status: complete
---

# Phase 01 Plan 02: Migration contract, PII-negative schema, FTS5 maintenance

**The 9-item ROADMAP migration checklist is now 9 failing-loud assertions, the schema provably cannot store recruiter PII, and the FTS5 index provably tracks inserts, updates and deletes through its triggers.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-09-15T17:20:33Z
- **Completed:** 2026-09-15T17:25:13Z
- **Tasks:** 2 of 2
- **Files modified:** 3 (all created)

## Accomplishments

- **The one-way door has an executable gate.** Each of the nine ROADMAP acceptance items is a test that introspects the migrated database (`PRAGMA table_info` / `index_list` / `index_info` / `sqlite_master`) and would fail on a schema regression: NOT NULL timestamps and hash, append-only `listing_events` that actually aborts UPDATE and DELETE, score decomposition, `cv_artifacts.verification_json` with a `'blocked'`-admitting CHECK, the nullable `applications.cv_artifact_id` FK, both D-19 dedup indexes *with their shape*, `sources.capabilities_json`/`tos_audited_at`, an indexed `blocking_key`, and a single Alembic head at `0001` exercised in the Dockerfile build.
- **PII has nowhere to land.** Every table discovered from `sqlite_master` is scanned for email/phone-shaped column names, and the set of JSON columns is asserted *exactly* against a documented per-table allow-list — the realistic vector for smuggling a recruiter identifier into a later migration fails loudly.
- **The FTS5 index cannot silently diverge.** The virtual table's DDL is asserted to be external-content (`USING fts5`, `content='listings'`, `content_rowid='id'`, `porter unicode61`), all three triggers are asserted present, and an ORM insert/update/delete round-trips through `MATCH` — the new term becomes findable while the old term stops matching, and a deleted row leaves no stale entry.

## Task Commits

Each task was committed atomically:

1. **Task 1: The 9-item migration acceptance checklist as assertions** - `51fa8f6` (test)
2. **Task 2: PII-cannot-be-stored and FTS5-is-maintained tests** - `738d633` (test)

**Plan metadata:** `docs(01-02): complete migration-contract plan` (SUMMARY + STATE + ROADMAP + REQUIREMENTS)

## Files Created/Modified

- `tests/db/test_migration_contract.py` - the nine checklist assertions plus the strengthened must-haves coverage (fixed-width `content_hash`, no insert path may omit the timestamps/hash, `cv_artifact_id` verified as a FK)
- `tests/db/test_no_pii_columns.py` - `test_no_email_or_phone_columns`, `test_json_columns_are_allow_listed`
- `tests/db/test_fts_triggers.py` - `test_listing_fts_is_external_content`, `test_all_three_triggers_exist`, `test_orm_insert_is_searchable`, `test_update_and_delete_keep_index_in_sync`

## Decisions Made

- **Introspect the migrated database, never the models.** Reading `Base.metadata` would let a migration that forgot an object pass because the *model* declares it; every assertion therefore runs against a temp file produced by `alembic upgrade head`.
- **Exact equality on the JSON allow-list.** A subset check would silently accept a new blob. Equality forces a deliberate act (and a review) to add one.
- **Assert index *shape*, not presence.** The D-19 pair is only correct if the first index is partial *and* restricted to `source_listing_id IS NOT NULL` and the second is unconditional over `(source, canonical_source_url)`; the test reads the `sqlite_master.sql` WHERE clause and the `PRAGMA index_info` column order.
- **Distinguish a real append-only trigger from an absent one.** `RAISE(ABORT)` surfaces as `sqlite3.IntegrityError` in Python (confirmed empirically), so the test asserts that class *and* the trigger's message.
- **Bound parameters for FTS `MATCH`.** The search term is passed as a bound parameter, establishing the discipline Phase 2's search port must not regress.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Strengthened `test_migration_contract.py` to back three `must_haves` truths the literal nine actions did not assert**
- **Found during:** Task 1 (migration contract)
- **Issue:** The plan's `must_haves.truths` include "no nullable-by-omission window exists", "`applications.cv_artifact_id` … nullable FK", and the `content_hash` contract, but the nine named test actions assert only column *presence*, nullability and value admission. As written, a migration that dropped the `cv_artifacts` FK, widened `content_hash` to free-form `TEXT`, or made the timestamps nullable-by-default would not all have been caught.
- **Fix:** Added, inside the existing nine tests: an `INSERT` into `listings` that omits `first_seen_at`/`last_seen_at`/`content_hash` must raise `IntegrityError`; `content_hash`'s declared type must be `VARCHAR(64)`; and `PRAGMA foreign_key_list(applications)` must map `cv_artifact_id` → `cv_artifacts`. No new test function was added, so the nine-name contract is unchanged.
- **Files modified:** `tests/db/test_migration_contract.py`
- **Verification:** `python -m pytest -q tests/db/test_migration_contract.py -x` → 9 passed; the file still collects exactly the nine named tests.
- **Committed in:** `51fa8f6` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical coverage)
**Impact on plan:** No scope creep — no new file, no new test name, no production change. The addition only makes the stated truths falsifiable.

## Issues Encountered

- **`pytest --collect-only -q` output format (pytest 9.1.1).** The plan's acceptance criterion says the quiet collect run should list the nine test names; in pytest 9.1.1 `-q --collect-only` prints `tests/db/test_migration_contract.py: 9` (count only). Verified the criterion's intent with the non-quiet collect output, which lists all nine `<Function test_…>` names. No code change needed.
- **`RAISE(ABORT)` exception class.** Confirmed empirically that it surfaces as `sqlite3.IntegrityError` (not `OperationalError`) before relying on it in the test.

## User Setup Required

None — no external service configuration required. This plan adds no dependency, no install step and no runtime surface; it consumes the plan 01-01 lock only.

## Next Phase Readiness

- **Ready for plan 01-03** (LinkedIn ingest slice): the schema contract, the PII-negative control and the FTS5 maintenance proof all hold, and `tests/conftest.py` still supplies `migrated_db` / `db_engine` / `session_factory` / `db_session` / `client`.
- **Two truths are explicitly delegated to plan 01-03 and must not be lost:**
  1. *Deterministic queue ordering when two listings share `first_seen_at`* (id descending tie-break) — the plan frontmatter names plan 01-03's queue read as the assertion site.
  2. *`content_hash` stability/difference* over `title`, `company_name`, `location_raw`, `description` — belongs to `app/domain/listing.py`, a plan 01-03 deliverable. This plan asserts only the schema half (NOT NULL, `VARCHAR(64)`, non-omittable). Both are recorded in the SUMMARY `coverage` block as `human_judgment: true` so `verify-work` routes them to a human rather than auto-passing.
- **Blockers:** none. The migration-0001 acceptance gate is green, `alembic heads` reports `0001` only, and the full suite is 34 passed.
- **`SRC-10` is not marked complete** — plan 01-05 also declares it and has no SUMMARY yet; `requirements.ready-ids` gates it. It is re-evaluated when 01-05 finishes.

---

*Phase: 01-walking-skeleton-foundations*
*Completed: 2026-09-15*

## Self-Check: PASSED

- All three files in `key-files.created` exist on disk.
- Task commits `51fa8f6` and `738d633` are present in `git log --oneline --all`.
- Plan verification re-run: `python -m pytest -q tests/db/test_migration_contract.py tests/db/test_no_pii_columns.py tests/db/test_fts_triggers.py -x` → **15 passed**; `python -m pytest -q` → **34 passed**; `ruff check .` → **All checks passed**; `alembic heads` → **0001 (head)**.
- `test_migration_contract.py` collects exactly the nine named tests and references `PRAGMA`/`sqlite_master` with zero ORM-metadata references.
- No stubs, no skipped tests, no unrun `<verify>` in this plan — every `<automated>` command in both tasks was executed and passed.
