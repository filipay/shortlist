---
phase: 01-walking-skeleton-foundations
plan: 05
subsystem: testing
tags: [sanitiser, pii, gdpr, ast-guard, fastapi, auth-seam, config-as-code, vendored-assets, pytest]

# Dependency graph
requires:
  - phase: 01-walking-skeleton-foundations
    provides: the sanitise stage (ingest/sanitize.py + domain/sanitize.py), the pipeline call site and the migration-0001 schema/PII-negative test
provides:
  - a hardened pure sanitiser with exact character-count truncation, HTML reduction, PII removal and an instruction-like flag
  - an AST-based no-credential-path guard across all of app/
  - a vendored-assets-only guard for every template (UI-07)
  - a non-vacuous universal auth-seam guard for every FastAPI route (PLAT-03)
  - a config-not-constants guard for the probe envelope (PLAT-04)
affects: [phase-2-sanitise-catalogue, phase-8-ui-assets, any-phase-adding-a-route, any-phase-touching-probe-limits]

# Actuals (#2632) — same estimateTokens scale as the plan's estimate (chars/4 over the realized diff)
actuals:
  tokens: 12018
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Static guard + positive-control test: every non-vacuous assertion is paired with a synthetic input or mutation that proves the guard can fail"
    - "Config-as-code enforced behaviourally (patch Settings, observe the builder output) and statically (no distinctive settings default appears as a literal)"
    - "Recursive FastAPI route walk: flatten _IncludedRouter wrappers, first prove the leaf set was reached, then assert per-route"

key-files:
  created:
    - tests/domain/test_sanitize.py
    - tests/domain/test_sanitize_pii.py
    - tests/domain/test_sanitize_edge.py
    - tests/test_no_credentials.py
    - tests/test_no_cdn.py
    - tests/test_auth_seam.py
    - tests/test_config.py
  modified:
    - app/domain/sanitize.py
    - app/ingest/sanitize.py
    - app/config.py
    - app/pipeline/run.py

key-decisions:
  - "Truncation is over Python code points: sanitize_text slices to exactly max_chars, the previous .rstrip() could return fewer than the documented limit, and the contract is stated in the module and function docstrings"
  - "PII is dropped and only an aggregate count is logged; the event payload is asserted with structlog capture_logs, a stdlib-backed caplog bridge and capsys because structlog has no explicit configuration and PrintLogger bypasses caplog"
  - "test_auth_seam.py recurses through _IncludedRouter.original_router.routes and proves the walk reached the four leaf routes before asserting the seam, closing the vacuous-pass hazard plan 01-04 reported"
  - "RULE 2 FIX: DEFAULT_QUERY (results_wanted=50, location='Ireland' literals) became default_query() reading settings, plus a new settings.probe_query_location, so must-have #9 holds"
  - "SanitizeResult renamed to SanitisedText (the plan's name) with SanitizeResult kept as an alias; the stage keeps sanitize_listing rather than gaining a British-spelling duplicate"

patterns-established:
  - "A static guard is only trusted with a positive control: tests/test_no_credentials.py, tests/test_no_cdn.py, tests/test_config.py and tests/test_auth_seam.py each ship a can-fail test (verified by mutation during execution)"
  - "The sanitise boundary is singular: no adapter may import the sanitiser, asserted by an AST import walk over app/sources"

requirements-completed: [SRC-06, SRC-08, SRC-10, PLAT-03, PLAT-04, UI-07]

coverage:
  - id: D1
    description: "Untrusted listing text is sanitised once at the single named `sanitize` ingest stage, before it is persisted"
    requirement: "SRC-08"
    verification:
      - kind: integration
        ref: "tests/pipeline/test_ingest_e2e.py#test_sanitise_stage_ran_and_dropped_the_email_canary"
        status: pass
      - kind: unit
        ref: "tests/domain/test_sanitize_pii.py#test_no_adapter_sanitises_independently"
        status: pass
      - kind: unit
        ref: "tests/domain/test_sanitize_pii.py#test_the_ingest_stage_is_named"
        status: pass
    human_judgment: false
  - id: D2
    description: "Recruiter emails and phones are removed from listing text, never hashed, and never recorded — only a count reaches the log"
    requirement: "SRC-10"
    verification:
      - kind: unit
        ref: "tests/domain/test_sanitize_pii.py#test_email_and_phone_are_removed_from_the_text"
        status: pass
      - kind: unit
        ref: "tests/domain/test_sanitize_pii.py#test_removed_pii_is_never_hashed"
        status: pass
      - kind: unit
        ref: "tests/domain/test_sanitize_pii.py#test_the_stage_emits_a_count_and_never_the_removed_value"
        status: pass
      - kind: unit
        ref: "tests/domain/test_sanitize_pii.py#test_the_removed_value_does_not_reach_captured_log_output"
        status: pass
      - kind: unit
        ref: "tests/domain/test_sanitize_pii.py#test_the_removed_value_does_not_reach_stdout"
        status: pass
    human_judgment: false
  - id: D3
    description: "Truncation is bounded to exactly max_chars Python characters; at-limit input is unchanged; multi-byte input truncates by code point without raising; null/empty is a deterministic empty string"
    requirement: "SRC-08"
    verification:
      - kind: unit
        ref: "tests/domain/test_sanitize_edge.py#test_exactly_at_the_limit_is_unchanged"
        status: pass
      - kind: unit
        ref: "tests/domain/test_sanitize_edge.py#test_one_over_the_limit_is_truncated_to_exactly_the_limit"
        status: pass
      - kind: unit
        ref: "tests/domain/test_sanitize_edge.py#test_multibyte_text_truncates_by_characters_not_bytes"
        status: pass
      - kind: unit
        ref: "tests/domain/test_sanitize_edge.py#test_null_and_empty_descriptions_sanitise_to_an_empty_string"
        status: pass
      - kind: unit
        ref: "tests/domain/test_sanitize_edge.py#test_sanitising_the_same_input_twice_is_identical"
        status: pass
    human_judgment: false
  - id: D4
    description: "The instruction-like flag fires for imperative system-style markers and stays clear for ordinary prose (the pattern catalogue remains a Phase 2 task)"
    requirement: "SRC-08"
    verification:
      - kind: unit
        ref: "tests/domain/test_sanitize.py#test_each_instruction_marker_is_flagged"
        status: pass
      - kind: unit
        ref: "tests/domain/test_sanitize.py#test_ordinary_prose_is_otherwise_unchanged"
        status: pass
      - kind: unit
        ref: "tests/domain/test_sanitize.py#test_the_flag_survives_truncation"
        status: pass
    human_judgment: false
  - id: D5
    description: "Two descriptions differing only in stripped PII sanitise equal, so content_hash is stable across PII variants of one listing"
    requirement: "SRC-10"
    verification:
      - kind: unit
        ref: "tests/domain/test_sanitize_pii.py#test_texts_differing_only_in_pii_sanitise_equal"
        status: pass
      - kind: unit
        ref: "tests/domain/test_sanitize_pii.py#test_content_hash_is_stable_across_pii_variants"
        status: pass
      - kind: unit
        ref: "tests/domain/test_sanitize_pii.py#test_content_hash_still_distinguishes_real_edits"
        status: pass
    human_judgment: false
  - id: D6
    description: "No source file under app/ reads a portal credential, builds a cookie jar, or opens an authenticated session"
    requirement: "SRC-06"
    verification:
      - kind: unit
        ref: "tests/test_no_credentials.py#test_no_credential_read_or_authenticated_session_under_app"
        status: pass
      - kind: unit
        ref: "tests/test_no_credentials.py#test_no_credential_token_appears_as_text_under_app"
        status: pass
      - kind: unit
        ref: "tests/test_no_credentials.py#test_the_scan_covers_the_application_package"
        status: pass
    human_judgment: false
  - id: D7
    description: "No template references a remote asset origin; static/vendor holds htmx.min.js, alpine.min.js and app.css, all non-empty, and base.html links them"
    requirement: "UI-07"
    verification:
      - kind: unit
        ref: "tests/test_no_cdn.py#test_no_template_references_a_remote_asset_origin"
        status: pass
      - kind: unit
        ref: "tests/test_no_cdn.py#test_vendored_assets_exist_and_are_non_empty"
        status: pass
      - kind: unit
        ref: "tests/test_no_cdn.py#test_base_template_links_the_three_vendored_assets"
        status: pass
    human_judgment: false
  - id: D8
    description: "Every route declares Depends(current_user) in its dependant tree, and no speculative identity column exists (AP14)"
    requirement: "PLAT-03"
    verification:
      - kind: unit
        ref: "tests/test_auth_seam.py#test_the_walk_reaches_the_application_leaf_routes"
        status: pass
      - kind: unit
        ref: "tests/test_auth_seam.py#test_every_route_with_a_dependant_declares_current_user"
        status: pass
      - kind: unit
        ref: "tests/test_auth_seam.py#test_no_speculative_identity_column_exists"
        status: pass
    human_judgment: false
  - id: D9
    description: "Every probe limit, threshold, country and budget value is read from Settings, and no distinctive threshold literal remains in app/pipeline"
    requirement: "PLAT-04"
    verification:
      - kind: unit
        ref: "tests/test_config.py#test_build_budget_reads_every_ceiling_from_settings"
        status: pass
      - kind: unit
        ref: "tests/test_config.py#test_default_query_reads_its_location_and_count_from_settings"
        status: pass
      - kind: unit
        ref: "tests/test_config.py#test_an_environment_override_changes_the_effective_value"
        status: pass
      - kind: unit
        ref: "tests/test_config.py#test_no_distinctive_threshold_literal_remains_in_probe_or_pipeline"
        status: pass
    human_judgment: false

duration: 22 min
completed: 2026-09-15
status: complete
---

# Phase 01 Plan 05: Sanitise Hardening + Platform Guards Summary

**Hardened ingest boundary — exact code-point truncation, PII dropped and never logged — plus four falsifiable platform guards: no credential path, no remote asset, a universal auth seam, and every limit read from Settings.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-09-15T18:05:54Z
- **Completed:** 2026-09-15T18:28:01Z
- **Tasks:** 2
- **Files modified:** 11 (9 written by this plan + 2 pre-existing sources changed for the PLAT-04 fix)
- **Commits:** 3 (measured: `git rev-list --count 8c781d6..HEAD`)

## Accomplishments

- **The sanitiser's truncation contract is now exact and stated.** `sanitize_text` returns `SanitisedText` and slices to *exactly* `max_chars` Python characters; the previous `text[:max_chars].rstrip()` could return fewer than the documented limit. The "characters, not bytes, not grapheme clusters" contract is written in the module and function docstrings and pinned by a multi-byte (CJK) test that would raise on a byte slice.
- **PII is provably unrecorded.** Emails and phones are dropped (never hashed), the returned object cannot carry the removed value, and the stage logs only an aggregate `pii_removed` count. The assertion is made against the real structlog payload (`capture_logs`), a stdlib-backed `caplog` bridge, and true stdout (`capsys`) — three independent sinks.
- **SRC-06 is now falsifiable across all of `app/`.** An AST walk collects credential-shaped environment reads, session/cookie constructor keyword arguments and authenticating calls; the raw-token scan was broadened from `app/sources/` to `app/` with a deliberately narrow token list (bare `PASSWORD` would false-positive on the legitimate `opencode_server_password`).
- **The auth seam is proven, not assumed.** Plan 01-04's finding is closed: `include_router` yields `_IncludedRouter` wrappers with no `.dependant`/`.path`, so the test first *proves* its recursive walk reaches `/`, `/runs`, `/runs/{run_id}/status` and `/health`, then asserts `Depends(current_user)` on each. A route added later without the seam fails CI.
- **PLAT-04 is enforced three ways.** Settings surface + documented defaults, an environment override changing the effective value, behavioural proof that `build_budget()`/`default_query()` reflect patched settings, and a static scan proving no distinctive settings default appears as a literal in `app/pipeline`.
- **Every guard was mutation-checked.** Removing the seam from `/health`, adding a CDN `<link>` to `base.html`, re-hard-coding `results_wanted=50`, introducing `os.getenv("LINKEDIN_PASSWORD")`, and importing the sanitiser into an adapter each made exactly the intended test fail.

## Task Commits

Each task was committed atomically:

1. **Task 1: Harden the sanitise stage (PII, HTML, truncation, instruction flag)** - `33d4f61` (feat)
   - follow-up in the same task's scope: `3b9948b` (test) — the singular-and-named-stage assertions that back must-have #1
2. **Task 2: Platform guards (no credentials, no CDN, auth seam, config-not-constants)** - `7587f9a` (feat)

**Plan metadata:** _(this commit)_ (docs: complete plan)

## Files Created/Modified

- `app/domain/sanitize.py` — `SanitisedText` (alias `SanitizeResult`), exact code-point truncation, docstring-level unit contract, and a new 48-line docstring/implementation delta
- `app/ingest/sanitize.py` — the named stage now logs an aggregate `pii_removed` count and also fires for an instruction-like flag
- `app/config.py` — new `probe_query_location` setting (config surface, not a new trust boundary)
- `app/pipeline/run.py` — `DEFAULT_QUERY` constant replaced by `default_query()` reading `settings.probe_results_wanted` and `settings.probe_query_location`
- `tests/domain/test_sanitize.py` — HTML/entities/whitespace reduction, prose passthrough, instruction-flag behaviour (14 tests)
- `tests/domain/test_sanitize_pii.py` — PII removal, never-hashed, three-sink log absence, variant equality, `content_hash` stability, singular stage (13 tests)
- `tests/domain/test_sanitize_edge.py` — null/empty, one-under/at/one-over the limit, a space at the boundary, multi-byte, accented, determinism (11 tests)
- `tests/test_no_credentials.py` — AST credential scan + token scan + 5 positive controls (8 tests)
- `tests/test_no_cdn.py` — remote-origin scan, vendored file existence, exact file set, `base.html` links, two scan controls (7 tests)
- `tests/test_auth_seam.py` — recursive route walk, seam assertion, identity-column absence, two helper controls (5 tests)
- `tests/test_config.py` — Settings surface, defaults, env override, settings-driven builders, literal-absence scan + control (8 tests)

## Decisions Made

- **`SanitizeResult` renamed to `SanitisedText`** (the plan's contract name) with `SanitizeResult` retained as an import-compatible alias. Nothing outside `app/domain/sanitize.py` referenced the old name, and the alias keeps the change churn-free.
- **The stage keeps the name `sanitize_listing`.** The plan's artifact list predicted a British-spelled `sanitise_listing()`; adding a second public name for the same callable would be worse than the missing alias, so it was not added and is recorded here instead.
- **`caplog` alone cannot see structlog.** No explicit `structlog.configure(...)` exists in the app, so `structlog.get_logger()` writes through `PrintLogger` to stdout and bypasses the stdlib logging tree. The PII tests therefore assert against `capture_logs()` (the real event payload) *and* a `structlog.wrap_logger(logging.getLogger(...))` bridge monkeypatched into the stage for `caplog`, plus `capsys` for the rendered output.
- **The config-not-constants fix is a Rule 2 auto-fix, not scope creep.** Must-have #9 ("no threshold literal appears in app/probe or app/pipeline") was false against `DEFAULT_QUERY = SearchQuery(..., results_wanted=50)`. A module constant would also freeze the ban-risk envelope at import time and ignore an operator override, defeating `Settings`.
- **Commits were made on `master`.** The project's `git.branching_strategy` is `"none"`, every prior phase commit (01-01…01-04) is on `master`, and the executor prompt directed sequential commits on the main working tree. No protected ref was rewritten and no git config was changed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Hard-coded thresholds in `app/pipeline/run.py` falsified the config must-have**
- **Found during:** Task 2 (`tests/test_config.py`)
- **Issue:** `DEFAULT_QUERY = SearchQuery(keywords="software engineer", location="Ireland", results_wanted=50)` restated two values that `Settings` already owns (`probe_results_wanted`, and the country/location). Must-have #9 requires every limit/country/budget value to be read from `Settings` and forbids a threshold literal in `app/pipeline`; the `50` literal made the truth false before the fix.
- **Fix:** Replaced the module constant with `default_query()`, which reads `settings.probe_results_wanted` and a new `settings.probe_query_location`. Only the keyword string (a product string, not a limit) remains literal. `run_pipeline` now calls `default_query()` at request time rather than reading a frozen constant.
- **Files modified:** `app/pipeline/run.py`, `app/config.py`
- **Verification:** `tests/test_config.py::test_default_query_reads_its_location_and_count_from_settings`, `::test_build_budget_reads_every_ceiling_from_settings`, and `::test_no_distinctive_threshold_literal_remains_in_probe_or_pipeline` (verified non-vacuous by re-introducing `results_wanted=50`, which failed the test).
- **Committed in:** `7587f9a` (Task 2 commit)

**2. [Rule 2 - Missing Critical] `SanitizeResult` was not the plan's named contract type**
- **Found during:** Task 1 (sanitiser hardening)
- **Issue:** The plan's artifact list names `SanitisedText` and specifies a truncation contract ("Python characters — stated in the function docstring and pinned by a multi-byte test") that the code did not state and could not honour: `.rstrip()` after slicing returned fewer than `max_chars` characters.
- **Fix:** Renamed the result type to `SanitisedText` (aliasing `SanitizeResult`), removed the `.rstrip()`, and documented the character-not-byte contract in both docstrings.
- **Files modified:** `app/domain/sanitize.py`
- **Verification:** `tests/domain/test_sanitize_edge.py::test_truncation_keeps_exactly_the_limit_even_at_a_space` (fails against the old `.rstrip()`) and `::test_multibyte_text_truncates_by_characters_not_bytes`.
- **Committed in:** `33d4f61` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 2 — missing critical functionality)
**Impact on plan:** Both fixes were required to make the plan's own `must_haves` true rather than merely asserted; neither adds product surface beyond one Settings field. No architectural change, no new dependency, no scope creep.

## Issues Encountered

- **`gsd_run query git.base-branch --is-protected master` returns `true`.** The generic executor assertion would have halted, but the environment directive (sequential executor on the main working tree, normal commits with hooks) and the project's `git.branching_strategy: "none"` make `master` the intended branch — every prior phase commit is there. No protected ref was force-rewritten and `git update-ref` was never used. Documented as a decision above.
- **`ruff format --check` is not a project gate.** 34 pre-existing files would be reformatted (including `app/pipeline/run.py`, `app/domain/sanitize.py` and `tests/sources/test_indeed.py` at HEAD), so new code was left in the repo's existing style. `ruff check .` — the stated gate — is clean.
- **`state.add-decision` probe.** A probe decision was added while discovering the flag shape; it was removed from `STATE.md` before the real decisions were recorded.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None. No stub, placeholder, `TODO`/`FIXME`, empty-value-to-UI or unwired data source was introduced by this plan.

## Threat Flags

None. This plan adds no network endpoint, no auth path, no file-access pattern and no schema change. `app/config.py` gains one non-secret setting (`probe_query_location`); the `opencode_server_password` field is pre-existing and unchanged.

## Threat Register Coverage

| Threat ID | Disposition | Covered by |
|-----------|-------------|------------|
| T-01-23 (recruiter PII in a description or log line) | mitigate | `tests/domain/test_sanitize_pii.py` (removal, never-hashed, `capture_logs`/`caplog`/`capsys`) |
| T-01-24 (credential or session path in an adapter) | mitigate | `tests/test_no_credentials.py` |
| T-01-25 (XSS through listing text) | mitigate | Sanitise-side HTML reduction asserted here; render-side autoescape is plan 01-03's surface |
| T-01-26 (remote asset origin) | mitigate | `tests/test_no_cdn.py` |
| T-01-27 (a route added without the identity seam) | mitigate | `tests/test_auth_seam.py` |
| T-01-28 (a threshold hard-coded) | mitigate | `tests/test_config.py` (behavioural + literal-absence) |
| T-01-SC (package installs) | accept | No new dependency (`tech-stack.added: []`) |

## Next Phase Readiness

- **Ready for plan 01-06** (cached liveness probe, boot-tolerant `/health`, per-source health strip, opencode discovery redaction). `tests/test_config.py` already tolerates the absent `app/probe` directory and will begin scanning it automatically once the probe module lands — a new hard-coded ceiling there will fail the guard.
- **PLAT-04's REQUIREMENTS.md checkbox remains open by design.** It is declared by 01-01, 01-05, 01-06 and 01-07; the shared-ID gate blocks it until the last declaring plan has a SUMMARY. `SRC-06`, `SRC-08`, `SRC-10`, `PLAT-03` and `UI-07` were marked complete.
- **Phase 2's sanitise work is unblocked and scoped:** `_INJECTION_PATTERNS` extends `INSTRUCTION_MARKERS` in `app/domain/sanitize.py`; the flag, the stage and the "no adapter may sanitise" guard are already in place.
- **Full suite:** `.venv/bin/python -m pytest -q -x` → **178 passed**; `ruff check .` → clean.

## Self-Check: PASSED

- **Files verified on disk:** all 9 files created/modified by this plan exist (`app/domain/sanitize.py`, `app/ingest/sanitize.py`, `app/config.py`, `app/pipeline/run.py`, and the 7 new test modules).
- **Commits verified:** `33d4f61`, `7587f9a`, `3b9948b` all present in `git log`.
- **Task acceptance criteria:** both tasks' `acceptance_criteria` re-run and passing (82 plan-scoped tests; 178-test full suite; ruff clean).
- **Plan `<verification>`:** `python -m pytest -q tests/domain tests/test_no_credentials.py tests/test_no_cdn.py tests/test_auth_seam.py tests/test_config.py -x` → 82 passed; `python -m pytest -q -x` → 178 passed.
- **`must_haves` truths:** all 9 plain truths are assertion-backed (see the `coverage:` block); all 3 `backstop` truths are pinned by tests (`test_multibyte_text_truncates_by_characters_not_bytes`, `test_sanitising_the_same_input_twice_is_identical`, `test_content_hash_is_stable_across_pii_variants`). No `human_judgment: true` entry was needed.
