# Roadmap: Job Search Copilot

## Overview

This roadmap delivers the Core Value directly: every morning one ranked, explained,
apply-ready queue of jobs worth considering. It derives its structure from
`research/ARCHITECTURE.md` §14.3 — a modular monolith built in dependency order, where
the data model that describes the past (migration 0001) ships first because it cannot be
backfilled, and both blocking unknowns are retired early as *measurements*: the
scraper-survival probe in Phase 1 and the real-`.tex`/Tectonic spike in Phase 4. Two
non-obvious orderings are honoured. **Ranking (Phase 5) precedes tailoring (Phase 6)**,
because tailoring consumes the requirement gaps the ranking pass produces and ranking
*is* the Core Value. **Phase 4 runs in parallel with Phases 2–3**, because the CV fact
store is a shared prerequisite of ranking and tailoring and carries the project's largest
unquantified cost. Every phase ships something a user can actually do — the walking
skeleton keeps walking.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Walking Skeleton + Foundations** - A scraped listing exists in the DB, is browsable, and the stack runs locally; the scraper-survival probe is answered (completed 2026-09-15)
- [x] **Phase 2: Clean, Filtered, Queryable Queue** - No duplicates; hard rules applied with recorded reasons; runs observable (completed 2026-09-17)
- [ ] **Phase 3: LLM Port + Structured Output** - Any schema-constrained call works end to end through opencode, with the contract pinned
- [ ] **Phase 4: CV Fact Store + LaTeX Compile Spike** - The structured CV reproduces the base CV and Tectonic compiles the real `.tex` (runs in parallel with Phases 2–3)
- [ ] **Phase 5: Ranking — CORE VALUE** - One ranked, explained queue with per-factor breakdown and named gaps
- [ ] **Phase 6: Tailoring + Verification** - A tailored, verified CV PDF, previewable and downloadable
- [ ] **Phase 7: Assisted Apply + Tracker** - Apply package plus application tracking linked to the exact verified artefact
- [ ] **Phase 8: Operations + Polish** - Scheduled runs, source health in the UI, responsive interface

## Phase Details

### Phase 1: Walking Skeleton + Foundations

**Goal**: A listing scraped from LinkedIn and Indeed exists in the DB and is browsable in the running app, on a skeleton whose non-backfillable foundation is already correct.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: SRC-01, SRC-02, SRC-03, SRC-04, SRC-05, SRC-06, SRC-07, SRC-08, SRC-09, SRC-10, QUEUE-01, QUEUE-02, QUEUE-05, RUN-01, RUN-02, PLAT-01, PLAT-03, PLAT-04, UI-07
**Success Criteria** (what must be TRUE):

  1. User can start the whole stack with one `docker compose up`, open the queue UI in a browser, and see listings that persist across a restart.
  2. User can trigger a LinkedIn search and an Indeed search and see both boards' results in one normalised listing shape.
  3. Re-running a search never creates a duplicate row for the same listing on the same source.
  4. Per-source health (last success, listings returned, field fill-rate) and a probe that detects silent breakage are observable, and the probe yields a recorded verdict on whether LinkedIn/Indeed survive at personal scale (re-ranking Adzuna from hedge to primary if they do not).
  5. The app exposes no credential path anywhere (public logged-out pages only), every API route answers through the `current_user` seam, and the domain-import-discipline test passes.

**Plans:** 7/7 plans complete

Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Walking skeleton: migrate, boot, browse; the one-way migration 0001 and the deployment path

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — Migration 0001 acceptance checklist as assertions, PII-negative schema, FTS5 trigger proof
- [x] 01-03-PLAN.md — LinkedIn ingest slice: adapter port, sanitise/normalise, two-key upsert, `run_pipeline()`, run trigger + poll

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-04-PLAN.md — Indeed adapter with the Ireland guard, adapter extensibility proof, capability warnings, domain import discipline
- [x] 01-05-PLAN.md — Sanitise hardening (PII/HTML/truncation) + no-credential, no-CDN, auth-seam, config guards
- [x] 01-06-PLAN.md — Cached liveness probe, boot-tolerant `/health`, per-source health strip, opencode discovery redaction

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 01-07-PLAN.md — Survival signals S1–S6 + Adzuna condition, the dated probe verdict, and the operator compose smoke

**Migration 0001 acceptance checklist (non-backfillable — `ARCHITECTURE.md` §9.4 / `PITFALLS.md` P8).** These fields describe the past and cannot be invented later; this checklist is the Phase 1 schema contract:

  1. `listings.first_seen_at`, `last_seen_at`, `content_hash` all `NOT NULL`
  2. `listing_events` exists and is **append-only** (the feedback-loop input, captured now, learned later)
  3. `scores.factor_scores_json` + `weights_json` + `criteria_version` exist — **not `total_score` alone**
  4. `cv_artifacts.verification_json` exists and `compile_status` can be `'blocked'`
  5. `applications.cv_artifact_id` exists (the verified-artifact ↔ outcome link)
  6. Partial unique index on `(source, source_listing_id)` **and** unconditional `(source, canonical_url)` index
  7. `sources.capabilities_json` + `sources.tos_audited_at` exist
  8. `listings.blocking_key` exists and is indexed
  9. Alembic at revision 0001, `alembic upgrade head` exercised in the container build

**Research flag:** scraper-survival probe design (a measurement, not a reading — needs an explicit probe + instrumentation task because the result re-ranks Adzuna); concrete opencode pinning/health wiring for compose.

### Phase 2: Clean, Filtered, Queryable Queue

**Goal**: A deduplicated, deterministically filtered, searchable queue the user trusts — with every rejection explained and every run observable.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: QUEUE-03, QUEUE-04, QUEUE-06, QUEUE-07, QUEUE-08, QUEUE-09, CRIT-01, CRIT-02, CRIT-03, FILT-01, FILT-02, FILT-03, FILT-04, RUN-03, RUN-04
**Success Criteria** (what must be TRUE):

  1. User can browse a deduplicated queue where the same job found on two sources appears once, with a merge rate and the rows behind it visible, and can revert an incorrect merge.
  2. User can see, for any excluded listing, which rule fired and why.
  3. User can create, edit, enable/disable, and delete named search criteria, and tune filter rules from the UI without a code change; past runs stay reproducible against a criteria version.
  4. User can full-text search the queue, save or hide a listing (recorded as append-only events), and see which listings are new since last visit and which look stale.
  5. User can see a run history in which each run records what it did, what it found, and — when the queue is empty — why.

**Plans**: 11/11 plans complete

- [x] 02-01-PLAN.md
- [x] 02-02-PLAN.md
- [x] 02-03-PLAN.md
- [x] 02-04-PLAN.md
- [x] 02-05-PLAN.md
- [x] 02-06-PLAN.md
- [x] 02-07-PLAN.md
- [x] 02-08-PLAN.md
- [x] 02-09-PLAN.md
- [x] 02-10-PLAN.md
- [x] 02-11-PLAN.md

**Notes:** Leave dedup threshold θ as a **setting plus a tuning task** against the first real corpus, not a frozen constant (the 10–15% merge-rate band is from a different market and query shape). Extend `domain/sanitize.py` with an `_INJECTION_PATTERNS`-style rule set (pattern-copied from Resume-Matcher's `improver.py`, attributed per Apache-2.0 §4). The criteria compiler consumes each adapter's declared capabilities so an unsupported filter is reported, not silently ignored (SRC-09).

### Phase 3: LLM Port + Structured Output

**Goal**: Any schema-constrained LLM call works end to end through `opencode serve` as a sibling service, with the structured-output contract pinned by a failing test.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: PLAT-02, PLAT-05
**Success Criteria** (what must be TRUE):

  1. The app completes a schema-validated structured call through the opencode backend with no second provider key configured.
  2. A schema violation is recorded as an explicit, retried run outcome rather than a silent failure.
  3. A CI contract test reads the installed server's `GET /doc` and fails loudly if the structured-output field name changes — resolving and pinning the `format` vs `outputFormat` ambiguity.
  4. Untrusted listing text reaches the model only as user content (never the system prompt) and tools are disabled by default.

**Plans:** 8/9 plans executed (7 executed, 2 gap-closure pending)

Plans:
**Wave 1**

- [x] 03-01-PLAN.md — Tracer: a schema-constrained call completes through the port, and the operator can run it

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 03-02-PLAN.md — The pinned `/doc` contract: default-lane snapshot + operator live diff
- [x] 03-03-PLAN.md — Schema-violation degradation: explicit, retried outcomes + salvage
- [x] 03-04-PLAN.md — Per-call telemetry: migration 0003 `llm_calls.server_version` + the audit writer
- [x] 03-05-PLAN.md — Ceilings are configuration: Settings guards, compose passthrough, `.env.example`

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 03-06-PLAN.md — Trust boundary: tools denied by default, system prompt constant, import discipline
- [x] 03-07-PLAN.md — The finding recorded and the counter seam

**Gap closure** *(planned 2026-09-18; wave 1 — all prerequisites above are executed)*

- [x] 03-08-PLAN.md — Backend contract correctness: the retry ceiling defaults to Settings, the tool-grant channel is wired, and a non-parseable structured payload keeps its identity and observation
- [ ] 03-09-PLAN.md — Trust-boundary + audit sweep: the deny-rule contract pin, the audited 500 on a raising backend, and the clean re-ingest guard

**Research flag:** resolve the `format` vs `outputFormat` field name against the user's own running server; plan the `/doc` contract test as a deliverable, not an assumption.
**Resolution (recorded during planning, 2026-09-17):** the field is **`format`** and the validated
payload arrives at **`info.structured`** (not `info.structured_output`) — both verified against the
live opencode 1.18.31 `/doc`. Plan 03-02 pins both, with a committed snapshot, a default-lane
negative control, and an operator live diff. `ARCHITECTURE.md` §6.2 and `STACK.md` §Q7 are
wire-inaccurate on the response name; plan 03-02 carries the correction into the runbook.

### Phase 4: CV Fact Store + LaTeX Compile Spike

**Goal**: `cv.yaml` exists and reproduces the human's CV fact-for-fact, and Tectonic compiles the real `.tex` inside the container — retiring the project's largest unquantified cost.
**Mode:** mvp
**Depends on**: Phase 1
**Runs in parallel with**: Phases 2–3 (per `ARCHITECTURE.md` §14.3). Do not serialise this behind the queue phases — the CV fact store is a shared prerequisite of ranking and tailoring, and doing this late means discovering a decomposition/Tectonic blocker at Phase 6 after the roadmap has promised a tailoring phase.
**Requirements**: CV-01, CV-02, CV-03, CV-04, CV-05, CV-06
**Success Criteria** (what must be TRUE):

  1. The CV is modelled as structured data with stable, enumerated IDs, and a golden reproduction test proves the base CV renders fact-equivalent (all orgs, titles, dates, bullet token-shingles present) from it.
  2. The human-authored LaTeX CV is never modified by the tool, and user content is escaped so it cannot break or corrupt the document.
  3. The container compiles LaTeX to PDF offline via Tectonic, with the engine selectable as configuration and a `Dockerfile.texlive` fallback available.
  4. The spike on the real `.tex` produces a written verdict on whether the document decomposes into `cv.yaml` and whether Tectonic's bundle covers its preamble — with the hand-authored `cv.yaml` fallback recorded if it does not.

**Plans**: TBD

**Research flag:** highest research need — the real `.tex` is unavailable to research. The plan must contain a spike task on one section, a Tectonic bundle-coverage check, and a pdfTeX-primitive/bibliography check before Phase 6 is estimated.

### Phase 5: Ranking — CORE VALUE

**Goal**: One ranked, explained queue: every surviving listing scored against the user's CV with named factors, stored sub-scores, a grounded rationale, and named gaps.
**Mode:** mvp
**Depends on**: Phases 2, 3, 4
**Requirements**: RANK-01, RANK-02, RANK-03, RANK-04, RANK-05, RANK-06, RANK-07, RANK-08, UI-01, UI-02, UI-03
**Success Criteria** (what must be TRUE):

  1. User can browse ranked jobs in a list where every listing is scored against their CV using named, inspectable factors, with per-factor sub-scores stored and the total computed in code.
  2. Re-running ranking gives the same listing a stable, absolute score — never a relative ranking of a batch.
  3. User can adjust factor weights from the UI and see rankings re-derive without a new LLM call.
  4. Opening a job detail shows a rationale grounded in stored evidence plus a requirement-by-requirement fit breakdown with named gaps.
  5. Once the per-run or per-day LLM spend cap is reached, further calls are refused before the call is made.

**Plans**: TBD
**UI hint**: yes

**Research flag:** the per-listing vs per-K-listings batching decision is unresolved and material; resolve it *in the plan*, together with the budget-cap semantics (enforce before the call, count in-flight calls). Also settle where requirement extraction happens (once per listing, cached) here, not in Phase 6.

### Phase 6: Tailoring + Verification

**Goal**: A tailored, verified CV PDF the user can preview and download — shipped with its verification gate, never before it.
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: TAIL-01, TAIL-02, TAIL-03, TAIL-04, TAIL-05, TAIL-06, TAIL-07, TAIL-08, UI-05
**Success Criteria** (what must be TRUE):

  1. User can generate a CV tailored to a specific listing, expressed as a typed patch (move / reweight / demote / drop / reorder) over enumerated IDs, with no free-text field on the path to the PDF and bullet text immutable.
  2. User can preview the tailored CV and its change log — including anything dropped and the reason — before compiling.
  3. The verification gate checks the compiled PDF for unsupported content, including metric containment (`_novel_numbers`-equivalent, with date-like-number exclusion).
  4. A CV that fails verification is blocked: it cannot be downloaded or attached, and the tool never auto-repairs it ("repair pressure is fabrication pressure").

**Plans**: TBD
**UI hint**: yes

**Research flag:** the verifier's 10-check list is designed in research rather than sourced; the plan should design/validate the checks (no-new-entity, metric containment, bullet conservation) against fixtures before execution. Adopt `_GROUNDING_REVIEW_THRESHOLD`-style similarity banding to inform confidence tiers and verifier check 6. Adopt `_verify_original_matches`-style optimistic concurrency as the guard on `apply_patch` and artifact persistence.

### Phase 7: Assisted Apply + Tracker

**Goal**: An apply package per listing plus an application tracker that links every outcome to the exact verified CV artefact that was sent.
**Mode:** mvp
**Depends on**: Phase 6
**Requirements**: APPLY-01, APPLY-02, APPLY-03, APPLY-04, APPLY-05, APPLY-06, UI-04
**Success Criteria** (what must be TRUE):

  1. User can open an apply package for a listing containing the verified PDF, the apply link, drafted screening answers, and a gap checklist.
  2. The tool never submits an application on the user's behalf.
  3. User can record an application with a status stage, notes, and a next-action date/deadline, and every application links to the exact verified CV artefact that was sent.
  4. Application status changes are recorded as an append-only event history the user can view and manage.

**Plans**: TBD
**UI hint**: yes

### Phase 8: Operations + Polish

**Goal**: A scheduled, self-reporting, responsive tool — once the pipeline is trustworthy enough that a cron job will not simply hide failures.
**Mode:** mvp
**Depends on**: Phase 7
**Requirements**: RUN-05, RUN-06, RUN-07, PLAT-06, UI-06
**Success Criteria** (what must be TRUE):

  1. User can schedule recurring runs and see when the next run will happen.
  2. Scheduled runs persist across restarts and execute only once with a single worker.
  3. User can check system and source health from a health endpoint surfaced in the UI, with source status surfaced from recorded stop signals rather than auto-escalation.
  4. The UI is usable from both a laptop and a phone browser, with all assets vendored locally and no CDN dependency.

**Plans**: TBD
**UI hint**: yes

**Notes:** Scheduling is deliberately late — manual "run now" is the right trigger until the pipeline is trustworthy. The Adzuna adapter (v2, SRC-11) remains a contingent hedge: promote it here only if the Phase 1 probe verdict says LinkedIn/Indeed do not survive. "Also seen on", export, and batched notification are v2 and out of this phase's requirement scope.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8
Note: Phase 4 executes **in parallel** with Phases 2–3, not after Phase 3.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Walking Skeleton + Foundations | 7/7 | Complete    | 2026-09-15 |
| 2. Clean, Filtered, Queryable Queue | 11/11 | Complete    | 2026-09-17 |
| 3. LLM Port + Structured Output | 8/9 | In Progress|  |
| 4. CV Fact Store + LaTeX Compile Spike | 0/0 | Not started | - |
| 5. Ranking — CORE VALUE | 0/0 | Not started | - |
| 6. Tailoring + Verification | 0/0 | Not started | - |
| 7. Assisted Apply + Tracker | 0/0 | Not started | - |
| 8. Operations + Polish | 0/0 | Not started | - |

---
*Roadmap created: 2026-09-15 from `research/SUMMARY.md` §Implications for Roadmap and `research/ARCHITECTURE.md` §14.3. Coverage: 74/74 v1 requirements mapped.*
