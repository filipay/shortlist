# Phase 07 — UI Review

**Audited:** 2026-10-12
**Baseline:** `07-UI-SPEC.md` (approved 2026-09-30; source-of-truth prose corrected 2026-10-12 by plan 07-13)
**Screenshots:** not captured — no dev server reachable on :3000/:5173/:8080/:8000. Code-only audit (Tailwind/class audit, copy-string audit, state-coverage check). Prior captures in `.planning/ui-reviews/` (`test-applications.png`, `test-record-applications.png`) are dated 2026-10-01, i.e. **before** the G-07-5/G-07-6 fixes, so they were not used as evidence.
**Registry audit:** skipped — no `components.json` (`shadcn_initialized: false`), no third-party registry declared.
**Deployment baseline (CR-01):** re-checked. `tests/test_stylesheet_coverage.py` → **10 passed**, including the byte-identity guard `test_the_committed_stylesheet_is_the_build_of_its_source` (it ran, did not skip, so `node` + the pinned 4.3.3 CLI were present). The committed `static/vendor/app.css` is the reproducible build of `assets/tailwind/input.css`, and every literal phase-7 class token resolves to a rule in the source. CR-01 is closed.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | Copy is specific and contract-faithful almost everywhere, but the declared drafting-failure error string was reworded, and the declared `Saved` success banner is not rendered anywhere. |
| 2. Visuals | 3/4 | Contract's focal point (Stage badge) and table shell implemented verbatim; refusal rows use an undefined `.listing-error` class (unstyled), and saves produce no positive visual feedback. |
| 3. Color | 4/4 | Exact `.badge-stage-*` token map, restrained accent (one `.apply-link`, links, submit buttons), no stray hues. |
| 4. Typography | 4/4 | No new sizes or weights; the declared 400/600 scale is respected via reused component rules. |
| 5. Spacing | 2/4 | The §Spacing **44×44px touch-target** requirement for new compact controls is entirely unimplemented — no `2.75rem`/`44px` anywhere in the sheet. |
| 6. Experience Design | 3/4 | Comprehensive state coverage (loading / empty / error / no-JS / destructive confirm), but no success confirmation on status/notes save. |

**Overall: 19/24**

---

## Top 3 Priority Fixes

1. **New compact controls do not meet the 44×44px touch target** — `07-UI-SPEC.md` §Spacing says *"every new icon-only or compact control (copy button, history toggle, stage filter chip) must clear 44×44px (`min-height:2.75rem; min-width:2.75rem`)"*. None does: the `Copy answer` button uses `.button` (padding `0.5rem 0.875rem`, `line-height:1.25` ≈ 38px tall), the `History (n)` toggle is a bare `.stage-log summary` (≈ 20px), and the `Needs action` / `Stage` filter chip `.queue-toggle` is ≈ 38px. `grep -rn "2.75rem\|44px" assets/tailwind/input.css static/vendor/app.css` → no matches. **User impact:** the phone layout (UI-06 / Phase 8) gets sub-minimum tap targets on the exact controls the spec singled out. **Fix:** add `min-height:2.75rem; min-width:2.75rem` to the three new controls (scoped, e.g. a `.copy-answer` / `.stage-log summary` / `.queue-toggle` rule), backfill `input.css`, and regenerate `app.css` with the pinned CLI (never hand-edit the artifact — CR-01).
2. **No success confirmation on save or status transition** — the Copywriting Contract declares `Save success / refusal banner | Saved / … (.settings-banner / .settings-banner-error)`. The refusal half is real (the 4xx `data-error` row fragment carries visible message text), but **`Saved` is rendered nowhere**: `POST /applications/{id}/status` and `POST /applications/{id}` both silently re-render the row (`applications.py:279-281, 320-322`), and `grep -rn '"Saved"' app/` finds no banner. **User impact:** after `Update status` / `Save notes` the user gets no confirmation the write landed — on a fast connection the swap is visually identical to a no-op. **Fix:** render the `.settings-banner` `Saved` line in the re-rendered row (or an `hx` out-of-band swap), and keep the existing `data-error` refusal path.
3. **Drafting-failure error copy diverges from the contract, and the refusal row is unstyled** — the contract's error state reads *"The drafting call did not return usable answers. Check that the LLM backend on Settings is reachable, then try again."*; the shipped string is *"The drafting call did not return a usable response. Your existing drafts were kept."* (`app/api/apply.py:337-340`). The shipped copy is arguably more honest (it states drafts survive), but it is not the approved string. Separately, `_row_error` emits `class="listing-row listing-error"` (`applications.py:89-92`), and **`.listing-error` is defined in neither `input.css` nor `app.css`** — so a refused transition renders as an untargeted plain row (the message text does show, so this is cosmetic, not silent). **Fix:** reconcile the error copy with the spec (or amend the spec), and either define `.listing-error` in `input.css` or reuse an existing danger/notice rule.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

Audited every declared string in `## Copywriting Contract` and `### Phase-specific copy` against the templates and routes.

**Matched exactly (no generic `Submit`/`OK`/`Cancel` labels anywhere):**
- Package H2 `Apply package` (`apply.html:20`), back link `Back to the listing` (`:22`).
- Gated heading/body/CTA (`:25-31`), including `data-state="no-ok-artifact"`.
- No-submit reassurance (`:34-36`), outbound CTA `Open the application form` + empty-link fallback (`:41-43`).
- Verified-PDF block: `Your verified CV`, `Preview`, `Download the exact PDF you'll send` (`:47-52`).
- Gap checklist heading + empty copy (`:57-68`).
- `Drafted answers`, `Not yet drafted.`, empty copy, `Add a question` + placeholder, `Draft answers`, `Copy answer` → `Copied`, unsupported-claim warning, `Evidence: ` (`_screening_drafts.html:25-97`).
- Tracker H2/nav `Applications`, count pluralisation, `Needs action`, needs-action empty, `Stage`, `Search` + placeholder, `History ({{ n }})`, history entry + `created` for NULL, `No history recorded.`, `Move to`, `CV you sent` + helper, `Notes`, `Next action`, `Applied` (`applications.html`, `applications_list.html`, `_application_row.html`, `_application_history.html`).
- Destructive confirmation `Delete this drafted answer?` + the "only the answer is removed" note (`_screening_drafts.html:56,60`).
- Refusal copy `Record a verified CV first — …` at both write sites (`applications.py:201,269`).

**Findings:**
1. **Drafting-failure copy reworded** (WARNING) — spec error state vs `apply.py:338`. See Top Fix 3.
2. **Declared `Saved` success banner unimplemented** (WARNING) — see Top Fix 2. No template or route emits it.
3. **Spec-internal conflict on the tracker empty state** (INFO) — the contract's generic `Empty state heading/body` rows (`No applications yet` + the long "linked to the exact CV you sent…" body) are not what renders; the `Tracker empty` variant `No applications yet. Record one from a job's apply package.` does (`applications_list.html:23`). The two spec rows contradict each other; the implementation picks the phase-specific one. Not a defect, but the spec should drop the generic rows.
4. **Extra `All stages` option** (INFO) — `applications.html:42` adds an empty option so the select can represent "no filter". Sensible and necessary; the spec's "options are the eight frozen values" is now imprecise.

### Pillar 2: Visuals (3/4)

- **Focal point implemented per contract** — the Stage column is `<span class="badge badge-stage-{{ row.status }}">` and is the only colour-coded element in an otherwise neutral `.queue-table`; the Listing/Company cell stays first, so the tracker and the queue read the same (`_application_row.html:13-18`).
- **Table shell reused verbatim** — `.queue-table` on `<table>` with `scope="col"` headers (`applications_list.html:27-36`); `.listing-row` on `<tr>` with `.listing-stale` for overdue (`_application_row.html:10-12`).
- **Overdue second focal point** — `.next-overdue` on the next-action cell when `row.is_overdue` (`_application_row.html:20`).
- **No icon-only controls** — the copy button and history toggle both carry text labels, so no `aria-label` gap.
- **Finding (WARNING):** `.listing-error` is undefined in the stylesheet (see Top Fix 3) — a refused transition row has no danger treatment; the message is visible only because the `<td colspan="6">` text is unstyled-but-present.
- **Finding (WARNING):** no positive visual state change after a successful save (see Top Fix 2).

### Pillar 3: Color (4/4)

- **60/30/10 respected** — paper `#ffffff` surfaces (page, `.queue-table`, `.stage-log`), `--color-surface`/`--color-surface-2` panels and chips (`.tailoring-review`, `.apply-assurance` info-bg, `.queue-toggle`), accent `#2563eb` confined to the declared list.
- **Stage badge map matches the contract table rule-for-rule** (`input.css:1866-1873`): discovered/queued/withdrawn → surface-2/muted; shortlisted/interviewing → info-bg/info; applied → accent-bg/accent-hover; offer → success-bg/success; rejected → danger-bg/danger. No new hues introduced.
- **Accent restraint verified by grep** — phase-7 templates use exactly one `.apply-link`, one `.cv-download` (bold, not accent), two `.listing-detail-link`s, and the automatic `button[type=submit]` accent on `Record application` / `Update status` / `Save notes` / `Add question` / `Draft answers`. The `Copy answer` control is `type="button"` with `class="button"` → neutral paper, as the spec demands.
- **Hardcoded colours are the sanctioned copies** — `.apply-assurance` `#155e75` and `.answer-warning` `#92400e` mirror `.criteria-note` / `.capability-warning` verbatim, exactly as the spec's "New tokens" list instructs. `.apply-link` `#fff` mirrors `#run-search-now`.
- No deviations found.

### Pillar 4: Typography (4/4)

- `grep -rhoE "text-(xs|sm|base|lg|xl|2xl|3xl)"` over the six phase-7 templates → **zero** utility font-size classes; sizing comes from reused component rules only.
- No `font-{thin,light,normal,medium,semibold,bold}` utility classes in the templates — the two declared weights (400 body, 600 headings/labels) plus the inherited `font-weight:500` on `button`/`label`/`.field-label`/`th` are used exactly as the spec allows ("Phase 7 *inherits* those rules … and does **not** declare a third weight").
- `.answer-text { max-width:65ch }` (`input.css:1883`) gives the drafted answer the declared readable line length and matches `.detail-rationale`.
- Micro sizes are reused, not added: `.answer-warning` inherits `.capability-warning`'s `0.9rem`, `.badge` stays `0.75rem`, `.stage-entry` `0.9rem`.
- No deviations found.

### Pillar 5: Spacing (2/4)

- **No arbitrary values** — `grep -rnE "\[[0-9.]+(px|rem)\]"` over the phase-7 templates → no matches; all spacing comes from shipped rules.
- **Tracker cell spacing is correct** — `.tracker-note` (`white-space:normal; overflow-wrap:anywhere; max-width:24rem`), `.tracker-actions` (`min-width:16rem; white-space:normal; vertical-align:top`), `.tracker-action` (`display:block; margin:0 0 .5rem`) are present in `input.css:719-734` and match the spec's new-token list; the note cell also keeps the full string in `title=""` (`_application_row.html:21`).
- **BLOCKING-ish deviation (scored as WARNING): the 44×44px touch-target requirement is unmet.** The spec is explicit and names the three controls. Measured from the shipped rules:
  - `Copy answer` → `.button`/`button` padding `0.5rem` + `line-height:1.25` on 1rem ≈ **38px** tall, no `min-width`.
  - `History (n)` → `.stage-log summary` sets only `font-weight:600; cursor:pointer` ≈ **20px** tap box (the `<details>` padding does not enlarge the summary hit area).
  - `Needs action` toggle / `Stage` chip → `.queue-toggle` padding `0.5rem 0.75rem` ≈ **38px**.
  `grep -rn "2.75rem\|44px" assets/tailwind/input.css static/vendor/app.css` → **no matches**. The contract's touch-target clause is simply not implemented.
- Everything else in the spacing contract (anchor values, micro-step reuse, no normalisation) is honoured.

### Pillar 6: Experience Design (3/4)

State coverage is unusually thorough and was checked against the spec's `## UI Considerations` table:

- **Loading:** `Draft answers` carries `hx-indicator="#draft-progress"` + `hx-disabled-elt="find button"` with a `role="status" aria-live="polite"` line (`_screening_drafts.html:87-96`); `Copy answer` flips its own label to `Copied` for ~2s and leaves the text selectable on clipboard failure (`:46-49`).
- **Empty:** tracker empty vs filtered-empty with `Clear filters` (`applications_list.html:11-24`), needs-action empty, history empty `No history recorded.` (`_application_history.html:19`), answers empty, gap-checklist empty, gated package panel.
- **Error:** drafting refusal via `_answers_error` (`apply.py:335-347`), transport failure via `base.html:58-68` (covers `#apply-answers`), refused transition as a `data-error` row fragment (`applications.py:84-93`), unknown listing 404 fragment.
- **No-JS degrade:** every control is a real `<form method=post action=…>` or a real `<a>`; the outbound apply action is a plain anchor, never a POST (`apply.html:41`); the `applied` picker renders always when Alpine is off and the server ignores it unless `status=applied` (`application_repo.py:461-474`, verified: a non-`applied` record stores `cv_artifact_id=None`).
- **Destructive confirmation:** the only destructive affordance uses `confirm('Delete this drafted answer?')` and `.cv-delete` (danger) (`_screening_drafts.html:54-59`).
- **Append-only history:** `<details class="stage-log">` with an HTMX `toggle once` fetch; the summary count is server-computed (`_application_row.html:62-68`).

**Findings:**
1. **No success confirmation on save/transition** (WARNING) — see Top Fix 2. This is the one real state-coverage gap.
2. **`.listing-error` undefined** (WARNING) — see Top Fix 3; the refusal state is functionally present but visually untreated.
3. **Preserved human checks still open** (INFO) — the G-07-6 rendered-rect measurement and the multi-paragraph clipboard-fidelity backstop remain `PRESENT_BEHAVIOR_UNVERIFIED` per `07-VERIFICATION.md`; this code-only audit cannot close them and they are not defects.

---

## Registry Safety

Not applicable — `components.json` absent, `shadcn_initialized: false`, no third-party registry declared. No block entered the contract, so no vetting gate ran.

---

## Files Audited

Templates:
- `app/web/templates/html/apply.html`
- `app/web/templates/html/_screening_drafts.html`
- `app/web/templates/html/applications.html`
- `app/web/templates/html/applications_list.html`
- `app/web/templates/html/_application_row.html`
- `app/web/templates/html/_application_history.html`
- `app/web/templates/html/base.html` (nav + transport-error script)
- `app/web/templates/html/listing_detail.html` (entry point, `:48`)

Stylesheet:
- `assets/tailwind/input.css` (source of truth — `:245-314`, `:389-400`, `:455-483`, `:569-734`, `:795-806`, `:1040-1052`, `:1500-1536`, `:1819-1885`)
- `static/vendor/app.css` (committed build)

Routes / logic:
- `app/api/apply.py` (`:325-354`)
- `app/api/applications.py` (`:76-93`, `:185-279`, `:286-322`)
- `app/db/repositories/application_repo.py` (`:439-558`)
- `app/web/filters.py`, `app/web/template_env.py` (`human_label`, `format_datetime`)

Verification evidence:
- `tests/test_stylesheet_coverage.py` — **10 passed** (byte-identity build guard ran, did not skip)
- `.planning/phases/07-assisted-apply-tracker/07-VERIFICATION.md`, `07-UAT.md`, `07-11-SUMMARY.md`, `07-13-SUMMARY.md`, `07-14-SUMMARY.md`

---

## Verdict

**19/24 — no blocking issue.** The phase's two surfaces (apply package, tracker) are implemented against the design contract with high fidelity: copy is specific, the colour token map is exact, typography introduces nothing new, and state coverage is thorough. CR-01 (the deployed-stylesheet divergence that blocked the prior verification) is **closed and now guarded** — the committed `app.css` is the reproducible build of `input.css` and every phase-7 class resolves.

The remaining work is small and concrete: implement the spec's 44px touch targets, surface the declared `Saved` confirmation, and reconcile the drafting-failure copy / the undefined `.listing-error` refusal styling. None of these break task completion; all three are visible-quality regressions on the phone layout and the save loop.
