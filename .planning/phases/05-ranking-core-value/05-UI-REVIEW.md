# Phase 5 — UI Review

**Audited:** 2026-09-23 (round-3 re-audit; **supersedes** the 2026-09-22 review in this file)
**Baseline:** abstract 6-pillar standards — **no `UI-SPEC.md` exists** in this phase dir or anywhere under `.planning/` (re-verified this run: `find .planning -iname "*UI-SPEC*"` → empty). There is therefore no approved design contract; findings are judged against the phase's own decision record (`05-CONTEXT.md` D-88…D-100), the plan acceptance criteria, and general 6-pillar standards.
**Screenshots:** **not captured.** No dev server was reachable this run — ports 3000 / 5173 / 8080 / 8000 all returned connection failure (`000`). The reason is unchanged: the shipped default DB URL is `sqlite+aiosqlite:////data/jobsearch.db` (absolute `/data`, absent here) while the real DB lives at `./data/jobsearch.db`. Audit is therefore **code-only** (template + compiled-CSS + route + rendered-test analysis). No screenshots were fabricated.
**Method:** template source, the compiled `static/vendor/app.css` (Tailwind v4.3.3), `app/web/routes.py`, `app/api/listings.py`, `app/api/settings.py`, `app/api/health.py`, the rendered-HTML tests, and a Jinja render probe for the two precedence/repr defects. Test run this audit: `.venv/bin/python -m pytest tests/api/test_queue_ranked.py tests/api/test_listing_detail.py tests/api/test_ranking_weights.py tests/test_stylesheet_coverage.py tests/api/test_health.py tests/api/test_settings_page.py tests/api/test_queue_ranking_adversarial.py` → **70 passed, 1 xfailed** (the WR-03 `min_score=nan` strict-xfail sentinel remains).
**Scope of this round:** the round-2 gap-closure UI deltas — 05-08 (`queue.html` `#ranking-strip`, five states), 05-09 (`listing_detail.html` ranking-state copy + CV path), 05-10 (`settings.html` CV card, `_health_strip.html` `#cv-fact-store-status`, `app.css` `.cv-status`) — plus the surviving findings from the prior review, re-verified.

**Reused evidence (stated explicitly):** `queue_list.html`, `_listing_row.html`, `base.html`, `runs.html`, `criteria.html`, `merges.html` are unchanged since the prior review and are carried forward as re-verified. The colour-contrast ratios **were** recomputed from the current compiled stylesheet.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 2/4 | The round-2 work added excellent honest state copy, but also **regressed**: `/runs/{id}` now prints the new ranking marker as a raw Python dict repr (WR-01), and the two pre-existing raw-token leaks (`all_filtered`, `per_run`) remain. |
| 2. Visuals | 3/4 | The CV prerequisite — the blocker for the phase's Core Value — is disclosed only at the very bottom of the queue page, inside `#source-health`, below the queue table. |
| 3. Color | 2/4 | Unchanged three AA failures (`req-met` 3.77:1, `badge-score-tier-high` 3.58:1, `badge-score-tier-low` 4.39:1) plus a new 4.39:1 muted-on-`surface-2` failure on the CV-path `<code>` spans. |
| 4. Typography | 3/4 | Coherent, modest size/weight set; verdicts and body still share one size so hierarchy rests on colour alone. |
| 5. Spacing | 3/4 | Disciplined rem scale, no arbitrary `[Npx]` values; new `.cv-status` matches `.llm-status` padding. Minor chip-padding inconsistency. |
| 6. Experience Design | 2/4 | Still the worst pillar: **detail-page Save/Hide remain inert** (BLOCKER — unchanged), plus the `nan`/`inf` threshold, the 5000-row truncation, and no busy state on the primary run action. |

**Overall: 15/24** (down from 16/24). The round-2 observability work is a genuine improvement to state coverage — but Pillar 1 loses a point to a **new, user-visible regression** (the run-detail dict repr) that the delta itself introduced. No other pillar moved.

Requirement read: **UI-01** (browse ranked list) — the strip is now truthful across five states; the silent `>5000`-row truncation (WR-01 prior) remains. **UI-02** (detail with fit breakdown + rationale) — the unscored state now names a real cause (05-09, good), but its primary actions are still inert (WR-04 prior). **UI-03** (edit criteria + weights) — met; the weights editor is a clean, plain form.

---

## Top 3 Priority Fixes

1. **Detail-page Save/Hide is still inert (BLOCKER — WR-04, unchanged).** `listing_detail.html:103` and `:114` set `hx-target="#listing-row-{{ row.id }}"`, but `#listing-row-*` is emitted only by `_listing_row.html:30` on the queue page. htmx resolves the target after the response, finds nothing, fires `htmx:targetError`, and performs **no swap** — the user clicks Save/Hide, the event is appended server-side, and **nothing changes on screen**. The template comment (`:96-99`) now documents this as deliberate ("the page reflects the new state on reload"), but a primary action that gives zero feedback is a broken interaction on UI-02's flagship surface. Fix: drop the `hx-*` attributes for a plain full-page `method="post"` form (the posture the comment claims), or return a purpose-built fragment and swap `#detail-actions`, or use an `hx-swap-oob` button flip. Do not leave a dead htmx target.

2. **`/runs/{id}` prints the new ranking marker as a raw Python dict repr (WARNING — WR-01, NEW in 05-08).** `runs.html:106-112` iterates the whole `reason_counts` bag generically; 05-08 merged a **nested object** into it (`reason_counts_json['ranking'] = {"status": ..., "reason": ...}`). Every other value is a scalar, so the run-detail "Counts behind the reason" list now renders, for every skipped or nothing-to-rank run:
   `<dt>ranking</dt><dd>{'status': 'skipped', 'reason': 'fact_store_absent'}</dd>` (reproduced this audit via a Jinja render probe; quotes arrive as `&#39;`). The 05-08 decision that "existing readers ignore the unknown sub-key" is **false** — `runs.html` is the counterexample. Fix: skip non-scalar values in the loop and render `status`/`reason` explicitly, or persist the outcome as two scalar keys (`ranking_status`/`ranking_reason`) so no generic bag reader meets a nested shape. Add a run-detail test seeding a marker and asserting the repr is absent.

3. **Four colour pairings fail WCAG AA (WARNING — accessibility).** Recomputed from the current compiled `app.css`: `.req-met` `#059669` on white = **3.77:1**; `.badge-score-tier-high` `#059669` on `#ecfdf5` = **3.58:1**; `.badge-score-tier-low` `#6b7280` on `#f3f4f6` = **4.39:1**; and **new this round** — the CV-path `<code>` spans introduced by 05-09/05-10 render `--color-muted` on `code`'s `--color-surface-2` background = **4.39:1** (in `.cv-status` `_health_strip.html:24,26`, `.settings-note` `settings.html:116,120,124-127`, and `.detail-not-ranked` `listing_detail.html:72`). All are below the 4.5:1 floor for normal text. Fix: darken the success/tier-low text token (e.g. `#047857`, ~5.1:1) or move verdict colour off the sentence body; give `code` a darker colour inside muted contexts.

---

## Detailed Findings

### Pillar 1: Copywriting (2/4)

**What the round-2 work got right.** The five-state strip is honest and specific: `Ranked 5 of 30` / `Ranking in progress. Scores appear as they land — refresh to update.` / `Ranking skipped — <human reason>.` / `Nothing to rank on the last run.` / `Ranking has not completed for the last run.` (`queue.html:148-162`). The skip vocabulary has one definition (`RANK_SKIP_LABELS`, `app/pipeline/rank.py:92-97`) and the template never hardcodes a reason string. The detail page's unscored block (`listing_detail.html:72`) now names a real cause — including the CV fact-store skip with the exact loader path and a `/settings` pointer — and says "not readable", never "missing file". Empty states still distinguish *"No listings yet…"* from *"No listings match these filters. Clear filters"* (`queue_list.html:44-54`), and an absent factor still renders the words `no data`, never `0.00`.

**Findings.**
- **Raw Python dict repr on the run-detail page (WARNING, NEW — WR-01):** `runs.html:106-112` stringifies the nested `ranking` marker. This is the regression that costs the pillar its point. → see Top-3 fix 2.
- **Raw enum still leaks into the last-run strip (WARNING, unchanged — IN-01):** `queue.html:30` is `{{ last_run.reason or 'unknown' | human_label }}`; Jinja's `|` binds tighter than `or`, so `human_label` only ever applies to the `'unknown'` fallback. Re-proven this run: `all_filtered` → `all_filtered`, `no_survivors` → `no_survivors`, `None` → `Unknown`. Same bug at `runs.html:66`. Fix: `{{ (last_run.reason or 'unknown') | human_label }}`.
- **Raw cap token still leaks into the ranking strip (WARNING, unchanged):** `queue.html:151` interpolates `cap_reason` unfiltered; the read model returns the bare `per_run`/`per_day` text (`llm_call_repo.py:253-268`). The D-93 sentence therefore reads *"Ranked 12 of 40 — cap reached (per_run)"*. Fix: apply `human_label` to `cap_reason`.
- **The queue CV line overstates (WARNING, NEW — IN-03):** `_health_strip.html:26-27` is unconditional and asserts "ranking is skipped until one is supplied". When `Settings.ranking_enabled` is false, ranking is *off*, not blocked on the CV; and a queue that a prior run already scored is not unranked. Fix: pass `ranking_enabled` into the strip and soften/omit the sentence when ranking is disabled.
- **A corrupt CV store can be reported as the wrong cause (WARNING, NEW — WR-02):** `ranking_skip_reason()` (`rank.py:100-112`) claims totality but catches only `(CvFactStoreError, OSError)`; a `RecursionError` from a deeply nested `cv.yaml` escapes, is swallowed by the ranking block's broad handler, and the strip then says *"Ranking skipped — the pass could not be started"* when the real cause is an unreadable fact store. Fix: add the `except Exception` catch-all the sibling `fact_store_report` already has.
- **Low-context link text:** the queue row's only path to the fit breakdown is a bare **"Details"** link (`_listing_row.html:37`) — for the phase's headline capability it says nothing about fit breakdown or why this score. → recommendation.
- **"Signals" column header** (`queue_list.html:60`) still umbrellas badges as different as `new`, `stale`, `flagged`, `merged`, the score and the confidence tier; the score has no label of its own. → recommendation.
- The 404 body is the bare fragment `"Unknown listing."` (`app/api/listings.py:70`) with no chrome or route back. → minor.

### Pillar 2: Visuals (3/4)

**What is good.** There is a clear focal point per surface: the queue's first column carries title + the `Details` link; the detail page leads with `h2` title, then "Fit score", "Factor breakdown", "Why", "Requirement fit", and actions. Hierarchy comes from section `h3`s, a bordered factor table with uppercase muted `th`s, and badges. **No icon-only buttons exist** — every control carries a text label. External anchors are correctly `rel="noopener noreferrer"` and render only when the URL is truthy. The factor table shows each factor's sub-score **and** its weight, with a dropped factor in muted italic — good disclosure.

**Findings.**
- **The Core Value's prerequisite is buried (NEW, hierarchy):** the CV fact-store status line renders inside `#source-health` (`_health_strip.html:21-30`), which is the **last section** of the queue page (`queue.html:169`), below the queue table. For a fresh checkout — the exact case G-05-2 exists for — the one fact that explains why nothing is ranked sits under "Source health", off-screen on any populated queue. The disclosure is correct but not where the user looks. → recommendation: surface the unreadable-store state beside `#ranking-strip` (or above the queue table) and leave the healthy case in the health strip.
- **The primary queue does not adapt to small screens.** `queue_list.html:56-74` renders up to 8 columns; `.queue-table` is `display:block;overflow-x:auto`, so a 375 px viewport is a long horizontal scroll, not a stacked/card layout. No table-to-card breakpoint exists in the compiled stylesheet (only `min-width` 40/48/64/80/96rem). Soft gap for a desktop-first local tool (D-16), but a real mobile gap with no declared breakpoint contract. → WARNING.
- **The requirement list colours whole sentences.** `listing_detail.html:86` puts `req-met`/`req-partial`/`req-gap` on the `<li>` and `app.css` sets `color` on that element, so an entire requirement sentence renders green/amber/red rather than just the verdict marker — a red/green wall that is hard to scan, and the direct cause of the Pillar 3 contrast failures. → recommendation: colour only the verdict chip.
- **The score badge has no accessible context.** `_listing_row.html:49` renders `<span class="badge badge-score">0.82</span>`; a screen reader announces "0.82" inside a cell headed by the vague "Signals", with nothing saying it is a fit score out of 1.0. → recommendation: `aria-label="Fit score 0.82 of 1.00"`.
- No skip-to-content link in `base.html` (nav → `<main>` only). → minor.

### Pillar 3: Color (2/4)

**Token discipline is good.** The compiled theme defines a coherent 17-token palette (`app.css` `@layer theme`). The phase-5 additions (`badge-score`, `badge-score-tier-*`, `badge-unranked`, `req-*`, `factor-absent`, `detail-*`, `ranking-strip`, `weight-*`, and now `cv-status`) are written entirely in `var(--color-*)` tokens — **no new hardcoded hex in any phase-5 template** (the only `#` match in `app/web/templates/html/` is the `&#9733;` entity). Raw hexes still present are confined to earlier phases' `rule-chip-*` and health badges.

**60/30/10 distribution is sound.** Neutral tokens dominate; the accent family is reserved for links, the score badge and primary actions. There is no accent overuse.

**Findings — contrast failures (WARNING, accessibility). Ratios recomputed from the current compiled CSS:**

| Pairing | Ratio | AA |
|---|---|---|
| `.req-met` `#059669` on white | **3.77:1** | FAIL |
| `.badge-score-tier-high` `#059669` on `#ecfdf5` | **3.58:1** | FAIL |
| `.badge-score-tier-low` `#6b7280` on `#f3f4f6` | **4.39:1** | FAIL |
| **`code` on `--color-surface-2` inside `.cv-status` / `.settings-note` / `.detail-not-ranked` (NEW)** | **4.39:1** | FAIL |
| `.req-partial` `#b45309` on white | 5.02:1 | pass |
| `.req-gap` `#dc2626` on white | 4.83:1 | pass |
| `.badge-score` `#1d4ed8` on `#eff6ff` | 6.16:1 | pass |
| `--color-muted` on white / surface | 4.83 / 4.63:1 | pass |

The three pre-existing failures land on phase-5 surfaces (requirement fit, confidence tier). The new fourth is introduced by the CV-path disclosure: `code` sets only a background (`--color-surface-2`) and inherits the surrounding muted colour, so every `<code>{{ cv.path }}</code>` in a muted paragraph sits at 4.39:1. Fix by darkening the success/tier-low text tokens and giving `code` an explicit ink-coloured text.

### Pillar 4: Typography (3/4)

**What is good.** A compact, intentional set. Phase-5 surfaces draw from only a handful: `.badge` 12 px/600, table `th` 12.8 px/600 uppercase, controls `.85rem`, `ranking-strip` `.95rem`, body 1rem, section `h3` 1.25rem. Weights used are 400/500/600/700 only. Two deliberate touches: the score badge and evidence IDs use `--font-mono`, and `.detail-rationale` is capped at `65ch`. Headings use a serif display face (`--font-display`) against sans body. The new `.cv-status` (`.75rem 1rem` padding, `font-weight:500`, 1rem) matches `.llm-status` — consistent.

**Findings.**
- The requirement verdict (`<strong>{{ entry.verdict }}</strong>`) and the requirement text share the same size and weight; hierarchy rests entirely on colour — which is the Pillar 3 problem. A size/weight step or a chip for the verdict would decouple legibility from hue. → recommendation.
- `badge` at 12 px bold is the smallest text on the row, yet it carries the row's most important number (the fit score). → minor.
- The `confidence_tier` badge prints the raw lowercase token (`high`/`medium`/`low`, `_listing_row.html:50`, `listing_detail.html:40`) with no "confidence" label. → minor, copy-adjacent.

### Pillar 5: Spacing (3/4)

**What is good.** A single coherent rem scale (`.125/.2/.25/.375/.5/.625/.75/.875/1/1.25/1.5/2/2.5/3rem`), table cells on `.875rem 1rem`, cards on `1.25rem`, page gutters `1.5rem 1rem 3rem` (`#content`). **No arbitrary `[Npx]`/`[Nrem]` values anywhere.** New phase-5 layouts are responsive by construction: `.weight-grid{repeat(auto-fit,minmax(11rem,1fr))}`, `.factor-table{max-width:44rem;overflow-x:auto}`. The new `.cv-status` uses `.75rem 1rem` with `1rem` bottom margin, matching `.llm-status`. Grouping is consistent (`gap:.5rem` for action clusters, `.25rem` for label/field stacks).

**Findings.**
- Two chip padding scales coexist: `.badge{padding:.2rem .5rem}` vs `.rule-chip{padding:.25rem .625rem}`. Both look intentional but there is no documented scale (no UI-SPEC) to say which is canonical. → minor.
- `.queue-sort`/`.queue-threshold` use a vertical `gap:.25rem` stack while sibling filter controls sit inline; the filter bar mixes two alignment models. → minor observation.

### Pillar 6: Experience Design (2/4)

**What is good — and what round-2 added.** State coverage is broad and materially better after 05-08/09/10: loading/progress via the polling `#run-status` fragment (`_run_status.html`, `aria-live="polite"`, 2 s poll); error states for a failed/partial run, the LLM backend (`settings-banner-error`, probe cause line), and a 404 fragment; two distinct empty states; a `disabled` button pattern (`merges.html:92`); destructive actions confirmed (`hx-confirm` on Dismiss-all, typed-token confirmation on reset). The `#ranking-strip` now distinguishes five states instead of one blank, derives `running` from the live task so a crashed pass degrades honestly, and the detail page names the last run's cause — a real fix for the "I don't know why the queue is unranked" report. The weights editor explicitly promises "no new model call". The CV disclosure answers "where do I put my CV?".

**Findings.**
- **Detail-page Save/Hide is inert (BLOCKER, unchanged):** `listing_detail.html:103,114` target `#listing-row-{{ row.id }}`, which exists only on the queue page. htmx raises `htmx:targetError` and performs no swap, so the click appends the event but gives **no feedback at all** — not even a button flip. → WR-04; see Top-3 fix 1. This is the single highest-impact open defect in the phase and neither 05-09 nor 05-10 touched it.
- **No busy/disabled state on the primary action:** `queue.html:7-13` (`#run-search-now`) has no `hx-indicator`, no `hx-disabled-elt`, no `aria-busy` (verified: zero matches across all templates). The button stays fully clickable while a run is in flight; feedback appears only later inside `#run-status-slot`. → WARNING.
- **A junk threshold silently hides every scored listing:** `?min_score=nan` (and now `inf`) passes `_float_or_none` (`routes.py:122-129`, bare `float()`), and `total_score >= nan` is False for every scored row, so the queue empties of scored jobs while unscored ones remain — contradicting the documented "junk degrades to `None`". Still pinned by the one remaining strict-xfail sentinel (`tests/api/test_queue_ranking_adversarial.py`). → WR-02 prior, WARNING.
- **The queue can silently omit listings:** the default score sort is bounded by `SCORE_SORT_SCAN_LIMIT = 5000` (`queue_repo.py`), so beyond 5 000 matches the oldest listings are absent from the queue entirely and `page.total` under-reports so paging stops early. This also defeats the Dismiss-all cap guard. → CR-01 prior, WARNING.
- **A cap-read failure drops the whole strip:** `_ranking_strip` (`routes.py:319-332`) builds `ranked`/`candidates`/`state`/`reason`/`cap_reason` in one `try`; a failure in the unrelated `rank_cap_reason_for_run` read returns `{}` and vanishes the disclosure it exists to provide. → IN-04, minor.
- **The 404 has no way back:** the fragment from `app/api/listings.py:67-72` renders without the base layout/nav, so a mistyped or stale detail URL strands the user. → minor.

---

## Registry Safety

Skipped: no `components.json` exists (this is a Jinja2 + HTMX + vendored-Tailwind app, not a shadcn project), and no third-party registry blocks are declared anywhere. Re-verified this run. No registry audit performed.

---

## Files Audited

**Re-read and re-verified this run:**

- `app/web/templates/html/queue.html` — five-state `#ranking-strip` (05-08); raw `reason` (`:30`) and `cap_reason` (`:151`) leaks confirmed
- `app/web/templates/html/listing_detail.html` — state-driven unscored copy (`:72`, 05-09); inert action targets (`:103,:114`) confirmed
- `app/web/templates/html/settings.html` — `#cv-fact-store` card (`:112-131`, 05-10); `<code>` path spans
- `app/web/templates/html/_health_strip.html` — `#cv-fact-store-status` line (`:21-30`, 05-10)
- `app/web/templates/html/runs.html` — generic `reason_counts` loop (`:106-112`) → the dict-repr regression; raw reason (`:66`)
- `app/web/templates/html/_listing_row.html` — badges (`:48-50`), `Details` link (`:37`), action forms
- `app/web/templates/html/queue_list.html` — 8-column table, empty-state predicates
- `app/web/templates/html/base.html` — nav/`main`, no skip link
- `app/web/routes.py` (`_ranking_strip`, `_cv_status`, `_float_or_none`, queue handler)
- `app/api/listings.py` (detail route, ranking-state context, 404 fragment)
- `app/api/settings.py` (`cv` context entry)
- `app/db/repositories/llm_call_repo.py` (`rank_cap_reason_for_run` — the raw cap token source)
- `app/pipeline/rank.py` (`RANK_SKIP_LABELS`, `ranking_in_progress`, `ranking_skip_reason`)
- `app/web/filters.py` (`human_label`) + empirical Jinja precedence and dict-repr probes
- `static/vendor/app.css` (compiled Tailwind v4.3.3) — contrast ratios recomputed, `.cv-status` rule verified
- Tests: `tests/api/test_queue_ranked.py`, `tests/api/test_listing_detail.py`, `tests/api/test_ranking_weights.py`, `tests/api/test_health.py`, `tests/api/test_settings_page.py`, `tests/api/test_queue_ranking_adversarial.py`, `tests/test_stylesheet_coverage.py` → **70 passed, 1 xfailed**
- `.planning/phases/05-ranking-core-value/05-CONTEXT.md` (D-88…D-100), `05-01…05-10-PLAN.md`, `05-08…05-10-SUMMARY.md`, `05-REVIEW.md`

**Note on screenshot hygiene:** `.planning/ui-reviews/.gitignore` already exists and ignores `*.png`/`*.webp`/`*.jpg`/etc. The gitignore gate was re-run before any capture attempt (none succeeded — no server). No binaries were written by this audit.

_Reviewed: 2026-09-23_
_Reviewer: the agent (gsd-ui-auditor)_
_Baseline: abstract 6-pillar (no UI-SPEC.md exists)_
_Round-2 delta: 05-08/09/10 landed; Pillar 1 regressed via WR-01 (raw dict repr on `/runs/{id}`); detail-page Save/Hide BLOCKER remains_
