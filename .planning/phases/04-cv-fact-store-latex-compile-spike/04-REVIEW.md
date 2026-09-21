---
phase: 04-cv-fact-store-latex-compile-spike
reviewed: 2026-09-21T15:41:13Z
depth: standard
files_reviewed: 47
files_reviewed_list:
  - .env.example
  - .gitattributes
  - .gitignore
  - Dockerfile
  - Dockerfile.texlive
  - app/api/health.py
  - app/config.py
  - app/cv/__init__.py
  - app/cv/factstore.py
  - app/cv/import_tex.py
  - app/db/repositories/cv_repo.py
  - app/domain/cv.py
  - app/domain/tex.py
  - app/latex/__init__.py
  - app/latex/base.py
  - app/latex/compile.py
  - app/latex/env.py
  - app/latex/render.py
  - app/latex/templates/cv.tex.jinja
  - compose.yml
  - pyproject.toml
  - requirements.txt
  - scripts/cv-tex-spike.sh
  - tests/api/test_health.py
  - tests/cv/__init__.py
  - tests/cv/test_factstore.py
  - tests/cv/test_import_tex.py
  - tests/db/test_cv_repo.py
  - tests/domain/test_cv_ids.py
  - tests/domain/test_tex_escape.py
  - tests/domain/test_tex_preamble.py
  - tests/fixtures/cv/awesomecv_standin.tex
  - tests/fixtures/cv/awesomecv_standin.yaml
  - tests/golden/__init__.py
  - tests/golden/base.rendered.tex
  - tests/golden/test_render_bytes.py
  - tests/latex/__init__.py
  - tests/latex/test_compile.py
  - tests/latex/test_fact_equivalence.py
  - tests/llm/test_contract_snapshot.py
  - tests/test_config.py
  - tests/test_cv_hygiene.py
  - tests/test_dependency_pins.py
  - tests/test_deploy_manifest.py
  - tests/test_import_discipline.py
  - tests/test_latex_engine_seam.py
  - tests/test_render_determinism.py
findings:
  critical: 0
  warning: 4
  info: 7
  total: 11
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-09-21T15:41:13Z
**Depth:** standard
**Files Reviewed:** 47
**Status:** issues_found

## Summary

Phase 04 builds the CV fact store, the deterministic LaTeX renderer, the
`LatexEngine` port with its Tectonic/TeX Live adapters, the PDF fact-equivalence
lane, the `cv_versions` revision log, and the bounded `.tex` importer. The
structural work is sound where it matters most: escaping really is centralised at
one Jinja `finalize` callback with no registered escape filter; the engine argv is
a fixed `list[str]` handed to `create_subprocess_exec` with no `shell=True`
anywhere; YAML goes through `safe_load` only; the fact-store validator rejects
unknown keys, duplicate IDs, unresolved `org_id`/`title_id` references and a
schema-version mismatch, path-qualified; and the golden renderer baseline is
committed and read with `read_bytes`, never written by its own test.

The defects below are in the seams the phase's own prose claims to have closed.
The strongest is `snapshot_version`'s SAVEPOINT discipline: the "current row"
clear runs *before* `begin_nested()`, so the documented invariant ("clears the
previous flag then inserts the new row inside one SAVEPOINT") does not hold, and a
failed insert leaves the table with zero current rows — reproduced below. The
importer silently collapses distinct employer/title names that slugify to the same
ID, which is exactly the class of fact corruption this phase exists to prevent.
Two hard-coded ceilings in `app/latex/compile.py` contradict 04-02's explicit
claim that every new ceiling is a Settings field.

Container-only claims (the real compile, the installed binary's flag names, the
TeX Live fallback) were already recorded as unverified/operator-run and are not
re-reported here. The hermetic suite is green: `281 passed` for the
domain/cv/golden/db-cv_repo subset run during this review.

## Warnings

### WR-01: `snapshot_version` clears the current-row flag *outside* the SAVEPOINT

**File:** `app/db/repositories/cv_repo.py:79-92`

**Issue:** The docstring (and the 04-04 SUMMARY's D3 claim) states the previous
current row's flag is cleared and the new row inserted **inside one SAVEPOINT**, so
a failure cannot leave the table without a current row. The implementation does
not do that:

```python
await session.execute(
    update(CvVersion).where(CvVersion.is_current.is_(True)).values(is_current=False)
)                                    # <-- runs in the OUTER transaction
row = CvVersion(...)
async with session.begin_nested():   # <-- SAVEPOINT starts here
    session.add(row)
    await session.flush()
```

SQLAlchemy emits `UPDATE cv_versions SET is_current=0 ...` **before**
`SAVEPOINT sa_savepoint_1` (verified with `echo=True`). The SAVEPOINT therefore
protects only the INSERT. Reproduced: seed one current row, force `flush()` to
raise inside the savepoint, catch the error and commit the caller's session — the
result is `current rows: 0 | total rows: 1`, with the previously-current row now
`is_current=False`. The savepoint's stated purpose ("a failure here cannot poison
the caller's outer transaction") is not met, and the "exactly one current row"
invariant is violated.

**Fix:** Move the flag clear inside the savepoint so both statements roll back
together:

```python
row = CvVersion(...)
async with session.begin_nested():
    await session.execute(
        update(CvVersion).where(CvVersion.is_current.is_(True)).values(is_current=False)
    )
    session.add(row)
    await session.flush()
```

Add a regression test that forces a flush failure and asserts the pre-existing
current row survives (the existing suite only exercises the happy path).

### WR-02: Distinct org/title names that slugify identically collapse silently

**File:** `app/cv/import_tex.py:275-280`, `app/cv/import_tex.py:395-401`, `app/cv/import_tex.py:498-499`

**Issue:** `_org_id` / `_title_id` derive the enumeration ID by `slugify(name)`,
and the draft is built from `orgs.setdefault(id, name)` / `titles.setdefault(...)`.
Two different names whose slugs collide therefore merge into one enumeration
entry, with the **first** name winning and the second silently discarded. The
report's `entry_id_collisions` only covers *entry* IDs (which are
name+year-derived), so the org/title collision is never reported. Reproduced:

```
\cvrole{Acme Ltd}{Engineer}{2020-01 -- 2021-01}
\cvrole{Acme-Ltd}{Manager}{2022-01 -- 2023-01}
-> orgs: [{'id': 'org.acme-ltd', 'name': 'Acme Ltd'}]
   entry org_ids: ['org.acme-ltd', 'org.acme-ltd']
   collisions reported: ()
```

Both entries render under "Acme Ltd". The fact store accepts this (the IDs are
unique), so nothing downstream catches it — a wrong employer can reach the
rendered CV, which is the fabrication class this phase is built to exclude.

**Fix:** Detect slug collisions while building the enumerations and report them
(reuse the `entry_id_collisions` pattern, or emit a `unresolved_macros`-style
entry), or make the ID collision-safe the way `qualify_entry_ids` already is
(e.g. suffix `-2`). At minimum, a colliding name must be loud rather than dropped.

### WR-03: Hard-coded probe timeout (and log-tail bound) in `app/latex/compile.py`

**File:** `app/latex/compile.py:48`, `app/latex/compile.py:50`

**Issue:** `_HEALTH_TIMEOUT_SECONDS = 5.0` is a compile-adjacent ceiling living as
a module constant. The 04-02 SUMMARY asserts "Every new ceiling is a Settings
field and the PLAT-04 absence scan covers `app/latex` and `app/cv`", and
`app/config.py` already has the exact analogue for the LLM lane
(`opencode_timeout_seconds: float = 5.0`). The absence scan cannot see this
literal: it walks `ast.Constant` ints and `5.0` is a float (and `5` is not in the
derived distinctive set anyway), so the guard passes vacuously for this value.
`_LOG_TAIL_CHARS = 4000` is the same class of unbounded-config constant. The
`--version` probe runs on every `/health` request, so this is an operator-tunable
budget in practice.

**Fix:** Add a `latex_probe_timeout_seconds: float = 5.0` (and, if the log tail is
to be tunable, `latex_log_tail_chars: int`) to `Settings`, thread it through
`_probe`, and extend the phase-four ceiling guards so a float ceiling is covered.
If these are deliberately constants, say so and drop the "every new ceiling is a
Settings field" claim.

### WR-04: `_flatten` strips escaped braces, leaving a dangling backslash

**File:** `app/cv/import_tex.py:222`

**Issue:** `_flatten` unwraps inline markup, then unconditionally removes every
remaining `{`/`}` (`value.replace("{", "").replace("}", "")`). `_ESCAPE_RE`
restores only `\% \& \_ \# \$`, so an escaped brace `\{`/`\}` loses its brace and
leaves a bare backslash. Reproduced: `_flatten(r"literal \{ and \} braces", 12)`
returns `'literal \\ and \\ braces'`. That backslash is later escaped by
`escape_tex` into `\textbackslash{}`, so the rendered bullet shows a spurious
backslash instead of the intended brace.

**Fix:** Consume escaped braces before the blanket strip, e.g. add `{` and `}` to
`_ESCAPE_RE`'s character class (`r"\\([%&_#$])"` -> `r"\\([%&_#${}])"`) so `\{`
becomes `{` and is then preserved, or handle the escape in the same pass as the
brace strip.

## Info

### IN-01: `sanitise_preamble` has no production caller

**File:** `app/domain/tex.py:208`

**Issue:** `sanitise_preamble` is only referenced by its own unit tests. Nothing in
the render or compile path calls it, so the pdfTeX-only primitives it exists to
neutralise are never actually commented out for a real document — the human
`.tex` fixture is compiled as-is in the fact-equivalence lane, and the renderer's
own template contains none of them. The capability reads as present but is not
wired.

**Fix:** Either call it on the document handed to `LatexEngine.compile` (and
surface `removed` in `CompileResult`/the run log), or record explicitly that the
wiring is deferred to Phase 6 so the phase's "sanitised" claim is not read as
active.

### IN-02: The importer's `meta: {}` makes a missing name/contact silent

**File:** `app/cv/import_tex.py:496`

**Issue:** The draft always carries `"meta": {}`. `Meta` defaults `name=None`,
`contact=None`, `max_pages=2`, so `load_facts` accepts a draft with no identity at
all — the template then renders no name and no contact block. This contradicts the
importer's stated principle that "a field the parser could not fill is absent and
loud, so the fact store fails loudly at that path": for `meta`, unresolved and
empty are indistinguishable.

**Fix:** Have the importer emit `meta` as an unresolved field (report it, or omit
the key and let validation fail), or extract name/contact, so a human cannot
accept a nameless CV by accident.

### IN-03: `is_current` is written but never read

**File:** `app/db/repositories/cv_repo.py:97-110`

**Issue:** `current_version` selects the newest row by `created_at`/`id` and never
filters on `is_current`, even though the write path spends an `UPDATE` per snapshot
maintaining that flag and the record type exposes it. The column is effectively
write-only, and the "exactly one current row" invariant has no reader enforcing or
depending on it (which is also why WR-01 is not yet user-visible).

**Fix:** Either filter the read on `is_current` (with the id tie-break as a
backstop), or document that the flag is an audit marker for Phase 6 and not the
read predicate.

### IN-04: The dependency guard does not enforce full manifest lockstep

**File:** `tests/test_dependency_pins.py:52-71`

**Issue:** The module docstring claims a `requirements.txt` that "falls out of
step with `pyproject.toml`" fails here, but `_declaration_misses` only checks the
three `PINNED_PACKAGES` rows. A dependency added to `[project].dependencies` and
omitted from `requirements.txt` (or vice versa) passes. The two manifests happen
to agree exactly today — same entries, same order, same JobSpy VCS ref — so D-17
holds; the guard just does not protect it.

**Fix:** Add one test comparing the normalised entry sets of
`[project].dependencies` and the non-comment `requirements.txt` lines.

### IN-05: `finalize` escapes `str` only — non-str values are a latent bypass

**File:** `app/latex/env.py:56-74`

**Issue:** The choke point returns non-`str` values unchanged; Jinja then applies
`str()` to them. The current template only interpolates `str` fields and iterates
lists, so there is no live bypass, but a future `\VAR{plan.contact_links}` (or any
list/dict field) would emit an unescaped Python repr containing literal `{`, `}`
and possibly `&`.

**Fix:** In `_latex_finalize`, `str()`-and-escape anything that is not `Markup` and
not already a `str`, or add a template guard test that rejects `\VAR{` on a
container field.

### IN-06: `line_statement_prefix = "%%"` collides with LaTeX `%%` comments

**File:** `app/latex/env.py:38`

**Issue:** `%%` is a common LaTeX comment style (section dividers). In this
environment it is the Jinja line-statement prefix, so a future template line
beginning with `%%` is parsed as Jinja code and raises a template syntax error.
The current template has no such line, so this is a latent authoring hazard rather
than a defect.

**Fix:** Document the constraint beside the delimiter table, or use a prefix that
cannot begin a LaTeX comment (e.g. `\BLOCK` for statements and reserve the line
prefix for something non-`%`).

### IN-07: Three phase-4 test files exist only as untracked working-tree files

**File:** `tests/test_cv_tex_spike_docs.py`, `tests/test_cv_tex_spike_script.py`, `tests/test_latex_lane_contract.py`

**Issue:** These three phase-4 control tests (04-05 verdict/runbook shape, the
`cv-tex-spike.sh` contract, and the D-69 collected-and-skipped lane guard) are
present on disk but untracked (`git status` shows `??`) — they are not in
`87124ea..HEAD` and not in the declared review scope. They pass
(`16 passed in 9.01s`), so they are real, working guards that the repository does
not carry: a clean clone or CI run loses them entirely. The 04-05 SUMMARY records
these checks as one-off shell assertions, so their permanent form was never
committed.

**Fix:** Commit the three files (they are hermetic and pass) or delete them if they
are superseded; leaving valid phase controls untracked means the phase's own
honesty guards silently stop existing on the next checkout.

---

_Reviewed: 2026-09-21T15:41:13Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
