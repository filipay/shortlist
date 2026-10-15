---
phase: 01-walking-skeleton-foundations
plan: 07
subsystem: infra
tags: [probe, survival-signals, sqlite, docker-compose, jobspy, pandas, ledger, runbook, provisional-verdict]

# Dependency graph
requires:
  - phase: 01-walking-skeleton-foundations
    provides: the migration-0001 schema (01-02), the ingest pipeline + runs/ledger tables (01-03), the adapter registry and both boards (01-04), the guards/config surface (01-05), the cached probe + /health + health strip (01-06)
provides:
  - survival signals S1-S6 and the Adzuna promotion condition, every boundary read from Settings
  - the politeness ledger write path (one source_request_log row per outbound request) and the S2 baseline anchor
  - the operator probe entry point, the probe runbook, and the dated PROVISIONAL verdict document
  - the operator compose-smoke script and runbook (PLAT-01), plus the sources allow-list seeding that makes a fresh deployment work at all
affects: [phase-2-filtering-and-dedup, phase-8-scheduling-and-adzuna-decision, phase-8-source-health-ui, any-phase-touching-probe-or-ingest]

# Actuals (#2632) — same estimateTokens scale as the plan's estimate (44000 tokens / 3 tasks)
actuals:
  tokens: 37269
  tasks: 3
  commits: 12

tech-stack:
  added: []
  patterns:
    - "A boundary is only trusted with a mutation test: every WARN/FAIL edge is asserted exactly at its configured value and one step below"
    - "Thin evidence returns `skip`, never a verdict — which is what makes an honest PROVISIONAL document possible"
    - "Two instruments never conflated: probe() answers liveness, the ledger/runs answer survival; the verdict derives from the ledger"
    - "Operator gates are scripted and the script refuses to leave the documented envelope without an explicit confirmation flag"

key-files:
  created:
    - app/probe/survival.py
    - app/sources/_ledger.py
    - tests/probe/test_thresholds.py
    - tests/live/test_probe_live.py
    - tests/sources/test_dataframe_conversion.py
    - tests/sources/test_jobspy_contract.py
    - tests/db/test_source_seeding.py
    - scripts/run-probe.sh
    - scripts/compose-smoke.sh
    - docs/probes/README.md
    - docs/probes/2026-09-15-scraper-survival.md
    - docs/runbook-compose-smoke.md
  modified:
    - app/config.py
    - app/sources/base.py
    - app/sources/_jobspy_transport.py
    - app/sources/_jobspy_mapping.py
    - app/sources/linkedin.py
    - app/sources/indeed.py
    - app/db/repositories/source_repo.py
    - app/main.py
    - app/pipeline/run.py
    - app/web/templates/html/_run_status.html
    - pyproject.toml
    - requirements.txt
    - Dockerfile
    - tests/pipeline/test_partial_failure.py
    - tests/test_deploy_manifest.py
    - tests/api/test_run_trigger.py
    - tests/fixtures/listings/*.json

key-decisions:
  - "Every S1-S6 threshold and every P-1..P-5 boundary is read from Settings via thresholds(), so the verdict document cites the same names the code reads and Phase 8 can re-evaluate the condition by code"
  - "No absolute fill-rate target exists anywhere: every judgement is a delta against the recorded baseline or a trailing average, because JobSpy's description-salary extraction is USA-only and an Irish search is structurally low"
  - "The ledger lives in app/sources/_ledger.py, not in _jobspy_transport.py, because that module imports jobspy whose native TLS library cannot load in the sandbox — a ledger there would be untestable; the transport re-exports it"
  - "classify_response moved to app/sources/base.py so the survival signals can classify a fetch outcome without importing the scraper toolchain"
  - "The pipeline writes the ledger row and the baseline inside a SAVEPOINT: bookkeeping must never abort a run whose listings already persisted"
  - "The verdict is PROVISIONAL with 1 run on 1 day, and the first run's created/updated split is explicitly marked non-representative because it predates the DataFrame-row fix"
  - "probe() is recorded as an unreliable proxy for fetch() rather than quietly trusted: the verdict derives from runs + source_request_log, and P-4 is flagged unusable until resolved (WINDOWS #4)"

patterns-established:
  - "An operator gate ships as: a script that refuses to exceed the documented envelope, a runbook stating the pass criteria, and a document whose every figure is traceable to a row"
  - "A defect found by an operator gate is fixed with a regression test that would have caught it (DataFrame conversion, zero-source run, sources seeding, Dockerfile instruction set)"

requirements-completed: [SRC-07, PLAT-01, PLAT-04]

coverage:
  - id: D1
    description: "Survival signals S1-S6 and the Adzuna promotion condition P-1..P-5 are implemented, board-agnostic and pure over persisted rows"
    requirement: "SRC-07"
    verification:
      - kind: unit
        ref: "tests/probe/test_thresholds.py#test_s1_counts_each_status_correctly"
        status: pass
      - kind: unit
        ref: "tests/probe/test_thresholds.py#test_every_promotion_result_names_the_board_and_the_window"
        status: pass
      - kind: unit
        ref: "tests/probe/test_thresholds.py#test_the_keep_as_hedge_outcome_holds_when_no_condition_fires"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every WARN/FAIL boundary fires exactly at its configured value and not one step earlier, and is not armed below its arming run count"
    requirement: "SRC-07"
    verification:
      - kind: unit
        ref: "tests/probe/test_thresholds.py#test_s2_warns_exactly_at_the_configured_warn_drop"
        status: pass
      - kind: unit
        ref: "tests/probe/test_thresholds.py#test_s2_fails_exactly_at_the_configured_fail_drop"
        status: pass
      - kind: unit
        ref: "tests/probe/test_thresholds.py#test_s2_is_silent_one_point_below_the_warn_drop"
        status: pass
      - kind: unit
        ref: "tests/probe/test_thresholds.py#test_s3_is_not_armed_below_the_configured_run_count"
        status: pass
      - kind: unit
        ref: "tests/probe/test_thresholds.py#test_s4_does_not_fire_one_run_earlier"
        status: pass
      - kind: unit
        ref: "tests/probe/test_thresholds.py#test_s6_reports_a_missing_expected_column"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every outbound scrape request writes one source_request_log row carrying kind, status_code, ok and a fetch-side/parse-side note"
    requirement: "SRC-07"
    verification:
      - kind: unit
        ref: "tests/probe/test_thresholds.py#test_a_run_writes_one_ledger_row_and_records_the_baseline"
        status: pass
      - kind: unit
        ref: "tests/probe/test_thresholds.py#test_a_blocked_result_is_recorded_as_fetch_side"
        status: pass
      - kind: integration
        ref: "data/probe.db: 2 source_request_log rows, kind=search, ok=True, note='ok: no observable status returned 34 rows' (operator run, 2026-09-15)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The fill-rate baseline is recorded once on the first successful run per source and never overwritten"
    requirement: "SRC-07"
    verification:
      - kind: unit
        ref: "tests/probe/test_thresholds.py#test_record_baseline_writes_once_and_never_overwrites"
        status: pass
      - kind: integration
        ref: "data/probe.db: field_fill_baseline_json present for both indeed and linkedin"
        status: pass
    human_judgment: false
  - id: D5
    description: "Probe volume stays inside the configured envelope, and the transport has no retry or escalation path for a block"
    requirement: "SRC-07"
    verification:
      - kind: unit
        ref: "tests/probe/test_thresholds.py#test_the_envelope_ceilings_are_read_from_settings"
        status: pass
      - kind: unit
        ref: "tests/probe/test_thresholds.py#test_the_transport_has_no_retry_or_escalation_path"
        status: pass
      - kind: automated_ui
        ref: "scripts/run-probe.sh --dry-run: default envelope exits 0; PROBE_MAX_RESULTS=500 exits 3 with the refusal message"
        status: pass
    human_judgment: false
  - id: D6
    description: "The live probe lane exists, is marked `live`, and can never run in the default lane"
    requirement: "SRC-07"
    verification:
      - kind: other
        ref: "pyproject.toml addopts = -m 'not live'; `pytest -q` reports '2 deselected' and `pytest -m live --collect-only` collects the 2 live tests"
        status: pass
    human_judgment: false
  - id: D7
    description: "A dated scraper-survival verdict document exists, is derivable from runs/source_request_log, and carries an explicit PROVISIONAL/FINAL marker"
    requirement: "SRC-07"
    verification: []
    human_judgment: true
    rationale: "The document exists and is PROVISIONAL with 1 run on 1 day, which is the honest state. The plan's human-check requires the operator to have run the probe on >=3 distinct days and every figure to be traceable — that cannot pass yet. The operator will keep running daily; the marker flips to FINAL only when the window is met."
  - id: D8
    description: "The whole stack starts with one docker compose up, /health answers 200, and listings persist across a restart (PLAT-01)"
    requirement: "PLAT-01"
    verification: []
    human_judgment: true
    rationale: "Docker is absent from the agent sandbox, so this is operator-verified by design. The operator ran scripts/compose-smoke.sh on a cold database and it printed PASS: /health 200 with db ok, a triggered run reaching terminal, and 101 identical listing titles before and after docker compose restart. The raw output lives in the phase summary, not in an automated assertion."
  - id: D9
    description: "The seven defects the operator gates exposed are fixed, each with a regression test that would have caught it"
    requirement: "PLAT-01"
    verification:
      - kind: unit
        ref: "tests/sources/test_dataframe_conversion.py#test_distinct_dataframe_rows_do_not_collapse_to_one_content_hash"
        status: pass
      - kind: unit
        ref: "tests/sources/test_dataframe_conversion.py#test_frame_rows_raises_for_anything_that_is_not_a_frame_or_rows"
        status: pass
      - kind: unit
        ref: "tests/sources/test_jobspy_contract.py#test_desired_order_is_the_exact_pinned_jobspy_column_contract"
        status: pass
      - kind: unit
        ref: "tests/pipeline/test_partial_failure.py#test_a_run_that_resolved_no_sources_is_not_a_clean_success"
        status: pass
      - kind: unit
        ref: "tests/db/test_source_seeding.py"
        status: pass
      - kind: unit
        ref: "tests/test_deploy_manifest.py"
        status: pass
    human_judgment: false
  - id: D10
    description: "probe()'s classification is not a reliable proxy for fetch(), recorded as an open limitation with evidence rather than papered over"
    requirement: "SRC-07"
    verification: []
    human_judgment: true
    rationale: "In the same container session /health's probe reported indeed=unreachable and linkedin=degraded at 21:02:36 while runs.id=1 had just fetched 50 usable listings from EACH board at 21:02:01. The survival verdict is unaffected (it derives from the ledger), but /health's liveness badge can mislead and promotion condition P-4 is unusable until a human decides whether the probe URL/classification is wrong or the board challenged that client transiently. Recorded as .planning/WINDOWS.md entry #4 and section 7 of the verdict."

duration: 22 min
completed: 2026-09-15
status: complete
---

# Phase 01 Plan 07: Survival Probe, Verdict Document + Compose Smoke Summary

**Survival signals S1–S6 with every boundary read from Settings, a real politeness ledger written by the pipeline, and both operator gates passed — the dated verdict is honestly PROVISIONAL at 1 run on 1 day, and the gates exposed seven real defects (including a DataFrame-iteration bug that collapsed a full page to one blank listing) which are fixed with regression tests.**

## Performance

- **Duration:** 22 min of executor time — 17 min for the first session (signals, ledger, config, tests) + ~5 min for this close-out.
- **Wall clock:** 2026-09-15T18:55:05Z → 2026-09-15T21:06Z (~2 h 11 m), of which **92 min was the operator-driven defect-fix cycle** between the checkpoint (`74504df`) and the last fix (`f690153`), plus the two operator gate runs. Those are recorded in Deviations, not counted as executor time.
- **Started:** 2026-09-15T18:55:05Z
- **Completed:** 2026-09-15T21:06:00Z
- **Tasks:** 3 (1 automated + 2 operator gates, both now passed)
- **Files modified:** 35
- **Commits:** 12 (measured: `git rev-list --count dc76a97..HEAD`)

## Task Commits

1. **Task 1: Survival signals S1–S6, the config envelope, and the request ledger** — `5e5c242` (feat)
2. **Task 2 (offline half) + Task 3 (offline half): operator-gate scaffolding** — `74504df` (feat) — run-probe.sh, compose-smoke.sh, the runbook, the PROVISIONAL verdict
3. **Task 2: operator probe run + verdict** — **PASSED** (evidence below)
4. **Task 3: operator compose smoke + restart persistence** — **PASSED** (evidence below)

**Defect-fix commits** (all found by the two gates, all part of this plan's realized cost):

| Commit | Subject |
|---|---|
| `aa6bb97` | fix(01-01): name the real distribution (python-jobspy) in the pinned VCS reference |
| `9cbe015` | fix(01-01): keep the JobSpy revision assertion classic-builder safe |
| `025daae` | fix(01-07): fail fast and loudly when the probe interpreter is unusable |
| `2ab01f0` | fix(01-07): seed the sources allow-list from the adapter registry |
| `683976b` | fix(01-07): read the run id from the POST /runs response in the compose smoke |
| `58a2abf` | fix(01-07): stop a zero-source run reporting done |
| `489422d` | fix(01-07): convert a scraped DataFrame to rows, not column labels |
| `0e70991` | fix(01-07): complete DESIRED_ORDER with the naukri tail of jobspy desired_order |
| `f690153` | test(01-07): realign fixtures to the flattened frame and pin the DataFrame contract |
| `9c90888` | chore: ignore editable-install egg-info |

**Plan metadata:** _(this commit)_ (docs: complete plan)

## Operator Gate Evidence (independently verified from the recorded rows)

Both gates were re-derived by this executor directly from the operator's gitignored
databases (opened read-only), rather than taken on trust.

### Gate B — live probe (`data/probe.db`)

- `runs.id = 1`, `trigger=manual`, `status=done`, `started_at=2026-09-15 20:23:40`, `fetched_count=68`
- **1 distinct day** (`2026-09-15`); the script printed `PROVISIONAL: fewer than 3 distinct days recorded`
- per source, both boards identical: `status=ok`, `fetched=34`, `created=1`, `updated=33`, `failed=0`, `requests_used=1`
- `source_request_log`: **2 rows**, `kind=search`, `status_code=NULL`, `ok=True`, note `ok: no observable status returned 34 rows`
- `sources`: `indeed` and `linkedin` both enabled; **`field_fill_baseline_json` recorded for both** (the S2 anchor exists)
- `tests/live/test_probe_live.py` ran as `2 passed, 287 deselected`

> ⚠️ **This run predates `489422d`.** The `created 1 / updated 33` split is the
> DataFrame-iteration bug signature (all 34 rows collapsing onto one blank listing),
> not a result about either board. The verdict document marks it explicitly
> non-representative.

### Gate A — compose smoke (`data/jobsearch.db`, cold DB)

- `/health` = 200 with `{"status":"ok","db":"ok","opencode":{"reachable":true,"version":"1.18.29"},"sources":{"indeed":{...,"enabled":true},"linkedin":{...,"enabled":true}}}`
- run triggered, reached terminal, `docker compose restart`, script printed `== PASS`
- **101 `listing-title` cells before and identical after the restart**
- independently verified: `sources` `indeed`+`linkedin` enabled; `listings=100`; **`distinct content_hash=100`**; `blank titles=0`; `indeed 50 / linkedin 50`; `duplicate listing_ids=0`; run 1 `status=done`, `fetched_count=100`, `created 50+50`, `updated=0`; ledger 2 rows `ok`; sample rows carry real titles/companies/locations (e.g. `Senior Software Engineer / mastercard / Dublin, D, IE`)

## Deviations from Plan

### Auto-fixed Issues (all seven were exposed by the operator gates, which is what the gates exist for)

**1. [Rule 3 - Blocking] The pinned dependency named a non-existent distribution (`aa6bb97`, `9cbe015`)**
- **Found during:** Gate B (dependency install)
- **Issue:** `requirements.txt`/`pyproject.toml` referenced `jobspy`; the repository's distribution is `python-jobspy`. pip built the sdist, hit `MetadataInconsistent` (logged at INFO and swallowed), discarded the candidate and reported a misleading `jobspy (unavailable)`. The PyPI `jobspy` is an unrelated 2016 Redis package — installing it would have been a supply-chain error, not a version error. Separately, the PEP 610 build-time revision assertion was written as a BuildKit heredoc, which the operator's classic builder cannot parse.
- **Fix:** named `python-jobspy` in the pinned VCS reference; converted the revision assertion to a single-line `python -c`. A manifest test now rejects heredocs and validates every Dockerfile logical line against the classic instruction set.
- **Verification:** `tests/test_deploy_manifest.py`.
- **Committed in:** `aa6bb97`, `9cbe015`

**2. [Rule 3 - Blocking] `run-probe.sh` did not fail fast on an unusable interpreter (`025daae`)**
- **Found during:** Gate B (first run attempt)
- **Issue:** an unusable interpreter produced empty envelope values and a raw `[: : integer expected` from the comparison, which reads like a script bug rather than a platform problem.
- **Fix:** exit 2 with the real import error and a platform remedy.
- **Committed in:** `025daae`

**3. [Rule 3 - Blocking] `sources` was never seeded in production (`2ab01f0`)**
- **Found during:** Gate B
- **Issue:** nothing outside tests ever inserted a `sources` row, so `enabled_source_names()` returned `[]`; `/health` reported `sources:{}` and a run did nothing. The whole ingest path was inert on a fresh deployment.
- **Fix:** idempotent `ensure_registered_sources()` in `app/db/repositories/source_repo.py`, called from the `app/main.py` lifespan and from `scripts/run-probe.sh` after migration.
- **Verification:** `tests/db/test_source_seeding.py`; the gate output `sources registered: indeed, linkedin`.
- **Committed in:** `2ab01f0`

**4. [Rule 1 - Bug] The compose smoke could never read its run id (`683976b`)**
- **Found during:** Gate A
- **Issue:** the script discarded the `POST /runs` response body and then regexed `/`, which never renders a run fragment — so it always failed at the run-id step.
- **Fix:** parse the 202 fragment the script already receives.
- **Committed in:** `683976b`

**5. [Rule 1 - Bug] A zero-source run reported `done` (`58a2abf`)**
- **Found during:** Gate A
- **Issue:** `all([])` is `True`, so a run that resolved no sources reported a clean success — the exact "green run, broken scrape" failure PITFALLS P1 warns about.
- **Fix:** `partial` with `NO_SOURCES_REASON` in `errors_json`, rendered by `_run_status.html`; the runbook no longer misattributes an empty queue to a scrape result.
- **Verification:** `tests/pipeline/test_partial_failure.py#test_a_run_that_resolved_no_sources_is_not_a_clean_success`.
- **Committed in:** `58a2abf`

**6. [Rule 1 - Bug] THE CRITICAL ONE — a scraped DataFrame was iterated as column labels (`489422d`, `0e70991`, `f690153`)**
- **Found during:** Gate A / Gate B (`created 1 / updated 33` on a 34-row page)
- **Issue:** both adapters did `rows = list(frame)` on a pandas DataFrame, which yields **column labels**, not records. Every mapped field was `None`, every `content_hash` was identical, and a full page collapsed to a single blank listing. The queue would have looked populated while containing one meaningless row per board.
- **Fix:** `frame_rows()` + `UnsupportedFrameError` as the one explicit conversion point (no silent-empty fallback), split the flattened comma-joined `job_type`, completed `DESIRED_ORDER` to the full `jobspy.util.desired_order`, realigned the fixtures, and added real-DataFrame regression tests.
- **Verification:** `tests/sources/test_dataframe_conversion.py` (incl. `#test_distinct_dataframe_rows_do_not_collapse_to_one_content_hash`), `tests/sources/test_jobspy_contract.py`; mutation-verified. Post-fix evidence: 100 listings with **100 distinct content_hash** and 0 blank titles.
- **Committed in:** `489422d`, `0e70991`, `f690153`

---

**Total deviations:** 7 auto-fixed (3 blocking, 4 bugs) + 1 hygiene commit.
**Impact on plan:** Every fix was necessary for the plan's own deliverable to be true — the probe gate could not even install its dependency, and the compose gate could not produce a meaningful listing. Two of them (the distribution name and the DataFrame iteration) would have shipped a broken or deceptive system. No architectural change, no new dependency.

## Issues Encountered

- **`probe()` is not a reliable proxy for `fetch()` — recorded, not papered over.** In the *same container session* the `/health` probe reported `indeed: unreachable` and `linkedin: degraded` at 21:02:36, while `runs.id = 1` had just fetched **50 usable listings from each board** at 21:02:01. The two instruments use different request paths, so the probe's classification does not corroborate ingest success. The survival verdict is unaffected (it derives from `runs` + `source_request_log`, both healthy), but `/health`'s liveness badge can mislead a user, and promotion condition **P-4 is unusable as written** because it is the one condition that reads `probe()`. This is the same family as WINDOWS entry #3 (the deferred positive structural marker). Recorded as `.planning/WINDOWS.md` entry **#4** and §7 of the verdict document, as a candidate human-verification item for phase verification.
- **`DATABASE_URL` in `compose.yml` is dead configuration.** The `Settings` field is `database_url_async` (env `DATABASE_URL_ASYNC`), so the compose variable never reaches the app; the container works only because the field default is the same path (`sqlite+aiosqlite:////data/jobsearch.db`). Harmless today, misleading the moment someone changes one of them. `scripts/run-probe.sh` uses the correct names. Not fixed here (documentation/tracking close-out only).
- **The verdict's window is not met.** One run on one day is not a measurement; the operator will keep running daily and the document flips to FINAL when ≥3 distinct days are recorded.

## User Setup Required

None beyond the operator steps already completed. Two deliverables remain operator-cadenced rather than blocked: keep running `bash scripts/run-probe.sh` daily until the ≥3-distinct-day window is met, then replace §2/§3 of the verdict and flip the marker to FINAL.

## Known Stubs

None. No stub, placeholder, `TODO`/`FIXME`, empty-value-to-UI or unwired data source was introduced. The two `human_judgment` coverage entries are the honest gaps (the not-yet-met verdict window and the probe-vs-fetch limitation), not stubs.

## Threat Flags

None new. The highest-risk surface here is outbound volume against hostile boards (T-01-35/T-01-36): mitigated by the config envelope, the script's refusal above the ceiling, and the AST-asserted absence of any retry path for a block.

## Threat Register Coverage

| Threat ID | Disposition | Covered by |
|-----------|-------------|------------|
| T-01-35 (unbounded request velocity → ban risk) | mitigate | envelope from `Settings`; `scripts/run-probe.sh` refuses above the ceiling (verified offline: exit 3) |
| T-01-36 (an escalating retry loop converting a block into a ban) | mitigate | `tests/probe/test_thresholds.py#test_the_transport_has_no_retry_or_escalation_path` (AST: no `tenacity`, no `while`) |
| T-01-37 (a verdict document that overstates its evidence) | mitigate | PROVISIONAL marker with the true run count; §2/§3 mark the one run non-representative; §4 maps every figure to a row |
| T-01-38 (a probe run leaking listing PII into the verdict) | mitigate | document carries counts, statuses and fill-rates only; verified no listing text or contact-shaped token present |
| T-01-39 (the smoke exposing the app beyond the host) | mitigate | `compose.yml` binds 8000 on the host only; `tests/test_deploy_manifest.py` |
| T-01-SC (package installs) | accept | `tech-stack.added: []` — but see deviation 1, where the *pinned* reference named a different distribution |

## Next Phase Readiness

- **Phase 1 is functionally complete and measured, with one honest gap.** All 7 plans are executed: the walking skeleton boots via `docker compose up`, both boards ingest real listings, the queue renders them, per-source health is visible, and the survival verdict exists in the only honest form available at 1 run — PROVISIONAL.
- **The Adzuna decision stays deferred to Phase 8**, as the roadmap provides. The condition is code-checkable: `adzuna_promotion_condition()` reads the same settings the verdict cites.
- **Two open items for phase verification** (both in `.planning/WINDOWS.md`): entry #3 (the deferred positive structural marker) and entry #4 (the probe-vs-fetch discrepancy). Both need a human decision, and both are recorded with evidence rather than waived.
- **Phase 2 inherits a healthy foundation:** a real ledger (`source_request_log`), a recorded fill-rate baseline per source, the `runs` observation surface, and adapters whose DataFrame conversion is now explicitly contracted and regression-tested.
- **One correction worth carrying:** fix the dead `DATABASE_URL` in `compose.yml` (or align the field name) before a hosted deployment relies on it.

## Self-Check: PASSED

- **All planned deliverables exist on disk:** `app/probe/survival.py`, `app/sources/_ledger.py`, `tests/probe/test_thresholds.py`, `tests/live/test_probe_live.py`, `scripts/run-probe.sh`, `scripts/compose-smoke.sh`, `docs/probes/README.md`, `docs/probes/2026-09-15-scraper-survival.md`, `docs/runbook-compose-smoke.md`.
- **Commits verified:** `5e5c242` and `74504df` (this executor) plus the ten defect-fix commits are all present in `git log` from the plan base `dc76a97`.
- **Operator gates verified *independently*:** every figure quoted in this SUMMARY and in the verdict document was re-read by this executor from `data/probe.db` and `data/jobsearch.db` (opened read-only) — not copied from the operator's message. Both match.
- **Task acceptance criteria re-checked:** Task 1's criteria pass (`tests/probe/test_thresholds.py` → 43 passed); Task 2's script/runbook/verdict artefacts pass, with the verdict honest about its window; Task 3's script/runbook artefacts pass and the operator's smoke printed PASS.
- **Plan `<verification>`:** `python -m pytest -q -x` → all green (count reported in the completion message); the `live` lane is excluded by default. Ruff clean.
- **`must_haves`:** every truth is assertion-backed or explicitly recorded. The three window-dependent truths (S2 drift measured from a baseline, S3 armed at ≥2 prior runs, S4 at 3 consecutive runs) are implemented and boundary-tested but **not yet exercisable on real data** — they are the reason the verdict is PROVISIONAL, and coverage entries D7/D10 record that rather than claiming a measurement. The `backstop` statements (S1, S5, S6, the first-run baseline) are all assertion-backed (D1–D4).
- **Nothing was fabricated:** the verdict carries 1 run on 1 day, marks the single run non-representative, and states the Adzuna decision as deferred.
