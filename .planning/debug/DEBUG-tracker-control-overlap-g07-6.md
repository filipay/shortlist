---
status: diagnosed
gap: G-07-6
slug: tracker-control-overlap-g07-6
created: 2026-10-12
goal: find_root_cause_only
audit_acknowledged:
  milestone: v1.0
  at: 2026-10-15
  status: diagnosed
---

# G-07-6 — Tracker row controls overlap (`dd/mm/yyyy` over `Update status`)

## Gap

**Truth (what must hold):** The row's controls do not overlap: the `Update status`
button is legible and clickable, with no date field (`dd/mm/yyyy`) overlaid on it.

**Expected (UAT test 1):** The tracker row controls render cleanly with no overlap;
the `Update status` button is readable and pressable.

**Actual (verbatim):** `"Also \"Update Status\" has dd/mm/yyyy overlaying it, making it
hard to read and press."`

**Reproduction:** `/applications` (tracker page), UAT test 1. Confirmed against the
committed UI-review screenshot `.planning/ui-reviews/test-applications.png` (one row).

## Root Cause

**The tracker's action cell reuses the queue's action-cell classes, whose layout
contract assumes bare buttons, on a cell that now contains full-width labelled form
controls.** The queue's `white-space: nowrap` removes the soft-wrap opportunity between
a `width:100%` control and the button that follows it, so the button overflows its
shrink-to-fit `inline-block` form box and is painted over by the next form's date input.

The overlap is a conjunction (AND-gate) of conditions, all present:

1. `_application_row.html:22` — the `<td class="listing-actions">` reuses the queue-only
   cell class.
2. `input.css:701-704` — `.listing-actions { min-width:10rem; white-space:nowrap }`.
   `white-space` is inherited by every descendant, including the forms' inline content.
3. `input.css:706-709` — `.listing-action { display:inline-block }`. Each form is a
   shrink-to-fit inline-block, so the two forms (and their boxes) sit side-by-side on
   one line; the wrapping cell also cannot wrap between them.
4. `input.css:299-313` — `input[type=text]… select … { width:100% }`. A `width:100%`
   control resolves against the form's content width and consumes the whole form content
   box, leaving zero width for a following inline-block sibling.
5. `input.css:843-849` (`.field-label`) and base `label { display:block }` put the label
   in a block of its own, but the form's two `x-show`-hidden elements
   (`_application_row.html:39-44`) generate no boxes at runtime, so the visible
   `select` and the `button` become **consecutive inline-level boxes in one anonymous
   block → one line box** (`select` + `button` on the same line).
6. `_application_row.html:45` — `Update status` is the inline-block button on that line.
   With `white-space:nowrap` in force it cannot wrap to the next line, so it overflows
   the form's right edge by its full width.
7. `_application_row.html:50-59` — the second form starts exactly at the first form's
   right edge (no margin/negative margin involved; inline-blocks pack left-to-right).
   Its `Next action` `<input type="date">` is the leading inline content of its own last
   line box, so it begins at that same x. Because the second form comes later in the
   DOM, it paints **on top** of the overflowing button.

**Net effect** (measured on `test-applications.png`, 2694×2002):

- Form 1's `select` right edge = `x≈2130`; the `Update status` blue button spans
  `x≈2141–2409` — i.e. the button starts *at* the form's right edge and lies entirely
  outside it (overflow).
- Form 2's box left edge = form 1's right edge; form 2's date input spans the same
  `x` band, so `10/01/2026` and its calendar glyph render directly over `Update status`.
- Form 2's own last-line button (`Save notes`) overflows form 2 the same way, which is
  why it is clipped at the cell's right edge.

The queue does **not** exhibit this because its forms contain only hidden inputs and
buttons, never a `width:100%` control: `_listing_row.html:65` →
`_action_forms.html:19-42`.

The hypothesis from G-07-5 is **confirmed**, with one correction: the date input carries
no `width:100%` (it is *not* in the `input.css:299-305` selector list); it overlaps by
*position* (first item of form 2's last line box), not by width. The width:100%
statement correctly applies to form 1's `select`.

## Evidence Summary (file:line)

| # | Location | Rule / markup | Role |
|---|----------|---------------|------|
| 1 | `app/web/templates/html/_application_row.html:22` | `<td class="listing-actions">` | Tracker reuses the queue's action-cell class |
| 2 | `assets/tailwind/input.css:701-704` | `.listing-actions{min-width:10rem;white-space:nowrap}` | Inherited `nowrap` suppresses the wrap between the `width:100%` control and the button |
| 3 | `assets/tailwind/input.css:706-709` | `.listing-action{display:inline-block;margin-right:.5rem}` | Two shrink-to-fit forms pack side-by-side; the button cannot wrap inside its form |
| 4 | `assets/tailwind/input.css:299-313` | `input[type=text]…,select,textarea{width:100%}` | The `select`/text inputs fill the whole form content box → button has no room |
| 5 | `assets/tailwind/input.css:843-849` + `:354-359` | `.field-label{display:block}` / `label{display:block}` | Labels are block; the two `x-show` elements vanish at runtime, joining `select`+`button` into one line box |
| 6 | `app/web/templates/html/_application_row.html:34-45` | `select` (width 100%) + `button Update status` | The overflowing button |
| 7 | `app/web/templates/html/_application_row.html:50-59` | form 2: text input, `input type="date"`, `Save notes` | Form whose date input paints on top |
| 8 | `app/web/templates/html/_application_row.html:39-44` | `x-show="stage === 'applied'"` label + select | Hidden → enables the single-line box (JS/Alpine on; with JS off the geometry differs) |
| 9 | `app/web/templates/html/_listing_row.html:65` + `_action_forms.html:19-42` | Queue action cell: hidden inputs + buttons only | Counter-example proving the classes are queue-shaped, not tracker-shaped |
| 10 | `static/vendor/app.css` (built) | `.listing-actions{white-space:nowrap;min-width:10rem}`, `.listing-action{display:inline-block}`, `select,…{width:100%}`, `.field-label{display:block}` | Built stylesheet is current — the bug ships |
| 11 | `.planning/ui-reviews/test-applications.png` (2694×2002) | Blue button band `x2141–2554`, `y1026–1101`; date glyphs `10/01/2026` + calendar icon over `Update status` | Independent pixel confirmation |

No `position:absolute`, `float`, negative margin, flex or grid is involved; grep of
`input.css` shows only `:701-713` styles these classes. The overlap is pure
inline-block overflow paint order.

## Files Involved

- `app/web/templates/html/_application_row.html` — reuse of `listing-actions` /
  `listing-action` around labelled `width:100%` controls and a date input (lines 22, 28,
  34-45, 50-59). Primary surface.
- `assets/tailwind/input.css` — `.listing-actions` (`:701-704`), `.listing-action`
  (`:706-709`), `input/select{width:100%}` (`:299-313`), `label/.field-label`
  (`:354-359`, `:843-849`). Shared rules; queue-shaped.
- `app/web/templates/html/applications_list.html:27-43` — the tracker table that renders
  the row (context: no per-cell class is added here).
- `app/web/templates/html/_listing_row.html:65` + `app/web/templates/html/_action_forms.html`
  — the queue usage that the shared classes were designed for (must not regress).
- `static/vendor/app.css` — built artefact; regenerated by the Tailwind CLI, so a CSS
  fix implies a rebuild.

## Suggested Fix Direction (diagnosis only)

Do **not** reuse the queue's button-only layout contract for a cell that stacks labelled
full-width controls. Give the tracker's action cell its own class (e.g.
`tracker-actions`) whose layout permits normal wrapping and full-width stacked forms —
`white-space: normal` and/or `display: block` on the forms — rather than relying on
`inline-block` + `nowrap`. Alternatively scope an override so the tracker cell resets
`white-space` and stacks its forms, leaving `.listing-actions`/`.listing-action`
untouched for the queue.

- Prefer the smallest, scoped change: the bug is caused by the tracker *reusing* a class
  built for bare buttons. Changing the shared rule would risk the queue row layout
  (Save/Hide must stay on one line) and the sibling gap G-07-5's notes cell.
- Constraint: any change to `assets/tailwind/input.css` requires a Tailwind rebuild so
  `static/vendor/app.css` reflects it (it currently contains the offending rules).
- Verification should assert geometry, not just presence: e.g. the rendered
  `Update status` button's bounding rect must not intersect the `Next action` date
  input's rect (a Playwright `boundingBox()` overlap assertion), on a row where the
  `x-show` picker is hidden (the shipped default) and with JS on.
