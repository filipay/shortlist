# Phase 5 — UI Review

**Audited:** 2026-09-22
**Baseline:** abstract 6-pillar standards — **no `UI-SPEC.md` exists** in this phase dir or anywhere under `.planning/` (verified: `find .planning -name "*UI-SPEC*"` → empty). There is therefore no approved design contract to audit against; findings below are judged against the phase's own decision record (`05-CONTEXT.md` D-88…D-100), `05-REVIEW.md`, and general 6-pillar standards.
**Screenshots:** **not captured.** No dev server was running on 3000/5173/8080/8000. A boot was attempted on 3000; it failed at startup because the shipped default DB URL is `sqlite+aiosqlite:////data/jobsearch.db` (absolute `/data`, absent in this environment) while the real DB lives at `./data/jobsearch.db` (root-owned, not writable by the audit uid). Audit is therefore **code-only** (template + compiled-CSS + rendered-test analysis).
**Method:** template source, compiled `static/vendor/app.css` (Tailwind v4.3.3, 30 lines / 35 KB), and the phase's rendered-HTML tests. `tests/test_stylesheet_coverage.py`, `tests/api/test_listing_detail.py`, `tests/api/test_queue_ranked.py`, `tests/api/test_ranking_weights.py`, `tests/api/test_queue_ranking_adversarial.py` → **26 passed, 2 xfailed**.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 2/4 | `#ranking-strip` renders a numerator and denominator from **different populations** → routinely reads "Ranked 30 of 5" (CR-01, confirmed live in `routes.py:293`). |
| 2. Visuals | 3/4 | Clear hierarchy and all-labelled buttons, but the primary queue is an 8-column table that only horizontally scrolls on mobile, and the score badge carries no accessible context. |
| 3. Color | 2/4 | Three phase-5 token pairings **fail WCAG AA**: `req-met` 3.77:1, `badge-score-tier-high` 3.58:1, `badge-score-tier-low` 4.39:1. |
| 4. Typography | 3/4 | Coherent, modest size/weight set with a nice mono-for-numbers touch; verdicts and body share one size so hierarchy rests on colour alone. |
| 5. Spacing | 3/4 | Disciplined rem scale, no arbitrary `[Npx]` values; minor inconsistency between two chip padding scales. |
| 6. Experience Design | 2/4 | **Save/Hide on the detail page target an element that does not exist on that page** → the control silently does nothing (WR-04). No busy/disabled state on "Run search now". |

**Overall: 15/24**

Requirement read: **UI-01** (browse ranked list) structurally met but with a misleading coverage strip and a silent 5 000-row truncation; **UI-02** (detail with fit breakdown + rationale) met structurally, but its primary actions are inert; **UI-03** (edit criteria + weights) met — the weights editor is a clean, plain form.

---

## Top 3 Priority Fixes

1. **`#ranking-strip` mixes two populations — fix the denominator (BLOCKER).** `app/web/routes.py:293` sets `candidates: int(page.total)` (this request's filtered, truncated queue) while `ranked` is `latest_run.ranked_count` (score rows for one run). `queue.html:135` renders them as a ratio, so with a search matching 5 listings after a run that scored 30 the page says **"Ranked 30 of 5"**. This is wrong, user-visible information on the one surface that exists to make ranking coverage legible (D-89/D-93). Fix: use the run's own candidate count — `_finish` already persists `reason_counts_json["survivors"]` — so numerator and denominator come from one population. (Already filed as CR-01; a strict-`xfail` sentinel at `tests/api/test_queue_ranking_adversarial.py:84` pins it.)

2. **Make the detail page's Save/Hide actually do something visible (BLOCKER).** `listing_detail.html:96-117` sets `hx-target="#listing-row-{{ row.id }}"`, but `#listing-row-*` is emitted only by `_listing_row.html:30` on the queue page. htmx cannot resolve the target, raises `htmx:targetError`, and performs no swap — the user clicks Save, the event is appended server-side, and **nothing changes on screen** (not even a button flip). A control that appears inert breaks task completion on UI-02's flagship surface. Fix: wrap the actions block in an id that exists on the detail page and swap that, or drop the `hx-*` attributes for a plain `method="post"` full-page form (which matches the template's own "reflects state on reload" comment). (Filed as WR-04.)

3. **Bring the new colour pairings to WCAG AA (WARNING — accessibility).** Computed contrast ratios (white/`#ecfdf5`/`#f3f4f6` backgrounds, normal text): `.req-met` `#059669` = **3.77:1**, `.badge-score-tier-high` = **3.58:1**, `.badge-score-tier-low` = **4.39:1** — all below the 4.5:1 AA floor for text under 18.66px bold / 24px. The requirement list is a core RANK surface, so its "met" rows are the least legible. Fix: darken the success token used for text (e.g. `#047857`, ~5.1:1) and the tier-high/tier-low text, or move the verdict colour onto the `<strong>` verdict chip only (see Pillar 2) and keep sentence text at `--color-ink`.

---

## Detailed Findings

### Pillar 1: Copywriting (2/4)

**What is good.** The copy is specific and honest, which is unusually strong for this stage: the unranked detail state says *"Not yet ranked. This listing has no score yet — ranking may still be running, or the pass was skipped. Refresh once it finishes."* (`listing_detail.html:65-68`); an absent factor renders the words `no data`, never `0.00` (`listing_detail.html:56`, `_listing_row.html:48`); the destructive reset explains exactly what is deleted and kept (`settings.html:114-125`); the empty states distinguish *"No listings yet…"* from *"No listings match these filters. Clear filters"* (`queue_list.html:44-54`). Button labels are honest and flip to the inverse action (`Save`/`Unsave`, `Hide`/`Unhide`).

**Findings.**
- **Misleading coverage copy (BLOCKER, cross-cuts Pillar 6):** `queue.html:135` renders `Ranked {{ ranked }} of {{ candidates }}` from `routes.py:291-293`, where the two values come from different sets. It can print "Ranked 30 of 5". This is not a wording nit — the sentence is false. → CR-01.
- **Raw enum leaks into the last-run strip (WARNING):** `queue.html:30` is `{{ last_run.reason or 'unknown' | human_label }}`. Jinja filters bind tighter than `or`, so the filter only ever applies to the `'unknown'` fallback; a real reason renders as the raw machine value (e.g. `all_filtered`), not the humanised label. Phase-touched surface. → IN-01.
- **Low-context link text:** the queue row's only path to the fit breakdown is a bare **"Details"** link (`_listing_row.html:37`). For the phase's headline capability (UI-02), "Details" says nothing about *fit breakdown / why this score*. → recommendation.
- **"Signals" column header** (`queue_list.html:60`) is the umbrella for badges as different as `new`, `stale`, `flagged`, `merged`, the score, and the confidence tier. The score has no label of its own. → recommendation.
- The 404 body is the bare fragment `"Unknown listing."` (`app/api/listings.py:57`) with no chrome or route back.

### Pillar 2: Visuals (3/4)

**What is good.** There is a clear focal point per surface: the queue's first column carries title + the `Details` link; the detail page leads with `h2` title, then a "Fit score" section, then "Factor breakdown", "Why", "Requirement fit", and actions. Hierarchy comes from section `h3`s, a bordered/surface-treated factor table with uppercase muted `th`s, and badges. **No icon-only buttons exist** — every control carries a text label, so there is no unlabelled-glyph risk. External anchors are correctly marked `rel="noopener noreferrer"` and only render when the URL is truthy (`_listing_row.html:55`, `listing_detail.html:26`). The factor table shows each factor's sub-score **and** its weight, with a dropped factor in muted italic — good disclosure.

**Findings.**
- **The primary queue does not adapt to small screens.** `queue_list.html:56-67` renders up to 8 columns (Title, Signals, Company, Location, Source, Posted, optional Excluded by, Actions). `app.css` gives `.queue-table` `display:block;overflow-x:auto`, so on a 375 px viewport it is a long horizontal scroll — not a stacked/card layout. The compiled stylesheet only contains `min-width` breakpoints (40/48/64/80/96rem) and no table-to-card transform. For a local desktop tool this is a soft gap, but it is a real mobile experience gap and there is no declared breakpoint contract to point at.
- **The requirement list colours whole sentences.** `listing_detail.html:79-86` puts `req-met`/`req-partial`/`req-gap` on the `<li>`, and `app.css` sets `color` on the `li` — so an entire requirement sentence renders green/amber/red rather than the verdict marker. A list of mixed verdicts becomes a red/green wall that is hard to scan, and it is the direct cause of the Pillar 3 contrast failures. → recommendation: colour only the verdict chip.
- **The score badge has no accessible context.** `_listing_row.html:49` renders `<span class="badge badge-score">0.82</span>`. A screen reader announces "0.82" inside a cell whose header is the vague "Signals"; nothing states it is a fit score out of 1.0, nor ties it to the tier badge. → recommendation: `aria-label="Fit score 0.82 of 1.00"` or a visually-hidden label.

### Pillar 3: Color (2/4)

**Token discipline is good.** The compiled theme defines a coherent 17-token palette (`app.css:2`, `@layer theme`): `ink/paper/muted/border/surface/surface-2/accent/accent-hover/accent-bg/success/success-bg/warning/warning-bg/danger/danger-bg/info/info-bg`. Phase-5 additions (`badge-score`, `badge-score-tier-*`, `badge-unranked`, `req-*`, `factor-absent`, `detail-*`, `ranking-strip`, `weight-*`) are written entirely in `var(--color-*)` tokens — **no new hardcoded hex**. (The raw hexes still present in the file are confined to earlier phases' `rule-chip-*` and health badges.)

**60/30/10 distribution is sound.** Of 232 colour-token usages in the app region, neutral tokens (`border` 41, `muted` 39, `surface` 25, `surface-2` 15, `paper` 12, `ink` 6 = 138) dominate; accent-family usage is 30 (accent 15, accent-hover 9, accent-bg 6) and is reserved for links, the score badge and primary actions; semantic colours account for the rest. There is no accent overuse.

**Findings — contrast failures (WARNING, accessibility).** Computed WCAG ratios:

| Pairing | Ratio | AA |
|---|---|---|
| `.req-met` `#059669` on white | **3.77:1** | FAIL |
| `.badge-score-tier-high` `#059669` on `#ecfdf5` | **3.58:1** | FAIL |
| `.badge-score-tier-low` `#6b7280` on `#f3f4f6` | **4.39:1** | FAIL |
| `.req-partial` `#b45309` on white | 5.02:1 | pass |
| `.req-gap` `#dc2626` on white | 4.83:1 | pass |
| `.badge-score` `#1d4ed8` on `#eff6ff` | 6.16:1 | pass |
| `--color-muted` on white / surface | 4.83 / 4.63:1 | pass |

The three failures land on phase-5 surfaces (requirement fit, confidence tier). Fix by darkening the success/tier-low text token or by moving colour off the sentence body.

### Pillar 4: Typography (3/4)

**What is good.** The app uses a compact, intentional set. Declared `font-size` values cluster on a scale (`.75/.8/.85/.875/.9/.95/1/1.125/1.25/1.5/1.75/2rem`); the phase-5 surfaces draw from only a handful: `.badge` 12 px/600, table `th` 12.8 px/600 uppercase, controls `.85rem`, `ranking-strip` `.95rem`, body 1rem, section `h3` 1.25rem. Weights used are 400/500/600/700 only. Two deliberate, good touches: the score badge and evidence IDs use `--font-mono`, and `.detail-rationale` is capped at `65ch` for readable line length. Headings use a serif display face (`--font-display`) against sans body — a clear typographic hierarchy.

**Findings.**
- The requirement verdict (`<strong>{{ entry.verdict }}</strong>`) and the requirement text share the same size and weight; hierarchy rests entirely on colour — which is the Pillar 3 problem. A size/weight step or a chip for the verdict would decouple legibility from hue. → recommendation.
- `badge` at 12 px bold is at the small end for the primary score readout; with the tier badge alongside, the row's most important number is the smallest text on the row. → minor.
- The `confidence_tier` badge prints the raw lowercase token (`high`/`medium`/`low`, `_listing_row.html:50`, `listing_detail.html:34`) with no "confidence" label. → minor, copy-adjacent.

### Pillar 5: Spacing (3/4)

**What is good.** The custom region uses a single coherent rem scale — `.125/.2/.25/.375/.5/.625/.75/.875/1/1.25/1.5/2/2.5/3rem` — with table cells on `.875rem 1rem`, cards on `1.25rem`, and page gutters on `1.5rem 1rem 3rem` (`#content`). **No arbitrary `[Npx]`/`[Nrem]` values appear anywhere.** The new phase-5 layouts are responsive by construction: `.weight-grid{grid-template-columns:repeat(auto-fit,minmax(11rem,1fr))}` and `.factor-table{max-width:44rem;overflow-x:auto}`. Grouping is consistent (`gap:.5rem` for action clusters, `.25rem` for label/field stacks).

**Findings.**
- Two chip padding scales coexist: `.badge{padding:.2rem .5rem}` vs `.rule-chip{padding:.125rem .375rem}`. Both are intentional-looking but there is no documented scale (no UI-SPEC) to say which is canonical. → minor.
- `.queue-sort`/`.queue-threshold` use a vertical `gap:.25rem` stack while sibling filter controls sit inline; visually fine, but the filter bar mixes two alignment models. → minor observation.

### Pillar 6: Experience Design (2/4)

**What is good.** State coverage is broad: loading/progress via the polling `#run-status` fragment (`_run_status.html`, `aria-live="polite"`, 2 s poll); error states for a failed/partial run (`run-failed`, `run-degraded`), for the LLM backend (`settings-banner-error`, probe cause line), and a 404 fragment for an unknown listing; two distinct empty states; a `disabled` button pattern exists (`merges.html:92`); destructive actions are confirmed (`hx-confirm` on Dismiss-all, typed-token confirmation on reset); the `#ranking-strip` correctly renders nothing until `ranked_count` is written, avoiding a misleading "Ranked 0 of N". The weights editor explicitly promises "no new model call" — good expectation-setting.

**Findings.**
- **Detail-page Save/Hide is inert (BLOCKER):** `listing_detail.html:96-117` targets `#listing-row-{{ row.id }}`, which exists only on the queue page. htmx raises `htmx:targetError` and performs no swap, so the click appends the event but gives **no feedback at all** — not even the button flip. → WR-04.
- **No busy/disabled state on the primary action:** `queue.html:7-13` (`#run-search-now`) has no `hx-indicator`, no `hx-disabled-elt`, no `aria-busy`. The button stays fully clickable while a run is in flight; feedback only appears later inside `#run-status-slot`. → WARNING.
- **A junk threshold silently hides every scored listing:** `?min_score=nan` passes `_float_or_none` (`routes.py:109-116`) and `total_score >= nan` is False for every scored row, so the queue empties of scored jobs while unscored ones remain. Contradicts the documented "junk degrades to `None`". → WR-03.
- **The queue can silently omit listings:** the default score sort is bounded by `SCORE_SORT_SCAN_LIMIT = 5000` (`queue_repo.py`), so beyond 5 000 matches the oldest listings are absent from the queue entirely (not merely "unranked last"), and `page.total` under-reports so paging stops early. This also defeats the Dismiss-all cap guard. → WR-01.
- **The 404 has no way back:** the fragment returned by `app/api/listings.py:54-59` renders without the base layout/nav, so a mistyped or stale detail URL strands the user. → minor.

---

## Registry Safety

Skipped: no `components.json` exists (this is a Jinja2 + HTMX + vendored-Tailwind app, not a shadcn project), and no third-party registry blocks are declared anywhere. No registry audit performed.

---

## Files Audited

- `app/web/templates/html/listing_detail.html`
- `app/web/templates/html/queue.html`
- `app/web/templates/html/queue_list.html`
- `app/web/templates/html/_listing_row.html`
- `app/web/templates/html/settings.html`
- `app/web/templates/html/base.html`
- `app/web/templates/html/_run_status.html`
- `static/vendor/app.css` (compiled Tailwind v4.3.3)
- `app/web/routes.py` (`_ranking_strip`, queue handlers)
- `app/api/listings.py` (`GET /listings/{id}`, 404 fragment)
- `app/domain/rubric.py` (`FACTOR_LABELS`, `DEFAULT_WEIGHTS`)
- `tests/test_stylesheet_coverage.py`
- `tests/api/test_listing_detail.py`, `test_queue_ranked.py`, `test_ranking_weights.py`, `test_queue_ranking_adversarial.py`
- `.planning/phases/05-ranking-core-value/05-REVIEW.md` (upstream code review; CR-01/WR-01/WR-03/WR-04/IN-01 corroborated here)

**Note on screenshot hygiene:** `.planning/ui-reviews/.gitignore` already exists and ignores `*.png`/`*.webp`/`*.jpg`/etc.; `git check-ignore` confirms the stray `test-search.png` there is ignored and untracked. No new binaries were written by this audit.

_Reviewed: 2026-09-22_
_Reviewer: the agent (gsd-ui-reviewer)_
_Baseline: abstract 6-pillar (no UI-SPEC.md exists)_
