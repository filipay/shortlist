<!-- GSD:project-start source:PROJECT.md -->

## Project

**Shortlist**

A local, self-hosted job-search pipeline for the author and a few friends. It
aggregates listings from pluggable sources (LinkedIn and Indeed first), cuts them
down with deterministic rules, ranks the survivors with an LLM against the user's
CV and stated preferences, produces an honest tailored CV per job, and exposes a
web UI to browse, review, and track applications.

It exists to replace the daily dead time of manually checking portals, reading
every listing, judging fit from scratch, and hand-editing a CV — turning that loop
into one ranked, review-ready queue. The human stays in the loop at the point that
matters: they review the draft and press submit themselves.

**Core Value:** Every morning there is one ranked, explained, apply-ready queue of jobs worth
considering — so the search→judge→tailor loop costs minutes instead of hours.

If everything else fails, this must work: listings come in, get filtered, get
scored against the user's CV with a reason attached, and land in a queue the user
can act on. Every other feature is downstream of that.

### Constraints

- **Tech stack**: Python-first backend — the scraping, LLM, PDF/LaTeX, and
  scheduling ecosystems are strongest there, and the user selected it explicitly.
- **CV source format**: LaTeX. Tailoring must operate on `.tex` and compile to PDF.
- **LLM backend**: opencode (`serve` preferred, CLI fallback). No second provider
  key should be required for v1.
- **Deployment**: Docker container on a local machine. Must remain portable to a
  hosted deployment later without a rewrite.
- **Legal / ToS**: LinkedIn and Indeed actively detect and ban automation. This is
  why applying is assisted-only and why scraping approach must be validated before
  it becomes load-bearing.
- **Privacy**: CVs and personal job-search data are sensitive. Everything runs
  locally for v1; no third party sees the user's CV content.
- **Auth**: none in v1. The code should not architecturally block adding Authentik
  OAuth later, but must not pay for it now.
- **Cost**: LLM calls are the dominant variable cost. Hard-rule filtering before
  ranking is a deliberate cost-control measure, not an optimisation to skip.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->

## Technology Stack

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | **3.13** | Runtime | Every dependency below has 3.13 wheels. **Do not use 3.14 yet** (local machine is on 3.14.7, but Playwright/curl_cffi/lxml wheel coverage is the risk) — pin 3.13 in the Docker image. |
| **FastAPI** | **0.141.1** (MIT) | HTTP API + server-rendered UI | Async-first for fan-out I/O (N sources concurrently + LLM calls), Pydantic v2 native, OpenAPI for free, tiny container footprint. Both closest prior-art projects (Resume-Matcher, TailorCV) chose it. |
| **JobSpy** (`speedyapply/JobSpy`) | git `main` (PyPI `python-jobspy` is 1.1.82, 2025-07-28) | LinkedIn + Indeed + Glassdoor/Google/ZipRecruiter acquisition | The de-facto Python job-board scraper; MIT; ~4,300★; normalises all boards into one schema. **Install from git, not PyPI** — see the supply-chain warning below. |
| **SQLite (WAL) + SQLAlchemy** | SQLite 3.4x / **SQLAlchemy 2.0.53** (MIT) | Persistence | Single-file, zero-ops, read-heavy workload. The single-writer limit is irrelevant at 1–5 users. Portable to Postgres later via a DSN change. |
| **APScheduler** | **3.11.3** (MIT) | In-process scheduling | Persistent job store + API-driven jobs + survives restarts, with no broker. **4.x is still alpha — do not use it** (verified). |
| **Tectonic** | **0.17.0** (2026-07-27) | LaTeX → PDF | ~124 MB vs ~2.3 GB TeX Live; auto-fetches packages; auto-reruns to convergence; fastest and most portable LaTeX engine in published benchmarks. |
| **Jinja2** (LaTeX-safe delimiters) | **3.1.6** | `.tex` templating | The only sane way to template LaTeX with stable structure; requires custom delimiters (see Q6). |
| **opencode** (`serve`) | server as deployed (OpenAPI 3.1 at `/doc`) | LLM backend | Reuses the user's existing opencode + models; **native JSON Schema structured output**; no second provider key. |
| **HTMX + Alpine.js + Jinja2** | HTMX 2.x / Alpine 3.x | Web UI | Queue/CRUD/partial-update app = HTMX's sweet spot. No Node toolchain in the image. |
| **Tailwind CSS** | 4.x (CLI build or vendored) | Styling | Fast to build a clean queue UI without hand-rolling CSS. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pydantic` | **2.13.5** (MIT) | Validation + JSON Schema generation | Everywhere. Central to the anti-fabrication design — Pydantic models → `.model_json_schema()` → opencode `format.schema`. |
| `alembic` | **1.20.0** (MIT) | DB migrations | From day one. Non-negotiable if you want the Postgres path later to be cheap. |
| `aiosqlite` | **0.22.1** | Async SQLite driver | Required for async SQLAlchemy against SQLite. |
| `httpx` | **0.28.1** (BSD-3) | HTTP client | Talking to `opencode serve`; thin hand-rolled client over ~5 endpoints. |
| `curl_cffi` | **0.16.3** (MIT) | TLS/JA3 browser impersonation | For HTTP-only adapters that get 403'd on fingerprint alone. Escalation rung 2 for scraping. |
| `invisible-playwright` | **0.16.0** (MIT AND Apache-2.0) | Stealth patched-Firefox Playwright | Escalation rung 3 — real browser needed. This is the engine AIHawk now ships. |
| `tenacity` | **9.1.4** (Apache-2.0) | Retry/backoff | Transport errors on scrape + LLM calls. |
| `rapidfuzz` | 3.x (MIT) | Fuzzy matching | Tier-2 listing dedup (normalised company+title+location). |
| `pypdf` | **6.18.1** (BSD-3) | PDF read/manipulation | Extract text from compiled CV for diffing/verification. |
| `selectolax` *or* `lxml` | current | Fast HTML parsing | For adapters that parse HTML directly (JobSpy brings its own). |
| `structlog` | current | Structured logging | Per-run pipeline logs; makes "why did this listing get filtered?" answerable. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `openapi-python-client` / `datamodel-code-generator` | Inspect opencode's `/doc` spec | Optional — used only to **verify field names** for structured output. 5 endpoints is less code hand-rolled than a generated client. |
| `pytest` + `pytest-asyncio` | Tests | Contract test against opencode `/doc`; golden tests for the LaTeX renderer. |
| `ruff` | Lint + format | Fast, single tool. |
| `pre-commit` | Hooks | Keep `.tex`/`.yaml` fixtures clean. |

## Installation

# --- Application (Python 3.13) ---

# Web + persistence

# Scheduling

# Acquisition — NOTE: install JobSpy from git, NOT PyPI

# Escalation rung 3 (only if a source needs a real browser)

# PDF verification

# --- LaTeX engine: Tectonic (standalone binary, not pip) ---

# In Docker: pin Tectonic 0.17.0 and PRIME THE PACKAGE CACHE at build time (see Q6).

## Critical Version Corrections (training data gets these wrong)

## Q1 — Job-Portal Data Acquisition (LinkedIn & Indeed): the hard problem

### The headline finding

### LinkedIn

| Surface | What it does | Can this project use it? |
|---|---|---|
| Job Posting API | Employers/ATS partners **post** jobs to LinkedIn | ❌ Employer-side; no read/search |
| Apply Connect / RSC | Deliver applications back to an ATS | ❌ Partner-gated; wrong direction |
| Job Credits / Reseller | Post jobs on behalf of customers | ❌ Wrong direction |
| **Job search / listings** | — | **Does not exist for third parties** |

### Indeed

| Surface | Status | Read listings? |
|---|---|---|
| **Publisher API** (XML feed, `publisher=` param) | **Retired** — keys stopped working | ❌ Gone |
| Hosted-search widget (`publisher.indeed.com`) | iframe-only, returns rendered HTML | ❌ Not data-accessible |
| Job Sync API (GraphQL) | Partner-gated, employer-side | ❌ Publish only |
| Indeed Apply | Partner-gated | ❌ Applications in |
| Disposition Sync | Partner-gated | ❌ Outcomes out |
| Sponsored Jobs | Partner-gated | ❌ Campaign mgmt |
| Enterprise data licensing | NDA-gated, sales-led | ⚠️ Commercially prohibitive |

### So the real choice: scrape, or buy an aggregator

#### Option A — Scrape with JobSpy (RECOMMENDED as the primary path)

- It already contains the reverse-engineered LinkedIn/Indeed internals you would otherwise spend weeks rebuilding and maintaining.
- MIT licence — no copyleft obligation on your project.
- It has proxies baked in, and the project explicitly documents the rate-limit reality.

#### Option B — Escalation ladder for blocked sources

| Rung | Technique | Library | When |
|---|---|---|---|
| 1 | Polite pacing: delays, jitter, backoff, UA rotation, `Accept-Language`, one search per run | stdlib + `tenacity` | Always. First line of defence; often sufficient. |
| 2 | **TLS/JA3 + HTTP/2 fingerprint impersonation** | `curl_cffi` 0.16.3 (MIT) | Source returns 403 on fingerprint alone. Note: "TLS fingerprinting alone isn't enough for modern bot protection." |
| 3 | **Real browser, stealth-patched** | `invisible-playwright` 0.16.0 / `camoufox` 0.5.6 | Source requires a JS runtime / browser fingerprint. Heavier; use per-adapter. |
| 4 | Residential/rotating proxies | paid | Only if rungs 1–3 fail. Costs money and trust; document the spend. |
| 5 | Aggregator API | Adzuna (below) | Reliability hedge, not a substitute. |

#### Option C — Adzuna as a genuine free aggregator (RECOMMENDED as adapter #3)

- Free tier **~1,000 calls/month** (≈33/day), JSON, self-serve `app_id`/`app_key`.
- **Country-scoped**: `https://api.adzuna.com/v1/api/jobs/{country}/search/{page}` — supports 16+ countries, UK/IE-relevant coverage (verify the exact Ireland endpoint code, likely `ie`, during implementation).
- Rich query surface: `what`, `what_exclude`, `where`, `salary_min`, `full_time`, `permanent`, `sort_by`, `distance`.
- Bonus **analytics endpoints** nobody uses: `/histogram` (salary distribution), `/history` (salary over time), `/top_companies`, `/geodata`. These can make the UI genuinely better than a raw listing list (e.g. "this listing is below the market median for this role in Dublin").
- Honest limitations: descriptions are **excerpts**, `salary_is_predicted` is common, links route through Adzuna, no per-source attribution, and 33 calls/day is easy to exhaust with a broad query matrix. Quota-aware caching is mandatory.

### Legal / ToS posture (Dublin-based, so EU + Irish law is operative)

- Ninth Circuit, *hiQ Labs v. LinkedIn*, 938 F.3d 985 (2019), **reaffirmed on remand 2022** (17-16783, 2022-04-18) after *Van Buren*: the CFAA's "without authorization" concept **does not apply to publicly accessible web pages**. HiQ won a preliminary injunction against LinkedIn blocking its access to public profiles.
- **But the same litigation shows the real risk is contract, not crime.** N.D. Cal. (2022-11-04) held hiQ **breached LinkedIn's User Agreement** by scraping and by using contractors ("turkers") to create false profiles, and granted summary judgment to LinkedIn on the breach-of-contract claim. Commentary is consistent: "@ violation of the terms of use of a website — without more — cannot establish liability under the CFAA", but ToS **are** enforceable as contract.
- **GDPR** applies to any listing content containing personal data — a named hiring manager, recruiter email, phone. Publicly posted ≠ exempt. The EDPB's **Guidelines 03/2026 on web scraping** (published July 2026) and the **CNIL focus sheet on legitimate interest in web scraping** (Jan 2026) both emphasise purpose limitation, data minimisation, and exclusion of sensitive data. For a *non-AI-training, personal job-search* use, the compliance burden is light — but the duties are real.
- **EU Database Directive sui generis database right** protects databases built with substantial investment. Systematic bulk extraction of a job board's listings can infringe **even with no personal data involved**. "Personal, low-volume, non-redistributive" is the posture that keeps this theoretical.
- **Irish computer-misuse law** (Criminal Justice (Theft and Fraud Offences) Act 2001, s.5 — unauthorised access) is the local analogue. Again: public pages, no auth bypass, no practical exposure.
- **ToS is legally significant in the EU too.** Courts in multiple jurisdictions treat ToS-violating automated collection as evidence of unauthorised access, and it is a straightforward breach-of-contract claim. LinkedIn clause 8.2 explicitly prohibits scraping.

## Q2 — Prior-Art Survey (and whether this should be greenfield at all)

### Cluster A — Job-board aggregation (adopt, don't rebuild)

| Project | Licence | Health (2026-09-15) | What it does well | Where it stops |
|---|---|---|---|---|
| **JobSpy** (`speedyapply/JobSpy`) | MIT | ~4,284★, 846 forks, 64 open issues, last commit 2026-02-18, last release v1.1.79 (2025-03-21) | One call → LinkedIn/Indeed/Glassdoor/Google/ZipRecruiter/Bayt; proxy support built in; de-facto standard | No persistence, **no dedup, no change tracking**, query-shaped not feed-shaped, ~1000 cap/query, LinkedIn needs proxies. Lightly maintained, not "actively": 1 external PR in the last 7 months. |

### Cluster B — Auto-appliers (the thing this project explicitly rejects)

| Project | Licence | Health | Notes |
|---|---|---|---|
| **AIHawk** (`feder-cr/AIHawk`) | **MIT** (was AGPL-3.0) | ~31,593★, pushed **2026-09-15** — very active | **Pivoted.** No longer a job auto-applier. Now "an anti detect browser and web browsing agent … with an MCP server for coding agents". Ships `invisible-playwright` (patched-Firefox stealth engine), proxy + profile + seed options, BYO OpenRouter key. |
| LazyApply, Sonara, Simplify, LoopCV (commercial) | proprietary SaaS | active | Mass auto-apply. No self-hosting, no CV-as-source-of-truth, no local privacy. Generic/regurgitated applications, documented repairability problems. |

### Cluster C — CV tailoring / ATS optimisation (closest prior art — study before building)

| Project | Licence | Health | Stack | Notes |
|---|---|---|---|---|
| **Resume-Matcher** (`srbhr/resume-matcher`) | **Apache-2.0** | **~28,434★, 5,035 forks, 55 open issues, pushed 2026-09-10 (5 days ago)** | FastAPI + Python 3.13+ + **LiteLLM** + Next.js 16/React 19 + **TinyDB** + **Playwright headless Chromium** for PDF | **The single most important prior-art artefact.** Master resume → paste JD → AI-tailored resume + cover letter + interview prep + match scoring + keyword highlighting. 100+ LLMs incl. Ollama/OpenAI/Anthropic/Gemini/OpenRouter/DeepSeek. |
| **ResuMorph** (`hannibalevit/resumorph`) | Apache-2.0 | 6★, 10 open issues, pushed 2026-08-30, **pre-release** | Chrome MV3 extension + **FastAPI + SQLite** | Conceptually closest to *assisted apply*: "an inline AI button on non-sensitive text fields drafts an answer you can preview, then insert, copy, or cancel." Local-first, Docker, BYO key **or Ollama**. Too immature to depend on — excellent architecture to study for the prefill/preview/insert UX. |
| **TailorCV** (`yishaik/TailorCV`) | MIT | 0★, pushed 2026-06-29 | Python 3.12 + FastAPI 0.109 + Pydantic + React 19 | Directly implements your ethical constraint: requirement extraction → CV facts extraction → evidence mapping → generation → **fabrication detection that blocks invented companies/skills/metrics** + **borderline flagging** + **change logging** + 3 strictness levels. Immature, but the *design* is liftable verbatim. |
| **tailit** (`sardorml/tailit`) | MIT | 27★, pushed 2026-06-17 | Next.js 16 + React 19 + **Typst** 65 templates + Groq | Wrong stack, right ideas: "the tailoring prompt only rephrases/reorders your real content and reports gaps honestly — it never invents employers, dates, or skills." Validates Typst as a LaTeX alternative. |
| **rshivam973/resume-tailor** | MIT | 0★ | Agent skill + Python scripts | A written **truthfulness policy** split into allowed / forbidden operations, with unsupported skills routed to "confirmation items" rather than added. Steal this as the prompt spec. |

### The honest greenfield verdict

- The scraper. JobSpy exists, is MIT, and covers both target boards.
- The LaTeX compiler. Tectonic exists and is better than what you'd write.
- The ranking/tailoring *prompt engineering*. Resume-Matcher and TailorCV have already iterated on this in public; start from their structures.
- The anti-fabrication QA *design*. TailorCV's detect-and-block + borderline-flag + change-log pattern is exactly your "ethical hard line", already thought through.

## Q3 — Python Web Framework: FastAPI

### Why

| Decision driver | FastAPI | Django 6 |
|---|---|---|
| Workload shape: fan out to N sources + LLM calls, all I/O-bound | **Async-first (Starlette/ASGI)** | Async improved in 5.x/6 but the ecosystem still catches up |
| Validation + JSON Schema (needed for opencode structured output) | **Pydantic v2 native** — `.model_json_schema()` is a first-class call | DRF serializers; no Pydantic-native path |
| Container footprint | ~3 deps, 200-line app | Full framework whether you use it or not |
| Auth ("Authentik later") | OAuth via `authlib` in a dependency — small, composable | Sessions/perms built in, but you don't want session auth *now* |
| Admin panel | Replaced by the actual product UI (the ranked queue) | Django admin is the killer feature — and irrelevant here |
| Prior-art precedent | **Resume-Matcher and TailorCV both use FastAPI** | — |

### Supporting choices

- **`uvicorn` 0.53.0 (BSD-3)** as the ASGI server. **Pin `--workers 1`** — see Q5 (multiple workers = multiple schedulers).
- **Jinja2 3.1.6** via `fastapi.templating.Jinja2Templates` — **but with LaTeX-safe delimiters for `.tex`** (see Q6). Use standard delimiters for `.html`, a second configured `Environment` for `.tex`. Two environments, one process.
- **No ORM shortcuts:** SQLAlchemy 2.0 declarative models, Alembic migrations, no `create_all()` in production paths.
- **Layout:** `app/{api,web,domain,sources,llm,latex,db,jobs}`. `sources/` is the pluggable adapter package (see Q1); `llm/` is the opencode client (Q7); `latex/` is render+compile (Q6); `jobs/` holds the pipeline callable used by both the manual trigger and the scheduler (Q5).

## Q4 — Persistence: SQLite (WAL) + SQLAlchemy + Alembic

### Why SQLite here

- Writes happen in one nightly batch (insert/update listings, scores, CV artefacts) plus occasional user interactions (status changes, criteria edits).
- Reads dominate (browsing the queue, detail views, filtering/search).

### Non-negotiable configuration

# engine setup

### Schema design for the two things SQLite must earn its keep on

- `listings` — the canonical, deduped job. `id`, normalised `company`, `title`, `location`, `remote_flag`, `description`, `salary_*`, `posted_at`, `first_seen_at`, `last_seen_at`, `is_active`, `content_hash`.
- `listing_sources` — join table, **many sources → one listing**: `listing_id`, `source` (`linkedin`/`indeed`/`adzuna`), `source_listing_id`, `source_url`, `first_seen_at`, `last_seen_at`, plus a `UNIQUE(source, source_listing_id)` constraint. This is what makes the pluggable-adapter design pay off: adding a source adds rows, not schema.
- **Tier 1 dedup (exact):** `UNIQUE(source, source_listing_id)` — an upsert key. Never insert twice.
- **Tier 2 dedup (fuzzy):** normalise `(company, title, location)` — casefold, strip punctuation/legal suffixes, collapse whitespace — then match on the normalised tuple, and fall back to `rapidfuzz` token-set ratio above a configurable threshold (~90). Store the pair in a `listing_dupes` audit table so a false merge is *reversible* (this matters — silent bad merges are the worst failure mode).
- **Change tracking falls out for free:** `last_seen_at` older than N days ⇒ `is_active = false`. "New since your last run" = `first_seen_at > last_run_at`. This directly fills the gap JobSpy leaves.

### Application state (the tracker)

- `applications` — `listing_id`, `status` (enum: `queued`/`shortlisted`/`applied`/`interviewing`/`offer`/`rejected`/`withdrawn`), `applied_at`, `notes`.
- `cv_artifacts` — one row per tailored CV: `listing_id`, `base_cv_version`, `structured_diff` (JSON: which bullet IDs were reordered/re-weighted), `tex_path`, `pdf_path`, `compiled_at`, `compile_log`. Linking a specific artifact to an application is what closes the loop and is absent from every prior-art tool.
- `runs` — one row per pipeline run: `started_at`, `finished_at`, `source_counts`, `filtered_count`, `ranked_count`, `llm_tokens_or_calls`, `errors`. Makes "why is the queue empty today?" answerable.

### The portability requirement

### What NOT to use

- **TinyDB** (what Resume-Matcher uses) — a JSON file. No concurrency, no indexes, no FTS, no migrations, no partial updates. Fine for a single-user demo; wrong the moment you have a queue with filtered search.
- **MongoDB** — schemaless buys you nothing here; you have a stable normalised listing schema and you want migrations and joins.
- **`sqlite-vec` / vector search** — genuinely tempting for semantic dedup and "similar jobs", but it's a native extension that complicates the Docker build and adds an embedding model dependency. **Defer to a later milestone.** FTS5 + fuzzy tuple matching covers v1.

## Q5 — Scheduling: APScheduler 3.11.3 inside the app process

### Why APScheduler over the alternatives

| Option | Why not |
|---|---|
| **System/container cron** | Lives outside git, isn't portable to a hosted deployment, can't be driven by the API, and can't show "next run" in the UI. Fragile inside a container (no init, TZ handling, no graceful shutdown). |
| **Celery + Beat** | Requires Redis/RabbitMQ — a whole broker + separate worker process for **one nightly job**. Massively overkill; more moving parts to fail. |
| **K8s CronJob** | Wrong deployment target (single local Docker container). |
| **APScheduler 4.x** | **Still alpha** (4.0.0a6, 2025-04-27). Not for a project you want to rely on. |
| **APScheduler 3.11.3** ✅ | Persistent job store, survives restarts, add/pause/resume/remove jobs at runtime via your own API, no broker, runs in-process. |

### Implementation shape

# app/jobs/scheduler.py

- `coalesce=True` — if the machine was asleep/off and missed 3 runs, run once, not three times.
- `max_instances=1` — never overlap a long scrape with the next run.
- `misfire_grace_time=3600` — a run missed by <1h still happens (a laptop closing overnight shouldn't skip the day).
- `replace_existing=True` — restarting the app re-registers the job instead of duplicating it.
- **Timezone explicitly `Europe/Dublin`** — the user is Dublin-based; don't inherit container UTC silently, and don't let DST shift the morning run.

## Q6 — LaTeX Compilation in Docker

### Tectonic vs TeX Live

| Approach | Image size | Build time | Notes |
|---|---|---|---|
| `texlive-full` (apt) | **~4.2 GB** | 8–15 min | 4,152 packages, 6,000+ CTAN packages, 1,200+ fonts. Absurd for one CV. |
| `texlive-latex-extra` | ~1.5 GB | 3–5 min | Still heavy. |
| `texlive` base | ~400 MB | 1–2 min | Missing packages → back to installing more. |
| Curated TeX Live subset | ~200–800 MB | 5–10 min + trial/error | You own the maintenance. |
| **Tectonic** ✅ | **~124 MB** (pre-cached image ~75–94 MB compressed) | **~50 s** | Auto-fetches packages; auto-reruns to convergence; single binary. |

### Why Tectonic fits *this* project specifically

- **Auto-reruns until convergence** kills the classic "how many `pdflatex` passes does this CV need?" problem — and the cross-reference/bibliography ordering bugs that follow it.
- **Auto-fetches packages** means a CV using some unusual `\usepackage` doesn't require editing a Dockerfile and rebuilding. For a *user-owned* `.tex` document that may evolve, this is a large ergonomic win.
- **Single static binary** — no apt dependency tree, no interpreter, trivially pinned.
- **XeTeX-derived**, so `fontspec`/OpenType fonts work (relevant if the CV uses a custom font).

### The three Tectonic caveats you MUST design around (all verified)

### When to fall back to TeX Live

### Templating: Jinja2 with LaTeX-safe delimiters (a real, documented pitfall)

### Escaping is mandatory, not optional

### ⭐ The architectural consequence of "never fabricate": model the CV as data, not as .tex

- **Fabrication becomes structurally impossible** in the dangerous dimensions: the model can only pick from an enumeration of real bullet IDs. It cannot invent an employer because the schema doesn't have a free-text employer field on that path.
- **You get the diff for free** — the patch *is* the change log, satisfying "flag gaps / suggest adjustments / never invent" and giving the UI an honest "what changed and why" view.
- **Rendering is stable and testable** — golden-file tests on the renderer, independent of LLM non-determinism.
- It maps **directly** onto opencode's JSON-Schema structured output (Q7). The two decisions reinforce each other.

### Stay on LaTeX; don't migrate to Typst

## Q7 — Integrating the opencode LLM Backend from Python

### Why HTTP beats the CLI subprocess

| | `opencode serve` (HTTP) | `opencode` CLI subprocess |
|---|---|---|
| Latency per call | One persistent server | Process spawn per call |
| Structured output | **Native JSON Schema** | Parse stdout and hope |
| Progress streaming | **SSE `GET /event`** | None |
| Concurrency | Multiple sessions | Awkward |
| Error semantics | HTTP status + typed error objects | Exit codes + stderr text |
| Health check | `GET /global/health` | `--version` |

### The endpoints you actually need (verified against official docs, last updated 2026-09-14)

| Method | Path | Use |
|---|---|---|
| `GET` | `/global/health` | Startup probe → `{ healthy, version }`. **Fail fast and surface a clear error** rather than discovering the server is missing mid-run. |
| `POST` | `/session` | Create a session per run (or per pipeline stage). Body `{ title?, parentID? }`. |
| `POST` | `/session/:id/message` | Send + wait. Body `{ messageID?, model?, agent?, noReply?, system?, tools?, parts, format? }` → `{ info, parts }`. |
| `POST` | `/session/:id/prompt_async` | Fire-and-forget (204). Useful for long tailoring jobs. |
| `GET` | `/event` | **SSE stream** — stream progress/log lines to the UI. |
| `GET` | `/doc` | OpenAPI 3.1 spec — **the authoritative contract for your version**. |
| `GET` | `/provider`, `GET` /agent` | Discover available providers/models and agents. |

### Structured output — the key capability

# → format={"type": "json_schema", "schema": schema, "retryCount": 2}

# then validate: RankedListing.model_validate(info["structured_output"])

### Prompt-injection boundary (accepted residual risk under the opencode V2 API)

Under the opencode **V2** API there is **no `system` field** on `generate` or
`prompt`, so the app's frozen instructions and the untrusted listing text share
one prompt (frozen instructions first, then the schema block, a hard delimiter, an
explicit untrusted-data directive, and the existing per-part labels). Domain
grounding still blocks fabrication of employers, titles, dates, bullets and
skills — a successful injection cannot invent a fact — but a malicious listing
could drive **schema-valid-but-dishonest** output (e.g. a wrong-but-grounded
rationale). This residual risk is **accepted for now**, on the condition that it
is documented: see `docs/runbook-opencode-contract.md` ("Residual
prompt-injection risk (accepted)") and the `README`. Revisit candidates are the
experimental per-session instructions endpoint (placement unconfirmed) or a plugin
`context` hook (`ctx.session.hook("context")`, which needs plugin files outside
the repo). Do not mistake this for an oversight.

### Model and agent selection

### Python client: hand-roll it, but pin it

### Fallback: CLI subprocess (degraded mode only)

## Q8 — Frontend: Jinja2 + HTMX + Alpine.js

### Why HTMX here (and not React/Next)

- Browse/filter/sort the ranked job queue
- Job detail with fit breakdown and rationale
- Edit search criteria and ranking weights
- Application tracker (status changes)
- CV preview (embed the compiled PDF) + download

### Composition

| Layer | Choice | Use for |
|---|---|---|
| Templates | **Jinja2 3.1.6** (standard delimiters for HTML) | Full pages and fragments; one `Environment` for `.html`, a **separate** LaTeX-configured `Environment` for `.tex` (Q6) |
| Interactivity | **HTMX 2.x** | Filtering the queue, changing status, pagination, "run search now" with progress polling, loading detail panels |
| Local state | **Alpine.js 3.x** | Dropdowns, tabs, modals, toggles — *sparingly*, not as a framework |
| Styling | **Tailwind CSS 4** (CLI build at image build) or Pico.css | Fast, clean queue UI |
| PDF preview | `<iframe>` to the PDF endpoint, or a **pdf.js** embed | Preview the tailored CV inline before downloading |
| Section reordering (optional) | Sortable.js + an HTMX POST | Drag-to-reorder CV section priority — **defer**; a plain ordered form is fine in v1 |

### Authentik-readiness for ~zero cost

### Docker deployment

- **`workers=1`** for uvicorn (Q5).
- **Do not publish the opencode port** to the host; only `app` is exposed.
- **Pin the opencode image/version.** opencode's API is evolving; a floating tag can break the `format`/structured-output contract. Pin it and run the `/doc` contract test in CI.
- **Multi-stage Dockerfile:** stage 1 builds wheels (and runs the Tailwind CLI); stage 2 is runtime + Tectonic binary + **primed TeX cache**. Keep `Dockerfile.texlive` as the documented fallback.
- **Python 3.13-slim** base, not 3.14 — wheel availability (Playwright/curl_cffi/lxml).
- Health check on `app` too, and a `/health` endpoint that reports opencode reachability — so the UI can say "LLM backend unreachable" instead of failing mysteriously.

## Alternatives Considered

| Category | Recommended | Alternative | When the Alternative Wins |
|---|---|---|---|
| Web framework | **FastAPI 0.141.1** | Django 6 | If you later want the built-in admin + session auth + ORM as a genuine product surface, or if the team grows and convention beats assembly. Not for v1. |
| Web framework | FastAPI | Flask | Only for a tiny single-file app. FastAPI does everything Flask does here, with typed schemas and OpenAPI. |
| Persistence | **SQLite (WAL)** | PostgreSQL 17 | The moment you have >1 concurrent writer, multi-node, or want `pg_stat_vector`/rich introspection. Migration is a DSN swap + FTS implementation, by design. |
| Persistence | SQLAlchemy 2.0 | SQLModel 0.0.42 | SQLModel is nicer for trivial CRUD but constrains you to its model patterns; you need FTS virtual tables, join tables, and custom types — plain SQLAlchemy is better. |
| Scheduling | **APScheduler 3.11.3** | Celery + Beat | Only if you need distributed execution across many workers with retries/monitoring. Not at one nightly job. |
| Scheduling | APScheduler | `fastapi-apscheduler4` | Only when APScheduler 4.0 ships stable — that package targets 4.x and needs Redis + a shared DB. Not yet. |
| LaTeX | **Tectonic 0.17.0** | TeX Live (curated subset) | If the CV needs `minted`/`pythontex`/complex `biblatex`+`biber`, or a package outside Tectonic's bundle, or pdfTeX-only primitives you can't sanitise. |
| LaTeX | LaTeX | Typst | If compilation pain becomes real. The structured-CV design makes this a renderer swap, not a rewrite. Defer. |
| LaTeX templating | **Jinja2 `\VAR{}`/`\BLOCK{}`** | `(((...)))` / `((* *))` | If you need braces *inside* a block body, or want editor tooling (`jinjahtml-vscode`). Pick one; never mix. |
| Frontend | **Jinja2 + HTMX** | Next.js/React SPA | Only if you add real-time collaboration, offline mode, or a heavy client-side state graph. None apply. |
| LLM backend | **`opencode serve` HTTP** | opencode CLI subprocess | Only if `serve` can't run in the container. Implement as a `Backend` protocol so it's a class, not a refactor. |
| Acquisition | **JobSpy + Adzuna** | Paid aggregator (JobsPipe/Apify/ScrapFly) | If scraping reliability proves unacceptable and you're willing to pay. Keep the adapter interface so this is a config change. |
| Acquisition | JobSpy | Hand-rolled LinkedIn/Indeed scrapers | Essentially never — you'd be rebuilding JobSpy's reverse-engineered internals and owning the maintenance. Only if JobSpy dies completely. |

## What NOT to Use

| Avoid | Why | Use Instead |
|---|---|---|
| **LinkedIn official APIs for reading listings** | Employer-side only; **not accepting new Job Posting partnerships**; restricted to approved partners. No third-party job-search API exists. | Adapter-per-source scraping (JobSpy) + Adzuna. |
| **Indeed Publisher API / any "get an Indeed API key" tutorial** | Retired; no self-serve key; surviving surfaces are employer-side and don't return postings. Most tutorials predate the shutdown. | JobSpy / Adzuna. |
| **`pip install python-jobspy` (pinned to PyPI)** | PyPI is at 1.1.82 (2025-07-28); the repo has moved on (`cullenwatson/JobSpy` now 301s to `speedyapply/JobSpy`, commits to 2026-02-18). You'd ship a stale LinkedIn parser that breaks on date formats. | `pip install git+https://github.com/speedyapply/JobSpy.git` and pin a commit. |
| **APScheduler 4.x** | **Still alpha** (4.0.0a6, Apr 2025). API churn. | APScheduler **3.11.3**. |
| **`texlive-full` in the image** | ~4.2 GB, 8–15 min builds, giant registry/CI cost, for one CV. | Tectonic (~124 MB) or a curated TeX Live subset. |
| **Tectonic `-Z shell-escape`** | Arbitrary code execution on machine-influenced content. | Leave it off. Sanitise the preamble; never enable escape. |
| **Runtime package downloads for LaTeX** | Container compiles fail offline on a laptop. | Prime the Tectonic cache at image build time. |
| **Default Jinja2 delimiters in `.tex`** | `{{ }}`/`{% %}` collide with LaTeX braces. | LaTeX-configured Jinja `Environment` with `\VAR{}`/`\BLOCK{}`. |
| **Unescaped interpolation into `.tex`** | `&`, `%`, `#`, `_`, `$` in real CV/JD text will break the compile. | A mandatory `escape_tex` filter (backslash first). |
| **Letting the LLM emit `.tex` or free prose for the CV** | Directly violates the "never fabricate" hard line, and is unauditable. | Structured CV + LLM returns an ID-based reorder/re-weight patch; render deterministically. |
| **TinyDB** (Resume-Matcher's choice) | JSON file: no concurrency, indexes, FTS, migrations, or partial updates. | SQLite + SQLAlchemy + Alembic. |
| **Postgres in v1** | A second container, pooler, credentials, backup tooling — for 1–5 users and one writer. | SQLite WAL; keep the migration path open by design. |
| **`uvicorn --workers > 1` with APScheduler** | N workers ⇒ N schedulers ⇒ the same job runs N times. | Pin `--workers 1`; add a Postgres advisory lock only if you later scale out. |
| **`LIKE '%term%'` for listing search** | Full scan; unusable as the corpus grows. | FTS5 virtual table with BM25 `rank`. |
| **Auto-apply / unattended submission** | Ban risk (LinkedIn has banned automation users *and* AIHawk's contributors); velocity detection added 2025; reputational and ethical cost. | **Assisted apply**: draft + prefill + human presses send. Already the project's decision — keep it. |
| **Full opencode tool access on listing-driven sessions** | Job listings are untrusted input; `/session/:id/shell` and `/file/*` exist. Prompt injection → tool abuse. | `tools`-restricted sessions, no listing content in `system`, locked-down agent/permission config, password-protected server on the internal network. |
| **CAPTCHA-solving services / auth circumventers** | The bright legal line; also fragile and paid. | Stop at fingerprint/JS impersonation on public pages; use Adzuna instead. |
| **A React/Next SPA for this UI** | Node toolchain in the image, a second build/serve path, an API contract to maintain — for a CRUD queue. | Jinja2 + HTMX + Alpine. |
| **Persisting recruiter PII from listings** | GDPR exposure for zero product value. | Strip emails/phones at ingest; store no personal identifiers. |

## Stack Patterns by Variant

- Promote that adapter to `curl_cffi` (TLS/JA3 impersonation) — same normalised output, different transport.
- Because "TLS fingerprinting alone isn't enough for modern bot protection" is also true, keep rung 3 available.
- Promote to `invisible-playwright` 0.16.0 (patched Firefox, deterministic stealth profile + seed, proxy-aware).
- Because it's the same engine the most-starred project in this space now depends on, and it's MIT/Apache-2.0.
- Add paid aggregator adapters (JobsPipe / Apify / ScrapFly) behind the same interface, and/or shift LinkedIn/Indeed weight onto Adzuna.
- Because the adapter interface makes this a config/priority change, not a rewrite — this is *why* the interface exists.
- Set `LATEX_ENGINE=texlive` and build the curated-subset `Dockerfile.texlive`.
- Because compile reliability beats image size; and the setting is config, not code.
- Move to Postgres, swap `aiosqlite`→`asyncpg`, implement the Postgres FTS variant, add `pg_advisory_lock` around scheduled jobs.
- Because that's the exact point where SQLite's single-writer model and APScheduler's per-process scheduler both stop being safe.
- Sanitise the preamble (comment out `\pdfcompresslevel` / `\pdfminorversion` / `\pdfobjcompresslevel`) before handing it to Tectonic.
- Because Tectonic (XeTeX-derived) rejects them.
- Read the `runs` table and the per-run structured logs (`structlog`), plus the `cv_artifacts.structured_diff`.
- Because "why did this listing get filtered?" and "what changed in this CV?" should never require re-running the pipeline.

## Version Compatibility

| Package A | Compatible With | Notes |
|---|---|---|
| Python **3.13** | all of the below | ⚠️ **Do not use 3.14** despite the local machine having 3.14.7 — wheel coverage for Playwright `invisible-playwright`/`curl_cffi`/`lxml` is the risk. Pin 3.13 in the image. |
| FastAPI 0.141.1 | Pydantic 2.13.5, Starlette (bundled), Uvicorn 0.53.0 | FastAPI requires Pydantic **v2**. Do not install Pydantic v1 or `pydantic.v1` shims. |
| SQLAlchemy 2.0.53 | Alembic 1.20.0, aiosqlite 0.22.1 | `aiosqlite` is required for async; Alembic migrations are typically run with the **sync** driver (`sqlite://`) — hold both URLs, like APScheduler forces you to. |
| **APScheduler 3.11.3** | SQLAlchemy 2.0.x (verify on install) | APScheduler 3.x `SQLAlchemyJobStore` needs a **sync** engine. Confirm the 3.11.x ↔ SQLAlchemy 2.0 pairing at install time; pin both. **4.x is alpha — out.** |
| JobSpy (git) | Python >=3.10,<4.0 | Brings `pandas` + `numpy` (>=1.26, per a recent commit relaxing the constraint). Adds ~100 MB to the image; consider installing with `--no-deps` + explicit minimal deps if size matters. |
| `invisible-playwright` 0.16.0 | Playwright 1.62.0 | Verify the patched engine's install step and pin both; a Playwright bump can break the patched Firefox build. |
| `curl_cffi` 0.16.3 | Python >=3.10 | Ships pre-compiled; supports `impersonate="chrome"`. Fingerprints can be refreshed without upgrading (`curl-cffi update`). |
| Jinja2 3.1.6 | FastAPI templating | Use **two `Environment` instances** (HTML, LaTeX) — do not try to share one. |
| **Tectonic 0.17.0** | biber **2.17** (not 2.18) | Tectonic's bundled `biblatex` control file v3.8 requires **biber 2.17**; Debian's apt `biber` 2.18 is too new and will fail. Pin biber explicitly. Only relevant if the CV has a bibliography. |
| opencode (pinned image) | `httpx` 0.28.1 | The API is evolving: `format` vs `outputFormat` inconsistency exists *today*. Pin the server version and run a `/doc` contract test in CI. |
| pypdf 6.18.1 | — | Used only to extract text from the compiled PDF for the anti-fabrication assertion step. |
| SQLite (bundled) | FTS5 enabled by default | Python's stdlib `sqlite3` ships FTS5 in the amalgamation. Verify `PRAGMA compile_options` includes `ENABLE_FTS5` in the container. |

## Open Questions / Gaps (carry into roadmap research)

## Sources

- Microsoft Learn, LinkedIn Talent Solutions — Job Posting API overview, Apply Connect, Job Posting Certification (LTS `2026-03`/`2026-04` views) — https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/overview · https://learn.microsoft.com/en-us/linkedin/talent/apply-connect/create-apply-connect-jobs — **HIGH**
- Indeed Partner Docs — Job Sync API, Job Update API (`docs.indeed.com`, pages dated 2026-07/2026-08) — https://docs.indeed.com/job-sync-api/integrate-with-job-sync-api — **HIGH**
- Indeed ToS (Ireland, `ie.indeed.com/legal`) — job-seeker licence scope, application review obligations — **HIGH**
- opencode — Server docs (last updated 2026-09-14), SDK docs (structured output / JSON Schema) — https://opencode.ai/docs/server/ · https://opencode.ai/docs/sdk/ — **HIGH**
- SQLite — FTS5 extension reference (`sqlite.org/fts5.html`, updated 2026-08-01) — **HIGH**
- PyPI JSON API — verified versions for fastapi, sqlalchemy, alembic, apscheduler, pydantic, jinja2, httpx, playwright, aiosqlite, sqlmodel, instructor, curl-cffi, pypdf, tenacity, uvicorn, litellm, python-jobspy, invisible-playwright, scrapling, camoufox — **HIGH**
- GitHub API — repo health for `speedyapply/JobSpy`, `feder-cr/AIHawk`, `srbhr/resume-matcher`, `hannibalevit/resumorph`, `yishaik/TailorCV`, `sardorml/tailit` (pulled 2026-09-15) — **HIGH**
- Tectonic — 0.17.0 release notes (2026-07-27) and CHANGELOG — https://github.com/tectonic-typesetting/tectonic/releases — **HIGH**
- Adzuna — developer portal, API overview and search endpoint docs — https://developer.adzuna.com/ · https://api.adzuna.com/v1/doc — **HIGH**
- *hiQ Labs, Inc. v. LinkedIn Corp.*, 9th Cir. 17-16783 (2022-04-18) — CFAA inapplicable to public web pages — https://cdn.ca9.uscourts.gov/datastore/opinions/2022/04/18/17-16783.pdf — **HIGH**
- N.D. Cal., hiQ v. LinkedIn, summary judgment (2022-11-04) — ToS anti-scraping clauses enforceable in breach of contract — Proskauer / Privacy World analyses — **HIGH**
- EDPB, *Guidelines 03/2026 on web scraping in the context of generative AI* (July 2026) — https://www.edpb.europa.eu/ — **HIGH**
- CNIL, *Legal basis of legitimate interest: measures for web scraping* (Jan 2026) — https://cnil.fr/ — **HIGH**
- Openindex, *How do you ensure vacancy data is collected legally and ethically?* (2026-08-28) — GDPR + EU Database Directive + robots.txt framing — **MEDIUM**
- *Engine-Transfer-Bench* (alphaXiv 2608.18329, 2026-08-18) — Tectonic vs pdfLaTeX/XeLaTeX/LuaLaTeX/Typst reliability, latency, portability — **MEDIUM-HIGH**
- Josh Finnie, *Why I Switched From TeX Live to Tectonic* (2025-11-17) — 2.3 GB→124 MB, 5 min→50 s, package preloading — **MEDIUM**
- `sunsided/clothoid-latex` PR #4 — Tectonic + pinned biber 2.17, VFS/temp-dir workaround, dual Dockerfile pattern — **MEDIUM**
- FormaTeX, *Why TeX Live Docker Images Are 4 GB* (2026-06-16) — size/time breakdown — **MEDIUM**
- Bradley Erickson, *LaTeX templates with Python and Jinja2* — the `\VAR{}`/`\BLOCK{}` environment — **MEDIUM** (widely replicated; older but the canonical reference)
- `jinjahtml-vscode` docs — alternative `(((...)))` LaTeX delimiters used by nbconvert — **MEDIUM**
- APScheduler + FastAPI + SQLAlchemy persistent-scheduler write-ups (elitedev, 2026-04/05; levelup.gitconnected, 2026-07) — `SQLAlchemyJobStore`, sync-engine requirement, `coalesce`/`misfire_grace_time`, advisory-lock caveat — **MEDIUM**
- DRS Web, *React is Overkill: Why Python + HTMX…* (2026-06-04) — HTMX vs React for CRUD; 412 ms vs 2,847 ms migration datapoint — **LOW-MEDIUM** (advocacy piece, but the structural argument and HTMX adoption figure are corroborated elsewhere)
- JobsPipe blog: Indeed API key, Indeed 2026, Adzuna API, JobSpy review — **LOW-MEDIUM** (JobsPipe sells against both JobSpy and Adzuna; used only for corroboration, and its claims were cross-checked against JobSpy's own README and Indeed's own docs)
- SQLite vs PostgreSQL comparisons (cr0x.net 2025-12-20; kunalganglani.com 2026-07-11) — single-writer constraint, FTS5 vs tsvector, migration triggers — **MEDIUM**
- **Indeed Publisher API shutdown year:** 2023 vs 2024 — sources disagree. Decision unaffected; year unresolved.
- **"Indeed is the best scraper currently with no rate limiting"** (JobSpy README) vs the same README's "all of the job board sites are aggressive with blocking" vs third-party claims that Indeed/Glassdoor run serious bot management. **Unresolved — design for blocking on both.** Confidence: LOW.
- **AIHawk's licence:** GitHub API now reports **MIT**; third-party search results and its own earlier README state **AGPL-3.0**. The change is recent. Verify `LICENSE` in the repo before reusing any code. Confidence: MEDIUM.
- **opencode structured output field:** `format` (SDK code example) vs `outputFormat` (server API prose). Treat the code example as authoritative but **verify against your own `/doc`**. Confidence: MEDIUM.

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Full rules in `.planning/CONVENTIONS.md`. Binding highlights for checks that compare model-produced free text against structured project data (`app/verify/*`):

1. **Anchor structurally, never lexically.** Region/section/entity boundaries come from a discriminator free text cannot accidentally satisfy (date-range token, separator, index into `app/domain/cv.py` entries) — never substring containment over extracted or LLM text.
2. **Fail closed, visibly.** A check that cannot locate what it needs emits a `warn`; it must never degrade to empty candidates and a silent skip (a silent skip on a fabrication detector is a false negative).
3. **Every gap-closure fix adds a fixture with the finding's literal repro string** and asserts the corrected behavior.
4. **Test the failure class, not the instance.** Add a property/parametrized test that mutates text to embed other entities' identifiers and asserts the checker still passes.
5. **The fix author does not certify closure.** A reviewer/verifier owns the "closed" verdict; run a scoped code review on changed files after each gap-closure fix.
6. **No false guarantees in prose.** A docstring claiming a guarantee the code doesn't deliver suppresses scrutiny; surface known trade-offs as runtime-visible warnings instead.
7. **Verification pressure is asymmetric by design** — explicitly budget test effort for "does it accept valid input?", not only "does it catch the bad thing?".
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
