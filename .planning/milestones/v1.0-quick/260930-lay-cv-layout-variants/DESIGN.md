# CV layout variants — design and selection UX

Three committed layouts render the same `RenderPlan` with identical facts and
identical semantics; only presentation differs. The template is application code
(D-71): each layout is one file under `app/latex/templates/`, and the existing
`cv.tex.jinja` stays byte-for-byte unchanged because `tests/golden/base.rendered.tex`
pins its output.

| | File | Font | Body | Margins | Headings | Skills | Feel |
|---|---|---|---|---|---|---|---|
| Classic | `cv.tex.jinja` | TeX Gyre Pagella | 11pt | 1in | `\large` bold, spaced | `tabularx` label/column table | Neutral, established |
| Modern | `cv-modern.tex.jinja` | TeX Gyre Pagella | 11pt | 1in | uppercase, hairline rule beneath, airier | bold group + bullet + list, one line per group | Editorial, contemporary |
| Compact | `cv-compact.tex.jinja` | TeX Gyre Pagella | 10pt | 0.65in | base-size bold, tight, no rule | single flowing paragraph (`group: a, b, c`) | Dense, no wasted line |

All three use the same delimiters (`\VAR{}` / `\BLOCK{}`), the same package set,
and the same escaping choke point, so no new dependency, font, shell-escape or
external asset is introduced. Only the two new files are added.

## 1. The three layouts

### Classic — `cv.tex.jinja` (existing, unchanged)

- **Visual intent:** a conventional single-column CV. Centred name block;
  `\large` bold section headings; entries as **Org** — *Title* with the date range
  right-aligned and location on its own italic line; skills as a two-column
  `tabularx` table.
- **Differs from the others by:** being the reference. It is neither the roomiest
  nor the densest, and it is the only one that centres the header and tabulates
  skills.
- **Suits:** the safe default for any candidate, and anyone whose applications are
  read by a human first rather than an ATS parser.

### Modern — `cv-modern.tex.jinja` (new)

- **Visual intent:** a left-flush, editorial header (large name, contact details
  on one bullet-separated line, a hairline rule under the whole header) and
  uppercase section headings with a 0.6pt rule beneath, given more air above.
- **Concretely different from Classic:** header is left-aligned with a rule rather
  than centred; headings are uppercased by `\MakeUppercase` and underlined via
  `\titlerule`; the entry line uses a middle dot (**Org** · Title) with the title
  in roman and the dates in italic (Classic uses an em-dash, an italic title and
  roman dates); skills are stacked, one `group • a, b, c` line per group, not a
  table.
- **Suits:** candidates with a shorter history who want a more designed, modern
  read and can afford the extra vertical space.

### Compact — `cv-compact.tex.jinja` (new)

- **Visual intent:** maximum information per page with no line spent for its own
  sake. 10pt body, 0.65in margins, base-size bold headings with tight spacing and
  no rule, and zero paragraph separation inside bullet lists.
- **Concretely different from Classic:** smaller type and narrower margins;
  location moves inline onto the entry line as `(Dublin, IE)` instead of taking a
  line of its own; skills become one flowing paragraph (`languages: Python  databases: PostgreSQL`);
  bullet `itemsep` is 0pt (Classic uses 1pt).
- **Suits:** long or dense histories under a hard page budget, where preserving
  one more bullet matters more than generous whitespace.

## 2. Recommended default

**Keep Classic (`cv.tex.jinja`) as the shipped default.** It is the current default
and its bytes are pinned by `tests/golden/base.rendered.tex`; the two new layouts
are opt-in. The renderer's default argument must keep resolving to this file, so an
unset or unknown preference always produces today's exact output. Modern and
Compact are alternatives a user selects, never a silent switch.

## 3. Page consumption vs. the 2-page budget

The page budget is `meta.max_pages` (default 2) and is enforced by
`next_page_trim`: after a compile, the lowest-value bullet is dropped and the
document re-rendered until it fits, the candidates are exhausted, or the pass cap
is hit (`260929-pan`). Page count is measured by compiling, so **the layout changes
how many bullets survive the budget**:

- **Compact** spends the least vertical space per bullet and per section, so the
  same CV fits more content inside 2 pages — fewer bullets dropped. It is the
  right choice when the budget is biting.
- **Classic** is the middle ground and the tuned baseline.
- **Modern** adds air (larger heading gaps, uppercase+rule, stacked skills), so the
  same content is taller and more bullets are dropped to stay within the budget.
  The user trades content for presentation.

This is an honest trade-off, not a bug: the trim loop is deterministic and layout
is a global preference, so a given CV, layout and budget always yield the same
survivors. The picker copy should say the choice affects the *next* tailored CV.

## 4. Selection UX

### Where

In `app/web/templates/html/settings.html`, inside the existing **CV fact store**
card (`#cv-fact-store`), directly after the upload form. The layout is a property
of how the stored CV is rendered, so it belongs with the CV control the user
already visits — not a new top-level section.

### Control

A plain HTML `<form method="post" action="/settings/cv-layout">` with a `<select>`
of the three keys and a "Save layout" button. No HTMX: like the reset and weights
forms, this is a one-field setting where a full-page POST and redirect is the
simplest correct thing, and it works with JavaScript off.

Grounded copy, no marketing tone:

> **CV layout**
> Which committed layout the tailored CV is rendered with. This affects the next
> tailored CV, not ones already generated.

Options (label — short note):

- `Classic (default)` — centred header, section rules under headings, skills in a table.
- `Modern` — left header with a rule, uppercase ruled headings, stacked skills.
- `Compact` — smaller type, tighter spacing, fewer dropped bullets per page.

Do not include preview images: the app vendors no external assets and there is no
render-to-image path; a text description is the honest control.

### States

- **Unselected / default.** The preference document has no usable value, so the
  read resolves to `classic`. The select shows `Classic (default)`; a small note
  reads "Using the default." No row is required to exist.
- **Selected.** The chosen key is persisted and the select shows it. After a save
  the existing `settings-banner` idiom confirms it: "Layout set to Modern. The next
  tailored CV will use it." An unknown or hand-edited key fails **closed** to
  `classic` — a bad preference can never break a render.
- **Remembered.** One value, global, not per-user and not per-search (v1 has no
  user). The tailoring render path reads it once and passes it to
  `render_plan_to_tex`, which gains an **optional** `template_name` argument
  defaulting to the committed classic constant. `render_plan_to_tex(plan)` with no
  argument must keep returning today's exact bytes.

### Storage — no new table, no migration

Reuse the existing pinned-singleton pattern (`ranking_config`, one row pinned to
`id = 1` by `ck_ranking_config_singleton`). The `weights_json` column is already
JSON and carries six floats; add exactly one more key, `cv_layout`, to that same
document, validated at the storage boundary against the three known layout keys
(unknown → dropped, missing → `classic`), the same total-read/strict-write shape
as `read_weights`/`write_weights`.

One implementation wrinkle for the reviewer: `write_weights` currently rebuilds the
document from factors only, so it would erase `cv_layout`. The two writers must
merge-preserve each other's keys (or a single document-level read/write pair takes
over). This is a code change in `app/db/repositories/ranking_config_repo.py` — no
schema change and no migration, because the column already exists.

An alternative home is a one-line file in the mounted `cv/` volume (e.g. `/cv/layout`),
mirroring how `cv.yaml` already persists user-owned data outside the database. It is
equally migration-free and arguably cleaner semantically (a layout is not a ranking
weight), at the cost of a second persistence idiom. Flagged below.

## 5. What a reviewer must decide

1. **Storage home.** Extend the `ranking_config` JSON document with `cv_layout`
   (instruction's pinned-singleton route, no migration) versus a `/cv/layout` file
   in the CV volume (no schema coupling, second idiom). The design assumes the
   former; the latter is the cleaner semantics if the reviewer prefers it.
2. **Card placement.** Layout picker inside the CV fact-store card (recommended) or
   its own card under Settings.
3. **Scope.** The preference affects only *future* renders; stored `cv_artifacts`
   are never re-rendered. Confirm that is intended.
4. **Golden coverage.** The two new templates currently have no pinned golden bytes
   (the task forbids touching tests). Without one per layout, a future edit can
   drift silently. A reviewer should decide whether to add per-layout golden files.
5. **Compact's readability.** 10pt with 0.65in margins is deliberately dense; confirm
   it clears the app's readability bar or whether it should stay 11pt and gain
   density only from spacing.
6. **Default-arg guard.** Add a test asserting the unset preference and the unknown
   preference both render the classic bytes, so selection can never move the
   baseline.
