# 260930-lay — Selectable CV layout variants

**Status:** awaiting human review (spec gate — no wiring code until approved)
**Date:** 2026-09-30
**Design:** [./DESIGN.md](./DESIGN.md) (authored by des-4)
**Templates:** `app/latex/templates/cv-modern.tex.jinja` and `cv-compact.tex.jinja` already written by des-4 and currently **untracked**; they are the product of this task and must be committed with it.

## Goal

Let the user pick one of three committed CV layouts — Classic / Modern / Compact — as a single global preference, remembered across restarts and applied to the **next** tailored CV. Classic stays the default and its rendered bytes must not move.

## Locked decisions (user, 2026-09-30)

1. **Three layouts** = the existing `cv.tex.jinja` (Classic, untouched) + `cv-modern.tex.jinja` + `cv-compact.tex.jinja`.
2. **Storage:** a one-token file `layout` in the existing CV volume (`Settings.cv_dir`, default `/cv`), read and written by the `app/cv/` package, which is already documented as the only place that touches CV-volume user data (`cv.yaml`). **No new table, no Alembic revision, no Settings field.**
   - *Rejected:* adding a `cv_layout` key to `ranking_config.weights_json`. It is migration-free, but it stores a non-ranking value inside the ranking-weights document and forces both writers to merge-preserve each other's keys — a cross-concern invariant whose silent failure erases the other value (des-4 flagged precisely this). A file beside `cv.yaml` is smaller and decoupled.
3. **Fail closed:** missing file, unreadable file, unknown token, or an unresolvable template → `classic`. A bad preference must never break a render.
4. The choice affects **future renders only**; stored `cv_artifacts` are never re-rendered.
5. The picker lives inside the existing CV fact-store card in `app/web/templates/html/settings.html`.

## Tasks

### Task 1 — renderer takes an optional layout (tracer)

`app/latex/render.py`

- Add `DEFAULT_LAYOUT = "classic"` and `LAYOUTS: dict[str, str] = {"classic": "cv.tex.jinja", "modern": "cv-modern.tex.jinja", "compact": "cv-compact.tex.jinja"}`. Keep `TEMPLATE_NAME` (= the Classic filename) for existing importers.
- `render_plan_to_tex(plan, *, layout=DEFAULT_LAYOUT, env=None) -> str`; unknown/`None` resolves to Classic. No file IO and no clock/uuid in this module — the render path must stay pure (`tests/test_render_determinism.py`).
- `render_plan_to_tex(plan)` must still return today's exact bytes.

### Task 2 — preference store + pipeline wiring

- New `app/cv/layout.py`: `read_layout(cv_dir) -> str` (absent/garbage → `"classic"`) and `write_layout(cv_dir, layout) -> None` (validate against `render.LAYOUTS` keys; atomic write via temp file + `os.replace`; plain single-token file named `layout`). The module stays IO-only and imports the key set from `app.latex.render` — it must not perform rendering.
- `app/pipeline/tailor.py`: read the preference **once per compile** and pass `layout=` to **both** `render_plan_to_tex` call sites — the initial render (currently `:358`) and the page-trim re-render (currently `:393`) — so a trimmed document keeps the chosen layout.

### Task 3 — settings endpoint + control

- Settings route (wherever the existing settings POST handlers live, alongside reset/weights): `POST /settings/cv-layout` → validate the token against `LAYOUTS`, `write_layout`, redirect back with the existing settings-banner idiom. An invalid token writes nothing and the banner reports it.
- `app/web/templates/html/settings.html`: a plain `<form method="post" action="/settings/cv-layout">` with a `<select>` of the three keys and a "Save layout" button, inside `#cv-fact-store` directly after the upload form. Copy per DESIGN.md §4 (grounded, no marketing tone). No HTMX — this matches the reset and weights forms, and works with JavaScript off.

### Task 4 — tests and per-layout golden coverage

- `tests/latex/test_layouts.py` (new): each layout renders; two renders of the same plan are byte-identical; every expected fact appears; a hostile bullet is escaped; LF-only output; `render_plan_to_tex(plan)` equals the Classic bytes; unknown/`None`/absent layout equals the Classic bytes.
- Per-layout golden files under `tests/golden/` (`base.rendered.modern.tex`, `base.rendered.compact.tex`) pinned by a test, so a future template edit cannot drift silently. The existing Classic golden is untouched.
- `tests/cv/test_layout_store.py` (new): round-trip; missing file → Classic; garbage token → Classic; write rejects/strips an unknown token; atomic replace leaves no temp file behind.
- Pipeline/API tests: `compile_tailored` renders the chosen layout and the trim re-render keeps it; the settings POST sets the value and redirects; an invalid token writes nothing.
- `tests/db/test_migration_contract.py` and `tests/db/test_orm_drift.py` stay green (no schema change).

## Non-goals

- No Alembic revision (`0006` stays free); no new table, column, or Settings field.
- No new dependency, font, external asset, or shell-escape.
- Do not modify `cv.tex.jinja` or `tests/golden/base.rendered.tex`.
- No per-listing or per-artifact layout choice; no re-render of stored artifacts; no preview images.
- No change to `VERIFIER_VERSION`, the verification schema, or `cv_artifacts`.

## Verification

```
/workspace/job-search/.venv/bin/python -m pytest -q
/workspace/job-search/.venv/bin/python -m ruff check <changed files>
/workspace/job-search/.venv/bin/python -m ruff format --check <changed files>
git diff --name-only   # must NOT list cv.tex.jinja, tests/golden/base.rendered.tex, alembic/, or app/db/models.py
```

## Open items for the human reviewer

1. **Storage home** confirmed as `/cv/layout` (rejecting the `ranking_config` JSON key). Object now if you disagree.
2. **Compact is 10pt / 0.65in margins.** There is **no LaTeX engine in this environment**, so none of the three layouts has been compiled or eyeballed — only byte-rendered and unit-tested. Visual sign-off is deferred until an engine is available (the same `cv/base.tex` spike gap STATE already tracks). If you want to be conservative, say so and Compact becomes 11pt with density from spacing only.
3. **Scope:** the preference applies to future renders only.
4. **Per-layout golden files** are included above; say so if you would rather not pin them.
