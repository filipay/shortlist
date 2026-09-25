# Phase 6 — UI Review

**Audited:** 2026-09-25
**Baseline:** abstract 6-pillar standards — **no `UI-SPEC.md` exists** anywhere under `.planning/` (`find .planning -iname "*UI-SPEC*"` → empty). Findings are judged against the phase's own decision record (`06-CONTEXT.md` D-105…D-119, especially D-108/D-116/D-117/D-118), the plan acceptance criteria, requirement **UI-05** ("User can preview and download the tailored CV PDF"), and general 6-pillar standards.
**Screenshots:** **not captured.** No dev server was reachable this run — ports 3000 / 5173 / 8080 / 8000 all returned `000`; no Playwright binary or Python package is installed. Audit is therefore **code-only** (template source, `assets/tailwind/input.css` + compiled `static/vendor/app.css`, inline HTML fragments in `app/api/tailoring.py`, the vendored `htmx.min.js`, and the route/tests). No screenshots were fabricated.
**Method:** `.planning/ui-reviews/.gitignore` re-verified (exists, ignores `*.png|webp|jpg|jpeg|gif|bmp|tiff`) before any capture attempt; none succeeded. Test run this audit: `.venv/bin/python -m pytest tests/api/test_tailoring_generate.py tests/api/test_tailoring_review.py tests/test_stylesheet_coverage.py -q` → **29 passed**. The Tailwind build was re-run reproducibly: `./node_modules/.bin/tailwindcss -i ./assets/tailwind/input.css -o /tmp/app-rebuild.css --minify` (the exact Dockerfile command).

**Scope:** the Phase 6 delta — the dedicated tailoring page and the generate → review → compile → download flow (UI-05) plus the verification surfacing it owns: `tailoring.html`, `_tailoring_review.html`, `_cv_findings.html`, the tailoring CSS rules added in 06-01, the inline fragments built in `app/api/tailoring.py`, and the detail-page entry link. Shared-shell defects carried from Phase 5 (`listing_detail.html`, `_listing_row.html`, `queue*`) are named only where this phase's surface re-exposes them.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | Empty/skip/blocked copy is specific and honest, but raw `compile_status` tokens (`ok`/`blocked`/`failed`) leak as user text, and every "Download PDF" link is an inline-preview link — the UI has no actual download path. |
| 2. Visuals | 2/4 | The generate → review flow renders a **nested duplicate card** (two `#tailoring-review` elements, double border/padding), an empty bordered box on first load, and the primary "Generate" control is styled as a secondary button. |
| 3. Color | 2/4 | Correct token reuse and zero hardcoded hex, but the review coverage/findings panels put `req-met` (`#059669`) on whole sentences → **3.77:1 AA failure** on the phase's own primary output. |
| 4. Typography | 3/4 | Coherent existing scale, mono for IDs, no new sizes/weights; raw enum tokens and `h2→h5` depth are the only nits. |
| 5. Spacing | 3/4 | Disciplined rem scale, no arbitrary values; the empty review box reserves dead space and the nested card doubles the intended padding. |
| 6. Experience Design | 2/4 | **Worst pillar.** Every typed refusal (`tailoring_failed` 502, `stale-patch` 409, disabled 409, …) returns 4xx/5xx, and htmx 2.0.10 does **not swap non-2xx responses** — so the entire refusal UX is invisible in the browser. No busy/disabled state on the LLM or LaTeX actions; history download links misdirect to the newest PDF. |

**Overall: 15/24**

Requirement read: **UI-05** — *preview* is met on the happy path (inline HTML preview before compile; the PDF route serves `inline`, so a click previews it in a tab), but *download* is not reachable from the UI (no link carries `?download=1`), and the verification surfacing works only on the 200 path (blocked findings render; refusals do not).

---

## Top 3 Priority Fixes

1. **Typed refusals never reach the user — htmx does not swap 4xx/5xx (BLOCKER).** `htmx.min.js` v2.0.10 ships the default `responseHandling:[{code:"204",swap:false},{code:"[23]..",swap:true},{code:"[45]..",swap:false,error:true}]` and **no** `htmx:beforeSwap`/`responseHandling` override or `HX-Retarget`/`HX-Reswap` exists anywhere in the app (grep confirms; only `app/api/runs.py:180` ever sets `HX-Reswap`, using an exotic `286` status). Every refusal from `app/api/tailoring.py` is built as a swap-target fragment — `_error_fragment` (`:223-229`) returned at `:365` (disabled, 409), `:369` (no score, 422), `:374` (fact store, 409), `:388` (**`tailoring_failed`, 502** — the WR-01 deliverable), `:397` (`invalid-patch`, 502), `:443`/`:447` (`bad-patch`, 422), `:452` (409), `:470` (`stale-patch`, 409) — and `_not_found` (`:113-118`, 404). Because the status is ≥400, htmx discards the body and fires an unhandled `htmx:responseError`: the user clicks **Generate tailored CV**, the transport fails or the backend is disabled, and **nothing changes on screen**. The docstring at `:224` ("so a swap never empties the DOM") and the 06-09 summary's "surfaces the route's typed 502 `tailoring_failed` refusal" are both false in the browser. The green API tests (29 passed) assert status + body server-side and never exercise htmx's swap rules — the gap is invisible to them. **Fix:** add `hx-swap="innerHTML show:top"` with a `htmx:beforeSwap` handler that swaps on `data-error` (`evt.detail.shouldSwap = true` when the response carries `data-error`), or return these refusals with a 200 + `HX-Retarget`/`HX-Reswap`, or set an `hx-on::response-error` handler. Add one browser-level assertion that the refusal text is visible.

2. **The Docker-built image ships without any of the phase's CSS (BLOCKER).** `.tailoring-review`, `.tailoring-empty`, `.cv-generate`, `.cv-download` were added **only** to the committed `static/vendor/app.css` (`:31-34`, commit 404d995) and never to the Tailwind source `assets/tailwind/input.css`. The same is true of `.requirement-list`, `.req-met`/`.req-partial`/`.req-gap` (from 05-03) and the phase-05 classes `.badge-score*`, `.factor-table`, `.detail-rationale`, `.listing-detail-link`, `.ranking-strip`, `.cv-status`, `.badge-unranked`. The Dockerfile stage-1 runs `tailwindcss -i ./assets/tailwind/input.css -o ./static/vendor/app.css --minify` (`Dockerfile:19`) and stage-2 does `COPY --from=assets /app/static/vendor ./static/vendor` (`Dockerfile:113`) — so the image serves a freshly generated stylesheet. Re-running that exact build drops every one of those selectors (verified: `/tmp/app-rebuild.css` contains **0** occurrences of `tailoring-review`, `tailoring-empty`, `cv-download`, `requirement-list`, `req-met`, `req-gap`). In the project's stated deployment target the tailoring page therefore renders with no review card, no empty state, no bullets, and no verdict colours. `tests/test_stylesheet_coverage.py` cannot catch it: it scans only template `class="..."` attributes against the committed artifact, never the source→build round-trip. **Fix:** move all component rules into `input.css` (the file already hosts every other component rule), rebuild, and add a test that re-runs the Tailwind CLI and asserts the selectors survive.

3. **The review region nests a duplicate `id="tailoring-review"` and a double card (WARNING).** `tailoring.html:35` renders `<div id="tailoring-review" class="tailoring-review">`, and the generate response root is `<section id="tailoring-review" class="tailoring-review" aria-live="polite">` (`_tailoring_review.html:17`). The generate swap is `hx-target="#tailoring-review" hx-swap="innerHTML"` (`tailoring.html:31-32`), so the section is inserted **inside** the div — two identical ids in the DOM, and two `.tailoring-review` borders/backgrounds/paddings stacked (`app.css:31`), i.e. a visibly double-framed card. The compile form (`_tailoring_review.html:66-72`) then targets `#tailoring-review` again; `querySelector` returns the **outer** div, so the compile result replaces the live section — destroying the `aria-live="polite"` region, so "Compiled." / the blocked findings are never announced. **Fix:** make the swap target a wrapper with a different id (e.g. `#tailoring-review-slot`) or give the response a different root id, and keep a persistent live region outside the swapped node.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

**What is good.** The phase's copy is a genuine strength: honest, specific, and free of generic filler. The rank-first precondition is explained (`tailoring.html:22`, "Rank this listing first — tailoring works from the stored requirement list."), `skip_label` is precomputed server-side rather than branched in the template, the review instruction is explicit that no PDF exists yet (`_tailoring_review.html:19`), suggestions are marked "(not applied to the render)" (`:58`), and the blocked state explains both the cause and the only recovery (`_cv_findings.html:13-17`). "Warnings never block a download; only a failing check does." (`:27`) is exactly the reassurance a gate needs. Button labels are verbs, not "Submit/OK".

**Findings.**
- **Raw machine tokens leak as user text (WARNING — new on this surface).** `tailoring.html:41` renders `Status: {{ latest.compile_status }}` → "Status: ok / blocked / failed"; `:61` renders `<span class="badge">{{ entry.compile_status }}</span>` → "ok". The app already owns a `human_label` filter (`app/web/filters.py:34`, registered in `template_env.py:20`) used for other enums; this surface bypasses it. `human_label("ok")` → "Ok" is still weak; the fix is an explicit map (`ok → Compiled`, `blocked → Blocked`, `failed → Failed`).
- **"Download PDF" is not a download (WARNING — UI-05 gap).** Both links (`tailoring.html:43,64`) point at `/listings/{id}/cv/pdf` with no query, and the route serves the artifact with `Content-Disposition: inline` unless `?download=1` (`app/api/tailoring.py:526`). No template anywhere emits `?download=1`. So the label promises a file download and the browser instead opens a PDF viewer tab — the UI provides **no** download affordance, despite UI-05 saying "preview **and download**". Fix: split the affordances ("Preview" → inline, "Download" → `?download=1`) or append `?download=1` to a second link.
- **The "Previous compiles" list lies about each entry (WARNING).** Every `ok` history entry (`tailoring.html:59-66`) renders an identical `Download PDF` link to the same URL, and the route always selects the **latest** `ok` artifact (`latest_for_listing(..., ok_only=True)`, `:512`). Downloading from a week-old row yields the newest PDF. Either drop the per-row link, label it "Download latest", or pass the artifact id.
- **Bare 404 copy (minor, inherited).** `_not_found()` returns "Unknown listing." with no nav or way back (`:113-118`), consistent with the Phase-5 finding.

### Pillar 2: Visuals (2/4)

**What is good.** A clear document hierarchy (page `h2` → fragment `h3` → `h4` sub-panels → `h5` section titles), a single bordered card for the review, struck-through dropped bullets with reasons (`_tailoring_review.html:33`), and colour-coded coverage rows. No icon-only controls, no images. The detail-page entry point is a clear text link (`listing_detail.html:43`, "Tailor my CV for this job").

**Findings.**
- **Nested duplicate review card (WARNING).** As Top-3 fix 3: two `.tailoring-review` roots stack their border + `--color-surface` background + `1rem` padding, producing a double-framed panel — a direct visual defect on the phase's central surface, not just an id-hygiene issue.
- **An empty bordered box renders on first load (minor, NEW).** `tailoring.html:35` emits `<div id="tailoring-review" class="tailoring-review"></div>` **unconditionally**, and `.tailoring-review` carries `border:1px solid;padding:1rem;background:surface;margin-top:1rem` (`app.css:31`). Before any generate click the user sees a ~2rem-tall empty outlined rectangle under the button. Leave the slot classless until it is populated.
- **The primary action looks secondary (WARNING, NEW).** `<button class="cv-generate" hx-post=…>` (`tailoring.html:28`) has **no `type` attribute**. The stylesheet paints only `button[type="submit"]` accent-blue (`input.css:280-285`); the generate control therefore renders with the default white/neutral button style, while "Compile PDF" (`type="submit"`, `_tailoring_review.html:76`) is accent-blue. The first and most important control on the page is visually the least prominent. Add `type="button"` **plus** a primary class, or explicitly style `.cv-generate`. (The accompanying rule `.cv-generate{align-self:flex-start}` is inert — the button has no flex parent but `#content`, so it is a no-op rule.)
- **Status/grounding badges have no chip treatment (minor, NEW).** `<span class="badge">` is used three times (`tailoring.html:61`, `_tailoring_review.html:51`, `_cv_findings.html:21`) without any `badge-*` colour variant. `.badge` alone sets only padding/radius/weight (`input.css:564-574`) — no background, no colour — so these render as small bold text, not the coloured chips used elsewhere. A `ok/warn/fail` or band label that looks like plain text carries no signal.
- **The requirement verdict is signalled by colour alone (inherited).** `_tailoring_review.html:49` and `_cv_findings.html:20` put `req-met/req-partial/req-gap` on the whole `<li>`; the status word and the requirement sentence share size and weight. See Pillar 3.

### Pillar 3: Color (2/4)

**Token discipline is good.** Phase 6 introduces **no** colour and **no** hardcoded hex; `.tailoring-review`, `.tailoring-empty`, `.cv-download` reuse `--color-border`, `--color-surface`, `--color-muted`, `--color-accent`/`--color-accent-hover` (`app.css:31-34`). The 60/30/10 distribution is preserved — accent remains on links/primary buttons only, and the review card stays neutral surface. `.tailoring-empty` (`--color-muted #6b7280` on `--color-surface #f9fafb`) recomputes to **4.63:1** and passes AA.

**Findings — one AA failure is re-exposed on this phase's primary output (WARNING, accessibility).**

| Pairing (phase-06 surface) | Ratio | AA |
|---|---|---|
| `.req-met` `#059669` on white — **direct-match coverage rows** (`_tailoring_review.html:49`) and **passing findings** (`_cv_findings.html:20`) | **3.77:1** | **FAIL** |
| `.req-gap` `#dc2626` on white — gap rows / failing findings | 4.83:1 | pass |
| `.req-partial` `#b45309` on white — partial / warn rows | 5.02:1 | pass |
| `.tailoring-empty` `#6b7280` on `#f9fafb` | 4.63:1 | pass |

The failure is inherited from the Phase-5 `req-met` token, but "direct" is the **most common** coverage status, so on a typical review most of the Requirement-coverage list renders as green body text below AA — and in `_cv_findings.html` every passing check does too. This is the phase's verification output, i.e. exactly what UI-05 is for. Fix: darken the success token (e.g. `#047857`, ~5.1:1) and/or move the verdict to a chip so the sentence body keeps ink contrast.

### Pillar 4: Typography (3/4)

**What is good.** The phase introduces **no new size or weight**. It composes from the established scale: `h3` 1.25rem / `h4` 1.125rem / `h5` 1rem / `h6` 0.875rem (serif, weight 600 — `input.css:76-106`), body 1rem/1.6, `.badge` 0.75rem/600, `code` mono at 0.9em on `--color-surface-2` (`input.css:163-169`). IDs (`change.target_id`, `finding.evidence_ids`) use `code`/mono correctly; the dropped-bullet `<s>` treatment reads cleanly.

**Findings.**
- Raw status tokens and machine ids (`ok`, `blocked`, `failed`, `gap`, `direct`, `bul_…`) are rendered as normal text rather than going through the human-label filter — same root cause as Pillar 1. `code` at 0.9em on `--color-surface-2` inside the `.tailoring-review` surface also sits at **4.39:1** against that chip background (the inherited Phase-5 finding), affecting evidence IDs.
- `h2` ("Tailored CV") → `h3` ("Review the tailored CV") is mildly redundant, and the fragment's `h5` section titles at 1rem compete with the `<strong>` org line — a shallow hierarchy nit, not a defect.

### Pillar 5: Spacing (3/4)

**What is good.** A single rem scale throughout; **no arbitrary `[Npx]`/`[Nrem]` values** in any Phase-6 template or CSS. `.tailoring-review` uses `margin-top:1rem;padding:1rem` (`app.css:31`), consistent with `.listing-action`/card conventions; the compile form, the coverage list and the preview sit in a normal block flow; `section{margin-bottom:2.5rem}` (`input.css:239`) gives the page's sections breathing room.

**Findings.**
- **The empty review slot reserves dead space (minor).** See Pillar 2 — `.tailoring-review`'s padding+border make the pre-generate slot a visible ~2rem empty box.
- **The nested card doubles the spacing (WARNING).** Two `.tailoring-review` paddings + `margin-top:1rem` stack when the generate fragment lands inside the slot (Top-3 fix 3), so the intended 1rem inset becomes ~2rem plus a doubled border gap.
- **`align-self` with no flex parent (minor).** `.cv-generate{align-self:flex-start}` (`app.css:33`) has no effect in the page's block layout — dead declaration.

### Pillar 6: Experience Design (2/4)

**What is good.** The state model is genuinely thorough: `rank_first / ready / generated / compiled_ok / blocked` computed server-side (`app/api/tailoring.py:121-137`), a `skip_reason`+`skip_label` pair for the disabled/fact-store/no-score cases, a retained append-only compile history including blocked rows (D-117, `tailoring.html:55-70`), an optimistic-concurrency guard on compile (D-109, `:461-475`), advisory-only grounding bands that never block (`:199-220`), and inline swaps that avoid full reloads. Blocked artifacts are correctly unreachable for download (`ok_only=True`, `:512`) and the recovery path (fresh tailor) is explained.

**Findings.**
- **Typed refusals are invisible (BLOCKER).** As Top-3 fix 1 — the phase's explicit refusal deliverable (`tailoring_failed`) and every other error path return 4xx/5xx, which htmx 2.0.10 refuses to swap. The user gets no feedback on a failed generate, a stale patch, a disabled surface, or a parse error; the DOM is simply unchanged.
- **No busy state on the two expensive operations (WARNING, NEW).** The generate control (`tailoring.html:28-34`) and the compile button (`_tailoring_review.html:66-77`) carry no `hx-indicator`, `hx-disabled-elt`, `hx-sync`, or `aria-busy` (grep: zero `hx-indicator`/`hx-disabled`/`hx-sync` in any template). Generate performs an LLM call and compile shells out to Tectonic — both multi-second. Double-clicking Generate fires two paid LLM calls and two racing swaps; the user sees nothing while waiting. For a project whose stated constraint is LLM cost, this is more than cosmetic. Fix: `hx-disabled-elt="this"` (the existing `button:disabled{opacity:.6;cursor:not-allowed}` rule already styles it) and an `hx-indicator` label.
- **History download links misdirect (WARNING).** As Pillar 1 — a per-entry affordance resolves to the newest artifact.
- **The compile result destroys its own live region (WARNING).** As Top-3 fix 3 — after compile, the `aria-live="polite"` section is replaced by a non-live `div` (`_download_fragment`, `:263-269`), so neither "Compiled." nor blocked findings are announced. Conversely, on a successful generate the entire long preview + change log + coverage panel is injected inside a live region at once — a screen-reader flood rather than a concise announcement.
- **The compile response fragments are unstyled (WARNING, NEW).** `_download_fragment` (`:263-269`) uses `class="tailoring-result"` and `_findings_fragment` (`:272-288`) uses `class="verification-findings"`; **neither class has a rule** in `input.css` or `app.css`. Tailwind preflight resets `ol,ul,menu{list-style:none}`, so the blocked-checks list renders as an unbulleted, unindented run of text — inconsistent with the page-rendered `_cv_findings.html`, which uses `.requirement-list` (disc + indent + margins). The inline fragment also drops the per-row `req-gap`/`req-partial` colour and `badge` treatment and omits the `offending` ids that the page variant shows. `tests/test_stylesheet_coverage.py` misses these because they are literal classes in Python strings, not template `class="…"` attributes. Fix: reuse `.requirement-list` and the existing status classes in the inline fragments.
- **Generate has no non-JS fallback (minor).** It is a bare `<button hx-post=…>` with no enclosing form, unlike the compile control which carries `method="post"`. If htmx fails to load, Generate is dead while Compile still posts.
- **No URL/history state (minor, inherent).** The generate/compile swaps set no `hx-push-url`; refresh returns to the page shell. Acceptable for a local tool, but named for completeness.

---

## Registry Safety

Skipped: no `components.json` exists (this is a Jinja2 + HTMX + vendored-Tailwind app, not a shadcn project), and no third-party registry blocks are declared anywhere. No registry audit performed.

---

## Files Audited

- `app/web/templates/html/tailoring.html` — page shell: generate control (`:28-34`), unconditional empty slot (`:35`), raw `compile_status` (`:41,61`), inline-only download links (`:43,64`), history (`:55-70`)
- `app/web/templates/html/_tailoring_review.html` — review fragment root id (`:17`), struck drops (`:33`), coverage classes (`:49-53`), bare badge (`:51`), compile form (`:66-77`)
- `app/web/templates/html/_cv_findings.html` — blocked findings (`:12-27`), `req-*` classes (`:20`), bare badge (`:21`)
- `app/web/templates/html/listing_detail.html:43` — the "Tailor my CV for this job" entry link
- `app/web/templates/html/base.html` — shell, vendored assets, nav
- `app/api/tailoring.py` — `_error_fragment` (`:223-229`), `_download_fragment` (`:263-269`), `_findings_fragment` (`:272-288`), refusal call sites (`:365,369,374,388,397,443,447,452,470`), `_not_found` (`:113-118`), PDF disposition (`:526`); all 4xx/5xx
- `static/vendor/app.css:31-34` — the four phase-06 rules (present only here) + `:17-21` requirement/verdict rules
- `assets/tailwind/input.css` — component layer, base layer (`:62-170`), button rule (`:252-297`); **absent** every phase-06/05 component class
- `static/vendor/htmx.min.js` — v2.0.10 `responseHandling` default (`[45]..` → `swap:false,error:true`)
- `Dockerfile:14-19,113` — Tailwind rebuild and `COPY --from=assets`
- `tests/api/test_tailoring_generate.py`, `tests/api/test_tailoring_review.py` — status/body-only assertions
- `tests/test_stylesheet_coverage.py` — template-only class scan (EXEMPT_CLASSES at `:47-77`)
- `app/web/filters.py:34-51` — `human_label` / `format_datetime`
- `.planning/phases/06-tailoring-verification/06-CONTEXT.md`, `06-08-SUMMARY.md`, `06-09-SUMMARY.md`, `.planning/REQUIREMENTS.md:104`
- Rebuild proof: `/tmp/app-rebuild.css` (33,427 B vs committed 36,100 B; zero phase-06 selectors)

**Screenshot hygiene:** `.planning/ui-reviews/.gitignore` present and covers `*.png|webp|jpg|jpeg|gif|bmp|tiff`; the gate ran before capture; no server and no Playwright, so no binaries were written by this audit.

---

_Reviewed: 2026-09-25_
_Reviewer: gsd-ui-auditor_
_Baseline: abstract 6-pillar (no UI-SPEC.md exists)_
_Overall: 15/24 — happy-path preview/compile works and state coverage is strong, but typed refusals never render (htmx 4xx no-swap) and the Docker-built stylesheet drops every phase-06 component rule; UI-05 download affordance is unreachable from the UI._
