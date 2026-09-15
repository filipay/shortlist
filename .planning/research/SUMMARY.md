# Project Research Summary

**Project:** Job Search Copilot
**Domain:** Local, self-hosted AI-assisted job-search pipeline (aggregation → deterministic filter → LLM ranking → LaTeX CV tailoring → assisted apply → tracker)
**Researched:** 2026-09-15
**Confidence:** MEDIUM-HIGH

## Executive Summary

This is a **local, single-user-first, Python/Docker** application that replaces the daily manual loop of checking job portals, judging fit, and hand-editing a CV with one ranked, explained, apply-ready queue. Experts build this class of tool as a **modular monolith with strict internal ports**: a pluggable source-adapter layer (JobSpy for LinkedIn/Indeed, Adzuna as a legal free hedge), a deduped SQLite listing store, a deterministic hard-rule filter that runs *before* any LLM spend, a two-stage ranking pass (LLM emits per-factor scores → code computes the weighted sum), a structured CV fact store with stable IDs, a deterministic LaTeX renderer compiled by Tectonic, and a **verification gate that blocks rather than repairs** fabricated content. Everything runs in one Docker container with `opencode serve` as a sibling service — no second LLM provider key.

The research strongly validates the project's three central decisions. **Assisted apply, not auto-submit**: the most-starred auto-applier in the ecosystem (AIHawk) had its contributors banned by LinkedIn and removed LinkedIn automation entirely, and independent 2026 reviews document 25–40% silent delivery failure in commercial auto-appliers. **Filter before LLM spend**: the field universally skips this, and it is both the cost gate and the first layer of explainability. **Never fabricate**: prompt-level guardrails alone still left a fabricated claim in 50% of outputs in a controlled 180-run study — the fix is structural (enumerated IDs in the schema, no free-text on the path to the PDF) plus a text-level verifier over the compiled output, shipped together.

The recommended build is the eight-phase order from `ARCHITECTURE.md` §14.3, whose two non-obvious features are that **ranking precedes tailoring** (tailoring consumes the requirement gaps the ranking pass produces) and that the **CV fact store + LaTeX compile spike runs in parallel with Phases 2–3**, because it carries the project's largest unquantified cost. The two blocking unknowns are both *measurements, not readings*: (1) the real `.tex` is **not in this repository**, so `.tex → cv.yaml` import cost and Tectonic bundle coverage are unmeasured — a Phase-4 hard gate that must be spiked on one section before the tailoring phase is estimated; (2) **LinkedIn/Indeed scrape survival at personal scale is unmeasured** — a Phase-1 probe must answer it, and the answer determines whether Adzuna is promoted from hedge to primary source. Design for blocking on both boards; the JobSpy README's claim that "Indeed has no rate limiting" is contradicted by the same README and by third-party evidence, and must not be trusted.

## Key Findings

### Disagreements Resolved (read this before planning)

The four source documents deliberately surfaced conflicts rather than silently reconciling them. Every one is resolved or explicitly framed below.

| # | Conflict | Resolution |
|---|----------|------------|
| **D1** | **"CV source of truth"** — `PROJECT.md` says the `.tex` is the source of truth; `STACK.md` Q6 says model the CV as structured data (`cv.yaml`) with stable IDs. | **Two-canonical-documents model** (`ARCHITECTURE.md` §7.1, `PITFALLS.md` P11). `cv/base.tex` is the **human's** canonical document — hand-authored, immutable by the tool. `cv/cv.yaml` is the **machine's** derived fact store — the only input to the patch engine. `artifacts/<id>/cv.tex` is a rendered derivative, never edited. The derivation is made verifiable by a **golden reproduction test**: render the base CV from `cv.yaml` with an identity patch, extract text from both PDFs, assert fact-equivalence (all orgs, titles, dates, bullet token-shingles present). Byte-equality is *not* required. Fail the build on drift (CV-R2). The phrase "source of truth" must never appear in the codebase without a qualifier. |
| **D2** | **Tier-1 dedup key** — `STACK.md` Q4 specifies `UNIQUE(source, source_listing_id)` as "the upsert key. Never insert twice." | **Keep the constraint, add a mandatory fallback.** JobSpy's own docs type `id` as `str \| None`; SQLite permits unlimited NULLs in a UNIQUE index, so the key silently degrades to "insert everything" on any board that omits `id`. Implement a **partial unique index** on `(source, source_listing_id) WHERE source_listing_id IS NOT NULL` **plus an unconditional unique index** on `(source, canonical_url)` (`ARCHITECTURE.md` A2/§8.1, `PITFALLS.md` P3/m9). |
| **D3** | **LinkedIn and Indeed as adapters** — `STACK.md` Q1 treats JobSpy as "the acquisition layer"; two boards could become one adapter class. | **One adapter per board, one shared transport** (`ARCHITECTURE.md` A3/§5.3). LinkedIn and Indeed are two `JobSource` implementations sharing `sources/_jobspy_transport.py`. Never call JobSpy once with `site_name=["linkedin","indeed"]` — one call means one failure domain, no per-board capability, budget, health, or `first_seen_at` attribution, and no per-board escalation path. |
| **D4** | **Ranking vs tailoring order** — `PROJECT.md` lists tailoring before ranking in its requirement order. | **Ranking (Phase 5) precedes tailoring (Phase 6).** Tailoring consumes the requirement gaps and fit factors produced by the ranking pass, and ranking *is* the Core Value (`ARCHITECTURE.md` §14.3). |
| **D5** | **opencode structured-output field name** — SDK code example says `format`; server API prose says `outputFormat` (`STACK.md` Q7). | **Unresolved by research; resolve against your own server.** Read field names from `GET /doc` on the installed version and write a **contract test** that asserts the field still exists. Treat the code example as authoritative but do not guess. This is the single highest-value 30 minutes in the LLM integration. |
| **D6** | **JobSpy reliability claim** — its README says "Indeed is the best scraper currently with no rate limiting" while the same README says "all of the job board sites are aggressive with blocking." | **Unresolved; treat as LOW confidence.** The second statement and third-party evidence (Cloudflare bot management, datacenter-IP blocking) contradict the first. **Design for blocking on both boards.** |
| **D7** | **Indeed Publisher API shutdown year** — sources say 2023 vs 2024. | **Year unresolved; decision unaffected.** No self-serve read API exists either way; the direction of travel is unambiguous. |
| **D8** | **AIHawk licence** — GitHub API now reports MIT; earlier README/third-party sources say AGPL-3.0. | **Verify the repo's `LICENSE` file before copying anything.** Use `invisible-playwright` as a scraping dependency if needed; never use AIHawk as an application engine (it pivoted away from job application entirely and now requires an OpenRouter key). |
| **D9** | **Greenfield vs reuse** — prior art is rich; `STACK.md` Q2 recommends greenfield *conditionally*. | **Conditional greenfield:** run a 1–2 day Resume-Matcher spike (point it at a local model; ask whether its tailoring engine can be driven by opencode and its output path replaced with LaTeX). If yes, the roadmap changes substantially; if no (likely), build — reusing three specific things: JobSpy, Tectonic, and TailorCV's anti-fabrication design pattern. |
| **D10** | **Ranking call shape** (`STACK.md` Open Q7) — one LLM call per listing vs one call per K listings. | **Unresolved and material.** It changes cost, timeout design, and whether `prompt_async` + SSE progress is required. **Resolve in the Phase-5 plan, not its execution** (`FEATURES.md` Gap 1, `PITFALLS.md` P4). |

### Recommended Stack

`STACK.md` is prescriptive and version-verified against PyPI/GitHub on 2026-09-15 (not training data). Several corrections change decisions: **APScheduler 4.x is still alpha** (use 3.11.3); **PyPI `python-jobspy` is stale** and its project URL 301-redirects (install from git and pin a commit); **there is no official Python SDK for opencode** (hand-roll ~5 endpoints, pinned by a contract test); **AIHawk is no longer an auto-applier**.

**Core technologies:**
- **Python 3.13** — runtime; **do not use 3.14** despite the local machine having 3.14.7 (Playwright/`curl_cffi`/`lxml` wheel coverage is the risk)
- **FastAPI 0.141.1** — async-first for fan-out I/O, Pydantic v2 native, both closest prior-art projects chose it; Django's killer feature (admin) is irrelevant because the product UI *is* the ranked queue
- **JobSpy (git `main`, pinned commit)** — LinkedIn + Indeed + Glassdoor/Google/ZipRecruiter behind one normalised schema; MIT; wrapped behind adapters; install from git, not PyPI
- **SQLite (WAL) + SQLAlchemy 2.0.53 + Alembic 1.20.0 + aiosqlite** — single-file, zero-ops, read-heavy; Postgres deferred but designed-for via migrations and a `search` port
- **FTS5 + BM25** — queue search; never `LIKE '%term%'`
- **APScheduler 3.11.3** + `SQLAlchemyJobStore`, in-process, `--workers 1` — persistent schedule + manual trigger, no broker
- **Tectonic 0.17.0** — ~124 MB / ~50s build vs TeX Live's ~2.3 GB / 5+ min; auto-reruns to convergence; keep `Dockerfile.texlive` as fallback and `LATEX_ENGINE` as config
- **Jinja2 3.1.6 with LaTeX-safe delimiters** (`\VAR{}`/`\BLOCK{}`, separate `Environment` from HTML) — no other sane way to template `.tex`
- **opencode `serve`** over HTTP with native JSON-Schema structured output — reuses the user's existing models, no second provider key
- **Jinja2 + HTMX + Alpine.js + Tailwind** — server-rendered CRUD/queue UI; no Node toolchain in the image; vendor assets locally, never a CDN

**Supporting:** `pydantic` 2.13.5 (the anti-fabrication design is built on `.model_json_schema()`), `httpx`, `curl_cffi` (escalation rung 2), `invisible-playwright` (rung 3, opt-in), `tenacity`, `rapidfuzz`, `pypdf` (PDF text extraction for verification), `structlog`.

### Expected Features

`FEATURES.md` inventories four prior-art clusters and finds the field's tools fail in exactly two places: **silent delivery failure** (auto-appliers) and **silent fabrication** (tailoring tools). Both are *trust* failures. The feature set is therefore organised so the pipeline's honesty is observable.

**Must have (table stakes):** pluggable source adapters + one normalised schema (TS-1); persistence with `first_seen_at`/`last_seen_at`/`content_hash` (TS-2); reversible two-tier cross-source dedup (TS-3); editable search criteria in the DB (TS-4); deterministic hard-rule filter with recorded exclusion reasons (TS-5); FTS5 queue search (TS-6); tracker with explicit stages + notes (TS-7/TS-8); run-history observability (TS-9); manual + scheduled runs (TS-10); structured CV fact store (TS-11); tailored PDF + review-before-compile (TS-12/TS-13); compile-time honesty verification (TS-14); new-since badge (TS-15); save/hide with persistent events (TS-16); stale signal (TS-17).

**Should have (competitive/differentiators):** LaTeX as both CV source and tailoring target (DF-1 — *nobody else in the field does this*); deterministic filter before LLM spend (DF-2 — absent from the field); per-factor sub-scores + code-computed weighted sum with sliders (DF-3); grounded rationale over pre-computed evidence (DF-4); requirement-by-requirement fit breakdown with named gaps (DF-5); evidence IDs + provenance labels (DF-6); honest gap flagging instead of padding (DF-7); change log/structural diff (DF-8); **application ↔ specific tailored CV version link with version→outcome data** (DF-9 — absent from every prior-art tool); listing-quality score separated from candidate fit (DF-10); feedback loop (DF-11); assisted-apply package (DF-12); "also seen on…" (DF-13); salary-market context (DF-14); ATS parse check (DF-15).

**Defer (v1.x / v2+):** provenance UI and gap-checklist UI (data model ships in v1), ghost/quality score as a first-class signal (fields stored), grounded cover letter (must reuse the same evidence IDs when built), "also seen on" UI, export, ntfy push, ATS parse checks, feedback *learning* (events captured in v1, learning deferred), Adzuna adapter #3 (interface ready, P2), Authentik OIDC + multi-user, MCP server, embedding pre-filter, Typst migration, CRM depth, mobile app.

**Do not build in v1 (anti-features, `FEATURES.md` AF-1…AF-15):** unattended auto-apply/auto-submit; autofilled screening answers submitted without confirmation; mass recruiter cold email; any fabrication feature; 100% ATS-match optimisation; LLM emitting `.tex` or free prose; unconstrained LLM scoring with no rubric; embedding/vector ranking as the v1 signal; a browser extension driving LinkedIn/Indeed/ATS pages; general PDF/DOCX parsing as the primary ingestion path; a full job-search CRM; multi-user accounts/teams/sharing/auth; a mobile app; a bulk "apply to all selected" action; real-time everything.

### Architecture Approach

`ARCHITECTURE.md` specifies a **modular monolith with internally hexagonal boundaries, enforced as import rules rather than conventions**: `domain/` imports nothing with I/O (a test asserts this); adapters are the only place board specifics exist; the LLM is a port; untrusted text is sanitised at exactly one place (the ingest boundary) before it can reach a prompt, template, or the database. The two pipelines are deliberately different animals — batch ingest (many listings, failure-tolerant, cost-capped) and per-listing tailoring (one listing, expensive, must-not-fail-open, human-reviewed) — and must never share a control path.

**Major components:**
1. **Source adapters** (`sources/`) — board-specific search, pacing, parsing; return a total `FetchResult` that never raises; one adapter per board over a shared `JobSpyTransport`
2. **Ingest pipeline** (`pipeline/run.py`) — fetch → sanitise → normalise → dedup/merge → persist → filter → rank → queue; hard ordering: **fetch fully, merge, then filter and cap**
3. **Hard-rule filter** (pure) — the cost gate; every rejection writes a `listing_exclusions` row with a rule id and reason
4. **Ranking + narrative services** — LLM returns per-factor `φ_f` and evidence IDs; **code computes `U = Σ w_f·φ_f`**; a second call narrates only pre-computed scores
5. **CV fact store + patch engine** — `cv.yaml` with stable, enumerated IDs; the LLM returns a typed `TailoringPatch` (move/reweight/demote/drop/reorder) with **no free-text field on the path to the PDF**
6. **Renderer + compiler + verifier** — deterministic Jinja2 LaTeX render, Tectonic subprocess, then `pypdf` text extraction and the 10-check verification gate
7. **Assisted-apply + tracker** — verified PDF + apply link + drafted answers; `applications.cv_artifact_id` closes the version↔outcome loop
8. **Scheduler, search, repositories, auth seam** — APScheduler in-process; FTS5 behind a `search` port; `Depends(current_user)` on every route from day one

### Critical Pitfalls

`PITFALLS.md` catalogues 14 critical, 10 moderate, 10 minor pitfalls. The five that most shape the roadmap:

1. **Scraper breakage is a permanent operating condition, not a one-time bug (P1).** Selector drift, A/B markup, and block pages all return HTTP 200 and parse as valid HTML. *Avoid by:* total `FetchResult` adapters, per-source per-field fill-rate metrics against a baseline, a cheap `probe()` liveness check surfaced in `/health` and the source-status UI, and a "why is the queue empty?" answer recorded on every run.
2. **Logging in with a real account converts a maintenance problem into an account-ban problem (P2).** LinkedIn's 2026 enforcement escalated (bans, IP blacklisting); AIHawk's contributors were banned and the project retreated from LinkedIn entirely. *Avoid by:* hard-coding the bright line — **public, logged-out pages only; no credential fallback, no CAPTCHA solving, no driving the user's live session, ever** — and keeping volume inside the personal envelope (a handful of searches, once a day, one IP, `<=50–100` results/run, ceilings in config).
3. **Aggressive or irreversible dedup destroys real jobs (P3).** *Avoid by:* two-tier dedup with the canonical-URL fallback key, **merge-don't-discard**, a `listing_dupes` audit table with a pre-merge `snapshot_json` and a real revert path, all key components required, and the merge rate published with a view of the rows behind it.
4. **Prompt wording does not prevent CV fabrication (P6).** A controlled 180-run study: 96.7% of baseline outputs contained an unsupported claim; guardrails cut density 86% but **50% still fabricated**. *Avoid by:* making fabrication structurally unrepresentable (typed patch over enumerated IDs, no free-text field on the PDF path), keeping `bullet.text` immutable, shipping **verification with tailoring as a gate**, and **blocking rather than repairing — "repair pressure is fabrication pressure."**
5. **Data-model omissions cannot be backfilled (P8).** History is an observation, not a column. *Avoid by:* putting the non-backfillable set in **migration 0001** and treating §9.4 as the acceptance checklist (see below).

## Implications for Roadmap

The recommended phase structure is `ARCHITECTURE.md` §14.3, which optimises for retiring unknowns early and reaching the Core Value directly. It is reproduced below with the research flags and pitfall mappings attached.

### Phase 1: Walking Skeleton + Foundations
**Rationale:** The project's biggest unknown is *whether scraping survives at personal scale* — prove it in week 1, not week 8. Contains the foundations everything else depends on, including the migration that cannot be deferred.
**Delivers:** Docker/compose skeleton (opencode sidecar unpublished + password-protected); **migration 0001** with the full non-backfillable set; FTS5; repositories; `runs` logging + `/health` + the import-discipline test; `current_user` seam on every route; adapter port + registry; sanitise; normalise; Tier-1 upsert; minimal queue UI; **the scraper-survival probe** (blocking-unknown gate #2).
**Addresses:** TS-1, TS-2, part of TS-9, foundations for all.
**Avoids:** P1 (source-status + probe from day one), P2 (never build the credentialed path), P3/AP7 (fallback key in 0001), P8 (migration acceptance checklist), P10 (two-callable shape, total functions), P12/M5 (workers=1, sync engine, timezone), M3 (background the pipeline, `asyncio.to_thread`), M6 (route seam), M8 (PRAGMAs + WAL backup), M10 (opencode exposure), m1, m4, m10.

**Migration 0001 acceptance checklist (non-backfillable — from `ARCHITECTURE.md` §9.4 / `PITFALLS.md` P8):**
1. `listings.first_seen_at`, `last_seen_at`, `content_hash` all `NOT NULL`
2. `listing_events` exists and is **append-only** (the DF-11 input, captured now, learned later)
3. `scores.factor_scores_json` + `weights_json` + `criteria_version` exist — **not `total_score` alone**
4. `cv_artifacts.verification_json` exists and `compile_status` can be `'blocked'`
5. `applications.cv_artifact_id` exists (the version↔outcome link)
6. Partial unique index on `(source, source_listing_id)` **and** unconditional `(source, canonical_url)` index
7. `sources.capabilities_json` + `sources.tos_audited_at` exist
8. `listings.blocking_key` exists and is indexed
9. Alembic at revision 0001, `alembic upgrade head` exercised in the container build

### Phase 2: Clean, Filtered, Queryable Queue
**Rationale:** Filtering a duplicate-heavy feed produces a queue the user mistrusts immediately, and dedup thresholds can only be tuned against a real corpus — this phase produces it.
**Delivers:** Tier-2 fuzzy dedup + merge/revert audit; criteria store + compiler; hard-rule filter with a `listing_exclusions` row per rejection; exclusion UI; `runs` UI; FTS5 search; new/stale badges.
**Addresses:** TS-3, TS-4, TS-5, TS-6, TS-9, TS-15, TS-16, TS-17.
**Avoids:** P3 (audit + revert + merge-rate sanity band), P4 (the cost gate must exist before the first real LLM run), P9 (an empty run must explain itself), M4 (FTS5, never LIKE), m6 (annual salary normalisation), m7 (no raw counts pre-dedup).
**Notes:** leave dedup threshold θ as a **setting plus a tuning task**, not a frozen constant; the 10–15% merge-rate band is from a different market and query shape.

### Phase 3: LLM Port + Structured Output (small)
**Rationale:** Any schema-constrained call must work end to end before ranking can be planned, and it is where the opencode field-name ambiguity is retired.
**Delivers:** `LLMBackend` protocol + `OpenCodeServerBackend`; schema validation at the boundary with bounded retry; `tools=[]` by default; listing text in `parts` never `system`; **the `/doc` contract test** in CI; pinned opencode image.
**Addresses:** the opencode requirement; enables TS-14/DF-3/DF-4.
**Avoids:** D5/M1 (record validation failure as a run outcome, `model_validate_json`, discriminated unions), M9 (pin + record model/version), m5 (untrusted input boundary).

### Phase 4: CV Fact Store + LaTeX Compile Spike — *runs in PARALLEL with Phases 2–3*
**Rationale:** This is the **largest unquantified cost in the plan** and it holds the project's other blocking unknown. Serialising it behind the queue phases means discovering a `.tex`-decomposition or Tectonic blocker at Phase 6, after the roadmap has already promised a tailoring phase.
**Delivers:** `cv/cv.yaml` with stable enumerated IDs; the `.tex → cv.yaml` import (human-reviewed); the **golden reproduction test**; the Tectonic compile harness with a primed cache and no shell-escape; `escape_tex`; the LaTeX-safe Jinja2 environment; `Dockerfile.texlive` fallback; `LATEX_ENGINE` config; **the spike on the real `.tex`** (blocking-unknown gate #1).
**Addresses:** TS-11, DF-1 groundwork.
**Avoids:** P7 (cold cache, pdfTeX primitives, escaping), P11 (two CV truths), CV-R1…CV-R8, m2.
**Gate:** if the document is macro-heavy and does not decompose, fall back to hand-authoring `cv.yaml` once and treating `base.tex` as a read-only reference — acceptable, but it changes the tailoring phase's shape. Measure by doing on one section before estimating Phase 6.

### Phase 5: Ranking — ★ CORE VALUE
**Rationale:** This is the Core Value: one ranked, explained queue with per-factor breakdown and named gaps. It must precede tailoring because tailoring consumes its output.
**Delivers:** rubric + named factors; absolute per-listing scoring (never relative ranking); code-computed weighted sum; grounded narrative; fit breakdown with named gaps; weights UI/sliders; **the batching decision and the cost budget resolved in this phase's plan**; a two-run ranking stability check.
**Addresses:** DF-3, DF-4, DF-5, part of TS-14 inputs.
**Avoids:** P4 (per-run ceiling + daily cap that *refuse* calls; account for in-flight calls), P5 (bounded absolute scoring, stored sub-scores, calibrated prompt against inflation, confidence tiers), AF-7.

### Phase 6: Tailoring + Verification (shipped together)
**Rationale:** Shipping tailoring first means shipping a fabrication window. Verification is a gate, not a follow-on.
**Delivers:** `TailoringPatch` schema + `apply_patch`; deterministic renderer; compile wrapper (stage → temp dir → copy out); the **verifier** with its 10 checks; `blocked` artefacts that are not downloadable and not linkable; change log/diff; page-count and ATS warnings.
**Addresses:** TS-12, TS-13, TS-14, DF-8 (free from the patch).
**Avoids:** P6 (structural + verification, block don't repair), P7's tail, CV-R3 (page budget as warning, never auto-truncate), CV-R5 (explicit drops with reasons), M2 (target 60–80% honest coverage), M7 (design the cover-letter seam to reuse evidence IDs).

### Phase 7: Assisted Apply + Tracker
**Rationale:** The differentiator — the exact artefact sent linked to the outcome — requires the artefact to exist first.
**Delivers:** apply package (verified PDF + link + drafted screening answers + gap checklist); tracker with stages, notes, `applied_at`, `next_action_at`; `applications.cv_artifact_id`; append-only `application_events`.
**Addresses:** TS-7, TS-8, DF-9, DF-12, part of DF-5.
**Avoids:** AF-1/AF-2/AF-14 (no submit, no bulk, drafts only), the "Applied with no link to what was sent" UX pitfall.

### Phase 8: Operations + Polish
**Rationale:** Scheduling is late on purpose — a cron job running an unstable pipeline just hides failures. Manual "run now" is the right trigger until the pipeline is trustworthy.
**Delivers:** APScheduler wiring + "next run at…"; source health UI surfaced from the stop signals (never auto-escalate); Adzuna adapter #3 with a quota ledger; "also seen on"; export; batched notification (if still needed).
**Addresses:** TS-10, DF-13, DF-14, TS-19, F5–F7.
**Avoids:** P12/M5 (explicit id + `replace_existing`, coalesce/max_instances/misfire_grace_time, Europe/Dublin), m3 (Adzuna quota), the per-listing-notification UX pitfall.

### Phase Ordering Rationale

- **Dependencies discovered:** migration 0001 is the single hardest ordering constraint — `first_seen_at`/`last_seen_at`/`content_hash`, the event tables, per-factor score columns, the canonical-URL key, and `cv_artifact_id` describe the past and cannot be invented later.
- **Grouping from architecture:** the CV fact store is a **shared prerequisite of both ranking and tailoring**, which is why Phase 4 sits beside Phases 2–3 rather than inside the tailoring work.
- **Unknowns retired early:** both blocking unknowns (scrape survival; `.tex`/Tectonic viability) are scheduled in Phases 1 and 4 so they cannot re-scope a phase late.
- **Pitfall avoidance:** total functions at every boundary keeps one board's 429 or one CV's compile failure from producing an empty queue; keeping the batch and per-listing pipelines separate is what makes both "degrade gracefully" and "never fail open" achievable.
- **No phase is infrastructure-only:** Phase 1 ships a browsable list; Phase 2 ships a usable queue — the walking skeleton keeps walking.

### Research Flags

Phases likely needing deeper research during planning (`/gsd-plan-phase --research-phase`):
- **Phase 1:** scraper-survival probe design is a measurement, not a reading — the plan needs an explicit probe + instrumentation task, because the result re-ranks Adzuna. Also needs the concrete opencode pinning/health wiring for compose.
- **Phase 3:** the `format` vs `outputFormat` question must be resolved against the user's own running server; plan the `/doc` contract test as a deliverable, not an assumption.
- **Phase 4:** highest research need — the real `.tex` is unavailable to research. The plan must contain a spike task on one section, a Tectonic bundle-coverage check, and a pdfTeX-primitive/bibliography check before Phase 6 is estimated.
- **Phase 5:** the batching/cost decision is unresolved and material; resolve it *in the plan*, together with the budget-cap semantics (enforce before the call, count in-flight).
- **Phase 6:** the verifier check list is designed in research rather than sourced; the plan should design/validate the checks (no-new-entity, metric containment, bullet conservation) against fixtures before execution.

Phases with well-documented patterns (skip research-phase):
- **Phase 2:** dedup hierarchy, FTS5, criteria CRUD — standard patterns, though θ needs a tuning task with real data.
- **Phase 7:** tracker CRUD, stages, links — conventional.
- **Phase 8:** APScheduler settings and source-health UI — documented upstream with explicit settings (the pitfall is misconfiguration, not uncertainty).

### Do Not Build in v1 (consolidated)

Credentialed scraping path (ever); auto-apply/auto-submit; bulk apply; CAPTCHA-solving integration; a browser extension driving portals; LLM emitting `.tex` or free prose; general PDF/DOCX resume parsing; vector DB / embedding ranking; multi-user/auth; MCP server; mobile app; CRM depth; real-time feeds; a wide `listings` table with a column per board field; one adapter class for two boards; a global `last_run_at`.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | **MEDIUM-HIGH** | HIGH on stack/library choices and the LinkedIn/Indeed API dead-end (primary docs + PyPI/GitHub verified 2026-09-15). MEDIUM on scraper longevity and Tectonic vs TeX Live. LOW on the exact Indeed shutdown year and on the JobSpy "no rate limiting" claim — both flagged, neither decision-affecting. |
| Features | **MEDIUM-HIGH** | HIGH on prior-art feature inventories (READMEs/docs read directly). MEDIUM on "what users complain is missing" (review sites carry selection bias; several comparison pages vendor-authored). MEDIUM-HIGH on anti-fabrication (three OSS implementations + two academic evaluations converge). LOW on dedup thresholds at this scale. |
| Architecture | **MEDIUM-HIGH** | HIGH on pipeline shape, adapter boundary, dedup placement, verification placement. MEDIUM on the structured-CV decomposition (real `.tex` is not in this repo). MEDIUM on the auth seam's cost (routes are free, the data model is not). |
| Pitfalls | **MEDIUM-HIGH** | HIGH on data-model, dedup, anti-fabrication and scheduler pitfalls (primary docs, peer-reviewed studies, upstream trackers). MEDIUM on scraper longevity, ban triggers and UX. LOW on single-vendor numbers, labelled inline. |

**Overall confidence: MEDIUM-HIGH.** The architecture and the ethical constraints are well-evidenced; the two things that can genuinely change the plan are **measurements that have not been taken** (scrape survival, `.tex` import cost), and both are scheduled as early gates.

### Gaps to Address

- **The real `.tex` is not in this repository (HIGHEST PRIORITY).** `.tex → cv.yaml` import cost and Tectonic bundle coverage are unmeasured. *Handle:* Phase-4 spike on one section, before the tailoring phase is estimated; fallback is a one-time hand-authored `cv.yaml`. Also unverified: whether the CV has a bibliography (which triggers the pinned-biber 2.17 caveat).
- **LinkedIn/Indeed survival rate at personal scale is unmeasured.** *Handle:* Phase-1 probe; the result determines whether Adzuna is promoted from hedge to primary. Design for blocking on both boards regardless.
- **Ranking batching is unresolved.** *Handle:* decide in the Phase-5 plan; it changes cost, timeouts, and whether `prompt_async` + SSE is required.
- **opencode structured-output field name and server pinning.** *Handle:* resolve against `GET /doc`; add a contract test so an upgrade fails loudly in CI.
- **Dedup threshold θ and the merge-rate sanity band are untunable in advance.** *Handle:* settings + a tuning task once the first real corpus exists.
- **`job_url_direct` availability for Indeed is unknown** (verified for LinkedIn, which needs the O(n) description pass). This determines how hard Tier-2b dedup has to work. *Handle:* measure in Phase 1/2.
- **Feedback-loop feasibility is genuinely uncertain** — no surveyed tool has shipped save/skip-driven ranking learning at this scale. *Handle:* capture the events in migration 0001 anyway; treat DF-11 as an experiment.
- **Blocked-artefact override path is not designed.** A false-positive verifier check would be frustrating. *Handle:* decide after the first real failure; do not build in v1.
- **Requirement extraction placement** (once per listing, cached, vs per tailoring call) is unsettled. *Handle:* settle in Phase 5, not discovered in Phase 6.
- **Resume-Matcher spike outcome** (whether its tailoring engine can be driven by opencode with a LaTeX output path). *Handle:* 1–2 day spike before committing to greenfield; if it succeeds, the roadmap changes substantially.
- **Adzuna Ireland coverage** (country path segment and result quality for Dublin roles, plus realistic quota burn). *Handle:* verify during the Phase-8 adapter, and earlier if Phase 1 promotes it.
- **No first-hand user research** — every "users complain" claim is mediated by review sites. *Handle:* a short validation pass with the actual user on the MVP list would raise confidence on TS-15/TS-16/TS-18 priority.
- **Cross-portal duplicate rate at personal scale is unknown.** *Handle:* measure on the first few runs and move θ against real data.

## Sources

### Primary (HIGH confidence)
- Microsoft Learn, LinkedIn Talent Solutions — Job Posting API, Apply Connect, certification (LTS 2026-03/04 views): no third-party read/search API; "not accepting new partnerships"
- Indeed Partner Docs (`docs.indeed.com`, pages dated 2026-07/08) + Indeed ToS (Ireland) — only employer-side surfaces survive; Publisher API retired
- opencode server + SDK docs (updated 2026-09-14) — endpoints, SSE, JSON-Schema structured output, and the `format` vs `outputFormat` inconsistency
- JobSpy documentation site + README + issue tracker (#374, #370, #112, #129) — `id: str | None`, `job_url_direct`, `emails`, O(n) description cost, single-filter limitation, rate-limit reality
- PyPI JSON API + GitHub API (read 2026-09-15) — verified versions and repo health (JobSpy, AIHawk, Resume-Matcher, Resumorph, TailorCV, tailit)
- SQLite FTS5 reference; APScheduler 3.x docs + issue tracker (#559, #421, #133, #87); Pydantic v2 docs (Context7); FastAPI docs (Context7); SQLAlchemy 2.0 docs (Context7)
- Tectonic 0.17.0 release notes; Adzuna developer portal
- *hiQ Labs v. LinkedIn* (9th Cir. 2022) + N.D. Cal. summary judgment — CFAA inapplicable to public pages; ToS enforceable as contract
- EDPB Guidelines 03/2026 on web scraping; CNIL legitimate-interest scraping sheet (Jan 2026)
- LinkedIn Prohibited Software policy + 2026 enforcement summaries

### Secondary (MEDIUM confidence)
- **Feature prior art:** Resume-Matcher, TailorCV, `aarg`, `resume-honest`, ResuMorph, `tailit`, JobRadar, `career-ops`, `linkedin-assistant`, ShouldApply, JobGhosting, `strata-match`, `redrob-hirefit-ranker`
- **Academic:** *Mitigating Fabrication in Multi-Stage LLM Pipelines for Hiring* (arXiv 2608.26171 — 96.7% baseline fabrication, 50% residual under guardrails); *Grounded Optimization* (arXiv 2607.01457); *JobMatchAI* (ACL 2026 demo — per-factor scoring, adjustable weights); job-posting dedup literature (CIKM 2021; MDPI 2026); position-bias / scoring-bias / framing-bias / sycophancy studies; LLM-system failure taxonomy (version drift)
- **Dedup engineering:** CleanJobData, Canaria, DEV Community "same job on three boards" — hierarchy, canonical-source choice, merge-rate band, "print the rows"
- **Scraper observability/testing:** ScraperGuard, Apify fixture/mock/staging guidance, silent-failure write-ups
- **Notification:** ntfy vs Apprise self-hosting write-ups — delivery-vs-routing split, "always have a deduper"
- **Engineering:** Tectonic migration write-ups, `sunsided/clothoid-latex` PR #4 (pinned biber, temp-dir workaround, dual Dockerfile), APScheduler+FastAPI persistence guides, HTMX-vs-React CRUD analysis

### Tertiary (LOW confidence — directional only, flagged in-source)
- JobsPipe/Adzuna/ATS comparison content and other vendor-authored pages (treated as marketing; used only where independently corroborated)
- Ban-trigger thresholds and LinkedIn restriction percentages (vendor pages, inconsistent over time)
- Ghost-job prevalence figures (18–22%, "1 in 3", 30–40% stale) — several sources sell competing services
- Specific scraper block-rate percentages

### Conflicting evidence, carried forward unresolved
- Indeed Publisher API shutdown year (2023 vs 2024) — decision unaffected
- JobSpy README "Indeed has no rate limiting" vs its own blanket blocking statement vs third-party bot-management evidence
- AIHawk licence (MIT vs AGPL-3.0) — verify `LICENSE` before reuse
- opencode structured-output field (`format` vs `outputFormat`)
- APScheduler duplicate-job mechanism (fix corroborated regardless)

---

*Research completed: 2026-09-15*
*Ready for roadmap: yes — with two hard gates (Phase 1 scrape-survival probe; Phase 4 `.tex`/Tectonic spike) carried into planning.*
