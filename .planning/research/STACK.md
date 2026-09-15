# Stack Research

**Domain:** AI-assisted job search automation (local, self-hosted, Python-first, Dockerised)
**Researched:** 2026-09-15
**Confidence:** MEDIUM-HIGH overall (HIGH on stack/library choices and the LinkedIn/Indeed API dead-end; MEDIUM on scraper longevity and Tectonic vs TeX Live; LOW on exact Indeed shutdown year — see conflicts)

> Scope: this file answers the eight questions the project asked. It is **prescriptive** — one recommendation per question with a stated reason, plus what to avoid. Version numbers were verified against PyPI/GitHub/official docs on 2026-09-15, **not** from training data.

---

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

---

## Installation

```bash
# --- Application (Python 3.13) ---
# Web + persistence
pip install "fastapi==0.141.1" "uvicorn[standard]==0.53.0" \
            "sqlalchemy==2.0.53" "alembic==1.20.0" "aiosqlite==0.22.1" \
            "pydantic==2.13.5" "jinja2==3.1.6"

# Scheduling
pip install "apscheduler==3.11.3"

# Acquisition — NOTE: install JobSpy from git, NOT PyPI
pip install "git+https://github.com/speedyapply/JobSpy.git"
pip install "httpx==0.28.1" "curl-cffi==0.16.3" "rapidfuzz" "selectolax" "tenacity==9.1.4"

# Escalation rung 3 (only if a source needs a real browser)
pip install "invisible-playwright==0.16.0"
python -m playwright install firefox   # verify the patched engine's own install step

# PDF verification
pip install "pypdf==6.18.1"

# --- LaTeX engine: Tectonic (standalone binary, not pip) ---
curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh
# In Docker: pin Tectonic 0.17.0 and PRIME THE PACKAGE CACHE at build time (see Q6).
```

**Dev:** `pip install pytest pytest-asyncio ruff pre-commit`

**Frontend:** no npm required at runtime. Either vendor `htmx.min.js` + `alpinejs` as static files, or run the Tailwind CLI once at image build to emit `app.css`.

---

## Critical Version Corrections (training data gets these wrong)

These were checked directly against PyPI/GitHub on 2026-09-15 and each one changes a decision:

1. **APScheduler 4.x is NOT released.** Latest stable is **3.11.3** (2026-06-28). 4.0 exists only as `4.0.0a1…4.0.0a6` (last alpha 2025-04-27). **Plan on 3.11.3.** Any advice to "use APScheduler 4 with the new plugin API" is premature.
2. **PyPI `python-jobspy` is stale and its project URL is a redirect.** PyPI ships **1.1.82** (2025-07-28) and points its homepage at `cullenwatson/JobSpy`, which now **HTTP 301-redirects to `speedyapply/JobSpy`**. The git repo has commits up to **2026-02-18** (including `fix(linkedin): add fallback for date parsing on new job listings`). **Pin the git commit, not the PyPI version.**
3. **AIHawk is no longer an auto-applier.** The repo moved `feder-cr/Jobs_Applier_AI_Agent_AIHawk` → **`feder-cr/AIHawk`**, is now **MIT** (was AGPL-3.0), ~31.6k★, pushed **2026-09-15**, and describes itself as an anti-detect browsing agent with an MCP server. Its job-application framing is gone. See Q2.
4. **There is no official Python SDK for opencode.** Only JS/TS. Plan a thin Python client over the 5 endpoints you need (Q7).
5. **opencode's structured-output field name is documented inconsistently** (`format` in the SDK code example vs `outputFormat` in prose). Resolve against your own server's `/doc` (Q7).

---

## Q1 — Job-Portal Data Acquisition (LinkedIn & Indeed): the hard problem

### The headline finding

**There is no official API path to _read_ job listings from LinkedIn or Indeed. Both are closed to data consumers by design.** This is not a "hard to find the docs" situation — it is a deliberate product decision at both companies. Plan the architecture around it.

### LinkedIn

| Surface | What it does | Can this project use it? |
|---|---|---|
| Job Posting API | Employers/ATS partners **post** jobs to LinkedIn | ❌ Employer-side; no read/search |
| Apply Connect / RSC | Deliver applications back to an ATS | ❌ Partner-gated; wrong direction |
| Job Credits / Reseller | Post jobs on behalf of customers | ❌ Wrong direction |
| **Job search / listings** | — | **Does not exist for third parties** |

Official Microsoft Learn docs (LTS `2026-03`, `2026-04` views) state:

> DATA_Wv2cE8kP_START
> "We are currently not accepting new partnerships for LinkedIn's Job Posting API. If you would like to gain access to LinkedIn's Job Posting APIs please request access to Apply Connect."
> DATA_Wv2cE8kP_END

and

> DATA_Kx7pQ2mR_START
> "The use of these APIs is restricted to those developers approved by LinkedIn."
> DATA_Kx7pQ2mR_END

Even if approved, Apply Connect is for pushing applications *into* LinkedIn, not reading postings out. Onboarding involves a BD contract, a provisioning request, a certification video, and a technical sign-off — for a **wrong-direction** API. **Verdict: ruled out. Confidence: HIGH** (primary source: Microsoft Learn, current LTS views).

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

> DATA_Tz4nW9Ls_START
> "Indeed shut down the Publisher API in 2023 and never replaced it with a self-serve equivalent. … None of them returns job postings, so even a successful approval would not give you the endpoint most people want the key for."
> DATA_Tz4nW9Ls_END

Approval is described as sales-led and scoped to use cases Indeed wants to exist ("We want to read job postings" is not one). **Verdict: ruled out. Confidence: HIGH that no self-serve read API exists; LOW on the exact shutdown year** — sources conflict between **2023** and **2024** (one page says "deprecated the public Publisher API in 2024" while another says 2023). Treat the year as unresolved; the direction of travel is unambiguous and was confirmed by Indeed's own partner docs at `docs.indeed.com` (live pages dated 2026-07/2026-08 describe only employer-side GraphQL surfaces). Confidence in the *decision*: HIGH.

### So the real choice: scrape, or buy an aggregator

#### Option A — Scrape with JobSpy (RECOMMENDED as the primary path)

`speedyapply/JobSpy` — MIT, ~4,300★, 846 forks, last commit 2026-02-18. One `scrape_jobs()` call returns LinkedIn + Indeed + Glassdoor + Google + ZipRecruiter + Bayt as a DataFrame.

**Why this is the right primary path, stated honestly:**
- It already contains the reverse-engineered LinkedIn/Indeed internals you would otherwise spend weeks rebuilding and maintaining.
- MIT licence — no copyleft obligation on your project.
- It has proxies baked in, and the project explicitly documents the rate-limit reality.

**Its real reliability envelope** (from the project's own README, verbatim):

> DATA_Bq8vH3dF_START
> "* Indeed is the best scraper currently with no rate limiting.
> * All the job board endpoints are capped at around 1000 jobs on a given search.
> * LinkedIn is the most restrictive and usually rate limits around the 10th page with one ip. Proxies are a must basically."
> DATA_Bq8vH3dF_END

and

> DATA_Yw6jR5tN_START
> "**Q: Received a response code 429?** — A: This indicates that you have been blocked by the job board site for sending too many requests. All of the job board sites are aggressive with blocking."
> DATA_Yw6jR5tN_END

⚠️ **These two README statements are in tension.** "Indeed … no rate limiting" contradicts the same README's blanket "all of the job board sites are aggressive with blocking", and contradicts third-party reviews stating Indeed and Glassdoor "run serious bot management". **Do not treat "Indeed has no rate limiting" as true** — I could not corroborate it and the evidence points against it. Confidence in the Indeed claim: **LOW**. Design for blocking on both boards.

**The framing that makes this tractable:** the anti-bot problem is *severe at job-board scale* and *tolerable at personal scale*. Independent analysis puts a DIY production pipeline at "$3,000/month before opportunity cost" in proxies + maintenance + on-call — but that is for continuous, comprehensive, SLA-backed coverage. **This project runs a handful of searches, once a day, for one person.** At ~10 LinkedIn pages per IP per run, with delays and a single residential IP, that is inside the budget of what works. The cap (~1000 results/search) and the lack of dedup/change-tracking are the real gaps — and **both are things this project must build itself** regardless of source (see Q4).

**Mandatory wrapper discipline:** never import JobSpy from domain code. Put it behind the source-adapter interface, return the normalised listing schema, and treat it as a best-effort, failure-tolerant adapter that can return partial results or nothing. Its history shows the pattern you should expect: `fix(linkedin): add fallback for date parsing on new job listings (#343)` — LinkedIn breaks, the library patches, you upgrade.

#### Option B — Escalation ladder for blocked sources

Build adapters so a source can be promoted up this ladder without touching the rest of the app:

| Rung | Technique | Library | When |
|---|---|---|---|
| 1 | Polite pacing: delays, jitter, backoff, UA rotation, `Accept-Language`, one search per run | stdlib + `tenacity` | Always. First line of defence; often sufficient. |
| 2 | **TLS/JA3 + HTTP/2 fingerprint impersonation** | `curl_cffi` 0.16.3 (MIT) | Source returns 403 on fingerprint alone. Note: "TLS fingerprinting alone isn't enough for modern bot protection." |
| 3 | **Real browser, stealth-patched** | `invisible-playwright` 0.16.0 / `camoufox` 0.5.6 | Source requires a JS runtime / browser fingerprint. Heavier; use per-adapter. |
| 4 | Residential/rotating proxies | paid | Only if rungs 1–3 fail. Costs money and trust; document the spend. |
| 5 | Aggregator API | Adzuna (below) | Reliability hedge, not a substitute. |

⚠️ **Do not plan on circumventing authentication.** Scraping *public* pages is the defensible line; logging in with a real account to harvest and automating it is where both ToS and computer-misuse exposure escalate (and where AIHawk's contributors got banned — see Q2). Rungs 2–3 are fingerprint/JS challenges on public pages, not auth bypass.

#### Option C — Adzuna as a genuine free aggregator (RECOMMENDED as adapter #3)

**Adzuna** (`developer.adzuna.com`) is the strongest free, self-serve, *legal* job API for this project:
- Free tier **~1,000 calls/month** (≈33/day), JSON, self-serve `app_id`/`app_key`.
- **Country-scoped**: `https://api.adzuna.com/v1/api/jobs/{country}/search/{page}` — supports 16+ countries, UK/IE-relevant coverage (verify the exact Ireland endpoint code, likely `ie`, during implementation).
- Rich query surface: `what`, `what_exclude`, `where`, `salary_min`, `full_time`, `permanent`, `sort_by`, `distance`.
- Bonus **analytics endpoints** nobody uses: `/histogram` (salary distribution), `/history` (salary over time), `/top_companies`, `/geodata`. These can make the UI genuinely better than a raw listing list (e.g. "this listing is below the market median for this role in Dublin").
- Honest limitations: descriptions are **excerpts**, `salary_is_predicted` is common, links route through Adzuna, no per-source attribution, and 33 calls/day is easy to exhaust with a broad query matrix. Quota-aware caching is mandatory.

**This is the single best hedge against LinkedIn/Indeed breaking.** If scraping dies for a week, Adzuna keeps the queue alive.

Other aggregators: **Jooble**, **JSearch** (RapidAPI), **JobsPipe** (the vendor whose reviews surfaced above — commercial, free tier 1,000 jobs/month, keyless sandbox). Note the obvious: much of the best public "JobSpy review" content is written by JobsPipe to sell against JobSpy. **Treat all vendor-authored comparisons as marketing** and weight the primary sources (JobSpy's own README, GitHub data) higher.

### Legal / ToS posture (Dublin-based, so EU + Irish law is operative)

This is research, not legal advice. But the shape is clear enough to architect against.

**US — CFAA (the famous hiQ case):**
- Ninth Circuit, *hiQ Labs v. LinkedIn*, 938 F.3d 985 (2019), **reaffirmed on remand 2022** (17-16783, 2022-04-18) after *Van Buren*: the CFAA's "without authorization" concept **does not apply to publicly accessible web pages**. HiQ won a preliminary injunction against LinkedIn blocking its access to public profiles.
- **But the same litigation shows the real risk is contract, not crime.** N.D. Cal. (2022-11-04) held hiQ **breached LinkedIn's User Agreement** by scraping and by using contractors ("turkers") to create false profiles, and granted summary judgment to LinkedIn on the breach-of-contract claim. Commentary is consistent: "@ violation of the terms of use of a website — without more — cannot establish liability under the CFAA", but ToS **are** enforceable as contract.

**EU / Ireland (the applicable regime):**
- **GDPR** applies to any listing content containing personal data — a named hiring manager, recruiter email, phone. Publicly posted ≠ exempt. The EDPB's **Guidelines 03/2026 on web scraping** (published July 2026) and the **CNIL focus sheet on legitimate interest in web scraping** (Jan 2026) both emphasise purpose limitation, data minimisation, and exclusion of sensitive data. For a *non-AI-training, personal job-search* use, the compliance burden is light — but the duties are real.
- **EU Database Directive sui generis database right** protects databases built with substantial investment. Systematic bulk extraction of a job board's listings can infringe **even with no personal data involved**. "Personal, low-volume, non-redistributive" is the posture that keeps this theoretical.
- **Irish computer-misuse law** (Criminal Justice (Theft and Fraud Offences) Act 2001, s.5 — unauthorised access) is the local analogue. Again: public pages, no auth bypass, no practical exposure.
- **ToS is legally significant in the EU too.** Courts in multiple jurisdictions treat ToS-violating automated collection as evidence of unauthorised access, and it is a straightforward breach-of-contract claim. LinkedIn clause 8.2 explicitly prohibits scraping.

**Architectural implications (build these in, don't bolt them on):**
1. **Respect `robots.txt`** per source and record the check. CNIL states collection cannot fall within reasonable expectations if you ignore robots.txt or CAPTCHAs.
2. **Never collect or persist recruiter PII.** Strip emails/phones from descriptions at ingest. This is the cheapest, highest-value GDPR control.
3. **No redistribution, no public exposure.** v1 is local-only (already the plan) — keep it that way. Redistribution flips both copyright/database-right and GDPR exposure.
4. **Honest User-Agent** identifying a personal job-search tool.
5. **Baked-in rate limits with ceilings in config**, not just "we happened to be polite."
6. **No auth bypass, no CAPTCHA solving.** CAPTCHA-solving APIs (advertised around `curl_cffi`) are the bright line — do not integrate them.
7. Re-audit source ToS quarterly; record the audit date.

The project's own constraint is correct and now evidence-backed: **assisted apply only.** LinkedIn has stated that unauthorised automation tools can lead to restrictions or suspensions, and independent 2026 analysis puts "AI drafts content, human reviews and clicks send" in the low-risk, user-initiated category that enforcement has not targeted — while mass auto-application is in a growing-risk grey zone with velocity-based detection. Your design is already on the right side of that line.

---

## Q2 — Prior-Art Survey (and whether this should be greenfield at all)

The honest answer: **the problem space is well-trodden, but no existing tool does what this project needs. Recommendation: spend 1–2 days spiking Resume-Matcher before committing to greenfield — then build, reusing three specific things.**

All GitHub metrics below were pulled from the GitHub API on **2026-09-15**.

### Cluster A — Job-board aggregation (adopt, don't rebuild)

| Project | Licence | Health (2026-09-15) | What it does well | Where it stops |
|---|---|---|---|---|
| **JobSpy** (`speedyapply/JobSpy`) | MIT | ~4,284★, 846 forks, 64 open issues, last commit 2026-02-18, last release v1.1.79 (2025-03-21) | One call → LinkedIn/Indeed/Glassdoor/Google/ZipRecruiter/Bayt; proxy support built in; de-facto standard | No persistence, **no dedup, no change tracking**, query-shaped not feed-shaped, ~1000 cap/query, LinkedIn needs proxies. Lightly maintained, not "actively": 1 external PR in the last 7 months. |

**Verdict: use it, wrap it, expect to patch it.** Nothing here to rebuild; everything to integrate.

### Cluster B — Auto-appliers (the thing this project explicitly rejects)

| Project | Licence | Health | Notes |
|---|---|---|---|
| **AIHawk** (`feder-cr/AIHawk`) | **MIT** (was AGPL-3.0) | ~31,593★, pushed **2026-09-15** — very active | **Pivoted.** No longer a job auto-applier. Now "an anti detect browser and web browsing agent … with an MCP server for coding agents". Ships `invisible-playwright` (patched-Firefox stealth engine), proxy + profile + seed options, BYO OpenRouter key. |
| LazyApply, Sonara, Simplify, LoopCV (commercial) | proprietary SaaS | active | Mass auto-apply. No self-hosting, no CV-as-source-of-truth, no local privacy. Generic/regurgitated applications, documented repairability problems. |

**AIHawk's history is the strongest evidence for this project's central design decision.** LinkedIn banned all AIHawk contributors and demanded removal of platform links; the project then announced: "LinkedIn requested the removal of all links to the platform and banned all project contributors, so to comply with their guidelines, we have removed any form of automation on LinkedIn." The most-starred auto-applier in the ecosystem had to **retreat from LinkedIn entirely**. It also now requires an OpenRouter key — which violates your "no second provider key" constraint. **Do not use AIHawk as an application engine; do consider `invisible-playwright` as a scraping dependency.**

### Cluster C — CV tailoring / ATS optimisation (closest prior art — study before building)

| Project | Licence | Health | Stack | Notes |
|---|---|---|---|---|
| **Resume-Matcher** (`srbhr/resume-matcher`) | **Apache-2.0** | **~28,434★, 5,035 forks, 55 open issues, pushed 2026-09-10 (5 days ago)** | FastAPI + Python 3.13+ + **LiteLLM** + Next.js 16/React 19 + **TinyDB** + **Playwright headless Chromium** for PDF | **The single most important prior-art artefact.** Master resume → paste JD → AI-tailored resume + cover letter + interview prep + match scoring + keyword highlighting. 100+ LLMs incl. Ollama/OpenAI/Anthropic/Gemini/OpenRouter/DeepSeek. |
| **ResuMorph** (`hannibalevit/resumorph`) | Apache-2.0 | 6★, 10 open issues, pushed 2026-08-30, **pre-release** | Chrome MV3 extension + **FastAPI + SQLite** | Conceptually closest to *assisted apply*: "an inline AI button on non-sensitive text fields drafts an answer you can preview, then insert, copy, or cancel." Local-first, Docker, BYO key **or Ollama**. Too immature to depend on — excellent architecture to study for the prefill/preview/insert UX. |
| **TailorCV** (`yishaik/TailorCV`) | MIT | 0★, pushed 2026-06-29 | Python 3.12 + FastAPI 0.109 + Pydantic + React 19 | Directly implements your ethical constraint: requirement extraction → CV facts extraction → evidence mapping → generation → **fabrication detection that blocks invented companies/skills/metrics** + **borderline flagging** + **change logging** + 3 strictness levels. Immature, but the *design* is liftable verbatim. |
| **tailit** (`sardorml/tailit`) | MIT | 27★, pushed 2026-06-17 | Next.js 16 + React 19 + **Typst** 65 templates + Groq | Wrong stack, right ideas: "the tailoring prompt only rephrases/reorders your real content and reports gaps honestly — it never invents employers, dates, or skills." Validates Typst as a LaTeX alternative. |
| **rshivam973/resume-tailor** | MIT | 0★ | Agent skill + Python scripts | A written **truthfulness policy** split into allowed / forbidden operations, with unsupported skills routed to "confirmation items" rather than added. Steal this as the prompt spec. |

### The honest greenfield verdict

**What you should NOT build:**
- The scraper. JobSpy exists, is MIT, and covers both target boards.
- The LaTeX compiler. Tectonic exists and is better than what you'd write.
- The ranking/tailoring *prompt engineering*. Resume-Matcher and TailorCV have already iterated on this in public; start from their structures.
- The anti-fabrication QA *design*. TailorCV's detect-and-block + borderline-flag + change-log pattern is exactly your "ethical hard line", already thought through.

**What genuinely does not exist anywhere, and is the real product:**
1. A single local pipeline joining **LinkedIn + Indeed aggregation** → **deterministic hard filtering** → **LLM ranking against the user's CV with reasons and explicit gaps** → **LaTeX-native tailoring** → **application tracking**, in one store.
2. **LaTeX as the CV source of truth and tailoring target.** Every prior-art tool uses HTML→PDF (Resume-Matcher: headless Chromium), DOCX (TailorCV, ResuMorph), or Typst (tailit). Nobody templates and recompiles `.tex`. This is a genuine differentiator and the user's actual asset.
3. **opencode as the LLM backend with no second key.** Every prior-art tool requires an API key (Gemini/OpenAI/Groq/OpenRouter) or wires LiteLLM to provider keys. Using `opencode serve` with native JSON-Schema structured output, reusing the user's existing models, is genuinely novel here and *removes a whole class of configuration burden*.
4. **Hard rules before LLM spend.** Resume-Matcher etc. go straight to the LLM. Your filter-before-rank design is both a cost control and an explainability win, and is absent from the field.
5. **Application state tracking tied to the tailored artefact.** ResuMorph drafts; nothing tracks applied/interviewing/rejected alongside the *specific* tailored CV version that was sent. That version↔outcome link is the thing that makes the tool improve over time.

**The spike you should run first (1–2 days, high value):** stand up Resume-Matcher, point it at a local Ollama/openai-compatible endpoint, and answer one question: *can its tailoring engine be driven by opencode and can its output path be replaced with LaTeX?* Its PDF layer is Playwright→Chromium and its store is TinyDB, and its LLM layer is LiteLLM with provider credentials — so the answer is likely "no, not without a fork that costs more than building". But if the answer is "yes", you save months. **This is the honest resolution of "should this be greenfield at all": yes — conditionally, after a documented spike.**

**Licence note for reuse:** Resume-Matcher is Apache-2.0 (fine to borrow patterns/design, attribution required for code reuse); TailorCV/tailit/resume-tailor are MIT (fine). **AIHawk changed from AGPL-3.0 to MIT** — verify the current `LICENSE` file yourself before copying anything, since the change is recent and GitHub's API may lag the repository.

---

## Q3 — Python Web Framework: FastAPI

**Recommendation: FastAPI 0.141.1 (MIT). Confidence: HIGH.**

### Why

| Decision driver | FastAPI | Django 6 |
|---|---|---|
| Workload shape: fan out to N sources + LLM calls, all I/O-bound | **Async-first (Starlette/ASGI)** | Async improved in 5.x/6 but the ecosystem still catches up |
| Validation + JSON Schema (needed for opencode structured output) | **Pydantic v2 native** — `.model_json_schema()` is a first-class call | DRF serializers; no Pydantic-native path |
| Container footprint | ~3 deps, 200-line app | Full framework whether you use it or not |
| Auth ("Authentik later") | OAuth via `authlib` in a dependency — small, composable | Sessions/perms built in, but you don't want session auth *now* |
| Admin panel | Replaced by the actual product UI (the ranked queue) | Django admin is the killer feature — and irrelevant here |
| Prior-art precedent | **Resume-Matcher and TailorCV both use FastAPI** | — |

Django's "batteries" (ORM, admin, auth, templates) are mostly things this project either doesn't need (admin, sessions) or wants to choose deliberately (ORM, templates). The one place Django would win — an instant admin panel for CRUD — is solved better by building the real UI, because the primary interaction is "here is a ranked queue with reasons", not "edit these rows".

**Counter-argument to record honestly:** Django 6 (Dec 2025) added built-in background tasks and CSP middleware, and the "assembly cost is real" critique of FastAPI is fair — you *will* wire SQLAlchemy + Alembic + templates yourself. That cost is estimated at a few hours here, not weeks, because the app is small and single-tenant. Also, at this scale the 3–4× throughput difference is irrelevant; FastAPI wins on **shape fit and Pydantic-native structured output**, not speed.

### Supporting choices

- **`uvicorn` 0.53.0 (BSD-3)** as the ASGI server. **Pin `--workers 1`** — see Q5 (multiple workers = multiple schedulers).
- **Jinja2 3.1.6** via `fastapi.templating.Jinja2Templates` — **but with LaTeX-safe delimiters for `.tex`** (see Q6). Use standard delimiters for `.html`, a second configured `Environment` for `.tex`. Two environments, one process.
- **No ORM shortcuts:** SQLAlchemy 2.0 declarative models, Alembic migrations, no `create_all()` in production paths.
- **Layout:** `app/{api,web,domain,sources,llm,latex,db,jobs}`. `sources/` is the pluggable adapter package (see Q1); `llm/` is the opencode client (Q7); `latex/` is render+compile (Q6); `jobs/` holds the pipeline callable used by both the manual trigger and the scheduler (Q5).

---

## Q4 — Persistence: SQLite (WAL) + SQLAlchemy + Alembic

**Recommendation: SQLite in WAL mode via SQLAlchemy 2.0.53 + Alembic 1.20.0, async through `aiosqlite` 0.22.1. Confidence: HIGH for v1; the Postgres migration path is the documented escape hatch.**

### Why SQLite here

The workload is **read-heavy, write-light, single-node, 1–5 users**:
- Writes happen in one nightly batch (insert/update listings, scores, CV artefacts) plus occasional user interactions (status changes, criteria edits).
- Reads dominate (browsing the queue, detail views, filtering/search).

SQLite's constraint is **serialised writes**, and this workload does not approach it. There is no second writer, no team running ad-hoc queries, no horizontal scaling. The upside is large: no second container, no connection pool, no credentials, no backup tooling — the entire database is one file that can be copied, snapshotted, and mounted as a Docker volume.

**Do not reach for Postgres in v1.** Managed Postgres is ~$20–25/month and adds a service to operate for zero benefit at this scale. The failure mode to avoid is the opposite one: choosing SQLite and *not planning for concurrency*. Plan for it by keeping the write path behind a single writer (the nightly job) and enabling WAL.

### Non-negotiable configuration

```python
# engine setup
PRAGMA journal_mode=WAL;      # concurrent readers during writes
PRAGMA synchronous=NORMAL;    # durable enough with WAL; much faster
PRAGMA foreign_keys=ON;       # SQLite defaults OFF — turn it on
PRAGMA busy_timeout=5000;     # avoid immediate SQLITE_BUSY under contention
```

### Schema design for the two things SQLite must earn its keep on

**(1) Dedup — this is a core requirement, not a nice-to-have.** JobSpy gives you "no dedup, no change tracking"; the same role appears on three boards as three rows, and nothing tells you when a posting closed. Design for it:

- `listings` — the canonical, deduped job. `id`, normalised `company`, `title`, `location`, `remote_flag`, `description`, `salary_*`, `posted_at`, `first_seen_at`, `last_seen_at`, `is_active`, `content_hash`.
- `listing_sources` — join table, **many sources → one listing**: `listing_id`, `source` (`linkedin`/`indeed`/`adzuna`), `source_listing_id`, `source_url`, `first_seen_at`, `last_seen_at`, plus a `UNIQUE(source, source_listing_id)` constraint. This is what makes the pluggable-adapter design pay off: adding a source adds rows, not schema.
- **Tier 1 dedup (exact):** `UNIQUE(source, source_listing_id)` — an upsert key. Never insert twice.
- **Tier 2 dedup (fuzzy):** normalise `(company, title, location)` — casefold, strip punctuation/legal suffixes, collapse whitespace — then match on the normalised tuple, and fall back to `rapidfuzz` token-set ratio above a configurable threshold (~90). Store the pair in a `listing_dupes` audit table so a false merge is *reversible* (this matters — silent bad merges are the worst failure mode).
- **Change tracking falls out for free:** `last_seen_at` older than N days ⇒ `is_active = false`. "New since your last run" = `first_seen_at > last_run_at`. This directly fills the gap JobSpy leaves.

**(2) Search — use FTS5, not `LIKE`.**

```sql
CREATE VIRTUAL TABLE listing_fts USING fts5(
  title, company, description,
  content='listings', content_rowid='id',
  tokenize='porter unicode61'
);
SELECT l.*, f.rank FROM listing_fts f
JOIN listings l ON l.id = f.rowid
WHERE listing_fts MATCH ? ORDER BY f.rank;   -- BM25 via the `rank` column
```

FTS5 is built into the SQLite amalgamation, ships with Python's `sqlite3`, uses BM25 ranking, and is "shockingly good" for this corpus size (thousands to low hundreds of thousands of rows). Keep the FTS index in sync with triggers or SQLAlchemy `before_commit`/`after_commit` listeners on an external-content table. **Never do `LIKE '%term%'` on descriptions** — it cannot use an index.

### Application state (the tracker)

- `applications` — `listing_id`, `status` (enum: `queued`/`shortlisted`/`applied`/`interviewing`/`offer`/`rejected`/`withdrawn`), `applied_at`, `notes`.
- `cv_artifacts` — one row per tailored CV: `listing_id`, `base_cv_version`, `structured_diff` (JSON: which bullet IDs were reordered/re-weighted), `tex_path`, `pdf_path`, `compiled_at`, `compile_log`. Linking a specific artifact to an application is what closes the loop and is absent from every prior-art tool.
- `runs` — one row per pipeline run: `started_at`, `finished_at`, `source_counts`, `filtered_count`, `ranked_count`, `llm_tokens_or_calls`, `errors`. Makes "why is the queue empty today?" answerable.

### The portability requirement

The constraint is "must remain portable to a hosted deployment later without a rewrite." Satisfy it by *design*, not by deploying Postgres now:

1. Alembic from the first migration (schema changes are versioned, not ad-hoc).
2. SQLAlchemy 2.0 style everywhere — no hand-written SQLite SQL in the domain layer.
3. Avoid SQLite-only types/behaviour (no abusing dynamic typing; use `JSON` type via SQLAlchemy which maps to JSONB on Postgres).
4. Keep the FTS layer behind a `search` interface with a SQLite FTS5 implementation and a documented Postgres `tsvector`+GIN alternative.
5. When multi-writer appears, the change is: new DSN, swap `aiosqlite`→`asyncpg`, add Postgres FTS implementation, run migrations. Days, not a rewrite.

### What NOT to use

- **TinyDB** (what Resume-Matcher uses) — a JSON file. No concurrency, no indexes, no FTS, no migrations, no partial updates. Fine for a single-user demo; wrong the moment you have a queue with filtered search.
- **MongoDB** — schemaless buys you nothing here; you have a stable normalised listing schema and you want migrations and joins.
- **`sqlite-vec` / vector search** — genuinely tempting for semantic dedup and "similar jobs", but it's a native extension that complicates the Docker build and adds an embedding model dependency. **Defer to a later milestone.** FTS5 + fuzzy tuple matching covers v1.

---

## Q5 — Scheduling: APScheduler 3.11.3 inside the app process

**Recommendation: APScheduler 3.11.3 with `AsyncIOScheduler` + `SQLAlchemyJobStore` on the same SQLite file, started and stopped in FastAPI's `lifespan`. Confidence: HIGH. `--workers 1`. Do NOT use 4.x (alpha).**

### Why APScheduler over the alternatives

| Option | Why not |
|---|---|
| **System/container cron** | Lives outside git, isn't portable to a hosted deployment, can't be driven by the API, and can't show "next run" in the UI. Fragile inside a container (no init, TZ handling, no graceful shutdown). |
| **Celery + Beat** | Requires Redis/RabbitMQ — a whole broker + separate worker process for **one nightly job**. Massively overkill; more moving parts to fail. |
| **K8s CronJob** | Wrong deployment target (single local Docker container). |
| **APScheduler 4.x** | **Still alpha** (4.0.0a6, 2025-04-27). Not for a project you want to rely on. |
| **APScheduler 3.11.3** ✅ | Persistent job store, survives restarts, add/pause/resume/remove jobs at runtime via your own API, no broker, runs in-process. |

The deciding factor is **not** "which scheduler is most powerful" — it's that this app needs *both* a manual "Run search now" button *and* a persisted daily schedule, visible in the UI, with "next run at…". Only the in-process scheduler gives you that with zero extra infrastructure.

### Implementation shape

```python
# app/jobs/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger

jobstores = {"default": SQLAlchemyJobStore(url=settings.sync_database_url)}
job_defaults = {"coalesce": True, "max_instances": 1, "misfire_grace_time": 3600}

@asynccontextmanager
async def lifespan(app):
    scheduler = AsyncIOScheduler(jobstores=jobstores, job_defaults=job_defaults, timezone="Europe/Dublin")
    scheduler.add_job(run_pipeline, CronTrigger(hour=7, minute=0),
                      id="daily_search", replace_existing=True)
    scheduler.start()
    app.state.scheduler = scheduler
    yield
    scheduler.shutdown(wait=False)
```

**Settings that matter (each solves a real bug):**
- `coalesce=True` — if the machine was asleep/off and missed 3 runs, run once, not three times.
- `max_instances=1` — never overlap a long scrape with the next run.
- `misfire_grace_time=3600` — a run missed by <1h still happens (a laptop closing overnight shouldn't skip the day).
- `replace_existing=True` — restarting the app re-registers the job instead of duplicating it.
- **Timezone explicitly `Europe/Dublin`** — the user is Dublin-based; don't inherit container UTC silently, and don't let DST shift the morning run.

**Shared code path:** make the pipeline a plain `async def run_pipeline()` callable. The cron job calls it; the "Run search now" endpoint calls it (queued, not inline — see below). One path, two triggers, identical behaviour and logging.

**Two gotchas to plan for:**
1. **Two SQLAlchemy engines.** `SQLAlchemyJobStore` needs a **sync** engine; the app uses async. You will hold both against the same SQLite file. This is normal and documented, but it must be deliberate — keep the sync engine scoped to the scheduler and the async engine for everything else.
2. **One worker only.** `uvicorn --workers 4` gives you four schedulers, each firing the same job. **Pin `--workers 1`** for v1. If you ever need more workers, the documented escape hatch is a Postgres advisory lock (`pg_advisory_lock`) around job execution — but don't build it now; just don't be surprised by it later.

**Don't run the pipeline in a request handler.** LLM ranking over a batch takes minutes. The manual trigger should enqueue/background the run and return immediately (FastAPI `BackgroundTasks` is fine at `workers=1`, or just kick the same callable on the event loop), with progress surfaced via the opencode SSE stream or the `runs` table. The API stays responsive; the UI polls or subscribes.

---

## Q6 — LaTeX Compilation in Docker

**Recommendation: Tectonic 0.17.0 as the default engine, invoked as a subprocess, with a primed package cache and a curated-TeX-Live fallback Dockerfile. Confidence: MEDIUM-HIGH (HIGH on the size/speed advantage; MEDIUM on Tectonic handling every package a personal CV might use).**

### Tectonic vs TeX Live

| Approach | Image size | Build time | Notes |
|---|---|---|---|
| `texlive-full` (apt) | **~4.2 GB** | 8–15 min | 4,152 packages, 6,000+ CTAN packages, 1,200+ fonts. Absurd for one CV. |
| `texlive-latex-extra` | ~1.5 GB | 3–5 min | Still heavy. |
| `texlive` base | ~400 MB | 1–2 min | Missing packages → back to installing more. |
| Curated TeX Live subset | ~200–800 MB | 5–10 min + trial/error | You own the maintenance. |
| **Tectonic** ✅ | **~124 MB** (pre-cached image ~75–94 MB compressed) | **~50 s** | Auto-fetches packages; auto-reruns to convergence; single binary. |

A published migration reports TeX Live → Tectonic as **2.3 GB → 124 MB** and **5+ min → 50 s** in Docker. The *Engine-Transfer-Bench* study (1,784 documents, pinned versions: TeX Live 2025, Tectonic 0.17.0) found Tectonic **maintained 100% success** across a corpus of 107 engine-specific templates where pdfLaTeX dropped to as low as 29%, was **~2.23× faster than pdfLaTeX and ~3.24× faster than LuaLaTeX** on documents where all succeeded, and was by far the most portable across macOS/Ubuntu/Windows (96.3–97.2% success, <1pp variance, vs up to 20pp variance for classic engines depending on distribution policy).

### Why Tectonic fits *this* project specifically

- **Auto-reruns until convergence** kills the classic "how many `pdflatex` passes does this CV need?" problem — and the cross-reference/bibliography ordering bugs that follow it.
- **Auto-fetches packages** means a CV using some unusual `\usepackage` doesn't require editing a Dockerfile and rebuilding. For a *user-owned* `.tex` document that may evolve, this is a large ergonomic win.
- **Single static binary** — no apt dependency tree, no interpreter, trivially pinned.
- **XeTeX-derived**, so `fontspec`/OpenType fonts work (relevant if the CV uses a custom font).

### The three Tectonic caveats you MUST design around (all verified)

1. **Runtime network dependence.** Tectonic downloads packages from its bundle on demand. In a local Docker container, that means the **first** compile of any new package set needs network. **Fix: prime the cache at image build time** with a preload `.tex` that `\usepackage`s everything the CV uses (plus common extras), run during `docker build`. After that, compilation is offline. Alternatively start from a pre-cached image (`dxjoke/tectonic-docker`, primed). **Do not ship a container that needs the internet to compile a CV on the user's laptop.**
2. **VFS + `biber` on bind mounts.** Known bug: Tectonic 0.15/0.17's VFS "cannot re-open the primary input after biber runs on a Docker-mounted volume", and Debian's apt `biber` 2.18 is too new for Tectonic's bundled `biblatex` (a pinned `biber` 2.17 is required). **Mitigation pattern (from a real PR): compile in a temp dir inside the image and copy the PDF back out to the mounted volume.** If your CV has no bibliography, this is moot — but design the compile wrapper as "stage → compile in temp → copy artefacts out" from day one so you never have to retrofit it.
3. **pdfTeX-only primitives.** Tectonic rejects things like `\pdfcompresslevel`, `\pdfminorversion`, `\pdfobjcompresslevel`. Docling's Tectonic backend sanitises these out of the preamble before compiling. If your existing CV preamble contains pdfTeX-isms, expect a compile failure and have a sanitiser ready.

⚠️ **Security:** do **not** pass `-Z shell-escape` (the `--allow-shell-escape` style option). Tectonic is invoked on machine-generated content (the LLM contributes text into the template), and shell-escape is arbitrary code execution. Docling exposes this as a flag defaulting to `True` — **you should default it to `False` and never enable it.**

### When to fall back to TeX Live

Keep a `Dockerfile.texlive` alongside `Dockerfile.tectonic` (a real project, `sunsided/clothoid-latex`, does exactly this and preserves the old Dockerfile as fallback): TeX Live is required if the CV needs **external programs** — `minted` (needs Pygments), `pythontex`, complex `biblatex`+`biber` combinations — or a package absent from Tectonic's bundle. Build a **curated subset** (`texlive-latex-recommended`, `texlive-fonts-recommended`, plus named extras), not `texlive-full`. Make the engine a config setting (`LATEX_ENGINE=tectonic|texlive`) so switching is config, not code.

### Templating: Jinja2 with LaTeX-safe delimiters (a real, documented pitfall)

**Default Jinja2 delimiters collide with LaTeX.** `{{ }}` and `{% %}` are unusable in a `.tex` file because LaTeX is *made of* braces. Every serious project that has done this hits the same wall and solves it the same way.

**Recommended: the Bradley Erickson environment** (the most-cited solution):

```python
import jinja2
latex_env = jinja2.Environment(
    block_start_string="\\BLOCK{",
    block_end_string="}",
    variable_start_string="\\VAR{",
    variable_end_string="}",
    comment_start_string="\\#{",
    comment_end_string="}",
    line_statement_prefix="%%",
    line_comment_prefix="%#",
    trim_blocks=True,
    autoescape=False,          # NOT HTML — must be off; escaping is a custom filter
    loader=jinja2.FileSystemLoader("templates/latex"),
)
```

Template then reads naturally:
```latex
\section*{\VAR{section.title}}
\BLOCK{ for item in section.items }
  \cvitem{\VAR{item.name}}{\VAR{item.value}}
\BLOCK{ endfor }
```

⚠️ **Known limitation of this convention, state it up front:** `block_end_string` is a **single `}`**, so a `\BLOCK{ … }` body **cannot contain a `}`**. Keep blocks pure control flow (loops/conditionals) and emit all braces via separate `\VAR{…}` expressions. If you ever need braces inside a block body, switch to the **`((* *))` / `((( )))`** convention used by nbconvert/Jupyter and the `jinjahtml-vscode` extension — it permits braces inside blocks and has editor tooling, but `((` can appear in LaTeX math. **Pick one convention, apply it consistently, and document it in the repo.** Do not mix.

### Escaping is mandatory, not optional

The single most likely crash: a CV bullet or job description containing `&`, `%`, `#`, `_`, `$`, `~`, `^`, `{`, `}`. "R&D" or "improved throughput by 20%" will break the compile. Write a `escape_tex` filter:

```python
def escape_tex(s: str) -> str:
    for a, b in [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
                 ("$", r"\$"), ("#", r"\#"), ("_", r"\_"), ("{", r"\{"),
                 ("}", r"\}"), ("~", r"\textasciitilde{}"),
                 ("^", r"\textasciicircum{}")]:
        s = s.replace(a, b)
    return s
```

Apply it to **every** interpolated value, including all text originating from job listings. Note the backslash must be replaced **first**, or you double-escape your own escapes.

### ⭐ The architectural consequence of "never fabricate": model the CV as data, not as .tex

This is the most important design decision in the LaTeX layer.

**Do not let the LLM emit `.tex`.** Instead:

1. Keep the CV as **structured data** (`cv.yaml` / `cv.json`) with stable IDs and provenance:
   ```yaml
   sections:
     - id: experience
       entries:
         - id: exp-acme-2021
           company: Acme
           title: Senior Engineer
           bullets:
             - id: b-acme-003
               text: "Reduced p99 latency 40% by ..."   # immutable source text
               weight: 1.0
   ```
2. The LLM's tailoring task returns a **selection/reordering/re-weighting over those IDs** — validated by a Pydantic model — never free prose, never `.tex`.
3. Render `.tex` **deterministically** from (structured CV + the LLM's ordering/weighting patch) through Jinja2.
4. Compile, extract text with `pypdf` 6.18.1, and assert every factual string from the source CV is still present and no new employer/date/skill appeared.

Why this is strictly better:
- **Fabrication becomes structurally impossible** in the dangerous dimensions: the model can only pick from an enumeration of real bullet IDs. It cannot invent an employer because the schema doesn't have a free-text employer field on that path.
- **You get the diff for free** — the patch *is* the change log, satisfying "flag gaps / suggest adjustments / never invent" and giving the UI an honest "what changed and why" view.
- **Rendering is stable and testable** — golden-file tests on the renderer, independent of LLM non-determinism.
- It maps **directly** onto opencode's JSON-Schema structured output (Q7). The two decisions reinforce each other.

This mirrors what the best prior art already does: TailorCV's "fabrication detection" + "borderline flagging" + "change logging", and `resume-tailor`'s "keeps tailoring truthful by separating unsupported missing skills into confirmation items instead of adding them to the resume". Adopt the pattern; implement it with IDs and schema enums so it's enforced by construction rather than by prompt.

### Stay on LaTeX; don't migrate to Typst

`tailit` uses **Typst** (65 templates, fast, modern) and it's a genuinely attractive engine. But the project's CV source of truth is `.tex`, and migrating formats is pure cost with no v1 benefit. **Record Typst as a future option** if LaTeX compilation proves painful — the structured-CV design above makes that migration cheap anyway, since only the renderer changes.

---

## Q7 — Integrating the opencode LLM Backend from Python

**Recommendation: `opencode serve` over HTTP as the primary path, with a thin hand-rolled `httpx` client pinned against your own server's OpenAPI spec, using opencode's native JSON-Schema structured output. CLI subprocess as an explicit degraded fallback. Confidence: HIGH on the shape; the exact structured-output field name must be verified against your installed version.**

### Why HTTP beats the CLI subprocess

| | `opencode serve` (HTTP) | `opencode` CLI subprocess |
|---|---|---|
| Latency per call | One persistent server | Process spawn per call |
| Structured output | **Native JSON Schema** | Parse stdout and hope |
| Progress streaming | **SSE `GET /event`** | None |
| Concurrency | Multiple sessions | Awkward |
| Error semantics | HTTP status + typed error objects | Exit codes + stderr text |
| Health check | `GET /global/health` | `--version` |

The SSE stream is the underrated win: it gives the web UI **live pipeline progress** ("ranking 34/120…") for free, which materially improves a tool whose runs take minutes.

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

Server config: `opencode serve --port 4096 --hostname 0.0.0.0`. Set **`OPENCODE_SERVER_PASSWORD`** (HTTP basic auth, username defaults to `opencode`, override with `OPENCODE_SERVER_USERNAME`) **even on a local network** — it costs nothing and closes an obvious hole. Do **not** enable `--mdns` (broadcasts the endpoint). Add `--cors` only for the exact UI origin.

### Structured output — the key capability

opencode supports native JSON-Schema-constrained output. Verified shape from the official SDK docs:

```js
body: {
  parts: [{ type: "text", text: "..." }],
  format: {
    type: "json_schema",
    schema: { /* JSON Schema object */ },
    retryCount: 2,          // optional, default 2
  },
}
// result: result.data.info.structured_output
// on exhausted retries: result.data.info.error = StructuredOutputError { name, message, retries }
```

⚠️ **Documentation is internally inconsistent — resolve this before writing the client.** The SDK page's code example and its JSON Schema section use **`format`**; the server API table's prose note says the prompt endpoint "supports `body.outputFormat` for structured output". **The code example is almost certainly correct and `outputFormat` is stale prose**, but do not guess: **generate/inspect the client from `GET /doc` on your own running server** and write a **contract test** that asserts the field name still exists. This is the single highest-value 30 minutes in the integration, because everything downstream depends on it.

**How to use it:**

```python
class RankedListing(BaseModel):
    listing_id: int
    score: float = Field(ge=0, le=100)
    rationale: str
    matched_requirements: list[str]
    gaps: list[str]

schema = RankedListing.model_json_schema()
# → format={"type": "json_schema", "schema": schema, "retryCount": 2}
# then validate: RankedListing.model_validate(info["structured_output"])
```

**This is where the whole design coheres.** Pydantic v2 models generate the JSON Schema; opencode constrains generation to it; you re-validate the response with the same model. For CV tailoring the schema should enumerate **real bullet/section IDs** — which, combined with the structured-CV design in Q6, makes fabricated experience *structurally* impossible rather than merely *discouraged by a prompt*. You are replacing an ethical instruction with a type system.

### Prompt-injection boundary (a concrete, non-theoretical risk here)

Job-listing text is **untrusted input**. Descriptions are attacker-controllable (anyone can post a job) and are fed into a prompt. opencode's server also exposes high-privilege surfaces — `POST /session/:id/shell`, `/file/*`, `/find/*`, `/session/:id/permissions/*`.

**Controls, in priority order:**
1. **Constrain tools per call.** Pass `tools` to disable everything the ranking/tailoring calls don't need. A ranking call needs *no* tools. Do not run these sessions with the user's default agent/permissions.
2. **Structured output is your best defence.** A schema-constrained response dramatically shrinks the blast radius: an injection can only fill allowed fields, not redirect behaviour.
3. **Never put listing content in `system`.** It goes in `parts` (user turn), fenced with explicit delimiters and labelled as untrusted data.
4. **Run opencode with a locked-down agent + permission config**, not the user's interactive default. A dedicated config/agent with shell/file tools denied for this integration.
5. **Treat any instruction-like text found in a listing as a finding to record, not an instruction to follow** — and strip it before it reaches the UI.
6. **Bind the server to the Docker network only**, password-protected, never published to the host/LAN in v1.

### Model and agent selection

Pass `model: { providerID, modelID }` and `agent` **explicitly per call** rather than relying on server defaults — ranking (many cheap calls, low stakes) and tailoring (few calls, high stakes) should use different models. Discover options from `GET /provider` and `GET /agent` at startup and expose the choice in the UI.

### Python client: hand-roll it, but pin it

There is **no official Python SDK** (JS/TS only). Options: generate one from `/doc` with `openapi-python-client`/`datamodel-code-generator`, or hand-roll ~5 endpoints with `httpx` 0.28.1. **Recommendation: hand-roll.** Five endpoints over a stable, small surface is less code than a generated client plus its regeneration workflow — and you'll want hand-written retry/SSE logic anyway. But **read the field names from `/doc`** and add a contract test so a server upgrade that renames a field fails loudly in CI rather than silently in production.

### Fallback: CLI subprocess (degraded mode only)

Use only if `serve` cannot run in the container, or for an offline one-shot mode. Downsides that make it strictly worse: no SSE, process-per-call cost, structured output must be parsed from stdout (fragile), retries are yours to build, and argv is a prompt-injection surface. **Implement the LLM layer behind a `LLMBackend` protocol with `OpenCodeServerBackend` and `OpenCodeCLIBackend` implementations** so the fallback costs a class, not a refactor — then default to `serve`.

---

## Q8 — Frontend: Jinja2 + HTMX + Alpine.js

**Recommendation: server-rendered Jinja2 templates, HTMX for partial updates, Alpine.js for local UI state, Tailwind for styling. Confidence: HIGH.**

### Why HTMX here (and not React/Next)

Every screen in this app is a **queue + detail + form**:
- Browse/filter/sort the ranked job queue
- Job detail with fit breakdown and rationale
- Edit search criteria and ranking weights
- Application tracker (status changes)
- CV preview (embed the compiled PDF) + download

That is CRUD with partial updates — HTMX's exact sweet spot. The evidence for choosing it over an SPA here is strong: HTMX is 40k+★ and production-mature; a documented React→HTMX dashboard migration went **2,847 ms → 412 ms on throttled 3G** by shipping HTML instead of a JS bundle; and the well-known advice holds that "for standard CRUD applications — forms, dashboards, filtered tables, booking flows — HTMX is typically the more efficient choice" while React is correct when you need "significant client-side state between interactions, real-time collaboration, offline functionality, or complex optimistic UI updates" — **none of which this app has**.

**Concrete wins for this project:** no Node toolchain in the Docker image, one language across the stack, no API contract to maintain between two halves of your own app, and a single deployable.

⚠️ **Resume-Matcher uses Next.js 16 + React 19.** That is the right call *for them* — a multi-tenant web product with a marketing surface. For a local single-user Dockerised tool it's a tax with no return. Don't copy that part of their stack; do study their UI.

### Composition

| Layer | Choice | Use for |
|---|---|---|
| Templates | **Jinja2 3.1.6** (standard delimiters for HTML) | Full pages and fragments; one `Environment` for `.html`, a **separate** LaTeX-configured `Environment` for `.tex` (Q6) |
| Interactivity | **HTMX 2.x** | Filtering the queue, changing status, pagination, "run search now" with progress polling, loading detail panels |
| Local state | **Alpine.js 3.x** | Dropdowns, tabs, modals, toggles — *sparingly*, not as a framework |
| Styling | **Tailwind CSS 4** (CLI build at image build) or Pico.css | Fast, clean queue UI |
| PDF preview | `<iframe>` to the PDF endpoint, or a **pdf.js** embed | Preview the tailored CV inline before downloading |
| Section reordering (optional) | Sortable.js + an HTMX POST | Drag-to-reorder CV section priority — **defer**; a plain ordered form is fine in v1 |

**Vendor HTMX/Alpine/Tailwind output as local static files** (served via `StaticFiles`) — **no CDN**. A local self-hosted tool must work with no internet.

### Authentik-readiness for ~zero cost

The requirement is "must not architecturally block adding Authentik OAuth later, but must not pay for it now." Satisfy it with one seam:

```python
async def current_user() -> User:
    # v1: returns the fixed local user
    return LOCAL_USER

@router.get("/queue")
async def queue(user: User = Depends(current_user)): ...
```

Put `Depends(current_user)` on **every** route from day one. It costs nothing, changes no behaviour, and later becomes an OAuth/Authentik dependency — possibly as an ASGI middleware or `authlib` dependency — **with no route signature changes and no refactor**. When the time comes, `authlib` handles the OIDC dance; you do not need it now. (Authentik speaks standard OIDC, and the local user seam is the standard way to defer this.) An alternative is placing Authentik's forward-auth/`auth_request` in front of the container behind a reverse proxy at the hosted stage — also unblocked by this shape.

### Docker deployment

**`compose.yml` with two services** — this is the right shape and matches how the user already runs Docker:

```yaml
services:
  app:
    build: .
    ports: ["8000:8000"]
    volumes:
      - ./data:/data          # SQLite file (WAL), backups
      - ./cv:/cv              # .tex + structured cv.yaml — the source of truth
      - ./artifacts:/artifacts # compiled PDFs
    environment:
      - OPENCODE_BASE_URL=http://opencode:4096
      - OPENCODE_SERVER_PASSWORD=...
      - DATABASE_URL=sqlite+aiosqlite:////data/jobsearch.db
      - LATEX_ENGINE=tectonic
    depends_on:
      opencode: { condition: service_healthy }
  opencode:
    image: <pin the user's opencode version>   # or build a small image that runs `opencode serve`
    command: ["opencode", "serve", "--hostname", "0.0.0.0", "--port", "4096"]
    environment: [OPENCODE_SERVER_PASSWORD=...]
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:4096/global/health"]
    # NOT published to the host — app talks to it over the compose network
```

Notes:
- **`workers=1`** for uvicorn (Q5).
- **Do not publish the opencode port** to the host; only `app` is exposed.
- **Pin the opencode image/version.** opencode's API is evolving; a floating tag can break the `format`/structured-output contract. Pin it and run the `/doc` contract test in CI.
- **Multi-stage Dockerfile:** stage 1 builds wheels (and runs the Tailwind CLI); stage 2 is runtime + Tectonic binary + **primed TeX cache**. Keep `Dockerfile.texlive` as the documented fallback.
- **Python 3.13-slim** base, not 3.14 — wheel availability (Playwright/curl_cffi/lxml).
- Health check on `app` too, and a `/health` endpoint that reports opencode reachability — so the UI can say "LLM backend unreachable" instead of failing mysteriously.

---

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

---

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

---

## Stack Patterns by Variant

**If a source blocks rung 1 (pacing/backoff):**
- Promote that adapter to `curl_cffi` (TLS/JA3 impersonation) — same normalised output, different transport.
- Because "TLS fingerprinting alone isn't enough for modern bot protection" is also true, keep rung 3 available.

**If a source needs a JS runtime (browser fingerprint, client-rendered results):**
- Promote to `invisible-playwright` 0.16.0 (patched Firefox, deterministic stealth profile + seed, proxy-aware).
- Because it's the same engine the most-starred project in this space now depends on, and it's MIT/Apache-2.0.

**If scraping reliability becomes unacceptable across the board:**
- Add paid aggregator adapters (JobsPipe / Apify / ScrapFly) behind the same interface, and/or shift LinkedIn/Indeed weight onto Adzuna.
- Because the adapter interface makes this a config/priority change, not a rewrite — this is *why* the interface exists.

**If the CV uses packages Tectonic's bundle lacks:**
- Set `LATEX_ENGINE=texlive` and build the curated-subset `Dockerfile.texlive`.
- Because compile reliability beats image size; and the setting is config, not code.

**If the app ever needs >1 uvicorn worker or a second container:**
- Move to Postgres, swap `aiosqlite`→`asyncpg`, implement the Postgres FTS variant, add `pg_advisory_lock` around scheduled jobs.
- Because that's the exact point where SQLite's single-writer model and APScheduler's per-process scheduler both stop being safe.

**If the CV's `.tex` contains pdfTeX-only primitives (pre-existing):**
- Sanitise the preamble (comment out `\pdfcompresslevel` / `\pdfminorversion` / `\pdfobjcompresslevel`) before handing it to Tectonic.
- Because Tectonic (XeTeX-derived) rejects them.

**If a run needs to be inspected after the fact:**
- Read the `runs` table and the per-run structured logs (`structlog`), plus the `cv_artifacts.structured_diff`.
- Because "why did this listing get filtered?" and "what changed in this CV?" should never require re-running the pipeline.

---

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

---

## Open Questions / Gaps (carry into roadmap research)

1. **Resume-Matcher spike outcome (highest priority).** Can its tailoring engine be driven by opencode and its output path replaced with LaTeX? If yes, the roadmap changes substantially. **Answered by doing, not reading** — 1–2 days.
2. **Adzuna Ireland coverage.** Confirm the country path segment for Ireland and actual result quality for Dublin-based roles, plus realistic quota burn for the intended query matrix.
3. **Actual LinkedIn/Indeed survival rate at personal scale.** I found *documented* limits (≈10 LinkedIn pages/IP; ~1000 results/query; 429s common) but no evidence of a real once-daily single-user run's success rate. **Build a throwaway probe early and measure** — this determines whether Adzuna must be promoted to a primary source.
4. **opencode structured-output field name on the installed version** (`format` vs `outputFormat`) and whether the server's `/session/:id/message` body accepts `format` at all (the server docs table omits it while the SDK docs require it). Resolve against `/doc`.
5. **Whether opencode can be pinned/baked into the image** as the user runs it, or whether it must run as a sibling compose service with a mounted config/auth volume. Depends on the user's opencode auth/model setup.
6. **Tectonic's bundle contents vs the actual CV package list.** Unknown until the real `.tex` is run through it. Gate this with a spike on the user's actual CV before committing to Tectonic as default.
7. **Does ranking need per-listing LLM calls** (N calls, higher cost/latency) or can it batch (1 call per K listings)? Materially changes cost, timeout design, and whether `prompt_async` + SSE is required.
8. **JobSpy's `pandas`/`numpy` weight** in the image, and whether to isolate it in a separate worker/service from the FastAPI app.

---

## Sources

**Primary — official docs / specifications**
- Microsoft Learn, LinkedIn Talent Solutions — Job Posting API overview, Apply Connect, Job Posting Certification (LTS `2026-03`/`2026-04` views) — https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/overview · https://learn.microsoft.com/en-us/linkedin/talent/apply-connect/create-apply-connect-jobs — **HIGH**
- Indeed Partner Docs — Job Sync API, Job Update API (`docs.indeed.com`, pages dated 2026-07/2026-08) — https://docs.indeed.com/job-sync-api/integrate-with-job-sync-api — **HIGH**
- Indeed ToS (Ireland, `ie.indeed.com/legal`) — job-seeker licence scope, application review obligations — **HIGH**
- opencode — Server docs (last updated 2026-09-14), SDK docs (structured output / JSON Schema) — https://opencode.ai/docs/server/ · https://opencode.ai/docs/sdk/ — **HIGH**
- SQLite — FTS5 extension reference (`sqlite.org/fts5.html`, updated 2026-08-01) — **HIGH**
- PyPI JSON API — verified versions for fastapi, sqlalchemy, alembic, apscheduler, pydantic, jinja2, httpx, playwright, aiosqlite, sqlmodel, instructor, curl-cffi, pypdf, tenacity, uvicorn, litellm, python-jobspy, invisible-playwright, scrapling, camoufox — **HIGH**
- GitHub API — repo health for `speedyapply/JobSpy`, `feder-cr/AIHawk`, `srbhr/resume-matcher`, `hannibalevit/resumorph`, `yishaik/TailorCV`, `sardorml/tailit` (pulled 2026-09-15) — **HIGH**
- Tectonic — 0.17.0 release notes (2026-07-27) and CHANGELOG — https://github.com/tectonic-typesetting/tectonic/releases — **HIGH**
- Adzuna — developer portal, API overview and search endpoint docs — https://developer.adzuna.com/ · https://api.adzuna.com/v1/doc — **HIGH**

**Legal / regulatory**
- *hiQ Labs, Inc. v. LinkedIn Corp.*, 9th Cir. 17-16783 (2022-04-18) — CFAA inapplicable to public web pages — https://cdn.ca9.uscourts.gov/datastore/opinions/2022/04/18/17-16783.pdf — **HIGH**
- N.D. Cal., hiQ v. LinkedIn, summary judgment (2022-11-04) — ToS anti-scraping clauses enforceable in breach of contract — Proskauer / Privacy World analyses — **HIGH**
- EDPB, *Guidelines 03/2026 on web scraping in the context of generative AI* (July 2026) — https://www.edpb.europa.eu/ — **HIGH**
- CNIL, *Legal basis of legitimate interest: measures for web scraping* (Jan 2026) — https://cnil.fr/ — **HIGH**
- Openindex, *How do you ensure vacancy data is collected legally and ethically?* (2026-08-28) — GDPR + EU Database Directive + robots.txt framing — **MEDIUM**

**Benchmarks / engineering write-ups**
- *Engine-Transfer-Bench* (alphaXiv 2608.18329, 2026-08-18) — Tectonic vs pdfLaTeX/XeLaTeX/LuaLaTeX/Typst reliability, latency, portability — **MEDIUM-HIGH**
- Josh Finnie, *Why I Switched From TeX Live to Tectonic* (2025-11-17) — 2.3 GB→124 MB, 5 min→50 s, package preloading — **MEDIUM**
- `sunsided/clothoid-latex` PR #4 — Tectonic + pinned biber 2.17, VFS/temp-dir workaround, dual Dockerfile pattern — **MEDIUM**
- FormaTeX, *Why TeX Live Docker Images Are 4 GB* (2026-06-16) — size/time breakdown — **MEDIUM**
- Bradley Erickson, *LaTeX templates with Python and Jinja2* — the `\VAR{}`/`\BLOCK{}` environment — **MEDIUM** (widely replicated; older but the canonical reference)
- `jinjahtml-vscode` docs — alternative `(((...)))` LaTeX delimiters used by nbconvert — **MEDIUM**
- APScheduler + FastAPI + SQLAlchemy persistent-scheduler write-ups (elitedev, 2026-04/05; levelup.gitconnected, 2026-07) — `SQLAlchemyJobStore`, sync-engine requirement, `coalesce`/`misfire_grace_time`, advisory-lock caveat — **MEDIUM**
- DRS Web, *React is Overkill: Why Python + HTMX…* (2026-06-04) — HTMX vs React for CRUD; 412 ms vs 2,847 ms migration datapoint — **LOW-MEDIUM** (advocacy piece, but the structural argument and HTMX adoption figure are corroborated elsewhere)

**Comparison / ecosystem (vendor-authored — treated as marketing)**
- JobsPipe blog: Indeed API key, Indeed 2026, Adzuna API, JobSpy review — **LOW-MEDIUM** (JobsPipe sells against both JobSpy and Adzuna; used only for corroboration, and its claims were cross-checked against JobSpy's own README and Indeed's own docs)
- SQLite vs PostgreSQL comparisons (cr0x.net 2025-12-20; kunalganglani.com 2026-07-11) — single-writer constraint, FTS5 vs tsvector, migration triggers — **MEDIUM**

**Conflicting evidence, flagged (do not present as settled)**
- **Indeed Publisher API shutdown year:** 2023 vs 2024 — sources disagree. Decision unaffected; year unresolved.
- **"Indeed is the best scraper currently with no rate limiting"** (JobSpy README) vs the same README's "all of the job board sites are aggressive with blocking" vs third-party claims that Indeed/Glassdoor run serious bot management. **Unresolved — design for blocking on both.** Confidence: LOW.
- **AIHawk's licence:** GitHub API now reports **MIT**; third-party search results and its own earlier README state **AGPL-3.0**. The change is recent. Verify `LICENSE` in the repo before reusing any code. Confidence: MEDIUM.
- **opencode structured output field:** `format` (SDK code example) vs `outputFormat` (server API prose). Treat the code example as authoritative but **verify against your own `/doc`**. Confidence: MEDIUM.

---

*Stack research for: AI-assisted job search automation (local, self-hosted, Python-first)*
*Researched: 2026-09-15*


