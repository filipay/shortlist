---
status: diagnosed
trigger: "queue remains unranked, i don't know why ... i have no indication if the ranking is running so i cannot tell"
created: 2026-09-23T09:08:00Z
updated: 2026-09-23T09:08:00Z
gap_id: G-05-1
phase: 05-ranking-core-value
truth: "The queue ranking strip and the job detail page distinguish ranking-in-progress from ranking-skipped, and name the skip reason when the pass did not run."
mode: find_root_cause_only
audit_acknowledged:
  milestone: v1.0
  at: 2026-10-15
  status: diagnosed
---

## Current Focus

<!-- OVERWRITE on each update - reflects NOW -->

hypothesis: "CONFIRMED — the ranking pass's outcome is never persisted on the run. `_finish` is the sole writer of the three free-form JSON columns and writes them independently of the detached ranking task; all three skip paths return before `run_ranking`'s one write (`ranked_count`), so `runs.ranked_count` stays NULL and the queue strip — gated on `ranked_count is not None` — renders nothing. Running and skipped are therefore visually identical, and no reason is recorded anywhere a UI can read."
test: "Read rank.py/run.py/routes.py/run_repo.py/templates end-to-end; grep every writer of the JSON columns and ranked_count; map the asyncio ordering between start_ranking_task and _finish."
expecting: "Exactly one writer per column (`_finish`), NULL conflates running/skipped/crashed/not-attempted, no reason persisted."
next_action: "Diagnosis complete; hand fix surface to the planning/executing agent. No code modified."

## Symptoms

<!-- Written during gathering, then IMMUTABLE -->

expected: "When ranking does not run, the queue ranking strip says ranking is skipped and names why; while it is running the strip says so; the job detail page says the same. The user can tell 'still running' from 'skipped' from 'ranked'."
actual: "Queue shows 3 listings, every row's Signals cell renders `not ranked`. No ranking strip renders at all. The detail page says 'Not yet ranked. This listing has no score yet — ranking may still be running, or the pass was skipped. Refresh once it finishes.' The only durable trace of the skip is a structlog line (`pipeline.rank_skipped error=CvFactStoreError reason=fact_store_absent run_id=2`)."
errors: "Container log: `2026-09-23 08:34:55 [info] pipeline.rank_skipped  error=CvFactStoreError reason=fact_store_absent run_id=2` followed by `pipeline.finished ... run_id=2 status=done trigger=manual`. No HTTP error, no run failure."
reproduction: "Run the pipeline with `settings.cv_dir` containing no readable `cv.yaml` (the user's compose stack: no CV mounted). `run_pipeline` completes `status=done`, `runs.ranked_count` stays NULL, zero `scores` rows, zero `llm_calls` rows. Load `/`."
started: "Always — the skip paths have existed since Phase 5 (D-88/D-94). There has never been a persisted ranking-outcome marker."

## Eliminated

<!-- APPEND only - prevents re-investigating -->

- hypothesis: "The ranking task crashed mid-pass and lost its result."
  evidence: "`run_ranking`'s disabled and fact-store-absent paths are synchronous returns with no exception (rank.py:373-387). The user's log shows a clean `pipeline.rank_skipped` + `pipeline.finished ... status=done`, not a traceback. And the question is observability, not a crash."
  timestamp: 2026-09-23T09:08:00Z

- hypothesis: "The strip is missing because `_ranking_strip` raised and returned `{}`."
  evidence: "`_ranking_strip` returns `{}` only on exception; the reproducible case is `latest_run.ranked_count is None`, which builds a non-empty dict `{'ranked': None, ...}`. The template's own gate `{% if ranking_strip.get('ranked') is not none %}` (queue.html:139) is what suppresses it. `_ranking_strip` is a red herring for the *absence*; it is a real target for the *fix*."
  timestamp: 2026-09-23T09:08:00Z

- hypothesis: "`runs.status` can distinguish a ranking skip (e.g. `partial`)."
  evidence: "D-88 detaches ranking; `_finish` writes `status='done'` unconditionally for a healthy ingest (run.py:850-854, 942-953) and never consults ranking. The user's log confirms `status=done`. `Run.in_flight` is `finished_at is None`, false while the detached task runs."
  timestamp: 2026-09-23T09:08:00Z

- hypothesis: "A fourth `runs.reason` enum value already records a ranking skip."
  evidence: "`ck_runs_reason` permits only `no_sources_enabled|all_sources_failed|zero_fetched|all_filtered|nothing_new|mixed` (models.py:343-347); the value is computed by `compute_empty_reason` from ingest counts before ranking. No ranking reason exists."
  timestamp: 2026-09-23T09:08:00Z

- hypothesis: "`ranked_count = 0` is the skip state."
  evidence: "`ranked_count` is written only at rank.py:487, reached only after the scoring loop; every skip path returns before it. A skip leaves NULL, never 0. `0` means 'the pass completed and wrote zero Score rows' (all calls failed/refused)."
  timestamp: 2026-09-23T09:08:00Z

## Evidence

<!-- APPEND only - facts discovered -->

- timestamp: 2026-09-23T09:08:00Z
  checked: "Every writer of `runs.errors_json`, `runs.reason_counts_json`, `runs.stage_log_json`."
  found: "`app/pipeline/run.py::_finish` is the ONLY writer in `app/`: `run.errors_json = errors or None` (:591), `run.stage_log_json = stage_log or None` (:610), `run.reason_counts_json = reason_counts or None` (:616). Verified by `\\.(errors_json|reason_counts_json|stage_log_json)\\s*=` across `app/` — 3 hits, all in `_finish`. (Only `ranked_count` has another app writer: rank.py:487.)"
  implication: "Any ranking marker written by the detached `run_ranking` BEFORE `_finish` is overwritten wholesale (`or None`). `_finish` must be the writer, or the marker needs a column `_finish` does not touch."

- timestamp: 2026-09-23T09:08:00Z
  checked: "All three ranking skip paths and their control flow."
  found: "`ranking_in_flight` is decided in `start_ranking_task` (rank.py:524-526) BEFORE any task is created, and is the only reason decided outside `run_ranking`. `ranking_disabled` (rank.py:373-375) and `fact_store_absent` (rank.py:377-387) are decided inside `run_ranking`, synchronously, before its first DB access. `run_pipeline` invokes `start_ranking_task` at run.py:905, then awaits `_assemble_run_reason` (:934) and `_finish` (:942)."
  implication: "A reason is knowable before `_finish` for `ranking_in_flight` and (via a synchronous precheck) for disabled/absent. The detached task cannot deterministically persist into `_finish`'s columns."

- timestamp: 2026-09-23T09:08:00Z
  checked: "asyncio ordering between task creation and `_finish` (race check)."
  found: "`asyncio.create_task` (rank.py:529) schedules; `run_pipeline` then yields at `_assemble_run_reason`'s `async with session_factory()` (`__aenter__`). The disabled/absent skip paths contain NO `await` today, so they currently finish in one loop step. Adding a DB write (which must await) interleaves non-deterministically with `_finish`. The repo's own `05-06-PLAN.md` documents the same ordering: 'run_pipeline starts the detached ranking task BEFORE `_finish` and keeps awaiting, so the skip log can be emitted before `_run_with_one_listing` returns — capturing only the drain would be racy.' (test_rank_optional.py:135-137 repeats it.)"
  implication: "Persisting from the detached task into `reason_counts_json`/`stage_log_json`/`errors_json` is racy and can be silently clobbered. Deterministic fix = precompute in `run_pipeline`, write in `_finish`."

- timestamp: 2026-09-23T09:08:00Z
  checked: "`ranked_count` writers and NULL-vs-0 semantics."
  found: "Only writer: rank.py:487 `run.ranked_count = scored`, `scored = COUNT(scores WHERE run_id=?)` (:480-485). `_finish` explicitly never touches it (:626). `Run(...)` creation (run.py:720, api/runs.py:92) leaves NULL. Skipped/disabled/in-flight/running/crashed/not-attempted all leave NULL; `0` requires the terminal write."
  implication: "NULL-vs-0 IS a usable 'never completed' vs 'completed with zero' discriminator, but it does NOT split running from skipped and carries no reason. It is necessary but not sufficient for the truth."

- timestamp: 2026-09-23T09:08:00Z
  checked: "The queue strip's gate and the `RunSummary` fields feeding it."
  found: "`queue.html:139` renders `#ranking-strip` only `{% if ranking_strip.get('ranked') is not none %}`; comment :130-132 states this is deliberate ('a fresh run shows nothing rather than a misleading Ranked 0 of N'). `_ranking_strip` (routes.py:276-310) returns `{ranked, candidates, cap_reason}` only; `cap_reason` comes from `llm_call_repo.rank_cap_reason_for_run` (a `budget_exceeded` row in `llm_calls`), which a skip never writes."
  implication: "When `ranked_count IS NULL` the strip is absent — running and skipped look identical. `_ranking_strip` carries no skip reason today. This is the exact surface the truth names."

- timestamp: 2026-09-23T09:08:00Z
  checked: "All user-visible not-ranked/no-score surfaces."
  found: "(1) `_listing_row.html:48` row badge `not ranked` (the 'Signals = not ranked' the user saw; header `Signals` at queue_list.html:60). (2) `listing_detail.html:64-69` hedged copy. (3) `queue.html:130-143` ranking strip (renders nothing on NULL). (4) `_run_status.html` (queue last-run strip + `GET /runs/{id}/status`) shows only run status/sources. (5) `runs.html` list+detail shows status/reason/counts/stage-log/errors, no ranking. (6) `routes.py:302-303` is the only consumer of `ranked_count`/`candidate_count`."
  implication: "The fix primary targets are (3) and (2); (1) is the actual visual the user hit but is row-scoped and needs run-level context; (4)/(5) are optional honesty surfaces."

- timestamp: 2026-09-23T09:08:00Z
  checked: "Free-form JSON columns on `runs` (migration/CHECK constraints)."
  found: "`errors_json`, `reason_counts_json`, `stage_log_json`, `criteria_snapshot_json` are all `Column(JSON)` with no CHECK (models.py:319-332). `reason_counts_json` keys are built in `_assemble_run_reason` (:544-560); `stage_log_json` entries via `_stage_entry` for persist/dedup/filter/criteria_compile. `RANK_STAGE = 'rank'` already exists (rank.py:72) and is already used as an `errors_json` source on start failure (run.py:913). `_write_criteria_snapshot` writes `criteria_snapshot_json` (:412-429) BEFORE `_finish` and is NOT clobbered by it."
  implication: "A marker needs no new column for storage space — but the CLOBBER is the constraint, not the schema. Reuse is free only if `_finish` writes it."

- timestamp: 2026-09-23T09:08:00Z
  checked: "Alembic head pinning."
  found: "`tests/db/test_migration_contract.py` asserts `versions == ['0004']` (:295, :561) and the single head starts with `0004` (:306); `tests/db/test_skeleton_boot.py:76` asserts `[('0004',)]`. Head is `0004_ranking_config.py`."
  implication: "Reusing an existing JSON column avoids a `0005` revision and both pinned-contract updates. A new dedicated column costs one revision + two test updates."

- timestamp: 2026-09-23T09:08:00Z
  checked: "Existing tests that pin the skip behaviour."
  found: "`tests/pipeline/test_rank_optional.py` proves all four skip/lifecycle paths write zero `llm_calls`/`scores` rows and leave `run.status == 'done'` (`_assert_skipped`, :67-78). `test_non_utf8...` captures `pipeline.rank_skipped reason=fact_store_absent` from logs only (:124-147). `tests/api/test_queue_ranked.py` pins the strip renders `Ranked N` / `Ranked N of M` when `ranked_count` is set, and row badge `not ranked`.
  implication: "A fix that persists a marker changes the premise of `_assert_skipped` (still zero LLM/score rows, but now a run-row marker); new/changed assertions will be needed. No test currently asserts a run-level ranking-skip marker because none exists."

## Resolution

<!-- OVERWRITE as understanding evolves -->

root_cause: >
  The ranking outcome is never persisted on the run, so every consumer is blind.
  `runs.ranked_count` is written only at the end of a successful `run_ranking`
  (rank.py:487) and is left NULL by all four non-completing states: the three
  skip paths (`ranking_in_flight` rank.py:524-526, `ranking_disabled` :373-375,
  `fact_store_absent` :377-387) plus the no-candidates path (run.py:904 gate) and
  a crash mid-pass. The only writer of the three free-form JSON columns that could
  carry a reason is `_finish` (run.py:591/610/616), which runs detached from and
  independently of the ranking task (D-88) and would clobber any earlier JSON
  write. So a skip leaves no machine-readable reason anywhere — just a structlog
  line. The queue strip is deliberately gated to render nothing when
  `ranked_count IS NULL` (queue.html:139), which makes "ranking is running" and
  "ranking was skipped" literally the same rendering (no strip), while the row
  badge and detail hedge can only offer a guess. NULL-vs-0 discriminates
  "never completed" from "completed with zero scores" but cannot split running
  from skipped and names no reason. The truth requires a persisted, per-run
  ranking state + reason that `_ranking_strip` and the detail page can render.

fix: >
  TODO — not implemented (diagnose-only). Recommended minimal surface below.

verification: >
  Not run (no fix applied). The reproduction is deterministic: no readable
  `cv.yaml` -> run `done`, `ranked_count` NULL, zero `scores`, strip absent.

files_changed: []

---

# TODO findings (requested)

## TODO 1 — Existing per-run JSON writers and free space

| Column | Writer(s) | Written how | Free for a ranking marker? |
|---|---|---|---|
| `runs.reason_counts_json` | `app/pipeline/run.py::_finish` (:616) | wholesale `reason_counts or None`, payload from `_assemble_run_reason` (:544-560) | **Yes** — plain dict, no CHECK; a `"ranking"` sub-key is ignored by `run_repo.run_counts_for` (reads named keys) and `RunSummary` |
| `runs.stage_log_json` | `_finish` (:610) | wholesale `stage_log or None`; entries from `_stage_entry` for `persist:<src>`, `dedup`, `filter`, `criteria_compile` | **Yes** — list, no CHECK; a `{"stage": "rank", "counts": {...}}` entry mirrors the existing pattern and `RANK_STAGE="rank"` already exists |
| `runs.errors_json` | `_finish` (:591) | wholesale `errors or None`; `{"source","status","error"}` shapes; only RANK entry today is on start FAILURE (:913) | **Discouraged** — a skip is not an error; `runs.html` renders every entry under `Errors`, and `_run_status.html` treats `*` entries as "no sources ran" |
| `runs.criteria_snapshot_json` | `_write_criteria_snapshot` (run.py:412-429) | written before `_finish`, NOT clobbered by it | **No** — wrong semantics (the query/rules used) |

**No extra writer exists.** The only app-level writers are `_finish` (three columns) and `rank.py:487` (`ranked_count`). Tests write the columns directly. `llm_call_repo.record_llm_call` writes `llm_calls`, not `runs` — a skip writes zero of those, so `rank_cap_reason_for_run` (the existing `cap_reason` read) cannot serve a skip.

## TODO 2 — Is `ranked_count` NULL vs 0 a usable discriminator?

| State | `ranked_count` |
|---|---|
| ranking running (task started, not finished) | NULL |
| `ranking_disabled` skip | NULL |
| `fact_store_absent` skip | NULL |
| `ranking_in_flight` skip | NULL |
| crashed mid-pass | NULL |
| no candidates (never attempted; run.py:904 gate) | NULL |
| completed, ≥1 score row | N (>0) |
| completed, zero score rows (all calls failed/refused) | **0** |

- **Writers of `ranked_count`:** exactly one — `app/pipeline/rank.py:487` (`run.ranked_count = scored`, `scored = COUNT(scores WHERE run_id=?)`, :480-485). `_finish` deliberately never touches it (`run.py:626`). Run creation (`run.py:720`, `api/runs.py:92`) leaves it NULL.
- **Verdict:** NULL-vs-0 is a **usable but insufficient** discriminator. It cleanly separates "never reached the terminal write" (NULL) from "completed and wrote zero" (0). It cannot separate running from skipped, and it carries no reason. The truth therefore needs *at least* one additional persisted fact (a skip reason, and ideally a `running` state).
- **Caveat:** the existing gate at `run.py:904` means a run with no non-excluded candidates never calls `start_ranking_task` and logs nothing — a fifth NULL state ("nothing to rank") that is not a "skip reason" but will need its own UI wording.

## TODO 3 — Can the ranking task know it was skipped in time to persist it?

Exact control flow:

```
run_pipeline
  ...persist/dedup/filter...
  run.py:898-910  try:
                    candidates = active_listings(...); excluded_ids = ...
                    if any(non-excluded):                      # run.py:904 gate
                      start_ranking_task(run_id, session_factory, llm, search_id)
                        rank.py:524  if _RANKING_TASK live:   # reason = ranking_in_flight
                        rank.py:525      log.info(rank_skipped, reason=ranking_in_flight); return
                        rank.py:529  task = asyncio.create_task(run_ranking(...))   # detached
                  except: record rank_start_failed in errors_json            # run.py:911-913
  run.py:934  reason, reason_counts = await _assemble_run_reason(...)   # YIELDS (async with)
  run.py:942  await _finish(...)   # writes status/errors/reason_counts/stage_log in ONE commit

run_ranking (detached, scheduled by create_task)
  rank.py:373  if not settings.ranking_enabled:  log(rank_skipped, ranking_disabled);  return   # (A)
  rank.py:377  if facts is None:
  rank.py:379      facts = load_facts(Path(settings.cv_dir)/CV_FILENAME)   # SYNC
  rank.py:380-387  except (CvFactStoreError, OSError): log(rank_skipped, fact_store_absent); return  # (B)
  ...scoring loop...
  rank.py:476-490  write run.ranked_count = scored; run.llm_calls/tokens; commit   # (C)
```

- **(A) `ranking_disabled`** and **(B) `fact_store_absent`** are decided inside `run_ranking`, which has `session_factory` + `run_id` and is async — so *in principle* it can persist. **But it cannot do so deterministically**: it is started by `create_task` and `run_pipeline` keeps awaiting; a DB write in (A)/(B) yields and interleaves with `_finish`, which then clobbers `reason_counts_json`/`stage_log_json`/`errors_json` with `or None`. The repo's own `05-06-PLAN.md` and `test_rank_optional.py:135-137` document this ordering as racy.
- **(1) `ranking_in_flight`** is decided in the synchronous `start_ranking_task` BEFORE `run_ranking` exists. It never reaches (A)/(B)/(C). It has `run_id`+`session_factory` but is sync and returns nothing.
- **Therefore:** to persist deterministically, compute the outcome in `run_pipeline` **before** `_finish` and let `_finish` write it (single writer, one commit). All three reasons are synchronously knowable there:
  1. `ranking_in_flight` — `start_ranking_task` returns the reason (change its return type from `None` to `str | None`).
  2. `ranking_disabled` — `settings.ranking_enabled` is directly readable in `run_pipeline`.
  3. `fact_store_absent` — a shared sync precheck (`load_facts` attempt) reading the same `settings.cv_dir`/`CV_FILENAME`; factor the disabled/absent checks into one helper used by both the precheck and `run_ranking` so the reason strings cannot drift.
- The detached task's final write (C) can additionally flip a `running` marker to `done` alongside `ranked_count`; the skip paths can stay log-only for storage *if the precheck is authoritative*.
- Alternative that keeps persistence inside the detached task: give it a column `_finish` does not clobber (new Alembic revision). Rejected as non-minimal.

## TODO 4 — Every user-visible not-ranked / no-score surface

| # | Surface | File:line | What it says |
|---|---|---|---|
| 1 | Queue row badge (the "Signals" column) | `app/web/templates/html/_listing_row.html:48` (header `Signals` at `queue_list.html:60`) | `not ranked` (`badge badge-unranked`, id `listing-unranked-{id}`) — rendered whenever `row.total_score is none`, both when ranking was skipped and when it is still running. Per-listing, so it also appears when the run ranked *other* rows. |
| 2 | Job detail page | `app/web/templates/html/listing_detail.html:64-69` | `Not yet ranked. This listing has no score yet — ranking may still be running, or the pass was skipped. Refresh once it finishes.` — the hedge the user quoted. |
| 3 | Queue ranking strip | `app/web/templates/html/queue.html:130-143` | Gated on `ranking_strip.get('ranked') is not none` (:139). When `ranked_count IS NULL` it renders **nothing** — this is the direct "no indication if the ranking is running" surface. |
| 4 | Queue last-run strip / run status fragment | `app/web/templates/html/_run_status.html` (via `routes.py:241-273`, `api/runs.py`) | `Run #N — done`, source counts, and (for `partial`) degradation copy. Never mentions ranking; reads "done" during a skip. |
| 5 | Run history list + detail | `app/web/templates/html/runs.html` (list :19-98, detail :100-163) | Status, reason, counts, excluded-by-rule, criteria, stage log, errors. No ranking column or stage entry — a skip is invisible. |
| 6 | (data, no dedicated surface) | `app/web/routes.py:302-303` | `ranked`/`candidates` consumed only by surface 3. |

Surface 3 is the truth's "queue ranking strip"; surface 2 is its "job detail page". Surface 1 is the exact visual the user reported but is row-scoped and lacks run context. Surfaces 4/5 are optional honesty additions.

---

# Recommended minimal fix surface (NOT implemented)

**Files that must change:**

1. `app/pipeline/rank.py` — `start_ranking_task` returns its skip reason (`str | None`) instead of only logging; extract the `ranking_disabled` + `fact_store_absent` checks into a shared sync helper used by both the new precheck and `run_ranking`. (Optionally have `run_ranking`'s terminal write set `ranking.status="done"`.)
2. `app/pipeline/run.py` — in the ranking block (:898-913) compute the outcome (`started` / `ranking_in_flight` / `ranking_disabled` / `fact_store_absent` / `not_attempted`) synchronously; pass it into `_finish`; `_finish` writes it as `reason_counts_json["ranking"] = {"status": ..., "reason": ...}` (or a `rank` entry in `stage_log_json`), in its single commit.
3. `app/db/repositories/run_repo.py` — `RunSummary` gains `ranking_status` / `ranking_reason`, parsed in `_summary`; `_ranking_strip` consumes them.
4. `app/web/routes.py` — `_ranking_strip` (:276-310) includes the outcome keys, preserving the never-raise guard and empty-mapping return.
5. `app/web/templates/html/queue.html` — replace the `ranked is not none`-only gate with branches: `running` → "Ranking in progress…", `skipped:<reason>` → "Ranking skipped — <human reason>", `not_attempted` → "Nothing to rank", `ranked` → existing `Ranked N [of M]`.
6. `app/web/templates/html/listing_detail.html` — replace the hedge (:64-69) with the run's actual state/reason (requires the detail route, `app/api/listings.py`, to pass the run-level ranking state to the template — currently it passes `row`, `score`, `factors`, `weights`).
7. Optional, for the user's exact surface: `_listing_row.html` badge could carry the run-level state, but this needs new row/page context and is wider than the truth's literal scope.

**Alembic revision avoidable?** **Yes.** Reuse `reason_counts_json` (dict, no CHECK) or `stage_log_json` (list, no CHECK); no `0005`, no change to `tests/db/test_migration_contract.py` (:295/:306/:561) or `tests/db/test_skeleton_boot.py:76`.

**Tradeoff (one/two lines):** Reusing a free-form JSON column keeps the migration contract frozen and `_finish` as the single deterministic writer, at the cost of stretching a generic column and needing the read model to parse it — and it forces the skip reason to be precomputed before `_finish`. A dedicated `ranking_status`/`ranking_reason` column is cleaner and lets the detached task write directly (no race, no precheck duplication) but costs one Alembic revision plus two pinned-contract test updates.

# Contradicting evidence / caveats

1. **The empty strip is deliberate, not an oversight.** `queue.html:130-132` documents rendering nothing on NULL "rather than a misleading Ranked 0 of N". The fix must preserve the no-fabricated-zero property (`_optional_int` already models a positive-only denominator) while *adding* a truthful skipped/running message — it is a reversal of a prior design decision, not a plain bug.
2. **D-88 refresh-only.** No polling/SSE/poll target may be added. "In progress" can only be a snapshot at render time; if ranking finishes while the page is open, the strip stays stale until a manual refresh. A live spinner is out of scope.
3. **Startup recovery is deliberately absent.** `rank.py:31-34` states an interrupted ranking task "leaves a NULL `runs.ranked_count`". A persisted `running` marker therefore risks a permanent stale "Ranking in progress…" after a crash. The fix must define staleness (e.g. only trust `running` when the task is in `_BACKGROUND_TASKS`, or when the run is the latest and no terminal marker exists) — real complexity a naive "write running at task start" ignores.
4. **The row badge is row-scoped.** It can legitimately read `not ranked` for a single listing while the run ranked others (listing excluded/failed). It cannot name the run-level skip reason without new context; the truth scopes the requirement to the strip + detail page, so widening to the badge may exceed the gap.
5. **`fact_store_absent` covers absent AND unreadable (and non-UTF-8).** `test_rank_optional.py:110-147` + `05-06-SUMMARY.md` confirm the single reason is deliberate. UI copy must say "no readable CV fact store", not "file missing".
6. **Fixing this changes `_assert_skipped`'s premise.** `test_rank_optional.py:67-78` currently proves skips write literally nothing to the run beyond `status=done`; a persisted marker adds one run-row write. New assertions will be required (tests are out of scope for this diagnosis).
