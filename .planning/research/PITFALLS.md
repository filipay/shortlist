# Pitfalls Research

**Domain:** AI-assisted job search automation (local, self-hosted, Python-first, Dockerised) — pluggable source adapters → deduped listing store → deterministic hard-rule filter → LLM ranking against a structured CV → LaTeX CV tailoring with anti-fabrication verification → assisted apply → tracker
**Researched:** 2026-09-15
**Confidence:** MEDIUM-HIGH overall. HIGH on the data-model, dedup, anti-fabrication and scheduler pitfalls (they are corroborated by primary library docs, peer-reviewed studies and upstream issue trackers). MEDIUM on the scraper-longevity, ban-trigger and UX pitfalls (convergent engineering write-ups and platform policy pages, but several sources sell competing products). LOW where only a single vendor or blog supports a specific number — those are labelled inline and must not be treated as authoritative.

> **How this file relates to its siblings.** `STACK.md`, `FEATURES.md` and `ARCHITECTURE.md` in this directory are treated as settled: JobSpy behind an adapter interface, SQLite WAL + SQLAlchemy + Alembic, APScheduler 3.11.3 at `--workers 1`, Tectonic 0.17.0, LaTeX-safe Jinja2, `opencode serve`, and the structured-CV-with-stable-IDs design. This file does not re-litigate them. Where a pitfall reveals a gap or a tension in a sibling, it is called out explicitly. Pitfall IDs (`P#`, `M#`, `m#`) are local to this file; `TS-*`/`DF-*`/`AF-*` refer to `FEATURES.md` and `§n` to `ARCHITECTURE.md` section numbers.
>
> **Phase names** used in the "Phase to address" lines are the eight suggested phases from `ARCHITECTURE.md` §14.3: (1) Walking skeleton + foundations, (2) Clean/filtered/queryable queue, (3) LLM port + structured output, (4) CV fact store + LaTeX compile spike, (5) Ranking, (6) Tailoring + verification, (7) Assisted apply + tracker, (8) Operations + polish.

---

## Critical Pitfalls

Mistakes that cause rewrites, personal harm, or a tool that silently produces nothing. For this project the last of those is the worst outcome: `PROJECT.md` states plainly that "a tool that silently produces nothing is worse than no tool" — several of the pitfalls below are precisely ways that happens.

### P1: Treating scraper breakage as a bug to fix once, not a permanent operating condition

**What goes wrong:**
The pipeline works on day one and returns hundreds of listings. Weeks later it returns zero — no exception, no red log line, HTTP 200 throughout — because LinkedIn renamed a CSS class, moved a field into a different container, or started serving a block/interstitial page that still parses as valid HTML. Every downstream stage then operates on an empty or partially-filled input, and the LLM "produces nothing" for reasons no one can see. The inverse also happens: the broken scraper returns *plausible-looking garbage* (wrong element scraped, null salary fields, an empty description) that is persisted as if valid.

**Why it happens:**
A scraper carries an implicit dependency on someone else's HTML, and that HTML is not a stable API. It drifts in predictable ways — selector renames, layout changes, A/B tests serving different markup to different visitors, anti-bot challenges — and critically, **most of these do not throw**. When the fetch succeeds and the parse succeeds and the row is written, the run looks healthy. Developers who test only against their own happy-path run, once, have no mechanism to notice the world changed.

**Warning signs:**
- A run whose fetched count drops sharply without an error (e.g. 200 → 4), or global success rate looks fine while one board's count collapses.
- A field that used to be populated (salary, location, description) is null on an implausibly high share of new rows — *per-field fill rate*, not run success, is the signal.
- `runs` rows completing with `status='done'` but `ranked_count = 0`, and no stage recording *why*.
- The queue is empty one morning and nobody can say whether that is "no matching jobs" or "LinkedIn blocked us".
- Output volume drifting from the baseline without a corresponding change in search criteria.

**Prevention:**
- **Design every adapter as total and failure-tolerant**: return a `FetchResult(status=...)`, never raise for a source-specific failure (`ARCHITECTURE.md` R1). A blocked source degrades the queue; it does not abort the run and does not masquerade as success.
- **Instrument the metrics that catch silent failure, per source**: per-domain success rate, per-field null/fill rate against a baseline, output-count delta vs the trailing average, and *freshness* (timestamp of the last successfully parsed listing). Alert on staleness, not just on exceptions.
- **Separate fetch-level failure from parse-level failure.** A 403, a CAPTCHA page, or a suspiciously short body is a fetch problem; a valid page with a missing field is a parse problem. They need opposite fixes, and both present as empty data.
- **Treat selectors as data, not constants.** Keep extraction recipes in config/fixtures that can be regenerated, validate a proposed selector against the DOM before trusting it, and make the fallback selectors explicit (the Indeed scrapers that survive use an embedded-JSON path first and CSS selectors with several fallbacks second).
- **A cheap liveness probe per source** (`probe()` for `/health` and the source-status UI) that fetches one fixed known URL and asserts a known answer, so a break is found by the system, not by the user noticing an empty queue.
- **Record the "why is the queue empty?" answer** on every run: per-source fetched/status counts and per-listing exclusion reasons (`FEATURES.md` TS-9, `runs.errors_json`). This is the difference between an incident and a data disaster.

**Phase to address:** Phase 1 — the walking skeleton must prove source survival and include the probe/source-status surface, not just a successful first scrape. Carried into Phase 2 (`runs` UI, exclusions) and Phase 8 (source health).

**Evidence / confidence:** Very high that silent breakage is the dominant failure mode of production scrapers — four independent 2026 engineering write-ups and two open-source observability tools (ScraperGuard, ScrapeSentinel-style) describe the same pattern and metrics. MEDIUM-HIGH. The specific claim that "a block page and a layout change look identical in your data" is stated across independent sources. JobSpy's own issue tracker shows live examples (`Job Description is empty for linkedin` #374, `job_url_direct missing for linkedin` #370) — HIGH that this library breaks in exactly this way.

---

### P2: Logging into LinkedIn/Indeed with a real account to scrape or autofill

**What goes wrong:**
The most reliable-looking fix for job-board hostility is to use an authenticated session: the user's real LinkedIn or Indeed login, either for scraping more results or to prefill/auto-submit an application. This converts a scraping maintenance problem into a **personal account-ban problem**. LinkedIn's enforcement escalated in 2026, moved connection-request limits from 100/day to 100/week, restricted millions of accounts in 2025, and permanently bans repeat offenders with IP blacklisting. The user's real professional identity — connections, history, endorsements — is the collateral.

**Why it happens:**
The guest/public surface rate-limits around the 10th page and shows only a few profiles before an auth wall. Every tutorial and several current tools (and `JobSpy` itself, via `JOBSPY_CREDS`/credential fallback) make "just add credentials" the obvious next rung on the ladder. It is technically effective and it is exactly where both ToS exposure and computer-misuse risk escalate — and where AIHawk's contributors were banned (the project then removed LinkedIn automation entirely).

**Warning signs:**
- Any code path that reads `LINKEDIN_USERNAME`/`LINKEDIN_PASSWORD` or stores session cookies for a real account.
- A feature request or design note that says "when blocked, fall back to authenticated scraping".
- The browser extension / autofill idea reappearing as "it is the only way to reach login-gated boards" (`FEATURES.md` AF-9).
- Any plan to raise `results_wanted` beyond the anonymous envelope "because with login it works".

**Prevention:**
- **Hard-code the bright line: public, logged-out pages only.** No auth bypass, no CAPTCHA-solving integration, no credential fallback, no driving the user's live session. Document it in the repo, not just in a plan.
- **Stay on the assisted-apply posture** (already a `PROJECT.md` Key Decision): generate the package, the human pastes and clicks. Independent 2026 analysis places "AI drafts content, human reviews and clicks send" in the low-risk, user-initiated category and mass/authenticated automation in the escalating-risk grey zone.
- **Keep volume inside the personal envelope**: a handful of searches, once a day, one residential IP, honest User-Agent, randomised pacing, raw `results_wanted` moderate (≤50–100 per run), no burst.
- **Bake politeness ceilings into config** (`FetchBudget` per source) rather than relying on "we happened to be polite". Respect and record `robots.txt`.
- **Encode the stop signals**: CAPTCHA, forced re-login, "unusual activity" notice, or a sudden drop in results means stop and let the account rest — never retry harder.
- **Prefer the legal hedges**: Adzuna (free, self-serve, quota-limited) as a genuine source, and the employer's own ATS listing where available, rather than escalating on a hostile board.

**Phase to address:** Phase 1 (architectural — never build the credentialed path), enforced continuously. Phase 8 (source health must surface the stop signals, not auto-escalate).

**Evidence / confidence:** HIGH on the direction (LinkedIn's own Prohibited Software policy, the 2026 crackdown, and AIHawk's documented retreat from LinkedIn). MEDIUM on the specific numeric triggers (23% restriction rate in 90 days; ~100–150 profiles/hour; 100/week connection limit) — these come from tool vendors and policy-summary pages, several of which sell competing automation products. Treat as directional; the direction is unambiguous.

---

### P3: Deduplication that merges too aggressively, deletes the loser, and cannot be undone

**What goes wrong:**
The same role appears on LinkedIn and Indeed as two rows. A fuzzy rule merges them wrongly — or merges two genuinely different roles at the same company ("Software Engineer II" vs "Senior Software Engineer", or two locations) — and, because the implementation "picks a winner and deletes the loser", a real job silently disappears from the queue. Nobody notices until the user compares against the portals and finds a job they would have applied to was never shown. The opposite failure is equally corrosive: the key never merges anything, so the queue shows the same job three times and the user stops trusting the feed.

**Why it happens:**
Exact matching on title+company+location barely works because all three drift between reposts ("Macy's" / "Macys Inc"; "SF" / "San Francisco, CA"; "Sr. Engineer" / "Senior Engineer"). The naive fixes are to *loosen* the key until duplicates collapse (which starts merging distinct jobs), or to match on a single strong signal (canonical URL) which misses most true cross-source duplicates because syndicated copies have different URLs. Deleting the absorbed row is the tempting implementation because it keeps the table clean — and it is the one that destroys data irreversibly.

**Warning signs:**
- An implausible collapse ratio — e.g. 200 raw postings → 12 records. (The sanity band cited by practitioners is roughly **10–15% cross-board merge rate per keyword**; far above that means the key is too loose.)
- The opposite: a cross-board merge rate near zero after the first weeks, i.e. normalisation is doing nothing.
- `listings` has no merge-audit table, or merges are `DELETE`d rather than marked.
- The dedup key includes a truncated free-text title and no location/window constraint.
- You cannot answer "show me the rows behind this duplicate count" — practitioners are emphatic: *every dedup bug looked reasonable as a percentage and obviously wrong as a list of titles*.

**Prevention:**
- **Two-tier as designed, plus the missing fallback key.** Tier 1 exact upsert on `(source, source_listing_id)` **plus** the mandatory `(source, canonical_url)` fallback, because JobSpy documents `id` as nullable and SQLite permits unlimited NULLs in a UNIQUE index — without the fallback the constraint silently degrades to "insert everything" (`ARCHITECTURE.md` A2/AP7). Tier 2 fuzzy on normalised `(company, title, location, posted_week)` with a threshold.
- **Merge, don't discard.** Union the fields (one board has the salary, another the accurate date, a third the full description), keep every `listing_sources` row and every apply URL.
- **Make every merge reversible.** `listing_dupes` with a pre-merge `snapshot_json`, `merged_at`/`reverted_at`/`reverted_by`, and a real revert path (`FEATURES.md` TS-3, `ARCHITECTURE.md` §8.3).
- **Require all key components.** Never merge on a bare fuzzy title; short strings are similar by accident.
- **Ordering is not optional:** fetch fully → sanitise → normalise → merge → *then* filter and cap (`ARCHITECTURE.md` §8.1). Filtering or capping first throws away the duplicate copy that carried the salary.
- **Measure and print.** Publish the merge rate per run and provide a listing view of exactly which rows merged; leave the threshold θ as a **setting with a tuning task** once a real corpus exists (`FEATURES.md` Gap 3) rather than a frozen constant.
- **Choose a canonical source deliberately and record why**: employer ATS posting (`direct_url` present) > most recently updated > most complete. Treat a live recruiter repost with a dead original as evidence the role **closed**, not as a live listing.

**Phase to address:** Phase 2 — and the `listing_dupes` audit table plus the two-key Tier-1 index must exist in **migration 0001** (Phase 1) because a false merge cannot be reconstructed after the fact.

**Evidence / confidence:** MEDIUM-HIGH on the hierarchy and the merge-not-discard posture (multiple independent production write-ups plus the CIKM 2021 framework on Adzuna data; the 50–80% duplicate-proportion figure is from the peer-reviewed source). LOW on the specific threshold and the 10–15% merge-rate band at *this* project's scale — untunable without the user's corpus, hence "setting + tuning task", not a constant.

---

### P4: Runaway LLM spend because the cost gate is an afterthought

**What goes wrong:**
A run that should have cost cents costs dollars, or a per-listing call path quietly becomes N calls per listing across a batch of hundreds. The dominant variable cost in this project is LLM calls (`PROJECT.md` Constraints). The classic blowups are structural, not exotic: ranking every fetched listing instead of the filtered survivors; re-sending a large repeated system prompt and full CV for every listing; unbounded retry loops that re-send the accumulated failure context; verbose rationales with no output-length bound; and a model upgrade or auto-upgrade changing the price per token without anyone noticing.

**Why it happens:**
The obvious implementation ("for each job: ask the LLM to score it") is the one that scales linearly with the *unfiltered* feed. The hard-rule filter exists precisely to cap this, so building ranking before the filter — or letting the filter be bypassed/degraded — removes the only cost control that exists. There is also a perverse incentive: rationale text and chain-of-thought feel like quality, so prompts grow.

**Warning signs:**
- `llm_calls` / `runs.llm_tokens` is absent, or present but nobody can attribute cost to a stage.
- A run's candidate count is not bounded before the LLM stage.
- No per-run or per-day budget cap anywhere in config; no `perRequestLimit`-style setting.
- The system prompt plus CV is re-sent per listing with no caching or batching consideration.
- Retry count is unbounded or the retry prompt includes the entire prior failed trajectory.
- Adding a source or widening criteria multiplies cost with no gate change.

**Prevention:**
- **Filter before rank, always** (`FEATURES.md` DF-2) — and treat the filter's output count as the *budget input* to the ranking phase, not just a boolean gate.
- **Resolve the batching question in the Phase 5 plan, before execution** (`STACK.md` Open Q7, `FEATURES.md` Gap 1): one call per listing for best per-listing rationale, or one call per K listings sharing one system prompt to amortise the fixed prompt cost — noting the documented trade-off that quality degrades as batch size grows and the prompt approaches the effective context window.
- **Hard cost controls, not observability alone**: a per-run token/call ceiling and a daily/monthly cap that *refuses calls* once reached (the budget-guard pattern), plus per-request limits and loop detection. Remember the documented parallel-call overshoot: caps checked on settled spend let all in-flight calls through, so 100 concurrent calls against a $5 cap can settle at $10 — enforce before the call and count in-flight.
- **Design the prompt for cost**: stable prefix first (system + CV) and dynamic listing content last, so prompt caching can work; trim retrieved context; bound output length explicitly ("≤3 bullets", max tokens).
- **Record cost per call and per run** in `llm_calls`, with model, tokens, latency, and status, so a spike is attributable. Model/version drift between ranking and tailoring is a real documented failure class ("version drift", "cost-driven performance collapse").
- **Never put the CV or a full description where a snippet will do.** Input tokens dominate; cutting context by half is usually free quality-wise.

**Phase to address:** Phase 2 (the filter and the `runs`/`llm_calls` counters) and Phase 5 (the batching decision and the budget caps). The budget caps belong in the Phase 5 plan, not bolted on after the first expensive run.

**Evidence / confidence:** MEDIUM-HIGH on the failure modes and mitigations (independent cost-engineering write-ups converge; a 2026 paper catalogues agent budget overruns as a documented production failure class with a 63-item empirical catalogue). LOW on any specific dollar figure for this project — cost is unmeasured until the model and batch shape are chosen.

---

### P5: Treating LLM ranking output as stable, calibrated, and objective

**What goes wrong:**
The score numbers *look* authoritative — 87, 71, 43 — so the user treats them as a real ordering. In reality LLM scores are assumption-sensitive and unstable: the same listing can move materially between runs, and the ordering depends on things that have nothing to do with candidate fit. Position bias means a candidate's rank in the prompt influences the judgment, with the direction of the bias (primacy vs recency) varying by model and task. Scoring bias means the *scoring prompt itself* shifts absolute scores — adding one in-context example for a score level moved unrelated samples in a documented case, and rubric ordering and score-ID formatting perturb results. Sycophancy means a model may favour agreement over truthfulness, and self-preference means an evaluator favours output that resembles its own. If the model also writes the rationale, a low score can be narrated as a good fit (or vice versa), and the rationale will read fluently enough that nobody checks it against the underlying evidence.

**Why it happens:**
The simplest prompt is "rank these jobs". Relative ranking is the framing most exposed to position and framing effects, and it is also the framing that produces a single opaque number with no way to audit *why* it changed. A subtle trap from `FEATURES.md` §2: a controlled study found implicit attribute weights shift between *scoring* and *ranking* framings, so signals that look negligible in absolute scoring can be amplified in a ranking context. Rationale unfaithfulness compounds it — the JobMatchAI audit found the top contributing factor was mentioned in only ~70% of generated explanations (and ~58–59% for medium/low matches vs ~94% for high matches).

**Warning signs:**
- A listing's score changes materially between two runs with no change to the CV or criteria.
- Ranking is implemented as "rank these N jobs" rather than a bounded absolute score per listing against an explicit rubric.
- Only a total score is stored, so the only way to answer "why did this change?" or "what if I weight salary more?" is another LLM call.
- Rationales are plausible prose that does not reference the actual factors that moved the score.
- Scores cluster near the top (everything is 80+) — the sign of a lenient/sycophantic grader.
- The same CV element appears in `strengths` for listings that are otherwise unrelated.

**Prevention:**
- **Bounded absolute scoring against an explicit rubric; never relative ranking.** One listing, one rubric, one score in a fixed range. Store the per-factor sub-scores (`φ_f`) and the weights (`weights_json`) and compute `U = Σ w_f·φ_f` **in code** — the single design choice that makes weight sliders, the fit breakdown and honest re-ranking cheap (`FEATURES.md` DF-3, `ARCHITECTURE.md` §9.1).
- **The LLM narrates pre-computed evidence; it does not invent the score.** Pass it the six factor scores and supporting evidence IDs, not raw documents (JobMatchAI's stated principle). Render the factor table as structured UI and treat the LLM prose as a supplement.
- **Make instability diagnosable rather than hidden**: record `model`, `provider`, `rubric_version`, `criteria_version` and `backend` on every `scores` row so a score shift can be traced to a criteria edit, a model change, or genuine noise.
- **Temper the prompt against inflation**: explicit "score honestly; most listings are not a strong fit; reserve the top of the range", and include a cheap calibration anchor. Avoid adding worked examples for specific score levels — that is the exact perturbation documented to shift unrelated scores.
- **Treat confidence as first-class**: a `HIGH/MEDIUM/LOW` confidence tier per listing (as `strata-match` does) communicates uncertainty that a bare number hides.
- **Run a stability check as a phase deliverable**: score a fixed set of ~10 listings twice and report the score variance and rank-order change. This is the only way to know whether the numbers mean anything.

**Phase to address:** Phase 5 (rubric, per-factor storage, calibration and the stability check). The `scores` schema with `factor_scores_json` must exist in migration 0001 (Phase 1) — retrofitting per-factor storage is the most expensive change in the project (`FEATURES.md` §2).

**Evidence / confidence:** HIGH that these biases are real and large (peer-reviewed position-bias study across 15 judges / 150k instances; first dedicated scoring-bias study; framing-bias study across 14 judges; SycEval and follow-up sycophancy work with ~56–62% rates and ~78.5% persistence). MEDIUM on the magnitude for *this* rubric and model — unmeasured until the scoring phase runs a stability check.

---

### P6: Relying on prompt wording to prevent CV fabrication

**What goes wrong:**
The tailoring prompt says, emphatically and repeatedly, "do not fabricate; only use the user's real experience". The model fabricates anyway — because the instruction is not a constraint. A controlled 180-run study of multi-stage hiring pipelines found a fully automated baseline produced at least one unsupported claim in **96.7%** of outputs (mean 6.80 findings/output). Adding prompt guardrails cut finding density by 86% — and **50% of outputs still contained a fabrication**. The failure modes are specific and subtle: *temporal fabrication* (technology that did not exist during the claimed dates), *cross-domain contamination* (an AWS-only role rewritten with Azure services — 79–89% of baseline incidents), *structural mutation* (silently condensing 8 bullets into 4, removing truth rather than adding falsehood), and *content fabrication*. The tailored CV looks perfect, the user sends it, and the lie is discovered in an interview or a reference check.

**Why it happens:**
Optimising a document for "match the job description" is an optimisation problem, and the cheapest path to a higher match score is to add the missing keywords. A prompt is part of the input, not part of the type system. The model is also rewarded in training for being helpful and for producing what the user appears to want — which is exactly the sycophancy dynamic (P5). And a "reframe it in the JD's vocabulary" instruction without an ID boundary is the documented path from benign rephrasing to invented content.

**Warning signs:**
- The LLM is given the `.tex` (or free rein over prose) and returns text, rather than returning an ID-based reorder/re-weight patch rendered deterministically (`ARCHITECTURE.md` §7, AP2).
- The tailoring schema has any free-text field on the path to the PDF.
- Verification is planned "after" tailoring rather than shipping with it (`FEATURES.md` §7.5).
- A "suggest improvements" path whose output is applied automatically.
- Any pipeline stage whose job is to "fix" a failing claim — repair pressure is fabrication pressure.
- Keyword gaps are fed back into the generation prompt, which is the documented backdoor that turns an ATS miss into an invented bullet (`FEATURES.md` DF-7).

**Prevention:**
- **Make fabrication structurally unrepresentable.** The LLM returns a `TailoringPatch` of typed operations over enumerated, stable IDs (move / reweight / demote / drop / reorder); there is no free-text field anywhere in the schema that becomes text in the PDF. Employers, titles and skills are enumerated lists, so a fabricated employer is not merely discouraged but unrepresentable (`ARCHITECTURE.md` §7.3).
- **Keep `bullet.text` immutable.** The engine may reorder, re-weight, demote and drop; it must never rewrite. Reframing, if wanted, is a separate human-approved `Suggestion` with its own evidence ID and its own verification pass.
- **Ship verification *with* tailoring, as a gate.** Extract the compiled PDF text with `pypdf` and assert: id containment, no new named entity, bullet conservation (`rendered == facts − declared_drops`, both directions), metric containment, temporal consistency, requirement→evidence integrity, and injection residue. On any fail, store the artefact as `blocked` — not downloadable, not linkable from an application.
- **Block, do not repair.** A false positive should be resolved by a recorded, human-acknowledged override or a one-click "drop this bullet and re-render", never by asking the model to fix the claim.
- **Add the human checkpoint.** The same study found prompt guardrails and a human-in-the-loop checkpoint are complementary, and the checkpoint eliminated identity fabrications and cut JD-baited claims from 47% to 2%. Here the checkpoint is assisted apply plus block-and-review — which works only because the structural layer means the human is reviewing *reorderings*, not fact-checking prose.
- **Encourage honesty, it is not a quality trade-off**: claim retention exceeded 99% under both guardrail and checkpoint conditions.

**Phase to address:** Phase 6 (tailoring + verification shipping together). The structured CV fact store with stable IDs is a **shared prerequisite of both ranking and tailoring** and should be built early — see Phase 4 in `ARCHITECTURE.md` §14.3, which runs in parallel with Phases 2–3.

**Evidence / confidence:** MEDIUM-HIGH — the most strongly corroborated finding in the sibling research. Two independent academic evaluations (the 180-run guardrail-vs-checkpoint study; the five-layer grounded-optimisation framework) plus three open-source implementations (TailorCV, `aarg`, `resume-honest`) converge on fact-store + IDs + a separate incentive-free verifier + drop-rather-than-repair.

---

### P7: A LaTeX pipeline that works on the developer's machine and fails in the container (or vice versa)

**What goes wrong:**
Three distinct failures, any of which ships a broken CV path:
1. **Cold cache / no network.** Tectonic downloads packages on demand. On the developer's machine the cache is warm; in a fresh container, or on the user's laptop after a rebuild, the first compile of an unfamiliar package fails with network errors and font-not-found errors. The user's CV uses one `\usepackage` outside the primed set and compilation dies.
2. **Compile failure from the user's real preamble.** Tectonic is XeTeX-derived and rejects pdfTeX-only primitives (`\pdfcompresslevel`, `\pdfminorversion`, `\pdfobjcompresslevel`), and a package may be outside its bundle. The real `.tex` is **not in this repo**, so this is unverified (`ARCHITECTURE.md` Open Q1/Q2, CV-R7).
3. **Escaping crash.** A CV bullet or a listing description contains `&`, `%`, `#`, `_`, `$`, `~`, `^`, `{` or `}`. "R&D" or "improved throughput by 20%" breaks the compile. This is the single most likely runtime crash in the LaTeX layer.

**Why it happens:**
Tectonic's auto-fetch is a feature on a warm machine and a landmine on a cold one; the docs are clear that packages are fetched on demand and cached. Preambles written for `pdflatex` are common and portable in the author's mind but not to Tectonic. And templating a language made of braces with a templating language made of braces is inherently collision-prone — every serious project hits the delimiter wall.

**Warning signs:**
- The Docker image does not pre-cache packages at build time, or the cache lives outside the image.
- No `Dockerfile.texlive` fallback, and `LATEX_ENGINE` is hard-coded rather than a setting.
- The first time the pipeline is run against a fresh checkout/container is during a demo.
- The real `.tex` has never been compiled by Tectonic in a throwaway spike.
- Interpolation into `.tex` without a mandatory `escape_tex` filter (backslash replaced **first**, or you double-escape).
- Default Jinja2 delimiters (`{{ }}`/`{% %}`) in a `.tex` file.
- `-Z shell-escape` appears anywhere in the compile invocation.

**Prevention:**
- **Prime the package cache at image build time** with a preload `.tex` that uses everything the CV uses plus common extras, so compilation is offline afterwards. This is the non-negotiable Docker step (`STACK.md` Q6).
- **Stage → compile in a temp dir inside the image → copy artefacts out.** This sidesteps the known Tectonic VFS bug re-opening the primary input after `biber` on a bind-mounted volume, and it is cheaper to design in than to retrofit.
- **Run the Tectonic spike on the user's actual `.tex` before the tailoring phase is estimated** — bundle coverage, pdfTeX-only primitives, bibliography/biber usage. Keep a curated TeX Live fallback Dockerfile and make the engine a config setting.
- **Sanitise known pdfTeX-only primitives** from the preamble before compiling.
- **Mandatory `escape_tex` filter on every interpolated value**, including all text originating from job listings. Use a LaTeX-safe Jinja environment (`\VAR{}`/`\BLOCK{}`), and document the single-brace block-end limitation (a block body cannot contain a closing brace) so nobody trips on it later. Pick one convention; never mix.
- **Never enable shell-escape** — the compile input is machine-influenced, so it is arbitrary code execution. Default it off explicitly.
- **Treat compile failure as a structured result**, not an exception: capture exit code, `compile_log`, page count, and render a blocked artefact with the log surfaced (`ARCHITECTURE.md` C12/C13).

**Phase to address:** Phase 4 — the LaTeX spike runs in parallel with Phases 2–3, deliberately ahead of the tailoring phase, because it retires the project's largest unquantified risk. Phase 6 executes against the validated engine.

**Evidence / confidence:** MEDIUM-HIGH on the mechanics (Tectonic's own issue tracker shows the offline/`\tiny` font failure; the VFS+biber bug is documented in a real PR; the pdfTeX-primitive rejection is documented in `STACK.md` Q6). The specific risk to *this user's* CV is LOW confidence — **unmeasured because the `.tex` is not in the repo**. This is why the phase mapping makes the spike a hard gate rather than a task.

---

### P8: Data-model choices that cannot be backfilled later

**What goes wrong:**
The schema is built for what the app does *today*, and the omissions are exactly the columns that history cannot reconstruct:
- No `first_seen_at` / `last_seen_at` / `content_hash` → no "new since your last visit", no stale detection, no repost detection, and no way to generate them retroactively.
- No `listing_events` (save/skip/hide/shortlist) captured from day one → the future ranking-feedback loop is impossible, because the events describe decisions that already happened.
- Only a total `score`, no per-factor sub-scores or weights → every weight-slider adjustment, re-rank, or fit-breakdown view requires a fresh, paid LLM call. `FEATURES.md` calls this "the cheapest mistake to avoid and the most expensive to retrofit".
- No `applications.cv_artifact_id` → the version↔outcome link (the project's genuine differentiator, DF-9) can never be reconstructed because you cannot know which PDF was sent.
- `updated_at`-style single-row state instead of an append-only event log → the status history is overwritten and later analytics (response rate by tailoring strategy) are untrustworthy.
- Missing/incorrect timestamps or local-time storage → cross-run comparisons and freshness logic are wrong in ways that are hard to detect.

**Why it happens:**
The columns feel speculative at build time ("nothing reads `last_seen_at` yet"), so they get deferred. But these are not features — they are *observations*, and observations not recorded at the moment they happen are gone. A migration can add a column; it cannot invent the history that column was meant to hold. Event sourcing is also widely misunderstood: the small, pragmatic version here is one immutable event table beside the mutable current-state table — not a CQRS rewrite.

**Warning signs:**
- A migration review that says "we'll add tracking fields when we need them".
- A single `last_run` on the user/global rather than per named search — it breaks "new since" the moment there is more than one search.
- Timestamps stored in local time, or `updated_at` overwritten in place.
- `applications` with a status column but no `application_events` history.
- `scores` with a single `total_score` column and no `factor_scores_json`/`weights_json`/`criteria_version`.
- Save/hide implemented as a boolean on the listing with no timestamped event row.

**Prevention:**
- **Migration 0001 must contain the non-backfillable set**, and `ARCHITECTURE.md` §9.4 is the acceptance checklist: `first_seen_at`/`last_seen_at`/`content_hash` NOT NULL; append-only `listing_events`; `scores.factor_scores_json`+`weights_json`+`criteria_version`; `cv_artifacts.verification_json` with a `blocked` state; `applications.cv_artifact_id`; the partial unique index on `(source, source_listing_id)` and the unconditional `(source, canonical_url)`; `sources.capabilities_json` + `tos_audited_at`; `listings.blocking_key`.
- **One immutable event row per change, with a UTC timestamp and a stable FK.** Keep current state in a separate projected table.
- **Store the raw value and the normalised value** for high-cardinality fields (titles, locations, companies) so grouping and dedup do not require re-parsing.
- **Never overwrite state that has analytic value** — status transitions append to `application_events`, they do not just update a column.
- **Treat the event capture as a v1 obligation even though the learning is deferred.** DF-11 is a v3 experiment; the *data* it needs is a v1 migration.

**Phase to address:** Phase 1 (migration 0001) — this is the single hardest ordering constraint in the project. Phase 2 (events, exclusions), Phase 5 (`scores` decomposition), Phase 7 (`applications.cv_artifact_id`).

**Evidence / confidence:** HIGH on the principle (append-only event tables, UTC timestamps, grain separation, and never overwriting history are standard data-engineering practice with consistent multi-source agreement). HIGH that the specific fields are unbackfillable — they are observations of events that occur in time.

---

### P9: A queue that is silently empty, stale, or full of ghost jobs — and the user stops trusting it

**What goes wrong:**
The tool runs every morning and the user opens it with decreasing frequency because: the queue is empty with no explanation; or it shows the same jobs for days; or half the "opportunities" turn out to be dead/ghost postings; or a notification fires for every listing and gets muted. This is a product failure, not a technical one, and it is self-reinforcing: the Core Value ("every morning there is one ranked, explained, apply-ready queue") is a habit, and a habit broken by noise or silence does not come back.

**Why it happens:**
Research suggests roughly **30–40% of listings on major aggregators are duplicates or stale**, and ghost jobs are pervasive enough that in UK data 24% of workers had applied for a ghost job and only 38% of search results were seen as genuinely relevant. Job boards monetise volume, not candidate outcomes; listings persist for the term they were bought even after the role is filled. The tooling mistake is to treat every persisted listing as an opportunity and to notify on all of them.

**Warning signs:**
- The queue is empty and `runs` shows a successful run — with no per-source counts or exclusion reasons to explain it.
- The same listing is visible for many consecutive days with no Fresh/Stale/Likely-dead signal.
- A listing's `last_seen_at` keeps advancing but its `content_hash` never changes (repost/evergreen signal ignored).
- A "why is this not in my queue?" question cannot be answered from `listing_exclusions`.
- Notifications are per-listing rather than one batched digest per run.
- The user starts checking the portals manually "just to be sure" — the trust has already gone.

**Prevention:**
- **Make every run explain itself.** One `runs` row per run with per-source fetched/status counts, deduped/filtered/ranked counts, errors, and tokens; one `listing_exclusions` row per rejection with the rule id and reason. "Zero results" must never be ambiguous (`FEATURES.md` TS-9).
- **Surface freshness in the UI**: a "new since your last visit" badge from `first_seen_at > last_run_at` (per named search, not global) and a Fresh / Stale (30d+) / Likely-dead (60d+) badge from `first_seen_at`, `last_seen_at` and `content_hash` change.
- **Separate job quality from candidate fit.** A low score must tell the user whether the problem is them or the posting — ShouldApply's "Why Not 100" framing: *"You should not improve your skills to fix a ghost job flag."* Store the quality signals (`quality_signals_json`) so a ghost-job badge is cheap given the timestamps dedup already needs.
- **One batched digest per run, never per-listing pushes** when notification is added (ntfy later). The documented homelab failure is exactly the absence of a deduper: repetitive alerts get muted and the real one is missed.
- **Give the dross a low-cost exit**: hide/save/archive with sticky state, and one-click "hide jobs like this" that becomes an exclusion term.
- **Add a follow-up nudge** (`next_action_at = applied_at + N days`) so the tracker becomes a reason to return, not just a record.

**Phase to address:** Phase 2 (run log, exclusions, stale/new badges) and Phase 5 (quality vs fit separation in the ranking view). Phase 8 adds notification, batched.

**Evidence / confidence:** MEDIUM-HIGH on the drivers (multiple independent UX studies and the MeasuringU SUPR-Q work are consistent: relevance/filters and trust are the top experience drivers, and tracking is a significant one; ghost-job prevalence is well documented). MEDIUM on the specific numbers — several ghost-job sources sell competing services and are flagged as such. The *feature* is justified regardless of the precise percentage.

---

### P10: Every run tries to do everything, so one failure produces nothing

**What goes wrong:**
Scrape, sanitise, dedup, filter, rank, tailor and notify are wired as one monolithic job. LinkedIn rate-limits halfway through, or one CV fails to compile, and the run aborts — so there is no queue that morning even though 180 usable listings were fetched. Or the inverse: to keep the batch moving, the code proceeds past a failed verification and publishes an unverified CV. Both are consequences of conflating two different kinds of work.

**Why it happens:**
"One pipeline" is simpler to write and demo than two pipelines with different tolerances. But ingest is many-listing, cheap-per-item, failure-tolerant and cost-capped; tailoring is one-listing, expensive, must-not-fail-open and human-reviewed (`ARCHITECTURE.md` §1.3). A single control path forces one tolerance onto both.

**Warning signs:**
- A single source returning `partial`/`blocked` aborts the whole run.
- A CV compile failure is swallowed so the batch can continue.
- The `runs` row has one `status` for the whole pipeline and no per-stage counts.
- The manual "run search now" and the tailoring action share one code path.

**Prevention:**
- **Keep the two pipelines separate**: `run_pipeline()` (batch ingest → filter → rank) and `tailor_listing()` (per-listing patch → render → compile → verify → package). They may share the LLM port and repositories, not a control path.
- **Total functions at every boundary** (`FetchResult`, `StructuredCallResult`, compile result objects) so a partial failure degrades one stage rather than the run (`ARCHITECTURE.md` Pattern 2).
- **Per-stage instrumentation and a `partial` run status** so "37 of ~200 expected, rate-limited after page 4" is visible (`ARCHITECTURE.md` §5.4).
- **Verification must be able to block without blocking the queue** — a blocked artefact is stored for diagnosis, not downloadable, not linkable.

**Phase to address:** Phase 1 (two-callable shape, total functions) and Phase 6 (compile/verify isolation).

**Evidence / confidence:** HIGH — it follows directly from the stated constraints and is the most common architecture mistake named in the sibling architecture file.

---

### P11: Treating the CV as one document instead of two, so "source of truth" becomes ambiguous

**What goes wrong:**
`PROJECT.md` says the `.tex` is the source of truth. `STACK.md` Q6 says model the CV as structured data with stable IDs. Both are right, and the ambiguity is dangerous: if the structured store and the `.tex` are allowed to drift, `render(cv.yaml)` no longer equals the user's real CV, and the tool silently replaces their livelihood document with a slightly different one (a dropped bullet, a reordered section, a changed date). The failure is invisible because the PDF looks fine — it is just not *their* CV.

**Why it happens:**
"Source of truth" gets used without a qualifier. Nobody defines which artefact wins when they disagree, so whichever was edited most recently wins by accident. A human editing `base.tex` out of habit after the import is the trigger.

**Warning signs:**
- No golden test comparing a base render from `cv.yaml` against `base.tex`.
- `base.tex` is writable/edited after import with no re-import path.
- The rendered output has a slightly different bullet count or ordering than the original with no diff explaining it.
- "Source of truth" appears in the codebase without a qualifier.

**Prevention:**
- **Name two canonical documents** (`ARCHITECTURE.md` §7.1): `cv/base.tex` is the **human's** canonical document, immutable by the tool; `cv/cv.yaml` is the **machine's** derived fact store, edited by import + explicit human curation; `artifacts/<id>/cv.tex` is a rendered derivative, never edited.
- **Make the derivation verifiable with a golden test**: render the base CV from `cv.yaml` with an identity patch, extract text from both PDFs, and assert fact-equivalence (all orgs, titles, dates, bullet token-shingles present). Byte-equality is not required. Fail the build on drift.
- **Treat `base.tex` as read-only after import**, with an explicit re-import-on-demand + diff-review path.
- **Plan for the real `.tex` not decomposing cleanly.** Macro-heavy documents (`moderncv`, `awesome-cv`, custom `\newcommand` resumes) can encode structure in macros rather than repeated environments. This is the largest unquantified cost in the plan (`FEATURES.md` Gap 5). Spike it on one section before estimating the tailoring phase; the acceptable fallback is to hand-author `cv.yaml` once and treat `base.tex` as a reference.

**Phase to address:** Phase 4 (fact store + import + golden reproduction test + spike).

**Evidence / confidence:** MEDIUM — the design is strongly corroborated (three OSS implementations plus two academic evaluations), but the *cost* is unknown because the `.tex` is not in this repo. LOW on whether it decomposes cleanly.

---

### P12: APScheduler configured so runs duplicate, disappear, or crash on serialisation

**What goes wrong:**
Four concrete failures, all documented upstream:
1. **Duplicate execution.** `uvicorn --workers 4` (or a second app replica / a debug-mode reloader) gives you N schedulers, each firing the same job — a documented case printed the job four times. A long scrape then runs concurrently against itself and invites rate-limiting.
2. **Duplicate jobs on every restart.** Scheduling jobs at startup against a persistent job store without an explicit `id` and `replace_existing=True` adds a new copy every restart.
3. **Pickle failures.** `SQLAlchemyJobStore` serialises the callable with pickle by reference, so bound methods, local functions, or instances holding locks/SSL contexts fail with `can't pickle _thread._local` / `SSLContext` — the job simply cannot be scheduled.
4. **Missed or doubled runs.** `misfire_grace_time`, `coalesce` and `max_instances` default to behaviour that drops a run after a laptop slept, or fires three times when it wakes, and a scheduler timezone differing from the system timezone can schedule a one-off job hours in the past or an hour off across DST.

**Why it happens:**
The defaults are designed for a single long-lived process, and the failure modes are invisible until the second worker, the restart, or the DST boundary.

**Warning signs:**
- `--workers` is anything other than 1, or a second container runs the app.
- `add_job` is called without an `id`/`replace_existing`.
- The scheduled function is a bound method or a closure.
- Scheduler timezone is unset (inherits container UTC).
- Two runs at the same minute in `runs`, or a `database is locked` error during a run.

**Prevention:**
- **Pin `--workers 1`** for v1 and document why; the Postgres advisory-lock escape hatch is for later (`STACK.md` Q5, `ARCHITECTURE.md` AP13).
- **Use a top-level module-level async function** as the job target, with an explicit `id` and `replace_existing=True`.
- **Set `coalesce=True`, `max_instances=1`, `misfire_grace_time=3600`, `timezone="Europe/Dublin"`** explicitly (`STACK.md` Q5).
- **Make the manual trigger and the cron call the same `run_pipeline()` callable** (Pattern 5), enqueued rather than inline.
- **Accept the two engines deliberately**: `SQLAlchemyJobStore` needs a sync engine while the app uses async — hold both against the same SQLite file, scoped clearly.

**Phase to address:** Phase 1/compose (workers=1, sync engine) and Phase 8 (scheduler wiring + "next run at…" UI).

**Evidence / confidence:** HIGH — each failure is documented in APScheduler's own docs (pickle requirement, `misfire_grace_time` semantics, deployment guidance on persistent stores) or its issue tracker (duplicate jobs across workers; `ConflictingIdError`/`replace_existing`; pickle of bound methods/SSLContext; DST bugs), corroborated by a Stack Overflow reproduction.

---

### P13: No way to test what depends on a live, hostile website — so nothing is ever verified

**What goes wrong:**
The scraper is only exercised by hitting the real site. CI either skips it or is flaky; a change to normalisation or dedup cannot be tested because it needs live data; and when a source breaks, there is no fixture to reproduce against. The team ends up with "it worked when I ran it" as the entire verification story, which is exactly the regime in which silent breakage (P1) thrives.

**Why it happens:**
Live-scraping tests are tempting because they test "the real thing". They are also slow, rate-limit the user's own IP, break on every site change, and cannot run in CI.

**Warning signs:**
- No saved HTML/payload fixtures in the repo.
- Tests marked skip-by-default because they hit the network.
- No golden/snapshot test on extraction output.
- Parser changes cannot be validated without a live call.

**Prevention:**
- **Save raw payload fixtures per source** (`tests/fixtures/listings/`) and unit-test parsing/normalisation/dedup offline and fast. `ARCHITECTURE.md` already reserves this directory.
- **Golden tests** for the extraction output (volatile fields ignored) and for the LaTeX renderer (same `RenderPlan` ⇒ same `.tex`).
- **Contract tests** on the output schema and on the opencode `/doc` field names, so a rename fails in CI.
- **A scheduled canary** (not part of the fast suite) that scrapes one fixed known URL and asserts a known answer, plus the source `probe()` for `/health`.
- Keep a small number of live integration tests that run rarely and deliberately, not on every commit.
- **Verification-stage fixtures** (`facts`, `patch`, extracted text → pass/fail) so the anti-fabrication checks are unit-testable with no LLM, no compiler, no network (`ARCHITECTURE.md` §10.1).

**Phase to address:** Phase 1 (fixture + probe + import-discipline tests) and Phase 2 (golden extraction tests). The verifier fixtures land with Phase 6.

**Evidence / confidence:** MEDIUM-HIGH — the fixture/golden/contract/canary split is the convergent recommendation across independent 2026 scraper-testing write-ups and several open-source toolkits.

---

### P14: Testing the happy path only, so the failure paths (which are the product) are unverified

**What goes wrong:**
The tests cover "a listing is fetched and stored" and "a CV renders". They do not cover: LinkedIn returning 429; JobSpy returning `id=None` for every row; a duplicated job across boards; a description containing `&`; the LLM returning an invalid patch; a merge that should be reverted; a blocked artefact never being downloadable; a run that fetched zero listings. Every one of those is a failure mode with a real user consequence, and every one is cheap to test with fixtures.

**Warning signs:**
Tests only ever pass against a happy-path fixture; no test is named for a 429, a null `id`, a cross-board duplicate, an `&`-in-description, an invalid patch, or a blocked artefact; the first time a failure path is exercised is during real use.

**Prevention:**
- Write the failure-path tests as part of the phase that introduces the feature, not after. The `ARCHITECTURE.md` "Looks done but isn't" style checks and §9.4 acceptance criteria are the checklist.
- Assert the negative guarantees explicitly: a `blocked` artefact returns 404/403 and cannot be linked from an application; a `partial` source does not abort a run; a false merge can be reverted and the job reappears.

**Phase to address:** every phase; first enforced in Phase 1.

**Evidence / confidence:** HIGH (general engineering discipline applied to the specific failure modes catalogued here).

---

## Moderate Pitfalls

Pitfalls that degrade quality, safety or trust without necessarily causing a rewrite. Each is cheap to prevent and annoying to discover late.

### M1: Pydantic/structured-output handling that crashes instead of degrading

**What goes wrong:**
The LLM returns valid JSON except for one enum, or truncated JSON, or a discriminator value that does not match. The naive handler lets the `ValidationError` propagate and kills the run (or the request), or silently stores a partial dict that downstream code then defends against with `if "score" in data`. Also common: a non-discriminated union producing four cascading errors instead of one useful one, and strict-mode surprises (a raw dict passed to `model_validate` raising on a value that `model_validate_json` accepts).

**Why it happens:**
LLM output is not typed until you validate it. Structured output is a strong constraint but not a guarantee (retry exhaustion yields a `StructuredOutputError`), and the natural unit-test path (a hand-built dict) differs from the wire path (a JSON string).

**Warning signs:**
A single bad LLM response crashes a run; downstream code contains defensive `if "field" in data` checks; union errors arrive as three or four cascading messages; the client has no contract test against `/doc`.

**Prevention:**
- Parse with `model_validate_json` (strict mode still coerces JSON-representable types like dates/tuples), and treat validation as a boundary concern in `llm/`, not in the domain (`ARCHITECTURE.md` §6.2).
- Use a discriminated union with a `Literal` tag and `Field(discriminator=...)` so only the matched variant is validated and the error is precise. Customise with `Discriminator(custom_error_type=..., custom_error_message=...)` if the default noise remains.
- Handle partial JSON explicitly with `pydantic_core.from_json(..., allow_partial=True)` and a `WrapValidator` that raises `PydanticUseDefault` for missing-only errors — so a truncated response degrades fields to defaults rather than failing the run. Only tolerate the error types you actually intend to.
- **A validation failure is a run outcome, not a crash.** Record it in `llm_calls` with `status='invalid'`, retry a bounded number of times at the backend, then surface it.
- Add a contract test against the installed opencode `/doc` for the structured-output field name (`format` vs `outputFormat` — `STACK.md` Open Q4). An upgrade that renames it should fail loudly in CI, not silently in production.

**Phase to address:** Phase 3 (LLM port + structured output), exercised properly in Phases 5–6.

**Evidence / confidence:** MEDIUM (Pydantic v2 docs via Context7 — discriminated unions, partial JSON, validation errors; corroborated by `ARCHITECTURE.md` §6.2 and `STACK.md` Q7).

---

### M2: Chasing a 100% ATS match score / keyword-stuffing the tailored CV

**What goes wrong:**
The match score becomes the goal, and the tool (or the user) stuffs the CV with keywords until coverage hits the top of the range. The result reads like the job ad played back, recruiters and ATS platforms flag it, and Workday/Greenhouse-style parsers penalise skill lists with no corroborating bullet evidence. Jobscan itself recommends roughly 75% and warns about over-optimisation, noting it may not be possible to score above 75% "without overstuffing your resume with keywords".

**Why it happens:**
A visible number with a ceiling invites maximisation. It is also the easiest thing to demo.

**Warning signs:**
The UI celebrates a rising match percentage; the tailored CV reads like the job ad played back; skills lists appear with no bullet evidence; a "maximise ATS" control exists.

**Prevention:**
- Target honest **60–80% coverage of requirements you can truthfully claim**; surface the rest as gaps, not padding (`FEATURES.md` AF-5, DF-7).
- Keep the gap checklist a first-class *finding* (interview prep / cover-letter topic), never an input back into generation.
- Make the ATS/parse check a **warning** (single column, standard headings, parseable dates), not a score to maximise (`ARCHITECTURE.md` check 9).

**Phase to address:** Phase 6.

**Evidence / confidence:** MEDIUM — vendor documentation (Jobscan) with independent corroboration on over-optimisation penalties.

---

### M3: Letting JobSpy (and Tectonic) block the single event loop

**What goes wrong:**
JobSpy is synchronous and uses a `ThreadPoolExecutor` internally; Tectonic is a subprocess. Running either directly on the asyncio event loop inside the single uvicorn worker freezes the HTTP server for the duration of a scrape or compile. The UI "feels dead", requests time out, and it looks like a crash. This is listed as the *first* real scaling pain (`ARCHITECTURE.md` §15.1).

**Warning signs:**
- The browser tab hangs while a run is in progress.
- A `/health` request takes seconds during a run.
- The pipeline is awaited inline in a request handler (`ARCHITECTURE.md` AP6).

**Prevention:**
- Wrap blocking calls with `asyncio.to_thread` / `run_in_executor`.
- Enqueue the pipeline and return immediately; surface progress via the `runs` table and opencode SSE (`ARCHITECTURE.md` Pattern 5, AP6).
- Consider a separate worker container later; the adapter interface and `run_pipeline()` callable make that a deployment change, not a rewrite.

**Phase to address:** Phase 1 (background the pipeline, isolate blocking calls).

**Evidence / confidence:** HIGH (direct consequence of the chosen stack; `STACK.md` Q2/Q5, `ARCHITECTURE.md` §15.1).

---

### M4: Search that degrades into `LIKE '%term%'`, or an FTS index that drifts

**What goes wrong:**
Queue search is implemented with `LIKE` on the description, which cannot use an index and gets slower as the corpus grows; or an FTS5 external-content table is created but never kept in sync, so searches miss newly added listings or return deleted ones. Also: `ENABLE_FTS5` is checked on the developer machine but not in the container's SQLite build.

**Warning signs:**
Any `LIKE '%...%'` on a description column; search results missing a listing that was just added; search latency rising with corpus size; `ENABLE_FTS5` never asserted in the container.

**Prevention:**
- FTS5 + BM25 (`rank`), never `LIKE '%term%'` (`STACK.md` Q4). Verify `PRAGMA compile_options` includes `ENABLE_FTS5` in the container.
- Keep the external-content index in sync with triggers or SQLAlchemy `after_commit` listeners, and test that a newly inserted listing is searchable.
- Keep FTS behind the `search` port with a documented Postgres `tsvector`+GIN alternative.

**Phase to address:** Phase 2.

**Evidence / confidence:** HIGH (SQLite FTS5 reference + standard practice).

---

### M5: Scheduler timezone/misfire mistakes that silently skip the morning run

**What goes wrong:**
See P12 for the full scheduler pitfall. The specific moderate version here: the container runs UTC, the user is Europe/Dublin, and the "7am run" fires at 8am local for half the year, or DST shifts it; or a job missed while the machine slept is dropped because `misfire_grace_time` is unset; or three missed runs fire three times because `coalesce` is off.

**Warning signs:**
The "next run at…" time does not match the user's local expectation; duplicate `runs` rows on the same day; no run happens after the laptop slept; multiple firings after a long downtime.

**Prevention:** explicit `timezone="Europe/Dublin"`, `coalesce=True`, `max_instances=1`, `misfire_grace_time=3600`, `replace_existing=True` (`STACK.md` Q5). Surface "next run at…" in the UI so the user can see it is correct.

**Phase to address:** Phase 8 (scheduler) — but the settings are decided in the Phase 1/compose config.

**Evidence / confidence:** HIGH (APScheduler docs list these effects explicitly; multiple upstream timezone issues).

---

### M6: Multi-user at friends-scale leaks data through a missing scope

**What goes wrong:**
v1 is single-user with no auth, which is correct. But when friends are added, the most common leak is a query that forgot the owner predicate — one missing `WHERE user_id = ?` or an unscoped join returns another person's CV, applications, or notes. A close second is a module-level cache or global that holds one user's data and serves it to the next request. CVs and job-search data are sensitive personal data, and the self-hoster is the data controller for friends' CVs.

**Why it happens:**
"I'll add auth later" is usually read as "I'll add a login page later". The login page is the cheap part; the data scoping is the expensive part (`ARCHITECTURE.md` §11.2 says this explicitly).

**Warning signs:**
- Repository/service functions take no user argument and read the global DB.
- Any module-level mutable state keyed by nothing user-specific.
- No plan for deletion/erasure of a friend's data, or data in logs.

**Prevention:**
- `Depends(current_user)` on every route from day one (cheap, no behaviour change).
- Thread an explicit `user`/`user_id` argument through repository/service calls **at the service layer** now, without adding the column yet — the call shape carries the user, the schema does not. Add the column in a bounded migration when auth arrives (`ARCHITECTURE.md` §11.2).
- Do not store recruiter PII from listings at all (see S5).
- Keep CV/application content out of logs and define a deletion/retention path before the first friend onboards.

**Phase to address:** Phase 1 (the seam), Phase 8 (the migration when multi-user actually ships).

**Evidence / confidence:** MEDIUM-HIGH (the shared-schema tenant-leak pattern and module-level-cache leak are documented across vendor security guidance and GDPR hosting write-ups; the route seam is verified against FastAPI docs).

---

### M7: Cover letters (and any other generated artefact) bypassing the evidence guardrail

**What goes wrong:**
Tailoring is verified; the cover letter is generated by a separate prompt with its own fact extraction, and is therefore not covered by the anti-fabrication schema or the PDF verifier. The honesty guarantee has a hole exactly where the most free-form prose is generated.

**Warning signs:**
A second prompt builds its own fact extraction; a generated artefact is downloadable without a verification record; the honesty guarantee is described as covering "the CV" but not the letter.

**Prevention:**
- Any generated artefact must reuse the same `CvFacts` evidence IDs and go through the same verification pattern (`FEATURES.md` TS-18). If it cannot be structured, it must be human-reviewed before use.
- Never build a second fact-extraction path.

**Phase to address:** Phase 6 (design the seam) / when the cover letter is actually built (v1.x).

**Evidence / confidence:** MEDIUM (direct extension of the anti-fabrication design; `FEATURES.md` flags this explicitly).

---

### M8: SQLite configured by default (no WAL, foreign keys off, FTS5 unverified, backups that lose the WAL)

**What goes wrong:**
SQLite defaults to `journal_mode=DELETE` and `foreign_keys=OFF`, so concurrent reads block during writes and referential integrity is silently not enforced. A backup that copies only `jobsearch.db` while `-wal` holds committed-but-uncheckpointed data restores a database missing recent writes. `busy_timeout` unset means contention surfaces as immediate `database is locked` errors.

**Warning signs:**
`database is locked` errors; foreign-key violations not being caught; a restored backup missing the most recent run's writes; FTS5 unavailable in the container.

**Prevention:**
- Set `journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON`, `busy_timeout=5000` on every connection (`STACK.md` Q4).
- Back up the database **and** its `-wal`/`-shm` files, or use SQLite's proper online-backup mechanism; test a restore.
- Verify `ENABLE_FTS5` in the container.

**Phase to address:** Phase 1.

**Evidence / confidence:** HIGH (SQLite documentation; `STACK.md` Q4).

---

### M9: Model/version drift between ranking and tailoring changing quality and cost silently

**What goes wrong:**
A model is auto-upgraded or a default changes, and the ranking scores or tailoring output shift with no code change. A documented LLM-system failure class is "version drift" and "cost-driven performance collapse" — the price-per-token and the behaviour both change underneath you. pinning the opencode image matters for the same reason the structured-output field name must be contract-tested (`STACK.md` Q8).

**Warning signs:**
Scores or tailoring quality shift with no code change; a run's cost changes while criteria and model settings look unchanged; the opencode image is a floating tag; no `/doc` contract test in CI.

**Prevention:**
- Record `backend`, `provider`, `model`, `agent` on every `scores` and `cv_artifacts` row so a regression is traceable to a model change.
- Pin the opencode server version and run the `/doc` contract test in CI.
- Treat ranking and tailoring as deliberately different model choices, recorded per call (`ARCHITECTURE.md` §6.4).

**Phase to address:** Phase 3 (pinning + contract test), Phase 5/6 (recording).

**Evidence / confidence:** MEDIUM (arXiv taxonomy of LLM-system failure modes incl. version drift; `STACK.md` Q7/Q8).

---

### M10: Exposing the opencode server or the app to the LAN without protection

**What goes wrong:**
opencode exposes high-privilege surfaces — `POST /session/:id/shell`, `/file/*`, `/find/*`, permissions endpoints. Publishing its port, running without `OPENCODE_SERVER_PASSWORD`, or enabling `--mdns` turns a local dev tool into a remote code execution surface. The app itself has no auth in v1, so exposing its port exposes everything.

**Warning signs:**
Port 4096 is in the host `ports:` list; no `OPENCODE_SERVER_PASSWORD`; `--mdns` appears in the command; the app port is reachable from another device on the LAN.

**Prevention:** bind opencode to the compose network only, never publish its port, set `OPENCODE_SERVER_PASSWORD` even locally, do not enable `--mdns`, add `--cors` only for the exact origin, and keep the app local-only in v1 (`STACK.md` Q7/Q8, `ARCHITECTURE.md` §6.3).

**Phase to address:** Phase 1 (compose shape).

**Evidence / confidence:** HIGH (opencode's own server documentation; `STACK.md` Q7).

---

## Minor Pitfalls

### m1: `pip install python-jobspy` pulls a stale LinkedIn parser
The PyPI package is behind the git repo, whose URL now redirects as the project moved. Install from git and pin a commit (`STACK.md` Q1 correction #2). Otherwise you ship a parser that breaks on date formats the maintained repo already fixed. *Warning sign:* the LinkedIn date parser fails on new postings while the repo's `main` already has a fix. **Phase 1.**

### m2: Tectonic/biber version mismatch and VFS bug on bind mounts
Tectonic 0.17's bundled `biblatex` requires biber 2.17; Debian's apt biber 2.18 is too new. Combined with the VFS re-open bug on mounted volumes, the fix is the temp-dir compile pattern and an explicit biber pin. Only bites if the CV has a bibliography. *Warning sign:* a bibliography compile fails on a mounted volume but succeeds when run locally. **Phase 4.**

### m3: Adzuna free-tier quota exhausted by a broad query matrix
~1,000 calls/month (≈33/day) disappears fast across many criteria. Cache aggressively, keep a quota ledger, and never call it per view (`STACK.md` Q1, `FEATURES.md` DF-14). Exhausting it also removes the project's best hedge when scraping degrades. *Warning sign:* the quota ledger hits its ceiling mid-month, or a broad criteria set fans out one call per term. **Phase 8.**

### m4: Front-end assets loaded from a CDN
A local self-hosted tool must work with no internet. Vendor HTMX, Alpine and the compiled Tailwind output as static files (`STACK.md` Q8). *Warning sign:* the UI breaks or loses styling when the machine is offline. **Phase 1.**

### m5: Trusting job descriptions as data and putting them in the system prompt
Job listings are attacker-controllable; anyone can post a job. Listing content belongs in the user turn, fenced and labelled untrusted, never in `system`; tool access should be denied by default on those calls. Instruction-like text found in a listing is a *finding to record*, not an instruction (`STACK.md` Q7, `ARCHITECTURE.md` §6.3). *Warning sign:* listing text is interpolated into the system message, or a listing-driven session has tools enabled. **Phase 3/5.**

### m6: Salary/currency normalisation done ad hoc
Listings mix intervals (hour/day/month/year), currencies, and predicted-vs-actual salaries (`salary_is_predicted` on Adzuna is common). Normalise to annual at ingest, record the source, and never compare raw strings. *Warning sign:* a salary filter behaves inconsistently because some listings are hourly or a different currency. **Phase 2.**

### m7: Ghost/duplicate inflation mistaken for market signal
A single opening can appear 10–50 times across the syndication chain; a naive "how many openings for this role?" count is meaningless without dedup. Do not surface raw counts as insight until dedup is trusted. *Warning sign:* a "market insight" count collapses by 90% once duplicates are collapsed. **Phase 2/8.**

### m8: Treating the LLM rationale as the explanation
The factor table is the explanation; the prose is a supplement (see P5). Rendering only the prose hides the actual ranking logic and makes the "why" unverifiable. *Warning sign:* the UI shows a paragraph of rationale but not the factor scores or weights. **Phase 5.**

### m9: Forgetting that `id` from JobSpy can be `None`
Already covered as P3/`ARCHITECTURE.md` A2, repeated here because it is easy to miss: a `UNIQUE` constraint on a nullable column permits unlimited NULLs, so the Tier-1 key silently does nothing on boards that omit IDs. *Warning sign:* duplicates multiply on a board despite the unique index appearing to exist. **Phase 1/2.**

### m10: A single global "last run" instead of per-search
A single global `last_run_at` breaks the "new since your last check" computation as soon as there is more than one saved search (`ARCHITECTURE.md` §9.1). *Warning sign:* the new-since badge is wrong or empty once a second search is added. **Phase 1 (schema).**

---

## Technical Debt Patterns

Shortcuts that look reasonable in week one and cost a rewrite, a migration, or a trust failure later. "Acceptable" is judged against this project's scale (1–5 users, local Docker).

| Shortcut | Immediate Benefit | Long-Term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Import JobSpy directly in domain/service code | One import, no adapter ceremony | Every board breakage becomes a codebase-wide risk; the escalation ladder becomes untestable; per-board health impossible | **Never** — `sources/_jobspy_transport.py` is the only importer (`ARCHITECTURE.md` AP1) |
| Let the LLM emit `.tex` or prose | Fastest possible tailoring demo | Fabrication by construction; no diff; no verification hook; unauditable | **Never** (`FEATURES.md` AF-6, `ARCHITECTURE.md` AP2) |
| Store one opaque `score` per listing | One column, simple UI | Weight sliders, fit breakdown and cheap re-ranking each require a paid LLM call; the most expensive thing to retrofit | **Never** — store per-factor `φ_f` + weights (`ARCHITECTURE.md` AP3) |
| Dedupe by exact URL and `DELETE` the loser | Table stays clean; trivial | Misses all cross-source duplicates; a false merge destroys a real job with no recovery | **Never** — two-tier, merge-not-discard, reversible (`ARCHITECTURE.md` AP5) |
| Filter or cap each source before merging | Bounds memory; simpler batch | Discards the duplicate copy that carried the salary/description; merged record is worse than either input | **Never** — fetch fully → merge → filter/cap (`ARCHITECTURE.md` AP4) |
| Add tracking columns "when we need them" | Smaller first migration | `first_seen_at`, `last_seen_at`, `content_hash` and event rows describe the past — they cannot be invented later | **Never** (P8) |
| Skip verification until after tailoring ships | Ships the visible feature sooner | Ships a fabrication window in exactly the product whose ethical line is "never fabricate" | **Never** (`FEATURES.md` §7.5) |
| Run the pipeline inline in a request handler | No background machinery | LLM ranking takes minutes; the request times out, the UI hangs (`ARCHITECTURE.md` AP6) | Only for a throwaway probe script, never the app |
| Global `last_run_at` | One field | Breaks "new since" as soon as there is a second search | Only if there is provably ever one search — not this project |
| Defer the auth seam and add `Depends(current_user)` later | One less dependency | Every route changes when auth arrives; data scoping gets harder to thread retroactively | **Never** — the seam is free (`ARCHITECTURE.md` AP14) |
| Pre-add `user_id` columns "for later" | Feels future-proof | Complexity now, a guessed multi-tenancy model, every unique constraint complicated | **Never** — thread the user at the service layer, add the column later (`ARCHITECTURE.md` §11.2) |
| Local-only retention, no deletion path for friends' CVs | Nothing to build | The self-hoster is the data controller; a deletion request has no implementation | Acceptable *only* while genuinely single-user; must exist before friend #1 |
| One adapter class with `site_name=["linkedin","indeed"]` | Fewer classes | No per-board health, budget, capability or failure attribution; blocks per-board escalation | **Never** (`ARCHITECTURE.md` A3/AP16) |
| Wide `listings` table with a column per board field | Easy to query per field | Schema churn on every new source; contradicts "adding a source adds rows, not schema" | **Never** — `source_extras_json` (`ARCHITECTURE.md` AP15) |

---

## Integration Gotchas

Common mistakes when wiring this project's external dependencies.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| **JobSpy** | Importing it in domain/service code; calling it once with `site_name=["linkedin","indeed"]`; relying on `id` being non-null; persisting its `emails` field | Only `_jobspy_transport.py` imports it; one call per board; treat `id` as nullable and add the canonical-URL fallback key; `RawListing` has no email/phone field, sanitise at the boundary |
| **JobSpy (rates)** | Treating the README's "Indeed has no rate limiting" as true; retrying 429s harder | The same README contradicts that claim ("all boards are aggressive"); design for blocking on both; back off and record the block, do not escalate |
| **opencode `serve`** | Assuming the structured-output field is stable (`format` vs `outputFormat`); using server defaults for model/agent; leaving tools enabled on listing-driven calls | Verify against your own `/doc` and add a contract test; pass `model`/`agent` explicitly per call; `tools=[]` by default; never put listing text in `system` |
| **opencode `serve` (exposure)** | Publishing port 4096, no password, `--mdns` on | Bind to the compose network only, set `OPENCODE_SERVER_PASSWORD`, no mDNS, `--cors` only for the exact origin |
| **Tectonic** | Compiling with a cold cache; passing the mounted dir directly (biber VFS bug); `-Z shell-escape`; assuming the real preamble compiles | Prime the cache at image build; stage → compile in a temp dir → copy out; never shell-escape; spike the real `.tex` before estimating the phase |
| **Tectonic/biber** | Installing apt biber 2.18 | Pin biber 2.17 (Tectonic 0.17's bundled biblatex requires it); only matters if the CV has a bibliography |
| **SQLite** | Default `journal_mode`, `foreign_keys=OFF`, unset `busy_timeout`, copying only the `.db` for backup | WAL + `foreign_keys=ON` + `busy_timeout`; back up the `-wal`/`-shm` too or use online backup; verify FTS5 in the container |
| **APScheduler** | `--workers > 1`; no explicit job `id`; scheduling a bound method or closure; scheduler timezone left at UTC | `--workers 1`; top-level module function + `replace_existing=True`; explicit `id`; `Europe/Dublin` explicitly; success/failure is a `runs` row, never an exception into the scheduler |
| **Adzuna** | Per-view live calls; ignoring quota | Cache enrichment; keep a quota ledger; `~1,000 calls/month` is easily exhausted by a broad query matrix |
| **LinkedIn / Indeed** | Adding credentialed fallback when blocked; solving CAPTCHAs | Public logged-out surface only; no auth bypass, no CAPTCHA solving; stop and rest on the stop signals |
| **Pydantic + opencode** | Parsing a raw dict under `strict=True`; non-discriminated unions; letting `ValidationError` crash the run | `model_validate_json`; discriminated unions with a `Literal` tag; validation failure is a recorded run outcome with bounded retry |
| **Jinja2 + LaTeX** | Default delimiters; unescaped interpolation | Separate LaTeX environment (`\VAR{}`/`\BLOCK{}`); mandatory `escape_tex` (backslash first); document the single-brace block limitation |

---

## Performance Traps

Patterns that work at demonstration scale and degrade as the corpus grows. None of these is a 1M-user concern; all are realistic at a few thousand listings and a handful of users.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| **O(n²) fuzzy dedup** — comparing every listing to every other | Dedup stage time grows super-linearly as listings accumulate; a full run takes minutes and keeps growing | Blocking key (`company_token`, `title_token_set_signature`) with an index so Tier 2 compares only within buckets (`ARCHITECTURE.md` §9.2) | Noticeable around low thousands of active listings |
| **Context accumulation / re-sending the full CV and system prompt per listing** | Per-run token count scales faster than the listing count; a widened criteria burns budget | Batch prompting that shares one system prompt; stable prompt prefix for caching; trim context; bound output | As soon as ranking runs over tens of listings per run |
| **Unbounded retry loops that re-send failure context** | Cost spikes exactly when things go wrong; failed trajectories compound | Circuit breaker at the orchestrator; strip failed trajectories before retry; cap retries; a per-run call ceiling | On the first sustained provider error |
| **`LIKE '%term%'` search** | Search slows as the corpus grows; no index use | FTS5 + BM25 `rank` | A few thousand rows |
| **Blocking the event loop with JobSpy/Tectonic** | UI freezes for the duration of a run; requests time out | `asyncio.to_thread` / `run_in_executor`; background the pipeline; later a worker container | From the first real run (P3/M3) |
| **Cold Tectonic cache** | First compile after a rebuild takes minutes or fails offline | Prime the cache at image build | Every container build / fresh checkout |
| **Optional browser runtime in the default image** | Image grows by hundreds of MB and build time balloons; memory pressure during runs | Keep `invisible-playwright` as an opt-in extra / separate image, not the default path (`STACK.md` Q1 rung 3) | At image-build time, immediately |
| **Pandas/numpy weight from JobSpy in the FastAPI image** | Image ~hundreds of MB heavier; memory footprint grows per run | `--no-deps` install with minimal deps, or isolate JobSpy in a separate worker (`STACK.md` Open Q8) | At build time; revisit after Phase 1 measures duration and memory |

---

## Security Mistakes

Domain-specific security issues beyond generic web hardening. Risk is relative to a local, single-user v1 with a path to a few friends and possibly a hosted instance.

| Mistake | Risk | Prevention |
|---------|------|------------|
| **Scraping with the user's logged-in LinkedIn/Indeed session** | Personal account restriction or permanent ban (P2); ToS and computer-misuse exposure; possible IP blacklist | Public logged-out surface only; never store real credentials or session cookies; assisted apply with a human submit |
| **Persisting recruiter/hiring-manager PII from listing payloads** | GDPR/UWG exposure for zero product value (emails, phones, names) | `RawListing` has no such field; strip emails/phones at the sanitise boundary; never store personal identifiers |
| **Listing text treated as instructions, or fed to a tool-enabled session** | Prompt injection → tool abuse (the opencode server exposes `/session/:id/shell` and `/file/*`) | Untrusted content in the user turn only, fenced and labelled; `tools=[]` by default; schema-constrained output; lock down the agent/permission config; record instruction-like text as a finding |
| **opencode server exposed on the LAN / no password** | Remote code execution via shell/file endpoints | Compose-network only, port unpublished, `OPENCODE_SERVER_PASSWORD` set, no `--mdns` |
| **App port exposed with no auth** | v1 has no authentication; exposure = full access to CVs and personal data | Local-only in v1; no public exposure until the auth milestone |
| **Tectonic `-Z shell-escape` enabled** | Arbitrary code execution on LLM-influenced content | Default it off explicitly; sanitise the preamble; never enable it |
| **CV/application content in logs** | Sensitive PII (and, for friends, another person's data) written to disk and log aggregators | Keep CV/application content out of structured logs; log IDs and counts, not prose; scrub at the logging boundary |
| **Unscoped queries / module-level caches when multi-user arrives** | Cross-tenant leak of one friend's CV into another's view | Thread an explicit user through service calls now; scope every query by owner; never hold user data at module scope |
| **No deletion/retention path for friends' data** | A GDPR erasure request the self-hoster cannot fulfil; backups retain data past its life | Define retention + deletion before friend #1; treat backups as in scope; document the path |
| **Naive `pickle` in the scheduler job store on untrusted input** | Deserialisation risk if the job store data is tamperable | Trust the local SQLite job store or switch to a non-pickle serialiser (`CBORSerializer`/`JSONSerializer`) if the store is ever externalised |

---

## UX Pitfalls

How this category of tool loses its user. Each entry is the documented failure mode, the user impact, and the better approach already in the design.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| **Per-listing notifications** | Alert fatigue; the channel gets muted; the one important alert is missed | One batched digest per run (N new, top M high-scoring); never per-listing pushes (`FEATURES.md` §6) |
| **An empty queue with no explanation** | The user cannot tell "no matching jobs" from "the scraper is broken"; trust drops immediately | Runs UI + per-source counts + per-listing exclusion reasons; a failed/empty run must look like a failed/empty run (`FEATURES.md` TS-9) |
| **Duplicate flood across boards** | The feed looks padded; the user stops believing the list is deduplicated | Two-tier reversible dedup, merge-not-discard, "also seen on…" as a feature (`FEATURES.md` TS-3/DF-13) |
| **A score with no explanation, or an explanation that does not match the score** | The user cannot act on the ranking or learn what the tool optimises for | Per-factor breakdown with weights, visible factor table, grounded rationale over pre-computed evidence (P5) |
| **Stale/ghost postings shown as live opportunities** | Wasted effort, and the user concludes "I'm not good enough" when the listing was dead | Fresh / Stale / Likely-dead badges; separate job-quality from candidate fit (`FEATURES.md` TS-17/DF-10) |
| **No "what's new since I last looked"** | The user has to re-read the whole queue daily; the habit does not form | New-since badge from `first_seen_at > last_run_at`, per named search (`FEATURES.md` TS-15) |
| **A bulk "apply to all selected" action** | Pushes toward the low-quality mass application the project exists to avoid; also the velocity signature detection looks for | Per-listing application package; no bulk submit, ever (`FEATURES.md` AF-14) |
| **Autofilled screening answers that are wrong at scale** | Silent knockouts (wrong salary band, wrong work-authorisation answer) repeated across many applications | Draft answers only; explicit confirmation for structured questions (`FEATURES.md` AF-2) |
| **"Applied" shown with no link to what was sent** | The user cannot recall which CV went where; the version↔outcome link is lost | `applications.cv_artifact_id`; the exact PDF retrievable; blocked artefacts never linkable (`FEATURES.md` DF-9) |
| **Gaps hidden or disguised as matches** | The user is surprised in the interview; the tool's honesty claim is damaged | Explicit gap checklist with `direct / transferable / adjacent / gap` labels, never fed back into generation (`FEATURES.md` DF-7) |
| **A one-page CV silently reflowing to two pages after tailoring** | A quality regression the user did not choose | Assert `page_count <= max_pages` and surface it as a **warning finding**, never auto-truncate (`ARCHITECTURE.md` CV-R3) |
| **Search/filters that cannot actually narrow the list** | The strongest measured driver of job-search UX is relevance and filtering; poor filters alone lose the user | In-app FTS, editable criteria, one-click "hide jobs like this" (`FEATURES.md` TS-4/TS-6) |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing the piece that makes them safe. Use during phase verification.

- [ ] **Source adapter:** Looks done when it returns listings. Verify it also returns `partial`/`blocked` gracefully, writes a politeness-ledger row, declares per-board capabilities, and that `probe()` reports health. (P1, P10)
- [ ] **Dedup:** Looks done when duplicates collapse. Verify the `canonical_url` fallback key exists, merges are recorded with a pre-merge snapshot and are **revertible**, and the merge-rate metric is published with a rows-behind-it view. (P3)
- [ ] **Hard-rule filter:** Looks done when it excludes listings. Verify **every** rejection writes a `listing_exclusions` row with the rule id and reason, and that it runs **before** any LLM call. (P4, P9)
- [ ] **Ranking:** Looks done when it produces scores. Verify per-factor `φ_f` + weights + `criteria_version` are stored (not just a total), the task is absolute scoring not relative ranking, and a stability check has been run. (P5)
- [ ] **LLM client:** Looks done when a structured call returns. Verify the `/doc` contract test exists, validation failure is a recorded outcome with bounded retry, tools are denied by default, and listing text never enters `system`. (M1, S3)
- [ ] **CV fact store:** Looks done when `cv.yaml` exists. Verify the golden reproduction test passes (base render ≡ `base.tex` fact-equivalently) and that `base.tex` is treated as read-only. (P11)
- [ ] **Tailoring:** Looks done when the LLM returns a patch. Verify the schema has **no free-text field on the path to the PDF**, `apply_patch` rejects unknown IDs, and drops are explicit with reasons. (P6)
- [ ] **Verification gate:** Looks done when checks run. Verify a `fail` produces `compile_status='blocked'` that is **not downloadable and not linkable**, and that the pipeline never auto-repairs. (P6)
- [ ] **LaTeX compile:** Looks done when it compiles on the dev box. Verify the image primes the package cache, compiles offline, uses no shell-escape, and has a tested escape filter and TeX Live fallback. (P7)
- [ ] **Tailored PDF:** Looks done when the PDF downloads. Verify `page_count`, ATS parse checks, the change log, the `.tex` snapshot and hashes are stored, and a blocked artefact returns 404/403. (P7, UX table)
- [ ] **Application tracker:** Looks done when status changes save. Verify `applications.cv_artifact_id` is set, `application_events` is append-only, and `next_action_at` is computed. (P8)
- [ ] **Scheduler:** Looks done when the cron fires. Verify `workers=1`, explicit job `id` + `replace_existing`, `coalesce`/`max_instances`/`misfire_grace_time`, `Europe/Dublin`, a top-level job function (no bound methods), and "next run at…" in the UI. (P12)
- [ ] **Run pipeline:** Looks done when it completes. Verify a single source failing yields `status='partial'` rather than an abort, and that one CV failing to compile does not stop the batch. (P10)
- [ ] **Multi-user seam:** Looks done when routes have `Depends(current_user)`. Verify service/repository calls already accept a user, CV content is out of logs, and a deletion path is documented. (M6, S7)
- [ ] **Queue UI:** Looks done when it lists jobs. Verify new/stale badges, a "why not in my queue" path, and that an empty queue explains itself. (P9)

---

## Recovery Strategies

When a pitfall bites despite prevention, how to recover — and what recovery honestly costs.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| **P1 Scraper breaks silently** | MEDIUM | Read the source-status panel and `runs` per-source counts; compare fill rates against baseline; classify fetch (block/CAPTCHA) vs parse (selector) from the captured fixture; patch the selector/transport for that adapter only; re-run. If it is a block, back off and lean on Adzuna rather than escalating. |
| **P2 Account restricted/banned** | HIGH (personal) | Stop all automation on that account immediately; comply with any identity-verification/lock flow; do not retry from the same IP; treat a permanent ban as unrecoverable (IP blacklist). Remove any credentialed code path from the project permanently. This is the one pitfall where the recovery cost is largely outside the tool. |
| **P3 False merge / duplicate flood** | LOW if reversible, HIGH if deletes happened | If `listing_dupes` + `snapshot_json` exist: revert the merge, the job reappears. If rows were deleted: re-run the fetch to re-ingest, and accept that `first_seen_at`/events for those rows may be wrong or new. Then tighten/loosen θ and add a tuning task. |
| **P4 Cost blowup** | LOW–MEDIUM | Add the per-run ceiling and daily cap now; disable the offending path; re-run with a bounded candidate set; attribute spend from `llm_calls` by stage/model before re-enabling. |
| **P5 Ranking instability / sycophantic scores** | MEDIUM | Switch any relative-ranking call to bounded absolute scoring; add the factor table so instability is visible; widen the rubric wording against inflation; run the two-run stability check to quantify; consider a different model for ranking. |
| **P6 Fabrication reached a sent CV** | HIGH (reputational) | The verification gate should have blocked it — if it did, fix the check and re-render. If it did not, stop, tell the user, withdraw/correct the application, then add the missing check (no-new-entity / metric containment / bullet conservation) and re-run all artefacts through it. Never "repair" the claim in place. |
| **P7 LaTeX image/compile failure** | LOW–MEDIUM | Prime/extend the cache or add the missing package; if a package is unavailable, switch `LATEX_ENGINE=texlive` with the curated subset; sanitise pdfTeX-only primitives; add the missing `escape_tex` case (this is almost always escaping). |
| **P8 Missing history/columns** | HIGH (unrecoverable) | There is no true recovery for unobserved history. Add the column now; accept that historical values are null/unknown; where possible reconstruct the present state (e.g. derive `is_active` from the next run) and explicitly mark the gap rather than fabricate it. This is why P8 is a Phase-1 gate. |
| **P9 User lost trust in the queue** | MEDIUM–HIGH | Make the run explain itself (counts + exclusion reasons); surface freshness/ghost badges; de-duplicate visibly; add the "new since" delta; stop per-listing notifications. Trust returns slowly — the fix is observability, not a redesign. |
| **P12 Scheduler duplicates/misses** | LOW–MEDIUM | Verify `workers=1` and a single replica; add explicit `id` + `replace_existing`; move the job to a top-level function; set `coalesce`/`max_instances`/`misfire_grace_time`/timezone; investigate duplicate `runs` rows and `database is locked` errors. |
| **M6 Cross-user data leak** | HIGH (privacy) | Stop the exposure; identify the unscoped query/cache; add the owner predicate everywhere it applies; tell affected friends honestly; add the deletion path if it was missing. |
| **M8 Corrupt/partial SQLite restore** | MEDIUM | Restore with the `-wal`/`-shm` files or via online backup; if WAL data is lost, the last committed writes are gone — re-run the pipeline to re-derive listings (events/history for the gap are lost). Enable WAL/backup properly before the next cycle. |

---

## Pitfall-to-Phase Mapping

How the eight suggested phases prevent these pitfalls, and how to verify the prevention worked. Phases follow `ARCHITECTURE.md` §14.3.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| **P1 Scraper death / silent zero** | Phase 1 (probe, total fetch, source status); Phase 2 (`runs`/exclusions); Phase 8 (health UI) | A deliberately broken fixture returns `partial`/`blocked`, not a crash; a zero-result run is explainable from `runs`; fill-rate metric drops visibly when a fixture selector is renamed |
| **P2 Account ban** | Phase 1 (never build the credentialed path); continuous | Code search finds no credential/session path; the adapter has no CAPTCHA/auth surface; run volumes are within the configured `FetchBudget` |
| **P3 Dedup failure** | Phase 1 (keys in migration 0001); Phase 2 (tier 2, audit, tuning) | A seeded false merge is revertible and the job reappears; a seeded cross-source duplicate merges; merge rate is within the sanity band and the rows are inspectable |
| **P4 LLM cost blowup** | Phase 2 (filter + counters); Phase 5 (batching + caps) | A run with a widened candidate set still costs within the cap; `llm_calls` attributes spend per stage; a cap breach refuses calls rather than overshooting |
| **P5 Ranking bias/instability** | Phase 5 | Two-run stability check reports variance and rank change; every score stores `φ_f` + weights + versions; no relative-ranking call exists |
| **P6 CV fabrication** | Phase 4 (fact store) + Phase 6 (verification with tailoring) | An injected fabricated employer/metric fails the verifier and produces a `blocked`, non-downloadable artefact; a `direct` gap with no evidence ID is rejected |
| **P7 LaTeX pipeline** | Phase 4 (spike + primed cache) + Phase 6 | The real `.tex` compiles offline in the container; an `&`/`%` description renders; `shell-escape` is absent; compile failures are structured results |
| **P8 Un-backfillable data** | Phase 1 (migration 0001 per §9.4) | Schema review passes every §9.4 item; a new listing gets `first_seen_at`/`last_seen_at`/`content_hash`; a save writes an event row |
| **P9 Empty/stale/ghost queue** | Phase 2 (observability, badges) + Phase 5 (quality vs fit) | An empty run displays its counts and reasons; a listing older than the threshold shows Stale; quality score is displayed separately from fit |
| **P10 Monolithic run** | Phase 1 + Phase 6 | A simulated source failure yields `status='partial'` with the rest of the pipeline completing; a simulated compile failure does not abort the batch |
| **P11 Two CV truths** | Phase 4 | The golden reproduction test passes; editing `base.tex` after import is flagged; a non-decomposing section triggers the documented fallback |
| **P12 Scheduler duplication/miss** | Phase 1 (workers=1) + Phase 8 (wiring) | Restarting the app does not duplicate the job; a simulated missed window coalesces to one run; "next run at…" is correct for Europe/Dublin across a DST boundary |
| **P13 No offline scraper tests** | Phase 1 + Phase 2 | CI parses planted fixtures with no network; a schema contract test fails on a renamed field; a golden extraction test fails on a changed fixture |
| **P14 Happy-path-only tests** | Every phase, first enforced Phase 1 | 429, `id=None`, duplicate, `&`-in-description, invalid-patch and blocked-artefact cases all have passing tests before the phase is marked complete |
| **M1 Pydantic failure** | Phase 3 | A truncated-JSON fixture degrades to defaults; an invalid discriminator returns one precise error and a recorded outcome, not a crash |
| **M2 ATS over-optimisation** | Phase 6 | The UI targets 60–80% coverage and surfaces gaps; no "maximise score" affordance exists |
| **M3 Event-loop blocking** | Phase 1 | HTTP stays responsive during a simulated long run; blocking calls are wrapped |
| **M4 FTS degradation** | Phase 2 | A newly inserted listing is searchable; no `LIKE '%term%'` in the codebase; `ENABLE_FTS5` verified in the container |
| **M5 Timezone/DST** | Phase 8 (settings from Phase 1) | A DST-boundary test schedules the correct local time |
| **M6/m7 Multi-user & ghost inflation** | Phase 1 (seam) + Phase 8 | Service calls accept a user; no raw opening counts surfaced pre-dedup; a deletion path exists before onboarding |
| **M8 SQLite config/backup** | Phase 1 | PRAGMAs asserted at connection; a restore-from-backup test includes the WAL |
| **M9 Model drift** | Phase 3 + Phases 5–6 | The `/doc` contract test is in CI; every score/artefact records model and version |
| **M10 opencode exposure** | Phase 1 | The opencode port is unpublished; a password is set; no `--mdns` |
| **P7/S6 Tectonic shell-escape** | Phase 4 | A code/config assertion that `-Z shell-escape` never appears |

---

## Sources

**Primary — official docs, specifications and upstream trackers**

- JobSpy (`speedyapply/JobSpy`) — README (rate limits, ~1000 cap/query, "all boards aggressive with blocking") and issue tracker (#374 empty LinkedIn description, #370 `job_url_direct` missing, #112 rate limiter, #129 429 retry). GitHub, read 2026-09-15 — **HIGH**
- APScheduler 3.x documentation — `SQLAlchemyJobStore` (pickle serialisation of the callable by reference), `apscheduler.job` (`coalesce`, `max_instances`, `misfire_grace_time` semantics), user guide (persistent-store deployment requirements, DST/timezone guidance) — **HIGH**
- APScheduler issue tracker — #559 duplicate jobs / `replace_existing`, #421 `can't pickle _thread._local` / SSLContext, #133 and #87 timezone/DST scheduling bugs — **HIGH**
- Pydantic v2 documentation (via Context7) — `model_validate_json` and strict mode, discriminated unions and `Discriminator` custom errors, partial JSON with `pydantic_core.from_json(allow_partial=True)` + `WrapValidator`/`PydanticUseDefault`, `ValidationError` structure — **MEDIUM**
- LinkedIn Prohibited Software policy and 2026 enforcement summaries (connection-limit change to 100/week; 2025 restriction volume; progressive enforcement ladder) — **HIGH** on policy, **MEDIUM** on the numeric study figures reported by vendor pages
- Indeed partner/ToS documentation and the retired Publisher API (via `STACK.md` Q1) — **HIGH**
- Tectonic — project site/issue tracker (on-demand package fetch and offline failure, bundle contents question, biber/VFS bug references in `STACK.md` Q6) — **HIGH** on mechanism, **MEDIUM** on applicability to the unseen CV

**Academic / peer-reviewed**

- *Mitigating Fabrication in Multi-Stage LLM Pipelines for Hiring: An Empirical Evaluation of Prompt Guardrails and Human-in-the-Loop Checkpoints* (arXiv 2608.26171, Jul 2026) — 96.7% baseline fabrication; 86% reduction under guardrails; 50% residual; human checkpoint cuts JD-baited claims 47%→2%; >99% claim retention — **MEDIUM-HIGH**
- *Grounded Optimization* (arXiv 2607.01457) — five-layer anti-hallucination framework; four fabrication modes; cross-domain contamination at 79–89% of baseline incidents — **MEDIUM-HIGH**
- *Judging the Judges: A Systematic Study of Position Bias in LLM-as-a-Judge* (arXiv 2406.07791, v8/v9) — 15 judges, >150k instances; position bias varies by judge/task; primacy vs recency; strongly affected by the quality gap — **HIGH**
- *Evaluating Scoring Bias in LLM-as-a-Judge* (arXiv 2506.22316) — rubric order bias, score-ID bias, reference-answer score bias; a single in-context example shifts unrelated scores — **HIGH**
- *When Wording Steers the Evaluation: Framing Bias in LLM judges* (arXiv 2601.13537) — all 14 judges susceptible to predicate-positive/negative framing — **HIGH**
- *SycEval: Evaluating LLM Sycophancy* (AIES/arXiv 2502.08177) — 56–62% sycophancy under rebuttal; 78.5% persistence; regressive sycophancy — **HIGH**
- *Do LLM Evaluators Prefer Themselves for a Reason?* (arXiv 2504.03846) — harmful self-preference grows with model capability — **MEDIUM-HIGH**
- *Failure Modes in LLM Systems: A System-Level Taxonomy* (arXiv 2511.19933) — 15 hidden failure modes incl. version drift and cost-driven performance collapse — **MEDIUM**
- *Token Budgets: An Empirical Catalog of 63 LLM…* (Hugging Face papers 2606.04056) — agent budget overruns as a production failure class; parallel-call overshoot; estimator over-reservation — **MEDIUM**
- *A Framework for Duplicate Detection from Online Job Postings* (CIKM 2021, ACM) — 50–80% duplicate proportion cited; 60-day repost window — **MEDIUM**
- *A Survey of Text Deduplication* (IEEE, 2026) — false negatives pollute, false positives lose unique records — **MEDIUM**
- *Measuring Validity in LLM-based Resume Screening* (IASEAI 2026) and *Human and LLM-Based Resume Matching* (NAACL 2025 findings) — LLM scores correlate only minorly with human ratings and are unstable — **MEDIUM-HIGH**
- *Measuring Real-World Prompt Injection Attacks in LLM-based Resume Screening* (arXiv 2605.28999) — ~200K resumes; >90% of injections are data-only — **MEDIUM-HIGH**

**Engineering write-ups and tooling (MEDIUM–LOW; vendor-authored content flagged)**

- Scraper silent-failure and observability: link.sc (2026-07-18), PromptCloud (2026-04-08), Datahen (2026-07-03), Shifter (2026-08-04), ScraperGuard and `opensyndicate/scrapeguard` — per-domain success rate, field fill rate, schema drift, freshness, block-vs-parse classification — **MEDIUM**
- Scraper testing: Apify "Testing Web Scrapers: Fixtures, Mocks & Staging", `spinov001-art/automated-testing-scrapers` (snapshot/contract/canary/quality gates), datawookie (2025-01-26), golden-file management (QASkills 2026-08-07) — **MEDIUM**
- Indeed anti-bot reality: SpyderProxy (2026-05-10, "~20–30% block rate even with residential proxies; parse the embedded JSON"), dataimpulse (2026-09-06), ScraperAPI/Decodo pages — **MEDIUM**; several are proxy vendors and are treated as directional
- LinkedIn ban mechanics: connectsafely.ai (2026-05-16), linkednav.com (2026-05-19 / 2026-08-18 / 2026-09-10), linkedapi.io (2026-06-24), vayne.io (2026-04-28), linkedinpreview.com (2026-07-07) — directional; most sell competing tools — **MEDIUM/LOW**
- Job-board dedup at scale: DEV Community "The same job is posted on three boards" (2026-07-27, 10–15% merge-rate band, "print the rows"), CleanJobData (2026-07), Canaria (2026-03), JobDataLake (2026-04-18), LinkUp (2024-02-17) — **MEDIUM**
- LLM cost engineering: MachineLearningMastery "Identifying Token Costs Hiding in Your Agentic Loop", Palo Alto Networks AI cost observability (2026-09-04), Silicon Data (2026-01-22), budget-guard / llm-cost-guard packages — **MEDIUM**
- Playwright/stealth: Patchright and browser-scraper READMEs, Browserless "Bypass Cloudflare with Playwright" (2026-01-08), The Web Scraping Club (CDP detection), `playwright-cdp-probe` — **MEDIUM**
- Job-search UX/trust: MeasuringU SUPR-Q job-search UX study, UX Collective "Hey, LinkedIn: UX matters even for job searching" (2024-07-27), BBC Worklife ghost jobs (2024-03-19), Rochester Business Journal (2025-08-06), Employment Hero UK (2026-01-30), Forbes (2025-11-19) — **MEDIUM**; ghost-job figures are directional and several sources are commercially interested
- GDPR/multi-tenant isolation: DCHost multi-tenant GDPR architectures, Atlassian Forge tenant-isolation guidance (module-level cache leak), `n8n` self-hosted GDPR note (self-hoster is responsible for deletion) — **MEDIUM**
- APScheduler + FastAPI duplicates: Stack Overflow "single job instance across multiple workers" (2023), context-hub APScheduler doc (use `BackgroundScheduler`, tune `max_instances`/`coalesce`/`misfire_grace_time`, UTC-vs-local) — **MEDIUM**
- Job-search data quality: JobDataLake "Job Listing Data Quality" (2026-04-18), JobsPikr pipeline — **LOW–MEDIUM** (vendor).

**Inherited from the sibling research files (not re-verified here)**

- `STACK.md` — the JobSpy/Indeed/LinkedIn acquisition dead-end, the escalation ladder, legal posture (hiQ, GDPR, EU Database Directive), Tectonic vs TeX Live, the opencode endpoint/structured-output ambiguity, APScheduler settings, `compose.yml` shape.
- `FEATURES.md` — the anti-fabrication evidence base; the fetch→merge→filter ordering; dedup hierarchy and merge-rate band; ghost-job and notification findings; the ranking-bias cautions.
- `ARCHITECTURE.md` — the anti-patterns table (AP1–AP16), the §9.4 migration acceptance criteria, the verification check list, the auth-seam honesty note, and the eight-phase build order used for mapping above.

**Conflicting evidence, flagged (do not present as settled)**

- **"Indeed is the best scraper currently with no rate limiting"** (JobSpy README) vs the same README's "all of the job board sites are aggressive with blocking" vs multiple 2026 guides reporting Cloudflare bot management and datacenter-IP blocking on Indeed. **Unresolved; design for blocking on both boards.** Confidence in the Indeed claim: **LOW**.
- **Scraper-breakage detection numbers** (e.g. "23 times in my career", specific block-rate percentages) come from individual practitioners and vendor blogs. The *pattern* is corroborated across independent sources; the *numbers* are directional. **MEDIUM at best.**
- **Ban-trigger thresholds** (actions/day, profiles/hour, connection-request limits) are reported inconsistently across vendor pages and change over time. LinkedIn's own direction (stricter, progressive enforcement) is HIGH; the numbers are LOW–MEDIUM.
- **Ghost-job prevalence** (18–22%, "1 in 3", "30–40% of aggregator listings are duplicates or stale") is well-publicised but several sources sell competing services. Directional only.
- **APScheduler duplicate-job behaviour**: upstream issue discussion shows the store raises `ConflictingIdError` and the scheduler replaces the job, while the reporter saw a duplicate; the practical rule (explicit `id` + `replace_existing=True`; `--workers 1`) is corroborated regardless. Confidence in the mechanism: **MEDIUM**; in the fix: **HIGH**.

---

*Pitfalls research for: AI-assisted job search automation (local, self-hosted, Python-first, Dockerised)*
*Researched: 2026-09-15*
