# Phase 4: CV Fact Store + LaTeX Compile Spike - Context

**Gathered:** 2026-09-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 4 delivers the machine's canonical CV document and the proof that it can be
turned into a real PDF inside this container:

- `cv.yaml` as structured data with stable, enumerated IDs (CV-01)
- a bounded `.tex → cv.yaml` import path, proven on one macro-heavy section (CV-01)
- deterministic LaTeX rendering from that data, with user content escaped so it
  cannot break or corrupt the document (CV-04, CV-06)
- Tectonic compiling LaTeX to PDF offline in the image, with the LaTeX engine
  selectable as configuration and a working `Dockerfile.texlive` fallback (CV-05)
- a golden reproduction test proving the structured CV renders back to a
  fact-equivalent base CV (CV-03)
- `base.tex` treated as the human's canonical document, never modified by the
  tool (CV-02)
- `cv_versions` snapshots so a rendered artifact can name the revision it was
  built from

**Explicitly not this phase:** LLM ranking (Phase 5); the tailoring patch engine,
CV preview UI, and verification checks (Phase 6); cover letters; PDF/DOCX as an
*input* format; ATS-match optimisation. The LLM never emits LaTeX or prose for
the CV at any point (ARCHITECTURE.md AP2).

The phase runs in parallel with Phases 2–3 by design (ARCHITECTURE.md §14.3) and
exists to retire the project's largest unquantified cost as a *measurement*.

</domain>

<decisions>
## Implementation Decisions

### CV source & spike shape
- **D-58:** The repo commits a synthetic `.tex` fixture for tests; `cv/base.tex` and
  `cv/cv.yaml` are gitignored local files in the same class as `.env`. The spike
  runs against the real CV and writes the verdict. Tests stay hermetic and the
  real CV never enters git. `.gitignore` currently has no `cv/` entry and
  `compose.yml` mounts only `./data` — both change under this decision.
  — **Reversibility:** costly — the volume layout is what every later phase's
  paths and the health check are written against, and `compose.yml` plus
  `.gitignore` plus `app/config.py` all encode it.
- **D-59:** Import is a **bounded parser plus curation**. `app/cv/import_tex.py`
  parses the tractable subset (sections, entry macros, bullets) into a draft
  `cv.yaml` plus an unresolved-items report; a human curates the remainder. In
  this phase it is bounded to one section of the real document. ARCHITECTURE.md
  already names this file and calls it human-reviewed.
- **D-60:** The spike emits an executable script reporting counts (sections parsed,
  entries, unresolved macros, TeX packages requested) plus a written verdict at
  `docs/probes/2026-09-21-cv-tex-spike.md`, matching the Phase 1 scraper-probe
  precedent and re-runnable whenever the real CV changes.
- **D-61:** The committed fixture is an **awesome-cv-style stand-in** built from the
  package set a popular modern template relies on — `fontspec` with an OpenType
  font, `paracol`/`tabularx`, `enumitem`, `titlesec`, `hyperref`, `geometry` —
  plus its own `\newcommand` entry macros. Deliberately the macro-heavy case, so
  the measurement is conservative. No third-party template is vendored.
  The user has no `.tex` yet and confirmed a popular template may be assumed and
  extended later ("I don't have my .tex file yet, would it make sense to assume a
  template that's fairly popular? We can always extend the capabilities later
  right?").
- **D-62:** The verdict is a **partial verdict plus a trigger**. The probe doc
  states what the stand-in proves (bundle coverage for that package set, parser
  behaviour on macro-encoded structure) in a section clearly separated from an
  "UNRESOLVED — blocked on the real document" section naming the exact command to
  run. STATE.md blocking unknown #1 stays open and is rewritten to point at that
  trigger. Phase 4 ships; Phase 6 estimation proceeds knowing the measurement is
  outstanding.

### Fact store & ID scheme
- **D-63:** IDs are **hierarchical slug plus index** — `exp/acme-2021` for an entry,
  `bul/acme-2021/3` for a bullet. Readable in LLM prompts, diffs and logs, which
  matters because the Phase 6 patch is ID-based and the IDs appear in a prompt.
  The positional suffix is safe precisely because the fact store is frozen:
  reordering is a RenderPlan concern, not a `cv.yaml` edit.
  — **Reversibility:** costly — the ID strings are embedded in stored
  `structured_diff`/`patch_json` rows and in Phase 6 prompts; changing the format
  invalidates the audit trail of anything already rendered.
- **D-64:** IDs are **frozen at import; edits create new IDs**. An ID is assigned
  once and never reassigned; editing a bullet's text retires the old ID and
  introduces a new one, recorded as such. That keeps `cv_artifacts.structured_diff`
  a truthful audit trail and lets an old tailored PDF always be explained from the
  fact-store revision it was built against.
  — **Reversibility:** costly — undo means re-deriving IDs and rewriting the
  meaning of existing artifact rows.
- **D-65:** The phase adopts the researched **§7.3 `cv.yaml` shape as written** —
  `schema_version: 1`, meta (including `max_pages`), identity/contact, experience,
  education, skills, projects — and defines now the patch types CV-R4/R5/R6
  already commit to: `Suggestion`, `DropBullet`, `BulletWeight`. Extra sections
  (publications, awards, languages, certifications) were rejected as speculative.
  — **Reversibility:** costly — Phase 6 is written against these types;
  discovering an absent type later means a `schema_version` bump plus a Phase 6
  code change plus handling stored rows of the old version.
- **D-66:** `app/cv/factstore.py` is the single reader and validates with
  **Pydantic, failing loudly**: a malformed `cv.yaml` raises a path-qualified error
  naming the offending field, with no default-filling and no partial load. A
  missing date quietly supplied by a default is invented CV content, which the
  never-fabricate line forbids.
- **D-67:** Escaping is enforced **at the choke point**: the LaTeX Jinja
  `Environment` gets a `finalize` callback running `escape_tex` on every plain
  `str` output. Returning `markupsafe.Markup` is the explicit opt-out for a rare
  intentional LaTeX fragment. One line in the factory; no template discipline to
  remember and no template can bypass it. It composes with `autoescape=False` and
  `\VAR{}`/`\BLOCK{}` unchanged. Jinja `autoescape=True` was ruled out in advance —
  `markupsafe`/`html.escape` emits HTML entities (`&amp;`) and does not escape
  `%`, `_`, `#`, `$`, so it is wrong for TeX.

### Golden test mechanics
- **D-68:** The golden reproduction is **two tests with two failure classes**.
  `tests/golden/base.rendered.tex` is a byte-exact renderer regression — fully
  deterministic, needs no engine, so it runs in the default hermetic `pytest` pass
  under the existing `addopts="-m 'not live'"`. Separately, the fact-equivalence
  assertion extracts text from the two compiled PDFs, measuring the artefact a
  human and an ATS actually read (CV-R2). `render(cv.yaml)` and `base.tex` can
  never be byte-comparable — they are different templates by design — so the only
  meaningful comparison reduces both sides to extracted facts.
- **D-69:** The PDF half runs as a **marked lane inside the container**: its own
  pytest marker plus a skip-if-`tectonic`-absent guard, documented in the runbook.
  The real gate is `docker compose run --rm app pytest -m latex` inside the image
  where Tectonic lives — the same shape as D-53's committed-fixture +
  operator-run lane. No new CI infrastructure; the repo has none.
- **D-70:** PDF text assertions **normalise, then check membership**. Normalise
  first (collapse whitespace, fold ligature characters, join hyphenated
  line-breaks, unify dashes/quotes), then assert every org, title, date and each
  bullet's token-shingle is present on the other side. That catches real loss (a
  dropped bullet, a mangled date) while ignoring reflow, kerning spaces and
  extractor artefacts — CV-R2's "byte-equality is not required or expected" read
  literally. A fuzzy-ratio threshold was rejected because a high ratio over a long
  section can hide exactly the dropped bullet CV-R5 exists to catch.
- **D-71:** The renderer's LaTeX template is **committed in `app/latex/templates/`**
  as `.tex.jinja` application code, versioned with the renderer and changed only
  by a code change plus a golden-fixture update. `cv/` stays purely the human's
  data (`base.tex`, `cv.yaml`, both gitignored per D-58). Rendering therefore
  stays deterministic against a file in git and the golden test stays meaningful.
  **This is a deliberate correction to ARCHITECTURE.md's volume listing, which puts
  templates in `cv/`** — record it as a correction.
- **D-72:** The golden test **proves it can fail** by in-test mutation: after
  asserting equivalence against the correct fact store, the same test loads a deep
  copy, mutates one field (one bullet's text changed, one date shifted), renders
  it, and asserts the equivalence check *fails*. Self-contained, no extra
  committed artefact, and it proves the predicate discriminates rather than passing
  on empty input. A fact-count floor (at least N facts compared) rides along in
  the same test. Mirrors the existing vacuity guard in `tests/test_config.py`.

### Tectonic in image
- **D-73:** Tectonic arrives as a **pinned tarball plus checksum**: a build stage
  fetches `tectonic-0.17.0-x86_64-unknown-linux-musl.tar.gz`, verifies its SHA256
  in the same `RUN`, and unpacks to `/usr/local/bin`; `ARG TECTONIC_VERSION` and
  `ARG TECTONIC_SHA256` make the pin greppable. Mirrors the JobSpy SHA-assertion
  idiom already in the Dockerfile and must stay single-line shell (no heredocs) for
  the same classic-builder-fallback reason that assertion does. Static musl binary,
  so no runtime library dependencies.
- **D-74:** The package cache is primed by **compiling the fixture at image build**.
  A build-time `RUN` compiles the committed fixture through Tectonic so fetched
  packages land in an image layer; it doubles as a build-time proof the engine
  actually works — the same shape as the existing migration smoke ("Acceptance
  item 9"). The primed set is exactly the fixture's package set, which is why D-61
  and the D-62 trigger matter.
- **D-75:** A missing package **fails loudly with a documented rebuild**: compilation
  runs in Tectonic's cached-only mode (network disabled) so criterion 3's
  "offline" is literally true. **The exact flag name must be verified against
  `tectonic --help` at implementation time, not assumed.** The failure names the
  package and the fix — add it (or the priming document) to the build-time prime
  step and rebuild. Automatic fallback to the texlive image was rejected: the
  setting would silently override itself, so the engine actually used would stop
  matching the configuration.
- **D-76:** The engine seam is real and the fallback is **measured once**. A
  `LatexEngine` Protocol (`compile(*, tex, workdir) -> CompileResult`,
  failure-as-value) with `TectonicEngine` implemented and tested, selected through a
  DI factory next to `get_llm_backend` so tests can override it via
  `app.dependency_overrides`. `Dockerfile.texlive` is committed, the switch
  documented, **and the image is actually built once by hand with the fixture
  compiled through it, the result recorded in the verdict doc.** Cost: one slow
  multi-GB build, once. Gain: "fallback available" becomes a measured fact rather
  than a written intention.
  — **Reversibility:** costly — the DI seam and Protocol signature are what render,
  compile, the health check and every future caller bind to.

### CV revision persistence
- **D-77:** `cv.yaml` stays the human-editable machine canonical document, and
  **every accepted revision snapshots into `cv_versions`** through a new
  `app/db/repositories/cv_repo.py` (takes an `AsyncSession`, never commits — the
  caller owns the commit), inserting `facts_json`, `schema_version`, a `label`, a
  `source` of `import_tex` or `hand`, and `is_current=1` with the previous row's
  flag cleared. This gives `cv_artifacts.base_cv_version_id` a producer, makes
  "which revision was this PDF built against" answerable, and records file→DB
  drift instead of hiding it. Migration 0001 already ships both `cv_versions` and
  `cv_artifacts`; there is no repository for either table today. An import-only
  snapshot was rejected: once hand curation moves past it, the single row stops
  matching the file and `base_cv_version_id` is confidently wrong.
  — **Reversibility:** costly — revision semantics and the `is_current` protocol
  are inherited by Phase 6 artifact writes.

### the agent's Discretion
No area was delegated with an explicit "you decide". The following were left open
by the shape of the decisions above and are implementation detail, not
requirements to re-ask:

- the exact parser subset in `app/cv/import_tex.py` (which macros are tractable)
- the shape of the unresolved-items report
- the Tectonic cached-only flag name (verify against `tectonic --help`)
- fixture and template file names, and the `latex` setting names added to
  `app/config.py`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

ROADMAP.md carries **no `Canonical refs:` line for Phase 4** — the list below is
assembled from the research files, the roadmap's own text, and the codebase scout.

### Design contract — the structured-CV model and the LaTeX pipeline
- `.planning/research/ARCHITECTURE.md` §0 A1 — the two-canonical-documents
  resolution and the rule that "source of truth" never appears unqualified
- `.planning/research/ARCHITECTURE.md` §7 (lines 609–744) — **the Phase 4 design
  contract**: the three artefacts (`cv/base.tex` human, `cv/cv.yaml` machine,
  `artifacts/<id>/cv.tex` derived), bullet immutability, `schema_version: 1`, and
  §7.4's deterministic renderer that must not call `now()`
- `.planning/research/ARCHITECTURE.md` lines 737–744 — risk table CV-R1 … CV-R8
  (decomposition risk, reproduction drift, page reflow, reorder-becoming-rewrite,
  silent condensing, presentation inflation, pdfTeX-only primitives, base.tex
  staleness)
- `.planning/research/ARCHITECTURE.md` lines 103–106 — components **C9**
  `cv/factstore.py`, **C11** `latex/render.py`, **C12** `latex/compile.py`
- `.planning/research/ARCHITECTURE.md` lines 125–197 — project structure
  (`app/cv/import_tex.py`, `Dockerfile.texlive`, `cv/` and `artifacts/` volumes,
  `tests/golden/`, `tests/contract/`)
- `.planning/research/ARCHITECTURE.md` §10 (lines 1057–1062) — check 3 bullet
  conservation (fail) and check 8 page budget (warn), and the base-render identity
  patch as the CV-R2 regression guard
- `.planning/research/ARCHITECTURE.md` §14.3 — Phase 4 runs in parallel with
  Phases 2–3; Tectonic invocation via `asyncio.create_subprocess_exec` with no
  `-Z shell-escape`, temp-dir compile, primed cache, sanitised pdfTeX-only
  primitives
- `.planning/research/ARCHITECTURE.md` lines 1370–1371 — Open Questions #1 (does
  the real `.tex` decompose?) and #2 (Tectonic bundle coverage for the real
  preamble)
- `.planning/research/ARCHITECTURE.md` AP2 / AP12 — never let the LLM emit `.tex`
  or prose; never re-parse the compiled PDF

### Stack decisions that constrain the implementation
- `.planning/research/STACK.md` Q6 — Tectonic 0.17.0 vs TeX Live, the three
  Tectonic caveats, Jinja2 LaTeX-safe delimiters (`\VAR{}`/`\BLOCK{}`,
  `autoescape=False`), the mandatory `escape_tex` filter with backslash replaced
  first, and "model the CV as data, not as `.tex`"
- `.planning/research/STACK.md` "What NOT to Use" — Tectonic `-Z shell-escape`,
  runtime package downloads, default Jinja delimiters in `.tex`, unescaped
  interpolation, LLM-emitted `.tex`, `texlive-full` in the image
- `.planning/research/FEATURES.md` TS-11 / TS-12 and Gap 5 — structured CV fact
  store as the tailoring source; "the actual `.tex` is not available to research"
- `.planning/research/PITFALLS.md` M1 / M3 — schema-violation semantics, and
  blocking work wrapped in `asyncio.to_thread` (applies to Tectonic, per D-22)

### Requirements and phase constraints
- `.planning/REQUIREMENTS.md` CV-01 … CV-06 — the six requirements this phase
  closes, plus the Out-of-Scope rows (LLM emitting LaTeX; PDF/DOCX résumé parsing;
  ATS-match optimisation)
- `.planning/REQUIREMENTS.md` PLAT-04 — every limit, threshold and **the LaTeX
  engine** is configuration, not a hard-coded constant
- `.planning/PROJECT.md` — constraints (LaTeX canonical, Docker-local, privacy,
  no-auth-but-seam) and the "LaTeX as the CV source and tailoring target" key
  decision
- `.planning/STATE.md` Blockers/Concerns — **blocking unknown #1**: "the real
  `.tex` is not in this repo; `.tex → cv.yaml` import cost and Tectonic bundle
  coverage are unmeasured. Spike on one section is a hard gate before Phase 6 is
  estimated."

### Precedent to follow
- `docs/probes/2026-09-15-scraper-survival.md` — the Phase 1 probe + verdict doc
  shape being mirrored by D-60/D-62
- `docs/runbook-compose-smoke.md` and `docs/runbook-opencode-contract.md` — the
  operator-run lane documentation pattern D-69 extends
- `docs/implementation-notes.md` — running implementation notes

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/config.py` — the single `Settings` class where the LaTeX engine selector,
  Tectonic paths/timeouts and any page-budget knob must live (PLAT-04);
  `tests/test_config.py` AST-scans for hard-coded literals.
- `app/domain/sanitize.py` — the house template for `escape_tex`: pure, total,
  deterministic, config-free, with a frozen report type carrying counts only and
  an Apache-2.0 §4(c) attribution block for pattern-copied regexes.
- `app/web/template_env.py` — `make_templates(directory)` factory; the model for a
  second LaTeX-configured Jinja `Environment` factory with D-67's `finalize`.
- `app/api/health.py` — total-function `/health` returning `{status, db, opencode,
  sources}`; Phase 4 adds the `tectonic` key.
- `app/llm/base.py` + `get_llm_backend()` DI factory — the exact shape D-76's
  `LatexEngine` Protocol and factory copy, including the
  `app.dependency_overrides[get_latex_engine]` test override.
- `app/db/models.py` lines 359–402 — `cv_versions` and `cv_artifacts` already
  exist, including `ck_cv_artifacts_compile_status` on `('ok','failed','blocked')`.
- `Dockerfile` — the JobSpy SHA assertion and the build-time migration smoke are
  the two idioms D-73 and D-74 reuse; single-line shell only, no heredocs.
- `app/pipeline/run.py` — the single `run_pipeline()` callable and the
  `asyncio.to_thread` wrapping discipline Tectonic work must follow.
- `tests/test_config.py`, `tests/db/test_migration_contract.py`,
  `tests/test_import_discipline.py` — the vacuity/contract guard patterns D-72 and
  the module-purity rule extend.

### Established Patterns
- Port + adapter + DI factory + `app.dependency_overrides` test override.
- Repositories are the only place SQL lives; they take an `AsyncSession` and never
  commit — the caller owns the commit.
- `app.domain.*` is pure and must not import `httpx | sqlalchemy | jobspy | jinja2 |
  subprocess`; a renderer or fact store that needs pure text handling belongs in
  `domain`, while `app/latex/` and `app/cv/` carry the I/O.
- Every ceiling is a `Settings` field; failures are values, not exceptions, at
  boundaries; contract types use `extra="forbid"`.
- Migrations are one-way; `tests/db/test_migration_contract.py` asserts
  `alembic_version == ["0001"]` and a single head, so Phase 4 adds **no** migration
  — `cv_versions` is already there.
- Every load-bearing dependency gets a build-time proof (JobSpy SHA assertion,
  migration smoke) — this is the precedent for D-73/D-74.

### Integration Points
- `app/main.py` — wiring the new router/factory and the engine DI factory.
- `app/api/health.py` — add the `tectonic` reachability key.
- `app/pipeline/run.py` — Tectonic compiles are blocking; wrap per D-22.
- `compose.yml` — `./data:/data` is the only mount today; `cv/` and `artifacts/`
  volumes plus their env passthroughs must be added (`${VAR:-default}` mirroring
  `app/config.py`, or host-side overrides silently lose to in-code defaults).
- `.gitignore` — needs `cv/` and `artifacts/` so the real CV never enters git.
- `requirements.txt` / `pyproject.toml` — `pyyaml` and `pypdf` are both absent and
  are needed for `cv.yaml` loading and PDF text extraction; both files mirror each
  other exactly (D-17).
- `alembic/` — no new migration; `cv_versions` and `cv_artifacts` ship in 0001.
- `tests/` — no `tests/golden/` directory exists yet; D-68 creates it.

</code_context>

<specifics>
## Specific Ideas

- The user has no `.tex` yet. Assume a popular modern template's package set and
  extend later; do not wait on the real document, and do not let the stand-in
  pretend to answer bundle coverage for a document nobody has seen (D-61, D-62).
- Verdict doc path: `docs/probes/2026-09-21-cv-tex-spike.md`, mirroring
  `docs/probes/2026-09-15-scraper-survival.md`.
- The stand-in package set is named explicitly: `fontspec` (with an OpenType font),
  `paracol`/`tabularx`, `enumitem`, `titlesec`, `hyperref`, `geometry`, plus its own
  `\newcommand` entry macros.
- The container gate command is `docker compose run --rm app pytest -m latex`.
- The texlive fallback is proven by one hand-run build with the fixture compiled
  through it; the result goes in the verdict doc (D-76).
- "Settle criterion 4 now" — the user chose to resolve success criterion 4's
  unavoidably-partial nature immediately (D-62) rather than leaving it to the plan.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. No external spec, ADR or document was
referenced by the user; the canonical-ref list is entirely repo files.

</deferred>

---

*Phase: 4-CV Fact Store + LaTeX Compile Spike*
*Context gathered: 2026-09-21*
