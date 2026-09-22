# Phase 5: Ranking — CORE VALUE - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-22
**Phase:** 5-Ranking — CORE VALUE
**Areas discussed:** Scoring depth (LLM vs code), Rubric & factor set, Batching & latency budget, Spend cap semantics & enforcement, Job detail view & queue integration, Weight editing & re-derive, Degraded / failure posture

---

## Area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Rubric & factor set | What the named factors are and what each means against a CV | ✓ |
| Scoring depth: LLM vs code | Which sub-scores come from the LLM vs deterministic code | ✓ |
| Batching & latency budget | One call per listing vs per K listings | ✓ |
| Spend cap semantics & enforcement point | Per-run + per-day caps, enforced before the call | ✓ |
| Job detail view & queue integration | UI-01/UI-02 surfacing of rankings | ✓ |
| Weight editing & re-derive | Where weights live; how rankings re-derive | ✓ |
| Degraded / failure posture | LLM unreachable / invalid schema / no cv.yaml | ✓ |

**User's choice:** all seven areas selected for discussion.

---

## Scoring depth: LLM vs code

| Option | Description | Selected |
|--------|-------------|----------|
| LLM gives sub-scores only | LLM returns per-factor sub-scores + rationale + gaps; code computes the total | ✓ |
| Hybrid: code derives hard factors, LLM scores fuzzy ones | Deterministic factors from Phase 2 data, LLM only for fuzzy fit | |
| LLM emits total too, code recomputes over it | LLM total kept as cross-check/fallback | |

**User's choice:** LLM gives sub-scores only.
**Notes:** chosen as the only shape where SC-3 ("adjust weights, re-rank without a new LLM call") is actually true.

| Option | Description | Selected |
|--------|-------------|----------|
| Prose-defined factors, normalised weighted mean | Free 0–1 sub-scores, prose factor definitions, normalised weighted mean | ✓ |
| Ordinal levels per factor, mapped to values in code | Fixed named levels (strong/partial/none) → fixed values | |
| Prose factors + a rubric_version constant bumped on wording change | Versioned factor definitions with a stamped version | ✓ |

**User's choice:** *"i like option 1 and 3, i want by default for llm to choose for me but i also want to be able to provide a rubrick to score against"* — a combination of options 1 and 3.
**Notes:** interpreted as the normalised weighted mean (option 1) plus a versioned rubric constant (option 3), with the default rubric used automatically and a user-supplied override deferred.

| Option | Description | Selected |
|--------|-------------|----------|
| Both in Phase 5: default + optional per-search override | Default rubric plus a live per-search override UI | |
| Default rubric now, override designed-for but deferred | Default rubric + version stamping; override hook designed, not exposed | ✓ |
| Deferral, but note the override must go through parts + sanitize when added | Same as deferral plus an explicit trust-boundary note | |

**User's choice:** default rubric now, override designed-for but deferred.

| Option | Description | Selected |
|--------|-------------|----------|
| app/domain/rubric.py constants + hand-bumped version string | Pure constants module; `rubric_version` a hand-bumped string | ✓ |
| Content-hash the rubric definition to derive the version | `rubric_version` derived as a content hash | |
| Rubric as versioned DB rows, not code | Factor definitions stored in a versioned DB table | |

**User's choice:** `app/domain/rubric.py` constants + hand-bumped version string.

---

## Rubric & factor set

| Option | Description | Selected |
|--------|-------------|----------|
| 5 factors: skills, seniority, domain, location, evidence | The recommended core set | |
| 7 factors: add compensation + trajectory | Five plus compensation and trajectory | |
| LLM proposes factors freely per listing | Factors chosen by the model per listing | |

**User's choice:** *"I think 5 factors make sense + compensation"* — the recommended five plus compensation, i.e. **six** factors.
**Notes:** the user also asked whether level.fyi could be pulled to estimate salary when missing.

| Option | Description | Selected |
|--------|-------------|----------|
| Compensation from listing's own data; omit factor when absent | Score only from ingested salary fields; missing ⇒ factor dropped, weights re-normalise | ✓ |
| Same, plus record a v2 deferred idea for a market-salary source | As above, with a recorded v2 deferred idea | |
| Actually pull level.fyi now (not recommended) | Build a level.fyi lookup in Phase 5 | |

**User's choice:** compensation from listing's own data; omit factor when absent.
**Notes:** level.fyi was declined — no public API, likely credentialed/scraped, collides with `tests/test_no_credentials.py`, and RANK-11 is explicitly v2. Recorded as a v2 deferred idea with Adzuna `/histogram` named as the credential-free alternative.

| Option | Description | Selected |
|--------|-------------|----------|
| Dynamic denominator; flag reduced-evidence as confidence_tier | `total = Σ(sub×w)/Σ(w over present factors)`; tier flags reduced evidence | ✓ |
| Fixed denominator; missing factor scores zero | Full weight sum always; missing factor contributes 0 | |
| No total when factors are missing | Leave `total_score` NULL and render "insufficient data" | |

**User's choice:** dynamic denominator + `confidence_tier` flagging.
**Notes:** user added *"lets make it be possible to change the weights on the settings page for each factor"* in the same answer — carried into the weights area.

---

## Batching & latency budget

| Option | Description | Selected |
|--------|-------------|----------|
| One call per listing | Single-listing schema, absolute scores by construction, per-listing failure isolation | ✓ |
| K listings per call, scored independently in one response | Cheaper, but siblings invite relative judgment and one bad response loses K | |
| Per-listing, with a K knob for later | Per-listing default plus an untuned K knob | |

**User's choice:** one call per listing.

| Option | Description | Selected |
|--------|-------------|----------|
| In-run stage with a per-run ranking ceiling | Rank inside `run_pipeline()` bounded by a ceiling | |
| Separate on-demand ranking action, run stays LLM-free | Ranking triggered manually | |
| In-run stage, concurrent calls with a bounded semaphore | Concurrent ranking with bounded parallelism | |

**User's choice:** in-run stage, but non-blocking — *"they should not block each other. The user should be able to see the queue and as we get the ranks in, the scores should update. At the start we don't need to dynamically update them. User can refresh the page."*
**Notes:** interpreted as a detached background ranking task that scores listings after the run completes (D-88), with refresh-based progress.

| Option | Description | Selected |
|--------|-------------|----------|
| Run completes first; detached ranking task scores listings afterward | Run completes normally; detached task upserts scores as they land | ✓ |
| Run stays open until ranking completes, progress in stage log | Run 'running' until ranking finishes | |
| Separate ranking run with its own runs row | Ranking as its own run with its own `runs` row | |

**User's choice:** run completes first; detached ranking task.
**Notes:** user added *"I think we should also be able to filter out rankings/score which are below a threshold if needed."*

| Option | Description | Selected |
|--------|-------------|----------|
| View filter: hide below threshold on the queue | Minimum-score control filters the view; nothing destroyed | ✓ |
| View filter, but un-scored listings always stay visible | As above with explicit un-scored handling | |
| Treat low scores as exclusions, same as Phase 2 rules | Below-threshold listings recorded as `listing_exclusions` | |

**User's choice:** view filter (un-scored listings stay visible).

---

## Spend cap semantics & enforcement point

| Option | Description | Selected |
|--------|-------------|----------|
| Two caps (per-run + rolling 24h), either one refuses the call | Matches RANK-08's "per run and per day" wording exactly | ✓ |
| Per-run cap only; day limit as a derived read-out | Cap only the run; derive the day figure | |
| Token-based caps instead of call counts | Cap tokens rather than calls | |

**User's choice:** two caps (per-run + rolling 24h), either refuses.

| Option | Description | Selected |
|--------|-------------|----------|
| Reserve-then-call inside the ranking task, released on completion | `asyncio.Lock`-guarded in-flight counter; no migration | ✓ |
| Write a pending row before the call, update after | Persist `status='pending'` — requires a migration on the status CHECK | |
| Process-local counter, documented as single-worker-only | Counter only in-process with a documented ceiling | |

**User's choice:** reserve-then-call inside the ranking task, released on completion.

| Option | Description | Selected |
|--------|-------------|----------|
| Graceful stop, run reports ranked-X-of-Y and cap reason | Cap hit is a normal outcome; nothing lost; run not failed | ✓ |
| Same, plus one refusal row in llm_calls per refused call | As above, with an audit row per refusal | |
| Mark the run as failed when the cap is hit | Run marked failed on cap hit | |

**User's choice:** graceful stop, run reports ranked-X-of-Y and cap reason.

---

## Job detail view & queue integration

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated GET /listings/{id} full page | New full page reusing `read_row()`; the lawful home for SC-4 | ✓ |
| Expandable panel fragment inside the queue | HTMX fragment, no new route | |
| Detail page AND enrich the queue row with score + factor hint | Detail page plus a richer queue row | |

**User's choice:** dedicated `GET /listings/{id}` full page.

| Option | Description | Selected |
|--------|-------------|----------|
| Default sort by score DESC; row shows score + tier badge | Queue defaults to score order; row shows total + `confidence_tier` | ✓ |
| Add an explicit sort control: score / newest / relevance | Sort control matching the existing query-param pattern | |
| Score default, bm25 only while actively searching | Score default with bm25 preserved during search | |

**User's choice:** default sort by score DESC; row shows score + tier badge.

---

## Weight editing & re-derive

| Option | Description | Selected |
|--------|-------------|----------|
| Global weights on the settings page | One set of six weights in Settings | ✓ |
| Per-search weights in criteria_json | Weights per named search | |
| Global defaults + per-search override | Global defaults with per-search overrides | |

**User's choice:** global weights on the settings page.

| Option | Description | Selected |
|--------|-------------|----------|
| Compute totals on read from stored sub-scores | Weights are presentation; sub-scores are immutable facts | ✓ |
| Rewrite total_score rows when weights change | Recompute and persist totals on weight save | |
| Read-time compute plus an in-memory cache | Read-time compute with caching | |

**User's choice:** compute totals on read from stored sub-scores.

| Option | Description | Selected |
|--------|-------------|----------|
| One score row per listing per run; weights_json is an audit snapshot | Stored total is an audit snapshot, not the sort source | ✓ |
| Stored total stays authoritative; sort on the index | Sort on the stored `total_score` column and its index | |
| Store scoring-time total, also show current-weight total on detail | Two totals per row in the detail view | |

**User's choice:** one score row per listing per run; `weights_json` is an audit snapshot.

---

## Degraded / failure posture

| Option | Description | Selected |
|--------|-------------|----------|
| Ranking optional; ingest always succeeds unranked | LLM unreachable / no cv.yaml / disabled ⇒ run completes unranked, zero llm_calls | ✓ |
| Optional, plus a persisted run reason when ranking is skipped | As above, with a loud skipped reason on `/runs` | |
| Ranking failure fails the run | Run fails when the LLM is unreachable | |

**User's choice:** ranking optional; ingest always succeeds unranked.
**Notes:** this question was dismissed once and re-asked at the user's request, then answered.

| Option | Description | Selected |
|--------|-------------|----------|
| Per-listing failure isolated; task continues | Failed listing → `llm_calls` row, no scores row, task continues | ✓ |
| Same, and explicitly no extra retry loop in the ranking stage | As above, retries stay inside `llm/` | |
| Abort ranking after N consecutive failures | Stop early after repeated failures | |

**User's choice:** per-listing failure isolated; task continues.

---

## the agent's Discretion

- Exact prose wording of each factor definition in `app/domain/rubric.py`.
- Concrete Pydantic schema field names for the ranking response and requirement list.
- Score display precision/rounding.
- Exact `confidence_tier` boundaries.
- Concrete cap default values (as `Settings` fields).
- Ranking task lifecycle mechanics: startup recovery, re-run overlap handling.
- Where the "ranked X of Y" / cap-reason surface lives.
- Prompt assembly placement outside `llm/` and the `parts` composition.

## Deferred Ideas

- **User-supplied rubric override** (UI + storage) — deferred (D-83); must route through `parts` + `sanitize` when added.
- **Market-salary data source** for compensation — v2 / RANK-11 (D-90); Adzuna `/histogram` preferred over level.fyi.
- **RANK-09** (learns from save/skip history), **RANK-10** (listing-quality score separate from fit) — v2.
- **Live/streaming score updates** — unnecessary now; refresh suffices (D-88).
- **Per-search factor weights** — deferred (D-99).
- **In-memory caching of read-time totals** — premature at personal scale (D-100).
