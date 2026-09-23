# Phase 5 — UI Review

**Audited:** 2026-09-23 (round-4 re-audit; **supersedes** the 2026-09-23 round-3 review in this file)
**Baseline:** abstract 6-pillar standards — **no `UI-SPEC.md` exists** in this phase dir or anywhere under `.planning/` (re-verified: `find .planning -iname "*UI-SPEC*"` → empty). There is no approved design contract, so findings are judged against the phase's own decision record (`05-CONTEXT.md` D-88…D-100), the plan acceptance criteria, and general 6-pillar standards.
**Screenshots:** **not captured.** No dev server was reachable this run — ports 3000 / 5173 / 8080 / 8000 all returned connection failure (`000`). The shipped default DB URL is `sqlite+aiosqlite:////data/jobsearch.db` (absolute `/data`, absent here) while the real DB lives at `./data/jobsearch.db`; the app cannot boot as-shipped. Audit is therefore **code-only** (template source, compiled `static/vendor/app.css`, repository/route source, rendered-HTML tests). No screenshots were fabricated.
**Method:** `queue_list.html`, `queue.html`, `_listing_row.html`, `listing_detail.html`, `runs.html`, `_health_strip.html`, `app/db/repositories/queue_repo.py`, `app/web/routes.py`, `app/pipeline/run.py`, `assets/tailwind/input.css` + compiled `static/vendor/app.css`, vendored `htmx.min.js` (v2.0.10), and the paging tests. Test run this audit: `.venv/bin/python -m pytest tests/api/test_queue_excluded.py tests/test_stylesheet_coverage.py tests/api/test_queue_ranked.py tests/api/test_listing_detail.py` → **39 passed**.
**Scope of this round:** the 05-11 gap-closure delta (G-05-3) — the forward-only "Load more" control replaced by a two-way `#queue-pager` (Previous / `Page X of Y (N per page)` / Next) in the shared `queue_list.html` fragment, plus the derived `QueuePage` accessors and the two id-scoped CSS rules. Surviving findings from round 3 are re-verified, not assumed.

**Reused evidence (stated explicitly):** `_listing_row.html`, `base.html`, `criteria.html`, `merges.html`, `_health_strip.html` are unchanged since round 3. `queue.html`'s filter comment changed (no markup change). Colour ratios **were** recomputed from the current compiled stylesheet. The 05-11 delta touched only the queue pager and its CSS.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 2/4 | The pager's own copy is clean and the mislabelled "Load more" is gone — but the round-3 raw-token leaks and the `/runs/{id}` dict repr (WR-01) are untouched. |
| 2. Visuals | 3/4 | New pager instability: Previous is *omitted* on page 1 and Next on the last page, so the position line jumps horizontally between pages; the top-of-list count still doesn't disclose that the list is paginated. |
| 3. Color | 2/4 | Unchanged four AA failures (`req-met` 3.77:1, `badge-score-tier-high` 3.58:1, `badge-score-tier-low` 4.39:1, `code` on `surface-2` 4.39:1). The pager adds no new colour and its own line passes (4.83:1). |
| 4. Typography | 3/4 | Coherent, modest set; the pager's `.9rem` position line and `.85rem` controls sit inside the existing scale. Verdicts and body still share one size. |
| 5. Spacing | 3/4 | Disciplined rem scale, no arbitrary values; `#queue-pager` `gap:1rem` / `margin-top:1rem` match the system. New minor: the pager has no `flex-wrap`, so it can overflow at narrow widths / large page counts. |
| 6. Experience Design | 2/4 | Still the worst pillar. The pager is correct but has **no scroll reset, no busy state, and no request coalescing**; the detail-page Save/Hide BLOCKER is unchanged; the 5000-row scan cap now manifests as a **wrong page count**. |

**Overall: 15/24** (unchanged from round 3). The 05-11 delta genuinely closes G-05-3 — the queue is now two-way pageable and the control no longer lies about appending — but the replacement pager introduces its own interaction gaps, so no pillar moves.

Requirement read: **UI-01** (browse ranked list) — materially improved: a discrete page swap is now correctly labelled, backward navigation exists, and the page size is surfaced. **UI-02** (detail with fit breakdown + rationale) — unchanged; primary actions still inert (BLOCKER). **UI-03** (edit criteria + weights) — met.

---

## Top 3 Priority Fixes

1. **Detail-page Save/Hide is still inert (BLOCKER — carried forward, unchanged).** `listing_detail.html:103,114` set `hx-target="#listing-row-{{ row.id }}"`, but `#listing-row-*` is emitted only by `_listing_row.html:30` on the queue page. htmx resolves the target after the response, finds nothing, fires `htmx:targetError`, and performs **no swap** — the user clicks Save/Hide, the event is appended server-side, and **nothing changes on screen**. The template comment (`:96-99`) documents this as deliberate ("the page reflects the new state on reload"), but a primary action that gives zero feedback is a broken interaction on UI-02's flagship surface. Fix: drop the `hx-*` attributes for a plain full-page `method="post"` form, or return a purpose-built fragment and swap `#detail-actions`, or use an `hx-swap-oob` button flip. Do not leave a dead htmx target.

2. **Pager swaps do not reset scroll (WARNING — NEW, 05-11).** Both pager controls swap `#queue-list` with `hx-swap="innerHTML"` and **no `show:` modifier** (`queue_list.html:88-90, 98-100`; vendored htmx 2.0.10 only scrolls when `show` is truthy, and nothing here sets it). The pager sits *below* a table of up to 25 rows, so the user must scroll to the bottom to click Next — and after the swap the viewport stays at the bottom, showing the pager and the tail of the new page. The first rows of the new page are above the fold. This is the same class of defect for the filter form and the toggles. Fix: add `show:top` to the `#queue-list` swaps (`hx-swap="innerHTML show:top"`), or scroll `#queue-list` into view on `htmx:afterSwap`.

3. **Pager boundary controls are absent, not disabled (WARNING — NEW, 05-11).** `queue_list.html:85-93` omits Previous on page 1 and `:95-103` omits Next on the last page. Because `#queue-pager` is a plain `display:flex` row, the position line shifts horizontally by roughly a button-width + `1rem` gap as the user moves between first, middle, and last pages, and there is no stable cue that the boundary has been reached beyond the text. Fix: always render both controls and set `disabled` + `aria-disabled="true"` when `not page.has_prev` / `not page.has_more` — the existing `button:disabled{opacity:.6;cursor:not-allowed}` rule already styles it. This also gives the busy state (fix 2's sibling) somewhere to live.

---

## Detailed Findings

### Pillar 1: Copywriting (2/4)

**What 05-11 got right.** The pager's copy is precise and conventional: `Previous` / `Next` are the correct labels for discrete page navigation, and `Page {{ page.page_index }} of {{ page.page_count }} ({{ page.limit }} per page)` states position *and* page size in one line (`queue_list.html:94`). Crucially, the old control is gone: `queue-load-more` returns **zero** matches in `app/`, `static/`, `assets/` and `tests/` (only stale `.pyc` strings and two doc-comments in `queue_repo.py:176,178` / `routes.py:163` / `config.py:126` still say "Load more" — cosmetic drift, not user-visible). A control that promised an append while its `innerHTML` swap destroyed the rows already on screen was a real lie, and it is now fixed.

**Findings.**
- **Raw Python dict repr on the run-detail page (WARNING, unchanged — WR-01):** `runs.html:106-112` iterates the whole `reason_counts` bag generically and `app/pipeline/run.py:976` merges a **nested object** into it (`reason_counts = {**reason_counts, "ranking": ranking_outcome}` where the outcome is `{"status": ..., "reason": ...}`). Every skipped/nothing-to-rank run therefore renders `<dt>ranking</dt><dd>{'status': 'skipped', 'reason': 'fact_store_absent'}</dd>`. The 05-08 assumption that "existing readers ignore the unknown sub-key" is false — `runs.html` is the counterexample. Fix: skip non-scalar values and render `status`/`reason` explicitly, or persist two scalar keys.
- **Raw enum still leaks into the last-run strip (WARNING, unchanged — IN-01):** `queue.html:30` is `{{ last_run.reason or 'unknown' | human_label }}`; Jinja's `|` binds tighter than `or`, so `human_label` only ever applies to the `'unknown'` fallback (`all_filtered` → `all_filtered`, `None` → `Unknown`). Same bug at `runs.html:66`. Fix: `{{ (last_run.reason or 'unknown') | human_label }}`.
- **Raw cap token still leaks into the ranking strip (WARNING, unchanged):** `queue.html:151` interpolates `cap_reason` unfiltered, so the D-93 sentence reads *"Ranked 12 of 40 — cap reached (per_run)"*.
- **The queue CV line overstates (WARNING, unchanged — IN-03):** `_health_strip.html:26-27` is unconditional and asserts "ranking is skipped until one is supplied", which is wrong when `Settings.ranking_enabled` is false.
- **Pager copy nit (minor, NEW):** on a single-page queue the pager renders a lone `Page 1 of 1 (25 per page)` with no controls. The summary defends it ("the page size is itself the answer"), but "1 of 1" carries no information and reads as a stray line. Consider suppressing the pager when `page.page_count == 1` unless a control is present.
- **Low-context link text (unchanged):** the queue row's only path to the fit breakdown is a bare **"Details"** link (`_listing_row.html:37`) — for the phase's headline capability it says nothing about fit breakdown or why this score.

### Pillar 2: Visuals (3/4)

**What is good.** Clear focal point per surface; section `h3`s, a bordered factor table with uppercase muted `th`s, and badges carry the hierarchy. **No icon-only buttons exist** — every control, including the new pager, carries a text label. External anchors are `rel="noopener noreferrer"` and render only when the URL is truthy. The new `#queue-pager` is a semantically correct `<nav aria-label="Queue pagination">` (`queue_list.html:84`).

**Findings.**
- **Pager layout instability (WARNING, NEW):** as Top-3 fix 3 — omitted Previous/Next move the position line horizontally between pages. A stable three-slot row (disabled-at-boundary) is the conventional fix.
- **The grand-total count does not disclose pagination (WARNING, NEW):** `#queue-count` renders `page.total` as `"30 listings"` at the **top** of the fragment (`queue_list.html:17`), while the only indication that the list is paginated — `Page 1 of 2 (25 per page)` — sits at the **bottom**, below the table (`:94`). A user reading "30 listings" over a 25-row table reasonably concludes all 30 are present until they scroll to the bottom. The two are styled near-identically (`.95rem` vs `.9rem`, both `--color-muted`), so there is no hierarchy distinguishing "how many matched" from "where you are". Fix: make the count line paging-aware (e.g. `30 listings · page 1 of 2`) or duplicate the pager above the table.
- **The pager has no `flex-wrap` (minor, NEW):** `#queue-pager{display:flex;gap:1rem}` (`input.css:468`). At 375 px with a three-digit page size (`Page 12 of 34 (100 per page)`) the row cannot wrap and will overflow. Desktop-first per D-16, so minor — but the fix is one property.
- **The Core Value's prerequisite is still buried (unchanged):** the CV fact-store status renders inside `#source-health` (`_health_strip.html:21-30`), the **last** section of the queue page (`queue.html:169`), below the queue table.
- **The requirement list colours whole sentences (unchanged):** `listing_detail.html:86` puts `req-met`/`req-partial`/`req-gap` on the `<li>`, so an entire requirement sentence renders green/amber/red — the direct cause of the Pillar 3 contrast failures.
- **The score badge has no accessible context (unchanged):** `_listing_row.html:49` renders `<span class="badge badge-score">0.82</span>` inside a cell headed by the vague "Signals"; nothing says it is a fit score out of 1.0.

### Pillar 3: Color (2/4)

**Token discipline is good.** The pager introduces **no new colour and no hardcoded hex** — `#queue-page-position` uses `--color-muted`, and the Previous/Next buttons inherit the generic `button` rule (border `--color-border`, background `--color-paper`, ink text). `#queue-page-position` (`#6b7280` on white) = **4.83:1** — passes. The phase's 60/30/10 distribution remains sound; the accent family stays on links, the score badge, and primary actions.

**Findings — four AA failures remain, all unchanged by 05-11 (WARNING, accessibility). Ratios recomputed from the current compiled CSS:**

| Pairing | Ratio | AA |
|---|---|---|
| `.req-met` `#059669` on white | **3.77:1** | FAIL |
| `.badge-score-tier-high` `#059669` on `#ecfdf5` | **3.58:1** | FAIL |
| `.badge-score-tier-low` `#6b7280` on `#f3f4f6` | **4.39:1** | FAIL |
| `code` on `--color-surface-2` inside `.cv-status` / `.settings-note` / `.detail-not-ranked` | **4.39:1** | FAIL |
| `#queue-page-position` `#6b7280` on white (**NEW, pager**) | 4.83:1 | pass |
| `.req-partial` `#b45309` on white | 5.02:1 | pass |
| `.badge-score` `#1d4ed8` on `#eff6ff` | 6.16:1 | pass |

Fix: darken the success token (e.g. `#047857`, ~5.1:1), move verdict colour off the sentence body onto a chip, and give `code` an explicit ink colour inside muted contexts. None of this is pager-specific — it is the surviving phase-level debt.

### Pillar 4: Typography (3/4)

**What is good.** A compact, intentional set: `.badge` 12 px/600, table `th` 12.8 px/600 uppercase, controls `.85rem`, body 1rem, section `h3` 1.25rem, weights 400/500/600/700 only. The pager adds `#queue-page-position` at `.9rem` and inherits `.85rem` buttons — both already in use elsewhere, so the pager introduces **no new size or weight**. Score badge and evidence IDs use `--font-mono`; `.detail-rationale` is capped at `65ch`.

**Findings.**
- The requirement verdict (`<strong>{{ entry.verdict }}</strong>`) and the requirement text share size and weight; hierarchy rests on colour alone — the Pillar 3 problem. → recommendation.
- The `confidence_tier` badge prints the raw lowercase token (`high`/`medium`/`low`) with no "confidence" label. → minor, copy-adjacent.
- `badge` at 12 px bold carries the row's most important number (the fit score). → minor.

### Pillar 5: Spacing (3/4)

**What is good.** A single coherent rem scale; table cells `.875rem 1rem`, cards `1.25rem`, page gutters `1.5rem 1rem 3rem`. **No arbitrary `[Npx]`/`[Nrem]` values anywhere.** The new pager uses `gap:1rem` and `margin-top:1rem`, consistent with the surrounding system, and `.queue-count` keeps its `margin-bottom:.75rem`. Grouping is consistent (`gap:.5rem` action clusters, `.25rem` label/field stacks).

**Findings.**
- **No `flex-wrap` on `#queue-pager` (minor, NEW):** see Pillar 2. One-property fix.
- **The pager's `margin-top:1rem` is the only separation from the table.** The table carries `border-radius` + `box-shadow`, so 1rem reads as slightly tight against the pager row. → minor observation.
- Two chip padding scales coexist (`.badge{padding:.2rem .5rem}` vs `.rule-chip{padding:.25rem .625rem}`) with no documented canonical scale. → minor, pre-existing.

### Pillar 6: Experience Design (2/4)

**What 05-11 got right.** G-05-3 is genuinely closed: paging is now two-way, the page model is derived (no schema, no route, no migration), the page size stays server-fixed (T-02-28 pinned by `test_the_page_size_is_server_fixed_and_only_surfaced`), and the first/last-page behaviour is pinned by tests. The four `QueuePage` accessors are total (`max(1, limit)` guards). Broad state coverage from 05-08/09/10 is retained.

**Findings.**
- **Detail-page Save/Hide is inert (BLOCKER, unchanged):** `listing_detail.html:103,114` → dead `#listing-row-*` target; htmx raises `htmx:targetError` and performs no swap. See Top-3 fix 1. Highest-impact open defect in the phase; neither 05-09, 05-10 nor 05-11 touched it.
- **No scroll reset after any `#queue-list` swap (WARNING, NEW):** see Top-3 fix 2. Affects the pager, the filter form, the toggles, and the search input.
- **No busy state and no request coalescing on the pager (WARNING, NEW):** `queue_list.html:86-102` has no `hx-indicator`, `hx-disabled-elt`, or `hx-sync` (verified: **zero** `hx-indicator`/`hx-disabled` matches across all templates). A double-click or two fast clicks on Next fire overlapping `GET /queue/list` requests (offset 25 and offset 50); htmx 2.0.10 does not abort in-flight requests to the same target, so responses can land out of order and the user can end up on an unintended page. Nothing tells the user a page load is in flight. Fix: `hx-disabled-elt="this"` (or `hx-sync="closest nav:replace"`) on both pager controls.
- **The pager's `aria-live="polite"` region is the whole list (WARNING, NEW):** the pager lives inside `<div id="queue-list" aria-live="polite">` (`queue.html:164`). Every page swap therefore announces the count, both action buttons, the full 25-row table, and the pager — a screen-reader flood for a control that changed one line. Fix: move the live region onto `#queue-count`/`#queue-page-position` only, or set `aria-live="off"` on the table.
- **No URL/history state (WARNING, documented trade-off, NEW):** the pager deliberately sets no `hx-push-url` (`05-11-SUMMARY.md` decision). The consequence is that the current page is not in the URL, browser Back does not return to the previous page (it leaves the queue), and a refresh always returns to page 1. The in-page Previous control is the only backward affordance. Acceptable for a local tool, but it is a real limitation of the new pager and should be named as such.
- **The 5000-row scan cap now manifests as a wrong page count (WARNING, inherited — CR-01):** the default score path sets `total = len(enriched)` where `enriched` is built from `_score_candidate_ids` bounded by `SCORE_SORT_SCAN_LIMIT = 5000` (`queue_repo.py:454-477, 553`). Beyond 5 000 matches, `page.total` under-reports, so `page_count` is wrong and Next disappears while listings remain unshown. The old "Load more" hid this as a silent truncation; the new position line makes it a visibly wrong `Page X of Y`.
- **A junk threshold silently hides every scored listing (WARNING, inherited):** `?min_score=nan`/`inf` passes `_float_or_none` (`routes.py:122-129`, bare `float()`), and `total_score >= nan` is False for every scored row, emptying the queue of scored jobs. Still pinned by the one remaining strict-xfail sentinel.
- **No busy state on the primary run action (WARNING, inherited):** `queue.html:7-13` has no `hx-indicator`/`hx-disabled-elt`/`aria-busy`.
- **The 404 has no way back (minor, inherited):** the fragment from `app/api/listings.py:67-72` renders without the base layout/nav.

---

## Registry Safety

Skipped: no `components.json` exists (this is a Jinja2 + HTMX + vendored-Tailwind app, not a shadcn project), and no third-party registry blocks are declared anywhere. Re-verified this run. No registry audit performed.

---

## Files Audited

**Re-read and re-verified this run:**

- `app/web/templates/html/queue_list.html` — the `#queue-pager` nav (`:84-104`): `#queue-page-prev` only when `has_prev` (`:85-93`), `#queue-page-position` on every non-empty page (`:94`), `#queue-page-next` only while `has_more` (`:95-103`); no `show:` modifier, no `hx-disabled-elt`, no `hx-sync`
- `app/web/templates/html/queue.html` — `#queue-count` at top of fragment, pager at bottom; `#queue-list` `aria-live="polite"` (`:164`); raw `reason` (`:30`) and `cap_reason` (`:151`) leaks confirmed
- `app/db/repositories/queue_repo.py` — `QueuePage.has_prev`/`prev_offset`/`page_index`/`page_count` (`:284-301`); `next_offset` (`:276`); score-path `total = len(enriched)` bounded by `SCORE_SORT_SCAN_LIMIT` (`:553`, `:454-477`)
- `app/web/routes.py` — `_queue_context` (`count = page.total`), `GET /queue/list`, server-fixed `limit=settings.queue_page_size` (`:151`)
- `assets/tailwind/input.css` (`:458-478`) + compiled `static/vendor/app.css` — `.queue-count`, `#queue-pager{display:flex;gap:1rem;margin-top:1rem}`, `#queue-page-position{color:muted;font-size:.9rem}`; contrast ratios recomputed
- `app/pipeline/run.py:976` — nested `ranking` marker merged into `reason_counts` (the WR-01 dict-repr source)
- `app/web/templates/html/listing_detail.html:103,114` — inert `#listing-row-*` htmx targets (BLOCKER) confirmed
- `app/web/templates/html/runs.html:106-112` — generic `reason_counts` loop → dict repr
- `app/web/templates/html/_listing_row.html` — badges (`:48-50`), `Details` link (`:37`), row action forms (`:70-91`)
- `static/vendor/htmx.min.js` — v2.0.10; `show` acts only when truthy (no default window scroll)
- Tests: `tests/api/test_queue_excluded.py` (pager regexes + first/last-page, server-fixed-limit, full-page assertions), `tests/test_stylesheet_coverage.py`, `tests/api/test_queue_ranked.py`, `tests/api/test_listing_detail.py` → **39 passed**
- `.planning/phases/05-ranking-core-value/05-11-PLAN.md`, `05-11-SUMMARY.md`, `05-CONTEXT.md` (D-88…D-100)

**Note on screenshot hygiene:** `.planning/ui-reviews/.gitignore` exists and ignores `*.png`/`*.webp`/`*.jpg`/`*.jpeg`/`*.gif`/`*.bmp`/`*.tiff`. The gitignore gate was re-run before any capture attempt (none succeeded — no server). No binaries were written by this audit.

---
_Reviewed: 2026-09-23_
_Reviewer: the agent (gsd-ui-auditor)_
_Baseline: abstract 6-pillar (no UI-SPEC.md exists)_
_Round-3 delta: 05-11 landed — G-05-3 closed (two-way pager, "Load more" mislabel gone); new pager interaction gaps (no scroll reset, absent-not-disabled boundaries, no busy/race); detail-page Save/Hide BLOCKER remains_
