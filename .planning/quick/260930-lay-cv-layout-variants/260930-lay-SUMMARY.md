# 260930-lay — Add three committed CV layouts with one remembered preference

## What shipped

The tailored CV can now be rendered in one of three committed layouts — Classic
(the default), Modern and Compact — chosen once as a single global preference and
remembered across restarts. The choice is applied to the next tailored CV, fails
closed to Classic if the stored token is missing or unreadable, and never
re-renders a stored artifact.

- `app/latex/render.py` — `DEFAULT_LAYOUT` and the `LAYOUTS` map (token → template
  filename); `render_plan_to_tex` gained an optional `layout=` keyword, unknown /
  `None` / absent resolving to Classic so the no-argument call still returns the
  exact bytes it did before.
- `app/latex/templates/cv-modern.tex.jinja` — left-flush header with a rule,
  uppercase ruled section headings, roomier editorial spacing.
- `app/latex/templates/cv-compact.tex.jinja` — 10pt, 0.65in margins, tight
  headings, inline location, single-paragraph skills.
- `app/cv/layout.py` — the one-token preference store: `read_layout` (total;
  Classic on absent / garbage / unreadable, including non-UTF-8), `write_layout`
  (validated against `LAYOUTS`, atomic temp file + `os.replace`), `LAYOUT_FILENAME`.
- `app/pipeline/tailor.py` — reads the preference once per compile and threads
  `layout=` to both render sites (the initial render and the page-trim re-render).
- `app/api/settings.py` — `POST /settings/cv-layout` validating the token, writing
  it, and re-rendering with the existing settings banner; invalid tokens write nothing.
- `app/web/templates/html/settings.html` — a plain, non-HTMX picker (select +
  Save layout) inside the `#cv-fact-store` card.
- `tests/latex/test_layouts.py` — per-layout rendering, determinism, fact
  presence, hostile-bullet escaping, LF-only, and the Classic-bytes equality guards.
- `tests/golden/base.rendered.modern.tex`, `tests/golden/base.rendered.compact.tex` —
  new per-layout goldens, pinned by tests.
- `tests/cv/test_layout_store.py` — store round-trip, fail-closed paths, atomic
  replace leaving no temp file, non-UTF-8 totality.
- `tests/pipeline/test_layout_wiring.py` — the compile uses the stored layout and
  the page-trim re-render keeps it.
- `tests/api/test_settings_layout.py` — the picker renders, POSTs without HTMX,
  persists a valid token with a banner, and writes nothing for invalid tokens.

## Commits

- `7fdd91a` feat(260930-lay): let the renderer take an optional CV layout
- `f6daef9` feat(260930-lay): store the CV layout preference and apply it
- `e7aa467` feat(260930-lay): add the CV layout picker to settings
- `06d1a13` test(260930-lay): pin the layouts, the preference store and the wiring
- `0b8911e` fix(260930-lay): keep read_layout total on a non-UTF-8 preference file

## Verification

- `.venv/bin/python -m pytest -q` → 1527 passed, 14 deselected, 2 xfailed.
- Focused re-run of the four layout test files → 44 passed.
- `.venv/bin/python -m ruff check` and `ruff format --check` on all changed files → clean.
- Scoped oracle review → one medium finding (M1: `read_layout` raised
  `UnicodeDecodeError` on a non-UTF-8 file instead of failing closed), fixed by
  `0b8911e`; every other area confirmed correct and well-pinned.

## Notes / deviations

- No LaTeX engine exists in this environment: none of the three layouts was
  compiled or visually inspected — verification is byte/render and unit-test
  level only. Compact is 10pt with 0.65in margins; rendering it at 11pt with the
  density coming from spacing alone remains an available adjustment.
- Deviation accepted: `POST /settings/cv-layout` re-renders with the settings
  banner (HTTP 200) rather than issuing a 303 redirect, matching the existing
  `/settings/weights` and `/settings/reset` handlers.
- L1 accepted as-is: the HTTP boundary rejects a whitespace-padded token while
  `write_layout` strips for direct callers; relaxing the boundary was out of scope.
- No new dependency, no Alembic revision, no new table or column, no Settings
  field. `cv.tex.jinja` and `tests/golden/base.rendered.tex` are unchanged.
