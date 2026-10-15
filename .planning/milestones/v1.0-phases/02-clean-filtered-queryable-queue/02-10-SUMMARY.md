---
phase: 02-clean-filtered-queryable-queue
plan: "10"
subsystem: ui
tags: [run-history, reason, stage-log, htmx, jinja2, observability]

# Dependency graph
requires:
  - phase: 02-clean-filtered-queryable-queue
    provides: "plan 02-05's `runs.reason` / `reason_counts_json` / `stage_log_json` (written on every run), the pure `app.domain.run_reason` layer and the stage-log caps"
  - phase: 02-clean-filtered-queryable-queue
    provides: "plan 02-07's thin `queue()` handler, the `#run-control` block and `#run-status-slot`"
  - phase: 01-walking-skeleton
    provides: "`POST /runs` with its status fragment, `GET /runs/{id}/status` with the HTTP-286 polling stop, and `_run_status.html`"
provides:
  - "`app/db/repositories/run_repo.py` — `RunSummary`, `RunDetail`, `list_runs`, `get_run_detail` plus the derived-sentence helpers"
  - "`GET /runs` — the run-history page, and `GET /runs/{run_id}` — the expansion fragment"
  - "`app/web/templates/html/runs.html` — the history page, with the list and the detail as two macros"
  - "the queue's last-run strip, rendered through the existing `render_run_fragment`"
affects: []

# Actuals (#2632) — measured, not narrated.
actuals:
  tokens: 12344        # chars/4 of `git diff a043d37..HEAD` => 49376/4
  tasks: 2
  commits: 2           # MEASURED: git rev-list --count a043d37..HEAD

tech-stack:
  added: []            # no new dependency — HTMX, Jinja and markupsafe already shipped
  patterns:
    - "Render what was persisted: the status is carried verbatim, the reason is the stored enum value, and the counts are that run's own decomposition — only the sentence is derived, and it is derived from those counts"
    - "One renderer, two surfaces: a structural Protocol lets the same run partial serve the run control's polling fragment and the queue's last-run strip"
    - "Escaping decided in Python, not in the template: a pre-rendered fragment is wrapped in `Markup` so no safe-marking filter appears anywhere in a template"
    - "Defence in depth on a bounded blob: the stage log is capped at write time and capped again at read time, so an old or hand-edited row cannot blow up the page"

key-files:
  created:
    - app/db/repositories/run_repo.py
    - app/web/templates/html/runs.html
    - tests/api/test_run_history.py
    - tests/api/test_run_reason.py
  modified:
    - app/api/runs.py
    - app/web/routes.py
    - app/web/templates/html/queue.html

key-decisions:
  - "The history page never recomputes an outcome. `runs.status` is rendered verbatim (so Phase 1's rule that `done` means it actually ran survives), the reason is the persisted enum value, and the counts are the persisted decomposition. The ONLY derived value is the human sentence, computed with the pure `reason_sentence` from those counts — never stored, so a historical run's sentence cannot drift from its own numbers (Pattern 4)."
  - "`RunCounts` is rebuilt from `reason_counts_json` plus `runs.fetched_count` (which `_finish` writes as exactly the sum of the per-source counts), so the sentence cannot cite a number the run never recorded. A test asserts the sentence's figure equals the persisted integer for `all_filtered`."
  - "`duration_seconds` is `None` when the run has not finished, never `0.0` — an in-flight run must not read as 'finished instantly'."
  - "Every nullable JSON column (`source_counts_json`, `errors_json`, `reason_counts_json`, `stage_log_json`, `criteria_snapshot_json`) defaults to an empty mapping/list, so a run that died mid-flight renders instead of 500-ing the page."
  - "The stage log is bounded AGAIN on read (`STAGE_LOG_RENDER_LIMIT` / `STAGE_LOG_ERROR_LIMIT`) even though the writer already capped it: a separate constant means the read model need not import the pipeline, and an old or hand-edited row is exactly the case this guards."
  - "`RunSummary.errors_json` is exposed under the COLUMN's name so the existing `_run_status.html` reads it unchanged — that is what lets one run renderer serve both the history page and the queue strip with no shim object."
  - "`render_run_fragment` is annotated with a structural `RunFragmentSource` Protocol, because it now legitimately serves both the ORM `Run` row and the frozen `RunSummary`. One renderer, two callers, no second template (D-43)."
  - "The strip's fragment is wrapped in `Markup` in Python rather than marked safe in the template. The escaping decision belongs where the renderer made it, and it keeps every template free of a safe-marking filter — so the rule holds without an exception."
  - "The strip's reason value, derived sentence and `/runs` link sit OUTSIDE the fragment root, so the strip's own 286 poll can swap the status block without dropping the explanation. The strip is a sibling of `#run-control`, never its parent, so the polling fragment keeps its `#run-status-slot` target."
  - "The history surface is GET-only and the latest-run read is wrapped in a never-raise guard: a decorative strip that fails yields no strip and a 200, never a broken product page."

patterns-established:
  - "Observability surfaces read the persisted decomposition and derive only the human-facing aggregate, so a past row is always explained by its own numbers."
  - "A single renderer shared across surfaces via a structural Protocol, instead of a shim object or a duplicated partial."

requirements-completed: [RUN-03, RUN-04]

coverage:
  - id: D1
    description: "`GET /runs` lists one row per run, newest first, carrying the trigger, started and finished times, the duration, the per-source fetched counts, `deduped_count`, `filtered_count` and any errors, with a stable per-row id and an explicit empty state."
    requirement: RUN-04
    verification:
      - kind: integration
        ref: "tests/api/test_run_history.py#test_a_run_renders_its_persisted_status_counters_and_reason"
        status: pass
      - kind: integration
        ref: "tests/api/test_run_history.py#test_a_fresh_database_shows_the_empty_state"
        status: pass
      - kind: integration
        ref: "tests/api/test_run_history.py#test_runs_render_newest_first_and_stably"
        status: pass
    human_judgment: false
  - id: D2
    description: "Each run shows the persisted reason and a sentence DERIVED from the persisted counts, and the expansion reveals the reason counts, the per-rule excluded counts, the criteria snapshot's search names and versions, and the bounded raw stage log inside a collapsed `<details>`."
    requirement: RUN-03
    verification:
      - kind: integration
        ref: "tests/api/test_run_history.py#test_the_detail_fragment_carries_the_stage_log_and_the_per_rule_counts"
        status: pass
      - kind: integration
        ref: "tests/api/test_run_history.py#test_a_run_renders_its_persisted_status_counters_and_reason"
        status: pass
    human_judgment: false
  - id: D3
    description: "A run that has not finished renders in-flight with an em dash and never `0s`, so it cannot read as a completed run with an empty duration."
    requirement: RUN-04
    verification:
      - kind: integration
        ref: "tests/api/test_run_history.py#test_an_unfinished_run_renders_in_flight_with_an_em_dash"
        status: pass
      - kind: unit
        ref: "tests/api/test_run_history.py#test_a_half_written_run_still_renders"
        status: pass
    human_judgment: false
  - id: D4
    description: "A partial or failed run is never presented as a clean success: `runs.status` is rendered verbatim and never re-derived."
    requirement: RUN-04
    verification:
      - kind: integration
        ref: "tests/api/test_run_history.py#test_a_half_written_run_still_renders"
        status: pass
    human_judgment: false
  - id: D5
    description: "The surface is read-only and deterministic: two identical `GET /runs` requests return identical bodies, no new mutating route exists, and the routes are bounded by an explicit limit with a newest-first id tie-break."
    requirement: RUN-04
    verification:
      - kind: integration
        ref: "tests/api/test_run_history.py#test_two_identical_requests_return_identical_bodies"
        status: pass
      - kind: integration
        ref: "tests/api/test_run_history.py#test_runs_render_newest_first_and_stably"
        status: pass
    human_judgment: false
  - id: D6
    description: "The queue carries a compact last-run strip rendered through the existing `render_run_fragment` (no second copy of the run markup), linking to `/runs`, and absent when no run exists."
    requirement: RUN-04
    verification:
      - kind: integration
        ref: "tests/api/test_run_reason.py#test_the_strip_links_to_the_run_history"
        status: pass
      - kind: integration
        ref: "tests/api/test_run_reason.py#test_the_strip_is_absent_when_no_run_exists"
        status: pass
    human_judgment: false
  - id: D7
    description: "An empty queue explains itself in place: `all_filtered` renders with a sentence whose number EQUALS the persisted `reason_counts_json` count, `nothing_new` says nothing is new, and `no_sources_enabled` renders alongside the pre-existing Phase-1 degraded message."
    requirement: RUN-03
    verification:
      - kind: integration
        ref: "tests/api/test_run_reason.py#test_an_all_filtered_run_explains_the_empty_queue_with_persisted_numbers"
        status: pass
      - kind: integration
        ref: "tests/api/test_run_reason.py#test_a_nothing_new_run_says_so"
        status: pass
      - kind: integration
        ref: "tests/api/test_run_reason.py#test_a_no_sources_run_keeps_the_phase_one_degraded_message"
        status: pass
    human_judgment: false
  - id: D8
    description: "Board-derived error strings are escaped on both the history page and the expansion fragment, and no template uses a safe-marking filter or a remote asset."
    verification:
      - kind: integration
        ref: "tests/api/test_run_history.py#test_the_page_escapes_a_board_derived_error_string"
        status: pass
      - kind: unit
        ref: "tests/test_no_cdn.py"
        status: pass
    human_judgment: false
  - id: D9
    description: "No Phase-1 contract regressed: `POST /runs` still returns the run id the compose smoke regexes, the 286 polling stop still works, and the pinned queue-page assertions (`hx-post=\"/runs\"`, `id=\"run-status-slot\"`, `0 listings`, `No listings yet`) survive the strip."
    verification:
      - kind: integration
        ref: "tests/api/test_run_trigger.py"
        status: pass
      - kind: integration
        ref: "tests/api/test_run_reason.py#test_the_pinned_phase_one_queue_contract_survives_the_strip"
        status: pass
      - kind: unit
        ref: "tests/test_auth_seam.py"
        status: pass
    human_judgment: false

# Metrics
duration: 17min
completed: 2026-09-16
status: complete
---

# Phase 02 Plan 10: Run history — one row per run, and an answer for an empty queue

**A `/runs` page that renders what each run persisted — status verbatim, counters, the stored reason with a sentence derived from that run's own counts, and the bounded stage log behind a collapsed `<details>` — plus a last-run strip on the queue that explains an empty queue in place.**

## Performance

- **Duration:** 17 min
- **Started:** 2026-09-16T12:14:25Z
- **Completed:** 2026-09-16T12:30:41Z
- **Tasks:** 2
- **Files modified:** 7 (`git diff --numstat a043d37..HEAD`: 7 files, +1226 / −3)

## Accomplishments

- **The history surface renders, and never recomputes.** `runs.status` is carried verbatim so Phase 1's rule ("`done` only when it actually ran, every board was healthy and every item persisted") survives; the reason is the value plan 02-05 stored; the counters are that run's own numbers. The one derived value is the human sentence, computed through the pure `reason_sentence` from the persisted counts — so a historical run is always explained by its own row and a changed count changes the sentence with no migration (Pattern 4).
- **The page cannot invent a number.** `RunCounts` is rebuilt from `reason_counts_json` plus `runs.fetched_count`, and the `all_filtered` test asserts the figure printed in the sentence equals the integer in the persisted `excluded_by_rule` map. An empty queue is therefore explained unambiguously rather than mysteriously — the exact failure `PITFALLS.md` P9 names.
- **The expansion is one round trip and stays collapsed.** `GET /runs/{run_id}` returns the detail fragment for an `hx-get`, carrying the reason counts, the per-rule excluded counts, the criteria snapshot's search names and versions, and the raw stage log inside a `<details>`.
- **A half-written or unfinished run still renders.** Every nullable JSON column defaults to an empty mapping/list, and a `running` run shows an em dash rather than `0s` — "in flight" must not read as "finished instantly".
- **One run renderer, two surfaces.** The queue's last-run strip is produced by `render_run_fragment`, the same function and the same `_run_status.html` the run control's polling fragment uses, so there is no parallel partial to drift (D-43) — and the strip's failure mode is `(None, None)`, so a decorative read can never 500 the product page.
- **The stage log is bounded twice.** Plan 02-05 caps it at write time; the read model caps it again, so an old or hand-edited row cannot blow up the page.
- **Nothing Phase 1 pinned regressed.** The compose-smoke run-id contract, the 286 polling stop, `hx-post="/runs"`, `id="run-status-slot"`, `0 listings` and the auth seam are all green.

## Task Commits

Each task was committed atomically:

1. **Task 1 (tracer): `/runs` renders a real run's reason, counts and stage log** - `2bfe005` (feat)
2. **Task 2: the last-run strip on the queue, rendered by the existing run renderer** - `52191f2` (feat)

**Plan metadata:** _committed with STATE/ROADMAP/REQUIREMENTS after this file_

_Note: `commits: 2` and `plan_head_before: a043d37405a78599880e23adc7eb603a34756426` are measured from the on-disk per-plan ledger at `.git/gsd-plan-head-before-02-10`, not narrated (#3968)._

## Files Created/Modified

- `app/db/repositories/run_repo.py` — `RunSummary`/`RunDetail`, `list_runs` (`(started_at DESC, id DESC)`, explicit `limit`), `get_run_detail`, and the `run_counts_for`/`sentence_for` helpers that rebuild the pure counts from the persisted JSON.
- `app/api/runs.py` — `GET /runs` and `GET /runs/{run_id}`, both behind the auth seam; `render_run_detail` renders the detail macro; `render_run_fragment` gained a structural `RunFragmentSource` Protocol so it serves both the ORM row and `RunSummary`.
- `app/web/templates/html/runs.html` — the list and the detail as two macros, with the status rendered verbatim, an em dash for a NULL duration, the reason value plus the derived sentence, and the stage log in a collapsed `<details>`.
- `app/web/routes.py` — the latest-run read for the strip inside a never-raise guard, and the pre-rendered fragment wrapped in `Markup`.
- `app/web/templates/html/queue.html` — the `#last-run` strip: a sibling of `#run-control`, carrying the one renderer's output plus the reason value, the derived sentence and the `/runs` link.
- `tests/api/test_run_history.py` (10 cases) and `tests/api/test_run_reason.py` (6 cases) — the two lanes.

## Decisions Made

- **The sentence is the only derived value, and it derives from the persisted counts.** Nothing else on either surface is computed: the page renders what the run wrote, so an outcome is never re-derived and a past run's explanation cannot drift.
- **`duration_seconds` is `None`, not `0.0`, for an unfinished run.** The template renders an em dash, which is the difference between "still running" and "finished instantly".
- **The stage log is capped on read as well as on write.** The read model keeps its own constant rather than importing the pipeline, because the case it guards (a row from an older build, or a hand-edited one) is exactly a row the pipeline's cap did not produce.
- **`RunSummary.errors_json` mirrors the column name.** That is what lets the existing `_run_status.html` render the strip unchanged — one renderer, no shim object, no second partial (D-43).
- **The strip's explanation sits outside the fragment root.** The strip's own 286 poll swaps `#run-status`, so the reason value, the sentence and the `/runs` link must be siblings of it or they would vanish on the first swap.
- **Escaping is decided in Python.** A pre-rendered fragment must not be escaped by the template that interpolates it, and the project forbids a safe-marking filter, so `_last_run_strip` wraps the fragment in `Markup` — the escaping decision stays where the renderer made it.

## Deviations from Plan

_None of the plan's declared requirements were dropped or weakened; the four notes below record necessary implementation choices._

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `render_run_fragment` needed a structural annotation to serve both callers**
- **Found during:** Task 2 (the strip)
- **Issue:** The plan requires the strip to reuse `render_run_fragment` (one renderer) *and* requires the history read model to be a frozen dataclass (no ORM row reaching a template). The function was annotated `run: Run`, so passing a `RunSummary` was a type error — a shim object or a second renderer were the only alternatives those two constraints left.
- **Fix:** a `RunFragmentSource` Protocol declaring only what `_run_status.html` reads (`id`, `status`, `errors_json`), with `source_counts` widened to `Mapping`. Both the ORM row and `RunSummary` satisfy it structurally, so the renderer is genuinely shared and no shim was introduced.
- **Files modified:** `app/api/runs.py`
- **Verification:** `tests/api/test_run_reason.py` and `tests/api/test_run_history.py` both pass against the same template.
- **Committed in:** `52191f2` (part of task 2)

**2. [Rule 3 - Blocking] The pre-rendered strip fragment was escaped into visible text**
- **Found during:** Task 2 (the strip), by a failing test
- **Issue:** `{{ last_run_fragment }}` rendered the whole `_run_status.html` fragment as escaped text — the queue page showed `<div id=&#34;run-status&#34;…` instead of a status badge. The obvious fix is a safe-marking filter, which this plan and project forbid in templates.
- **Fix:** `_last_run_strip` returns `Markup(render_run_fragment(...))`. Jinja honours `__html__`, so the fragment renders as markup while every template stays free of a safe-marking filter. The type annotation was updated to match.
- **Files modified:** `app/web/routes.py`
- **Verification:** `tests/api/test_run_reason.py#test_the_strip_links_to_the_run_history` asserts the strip carries `id="run-status"`, and `test_a_no_sources_run_keeps_the_phase_one_degraded_message` asserts the Phase-1 degraded paragraph renders inside it.
- **Committed in:** `52191f2` (part of task 2)

### Deviations of record (no code change)

**3. `_run_status.html` was deliberately NOT modified**
- **Found during:** Task 2 (the strip)
- **Issue:** The strip must carry the reason value and a link to `/runs`. The natural home for the reason is inside the run partial, but `_run_status.html` is not in this plan's `files_modified`, and putting the link there would put queue-specific navigation into a reusable partial. The plan's own framing also says the strip *carries* the link, not the partial.
- **Fix:** the reason value, the derived sentence and the `/runs` link live in `queue.html`, as siblings of the fragment root. `_run_status.html` is untouched, so the run control's polling fragment, `POST /runs` and the compose-smoke contract are all bit-for-bit unchanged.
- **Verification:** `tests/api/test_run_trigger.py` (4 passed) and `tests/api/test_run_reason.py` (6 passed).
- **Committed in:** `52191f2`

**4. [Environment] Every plan `<verify>` / `<verification>` command was run as `.venv/bin/python -m pytest …` instead of `.venv-host/bin/pytest …`**
- **Found during:** both tasks (plan-level verification)
- **Issue:** `.venv-host/bin/pytest` is unusable in this sandbox — its shebang is a build-time absolute path that does not exist here, and its compiled wheels are `x86_64-linux-gnu` while the interpreter expects a musl `EXT_SUFFIX`, so `import pydantic_core` fails.
- **Fix:** none — the sibling `.venv/` (same Python 3.14.7, same package versions) was used; every asserted command has an exact equivalent.
- **Verification:** the full suite is green under `.venv`.
- **Recorded in:** `.planning/phases/02-clean-filtered-queryable-queue/deferred-items.md` (from plan 02-01) and repeated here for this plan.

---

**Total deviations:** 2 auto-fixed (both Rule 3 - blocking), 1 deliberate non-edit and 1 environment substitution of record.
**Impact on plan:** No scope creep. Every file touched is on the plan's declared surface, and no contract the earlier plans pinned was modified.

## Issues Encountered

- **`selectattr` on a dict works, but the rendering did not — the bug was escaping, not the selector.** The failing assertion (`id="run-degraded"` absent) pointed at `_run_status.html`'s no-sources branch; isolating the template with a fake object proved the branch was fine, and the real cause was the double-escaping described above. Worth recording because the symptom and the cause were in different files.
- **`ruff` F401/E501/I001** on the two new modules and one import-ordering complaint after adding `markupsafe` — all cleared. `ruff check app tests` reports **All checks passed!**
- No stubs, no skipped tests, and no unrun `<verify>` blocks: no new entries were added to `.planning/WINDOWS.md`.
- The untracked `.gsd/` and `.planning/milestone.lock` paths pre-date this plan and are outside its scope; they were left untouched.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **This is the final plan of phase 02.** All ten plans are summarised; `STATE.md` now reads Plan 10 of 10, so the phase is ready for `/gsd-verify-work` and then `/gsd-complete-milestone` or the next phase.
- **Carry-forward for the verifier:** `deduped_count`, `filtered_count`, `fetched_count`, the reason/counts/stage-log WRITE path, the queue's search/signal/exclusion semantics and the event log are all unchanged. This plan added read surfaces only; the sole edit to an existing module beyond additive routes is the `render_run_fragment` annotation, which is not observable at runtime.
- **Known residual risk (accepted, from the plan):** the history page has no retention policy, so `runs` grows once per manual trigger. Pruning is recorded as a Phase-8 operations item rather than built here, because losing the pipeline's history while it is still being trusted would be the wrong trade.

---
*Phase: 02-clean-filtered-queryable-queue*
*Completed: 2026-09-16*

## Self-Check: PASSED

- All 7 created/modified artifacts and `02-10-SUMMARY.md` verified present on disk.
- Both plan commits verified in `git log --all`: `2bfe005`, `52191f2`.
- Full suite green: `584 passed, 2 deselected`.
- No missing items.
