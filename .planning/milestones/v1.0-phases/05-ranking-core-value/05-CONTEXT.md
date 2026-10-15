# Phase 5: Ranking — CORE VALUE - Context

**Gathered:** 2026-09-22
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the ranking half of the Core Value: **one ranked, explained queue**. Every listing that survives Phase 2's deterministic filter is scored against the user's CV using named, inspectable factors; each factor's sub-score is stored; the total is computed in code from those sub-scores and the current weights; each ranked listing carries a rationale grounded in stored evidence; and the job detail view shows a requirement-by-requirement fit breakdown with named gaps.

It also delivers the first **automatic** LLM consumer in the pipeline (Phase 3 deliberately shipped none — see D-49), with per-run and per-day spend caps enforced *before* each call is made.

**In scope:** the ranking rubric and factor set; the ranking schema and prompt assembly; the `scores` writer (the table exists and has never been written to); the requirement-extraction step co-located with ranking; the spend cap (config + enforcement + surface); a non-blocking in-run ranking task; the `GET /listings/{id}` detail page; score surfacing and score-based sorting on the queue; global weight editing on the settings page; read-time total derivation.

**Out of scope (explicitly):**
- **Tailoring / CV patching / CV preview / verification checks** — Phase 6. Ranking *stores* the requirement breakdown; it does not patch the CV.
- **Cover letters, PDF/DOCX input, ATS-match optimisation** — Phase 6 / never.
- **RANK-09** (ranking learns from save/skip history), **RANK-10** (listing-quality / ghost-stale score separate from fit), **RANK-11** (salary-market context) — all v2 per REQUIREMENTS.md.
- **A market-salary data source** (level.fyi or Adzuna `/histogram`) — explicitly deferred; see D-90. This is RANK-11's territory and it is v2.
- **User-supplied custom rubric text in the UI** — designed-for but deferred (D-83).
- **Vector / embedding-based ranking** — rejected at project level (REQUIREMENTS.md line 160: "+0.0000 NDCG@10 at 2.2× the runtime").
- **Live/streaming score push to the browser** — refresh-to-see-progress only (D-88).
- **ranking as a gate on ingest** — ingest always succeeds (D-94).

</domain>

<decisions>
## Implementation Decisions

### Scoring depth: LLM vs code
- **D-78:** The LLM returns **per-factor sub-scores only** — never a total. The total is computed in code from stored sub-scores and weights, satisfying RANK-03 literally. Code arithmetic lives in `app/domain` (pure, no I/O, per D-24). Consequence: weights can change with **zero** new LLM calls, which is the only shape in which SC-3 ("adjust weights, see rankings re-derive without a new LLM call") is actually true rather than aspirational. — **Reversibility:** costly — every stored `factor_scores_json` shape derives from this; moving to an LLM-supplied total later would invalidate stored rows and require a re-rank of the whole corpus.
- **D-79:** The total is a **normalised weighted mean**: `total = Σ(sub_i × w_i) / Σ(w_i over present factors)`. Result stays 0.0–1.0, so it is comparable across any weight set and across runs. Dynamic denominator (see D-82).
- **D-80:** `scores.rubric_version` is produced by a **hand-bumped version string** in the rubric module (e.g. `RUBRIC_VERSION = "v1"`), stamped onto every written score row. A content-hash-derived version was considered and rejected — it makes the version opaque in logs and churns every stored row on any wording fix, and it conflicts with the D-54 precedent (pin an explicit constant; "adaptive" rejected).
- **D-81 (requirement extraction placement — resolves the ROADMAP research flag):** requirement extraction happens **inside the ranking call**, not as a separate pass. One `complete_structured` response returns **both** the factor sub-scores **and** a structured requirements list, where each requirement carries `text`, a fit verdict (`met`/`partial`/`gap`), and the CV fact ID that evidences it (or null for a gap). Chosen over a separate cached extract call because it costs no extra round-trip, guarantees the breakdown matches the score that used it, and gives Phase 6 the stored requirement list to read instead of re-extracting. This settles the flag now, as ROADMAP demanded, rather than in Phase 6. — **Reversibility:** costly — the ranking schema and the Phase 6 input contract both derive from the co-located shape; splitting them later means re-ranking.

### Rubric & factor set
- **D-82:** The factor set is **six named factors**: `skills`, `seniority`, `domain`, `location`, `evidence`, `compensation`. (`compensation` was added at the user's request on top of the initially recommended five.) `evidence` means how well the listing's stated requirements are actually supported by real CV bullets — it is the honest-fit factor and the main reason the score is not just a keyword match.
- **D-83:** The default rubric ships as **prose-defined factor constants** in a committed, pure module (`app/domain/rubric.py`): factor key, display label, and the prose definition sent to the LLM. A **user-supplied rubric override** was explicitly requested and explicitly deferred: Phase 5 designs the hook but does not expose it in UI/config. When it is added (Phase 6/8), the override text is **untrusted free text** and MUST be routed through `parts` (user turn), never `system`, and subjected to the same `app/domain/sanitize.py` injection treatment as listing content (D-38). — **Reversibility:** costly — if the override is added without a reserved column/field, it needs a schema change and a migration on the settings/config path.
- **D-84:** The `compensation` factor is scored **only from the listing's own ingested salary fields**. No third-party or market-salary lookup. This keeps the score honestly about fit rather than inference and keeps SC-2 (stable absolute score) independent of a third-party site's uptime. A market-salary source is deferred to v2 under RANK-11 (D-90). — **Reversibility:** reversible.
- **D-85:** A factor with **no usable data** for a listing (the common case for `compensation`) is **dropped from that listing's weighted mean** and the remaining weights re-normalise (dynamic denominator, D-79). It is never scored as zero — a board omitting salary must not be read as the listing paying badly. Listings that lose factors are flagged via `scores.confidence_tier` (`high`/`medium`/`low`; the column and its CHECK constraint already exist) so reduced evidence is visible rather than silent.

### Batching & latency budget
- **D-86:** **One `complete_structured` call per listing.** The prompt contains exactly one listing and the CV; no sibling listings. Scoring is therefore absolute by construction, not by prompt discipline — which is what RANK-07 / SC-2 require ("never a relative ranking of a batch"). It also isolates failures per listing. A per-K batching mode was considered and rejected as directly contrary to SC-2; a `K` knob for later was rejected as two code paths for a knob with no measured data to tune it. — **Reversibility:** costly — the ranking stage, schema, and cap accounting are all shaped by per-listing calls; per-K would be a rewrite of the stage, not a parameter.
- **D-87:** Ranking runs **inside `run_pipeline()` as a stage after the hard filter and before `_finish`**, using the seam already reserved there (the `D-49 / Phase-5 SEAM` comment and the guarded `llm_calls`/`llm_tokens` writes). `rank_pipeline()`'s stage ordering is thus: fetch/persist → Tier-2 dedup → hard filter → **rank** → `_finish`.
- **D-88:** The ranking stage is **non-blocking with respect to the run's completion**. The run finishes fetch/dedup/filter and completes **normally** first; a **detached background ranking task** then scores surviving listings one at a time, upserting each score row as it lands. The queue is browseable throughout and refreshes to show new scores — **no live push / SSE / polling in Phase 5**. The user's words: *"they should not block each other. The user should be able to see the queue and as we get the ranks in, the scores should update. At the start we don't need to dynamically update them. User can refresh the page."* A separate `runs` row for ranking was considered and rejected (a second row per day plus a linkage); keeping the run open until ranking completes was rejected as it muddies the run lifecycle and the last-run strip. — **Reversibility:** costly — the run lifecycle, the `ranked_count` semantics, and the cap accounting all depend on the detached-task shape.
- **D-89:** `runs.ranked_count` records **how many listings actually have a score at the time it is written** — it is progress-of-a-detached-task, not a scheduled total. `_finish` still does not touch it (per the existing seam comment); the ranking path owns it.
- **D-90 (deferred idea recorded):** a market-salary data source is a **v2 / RANK-11** item. If revisited, Adzuna's `/histogram` endpoint is the credential-free option and is preferred over scraping level.fyi (which has no public API and would collide with `tests/test_no_credentials.py`). Recorded here so it is not lost.

### Spend cap semantics & enforcement
- **D-91:** **Two independent caps**, both in `Settings`: a **per-run** ranking-call ceiling and a **rolling-24h** call ceiling (`SUM` over `llm_calls.created_at`, which is indexed). A call is refused if **either** would be exceeded. This matches RANK-08's "per run and per day" wording directly. Token-based caps were considered and rejected: you cannot know a call's token cost before making it, so "refuse before the call" would degrade into a projection. — **Reversibility:** costly — `Settings` gains required fields (`tests/test_config.py` `REQUIRED_SETTINGS_FIELDS` / `LIMIT_FIELDS` must be updated in lockstep) and `compose.yml` / `.env.example` spellings are pinned by test.
- **D-92:** Enforcement is **reserve-then-call**: immediately before each call the ranking task reads the day total plus an in-flight counter guarded by an `asyncio.Lock`, refuses if the reservation would exceed either cap, and releases on completion. Because the ranking task is a single sequential task, the in-flight window is tiny and the counter is exact without a DB transaction. A DB-persisted `pending` row was considered and rejected — it requires a **migration** to extend the `llm_calls.status` CHECK constraint, for no gain at this scale.
- **D-93:** A cap hit is a **graceful stop, not an error**: ranking ends, remaining listings stay visibly *"not yet ranked"*, and the surfaces report *"ranked X of Y — cap reached"* plus which cap fired. No exception, no partial-batch corruption, nothing lost — the next run or the next day continues. The run is **not** marked failed (hitting a deliberate cost control is not a failure, and marking it failed would make `/runs` cry wolf daily). Optionally record one refusal row per refused call with `status='error'`, `error_kind='budget_exceeded'`, `run_id` set — consistent with "enforced before the call was made".

### Degraded / failure posture
- **D-94:** **Ranking is optional; ingest always succeeds unranked.** If opencode is unreachable, or `cv.yaml` is absent, or ranking is disabled in Settings, `run_pipeline()` completes exactly as it does today, writes **zero** `llm_calls`, and the queue shows unranked listings. Ranking never gates ingest. This is the only posture consistent with D-08 (the app boots and works without opencode) and it keeps the existing zero-LLM test guards meaningful by default. — **Reversibility:** reversible.
- **D-95:** **Per-listing failure is isolated.** A listing whose call fails or returns an invalid schema is recorded in `llm_calls` using the **D-52 error taxonomy** (`status` ∈ `ok`/`invalid`/`timeout`/`error` plus `error_kind` and `attempts`) and simply **gets no `scores` row**; the ranking task continues to the next listing. The run reports "ranked X of Y, Z failed". The ranking stage adds **no retry loop of its own** — bounded retries stay inside `llm/` via the existing `retryCount` (D-56).

### Job detail view & queue integration
- **D-96:** A **dedicated `GET /listings/{id}` full page** is added (no such route or template exists today) and reuses `read_row()` from `app/db/repositories/queue_repo.py`. It contains: the total score and `confidence_tier`; the per-factor breakdown showing each factor's sub-score **and** its weight; the rationale; the requirement-by-requirement fit list with named gaps and evidencing CV fact IDs; the "merged from N sources" record (D-26); and the existing save/hide/shortlist actions. A fragment/expandable panel was rejected because the breakdown is rich and would have to be rebuilt as a page when Phase 6 adds CV preview. The route MUST declare `user: User = Depends(current_user)` (auth-seam test). — **Reversibility:** costly — Phase 6's CV preview is expected to hang off this page.
- **D-97:** The queue **defaults to `score DESC`** with unranked/unscored listings last, and each row shows the total score plus a `confidence_tier` badge. The existing `first_seen_at DESC, id DESC` ordering stays available. This is the smallest change that makes the queue genuinely "ranked" per the Core Value sentence.
- **D-98:** A **minimum-score threshold** is added as a **view filter** on the queue (same interaction shape as Phase 2's existing "Show excluded" toggle — view-only, instant, reversible, no stored exclusion, no schema change). Un-scored listings always remain visible so that "queue usable before ranking finishes" (D-88) is not broken by the threshold. Treating low scores as `listing_exclusions` was considered and rejected: it would conflate a soft quality judgment with the hard deterministic rules D-34/D-36 define.

### Weight editing & re-derive
- **D-99:** Factor weights are **global ranking configuration on the settings page** — one set of six numbers — not per-search. This matches the user's request (*"lets make it be possible to change the weights on the settings page for each factor"*) and leaves D-32's per-search scope untouched. Per-search weights and a defaults-plus-override scheme were both considered and rejected as complexity for a need that has not appeared. The form follows the established `app/api/searches.py` + fragment-swap pattern (stdlib `read_form()`, no `python-multipart`, mutating POST returns the re-rendered fragment). — **Reversibility:** costly — moving to per-search weights later means a schema addition and a precedence rule.
- **D-100:** Totals are **computed on read** from stored sub-scores under the **current** weights: `total = Σ(sub_i × w_i) / Σ(w_i)`. A weight change therefore triggers **zero** LLM calls and re-derives instantly. Stored `scores.total_score` and `scores.weights_json` are an **audit snapshot** of what the rubric and weights were *at scoring time* — they are not the sort source. Rewriting `total_score` rows on weight change was rejected (it writes N rows per save and blurs "what the LLM said" vs "what the weights said"). A caching layer was rejected as premature at personal scale. — **Reversibility:** costly — queue sorting becomes a computed expression rather than a plain indexed column read (`ix_scores_listing_total` stops being the sort path); reverting means re-materialising totals.
- **D-101:** **One score row per listing per run** (the existing `uq_scores_listing_run_criteria` constraint already enforces this). Weight tweaks never multiply rows.

### Prior-phase constraints this phase must honour (no new decision, recorded for the planner)
- **D-102:** `run_pipeline()` becomes the first automatic LLM consumer, which **supersedes D-49's "no automatic per-run LLM stage"** — that decision was explicitly scoped to Phase 3 and named Phase 5 as ranking's owner. The two existing zero-LLM guards (`tests/pipeline/test_finish_llm_counters.py::test_a_pipeline_run_writes_zero_llm_calls`, `tests/pipeline/test_filter_stage.py:197`) must be **deliberately updated** to reflect ranking being optional/disabled-by-default in the test lane, not silently left to fail. Resume the D-12 per-call telemetry requirement (model + version recorded per call) and the §6.3 requirement that instruction-like sanitizer findings be **recorded**, not discarded.

### the agent's Discretion
- The exact prose wording of each factor definition in `app/domain/rubric.py` (the factor keys are locked; the wording is not).
- The concrete Pydantic schema field names for the ranking response and the requirement list, provided sub-scores are per-factor and requirements carry text + verdict + evidencing fact ID.
- Score display precision/rounding on the queue and detail page.
- The exact `confidence_tier` boundaries.
- Concrete cap default values (they must be `Settings` fields, per D-91 and `tests/test_config.py`).
- The ranking task's concrete lifecycle mechanics: startup recovery for an interrupted ranking task, and how a re-run that overlaps an in-flight ranking task is handled.
- Where the "ranked X of Y" / cap-reason surface lives (settings/health surface vs `/runs` detail vs queue strip).
- Prompt assembly placement outside `llm/` and the exact `parts` composition for the CV + listing payload.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

> ROADMAP.md contains **no `Canonical refs:` line** for Phase 5 (verified by grep — the same absence as Phases 3 and 4). The list below is therefore assembled from REQUIREMENTS.md, PROJECT.md, the `.planning/research/` volumes, and the prior phase CONTEXT files.

### The design contract (read in this order)
- `.planning/research/ARCHITECTURE.md` §6 `llm/` (L530–607) — the LLM port design contract: `StructuredCallResult`, `complete_structured()` signature, trust boundary (`parts` only for untrusted content, `system` never from data, `tools=()`), §6.2 schema-violation-as-run-outcome semantics, §6.3 injection findings must be recorded, §6.5 nothing outside `llm/` imports `httpx`/`subprocess`.
- `.planning/research/ARCHITECTURE.md` — component C-numbering and project structure (L103–106 components, L125–197 layout) for where `app/domain/rubric.py`, the ranking stage, and the `score_repo` belong.
- `.planning/research/ARCHITECTURE.md` AP2/AP12 — the never-fabricate architecture principles; AP2 governs why the LLM never emits prose for the CV and why ranking returns IDs/subscores rather than free judgment.
- `.planning/research/PITFALLS.md` — M1 (schema-violation handling), M9 (per-call model+version telemetry), M10, M3 (blocking work off the event loop), m5.
- `.planning/research/STACK.md` §Q7 — the opencode integration, structured output, and the budget/quota framing; STACK §Q1 for the salary-data reality (`salary_is_predicted` common, Adzuna `/histogram`) that grounds D-84/D-90.
- `.planning/REQUIREMENTS.md` — RANK-01…RANK-08 (exact text), UI-01/UI-02/UI-03; Out-of-Scope table line 160 (vector/embedding ranking) and line 156 (CAPTCHA/credentialed scraping); RANK-09/10/11 as v2.
- `.planning/PROJECT.md` — Core Value sentence, cost constraint ("LLM calls are the dominant variable cost"), the never-fabricate hard line, the no-auth-in-v1 seam.
- `.planning/ROADMAP.md` — Phase 5 goal, the 5 success criteria, and the research flag requiring batching + cap semantics + extraction placement to be settled here.
- `.planning/WINDOWS.md` #2 and #4 — the opencode call-timing/health window notes (a health badge is not a proxy for a real call).

### Prior phase decisions this phase builds on
- `.planning/phases/03-llm-port-structured-output/03-CONTEXT.md` — D-48…D-57 (the selftest action, the no-per-run-LLM decision that Phase 5 now supersedes, `llm_calls` probe recording, the D-52 failure-cause taxonomy, the pinned wire constants and the `/doc` snapshot chain of proof).
- `.planning/phases/02-clean-filtered-queryable-queue/02-CONTEXT.md` — D-32/D-33 (search + criteria_version scope), D-34/D-36 (typed filter rules; hard rules stay deterministic and separate from ranking), D-41 (append-only `listing_events` save/hide), D-42 (FTS + queue ordering), D-44 (persisted run reason).
- `.planning/phases/01-walking-skeleton-foundations/01-CONTEXT.md` — D-08 (degraded-tolerant opencode, app boots without it), D-12 (per-call model+version), D-14/D-15 (Tailwind/HTMX/Alpine vendored, no CDN), D-20 (`scores.factor_scores_json` + `weights_json` + `criteria_version` were a migration-0001 acceptance item), D-21 (auth seam on every route), D-23 (deterministic filter precedes any LLM).
- `.planning/phases/04-cv-fact-store-latex-compile-spike/04-CONTEXT.md` — D-63/D-64 (the hierarchical CV fact IDs that ranking cites as evidence and that Phase 6's patch uses), D-65/D-66 (the `cv.yaml` shape and the single fail-loud factstore reader), D-77 (`cv_versions` snapshots).

### Existing code the plan must extend (path anchors)
- `app/db/models.py:322-355` — `Score` model (never written; the `scores` writer is net-new this phase).
- `app/db/repositories/llm_call_repo.py` — `record_llm_call()` (the audit writer), `llm_totals_for_run()`, and `PURPOSES` (already contains `rank`). Reuse for D-95; extend for the per-day aggregate D-91 needs.
- `app/llm/base.py` (`StructuredCallResult`, the `complete_structured` Protocol), `app/llm/contract.py` (pinned wire constants), `app/llm/__init__.py` `get_llm_backend` (the DI seam the ranking tests override).
- `app/pipeline/run.py` — the `_finish` seam (`D-49 / Phase-5 SEAM`, guarded `llm_calls`/`llm_tokens` writes, `ranked_count` deliberately untouched) and the stage call site between the filter stage and `_finish`.
- `app/db/repositories/queue_repo.py` — `read_queue()` (ordering + `QueueRow`), `read_row()` (the detail-page seam).
- `app/domain/cv.py` + `app/cv/factstore.py` — the fact IDs and the single reader that ranking must cite as evidence.
- `app/api/searches.py` + `app/web/templates/html/criteria.html` — the form/validation/fragment-swap pattern the weights editor and threshold control should copy.
- `app/config.py` + `tests/test_config.py` — the `REQUIRED_SETTINGS_FIELDS` / `LIMIT_FIELDS` contract every new cap/knob must satisfy.
- `tests/test_auth_seam.py` — every new route declares `current_user`.
- `tests/test_import_discipline.py` — `app/pipeline` must call the port, never `httpx`; `app/domain` stays pure (the rubric module must be I/O-free).
- `tests/test_stylesheet_coverage.py` + `tests/test_no_cdn.py` — every new template class needs a CSS rule; assets stay vendored.

### Precedent docs (how this repo records measured/probe outcomes)
- `docs/probes/2026-09-15-scraper-survival.md`, `docs/probes/2026-09-21-cv-tex-spike.md`, `docs/runbook-opencode-contract.md`, `docs/implementation-notes.md`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`scores` table + model already exist** (`app/db/models.py:322-355`; migration 0001) with `factor_scores_json`, `total_score`, `weights_json`, `rubric_version`, `confidence_tier`, `rationale`, `strengths_json`, `gaps_json`, `criteria_version`, and the `uq_scores_listing_run_criteria` unique constraint. **No writer exists** — this phase creates `app/db/repositories/score_repo.py`.
- **`llm_calls` writer already exists** (`record_llm_call`) and **`rank` is already a legal `purpose`** — no migration needed for ranking audit rows.
- **The `_finish` phase-5 seam already exists** (`app/pipeline/run.py:614-623`): `llm_calls`/`llm_tokens` are guarded optional params, `ranked_count` is deliberately untouched.
- **`_finish`'s `llm_totals_for_run()`** read is already documented as the call Phase 5's finish path must use.
- **`read_row()` in `queue_repo.py`** returns one enriched row by id — the detail page's data source.
- **`get_llm_backend` DI factory + `OfflineLLMBackend` test stub** (`tests/conftest.py:270`) — the ranking tests' override path.
- **`app/domain/rubric.py` is net-new** but must stay pure (no `httpx`/`sqlalchemy`/`jinja2`/`fastapi`; `tests/test_import_discipline.py`).

### Established Patterns
- **Failure is a value**: Phase 2/3 never raise for per-item problems; ranking follows the same shape (D-94/D-95).
- **Persisted structured reason + counts** (D-44) — the natural home for "ranked X of Y, cap reached".
- **Formatter/fragment idiom**: `render_*` helpers get a template, `make_module({...})`, call a macro, wrap in `HTMLResponse` — the detail page and weights editor should follow.
- **Purpose-built forms, never raw JSON textareas; validation at the storage boundary** (D-34) — applies to the weights editor.
- **`scanned-dir literal ban** (`tests/test_config.py:409-441`): any cap/weight integer ≥3 hard-coded under `app/pipeline/` fails the test. Caps must be `Settings` fields; weights belong in `app/domain/rubric.py` (not a scanned dir) or come from config.
- **Every route depends on `current_user`; no identity columns ever.**

### Integration Points
- `run_pipeline()` after the filter stage — the ranking stage call site.
- `_finish()` — where `llm_calls`/`llm_tokens` counters are written and where `ranked_count` is now owned.
- `queue_repo.read_queue()` — ordering changes for D-97 and the threshold for D-98.
- `app/web/routes.py` — the new `GET /listings/{id}` route joins the existing route set.
- `app/config.py` + `tests/test_config.py` + `compose.yml` + `.env.example` — the cap knobs land here in lockstep.
- `app/db/repositories/llm_call_repo.py` — a new per-day aggregate query backs D-91.

</code_context>

<specifics>
## Specific Ideas

- The user's Core Value framing for this phase: **"one ranked, explained queue"** — ranking has to land on the queue list itself, not only behind a detail click.
- On non-blocking ranking, verbatim: *"they should not block each other. The user should be able to see the queue and as we get the ranks in, the scores should update. At the start we don't need to dynamically update them. User can refresh the page."*
- On factor weights, verbatim: *"lets make it be possible to change the weights on the settings page for each factor."*
- On the factor set, verbatim: *"I think 5 factors make sense + compensation"* — the recommended five plus compensation, making six.
- On the compensation data source, the user asked whether level.fyi could be pulled when salary is missing. That was declined for Phase 5 (no public API, credentialed/scraped, RANK-11 is v2, `tests/test_no_credentials.py`) and recorded as a v2 deferred idea (D-90) with Adzuna `/histogram` named as the credential-free option.
- On threshold filtering, verbatim: *"I think we should also be able to filter out rankings/score which are below a threshold if needed."*

</specifics>

<deferred>
## Deferred Ideas

- **User-supplied rubric override (UI + storage)** — requested, explicitly deferred out of Phase 5 (D-83). When added it must route through `parts` + `sanitize`, never `system`. Likely Phase 6/8.
- **Market-salary data source for the compensation factor** — v2 under RANK-11 (D-90). Adzuna `/histogram` is the credential-free route; level.fyi was proposed and declined (no public API, likely credentialed/scraped).
- **RANK-09** (ranking learns from save/skip history), **RANK-10** (listing-quality / ghost-stale score separate from fit) — v2 per REQUIREMENTS.md.
- **Live/streaming score updates** (SSE/HTMX polling as scores arrive) — explicitly unnecessary now; refresh is sufficient (D-88). Revisit only if refresh proves annoying.
- **Per-search factor weights** — considered and deferred (D-99); global weights only in v1.
- **In-memory caching of read-time totals** — premature at personal scale (D-100).

### Reviewed Todos (not folded)
None — `cross_reference_todos` found no pending todos (STATE.md pending todos: none).

</deferred>

---

*Phase: 5-Ranking — CORE VALUE*
*Context gathered: 2026-09-22*
