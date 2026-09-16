---
phase: 02-clean-filtered-queryable-queue
status: issues_found
audited: 2026-09-16
baseline: none (no UI-SPEC.md existed — see Baseline Substitution)
baseline_substituted: ROADMAP Phase-2 success criteria SC2/SC4/SC5 + the phase's own UI surface
screenshots: not captured (no dev server detected on :3000, :5173 or :8080)
rendered_markup_audited: true
overall_score: 10/24
blockers: 3
undefined_css_classes: 160 of 160
---

# Phase 02 — UI Review

**Audited:** 2026-09-16
**Baseline:** No UI-SPEC.md (substituted — see below)
**Screenshots:** not captured — no dev server on `:3000`, `:5173` or `:8080`, no
`uvicorn`/`gunicorn` process listening. Audit was performed on **rendered markup**
(the method's ground truth: the app exercised through an httpx ASGI client against a
real migrated temp DB) plus the compiled stylesheet. Every finding below is grounded
in output actually rendered during this audit, not inferred from templates alone.

---

## Baseline Substitution (read this first)

`/gsd-ui-review` declares `02-UI-SPEC.md` as its audit baseline. **No UI-SPEC.md was
ever created for Phase 2** — `ls .planning/phases/02-clean-filtered-queryable-queue/*-UI-SPEC.md`
returns nothing, and no `ui-phase` was run for this phase. The verify hook's `onError`
is `skip`, so the correct behaviour is to substitute, not to stall and not to invent a
contract.

**Substituted baseline (what this audit scored against):**

1. **ROADMAP Phase-2 success criteria** — SC2 (which rule fired and why is visible for
   an excluded listing), SC4 (queue is full-text searchable; a listing can be saved or
   hidden; new-since-last-visit and stale listings are distinguishable), SC5 (run
   history records what each run did, what it found, and why the queue is empty).
2. **The phase's own enumerated UI surface**, as supplied in the audit brief: the nine
   `app/web/templates/html/*.html` files and the six routes that serve them.
3. **The project's declared stack** (AGENTS.md / research STACK.md Q8): Jinja2 + HTMX +
   Alpine.js + Tailwind CSS 4, vendored, **no CDN**, no React/SPA, no Node at runtime.
4. **Abstract 6-pillar standards** for anything the above did not pin.

No design tokens, no declared spacing scale, no declared type scale and no copywriting
contract existed to audit against. That absence is itself reported as a finding
(see Pillar 2) rather than papered over.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Visual Hierarchy | **1/4** | No stylesheet delivers anything: 160 of 160 template classes have no rule, and Tailwind preflight actively strips heading size/weight — so `<h1>`–`<h4>` render identically to body text. |
| 2. Consistency with the Design System | **1/4** | The design system exists only as a class vocabulary. `input.css` is 11 lines and has contained zero custom CSS in its entire git history; `app.css` is a real Tailwind 4.3.3 build containing only preflight + theme. |
| 3. Responsive Behaviour | **2/4** | Phone-first is legitimately deferred to Phase 8 (D-16), but there are zero media-rule-driven layout rules and the 8- and 11-column tables have no `overflow-x` containment. |
| 4. Interaction / Affordance Clarity | **1/4** | Preflight reduces every button to `border:0; padding:0; background:transparent`, so `Save`, `Hide`, `Load more`, `Revert`, `Run search now` render as plain text with no clickable affordance. `dimmed` is a no-op. |
| 5. Empty / Error / Loading States | **2/4** | Good breadth of empty and error copy, but **zero** loading feedback, no double-submit guard, no htmx error handler, and the filtered-empty case shows the no-data-ever message. |
| 6. Accessibility | **3/4** | Strong native semantics (real `button`/`form`/`label for`/`th scope`/heading nesting, focus rings survive preflight); deductions for no `aria-live` on any of the six async swap regions and no `aria-expanded` on Alpine disclosures. |

**Overall: 10/24**

---

## Top 3 Priority Fixes

### 1. BLOCKER — The stylesheet layer was never written; the entire UI ships unstyled

**Evidence.** `assets/tailwind/input.css` is 11 lines: `@import "tailwindcss";` plus a
comment and `@source "../../app/web/templates"`. It defines **no component CSS**. Git
history confirms it has contained zero class definitions since it was created in
`9e5eb01` (Phase 1).

Tailwind only emits rules for class names it recognises as utilities. The templates use
**no Tailwind utilities at all** — 0 occurrences of `flex`, `grid`, `p-*`, `text-*`,
`bg-*`, `rounded`, etc. across all nine templates. They use only semantic component
names. Measured result:

- **160 of 160** real classes used in the templates have **no rule** in
  `static/vendor/app.css` (the 2 apparent matches, `not` and `or`, are artefacts of my
  extractor reading Jinja expressions — verified not real classes).
- The phase's specific new classes are all absent:
  `rule-chip`, `rule-chip-<kind>`, `dimmed`, `badge-new`, `badge-stale`,
  `listing-exclusion`, `listing-actions` → **0 occurrences each**.

Tailwind **preflight**, however, *is* present, and it makes the situation worse than
plain unstyled HTML by actively removing browser defaults:

```
h1,h2,h3,h4,h5,h6{font-size:inherit;font-weight:inherit}
ol,ul,menu{list-style:none}
table{text-indent:0;border-color:inherit;border-collapse:collapse}
button{box-sizing:border-box;border:0 solid;margin:0;padding:0}
```

(quoted verbatim from `static/vendor/app.css`)

So: every heading is the same size and weight as body text; every list loses its
bullets; tables have no borders and no cell padding (`td{` → 0 rules); and every
button and form control is reduced to borderless, backgroundless, paddingless text.

**User impact.** The phase's headline deliverable — a *clean* queue — does not exist.
There is no focal point, no scannable column structure, and no way to tell a button
from a label. `dimmed` being a no-op means an excluded listing is visually
indistinguishable from a kept one in the `Show excluded` view, which is the one view
SC2 depends on.

**Concrete fix.** Add the component layer to `assets/tailwind/input.css` (either
`@layer components { .rule-chip { ... } }` definitions for the existing vocabulary, or
rewrite the templates in Tailwind utilities), then rebuild
`static/vendor/app.css` with the Dockerfile's `assets` stage
(`tailwindcss -i ./assets/tailwind/input.css -o ./static/vendor/app.css --minify`) and
commit it. **Then add the missing guard test** — see the Process Note below.

---

### 2. BLOCKER — The excluded-listing chip prints the wrong number

**Evidence.** `app/db/repositories/queue_repo.py:433` sets each chip's `count` from
`rule_counts`, which is fetched at line 416 from `_page_rule_counts` (line 512) →
`excluded_counts_for_run` (`app/db/repositories/exclusion_repo.py:103`). That function
is a `GROUP BY rule_id` over **the whole run**, not over the listing.

Confirmed empirically: I seeded two *different* listings, each excluded exactly **once**
by the same rule, and rendered `GET /?excluded=1`. Both rows printed:

```html
<span class="rule-chip rule-chip-exclude_keyword">exclude_keyword (2)</span>
<span class="rule-chip rule-chip-exclude_keyword">exclude_keyword (2)</span>
```

**User impact.** The number sits inside a single listing's row, so it reads as "this
rule matched twice in this listing". It is a false statement about the user's own data,
in the exact place SC2 points at, and it will be read as evidence when the user decides
whether to retune a rule.

**Concrete fix.** Make the chip count per-listing. `rule_counts_for_listings`
(`exclusion_repo.py:121`) already returns `listing_id → [rule_id, ...]`; deriving the
per-listing count from that list length is sufficient and needs no new query.
Alternatively, drop the count from the chip entirely — it carries no meaning a user
needs, since each chip already represents one firing.

---

### 3. WARNING — The chip does not answer SC2's "why", and the evidence to answer it is persisted but unread

**Evidence.** The template renders only kind and count
(`app/web/templates/html/_listing_row.html:43`):

```jinja
<span class="rule-chip rule-chip-{{ rule.kind }}">{{ rule.kind }} ({{ rule.count }})</span>
```

- The firing **rule identity is dropped by the template**. `QueueRule.rule_id` exists
  and is populated (`queue_repo.py:156`, `:431`) but is referenced by **no template**.
- The **matched term and field are never loaded**. `RuleOutcome.detail` is persisted to
  `listing_exclusions.detail_json` (`app/domain/filter.py:113-119` →
  `exclusion_repo.py:76`), and `exclusions_for_run` (`exclusion_repo.py:144`) can read
  it back — but that function has **zero callers in `app/` and zero in `tests/`**. It is
  dead code. The column is written on every exclusion and never read.
- The only place a rule id reaches a screen is `app/web/templates/html/runs.html:121`,
  as a bare internal number (`rule 1: 2`) on a different page, unlinked to the rule the
  user can actually edit.
- The chip also renders the raw internal enum (`exclude_keyword`, `salary_floor`,
  `company_blocklist`) rather than a human label.

**Verdict on the SC2 question (see the dedicated section below): partially met; the
"which rule" half is degraded and the "why" half is absent.**

**Concrete fix.** Add `detail` to `QueueRule` (`queue_repo.py:153`) by joining the
`rule_counts_for_listings` query against `listing_exclusions.detail_json` for the latest
run, and render e.g. `exclude_keyword: description contains "crypto" (rule 1)`. Also
map the kind enum through a display-label dict shared with `criteria.html:320`.

---

## Detailed Findings

### Pillar 1: Visual Hierarchy (1/4)

- **No hierarchy is possible.** Preflight's
  `h1,h2,h3,h4,h5,h6{font-size:inherit;font-weight:inherit}` applies, and nothing
  re-establishes a scale. Rendered `<h1>Job Search Copilot</h1>`
  (`base.html:15`), `<h2>Queue</h2>` (`queue.html:40`), `<h3>` and `<h4>` all render at
  body size and weight. There is no focal point on any page.
- **The queue table has no column separation.** `table{border-collapse:collapse}` with
  no `th`/`td` border or padding rules (`td{` → 0 rules in `app.css`). Eight columns of
  raw text sit flush against each other; long values run together.
- **`site-header` / `tagline`** (`base.html:14-17`) are unstyled, so the page has no
  masthead and the tagline is visually indistinguishable from body copy.
- **`last-run` / `last-run-reason` / `reason-value` / `reason-sentence`**
  (`queue.html:26-32`) are unstyled, so the run reason is not set apart from the strip
  around it — and `reason-value` (the machine value, e.g. `unknown`) and
  `reason-sentence` (the derived sentence) are equally weighted despite serving
  different purposes.
- Positives: heading **levels** are correctly nested throughout (h2 → h3 → h4,
  e.g. `criteria.html:355` → `:197` → `:29`), so the document outline is sound even
  though the visual rendering of it is absent.

### Pillar 2: Consistency with the Design System (1/4)

- **There is no design system in the artifact.** `assets/tailwind/input.css` is 11 lines
  and has never contained a class definition (verified across full git history for that
  path). `static/vendor/app.css` was last rebuilt in `9e5eb01` (Phase 1) and contains
  only `@layer properties`, theme variables, preflight and a handful of utility
  primitives — none of which the templates use.
- **The breakpoint media queries in `app.css` contaminate a naive audit.** They look
  responsive (`min-width:40rem/48rem/64rem/80rem/96rem`) but they are Tailwind's theme
  variable declarations, not layout rules. No template class is responsive, so nothing
  changes at any width.
- **The class vocabulary is internally consistent and well-named** — this is the one
  place the phase scores: a coherent BEM-ish naming scheme (`listing-*`, `run-*`,
  `merge-*`, `search-*`, `rule-*`, `criteria-*`, `health-*`) applied consistently
  across all nine templates. It reads as a design system's vocabulary with the
  implementation missing.
- **Corroborating signal: the data hooks have no consumers.** `data-new`, `data-stale`,
  `data-saved`, `data-hidden`, `data-merged-from`, `data-status`, `data-rule-id` and
  `data-search-id` each appear **exactly once** across all templates — in the markup
  only. No CSS selector targets them and no JavaScript reads them. They are hooks
  written for a styling/behaviour layer that was never built.
- **Process root cause.** No Phase-2 artifact mentions Tailwind, the CSS build, or
  styling at all — `grep -rln "tailwind" .planning/phases/02-.../` returns nothing. The
  plans treated emitting `class="..."` as completing UI work. The tests then locked that
  in: `tests/api/test_queue_signals.py:157,238` and
  `tests/api/test_queue_excluded.py:179,181` assert class **strings** are present
  (`assert "dimmed" in toggled.text`) and never that the class is *styled*. That is why
  592 green tests and 10 plans did not catch this.

  **Add a guard:** a test that parses every `class="..."` out of
  `app/web/templates/html/*.html`, strips Jinja, and asserts each resulting token has a
  matching rule selector in `static/vendor/app.css` (with an explicit allowlist for
  known-framework classes). That single test converts this whole class of defect from
  invisible to blocking.

### Pillar 3: Responsive Behaviour (2/4)

- **The deferral is legitimate and I have not scored it as a failure.** D-16 explicitly
  defers the phone-first layout pass to Phase 8, and `routes.py:186-188` documents
  "Desktop-first by explicit scoping decision (D-16)". A locked, recorded decision to
  defer is not a defect.
- **What is not covered by that deferral:** `queue_list.html` renders a 7–8 column table
  and `runs.html` an 11 column table, neither wrapped in an `overflow-x` container
  (`queue_list.html:36`, `runs.html:27`). On a narrow viewport this forces horizontal
  scrolling of the **whole page**, not just the table. "Phone-first layout" being
  deferred does not make this intended — an uncontained wide table breaks the document,
  which is a defect independent of the deferral.
- **`viewport` meta is present** (`base.html:5`) — correct, and necessary for any future
  responsive pass.
- Because there are no styles at all, there is nothing to respond. This pillar cannot
  exceed 2 until Pillar 2 is fixed; the fix is a prerequisite, not a parallel task.

### Pillar 4: Interaction / Affordance Clarity (1/4)

- **Every button renders as plain text.** Preflight applies
  `button{box-sizing:border-box;border:0 solid;margin:0;padding:0}` plus
  `background-color:#0000;border-radius:0` from the shared form-control rule. Affected
  controls, all confirmed present in rendered output: `Run search now`
  (`queue.html:7`), `Mark all as seen` (`queue_list.html:23`), `Load more`
  (`queue_list.html:59`), `Save` / `Hide`
  (`_listing_row.html:57`, `:68`), `Revert` (`merges.html:88`), `Show detail`
  (`runs.html:70`), `Add rule` (`criteria.html:113`), `Save search`
  (`criteria.html:221`, `:300`), `Edit` (`criteria.html:129`, `:254`), `Delete`,
  `Confirm delete` (`criteria.html:255-264`), `Run this one` (`criteria.html:272`).
  With no border, background, padding or cursor change, `Save` and `Hide` sitting side
  by side are two bare words.
- **The search input is invisible.** Preflight sets `border-width: 0` on `*`, so
  `<input type="search" id="queue-search">` (`queue.html:47`) renders as a transparent
  area with no visible boundary. The primary entry point of a "queryable queue" has no
  affordance.
- **`dimmed` is a no-op** (`_listing_row.html:22`), so in the `Show excluded` view an
  excluded listing is visually identical to a kept one. The chip text is the only cue.
- **`badge-new` / `badge-stale` / `badge-saved` / `badge-hidden` / `badge-merged` are all
  no-ops** (`_listing_row.html:30-34`). The Signals cell renders as the plain run
  `new stale`. SC4's "distinguishable" is satisfied **only textually, and only by
  accident** — the words happen to be there. There is no visual distinction and no
  separation between badges other than whitespace.
- **The three filter checkboxes have inconsistent semantics, unsignalled.** In
  `queue_repo.py:311-318`, `Show excluded` and `Hidden` are **reveal** toggles (they
  *stop applying* an exclusion predicate) while `Saved` is an **exclusive filter** (it
  *adds* `saved_predicate()`). So checking `Show excluded` widens the set and checking
  `Saved` narrows it, yet all three are rendered identically as plain checkboxes in a
  bare `<form>` (`queue.html:42-97`). The labels do not convey this: `Show excluded` is
  a verb phrase, `Hidden` is a bare adjective, `Saved` is a bare adjective. A user
  cannot predict what checking `Hidden` will do.
- **Genuine positive: the disabled state is real.** `merges.html:86` renders
  `<button class="merge-revert-disabled" disabled>Reverted</button>` — a true native
  `disabled` attribute, so the browser greys it. That one control *is* visually
  differentiated, by the browser rather than by the app.
- **Destructive-action confirmation is inconsistent.** Search delete has a two-step
  confirm (`criteria.html:255-265`). Rule delete (`criteria.html:331-337`) fires
  `hx-post` immediately with no confirmation and no undo, despite the page's own copy
  saying rules are re-evaluated from scratch each run. Same asymmetry for merge `Revert`
  (`merges.html:88`) — reversible in principle, but with no undo affordance in the UI.

### Pillar 5: Empty / Error / Loading States (2/4)

Coverage of **empty** and **error** states is genuinely good and is the reason this
pillar is not a 1:

- Empty states exist for every collection: `queue-empty` (`queue_list.html:32`),
  `merges-empty` (`merges.html:32`), `runs-empty` (`runs.html:22`), `criteria-empty`
  (`criteria.html:226`), `rule-none` (`criteria.html:344`), `source-health-empty`
  (`_health_strip.html:47`), plus two inline detail empties
  (`runs.html:114`, `:125`, `:136`).
- Error surfaces exist and are specific: `criteria-errors` (`criteria.html:189`),
  `run-errors` (`runs.html:85`, `:156`), `run-degraded` / `run-failed`
  (`_run_status.html:22-33`), `llm-unreachable` (`_health_strip.html:9`), and
  `merges-note` (`merges.html:28`).
- Empty-state copy is purposeful rather than generic — `runs.html:22` tells the user
  where the button is and links to it. This is well above the "No data" baseline.

Deductions:

- **Zero loading feedback anywhere.** `hx-indicator` → **0 occurrences** across all
  templates; `aria-busy` → 0. The search box fires a request after a 300 ms debounce
  (`queue.html:52`) and swaps the whole list with no feedback. The same is true of
  `Load more`, `Mark all as seen`, `Save`, `Hide`, `Revert`, and every criteria mutation.
- **No double-submit protection.** `hx-disabled-elt` → 0 occurrences. `Run search now`
  (`queue.html:7`) and the row `Save`/`Hide` forms are plain submits; a double click
  issues two POSTs.
- **No htmx error handling at all.** `grep -rn "htmx:" app/web/ app/static` returns
  nothing — there is no `htmx:responseError` or `htmx:sendError` handler. A failed swap
  leaves the UI silently unchanged, which is indistinguishable from a no-op.
- **The filtered-empty case shows the wrong copy.** Confirmed by rendering
  `GET /?q=zzzz-no-such-term`: the response is
  `<p class="queue-count">0 listings</p>` followed by
  `No listings yet. Once a search runs, its normalised results appear here.`
  That is the *no-data-ever* message shown for a *no-matches* condition. The queue is
  not empty; the query matched nothing. There is also no "clear filters" affordance —
  `queue_list.html:31` has exactly one empty branch and no awareness of whether
  `page.query.q` is set.
- **`unknown` leaks as a visible value.** `queue.html:30` renders
  `{{ last_run.reason or 'unknown' }}` and `runs.html:66` does the same — confirmed in
  rendered output as `<span class="reason-value">unknown</span>`. A run that recorded no
  reason has no reason recorded; "unknown" is a raw sentinel, not copy.
- **Timestamps are rendered raw and inconsistently.** `_listing_row.html:39` prints
  `2026-09-01T00:00:00` (ISO with a `T`, from `queue_repo.py:444`), while
  `runs.html:53` prints `2026-09-02 12:00:00` (space-separated). Two formats for the
  same concept on two pages, neither humanised.
- **`criteria.html`'s rule form depends on Alpine for its initial state.**
  `x-data="{ kind: 'salary_floor' }"` with six sibling `x-show` groups
  (`criteria.html:28-111`) means that if Alpine fails to load, **all six field groups
  render simultaneously** as one confused form. The same applies to
  `search-edit` (`:282`), `rule-edit-fields` (`:130`) and `search-delete-confirm`
  (`:256`). No `<noscript>` fallback and no server-rendered default.

### Pillar 6: Accessibility (3/4)

**What is genuinely good** — and this is a real strength of the phase:

- Native elements throughout: real `<button type="button">`, `<form>`, `<a href>`,
  `<table>`, `<ul>/<li>`, `<details>/<summary>` (`runs.html:139`). No `div`-as-button,
  no click handlers on non-interactive elements.
- Every form control is labelled: `<label for="queue-search">` (`queue.html:46`),
  `for="queue-toggle-*"` (`:60`, `:73`, `:86`), `for="new-search-*"`
  (`criteria.html:202-219`), `for="rule-kind-*"` (`:30`). Wrapping labels for
  checkboxes. `aria-label` count of 0 is *correct* here rather than a gap, because no
  icon-only button exists — every control has visible text.
- Tables use `<th scope="col">` on every header (`queue_list.html:39-46`,
  `merges.html:40-46`, `runs.html:30-40`, `_health_strip.html:23-27`).
- `lang="en"` (`base.html:2`), `viewport` meta (`:5`), exactly one `<h1>` (`:15`),
  correct heading nesting.
- Purposeful input attributes: `type="search"` (`queue.html:47`),
  `inputmode="numeric"` with `min`/`step` (`criteria.html:42`, `:216`, `:295`),
  `maxlength="255"` (`:203`, `:287`).
- No `tabindex` hacks anywhere (0 occurrences) — native tab order is intact.
- **Focus visibility survives.** Tailwind preflight does **not** strip outlines (the
  `outline-*` entries in `app.css` are unused utility definitions, never applied), so
  browser default focus rings are present. I checked this specifically because it is a
  common preflight casualty.

**Deductions:**

- **No live-region announcements on any async swap.** `aria-live` → **0 occurrences**.
  The run-status fragment self-polls with `hx-trigger="every 2s"`
  (`_run_status.html:1-4`) and replaces its own content; a screen-reader user is never
  told the run started, progressed or finished. Same for every `#queue-list` swap, the
  `#criteria-list` swaps, and the row `outerHTML` swaps. This is the single most
  consequential a11y gap, because the queue's core interaction model *is* background
  swap.
- **No `aria-expanded` / `aria-controls` on the Alpine disclosures.** `Edit`
  (`criteria.html:254`), `rule-edit-toggle` (`:129`) and `Delete`/confirm (`:255-265`)
  toggle visibility via `@click` with no state exposed to assistive tech.
- **No `<caption>` on any table**, and no `<fieldset>`/`<legend>` grouping the three
  filter checkboxes (`queue.html:60-97`) — which compounds the Pillar 4 semantics
  finding, since the grouping is load-bearing for understanding the two different
  filter behaviours.
- **Contrast is currently unremarkable but only by default.** With no CSS, everything
  is browser-default black-on-white, which passes. This is not a pass earned by the
  implementation: `dimmed` on excluded rows is precisely the kind of treatment that
  fails WCAG AA if implemented as opacity/greyed text on a light background. It must be
  re-checked when Pillar 2 is fixed — `listing-stale` and `merge-row-reverted` are the
  other two candidates.

---

## SC2 Verdict: Does the excluded-listing chip satisfy "which rule fired and why"?

**Verdict: Partially met. The "which rule" half is degraded, and the "why" half is
absent. The chip does not satisfy SC2 as written.**

I reached this independently and I concur with the verifier's advisory
(`02-VERIFICATION.md:415`), but my assessment is stronger than "advisory" for three
reasons the verifier did not have:

1. **The "why" evidence is persisted, readable, and provably unread.**
   `listing_exclusions.detail_json` holds the matched term and field — for the seeded
   fixture, `{"term": "crypto", "field": "description", "count": 1}` — written on every
   exclusion via `exclusion_repo.py:76`. `exclusions_for_run`
   (`exclusion_repo.py:144`) exists specifically to read it back and **has zero callers
   in `app/` and zero in `tests/`**. This is not a missing feature; it is a built,
   tested-at-the-repository-level capability that was never wired to a screen. The user
   sees `exclude_keyword (2)` and cannot see that the word "crypto" in the description
   caused it.

2. **The rule identity is available and dropped by one line.** The verifier's framing
   ("the firing rule id … has no UI consumer") is accurate at the template level, but
   the fix is cheaper than that framing suggests: `QueueRule.rule_id` already exists and
   is already populated (`queue_repo.py:156`, `:431`). `_listing_row.html:43` simply
   does not render it. The information is one template edit away, not one query away.

3. **The number that IS shown is wrong** (Pillar 2 priority fix #2, empirically
   confirmed above). This matters for the SC2 judgment: SC2 asks that the reason for
   exclusion be *visible*. What is visible is not just incomplete — for the count, it is
   incorrect. An incomplete answer invites investigation; a wrong answer forecloses it.

**What SC2 *is* owed credit for:** the plumbing is right. The chip is rendered only in
the `Show excluded` view; it names the rule *kind*; the exclusion toggle is a view over
`listing_exclusions` with correct per-run (D-36) semantics — a listing excluded by an
older run returns to the default view, which I confirmed is enforced and pinned by
`test_queue_excluded.py`. The exclusion write path records the firing rule per listing
per run and is fully tested. FILT-02's *recording* requirement is met and I do not
dispute that. What is missing is the *presentation* of that record.

**Minimum fix to close SC2:** render the firing rule's human-readable summary plus the
matched term/field, sourced from the already-persisted `detail_json`. Concretely, extend
`QueueRule` with `detail` (populated from a join on `listing_exclusions`) and change
`_listing_row.html:43` to something like
`exclude_keyword: description contains "crypto" (rule 1)` with a display-label mapping
so the raw enum stops leaking.

---

## Undefined CSS Classes — Complete Inventory

**Summary: 160 of 160 classes used in `app/web/templates/html/*.html` have no rule in
`static/vendor/app.css`.** Zero Tailwind utility classes are used in any template. The
phase's seven named new classes are all among them.

Method: extracted every `class="..."` token from all nine templates (162 tokens), then
tested each against the compiled stylesheet. Two apparent hits (`not`, `or`) were
verified to be artefacts of the extractor reading Jinja expressions
(`{{ row.health or 'unknown' }}`, `{% if not search.enabled %}`) matching
`.not-italic` / `.order-0` as substrings; they are not real classes. All 160 genuine
classes are unbacked.

**The phase's newly-introduced classes (the specific set flagged for this audit):**

| Class | Used at | Status |
|-------|---------|--------|
| `rule-chip` | `_listing_row.html:43` | ❌ no rule in `app.css` |
| `rule-chip-<kind>` (`rule-chip-exclude_keyword` etc.) | `_listing_row.html:43` | ❌ no rule |
| `dimmed` | `_listing_row.html:22` | ❌ no rule |
| `badge-new` | `_listing_row.html:32` | ❌ no rule |
| `badge-stale` | `_listing_row.html:33` | ❌ no rule |
| `listing-exclusion` | `_listing_row.html:41` | ❌ no rule |
| `listing-actions` | `_listing_row.html:47` | ❌ no rule |

**Full inventory by template (all ❌ — every token below lacks a rule):**

- `base.html`: `site-header`, `tagline`
- `queue.html`: `last-run`, `last-run-reason`, `reason-value`, `reason-sentence`,
  `last-run-link`, `queue-toggle`
- `queue_list.html`: `queue-count`, `empty-state`, `queue-table`
- `_listing_row.html`: `listing-row`, `listing-stale`, `dimmed`, `listing-title`,
  `listing-badges`, `badge`, `badge-saved`, `badge-hidden`, `badge-new`, `badge-stale`,
  `badge-merged`, `listing-company`, `listing-location`, `listing-source`,
  `listing-posted`, `listing-exclusion`, `rule-chip`, `rule-chip-<kind>`,
  `listing-actions`, `listing-action`, `listing-action-save`, `listing-action-hide`,
  `listing-save-button`, `listing-hide-button`, `is-on`
- `merges.html`: `merge-rate`, `merges-note`, `empty-state`, `merges-table`,
  `merge-row`, `merge-row-reverted`, `merge-merged-at`, `merge-method`, `merge-score`,
  `merge-survivor`, `merge-twin`, `merge-title`, `merge-company`, `merge-location`,
  `merge-sources`, `merge-url`, `merge-snapshot`, `merge-snapshot-list`,
  `merge-snapshot-none`, `merge-action`, `merge-reverted`, `merge-revert`,
  `merge-revert-disabled`, `merges-intro`
- `runs.html`: `empty-state`, `runs-table`, `run-row`, `run-row-<status>`,
  `run-in-flight`, `run-id`, `run-status`, `run-status-<status>`, `run-trigger`,
  `run-started`, `run-finished`, `run-duration`, `run-sources`, `run-source`,
  `run-source-<name>`, `run-deduped`, `run-filtered`, `run-reason`, `reason-value`,
  `reason-sentence`, `run-detail-slot`, `run-detail-row`, `run-errors-row`, `run-errors`,
  `run-error`, `run-detail`, `run-detail-sentence`, `run-reason-counts`,
  `run-detail-empty`, `run-excluded-counts`, `run-excluded-count`, `run-searches`,
  `run-search`, `stage-log`, `stage-entry`, `stage-name`, `stage-count`, `stage-error`,
  `runs-intro`
- `criteria.html`: `rule-form`, `rule-fields`, `rule-salary_floor`,
  `rule-exclude_keyword`, `rule-location`, `rule-remote`, `rule-seniority`,
  `rule-company_blocklist`, `rule-help`, `rule-submit`, `rule-edit`,
  `rule-edit-toggle`, `rule-edit-fields`, `rule-edit-save`, `criteria-note`,
  `criteria-errors`, `criteria-error`, `search-create`, `search-remote`, `empty-state`,
  `search-card`, `search-disabled`, `search-header`, `search-name`, `search-version`,
  `search-state`, `search-last-run`, `search-controls`, `search-toggle`,
  `search-edit-toggle`, `search-delete`, `search-delete-confirm`, `search-delete-yes`,
  `search-delete-no`, `search-run`, `search-run-now`, `search-edit`, `search-save`,
  `capability-warnings`, `capability-warning`, `rule-list`, `rule-row`, `rule-disabled`,
  `rule-kind`, `rule-summary`, `rule-state`, `rule-controls`, `rule-toggle`,
  `rule-delete`, `rule-none`, `criteria-intro`
- `_run_status.html`: `run-badge`, `run-status-<status>`, `run-sources`, `run-source`,
  `run-degraded`, `run-failed`
- `_health_strip.html`: `llm-status`, `llm-unreachable`, `llm-reachable`, `health-table`,
  `health-row`, `health-source`, `health-badge`, `health-<health>`,
  `health-last-success`, `health-returned`, `health-fill-rate`, `fill-rate`,
  `fill-<field_name>`, `health-empty`

**Build note:** the vendored `app.css` is a genuine Tailwind v4.3.3 build
(`/*! tailwindcss v4.3.3 | MIT License */`) produced by the Dockerfile's `assets` stage.
Re-running that build **would not change anything**, because Tailwind v4 emits rules only
for class names it recognises as utilities or emits via `@utility`/`@layer components`,
and none of the 160 names is defined anywhere. `input.css` must gain the component
definitions (or the templates must move to utilities) before any rebuild is meaningful.

---

## Minor Recommendations

Findings that did not drive a pillar score but are worth folding into the fix:

1. **Navigation is missing entirely.** No `<nav>` element exists in any template, and
   `/searches` (the Criteria UI) has **no inbound link from anywhere** —
   `grep -rn 'href="/searches"' app/web/templates/` returns nothing. The only way to
   reach the rule-authoring surface that SC2's "retune a rule" rests on is to type the
   URL. `/merges` is reachable only from `_listing_row.html:34`, which renders **only
   when `row.merged_from` is truthy** — so with no merges, `/merges` is unreachable.
   `/runs` is reachable only from `queue.html:34`, inside `{% if last_run %}` — so on a
   fresh install with no runs, it is unreachable too. `runs.html:24` links back to `/`.
   Fix: a persistent nav in `base.html`.
2. **The display name of a company is the normalised one.** Rendered output shows
   `<td class="listing-company">acme</td>` for a listing whose company is "Acme" —
   `queue_repo.py:441` uses `listing.company_norm`. `merges.html:57,64` has the same
   issue via the merge read model. Show the raw/display company and keep `_norm` for
   matching.
3. **Raw internal enums leak as user-facing copy**: `exclude_keyword`, `salary_floor`,
   `location`, `remote`, `seniority`, `company_blocklist`, `norm_equals`, `substring`
   (`criteria.html:32-37`, `:71-73`, `:104-107`, `:320`); `done`/`partial`/`failed`/
   `manual` (`runs.html:51-52`, `:46`); `linkedin`/`indeed` (`_listing_row.html:38`);
   `unknown` as a fallback reason (`queue.html:30`, `runs.html:66`). These want a
   display-label mapping.
4. **`/merges` and `/runs` expose raw URLs without links.** `merges.html:60,67` renders
   `<span class="merge-url">{{ row.survivor.url }}</span>` — a long URL as unclickable
   text in a table cell, where an `<a>` would be both more useful and better for a
   narrow cell.
5. **The `Signals` cell header does not describe its contents.** It holds save/hidden/
   new/stale badges and the merge link (`_listing_row.html:29-35`) and renders as the
   plain run `new stale`. "Signals" is also the word the phase uses for FTS (`SC4`), so
   it collides with the search feature's own vocabulary.
6. **`search-remote` and `queue-toggle` differ in nothing but name**, both being
   checkbox-plus-label wrappers (`criteria.html:211`, `queue.html:60`).
7. **`_health_strip.html:39` renders `fill-<field_name>`** with `field_name` derived
   from data — an unbounded dynamic class. Once a component layer exists, these will
   silently miss unless generated or allowlisted.

---

## Process Note: why 592 green tests did not catch the highest-severity finding

Every UI test in the suite asserts on **strings and structure**, never on **styling**:

- `tests/api/test_queue_signals.py:157` — `assert "badge-new" in response.text`
- `tests/api/test_queue_signals.py:238` — `assert "badge-new" in response.text and "badge-stale" in response.text`
- `tests/api/test_queue_excluded.py:179` — `assert "dimmed" in toggled.text`
- `tests/api/test_queue_excluded.py:181` — `assert f'class="rule-chip rule-chip-{RULE_KIND}"' in toggled.text`
- `tests/pipeline/test_ingest_e2e.py:38` — reads
  `<td class="listing-title">([^<]+)</td>`

A class string being present in the response is a *necessary* condition for the styling
to apply and a *sufficient* condition for none of it. The tests pinned the contract
"this class name is emitted" and the implementation satisfied exactly that, so the suite
was green while the UI was unstyled. This is a structural gap in the verification
surface, not an oversight in any one plan — and it will recur in Phases 6–8 unless a
class-has-a-rule guard test is added alongside priority fix #1.

---

## Files Audited

**Templates (rendered and read in full):**

- `app/web/templates/html/base.html`
- `app/web/templates/html/queue.html`
- `app/web/templates/html/queue_list.html`
- `app/web/templates/html/_listing_row.html`
- `app/web/templates/html/merges.html`
- `app/web/templates/html/runs.html`
- `app/web/templates/html/criteria.html`
- `app/web/templates/html/_run_status.html`
- `app/web/templates/html/_health_strip.html`

**Styling pipeline:**

- `assets/tailwind/input.css`
- `static/vendor/app.css`
- `Dockerfile` (`assets` stage — Tailwind CLI build)

**Routes and read models:**

- `app/web/routes.py`
- `app/db/repositories/queue_repo.py`
- `app/db/repositories/exclusion_repo.py`
- `app/domain/filter.py`
- `app/api/runs.py`, `app/api/events.py`, `app/api/searches.py` (referenced for the
  renders and fragments they produce)

**Planning artifacts (baseline substitution + cross-check):**

- `.planning/phases/02-clean-filtered-queryable-queue/02-CONTEXT.md` (D-16 deferral)
- `.planning/phases/02-clean-filtered-queryable-queue/02-VERIFICATION.md`
- `.planning/phases/02-clean-filtered-queryable-queue/02-UAT.md` (test 5)
- `.planning/phases/02-clean-filtered-queryable-queue/02-RESEARCH.md`
- `.planning/ROADMAP.md` (SC2/SC4/SC5)
- `AGENTS.md`, research `STACK.md` Q8 (declared UI stack)

**Tests (read to establish what markup is already pinned):**

- `tests/conftest.py`
- `tests/api/test_queue_search.py`
- `tests/api/test_queue_signals.py`
- `tests/api/test_queue_excluded.py`
- `tests/api/test_merges_view.py`
- `tests/api/test_run_history.py`
- `tests/api/test_searches_crud.py`
- `tests/api/test_criteria_capabilities.py`
- `tests/pipeline/test_ingest_e2e.py`

**Verification performed:**

- `pytest -q tests/api tests/domain` → 272 passed
- `pytest -q` (full suite) → **592 passed, 2 deselected** (matches the stated baseline)
- All nine pages rendered to raw markup via the httpx ASGI client against a migrated
  temp DB; markup inspected directly
- Two empirical probes: run-wide chip count, filtered-empty copy (both findings above
  are the observed output, not inference)
- `git status` clean apart from `.gsd/`, `.planning/milestone.lock`,
  `.planning/phases/02-.../02-SECURITY.md` and `.planning/WINDOWS.md` (all pre-existing)
  plus `.planning/ui-reviews/` (created by the mandatory gitignore gate)
- No source file modified; both throwaway test files deleted
- Registry safety audit: **skipped** — no `components.json`, so shadcn is not
  initialised and no third-party registry is in play
