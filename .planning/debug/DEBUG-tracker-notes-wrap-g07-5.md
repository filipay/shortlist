---
status: diagnosed
trigger: "G-07-5 — tracker Notes column forces horizontal scroll; long notes don't wrap; actions unreachable (and dd/mm/yyyy overlays Update status)"
created: 2026-10-06T00:00:00Z
updated: 2026-10-06T00:00:00Z
audit_acknowledged:
  milestone: v1.0
  at: 2026-10-15
  status: diagnosed
---

## Current Focus

<!-- OVERWRITE on each update - reflects NOW -->

hypothesis: "CONFIRMED — the tracker reuses the queue's nowrap cell vocabulary on a row shape it was never sized for. `.truncate` (nowrap, no width) makes the note column demand the note's full max-content width; `.listing-actions` (nowrap) makes the actions column demand the sum of both edit forms; because `.queue-table` is `display:block; overflow-x:auto`, that over-width becomes a horizontal scrollbar instead of wrapping, pushing the last (Actions) column off-screen."
test: "Read tracker templates + the two CSS layers; confirmed against the committed styled UI screenshot `.planning/ui-reviews/test-applications.png`."
expecting: "Done — mechanism matches the screenshot and the CSS."
next_action: "None — diagnosis complete (find_root_cause_only)."

## Symptoms

<!-- Written during gathering, then IMMUTABLE -->

expected: "The tracker Notes column is readable without horizontal scrolling; long notes wrap and the row's actions remain reachable. (UAT test 1 as originally written asserted one-line truncation + title=; the corrected truth is wrap.)"
actual: "\"I think the notes should wrap and scroll vertically rather than do a horizontal scroll, since actions are at the end of that table. Also \"Update Status\" has dd/mm/yyyy overlaying it, making it hard to read and press. I dont see it wrapping\""
errors: "None reported"
reproduction: "Open `/applications` with a row whose note is longer than the cell; inspect the Latest note column and the Actions column."
started: "Discovered during UAT (2026-10-06)"

## Eliminated

<!-- APPEND only - prevents re-investigating -->

- hypothesis: "The note cell's `title=\"\"` attribute is missing, so the full note is lost."
  evidence: "`_application_row.html:21` renders `title=\"{{ row.notes or '' }}\"`. The attribute is present; the defect is layout, not data fidelity."
  timestamp: 2026-10-06

- hypothesis: "`.queue-table { overflow-x:auto }` is itself the bug and should be removed."
  evidence: "The wrapper's overflow is a deliberate, correct fallback (07-04-PLAN.md:29, 07-UI-SPEC.md:414). Removing it would clip the actions column instead of scrolling. The over-width comes from the nowrap CELLS, not the wrapper."
  timestamp: 2026-10-06

## Evidence

<!-- APPEND only - facts discovered -->

- timestamp: 2026-10-06
  checked: "app/web/templates/html/_application_row.html:21"
  found: "<td class=\"truncate\" title=\"{{ row.notes or '' }}\">{{ row.notes or '' }}</td> — the note cell is the only `.truncate` use in the whole template tree (grep of app/web/templates)."
  implication: "The tracker note column is deliberately `white-space:nowrap`; the fix is scoped to this cell (plus the CSS rule it depends on)."

- timestamp: 2026-10-06
  checked: "static/vendor/app.css — built Tailwind output"
  found: ".truncate{text-overflow:ellipsis;white-space:nowrap;overflow:hidden} — no width or max-width. `.truncate` is a Tailwind utility, absent from assets/tailwind/input.css."
  implication: "On an auto-layout <td>, `white-space:nowrap` makes the cell's min-content width equal the full note text. `overflow:hidden`/`text-overflow:ellipsis` cannot engage because the cell has no definite width to clip against, so the column grows to fit the whole note instead of ellipsizing."

- timestamp: 2026-10-06
  checked: "assets/tailwind/input.css:531-539 and static/vendor/app.css `.queue-table`"
  found: ".queue-table { display:block; overflow-x:auto; max-width:100%; ... } and global `table { width:100% }` (input.css:152-155)."
  implication: "The table box is capped at 100% of its container, and its over-wide content becomes a horizontal scrollbar. So the note-driven column growth is rendered as a horizontal scroll, exactly as the user reports, rather than wrapping."

- timestamp: 2026-10-06
  checked: "assets/tailwind/input.css:701-704 (.listing-actions) and :706-709 (.listing-action)"
  found: ".listing-actions { min-width:10rem; white-space:nowrap } ; .listing-action { display:inline-block; margin-right:0.5rem }."
  implication: "The Actions <td> (the LAST column, _application_row.html:22) refuses to wrap, so its min-content width is the sum of BOTH edit forms. This adds to the table's forced width and places the actions off the right edge — the user's 'actions are at the end of that table'."

- timestamp: 2026-10-06
  checked: "app/web/templates/html/_listing_row.html:65 vs _application_row.html:22-69; _action_forms.html"
  found: "The queue's `.listing-actions` cell holds two `.listing-action` forms, each with only a single <button>. The tracker reuses the same classes but puts a labelled <select>, a `width:100%` text input, a <input type=\"date\"> and a button inside the inline-block forms."
  implication: "Shape mismatch: the queue action vocabulary was sized for bare buttons, not for labelled 100%-width controls. This is the shared cause of both the forced width and the dd/mm/yyyy overlap."

- timestamp: 2026-10-06
  checked: "assets/tailwind/input.css:299-313, 354-359, 843-846; built .field-label"
  found: "input[type=text|search|number|email|url], select, textarea { width:100% } ; label { display:block } ; .field-label { display:block }."
  implication: "Inside a shrink-to-fit inline-block `.listing-action`, a `width:100%` control plus `white-space:nowrap` (inherited from `.listing-actions`) suppresses the soft wrap between the control and the following button, so the button overflows the form's narrow box to the right and paints over the next form's control."

- timestamp: 2026-10-06
  checked: ".planning/ui-reviews/test-applications.png (styled, CSS loaded)"
  found: "Actions column: the date input showing `02/10/2026` and the blue `Update status` button physically overlap at the same y; `Save notes` is clipped at the right edge. The date text and button text are superimposed."
  implication: "Direct visual confirmation of the overlap mechanism in evidence — the first form's button overflows its inline-block box onto the second form's date input."

- timestamp: 2026-10-06
  checked: "07-04-PLAN.md:33 and 07-UI-SPEC.md:415"
  found: "Both state the note cell 'wraps (`white-space:nowrap` stays off)' AND 'truncates to one line with the full string in title=\"\"' — mutually exclusive. The implementation chose `.truncate` (nowrap)."
  implication: "The spec carried a self-contradiction; the corrected truth resolves it in favour of wrapping. This is why the shipped behavior satisfies neither intent cleanly."

## Resolution

<!-- OVERWRITE as understanding evolves -->

root_cause: |
  The tracker reused the queue's non-wrapping table-cell vocabulary on a row shape it
  was never sized for, so every column is forced to its max-content width and the table
  overflows horizontally instead of wrapping.

  Concretely:
  (1) `_application_row.html:21` puts `.truncate` on the note <td>. `.truncate`
      (static/vendor/app.css) is `white-space:nowrap; overflow:hidden;
      text-overflow:ellipsis` with NO width. In an auto-layout table a nowrap cell's
      min-content width is the entire note string, and `overflow:hidden`/ellipsis cannot
      clip a cell with no definite width — so the column expands to fit the whole note
      instead of truncating. This is the direct cause of "I dont see it wrapping".
  (2) `.queue-table` (input.css:531-539) is `display:block; overflow-x:auto` with
      `max-width:100%`, so that column growth is rendered as a horizontal scrollbar
      rather than a layout that wraps.
  (3) `.listing-actions` (input.css:701-704) is `min-width:10rem; white-space:nowrap`,
      so the Actions <td> — the LAST column — refuses to wrap and its min-content width
      is the sum of both edit forms (labelled select + 100%-width text input + date
      input + buttons). The actions therefore sit off the right edge, behind the
      horizontal scroll: "actions are at the end of that table".
  (4) The same nowrap rule causes the dd/mm/yyyy overlap (G-07-6): inside the
      shrink-to-fit inline-block `.listing-action` form, `white-space:nowrap` suppresses
      the soft wrap between a `width:100%` control and the following button, so the
      button overflows the narrow form box to the right and paints over the next form's
      `<input type="date">` (confirmed in .planning/ui-reviews/test-applications.png).

  The root cause is NOT the `.queue-table` overflow wrapper (that is a correct fallback)
  and NOT the `title=""` attribute (present and correct). It is the combination of
  nowrap cells forcing max-content width on a row that also carries free text and two
  labelled edit forms. The queue row, whose action cell holds only two bare buttons,
  never exposed this; the tracker's richer shape did.

fix: ""
verification: ""
files_changed: []
