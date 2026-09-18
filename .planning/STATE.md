---
gsd_state_version: "1.0"
current_phase: 03
current_phase_name: LLM Port + Structured Output
status: executing
stopped_at: Completed 03-09-PLAN.md
last_updated: "2026-09-18T10:42:07.666Z"
last_activity: 2026-09-18
last_activity_desc: Phase 03 execution started
state_head: b219fd1331de0bc468d6d2347e0f93cf7e804d73
progress:
  total_phases: 8
  completed_phases: 0
  total_plans: 27
  completed_plans: 27
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-15)

**Core value:** Every morning there is one ranked, explained, apply-ready queue of jobs worth considering — so the search→judge→tailor loop costs minutes instead of hours.
**Current focus:** Phase 03 — LLM Port + Structured Output

## Current Position

Phase: 03 (LLM Port + Structured Output) — EXECUTING
Plan: 9 of 9
Status: Ready for verification
Last activity: 2026-09-18 — Completed 03-09-PLAN.md (all 9 plans summarised)

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**

- Total plans completed: 18
- Average duration: — min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 7 | - | - |
| 02 | 11 | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P01 | 23 min | 3 tasks | 40 files |
| Phase 01 P02 | 5 min | 2 tasks | 3 files |
| Phase 01 P03 | 15 min | 3 tasks | 34 files |
| Phase 01 P04 | 8min | 2 tasks | 12 files |
| Phase 01 P05 | 22 min | 2 tasks | 11 files |
| Phase 01 P06 | 22 min | 3 tasks | 20 files |
| Phase 01 P07 | 22 min | 3 tasks | 35 files |
| Phase 02 P01 | 8 min | 3 tasks | 8 files |
| Phase 02 P02 | 4 min | 2 tasks | 3 files |
| Phase 02 P03 | 15 min | 3 tasks | 6 files |
| Phase 02 P04 | 15 min | 2 tasks | 7 files |
| Phase 02 P05 | 22 min | 3 tasks | 10 files |
| Phase 02 P06 | 15 min | 2 tasks | 5 files |
| Phase 02 P07 | 22 min | 3 tasks | 13 files |
| Phase 02 P08 | 32 min | 3 tasks | 10 files |
| Phase 02 P09 | 20 min | 2 tasks | 8 files |
| Phase 02 P10 | 17 min | 2 tasks | 7 files |
| Phase 02 P11 | 212 min | 8 tasks | 21 files |
| Phase 03 P01 | 21 min | 3 tasks | 18 files |
| Phase 03 P02 | 8 min | 2 tasks | 4 files |
| Phase 03 P03 | 9 min | 2 tasks | 3 files |
| Phase 03 P04 | 8 min | 3 tasks | 7 files |
| Phase 03 P05 | 5 min | 2 tasks | 3 files |
| Phase 03 P06 | 13 min | 3 tasks | 10 files |
| Phase 03 P07 | 10 min | 3 tasks | 8 files |
| Phase 03 P08 | 5 min | 3 tasks | 5 files |
| Phase 03 P09 | 13 min | 3 tasks | 6 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Ranking (Phase 5) precedes tailoring (Phase 6) — tailoring consumes the requirement gaps ranking produces.
- [Roadmap]: Phase 4 (CV fact store + LaTeX spike) runs **in parallel** with Phases 2–3; it is a shared prerequisite and the largest unquantified cost.
- [Roadmap]: Scheduling is late (Phase 8) on purpose — a cron job over an unstable pipeline hides failures.
- [Phase 01]: Alembic's sync engine now applies the app's PRAGMAs (WAL + synchronous=NORMAL), so the first migration lands in the D-17 configuration; this also cut migration wall-clock from ~16s to ~5s
- [Phase 01]: The PRAGMA autocommit toggle is getattr-guarded: pysqlite needs it for foreign_keys=ON, but SQLAlchemy's aiosqlite adapter exposes no autocommit attribute
- [Phase 01]: conftest uses a session-scoped migrated template DB plus a per-test file copy, so each test gets an empty migrated database without re-running alembic (full suite stays inside the 30s lane)
- [Phase 01]: listing_sources.source keeps its FK to sources.name, so ingestion must register the source row first; foreign_keys=ON is genuinely enforced
- [Phase 01]: Migration-contract tests introspect the migrated temp DB (PRAGMA/sqlite_master) and never the ORM metadata, so model/DDL drift fails the contract
- [Phase 01]: The JSON-column set is asserted by exact equality against a per-table allow-list, so a new free-form blob (the realistic PII vector) fails the PII-negative test until added deliberately
- [Phase 01]: Queue-ordering tie-break and content_hash stability/difference are delegated to plan 01-03 (queue read + app/domain/listing.py); tracked as human_judgment coverage here, schema half asserted
- [Phase 01]: One runs row per trigger: POST /runs commits the row and passes run_id to run_pipeline, which updates it; without this both created a row and the polled run never terminated
- [Phase 01]: The JobSpy transport keeps its top-level import (one-importer grep holds) but is loaded lazily via an injectable factory, because tls_client cannot load libresolv.so.2 in the sandbox; production behaviour is unchanged
- [Phase 01]: Persistence is SAVEPOINT-per-item: listing_sources.source is a live FK, so a failed insert could otherwise commit an orphan listings row
- [Phase 01]: FINDING for plan 01-05: FastAPI 0.141.1 include_router yields _IncludedRouter objects with no .dependant, so a naive app.routes walk finds zero APIRoutes and a test_auth_seam.py written that way passes vacuously; recurse via original_router.routes
- [Phase 01]: The JobSpy row mapper is board-agnostic and lives on its own (app/sources/_jobspy_mapping.py): Indeed importing app.sources.linkedin would have coupled two boards that are meant to be independently upgradable
- [Phase 01]: The Indeed country guard is asserted at the transport boundary — that country_indeed reaches run_scrape — not merely that build_kwargs produces it
- [Phase 01]: registry.get() fails loudly on an unknown source; the single consumer catches UnknownAdapterError so one bad sources row degrades one board only
- [Phase 01]: Exclusive-filter-group resolution is alphabetical and documented rather than board-specific; the CapabilityWarning is the product value, not the drop
- [Phase 01]: compile_query_for_source() + CapabilityWarning ship in Phase 1 and are consumed by the Phase-2 criteria compiler
- [Phase 01]: Truncation is defined over Python characters (code points), not bytes and not grapheme clusters: sanitize_text slices to exactly max_chars and reports truncated=True; the contract is stated in the module and function docstrings and pinned by a multi-byte test (SRC-08)
- [Phase 01]: The sanitise stage emits an aggregate pii_removed count and never the removed value; the PII tests assert against structlog capture_logs (the real event payload), a stdlib-backed caplog bridge and capsys, because structlog has no explicit configuration and its PrintLogger bypasses caplog by default
- [Phase 01]: FastAPI 0.141.1 include_router appends _IncludedRouter wrappers with no .dependant and no .path; tests/test_auth_seam.py recurses through original_router.routes and proves it reached the four leaf routes before asserting Depends(current_user) — confirming the plan-01-04 finding and closing the vacuous-pass hazard
- [Phase 01]: PLAT-04 fix (Rule 2): DEFAULT_QUERY, which hard-coded results_wanted=50 and location='Ireland' in app/pipeline, became default_query() reading settings.probe_results_wanted and the new settings.probe_query_location; no distinctive threshold literal remains in app/pipeline, which the literal-absence scan now enforces
- [Phase 01]: SanitizeResult was renamed to SanitisedText (the plan's contract name) with SanitizeResult kept as an import-compatible alias; the stage keeps the name sanitize_listing rather than gaining a British-spelling duplicate, and a new test asserts no adapter imports the sanitiser so the single named stage cannot silently diverge
- [Phase 01]: No credential path exists under app/: the only AsyncClient call sites pass headers only, and app/config.py's opencode_server_password is the LLM-backend secret rather than a portal credential — so the raw-token scan stays narrow (LINKEDIN_PASSWORD, INDEED_EMAIL, cookies=, CookieJar, ...) instead of flagging bare PASSWORD
- [Phase 01]: probe_all() resolves sources in three documented steps — an explicit names list, else the enabled sources rows when a session_factory is given (the /health path), else every registered adapter — and skips an enabled row with no adapter rather than reporting it; only a freshly probed source is written back, so last_probe_at keeps meaning 'when the probe ran' and a cache hit costs no write
- [Phase 01]: The /health body renames 01-03's 'database' key to 'db' (the plan's shape) and keeps the app's own status independent of the LLM backend (D-08: an unreachable opencode is reported inside the opencode object, not as a degraded app); one consumer assertion in tests/api/test_run_backgrounded.py was updated
- [Phase 01]: Discovery redaction is a type-level property: ProviderModel has exactly provider_id and model_id with extra='forbid' (so feeding it a raw provider entry raises rather than dropping the secret), parse_providers() is pure and copies only identifiers, and the sentinel scan covers capture_logs, a caplog bridge, stdout, vars(backend) and every table
- [Phase 01]: 01-05's no-credentials guard was refined: bare 'auth' is scoped out of the keyword-name vocabulary because httpx takes a config-supplied credential as auth= (the allowed local opencode password, D-07), while an auth-named env read, a portal kwarg (username/password/token/cookie/credentials) and a login()/sign_in() call still fail — a new control test pins that the carve-out cannot widen
- [Phase 01]: tests/conftest.py now overrides get_llm_backend() with an offline stub, so no default-lane test opens a socket; the queue route reads persisted health only and never probes a board (the live probe belongs to TTL-cached /health), and get_llm_backend() lives in app/llm/__init__.py as the overridable seam
- [Phase 01]: source_repo computes fill-rate live over the latest run's normalised records (a blank description counts as empty, 1 of 2 not 2 of 2); field_fill_baseline_json and baseline_recorded_at remain plan 01-07's record_baseline() — the key_link in the plan names that column, but the baseline is S2's signal work
- [Phase 01]: RESIDUAL for plan 01-07: the adapter probe() asserts status, minimum body length and the absence of stop signals, but not a POSITIVE structural marker (3 of the 4 RESEARCH signals). Choosing a marker needs a real page to inspect, so it is recorded as an explicit human_judgment coverage entry rather than guessed into app/sources
- [Phase 01]: app/db/repositories/source_repo.py was created in task 1 (the task's own action requires the probe write path through the source repository) and extended in task 3 with SourceHealth + get_source_health(); probe_all persists through a lazy import so the probe module imports with or without the repo
- [Phase 01]: Every S1-S6 and P-1..P-5 boundary is read from Settings via thresholds(), and there is no absolute fill-rate target anywhere: every judgement is a delta against the recorded baseline or a trailing average, because JobSpy's description-salary extraction is USA-only so an Irish search is structurally low
- [Phase 01]: The politeness ledger lives in app/sources/_ledger.py rather than inside _jobspy_transport.py, and classify_response moved to app/sources/base.py, because the transport imports jobspy (whose native TLS library cannot load in the sandbox) — a ledger there would be untestable and the survival signals could not classify a fetch outcome
- [Phase 01]: The scraper-survival verdict is PROVISIONAL at 1 run on 1 distinct day, and its first run is explicitly marked non-representative because it predates the DataFrame-row fix (created 1/updated 33 is the bug signature); a single run is never presented as a measurement and the Adzuna decision stays deferred to Phase 8
- [Phase 01]: probe() is not a reliable proxy for fetch(): in the same container session /health reported indeed unreachable and linkedin degraded at 21:02:36 while runs.id=1 had fetched 50 usable listings from EACH board at 21:02:01. The verdict is unaffected (it derives from runs + source_request_log) but the health badge can mislead and P-4 is unusable until resolved — recorded as WINDOWS #4, same family as #3
- [Phase 01]: frame_rows() + UnsupportedFrameError is now the single explicit DataFrame-to-rows conversion point with no silent-empty fallback, after list(frame) was found to iterate COLUMN LABELS (every field None, one blank listing per board); DESIRED_ORDER was completed to the full jobspy.util.desired_order and pinned by a contract test
- [Phase 01]: The pinned dependency is python-jobspy, not jobspy (the PyPI jobspy is an unrelated 2016 Redis package, and pip had been discarding the real candidate after a swallowed MetadataInconsistent), and the Dockerfile must stay classic-builder safe: no BuildKit heredocs, asserted by tests/test_deploy_manifest.py
- [Phase 01]: ensure_registered_sources() seeds the sources allow-list from the adapter registry on app startup and before a probe run: nothing in production ever inserted a sources row, so enabled_source_names() was empty and a fresh deployment silently ingested nothing
- [Phase 2]: Migration 0002 is additive and pairs with its guard churn: five Phase-1 schema guards (four named plus test_skeleton_boot.py) updated deliberately alongside it, not treated as regressions
- [Phase 2]: dedup_fuzzy_threshold is a Settings value (default 88) with a tuning task, never a frozen constant (D-31); the named ck_runs_reason CHECK survived a batch table recreation that preserved ck_runs_trigger/ck_runs_status
- [Phase 2]: rapidfuzz==3.14.6 is Phase 2 only new runtime dependency: the SUS legitimacy verdict was cleared by a blocking human checkpoint before install, and the exact pin is declared in both pyproject.toml and requirements.txt
- [Phase 2]: rapidfuzz is installed in BOTH .venv-host (the plan must-have) and .venv (the only venv the suite runs in), because .venv-host has a broken pydantic_core compiled dependency
- [Phase 2]: The six filter-rule evaluators and the criteria assemblers are total pure functions: an absent value is never a rejection reason (A2/A3), a malformed rule is skipped with no outcome (never silently applied), and salary_floor consults the best known annualised figure so a straddling range is not rejected
- [Phase 2]: The injection catalogue flags and counts, never redacts: no re.sub is added, so the sanitised description and content_hash stay byte-identical to Phase 1; the Apache-2.0 s4(c) origin and significant-change notice lives in app/domain/sanitize.py and never in a template
- [Phase 2]: Tier-2 dedup merges automatically during the run (D-25) with a component gate primary and the fuzzy score secondary: token_sort_ratio gates, token_set_ratio is diagnostic only because it is subset-forgiving, and a grade conflict refuses before any score is computed
- [Phase 2]: listing_sources rows stay on the absorbed twin (A5, amending ARCHITECTURE 8.3) so a revert stays a flag flip; deduped_count now counts rows absorbed by a merge, and both reverted_pairs and merged_pairs are filtered in both orientations before scoring
- [Phase 2]: 02-05: `all_sources_failed` requires at least one reported source status; an empty status list falls through to `mixed` rather than claiming a failure it cannot evidence (P9).
- [Phase 2]: 02-05: `runs.reason` and `runs.reason_counts_json` are persisted on EVERY run, not only a thin/empty one — it is the run's outcome summary and plan 02-10 renders it unconditionally.
- [Phase 2]: 02-05: the capability-warning sentence in `runs.errors_json` is EXTENDED with '(enforced locally as a hard filter after the fetch)', never replaced, so Phase-1 assertions stay valid while the meaning becomes honest.
- [Phase 2]: 02-05: the stage log and the capability-warning list are bounded by two documented module constants (STAGE_LOG_MAX_ENTRIES=12, STAGE_LOG_MAX_ERRORS=10), deliberately not Settings knobs.
- [Phase 2]: 02-05: `new_since_watermark` reads the queue watermark read-only and a NULL watermark means every survivor counts as new; plan 02-07 owns advancing it.
- [Phase 2]: 02-06: the Merges panel is a Jinja macro inside merges.html rendered for the fragment via Template.make_module — one template file, one definition of the markup — and render_merges_table passes the same merges/rate/note the page body needs (make_module executes the content block).
- [Phase 2]: 02-06: the merge rate counts UN-REVERTED merges only over the latest run (un-reverted/fetched), rendered as a whole-number percentage with both integers beside it and None at a zero/null denominator; the reverted count is shown separately so a revert visibly moves the number.
- [Phase 2]: 02-06: revert_merge is UPDATE-only on listing_dupes, restores snapshot fields through the survivor's ORM row so the listings_au FTS trigger fires, counts a non-column snapshot key in RevertResult.skipped instead of raising, and never touches listing_sources (the A5 divergence).
- [Phase 2]: 02-06: the rate and the reverted count live inside the id=merges-table root so one htmx swap moves both — a revert can never leave a stale rate beside a fresh table.
- [Phase 2]: 02-06: no listing_events row is written on merge or revert (that log records user actions), and UNRENDERED_SNAPSHOT_FIELDS keeps source_extras_json/quality_signals_json off the audit page while revert still restores them.
- [Phase 2]: 02-07: every FTS token is double-quoted with internal quotes doubled (FTS5 parses MATCH as an expression, so quoting is the only correct escape); a blank query returns None so the caller skips the listing_fts join entirely and never issues MATCH ''.
- [Phase 2]: 02-07: every queue order ends in a unique tie-break (score, id DESC for FTS; first_seen_at DESC, id DESC otherwise) because bm25 alone is not deterministic; limit comes from Settings.queue_page_size and never from the request.
- [Phase 2]: 02-07: the queue watermark is a DB row with exactly two writers (opening the queue, after the read; and Mark all as seen) and never moves backwards; GET /queue/list deliberately does not advance it.
- [Phase 2]: 02-07: new and stale are independent flags (a listing can be both); stale is last_seen_at <= now - Settings.stale_after_days OR is_active false.
- [Phase 2]: 02-07: the exclusion predicate is a correlated NOT EXISTS against the LATEST run only, so an older run's exclusion stops applying; chips group the count over the run; and #queue-list swaps use hx-swap=innerHTML because the wrapper lives in queue.html.
- [Phase 2]: A whole-search enable/disable does NOT bump searches.version, but a rule toggle DOES — which rules are enabled is effective criteria; whether a search is scheduled is not. Both asserted in tests/db/test_search_repo_writes.py.
- [Phase 2]: delete_search clears the nullable runs.search_id pointer before deleting, because runs.search_id has no ON DELETE SET NULL and foreign_keys=ON is enforced; the run row and its criteria_snapshot_json survive the delete.
- [Phase 2]: Forms are parsed from the urlencoded request body with urllib.parse.parse_qsl rather than adding python-multipart; htmx posts urlencoded by default, so the dependency stays out.
- [Phase 2]: The pre-run capability report reuses compile_query_for_source (one compiler, two callers) and is wrapped so a registry failure degrades to no warnings, never a 500.
- [Phase 2]: run_pipeline(trigger, search_id, ...) scopes the snapshot, fetch query and filter rules to one search with the same callable, budget and failure path; search_id=None still unions every enabled search.
- [Phase 2]: 02-09: saved/hidden are PROJECTED from listing_events, never stored in a column — the latest of save/unsave and of hide/unhide respectively, ordered by (occurred_at, id) because two clicks in one second share a timestamp; shortlisted survives a save and is cleared by a later unsave; view sets only last_viewed_at.
- [Phase 2]: 02-09: the saved/hidden SQL predicates live in event_repo beside the fold and are built from the SAME SAVE_EVENTS/HIDE_EVENTS grouping — plan 02-07's 'latest event of any type' placeholder was wrong, because a view after a save would have made the Saved filter drop the listing.
- [Phase 2]: 02-09: state_for_listings is ONE query for a whole page (a per-row query is forbidden) and every requested id gets an entry, NO_STATE when it has no events, so 'no events' can never look like 'unreadable'.
- [Phase 2]: 02-09: the events POST validates the vocabulary against EVENT_TYPES (mirroring the CHECK) and the listing's existence BEFORE writing — 422/404 append nothing — and occurred_at is server-side so an event's time cannot be forged.
- [Phase 2]: 02-09: reuses app.api.searches.read_form for urlencoded bodies because request.form() requires python-multipart, which this project deliberately does not depend on.
- [Phase 2]: 02-10: the history page renders only what a run persisted — runs.status verbatim (never re-derived, so Phase 1's done-means-it-ran rule survives), the stored reason value and that run's own counts. The ONLY derived value is the sentence, computed with the pure reason_sentence from reason_counts_json plus runs.fetched_count.
- [Phase 2]: 02-10: duration_seconds is None (an em dash) for an unfinished run, never 0.0; every nullable JSON column on runs defaults to an empty mapping/list so a run that died mid-flight renders; and the stage log is bounded AGAIN on read (STAGE_LOG_RENDER_LIMIT/STAGE_LOG_ERROR_LIMIT) independently of the writer's caps.
- [Phase 2]: 02-10: render_run_fragment is annotated with a structural RunFragmentSource Protocol (id/status/errors_json) and RunSummary mirrors the errors_json column name, so ONE renderer and ONE partial serve the run control and the queue's last-run strip with no shim object or second template (D-43).
- [Phase 2]: 02-10: the pre-rendered strip fragment is wrapped in Markup in Python — Jinja would otherwise escape it into visible text — which keeps every template free of a safe-marking filter without an exception.
- [Phase 2]: 02-10: the strip's reason value, derived sentence and /runs link sit OUTSIDE the fragment root so the strip's own 286 poll can swap the status block without dropping the explanation; the strip is a sibling of #run-control so the polling fragment keeps its #run-status-slot target.
- [Phase 03]: 03-01: pin the opencode structured-output wire vocabulary in one no-I/O module (app/llm/contract.py); the request field is format and the live response field is info.structured, with no adaptive fallback (D-54/D-56).
- [Phase 03]: 03-01: parse_providers accepts the live dict shape AND the legacy list shape; OPENCODE_MODEL resolves through discovery and fails loud on a miss instead of silently omitting model.
- [Phase 03]: 03-01: the selftest is a plain full-page POST that writes exactly one llm_calls row (purpose='probe', run_id NULL) and no runs row; server_version is carried on the returned record but not persisted until migration 0003 (plan 03-04).
- [Phase 03]: 03-02: the /doc contract slice is indexed by MESSAGE_DOC_PATH (the OpenAPI path-template spelling) and never by MESSAGE_PATH; both constants are asserted present and distinct so a rename fails loudly rather than raising a bare KeyError.
- [Phase 03]: 03-02: the live lane diffs 22 named facts set-by-set and asserts the committed _meta.server_version matches GET /global/health, so a version-only upgrade still fails; it performs no model call (D-57) and a request hook asserts no POST occurred.
- [Phase 03]: 03-03: status stays inside the four legal llm_calls.status values; the operator cause lives in error_kind (unreachable/timeout/invalid/http_<code>/parse-exception), and ConnectTimeout is unreachable while ReadTimeout is timeout.
- [Phase 03]: 03-03: the client retry loop is bounded by the caller's retries argument (Settings supplies the default) and never retries a schema failure; attempts is the server's info.error.data.retries when supplied, else the issued-request count.
- [Phase 03]: 03-03: TOLERATED_SCHEMA_ERRORS is an explicit frozenset allow-list and _salvage is wired into complete_structured; the WrapValidator substitutes defaults by removing the offending field, so a default-less field re-raises instead of leaking a PydanticUseDefault marker (P11).
- [Phase 03]: 03-04: Task 1's one-way-door gate resolved to migration-0003 — a dedicated nullable llm_calls.server_version VARCHAR(32) (migration 0003), because backend/provider/error each have distinct meanings another surface relies on and error is NULL on the successful rows where the version matters most.
- [Phase 03]: 03-04: llm_call_repo.latest_probe and llm_totals_for_run are the shared reads (total over half-written rows, never commit); _settings_context reads through latest_probe, so D-52's detail has one read shape and server_version now survives a reload.
- [Phase 03]: 03-04: the migration + ORM mirror land together so test_orm_drift enforces the pair; four revision assertions (three in test_migration_contract, one in test_skeleton_boot) moved deliberately to 0003, and no JSON column was added so test_no_pii_columns is untouched.
- [Phase 03]: 03-05: the three Phase-3 opencode ceilings are asserted by the config guard and proven env-tunable; the completion timeout stays a separate Settings field from opencode_timeout_seconds (P4) and the LIMIT_FIELDS comment records why they must not be merged.
- [Phase 03]: 03-05: compose.yml forwards all four opencode keys with ${VAR:-default} defaults matching app/config.py exactly — the three new ceilings plus the previously unforwarded OPENCODE_TIMEOUT_SECONDS — and .env.example documents each, so a host .env override is no longer silently defeated.
- [Phase 03]: 03-05: probe_cache_ttl_seconds was a ceiling LIMIT_FIELDS covered but REQUIRED_SETTINGS_FIELDS omitted; it is now required, so every LIMIT_FIELDS entry is a required numeric ceiling.
- [Phase 03]: 03-06: tools are denied by default through the session-level permission ruleset (DEFAULT_DENY_RULES), not the deprecated message-level tools map; the message body sends no tools key by default and a wildcard '*' key raises ValueError naming the permission control.
- [Phase 03]: 03-06: the session model shape {id: modelID, providerID} is the deliberate inverse of the message shape {providerID, modelID}; both key order and values are asserted together because a wrong placement is a silent 400.
- [Phase 03]: 03-06: the deny is observed, not asserted — StructuredCallResult.part_types/info_keys carry part TYPE names and info KEY names only (logged and rendered on /settings, transient), and a scoped import guard enforces §6.5 with a proven app/sources exclusion.
- [Phase 03]: 03-07: instruction-like text is recorded as a counts-only finding (instruction_like bool + patterns_matched int) on listings.quality_signals_json; a clean listing passes None so the column stays NULL and a recorded signal is never clobbered, and no redaction step was added.
- [Phase 03]: 03-07: the queue row ships a conditional 'flagged' badge with its own .badge-flagged CSS rule — the plan's condition held (the three queue tests assert badges additively), so the guard was satisfied rather than weakened.
- [Phase 03]: 03-07: _finish gains llm_calls/llm_tokens, assigned only when supplied and never touching ranked_count; Phase 3 wires no caller so D-49 holds and run_pipeline still writes zero llm_calls rows.
- [Phase 03]: 03-08: both the port and the adapter declare `retries: int | None = None`, so the documented `settings.opencode_max_retries` fallback is the live default path (PLAT-04); a test patches the setting to 7 and observes 7 POSTs.
- [Phase 03]: 03-08: the port keeps `tools: Sequence[str] = ()` (03-CONTEXT locked) and the adapter converts a non-empty sequence to the builder's `{name: True}` map; an empty sequence stays None so the fail-closed default emits no message-level tools key.
- [Phase 03]: 03-08: the `except ValueError` parse-failure branch sits AFTER `except ValidationError` because ValidationError subclasses ValueError; a non-JSON info.structured becomes `invalid` with provider/model/agent and part_types/info_keys preserved.
- [Phase 03]: D-55 widened deliberately: the committed /doc slice now also pins the session deny-rule field names and the deny action, because the permission ruleset is the ENFORCED tool control; _meta.note records the widening
- [Phase 03]: The live projection follows the session permission array items.$ref (with a one-level wrapper follow and a PermissionRule-name fallback) so a renamed rule reports drift instead of resolving to an empty schema
- [Phase 03]: The raise branch records the attempt BEFORE replying and returns 500 (the reset route convention for an unexpected internal failure), rather than lying with a 200

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1] Blocking unknown #2 — scrape survival at personal scale is unmeasured; the Phase 1 probe answers it and re-ranks Adzuna from hedge to primary if LinkedIn/Indeed fail.
- [Phase 4] Blocking unknown #1 — the real `.tex` is **not in this repo**; `.tex → cv.yaml` import cost and Tectonic bundle coverage are unmeasured. Spike on one section is a hard gate before Phase 6 is estimated.
- [Phase 3] `format` vs `outputFormat` in the opencode structured-output contract is unresolved; resolve against the running server and pin with a `/doc` contract test.
- [Phase 5] Ranking batching (one call per listing vs per K) and budget-cap semantics are unresolved; decide in the plan.
- [Phase 2] RESOLVED at the end-of-phase UAT (2026-09-17): θ=88 was assessed against the real corpus and retained, and the research 10–15% merge-rate band was judged non-transferable to this market — the blocking key plus the grade guard do the discriminating, which the cross-source-only merge rule then hardened. No longer a blocker for planning.

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-09-18T10:42:07.585Z
Stopped at: Completed 03-09-PLAN.md
Resume file: None
