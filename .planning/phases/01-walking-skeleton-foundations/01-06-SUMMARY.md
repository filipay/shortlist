---
phase: 01-walking-skeleton-foundations
plan: 06
subsystem: infra
tags: [health, probe, ttl-cache, opencode, httpx, redaction, pydantic, jinja2, htmx, fastapi]

# Dependency graph
requires:
  - phase: 01-walking-skeleton-foundations
    provides: the adapter registry + JobSource.probe() (01-03/01-04), the boot-tolerant /health and routers (01-03), the sources/runs schema (01-02), the Settings surface (01-05)
provides:
  - a TTL-cached, non-raising liveness probe over the registered adapters
  - a boot-tolerant /health reporting database, opencode and every source
  - the per-source health read model (last success, listings returned, field fill-rate)
  - the SRC-07 visible health strip on the queue page
  - an opencode HTTP client (health + discovery) whose redaction boundary is type-level and sentinel-tested
affects: [phase-3-llm-port, phase-7-survival-verdict, phase-8-scheduled-runs, phase-8-source-health-ui]

# Actuals (#2632) — same estimateTokens scale as the plan's estimate (46000 tokens / 3 tasks)
actuals:
  tokens: 20600
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "TTL cache in front of every outbound liveness check: a page load must never put a request on a board that bans automation"
    - "Redaction as a type property: the model that crosses the boundary has exactly the fields it may carry, plus extra='forbid'"
    - "Sentinel test for a secret boundary: assert the fake credential is absent from the real logger payload, a caplog bridge, stdout, the object graph AND every database table"
    - "Injectable backend seam (get_llm_backend) so the default test lane is offline by construction"

key-files:
  created:
    - app/probe/__init__.py
    - app/probe/probe.py
    - app/llm/__init__.py
    - app/llm/base.py
    - app/llm/opencode_server.py
    - app/db/repositories/source_repo.py
    - app/web/templates/html/_health_strip.html
    - tests/probe/__init__.py
    - tests/probe/test_probe.py
    - tests/llm/__init__.py
    - tests/llm/test_discovery_redaction.py
    - tests/fixtures/opencode_providers.json
    - tests/api/test_health.py
  modified:
    - app/api/health.py
    - app/web/routes.py
    - app/web/templates/html/queue.html
    - app/config.py
    - tests/conftest.py
    - tests/test_no_credentials.py
    - tests/api/test_run_backgrounded.py

key-decisions:
  - "probe_all() resolves sources in three documented steps (explicit names → enabled sources rows when a session_factory is given → every registered adapter) and writes back only a FRESH result, so last_probe_at keeps meaning 'when the probe ran'"
  - "The /health body renames 01-03's `database` key to the plan's `db`, and the LLM backend being down is reported inside the opencode object rather than degrading the app's own status (D-08)"
  - "Discovery redaction is type-level: ProviderModel carries only provider_id/model_id with extra='forbid', so feeding it a raw provider entry raises instead of silently dropping the api_key"
  - "01-05's no-credentials guard scopes bare `auth` out of the keyword-name vocabulary — httpx takes a config-supplied credential as auth= (the allowed local opencode credential, D-07) — while env names, literal args, portal kwargs and login() calls still fail"
  - "tests/conftest.py overrides get_llm_backend() with an offline stub; the queue route reads persisted health only and never probes a board (the live probe belongs to TTL-cached /health)"
  - "source_repo computes fill-rate live over the latest run's normalised records (a blank description counts as empty); field_fill_baseline_json/baseline_recorded_at stay plan 01-07's record_baseline()"

patterns-established:
  - "A cached outbound check is asserted with an invocation counter at both layers: the orchestrator unit test and an end-to-end triple /health call"
  - "Cross-plan guard refinement is paired with a control test that pins the carve-out cannot widen"

requirements-completed: [SRC-07, PLAT-04]

coverage:
  - id: D1
    description: "/health returns HTTP 200 with an unreachable opencode server, reporting reachable=false and the failure reason"
    requirement: "SRC-07"
    verification:
      - kind: unit
        ref: "tests/api/test_health.py#test_health_returns_200_and_reports_opencode_unreachable"
        status: pass
      - kind: unit
        ref: "tests/api/test_health.py#test_health_reports_the_opencode_version_when_reachable"
        status: pass
    human_judgment: false
  - id: D2
    description: "/health is total: a failing probe, an unreadable source map, a dead database or a raising backend each degrade the body instead of the request"
    requirement: "SRC-07"
    verification:
      - kind: unit
        ref: "tests/api/test_health.py#test_health_reports_database_reachability"
        status: pass
      - kind: unit
        ref: "tests/api/test_health.py#test_health_survives_a_probe_that_raises"
        status: pass
      - kind: unit
        ref: "tests/api/test_health.py#test_the_health_body_carries_no_raw_upstream_payload"
        status: pass
    human_judgment: false
  - id: D3
    description: "/health reports the per-source probe status and the persisted source health (last success, returned count, field fill-rate)"
    requirement: "SRC-07"
    verification:
      - kind: unit
        ref: "tests/api/test_health.py#test_health_reports_the_per_source_probe_status"
        status: pass
      - kind: unit
        ref: "tests/api/test_health.py#test_health_reports_persisted_source_health"
        status: pass
    human_judgment: false
  - id: D4
    description: "The queue page renders the per-source health strip: last success, listings returned and field fill-rate, plus a visible LLM-backend indicator"
    requirement: "SRC-07"
    verification:
      - kind: unit
        ref: "tests/api/test_health.py#test_the_strip_renders_last_success_returned_and_fill_rate"
        status: pass
      - kind: unit
        ref: "tests/api/test_health.py#test_the_queue_page_renders_the_strip_and_the_llm_indicator"
        status: pass
      - kind: unit
        ref: "tests/api/test_health.py#test_the_strip_template_declares_the_three_health_columns"
        status: pass
    human_judgment: false
  - id: D5
    description: "probe() results are TTL-cached, so repeated /health loads do not hammer a job board"
    requirement: "SRC-07"
    verification:
      - kind: unit
        ref: "tests/probe/test_probe.py#test_a_second_call_inside_the_ttl_window_does_not_re_probe"
        status: pass
      - kind: unit
        ref: "tests/probe/test_probe.py#test_force_bypasses_the_cache"
        status: pass
      - kind: unit
        ref: "tests/probe/test_probe.py#test_the_ttl_window_is_read_from_settings"
        status: pass
      - kind: integration
        ref: "tests/api/test_health.py#test_repeated_health_loads_probe_each_source_once"
        status: pass
    human_judgment: false
  - id: D6
    description: "A /health request while a pipeline run is in flight still answers promptly — the probe is cached and the run is off the event loop"
    requirement: "SRC-07"
    verification:
      - kind: unit
        ref: "tests/api/test_health.py#test_health_answers_promptly_while_a_run_is_in_flight"
        status: pass
    human_judgment: false
  - id: D7
    description: "A probe classification of degraded fires on a stop signal or a short body; unreachable fires on a transport error, a non-200 or an out-of-contract status"
    requirement: "SRC-07"
    verification:
      - kind: unit
        ref: "tests/sources/test_indeed.py#test_probe_returns_degraded_on_a_block_page"
        status: pass
      - kind: unit
        ref: "tests/sources/test_indeed.py#test_probe_returns_degraded_on_a_short_body"
        status: pass
      - kind: unit
        ref: "tests/sources/test_indeed.py#test_probe_returns_unreachable_on_a_transport_error"
        status: pass
      - kind: unit
        ref: "tests/sources/test_indeed.py#test_probe_returns_unreachable_on_a_non_200"
        status: pass
      - kind: unit
        ref: "tests/probe/test_probe.py#test_an_out_of_contract_status_is_reported_unreachable"
        status: pass
    human_judgment: false
  - id: D8
    description: "probe() additionally asserts a POSITIVE structural marker (the fourth RESEARCH signal), not just status/length/stop-signal absence"
    requirement: "SRC-07"
    verification: []
    human_judgment: true
    rationale: "Not implemented. The shipped adapters (plans 01-03/01-04) assert status, minimum body length and the absence of stop signals — 3 of the 4 signals RESEARCH specifies. Choosing a marker needs a real, known-stable page to inspect, which research never read; guessing one risks false `degraded` classifications in production. Deferred to plan 01-07, which owns the survival measurement and will have real pages to pick against."
  - id: D9
    description: "Discovery calls GET /config/providers only, never the 6 MB /provider catalogue"
    requirement: "PLAT-04"
    verification:
      - kind: unit
        ref: "tests/llm/test_discovery_redaction.py#test_discovery_requests_config_providers_only"
        status: pass
      - kind: unit
        ref: "tests/llm/test_discovery_redaction.py#test_the_module_never_references_the_full_catalogue_endpoint"
        status: pass
    human_judgment: false
  - id: D10
    description: "The raw discovery response — and the plaintext provider credential it carries — is never logged, persisted, cached or returned; only provider/model identifiers cross the boundary"
    requirement: "PLAT-04"
    verification:
      - kind: unit
        ref: "tests/llm/test_discovery_redaction.py#test_the_real_logger_never_carries_the_sentinel"
        status: pass
      - kind: unit
        ref: "tests/llm/test_discovery_redaction.py#test_the_sentinel_does_not_reach_captured_log_output"
        status: pass
      - kind: unit
        ref: "tests/llm/test_discovery_redaction.py#test_the_sentinel_does_not_reach_stdout"
        status: pass
      - kind: unit
        ref: "tests/llm/test_discovery_redaction.py#test_provider_model_cannot_carry_a_raw_provider_entry"
        status: pass
    human_judgment: false
  - id: D11
    description: "Discovery parsing is tolerant of a provider with no models list, a model with no id and a malformed payload, returning a deterministic empty list rather than raising"
    requirement: "PLAT-04"
    verification:
      - kind: unit
        ref: "tests/llm/test_discovery_redaction.py#test_a_provider_without_models_yields_an_empty_list"
        status: pass
      - kind: unit
        ref: "tests/llm/test_discovery_redaction.py#test_a_model_without_an_id_is_skipped"
        status: pass
      - kind: unit
        ref: "tests/llm/test_discovery_redaction.py#test_a_malformed_payload_is_tolerated"
        status: pass
    human_judgment: false
  - id: D12
    description: "A probe result is written back to the source's row (last_probe_at, health), the read model derives fill-rate from normalised records, and enabled rows are resolved from the database"
    requirement: "PLAT-04"
    verification:
      - kind: unit
        ref: "tests/api/test_health.py#test_health_records_the_probe_result_on_the_sources_row"
        status: pass
      - kind: unit
        ref: "tests/probe/test_probe.py#test_a_fresh_probe_writes_the_sources_health_row"
        status: pass
      - kind: unit
        ref: "tests/probe/test_probe.py#test_enabled_rows_are_resolved_from_the_database"
        status: pass
      - kind: unit
        ref: "tests/probe/test_probe.py#test_a_cache_hit_does_not_rewrite_the_row"
        status: pass
    human_judgment: false

duration: 22 min
completed: 2026-09-15
status: complete
---

# Phase 01 Plan 06: Cached Liveness Probe + Boot-Tolerant Health Summary

**A TTL-cached liveness probe per board, a `/health` that answers 200 with a dead opencode server and a dead database, a visible per-source health strip, and an opencode discovery client whose plaintext-credential redaction boundary is proven by a sentinel test.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-09-15T18:34:01Z
- **Completed:** 2026-09-15T18:53:10Z
- **Tasks:** 3
- **Files modified:** 20 (13 created, 7 modified)
- **Commits:** 4 (measured: `git rev-list --count 5ecc5b8..HEAD`)

## Accomplishments

- **Liveness is cached, isolated and total.** `probe_all()` resolves the enabled sources, calls each adapter's `probe()`, caches the status for `settings.probe_cache_ttl_seconds`, isolates a failing board to itself and never raises. Only a *freshly* probed source is written back to its `sources` row, so `last_probe_at` keeps meaning "when the probe ran" and a cache hit costs no write.
- **`/health` is boot-tolerant in the strong sense.** With an unreachable opencode server it returns 200 and reports `reachable: false`; with a dead database it returns 200 and reports `db: "unreachable"`/`status: "degraded"`; a probe that raises or a naive backend holding the raw response changes nothing. The LLM backend being down does not degrade the app's own status (D-08).
- **SRC-07 is visible, not just JSON.** `_health_strip.html` renders one row per source with last success, listings returned and field fill-rate, plus an unmistakable "LLM backend unreachable" indicator. Fill-rate is computed over the run's *normalised* records, so an all-blank description counts as empty (1 of 2, not 2 of 2).
- **The discovery credential boundary is type-level and sentinel-proven.** `ProviderModel` carries only `provider_id`/`model_id` and forbids extras (feeding it a raw provider entry *raises* rather than silently dropping the `api_key`). The fake sentinel in the response is absent from the real structlog payload, a stdlib-backed `caplog` bridge, stdout, `vars(backend)` and every table in the migrated database.
- **The default test lane is offline by construction.** `get_llm_backend()` is an injectable seam that `tests/conftest.py` overrides with a stub that never opens a socket, and the queue route reads persisted health only — the live probe belongs to the TTL-cached `/health`.

## Task Commits

Each task was committed atomically:

1. **Task 1: TTL-cached liveness probe over registered adapters** - `a02e409` (feat)
2. **Task 2: opencode client with the discovery redaction boundary** - `a517f44` (feat)
3. **Task 3: Boot-tolerant `/health` and the per-source health strip** - `5f3b2b9` (feat)
   - follow-up in the same task's scope: `6b10834` (test) — the end-to-end "repeated `/health` loads probe once" assertion backing must-have #4

**Plan metadata:** _(this commit)_ (docs: complete plan)

## Files Created/Modified

- `app/probe/probe.py` — `probe_all()`, `probe_source()`, `clear_cache()`; TTL cache read from `Settings`, per-source isolation, lazy persistence
- `app/probe/__init__.py` — the package surface
- `app/llm/base.py` — `LLMBackend` Protocol, `ProviderModel` (two id fields, `extra="forbid"`), `DiscoveryResult`, `ProbeOutcome`
- `app/llm/opencode_server.py` — `GET /global/health` + `GET /config/providers`, pure `parse_providers()`, bounded timeout, Basic auth only when configured
- `app/llm/__init__.py` — the `get_llm_backend()` dependency seam
- `app/db/repositories/source_repo.py` — `enabled_source_names()`, `record_probe_result()`, `SourceHealth`, `get_source_health()`
- `app/api/health.py` — the rebuilt `/health` (status, db, opencode, sources)
- `app/web/routes.py` — the queue page renders the strip; `_health_strip()` never raises and never probes a board
- `app/web/templates/html/_health_strip.html` — the SRC-07 strip
- `app/web/templates/html/queue.html` — includes the strip
- `app/config.py` — `opencode_timeout_seconds` (bounded health/discovery calls, T-01-32)
- `tests/probe/test_probe.py` — caching, force, clear, isolation, ordering, DB resolution, persistence (15 tests)
- `tests/llm/test_discovery_redaction.py` — identifiers-only, the four-sink sentinel hunt, the endpoint contract, tolerance from §A2 (23 tests)
- `tests/api/test_health.py` — totality, per-source reporting, the strip, promptness, no-raw-payload (15 tests)
- `tests/fixtures/opencode_providers.json` — the documented shape with a fake sentinel credential, a model-less provider and a missing model id
- `tests/conftest.py` — the offline `OfflineLLMBackend` override on the shared client
- `tests/test_no_credentials.py` — the `auth` kwarg carve-out + a control test
- `tests/api/test_run_backgrounded.py` — the renamed `db` key assertion

## Decisions Made

- **`probe_all()` has three documented resolution steps:** an explicit `names` list; else the enabled `sources` rows when a `session_factory` is given (`/health`'s production path); else every registered adapter. An enabled row with no adapter is *skipped*, not reported as unreachable — the pipeline degrades one board the same way.
- **The `/health` body renames 01-03's `database` key to the plan's `db`** and keeps the app's own `status` independent of the LLM backend. This required updating one assertion in `tests/api/test_run_backgrounded.py` (its consumer), which is in scope because the response shape changed here by design.
- **Redaction is enforced by the type, not by discipline.** `extra="forbid"` means a future author who tries to carry the raw entry gets a loud failure instead of a silent secret.
- **01-05's no-credentials guard needed one refinement.** `httpx` takes a config-supplied credential as `auth=`, which is exactly how the allowed local opencode password is passed (D-07), so bare `auth` was scoped out of the *keyword-name* vocabulary only. An `auth`-named environment read, a portal kwarg (`username`/`password`/`token`/`cookie`/`credentials`) and a `login()`/`sign_in()` call all still fail, and a new control test pins that the carve-out cannot widen.
- **`source_repo.py` was created in Task 1 and extended in Task 3.** The plan's task-1 action requires recording `last_probe_at`/`health` "through the source repository", so the write path lands with the probe; the read model lands with the strip. `probe_all` persists through a lazy import, so the probe module imports with or without the repo.
- **The fill-rate baseline stays plan 01-07's.** The plan's key_link names `field_fill_baseline_json`, but that column is S2's baseline and 01-07 owns `record_baseline(...)`; the strip computes its fill-rate live over the latest run's records, as the task action specifies.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] 01-05's no-credentials guard failed on the legitimate `auth=` kwarg**
- **Found during:** Task 2 (the opencode client)
- **Issue:** `tests/test_no_credentials.py` matched the credential pattern `auth` against session-call *keyword names*, so `httpx.AsyncClient(auth=...)` — the documented way to pass the optional, config-supplied local opencode password (D-07, explicitly allowed) — was reported as "a credentialed acquisition path under app/". The guard's own raw-token list had already carved out the LLM credential; its pattern list had not.
- **Fix:** Introduced `CREDENTIAL_KWARG_PATTERNS` (the vocabulary minus `auth`) for keyword names only. Env-var names and string-literal arguments keep `auth`; portal kwargs and `login()`/`sign_in()`/`authenticate()` calls are unchanged.
- **Files modified:** `tests/test_no_credentials.py`
- **Verification:** the guard passes; a new control test asserts `auth=` alone is not flagged while `username`/`password` kwargs and `os.getenv("LINKEDIN_AUTH")` still are.
- **Committed in:** `a517f44` (Task 2 commit)

**2. [Rule 3 - Blocking] The shared `client` fixture would have reached a live server**
- **Found during:** Task 3 (wiring `/health` and the queue strip)
- **Issue:** `/health` and the queue page now consult the LLM backend, so every existing test using the shared `client` fixture would have opened a socket to the configured opencode URL — violating the plan's "no live opencode server in any default-lane test" criterion and depending on a DNS failure being fast.
- **Fix:** added `OfflineLLMBackend` to `tests/conftest.py` and overrode `get_llm_backend` in the shared `client` fixture. Tests that need a specific backend override it again explicitly (`tests/api/test_health.py` does).
- **Files modified:** `tests/conftest.py`
- **Verification:** the full suite runs in ~13-27 s with no network; `/health` still exercises its real code path (empty DB → zero probes).
- **Committed in:** `5f3b2b9` (Task 3 commit)

**3. [Rule 3 - Blocking] `/health`'s `db` key broke a 01-03 assertion**
- **Found during:** Task 3
- **Issue:** `tests/api/test_run_backgrounded.py` asserted `health.json()["database"]`; the plan specifies a `db` key.
- **Fix:** updated that one assertion to `db`. The plan owns this response shape, and the test is its direct consumer.
- **Files modified:** `tests/api/test_run_backgrounded.py`
- **Verification:** `tests/api/test_run_backgrounded.py` passes, including the mid-run `/health` assertions.
- **Committed in:** `5f3b2b9` (Task 3 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 3 — blocking, each directly caused by this plan's changes)
**Impact on plan:** Two are test-harness corrections required by the offline-lane criterion and the response-shape change; one is a narrowing of a prior guard's over-broad pattern. No product behaviour was weakened: portal-credential detection is unchanged and pinned by a control test. No new dependency, no architectural change.

## Issues Encountered

- **The adapter `probe()` does not assert a positive structural marker.** RESEARCH specifies four signals (status, minimum body length, a structural marker, absence of stop signals); the adapters shipped in 01-03/01-04 implement three. Adding a marker means guessing at a board's healthy markup without ever having read a live page, which risks *false* `degraded` classifications — worse than the current state. Recorded as an explicit `human_judgment` coverage entry (D8) and deferred to plan 01-07, which owns the survival measurement and will have real pages to inspect. **This is the only must-have half that is not assertion-backed, and it is recorded rather than claimed.**
- **The plan's `key_links` names `field_fill_baseline_json`, which this plan does not touch.** Verified that `01-07-PLAN.md` owns `record_baseline(...)` / `baseline_recorded_at`; the strip's fill-rate is the live per-run computation the task action specifies.

## User Setup Required

None - no external service configuration required. The opencode server remains user-managed and optional (D-05/D-08); `OPENCODE_SERVER_PASSWORD` is read from an uncommitted `.env` and is only sent when non-empty.

## Known Stubs

None. No stub, placeholder, `TODO`/`FIXME`, empty-value-to-UI or unwired data source was introduced. The two `human_judgment` items are the deferred structural marker (D8) and nothing else.

## Threat Flags

None. This plan adds no new endpoint beyond the `/health` and `/` bodies already in the app, no new auth path, and no schema change. The one new outbound surface (`GET /config/providers`) is explicitly in the plan's threat model and mitigated by test.

## Threat Register Coverage

| Threat ID | Disposition | Covered by |
|-----------|-------------|------------|
| T-01-29 (plaintext provider key reaching a log or the DB) | mitigate | `tests/llm/test_discovery_redaction.py` (capture_logs, caplog bridge, stdout, `vars(backend)`, every table) |
| T-01-30 (`/health` echoing a raw upstream payload) | mitigate | `tests/api/test_health.py#test_the_health_body_carries_no_raw_upstream_payload` (exact body-key set + recursive key scan + sentinel) |
| T-01-31 (`/health` hammering a board) | mitigate | `tests/probe/test_probe.py` cache tests + `tests/api/test_health.py#test_repeated_health_loads_probe_each_source_once` |
| T-01-32 (a hung outbound call pinning the worker) | mitigate | bounded `settings.opencode_timeout_seconds`; `health()`/`discover_models()` return a value on every exception |
| T-01-33 (a block page read as healthy) | mitigate | the adapter probes assert a stop-signal absence and a minimum body; **the structural marker half is deferred (D8)** |
| T-01-34 (a degraded source presented as healthy) | mitigate | `degraded` is a distinct state rendered in the strip; the `ok`-but-nothing-new contradiction is plan 01-07's signal S4 |
| T-01-SC (package installs) | accept | `tech-stack.added: []` — `httpx`, `pydantic`, `structlog` were already pinned |

## Next Phase Readiness

- **Ready for plan 01-07** (survival signals S1–S6, the dated probe verdict, the operator compose smoke). Two hooks are already in place: `app/probe/` is scanned by `tests/test_config.py`, so a hard-coded threshold in `app/probe/survival.py` will fail the config guard; and `source_repo` exposes the per-source history the S2 baseline will extend.
- **`SRC-07` and `PLAT-04` remain open in REQUIREMENTS.md by design** — both are also declared by plan 01-07, so the shared-ID gate blocks them until 01-07 has a SUMMARY. `requirements.ready-ids` returned `{"ready": [], "blocked": ["SRC-07", "PLAT-04"]}`.
- **Phase 3 inherits a ready seam.** `LLMBackend.health()` exposes the server version and `discover_models()` the model ids, so D-12's per-call model+version recording can be added without changing the protocol or any route. The `format` vs `outputFormat` ambiguity remains Phase 3's to resolve against a running server.
- **Phase 8 inherits the strip and the enums.** The health strip is already the surface source health will be reported on; scheduling must keep `--workers 1` so the probe cache and any future scheduler stay per-process.
- **Full suite:** `.venv/bin/python -m pytest -q -x` → **232 passed**; `ruff check .` → clean.

## Self-Check: PASSED

- **Files verified on disk:** all 14 created/modified paths exist (`app/probe/*`, `app/llm/*`, `app/db/repositories/source_repo.py`, `app/api/health.py`, `app/web/routes.py`, `_health_strip.html`, `queue.html`, and the 5 new test/fixture files).
- **Commits verified:** `a02e409`, `a517f44`, `5f3b2b9`, `6b10834` all present in `git log`.
- **Task acceptance criteria:** all three tasks' criteria re-run and passing.
- **Plan `<verification>`:** `python -m pytest -q tests/probe tests/api/test_health.py tests/llm -x` → 53 passed; `python -m pytest -q -x` → 232 passed; no live board contact (the probe is exercised with stub adapters and a recorder, and the shared client's backend is an offline stub).
- **`must_haves` truths:** 7 of 8 are assertion-backed (see `coverage:`); the eighth (truth 5) is assertion-backed for the three shipped signals (D7) with its structural-marker half recorded as an explicit `human_judgment` entry (D8). All three `backstop` statements are covered: promptness (D6), the classification boundaries (D7, minus the marker — recorded in D8), and the parser tolerance (D11).
- **Non-vacuity spot-checks by mutation:** letting a probe exception escape `/health`, counting a blank description as populated, dropping the seam from `/health`, ignoring the probe cache, and flagging `auth=` as a portal kwarg each made exactly the intended assertion fail.
