---
phase: 08-operations-polish
status: issues_found
audited: 2026-10-14
baseline: 08-UI-SPEC.md (approved 2026-10-14; CHECKER SIGN-OFF still `pending` at audit time)
screenshots: not captured (no dev server on :3000, :5173, :8080 or :8000; no browser, no Docker in the sandbox)
audit_method: code/contract audit (Tailwind source + committed build, template class/attr audit, copy-string audit, state-coverage check, stylesheet byte-identity guard re-run)
registry_audit: skipped (no components.json — shadcn_initialized false; no third-party registry declared)
overall_score: 20/24
blockers: 0
unverified_rendered_claims: 5
---

# Phase 08 — UI Review

**Audited:** 2026-10-14
**Baseline:** `08-UI-SPEC.md` (approved 2026-10-14). The spec's own `## Checker Sign-Off` block is still `pending`, but its content is the binding contract and is what this audit scores against.
**Screenshots:** **not captured.** Ports 3000 / 5173 / 8080 / 8000 all returned `000`; no browser and no Docker exist in the sandbox, so no rendered pixels were observed and none were fabricated. This is a **code/contract audit**: the Tailwind source + its committed build, the template class/attribute audit, the copy-string audit, the state-coverage check, and the stylesheet guard re-run.
**Screenshot hygiene:** `.planning/ui-reviews/.gitignore` re-verified **before** any capture attempt (present; ignores `*.png|webp|jpg|jpeg|gif|bmp|tiff`). No binaries were written this audit.
**Deployment baseline (CR-01 equivalent):** re-checked. `tests/test_stylesheet_coverage.py` → **10 passed** (49.7 s — the byte-identity guard `test_the_committed_stylesheet_is_the_build_of_its_source` *ran* the pinned `tailwindcss@4.3.3` CLI rather than skipping), so the committed `static/vendor/app.css` is the reproducible build of `assets/tailwind/input.css`. `tests/test_no_cdn.py` → **7 passed** (every UI asset is local and vendored; `base.html:8-10` links only `/static/vendor/*`). The pre-existing artifact drift that 08-01 logged and 08-02 rebuilt is closed.
**Registry audit:** skipped — `components.json` absent, `shadcn_initialized: false`, no third-party registry declared. No block entered the contract, so no vetting gate ran.
**Unverified rendered claims (recorded, not passed):** the 44×44px box sizes, the `@variant max-md` card-reflow at 320/375px, the `overflow-wrap:anywhere` long-token backstop, the desktop table inside its 768px scroll region, and the `.health-badge`-on-a-`<td>` phone rendering are all only observable in a real browser. They are carried by `docs/runbook-responsive-ui.md` (operator-run, D-161) and are **not** asserted as passing here.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | `/status` and prune copy are specific and near-verbatim, but the declared `Adzuna hedge:` verdict prefix ships as `Indeed hedge:`/`Linkedin hedge:`, and the declared schedule helper string is replaced by different wording. |
| 2. Visuals | 3/4 | `/status` order, the `.table-scroll` regions and the journey reflow all match the contract; `.listing-error` is still undefined, and the tracker's `#application-filters` form has no stylesheet rule at all (unlike `#queue-filters`). |
| 3. Color | 4/4 | Exact token reuse, zero hardcoded hues in phase-8 templates, accent confined to the declared list, danger-card painting the prune confirm as the spec intends. |
| 4. Typography | 4/4 | Zero `text-*`/`font-*` utility classes; no new sizes or weights; the reflow changes layout only. |
| 5. Spacing | 3/4 | The 07 44×44px floor is now implemented and grouped (`.touch-target` + `.queue-toggle`), but the spec's named "prune controls" and "health page's compact links" still do not carry it. |
| 6. Experience Design | 3/4 | Thorough total-function state coverage across `/status`, prune and schedule with keyboard-reachable scroll regions and no new JS; `#settings-banner` is not the `role="status" aria-live="polite"` region the spec claims. |

**Overall: 20/24 — no blocking issue.**

---

## Top 3 Priority Fixes

1. **The named prune/schedule controls are the last ones under the 44×44px floor** — `08-UI-SPEC.md` §Spacing names "**the prune controls**" in the `.touch-target` list. `grep -rn "touch-target" app/web/templates/html/settings.html` → **zero matches**: `#prune-preview-submit` (`settings.html:330`), `#prune-confirm-submit` (`settings.html:356`) and `#schedule-submit` (`settings.html:269`) render at the shipped `button[type="submit"]` box (padding `0.5rem` + `line-height:1.25` on `1rem` ≈ **38px**, no `min-width`). **User impact:** the one irreversible control in the app (`Delete permanently`) is under the tap floor on the phone layout the phase exists to make first-class. **Fix:** add `class="touch-target"` to those three submits (the class and its rule already exist, `input.css:1906-1910`), then rebuild `static/vendor/app.css` with the pinned CLI — never hand-edit the artifact (`tests/test_stylesheet_coverage.py` byte-identity guard).
2. **`.listing-error` is still undefined, so a refused tracker transition is visually untreated** — `app/api/applications.py:90` emits `class="listing-row listing-error"`, but `listing-error` resolves to **no rule** in `assets/tailwind/input.css` or `static/vendor/app.css` (`grep` → zero). This is 07-UI-REVIEW Top Fix 3, unaddressed by phase 08 even though phase 08 rebuilt the stylesheet. **User impact:** the refusal message is present but reads as an untargeted plain row; the state looks like a no-op. **Fix:** define `.listing-error` in `input.css` (reuse `--color-danger-bg`/`--color-danger`, mirroring `.health-unreachable`) or render the fragment through an existing danger/notice class, then rebuild.
3. **Two declared `/status` copy strings are not what ships** — (a) the verdict label: UI-SPEC `## Copywriting Contract` line 182 and the `## UI Considerations` long-text row both declare `Adzuna hedge: 2/3 blocked runs — condition not met`, but `app/api/health_page.py:307` builds `f"{board.title()} hedge"` and `health.html:57` loops `PROMOTION_BOARDS`, so the page renders **two** lines reading `Indeed hedge: …` and `Linkedin hedge: …`; (b) the schedule helper: the spec declares `The pipeline runs once a day at this time, in {timezone}.` but `settings.html:262` ships `Times are read in this timezone, not the container's UTC.`. **User impact:** the audit trail (`08-UI-SPEC.md`) and the pixels disagree, so a future reader cannot tell intent from behaviour. **Fix:** either amend `08-UI-SPEC.md` to the shipped strings (the per-board label is arguably clearer since P-1 is computed per board) or change `health_page.py:307` / `settings.html:262`. Do not leave both claims standing.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

Audited every declared string in `## Copywriting Contract` and `### Phase-specific copy` against the templates and routes.

**Matched exactly:**
- `/status`: H2 `Health` (`health.html:6`), H3 `System` (`:12`), intro `Read from recorded run outcomes — opening this page never contacts a job board.` (`:14`), `Scheduling off` (`:29`), `Run history` link (`:47`), `Read the probe verdict` (`:60`), the four dependency labels (`Database`, `LLM backend`, `LaTeX engine`, `CV fact store` — `health_page.py:141-162`) and the detail strings `reachable — version {v}` / `unreachable ({ErrorClass})` / `no server password configured` / `available — version {v}` / `not available ({ErrorClass})` / `loaded from {path}` / `no readable CV fact store at {path} — ranking is skipped until one is supplied.` (`health_page.py:102-162`), and `Open the following per-source strings` `No sources registered yet.` (`_health_strip.html:67`).
- Schedule: `Run once a day` (`settings.html:248`), `Run at` (`:251`), `Timezone` (`:258`), `Save schedule` (`:269`), `Schedule saved.` (`settings.py:506`), `That time could not be understood. Pick a time of day and try again.` (`settings.py:490`), and the D-154 helper `Missed runs are skipped, never caught up, and a run already in progress is never overlapped.` (`settings.html:265`).
- Prune: H3 `Prune history` (`:302`), the intro (`:304-306`), labels `Category`/`Older than`/`days` (`:309,317,324`), `Preview deletion` (`:330`), `Delete permanently` (`:356`), `This cannot be undone.` (`:355`), the protected line `Kept regardless: the last {N} runs, the LLM call ledger, CVs attached to an application, and each listing's newest verified CV.` (`:347-348`), the empty copy `Nothing matches this threshold — nothing would be deleted.` (`settings.py:124`, `settings.html:343`), and the declared error `The preview could not be computed. Nothing has been deleted.` (`settings.py:123`) — verbatim.
- Nav entry `Health` (`base.html:34`).
- No generic `Submit`/`OK`/`Cancel`/`Save` labels anywhere in the phase-8 surfaces.

**Findings:**
1. **Verdict prefix diverges (WARNING)** — spec `Adzuna hedge:`; shipped `Indeed hedge:` / `Linkedin hedge:` on two `.ranking-strip` lines (`health_page.py:307,313,334`; `health.html:56-63`). Test-locked at `tests/api/test_health_page.py:540,554` (`adzuna-verdict-indeed`). See Top Fix 3.
2. **Schedule helper reworded (WARNING)** — spec `The pipeline runs once a day at this time, in {timezone}.` vs `settings.html:262`. See Top Fix 3.
3. **Undeclared schedule state (INFO)** — `health.html:31` renders `No run currently scheduled.` for `state == 'unscheduled'` (`health_page.py:235,242,248`). The copy table declares only three variants (`Next run in …` / `Next run at … — in …` / `Scheduling off`). The added state is honest (a disabled/missing scheduler must not print a made-up time) but is not in the contract; `tests/api/test_health_page.py:361` pins it.
4. **Prune preview summary shape (INFO)** — spec's illustrative row is `This will delete 42 runs, 118 artifacts, 3.1 GB.`; `settings.html:338` ships `This will delete {{ count }} {{ noun }} · {{ size_display }}.` (one noun + a `·`). The one-category-per-prune design (D-163) makes the single-noun form correct, so this is a spec row that should be rewritten, not a defect.
5. **The empty-preview sentence renders twice (INFO)** — `settings.py:1104` passes `banner=PRUNE_EMPTY` **and** `settings.html:343` hardcodes the same sentence inside `#prune-preview`, so one page shows it in both `#settings-banner` (top) and the panel. Harmless duplication; pick one surface.
6. **Carried forward from 07 (WARNING, out of this phase's contract)** — the declared `Saved` success banner for tracker status/notes is still absent (`app/api/applications.py` re-renders the row with no banner; `grep -rn '"Saved"' app/api/applications.py` → none), and the drafting-failure copy is still the 07-reworded string. Phase 08 did not take these on; they remain open from `07-UI-REVIEW.md` Top Fixes 2 and 3 (the `.listing-error` half is Top Fix 2 here).

### Pillar 2: Visuals (3/4)

- **`/status` layout matches §B top-to-bottom** — `<section id="health-system">` with the `<dl class="health-system">` definition grid (`health.html:11-22`), schedule line (`:26-36`), skip notice (`:40-42`), last-run line (`:44-49`), verdict region (`:56-63`), then the queue's own `_health_strip.html` included verbatim (`:67`). One definition, so the strip and the page cannot drift (D-138).
- **Accessible scroll regions implemented per D-160** — `<div class="table-scroll" role="region" tabindex="0" aria-label="…">` wraps the runs table (`runs.html:27`), the merges table (`merges.html:43`) and the detail factor table (`listing_detail.html:63`); the criteria rule list is correctly **not** wrapped, and each `<table>` keeps its own class. `role="region"` is on the wrapper, never on the `<table>` — exactly the contract's warning. The `.table-scroll` rule is in the build (`app.css`: `.table-scroll{max-width:100%;display:block;overflow-x:auto}`).
- **Focal point:** the `.health-badge` column remains the scanning anchor on both the strip and `/status` (single colour-coded cell per row), and the per-source table keeps its `.health-table` shell verbatim.
- **Finding (WARNING):** `.listing-error` undefined → a refused tracker transition has no danger treatment (`.listing-error` resolves in neither `input.css` nor the build). See Top Fix 2.
- **Finding (WARNING):** the tracker's own filter form is unstyled — `applications.html:14` declares `<form id="application-filters">`, but **no rule for `#application-filters`, `#application-search`, `#application-stage` or `#application-toggle-*` exists** in `input.css` or `app.css` (`grep` → zero), while the queue's equivalent `#queue-filters` has a full card shell (`input.css:499+`: flex, gap, padding, `--color-surface` background). The tracker therefore renders as a bare stacked form next to the queue's filter card — a visible inconsistency between the two journey pages, and the phase's reflow block only names `#queue-filters` (`input.css:1979`), so the tracker also gets no phone full-width treatment. The spec literally names only `#queue-filters`, so this is arguably in-contract; the *intent* ("the journey's stacked controls go full-width … nothing needs a pinch-zoom", §A) and the D-161 tracker walk are not met.
- **Finding (WARNING):** no positive visual state after a successful tracker status/notes save (carried from 07).
- **Finding (INFO):** `/status` heading depth runs H2 `Health` → H3 `System` → H2 `Source health` (the included partial's own `<h2>`). Correct per the contract's per-source heading, but the depth oscillates.
- **Unverified:** whether `.health-badge` (a class with background/padding, `input.css:1650-1659`) applied directly to a `<td>` (`_health_strip.html:54`) reads as a full-width coloured block once the reflow sets `.health-table td { display:block }` (`input.css:1931-1937`). This needs pixels; recorded as unverified, not passed.

### Pillar 3: Color (4/4)

- **No hardcoded hues introduced** — `grep -rnoE "#[0-9a-fA-F]{3,8}|rgb\("` over the phase-8 templates yields only `&#9733;`/`&#8594;` numeric character references (false positives), never a colour literal. No inline `style=` attributes anywhere.
- **Exact token reuse, no new classes:** the status pill is `<span class="health-badge health-{{ row.tone }}">` (`health.html:19`) over the shipped `.health-ok` / `.health-unreachable` / `.health-unknown` variants (`input.css:1661-1675`) — the mapping matches the spec's status-semantics table row for row (CV fact store absent → `.health-unknown`, never `.health-unreachable`; `health_page.py:159`). The verdict token is chosen by the recorded condition — `.req-partial` (warning) for not-met, `.req-met` (success) for met, `.health-empty` (muted) for absent (`health_page.py:311,331`).
- **60/30/10 holds** — paper `#ffffff` surfaces everywhere, `--color-surface`/`--color-surface-2` on the cards, nav, ranking strips and chips, and accent `#2563eb` confined to the declared list: primary submits, links, `.nav-current`, `#run-search-now` / `.apply-link`, `:focus-visible`. Nav links at rest are `--color-ink`, not accent (`input.css:202-212`).
- **Destructive scope exactly as specified** — `.danger-card button[type="submit"]` (`input.css:1776-1785`) paints `Reset queue data`, `Preview deletion` and `Delete permanently` with `--color-danger`; the spec explicitly sanctions `Preview deletion` inheriting danger inside the danger card.
- No deviations found.

### Pillar 4: Typography (4/4)

- `grep -rohE "text-(xs|sm|base|lg|xl|2xl|3xl|4xl|5xl)" app/web/templates/html/` → **zero**; `grep -rohE "font-(thin|light|normal|medium|semibold|bold|extrabold)"` → **zero**. All sizing/weight comes from reused component rules, as the contract requires.
- No new sizes or weights declared this phase: the only new typographic-adjacent rule, `.health-system` (`input.css:1914-1919`), copies `.run-reason-counts` (the spec's stated source) and declares layout only. `.touch-target` adds a box floor with no type change.
- **No size change at the breakpoint** — the `@variant max-md` block (`input.css:1925-1991`) declares `display`, `position`, `overflow-wrap`, `border`, `padding`, `content`, `font-weight:600` on the label line and widths — no `font-size`. The type scale is identical in both regimes.
- The label line copies the declared `font-weight:600` + `var(--color-muted)` pair (`input.css:1969-1975`), matching the spec's Spacing/Typography notes.
- No deviations found.

### Pillar 5: Spacing (3/4)

- **No arbitrary values** — `grep -rnE "\[[0-9.]+(px|rem)\]" app/web/templates/html/` → none; all spacing comes from shipped rules.
- **The 07 44×44px floor is now implemented** — `.touch-target, .queue-toggle { min-height: 2.75rem; min-width: 2.75rem }` (`input.css:1906-1910`; two `2.75rem` occurrences present in the committed build). The rule actually bites because every target is a non-inline box: `button`/`.button` are `display:inline-flex` (`input.css:252`), `.nav-link` is `display:inline-flex` (`input.css:202`), `<summary>` is a block-level list-item. Applied to `Copy answer` (`_screening_drafts.html:46`), both `History (n)` summaries (`_application_row.html:67`, `_application_history.html:9`), all six nav links (`base.html:28-34`) and both pagers (`queue_list.html:87,98`, `applications_list.html:56,67`); the journey filter labels are covered by grouping `.queue-toggle` into the same rule rather than editing `queue.html`/`applications.html`. **07-UI-REVIEW Top Fix 1 is closed for the journey.**
- **Gap (WARNING):** the spec's §Spacing list also names "**the prune controls**" and "**the health page's compact links**", and neither carries `.touch-target` (`grep -rn "touch-target" settings.html health.html` → zero). The prune submits (`settings.html:330,356`) stay at ≈38px. The health-page links (`#health-run-history` `health.html:47`, `#probe-verdict-*` `:60`) are inline `<a>` inside a `.ranking-strip` paragraph — `min-height`/`min-width` are inert on a non-replaced inline element, so that clause is **unimplementable as written** and is a spec defect rather than an implementation one. Either way the contract is not fully delivered.
- **Reflow spacing matches the contract** — card border + `0.5rem 0` padding per row (`input.css:1954-1958`), clip-hidden `thead` (not `display:none`, `:1943-1951`), `overflow-wrap:anywhere` on the value cells so a long source name or deep CV path cannot widen the page (`:1962-1965`), and full-width journey controls (`:1979-1985`).
- Anchor values and micro-step reuse are honoured; nothing was normalised.

### Pillar 6: Experience Design (3/4)

State coverage was checked against the spec's `## UI Considerations` table (17 covered + 1 backstop).

- **Every `/status` degradation is a total function** — `page_context` guards the dependency report, the source read, the schedule read, the skip notice, the last run and each board's verdict independently (`health_page.py:176-208,231-267,288-295,340-353`), so one failure degrades one line and the page always answers (D-08/T-08-20). Empty states: no sources → `.health-empty` + `No sources registered yet.`; no runs → no last-run line; disabled → `Scheduling off`; unscheduled → an honest no-time line; absent verdict → `no verdict recorded yet` with **no number** (`health_page.py:308-315`, asserted at `tests/api/test_health_page.py:570`).
- **Read-only evidence, no control** — `<section id="adzuna-verdict" aria-label="Adzuna promotion verdict">` contains only `.ranking-strip` paragraphs and the probe link (`health.html:56-63`); asserted at `tests/api/test_health_page.py:573-590` (no `<form>`, no `<button>`, exactly one anchor per board, no `enable`).
- **Destructive flow is two-step and no-JS safe** — preview (`settings.html:307-332`) then a **separate** confirm form (`:351-358`) that carries the category/threshold as hidden inputs; both are plain full-page POSTs, so a link or prefetch can never destroy anything, and the confirm form is absent when the preview is empty (`:350`). Refusals return the page with the cause (`settings.py:1012,1023,1125,1163`) and a real prune always writes an audit banner (`settings.py:1181-1194`).
- **Schedule:** invalid input → `400` + banner and the row is untouched (`settings.py:489`); success → `Schedule saved.` (`:506`); a post-commit scheduler failure is reported without rolling back the save (`:511-517`).
- **Keyboard:** the admin tables are keyboard-scrollable `role="region" tabindex="0" aria-label="…"` regions (`runs.html:27`, `merges.html:43`, `listing_detail.html:63`) — the D-160 requirement — and the `:focus-visible` ring is global.
- **No new JavaScript** — the phase adds no Alpine state and no HTMX swap (D-160); the prune and schedule forms work with JS off.
- **Finding (WARNING):** `#settings-banner` (`settings.html:13`) is a bare `<p class="settings-banner…">` with **no `role="status"` and no `aria-live`**, yet the spec's UI-Considerations row asserts "the existing `role="status" aria-live="polite"` banner region (`#settings-banner`) reports the result" (spec line 368) — a stated guarantee the code does not deliver (CONVENTIONS rule 6). Impact is low because both writes are full-page POSTs (the document reload replaces the region), but the inconsistency is real: the sibling `#cv-upload-result` (`settings.html:188-192`) and `#cv-upload-progress` (`:177-184`) **do** carry `role="status" aria-live="polite"`. Add the attributes or drop the spec claim.
- **Finding (WARNING, carried):** no success confirmation on tracker status/notes save (07 Top Fix 2).
- **Unverified:** the long-token 🧪 backstop (a long source name and a deep CV path must not widen the 320/375px page) rests on `overflow-wrap:anywhere` (`input.css:1962-1965`) and can only be confirmed in a browser — recorded as unverified per the runbook, not passed.

---

## Registry Safety

Not applicable — `components.json` is absent (`shadcn_initialized: false`) and no third-party registry is declared in `08-UI-SPEC.md` §Registry Safety. No block entered the contract, so no vetting gate ran and no `⚠️ REGISTRY FLAG` applies.

---

## Minor Recommendations

1. `#settings-banner` missing `role="status" aria-live="polite"` (`settings.html:13`) — see Pillar 6.
2. Give `#application-filters` the shipped filter-card shell (or at least the phone full-width rule) so the tracker's filter row matches the queue's (`applications.html:14`, `input.css:499+`, `:1979`).
3. Render the empty-preview sentence in one surface only (`settings.py:1104` banner vs `settings.html:343` panel).
4. The timezone `<select>` offers exactly one option (`settings.html:259-261`, `ALLOWED_TIMEZONES = {"Europe/Dublin"}`) — a control that looks interactive and cannot change. Consider a labelled read-only value, or widen the allow-list.
5. Heading depth on `/status` oscillates H2 → H3 → H2 (`health.html:6,12` + `_health_strip.html:8`).
6. `docs/runbook-responsive-ui.md:22` still says "The health page (`/status`) lands in plan 08-04. If it is not built yet, skip" — stale now that 08-04 shipped.
7. Amend the spec's `## Copywriting Contract` rows the implementation has legitimately superseded (the prune count/size shape; the per-board verdict label; the added `No run currently scheduled.` state) so the audit trail and the pixels agree.
8. Carried from 07 and still open: the `Saved` confirmation (Top Fix 2 there) and the drafting-failure copy wording.

---

## Files Audited

Templates (`app/web/templates/html/`):
- `base.html` (nav block `:27-35`, vendored-asset links `:8-10`)
- `health.html` (the whole `/status` page)
- `_health_strip.html` (shared strip, `data-label` cells `:52-62`)
- `settings.html` (schedule card `:235-272`, prune control `:298-361`, danger zone, banners)
- `queue_list.html` (reflow table `:56-74`, pagers `:84-106`)
- `_listing_row.html` (8 `data-label` cells `:37-65`)
- `queue.html` (filters `:42-127`, run control)
- `applications.html` (filters `:14+`)
- `applications_list.html` (reflow table, pagers)
- `_application_row.html` (6 `data-label` cells, `History (n)` summary `:67`)
- `_application_history.html`, `_screening_drafts.html` (`Copy answer` `:46`)
- `runs.html` (`table-scroll` region `:27`), `merges.html` (region `:43`), `listing_detail.html` (region `:63`)

Stylesheet:
- `assets/tailwind/input.css` — responsive block `:1887-1992` (`.table-scroll` `:1896`, `.touch-target`/`.queue-toggle` `:1906-1910`, `.health-system` `:1914-1919`, `@variant max-md` `:1925-1991`), `.danger-card button[type="submit"]` `:1776-1785`, `.health-*` `:1645-1708`, `.settings-card`/`.settings-banner`/`.settings-counts` `:1738-1768`, `.capability-warnings` `:1040-1046`, `.nav-link` `:202+`, `button`/`.button` `:252+`, `.queue-toggle` (after `:499`)
- `static/vendor/app.css` (committed build; `@media not all and (min-width:48rem)` present, `2.75rem` ×2, `.table-scroll`, `.health-system`, `td[data-label]:before` present)

Routes / logic:
- `app/api/health_page.py` (report assembly, schedule/skip/last-run/verdict lines, `HEALTH_PAGE_PATH = "/status"`)
- `app/api/health.py` (`dependency_report`, shared by the JSON endpoint and the page)
- `app/api/settings.py` (`PRUNE_*` copy `:121-124`, prune preview/confirm `:1090-1195`, schedule `:467-518`)
- `app/api/applications.py` (`_row_error` `.listing-error` `:90`)
- `app/web/templates/html/base.html` nav (7 entries, `touch-target`)

Evidence runs (this audit):
- `tests/test_stylesheet_coverage.py` → **10 passed** in 49.7 s (byte-identity CLI guard executed, not skipped)
- `tests/test_no_cdn.py` → **7 passed** (assets vendored, no CDN)

Planning artifacts:
- `08-UI-SPEC.md`, `08-01..08-05` PLAN/SUMMARY pairs (deviations: 08-01 stylesheet drift → rebuilt in 08-02; 08-02 five pinned-assertion updates; 08-03 four auto-fixes; 08-04 tz guard; 08-05 the no-JS threshold read-back), `docs/runbook-responsive-ui.md`, `07-UI-REVIEW.md`

---

## Verdict

**20/24 — no blocking issue.** Phase 08 delivers its three frontend commitments against the contract with high fidelity: the phone-first responsive contract (a correct, byte-reproducible `@variant max-md` reflow with complete and verbatim `data-label` cells on all 8 queue, 6 tracker and 5 health cells), the keyboard-reachable `.table-scroll` regions on the three admin tables, and the new `/status` page (contract-faithful structure, total-function state coverage, read-only evidence with no control). The 07 UI review's Top Fix 1 — the 44×44px touch-target floor — is **implemented and verified in source and build** for the journey controls, closing the phase's stated inheritance; the color and typography pillars are clean (no new hues, no new sizes or weights, no utility type classes, no hardcoded colours).

The remaining work is small and concrete: finish the touch-target floor on the three named prune/schedule submits, define `.listing-error`, harmonise the tracker's `#application-filters` with the queue's filter shell, add `role="status"` to `#settings-banner`, and reconcile the two declared copy strings the shipped page legitimately reworded. The five rendered-pixel claims (44px boxes, the 320/375/768 walk, the long-token backstop, the 768 scroll region, the badge-on-`<td>` phone rendering) stay **unverified** and are the operator's runbook to close — this audit does not assert them.

_Reviewed: 2026-10-14_
_Reviewer: gsd-ui-auditor_
_Baseline: 08-UI-SPEC.md (approved 2026-10-14)_
_Overall: 20/24 — no blocker; the responsive contract, the `/status` page and the admin scroll regions land, with the 44px floor complete except for the prune/schedule submits and the tracker filter shell left unvisualised._
