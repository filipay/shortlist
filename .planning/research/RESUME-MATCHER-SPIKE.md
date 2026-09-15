# Spike: Resume-Matcher Reuse Evaluation

**Spike question:** Can `srbhr/Resume-Matcher` be adopted, forked, or mined as the CV-tailoring half of Job Search Copilot?
**Repo inspected:** `https://github.com/srbhr/Resume-Matcher` @ `ab2b370d1fb98d9272f71b8d6e54a9c51ac75110` (2026-09-10, shallow clone `--depth 1` of `main`)
**Method:** direct inspection of the cloned repository — licence, manifests, Dockerfile, routes, services and prompts. Not summaries, not blog posts.
**Spike date:** 2026-09-15

---

## VERDICT

> **PATTERN-COPY** — build greenfield; lift specific, verified designs from Resume-Matcher into `domain/sanitize.py`, `domain/cv.py` and `latex/verify.py`.
> **Confidence: HIGH.** Every load-bearing claim below is backed by a file path and line reference from the inspected commit.

This confirms the tentative prediction in `STACK.md` Q2 and closes decision **D9** (Conditional Greenfield) in `SUMMARY.md`. The gate has been run; the condition is discharged; greenfield stands.

**One-line reason:** the project is a well-built, well-tested *application* for the CV half only, whose output path (HTML→Chromium), LLM path (OpenAI-compatible endpoints, not `opencode serve`), persistence and resume schema are all different from ours — but whose `resume_preservation.py` and diff/patch verification machinery contain real, hard-won IP that is cheaper to copy than to rebuild.

---

## Q1 — Licence and Health

| Signal | Value | Source |
|--------|-------|--------|
| Licence | **Apache-2.0** (verified in `LICENSE`) | `LICENSE` line 1-2 |
| Stars / forks / watchers | 28,434 / 5,035 / 92 | GitHub API, 2026-09-15 |
| Open issues | **20** (API `open_issues_count` reports 55, which includes PRs) | GitHub Search API |
| Open pull requests | **35** | GitHub Search API |
| Created | 2020-04-08 | GitHub API |
| Last push | 2026-09-10 (5 days before this spike) | GitHub API + `git log -1` |
| HEAD commit | `ab2b370d1fb98d9272f71b8d6e54a9c51ac75110` — a Dependabot merge (`next-16.3.3`) | `git log -1` |
| Releases | `1.0.0` 2026-01-06 · `1.1.0` 2026-02-10 · `1.2.0` 2026-04-02 · `v1.3.0` 2026-09-06 | GitHub Releases API |
| Test weight | **67 test files, 20,086 lines** vs 17,720 lines of app code (≈1.13:1) | `find tests` + `wc -l` |
| Not archived / not disabled | `archived: false` | GitHub API |

**Health reading.** Actively maintained, quarterly-ish releases, genuinely well-tested (a >1:1 test-to-app ratio is a strong signal and rare at this scale). Two cautions:

- **35 open PRs against 20 open issues** is a high PR backlog. This is consistent with either a thriving contributor base or a maintainer bottleneck; I did not inspect PR ages, so I cannot attribute it. **Unverified which.**
- **v1.0 shipped only in January 2026**, despite the repo existing since 2020 — so the stable API surface is ~8 months old and still moving. Combined with `main` receiving Dependabot merges at HEAD, `main` is a moving target.

**Is it a viable dependency to build on?** **No — not as a dependency.** It is a viable *reference implementation*. The backend is not published as a library (`rm-backend` → HTTP 404 on PyPI; the PyPI `resume-matcher` package is an unrelated 0.2 release from 2024-02-08 with no connection to this project). There is no `pip install` path to the engine. Anyone reusing it is vendoring or forking source.

---

## Q2 — Architecture and Stack Reality

**Backend** (`apps/backend/pyproject.toml`):

```
name = "rm-backend", version = 1.3.0, requires-python = ">=3.13"
fastapi==0.128.4          uvicorn==0.40.0        pydantic==2.12.5
pydantic-settings==2.14.2 tinydb==4.8.2          sqlalchemy[asyncio]==2.0.36
aiosqlite==0.20.0         cryptography==50.0.0   litellm==1.86.2
markitdown[docx]==0.1.4   pdfminer.six==20260107 playwright==1.58.0
python-docx==1.2.0
```

**Frontend:** Next.js 16 / React 19 on Node 22 (`Dockerfile` stage 1, `node:22-bookworm`).

**This is the important nuance:** the *backend is already Python + FastAPI + Pydantic + SQLAlchemy*. There is **no polyglot problem at the engine level.** The polyglot problem is entirely at the **deployment** level:

```
Dockerfile (single image, two runtimes):
  stage 1  node:22-bookworm        → builds Next.js standalone
  stage 2  python:3.13-slim-bookworm
             ├─ apt: libnss3, libatk*, libcups2, libgbm1, libgtk-3-0, fonts-noto-cjk …
             ├─ COPY --from=stage1  /usr/local/bin/node       ← Node runtime in a Python image
             ├─ pip install .                                  ← FastAPI backend (internal :8000)
             ├─ COPY .next/standalone                          ← Next.js server (public :3000)
             └─ CMD /app/start.sh                              ← starts both
  EXPOSE 3000 · VOLUME /app/backend/data · HEALTHCHECK backend /api/v1/health
```

So "adopt as a component" means running a **Node 22 + Next.js 16 + Chromium + ~400 MB of GTK/NSS/Cairo system libraries** container alongside Job Search Copilot's FastAPI app — to obtain a CV-tailoring API we would then have to drive over HTTP, whose output format we do not want.

**Interaction with our Python-first FastAPI decision:** the backend *language* aligns (Python 3.13, FastAPI, Pydantic v2). The stack *choices* do not:

| Concern | Resume-Matcher | Job Search Copilot (`STACK.md`) |
|---------|----------------|---------------------------------|
| Persistence | TinyDB **and** SQLAlchemy/aiosqlite (mid-migration off TinyDB; see `app/scripts/migrate_tinydb_to_sqlite.py`) | SQLite WAL + SQLAlchemy 2.0 + **Alembic** |
| LLM abstraction | **LiteLLM** with provider keys | `opencode serve` behind our own `LLMBackend` port |
| PDF output | **Playwright + headless Chromium** | **Tectonic** (LaTeX) |
| Secrets | `cryptography`-encrypted key store in its own config file | settings + opencode's own auth |
| Frontend | Next.js 16 SPA | Jinja2 + HTMX |
| Migrations | none observed (Alembic absent from deps) | Alembic from revision 0001 |

**Verdict on Q2: reuse does not force a polyglot *backend*, but adopting the application does force a second runtime + a browser engine into the deployment.** That is a cost we would pay for capability we are not adopting.

---

## Q3 — Is the Tailoring/Scoring Engine Extractable?

This was the decisive question. The answer is **mixed, and the positive half is real**.

### Evidence FOR extractability

- **`app/services/improver.py` (1,529 lines) has zero database imports.** A targeted grep for `database|db_engine|session|Session|tinydb|TinyDB` returned nothing. Its entire dependency set is:
  ```python
  from app.llm import complete_json
  from app.prompts import (CRITICAL_TRUTHFULNESS_RULES, DIFF_IMPROVE_PROMPT, …)
  from app.schemas import ResumeData, ResumeFieldDiff, ResumeDiffSummary
  from app.services.parser import has_meaningful_resume_content
  ```
  That is a genuinely clean service layer over `llm` + `prompts` + `schemas`.
- **`app/services/resume_preservation.py` (839 lines) is pure.** Its imports are `copy`, `re`, `collections`, `decimal`, `difflib`, `typing` — no I/O at all. This file is **trivially liftable verbatim** into our domain (as patterns or, with attribution, as code).
- **Clear layering by directory:** `app/{routers,services,schemas,prompts,scripts}` — the author has deliberately separated HTTP from logic.
- **No global app-state coupling** in the services; functions take explicit dict/pydantic arguments and return models.

### Evidence AGAINST extractability

- **Orchestration lives in the router, not in a service.** `app/routers/resumes.py` is **2,489 lines** — by far the largest file in the backend. The multi-step pipeline (parse → keywords → skill-target planning → diff generation → apply → preservation → preview → persist) is sequenced there. Extracting "the engine" means re-implementing that orchestration around the services.
- **The data model is theirs, not ours.** `app/schemas/models.py` (918 lines) defines `ResumeData`, `ResumeFieldDiff`, `ResumeDiffSummary`, `ResumeChange`, `ImproveDiffResult` — a JSON-Resume-shaped nested document. It is **not** the ID-stable fact store ARCHITECTURE.md §7.2 specifies. Adopting the engine means adopting or shimming this schema on both sides.
- **Config, crypto and database come along.** `app/config.py` (426), `config_cache.py`, `crypto.py`, `database.py` (1,245), `models.py` — a full config/secrets/persistence stack that we would have to either carry or rewire. There is no `EngineService(config)`-shaped constructor to inject into.
- **No library packaging.** `rm-backend` is not on PyPI (404). `[project.scripts] app = "app.main:main"` runs the **FastAPI app**, not the engine. There is no CLI for tailoring. So "consume as a library" is not available, and "consume as a CLI" is not available.
- **"Consume as a sidecar" is technically available but expensive:** run their whole Docker image and drive `POST /api/v1/resumes/...` over HTTP. You then inherit the Node runtime, Chromium, their config/keys, their DB, and receive an **HTML/PDF** result in their resume schema.

### Is the engine separable?

```
Separable today, cleanly:   app/services/resume_preservation.py     (pure, 839 lines)
Separable with work:        app/services/improver.py                (no DB, but pulls app.llm,
                                                                     app.prompts, app.schemas)
Not separable:              routers/resumes.py orchestration, database.py, config.py+crypto.py,
                            schemas/models.py (their resume document model)
Not available at all:       a pip-installable package or a CLI entry point
```

**Answer: it is a decoupled *service layer inside an application*, not a library.** "Extract the engine" realistically means copying ~2,400 lines of service code plus its prompt templates plus its Pydantic schemas into our repo, then writing new orchestration and a new adapter from their `ResumeData` to our `CvFacts`. That is not free, but it is bounded — and it is roughly the same work as building the engine from scratch with their designs in hand, minus the benefit of our own schema being the native one.

---

## Q4 — Is the LLM Provider Pluggable (Could It Point at `opencode`, No Second Key)?

**Partly. The mechanism exists; the target does not.** This is the sharpest finding of the spike.

**What exists** (`app/llm.py`, `app/config.py`, `app/routers/config.py`):

- Supported providers (`app/config.py:279`): `openai`, `openai_compatible`, `azure_foundry`, `anthropic`, `openrouter`, `gemini`, `deepseek`, `groq`, `ollama`.
- `LLMConfig` (`app/llm.py:94`) carries `provider, model, api_key, api_base, api_version, reasoning_effort`.
- `openai_compatible` with a user-supplied `api_base` is first-class, including a **blank-key sentinel**:
  ```python
  def _effective_api_key(provider, api_key):
      if provider == "openai_compatible" and not api_key:
          return _OPENAI_COMPATIBLE_SENTINEL
  ```
  This is exactly the affordance a self-hosted endpoint needs.
- There is a hostname-normalising `_normalize_api_base()` handling `/v1` suffixes per provider.

**Why it still fails:**

1. **Local `opencode serve` is not an OpenAI-compatible endpoint.** It exposes a *session* API (`POST /session`, `POST /session/:id/message`, `GET /event`) as catalogued in `STACK.md` Q7. There is no `/v1/chat/completions`. The opencode OpenAI-compatible surface is the **hosted** `https://opencode.ai/inference/openai/v1/chat/completions` (opencode Console docs), which requires an opencode bearer token and sends request content to a third party. Corroborating evidence: multiple community projects exist *precisely* to paper over this gap — `tguidoux/opencode-to-openai` ("wraps the OpenCode CLI behind a standard OpenAI-compatible REST API") and `vincentmin/opencode-ai-sdk-server` ("An api bridge to expose an ai-sdk compatible endpoint for the opencode server").
2. **JSON mode is allowlisted to one host.** `app/llm.py:88`:
   ```python
   JSON_MODE_VERIFIED_HOSTS: frozenset[str] = frozenset({"api.stepfun.com"})
   def _openai_compatible_supports_json_mode(config): ...
       return _uses_opencode_zen_hy3(config) or host in JSON_MODE_VERIFIED_HOSTS
   ```
   A custom endpoint therefore gets **no `response_format`** — it falls back to prompt-only JSON plus a Python `response_validator` (`complete_json(..., schema_type="diff", response_validator=_validate_diff_result)`, `app/llm.py:1506`). There is careful defensive JSON extraction (`MAX_JSON_EXTRACTION_RECURSION = 10`, `MAX_JSON_CONTENT_SIZE = 1 MB`). **That is a validator-on-a-string, not schema-constrained generation.**

Note on a red herring: `_uses_opencode_zen_hy3()` and `OPENCODE_ZEN_HOST = "opencode.ai"` refer to **OpenCode Zen**, opencode.ai's *hosted* model gateway, and specifically to a `no_think` reasoning switch for the `hy3`/`hy3-free` aliases. This is **not** integration with a local `opencode serve` and should not be read as evidence of one.

**What would need to change to point at our opencode:**

| Option | Change required | Assessment |
|--------|-----------------|------------|
| **A. OpenAI-compatible shim** in front of `opencode serve` | Build and maintain a new bridge component (translate `/v1/chat/completions` ↔ `/session/:id/message` + structured output) | New component to own; bridges in the wild are 0–small-star, indie, and none is production-proven. **Unverified** whether any is maintained. |
| **B. Fork `app/llm.py`** to add a native opencode backend | Rewrite the call path inside a 1,718-line module dense with per-provider edge cases, then re-do it on every upstream release | Real work, recurring cost, and it discards our own `LLMBackend` port design |
| **C. Point at hosted opencode.ai** | Add the host to `JSON_MODE_VERIFIED_HOSTS` (a one-line change) — or use the Zen HY3 route | **Rejected on privacy grounds:** `PROJECT.md` requires that "no third party sees the user's CV content". Hosted inference violates it. |

**Answer: no, not without either a new bridge component (A) or abandoning our LLM port for a fork (B), and in all cases you lose native JSON-Schema structured output, which ARCHITECTURE.md §7.3 depends on to make fabrication structurally impossible.** Worse, option B is only needed *because* the engine's abstraction is a different one from ours — LiteLLM's provider model is "many vendor keys", ours is "one local agent runtime".

---

## Q5 — Is the Output Path LaTeX-Replaceable?

**No — neither LaTeX today, nor cheaply LaTeX-able.** And there is a naming trap worth recording.

**What it emits today.** `app/pdf.py` (905 lines) opens with:

```python
"""PDF rendering utilities using headless Chromium."""
from playwright.async_api import (...)  # async_playwright
```

The renderer is serious production infrastructure: a browser pool (`_playwright`, `_browser`, `_active_renders`, `_acquire_browser_user`), render-slot admission control (`_BrowserBusyError`: "Raised when all renderer slots are active; exports are never queued"), stale-browser replacement (`_replace_disconnected_browser`), deadline budgeting (`_render_deadlines`, `_await_before_deadline`, `_stage_timeout_ms`), PDF format/margin maps, and manual Chromium executable discovery across `/usr/bin/chromium`, snap, and flatpak paths. The Docker image installs the full Chromium dependency stack plus `fonts-noto-cjk` for CJK rendering.

**The naming trap.** `app/routers/resumes.py:1984` lists a template called `latex`:

> `- template: swiss-single, swiss-two-column, modern, modern-two-column, latex, clean, or vivid`

That is **not LaTeX**. It resolves to:

- `apps/frontend/components/resume/resume-latex.tsx` — **423 lines of React**
- `apps/frontend/components/resume/styles/latex.module.css`
- `apps/frontend/lib/types/template-settings.ts:267` — `{ id: 'latex', name: 'LaTeX' }`

Its own docstring says it is a *"Classic serif academic layout **reminiscent of** the popular LaTeX résumé templates"*, with `latex: { headerFont: 'serif', bodyFont: 'serif' }`. It renders DOM nodes with CSS variables. A grep for `latex|.tex|tectonic|typst|pdflatex` across `apps/backend/app` and the top-level docs found **no LaTeX generation, no `.tex`, no LaTeX engine of any kind**.

**So Resume-Matcher *cosplays* LaTeX typographically while producing HTML→Chromium PDFs.** This is a striking confirmation of the `STACK.md` differentiator claim (DF-1: "Nobody templates and recompiles `.tex`") — and it sharpens it: one of the closest competitors ships a template *named* LaTeX that is a CSS theme.

**Cost of forcing a LaTeX output path:** replace, not adapt.

| Task | Effort |
|------|--------|
| Discard `app/pdf.py` + `app/preview.py` and the Playwright/Chromium/CJK image layer | Remove ~905 + N lines, plus ~400 MB of image |
| Write a `ResumeData → CvFacts` (their schema → ours) adapter | New code, ongoing coupling to their schema |
| Build our Jinja2 `\VAR{}`/`\BLOCK{}` renderer + Tectonic compile + verification gate | **This is our Phase 4/6 work anyway** (`ARCHITECTURE.md` §14.3) |
| Keep their preview/iteration UI? | It is React; ours is HTMX |

**Answer: the output path is deeply coupled (Chromium in the Dockerfile, Playwright in the deps, React templates in the frontend) and replacing it means deleting a subsystem rather than swapping a strategy.** Crucially, the replacement is work we have already planned — so reuse here buys **nothing** and costs the removal.

---

## Q6 — Anti-Fabrication Mechanism

**This is where Resume-Matcher is considerably stronger than the sibling research implied, and the finding changes what we should copy.**

`FEATURES.md`'s competitor matrix records Resume-Matcher's anti-fabrication column as *"Not a stated concern."* **That is wrong, and I am flagging it as a correction.** There are two substantial mechanisms.

### (a) Deterministic preservation — `app/services/resume_preservation.py` (839 lines)

> *"Deterministic preservation at the final AI-authored resume seam."*

- **Protected identity fields per section** (`_PROTECTED_FIELDS`):
  `workExperience: (id, title, company, location, years)`; `education: (id, institution, degree, years)`; `personalProjects: (id, name, role, years, github, website)`; `customItems: (id, title, subtitle, location, years)`.
  **This is the same insight as our stable-ID fact store**: identity fields are enumerated and protected, not regenerated.
- **Metric containment** — `_novel_numbers(source, candidate)` with a real numeric extractor (`_NUMBER_RE` handling currency symbols, thousands separators, units, and `_is_date_like_number` to avoid flagging dates). Directly parallels our verifier check 4.
- **Structural invariants** — `_entry_bucket_violation`, `_description_contract_preserved`, `_merge_entries`, `_merge_additional`, `_merge_custom_sections`: entries cannot be invented, dropped or re-bucketed.
- **Grounding band** — `_GROUNDING_REVIEW_THRESHOLD = 0.45` with `SequenceMatcher`-based `_similarity`, emitting `GROUNDING_REVIEW_REQUIRED` for weakly-grounded rewrites. Parallels our confidence tiering.
- **The seam** — `finalize_ai_resume(source, candidate, *, allow_review_claims=True, allow_appended_rows=False)`, documented as:
  > *"Return a non-mutating AI result that preserves the source contract. Weakly grounded rewrites remain when `allow_review_claims` is true so a preview can present them for explicit confirmation. **Definite new metrics, extra rows, missing sections and identity drift are always repaired.**"*

### (b) Diff/patch + verification — `app/services/improver.py`

The primary tailoring path is **not** "ask for the whole resume". It is a field-level diff:

```
generate_resume_diffs(original_resume, job_description, job_keywords, …)
   → ImproveDiffResult: list of ResumeChange { path, action, original, value }
apply_diffs(...)          # _resolve_path / _set_at_path, guarded by _is_path_allowed / _is_path_blocked
verify_diff_result(...)   # 5 local, zero-LLM-cost checks
```
with an **optimistic-concurrency check** `_verify_original_matches(actual, expected)` — the change is only applied if the original text still matches what the model claims it is editing. Plus `verify_skill_target_plan()` / `_skill_present_in_resume_text()` / `_build_allowed_skill_target_keys()`, which **refuse to target a skill that is not already in the resume** — i.e. an explicit anti-skill-injection guard. And `_INJECTION_PATTERNS` + `_sanitize_user_input()` for prompt-injection in the JD.

### Where it diverges from our design — and this is the whole point

| Dimension | Resume-Matcher | Job Search Copilot (ARCHITECTURE.md §7, §10) |
|-----------|----------------|---------------------------------------------|
| Who authors CV text? | **The LLM authors replacement prose** (diffs carry new free text) | **Nobody.** The LLM can only select/reorder/re-weight/drop enumerated IDs; no free-text field reaches the PDF |
| Fabrication defence | **Detect and repair** (`finalize_ai_resume` rewrites the offending field back to source) | **Make unrepresentable** (schema has no place to put an invented fact) + verify |
| Failure policy | **Repair, or warn and proceed.** `verify_diff_result` docstring: *"All checks are local (zero LLM cost). **Warnings are informational — they don't block the response.**"* | **Block.** No automatic repair — "repair pressure is fabrication pressure" |
| Human checkpoint | Yes — weak claims surface in preview for "explicit confirmation" | Yes — assisted apply + block-and-review |
| Structured output | Prompt-only JSON + `response_validator` (JSON mode not available to custom endpoints) | Native JSON-Schema constraint via `opencode` |

**Assessment.** Resume-Matcher independently arrived at the *same ingredients* we did — stable per-entry IDs, protected identity fields, metric-containment, structural invariants, a grounding-similarity band, path allowlists, injection sanitisation — but assembled them as **"let the model rewrite, then repair and warn"** rather than **"let the model only select, then block"**. The research in `FEATURES.md` §4 (96.7% of baseline outputs contained an unsupported claim; 50% survived prompt guardrails alone; "repair pressure is fabrication pressure") is precisely why our ordering is stronger: repair is the mechanism that reintroduces fabrication, because the cheapest way to satisfy a repair check is to rephrase rather than remove.

**Is anything worth adopting? Yes — several things, and they are concrete:**

1. `_novel_numbers` + `_NUMBER_RE` + `_is_date_like_number` → seed for verifier **check 4 (metric containment)**.
2. `_verify_original_matches` → the optimistic-concurrency pattern for our `apply_patch` / artifact persistence (guard: the facts snapshot must still match what the patch was computed against).
3. `_GROUNDING_REVIEW_THRESHOLD`-style similarity banding → informs our **confidence tier** and **check 6**.
4. `_INJECTION_PATTERNS` → seed list for `domain/sanitize.py`.
5. `_PROTECTED_FIELDS` per section → corroborates and can refine our `cv.yaml` immutable-field list.
6. `_is_path_allowed` / `_is_path_blocked` → an explicit field-level allow/deny layer as defence-in-depth behind the schema.

**Answer: it does not predate or ignore the problem — it solves a harder version of it (rewriting) with weaker guarantees (repair + warn). We keep the structural design and copy the detectors.**

---

## Q7 — Reuse Verdict

### The four differentiators, explicitly

| # | Differentiator | Reuse would… | Evidence |
|---|----------------|--------------|----------|
| 1 | **LaTeX as CV source of truth and target** | **BREAK** | No `.tex` anywhere; output is HTML→headless Chromium (`app/pdf.py`); the `latex` template is React + CSS (`resume-latex.tsx`, 423 lines) |
| 2 | **Deterministic filter before LLM spend** | **NEITHER — absent** | No ingestion of any kind: grep for `scrape\|jobspy\|linkedin\|indeed\|beautifulsoup\|selenium` finds only resume *contact fields*. It starts from a pasted JD. Nothing to reuse, nothing to conflict |
| 3 | **opencode backend, no second provider key** | **BREAK** | `openai_compatible` + `api_base` exists, but local `opencode serve` is not OpenAI-compatible; the only opencode OpenAI-compatible surface is hosted (breaks local-privacy); JSON mode is allowlisted to `api.stepfun.com`, so you lose schema-constrained output even if bridged |
| 4 | **Tailored-CV-version → outcome link** | **PARTIALLY RETAINED — this is a correction** | `applications` table (`app/models.py:124`) has `resume_id` and a `uq_application_job_resume` constraint; the tracker is a 7-column kanban; `get_application_detail` embeds "the applied resume". But `resume_id` points at a *mutable resume document*, not an immutable, verified, hash-stamped artifact with a change log — and there is no outcome analytics |

On (4) I am knowingly amending the sibling claim that a version↔outcome link is "absent from every prior-art tool surveyed" (`STACK.md` Q2, `FEATURES.md` DF-9). **Resume-Matcher has a partial version of it.** Our differentiator survives in the form that matters — linking the *exact verified artifact* to the outcome — but it should be described as "strongest, not unique", and DF-9's wording in the roadmap should be tightened to "verified artifact ↔ outcome" rather than "CV version ↔ outcome".

Similarly on our DF-3 ("per-factor sub-scores"), `app/services/ats.py` computes a **decomposed weighted score** (`keyword_match` 0.55 / `skills_coverage` 0.25 / `section_completeness` 0.20, `_WEIGHTS` summing to 1.0) with `_generate_recommendations()`. That is the same *shape* as our `U = Σ w_f·φ_f`, though the factors are ATS-coverage rather than candidate-fit, and no evidence IDs are attached. Another honest downgrade from "absent from the field" to "independently corroborated".

### Why not the other three verdicts

- **Adopt as-is — rejected.** It solves the wrong half, in the wrong formats, with the wrong runtime. Concretely: no ingestion (differentiator 2 untouched); HTML→Chromium output (differentiator 1 broken); a Node+Chromium deployment bolted onto a Python/FastAPI app; an LLM layer that cannot reach `opencode serve` without a new bridge (differentiator 3 broken); and its own resume schema, config store, crypto layer and TinyDB-legacy persistence. You would run a second application, in a second runtime, to obtain a PDF you intend to replace.
- **Fork and extend — rejected, but this is the closest call and worth stating fairly.** The genuine pull is real: `improver.py` has no DB coupling, `resume_preservation.py` is pure, the test suite is excellent, and the licence is permissive. But the arithmetic does not work:
  - *What you inherit:* ~17,700 lines of app + a Next.js 16 frontend + a Chromium deployment + a moving `main` (35 open PRs, dependabot at HEAD, quarterly releases, 8-month-old v1.0).
  - *What you must replace:* the entire output path, the entire LLM backend, the resume document model, the persistence layer, and the frontend.
  - *What you must add:* the entire other half — ingestion, adapters, dedup, criteria, filter, ranking, queue UI, scheduler, artifact verification gate, assisted apply, tracker link. This is the majority of the project.
  - *What you actually save:* roughly the two service modules and their prompts — call it ~2,400 lines of patterns, most of which we need to re-express against a different data model anyway.
  - *Ongoing cost:* a fork of a fast-moving 28k★ monolith diverges immediately. Apache-2.0 makes it legal; it does not make it cheap.
- **Reject — rejected.** Dismissing it would forfeit real IP. Six concrete, verified artefacts are worth lifting (§Q6), two of which (`_novel_numbers`, `_verify_original_matches`) directly improve the spec in ARCHITECTURE.md §10 and §7.4.
- **Pattern-copy — chosen.** It matches where the evidence lands: the engine is not importable (not on PyPI, no CLI), not addressable (wrong protocol for `opencode serve`), not our output format (HTML→Chromium vs LaTeX), and not our data model; but its hard-won detectors and its independent convergence on stable-ID/protected-field/metric-containment design are directly reusable.

**Additional note for the record:** `STACK.md` Q2 recommended a 1–2 day spike asking *"can Resume-Matcher's tailoring engine be driven by opencode and can its output path be replaced with LaTeX?"* The answer is now established as **"no without a bridge, and only by deletion respectively"** — the honest resolution `STACK.md` anticipated ("likely no, not without a fork that costs more than building").

---

## Roadmap Impact

**The phase order in `ARCHITECTURE.md` §14.3 does not change.** This is an explicit null result on sequencing, and a null result is the useful outcome here: no re-planning is required, and decision **D9 is closed** with greenfield confirmed.

The eight phases (1 walking skeleton → 2 clean queue → 3 LLM port → 4 CV fact store + Tectonic spike *in parallel* → 5 ranking ★ → 6 tailoring + verification → 7 assist + tracker → 8 ops) **stand as written**, including the deliberately-parallel Phase 4 track — which this spike reinforces, since it confirms there is no shortcut to the LaTeX path to be found in prior art.

Three **additive** changes only:

| Phase | Addition | Why |
|-------|----------|-----|
| **2** (clean queue) | Add a task: seed `domain/sanitize.py` with an `_INJECTION_PATTERNS`-style rule set | Verified: Resume-Matcher ships a concrete injection sanitiser (`app/services/improver.py:27`); cheaper to adapt than to invent |
| **4/6** (CV + verification) | Add a task: implement `_novel_numbers`-equivalent metric containment (`_NUMBER_RE` + date-like-number exclusion) as verifier check 4, and adopt `_verify_original_matches` as the optimistic-concurrency guard on `apply_patch` | Verified utility; `resume_preservation.py` is pure and trivially portable |
| **6** (tailoring) | Adopt `_GROUNDING_REVIEW_THRESHOLD`-style similarity banding to inform `confidence_tier` and verifier check 6 | Verified: a working, tuned threshold pattern already exists |

Two **documentation corrections** to carry into the roadmap (not scope changes):

1. **DF-9 wording** — from "CV version ↔ application link (absent from the field)" to **"verified artifact ↔ outcome link"**. Resume-Matcher's `applications.resume_id` is a partial precedent.
2. **DF-3 wording** — "per-factor sub-scores with weights computed in code" is independently corroborated by `ats.py`'s `_WEIGHTS` decomposition; it remains a differentiator in *purpose* (candidate fit + evidence IDs + sliders) but is no longer unique in *shape*.

And one source-correction worth carrying into `FEATURES.md` when it is next revised: the competitor matrix's Resume-Matcher anti-fabrication cell ("Not a stated concern") is contradicted by `app/services/resume_preservation.py` and `verify_diff_result`. The project's stance is *repair-and-warn*, not *indifference* — which strengthens rather than weakens our position, because it shows the industry's most-starred tool chose the weaker policy.

---

## What We Reuse / What We Build

### Reuse (copy patterns into our codebase; attribute in a `NOTICE`/comment per Apache-2.0 §4)

| Artefact | Source | Destination in our repo |
|----------|--------|-------------------------|
| Novel-number / metric-containment extractor and date-like exclusion | `app/services/resume_preservation.py` (`_NUMBER_RE`, `_is_date_like_number`, `_novel_numbers`) | `latex/verify.py` — check 4 |
| Grounding-similarity threshold band | `app/services/resume_preservation.py` (`_GROUNDING_REVIEW_THRESHOLD`, `_similarity`) | `domain/scoring.py` confidence tier + `latex/verify.py` check 6 |
| Per-section protected-field map | `app/services/resume_preservation.py` (`_PROTECTED_FIELDS`) | `cv/cv.yaml` immutable-field definitions |
| Optimistic-concurrency "original still matches" guard | `app/services/improver.py` (`_verify_original_matches`) | `domain/cv.py` `apply_patch` + artifact persistence |
| Injection pattern list + JD sanitiser | `app/services/improver.py` (`_INJECTION_PATTERNS`, `_sanitize_user_input`) | `domain/sanitize.py` |
| Path allow/deny for LLM-writable fields | `app/services/improver.py` (`_is_path_allowed`, `_is_path_blocked`) | `domain/cv.py` defence-in-depth behind the schema |
| Named-weights-summing-to-1.0 decomposition as a design precedent | `app/services/ats.py` (`_WEIGHTS`) | corroborates `domain/scoring.py` (no code needed) |
| Test-suite organisation: `unit` / `service` / `integration` / `eval` markers with evals excluded from the default run | `apps/backend/pyproject.toml` | `pyproject.toml` test config |
| TinyDB→SQLite transitional migration pattern | `app/scripts/migrate_tinydb_to_sqlite.py` | reference only, if we ever need a data import |

**Licence compliance:** Apache-2.0. Copying code requires attribution and a `NOTICE`-style record of the source, plus preservation of any licence headers. Patterns and ideas need no attribution but should be credited in a comment for traceability. Verify whether any recycled file carries a header before copying.

### Build (unchanged from ARCHITECTURE.md — reuse does not substitute for any of it)

- `sources/` — the entire pluggable adapter layer, LinkedIn + Indeed + Adzuna (Resume-Matcher has **no** ingestion)
- `domain/dedup.py`, `domain/criteria.py`, `domain/filter.py` — dedup, criteria compiler, hard-rule filter, exclusion reasons
- `domain/scoring.py` + `pipeline/rank.py` + `pipeline/narrate.py` — the ranking pipeline with per-factor evidence IDs and code-computed weighted sum
- `cv/factstore.py` + `domain/cv.py` — the ID-stable `cv.yaml` fact store and the ID-only patch model (structurally stronger than Resume-Matcher's author-then-repair diffs)
- `latex/` — Jinja2 `\VAR{}`/`\BLOCK{}` renderer, Tectonic compiler, **blocking** verification gate
- `llm/` — the `LLMBackend` port and the opencode server/CLI backends with native JSON-Schema structured output
- `jobs/` — APScheduler wiring
- `web/` — the queue, detail, criteria/weights, tracker and CV-preview surfaces in Jinja2 + HTMX
- The tracker's **verified-artifact ↔ outcome** link (stronger than `applications.resume_id`)

---

## Unverified Claims

Stated plainly, separated from what was directly established.

1. **Whether any OpenAI-compatible bridge for `opencode serve` is production-grade.** I verified such bridges exist (`tguidoux/opencode-to-openai`, `vincentmin/opencode-ai-sdk-server`) and that the gap they fill is real. I did **not** clone, run, or test any bridge against a live `opencode serve`. Star counts/low commit counts suggest none is battle-tested. **Unverified.**
2. **The runtime behaviour of Resume-Matcher's `complete_json` against a custom `openai_compatible` endpoint.** The no-JSON-mode conclusion is read from the `JSON_MODE_VERIFIED_HOSTS` allowlist and `_openai_compatible_supports_json_mode()`; I did not execute a call. High confidence in the reading, but not executed. **Unverified empirically.**
3. **Fork effort estimate.** The claim that a fork costs more than a build is a judgement from the file sizes, coupling and divergence rate — not a measured estimate. A team of five might reach a different conclusion.
4. **The 35-open-PR backlog's cause.** Whether it reflects healthy contribution or a maintainer bottleneck is not established; PR ages were not inspected.
5. **Full write-path semantics of `applications.resume_id`.** I read the schema (`app/models.py:124`), the constraint, and `get_application_detail`; I did not trace every write path, so the exact degree of immutability of the linked resume is unconfirmed.
6. **Whether Resume-Matcher's own resume model could be losslessly mapped to our `CvFacts`.** I inspected `app/schemas/models.py` structurally but did not attempt the mapping. This affects the size of the "what we save" estimate for a hypothetical fork.
7. **Alembic absence.** No Alembic dependency appears in `pyproject.toml` and none was observed in the tree; I did not exhaustively prove there is no migration mechanism.
8. **Any third-party fork or downstream that has already done the extraction.** Not investigated.
9. **Health metrics are a 2026-09-15 snapshot** and will drift.

---

*Spike output for: Resume-Matcher reuse evaluation — Job Search Copilot*
*Repo: `srbhr/Resume-Matcher` @ `ab2b370d1fb98d9272f71b8d6e54a9c51ac75110` (2026-09-10)*
*Reproduce with: `git clone --depth 1 https://github.com/srbhr/Resume-Matcher && cd Resume-Matcher && git log -1`*
*Spiked: 2026-09-15*