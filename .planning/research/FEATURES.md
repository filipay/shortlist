# Feature Research

**Domain:** AI-assisted job search automation (local, self-hosted, Python-first, Dockerised) — aggregation → hard-rule filter → LLM ranking → LaTeX CV tailoring → assisted apply → tracker
**Researched:** 2026-09-15
**Confidence:** MEDIUM-HIGH overall — HIGH on prior-art feature inventories (GitHub READMEs, product docs and review corpora, all read 2026-09-15); MEDIUM on "what users complain is missing" (review sites carry selection bias and several comparison pages are vendor-authored); MEDIUM-HIGH on the anti-fabrication design (independent academic papers and open-source implementations converge); LOW on dedup thresholds at this project's scale (no personal-scale corpus to tune against).

> Scope: this file answers the seven feature questions the project asked, categorised as **table stakes / differentiators / anti-features**, with complexity and dependencies so roadmap phases can be ordered. It is **prescriptive**, not a menu. Where the field disagrees, the disagreement is stated with both sides.
>
> Companion file: `STACK.md` (same directory, same date). Stack decisions referenced here — JobSpy, SQLite+FTS5, Tectonic, `opencode serve`, HTMX — are settled there and are not re-litigated.

---

## Method and prior-art clusters

Four clusters were inventoried. Each was read for **shipped features**, not marketing claims.

| Cluster | Representative tools | Their role for this project |
|---|---|---|
| **A — Aggregation / scraping** | JobSpy, Adzuna API, JobRadar, Faculty Atlas, `career-ops`, `linkedin-assistant`, ShouldApply, Nox, JobGhosting | Feature source for ingestion, dedup, freshness, pipeline UI |
| **B — Auto-appliers (rejected category)** | AIHawk, LoopCV, LazyApply, Sonara, JobCopilot, ApplyIQ | **Negative** evidence base: what fails, how it fails, what users hate |
| **C — CV tailoring / ATS** | Resume-Matcher, TailorCV, ResuMorph, `tailit`, `aarg`, `resume-honest`, Jobscan, Teal Resume Builder | Feature + guardrail source for tailoring; the fabrication boundary |
| **D — Trackers / CRMs** | Teal, Huntr, Simplify, TrackJobs, Jobscan Tracker | Feature source for the application pipeline and alerts |

**The most useful finding across all four clusters:** the tools that fail loudly fail in one of two places — **silent delivery failure** (Cluster B) and **silent fabrication** (Cluster C). Both are *trust* failures, not capability failures. The feature set should therefore be organised so that **the pipeline's honesty is observable**: every stage reports what it did, and every claim traces to a source fact.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Missing these makes the tool feel broken — not "minimal", broken. Ratings are implementation complexity for *this* stack, not for the category.

| # | Feature | Why Expected | Complexity | Notes / evidence |
|---|---|---|---|---|
| TS-1 | **Pluggable source adapters + one normalised listing schema** | The user asked for it; every aggregator has one | **MEDIUM** | JobSpy already normalises 5 boards; the work is the adapter *interface*, the canonical schema, and never importing JobSpy from domain code (`STACK.md` Q1). A source that fails must return partial/none, not raise. |
| TS-2 | **Persist listing with `first_seen_at` / `last_seen_at` / `content_hash`** | Without it there is no "new", no freshness, no closure | **LOW-MEDIUM** | JobSpy has **no persistence, no dedup, no change tracking** — the gap every JobSpy consumer fills itself. `last_seen_at` older than N days ⇒ inactive; `first_seen_at > last_run` ⇒ new. |
| TS-3 | **Cross-source deduplication with a reversible audit trail** | Duplicates are noticed instantly and destroy trust in the whole feed | **MEDIUM-HIGH** | Tier 1 `UNIQUE(source, source_listing_id)` upsert; Tier 2 normalised composite key + fuzzy threshold (~90) plus a `listing_dupes` audit table. **Merge, don't discard** — union the fields, keep every source URL. A false merge is the worst failure mode, so it must be undoable. |
| TS-4 | **Editable search criteria stored in the DB** (role/keywords, include/exclude terms, location, remote, salary floor, seniority) | "Filters work and I can change them" is the floor | **LOW-MEDIUM** | PROJECT.md requirement. Store as structured rows/JSON, not a config file — the UI edits them. |
| TS-5 | **Deterministic hard-rule filter applied before any LLM call** | Cost control + explainability; the user chose this explicitly | **LOW-MEDIUM** | Cheap, fast, auditable. **Record *which rule* excluded each listing** — "why is this not in my queue?" is a real question (see TS-9). |
| TS-6 | **Listing text search, filter and sort over the queue** | A daily queue you cannot query is a list | **LOW** | SQLite **FTS5 + BM25** (`STACK.md` Q4). Never `LIKE '%term%'`. |
| TS-7 | **Application tracker with explicit stages** | Every tracker in Cluster D has it; it is the second reason people install these tools | **LOW** | Converged stage set across Cluster D: `queued → shortlisted → applied → interviewing → offer` plus terminal `rejected` / `withdrawn`. Huntr and TrackJobs ship kanban; Teal ships kanban **and** table. Store `applied_at`, `notes`, and per-listing `status`. |
| TS-8 | **Manual status control + notes per application** | The human knows more than the tool does | **LOW** | Plain form + HTMX partial. |
| TS-9 | **Run history / pipeline observability** ("what did the last run do?") | *Silent failure is the best-documented complaint in Cluster B* | **LOW-MEDIUM** | One `runs` row per run: started/finished, per-source counts, filtered count, ranked count, LLM calls/tokens, errors. Plus a per-listing "excluded by rule X" reason. JobRadar ships exactly this ("agent activity, source status, source errors"). LoopCV's defining failure was invisible runs. This is a table stake precisely because it is the antidote to the field's worst failure mode. |
| TS-10 | **Manual "run now" + persisted daily schedule + visible next-run time** | Both triggers were explicitly requested; a scheduled-only tool you cannot nudge is unusable | **LOW-MEDIUM** | APScheduler 3.11.3 in-process, `--workers 1`, `coalesce`/`misfire_grace_time` (`STACK.md` Q5). The manual trigger must enqueue and return, not block. |
| TS-11 | **Structured CV fact store as the tailoring source** (`cv.yaml` with stable IDs) | Tailoring a `.tex` blob is unauditable; the ID model is what makes honesty enforceable | **MEDIUM** | The single highest-leverage design decision (`STACK.md` Q6). Not a user-visible "feature", but every differentiator below depends on it. |
| TS-12 | **Tailored CV PDF generation + preview + download** | This is the product | **MEDIUM-HIGH** | Jinja2 LaTeX environment → Tectonic → PDF; preview via `<iframe>`/pdf.js. Gated on TS-11. |
| TS-13 | **Review-and-edit the tailoring result before compiling** | A suggestion you cannot override is a liability | **MEDIUM** | Resume-Matcher ships edit / add-remove / rearrange. `STACK.md` notes a plain ordered form is fine in v1 with rich drag-drop deferred. Minimum: accept/reject/annotate each proposed change. |
| TS-14 | **Compile-time honesty verification (assert-then-block)** | PROJECT.md makes "never fabricate" a hard line, so it must be *enforced*, not prompted | **MEDIUM** | Extract `pypdf` text from the compiled PDF; assert every source-CV employer/date/skill string is still present and **no new named entity appeared**; fail the build and log otherwise. Prompt-only guardrails are demonstrably insufficient — see *Tailoring vs fabrication* below. |
| TS-15 | **In-app "new since your last visit" signal on the queue** | The Core Value is "every morning there is one queue"; without a delta the user cannot tell what changed | **LOW** | Badge/count from `first_seen_at > last_seen`. Faculty Atlas, `career-ops`, Adligator Trackers and Indeed itself (`fromage=last`) all converge on this. Satisfies the notification need in-app, honouring the PROJECT.md decision to skip email digests in v1. |
| TS-16 | **Save / hide / archive a listing, with the action sticky** | Un-dismissable noise makes the queue unusable | **LOW** | JobRadar's "save, ignore, or apply"; ShouldApply auto-archives stale items. Crucially: **persist these events from day one** — they are the training signal for DF-11. |
| TS-17 | **Stale-listing signal from age and last-seen** | Roughly 1 in 3 postings is stale or phantom, and users actively distrust old ads | **LOW** | Age from `first_seen_at`, plus `last_seen_at` recency and `content_hash` change. Surface as a badge: Fresh / Stale (30d+) / Likely dead (60d+). Cheap because TS-2 already stores the fields. |
| TS-18 | **Cover letter drafting from the same grounded fact set** | Clusters C and D both ship it; the alternative is hand-writing one per application | **MEDIUM** | **Project-deferred, not category-optional.** PROJECT.md does not list it; Jobscan, Teal, Huntr, Resume-Matcher and AIHawk all do. Put it in v1.x, but architect the prompt and guardrails so it reuses the same evidence IDs (TS-11) — otherwise it gets rebuilt. |
| TS-19 | **Data export (CSV/JSON) of the pipeline and artefacts** | Lock-in anxiety is real even for self-hosted tools; every Cluster D tool offers export | **LOW** | One endpoint over the same ORM models. Cheap insurance and a debugging aid. |

### Differentiators (Competitive Advantage)

These map directly to PROJECT.md's Core Value and to what the field demonstrably does **not** do.

| # | Feature | Value Proposition | Complexity | Notes / evidence |
|---|---|---|---|---|
| DF-1 | **LaTeX as CV source of truth *and* tailoring target** | Every prior-art tool renders HTML→Chromium (Resume-Matcher), DOCX (TailorCV, ResuMorph) or Typst (`tailit`). **Nobody templates and recompiles `.tex`.** It is the user's real asset and it makes diffable, deterministic, text-verifiable output possible | **HIGH** | `STACK.md` Q6. Payoffs that fall out for free: golden-file renderer tests, `pypdf` verification (TS-14), a real structural diff, and a cheap escape hatch to Typst later. |
| DF-2 | **Deterministic filter *before* LLM spend** | Absent from the field — Resume-Matcher and friends go straight to the LLM. Caps the dominant variable cost **and** makes "why is this ranked here?" explainable in two layers | **MEDIUM** | PROJECT.md Key Decision. The cost rationale is the user's and is sound; the *explainability* consequence is the underrated one — it makes run-level debugging possible without re-running. |
| DF-3 | **Per-factor sub-scores + weighted sum computed in code, LLM constrained to schema** | Weight sliders, fit breakdown, honest re-ranking and stable rationale all require the score to be **decomposed**, not opaque. This is the one design choice that makes four separate requirements cheap instead of expensive | **MEDIUM-HIGH** | JobMatchAI (ACL 2026 demo) does exactly this: a white-box utility `U = Σ w_f · φ_f` over skill/experience/location/salary/semantic/company with **user-adjustable sliders** and a default weight table (0.35/0.25/0.15/0.10/0.10/0.05). It is the strongest published precedent for the user's chosen ranking design. **Store `φ_f` per listing, not just the total.** |
| DF-4 | **Grounded rationale: the LLM narrates pre-computed evidence, it does not invent the score** | Solve the Hallucination-and-inflation problem structurally. The narrative can explain a ranking but cannot manufacture a high one | **MEDIUM** | JobMatchAI's stated architectural principle: the LLM "receives only the six pre-computed scores and supporting knowledge-graph paths, not raw documents, so the resulting explanations are auditable and traceable". `strata-match` independently converges: score → rationale → strengths → gaps → confidence tier, with a 0-100 bounded score. |
| DF-5 | **Explicit requirement-by-requirement fit breakdown with named gaps** | PROJECT.md requires it; it is also the differentiator the field is moving toward but has not standardised. Teal ships a match score and keyword gaps; almost nothing ships per-requirement evidence mapping | **MEDIUM** | TailorCV's requirements→evidence mapper with match types (direct / transferable / partial / learning potential) is the naming to reuse. `strata-match` returns `strengths[]`, `gaps[]` and a HIGH/MEDIUM/LOW confidence tier alongside the number. |
| DF-6 | **Evidence IDs + provenance labels on every CV bullet** (`verbatim` / `grounded` / `unrecorded`) | Turns "trust our AI" into "check our work". This is the trust feature, and it is what makes the anti-fabrication guarantee inspectable rather than asserted | **MEDIUM-HIGH** | `aarg` ships exactly this: every line "traces to evidence in your dataset" and is "labelled by where it traces: verbatim from a bullet, grounded in your evidence, or unrecorded", with unrecorded lines carrying a claim badge and a confirm-as-evidence button. The independent write-up of the same pattern calls provenance UI "the single biggest trust feature we shipped". |
| DF-7 | **Honest gap flagging instead of padding** | Every unmet requirement becomes a *finding* — an interview-prep item or a cover-letter topic — never a padded bullet. Cheap to build once TS-11 exists and impossible to fake | **MEDIUM** | `resume-honest` scores each bullet `direct match / transferable / adjacent / gap`; the `aarg` design deliberately **never feeds keyword gaps back into the prompt**, "which closes the obvious backdoor where an ATS miss turns into an invented bullet". |
| DF-8 | **Change log / structural diff of what tailoring changed and why** | The user must be able to audit a per-job CV before sending it, and answer "what did the tool do to my CV?" months later | **LOW-MEDIUM** | Falls out of the ID-patch design: the Pydantic patch *is* the change log. TailorCV ships "change logging — documents every modification with justifications"; Resume-Matcher shows tracked changes / diff view. |
| DF-9 | **Application ↔ specific tailored CV version link, with version→outcome data** | Nothing in the field links the *exact artefact sent* to the outcome. That link is what lets the tool get better over time, and it is absent from every prior-art tool surveyed in `STACK.md` | **LOW-MEDIUM** | `cv_artifacts` one row per tailored CV, linked from `applications`. Resume-Matcher and TailorCV produce artefacts; neither closes the loop. Huntr has analytics but no CV-version dimension. |
| DF-10 | **Listing-quality / ghost-job score surfaced *separately* from candidate fit** | Removes the biggest source of wasted effort (~1 in 3 postings) and — importantly — stops the user concluding "I'm not good enough" when the listing was dead | **LOW-MEDIUM** | ShouldApply's "Why Not 100" explicitly separates job-quality issues from skill gaps: "You should not improve your skills to fix a ghost job flag." Signals are all already stored: age, resightings, repost detection, missing salary, page count/description completeness. JobGhosting uses a confidence-scored badge (Fresh/Stale/Suspected Ghost/Ghost/Multiple Openings/Evergreen). |
| DF-11 | **Feedback loop: save/skip/hide influences future ranking** | The tool gets measurably better the longer it is used — the payoff for storing per-factor scores and events | **HIGH** | JobRadar's demo already implements "ignore feedback affecting similar job scores on the next run"; `career-ops` and FitHire both list it as roadmap. **Defer the learning, but capture the events in v1 (TS-16) — backfilling them later is impossible.** |
| DF-12 | **Assisted-apply package: tailored PDF + draft screening answers + apply link, reviewed by the human** | The exact deliverable the user asked for. The legitimate version of prefill — ResuMorph's model: "drafts an answer you can preview, then insert, copy, or cancel" | **MEDIUM** | ResuMorph is the closest architectural precedent for this UX (inline draft → preview → insert/cancel). It is too immature to depend on but its interaction model is right. |
| DF-13 | **Duplicate cluster surfaced as "also seen on…", with canonical-source preference** | Turns dedup from a hygiene task into a user benefit: choose the board with the fewest applicants, and see whether a role is syndicated everywhere | **LOW** | Falls out of TS-3 with merge-not-discard. The documented pattern keeps `sources[]` and all apply URLs and prefers the employer's own ATS posting as canonical, because reposts are frequently stale. |
| DF-14 | **Salary-market context per listing** (e.g. "below the Dublin median for this role") | Adzuna's `/histogram`, `/history` and `/top_companies` analytics endpoints are available on the free tier and, per `STACK.md` Q1, "nobody uses" them. Converts a listing into a negotiation signal | **MEDIUM** | Realistic limitations to design around: Adzuna descriptions are excerpts, `salary_is_predicted` is common, and the free tier is quota-limited, so this must be a cached enrichment, never a per-view call. |
| DF-15 | **Compiled-PDF ATS parse check** | ~75% of resumes are rejected before a human sees them, often for formatting/parsing rather than content. A LaTeX template mostly solves it, but proving it per-artefact is cheap and reassuring | **LOW** | `pypdf` extraction already exists for TS-14; run single-column / standard-headings / date-format assertions on the same pass. Jobscan's 30-check report is the commercial benchmark. |

### Anti-Features (Deliberately NOT Build)

Each entry names the surface appeal, the documented harm, and the alternative already in this plan.

| # | Anti-Feature | Why Requested | Why Problematic | Alternative |
|---|---|---|---|---|
| AF-1 | **Unattended auto-apply / auto-submit** | "Apply while you sleep" is the category's sales pitch | Bans on LinkedIn/Indeed; AIHawk's contributors were banned and the project removed LinkedIn automation entirely. Delivery is unverifiable: independent 2026 reviews report **25–40% silent failure** for Sonara and a Capterra-verified case of **2 of 60** applications actually submitted with LoopCV. LazyApply sits at ~2.4/5 on Trustpilot. Botched screening answers become silent knockouts (wrong salary band, wrong work-authorisation answer) applied at scale | **Assisted apply** — draft + prefill, human presses submit. Already a PROJECT.md Key Decision; this research strengthens it |
| AF-2 | **Auto-filling and auto-submitting screening questions** | It is the tedious part | "The tool doesn't check whether you meet the location requirement or the years-of-experience floor or the licensing rule. It sends the CV and moves on." Errors are invisible and repeated across dozens of applications | Draft answers only; require explicit confirmation for any structured question (salary, authorisation, notice period) |
| AF-3 | **Mass recruiter/hiring-manager cold email** | Looks like "outreach at scale" | LoopCV's documented failure: "they went direct to CEOs and half weren't even open job reqs" — a reputational cost at target companies. Also outside the ethical posture and a GDPR exposure | No outreach automation. If ever needed, a manual, personalised channel — not a feature of this tool |
| AF-4 | **Fabrication "features"** (inflate metrics, inject unheld skills, rewrite titles to match the posting) | Boosts keyword match; some competitors do it implicitly | Practical as well as ethical: unverifiable claims collapse in the first screen; fabricated metrics are the hardest failure to detect post-hoc; ATS platforms now apply density penalties, and employers screen for AI-generated text. The evidence that models do this unprompted is damning — see *Tailoring vs fabrication* | Reorder / re-weight / reframe / flag. The `aarg` and `resume-tailor` line: reframing is allowed, facts are immutable |
| AF-5 | **Optimising for a 100% ATS match score** | Match score is visible and feels like progress | Jobscan itself recommends ~75% and warns: "There is such a thing as an over-optimized resume… it might not be possible to score above 75% without overstuffing your resume with keywords." Workday and Greenhouse penalise Skills lists with no corroborating bullet evidence; recruiters flag resumes that read like the job ad played back | Target honest **60–80% coverage of requirements you can truthfully claim**; surface the rest as gaps (DF-7) |
| AF-6 | **Letting the LLM emit `.tex` or free-prose CV content** | Simplest possible implementation | Unauditable and fabrication-by-construction: no schema, no provenance, no diff, no verification hook | Structured CV + an ID-based reorder/re-weight patch rendered deterministically (`STACK.md` Q6) |
| AF-7 | **Unconstrained LLM scoring over the whole feed, with no rubric or schema** | Least code | Unbounded cost (the filter exists to cap it), unstable scores, no audit trail, and no way to power weight sliders or the fit breakdown. LLM scores are documented as assumption-sensitive: an ACL-adjacent study of LLM hiring evaluations found implicit weights shift between *scoring* and *ranking* framings, so demographic and prestige signals that are negligible in absolute scoring "may be amplified in ranking" | Bounded Pydantic schema, explicit named factors, sub-scores stored, weighted sum computed in code (DF-3/DF-4) |
| AF-8 | **A vector database / embedding-based ranking as the v1 ranking signal** | "Semantic search" is expected in 2026 | It was measured and did not hold up: `redrob-hirefit-ranker` shipped its semantic path **disabled by default** because "bigger models and semantic rerankers did not generalize on our blind arbiter" (static embeddings NDCG@10 gain **+0.0000** at 2.2× runtime). It also adds a native extension and an embedding model to a SQLite/FTS5 Docker build | FTS5 + BM25 for retrieval. Embeddings are legitimate **only** as a cheap pre-filter gate — `strata-match` uses vector cosine to skip 70–80% of listings before spending on the LLM at ~1/100th the cost per comparison |
| AF-9 | **A browser extension that drives LinkedIn/Indeed/ATS pages** | It is the only way to reach login-gated boards | Requires the user's live session and IP, which is precisely the surface flagged for automation; LoopCV's extension is the documented failure mode (silently times out when the Easy Apply button moves) and LazyApply's approach carries the LinkedIn risk. It is also a second runtime (MV3) in a Python/Docker project | Generate the application package (DF-12); the human pastes and clicks. A Simplify-style autofill extension is the *legitimate* form of this and is a plausible later milestone, not a v1 build |
| AF-10 | **General-purpose PDF/DOCX resume parsing as the primary ingestion path** | Resume-Matcher accepts PDF/DOCX, so it looks like table stakes | It is a large, low-quality-yield subsystem (scanned PDFs, columns, tables), and this project's CV source of truth is already structured text. Building it would be a detour that produces worse data than the user already has | One-time `.tex` → `cv.yaml` import plus manual curation. Accept the one-off curation cost; it is paid back by every differentiator above |
| AF-11 | **Full job-search CRM** (contact management, email integration, interview scheduling, LinkedIn inbox monitoring, analytics dashboards) | Huntr ships it; it looks like retention | Each surface is a real product. `linkedin-assistant` shows the shape (inbox reading, contact-adjacent automation) and also its cost. For a local tool built for one person plus friends, a CRM is scope that delays the Core Value | Notes + stages + follow-up date only (TS-7/TS-8). Add CRM depth in v2 only if a search genuinely runs long enough to need it |
| AF-12 | **Multi-user accounts, teams, sharing, auth in v1** | "A few friends will use it" | PROJECT.md explicitly defers it, and multi-tenancy changes the data model (per-user CVs, per-user criteria, per-user keys) in ways that are expensive to retrofit if assumed in v1 | `Depends(current_user)` seam returning a fixed local user on every route (`STACK.md` Q8); Authentik OIDC later with no signature changes |
| AF-13 | **A mobile app** | Simplify and Huntr have one | Bespoke iOS/Android clients for a self-hosted tool used by a handful of people. The web UI is already the product surface | Responsive HTMX UI in v1; ntfy push notification later if the daily habit needs it |
| AF-14 | **A bulk "apply to all selected" action** | Obvious convenience | Structurally pushes toward the low-quality mass application the project exists to avoid, and is the exact behavioural signature velocity-based detection looks for | Per-listing application package. No bulk submit, ever |
| AF-15 | **Real-time everything / live streaming job feeds** | Feels modern | No user benefit at a once-daily cadence; adds WebSocket/SSE complexity to a batch pipeline. The one legitimate real-time surface is *pipeline progress during a run* (opencode's SSE stream, `STACK.md` Q7) | Batch runs + SSE progress for the run in flight |

---

## Feature Dependencies

```
TS-1 source adapters ──requires──> TS-2 persistence ──requires──> TS-3 dedup
                                         │
                                         └──feeds──> TS-5 hard-rule filter ──requires──> DF-3 ranked scoring
                                                                                        │
TS-4 search criteria ──drives──> TS-5                                                  │
                                                                                        ▼
TS-11 structured CV (cv.yaml + IDs) ──requires──> DF-3 fit factors ──requires──> DF-4 rationale
        │                                              │
        │                                              ├──feeds──> DF-5 fit breakdown + gaps
        │                                              ├──feeds──> DF-9 version→outcome link
        │                                              └──feeds──> DF-11 feedback loop
        │
        └──requires──> TS-12 tailored CV render ──requires──> TS-14 verification
                                 │                                  │
                                 └──requires──> TS-13 review/edit ──┘
                                 │
                                 └──feeds──> DF-12 application package

TS-3 dedup ──enhances──> DF-13 "also seen on" + canonical source
TS-2 timestamps ──requires──> TS-17 stale signal ──enhances──> DF-10 ghost/quality score
TS-16 save/skip events ──requires──> DF-11 feedback loop (events are the input, learning is the build)
TS-15 new-since badge ──requires──> TS-2 timestamps
TS-9 run log ──enhances──> TS-5 diagnostic ("excluded by rule X")

DF-3 ──conflicts──> AF-7 (unconstrained LLM scoring): only one can be true
TS-14 ──conflicts──> AF-4 (any fabrication feature): structurally incompatible
AF-9 browser extension ──conflicts──> AF-1 assisted-apply posture
```

### Dependency notes

- **TS-2 before everything.** `first_seen_at`, `last_seen_at` and `content_hash` are a single migration that unlocks TS-15 (new badge), TS-17 (stale), DF-10 (ghost score) and DF-9 (outcome history). Add the columns on day one even if nothing reads them yet.
- **TS-11 (structured CV) gates all of Cluster C.** Without stable IDs there is no provenance (DF-6), no diff (DF-8), no verifiable anti-fabrication (TS-14) and no honest gap flagging (DF-7). This is why `STACK.md` Q6 calls it the most important design decision in the LaTeX layer.
- **DF-3 requires that you persist *per-factor* sub-scores, not one number.** If ranking writes only `score = 78`, then the weight sliders (PROJECT.md requirement), the fit breakdown, and re-ranking all require a fresh LLM call. Persist `phi_f` per factor plus the evidence spans; compute the weighted sum in code. This is the cheapest mistake to avoid and the most expensive to retrofit.
- **DF-11 (feedback loop) requires TS-16 events to exist first, and can be built long after.** Capture `saved / hidden / shortlisted / applied` events with timestamps from the first migration. The learning layer is a v2 feature; the *data* is a v1 obligation.
- **DF-12 depends on TS-12 and TS-14, not the reverse.** The application package must be built from an already-verified artefact, or the verification is theatre.
- **DF-10 is nearly free *given* TS-2 + TS-3, and expensive otherwise.** Repost detection needs dedup clusters plus `content_hash`; age needs `first_seen_at`. Do not schedule it before both.
- **DF-14 (salary context) has an external dependency**: Adzuna free-tier quota (~1,000 calls/month). It must be a cached, batched enrichment with its own quota ledger, never a per-view live call.
- **TS-18 (cover letter) must reuse TS-11's evidence IDs.** If it is built with its own prompt and its own fact extraction, DF-6 and TS-14 do not cover it and the honesty guarantee has a hole.

---

## MVP Definition

### Launch With (v1)

Aligned to PROJECT.md's Active requirements, plus the research-informed additions that are genuinely load-bearing. If a v1 item is missing, the Core Value ("one ranked, explained, apply-ready queue") does not hold.

- **TS-1, TS-2, TS-3** — adapters, persistence, dedup. Without these the queue is noise.
- **TS-4, TS-5** — editable criteria + deterministic filter. The cost gate and the first explainability layer.
- **TS-9** — run log and per-listing exclusion reason. Non-negotiable: it is the field's worst failure mode and it is cheap.
- **TS-11, TS-12, TS-13, TS-14** — structured CV, tailored PDF, review-before-compile, and the honesty assertion. This is the ethical hard line, so it ships with the feature rather than after it.
- **DF-3, DF-4, DF-5** — per-factor scoring, grounded rationale, fit breakdown with gaps. The Core Value.
- **TS-7, TS-8** — tracker with stages and notes.
- **TS-6, TS-15, TS-16, TS-17** — queryable queue, new-since badge, save/hide, stale badge. The daily-use ergonomics.
- **TS-10** — manual + scheduled runs.
- **DF-12** — assisted-apply package.
- **Environment**: Docker, no auth, opencode backend, `Depends(current_user)` seam on every route.

### Add After Validation (v1.x)

Trigger in each case is the signal that the core loop is working.

- **DF-6, DF-7, DF-8** (provenance UI, gap checklist, change log) — add when the first real tailoring run happens and the user wants to inspect it. The **data model** for all three must exist in v1 (DF-8 falls out of the patch; DF-6/DF-7 need the IDs), only the UI is deferred. *Trigger: first application sent from a tailored artefact.*
- **DF-10** (ghost/quality score as a first-class signal) — the stored fields already support it. *Trigger: first time the user applies to a posting that was already dead.*
- **TS-18** (cover letter, grounded) — *Trigger: first application that requires one.*
- **DF-13** ("also seen on" + canonical source) — *Trigger: first observed cross-board duplicate.*
- **TS-19** (export) — *Trigger: first backup or debugging session.*
- **External push notification** (ntfy, optionally Apprise as a fan-out router) — PROJECT.md excludes email digests in v1 and TS-15 covers the in-app need. ntfy is the 2026 default for self-hosted push and has an iOS/APNs path; Apprise is the fan-out layer if the destination list grows. *Trigger: the daily queue stops being checked daily.*
- **DF-15** (ATS parse check beyond text extraction) — *Trigger: an application that appears to have been screened out for formatting.*
- **DF-11** (feedback loop) — *Trigger: 100+ save/skip events accumulated.*
- **DF-14** (salary market context) — *Trigger: a live negotiation or an offer conversation.*

### Future Consideration (v2+)

- **Authentik OIDC + multi-user** — explicitly deferred; the `Depends(current_user)` seam keeps it cheap.
- **MCP server exposing the tool to opencode conversationally** — deferred by the user; would make the tool queryable in conversation ("show me my top 5 for this week").
- **Simpler-state embedding pre-filter** — only as a cost gate, only if LLM ranking cost becomes material (see AF-8).
- **Hosted deployment / public exposure** — the Postgres + `pg_advisory_lock` path in `STACK.md`.
- **CRM depth, interview prep, story bank, analytics dashboards** — Cluster D features; each is a real product and none is on the critical path.
- **Typst migration** — the structured-CV design makes it a renderer swap if LaTeX compilation proves painful.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---|---|---|---|
| TS-2 persistence + timestamps | HIGH | LOW-MEDIUM | **P1** |
| TS-3 dedup with audit trail | HIGH | MEDIUM-HIGH | **P1** |
| TS-5 hard-rule filter + exclusion reason | HIGH | LOW-MEDIUM | **P1** |
| TS-11 structured CV fact store | HIGH | MEDIUM | **P1** |
| DF-3 per-factor scoring + weights in code | HIGH | MEDIUM-HIGH | **P1** |
| DF-4 grounded rationale | HIGH | MEDIUM | **P1** |
| DF-5 fit breakdown + gaps | HIGH | MEDIUM | **P1** |
| TS-14 honesty verification | HIGH (existential to the design) | MEDIUM | **P1** |
| TS-9 run log / observability | HIGH | LOW-MEDIUM | **P1** |
| TS-7 + TS-8 tracker + notes | HIGH | LOW | **P1** |
| TS-12 + TS-13 tailored PDF + review/edit | HIGH | MEDIUM-HIGH | **P1** |
| DF-12 assisted-apply package | HIGH | MEDIUM | **P1** |
| TS-6 FTS5 queue search | MEDIUM | LOW | **P1** |
| TS-15 new-since badge | MEDIUM | LOW | **P1** |
| TS-16 save/hide (event capture) | MEDIUM | LOW | **P1** |
| TS-17 stale badge | MEDIUM | LOW | **P1** |
| TS-10 manual + scheduled runs | HIGH | LOW-MEDIUM | **P1** |
| TS-1 adapter interface | HIGH | MEDIUM | **P1** (interface) / **P2** (Adzuna adapter #3) |
| TS-4 criteria CRUD UI | HIGH | LOW-MEDIUM | **P1** |
| DF-8 change log / diff | HIGH | LOW-MEDIUM | **P2** |
| DF-6 provenance labels in UI | HIGH | MEDIUM-HIGH | **P2** |
| DF-7 gap checklist UI | MEDIUM-HIGH | MEDIUM | **P2** |
| DF-10 ghost/quality score | MEDIUM-HIGH | LOW-MEDIUM | **P2** |
| TS-18 grounded cover letter | MEDIUM-HIGH | MEDIUM | **P2** |
| DF-13 "also seen on" | MEDIUM | LOW | **P2** |
| TS-19 export | MEDIUM | LOW | **P2** |
| ntfy push notification | MEDIUM | LOW | **P2** |
| DF-15 ATS parse check | MEDIUM | LOW | **P2** |
| DF-14 salary market context | MEDIUM | MEDIUM | **P3** |
| DF-11 feedback loop | MEDIUM-HIGH | HIGH | **P3** (data capture is **P1**) |
| DF-1 LaTeX pipeline (as a distinct deliverable) | HIGH | HIGH | **P1** — but sequence it *after* TS-11 and validate Tectonic on the real `.tex` first |
| Auth / multi-user / MCP / CRM / embedding pre-filter | LOW-MEDIUM | HIGH | **P3** |

**Priority key:** P1 = must have for launch · P2 = should have, add when the core loop is validated · P3 = future consideration.

**The one sequencing warning:** DF-1 (the full LaTeX pipeline) is the highest-complexity item and it sits under four other P1s. `STACK.md` Q6 already flags a spike on the user's actual `.tex` (package availability in Tectonic's bundle, pdfTeX-only primitives, bib/biber) as a gate. Run that spike **before** the tailoring phase is planned, or the phase inherits an unknown.

---

## Competitor Feature Analysis

| Feature | Resume-Matcher (28k★) | Teal / Huntr (Cluster D) | AIHawk / LoopCV (Cluster B) | TailorCV / `aarg` (Cluster C) | **This project** |
|---|---|---|---|---|---|
| Aggregation | None — paste a JD | None — bring your own jobs (Chrome clipper) | Scrapes boards, auto-applies | None | **JobSpy + Adzuna behind a pluggable adapter interface** |
| Dedup across portals | N/A | Not a differentiator; manual | **Yes, by URL only** (AIHawk: "prevents duplicate applications via URL uniqueness") | N/A | **Two-tier, reversible, merge-not-discard (TS-3)** |
| Deterministic pre-filter | None — straight to LLM | Keyword filters, not cost-gating | Keyword/`work_preferences.yaml` filters | N/A | **Filter before LLM spend (DF-2)** — absent from the field |
| Ranking | Single match score vs JD | Match score (Teal) / basic (Huntr) | LLM 1–10 fit score with rationale (AIHawk PR branch) | Match scoring per requirement | **Per-factor sub-scores + code-computed weighted sum + sliders (DF-3)** |
| Explainability | Score + keyword highlight | Keyword gap list | Rationale text | Requirement→evidence mapping | **Grounded rationale over pre-computed evidence + named gaps (DF-4/DF-5)** |
| CV source format | PDF/DOCX → HTML/Chromium PDF | Builder-owned documents | YAML resume → generated docs | DOCX / Typst (`aarg`) | **LaTeX in, LaTeX out (DF-1)** — nobody else |
| Anti-fabrication | Not a stated concern | Not a stated concern | Not a stated concern | **Yes — the strongest prior art**: TailorCV blocks unevidenced claims + flags borderline + logs changes; `aarg` uses evidence IDs with verbatim/grounded/unrecorded labels | **Encoded in types + verified at compile (TS-14, DF-6)** |
| Application tracking | None | **Strong** — kanban/table, notes, contacts, follow-ups | Basic history + status | None | **Stages + notes + version↔outcome link (TS-7, DF-9)** |
| CV version ↔ application link | None | None | None | None | **Yes (DF-9)** — absent from the field |
| Assist level | Manual apply | Simplify: autofill, human submits; Huntr/Teal: manual | **Fully unattended submit** | Manual | **Assisted: package + human submits (DF-12)** |
| Delivery to the user | Web app | Web + Chrome extension + mobile | Browser extension/cloud | CLI / Claude skill | Local Docker web UI + in-app delta (+ ntfy later) |
| Cost model | Self-host, BYO LLM key | Freemium, $13–49/mo | $99–999/yr or ~$24–40/mo | Self-host, BYO key | **Self-host, opencode backend, no second key** |

---

## Deep dives on the seven research questions

### 1. What prior art actually ships, and what users complain is missing

**Cluster A (aggregators) ships discovery and nothing downstream.** JobSpy returns a DataFrame and stops; every consumer then builds persistence, dedup and a UI themselves. The open-source consumers surveyed (`career-ops`, `linkedin-assistant`, Faculty Atlas, JobRadar) converge on the same short feature list: multi-source fetch, dedup, score-against-profile, a simple pipeline, and a "new since last visit" marker. They also overwhelmingly converge on a **read-only, draft-only** posture — `linkedin-assistant` is explicit: it "never sends anything — the final click is always yours". That is independent corroboration that assisted apply is the mainstream safe design, not a compromise this project is settling for.

**Cluster B (auto-appliers) ships the features this project rejects, and its users' complaints are the most valuable data in the whole survey.** The recurring, cross-platform complaint is not "it applied to the wrong job" — it is **silent failure**:

> DATA_q4Xn7tKm_START
> "My experience with Loop CV has been nothing but terrible. While the service is great at matching you with jobs, it does nothing to actually APPLY to them… I spent a month and a half on the service and got matched with over 1800+ jobs. However, the service applied to 0 of them."
> DATA_q4Xn7tKm_END

The same review corpus documents a Capterra-verified case of 2 of 60 applications actually submitted, a 25–40% silent-failure rate for Sonara, and a support pattern where the dashboard shows "Applied" with no delivery confirmation. Three secondary complaints follow directly from that: **wrong-target applications** (roles filtered out, wrong seniority, closed requisitions), **screening answers filled incorrectly at scale**, and **refund friction**. AIHawk's own history — contributors banned, LinkedIn automation removed from the project — is the strongest single argument for the assisted posture.

**Cluster D (trackers) ships the pipeline well and the fit poorly.** Teal owns resume-to-JD match scoring, kanban/table tracking and **follow-up reminders**; Huntr owns the visual board, contacts, email integration, interview tracking and analytics; Simplify owns broad autofill and automatic logging. Their shared weakness is that tracking is not connected to the artefact: none links the *specific tailored CV version* to the outcome.

**What users report missing across all clusters** — the gaps this project can occupy:
1. A single pipeline from aggregation to a ready application (each cluster does one slice).
2. Any link between the CV version sent and the result.
3. Confidence in whether an application was actually delivered / a listing was actually live.
4. Filtering that is explainable and cheap rather than "the matching algorithm feels like it optimizes for job title keywords rather than actual fit".
5. Honest tailoring — the complaint is always that AI output is either **keyword-stuffed** or **obviously AI-generated**, and both are visible to the reader.

### 2. Filtered + LLM-ranked job feeds, and how users tune ranking

**The published state of the art is a two-or-three stage funnel with a cheap gate.** Two independent implementations converge without coordination:

- `strata-match`: **vector cosine gate → LLM nuance scoring**. The gate "filters out 70–80% of listings at near-zero cost" (~$0.0001/comparison vs ~$0.01 for the LLM pass, ~100ms vs 2–5s). Output is `score (0-100)`, `rationale`, `strengths[]`, `gaps[]`, `confidence_tier` HIGH/MEDIUM/LOW, and tokens are tracked per result for cost visibility.
- This project: **deterministic hard-rule filter → LLM scoring**. Same shape, cheaper gate, more explainable, no embedding dependency. The `strata-match` cost ratio is the strongest available evidence that *any* cheap gate is worth building, and the hard-rule filter is the cheapest one that exists.

> DATA_j6Bd2sYc_START
> "A distinguishing design property is the strict separation of scoring from explanation. … The six factor scores and their contributing knowledge-graph paths are then passed to an LLM, which synthesizes a cohesive narrative … Because the LLM receives pre-computed scores and graph evidence rather than raw documents, it can explain a ranking but cannot hallucinate a high one."
> DATA_j6Bd2sYc_END

JobMatchAI's default weight table is a directly liftable starting rubric, and — critically — **its weights are user-adjustable sliders whose recomputation is free because the factor scores are already stored**. Its user study found "AI match explanations" and "adjustable ranking weights" were rated the **most valuable** features, with participants citing "appreciation for transparency in scoring".

**How users tune ranking — the options, ranked by evidence:**
1. **Weight sliders over named factors, recomputed in code** (highest value, lowest cost once DF-3 exists). Instant, no LLM spend, and the user learns what the tool is optimising for.
2. **Edit the natural-language criteria/preferences** that feed the ranking prompt. Needed anyway; affects the next run only.
3. **Exclude/include terms** — a hard-rule adjustment, not a ranking adjustment. Users reach for this constantly; it must be one click from a listing ("hide jobs like this").
4. **Save/skip/hide feedback** — high value, high build cost (DF-11). JobRadar implements it in demo form; everyone else roadmaps it.
5. **Per-listing confidence tiers** rather than a bare number — users need to know when the tool is unsure, and `strata-match`'s HIGH/MEDIUM/LOW banding is a cheap way to communicate it.

**Two honest cautions.** First, LLM scores are **assumption-sensitive** and unstable across framings: a controlled study of LLM hiring evaluation found the model's implicit attribute weights shift substantially between *absolute scoring* and *relative ranking*, so factors that look negligible in isolation can be amplified in a ranking context. Practical consequence: keep the ranking task a **bounded absolute score per listing against an explicit rubric**, not a relative "rank these 40 jobs" task, and store the sub-scores so instability is diagnosable. Second, explanation faithfulness is not automatic — the JobMatchAI audit found the top contributing factor was mentioned in only ~70% of generated explanations, and notably worse for medium/low matches (~58–59%) than for high matches (~94%). Mitigation: render the factor table in the UI as structured data and treat the LLM prose as a supplement, not the explanation.

### 3. Application tracking / pipeline features

**Stages converged across the field.** Teal, Huntr, TrackJobs and `career-ops` all land on a close variant of: `Saved → Applied → Interviewing → Offer → Closed`, with TrackJobs shipping 8 stages and Huntr shipping a drag-and-drop board. For this project, `queued / shortlisted / applied / interviewing / offer / rejected / withdrawn` is the right set — it is the field convention plus the two terminal states `career-ops` and Teal both include.

**What separates a good tracker from a bad one is not the board — it is what is attached to each card.** Huntr's advantage is contacts, notes, documents, interview logs and email; Teal's is resume versions, keyword gaps and **follow-up reminders**. The features worth having:

- **Status + notes + `applied_at`** — the floor (TS-7/TS-8).
- **Follow-up / deadline nudge** — Teal ships it and it is the single feature that turns a tracker into a daily-use tool. Implement as a computed `next_action_at` on the application (default `applied_at + 7 days`) with an in-app overdue list, surfaced via TS-15 rather than an external notification, per the v1 scope decision.
- **Version ↔ application link** (DF-9) — the differentiator. Store `application.cv_artifact_id` so the exact PDF sent is retrievable, and so response-rate-by-tailoring-strategy becomes answerable later.
- **Separation of *job quality* from *candidate fit*** (DF-10) — ShouldApply's framing is the correct one and worth copying: a low score should tell the user whether the problem is them or the posting. "You should not improve your skills to fix a ghost job flag."
- **Analytics** (response rate, interview conversion, time-to-response) — Huntr's differentiator, but it only becomes meaningful after dozens of applications. Defer (v2+); the data is captured from v1 so nothing is lost.

### 4. CV tailoring and where the "tailoring vs fabrication" line sits

This is the best-evidenced area of the whole survey, and the field has already drawn the line. **Healthy tailoring = reorder, re-weight, reframe, surface, flag. Fabrication = invent, inflate, substitute, or silently drop.**

The evidence that prompt-level instructions are insufficient is now strong and should shape the implementation:

- A controlled multi-stage hiring-pipeline experiment (10 resumes × 2 JDs × 3 repetitions × 3 conditions = 180 runs) found a fully automated baseline produced at least one unsupported claim in **96.7%** of outputs (mean 6.80 findings/output). Adding prompt guardrails cut finding density by **86%** — but **50% of outputs still contained a fabrication**. Adding a human checkpoint eliminated all *identity* fabrications and cut JD-baited claims from 47% to 2%. The authors' conclusion: the two mitigations are complementary and neither alone is sufficient.
- A five-layer "grounded optimisation" framework for resume rewriting names four distinct failure modes — temporal fabrication (injecting technology that did not exist during the claimed dates), **cross-domain contamination (79–89% of baseline incidents: an AWS-only role rewritten with Azure services)**, structural mutation (silently condensing 8 bullets into 4, *removing* truth rather than adding falsehood), and content fabrication — and enforces them with temporal constraints, a deterministic 257-service regex taxonomy, structural invariants (never fewer roles or bullets), prompt immutability rules, and a separate evaluator agent.
- The implementation-level consensus is the **fact-store + citation + verifier** pattern: make source material addressable with IDs, force the generator to cite the ID it used, verify entailment with a *separate, incentive-free* pass that does not know the job description, and **drop rather than repair** on failure — because "repair pressure is fabrication pressure".

**The practical rule set this project should encode** (all of it enforceable in code given TS-11):

| Allowed | Forbidden |
|---|---|
| Reorder sections and bullets by relevance | Add an employer, role, date or qualification |
| Re-weight / re-order the skills list to surface genuine strengths | Add a skill or tool not evidenced in the source CV |
| Reframe an existing bullet in the JD's vocabulary | Introduce a metric or number absent from the source |
| Drop or demote genuinely irrelevant content (with a log entry) | Rewrite a job title to match the posting |
| Surface adjacency ("transferable", "partial") | Present adjacency as a direct match |
| Flag a requirement as a gap and route it to an interview-prep / cover-letter note | Convert a gap into a bullet |

Two mechanisms are worth copying almost verbatim: TailorCV's **three strictness levels** (Conservative / Moderate / Aggressive) that explicitly control whether *inferred* skills and keyword injection are allowed at all, and its **borderline-flagging** step that quarantines anything uncertain for human review rather than auto-merging. And `resume-honest`'s per-bullet confidence labels (`direct / transferable / adjacent / gap`) are a better user-facing vocabulary than a raw match percentage.

**Also worth recording as a positive finding:** the same research that shows fabrication is rampant also shows the fix does not cost quality — claim retention exceeded 99% under both guardrail and checkpoint conditions. Honesty is not a trade-off against usefulness.

### 5. Search-criteria management, saved searches, and deduplication

**Criteria management.** Every tool stores one or more criteria sets; the patterns to take are (a) criteria edits must take effect on the *next run*, not retroactively rewrite the queue, and (b) the criteria must be inspectable next to the result ("this passed because it matched X; it was not excluded by Y"). Indeed's own search surface shows the filter vocabulary users expect — keyword, location + radius, date posted (`fromage`: last / 1 / 3 / 7 / 14 days), salary, job type, experience level, remote/hybrid, company, education, sort order (relevance | date) — and that vocabulary is a reasonable superset for TS-4, minus company and education which are better expressed as include/exclude terms.

**Saved searches / named criteria.** Adligator's "Tracker" model is the clearest articulation of why this matters: a saved search is what "separates 'I check this sometimes' from 'this is in my Monday routine'", and its value is that it surfaces **only what is new since your last check**. For a 1–5 person tool the right shape is a small number of named criteria sets, each run by the scheduler, each with its own `last_run_at` — because a single global `last_run` breaks the "new since" computation as soon as there is more than one search.

**Deduplication is a genuinely hard matching problem and the field is unusually candid about it.** The key findings:

- **Exact matching on title+company+location barely works** — all three drift between reposts ("Macy's" / "Macys Inc" / "Macy's LLC"; "SF" / "San Francisco, CA"; "Software Engineer II" / "SDE II").
- **The strongest single signal is a canonicalised application URL** (strip `utm_*`/`gh_src`/`lever-source`, normalise trailing slashes and casing, resolve redirects). It handles LinkedIn→Workday syndication trivially because LinkedIn's apply button deep-links to the ATS. **But** most true cross-source duplicates have *different* URLs, so it cannot be the primary key.
- **The hierarchy that works in production:** (1) canonical apply URL; (2) normalised company + fuzzy title + geocoded location + posted-week window; (3) description shingling / MinHash or content hash; (4) conservative manual rules for companies that legitimately post many near-identical reqs.
- **Hash-only matching fails at scale.** One aggregator processing ~10B observations found hash-based matching systematically misses company/title/location drift and moved to multi-signal entity resolution with a company name deliberately *excluded* from the primary dedup key — "including company name in the hash would increase precision but dramatically reduce recall." **Recall matters more than precision here**, because a surviving duplicate is noise while a false merge *loses a real job*.
- **Merge, don't discard**, and require all key components rather than a bare fuzzy title match (short strings are similar by accident: "Accountant" vs "Shop Accountant" vs "Senior Accountant"). Union the fields across duplicates — one board has the salary, another the accurate date, a third the full description — and keep `sources[]` plus all apply URLs.
- **Watch the merge rate** as the health metric: a cross-board merge rate around 10–15% per keyword looks right, and an implausible ratio (200 → 12) means the key is too loose. The accompanying advice is excellent: "Print the rows behind any aggregate before you trust it. Every deduplication bug I've shipped looked perfectly reasonable as a percentage and obviously wrong as a list of titles."
- **Order matters: fetch fully → normalise → merge → then filter and cap.** Filtering or capping before merging throws away the copy that had the salary field.
- **Choose a canonical source deliberately:** prefer the employer's own ATS posting (source of truth, least stale), then most-recently-updated, then most complete. And treat a live recruiter repost with a dead original as a signal the role **closed**, not as a live listing.
- Tier-1 in-source dedup is worth separating from cross-source dedup: ~90% of raw observations in a real pipeline are re-observations of something already held, which is exactly what `UNIQUE(source, source_listing_id)` plus `last_seen_at` handles for free.

### 6. Notification and alerting

**The honest finding: for a category whose value proposition is a daily queue, some delivery signal is table stakes — but the *channel* is flexible, and the user's v1 exclusion of email digests is compatible with the need.** Cluster D pushes email alerts; job boards push saved-search alerts; Adligator's tracker model explicitly treats "only what is new since your last check" as the reason to return daily. The requirement underneath is *a reliable delta*, not *an email*.

**What to do in v1:** TS-15, the in-app "new since your last visit" badge, plus TS-9's run log so a failed or empty run is visibly a failed or empty run rather than an empty queue. This satisfies the delta need with zero external dependencies and honours the PROJECT.md scope decision.

**What to do when it is not enough:** self-hosted push is the right v2 shape, and the 2026 ecosystem has a settled architecture. **ntfy** is the delivery server — a single Go binary (~15 MB image, 30–50 MB RAM), a dead-simple API (`curl -d "msg" server/topic`), topic-scoped tokens, message persistence for offline devices, and — uniquely among the self-hosted options — a maintained iOS app on APNs, which gives 1–3 second cold-start delivery. **Apprise** is the fan-out router (130+ destinations, per-tag routing, a Python library and an `apprise-api` container) and is worth adding only when there is more than one destination. The dominant homelab pattern is ntfy for delivery with Apprise in front of it. **The one architectural mistake to avoid**, stated bluntly in the survey: never let the pipeline post raw events straight to the notification channel — "Always have a deduper", or repetitive alerts get muted and the real one is missed. For this project that means the notifier should send **one batched digest per run** (N new, top M high-scoring) and never per-listing pushes.

**What is *not* table stakes:** SMS, phone calls, escalation tiers, per-listing real-time pushes. Those belong to monitoring, not job search.

### 7. Complexity and dependency notes for roadmap ordering

Ordering rules that follow from the evidence above:

1. **Foundations before features.** TS-2 (timestamps/hash) and TS-11 (structured CV) are prerequisites for eight other items between them. They are two migrations and one import script, and building them late forces backfills that cannot be reconstructed.
2. **Ingest → dedup → filter gate → rank → queue** is the critical path and matches PROJECT.md's Core Value. Nothing else should be planned ahead of it.
3. **The filter is the cost control, so it must exist before the first real LLM run** — not because of elegance but because the ranking phase's timeout/cost design depends on the candidate count being bounded.
4. **Persist per-factor scores and events (saves/hides/shortlists) in the ranking-phase schema.** Two cheap decisions that unlock weight sliders, the fit breakdown, honest re-ranking and the future learning loop. Retrofitting them later is expensive; DF-11 in particular becomes impossible without historical events.
5. **Verification ships *with* tailoring, not after.** TS-14 is what makes the ethical constraint a property of the system rather than a claim in a prompt; the research above shows that shipping tailoring first and verification later means shipping a fabrication window.
6. **Validate the LaTeX pipeline on the real `.tex` before planning the tailoring phase** (`STACK.md` Q6 spike). Tectonic bundle coverage, pdfTeX-only primitives and any bibliography/biber usage are unknowns that can re-scope the phase.
7. **The ranking phase needs an explicit cost/time budget and a batching decision.** `STACK.md` Open Question 7 is unresolved: per-listing LLM calls (N calls, higher cost/latency) versus batched (1 call per K listings). The choice changes the timeout design and whether `prompt_async` + SSE progress is required. Resolve it in the ranking phase's plan, not its execution.
8. **Dedup tuning needs real data.** The thresholds (~90 fuzzy, merge-rate sanity band) can only be tuned against the user's actual result set. Plan a tuning task with the corpus in hand rather than freezing thresholds in the schema.
9. **Two features have external-quota or external-breakage risk and should never be on the critical path:** Adzuna (free-tier quota, DF-14, and the primary hedge if scraping degrades) and the scraper adapters themselves. Both need failure-tolerant adapters and visible status (TS-9).
10. **Deferred-but-architected:** cover letter (TS-18), provenance UI (DF-6/DF-7), feedback learning (DF-11), auth/multi-user. Each is cheap later *only* if v1 leaves the seam — evidence IDs, stored sub-scores, stored events, `Depends(current_user)`.

---

## Confidence assessment

| Area | Confidence | Notes |
|---|---|---|
| Prior-art feature inventories | **HIGH** | READMEs, product docs and changelogs read directly; GitHub repo presence confirmed. Feature lists are stated by the projects themselves. |
| User complaints / missing features | **MEDIUM** | Drawn from review aggregators (Trustpilot, Capterra, Product Hunt, Reddit citations) and vendor-authored comparison pages. The *pattern* is consistent across independent sources, which is why it is credible; individual figures are treated as directional. Several comparison sites sell competing products — flagged where used. |
| Ranking design & tunability | **MEDIUM-HIGH** | JobMatchAI is a peer-reviewed demo paper with an explicit weight table and a user study; `strata-match` is an independent production implementation with the same two-stage shape and a published cost ratio. The caution on LLM weight instability comes from a controlled factorial study. |
| Deduplication | **MEDIUM-HIGH** | Multiple independent production write-ups converge on the same hierarchy (canonical URL → normalised composite → shingling → manual rules) and the same warn-don't-over-merge posture. The one genuinely peer-reviewed source (MDPI, 50k postings) adds embedding-filter + LLM-validation as a fourth tier and reports ~40% true duplicate proportion. **LOW confidence on the specific thresholds** for this project's scale — untunable without data. |
| Anti-fabrication design | **MEDIUM-HIGH** | Three independent open-source implementations (TailorCV, `aarg`, `resume-honest`) plus two academic evaluations (the 180-run guardrail-vs-checkpoint study; the five-layer grounded-optimisation framework) converge on the same conclusion — prompt-level controls are insufficient, structural + verification controls are required. This is the most strongly corroborated finding in the file. |
| Application tracking / pipeline | **MEDIUM-HIGH** | Stage sets converge across Teal, Huntr, TrackJobs and `career-ops`; feature claims come from those vendors' own documentation. |
| Notification/alerting | **MEDIUM-HIGH** | ntfy/Apprise characteristics and the dominant deployment pattern are corroborated by three independent 2026 self-hosting write-ups; the "always have a deduper" caution is consistent across them. |
| Ghost/stale-job signal | **MEDIUM** | The phenomenon is well documented, but most quantitative sources sell a competing product or a service (CRS and Forbes both flag this). Figures (18–22% of postings, 40% of hiring managers, ~1 in 3 stale) are directional, not precise. The *feature* is justified regardless. |

## Gaps and open questions

Carry these into roadmap research — each is a place where this file deliberately stopped short.

1. **Ranking batching is unresolved** (`STACK.md` Open Question 7, restated here because it is a *feature* decision, not only a stack one): one LLM call per listing with `prompt_async` + SSE progress, or one call per K listings with deterministic fan-out. Per-listing gives better per-listing rationale and parallelism; batching cuts cost and enables cross-listing consistency. It changes the ranking phase's plan materially.
2. **No first-hand user research.** Every "users complain" claim here is mediated by review sites and vendor pages. A short validation pass with the actual user (and the friends) on the MVP feature list would raise the confidence on TS-15/TS-16/TS-18 relative priority considerably.
3. **Dedup thresholds and the merge-rate sanity band are untunable in advance.** Plan a tuning task once the first real corpus exists.
4. **Tectonic viability on the user's actual `.tex`** is unknown (`STACK.md` Open Question 6) and gates DF-1. Also unverified: whether the existing CV has a bibliography (which triggers the pinned-biber caveat).
5. **Does the user's `.tex` decompose cleanly into `cv.yaml` with stable IDs?** If the document is heavily macro-driven, the one-time import is more work than assumed. This is the largest unquantified cost in the plan and should be measured by doing it, on one section, before the tailoring phase is estimated.
6. **Cross-portal duplicate rate at personal scale is unknown.** The 10–15% merge-rate sanity band comes from a different market and query shape. Measuring the actual rate on the first few runs would validate or move the threshold.
7. **Feedback-loop feasibility is genuinely uncertain.** No surveyed tool has shipped save/skip-driven ranking learning at this scale (JobRadar implements it only in a demo; FitHire and `career-ops` list it as roadmap). Treat DF-11 as an experiment, not a commitment — but still capture the events.
8. **Whether ATS-form prefill is worth attempting at all.** ResuMorph's inline-draft UX is the closest precedent and it is pre-release. If browser-side prefill is ever revisited, it needs its own feasibility pass (extension runtime, ATS field mapping failures, permission scope) — it is explicitly not a v1 assumption.

## Sources

**Open-source prior art (primary — project READMEs, docs and PRs, read 2026-09-15)** — HIGH
- `srbhr/Resume-Matcher` — master resume → JD tailoring, match scoring, keyword highlighting, cover letter, interview prep, drag-drop section reorder, ATS score breakdown PR (#853, #813), tracked-changes/diff request (#810)
- `yishaik/TailorCV` — requirement extraction → CV fact extraction → evidence mapping → generation; **fabrication detection, borderline flagging, change logging, three strictness levels**
- `joseym/aarg` — adversarial tailor/review/revise loop, evidence IDs, **verbatim/grounded/unrecorded provenance labels**, gap interviews, claim-divergence lint, ATS + human PDF variants, local-first
- `sivsouvam/resume-honest` — truthfulness guardrails, per-bullet confidence scoring (`direct / transferable / adjacent / gap`), ATS compliance, humanisation pass
- `hannibalevit/resumorph` — assisted-apply UX (inline draft → preview → insert/copy/cancel), local-first, Docker
- `sardorml/tailit` — Typst-based tailoring with a stated "rephrase/reorder, never invent" policy
- `speedyapply/JobSpy` — multi-board scrape; the README's own stated limits (no persistence, no dedup, no change tracking)
- `career-ops`, `linkedin-assistant`, `JobRadar`, Faculty Atlas, `ShouldApply` — pipeline UI, "new since last visit", read-only/draft-only posture, ghost-job flagging, "Why Not 100" job-quality vs candidate-fit separation
- `andrewcrenshaw/strata-match` — two-stage vector-gate → LLM scoring, rationale/strengths/gaps/confidence tiers, token accounting
- `bansalbhunesh/redrob-hirefit-ranker` — measured-negatives evidence that embedding/semantic ranking did not generalise; deterministic explainability

**Academic / peer-reviewed** — MEDIUM-HIGH
- *JobMatchAI: explainable job search and candidate matching* (ACL 2026 demo, aclanthology.org/2026.acl-demo.52) — strict scoring/explanation separation, adjustable weights, default weight table, user study
- *Mitigating Fabrication in Multi-Stage LLM Pipelines for Hiring* (arXiv 2608.26171) — 180-run guardrail-vs-human-checkpoint experiment; 96.7% baseline fabrication, 50% residual under prompt guardrails alone
- *Grounded Optimization* (arXiv 2607.01457) — five-layer anti-hallucination framework; four fabrication modes; cross-domain contamination at 79–89% of baseline incidents
- *Job Posting Deduplication Using Embedding-Based Filtering and LLM Validation* (MDPI Information 17(3):233, 2026) — ~40% true duplicate proportion in an augmented 50k-posting corpus
- *Evaluating LLM Behavior in Hiring* (RecSysHR 2025) — implicit-weight instability between scoring and ranking framings

**Commercial product documentation and reviews (treated as vendor-adjacent)** — MEDIUM
- Teal / Huntr / Simplify feature comparisons and kanban-CRM analyses (bestjobsearchapps.com 2026-07/08/09; pitchhired.com 2026-07/08; trackjobs.co 2026-03) — tracking, follow-up reminders, autofill scope, CRM depth, pricing
- LoopCV / LazyApply / Sonara review corpora (remotejobassistant.com 2026-05; hiration.com 2026-07; adzuna.com 2025-10; applyghost.com 2026-02; loopcv.pro 2026-07) — **silent-failure and delivery-gap evidence; vendor-authored pages flagged**
- Jobscan product + review pages (jobscan.co; toolchase.com 2026; aitoolspolice.com 2026-06; gptprompts.ai 2026-04) — match-score mechanics, the 75% recommendation and the over-optimisation warning, ATS detection, Power Edit
- Huntr analytics/interview-tracking comparison (trackjobs.co) — CRM-depth feature inventory

**Deduplication and data-quality engineering** — MEDIUM-HIGH
- CleanJobData, *Deduplicating Job Listings Across Sources* (2026-07) — hierarchy, canonical-source selection, merge-not-discard
- Canaria, *4.47B Listings to 907M Unique Jobs* (2026-03) — two-stage dedup at scale, company-excluded dedup key, collapse rates by source type
- JobsPipe glossary + aggregator guide — dedup hierarchy, precision/recall trade-off, "duplicate rate is a core quality metric"
- DEV Community, *The same job is posted on three boards* (2026-07) — normalised composite key, merge-rate sanity band, fetch-normalise-merge-then-filter ordering

**Ghost / stale jobs** — MEDIUM
- noon.ai (2026-08), Nox (2026-05), Matcha.ai (2026-07), ShouldApply (2026-03), JobGhosting — ghost-job prevalence, posting-age signals, disclosure legislation (NY S8877, Ontario ESA from 2026-01-01), and the important caveat that most quantitative sources are commercially interested (flagged by CRS and Forbes)

**Notification infrastructure** — MEDIUM-HIGH
- selfhosting.sh (ntfy vs Apprise, 2026-02), bigiron.cc (Gotify vs ntfy vs Apprise vs Pushover, 2026-05), cloudhostreview.com (2026-05), shekse.com (2026-06), frasermclean.com (2025-10) — delivery-vs-routing split, iOS/APNs path, resource footprints, "always have a deduper"

**Cautions applied to all of the above**
- Vendor-authored comparison content (JobsPipe, LoopCV's own blog, ATS Resume AI, PitchHired) is treated as marketing and used only where an independent second source corroborates.
- No figure from a survey whose sponsor sells hiring-related services is used as a precise quantity; all are labelled directional in-place.
- All GitHub metrics and product features were read on 2026-09-15; `STACK.md` carries the same-date repo-health data.

---

*Feature research for: AI-assisted job search automation (local, self-hosted, Python-first)*
*Researched: 2026-09-15*

