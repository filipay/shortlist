# Roadmap: Shortlist

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
- [x] **Phase 3: LLM Port + Structured Output** - Any schema-constrained call works end to end through opencode, with the contract pinned (completed 2026-09-21)
- [x] **Phase 4: CV Fact Store + LaTeX Compile Spike** - The structured CV reproduces the base CV and Tectonic compiles the real `.tex` (runs in parallel with Phases 2–3) (completed 2026-09-21)
- [x] **Phase 5: Ranking — CORE VALUE** - One ranked, explained queue with per-factor breakdown and named gaps (completed 2026-09-24)
- [ ] **Phase 6: Tailoring + Verification** - A tailored, verified CV PDF, previewable and downloadable
- [x] **Phase 7: Assisted Apply + Tracker** - Apply package plus application tracking linked to the exact verified artefact (completed 2026-10-12)
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

**Plans:** 10/10 plans complete

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
- [x] 03-09-PLAN.md — Trust-boundary + audit sweep: the deny-rule contract pin, the audited 500 on a raising backend, and the clean re-ingest guard

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

**Plans:** 5/5 plans complete

Plans:
**Wave 1**

- [x] 04-01-PLAN.md — The two new dependencies (`pypdf`, `pyyaml`), behind a blocking human gate, plus the `latex` lane's default-lane exclusion

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 04-02-PLAN.md — Tracer: a committed `.tex` compiles to a real PDF offline through the engine port; the engine, its cache prime and its TeX Live fallback are configuration
- [x] 04-03-PLAN.md — The structured CV: fact store with stable enumerated IDs, deterministic render through one escape choke point, and the byte-exact golden file

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 04-04-PLAN.md — The fact-equivalence lane over extracted PDF text, with its mutation control, and the CV revision log

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 04-05-PLAN.md — The spike: bounded `.tex` import, the partial verdict with its real-document trigger, and the compile runbook

**Research flag:** highest research need — the real `.tex` is unavailable to research. The plan must contain a spike task on one section, a Tectonic bundle-coverage check, and a pdfTeX-primitive/bibliography check before Phase 6 is estimated.

**Resolution (recorded during planning, 2026-09-21):** the spike is planned as a **partial verdict plus a trigger** (D-62), not as a measurement. 04-05 ships the bounded importer, the executable spike script at `scripts/cv-tex-spike.sh`, and `docs/probes/2026-09-21-cv-tex-spike.md` with a `PARTIAL` marker and an `UNRESOLVED` section naming the exact command that closes it; STATE.md's blocking unknown #1 stays **open** and now points at that trigger. The bundle-coverage and pdfTeX-primitive checks are concrete runnable commands recorded in that document, and the `Dockerfile.texlive` fallback's availability is a one-off hand-run measurement (D-76) recorded there — or explicitly recorded as not yet taken. Two research corrections are carried into the plans: the `cv.yaml` shape lives in ARCHITECTURE §7.2 (not §7.3, which is the patch), and the renderer's template is application code in `app/latex/templates/` (not in the `cv/` volume, which stays purely the human's data).

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

**Plans:** 12/12 plans complete
**UI hint**: yes

Plans:

- [x] 05-07-PLAN.md

**Wave 1**

- [x] 05-01-PLAN.md — Tracer: pure rubric, top-level-scalar ranking schema, weights store (migration 0004), the `scores` writer, and one listing ranked end-to-end onto the queue row

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 05-02-PLAN.md — Spend caps enforced before the call (two `Settings` ceilings, rolling-24h ledger read, reserve-then-call) and the detached single-flight ranking lifecycle

**Wave 3** *(blocked on Wave 1 completion)*

- [x] 05-03-PLAN.md — Job detail page: score, per-factor breakdown with weights, grounded rationale, requirement-by-requirement fit list with named gaps

**Wave 4** *(blocked on Waves 1–3 completion)*

- [x] 05-04-PLAN.md — Weighted queue ordering (read-time total, unscored last), the minimum-score view filter, the weights editor, and the ranked-X-of-Y strip

**Gap closure** *(planned 2026-09-22; wave 1 — all prerequisites above are executed)*

- [x] 05-05-PLAN.md — The ranking strip reports one run's population: `RunSummary.candidate_count` (the run's own `reason_counts_json['survivors']`) replaces the request-derived page total, so the strip can no longer read "Ranked 30 of 5"
- [x] 05-06-PLAN.md — An unreadable (non-UTF-8) CV fact store takes the documented D-94 skip: one path-qualified `CvFactStoreError` at the read boundary, so the detached ranking task returns cleanly instead of leaking `UnicodeDecodeError`

**Gap closure — round 2** *(planned 2026-09-23 from the UAT diagnoses; wave 1 = 05-08, wave 2 = 05-09 and 05-10)*

- [x] 05-08-PLAN.md — G-05-1: the ranking outcome is persisted on the run (`reason_counts_json['ranking']`, written by `_finish`) and rendered, so the queue strip distinguishes running from skipped-and-why from not-attempted from ranked
- [x] 05-09-PLAN.md — G-05-1/G-05-2: the job detail page names the last run's real ranking state instead of hedging, and names the CV fact-store path when that is the skip reason
- [x] 05-10-PLAN.md — G-05-2: disclose the CV fact-store prerequisite — a `/settings` card naming the path and the supply steps, an unconditional queue status line, a `cv` object in `/health`, and the documented `cv.draft.yaml` → `cv.yaml` promotion

**Gap closure — round 3** *(planned 2026-09-23 from the ad-hoc UAT finding; wave 1)*

- [x] 05-11-PLAN.md — G-05-3: the queue's paging becomes two-way — `QueuePage` gains `has_prev`/`prev_offset`/`page_index`/`page_count`, the shared fragment renders a Previous / `Page X of Y (N per page)` / Next pager in place of the forward-only control, and the paging tests encode the two-way model (page size stays server-fixed, T-02-28)

**Gap closure — round 4** *(planned 2026-09-24 from the UAT diagnosis; wave 1)*

- [x] 05-12-PLAN.md — G-05-8: the detail page's Save/Hide become a real inline swap — one shared `_action_forms.html` for both surfaces, a `#detail-actions` section the events route re-renders for an allow-listed `surface=detail` origin, a saved/hidden indicator plus a link to the existing `/?saved=1` saved view, and the target-resolution regression tests the diagnosis says were missing

**Research flag — RESOLVED in the plans (2026-09-22):** batching is **one `complete_structured` call per listing, no sibling listings** (D-86), so scoring is absolute by construction rather than by prompt discipline; the budget cap is **reserve-then-call** with two independent `Settings` ceilings (per-run and rolling-24h over `SUM(llm_calls.created_at)`), refused *before* the request and released on completion (D-91/D-92); and requirement extraction is co-located **inside** the single ranking call (D-81), returning sub-scores and a structured requirement list in one response. Three CONTEXT claims were corrected against the tree and are carried into the plans: `llm_calls.created_at` is **not** indexed (a full scan is accepted, no index migration), `llm_calls` has **no `error_kind` column** (the cause is encoded in `error`), and `ix_scores_listing_total` is `(listing_id, total_score)` so it was never a cross-listing sort path. The blocking open question — where the live weights persist — is answered by **migration 0004 (`ranking_config`)**, which also updates the pinned Alembic head in `tests/db/test_migration_contract.py` and `tests/db/test_skeleton_boot.py`.

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

**Plans:** 11/11 plans executed (10 executed; 1 planned gap-closure), plus an unplanned round-5 gap-closure commit series (`da06178`/`3b3842b`/`5a667ec`) verified 2026-09-30

Plans:
**Wave 1**

- [x] 06-01-PLAN.md — Tracer: the real five-operation typed patch engine over enumerated IDs, the Layer-1 verification pre-check, the one `TailoringPatch` call with its shared 24h spend ceiling, the `cv_artifacts` writer, and the dedicated tailoring page's generate/compile/pdf path

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 06-02-PLAN.md — The verification gate complete: all ten §10.3 checks, region-scoped metric containment with date-like and page-number exclusion, the advisory grounding band, warn-not-block for checks 8/9, the block-don't-repair blocked-row contract, and the canary pin for the "no field becomes text in the PDF" guarantee
- [x] 06-03-PLAN.md — Review before compile: the tailored CV's HTML preview beside the change log with every drop and demotion explicit, the rank-first precondition, and the stale-patch optimistic-concurrency guard

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 06-04-PLAN.md — Blocked artifacts are unreachable: the `ok`-only repository selection, inline preview and `?download=1` attachment, the PITFALLS-P14 failure-path suite, and the blocked-findings surface with no repair affordance

**Gap closure** *(planned 2026-09-24 from `06-VERIFICATION.md` (`gaps_found`, 5/6); wave 1 — all prerequisites above are executed)*

- [x] 06-05-PLAN.md — CR-01/WR-03: check 4's region and allow-set construction is corrected (region-local date, page-number and non-entry-structured exclusion), so a valid CV whose trailing structured content carries a digit is verifiable and downloadable again and one entry's dates can no longer excuse a token in another region; `VERIFIER_VERSION` records the change
- [x] 06-06-PLAN.md — WR-02: bullet ops are grounded on the bullet-id set (and `reorder_section` on the section-id set) at the validation boundary, so a non-bullet id raises `UnknownIdError` instead of no-opping and emitting a phantom change-log entry
- [x] 06-07-PLAN.md — WR-01: `POST /listings/{id}/cv/compile` honours `tailoring_enabled`, refusing with the shared skip vocabulary before any filesystem read, render, compile or artifact row

**Gap closure (round 2)** *(planned 2026-09-24 from `06-VERIFICATION.md` (`human_needed`) + `06-REVIEW.md` (2 critical, 1 warning); wave 1 — all prerequisites above are executed)*

- [x] 06-08-PLAN.md — CR-01/CR-02: check 4 grounds an entry's digit-bearing location in its own region and anchors each region on its own entry header line (org AND title), so an ordinary CV whose location carries a digit, or whose bullet names a later employer, verifies and is previewable/downloadable again; `VERIFIER_VERSION` recorded once for the combined change
- [x] 06-09-PLAN.md — WR-01: a raised `complete_structured` transport error still writes exactly one `llm_calls` audit row (exception class only) and surfaces as the generate route's typed 502 `tailoring_failed` refusal instead of a bare 500, with the shared in-flight slot released

**Gap closure (round 3)** *(planned 2026-09-25 from `06-VERIFICATION.md` (`gaps_found`, 9/12) + the orchestrator's binding criteria A–E; wave 1 — all prerequisites above are executed)*

- [x] 06-10-PLAN.md — CR-01 residual / ESC-06-A + WR-01 / ESC-06-B: check 4's region anchor is replaced by a structural date-adjacency discriminator a body bullet cannot satisfy, and an unanchorable region fails closed as a visible `warn` instead of a silent skip, so a valid CV whose earlier bullet names a later entry's org AND title verifies and a fabricated digit in an unscopeable region is no longer invisible; `VERIFIER_VERSION` recorded once at 1.0.3

**Gap closure (round 4)** *(planned 2026-09-25 from `06-VERIFICATION.md` (`gaps_found`, 11/12) + `06-REVIEW.md` (1 warning, WR-02); wave 1 — all prerequisites above are executed)*

- [x] 06-11-PLAN.md — WR-02 residual / criterion E: check 4's region start must BEGIN with the entry's org (the template emits org first) and an anchored region's end is bounded at a later unanchored entry's lone date-range line, so a valid CV whose earlier bullet co-locates a later entry's org, title AND date-range no longer false-fails and an extractor line-merge yields a visible `warn` instead of a false fail; the false docstring absolute is replaced by an explicit residual; `VERIFIER_VERSION` recorded once at 1.0.4

**Gap closure (round 5)** *(planned 2026-09-30 from `06-VERIFICATION.md` (`gaps_found`, 15/18) + `06-REVIEW.md` (3 info); no plan file — executed as direct fix commits, wave 1 — all prerequisites above are executed)*

- [x] 06-12 (no plan file) — truths 6 / 15: check 4's region anchor now requires the template's org/title separator (`_dash_fold` keeps one hyphen per folded dash run, so `-`, `--`, `---`, en- and em-dash all satisfy; a candidate line must start with `org_dash + '-'`), so an earlier entry's bullet carrying a later entry's org+title+dates can no longer hijack that region; the gate is monotone-stricter (it can only refuse an anchor) so a real header losing its separator degrades to a visible `warn`, never a silent skip. The two falsified absolute docstrings are replaced and the full-header reproduction is pinned by a test as the documented hard-fail ceiling; `VERIFIER_VERSION` recorded once at 1.0.5 (commits `da06178` / `3b3842b` / `5a667ec`). Independent scoped review returned clean (0 Critical / 0 Warning / 5 Info, all resolved) and satisfied criterion E; independent verification returned 17/18 with `gaps_remaining: []` and `regressions: []`, leaving only the two container-only Tectonic UAT items open

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

**Plans:** 14/14 plans complete; 4 gap-closure plans executed (2026-10-05); CR-01 gap-closure plan 07-10 planned (2026-10-06); UAT gap-closure plans 07-11/07-12 planned (2026-10-12); re-verification gap-closure plans 07-13/07-14 planned (2026-10-12)
**UI hint**: yes

Plans:
**Wave 1**

- [x] 07-01-PLAN.md — Tracer: record an application and see it in the tracker with its append-only history (migration 0006, `application_repo`, `/applications`)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 07-02-PLAN.md — The apply package page: the `ok`-artefact gate, the outbound link, the gap checklist, and the no-submit guarantee
- [x] 07-03-PLAN.md — Grounded screening-answer drafting: the typed contract, the deterministic grounding check, the persisted drafts, and the one LLM call on the shared ceiling
- [x] 07-04-PLAN.md — Tracker slice-and-dice: stage filter, needs-action view, free-text search, and pagination

**Wave 3** *(blocked on Waves 1–2 completion)*

- [x] 07-05-PLAN.md — The drafted-answers surface: the question list, the package-page region, the draft action, and copy-to-clipboard

**Gap closure** *(planned 2026-10-05 from `07-UAT.md` `status: diagnosed`: G-07-1, G-07-2, G-07-3, G-07-4; wave 1 = 07-06/07-08/07-09, wave 2 = 07-07)*

- [x] 07-06-PLAN.md — G-07-2: coerce the recorded non-list screening payload shapes in the schema (so `_salvage` stops re-raising on `list_type` and the drafted answers are preserved) and split the unusable-response refusal from the genuinely-empty one, with a golden-payload fixture
- [x] 07-07-PLAN.md — G-07-3: persist the grounding warnings and the advisory band (migration 0007) and render them, so a flagged answer names its specific offender and the band surfaces as advisory only (UI-SPEC amendment)
- [x] 07-08-PLAN.md — G-07-1: the record route returns a 303 to `/applications` for the plain-form submit, so the user lands on the full styled tracker instead of a bare fragment, with the missing regression test
- [x] 07-09-PLAN.md — G-07-4: the CV PDF route takes an optional, listing-scoped artifact id and the compile banner stops duplicating the Latest CV control, so each download affordance serves the artifact it labels

**Gap closure — CR-01** *(planned 2026-10-06 from `07-VERIFICATION.md` `gaps:`: a partial drafting response must not delete unanswered stored drafts)*

- [x] 07-10-PLAN.md — CR-01: refuse a valid-but-partial drafting response with `drafting_partial` before `replace_for_listing` deletes the listing's rows, so unanswered ad-hoc questions survive, with the seeded-rows regression test

**Gap closure — UAT round 2** *(planned 2026-10-12 from `07-UAT.md` `status: diagnosed`: G-07-5, G-07-6, G-07-7; wave 1 = 07-11/07-12)*

- [x] 07-11-PLAN.md — G-07-5/G-07-6: the tracker note wraps and its phase-scoped action cell stacks full-width forms, so the notes column no longer forces a horizontal scroll and `dd/mm/yyyy` cannot paint over `Update status`, with the layout-contract regression
- [x] 07-12-PLAN.md — G-07-7: one shared unwrap helper absorbs the model's single-key array wrapper (`{"item": ...}`) on every list-typed wire field, so `Draft answers` persists usable answers, with the literal captured payload held out and every malformed shape still failing loudly

**Gap closure — re-verification** *(planned 2026-10-12 from `07-VERIFICATION.md` `status: gaps_found` + `07-REVIEW.md`: CR-01, WR-01; wave 1 = 07-13/07-14)*

- [x] 07-13-PLAN.md — CR-01: backfill the 33 template component rules into `assets/tailwind/input.css`, regenerate and commit `static/vendor/app.css` with the pinned Tailwind 4.3.3 CLI, and guard the build (source coverage + byte-identity), so the Docker image stops shipping an unstyled tracker/apply/detail/settings UI
- [x] 07-14-PLAN.md — WR-01: restrict the wire wrapper unwrap to the literal `"item"` key, bound the loop, and replace the two scalar-value tests with unknown-key-with-a-list-value cases, so code, docstrings and tests agree and the failure class — not an instance — is pinned (also closes IN-01/IN-02)

### Phase 07.1: Migrate the LLM backend to the opencode V2 HTTP API (INSERTED)

**Goal:** The app's LLM backend speaks the opencode V2 HTTP API, so ranking, tailoring, screening-answer drafting and CV fact extraction work again — while the retained V1 surface keeps working (dual-support with runtime detection). Trigger: the pinned V1 contract is dead on opencode 2.0.26 (legacy root routes serve SPA HTML, `POST /session` is a hard 405, every LLM call fails with `JSONDecodeError`).
**Requirements**: D-135, D-136, D-137, D-138, D-139, D-140, D-141, D-142, D-143, D-144, D-145, D-146, D-147, D-148, D-149, D-150 (CONTEXT decisions; ROADMAP lists no REQ ids for this inserted phase)
**Depends on:** Phase 7
**Plans:** 6 plans
**Out of scope:** any new user-facing capability (the Settings model picker is a separate phase).

Plans:
**Wave 1**

- [ ] 07.1-01-PLAN.md — Tracer: one V2 schema-constrained completion end-to-end — the V2 contract group, V2 builders, surface detection, the generate arm, the client-side schema-retry loop, and the auth fail-fast (D-136/D-139/D-140/D-141/D-142/D-147/D-148)
- [ ] 07.1-02-PLAN.md — The health/auth surface: `auth_configured` on `/health` and the queue's "auth missing" status line (D-136/D-137/D-138)

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 07.1-03-PLAN.md — The contract fixture rebuilt as the V2 slice, the V2 snapshot assertions, and the raw-text negative control (D-147/D-148/D-149/D-150)
- [ ] 07.1-04-PLAN.md — Discovery retargeted to `GET /api/model` + `GET /api/provider` with redaction preserved, plus the cold-start retry (D-143/D-144/D-146)

**Wave 3** *(blocked on Waves 1–2 completion)*

- [ ] 07.1-05-PLAN.md — The operator live lanes retargeted to `/openapi.json` + `/api/info` and the real positive/negative `generate` check, plus the selftest's contract-agnostic success signal (D-135/D-144/D-145/D-150)
- [ ] 07.1-06-PLAN.md — The operator documentation: the V2 runbook, `.env.example`, README, and the `AGENTS.md` security note recording the accepted residual prompt-injection risk (D-135/D-138/D-150)

**Notes:** `POST /api/session/{id}/generate` is chosen for the completion call because it has no tool-execution surface (unlike `/api/session/{id}/prompt`). The V2 spec's declared `security: []` is not honoured by the running server — every `/api/*` call is authenticated. `TOLERATED_SCHEMA_ERRORS` and `_salvage` stay byte-identical (D-142). The residual prompt-injection risk from V2's missing `system` field is accepted and documented, to be revisited in a later phase.

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
| 3. LLM Port + Structured Output | 10/10 | Complete    | 2026-09-21 |
| 4. CV Fact Store + LaTeX Compile Spike | 5/5 | Complete    | 2026-09-21 |
| 5. Ranking — CORE VALUE | 12/12 | Complete    | 2026-09-24 |
| 6. Tailoring + Verification | 11/11 | In Progress|  |
| 7. Assisted Apply + Tracker | 14/14 | Complete    | 2026-10-12 |
| 8. Operations + Polish | 0/0 | Not started | - |

---
*Roadmap created: 2026-09-15 from `research/SUMMARY.md` §Implications for Roadmap and `research/ARCHITECTURE.md` §14.3. Coverage: 74/74 v1 requirements mapped.*
