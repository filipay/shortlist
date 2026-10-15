---
phase: 08-operations-polish
plan: 04
subsystem: api
tags: [health, fastapi, jinja2, htmx, apscheduler, sqlite, sqlalchemy, probe, httpx, pytest]

# Dependency graph
requires:
  - phase: 08-operations-polish
    provides: "the scheduler (plan 08-03): next_run_at(), the stored ScheduleConfig and the durable D-154 skip notice on the operations row"
  - phase: 08-operations-polish
    provides: "plan 08-02's .health-system / .table-scroll / .touch-target CSS tokens and the shared base.html nav block"
  - phase: 01-probe-and-pipeline
    provides: "GET /health, its four dependency reports, VALID_HEALTH, get_source_health, the ledger (source_request_log) and the pure survival signals"
provides:
  - "dependency_report(session, backend, engine) — the four boot-tolerant probes in ONE definition, shared by the JSON endpoint and the page (D-138)"
  - "GET /status — a human health page that reads the database only and never contacts a job board (D-156)"
  - "get_source_health_with_signals(session) — per-source badges derived from recorded run outcomes AND recorded stop signals"
  - "board_evidence(session, source_name) — the missing BoardEvidence builder from persisted rows (RESEARCH Pattern 7)"
  - "the read-only Adzuna promotion verdict, with its number, on the page (D-158)"
affects: [08-05, 09, verification, ship, runbook-responsive-ui]

actuals:
  tokens: 15147
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "One report builder, N surfaces: extract a total computation into a named function rather than letting a second surface re-implement it, so the two cannot disagree"
    - "Assemble-don't-measure: a status page reads recorded rows (runs, source_request_log, the ops singleton) and derives sentences at render time; a missing value is an honest state, never a fabricated one"
    - "Structural note anchoring: read a recorded classification off the exact prefix ONE function emits, never a substring scan (CONVENTIONS rule 1)"
    - "Read-only evidence: a computed verdict renders with its number and a link, and a test asserts the region holds no control"
    - "Peak-pool-free dev loop: the page context is built from the same repository reads the JSON endpoint uses"

key-files:
  created:
    - app/api/health_page.py
    - app/web/templates/html/health.html
    - tests/api/test_health_page.py
  modified:
    - app/api/health.py
    - app/db/repositories/source_repo.py
    - app/main.py
    - app/web/templates/html/base.html
    - tests/test_auth_seam.py

key-decisions:
  - "The JSON endpoint keeps /health and the page takes /status (orchestrator decision C1): FastAPI is first-match-wins and /health is pinned by 25 .json() assertions, the auth-seam route inventory and scripts/compose-smoke.sh"
  - "dependency_report's returned key names and reading order are the JSON contract; the route merges them with **report rather than restating them"
  - "The page's source badge projects an S5 classification onto VALID_HEALTH ('pass' -> the stored value or ok, 'warn' -> degraded); 'unreachable' is not invented where the recorded evidence does not support it"
  - "The promotion verdict is decided by P-1 alone, whose observed fraction is the number the page prints; a short window renders the no-verdict sentence with no number"
  - "A run with no listing rows contributes no fill-rate sample to the board evidence rather than a zeroed one, which would falsely read as a collapse against a baseline"

patterns-established:
  - "Extraction over duplication: a second consumer of a total computation gets the computation named and shared, not copied"
  - "Recorded-prefix anchoring for ledger notes emitted by exactly one function"
  - "Every new read on a status surface is individually guarded so one failure degrades one line, not the page"

requirements-completed: [RUN-06, RUN-07]

coverage:
  - id: D1
    description: "GET /status renders the four dependency rows (Database, LLM backend, LaTeX engine, CV fact store) from the shared builder, and GET /health keeps its JSON shape under its existing assertions"
    requirement: "RUN-07"
    verification:
      - kind: integration
        ref: "tests/api/test_health_page.py#test_the_page_renders_the_four_dependency_rows"
        status: pass
      - kind: integration
        ref: "tests/api/test_health.py (20 exact JSON assertions, unchanged)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The page and the JSON endpoint cannot disagree about opencode reachability or auth_configured (D-138)"
    requirement: "RUN-07"
    verification:
      - kind: integration
        ref: "tests/api/test_health_page.py#test_the_page_and_the_json_cannot_disagree"
        status: pass
    human_judgment: false
  - id: D3
    description: "A page view issues no board request: a sentinel adapter's probe/fetch counters stay at zero and the live probe cache is untouched (D-156 / T-08-17)"
    requirement: "RUN-07"
    verification:
      - kind: integration
        ref: "tests/api/test_health_page.py#test_the_page_issues_no_board_request"
        status: pass
      - kind: integration
        ref: "tests/api/test_health_page.py#test_the_verdict_read_issues_no_board_request"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every failure degrades to data: a broken database read, an exploding dependency probe and a raising scheduler each still answer 200 (D-08)"
    requirement: "RUN-07"
    verification:
      - kind: integration
        ref: "tests/api/test_health_page.py#test_the_page_answers_when_the_database_read_fails"
        status: pass
      - kind: integration
        ref: "tests/api/test_health_page.py#test_the_page_answers_when_a_dependency_probe_raises"
        status: pass
      - kind: integration
        ref: "tests/api/test_health_page.py#test_the_page_answers_when_the_scheduler_raises"
        status: pass
    human_judgment: false
  - id: D5
    description: "The next-run line: a registered job renders the scheduled time plus a render-time countdown, a disabled schedule renders 'Scheduling off', and an enabled-but-unregistered schedule renders an honest no-run state with no number"
    requirement: "RUN-06"
    verification:
      - kind: integration
        ref: "tests/api/test_health_page.py#test_the_next_run_line_renders_a_countdown_for_a_registered_job"
        status: pass
      - kind: integration
        ref: "tests/api/test_health_page.py#test_a_disabled_schedule_reads_scheduling_off"
        status: pass
      - kind: integration
        ref: "tests/api/test_health_page.py#test_an_enabled_schedule_with_no_job_never_fabricates_a_time"
        status: pass
    human_judgment: false
  - id: D6
    description: "A skipped scheduled run is surfaced from its durable record (missed-run wording, in-flight wording) and never inferred from a gap in the run history"
    requirement: "RUN-06"
    verification:
      - kind: integration
        ref: "tests/api/test_health_page.py#test_the_missed_run_notice_renders_from_a_recorded_skip"
        status: pass
      - kind: integration
        ref: "tests/api/test_health_page.py#test_the_in_flight_skip_renders_its_own_wording"
        status: pass
      - kind: integration
        ref: "tests/api/test_health_page.py#test_no_notice_renders_without_a_recorded_skip"
        status: pass
    human_judgment: false
  - id: D7
    description: "The last-run line names the newest run's status and its one-line reason and links to /runs; it is absent when no run exists"
    requirement: "RUN-07"
    verification:
      - kind: integration
        ref: "tests/api/test_health_page.py#test_the_last_run_line_names_the_status_and_reason"
        status: pass
      - kind: integration
        ref: "tests/api/test_health_page.py#test_the_last_run_line_is_absent_with_no_runs"
        status: pass
    human_judgment: false
  - id: D8
    description: "Each source's badge is derived from recorded stop signals (classified fetch-side by the existing pure classifier) without any adapter being called"
    requirement: "RUN-07"
    verification:
      - kind: integration
        ref: "tests/api/test_health_page.py#test_a_recorded_stop_signal_classifies_the_badge_fetch_side"
        status: pass
      - kind: integration
        ref: "tests/api/test_health_page.py#test_a_source_with_no_recorded_request_keeps_its_stored_value"
        status: pass
    human_judgment: false
  - id: D9
    description: "The Adzuna promotion verdict shows as read-only evidence with its recorded number and the probe-document link; a short window prints the no-verdict sentence with no number, and the region holds no form, button or enabling control (D-158)"
    requirement: "RUN-07"
    verification:
      - kind: integration
        ref: "tests/api/test_health_page.py#test_the_verdict_line_carries_the_recorded_fraction"
        status: pass
      - kind: integration
        ref: "tests/api/test_health_page.py#test_a_short_window_renders_no_verdict_and_no_number"
        status: pass
      - kind: integration
        ref: "tests/api/test_health_page.py#test_the_verdict_region_offers_no_control"
        status: pass
    human_judgment: false
  - id: D10
    description: "The Health nav entry reaches /status with the current-page marker, and the route is in the auth-seam inventory (PLAT-03)"
    requirement: "RUN-07"
    verification:
      - kind: unit
        ref: "tests/test_auth_seam.py#test_every_route_with_a_dependant_declares_current_user"
        status: pass
      - kind: unit
        ref: "tests/test_stylesheet_coverage.py#test_every_template_class_has_a_stylesheet_rule"
        status: pass
    human_judgment: false
  - id: D11
    description: "The /status page laid out at 320 / 375 / 768 px is visually usable on a phone and a laptop"
    verification: []
    human_judgment: true
    rationale: "No browser and no Docker in the executor sandbox. The static half is proven (stylesheet byte-identity, reflow rules, data-label cells, tap-floor); the rendered walkthrough is the operator's, already recorded as an open unrun-verify in .planning/WINDOWS.md (entry 15) and documented in docs/runbook-responsive-ui.md, which carries a /status row."

# Metrics
duration: 41min
completed: 2026-10-14
status: complete
---

# Phase 08 Plan 04: The tool tells the truth about itself Summary

**A `/status` health page assembled from one shared dependency builder: the four probes, the next scheduled run (or `Scheduling off`, or an honest no-run state), the last run's status and reason, a missed/in-flight skip read off its durable record, and the Adzuna promotion verdict as read-only evidence with its number — all from recorded rows, with a test proving a page view never puts a request on a job board.**

## Performance

- **Duration:** ~41 min (18:58:40Z base commit → 19:39:50Z last task commit)
- **Started:** 2026-10-14T18:59:00Z (approx.)
- **Completed:** 2026-10-14T19:40:25Z
- **Tasks:** 3
- **Files modified:** 8 in the plan diff (`tests/api/test_health.py` deliberately untouched)

## Accomplishments

- **One builder, two surfaces.** `dependency_report(session, backend, engine)` in `app/api/health.py` owns the database check and the three module-level probes; `GET /health` merges its result with `**report` (key names and reading order unchanged) and the page reads the same function. `tests/api/test_health.py`'s 20 exact JSON assertions, the forbidden-body-keys scan and `tests/test_auth_seam.py` all stayed green with zero edits.
- **A page that is not a scrape.** `GET /status` reads the database only. The page module contains no reference to `probe_all`, a sentinel adapter's `probe`/`fetch` counters are asserted at zero after a fetch, and the live probe cache is asserted empty.
- **Source badges from recorded outcomes and recorded stop signals.** `get_source_health_with_signals` reuses the existing run-derived read and adds, per source, the newest `probe_count_trailing_runs` ledger rows classified by the shipped pure `classify_block_vs_parse`; the newest side projects onto `VALID_HEALTH` (`fetch-side` → `degraded`). No new write, no adapter call, no new vocabulary.
- **Schedule truth.** The stored singleton is the authority on enabled/disabled, `next_run_at()` supplies the next fire time, and the countdown is computed at render time in the schedule's timezone. A disabled schedule reads `Scheduling off`; an enabled schedule with no registered job reads `No run currently scheduled.` and prints no countdown; a past-due fire time floors at `0m` rather than counting backwards.
- **A skip is surfaced, never inferred.** The missed/in-flight notice comes only from the durable record on the operations row; a gap in the run history renders nothing.
- **The missing builder, written.** `board_evidence(session, source_name)` assembles `BoardEvidence` from persisted rows (the newest window of runs that recorded the board, the recorded baseline, the ledger's implied liveness, per-run fill-rates scoped exactly as `get_source_health` scopes them) and returns `None` when a board has no recorded evidence.
- **Evidence, not an action.** The verdict line carries P-1's observed fraction and its met/not-met wording, computed by the shipped pure `adzuna_promotion_condition`; a short window prints the no-verdict sentence with no number; the region contains no form, button or enabling control, and a test asserts it.

## Task Commits

Each task was committed atomically:

1. **Task 1: `/status` renders the system section from one shared dependency builder** — `a2f9e72` (feat)
2. **Task 2: The schedule line, the last-run line and the missed-run notice** — `e5c9e1e` (feat)
3. **Task 3: The Adzuna promotion verdict, read-only and with its number** — `9c06492` (feat)
4. **Hardening: degrade the schedule line when the tz database is absent** — `4782ba6` (fix)

**Plan metadata:** the SUMMARY + planning docs commit (this file)

## Files Created/Modified

- `app/api/health.py` — new `dependency_report()`; the `/health` route body now merges it and calls the probes exactly where they were
- `app/api/health_page.py` — **new**: `GET /status`, its total context helper, the four dependency-row view models, the schedule/skip/last-run readers, the verdict view models and `GET /status`
- `app/db/repositories/source_repo.py` — `SourceHealthDetail`, `CLASSIFICATION_HEALTH`, the recorded-prefix helpers, `get_source_health_with_signals()` and `board_evidence()`
- `app/main.py` — the health-page router included beside the existing health router
- `app/web/templates/html/health.html` — **new**: the system grid over `<dl class="health-system">`, the schedule/skip/last-run strips, `#adzuna-verdict`, then `_health_strip.html` included verbatim
- `app/web/templates/html/base.html` — the seventh nav entry, `Health` at `/status`
- `tests/api/test_health_page.py` — **new**: 25 tests (the page lane: the four rows, the page/JSON agreement, the sentinel no-board-request proof, three totality cases, three next-run cases, three skip-notice cases, two last-run cases, two badge cases, four verdict cases)
- `tests/test_auth_seam.py` — `/status` added to `EXPECTED_SEAM_ROUTES`

## Decisions Made

- **`/health` stays JSON; the page takes `/status`.** Forced by FastAPI's declaration-order matching plus 25 pinned `.json()` call sites and the compose smoke script. The page module asserts the path and that `/health` is never declared in it.
- **`**report` in the JSON route, not a re-listing of keys.** The extraction's whole value is that there is one definition; restating the keys would reintroduce the drift the plan exists to remove.
- **`parsed_items` reconstructed from `ok`.** The classifier needs a row count the ledger does not store; `ok` is the recorded outcome and reproduces ingest's classification for both the clean and the parse-side cases, while the stop signal and the transport-error prefix take precedence.
- **`degraded` is the only derived failure badge.** The recorded evidence supports "this board pushed back"; `unreachable` is a live-check verdict the ledger does not carry, so it is not invented.
- **P-1 decides the verdict.** P-1 is the signal whose number the copy names, so reading the met flag from the same result keeps the sentence and the flag consistent; P-2…P-5 remain inside the pure function for a later full evaluation. A short window prints no number at all.
- **A rowless run contributes no fill-rate sample.** Zeroed rates against a recorded baseline would read as a 100-point collapse — a fabricated failure.

## Deviations from Plan

### Task partition (Rule 3 — blocking/ordering)

**1. `board_evidence` + its helpers landed in Task 2's commit, not Task 3's.**
- **Found during:** Task 2 (`get_source_health_with_signals`)
- **Issue:** the builder's per-ledger-row helpers (`_recorded_stop_signal`, `_classify_ledger_row`, `_count`, `_window_days`, `_ledger_probe_status`) share the classification vocabulary Task 2 introduced, and splitting one cohesive repository module across two commits would have meant writing the helpers twice.
- **Fix:** `board_evidence` is in `source_repo.py` exactly where the plan's artifact list places it — the repository layer, beside the other run-derived reads. Only the *commit boundary* moved; the Task 3 work (the route's verdict view models, the template region and the four verdict tests) is in Task 3's commit as specified.
- **Verification:** `tests/api/test_health_page.py#test_the_board_evidence_builder_lives_in_the_repository_layer` asserts the builder is async and lives in `source_repo`; the Task 3 gate `-k "adzuna or verdict"` selects its 5 named cases.
- **Committed in:** `e5c9e1e` (Task 2 commit)

### Auto-fixed Issues

**2. [Rule 2 - Missing critical functionality] The timezone lookup was unguarded.**
- **Found during:** post-task review of `_schedule_line`
- **Issue:** `ZoneInfo(schedule.timezone)` raises `ZoneInfoNotFoundError` when the image ships no tz database — RESEARCH Pitfall 7 / assumption A1 is explicitly unverified, and a raise there would 500 a decorative page (T-08-20).
- **Fix:** the construction is now inside the line's own guard and degrades to the honest no-run state; the countdown still never comes from `None`.
- **Files modified:** `app/api/health_page.py`
- **Verification:** the page lane plus `tests/api/test_health.py`, `tests/test_auth_seam.py`, `tests/test_no_cdn.py`, `tests/test_stylesheet_coverage.py` — 74 passed.
- **Committed in:** `4782ba6`

---

**Total deviations:** 1 task-partition note + 1 auto-fixed (missing critical functionality)
**Impact on plan:** No scope creep and no contract change. The partition note is a commit-boundary artefact; the timezone guard is the same totality discipline every other read on this page follows.

## Issues Encountered

- **`tests/api/test_health.py` was listed in `files_modified` and was NOT changed.** That file is the proof the extraction preserved the contract; the plan says any failure there belongs in the extraction, not the assertion. It passed unmodified, so the file is absent from the diff by design.
- **The verification lane.** The project `.venv` is unusable in this sandbox (symlinked to a 3.11 `python3` with no `pytest`, built for 3.14.7). Every gate in the plan was run through the documented lane: `PYTHONPATH=/workspace/job-search:/workspace/job-search/.venv/lib/python3.11/site-packages /tmp/opencode/gsdvenv13/bin/python -m pytest`. The substitution is environmental, not a change to any assertion.
- **One test assertion was over-broad and was corrected at authoring time**, not by loosening the product: `assert not re.search(r"\d", line)` matched the `2026` inside the probe-document href. It now checks the rendered sentence span, so the assertion still fails on a fabricated number.

## Verification

- `tests/api/test_health_page.py` — 25 passed
- `tests/api/test_health.py` — 20 JSON assertions, unchanged, passed
- `tests/test_auth_seam.py` — passed, with `/status` in `EXPECTED_SEAM_ROUTES`
- `tests/test_no_cdn.py` + `tests/test_stylesheet_coverage.py` — passed, byte-identity assertion run (no rebuild needed: the page adds no class and no rule)
- Full hermetic suite — **1848 passed, 2 xfailed, 15 deselected**
- The plan's three static one-liners (page declares `/status` and not `/health`; no `probe_all` on the page path; `board_evidence` async in the repository layer; the template's verdict is read-only evidence with a link) all pass

## Known Stubs

None. Every section is wired to persisted data; the absent states (no sources, no runs, no notice, no verdict, no next run) are deliberate honest states with their own copy and their own tests, not placeholders.

## User Setup Required

None - no external service configuration required.

The two operator-run checks this plan feeds are unchanged and already recorded as open in `.planning/WINDOWS.md`:

- **entry 15** — the 320/375/768 walk of `docs/runbook-responsive-ui.md`, which already carries a `/status` row.
- **entry 16** — the schedule-persistence compose smoke whose `/health` JSON parse this plan deliberately left untouched.

## Next Phase Readiness

- The health surface is complete: `/health` (JSON, unchanged contract) and `/status` (human page, DB-only), sharing one builder and one partial, so D-138's "cannot disagree" holds by construction rather than by test alone.
- `board_evidence` is the builder RESEARCH Pattern 7 called out as missing; it is the natural input for a future Adzuna promotion decision and now has a production caller.
- Plan 08-05 (retention/pruning) can rely on `source_repo`'s ordering conventions and on `VALID_HEALTH` as the single badge vocabulary; note the new `app.probe.survival` import in `source_repo` (pure functions only — `app.probe.probe` is still never imported there).
- Residual, accepted: the verdict derives from a bounded run window, so a fresh corpus reads `no verdict recorded yet`. That is the honest state, and it is tested.

---
*Phase: 08-operations-polish*
*Completed: 2026-10-14*

## Self-Check: PASSED

- `app/api/health_page.py` — FOUND
- `app/web/templates/html/health.html` — FOUND
- `tests/api/test_health_page.py` — FOUND
- `.planning/phases/08-operations-polish/08-04-SUMMARY.md` — FOUND
- commits `a2f9e72`, `e5c9e1e`, `9c06492`, `4782ba6` — all FOUND
