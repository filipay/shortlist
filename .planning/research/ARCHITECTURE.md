# Architecture Research

**Domain:** AI-assisted job search automation (local, self-hosted, Python-first, Dockerised) — pluggable source adapters → deduped listing store → deterministic hard-rule filter → LLM ranking against a structured CV → LaTeX tailoring with anti-fabrication verification → assisted apply → tracker
**Researched:** 2026-09-15
**Confidence:** MEDIUM-HIGH overall — HIGH on the pipeline shape, adapter boundary, dedup placement and verification-stage placement (they follow directly from constraints stated in PROJECT.md plus verified library/board contracts); MEDIUM on the structured-CV decomposition (the real `.tex` is **not in this repository**, so the import cost is unmeasured — see Gaps); MEDIUM on the auth seam's cost (route shape is free, data-model multi-tenancy is not).

> **Relationship to the sibling files.** This file does not re-litigate stack or feature choices. It assumes `STACK.md` (FastAPI 0.141.1, SQLite WAL + SQLAlchemy 2.0.53 + Alembic, APScheduler 3.11.3 `workers=1`, Tectonic 0.17.0, Jinja2 `\VAR{}`/`\BLOCK{}`, HTMX, `opencode serve`, JobSpy) and `FEATURES.md` (TS-*/DF-*/AF-* numbering) as settled. Two places where the sibling files and this one pull in different directions are called out explicitly in **§0 Alignment and Disagreements** rather than silently contradicted.

---

## 0. Alignment and Disagreements

Three items are worth stating up front, because a roadmap built on a silent contradiction is a roadmap that gets re-planned.

| # | Item | STACK.md / FEATURES.md position | This file's position | Resolution |
|---|------|--------------------------------|----------------------|------------|
| A1 | **What is the CV's source of truth?** | PROJECT.md: "the source of truth is a LaTeX (`.tex`) document". STACK.md Q6: "**Do not let the LLM emit `.tex`**… Keep the CV as **structured data** (`cv.yaml`/`cv.json`) with stable IDs". These are compatible in spirit but ambiguous in practice. | Both are right, and the ambiguity is dangerous. The `.tex` is the **human's** canonical document; the structured fact store is the **machine's** canonical document for tailoring. They must be reconciled by a *golden test* or they become two sources of truth. | Adopt the **derived-fact-store** model in §7, with the reproduction test as a hard gate. Do not let the phrase "source of truth" appear in the codebase without a qualifier. |
| A2 | **`UNIQUE(source, source_listing_id)` as Tier-1 dedup key** | STACK.md Q4 specifies this constraint as "the upsert key. Never insert twice." | Verified against JobSpy's own schema docs: `id` is typed `str \| None` and is documented as possibly absent for some boards. A `UNIQUE` constraint on a nullable column in SQLite permits unlimited NULLs, so the key silently degrades to "insert everything" on any board that omits `id`. | Keep the constraint, **add a mandatory `canonical_url` fallback key**, and make the Tier-1 upsert a two-key lookup. See §8.1. |
| A3 | **LinkedIn and Indeed as "adapters"** | STACK.md Q1 treats JobSpy as "the acquisition layer" and warns "never import JobSpy from domain code". | If `linkedin` and `indeed` are two adapter classes that both delegate to one JobSpy call, you have one failure domain wearing two hats — a 429 on Indeed would be invisible to per-source health. | One adapter **per board name**, sharing a `JobSpyTransport` helper. This preserves per-board capability declaration, per-board budgets and per-board health, and lets one board be promoted up the escalation ladder without touching the other. See §5.3. |

Everything else in this file is additive to `STACK.md` and `FEATURES.md`, not corrective.

---

## 1. System Overview

### 1.1 Shape: modular monolith, one process, strict internal ports

The system is a **modular monolith** — one FastAPI process, one SQLite file, one Docker image, with `opencode` as a sibling container. It is explicitly *not* microservices, a task queue, or an event bus: at 1–5 users with one nightly writer (`STACK.md` Q4/Q5), a broker would be pure operational tax.

What matters is that the monolith is **internally hexagonal**. Four boundaries are load-bearing and are enforced as *import rules*, not conventions:

1. **`domain/` imports nothing with I/O.** No `httpx`, no `sqlalchemy`, no `jobspy`, no `opencode`. Pure functions over dataclasses/Pydantic. This is what makes dedup, filtering, scoring arithmetic and patch application unit-testable and deterministic.
2. **Adapters are the only place board specifics exist.** JobSpy, URL shapes, per-board filters and rate limits live behind `sources/`.
3. **The LLM is a port.** Nothing outside `llm/` knows whether the backend is HTTP or a subprocess.
4. **Untrusted text is sanitised at exactly one place** — the ingest boundary — before it can reach a prompt, a template, or the database.

### 1.2 Layer diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│  PRESENTATION            Jinja2 + HTMX + Alpine  (server-rendered)       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │ Queue    │ │ Listing  │ │ Criteria │ │ Tracker  │ │ CV       │        │
│  │ browse   │ │ detail   │ │ +weights │ │ board    │ │ preview  │        │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘        │
├───────┴────────────┴────────────┴────────────┴────────────┴──────────────┤
│  HTTP / ROUTES           api/ (JSON)  ·  web/ (HTML fragments)           │
│  ── every route declares  user: User = Depends(current_user)  ──  §11    │
├──────────────────────────────────────────────────────────────────────────┤
│  ORCHESTRATION           pipeline/  (run_pipeline)   ·  jobs/ (schedule) │
│  ┌────────────────────────────────┐  ┌─────────────────────────────────┐ │
│  │ INGEST PIPELINE (batch)        │  │ TAILOR PIPELINE (per listing)   │ │
│  │ fetch→sanitize→normalize→      │  │ patch→validate→render→compile→  │ │
│  │ dedup→persist→filter→rank→queue│  │ verify→persist artifact→package │ │
│  └────────────────────────────────┘  └─────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────────────┤
│  DOMAIN (pure, no I/O)                                                   │
│  ┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌─────────┐  │
│  │listing ││ dedup  ││criteria││ filter ││scoring ││  cv    ││ schemas │  │
│  │normalize││ match  ││ compile││ rules  ││ phi→U  ││+patch  ││(LLM I/O)│  │
│  └────────┘└────────┘└────────┘└────────┘└────────┘└────────┘└─────────┘  │
├──────────────────────────────────────────────────────────────────────────┤
│  PORTS (protocols)          the ONLY shapes the domain may depend on     │
│  JobSource · LLMBackend · ListingRepository · FactStore · Renderer ·     │
│  Verifier · Clock · CurrentUser                                          │
├──────────────────────────────────────────────────────────────────────────┤
│  ADAPTERS (the only place the outside world is known)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐  ┌──────────┐ ┌───────────────┐  │
│  │linkedin  │ │ indeed   │ │ adzuna   │  │opencode  │ │tectonic +     │  │
│  │(JobSpy)  │ │(JobSpy)  │ │(HTTP)    │  │serve/CLI │ │jinja2 render  │  │
│  └──────────┘ └──────────┘ └──────────┘  └──────────┘ └───────────────┘  │
├──────────────────────────────────────────────────────────────────────────┤
│  PERSISTENCE             db/  SQLAlchemy 2.0 + Alembic + FTS5            │
│  ┌─────────┐ ┌───────────┐ ┌─────────┐ ┌──────────┐ ┌─────────────────┐  │
│  │listings │ │listing_   │ │ scores  │ │cv_       │ │ applications +  │  │
│  │         │ │sources    │ │(factors)│ │artifacts │ │ events          │  │
│  └─────────┘ └───────────┘ └─────────┘ └──────────┘ └─────────────────┘  │
│  volumes:  /data/jobsearch.db (WAL)   /cv/*.tex+cv.yaml   /artifacts/*   │
└──────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Why this shape

- **The batch INGEST pipeline and the on-demand TAILOR pipeline are different animals** and must not share a control path. Ingest is many-listing, cheap-per-item, failure-tolerant, cost-capped. Tailor is one-listing, expensive, must-not-fail-open, human-reviewed. Conflating them (the common "one big job" mistake) produces a pipeline that either aborts the whole queue because one CV failed to compile, or publishes an unverified CV because the batch had to keep moving.
- **Ports are declared as Protocols**, but concrete adapters use an ABC for the **source** family specifically, because instantiation-time enforcement catches a half-implemented adapter immediately (§5.1).
- **Sanitisation is a pipeline stage, not a helper** — it has a name, a log line, and a test suite, because it is simultaneously the GDPR control and the prompt-injection control.

---

## 2. Component Boundaries

| # | Component | Owns | Explicitly does NOT own | Talks to |
|---|-----------|------|------------------------|----------|
| C1 | **Source adapters** (`sources/`) | Board-specific search params, auth/proxy/pacing, response parsing, raw field mapping, capability declaration, per-board rate budget | Persistence, dedup, filtering, scoring, any LLM call | `JobSource` port → returns `FetchResult` |
| C2 | **Sanitiser** (`ingest/sanitize.py`) | PII stripping (recruiter emails/phones), HTML/boilerplate reduction, injection-marker detection and recording, description truncation policy | Deciding what a listing *is* | Pure; called by ingest pipeline |
| C3 | **Normaliser** (`domain/listing.py`) | Canonical field mapping, salary→annual normalisation, location tokenisation, remote inference, `content_hash` computation, canonical-URL derivation | Merging, filtering, scoring | Pure |
| C4 | **Deduplicator** (`domain/dedup.py` + `ingest/merge.py`) | Blocking-key generation, fuzzy match scoring, merge policy, canonical-source selection, merge/revert records | DB writes (delegates to repository) | `ListingRepository` port |
| C5 | **Criteria compiler** (`domain/criteria.py`) | Turning stored user criteria into (a) adapter `SearchQuery` params and (b) filter rules; versioning criteria for score reproducibility | Calling adapters or DB | Pure |
| C6 | **Hard-rule filter** (`domain/filter.py`) | Evaluating include/exclude/location/salary/seniority/remote rules; producing a per-rule verdict with a reason | Hallucinating reasons; calling the LLM | Pure |
| C7 | **Ranking service** (`domain/scoring.py` + `pipeline/rank.py`) | Rubric definition, per-factor `φ_f` extraction, **code-computed weighted sum** `U = Σ w_f·φ_f`, confidence tier, evidence id collection | Letting the LLM produce the total; persisting raw documents into a prompt | `LLMBackend` port, `ScoreRepository` |
| C8 | **Narrative service** (`pipeline/narrate.py`) | Prompt construction for the *explanation only* — LLM receives pre-computed factor scores + evidence ids, never raw documents | Computing scores | `LLMBackend` port |
| C9 | **CV fact store** (`cv/factstore.py`) | Loading/validating `cv.yaml`, stable-ID assignment, enumeration generation, import from `.tex`, versioning | Rendering | Pure + file I/O |
| C10 | **Patch engine** (`domain/cv.py`) | The `TailoringPatch` model, `apply_patch(facts, patch) -> RenderPlan`, invariant enforcement (every id must exist, no free-text can reach output) | Rendering, compiling | Pure |
| C11 | **Renderer** (`latex/render.py`) | Jinja2 LaTeX environment, `escape_tex`, deterministic `.tex` emission from `RenderPlan` | Compiling, calling LLMs | Pure (filesystem out) |
| C12 | **Compiler** (`latex/compile.py`) | Tectonic subprocess invocation, temp-dir staging, package-cache preflight, page count, compile log capture | Judging correctness | Subprocess |
| C13 | **Verifier** (`latex/verify.py`) | The anti-fabrication assertions over the **compiled PDF text** (§10); pass/block decision; findings | Repairing content ("repair pressure is fabrication pressure") | Pure over extracted text |
| C14 | **Application/assist** (`pipeline/assist.py`) | Assembling the apply package (verified PDF + link + drafted screening answers), recording the artifact↔application link | Submitting anything | Repositories |
| C15 | **LLM port** (`llm/`) | `LLMBackend` protocol, opencode server + CLI implementations, structured-output call + **schema validation + bounded retry**, tool restriction, model/agent selection | Domain schemas (they live in `domain/schemas/`) | HTTP / subprocess |
| C16 | **Scheduler** (`jobs/`) | APScheduler wiring, cron triggers, `coalesce`/`max_instances`/`misfire_grace_time`, next-run exposure | Pipeline logic | `pipeline.run_pipeline` |
| C17 | **Search** (`search/`) | FTS5 query building, BM25 ranking, index sync | Business rules | DB |
| C18 | **Repositories** (`db/`) | All SQL, transaction boundaries, upserts, migrations | Business rules | SQLAlchemy |
| C19 | **Auth seam** (`api/deps.py`) | `current_user()` dependency returning the local singleton user | Real auth in v1 | Settings |

**The single most important boundary:** C1–C2 sit *outside* everything else, and C7/C8 sit *behind* the LLM port. The domain in the middle can be exercised entirely offline with fixtures — which is what makes the anti-fabrication guarantees testable rather than aspirational.

---

## 3. Recommended Project Structure

```
job-search/
├── pyproject.toml                 # uv-managed; pins per STACK.md
├── compose.yml                    # app + opencode (opencode NOT published)
├── Dockerfile                     # multi-stage; installs Tectonic + primes TeX cache
├── Dockerfile.texlive             # documented fallback (STACK.md Q6)
├── alembic.ini
├── alembic/
│   └── versions/                  # every schema change, from migration 0001
├── app/
│   ├── main.py                    # FastAPI app factory + lifespan (scheduler start/stop)
│   ├── config.py                  # pydantic-settings; LOCAL_USER_ID, LATEX_ENGINE, caps
│   ├── api/
│   │   ├── deps.py                # current_user() seam  ◄── §11
│   │   ├── queue.py  listings.py  criteria.py  tracker.py  cv.py  runs.py
│   │   └── health.py              # reports opencode + tectonic + source reachability
│   ├── web/
│   │   ├── routes.py              # HTML pages + HTMX fragments
│   │   └── templates/
│   │       ├── html/              # standard Jinja2 delimiters
│   │       └── latex/             # \VAR{} \BLOCK{} environment  ◄── separate Environment
│   ├── domain/                    # PURE. No I/O imports. Enforced by a test.
│   │   ├── models.py              # Listing, ListingSourceRef, CvFacts, Score, Application
│   │   ├── listing.py             # C3 normalise + canonical_url + content_hash
│   │   ├── dedup.py               # C4 pure matching (blocking key, fuzzy score, merge plan)
│   │   ├── criteria.py            # C5 compile criteria → SearchQuery + FilterRules
│   │   ├── filter.py              # C6 evaluate rules → verdicts
│   │   ├── scoring.py             # C7 weighted sum, tiers, factor definitions
│   │   ├── cv.py                  # C10 patch model + apply_patch + invariants
│   │   ├── sanitize.py            # C2 PII + injection markers (pure)
│   │   └── schemas/               # LLM-facing Pydantic models (ONLY these cross the LLM port)
│   │       ├── ranking.py
│   │       ├── patch.py
│   │       └── gaps.py
│   ├── sources/                   # C1
│   │   ├── base.py                # JobSource ABC, SourceCapabilities, SearchQuery, FetchResult
│   │   ├── registry.py            # name → adapter class
│   │   ├── _jobspy_transport.py   # the ONLY module that imports jobspy
│   │   ├── linkedin.py
│   │   ├── indeed.py
│   │   └── adzuna.py              # adapter #3 (P2)
│   ├── ingest/
│   │   ├── sanitize.py            # C2 stage wrapper (calls domain.sanitize)
│   │   └── merge.py               # C4 persistence of merge/revert decisions
│   ├── pipeline/
│   │   ├── run.py                 # run_pipeline(trigger, search_id)  ◄── one path, two triggers
│   │   ├── stages.py              # stage protocol + run-log instrumentation
│   │   ├── rank.py                # C7 orchestration over a filtered batch
│   │   ├── narrate.py             # C8 explanation-only LLM call
│   │   ├── tailor.py              # C9→C11→C12→C13 orchestration for one listing
│   │   └── assist.py              # C14 application package
│   ├── llm/
│   │   ├── base.py                # LLMBackend Protocol, StructuredCallResult
│   │   ├── opencode_server.py     # httpx against pinned opencode
│   │   ├── opencode_cli.py        # degraded fallback
│   │   └── contract_test.py       # asserts /doc field names (format vs outputFormat)
│   ├── cv/
│   │   ├── import_tex.py          # one-off .tex → cv.yaml (human-reviewed)
│   │   └── factstore.py           # C9 load/validate/enumerate versions
│   ├── latex/
│   │   ├── env.py                 # the LaTeX-safe Jinja2 Environment
│   │   ├── render.py              # C11
│   │   ├── compile.py             # C12
│   │   └── verify.py              # C13  ◄── the anti-fabrication gate
│   ├── search/fts.py              # C17
│   ├── jobs/scheduler.py          # C16
│   └── db/
│       ├── base.py  session.py  models.py  repositories/
│       └── migrations/            # (alembic lives at root; models here)
├── cv/                            # mounted volume: cv.yaml + base.tex + templates
├── artifacts/                     # mounted volume: compiled PDFs + .tex snapshots
├── data/                          # mounted volume: jobsearch.db (WAL) + backups
└── tests/
    ├── domain/                    # pure unit tests (fast, no DB, no network)
    ├── golden/                    # rendered .tex fixtures  ◄── renderer regression
    ├── fixtures/listings/         # captured raw payloads per source
    └── contract/                  # opencode /doc, JobSpy schema, Tectonic compile
```

**Structure rationale.**

- **`domain/` is import-disciplined.** A test asserts `app.domain.*` never imports `httpx|sqlalchemy|jobspy|jinja2|subprocess`. That single test is what keeps the architecture from decaying into a pile of scripts.
- **`sources/_jobspy_transport.py` is the only file allowed to `import jobspy`.** STACK.md Q1's "never import JobSpy from domain code" becomes a mechanically checkable rule rather than an intention. When LinkedIn inevitably breaks and needs promotion to `curl_cffi` or `invisible-playwright`, the change is confined to one adapter + its transport.
- **`domain/schemas/` is separate from `llm/`.** The LLM port consumes a schema; it does not define one. This keeps the wire format stable across backend swaps and lets the schemas be golden-tested without a server.
- **`pipeline/` holds the only orchestration.** Both the manual trigger and the cron job call `run_pipeline()`. `STACK.md` Q5 requires this ("one path, two triggers"); making it a folder makes it hard to violate.
- **Two Jinja2 `Environment` instances under one `templates/` tree** — `html/` with standard delimiters, `latex/` with `\VAR{}`/`\BLOCK{}`. `STACK.md` Q6/Q8.

---

## 4. Data Flow — End to End

Direction is stated explicitly on every arrow: **→** = data flows this way; the writer of each edge is named.

### 4.1 Flow A — Scheduled/manual ingest to ranked queue (batch, runs on a schedule)

```
[TRIGGER]                         ┌──────────────────────────────────────┐
  cron 07:00 Europe/Dublin ──────►│ jobs/scheduler.py                    │
  OR "Run search now" button ────►│   enqueues, returns immediately       │
                                   └───────────────┬──────────────────────┘
                                                   │ calls (never inline in a request)
                                                   ▼
   ┌──────────────────────────────────────────────────────────────────────────────┐
   │ pipeline/run.py — run_pipeline(search_id, trigger)                            │
   │ 1. INSERT runs row (status=running, started_at)                               │
   └───────────────┬──────────────────────────────────────────────────────────────┘
                   ▼
   ┌───────────────────────────┐   per enabled source, concurrently, budgeted
   │ C5 criteria compiler      │──► SearchQuery(capabilities-aware)
   └───────────────┬───────────┘
                   ▼
   ┌───────────────────────────┐   FetchResult(items | partial | error)  ← NEVER raises
   │ C1 source adapters        │   writes: source_request_log (politeness ledger)
   │ linkedin · indeed         │
   └───────────────┬───────────┘
                   ▼  RawListing  (untrusted)
   ┌───────────────────────────┐   strips recruiter PII, records injection markers,
   │ C2 SANITISE               │   truncates runaway descriptions
   └───────────────┬───────────┘
                   ▼  SanitisedRawListing
   ┌───────────────────────────┐   canonical_url, content_hash, salary→annual,
   │ C3 NORMALISE              │   location tokens, remote inference
   └───────────────┬───────────┘
                   ▼  NormalisedListing
   ┌───────────────────────────┐   Tier-0 in-run collapse → Tier-1 exact upsert
   │ C4 DEDUP + MERGE          │   → Tier-2 fuzzy cross-source merge
   │   (BEFORE filter/cap)     │   writes: listings, listing_sources, listing_dupes
   └───────────────┬───────────┘
                   ▼  merged Listing + all source refs
   ┌───────────────────────────┐   writes: listing_exclusions for EVERY rejection
   │ C6 HARD-RULE FILTER       │   (this is the cost gate — no LLM spend below here)
   └───────────────┬───────────┘
                   ▼  survivors (bounded set)
   ┌───────────────────────────┐   Stage 1: LLM returns per-factor φ_f + evidence ids
   │ C7 RANK                   │   Stage 2: code computes U = Σ w_f·φ_f
   │   rank.py + narrate.py    │   Stage 3: LLM narrates pre-computed scores only
   └───────────────┬───────────┘   writes: scores (JSON per-factor), llm_calls
                   ▼
   ┌───────────────────────────┐
   │ QUEUE  (read model)       │   UPDATE runs (status=done, counts, tokens, errors)
   │  listing × score × events │
   └───────────────────────────┘
```

**Hard ordering rules (each one is a documented failure mode, not a preference):**

1. **Fetch fully → sanitise → normalise → merge → THEN filter and cap.** Filtering or capping before merging discards the duplicate copy that happened to carry the salary field (`FEATURES.md` §5).
2. **Sanitise before the listing is persisted OR prompted.** It is the only point where both the GDPR control and the injection control can be applied once (STACK.md Q1 implications, Q7 injection boundary).
3. **Filter before rank.** The filter is the cost gate; the ranking phase's timeout and batching design depend on the candidate count being bounded (`FEATURES.md` §7.3).
4. **Scores are written with the criteria version that produced them.** Otherwise a later criteria edit makes every stored score unreproducible.

### 4.2 Flow B — Ranked listing to tailored, verified, apply-ready artifact (on demand)

```
[USER ACTION]  opens a listing in the queue, clicks "Tailor CV"
      │
      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ pipeline/tailor.py(tailor_listing(listing_id))                                │
└───────┬──────────────────────────────────────────────────────────────────────┘
        │ READ (never mutate)
        ├──────────────► C9 FactStore  →  CvFacts (current cv_version, all IDs)
        ├──────────────► listings row  →  requirements (extracted, cached)
        └──────────────► scores row    →  which factors matched, which were gaps
        ▼
┌───────────────────────────┐  LLM is given: the job requirements + the ENUMERATED
│ C15 StructuredCall        │  ids of the user's real content. It returns a PATCH.
│   schema = TailoringPatch │  It is NEVER given the .tex and NEVER returns text.
└───────────────┬───────────┘
                ▼  raw dict from opencode structured_output
┌───────────────────────────┐  Pydantic discriminated-union validation.
│ SCHEMA VALIDATION         │  Any unknown id → ValidationError → bounded retry →
│  (in llm/ boundary)       │  surface as an error. Fabrication is structurally
└───────────────┬───────────┘  impossible here: there is no free-text field on the path.
                ▼  TailoringPatch (typed, ids only)
┌───────────────────────────┐  Checks: every id exists; no drop is silent;
│ C10 apply_patch           │  produces RenderPlan. Pure, unit-tested.
└───────────────┬───────────┘
                ▼  RenderPlan
┌───────────────────────────┐  Jinja2 (\VAR/\BLOCK) + escape_tex on EVERY value.
│ C11 RENDER .tex           │  Deterministic: same RenderPlan ⇒ same .tex.
└───────────────┬───────────┘  writes: artifacts/<id>/cv.tex  (snapshot, kept)
                ▼
┌───────────────────────────┐  Tectonic subprocess, temp-dir, no shell-escape,
│ C12 COMPILE               │  primed package cache.
└───────────────┬───────────┘  writes: artifacts/<id>/cv.pdf, compile_log
                ▼  PDF bytes
┌───────────────────────────┐  pypdf text extraction + assertions vs the CvFacts
│ C13 VERIFY  ◄── THE GATE  │  snapshot AND the patch. See §10.
└───────┬───────────────┬───┘
        │ PASS          │ BLOCK  (findings recorded, artifact stored as 'blocked',
        ▼               ▼         NEVER downloadable, NEVER linkable to an application)
┌────────────────┐  ┌──────────────────────────┐
│ persist        │  │ UI shows findings + the   │
│ cv_artifacts   │  │ specific unsupported item │
│ (verified)     │  └──────────────────────────┘
└───────┬────────┘
        ▼
┌───────────────────────────┐  rendered PDF for preview/download
│ C14 APPLICATION PACKAGE   │  + direct apply URL + drafted screening answers
│   (assist.py)             │  + gap checklist. NO prefill-into-portal, NO submit.
└───────────────┬───────────┘
                ▼  user reviews in the browser
        ┌───────────────────────────────────────────────┐
        │ HUMAN presses submit on the portal (out of band)│
        └───────────────────┬───────────────────────────┘
                            ▼
        ┌───────────────────────────────────────────────┐
        │ tracker: POST status=applied                  │
        │   writes: applications(listing_id,            │
        │           cv_artifact_id ← THE LINK)          │
        │           + application_events (append-only)  │
        └───────────────────────────────────────────────┘
```

**The direction that matters most:** information flows **facts → patch → render → verify → artifact → application**, and never backwards. The compiled PDF is a *terminal* artifact, not an input. Nothing re-parses a PDF to recover CV content (`FEATURES.md` AF-10 explicitly forbids the general PDF-parsing path).

### 4.3 Flow C — User feedback (the loop that must be captured even though it is not used yet)

```
[USER] save / hide / shortlist / unsave / unhide  ──►  listing_events (APPEND-ONLY)
                                                            │
                                          ┌─────────────────┴──────────────────┐
                                          │ used NOW for:                      │
                                          │  · queue filtering (hide)          │
                                          │  · "new since" / delta badges      │
                                          └─────────────────┬──────────────────┘
                                                            │ NOT used yet
                                                            ▼
                                          DF-11 learning loop (P3). The EVENTS must
                                          be written from migration 0001 — they
                                          cannot be reconstructed retroactively.
```

### 4.4 State lifecycle of a listing

```
                    first observed
                          │
                          ▼
   NEW ──(next run, seen again)──► ACTIVE ──(not seen for N days)──► STALE
    │                                │                                 │
    │                                └──(content_hash changes)──► UPDATED (repost detected)
    ▼
  FILTERED (with rule id)   ──or──►  QUEUED (scored)  ──►  SHORTLISTED
                                                            │
                                              ┌─────────────┴─────────────┐
                                              ▼                           ▼
                                        HIDDEN (user)               APPLIED ──► INTERVIEWING
                                                                        │            │
                                                                        ▼            ▼
                                                                    REJECTED     OFFER/WITHDRAWN
```

`first_seen_at`, `last_seen_at`, `content_hash` and the event rows are the four things that make this lifecycle computable. All four must exist in migration 0001 (`FEATURES.md` TS-2, TS-16).

---

## 5. The Adapter Interface Contract (job sources)

This section answers "how do we keep LinkedIn/Indeed specifics out of the core". The rule is: **the core knows the shape of a job search, never the shape of a job board.**

### 5.1 The ports

```python
# app/sources/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

SourceName = Literal["linkedin", "indeed", "adzuna", "glassdoor", "google"]

@dataclass(frozen=True)
class SourceCapabilities:
    """What a board can actually do. Declared, not discovered at runtime."""
    supports_salary: bool
    supports_salary_min_filter: bool
    supports_remote_flag: bool
    supports_seniority: bool
    supports_full_description_in_search: bool
    requires_second_pass_for_description: bool   # LinkedIn: extra request per job
    supports_offset_paging: bool
    max_results_per_query: int | None            # boards cap ~1000
    # Mutually exclusive filter groups. LinkedIn honours ONLY ONE of
    # {hours_old, easy_apply}; supplying several is SILENTLY ignored upstream.
    exclusive_filter_groups: tuple[frozenset[str], ...] = ()

@dataclass(frozen=True)
class SearchQuery:
    """Board-agnostic search intent, already compiled from user criteria."""
    keywords: str
    location: str | None
    distance_miles: int | None
    remote_only: bool | None
    salary_floor: int | None
    seniority: tuple[str, ...]
    hours_old: int | None
    offset: int = 0
    results_wanted: int = 50

@dataclass(frozen=True)
class FetchBudget:
    """Per-source, per-run ceiling. Enforced by the adapter, logged by the core."""
    max_requests: int
    max_results: int
    max_detail_fetches: int
    deadline: datetime

@dataclass(frozen=True)
class RawListing:
    """ONE raw observation. No dedup, no filtering, no scoring, NO PII."""
    source: SourceName
    source_listing_id: str | None       # JobSpy `id` is documented as possibly None
    source_url: str                     # board's canonical listing URL
    direct_url: str | None              # employer's own apply page (job_url_direct)
    title: str
    company_name: str | None
    location_raw: str | None
    description: str | None             # already sanitised
    is_remote: bool | None
    salary_min: float | None
    salary_max: float | None
    salary_interval: str | None
    salary_currency: str | None
    salary_source: str | None           # direct_data | description
    posted_at: date | None
    job_type: tuple[str, ...] = ()
    source_extras: dict = field(default_factory=dict)   # job_level, company_industry, …

@dataclass(frozen=True)
class FetchResult:
    """A total, never an exception. Partial success is a first-class outcome."""
    source: SourceName
    items: list[RawListing] = field(default_factory=list)
    status: Literal["ok", "partial", "blocked", "rate_limited", "error"] = "ok"
    requests_used: int = 0
    error: str | None = None


class JobSource(ABC):
    """The ONLY surface the pipeline depends on. One instance per board."""

    name: SourceName
    capabilities: SourceCapabilities

    @abstractmethod
    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        """Cheap liveness check for /health and the source status UI."""

    @abstractmethod
    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        """Search-shaped, bounded, failure-tolerant. Sanitises before returning."""

    async def fetch_details(
        self, refs: list[RawListing], budget: FetchBudget
    ) -> dict[str, RawListing]:
        """Optional second pass. Default: no-op. Overridden only where the board
        requires O(n) extra requests (LinkedIn). Budgeted separately."""
        return {}
```

### 5.2 The seven contract rules

| # | Rule | Why (evidence) |
|---|------|----------------|
| R1 | **`fetch` never raises for a source-specific failure.** It returns `FetchResult(status=...)`. | Upstream has chosen to be hostile; a source failing must degrade the queue, not abort the run (`STACK.md` Q1: "return partial/none, not raise"). |
| R2 | **The adapter sanitises before returning.** `RawListing` has no `emails` field, and none may be added. | JobSpy's `JobPost` schema literally includes `emails: list[str]` extracted from the description. Persisting recruiter PII is the cheapest GDPR mistake to avoid (`STACK.md` Q1 implication 2). A schema with no such field cannot leak one. |
| R3 | **The adapter declares `capabilities`; the criteria compiler consults them and records a warning when a requested filter is unsupported or in an exclusive group.** | LinkedIn honours **only one** of `hours_old` / `easy_apply: "Providing more than one has no effect"`. Silent no-op means the user believes a filter is applied when it is not — which corrupts the whole "why is this in my queue" story. |
| R4 | **Description fetching is a separate, budgeted pass (`fetch_details`), never folded into `fetch`.** | `linkedin_fetch_description=True` makes "one additional request per job" and "significantly increases the risk of rate limiting". At personal scale that is the difference between surviving a daily run and getting blocked; making it a named, budgeted stage means it can be turned down or skipped per source without touching search. |
| R5 | **The adapter never touches the database, never dedups, never filters, never scores, never calls the LLM.** | Keeps the escalation ladder (pacing → `curl_cffi` → `invisible-playwright` → proxies) a per-adapter concern. If adapters wrote to `listings`, promoting a source would require re-testing merge semantics. |
| R6 | **`source_extras` is where board-specific fields go.** Core columns are board-agnostic. | Verified: `job_level`/`job_function` are LinkedIn-only, `company_num_employees`/`company_revenue`/`company_logo` Indeed-only, `skills`/`experience_range` Naukri-only. A wide table would grow per board; a JSON column does not. |
| R7 | **Adapters are keyed by `name` in an explicit registry, resolved from the `sources` table at run start.** | "Adding a source" must be: implement `JobSource`, register it, insert a `sources` row, run it. If it requires editing the pipeline or the schema, ADR-1 in PROJECT.md ("bolting this on later would be a rewrite") has failed. |

### 5.3 One adapter per board, one shared transport

LinkedIn and Indeed both go through JobSpy today. They are still **two `JobSource` implementations**: each declares its own capabilities (They differ! LinkedIn needs a proxy beyond ~100 results and rate-limits after ~10 pages; Indeed's constraints differ), its own budget, and its own health. Both delegate to a shared `_jobspy_transport.py`.

This matters because the escalation ladder is *per board*. When LinkedIn eventually blocks rung 1, `LinkedInSource.fetch` is replaced with a `curl_cffi` implementation and `IndeedSource` is untouched. If they were one `JobSpySource` class with `site_name=["linkedin","indeed"]`, that promotion would be impossible without splitting the class anyway.

**Critically: never call JobSpy once with a `site_name` list.** One call = one thread pool = one failure mode = no per-board budget, health, or `first_seen_at` attribution at the board level. Invoke per board.

### 5.4 What the core sends and receives (worked example)

```
User criteria row:
  keywords="platform engineer", location="Dublin, IE", remote=None,
  salary_floor=70000, seniority=("senior","lead"), exclude=("recruiter","unpaid")

C5 criteria compiler
  ├─ LinkedInSource.capabilities: supports_salary_min_filter=False,
  │        exclusive_filter_groups=({hours_old, easy_apply},)
  │        → SearchQuery(keywords="platform engineer", location="Dublin, IE",
  │                     salary_floor=None,          ← dropped, warned
  │                     hours_old=None)             ← must not combine
  │        → FilterRule(salary_floor>=70000) is applied LOCALLY by C6 instead
  │
  └─ AdzunaSource.capabilities: supports_salary_min_filter=True
           → salary_min=70000 pushed to the API (saves quota)

Adapter returns FetchResult(status="partial", items=[...37...], error="429 after page 4")
  → pipeline records the partial status on the runs row and continues with 37 items.
  → the source status panel shows "linkedin: rate_limited (37 of ~200 expected)".
```

That is the entire contract: **capabilities in, `FetchResult` out, no exceptions, no PII, no persistence.**

---

## 6. The LLM Backend Abstraction (opencode serve vs CLI)

### 6.1 The port

```python
# app/llm/base.py
from typing import Protocol, TypeVar, Type
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class StructuredCallResult(BaseModel):
    ok: bool
    data: BaseModel | None = None
    error: str | None = None
    raw: dict | None = None          # for the runs/llm_calls audit trail
    attempts: int = 0
    provider_tokens: int | None = None

class LLMBackend(Protocol):
    async def health(self) -> tuple[bool, str]: ...
    async def complete_structured(
        self,
        *,
        schema: Type[T],
        system: str,
        parts: list[str],            # untrusted content goes HERE, never in `system`
        model: str | None = None,
        agent: str | None = None,
        tools: list[str] = (),       # default EMPTY: deny, don't allow
        retries: int = 2,
    ) -> StructuredCallResult: ...
    def stream_events(self): ...     # SSE passthrough for run progress (server backend only)
```

Two implementations: `OpenCodeServerBackend` (httpx, primary) and `OpenCodeCLIBackend` (subprocess, degraded). Both are ~150 lines; `STACK.md` Q7 settles *why* server-first and lists the endpoints. The architecture-relevant points are the three below.

### 6.2 Where structured-output validation belongs

**Schema lives in `domain/schemas/`; validation lives in `llm/`; the domain never sees an unvalidated dict.**

```
domain/schemas/patch.py          llm/opencode_server.py            pipeline/tailor.py
  TailoringPatch        ──uses──►  .model_json_schema()   ──wire──►  opencode
  (discriminated union)                                               │
        ▲                                                             ▼
        └──── .model_validate(info["structured_output"]) ◄───── structured_output
                    ↑
              ValidationError → bounded retry (retryCount/attempts) → StructuredCallResult(ok=False)
```

Three rules follow, and all three are architectural rather than stylistic:

1. **The domain does not import `httpx`.** The schema is a pure Pydantic model; a fixture test can validate a golden response with no server running.
2. **Validation happens once, at the boundary.** Retries on validation failure are the backend's job (opencode supports a `retryCount` and reports a `StructuredOutputError` when exhausted), so the domain receives either a typed object or an explicit failure — never a partial dict it must defensively re-check.
3. **A validation failure is a run outcome, not a crash.** It is recorded in `llm_calls` and surfaced; `STACK.md` Q7's contract test against `GET /doc` is what makes an opencode upgrade that renames `format`→`outputFormat` fail loudly in CI rather than silently in production.

### 6.3 Untrusted input crosses the LLM port, not the domain

Job descriptions are attacker-controllable (anyone can post a job). The architecture places the boundary at the port:

| Control | Where it is enforced | Not where |
|---------|---------------------|-----------|
| Listing text goes in `parts` (user turn), never `system` | `pipeline/narrate.py` constructs the call; `llm/base.py` has no `system`-from-data path | — |
| Tools are **denied by default** (`tools=[]`) | `LLMBackend.complete_structured` default argument | A ranking/tailoring call needs no tools at all |
| Instruction-like text in a listing is a **finding to record**, not an instruction | `domain/sanitize.py` scans and flags; the flag is persisted on the listing and shown in the UI | Never executed, never stripped silently |
| Response is schema-constrained | `format={"type":"json_schema","schema":...,"retryCount":2}` | The schema is the blast-radius limiter: an injection can only fill allowed fields |
| Server is bound to the compose network, password set, port unpublished | `compose.yml` | `STACK.md` Q8 |

### 6.4 Model/agent selection is a call parameter, not a global

Ranking uses many cheap calls at low stakes; tailoring uses few calls at high stakes. `model` and `agent` are per-call parameters supplied from settings/UI, discovered from `GET /provider` and `GET /agent` at startup. The two pipelines therefore can (and should) use **different models**, and the choice is recorded on `scores` and `cv_artifacts` so a regression can be traced to a model change.

### 6.5 Why the CLI fallback is a class, not a branch

`OpenCodeCLIBackend` implements the same Protocol. It loses SSE, pays process-spawn per call, and must parse structured output from stdout (fragile), and argv is an injection surface — but because it is a class behind a Protocol, switching is a settings change, not a refactor. `STACK.md` Q7 already committed to this; the architecture consequence is that **nothing outside `llm/` may import `httpx` or `subprocess`** — enforced by the same import-discipline test as `domain/`.

---

## 7. The Structured-CV Model (`.tex` → ID-stable data → patch → `.tex`)

This is the highest-risk area and the one the sibling files flagged as unmeasured (`STACK.md` Open Q6, `FEATURES.md` Gap 5: *the actual `.tex` is not available to research*). This section gives the target design and names the risks precisely.

### 7.1 The two-canonical-documents rule

| Document | Who it is canonical for | Mutability | Location |
|----------|------------------------|------------|----------|
| `cv/base.tex` | **The human.** Hand-authored, the "real" CV. | Immutable by the tool. The tool never rewrites it. | `/cv/base.tex` (volume) |
| `cv/cv.yaml` | **The machine.** The fact store the patch engine addresses. | Edited by import + explicit human curation | `/cv/cv.yaml` (volume) |
| `artifacts/<id>/cv.tex` | Neither. A **rendered derivative**. | Never edited | `/artifacts` (volume) |

The phrase "the `.tex` is the source of truth" is only true of `base.tex`. `cv.yaml` is a *derived* representation, and the derivation must be **verifiable**. That is the difference between this design and a fragile one.

### 7.2 Decomposition

```yaml
# cv/cv.yaml — schema_version 1
schema_version: 1
meta:
  name: "…"                     # id: meta.name
  contact: { email_id: c.email, phone_id: c.phone, links: [c.gh, c.li] }
sections:
  - id: sec.experience
    title_key: sec.experience   # a KEY, not free text → rendered from a translation map
    order: 10
    entries:
      - id: exp.acme
        org_id: org.acme                    # ← enumerated employer, not free text
        title_id: title.senior_engineer     # ← enumerated title, not free text
        start: 2021-03
        end: null                            # null = present
        location: "Dublin, IE"
        bullets:
          - id: b.acme.003                   # STABLE. Never renumbered.
            text: "Reduced p99 latency 40% by …"   # IMMUTABLE source text
            evidence: verbatim               # verbatim | grounded | unrecorded  (DF-6)
            metrics: ["40%", "p99"]          # extracted once, used by the verifier
            skills: [skill.python, skill.kubernetes]
  - id: sec.skills
    order: 30
    skills:
      - { id: skill.python,       label_key: skill.python,       group: languages, weight: 1.0 }
orgs:    [{ id: org.acme,   name: "Acme Ltd", aliases: ["Acme"] }]      # enumeration
titles:  [{ id: title.senior_engineer, name: "Senior Engineer" }]       # enumeration
gaps:    []      # unmet requirements live HERE, in their own collection — never in bullets
```

Four design properties carry the whole guarantee:

1. **Enumeration.** Employers (`orgs`), titles (`titles`) and skills (`skill.*`) are enumerated lists. The LLM's schema can express them as `Literal[...]`/`enum`, so a fabricated employer is not merely discouraged — it is unrepresentable.
2. **Immutability.** `bullet.text` is the source string. The patch engine may reorder, re-weight, demote and drop bullets; it can never rewrite one. Reframing in the JD's vocabulary is therefore a **presentation** decision (see §7.5) rather than a content mutation.
3. **`gaps` is a separate collection.** This closes the backdoor `FEATURES.md` DF-7 names: "never feed keyword gaps back into the prompt, which closes the obvious backdoor where an ATS miss turns into an invented bullet."
4. **`schema_version`.** The import, render and patch layers each assert it. A format change is a migration, not a surprise.

### 7.3 The patch (what the LLM actually returns)

```python
# app/domain/schemas/patch.py
from typing import Annotated, Literal
from pydantic import BaseModel, Field

class BulletMove(BaseModel):
    op: Literal["move_bullet"]
    bullet_id: str          # validated against the fact store's id set
    before_id: str | None   # None = first in section

class BulletWeight(BaseModel):
    op: Literal["reweight_bullet"]
    bullet_id: str
    weight: Annotated[float, Field(ge=0.0, le=2.0)]

class DemoteBullet(BaseModel):
    op: Literal["demote_bullet"]           # explicit demotion, MUST carry a reason
    bullet_id: str
    reason: str                            # displayed in the change log

class DropBullet(BaseModel):
    op: Literal["drop_bullet"]             # structural mutation — loud, not silent
    bullet_id: str
    reason: str

class ReorderSection(BaseModel):
    op: Literal["reorder_section"]
    section_id: str
    order: int

class GapFinding(BaseModel):
    requirement: str
    status: Literal["direct", "transferable", "adjacent", "gap"]
    evidence_ids: list[str] = []           # empty ⇒ must be 'gap'

PatchOp = Annotated[
    BulletMove | BulletWeight | DemoteBullet | DropBullet | ReorderSection,
    Field(discriminator="op"),                 # ⟨discriminated union — Pydantic v2
]

class TailoringPatch(BaseModel):
    listing_id: int
    ops: list[PatchOp]
    gaps: list[GapFinding]
    suggestions: list[dict] = []   # shown to the human; NEVER applied automatically
```

There is **no field anywhere in this schema that becomes text in the PDF**. Every string is either an id (validated), a reason (UI-only), or a requirement (echoed from the listing, shown in the gap checklist). That property — not prompt wording — is what makes fabrication structurally impossible *in the dimensions the schema covers*.

The discriminated union pattern is verified Pydantic v2 behaviour: a common `Literal` tag plus `Field(discriminator=...)` makes validation target only the matched variant and produces precise errors (`union_tag_invalid`) rather than error proliferation across all members.

### 7.4 Rendering back to `.tex`

`apply_patch(facts, patch) -> RenderPlan` is a **pure function** in `domain/cv.py`:

```python
def apply_patch(facts: CvFacts, patch: TailoringPatch) -> RenderPlan:
    # 1. verify every id in ops/gaps exists in the fact store  → raise IdNotFound
    # 2. verify no bullet appears twice, no section loses all entries
    # 3. verify dropped bullets all carry a reason
    # 4. build ordered RenderPlan; attach `changes: list[ChangeRecord]` for the UI diff
```

Then `latex/render.py` emits `.tex` through the LaTeX-safe Jinja2 `Environment` (`STACK.md` Q6: `\VAR{}`/`\BLOCK{}`, `autoescape=False`, mandatory `escape_tex` filter with backslash replaced first). The renderer is deterministic — **it must not call `now()`**; any date in a rendered CV comes from the fact store or the artifact row.

`RenderPlan.changes` *is* DF-8's change log. The patch is the audit trail; no separate bookkeeping is needed.

### 7.5 Risks, stated plainly

| # | Risk | Why it bites | Mitigation |
|---|------|--------------|------------|
| CV-R1 | **The real `.tex` may not decompose cleanly.** Macro-heavy documents (custom `\newcommand` resumes, `moderncv`, `awesome-cv`) can encode structure in macros rather than repeated environments. | `FEATURES.md` Gap 5 calls this "the largest unquantified cost in the plan". If the import is a two-week parser, the tailoring phase re-scopes. | **Spike first, on one section, before the tailoring phase is estimated.** Hard gate. If it fails, the fallback is to hand-author `cv.yaml` for the current content and treat `base.tex` as a one-time reference — acceptable, because it is a one-off cost. |
| CV-R2 | **Reproduction drift: `render(cv.yaml) != base.tex`.** If they are not equivalent, there are two truths and the tool silently replaces the user's real CV with a slightly different one. | The user's CV is their livelihood; a silently altered ordering or dropped bullet is a real harm. | A **golden test**: render the base CV from `cv.yaml` with an identity patch, extract text from both PDFs, and assert fact-equivalence (all orgs, titles, dates, bullet token-shingles present). Byte-equality is *not* required or expected. Fail the build on drift. |
| CV-R3 | **Page-count reflow.** Reordering/weighting can push a one-page CV to two pages, or two to three. | Recruiters and ATS filters both react to length; a tailoring that silently spills is a quality regression. | Assert `page_count <= facts.meta.max_pages` in the verifier (§10) and surface it as a **warning finding** so the human can choose. Never auto-truncate to fit. |
| CV-R4 | **"Reorder" quietly becomes "rewrite".** Prompting an LLM to "rephrase in the JD's vocabulary" without an id boundary is the documented fabrication path (`FEATURES.md` §4: 96.7% of baseline outputs contained an unsupported claim; 50% survived prompt guardrails alone). | This is the design's entire justification. | The schema has no text field on the path (§7.3). Reframing, if wanted, must be a *separate, human-approved* `Suggestion` object with its own evidence id and its own verification pass — never applied automatically. |
| CV-R5 | **Silent condensing (structural mutation).** Feeds the "drop content" path: 8 bullets rendered where the source had 10 reads as honest but is a subtle misrepresentation (documented as one of four fabrication modes). | Invisible to a text-containment check, because *removed* strings obviously are not present. | `DropBullet` is an explicit op with a reason; the verifier compares `set(rendered_bullets) == set(facts_bullets) - set(dropped_ids)` and fails on any mismatch (§10, check 3). |
| CV-R6 | **Presentation inflation.** Bolding or promoting a bullet the facts do not support could read as emphasis-on-a-thin-claim. | Not fabrication, but not neutral either. | `BulletWeight` is bounded (`0.0–2.0`), every re-weight is logged in `RenderPlan.changes`, and the diff view shows it. If weight ever maps to bold text, that mapping is a template decision that must be visible in the diff. |
| CV-R7 | **pdfTeX-only primitives in the existing preamble.** Tectonic is XeTeX-derived and rejects `\pdfcompresslevel` etc. | Compile fails on the user's real CV — a late, surprising blocker. | Sanitise the preamble before compiling; run the Tectonic spike on the real `.tex` *before* the tailoring phase (`STACK.md` Open Q6). |
| CV-R8 | **`base.tex` staleness.** Once `cv.yaml` exists, the human may edit `base.tex` out of habit and the two diverge. | The derived model becomes wrong without anyone noticing. | Treat `base.tex` as read-only after import; the golden test (CV-R2) runs in CI so divergence is caught. Optionally re-import on demand with a diff review. |

**Confidence: MEDIUM.** The design is sound and independently corroborated (`FEATURES.md` §4: three open-source implementations plus two academic evaluations converge on fact-store + ids + a separate veto pass). The *cost* is unknown because the input document is unknown. Nothing in this section should be planned as "day 1".

---

## 8. Deduplication Architecture

### 8.1 Where it sits, and why exactly there

Dedup sits **between normalisation and persistence-with-filtering** — specifically *before* the hard-rule filter and *before* any per-source cap. The ordering is not stylistic:

```
fetch all sources (uncapped within budget)
        ↓
sanitise
        ↓
normalise
        ↓
┌─ Tier 0: in-run collapse (same run, same source) ── in memory
│         key: canonical_url
├─ Tier 1: exact persistent upsert
│         key A: (source, source_listing_id)   WHEN source_listing_id IS NOT NULL
│         key B: (source, canonical_url)       FALLBACK  ← mandatory (see below)
├─ Tier 2: fuzzy cross-source merge
│         blocking key → rapidfuzz score → constraints → merge plan
└─ persist: listings + listing_sources + listing_dupes
        ↓
hard-rule filter  (only NOW)
        ↓
cap / batch-selection for ranking
```

**Why before the cap:** `FEATURES.md` §5 states it directly — "fetch fully → normalise → merge → *then* filter and cap". Filtering or capping first throws away the copy that carried the salary field. A listing that fails the salary filter on the board that omitted salary may pass on the merged record.

**Why the canonical-URL fallback key is mandatory.** JobSpy's own schema documents `id` as `str | None` — possibly absent. In SQLite a `UNIQUE` constraint treats NULLs as distinct, so a `UNIQUE(source, source_listing_id)` on a board that returns `id=None` for every listing **silently prevents zero inserts and permits unlimited duplicates**. That is the failure mode alignment item A2 exists to prevent. Implementation: a partial unique index on `(source, source_listing_id) WHERE source_listing_id IS NOT NULL`, plus an unconditional unique index on `(source, canonical_url)`.

### 8.2 The keys, in priority order

| Tier | Signal | Notes |
|------|--------|-------|
| 0 | raw `source_url` within the run | cheap in-memory collapse; boards repeat rows within a page set |
| 1a | `(source, source_listing_id)` | nullable → partial index |
| 1b | `(source, canonical_url)` | **always available**; the real Tier-1 workhorse |
| 2a | `canonical_url` **cross-source** | catches LinkedIn→ATS syndication where the board deep-links to the employer (this is what `job_url_direct` gives us) |
| 2b | normalised `(company, title, location, posted_week)` + `rapidfuzz.token_set_ratio ≥ θ` | the workhorse for genuinely different URLs |
| 2c | `content_hash` of the sanitised description | catches re-posts and syndicated identical descriptions |
| 3 | manual blocklist/allowlist rules | for companies that legitimately post many near-identical reqs |

**URL canonicalisation** (a pure, unit-tested function in `domain/listing.py`): lowercase scheme and host, drop default ports, strip tracking parameters (`utm_*`, `gh_src`, `lever-source`, `src`, `ref`, `trk`), sort remaining query params, drop the fragment, normalise a trailing slash, and prefer `direct_url` over `source_url` when present. This is standard URL-normalisation practice (CIKM/CIKM-adjacent literature and the Web URL-normalisation line of work) applied at the job-listing level, and it is what makes `direct_url` valuable — verified: for LinkedIn, `job_url_direct` requires the extra `linkedin_fetch_description` pass, which is why R4 (budgeted second pass) and Tier-2a (canonical URL dedup) reinforce each other.

### 8.3 Merge policy — merge, don't discard

When a merge is decided:

- **Union the fields.** Prefer non-null; prefer the more complete description; prefer `salary_source='direct_data'` over `'description'`.
- **Keep every source reference.** All `listing_sources` rows move to the surviving `listing_id`; all apply URLs are retained. This is what makes DF-13 ("also seen on…") free.
- **Choose a canonical source deliberately:** employer ATS posting (`direct_url` present) > most recently updated > most complete. Record the choice and the reason.
- **Never delete the absorbed listing.** Mark it and keep the merge record.
- **Record reversibility:** `listing_dupes(listing_id, dup_listing_id, method, score, snapshot_json, merged_at, reverted_at, reverted_by)`. `snapshot_json` holds the pre-merge field values of the survivor so a revert restores them. `FEATURES.md` TS-3 is explicit that a false merge is the worst failure mode, so it must be undoable.

### 8.4 What dedup needs (dependencies)

| Need | Provided by |
|------|-------------|
| Canonicalisation + normalisation pure functions | `domain/listing.py` (no deps) |
| Fuzzy string scoring | `rapidfuzz` (`STACK.md` supporting libs) |
| A blocking strategy so Tier 2 is not O(n²) | `domain/dedup.py` — bucket by `(company_token, title_token_set)` then compare within bucket |
| Geolocation matching | normalised location tokens + country code. **Not** a geocoder in v1 — out of scope, and exact geocoding earns nothing at this scale |
| Posted-date window | `posted_at` (± 3 days) or `first_seen_at` week bucket. The literature uses a much wider window (60 days) for *repost series*, but that is a separate concern from *cross-source duplicate* |
| Re-runnability | A `dedup reconcile` command, because thresholds can only be tuned once a real corpus exists (`FEATURES.md` Gap 3) |
| A health metric | merge rate per run, plus a "print the rows behind the number" listing view — `FEATURES.md` §5: "Every deduplication bug I've shipped looked perfectly reasonable as a percentage and obviously wrong as a list of titles." |

**Confidence: MEDIUM-HIGH on the hierarchy** (multiple independent production write-ups converge), **LOW on the specific threshold θ** for this corpus — untunable in advance, so it must be a setting with a tuning task rather than a constant.

---

## 9. Persistence Schema Sketch

SQLite (WAL) + SQLAlchemy 2.0 + Alembic, per `STACK.md` Q4. This is concrete enough to become the schema phase's input. Column lists are the *load-bearing* columns, not exhaustive DDL.

### 9.1 Core tables

```
sources
  id PK · name UQ (linkedin|indeed|adzuna|…) · display_name · enabled · transport
  capabilities_json          # mirrors SourceCapabilities — so the UI can explain "why
                             # can't I filter by salary on LinkedIn?"
  rate_limit_json            # max requests/window, politeness config
  quota_json                 # Adzuna-style monthly quota {limit, used, window_reset_at}
  last_probe_at · health ('ok'|'degraded'|'unreachable')
  tos_audited_at             # STACK.md: "re-audit source ToS quarterly; record the date"
  robots_policy_json         # what robots.txt said, and when it was checked
  UNIQUE(name)

searches                          # a saved criteria set (FEATURES §5: named criteria sets)
  id PK · name · enabled · is_default
  criteria_json             # keywords, include[], exclude[], location, radius,
                            # remote, salary_floor, seniority[], job_type[]
  schedule_cron             # null = manual only
  version INT               # incremented on every edit → scores reference it
  last_run_at · created_at · updated_at
  # ONE last_run_at PER SEARCH, not global. A single global last_run breaks the
  # "new since your last check" computation the moment there is >1 search.

runs
  id PK · search_id FK · trigger ('manual'|'schedule')
  started_at · finished_at · status ('running'|'done'|'failed'|'partial')
  source_counts_json        # {linkedin: {fetched, status}, indeed: {...}}
  fetched_count · deduped_count · filtered_count · ranked_count
  llm_calls · llm_tokens
  errors_json               # structured, not a text blob
  # One row per run makes "why is the queue empty today?" answerable (TS-9).
```

```
listings                          # the CANONICAL, deduped job
  id PK
  canonical_url UQ
  apply_url                 # best available apply target (direct_url preferred)
  title · title_norm
  company_id FK→companies  · company_norm
  location_raw · city · region · country_code · location_norm
  remote_flag BOOL NULL · seniority
  description (sanitised) · description_hash
  salary_min · salary_max · salary_interval · salary_currency · salary_source
  posted_at
  first_seen_at NOT NULL    ◄── cannot be backfilled   (TS-2)
  last_seen_at  NOT NULL    ◄── cannot be backfilled   (TS-2)
  content_hash  NOT NULL    ◄── cannot be backfilled   (TS-2)
  is_active BOOL · inactive_since
  quality_signals_json      # age, resightings, missing salary, completeness (DF-10)
  source_extras_json        # per-board fields that don't deserve a column (R6)
  created_at · updated_at

companies                         # normalisation anchor for dedup + "also seen on"
  id PK · name · name_norm UQ · aliases_json · created_at

listing_sources                   # many sources → one listing  (the payoff of pluggable adapters)
  id PK · listing_id FK
  source FK→sources.name
  source_listing_id                 # NULLABLE — verified JobSpy contract
  source_url · direct_url
  first_seen_at · last_seen_at
  raw_hash                          # hash of the raw payload, to detect silent field changes
  UNIQUE(source, canonical_url_of_source)                     -- always present
  PARTIAL UNIQUE(source, source_listing_id) WHERE source_listing_id IS NOT NULL

listing_dupes                     # audit + REVERSIBILITY (TS-3)
  id PK · listing_id FK · dup_listing_id FK · method · score · snapshot_json
  merged_at · reverted_at · reverted_by

listing_events                    # APPEND-ONLY. The DF-11 input.
  id PK · listing_id FK · event_type ('save'|'unsave'|'hide'|'unhide'|'shortlist'|'view')
  occurred_at NOT NULL · context_json · run_id NULL FK
  # Written from migration 0001 because DF-11 cannot be backfilled (TS-16).

listing_exclusions                # "why is this NOT in my queue?" (TS-5/TS-9)
  id PK · listing_id FK · run_id FK
  rule_id · rule_kind · detail_json · created_at
```

```
scores                            # DF-3: PER-FACTOR, never one opaque number
  id PK · listing_id FK · run_id FK
  search_id FK · criteria_version INT     # so a re-weight/re-rank is reproducible
  rubric_version · backend · provider · model
  factor_scores_json
    # { "skills":       {"phi": 0.82, "evidence_ids": ["b.acme.003","skill.k8s"], "note": "…"},
    #   "experience":   {"phi": 0.70, "evidence_ids": [...], "note": "…"},
    #   "location":     {"phi": 1.00, …}, "salary": {"phi": 0.40, …},
    #   "seniority":    {...}, "semantic": {...} }
  total_score FLOAT            # computed IN CODE: U = Σ w_f·φ_f   (DF-3)
  weights_json                 # the weights used → sliders recompute locally, no LLM call
  confidence_tier ('high'|'medium'|'low')
  rationale TEXT               # LLM narrative over pre-computed evidence (DF-4)
  strengths_json · gaps_json   # DF-5
  created_at
  UNIQUE(listing_id, run_id, criteria_version)
```

```
cv_versions
  id PK · label · schema_version
  facts_json                    # full CvFacts snapshot — what was true at this version
  source ('import'|'manual') · created_at · is_current BOOL

cv_artifacts
  id PK · listing_id FK
  base_cv_version_id FK · patch_json (the TailoringPatch as returned)
  change_log_json               # RenderPlan.changes — DF-8 for free
  tex_path · pdf_path · tex_hash · pdf_hash
  compiled_at · compile_status ('ok'|'failed'|'blocked')
  compile_log TEXT
  verification_json             # {passed, checks:[{id,status,detail}], findings:[]}   ◄── §10
  page_count · ats_checks_json
  backend · provider · model
  created_at
  # 'blocked' artifacts are stored for diagnosis but are NOT downloadable and
  # NOT linkable from applications. Enforced in the repository layer.

applications
  id PK · listing_id FK
  status ('discovered'|'queued'|'shortlisted'|'applied'|'interviewing'|'offer'|'rejected'|'withdrawn')
  cv_artifact_id FK NULL        ◄── THE differentiator: the exact artefact sent (DF-9)
  applied_at · next_action_at   # next_action_at = applied_at + N days (follow-up nudge)
  notes TEXT · created_at · updated_at

application_events
  id PK · application_id FK · from_status · to_status · occurred_at · note
  # append-only: the history is never mutated, so response-rate analytics later
  # do not depend on rows that were edited in place.
```

```
llm_calls                         # cost + audit. Surfaces latency and failures.
  id PK · run_id NULL · purpose ('rank'|'narrate'|'tailor'|'extract'|'probe')
  backend ('server'|'cli') · provider · model · agent
  prompt_tokens · completion_tokens · latency_ms
  status ('ok'|'invalid'|'timeout'|'error') · attempts · error
  created_at

source_request_log                # politeness + quota ledger (STACK.md Q1 implications)
  id PK · source FK · run_id NULL · occurred_at · kind ('search'|'detail')
  status_code NULL · ok BOOL · note
```

### 9.2 FTS5 and indexes

- `listing_fts` — FTS5 external-content table over `listings(title, company_norm, description)`, `tokenize='porter unicode61'`, kept in sync with triggers or SQLAlchemy `after_commit` listeners (`STACK.md` Q4). BM25 via `rank`. Never `LIKE '%term%'`.
- Indexes: `listings(is_active, first_seen_at DESC)` for the queue; `listings(company_norm, title_norm)` for dedup blocking; `listing_events(listing_id, occurred_at)`; `scores(listing_id, total_score DESC)`.
- **Dedup blocking index:** a generated/maintained `blocking_key` column on `listings` (e.g. `company_token || '|' || title_token_set_signature`) with a plain index, so Tier-2 candidate lookup is an indexed equality, not a scan.

### 9.3 The `search` port

FTS is behind `search/fts.py` with a documented Postgres `tsvector`+GIN alternative, satisfying `STACK.md` Q4's portability requirement. Domain code calls `repo.search(text, filters)`; it never writes SQL.

### 9.4 Schema-phase acceptance criteria

The migration set is "done" when all of the following are true, because each one is a thing that cannot be added later without inventing history:

1. `first_seen_at`, `last_seen_at`, `content_hash` are `NOT NULL` on `listings`.
2. `listing_events` exists and is append-only.
3. `scores.factor_scores_json` + `weights_json` + `criteria_version` exist (not `total_score` alone).
4. `cv_artifacts.verification_json` exists and `compile_status` can be `'blocked'`.
5. `applications.cv_artifact_id` exists.
6. The partial unique index on `(source, source_listing_id)` and the unconditional `(source, canonical_url)` index both exist.
7. `sources.capabilities_json` and `sources.tos_audited_at` exist.
8. `listings.blocking_key` exists and is indexed.
9. Alembic is at revision 0001 with `alembic upgrade head` exercised in the container build.

---

## 10. The Anti-Fabrication Verification Stage

### 10.1 Where it sits

**Immediately after compile, before persistence-as-usable, and before any application can reference the artifact.** It is the last stage of the tailor pipeline and it is a **gate**, not an audit.

```
facts snapshot ─────┐
patch ──────────────┤
extracted PDF text ─┴──► C13 VERIFIER ──► VerificationResult ──► PASS ⇒ artifact persistable
requirements ───────┘                                          └► BLOCK ⇒ artifact 'blocked',
                                                                            findings surfaced,
                                                                            NOT downloadable,
                                                                            NOT linkable
```

Three placement facts matter:

1. **It runs on the rendered artefact, not on the patch.** The patch is already schema-validated, so *id-level* fabrication is impossible by construction. The verifier exists to catch what the schema cannot: text that arrived through the template, the preamble, or a renderer bug. Belt and braces, deliberately.
2. **It runs on every artefact, including a profile/base render.** A base render with an identity patch is the regression check that guards CV-R2 (reproduction drift).
3. **It is a stage in the pipeline, so it can be unit-tested with fixtures** — feed it a `facts` snapshot, a patch, and an extracted-text string; assert pass/fail. No LLM, no compiler, no network.

### 10.2 What it consumes and produces

**Consumes:**

| Input | Source | Why |
|-------|--------|-----|
| Compiled PDF text | `pypdf` extraction of `artifacts/<id>/cv.pdf` | The verifier must judge what was actually rendered |
| `CvFacts` snapshot | `cv_versions.facts_json` for `base_cv_version_id` | The ground truth vocabulary (orgs, titles, bullets, skills, metrics) |
| The applied patch | `TailoringPatch` | To distinguish *declared* drops from *undeclared* ones |
| Rendered bullet/entry id set | `RenderPlan` | To compare "what should be present" with "what is present" |
| Listing requirements | `listings` / extracted requirements | To check that `gaps` didn't silently become content |

**Produces:**

```python
class CheckResult(BaseModel):
    id: str                     # "no_new_org", "bullet_conservation", …
    status: Literal["pass", "warn", "fail"]
    detail: str
    offending: list[str] = []

class VerificationResult(BaseModel):
    passed: bool                # False if ANY check is 'fail'
    checks: list[CheckResult]
    findings: list[str]         # human-readable, shown in the UI
    extracted_text_hash: str
    page_count: int
    verifier_version: str        # a change here explains a change in outcomes
```

Persisted verbatim into `cv_artifacts.verification_json`, so "what did the checker say about the CV I sent?" is answerable months later.

### 10.3 The checks

| # | Check | Catches | Status on failure |
|---|-------|---------|-------------------|
| 1 | **Id containment.** Every entry/bullet/skill id in the `RenderPlan` exists in the `CvFacts` snapshot. | renderer bugs, stale facts, patch/version mismatch | **fail** |
| 2 | **No new named entity.** Every organisation and title string in the extracted text maps to an `orgs`/`titles` entry (or an alias). Any capitalised proper-noun sequence that resolves to nothing is reported. | fabricated employer/title that somehow reached text | **fail** |
| 3 | **Bullet conservation.** `rendered_bullets == facts_bullets − declared_drops` exactly, both directions. | silent condensing (CV-R5) and silent addition | **fail** |
| 4 | **Metric containment.** Every numeric token in the PDF (percentages, counts, years-in-role) appears in the source facts for the region it occurs in. | invented metrics — "the hardest failure to detect post-hoc" | **fail** |
| 5 | **Temporal consistency.** No overlapping/contradictory date ranges; `end >= start`; no future dates in the past-tense section. | temporal fabrication (technology/dates that cannot coexist) | **fail** |
| 6 | **Requirement→evidence integrity.** Every `GapFinding` with status `direct`/`transferable` carries ≥1 `evidence_id` that exists; every requirement with no evidence is status `gap`. | "presenting adjacency as a direct match" | **fail** |
| 7 | **Injection residue.** No instruction-like marker detected at sanitise time reappears in the PDF. | listing text leaking into the CV | **fail** |
| 8 | **Page budget.** `page_count <= facts.meta.max_pages`. | reflow regression (CV-R3) | **warn** |
| 9 | **Layout/ATS assertions.** Single column where the template claims it, standard section headings present, dates in a parseable format (DF-15). | ATS parse failures | **warn** |
| 10 | **Exact-verbatim integrity for `evidence: verbatim` bullets.** A verbatim bullet's text in the PDF must contain the source text (modulo TeX escaping and whitespace). | a "verbatim" label that isn't | **fail** |

### 10.4 The governing policy: block, don't repair

On any `fail`, the artefact is stored with `compile_status='blocked'` and is **not** downloadable and **not** linkable from `applications`. The pipeline does **not** attempt an automatic fix. This follows the strongest finding in the sibling research (`FEATURES.md` §4): *drop rather than repair, because "repair pressure is fabrication pressure"*. Automatic repair is exactly the loop that reintroduces fabrication — the model is asked to fix a claim, and the cheapest way to satisfy the check is to rephrase rather than remove.

The UI shows the specific offending item plus a one-click "drop this bullet and re-render", which keeps the human in the loop at the point that matters — the same posture as assisted apply.

### 10.5 Two lines of defence, and why both

| Defence | Mechanism | Covers |
|---------|-----------|--------|
| **Structural (first)** | Schema-constrained patch over enumerated ids. No free-text field on the path to the PDF. | Cannot invent an employer, title, skill, metric, or bullet. Fabrication is *unrepresentable*. |
| **Verification (second)** | Text-level assertions over the compiled PDF against the fact snapshot. | Catches renderer bugs, template leakage, stale-fact mismatches, silent condensing, injection residue, reflow. |

Neither alone is sufficient (`FEATURES.md` §4: prompt guardrails alone left 50% of outputs with a fabrication; the human checkpoint was the complement). Here the "human checkpoint" is assisted apply plus the block-and-review policy — and the *structural* layer means the human is reviewing reordering decisions, not fact-checking prose.

---

## 11. The Auth-Later Seam

### 11.1 The cheap part (do this in v1)

```python
# app/api/deps.py
LOCAL_USER = User(id=settings.local_user_id, name="Local", email=None)

async def current_user() -> User:
    """v1: the single local user. Later: OIDC/Authentik via authlib.
    ROUTE SIGNATURES DO NOT CHANGE."""
    return LOCAL_USER
```

```python
@router.get("/queue")
async def queue(user: User = Depends(current_user), ...): ...
```

Every route, from day one, declares `user: User = Depends(current_user)`. FastAPI's documented pattern composes (a security scheme → `get_current_user` → `get_current_active_user`, with `SecurityScopes` flowing required scopes through the dependency chain), so the later implementation replaces only the body of `current_user`. This is exactly what `STACK.md` Q8 specifies and it costs nothing.

### 11.2 The part that is *not* free — state it honestly

`FEATURES.md` AF-12 notes that multi-tenancy "changes the data model (per-user CVs, per-user criteria, per-user keys) in ways that are expensive to retrofit if assumed in v1". The seam makes the **route layer** free. It does **not** make the **data model** free. Concretely:

| Concern | Status after the seam alone |
|---------|----------------------------|
| Route signatures unchanged when auth arrives | ✅ free |
| `Depends(current_user)` can start enforcing/raising 401 | ✅ free |
| Authentik forward-auth / OIDC behind a reverse proxy | ✅ free |
| Per-user listings, criteria, scores, CVs, applications | ❌ **requires a migration** (add `user_id`, backfill the local user, add uniqueness constraints) |
| Per-user LLM keys / models | ❌ out of scope entirely (opencode is shared) |

**Recommendation:** do **not** pre-add `user_id` columns in v1. Adding nullable `user_id` everywhere "just in case" buys nothing, complicates every unique constraint, and is itself a guess about a multi-tenancy model that has not been designed. Instead, record this table in the roadmap so the future migration is a known, bounded task rather than a surprise. What *is* worth doing now, and only this:

1. `Depends(current_user)` on every route.
2. A `settings.local_user_id` that is stable and non-empty (so a backfill has a value to use).
3. All repository functions take an explicit `user` or `user_id` argument **at the service layer** where it costs nothing to thread through — but do not add the column yet.

That last point is the pragmatic middle: the *call shape* carries the user, the *schema* does not. When the column arrives, the plumbing is already there.

**Confidence: HIGH** on the route seam (verified against FastAPI's documented dependency patterns). **MEDIUM** on the claim that no `user_id` is needed in v1 — it is a judgement call, and the risk is a single future migration (low) versus a permanently more complex schema (certain).

---

## 12. Patterns to Follow

### Pattern 1 — Ports with import discipline (hexagonal, enforced by a test)

**What:** The domain declares Protocols for everything external (`JobSource`, `LLMBackend`, repositories, `Renderer`, `Verifier`, `Clock`, `CurrentUser`). Adapters implement them. A single test asserts the import graph.
**When:** From migration 0001. Retrofitting this is the rewrite PROJECT.md's Key Decisions table exists to avoid.
**Trade-offs:** Slight ceremony (a Protocol + a registry) in exchange for the ability to swap a scraper transport, the LLM backend, or the database without touching domain logic. At this codebase size the ceremony is ~100 lines.

```python
# tests/test_import_discipline.py
FORBIDDEN_IN_DOMAIN = {"httpx", "sqlalchemy", "jobspy", "subprocess", "jinja2", "fastapi"}

def test_domain_is_pure():
    for module in modules_under("app.domain"):
        assert not (imported_names(module) & FORBIDDEN_IN_DOMAIN), \
            f"{module} imports I/O — move it behind a port"
```

### Pattern 2 — Total functions at the boundary

**What:** Every external call returns a **result object**, never raises for an expected failure. `FetchResult(status='partial')`, `StructuredCallResult(ok=False)`.
**When:** All adapter and LLM calls.
**Trade-offs:** Slightly more verbose call sites; in exchange, one board being blocked cannot abort a run, and one malformed LLM response cannot kill the queue build. This is the pattern that makes `runs.status='partial'` meaningful.

### Pattern 3 — Persist the decomposition, compute the aggregate

**What:** The LLM returns per-factor evidence and `φ_f` values; the code computes `U = Σ w_f·φ_f`. Weights are stored so re-weighting is a pure local recompute.
**When:** Ranking (DF-3), and the same shape applies to the freshness/quality score.
**Trade-offs:** More columns and a slightly larger prompt; in exchange, weight sliders are instant and free, re-ranking needs no LLM call, and LLM weight-instability becomes diagnosable (`FEATURES.md` §2: implicit weights shift between scoring and ranking framings — so keep the task *absolute scoring against a rubric*, never "rank these 40 jobs").

### Pattern 4 — Append-only event log beside mutable state

**What:** `listing_events` and `application_events` are insert-only. Current state lives on `listings`/`applications`; history lives in the event tables.
**When:** From migration 0001 for events; from the tracker phase for status history.
**Trade-offs:** Duplicate-ish data (a status column and the event that set it); in exchange, history is never lost to an in-place edit, and later analytics (response rate by tailoring strategy) are trustworthy.

### Pattern 5 — One pipeline callable, two triggers

**What:** `pipeline/run.py:run_pipeline()` is a plain async callable. The cron job calls it; the "Run search now" endpoint enqueues it and returns immediately.
**When:** From the first runnable pipeline.
**Trade-offs:** Requires the UI to poll or subscribe for progress; in exchange, manual and scheduled runs are behaviourally identical and share one log, one budget and one failure path.

### Pattern 6 — Stage-wrapped pipeline with structured run logging

**What:** Each stage is a callable with a name and a counter; the runner records per-stage counts and errors into `runs.errors_json` with `structlog`.
**When:** To make `FEATURES.md` TS-9 real rather than a promise.
**Trade-offs:** A little indirection; in exchange, "why did this listing get filtered?" and "which stage dropped 90% of the batch?" are answerable without re-running.

### Pattern 7 — Filesystem snapshots for artefacts, DB for metadata

**What:** `cv_artifacts` stores paths, hashes and metadata; `artifacts/<id>/` stores `cv.tex` + `cv.pdf`. Render the `.tex` **snapshot**, keep it forever.
**When:** Tailoring.
**Trade-offs:** Two things to keep consistent (mitigated by `tex_hash`/`pdf_hash`); in exchange, the exact bytes sent are recoverable, and the DB stays small enough to copy trivially.

---

## 13. Anti-Patterns

| # | Anti-pattern | What people do | Why it's wrong here | Do instead |
|---|--------------|----------------|---------------------|------------|
| AP1 | **Domain imports the scraping library** | `from jobspy import scrape_jobs` in a service | Every board breakage becomes a codebase-wide risk; the escalation ladder becomes untestable | `sources/_jobspy_transport.py` is the only importer (§3) |
| AP2 | **Let the LLM emit `.tex` or prose for the CV** | "Ask the model to rewrite the CV to match the job" | Unauditable, fabricates by construction, no diff, no verification hook (`FEATURES.md` AF-6) | ID patch → deterministic render (§7) |
| AP3 | **Store one opaque score** | `listing.score = 78` | Weight sliders, fit breakdown and cheap re-ranking all require an LLM call to recompute — the single most expensive thing to retrofit (`FEATURES.md` §2 "cheapest mistake to avoid, most expensive to retrofit") | `factor_scores_json` + `weights_json` (§9.1) |
| AP4 | **Filter or cap before merging** | Cap each source at 20 then dedup | You discard the copy that had the salary/description, then merge into a worse record | Fetch fully → merge → filter/cap (§8.1) |
| AP5 | **Dedupe by exact URL only, and delete the duplicates** | `UNIQUE(job_url)`; `DELETE` the loser | Misses every cross-source duplicate (different URLs), and a false merge destroys a real job with no recovery | Two-key Tier-1, fuzzy Tier-2, merge-not-discard, reversible audit (§8) |
| AP6 | **Run the pipeline inside the request handler** | `POST /run` awaits the whole scrape+rank | LLM ranking takes minutes; the request times out and the UI looks broken | Enqueue, return, surface progress via `runs`/SSE |
| AP7 | **Trust `UNIQUE(source, source_listing_id)` alone** | Assume `id` is always present | Verified: JobSpy's `id` is `str \| None`. SQLite allows unlimited NULLs in a UNIQUE index → duplicates multiply silently (A2) | Add the `canonical_url` fallback key + partial index (§8.1) |
| AP8 | **Devote a stage to "fixing" a failed verification** | Ask the model to repair the offending bullet | Repair pressure is fabrication pressure; the loop converges on rephrasing rather than removing | Block, surface, let the human drop it (§10.4) |
| AP9 | **Put listing text in the `system` prompt / leave tools enabled** | Convenience | Job descriptions are attacker-controllable; opencode exposes `/session/:id/shell` and `/file/*` | Untrusted text in `parts`, `tools=[]`, schema-constrained output, locked-down agent (§6.3) |
| AP10 | **Thread board-specific filters through the core** | `if source == "linkedin": drop_easy_apply()` in the pipeline | The core learns board trivia; adding a source edits the pipeline (R7) | Adapter `capabilities` + compiler warnings (§5.2 R3) |
| AP11 | **Persist recruiter emails/phones because they're in the payload** | Store `JobPost.emails` | GDPR exposure for zero product value; verified that the field exists and is populated | `RawListing` has no such field; sanitise at the boundary (§5.2 R2) |
| AP12 | **Re-parse the compiled PDF to recover CV content** | Use the PDF as the fact source | Lossy, brittle, and makes tailoring depend on a renderer artefact; explicitly rejected in `FEATURES.md` AF-10 | `cv.yaml` is the machine's fact store; PDF is terminal (§7.1) |
| AP13 | **Two schedulers via `--workers > 1`** | Scale uvicorn for a CRUD app | N workers ⇒ N schedulers ⇒ the nightly job runs N times | `--workers 1`; Postgres advisory lock only if you later scale out (`STACK.md` Q5) |
| AP14 | **Pre-add `user_id` columns "for later auth"** | Speculative multi-tenancy | Complexity now, a guessed model, and every unique constraint complicated — for a feature explicitly deferred | Route seam now; bounded migration later (§11.2) |
| AP15 | **Wide `listings` table with a column per board field** | `naukri_experience_range`, `indeed_revenue`, … | Schema churn on every new source; contradicts "adding a source adds rows, not schema" | `source_extras_json` (R6) |
| AP16 | **One adapter class with `site_name=["linkedin","indeed"]`** | Fewer classes | No per-board health, budget, capability or failure attribution; blocks per-board escalation | One adapter per board, one shared transport (A3 / §5.3) |

---

## 14. Suggested Build Order and Dependencies

### 14.1 Component dependency graph

```
                    ┌─────────────────────────────────────────────────┐
                    │ FOUNDATIONS                                     │
                    │ F1 skeleton+Docker+compose+settings             │
                    │ F2 schema migration 0001 (§9.4) + FTS5 + repos  │
                    │ F3 current_user seam                            │
                    │ F4 runs logging + /health + import-discipline   │
                    └───────┬───────────────┬───────────────┬─────────┘
                            │               │               │
        ┌───────────────────▼───┐   ┌───────▼────────┐  ┌───▼──────────────────┐
        │ TRACK A — INGESTION   │   │ TRACK B — LLM  │  │ TRACK C — CV/LATEX   │
        │ A1 adapter port+reg   │   │ B1 LLMBackend  │  │ C1 fact store        │
        │ A2 sanitise           │   │    port+server │  │    + .tex import     │
        │ A3 normalise          │   │    + /doc test │  │ C2 Tectonic spike +  │
        │ A4 Tier-1 upsert      │   │ B2 structured  │  │    compile harness   │
        │ A5 Tier-2 dedup       │   │    call +      │  │ C3 renderer + golden │
        │ A6 criteria store     │   │    validation  │  │    reproduction test │
        │    + compiler         │   └───────┬────────┘  │ C4 patch schema +    │
        │ A7 hard filter +      │           │           │    apply_patch       │
        │    exclusion reasons  │           │           │ C5 verifier          │
        │ A8 queue + detail UI  │           │           └───┬──────────────────┘
        │ A9 FTS search         │           │               │
        │ A10 new/stale badges  │           │               │
        └───────────┬───────────┘           │               │
                    │                       │               │
                    └───────────┬───────────┴───────────────┘
                                ▼
                    ┌───────────────────────────┐
                    │ TRACK D — RANKING         │  needs: A7, B2, C1
                    │ D1 rubric + φ_f factors   │
                    │ D2 weighted sum in code   │  ◄── ★ CORE VALUE ACHIEVED
                    │ D3 grounded narrative     │
                    └───────────┬───────────────┘
                                ▼
                    ┌───────────────────────────┐
                    │ TRACK E — TAILOR + APPLY  │  needs: C4, C5, D1
                    │ E1 tailor pipeline        │
                    │ E2 cv_artifacts + preview │
                    │ E3 assist package         │
                    │ E4 tracker + artifact link│
                    └───────────┬───────────────┘
                                ▼
                    ┌───────────────────────────┐
                    │ TRACK F — OPERATIONS      │  needs: A8
                    │ F5 scheduler (APScheduler)│
                    │ F6 source health UI       │
                    │ F7 export                 │
                    └───────────────────────────┘
```

### 14.2 Which components are prerequisites for which

| Prerequisite | Unlocks | Why it cannot be deferred |
|--------------|---------|---------------------------|
| **F2 (schema 0001)** | Everything | `first_seen_at`/`last_seen_at`/`content_hash` and the event tables cannot be backfilled. This is the single hardest ordering constraint in the project. |
| **F3 (auth seam)** | The whole route layer | Free now; a migration across every route later |
| **A1–A4** | A5, A7, A8, D1 | There is no queue without listings |
| **A5 (dedup)** | A7 quality, DF-13, DF-10 later | Filtering a duplicate-heavy feed produces a queue the user mistrusts immediately |
| **A6 + A7 (criteria + filter)** | **D1 (ranking)** | The filter is the cost gate; ranking's timeout and batching design depend on a bounded candidate set |
| **C1 (CV fact store)** | **D1, C3, C4, C5** | Ranking needs CV facts as prompt input; tailoring needs ids. **A prerequisite shared by both halves** — which is why it is worth doing early even though it is not user-visible |
| **C2 (Tectonic spike on the real `.tex`)** | The tailoring phase's estimate | `STACK.md` Open Q6 + `FEATURES.md` §7.6: the spike gates the phase. Doing it late means re-scoping late |
| **C5 (verifier)** | E1 | Verification ships **with** tailoring, not after (`FEATURES.md` §7.5: shipping tailoring first means shipping a fabrication window) |
| **D1–D3 (ranking)** | E1 | Tailoring needs requirements + gaps, which come from the ranking/fit pass |
| **E2 (artifact)** | E4 (tracker link) | The version↔outcome link is the differentiator; it needs the artifact to exist |

### 14.3 Suggested phases

The ordering below optimises for **(a) retiring the unknowns that can re-scope a phase, as early as possible**, and **(b) reaching the Core Value — one ranked, explained, apply-ready queue — as directly as possible**.

| Phase | Goal | Contains | Retires the risk |
|-------|------|----------|------------------|
| **1. Walking skeleton + foundations** | A listing scraped from LinkedIn/Indeed exists in the DB and is browsable | F1–F4, A1–A4, minimal A8 | **Scraper survival at personal scale is the project's biggest unknown** (`STACK.md` Open Q3). Prove it in week 1, not week 8 |
| **2. Clean, filtered, queryable queue** | No duplicates; hard rules applied with recorded reasons; runs observable | A5, A6, A7, A9, A10, exclusion UI, `runs` UI | Dedup thresholds need a real corpus (`FEATURES.md` Gap 3) — this phase produces it |
| **3. LLM port + structured output** (small) | Any schema-constrained call works end to end | B1, B2, `/doc` contract test | The `format` vs `outputFormat` ambiguity (A2/`STACK.md` Open Q4) |
| **4. CV fact store + LaTeX compile spike** — *runs in PARALLEL with 2–3* | `cv.yaml` exists and reproduces the CV; Tectonic compiles the real `.tex` | C1, C2, C3 | **The largest unquantified cost in the plan** (`FEATURES.md` Gap 5) and the Tectonic package/primitives risk (`STACK.md` Open Q6). Schedule this concurrent with Phase 2 so the tailoring phase is estimated with facts |
| **5. Ranking — ★ CORE VALUE** | One ranked, explained queue with per-factor breakdown and named gaps | D1, D2, D3 + weights UI | The batching/cost decision (`STACK.md` Open Q7) must be resolved *in this phase's plan* |
| **6. Tailoring + verification** | A tailored, **verified** CV PDF, previewable and downloadable | C4, C5, E1, E2, change log | Verification is not a follow-on |
| **7. Assisted apply + tracker** | Apply package + application tracking with the artefact link | E3, E4 | — |
| **8. Operations + polish** | Scheduled runs, source health, "also seen on", export | F5, F6, F7, DF-13 | — |

**Phase ordering rationale (the non-obvious parts):**

- **Phase 4 is deliberately parallel, not sequential.** It has no dependency on Phases 2–3 and it contains the project's biggest unknown. Serialising it behind the queue-building phases means discovering a Tectonic/CV-decomposition blocker at Phase 6 — after the roadmap has already promised a tailoring phase.
- **Ranking (5) precedes tailoring (6)** even though PROJECT.md lists tailoring first, because tailoring consumes requirement gaps produced by the ranking/fit pass. Ranking is also the Core Value; tailoring is downstream of it.
- **Scheduling (F5) is late on purpose.** A cron job that runs an unstable pipeline just hides failures. Manual "run now" is the right trigger until the pipeline is trustworthy.
- **No phase contains only infrastructure.** Phase 1 ships a browsable list; Phase 2 ships a usable queue. That keeps the walking skeleton *walking*.

**Explicitly deferred (do not plan these into v1):** Adzuna adapter #3 (P2, and a hedge — keep the interface ready), ghost/quality score as a first-class signal (DF-10, the fields are stored), provenance UI and gap checklist UI (DF-6/DF-7, the data model exists), grounded cover letter (TS-18, must reuse `evidence_ids` when built), feedback learning (DF-11, events captured now), Authentik OIDC (§11), MCP server, embedding pre-filter, Typst migration.

---

## 15. Scaling Considerations

This project's realistic envelope is **1 user → a handful of friends → possibly a hosted instance**. It will not need 100k users. The useful question is not "how does it scale" but "what breaks first, and is the fix a config change or a rewrite".

| Scale | Architecture | What changes |
|-------|--------------|--------------|
| **1 user (v1)** | One uvicorn worker, one SQLite file, scheduler in-process, `opencode` sidecar, Tectonic in the app image | — |
| **2–10 users (friends)** | **Same process, same DB.** Add a `user_id` migration, per-user `searches`/`cv_versions`/`applications`, and route-level auth (Authentik OIDC via the seam). | Migration + auth wiring. **No architectural change.** LLM cost is the only new pressure, and it is bounded by the existing filter gate |
| **10–100 users (hosted)** | Split the pipeline into a worker container; Postgres replaces SQLite; scheduler guarded by `pg_advisory_lock`; artefacts to object storage | The documented `STACK.md` Q4/Q5 escape hatch: DSN swap, `aiosqlite`→`asyncpg`, Postgres FTS implementation, advisory lock. Days, not a rewrite |
| **>100 users** | Out of scope. Would require per-user LLM budget isolation, scraper-proxy spend, and a job-queue with retries | Not designed for, and not needed |

### 15.1 What breaks first, in order

1. **The long-running pipeline monopolises the single worker.** Scraping + LLM ranking takes minutes; while it runs, HTTP requests contend for the event loop and the UI feels dead. This is the *first* real pain — and it is a UX failure, not a crash.
   *Fix (cheap):* the pipeline already runs as a background task rather than inline; if it still starves the loop, isolate the blocking parts (JobSpy is synchronous and uses a `ThreadPoolExecutor` internally; Tectonic is a subprocess) with `run_in_executor` / `asyncio.to_thread`.
   *Fix (structural):* a separate worker container, which is also the fix for `STACK.md` Open Q8 (JobSpy's pandas/numpy weight in the FastAPI image).
2. **SQLite write contention.** Currently one nightly writer. With 10 users, concurrent criteria edits + tracker updates exceed comfortable single-writer behaviour.
   *Fix:* Postgres (`STACK.md` Q4). The schema is already portable by design; the FTS layer is behind a port.
3. **Scheduler duplication.** The moment `--workers > 1` or a second container appears, the nightly job runs more than once.
   *Fix:* `pg_advisory_lock` around job execution (`STACK.md` Q5).
4. **LLM cost and latency.** The dominant variable cost. Unbounded until Phase 2's filter exists.
   *Fix:* already designed — filter before rank; batch the ranking call if `STACK.md` Open Q7 resolves that way; store `llm_calls` so the cost is visible per run.
5. **Scraper degradation.** Not a scale problem — a *constant* condition. More runs and more users accelerate blocking.
   *Fix:* the adapter interface + escalation ladder; Adzuna as the hedge; per-source health surfaced in the UI.

### 15.2 Scaling priorities

1. **Protect the event loop** (background the pipeline, isolate blocking calls) — highest impact for the least work, and needed even at 1 user.
2. **Make the LLM gate airtight** (the hard-rule filter) — cost scales linearly with users and is the only genuinely variable expense.
3. **Keep the Postgres path open by design, not by hope** (Alembic from 0001, no SQLite-only types, FTS behind a port).

---

## 16. Integration Points

### 16.1 External services and processes

| Service | Integration pattern | Notes / gotchas |
|---------|--------------------|-----------------|
| **opencode (`serve`)** | `httpx` client over the compose network; `GET /global/health` probe at startup and in `/health` | Password-protected (`OPENCODE_SERVER_PASSWORD`) even locally; **port not published**; version pinned; `/doc` contract test in CI (`STACK.md` Q7/Q8) |
| **opencode (CLI)** | `asyncio.create_subprocess_exec`, structured output parsed from stdout | Degraded fallback only; argv is an injection surface — never interpolate listing text into argv |
| **JobSpy** | Imported **only** in `sources/_jobspy_transport.py`; synchronous, wraps a `ThreadPoolExecutor` internally | Install from git and pin a commit (`STACK.md` Q1); brings pandas/numpy; returns `id=None` for some boards and an `emails` field that must be dropped |
| **Tectonic** | `asyncio.create_subprocess_exec` with **no `-Z shell-escape`**; compile in a temp dir inside the image, copy artefacts out | Prime the package cache at image build so offline compilation works; `Dockerfile.texlive` kept as a fallback; sanitise pdfTeX-only primitives from the preamble (`STACK.md` Q6) |
| **Adzuna** (P2) | `httpx` against `api.adzuna.com`; quota-aware | ~1,000 calls/month free tier; every call logged to `source_request_log`; never a per-view live call (DF-14) |
| **LinkedIn / Indeed** | **No direct integration.** Reached only through adapters, which use JobSpy's reverse-engineered internals | robots.txt respected and recorded; no auth bypass; no CAPTCHA solving; honest User-Agent; rate ceilings in config (`STACK.md` Q1) |
| **Authentik** (later) | Standard OIDC; `authlib` in the `current_user` dependency, or forward-auth at a reverse proxy | Unblocked by the seam (§11); not built in v1 |
| **ntfy** (later) | One batched digest POST per run | Never per-listing pushes; "always have a deduper" (`FEATURES.md` §6) |
| **SQLite file** | Volume-mounted at `/data`; WAL + `foreign_keys=ON` + `busy_timeout` | Backup = copy the file (+ `-wal`); verify `ENABLE_FTS5` in the container's `PRAGMA compile_options` |
| **Filesystem volumes** | `/cv` (fact store + base `.tex`), `/artifacts/<id>/` (rendered `.tex` + PDF) | Artefacts are never GC'd silently — an unverified/blocked artefact is retained for diagnosis |

### 16.2 Internal boundaries — communication rules

| Boundary | Communication | Notes / enforcement |
|----------|---------------|---------------------|
| `api/` + `web/` ↔ `pipeline/` | Direct async function calls; long work **enqueued** | Never await a full pipeline inside a request handler (AP6) |
| `pipeline/` ↔ `sources/` | `JobSource` port; `SearchQuery` in, `FetchResult` out | Adapters never see the DB (R5) |
| `pipeline/` ↔ `llm/` | `LLMBackend` port; Pydantic schema in, typed model or explicit failure out | Domain does not import `httpx`; schemas live in `domain/schemas/` |
| `domain/` ↔ `db/` | Repository Protocols; domain defines the interface | Domain has no SQL; repositories have no business rules |
| `pipeline/` ↔ `latex/` | `Renderer` / `Compiler` / `Verifier` ports; `RenderPlan` in, `VerificationResult` out | The verifier is a *gate*: an `Application` may only reference an artifact whose `verification_json.passed` is true — enforced in the repository, not the template |
| `jobs/` ↔ `pipeline/` | One callable (`run_pipeline`) | One path, two triggers (Pattern 5) |
| `web/` ↔ `artifacts/` | `FileResponse` for the PDF, gated on `compile_status='ok'` | A blocked artifact must return 404/403, not the file |

---

## 17. Open Questions and Gaps

Carry these into roadmap research and phase planning. Each is a place where this file deliberately stopped short.

1. **Does the real `.tex` decompose into `cv.yaml` cleanly? (HIGHEST PRIORITY)** The `.tex` is **not in this repository**, so this is unmeasured. `FEATURES.md` Gap 5 calls it "the largest unquantified cost in the plan". **Answered by doing, not reading** — import one section before the tailoring phase is estimated. If it fails, the fallback (hand-author `cv.yaml` once) is acceptable but changes the phase's shape.
2. **Tectonic's bundle coverage for the real preamble.** Unknown until the actual document is compiled. May force `LATEX_ENGINE=texlive` and change the image. Gate with a spike (`STACK.md` Open Q6).
3. **Ranking batching: one call per listing, or one call per K listings?** Changes cost, timeout design, and whether `prompt_async` + SSE progress is required. Resolve *in the ranking phase's plan* (`STACK.md` Open Q7, `FEATURES.md` Gap 1).
4. **Can `job_url_direct` be populated affordably for Indeed?** Verified for LinkedIn (requires the O(n) description pass); unclear for Indeed. This determines how much of Tier-2a (canonical-URL cross-source dedup) is actually available, and therefore how hard Tier-2b has to work.
5. **Dedup threshold θ and the merge-rate sanity band.** Untunable without the user's real corpus. Plan a tuning task with data in hand rather than freezing a constant (`FEATURES.md` Gap 3).
6. **Measure the real LinkedIn/Indeed survival rate at personal scale.** No first-hand evidence exists (`STACK.md` Open Q3). The Phase 1 walking skeleton is the cheapest place to answer it — and the answer determines whether Adzuna gets promoted from hedge to primary.
7. **Does a blocked artefact need an "override" path?** §10.4 says block-and-do-not-repair. But a false-positive verifier check (e.g. a legitimate proper noun that is not an employer) would be frustrating. A recorded, human-acknowledged override with a reason is the likely compromise — **not designed in v1**; decide after the first real failure.
8. **Is the single-event-loop pipeline acceptable, or is a worker container needed from day one?** Depends on measured run duration and JobSpy's memory footprint (`STACK.md` Open Q8). Revisit after Phase 1.
9. **Where does requirement extraction happen?** This file assumes requirements are extracted once per listing (cached on the listing) rather than per tailoring call. That choice affects LLM cost and the `scores`/`cv_artifacts` boundaries; it should be settled in the ranking phase, not discovered in tailoring.

---

## 18. Sources

**Verified library and API contracts (primary) — HIGH**
- **JobSpy documentation site** (`speedyapply-jobspy.mintlify.app`, generated Mar 2026 from commit `fda080a`) — JobPost schema reference and the LinkedIn job-board page. Directly sourced four architecture-relevant facts: `id: str | None`; `job_url` vs `job_url_direct`; `emails: list[str]`; board-specific field lists; `linkedin_fetch_description` O(n) cost and rate-limit behaviour; LinkedIn's single-filter limitation. — **HIGH** (project's own docs)
- **JobSpy README** (`speedyapply/JobSpy`) — `scrape_jobs()` parameter list, `JobPost` schema, per-board support. — **HIGH**
- **Pydantic v2 documentation** — discriminated unions with `Field(discriminator=...)`, `Literal` tagging, nested `Annotated` discriminators, `Discriminator` instances with `Tag`. — **MEDIUM** (via Context7)
- **SQLAlchemy 2.0 documentation** — `DeclarativeBase` + `Mapped`/`mapped_column`, `create_async_engine`/`async_sessionmaker`, `MutableDict.as_mutable(JSONEncodedDict)`. — **MEDIUM** (via Context7)
- **FastAPI documentation** — `get_current_user` dependency pattern, `OAuth2PasswordBearer`, `SecurityScopes`, dependencies with `yield`. — **MEDIUM** (via Context7)

**Ecosystem / interface design — MEDIUM–LOW**
- Python typing documentation, *Protocols and structural subtyping*; Python discussion threads on `runtime_checkable` caveats and ABC-vs-Protocol trade-offs; PyPA *Entry points specification*; Real Python *Implementing Interfaces in Python*. — **LOW-MEDIUM** (structural claims corroborated across sources; the `runtime_checkable` name-only-check caveat is from CPython maintainers)
- `pydantic-ai` `_adapter.py` — real-world coexistence of `@runtime_checkable Protocol` (state handlers) and an `ABC` base (UI adapters). — **LOW** (illustrative, not authoritative)

**Deduplication**
- *A Framework for Duplicate Detection from Online Job Postings* (ACM, CIKM 2021, Adzuna Australia corpus) — duplicate proportions up to 50–80% in crawled aggregations; 60-day window for repost series; block-then-compare pipeline. — **MEDIUM**
- URL-normalisation literature (*URL normalization for de-duplication of web pages*, CIKM 2009; *A Pattern Tree-based Approach to Learning URL Normalization Rules*, WWW 2010; *De-duping URLs with Seq2Seq*, SIGIR 2017). — **MEDIUM**
- Aggregator engineering write-ups and open-source implementations (CleanJobData; Canaria; `apifyforge/job-market-intelligence`; `Ethanhndez/Job-Agent`; `OppaAI/Aiko-chan`) — canonical-URL-first, merge-not-discard, the risk of weak composite keys (e.g. `company + title[:60]`). — **LOW-MEDIUM** (engineering blog / README grade; used for corroboration only)

**Inherited from the sibling research files (not re-verified here)**
- `STACK.md` — FastAPI/SQLAlchemy/Alembic/APScheduler/Tectonic/JobSpy/opencode decisions, SQLite WAL + FTS5 guidance, the opencode endpoint and structured-output field-name ambiguity, the compose shape, the `current_user` seam.
- `FEATURES.md` — TS-*/DF-*/AF-* inventory; the anti-fabrication evidence base (the 180-run guardrail-vs-checkpoint study; the five-layer grounded-optimisation framework; TailorCV/`aarg`/`resume-honest` patterns); the fetch→merge→filter ordering rule; the JobMatchAI per-factor scoring precedent and adjustable-weight user study; note that `strata-match` and `redrob-hirefit-ranker` are the evidence for a cheap gate and against embeddings-as-ranking.

**Confidence summary**

| Area | Confidence | Reason |
|------|-----------|--------|
| Pipeline shape and component boundaries | **HIGH** | Follows directly from PROJECT.md's stated constraints plus the settled stack; no external unknown |
| Adapter interface contract | **HIGH** | Port shape is standard hexagonal; the *details* (nullable `id`, `job_url_direct`, `emails`, O(n) description cost, single-filter limitation) are verified from JobSpy's own docs |
| Dedup architecture | **MEDIUM-HIGH** | Hierarchy converges across independent sources; **thresholds are LOW confidence** and untunable in advance |
| Structured-CV model and patch | **MEDIUM** | Design is strongly corroborated; **the real `.tex` is unavailable**, so import cost is unknown |
| Verification stage | **MEDIUM-HIGH** | Placement follows from the constraint "a pipeline stage, not an afterthought"; the check list is designed here rather than sourced |
| Persistence schema | **MEDIUM-HIGH** | Concrete and internally consistent; exact column choices will shift in the schema phase |
| Auth-later seam | **HIGH on routes / MEDIUM on data model** | Route pattern verified against FastAPI docs; the claim that no `user_id` is needed in v1 is a judgement call |
| Build order and phases | **MEDIUM-HIGH** | Derived from an explicit dependency graph; the parallel-track recommendation for the LaTeX spike is the highest-value judgement in the file |

---

*Architecture research for: AI-assisted job search automation (local, self-hosted, Python-first, Dockerised)*
*Researched: 2026-09-15*
