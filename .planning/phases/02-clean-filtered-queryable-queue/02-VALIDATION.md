---
phase: "2"
slug: "clean-filtered-queryable-queue"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: false
wave_0_complete: true
created: "2026-09-16"
audited: "2026-09-16"
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
>
> **Audited 2026-09-16** (post-execution Nyquist audit). The requirement statuses below
> were re-derived from the ACTUAL executable check in the test files, not from the
> plan-time promises. Four genuine gaps were found and filled with new tests; two
> residual gaps are named and justified. See `## Nyquist Audit 2026-09-16`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `addopts="-m 'not live'"`) |
| **Quick run command** | `.venv/bin/python -m pytest -q tests/domain tests/db tests/pipeline` |
| **Full suite command** | `.venv/bin/python -m pytest -q` |
| **Estimated runtime** | ~30 s (quick) / ~70 s (full, offline lanes only) |

> **Command correction (audit).** The plan-time commands named `.venv-host/bin/pytest`.
> That shim is **unrunnable** — its shebang points at the original build host
> (`#!/mnt/data/docker/apps/opencode/workspace/job-search/.venv-host/bin/python3.14`),
> so every documented "automated command" in this file previously failed with
> `No such file or directory`. Everything below uses the working interpreter.

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest -q tests/domain tests/db tests/pipeline`
- **After every plan wave:** Run `.venv/bin/python -m pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green, plus the schema gate
  `.venv/bin/python -m pytest -q tests/db/test_migration_contract.py tests/db/test_no_pii_columns.py`
- **Max feedback latency:** 120 seconds
- **Live/operator lane:** `.venv/bin/python -m pytest -q -m live` — never in CI (P13)

---

## Per-Requirement Verification Map (audited — actual checks)

> Requirement → the executable check that would fail if the behaviour regressed.
> All rows are green on 2026-09-16 (`601 passed, 2 deselected`).

| Requirement | Behavior verified | Actual check (file:line) | Status |
|-------------|-------------------|--------------------------|--------|
| QUEUE-03 | Cross-source merge writes one visible listing + one absorbed twin + one audit row | `tests/pipeline/test_dedup_merge.py:96`; `tests/db/test_dupes.py:154,216` | ✅ green |
| QUEUE-03 | Fuzzy gate: grade guard, company/location gate, threshold, posted window | `tests/domain/test_dedup.py:60,71,122,140,154,167` | ✅ green |
| QUEUE-04 | Revert restores snapshot, marks audit row, twin reappears, next run does not re-merge | `tests/pipeline/test_dedup_revert.py:158,250`; `tests/api/test_merges_view.py:285`; `tests/api/test_queue_search.py:256` | ✅ green |
| QUEUE-06 | Hostile query parses; order stable; no-query keeps Phase-1 order; query composes with hidden/excluded | `tests/domain/test_search_query.py:82,94`; `tests/api/test_queue_search.py:120,144,162,304`; `tests/api/test_queue_excluded.py:185` | ✅ green |
| QUEUE-07 | New-since-watermark, stale boundary, mark-seen, page-open advance only | `tests/api/test_queue_signals.py:109,163,217,244,267,289`; `tests/db/test_queue_state.py:32,61,96,109` | ✅ green |
| QUEUE-08 | save/unsave/hide/unhide append events; projection; UPDATE/DELETE abort | `tests/db/test_listing_events.py:127,148,168,353`; `tests/api/test_listing_events.py:95,150` | ✅ green |
| QUEUE-09 | Merge rate windowed to the latest run; rows reachable on the same page | `tests/api/test_merges_view.py:159,201` | ✅ green |
| CRIT-01 | Named search + rules CRUD; form-created rule is applied by the next run | `tests/api/test_searches_crud.py:52,123,255,275,299,335,359,409`; `tests/pipeline/test_criteria_form_to_run.py:93,128` | ✅ green |
| CRIT-02 | Snapshot carries the exact query/rules; later edits do not rewrite a past run; per-row `criteria_version` | `tests/pipeline/test_criteria_snapshot.py:118,155`; `tests/pipeline/test_filter_stage.py:203` | ✅ green |
| CRIT-03 | Enable/disable without delete and without bumping the version | `tests/api/test_searches_crud.py:255`; `tests/db/test_search_repo_writes.py:107` | ✅ green |
| FILT-01 | Deterministic reject before any LLM call; `LlmCall` count is 0 | `tests/domain/test_filter.py` (27); `tests/pipeline/test_filter_stage.py:146,316` | ✅ green |
| FILT-02 | One `listing_exclusions` row per firing rule with `rule_id`/`kind`/`detail_json`/`run_id`/version | `tests/db/test_exclusions.py:104,200,232,283`; `tests/pipeline/test_filter_stage.py:146` | ✅ green |
| FILT-03 | Excluded out of default view; `Show excluded` toggle + chip + per-rule count; search does not bypass | `tests/api/test_queue_excluded.py:162,185,211,233` | ✅ green |
| FILT-04 | Rule params read from DB, not code; no distinctive literal under `app/pipeline`; form drives the run | `tests/test_config.py:156,191`; `tests/domain/test_filter.py:357,368`; `tests/pipeline/test_criteria_form_to_run.py:93` | ✅ green |
| RUN-03 | Six-value reason by precedence + counts; pipeline persists them | `tests/domain/test_run_reason.py:125,139,146,159`; `tests/pipeline/test_filter_stage.py:344,366,409`; `tests/api/test_run_reason.py:141,179,204` | ✅ green |
| RUN-04 | `/runs` newest-first; detail stage log + counts; last-run strip; in-flight row | `tests/api/test_run_history.py:146,158,198,217,253`; `tests/api/test_run_reason.py:223,260` | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

All Wave-0 test files exist and are exercised by the full suite:

- [x] `tests/domain/test_search_query.py` — 8 hostile inputs + `None`/blank branch
- [x] `tests/domain/test_dedup.py` — seniority guard, component gate, subset pathology
- [x] `tests/domain/test_filter.py` — six kinds, unknown-value policy, malformed `params_json`
- [x] `tests/domain/test_run_reason.py` — every enum branch + precedence
- [x] `tests/domain/test_injection_patterns.py` — 8 patterns, flag-not-mutate
- [x] `tests/db/test_migration_contract.py` — items 9–13 + `test_upgrade_populated_0001_to_head:478`
- [x] `tests/db/test_no_pii_columns.py` — JSON-column allow-list
- [x] `tests/db/test_queue_state.py`, `test_exclusions.py`, `test_listing_events.py`, `test_dupes.py`
- [x] `tests/pipeline/test_dedup_merge.py`, `test_dedup_revert.py`, `test_filter_stage.py`, `test_criteria_snapshot.py`, `test_capability_surface.py`
- [x] `tests/api/` — search/signals/excluded/events/searches/run-history/reason/merges
- [x] `tests/test_config.py` — new settings fields + distinctive-literal scan (+ anti-vacuous proof `:191`)
- [x] `rapidfuzz==3.14.6` pin — machine-checked in `tests/test_dependency_pins.py:40,54`

*(No shared-fixture work is needed: `migrated_db`, `session_factory`, `db_session`, `client`,
`registry_snapshot` and the offline LLM stub already cover every lane.)*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions | Disposition |
|----------|-------------|------------|-------------------|-------------|
| Dedup threshold θ tuned against the first real corpus | QUEUE-03 | No real corpus exists pre-run; θ must be a setting with a recorded tuning procedure, not a frozen constant (STATE.md Phase-2 blocker) | Run a real pipeline run, inspect `listing_dupes` pairs + merge rate, record chosen θ and band in `docs/` | **Remains manual** (UAT #1) |
| Merge-rate band sanity check | QUEUE-09 | The 10–15% band in research comes from a different market/query shape | After a real run, compare observed merge rate against the recorded θ; adjust or record why not | **Remains manual** (UAT #2) |
| dependency-legitimacy human check for `rapidfuzz` | Tier-2 dedup | Package-legitimacy gate returned `SUS` (`too-new`, `unknown-downloads`) | Confirm the pin `rapidfuzz==3.14.6` and licence (MIT) before install | **Remains manual** (UAT #4). The *pin* is machine-checked (`tests/test_dependency_pins.py`); only the out-of-band approval cannot be |
| Compose smoke of the running stack | PLAT-01 carry-over | WINDOWS.md open item #1 — the compose smoke is still unrun | `docker compose up` and browse the queue; record the result | **Remains manual** (UAT #3) — needs Docker + a browser. Its *output contract* is machine-pinned (`tests/api/test_run_trigger.py:126`, `tests/pipeline/test_single_search_run.py:197`) |
| Excluded chip sufficiency | FILT-03 / SC2 | The chip names the firing rule **kind** + a per-rule count; `detail_json` and the rule id have no UI consumer | Under `Show excluded`, confirm the chip is sufficient or require the rule id + matched `detail_json` term | **Remains manual** (UAT #5) — product judgment, not machine-decidable |

*If a row above is discharged in-phase, record the evidence path in the plan's SUMMARY.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter — **held false**: four genuine
      automated gaps were closed, but the five Manual-Only items above remain
      unverifiable without a real corpus / Docker / a human judgment

**Approval:** validated (PARTIAL) — 2026-09-16

---

## Nyquist Audit 2026-09-16

### Method

Read all ten PLAN `must_haves` (54 truths) and the ten SUMMARYs; then read the actual
test files and mapped each requirement to the executable check that would fail on a
regression — not to the plan's promised file. Ran the cited lanes and the full suite.
Applied the two known defect patterns from this cycle as a lens: *fresh-path-tested,
populated/upgrade-path-untested* (`tests/db/test_migration_contract.py:478`) and
*assertion-string-tested, real-consumer-untested* (`tests/test_stylesheet_coverage.py`).

### Per-requirement verdict (15/15)

| Requirement | Verdict | Proof / reasoning |
|-------------|---------|-------------------|
| QUEUE-03 | **Fully covered** | `tests/pipeline/test_dedup_merge.py:96` (asserts 2 listings, 1 dupe, salary fill, `deduped_count==1`); gate matrix in `tests/domain/test_dedup.py` |
| QUEUE-04 | **Fully covered** | `tests/pipeline/test_dedup_revert.py:158` (revert durable across a third run) + `tests/api/test_queue_search.py:256` (twin reappears, machine-decided) |
| QUEUE-06 | **Covered + gap filled** | Hostile-input anti-vacuous pair `tests/domain/test_search_query.py:82,94`; order `tests/api/test_queue_search.py:144`. **Gap:** search×hidden composition was untested → `test_a_search_does_not_surface_a_hidden_listing` (`tests/api/test_queue_search.py:304`) |
| QUEUE-07 | **Fully covered** | `tests/api/test_queue_signals.py:109,163,217,244,267,289`; watermark singleton in `tests/db/test_queue_state.py:109` |
| QUEUE-08 | **Covered + gap filled** | Append-only enforcement at DB and ORM `tests/db/test_listing_events.py:148,168`; projection `:353`. **Gap:** search×hidden (see QUEUE-06) and search×excluded were untested |
| QUEUE-09 | **Fully covered** | `tests/api/test_merges_view.py:201` — the 2-run regression (33%, not 67%) is exactly the real-world windowing path |
| CRIT-01 | **Covered + gap filled** | 19 CRUD tests in `tests/api/test_searches_crud.py`. **Gap:** no test drove a run from a form-created search/rule → `tests/pipeline/test_criteria_form_to_run.py:93,128` |
| CRIT-02 | **Fully covered** | `tests/pipeline/test_criteria_snapshot.py:155` (edit after run leaves the snapshot); per-owning-search version `tests/pipeline/test_filter_stage.py:203` |
| CRIT-03 | **Fully covered** | `tests/api/test_searches_crud.py:255` + `tests/db/test_search_repo_writes.py:107` prove toggle with no version churn |
| FILT-01 | **Fully covered** | `tests/pipeline/test_filter_stage.py:146` asserts `LlmCall == 0` — the no-LLM claim is executable, not prose |
| FILT-02 | **Fully covered** | `tests/db/test_exclusions.py:104,232,283` (verbatim detail, append-per-run, no prose) |
| FILT-03 | **Covered (with advisory)** | `tests/api/test_queue_excluded.py:162,185,211,233`. Advisory that the chip omits rule id / `detail_json` is a UI-sufficiency judgment → Manual-Only (UAT #5) |
| FILT-04 | **Covered + gap filled** | Static scan `tests/test_config.py:156` with anti-vacuous proof `:191`; malformed-params skip `tests/domain/test_filter.py:357,368`. **Gap:** the form→evaluator seam for kinds other than `exclude_keyword` was untested → `tests/pipeline/test_criteria_form_to_run.py:93` |
| RUN-03 | **Fully covered** | Full precedence matrix `tests/domain/test_run_reason.py:125–159`; pipeline persistence `tests/pipeline/test_filter_stage.py:344,366,409` |
| RUN-04 | **Covered** | `tests/api/test_run_history.py:146–253`. Truth 5 (read-only surface) is proven structurally (`app/api/runs.py` exposes only `GET /runs*`) plus body determinism `:185`; no route-mutation probe exists — acceptable, see residual R2 |

### Gaps found and resolved

| # | Requirement(s) | Gap (why the existing check was insufficient) | Resolution |
|---|----------------|-----------------------------------------------|------------|
| G1 | CRIT-01, FILT-01, FILT-04 | The CRUD lane pinned only `exclude_keyword`'s stored `params_json`; the stage lane seeded params by hand. No test crossed the seam, so a rename in `rule_params_from_form` for `remote`/`salary_floor`/`location`/`seniority`/`company_blocklist`, or a `criteria_from_form` key the assembler ignores, would keep both lanes green while the user's rule silently stopped firing | **FILLED** — `tests/pipeline/test_criteria_form_to_run.py:93` (POST a `remote` rule, run the pipeline, assert the exclusion) and `:128` (POST full criteria, assert the adapter receives `keywords`/`location`/`remote_only`/`salary_floor`/`seniority`) |
| G2 | QUEUE-06 × QUEUE-07/QUEUE-08 | Every search test used the default predicate set; every hidden/excluded test used no query. The FTS branch shares `predicates` with the no-query branch today (`queue_repo.read_queue:303-345`), but an edit that dropped `*predicates` from the `MATCH` statement would resurface hidden/rejected listings the moment the user typed — and nothing would fail | **FILLED** — `tests/api/test_queue_search.py:304` (hidden) and `tests/api/test_queue_excluded.py:185` (excluded; toggle is the only way back) |

### Residual gaps (named, justified SKIP)

| # | Requirement | Gap | Why SKIP |
|---|-------------|-----|----------|
| R1 | 02-01 truth 1 (schema coherence) | No test drives `alembic downgrade 0001` → `upgrade head` (empty **or** populated). The migration authors a `downgrade()`; the Phase-1 `listing_events` triggers and `listing_fts` are asserted on the upgrade path only | **Explicitly justified.** `0001` is the one-way door; downgrade exists only for Alembic tooling coherence. Manually probed on 2026-09-16: both empty and populated DBs complete `head → 0001 → head` with row counts preserved (`listings=1, runs=1, listing_exclusions=1, listing_dupes=1`). A real check would be a populated round-trip test in `tests/db/test_migration_contract.py`; recommend adding it if downgrade ever becomes user-facing |
| R2 | 02-10 truth 5 | "No route mutates a run" is proven by `app/api/runs.py` exposing only `GET` for the history paths plus body determinism (`tests/api/test_run_history.py:185`); there is no route-method inventory assertion | **Explicitly justified.** The guarantee is currently structural and the module's only POSTs (`/runs`, `/merges/{id}/revert`) mutate a run's creation and a dupe row respectively, not history. A regression here would require adding a new mutating history route, which is a feature decision, not a silent behaviour drift |

### Tests added (for commit)

- `tests/pipeline/test_criteria_form_to_run.py` — 2 tests (G1)
- `tests/api/test_queue_search.py` — `test_a_search_does_not_surface_a_hidden_listing` (G2)
- `tests/api/test_queue_excluded.py` — `test_a_search_does_not_surface_an_excluded_listing_unless_the_toggle_is_on` (G2)

No existing assertion was weakened or deleted. `ruff check app tests` → **All checks passed!**

### Audit metrics

| Metric | Count |
|--------|-------|
| Requirements audited | 15 |
| Must-have truths re-derived | 54 |
| Genuine gaps found | 2 |
| Gaps resolved (tests added) | 2 |
| Gaps escalated (BLOCKER) | 0 |
| Residual gaps (justified SKIP) | 2 |
| Manual-Only carried forward | 5 |
| Full suite after additions | **601 passed, 2 deselected** (was 597) |
