---
phase: 01-walking-skeleton-foundations
verified: 2026-09-15T21:49:03Z
status: passed
score: 81/83 must-haves verified (2 waived by human decision — see overrides)
covered_files:
  - .env.example
  - .gitignore
  - .planning/REQUIREMENTS.md
  - .planning/ROADMAP.md
  - .planning/STATE.md
  - .planning/WINDOWS.md
  - .planning/phases/01-walking-skeleton-foundations/01-01-PLAN.md
  - .planning/phases/01-walking-skeleton-foundations/01-01-SUMMARY.md
  - .planning/phases/01-walking-skeleton-foundations/01-02-PLAN.md
  - .planning/phases/01-walking-skeleton-foundations/01-02-SUMMARY.md
  - .planning/phases/01-walking-skeleton-foundations/01-03-PLAN.md
  - .planning/phases/01-walking-skeleton-foundations/01-03-SUMMARY.md
  - .planning/phases/01-walking-skeleton-foundations/01-04-PLAN.md
  - .planning/phases/01-walking-skeleton-foundations/01-04-SUMMARY.md
  - .planning/phases/01-walking-skeleton-foundations/01-05-PLAN.md
  - .planning/phases/01-walking-skeleton-foundations/01-05-SUMMARY.md
  - .planning/phases/01-walking-skeleton-foundations/01-06-PLAN.md
  - .planning/phases/01-walking-skeleton-foundations/01-06-SUMMARY.md
  - .planning/phases/01-walking-skeleton-foundations/01-07-PLAN.md
  - .planning/phases/01-walking-skeleton-foundations/01-07-SUMMARY.md
  - .planning/phases/01-walking-skeleton-foundations/01-CONTEXT.md
  - .planning/phases/01-walking-skeleton-foundations/01-REVIEW-FIX.md
  - .planning/phases/01-walking-skeleton-foundations/01-REVIEW.md
  - .planning/phases/01-walking-skeleton-foundations/01-VALIDATION.md
  - .planning/phases/01-walking-skeleton-foundations/COVERAGE.md
  - .planning/phases/01-walking-skeleton-foundations/SKELETON.md
  - Dockerfile
  - alembic.ini
  - alembic/env.py
  - alembic/script.py.mako
  - alembic/versions/0001_initial_schema.py
  - app/__init__.py
  - app/api/__init__.py
  - app/api/deps.py
  - app/api/health.py
  - app/api/runs.py
  - app/config.py
  - app/db/__init__.py
  - app/db/base.py
  - app/db/models.py
  - app/db/repositories/__init__.py
  - app/db/repositories/listing_repo.py
  - app/db/repositories/source_repo.py
  - app/db/session.py
  - app/domain/__init__.py
  - app/domain/listing.py
  - app/domain/models.py
  - app/domain/sanitize.py
  - app/ingest/__init__.py
  - app/ingest/sanitize.py
  - app/llm/__init__.py
  - app/llm/base.py
  - app/llm/opencode_server.py
  - app/main.py
  - app/pipeline/__init__.py
  - app/pipeline/run.py
  - app/pipeline/stages.py
  - app/probe/__init__.py
  - app/probe/probe.py
  - app/probe/survival.py
  - app/sources/__init__.py
  - app/sources/_jobspy_mapping.py
  - app/sources/_jobspy_transport.py
  - app/sources/_ledger.py
  - app/sources/base.py
  - app/sources/indeed.py
  - app/sources/linkedin.py
  - app/sources/registry.py
  - app/web/__init__.py
  - app/web/routes.py
  - app/web/templates/html/_health_strip.html
  - app/web/templates/html/_run_status.html
  - app/web/templates/html/base.html
  - app/web/templates/html/queue.html
  - assets/tailwind/input.css
  - compose.yml
  - docs/probes/2026-09-15-scraper-survival.md
  - docs/probes/README.md
  - docs/runbook-compose-smoke.md
  - entrypoint.sh
  - pyproject.toml
  - requirements.txt
  - scripts/compose-smoke.sh
  - scripts/run-probe.sh
  - static/vendor/alpine.min.js
  - static/vendor/app.css
  - static/vendor/htmx.min.js
  - tests/__init__.py
  - tests/api/__init__.py
  - tests/api/test_health.py
  - tests/api/test_run_backgrounded.py
  - tests/api/test_run_trigger.py
  - tests/conftest.py
  - tests/db/__init__.py
  - tests/db/test_fts_triggers.py
  - tests/db/test_migration_contract.py
  - tests/db/test_no_pii_columns.py
  - tests/db/test_persistence.py
  - tests/db/test_pragmas.py
  - tests/db/test_skeleton_boot.py
  - tests/db/test_source_seeding.py
  - tests/db/test_two_key_upsert.py
  - tests/domain/__init__.py
  - tests/domain/test_normalize.py
  - tests/domain/test_sanitize.py
  - tests/domain/test_sanitize_edge.py
  - tests/domain/test_sanitize_pii.py
  - tests/fixtures/listings/indeed_missing_id.json
  - tests/fixtures/listings/indeed_page1.json
  - tests/fixtures/listings/linkedin_empty_description.json
  - tests/fixtures/listings/linkedin_missing_id.json
  - tests/fixtures/listings/linkedin_page1.json
  - tests/fixtures/opencode_providers.json
  - tests/live/__init__.py
  - tests/live/test_probe_live.py
  - tests/llm/__init__.py
  - tests/llm/test_discovery_redaction.py
  - tests/pipeline/__init__.py
  - tests/pipeline/test_ingest_e2e.py
  - tests/pipeline/test_partial_failure.py
  - tests/probe/__init__.py
  - tests/probe/test_probe.py
  - tests/probe/test_thresholds.py
  - tests/sources/__init__.py
  - tests/sources/test_capabilities.py
  - tests/sources/test_dataframe_conversion.py
  - tests/sources/test_indeed.py
  - tests/sources/test_jobspy_contract.py
  - tests/sources/test_linkedin.py
  - tests/sources/test_registry.py
  - tests/test_auth_seam.py
  - tests/test_config.py
  - tests/test_deploy_manifest.py
  - tests/test_import_discipline.py
  - tests/test_no_cdn.py
  - tests/test_no_credentials.py
covered_digest: "v1:sha256:705959b4b84e83bfe8024f92137e8360af00133dbb533da9b8b6c21e3be50970"
behavior_unverified: 0
overrides_applied: 2
overrides:
  - truth: "probe() asserts a known answer (status, minimum body length, structural marker, absence of stop signals) rather than accepting any HTTP 200 (plan 01-06 must-have truth 5)"
    waived_by: human
    decided_at: "2026-09-15"
    window: 3
    reason: "Human decision at phase verification, taken by the operator on the orchestrator's request. Accept the probe's 3-of-4 signal set and waive the missing positive structural marker. Rationale: the deferral was deliberate and reasoned in plan 01-06 — choosing a marker requires a real known-stable page, and a guessed marker would cause FALSE 'degraded' classifications; the probe already asserts HTTP status, minimum body length and stop-signal absence; and the recorded survival verdict does not depend on the marker (it derives from runs + source_request_log). Re-open this by implementing a marker once a real board page has been observed."
  - truth: "A probe classification of degraded fires when the structural marker is absent or a stop signal is present, and unreachable fires on a transport error or non-200 — each at its own boundary (plan 01-06 backstop truth 10)"
    waived_by: human
    decided_at: "2026-09-15"
    window: 3
    reason: "Same root cause and same human decision as the truth above: the 'marker absent ⇒ degraded' branch is unimplemented because no marker is asserted. The other three classification boundaries (short body, stop signal, transport error / non-200) are implemented and tested."
decision_coverage:
  honored: 24
  total: 24
  not_honored: []
gaps:
  - truth: "probe() asserts a known answer (status, minimum body length, structural marker, absence of stop signals) rather than accepting any HTTP 200 (plan 01-06 must-have truth 5)"
    status: failed
    reason: "Pre-recorded open window .planning/WINDOWS.md #3 — NOT a new discovery. Both adapters' probe() assert HTTP 200, a minimum body length and the absence of stop signals (3 of the 4 RESEARCH signals) but assert NO positive structural marker. Choosing a marker needs a real known-stable page, which research never read; guessing one risks false 'degraded' classifications. Deliberately deferred to the operator/human decision at phase verification (human_verify_mode=end-of-phase) and recorded as coverage entry D8 in 01-06-SUMMARY.md."
    artifacts:
      - path: app/sources/linkedin.py
        issue: "probe() (lines 191-209) checks status/min-length/stop-signals only; no positive structural marker"
      - path: app/sources/indeed.py
        issue: "probe() (lines 166-184) checks status/min-length/stop-signals only; no positive structural marker"
    missing:
      - "A positive structural marker assertion in both probe() implementations (or an accepted override / WINDOWS #3 waiver)"
  - truth: "A probe classification of degraded fires when the structural marker is absent or a stop signal is present, and unreachable fires on a transport error or non-200 — each at its own boundary (plan 01-06 backstop truth 10)"
    status: failed
    reason: "Same root cause as WINDOWS #3: the 'structural marker absent ⇒ degraded' branch is unimplemented because no marker is asserted. The other three boundaries (short body, stop signal, transport error / non-200) are implemented and tested."
    artifacts:
      - path: app/sources/linkedin.py
        issue: "no 'marker absent' classification branch"
      - path: app/sources/indeed.py
        issue: "no 'marker absent' classification branch"
    missing:
      - "Implement the marker-absent ⇒ degraded branch once a marker is chosen (or accept the override)"
advisory:
  - finding: "Survival signals S1, S3, S4 and S6 (and S5's classify_block_vs_parse wrapper) have no production caller; only the S2 baseline and the ledger note are produced by run_pipeline(). The dated verdict is therefore derived by hand from runs/source_request_log rather than computed and surfaced at runtime."
    category: architectural
    reason: "Recorded as Info finding IN-05 in 01-REVIEW.md and accepted by that review as a Phase-8 item. Concrete and reproducible (no caller in app/ or scripts/), but it has no failing test and predates this verification, so it is advisory, not a blocker. Resolve by wiring the signals into the probe/verdict path or a Phase-8 health surface."
    evidence_status: "no failing test; grep-verified: only record_baseline/compute_fill_rates are called from app/pipeline/run.py, none of the S1/S3/S4/S5/S6 functions has a production caller"
human_verification:
  - test: "On a Docker host, run `bash scripts/compose-smoke.sh` from a cold DB (delete data/jobsearch.db*, `docker compose down`, `docker compose up -d --wait`)."
    expected: "/health returns 200 with db=ok; POST /runs runs to a terminal state; the queue renders non-empty listings; `docker compose restart` then renders the same listings. Also confirm the stack comes up with opencode stopped."
    why_human: "Docker is absent from the verification sandbox; this is the phase's designated operator checkpoint (WINDOWS #1, plan 01-07 D8). Operator evidence is recorded as PASS (101 identical listing-title values before/after restart) but is not independently reproducible here."
  - test: "Keep running `bash scripts/run-probe.sh` once per day on ≥3 distinct days and refresh docs/probes/2026-09-15-scraper-survival.md."
    expected: "≥3 distinct recorded days in data/probe.db; the document flips PROVISIONAL→FINAL; every figure traceable to runs/source_request_log; the Adzuna P-1..P-5 decision then re-evaluated at Phase 8."
    why_human: "Survival is a time-windowed measurement (1 run on 1 day today). PROVISIONAL is the honest state and must not be read as a verdict; the window cannot be compressed in the sandbox and needs live board egress."
  - test: "Dependency-legitimacy check (WINDOWS #2 / plan 01-01 human-check): confirm the resolved version set equals the RESEARCH Standard Stack table exactly (no floating ranges); `pip install --dry-run --report -r requirements.txt` resolves and the JobSpy entry resolves to the full SHA fda080a373e8226f3fd60635323f5da9af9892b1; `pip show aiosqlite`/`structlog` home pages point at github.com/omnilib/aiosqlite and github.com/hynek/structlog."
    expected: "All three confirmed; otherwise stop and re-resolve before building the image."
    why_human: "Package-legitimacy judgement against a research audit; collected at phase verification per workflow.human_verify_mode=end-of-phase."
  - test: "Decide WINDOWS #3: accept the probe's 3-of-4 signal set (waive the window / add an override) or require a positive structural marker chosen against a real LinkedIn/Indeed page."
    expected: "A recorded human decision. If accepted, add an `overrides:` entry for the two failed truths and re-verify; if required, open a scoped fix (not a full gap-closure plan)."
    why_human: "The deviation is a deliberate design deferral; choosing a marker needs a real stable page and a human risk call on false 'degraded' classifications."
  - test: "Decide WINDOWS #4: is probe()'s fixed URL/classification wrong, was the board serving a transient challenge to the probe client while serving JobSpy normally, or should the probe be re-pointed at (or corroborated by) the ingest path?"
    expected: "A recorded decision; until then treat /health's per-source probe badge as advisory and the ledger as authoritative, and treat promotion condition P-4 as unusable."
    why_human: "Observed empirically in the same container session (probe reported indeed=unreachable / linkedin=degraded at 21:02:36 while runs.id=1 had fetched 50 usable listings from each board at 21:02:01). Requires a human call on probe instrumentation."
---

# Phase 1: Walking Skeleton + Foundations — Verification Report

**Phase Goal:** A listing scraped from LinkedIn and Indeed exists in the DB and is browsable in the running app, on a skeleton whose non-backfillable foundation is already correct.
**Verified:** 2026-09-15T21:49:03Z (HEAD `6338c10`)
**Status:** passed (2 must-have truths waived by human decision — WINDOWS #3; 5 human-verification items recorded)
**Re-verification:** No — initial verification
**Mode:** mvp · `workflow.human_verify_mode: end-of-phase` · `workflow.windows_enforce: false`

## Verdict up front

**The phase goal is achieved.** 100 real listings (50 LinkedIn + 50 Indeed, 100 distinct content hashes, 0 blank titles) exist in `data/jobsearch.db` and render browsably from the running app in one normalised shape; the non-backfillable migration-0001 foundation passes all 9 ROADMAP checklist items; every one of the 19 declared requirement IDs is accounted for; the offline gate is green (315 passed, 2 deselected; ruff clean).

**The phase is `passed`, with 2 must-have truths waived by human decision.** Two plan-level must-have truths are observably unmet — both facets of the pre-recorded open window `.planning/WINDOWS.md` #3 (the adapter `probe()` asserts 3 of the 4 RESEARCH signals, with no positive structural marker). By the decision tree a FAILED must-have truth would force `gaps_found`; the operator reviewed this report and exercised the documented alternative — **accepting the deviation**, recorded as 2 `overrides:` entries above (WINDOWS #3 now waived). These are **pre-recorded, deliberately-deferred** items, not new discoveries, and no scoped fix was required. Five human-verification items also remain (compose smoke, survival window, dependency legitimacy, and the two open windows) — see Human Verification Required.

## Goal Achievement — Success Criteria

| # | Success Criterion (ROADMAP) | Verdict | Evidence |
|---|------------------------------|---------|----------|
| 1 | One `docker compose up` starts the stack; queue UI browsable; listings persist across a restart | ✓ VERIFIED (operator-executed) | `compose.yml` is app-only (no opencode service, no 4090/4096 port; `extra_hosts: host.docker.internal:host-gateway`); `entrypoint.sh` runs `alembic upgrade head` then `uvicorn --workers 1`; `tests/test_deploy_manifest.py` + `tests/db/test_persistence.py` pass. Operator ran `scripts/compose-smoke.sh` on a cold DB → PASS with 101 identical `<td class="listing-title">` values before/after `docker compose restart`. Not reproducible in this sandbox (no Docker) → human item #1. |
| 2 | Trigger a LinkedIn and an Indeed search; both boards' results in one normalised listing shape | ✓ VERIFIED | Both adapters share `app/sources/_jobspy_mapping.py` → one `RawListing`/`NormalisedListing` shape (`tests/sources/test_indeed.py::test_indeed_maps_into_the_same_normalised_shape_as_linkedin`). I re-rendered `GET /` from a copy of the real DB via TestClient: **200**, 100 `listing-title` cells, 0 blank, 50 linkedin + 50 indeed, company/location/posted cells present, count "100 listings". |
| 3 | Re-running a search never creates a duplicate row for the same listing on the same source | ✓ VERIFIED | Ordered two-key upsert (`app/db/repositories/listing_repo.py::upsert_listing_source`, key A `(source, source_listing_id)` then key B `(source, canonical_source_url)`, SAVEPOINT + IntegrityError re-read); partial unique index `uq_listing_sources_source_sid` + unconditional `uq_listing_sources_source_url` on a freshly migrated DB; `tests/db/test_two_key_upsert.py` (4 tests) + `tests/pipeline/test_ingest_e2e.py::test_reingesting_the_identical_payload_does_not_duplicate` pass. Live DB: 100 `listing_sources` rows, 100 distinct `listing_id`. |
| 4 | Per-source health (last success, listings returned, field fill-rate) + a silent-breakage probe observable, yielding a recorded verdict on LinkedIn/Indeed survival | ⚠️ PARTIAL — 2 must-have truths FAILED; human decision required | *Met:* per-source read model `app/db/repositories/source_repo.py` + health strip `_health_strip.html` render last success / returned / field fill-rate, verified by `tests/api/test_health.py`; verdict document `docs/probes/2026-09-15-scraper-survival.md` exists, is correctly marked **PROVISIONAL** (1 run on 1 day), cites the same `Settings` threshold names the code reads, and every figure is derivable from `runs`/`source_request_log` (2 rows, both `ok`). *Not met:* `probe()` asserts no positive structural marker (WINDOWS #3 → 2 FAILED truths), and `probe()` is empirically not a reliable proxy for `fetch()` (WINDOWS #4). Additionally S1/S3/S4/S6 have no production caller (advisory; REVIEW IN-05). |
| 5 | No credential path anywhere; every API route answers through the `current_user` seam; domain-import-discipline test passes | ✓ VERIFIED | `app/api/deps.py::current_user` + `LOCAL_USER`; all four routes (`/`, `/runs`, `/runs/{run_id}/status`, `/health`) declare `Depends(current_user)` and `tests/test_auth_seam.py` proves the recursion reaches the leaf routes (non-vacuous) and rejects a bare route; `tests/test_no_credentials.py` is a non-vacuous AST guard with can-fail controls; `tests/test_import_discipline.py::test_domain_imports_no_io` passes (domain imports only stdlib). |

## Migration 0001 Acceptance Checklist (ROADMAP — 9 items, non-backfillable)

Verified by migrating a **fresh temp DB** (`alembic upgrade head`, rc 0) and introspecting it with `PRAGMA`/`sqlite_master` — not by reading model definitions.

| # | Checklist item | Verdict | Evidence |
|---|----------------|---------|----------|
| 1 | `listings.first_seen_at`, `last_seen_at`, `content_hash` all NOT NULL | ✓ VERIFIED | `PRAGMA table_info(listings)` → notnull=1 for all three; live DB 0 nulls. |
| 2 | `listing_events` exists and is append-only | ✓ VERIFIED | Both `listing_events_no_update` and `listing_events_no_delete` triggers exist and reject UPDATE/DELETE with `RAISE(ABORT, 'listing_events is append-only')`. |
| 3 | `scores.factor_scores_json` + `weights_json` + `criteria_version` exist (not `total_score` alone) | ✓ VERIFIED | All four columns present. |
| 4 | `cv_artifacts.verification_json` exists; `compile_status` admits `'blocked'` | ✓ VERIFIED | `verification_json` present; `'blocked'` INSERT accepted, `'bogus'` rejected by named CHECK `ck_cv_artifacts_compile_status`. |
| 5 | `applications.cv_artifact_id` exists (nullable FK) | ✓ VERIFIED | Column present, notnull=0, FK to `cv_artifacts.id`. |
| 6 | Partial unique index on `(source, source_listing_id)` AND unconditional `(source, canonical_url)` index | ✓ VERIFIED | `uq_listing_sources_source_sid ... (source, source_listing_id) WHERE source_listing_id IS NOT NULL` and `uq_listing_sources_source_url ... (source, canonical_source_url)` (unconditional). |
| 7 | `sources.capabilities_json` + `sources.tos_audited_at` exist | ✓ VERIFIED | Both columns present. |
| 8 | `listings.blocking_key` exists and is indexed | ✓ VERIFIED | Column present; `ix_listings_blocking_key` exists. |
| 9 | Alembic at revision 0001; `alembic upgrade head` exercised in the container build | ✓ VERIFIED | `alembic_version = 0001` (single head); `Dockerfile:63` runs `DATABASE_URL_SYNC=sqlite:////tmp/migration-smoke.db alembic upgrade head` at image build, and `entrypoint.sh` runs it at boot. |

## Observable Truths (must_haves)

83 must-have truths were enumerated from the 7 PLAN frontmatter `must_haves` blocks (plans 01-01…01-07). All artifact/key-link/stub checks were performed, the offline gate re-run, and the databases independently re-derived.

| Plan | Truths | Result |
|------|--------|--------|
| 01-01 (skeleton + migration + deployment) | 12 | 12 VERIFIED |
| 01-02 (migration checklist + PII-negative + FTS5) | 14 | 14 VERIFIED |
| 01-03 (LinkedIn ingest slice + runs) | 13 | 13 VERIFIED |
| 01-04 (Indeed + registry + capabilities + purity) | 8 | 8 VERIFIED |
| 01-05 (sanitise hardening + guards) | 12 | 12 VERIFIED |
| 01-06 (probe + health + discovery redaction) | 11 | **9 VERIFIED, 2 FAILED** (probe positive structural marker — WINDOWS #3) |
| 01-07 (survival signals + verdict + compose smoke) | 13 | 13 VERIFIED (truth 9 is operator-executed; see human item #1) |
| **Total** | **83** | **81 VERIFIED / 2 FAILED** |

**Score:** 81/83 truths verified (0 present-behavior-unverified; 2 overrides — WINDOWS #3 waived by human decision on 2026-09-15).

Notable verification methods:
- **FRESH migration:** all 9 checklist items re-derived on a temp DB, not trusted from `tests/db/test_migration_contract.py` alone.
- **Live DB re-derived (read-only):** `data/jobsearch.db` → 100 listings / 100 distinct content_hash / 0 blank titles / 50+50 sources / 0 duplicate listing_ids / run 1 `done` fetched 100, per-source created 50 updated 0, `errors_json` empty / 2 ledger rows. `data/probe.db` → 1 run on 1 day, both boards `ok` with 34 rows, 2 ledger rows, baselines recorded.
- **Queue rendered for real:** `GET /` against a copy of the operator DB returned 200 with 100 normalised rows in one shape (50+50).
- **Gates:** `.venv/bin/python -m pytest -q` → **315 passed, 2 deselected**; `.venv/bin/python -m ruff check .` → clean; 87 targeted named tests re-run green.

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `alembic/versions/0001_initial_schema.py` | 17 tables + both dedup indexes + named CHECKs + append-only triggers + FTS5 + 3 triggers | ✓ VERIFIED | 458 lines; applied cleanly; all 9 checklist items hold. |
| `app/db/session.py` | async engine + PRAGMA connect listener | ✓ VERIFIED | WAL / foreign_keys=1 / busy_timeout verified by `tests/db/test_pragmas.py`. |
| `app/db/repositories/listing_repo.py` | two-key Tier-1 upsert | ✓ VERIFIED | Ordered key A→B + SAVEPOINT race handling. |
| `app/db/repositories/source_repo.py` | per-source health read model + probe write path + seeding | ✓ VERIFIED | Used by `/health` and the strip. |
| `app/api/deps.py` | `current_user()` + `LOCAL_USER` seam | ✓ VERIFIED | Returned to all four routes. |
| `app/sources/base.py` | JobSource port, RawListing (no PII field), FetchResult, capabilities compiler | ✓ VERIFIED | 327 lines; `RawListing` has no email/phone. |
| `app/sources/linkedin.py`, `indeed.py` | two adapters, one shape, Ireland guard | ✓ VERIFIED | Shared mapper; `country_indeed=settings.probe_country_indeed` pinned. |
| `app/pipeline/run.py` | `run_pipeline()` one callable, two triggers | ✓ VERIFIED | 362 lines; capability warnings recorded; `done` requires rows + all-ok + zero persist failures. |
| `app/api/runs.py` | `POST /runs` 202 + `GET /runs/{id}/status` 286 | ✓ VERIFIED | Both wired and tested. |
| `app/api/health.py` | boot-tolerant `/health` (db + opencode + per-source probe) | ✓ VERIFIED | Always 200; degrades to data. |
| `app/probe/probe.py` | TTL-cached liveness probe | ✓ VERIFIED | Settings-driven TTL; never raises. |
| `app/probe/survival.py` | signals S1–S6 + P-1..P-5 | ✓ VERIFIED (functions) | 761 lines, pure + tested; production producers partial (advisory). |
| `app/llm/opencode_server.py` | `/global/health` + `/config/providers` with redaction boundary | ✓ VERIFIED | Type-level redaction (`ProviderModel` `extra="forbid"`); sentinel tests. |
| `app/web/templates/html/queue.html`, `_health_strip.html`, `_run_status.html`, `base.html` | queue + health + run fragment | ✓ VERIFIED | Render real DB data; vendored assets only. |
| `compose.yml`, `Dockerfile`, `entrypoint.sh` | app-only deployment + build-time migration | ✓ VERIFIED | Item 9; `python:3.13-slim`; no CDN. |
| `static/vendor/{app.css,htmx.min.js,alpine.min.js}` | committed, non-empty, no CDN | ✓ VERIFIED | 43 KB / 51 KB / 55 KB present. |
| `docs/probes/2026-09-15-scraper-survival.md` | dated verdict, PROVISIONAL permitted | ✓ VERIFIED | PROVISIONAL, honest, traceable. |
| `scripts/compose-smoke.sh`, `scripts/run-probe.sh` | operator gates | ✓ VERIFIED | Smoke refuses success it did not observe; probe refuses out-of-envelope volume. |

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `entrypoint.sh` | `alembic/versions/0001_initial_schema.py` | `alembic upgrade head` before `exec uvicorn` | ✓ WIRED | Verified in file; migration applies. |
| `app/db/session.py` | `app/config.py` | `settings.database_url_async` | ✓ WIRED | Verify. |
| `app/main.py` | `app/web/routes.py` | `app.include_router` | ✓ WIRED | All 3 routers included. |
| `app/sources/linkedin.py` / `indeed.py` | `app/sources/_jobspy_transport.py` | `transport.run_scrape(...)` | ✓ WIRED | `jobspy` imported by exactly one module (grep). |
| `app/pipeline/run.py` | `app/ingest/sanitize.py` → `app/domain/sanitize.py` | stage call before normalise | ✓ WIRED | R2/PII tests. |
| `app/pipeline/run.py` | `app/db/repositories/listing_repo.py` | `upsert_listing_source` | ✓ WIRED | Dedup tests. |
| `app/api/runs.py` | `app/pipeline/run.py` | `asyncio.create_task(run_pipeline(...))` after commit | ✓ WIRED | 202-before-completion test. |
| `app/api/health.py` | `app/probe/probe.py` | cached per-source probe | ✓ WIRED | TTL test. |
| `app/api/health.py` | `app/llm/opencode_server.py` | reachability call that never raises | ✓ WIRED | Stub-driven test. |
| `app/sources/_jobspy_transport.py` | `source_request_log` | one row per outbound request | ✓ WIRED | 2 live rows; pipeline writes via `_ledger`. |
| `docs/probes/2026-09-15-scraper-survival.md` | `runs` + `source_request_log` | every figure derivable | ✓ WIRED | Re-derived and matched. |
| `tests/test_auth_seam.py` | `app/api/deps.py` | walks leaf routes, asserts `current_user` | ✓ WIRED | Non-vacuous. |

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `queue.html` | `listings` | `SELECT Listing JOIN ListingSource ORDER BY first_seen_at DESC, id DESC` | Yes — 100 rows from the real DB (50+50) | ✓ FLOWING |
| `_health_strip.html` | `source_health` | `source_repo.get_source_health()` over `sources` + `runs` + `listing_sources` | Yes — last success/returned/fill-rate from persisted rows | ✓ FLOWING |
| `_run_status.html` | `run`/`sources` | `runs` row + `source_counts_json` | Yes — run 1 counts | ✓ FLOWING |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Offline gate | `.venv/bin/python -m pytest -q` | 315 passed, 2 deselected | ✓ PASS |
| Lint | `.venv/bin/python -m ruff check .` | clean | ✓ PASS |
| Fresh migration + introspection | `alembic upgrade head` on temp DB | all 9 checklist items hold | ✓ PASS |
| Targeted named tests (12 files) | `pytest -q tests/db/test_migration_contract.py … tests/api/test_health.py` | 87 passed | ✓ PASS |
| Live DB re-derivation (read-only) | sqlite3 SELECTs over `data/jobsearch.db`, `data/probe.db` | matches recorded evidence exactly | ✓ PASS |
| Queue render from real DB | TestClient `GET /` against a copy | 200; 100 titles; 0 blank; 50+50 sources | ✓ PASS |
| Live board egress | (none) | sandbox has no board network egress | ? SKIP → human item #2 |

## Probe Execution

| Probe | Command | Result | Status |
|-------|---------|--------|--------|
| `scripts/run-probe.sh --dry-run` | not executed (needs live egress / `.venv` lane) | not run in sandbox | ? SKIP |
| `scripts/compose-smoke.sh` | not executed (no Docker) | operator PASS recorded | ? SKIP (human #1) |

No PLAN/SUMMARY-declared `probe-*.sh` under `scripts/`; the phase's probes are the two operator scripts above.

## Requirements Coverage

All 19 requirement IDs declared in PLAN frontmatter (SRC-01…SRC-10, QUEUE-01/02/05, RUN-01/02, PLAT-01/03/04, UI-07) are accounted for. Each is marked "Complete" in `.planning/REQUIREMENTS.md` and is covered by ≥1 SUMMARY `requirements-completed` entry.

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| SRC-01 | 01-03 | LinkedIn search → normalised listings | ✓ SATISFIED | adapter + `test_ingest_e2e` |
| SRC-02 | 01-04 | Indeed search → normalised listings | ✓ SATISFIED | IndeedAdapter + `test_indeed.py` |
| SRC-03 | 01-03/04 | one normalised shape | ✓ SATISFIED | shared mapper test |
| SRC-04 | 01-04 | add a source via one adapter + register | ✓ SATISFIED | `test_registry.py` (third adapter, no core edit) |
| SRC-05 | 01-03 | failing source degrades, doesn't abort | ✓ SATISFIED | `test_partial_failure.py` |
| SRC-06 | 01-05 | no credential path | ✓ SATISFIED | `test_no_credentials.py` |
| SRC-07 | 01-06/07 | per-source health + silent-breakage probe | ⚠️ PARTIAL | health/verdict verified; probe marker gap (gaps #1/#2) + WINDOWS #4 |
| SRC-08 | 01-03/05 | sanitise untrusted text at ingest | ✓ SATISFIED | `test_sanitize*.py` |
| SRC-09 | 01-04 | declared capabilities; unsupported filter reported | ✓ SATISFIED | `test_capabilities.py` + pipeline warning test |
| SRC-10 | 01-02/05 | strip third-party PII at the adapter boundary | ✓ SATISFIED | `test_no_pii_columns.py` + `test_sanitize_pii.py` |
| QUEUE-01 | 01-01 | persisted queue survives restarts | ✓ SATISFIED | `test_persistence.py` + operator restart smoke |
| QUEUE-02 | 01-01/03 | re-run never duplicates | ✓ SATISFIED | `test_two_key_upsert.py` + `test_ingest_e2e` |
| QUEUE-05 | 01-01/02 | first/last seen + content hash | ✓ SATISFIED | PRAGMA + `test_two_key_upsert.py` |
| RUN-01 | 01-03 | manual trigger from UI | ✓ SATISFIED | `test_run_trigger.py` |
| RUN-02 | 01-03 | background, UI not frozen | ✓ SATISFIED | `test_run_backgrounded.py` |
| PLAT-01 | 01-01/07 | runs locally via Docker Compose | ✓ SATISFIED | manifest tests + operator smoke (human #1) |
| PLAT-03 | 01-01/03/05 | auth seam on every route | ✓ SATISFIED | `test_auth_seam.py` |
| PLAT-04 | 01-01/05/06/07 | limits/thresholds/engine are config | ✓ SATISFIED | `test_config.py` |
| UI-07 | 01-01/05 | vendored UI assets, no CDN | ✓ SATISFIED | `test_no_cdn.py` |

No ORPHANED requirement IDs. No ID declared without evidence.

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No `TBD`/`FIXME`/`XXX` markers in any phase-modified file | ℹ️ Info | Debt-marker gate clean |
| `app/probe/survival.py` | S1/S3/S4/S6, `classify_block_vs_parse` | no production caller | ⚠️ Advisory | See `advisory:` — verdict is hand-derived; REVIEW IN-05 |
| `app/sources/linkedin.py` / `indeed.py` | `probe()` | positive structural marker absent | 🛑 Blocker | WINDOWS #3 → gaps #1/#2 |

## Test Quality Audit

| Check | Result |
|-------|--------|
| Disabled tests linked to requirements | 0 (the 2 `live`-marked tests are deliberately excluded from the default lane by `addopts = -m 'not live'`; they are the operator probe lane, not disabled requirement proof) |
| Circular tests | 0 |
| Non-vacuous guards | Every static guard (`test_no_credentials`, `test_no_cdn`, `test_auth_seam`, `test_import_discipline`, `test_config`) ships a can-fail positive control, verified by mutation during execution (`01-REVIEW-FIX.md`) |
| Assertion strength | Behavioral/integration for the core truths (ingest e2e, dedup, partial failure, backgrounding, verdict derivation); value-level for thresholds (each WARN/FAIL boundary asserted exactly at its configured value and one step below) |

**Blockers from test quality:** 0.

## Decision Coverage

All 24 trackable `01-CONTEXT.md` decisions are honored by shipped artifacts (`check.decision-coverage-verify` → `{honored: 24, total: 24, not_honored: []}`). Non-blocking; no status impact.

## Human Verification Required

1. **Compose smoke + restart persistence** — run `bash scripts/compose-smoke.sh` on a cold Docker DB; expect 200/db ok, a terminal run, non-empty queue, and identical listings after restart (also with opencode stopped). *(human item #1)*
2. **Scraper-survival window** — keep running `scripts/run-probe.sh` daily until ≥3 distinct days; refresh the verdict to FINAL. PROVISIONAL is the honest current state, not a failure. *(human item #2)*
3. **Dependency legitimacy** — confirm the resolved version set vs the RESEARCH audit, aiosqlite/structlog home pages, and the JobSpy full SHA. *(human item #3)*
4. **WINDOWS #3 decision** — accept the probe's 3-of-4 signal set (override/waive) or require a positive structural marker chosen against a real page. *(human item #4)*
5. **WINDOWS #4 decision** — resolve the probe() vs fetch() discrepancy and the usability of promotion condition P-4. *(human item #5)*

## Gaps Summary

Two must-have truths (both the positive-structural-marker facet, `WINDOWS.md` #3) are observably unmet and force `gaps_found`. They are **pre-recorded and deliberately deferred**, not regressions:

1. `probe()` asserts status / minimum body length / stop-signal absence but **no positive structural marker** — 3 of the 4 RESEARCH signals.
2. Consequently, the "structural marker absent ⇒ degraded" classification branch does not exist.

The phase goal itself is achieved; the recorded survival verdict is honest (PROVISIONAL, 1 run on 1 day, no overstatement); the health strip and recorded verdict are verified; the silent-breakage signal *functions* are implemented and boundary-tested (the advisory notes they are not yet wired to a runtime producer). The appropriate next action is a **human decision** rather than a full gap-closure plan: if the deviation is accepted, add an `overrides:` entry for the two truths above and re-verify; the outstanding human items (compose smoke, survival window, dependency legitimacy, WINDOWS #4) must be recorded/waived in the same pass.

---

_Verified: 2026-09-15T21:49:03Z_
_Verifier: the agent (gsd-verifier)_
