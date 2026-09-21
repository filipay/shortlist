# Phase 4: CV Fact Store + LaTeX Compile Spike - Research

**Researched:** 2026-09-21
**Domain:** Structured CV fact store (YAML + stable IDs), Jinja2 LaTeX templating with an escaping choke point, Tectonic/TeX Live compilation inside a container, PDF text extraction for fact-equivalence
**Confidence:** MEDIUM-HIGH overall. HIGH on the Tectonic CLI surface (flag names, checksums, cache, bundle search) and on the Jinja2 `finalize` mechanism, both verified against the projects' own sources this session. MEDIUM on Tectonic symbolic-font-name resolution (two issue reports, no fix in the 0.17.0 changelog). LOW on the real `.tex` decomposition — unmeasurable by design (D-62).

## Summary

This phase has one job: convert the project's largest unquantified cost into a *measurement*, and in doing so land the machine-canonical CV document that Phases 5 and 6 both consume. The research resolves every mechanism the plan needs, and it surfaces one hard constraint the plan will break on day one if it misses it: **`app/latex/compile.py` cannot `import subprocess` today.**

The load-bearing findings, in order of planning impact:

1. **`tests/test_import_discipline.py` forbids `subprocess` outside `app/llm/`** — a global AST guard, not a scoped one. `TectonicEngine` needs `asyncio.create_subprocess_exec`. The guard must be widened deliberately (with its own "the exclusion is deliberate" mirror test, matching the existing `app/sources` httpx precedent), or the build fails on the first Tectonic task.
2. **Tectonic's cached-only flag is verified: `-C` / `--only-cached`**, documented as "Use only resource files cached locally" / "refuse to connect to the network when searching for support files". D-75 left the name open; it is now closed. The V1 CLI is still the **default** in 0.17.0 (`-Y` selects V1 explicitly, `-X` selects V2), so the plain `tectonic <file>.tex` form plus flags is correct.
3. **Tectonic resolves fonts by filename, not by symbolic name.** Two independent reports (maintainer answer in #372, open issue #1118) plus the absence of any fix entry in the 0.17.0 changelog. A fixture that says `\setmainfont{TeX Gyre Pagella}` is a coin-flip; one that says `\setmainfont{texgyrepagella}[Extension=.otf, UprightFont=*-regular, ...]` resolves in *both* Tectonic and the TeX Live fallback. This is the single highest-value fixture decision in the phase.
4. **The Jinja2 `finalize` choke point works exactly as D-67 assumes, for a reason worth stating:** with `autoescape=False`, Jinja's compiler emits `str(environment.finalize(<expr>))` for variable output (`.venv/lib/python3.14/site-packages/jinja2/compiler.py:1483-1487`), and literal template text **does not go through `finalize` at all** (`compiler.py:1470-1472`). So one `finalize` in the Environment factory escapes every interpolated value, and every literal LaTeX brace/percent in the template is left alone. The `Markup` opt-out is ours to implement (our own `finalize` decides), not a Jinja feature.
5. **`pypdf` is genuinely lossy in two ways that change the test predicate**: it does not expand ligatures by default, and it drops spaces (a long-standing, still-documented class of bug). D-70's "normalise, then check membership" is right, but "collapse whitespace" does not fix a *missing* space. The shingle comparison must run on a **space-stripped canonical form**, or a bullet that extracts as `SeniorEngineer` fails a bullet that reads `Senior Engineer`.
6. **`cv_versions.schema_version` is `String(32)` while `cv.yaml` says `schema_version: 1` (an int).** D-77's repository must store `str(...)`. Silent coercion here would make the drift check meaningless.

Everything else in the phase is conventional once those are settled: a Pydantic-validated fact store that fails loudly and path-qualified (D-66), a pure `escape_tex` behind the choke point (D-67), a two-test golden pair (D-68), an engine seam that copies `get_llm_backend` (D-76), and a `cv_versions` writer for a table that already exists (D-77). **No Alembic migration is added** — `cv_versions` and `cv_artifacts` ship in 0001 and the migration contract test currently asserts the head is `0003`.

**Primary recommendation:** Build the pure layer first (`app/domain/tex.py`, `app/domain/cv.py`), then the fact store and its two golden tests, then the engine seam and the container, and run the real-document spike last as a *documented partial verdict plus trigger* (D-62). Do not serialise the phase behind Phases 2–3, and do not let the spike's verdict claim bundle coverage for a document nobody has seen.

## Project Constraints (from AGENTS.md)

These are treated with the authority of locked decisions. Every item below was extracted from `/workspace/job-search/AGENTS.md` and verified against the code that enforces it.

| # | Directive | Enforced / evidenced by |
|---|-----------|--------------------------|
| P1 | **Python 3.13**, never 3.14 (wheel coverage for Playwright/curl_cffi/lxml) | `Dockerfile:25` — `FROM python:3.13-slim AS runtime`; `pyproject.toml:9` — `requires-python = ">=3.13"` |
| P2 | **`app/domain/*` must stay pure** — no `httpx`, `sqlalchemy`, `jobspy`, `jinja2`, `subprocess`, `fastapi` | `tests/test_import_discipline.py:14-16` (verbatim below) |
| P3 | **Every ceiling is a `Settings` field** (PLAT-04) | `app/config.py` is the single `Settings` class; `tests/test_config.py` AST-scans for hard-coded threshold literals in `SCANNED_DIRS = ("app/probe", "app/pipeline")` |
| P4 | **Repositories take an `AsyncSession` and never commit** — the caller owns the commit | `app/db/repositories/llm_call_repo.py:1-11` docstring; every function there |
| P5 | **Contract types use `extra="forbid"`** | `app/llm/base.py:36`, `app/llm/base.py:73`; `ProviderModel` docstring calls it "the redaction control" |
| P6 | **No new Alembic migration in this phase** — `cv_versions`/`cv_artifacts` ship in 0001 | `tests/db/test_migration_contract.py:295` asserts the recorded revision is exactly `["0003"]`; `test_alembic_at_latest_revision` rejects a second head |
| P7 | **`requirements.txt` and `pyproject.toml` mirror each other exactly** (D-17) | `requirements.txt:1-2` says so; `tests/test_dependency_pins.py` asserts a pin appears in both |
| P8 | **Failures are values, not exceptions, at boundaries** | `app/llm/base.py:105-124` (`health`/`discover_models`/`complete_structured` all "Never raises; failure is a value"); `app/api/health.py:44` (`/health` is "a total function") |
| P9 | **Every load-bearing dependency gets a build-time proof** | `Dockerfile:49-50` (JobSpy SHA assertion), `Dockerfile:63-64` (migration smoke) — the precedent D-73/D-74 reuse |
| P10 | **Dockerfile shell is single-line only, no heredocs** | `Dockerfile:45-48` explains: heredocs are BuildKit-only and `docker compose build` falls back to the classic builder |
| P11 | **Work happens through a GSD command** | `AGENTS.md` "GSD Workflow Enforcement" block |
| P12 | **No credential path anywhere; no CDN assets** | Phase 1 artefacts (`tests/test_no_credentials.py`, `tests/test_no_cdn.py`) |

**Project skills:** none. No `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` directory exists in the repo (verified by directory listing this session), so no project skill patterns constrain the plan.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

Copied verbatim from `04-CONTEXT.md` §`Implementation Decisions`. Research below respects these; where a decision left a mechanism open, this file closes it and says so.

**CV source & spike shape**

- **D-58:** The repo commits a synthetic `.tex` fixture for tests; `cv/base.tex` and `cv/cv.yaml` are gitignored local files in the same class as `.env`. The spike runs against the real CV and writes the verdict. Tests stay hermetic and the real CV never enters git. `.gitignore` currently has no `cv/` entry and `compose.yml` mounts only `./data` — both change under this decision.
  — **Reversibility:** costly — the volume layout is what every later phase's paths and the health check are written against, and `compose.yml` plus `.gitignore` plus `app/config.py` all encode it.
- **D-59:** Import is a **bounded parser plus curation**. `app/cv/import_tex.py` parses the tractable subset (sections, entry macros, bullets) into a draft `cv.yaml` plus an unresolved-items report; a human curates the remainder. In this phase it is bounded to one section of the real document. ARCHITECTURE.md already names this file and calls it human-reviewed.
- **D-60:** The spike emits an executable script reporting counts (sections parsed, entries, unresolved macros, TeX packages requested) plus a written verdict at `docs/probes/2026-09-21-cv-tex-spike.md`, matching the Phase 1 scraper-probe precedent and re-runnable whenever the real CV changes.
- **D-61:** The committed fixture is an **awesome-cv-style stand-in** built from the package set a popular modern template relies on — `fontspec` with an OpenType font, `paracol`/`tabularx`, `enumitem`, `titlesec`, `hyperref`, `geometry` — plus its own `\newcommand` entry macros. Deliberately the macro-heavy case, so the measurement is conservative. No third-party template is vendored. The user has no `.tex` yet and confirmed a popular template may be assumed and extended later ("I don't have my .tex file yet, would it make sense to assume a template that's fairly popular? We can always extend the capabilities later right?").
- **D-62:** The verdict is a **partial verdict plus a trigger**. The probe doc states what the stand-in proves (bundle coverage for that package set, parser behaviour on macro-encoded structure) in a section clearly separated from an "UNRESOLVED — blocked on the real document" section naming the exact command to run. STATE.md blocking unknown #1 stays open and is rewritten to point at that trigger. Phase 4 ships; Phase 6 estimation proceeds knowing the measurement is outstanding.

**Fact store & ID scheme**

- **D-63:** IDs are **hierarchical slug plus index** — `exp/acme-2021` for an entry, `bul/acme-2021/3` for a bullet. Readable in LLM prompts, diffs and logs, which matters because the Phase 6 patch is ID-based and the IDs appear in a prompt. The positional suffix is safe precisely because the fact store is frozen: reordering is a RenderPlan concern, not a `cv.yaml` edit.
  — **Reversibility:** costly — the ID strings are embedded in stored `structured_diff`/`patch_json` rows and in Phase 6 prompts; changing the format invalidates the audit trail of anything already rendered.
- **D-64:** IDs are **frozen at import; edits create new IDs**. An ID is assigned once and never reassigned; editing a bullet's text retires the old ID and introduces a new one, recorded as such. That keeps `cv_artifacts.structured_diff` a truthful audit trail and lets an old tailored PDF always be explained from the fact-store revision it was built against.
  — **Reversibility:** costly — undo means re-deriving IDs and rewriting the meaning of existing artifact rows.
- **D-65:** The phase adopts the researched **§7.3 `cv.yaml` shape as written** — `schema_version: 1`, meta (including `max_pages`), identity/contact, experience, education, skills, projects — and defines now the patch types CV-R4/R5/R6 already commit to: `Suggestion`, `DropBullet`, `BulletWeight`. Extra sections (publications, awards, languages, certifications) were rejected as speculative.
  — **Reversibility:** costly — Phase 6 is written against these types; discovering an absent type later means a `schema_version` bump plus a Phase 6 code change plus handling stored rows of the old version.
- **D-66:** `app/cv/factstore.py` is the single reader and validates with **Pydantic, failing loudly**: a malformed `cv.yaml` raises a path-qualified error naming the offending field, with no default-filling and no partial load. A missing date quietly supplied by a default is invented CV content, which the never-fabricate line forbids.
- **D-67:** Escaping is enforced **at the choke point**: the LaTeX Jinja `Environment` gets a `finalize` callback running `escape_tex` on every plain `str` output. Returning `markupsafe.Markup` is the explicit opt-out for a rare intentional LaTeX fragment. One line in the factory; no template discipline to remember and no template can bypass it. It composes with `autoescape=False` and `\VAR{}`/`\BLOCK{}` unchanged. Jinja `autoescape=True` was ruled out in advance — `markupsafe`/`html.escape` emits HTML entities (`&amp;`) and does not escape `%`, `_`, `#`, `$`, so it is wrong for TeX.

**Golden test mechanics**

- **D-68:** The golden reproduction is **two tests with two failure classes**. `tests/golden/base.rendered.tex` is a byte-exact renderer regression — fully deterministic, needs no engine, so it runs in the default hermetic `pytest` pass under the existing `addopts="-m 'not live'"`. Separately, the fact-equivalence assertion extracts text from the two compiled PDFs, measuring the artefact a human and an ATS actually read (CV-R2). `render(cv.yaml)` and `base.tex` can never be byte-comparable — they are different templates by design — so the only meaningful comparison reduces both sides to extracted facts.
- **D-69:** The PDF half runs as a **marked lane inside the container**: its own pytest marker plus a skip-if-`tectonic`-absent guard, documented in the runbook. The real gate is `docker compose run --rm app pytest -m latex` inside the image where Tectonic lives — the same shape as D-53's committed-fixture + operator-run lane. No new CI infrastructure; the repo has none.
- **D-70:** PDF text assertions **normalise, then check membership**. Normalise first (collapse whitespace, fold ligature characters, join hyphenated line-breaks, unify dashes/quotes), then assert every org, title, date and each bullet's token-shingle is present on the other side. That catches real loss (a dropped bullet, a mangled date) while ignoring reflow, kerning spaces and extractor artefacts — CV-R2's "byte-equality is not required or expected" read literally. A fuzzy-ratio threshold was rejected because a high ratio over a long section can hide exactly the dropped bullet CV-R5 exists to catch.
- **D-71:** The renderer's LaTeX template is **committed in `app/latex/templates/`** as `.tex.jinja` application code, versioned with the renderer and changed only by a code change plus a golden-fixture update. `cv/` stays purely the human's data (`base.tex`, `cv.yaml`, both gitignored per D-58). Rendering therefore stays deterministic against a file in git and the golden test stays meaningful. **This is a deliberate correction to ARCHITECTURE.md's volume listing, which puts templates in `cv/`** — record it as a correction.
- **D-72:** The golden test **proves it can fail** by in-test mutation: after asserting equivalence against the correct fact store, the same test loads a deep copy, mutates one field (one bullet's text changed, one date shifted), renders it, and asserts the equivalence check *fails*. Self-contained, no extra committed artefact, and it proves the predicate discriminates rather than passing on empty input. A fact-count floor (at least N facts compared) rides along in the same test. Mirrors the existing vacuity guard in `tests/test_config.py`.

**Tectonic in image**

- **D-73:** Tectonic arrives as a **pinned tarball plus checksum**: a build stage fetches `tectonic-0.17.0-x86_64-unknown-linux-musl.tar.gz`, verifies its SHA256 in the same `RUN`, and unpacks to `/usr/local/bin`; `ARG TECTONIC_VERSION` and `ARG TECTONIC_SHA256` make the pin greppable. Mirrors the JobSpy SHA-assertion idiom already in the Dockerfile and must stay single-line shell (no heredocs) for the same classic-builder-fallback reason that assertion does. Static musl binary, so no runtime library dependencies.
- **D-74:** The package cache is primed by **compiling the fixture at image build**. A build-time `RUN` compiles the committed fixture through Tectonic so fetched packages land in an image layer; it doubles as a build-time proof the engine actually works — the same shape as the existing migration smoke ("Acceptance item 9"). The primed set is exactly the fixture's package set, which is why D-61 and the D-62 trigger matter.
- **D-75:** A missing package **fails loudly with a documented rebuild**: compilation runs in Tectonic's cached-only mode (network disabled) so criterion 3's "offline" is literally true. **The exact flag name must be verified against `tectonic --help` at implementation time, not assumed.** The failure names the package and the fix — add it (or the priming document) to the build-time prime step and rebuild. Automatic fallback to the texlive image was rejected: the setting would silently override itself, so the engine actually used would stop matching the configuration.
- **D-76:** The engine seam is real and the fallback is **measured once**. A `LatexEngine` Protocol (`compile(*, tex, workdir) -> CompileResult`, failure-as-value) with `TectonicEngine` implemented and tested, selected through a DI factory next to `get_llm_backend` so tests can override it via `app.dependency_overrides`. `Dockerfile.texlive` is committed, the switch documented, **and the image is actually built once by hand with the fixture compiled through it, the result recorded in the verdict doc.** Cost: one slow multi-GB build, once. Gain: "fallback available" becomes a measured fact rather than a written intention.
  — **Reversibility:** costly — the DI seam and Protocol signature are what render, compile, the health check and every future caller bind to.

**CV revision persistence**

- **D-77:** `cv.yaml` stays the human-editable machine canonical document, and **every accepted revision snapshots into `cv_versions`** through a new `app/db/repositories/cv_repo.py` (takes an `AsyncSession`, never commits — the caller owns the commit), inserting `facts_json`, `schema_version`, a `label`, a `source` of `import_tex` or `hand`, and `is_current=1` with the previous row's flag cleared. This gives `cv_artifacts.base_cv_version_id` a producer, makes "which revision was this PDF built against" answerable, and records file→DB drift instead of hiding it. Migration 0001 already ships both `cv_versions` and `cv_artifacts`; there is no repository for either table today. An import-only snapshot was rejected: once hand curation moves past it, the single row stops matching the file and `base_cv_version_id` is confidently wrong.
  — **Reversibility:** costly — revision semantics and the `is_current` protocol are inherited by Phase 6 artifact writes.

### the agent's Discretion

Copied verbatim from `04-CONTEXT.md` §`the agent's Discretion`:

> No area was delegated with an explicit "you decide". The following were left open by the shape of the decisions above and are implementation detail, not requirements to re-ask:
>
> - the exact parser subset in `app/cv/import_tex.py` (which macros are tractable)
> - the shape of the unresolved-items report
> - the Tectonic cached-only flag name (verify against `tectonic --help`)
> - fixture and template file names, and the `latex` setting names added to `app/config.py`

### Deferred Ideas (OUT OF SCOPE)

Copied verbatim from `04-CONTEXT.md` §`Deferred Ideas`:

> None — discussion stayed within phase scope. No external spec, ADR or document was referenced by the user; the canonical-ref list is entirely repo files.

Also explicitly out of scope per `04-CONTEXT.md` §`Phase Boundary`: LLM ranking (Phase 5); the tailoring patch engine, CV preview UI, and verification checks (Phase 6); cover letters; PDF/DOCX as an *input* format; ATS-match optimisation. The LLM never emits LaTeX or prose for the CV (ARCHITECTURE.md AP2). Publications/awards/languages/certifications sections were rejected as speculative (D-65).

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CV-01 | The CV is modelled as structured data with stable, enumerated IDs | §Standard Stack (`pydantic`, `pyyaml`), §Architecture Patterns P1 (fact store) and P2 (ID derivation), §Common Pitfalls 6 (`schema_version` type mismatch) and 7 (ID freezing), §Code Examples (`CvFacts` skeleton, `derive_entry_id`) |
| CV-02 | The human-authored LaTeX CV stays canonical and is never modified by the tool | §Architecture Patterns P1 (three-artefact rule; `base.tex` opened read-only), §Validation Architecture (a byte-hash-before/after test + a `.gitignore` guard), §Common Pitfalls 11 (`base.tex` staleness is a Phase 6+ concern, not a Phase 4 write) |
| CV-03 | A golden reproduction test proves the structured CV renders back to a fact-equivalent base CV | §Architecture Patterns P6 (two-test golden pair, in-test mutation negative control, fact-count floor), §Common Pitfalls 8 (pypdf whitespace loss breaks the naive predicate), §Code Examples (`normalise_for_compare`, `facts_present_in`) |
| CV-04 | The system renders LaTeX deterministically from structured data | §Architecture Patterns P5 (determinism rules; `auto_reload=False`, LF-only writes, no clock), §Common Pitfalls 9 (nondeterminism sources), §Validation Architecture (render-twice identity + AST clock scan) |
| CV-05 | The system compiles LaTeX to PDF inside the container | Findings 2/3 of §Summary, §Standard Stack (Tectonic 0.17.0 pinned tarball + verified SHA256), §Architecture Patterns P7 (engine seam + `subprocess` guard widening), §Common Pitfalls 1 (offline flag), 2 (cache priming), 4 (fonts), 5 (`subprocess` import guard) |
| CV-06 | User content is escaped so it cannot break or corrupt the LaTeX document | Finding 4 of §Summary, §Architecture Patterns P4 (the `finalize` choke point), §Code Examples (`escape_tex`, `_latex_finalize`), §Common Pitfalls 3 (escaping is not the same job as `--untrusted`) |
| PLAT-04 | Limits, thresholds, and the LaTeX engine are configuration, not hard-coded constants | §Architecture Patterns P8 (the new `Settings` fields and the guards that must be extended to see them) |

</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `cv.yaml` parse + validate | Filesystem / local data (`app/cv/factstore.py`) | Domain schema (`app/domain/cv.py`) | The file is local data, so the I/O sits in `app/cv/`; the types and invariants are pure and live in `app/domain/` so they can be tested with no filesystem. |
| Stable-ID derivation + enumeration | Domain (pure) | — | IDs are a property of the data, not of storage; a pure function is what makes D-64's "frozen at import" testable. |
| User-content escaping (`escape_tex`) | Domain (pure) | Renderer choke point | `app/domain/sanitize.py` is the house precedent for a pure, total, config-free escaper; `app/latex/env.py` is where it is *enforced*. |
| LaTeX emission from a `RenderPlan` | API/Backend (`app/latex/render.py`) | Domain (`RenderPlan`) | Filesystem output is I/O, so it belongs in `app/latex/`; the plan it consumes is pure. `jinja2` is forbidden in `app/domain/`. |
| PDF compilation | API/Backend (`app/latex/compile.py`, subprocess) | — | Process spawn is I/O. It must be the *only* new subprocess site and must be registered as such. |
| PDF text extraction + fact equivalence | API/Backend (I/O) + Domain (predicate) | — | `pypdf` is I/O (extraction in `app/latex/` or a test helper); the equivalence predicate is pure and belongs in `app/domain/` for hermetic unit testing. |
| Preamble sanitisation (pdfTeX-only primitives) | Domain (pure text transform) | Compiler | Pure string work with no engine dependency, so it is unit-testable without Tectonic. |
| `cv_versions` revision snapshot | Database / Storage (`app/db/repositories/cv_repo.py`) | — | All SQL lives in repositories; the session/commit ownership rule is a DB-tier concern. |
| Engine selection (`tectonic` vs `texlive`) | Configuration (`app/config.py`) + DI factory | — | PLAT-04 makes the engine a setting; the factory is the seam tests override. |
| Engine reachability in `/health` | API/Backend (`app/api/health.py`) | — | Mirrors the existing `opencode` key, including the "reported never raised" totality rule. |
| Import from `.tex` (bounded parser) | API/Backend (`app/cv/import_tex.py`) | Domain (pure tokenising helpers) | One-off, human-reviewed file→file transform; the tokeniser itself can be pure and unit-tested over fixtures. |

</phase_requirements>

## Standard Stack

### Core

| Library / Tool | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| **Tectonic** | **0.17.0** (released 2026-07-27) | LaTeX → PDF | Already the STACK.md Q6 choice: ~124 MB vs ~4.2 GB for `texlive-full`, auto-reruns to convergence, auto-fetches packages, single static binary, XeTeX-derived so `fontspec`/OpenType works. Installed as a **pinned tarball + SHA256**, not via apt. |
| **`pypdf`** [WARNING: flagged as suspicious — verify before using.] | **6.19.0** (latest on PyPI at research time; STACK.md recorded 6.18.1) | PDF page count + text extraction | The STACK.md Q6 choice for the anti-fabrication assertion step and CV-R3's `page_count`. Pure Python, no native extension, BSD-3-Clause, `requires_python >=3.9`. The package-legitimacy seam rates it `SUS` (see audit below). |
| **`pyyaml`** [WARNING: flagged as suspicious — verify before using.] | **6.0.3** | Loading `cv.yaml` | Already installed as a **dev** dependency (`pyproject.toml:43`) and already pinned in both manifest files; this phase **promotes it to a runtime** dependency. There is no stdlib YAML. Use `yaml.safe_load` only. |
| **`pydantic`** | **2.13.5** (already a runtime dep) | CV schema validation (D-66) | The project's existing validation boundary. `ValidationError.errors()` yields `loc` tuples, which is exactly what D-66's path-qualified error needs. `extra="forbid"` is the house rule (P5). |
| **`jinja2`** | **3.1.6** (already a runtime dep) | `.tex` emission | STACK.md Q6's LaTeX-safe-delimiter environment. Already installed; **must not be imported from `app/domain/`** (P2). |

### Supporting

| Library / Tool | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| **`markupsafe`** | pulled in by `jinja2` (transitively present) | The `Markup` opt-out for D-67 | Only where a template must emit an intentional LaTeX fragment. It is a `str` subclass, so `str()`-ing it is a no-op — which is why the opt-out works. |
| **`hashlib`** (stdlib) | — | `tex_hash` / `pdf_hash` on artefacts; byte-equality checks in tests | No crypto library; sha256 for identity, never for secrets. Never hand-roll. |
| **`unicodedata`** (stdlib) | — | NFKC folding in the PDF comparison normaliser (CV-03) | The ligature/whitespace fold D-70 requires. |
| **`asyncio`** (stdlib) | — | `asyncio.create_subprocess_exec` + `asyncio.to_thread` for the compile | D-76's Protocol and Pitfall M3 (never block the event loop). |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-written bounded `.tex` parser (D-59) | **TexSoup 0.3.3** (BSD-3-Clause, released 2026-04-05, ~325★) — a fault-tolerant Python LaTeX parse tree with `find_all`/`soup.section` traversal; its own benchmark claims 50/50 arXiv papers parsed where plasTeX managed 11/50 and LaTeXML 29/50 | Attractive, but it is a new dependency for a **one-off, human-reviewed** import path that Phase 6 never runs again. It also parses *valid* LaTeX as a soup, not *structure*: the tractable trick this phase needs (read `\newcommand` arity, then treat call sites as records) is app-specific. Recommend the bounded parser now, and record TexSoup as the documented escalation if the real `.tex` defeats it. Do not install it speculatively. |
| `escape_tex` in `app/domain/tex.py` | `jinja2`'s `autoescape` + a custom `escape` | Ruled out by D-67 and for the documented reason: `markupsafe.escape` emits HTML entities (`&amp;`) and never touches `%`, `_`, `#`, `$`. |
| A `LatexEngine` Protocol + two thin classes (D-76) | Calling `tectonic` directly from `app/latex/compile.py` | The Protocol is what makes `app.dependency_overrides[get_latex_engine]` possible in the default hermetic lane, and what makes `LATEX_ENGINE=texlive` a config change rather than a code change (PLAT-04). Copy `get_llm_backend`, do not invent. |
| `tectonic --only-cached` at runtime | Letting Tectonic fetch on demand at runtime | STACK.md Q6 caveat 1 and D-75: a container that needs the internet to compile a CV on the user's laptop is a defect. Prime at build, refuse the network at runtime. |
| `TectonicEngine` only | `TectonicEngine` + `TexLiveEngine` | D-76 names only `TectonicEngine` as implemented-and-tested. But criterion 3 says "the engine selectable as configuration" — a setting that can only ever hold one value is not a setting. **Recommend a ~15-line `TexLiveEngine`** that is the same subprocess wrapper with `xelatex -interaction=nonstopmode -halt-on-error` argv (see Pitfall 10 for why `xelatex` and not `pdflatex`). |

### Version verification

```bash
# Tectonic: verified from the project's own GitHub Releases API this session
#   tag        tectonic@0.17.0
#   published  2026-07-27T01:00:41Z
#   asset      tectonic-0.17.0-x86_64-unknown-linux-musl.tar.gz  (10,151,914 bytes)
#              sha256=8533d07f9ccbd7a65824b9e0459041bca34af1eb33daba48f59215593753a3b7
#   (aarch64 variant also published: b10954a95404f3ab2328d2fa59a5ebab8e657f893fab096f98be8db7c0c979b8)

# pypdf: PyPI JSON API, this session
#   latest = 6.19.0        requires_python = >=3.9        license = BSD-3-Clause
#   source = https://github.com/py-pdf/pypdf

# pyyaml: already present in the project's own manifests
grep -n pyyaml requirements.txt pyproject.toml

# Sanity: the pins below must appear in BOTH manifest files (D-17)
grep -n "pypdf==" requirements.txt pyproject.toml
grep -n "pyyaml==" requirements.txt pyproject.toml
```

**The Tectonic pin is `ARG`-based and greppable (D-73), and its SHA256 is verified above from the project's own release metadata — this is the exact value to put in `ARG TECTONIC_SHA256`.** Do not substitute a "latest" URL or a floating tag.

### Installation

No `pip install` is needed for Tectonic (standalone binary). Python additions, both files, exact pins only (D-17 / P7):

```bash
# requirements.txt — runtime
pypdf==6.19.0
pyyaml==6.0.3
```

```toml
# pyproject.toml — [project].dependencies (move pyyaml up from [project.optional-dependencies].dev;
# it must not appear twice)
"pypdf==6.19.0",
"pyyaml==6.0.3",
```

`pyyaml` is currently dev-only (`pyproject.toml:43`). Promoting it means **removing** the dev-list entry rather than duplicating it, and `requirements.txt` must gain the same line (it currently is absent there — verified: `requirements.txt` has no `pyyaml` line).

## Package Legitimacy Audit

Ran `query package-legitimacy check --ecosystem pypi pypdf pyyaml` this session. Result — both `SUS`:

| Package | Registry | Published (latest) | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|--------------------|-----------|-------------|---------|-------------|
| `pypdf` | PyPI | 2026-09-16 | unknown (not reported) | https://github.com/py-pdf/pypdf | **SUS** | Flagged — planner must add `checkpoint:human-verify` before install |
| `pyyaml` | PyPI | 2025-09-25 | unknown (not reported) | https://pyyaml.org/ | **SUS** | Flagged — planner must add `checkpoint:human-verify` before install |

**Interpreting these verdicts honestly.** Both `SUS` verdicts rest on the seam's heuristic signals (`too-new`, `unknown-downloads`), not on any evidence of slopsquatting or malice:

- `pypdf`'s `too-new` signal is triggered by the **latest release's** publish date (2026-09-16, five days before this research). The project itself is long-lived (`py-pdf/pypdf`, versions back to 3.x in 2023 — visible in the same PyPI payload), its docs are versioned (3.12, 4.0, 5.4, 6.14 read this session), and it is the package STACK.md Q6 already selected. The heuristic cannot distinguish "a mature project that shipped yesterday" from "a slopsquatted name".
- `pyyaml` is already installed in this repo's dev environment (`pyyaml-6.0.3.dist-info` present in `.venv/lib/python3.14/site-packages/`, verified by listing this session) and already pinned in `pyproject.toml:43`. It is a *promotion*, not a new dependency.

**Both are tagged `[WARNING: flagged as suspicious — verify before using.]` inline in the Standard Stack table above, and the planner must insert a `checkpoint:human-verify` task immediately before the manifest edit.** The checkpoint is cheap: confirm the two names and versions on PyPI and confirm the resolved versions import. This mirrors the existing `tests/test_dependency_pins.py` precedent, which documents that `rapidfuzz` also returned `SUS` (`too-new`, `unknown-downloads`) and was cleared by a blocking human checkpoint before install. **Recommend extending that test's pattern** with a `pypdf`/`pyyaml` counterpart rather than minting a new file.

**Packages removed due to `SLOP` verdict:** none.
**Packages flagged as suspicious `[SUS]`:** `pypdf`, `pyyaml` — planner inserts `checkpoint:human-verify` before each manifest edit.

*Install ordering note:* pin the versions resolved at implementation time. `pypdf` releases frequently (6.18.1 → 6.19.0 within the STACK.md→research window); the pin must be the version the checkpoint actually confirmed, not the value copied from this document.

## Architecture Patterns

### System Architecture Diagram

```
  OPERATOR / SPIKE                                    RUNTIME (every render+compile)
  ─────────────────                                   ─────────────────────────────
  cv/base.tex  (human, gitignored)                      cv/cv.yaml  (machine, gitignored)
        │  read-only, never written by the tool                     │
        │                                                           │
        │  ┌────────────────────────────────────────────────────────┘
        │  │
        ▼  ▼
   ┌───────────────────────────┐        ┌──────────────────────────────────────┐
   │ app/cv/import_tex.py      │        │ app/cv/factstore.py                  │
   │  bounded parser +         │        │  yaml.safe_load → CvFacts            │
   │  unresolved-items report  │───────▶│  Pydantic, extra="forbid",           │
   │  (D-59, D-60)             │ draft  │  FAIL LOUDLY, path-qualified (D-66)  │
   └───────────────────────────┘  yaml  └───────────────┬──────────────────────┘
                                                        │ CvFacts (frozen, IDs)
                                                        │ + schema_version assert
                     human curation ◀───────────────────┘
                                                        │
                          ┌─────────────────────────────┼──────────────────────────────┐
                          │                             ▼                              │
                          │              ┌──────────────────────────────┐               │
                          │              │ app/domain/cv.py   (PURE)    │               │
                          │              │  apply_patch(facts, patch)   │               │
                          │              │    -> RenderPlan             │               │
                          │              │  identity patch for base     │               │
                          │              └──────────────┬───────────────┘               │
                          │                             │ RenderPlan                    │
                          │                             ▼                               │
                          │              ┌──────────────────────────────┐               │
                          │              │ app/latex/env.py  (PURE+J2)  │               │
                          │              │  Environment(\VAR{}\BLOCK{}) │               │
                          │              │  finalize = _latex_finalize  │◀── escape_tex │
                          │              │      └─ escape_tex(str)      │    (PURE,     │
                          │              │      └─ Markup passthrough   │     domain)   │
                          │              └──────────────┬───────────────┘               │
                          │                             │                               │
                          │                             ▼                               │
                          │              ┌──────────────────────────────┐               │
                          │              │ app/latex/render.py          │               │
                          │              │  deterministic .tex bytes    │               │
                          │              │  NO clock, NO random, LF    │               │
                          │              └──────────────┬───────────────┘               │
                          │                             │ .tex                          │
                          │                             ▼                               │
                          │   ┌──────────────────────────────────────────────────┐       │
                          │   │ app/domain/tex.py (PURE)  sanitise_preamble()     │       │
                          │   │  comment out \pdf* pdfTeX-only primitives (CV-R7)│       │
                          │   └──────────────────────┬───────────────────────────┘       │
                          │                          │ .tex (sanitised)                  │
                          │                          ▼                                  │
                          │   ┌──────────────────────────────────────────────────┐       │
                          │   │ app/latex/compile.py    LatexEngine Protocol      │       │
                          │   │  TectonicEngine  ──▶ asyncio.create_subprocess_exec│      │
                          │   │    tectonic --only-cached --untrusted ...         │       │
                          │   │    stage in temp dir → compile → copy out         │       │
                          │   │  TexLiveEngine   ──▶ xelatex -interaction=...     │       │
                          │   │  failure is a VALUE (CompileResult), never raises │       │
                          │   └──────────────────────┬───────────────────────────┘       │
                          │                          │ PDF / compile_log / page_count    │
                          │                          ▼                                  │
                          │   ┌──────────────────────────────────────────────────┐       │
                          │   │ app/latex/verify.py  (Phase 6 owns; Phase 4 only  │       │
                          │   │  ships the shared text-normaliser + predicate)    │       │
                          │   └──────────────────────┬───────────────────────────┘       │
                          │                          │ VerificationResult                │
                          ▼                          ▼                                  │
   ┌────────────────────────────────────────────────────────────────┐                 │
   │ app/db/repositories/cv_repo.py   (AsyncSession, NEVER commits)  │                 │
   │   snapshot_version(facts_json, schema_version=str(1), label,     │                 │
   │                    source='import_tex'|'hand')                  │                 │
   │     └─ clear previous is_current, insert new is_current=True     │                 │
   └───────────────────────────┬────────────────────────────────────┘                 │
                               ▼                                                       │
                     cv_versions  (migration 0001 — already exists)                    │
                               ▲                                                       │
                     cv_artifacts.base_cv_version_id  ◀───────────────────────────────┘
                              (Phase 6 writes the artifact row)

  Container build (image-build only):
   stage assets ─┐
                 ├─▶ runtime: install Tectonic tarball (ARG+sha256) ─▶ PRIME CACHE
                 │     (compile the committed fixture WITH network, once)
                 └─▶ runtime: RUN alembic upgrade head  (existing smoke, unchanged)
                       └─▶ after this layer, `--only-cached` is provably offline-capable

  /health  ── reports { tectonic: {available, version, error} }  (reported, never raised)
```

### Recommended Project Structure

Only the new and changed paths; everything else stands.

```
job-search/
├── Dockerfile                       # + Tectonic ARG/ARG_SHA256 install RUN, + cache-prime RUN
├── Dockerfile.texlive               # NEW: curated TeX Live subset fallback (D-76)
├── .gitignore                       # + cv/  + artifacts/          (D-58)
├── .gitattributes                   # NEW (recommended): pin tests/golden/*.tex and app/latex/templates/*.tex to LF
├── compose.yml                      # + ./cv:/cv + ./artifacts:/artifacts volumes and env passthroughs
├── requirements.txt / pyproject.toml# + pypdf, pyyaml (runtime); move pyyaml out of [dev]
├── app/
│   ├── config.py                    # + the latex_* and cv_* Settings fields (PLAT-04)
│   ├── api/health.py                # + the `tectonic` key
│   ├── cv/
│   │   ├── __init__.py              # NEW
│   │   ├── factstore.py             # C9: load + validate + enumerate (D-66)
│   │   └── import_tex.py            # one-off bounded .tex → cv.yaml + report (D-59, D-60)
│   ├── domain/                      # PURE — no jinja2, no yaml, no subprocess
│   │   ├── cv.py                    # C10: CvFacts types, ID invariants, apply_patch, RenderPlan
│   │   └── tex.py                   # NEW: escape_tex, sanitise_preamble, normalise_for_compare
│   ├── latex/
│   │   ├── __init__.py              # NEW: LatexEngine Protocol re-export + get_latex_engine()
│   │   ├── env.py                   # C11: the LaTeX Jinja Environment factory + _latex_finalize
│   │   ├── render.py                # C11: RenderPlan → deterministic .tex bytes
│   │   ├── compile.py               # C12: TectonicEngine / TexLiveEngine, CompileResult
│   │   ├── base.py                  # NEW: LatexEngine Protocol + CompileResult (mirrors app/llm/base.py)
│   │   └── templates/
│   │       └── cv.tex.jinja         # D-71: application code, not cv/ data
│   └── db/repositories/
│       └── cv_repo.py               # D-77: cv_versions writer/reader (never commits)
├── cv/                              # gitignored volume: base.tex, cv.yaml  (D-58)
├── artifacts/                       # gitignored volume: <id>/cv.tex, <id>/cv.pdf
├── docs/probes/2026-09-21-cv-tex-spike.md   # the verdict (D-60, D-62)
├── docs/runbook-latex-compile.md    # NEW: the `-m latex` lane + the texlive switch
├── scripts/cv-tex-spike.sh          # NEW: the executable spike (D-60)
└── tests/
    ├── fixtures/cv/
    │   ├── awesomecv_standin.tex    # D-61: the committed synthetic fixture
    │   └── awesomecv_standin.yaml   # its hand-curated fact store (the other side of golden)
    ├── golden/
    │   ├── base.rendered.tex        # D-68: byte-exact renderer regression (committed)
    │   └── test_render_bytes.py     # default lane, no engine
    ├── latex/                       # NEW: the `latex`-marked lane
    │   ├── test_compile.py          # compiles the fixture, asserts PDF + page_count
    │   └── test_fact_equivalence.py # D-68/D-70/D-72: the PDF half + mutation control
    ├── domain/
    │   ├── test_tex_escape.py       # CV-06
    │   ├── test_tex_preamble.py     # CV-R7
    │   └── test_cv_ids.py           # CV-01 / D-63 / D-64
    └── cv/
        ├── test_factstore.py        # CV-01 / D-66
        └── test_import_tex.py       # D-59 over the fixture
```

### Pattern P1: Three artefacts, one canonical document each (ARCHITECTURE §7.1)

**What:** `cv/base.tex` is canonical *for the human* and is never opened for writing by any code path. `cv/cv.yaml` is canonical *for the machine* (the patch engine addresses it). `artifacts/<id>/cv.tex` is a rendered derivative that is never edited. "Source of truth" is never used unqualified (ARCHITECTURE §0 A1).
**When to use:** Always, in this phase and the next three.
**Enforcement that actually bites (CV-02):** open `base.tex` with `Path.read_text(encoding="utf-8")` only; assert the "never modified" property with a test that hashes the file before and after a full import+render+snapshot cycle. Do not rely on discipline.

### Pattern P2: Stable IDs are derived deterministically, and never reassigned (D-63, D-64)

**What:** An entry ID is `exp/<slug>-<start-year>`; a bullet ID is `bul/<entry-slug>/<index>`. Derivation is a pure function over the record's immutable identity fields (org slug + start year) so re-running the import on unchanged input yields identical IDs. A text edit retires the old ID and introduces a new one.
**When to use:** At import (once) and in the fact store's validator (asserting uniqueness).
**Key detail:** the positional suffix is safe *only* because the fact store is frozen — reordering is a `RenderPlan` concern (D-63). Do not let the renderer renumber.
**Collision rule:** if two entries produce the same `<slug>-<year>`, the second gets `-2`, `-3`, … **in source order**, so the rule is deterministic. Record the collision in the import report rather than hiding it (a silent collision is a silent ID change).

### Pattern P3: A single escaping choke point, enforced by `finalize` (D-67)

**What:** the LaTeX Jinja `Environment` is constructed with LaTeX-safe delimiters and a `finalize` callback. `finalize` returns `escape_tex(value)` for plain `str`, passes `Markup` and non-`str` through unchanged.
**Verified mechanics (this session, from the installed Jinja2 3.1.6 source):**

```python
# .venv/lib/python3.14/site-packages/jinja2/compiler.py:1483-1487  (verbatim)
        if frame.eval_ctx.volatile:
            self.write("(escape if context.eval_ctx.autoescape else str)(")
        elif frame.eval_ctx.autoescape:
            self.write("escape(")
        else:
            self.write("str(")
```

```python
# .venv/lib/python3.14/site-packages/jinja2/compiler.py:1470-1472  (verbatim)
        # Template data doesn't go through finalize.
        if isinstance(node, nodes.TemplateData):
            return str(const)
```

With `autoescape=False` the emitted code is `str(environment.finalize(<expr>))`, so:

1. `finalize` sees **every** `\VAR{}` value, including those inside a `\BLOCK{}` body, and including values that passed through a filter.
2. `finalize` sees the **raw** value — it must tolerate non-`str` (ints, `None`, lists) without raising. This is the hook's documented purpose ("can convert `None` implicitly into an empty string", Jinja API docs).
3. Literal template text — every `{`, `}`, `%`, `&`, `\` the template author typed — **never reaches `finalize`**. That is what makes D-67 safe: the template stays readable LaTeX and only interpolated data is escaped.
4. `Markup` returned from `finalize` survives intact because Jinja then applies `str()` to it, and `str(Markup(x)) == str(x)`.
5. `escape_tex` must be idempotent-safe only in the sense of "applied exactly once" — do **not** compose it with a filter, or a value could be escaped twice.

**Do not:** register `escape_tex` as a Jinja *filter* and require templates to use it. A filter is opt-in and a template can forget it; `finalize` is opt-out and a template cannot bypass it. This is the entire point of D-67.

### Pattern P4: The bounded `.tex` parser learns arity, then reads call sites (D-59)

**What:** the tractable subset is exactly:
- **Sections:** `\section{...}`, `\section*{...}` (and the same for `\subsection`), optionally through a `\newcommand` wrapper the preamble declares.
- **Entry macros:** any macro the preamble declares via `\newcommand{\name}[N]{body}` where the body begins to look like an entry header (contains `#1` and at least one of `#2`/`#3`). The parser records `N`, then captures the next `N` balanced brace groups at each `\name{...}` call site. This is the mechanism that makes a macro-heavy resume tractable without a TeX engine.
- **Bullets:** `\item` inside an `itemize`/`enumerate` environment, with balanced-brace capture and inline `\textbf{}`/`\emph{}` flattened to plain text.
- **Preamble packages:** every `\usepackage[...]{...}` name, collected for D-60's "TeX packages requested" count.
- **Comments:** `%` to end of line, honouring `\%`.

**When to use:** one section of the real document in this phase; the fixture exercises the whole subset.
**Everything not on that list is *reported*, never guessed.** The report is counts-and-names only (the `SanitizeReport` discipline): `unresolved_macros: dict[str, int]`, `packages_requested: list[str]`, `sections_parsed`, `entries_parsed`, `bullets_parsed`, `lines_scanned`, `truncated: bool`.
**Bounds (PLAT-04):** a max-lines and a max-nesting-depth ceiling, both `Settings` fields. A pathological document must not be able to hang the single worker.

### Pattern P5: Determinism is a property with named enemies

**What:** the renderer's output must be byte-identical for identical input. The enemies, each with a concrete rule:

| Enemy | Rule |
|-------|------|
| Clock | No `datetime`, `time`, `now()` anywhere in the render path. A `generated_at` in the PDF would also break the golden test. Any date in a rendered CV comes from the fact store or the artefact row (ARCHITECTURE §7.4). |
| Randomness / hashing order | No `random`, no `set` iteration, no `dict` iteration for ordered output. `cv.yaml` is list-based precisely so ordering is explicit (`sections[].order`). |
| Template cache / reload | `Environment(auto_reload=False, cache_size=...)`. Default `auto_reload=True` re-stats the file; it does not change bytes, but pinning it removes a class of surprise. |
| Newlines | Write with `Path.write_text(text, encoding="utf-8", newline="\n")` (or `.write_bytes(text.encode())`). A Windows checkout with `core.autocrlf` would otherwise change the golden bytes. `Environment(newline_sequence="\n", keep_trailing_newline=True)` too. |
| Whitelist ordering | `\usepackage` lines and section order come from `cv.yaml`'s explicit lists, never from a `dict`. |
| Float formatting | If weights ever render as numbers, format with a fixed spec (`f"{w:.1f}"`), never `str(float)` across Python versions. |

**Verification that bites:** (a) the byte-exact golden fixture; (b) a render-twice-identical test; (c) an AST guard scanning `app/latex/render.py` and `app/latex/env.py` for `datetime`/`time`/`random`/`uuid` imports — the same idiom `tests/test_config.py` already uses to scan for threshold literals, so the pattern is house style, not invention.

### Pattern P6: The golden reproduction is two tests with two failure classes (D-68)

**What:**

| Test | Lane | Senses | Fails on |
|------|------|--------|----------|
| `tests/golden/test_render_bytes.py` | default (`-m 'not live'`) | renderer determinism + template regressions | any byte change in `tests/golden/base.rendered.tex` |
| `tests/latex/test_fact_equivalence.py` | `-m latex` inside the container | fact loss in the compiled PDF | a dropped org/title/date/bullet-shingle, plus the D-72 mutation control |

**The mutation control (D-72) is what makes the second test non-vacuous.** Order matters: assert equivalence passes, then deep-copy the facts, mutate one bullet's text and shift one date, re-render, and assert the predicate now *fails*. A fact-count floor (`compared >= N`) rides in the same test so an empty extraction cannot pass. This mirrors `tests/test_config.py::test_the_literal_scan_can_actually_fail` and `tests/test_import_discipline.py::test_the_walker_actually_detects_a_forbidden_import` — every guard in this repo proves it can fail.

### Pattern P7: The engine seam copies `get_llm_backend` exactly (D-76)

**What:** `app/latex/base.py` holds the `LatexEngine` Protocol and `CompileResult`; `app/latex/__init__.py` holds `get_latex_engine()`. The Protocol is `@runtime_checkable`, its methods never raise, and failure is a value.

The model to copy, verbatim from the repo:

```python
# app/llm/__init__.py:13-20  (verbatim)
def get_llm_backend() -> LLMBackend:
    """FastAPI dependency: the configured backend, built per request.

    A function rather than a module-level instance for two reasons: a test can
    override it (the default lane must never touch a live server), and no client
    state is shared between requests.
    """
    return OpenCodeServerBackend()
```

```python
# app/llm/base.py:101-107  (verbatim)
@runtime_checkable
class LLMBackend(Protocol):
    """The ONLY surface the app depends on."""

    async def health(self) -> ProbeOutcome:
        """Server reachability (and version when reported). Never raises."""
        ...
```

**Recommendation:** `CompileResult` mirrors `StructuredCallResult` — `extra="forbid"`, all-scalar fields, `ok`/`error`/`error_kind`/`log`/`pdf_path`/`page_count`/`duration_ms`/`engine`/`sanitised_preamble: list[str]`. Same redaction discipline applies: nothing on this type can carry a raw PDF or the TeX body.

**Blocking discipline (Pitfall M3 / D-22):** `asyncio.create_subprocess_exec` is already async, so no `to_thread` is needed *for the process*; but any `pypdf` extraction on the compile path is blocking CPU work and must go through `asyncio.to_thread`, per the project's existing discipline in `app/pipeline/run.py` (which wraps the synchronous JobSpy path the same way).

### Pattern P8: Every new ceiling is a `Settings` field, and the guards must be widened to see it (PLAT-04)

**What:** add to `app/config.py` (names are the agent's discretion per CONTEXT; these are the recommended spellings):

| Field | Default | Purpose |
|-------|---------|---------|
| `latex_engine` | `"tectonic"` | `Literal["tectonic", "texlive"]` — the D-76/PLAT-04 selector |
| `tectonic_binary` | `"/usr/local/bin/tectonic"` | pinned install location |
| `tectonic_cache_dir` | `"/opt/tectonic-cache"` | explicit, HOME-independent cache path (see Pitfall 2) |
| `tectonic_timeout_seconds` | `60` | per-compile ceiling; a hung engine must not pin the worker |
| `tectonic_offline` | `True` | D-75's cached-only mode as configuration, so a prime run can differ from a render run |
| `latex_xelatex_binary` | `"/usr/bin/xelatex"` | the TeX Live fallback engine (must be xelatex — Pitfall 10) |
| `cv_dir` | `"/cv"` | the fact-store volume root |
| `artifacts_dir` | `"/artifacts"` | the artefact volume root |
| `tex_import_max_lines` | `20000` | the D-59 parser bound |
| `tex_import_max_depth` | `12` | the D-59 nesting bound |

**`meta.max_pages` is deliberately NOT duplicated here.** CV-R3's page budget lives in the fact store (`facts.meta.max_pages`) per D-65. A settings twin would create two sources for one limit. State in the code comment that this *is* the PLAT-04 configuration surface for that limit — it is data, not a constant.

**The guard widening is part of the task, not an afterthought.** `tests/test_config.py` currently derives distinctive literals from `LIMIT_FIELDS` and scans `SCANNED_DIRS = ("app/probe", "app/pipeline")`. A `60`-second timeout hard-coded in `app/latex/compile.py` would pass unnoticed. Extend:

```python
# tests/test_config.py — current values (verbatim, lines 61-107)
LIMIT_FIELDS = (
    "probe_max_results",
    ...
)
SCANNED_DIRS = ("app/probe", "app/pipeline")
```

to add `"tectonic_timeout_seconds"`, `"tex_import_max_lines"`, `"tex_import_max_depth"` to `REQUIRED_SETTINGS_FIELDS` and `LIMIT_FIELDS`, and to extend `SCANNED_DIRS` with `"app/latex"` and `"app/cv"`. Note `tectonic_timeout_seconds = 60 >= DISTINCTIVE_THRESHOLD_FLOOR (3)`, so it actually contributes to the literal scan — unlike the Phase-3 `opencode_max_retries = 2`, which the existing comments already flag as adding nothing to the scan.

### Pattern P9: `cv_versions` is a revision log with one current row (D-77)

**What:** `app/db/repositories/cv_repo.py` is the only SQL for the table. Two functions:

```python
async def snapshot_version(
    session: AsyncSession,
    *,
    facts_json: dict[str, Any],
    schema_version: str,          # str, NOT the YAML int — see Pitfall 6
    source: str,                  # "import_tex" | "hand"
    label: str | None = None,
    now: datetime | None = None,
) -> CvVersionRecord: ...

async def current_version(session: AsyncSession) -> CvVersionRecord | None: ...
```

`snapshot_version` clears the previous `is_current` and inserts the new row with `is_current=True`, inside a `session.begin_nested()` SAVEPOINT (the house rule), and **never commits**. `current_version` orders by `created_at DESC, id DESC` — the same deterministic tie-break `llm_call_repo.latest_probe` and `event_repo`'s projection already use, because two revisions within one second share a `created_at`.
`schema_version` is a `String(32)` column with no CHECK, so the vocabulary is app-level: mirror the `llm_call_repo.PURPOSES`/`STATUSES` idiom with a module-level frozenset and validate *before* issuing SQL, raising a clear `ValueError` rather than a raw `IntegrityError`.

### Pattern P10: `/health` gains a `tectonic` key that is reported, never raised

The shape to extend, verbatim from the repo:

```python
# app/api/health.py:106-112  (verbatim)
    return {
        # The LLM backend being down does NOT degrade the app's own health (D-08).
        "status": "ok" if database == "ok" else "degraded",
        "db": database,
        "opencode": opencode,
        "sources": sources,
    }
```

Add `"tectonic": {"available": bool, "version": str | None, "error": str | None}`, produced by a local `_tectonic_report()` that mirrors `_opencode_report` exactly — including the `except Exception` totality guard (`app/api/health.py:42-45`). A missing engine must leave `/health` at HTTP 200. `tests/api/test_health.py` already asserts the 200-in-every-case property and the `FORBIDDEN_BODY_KEYS` redaction set; the new key must satisfy both.

### Anti-Patterns to Avoid

- **Registering `escape_tex` as a Jinja filter instead of `finalize`.** A filter is opt-in; a template can forget it. D-67 chose `finalize` because "no template can bypass it". Do not add both.
- **Reading `base.tex` to produce the base render.** The base render comes from `cv.yaml` through an identity patch (ARCHITECTURE §7.4, CV-R2). If the renderer ever reads `base.tex`, the two-canonical-documents rule has collapsed.
- **Letting the identity render reuse `base.tex`'s preamble verbatim.** `base.tex` is the *human's* document; the renderer's template is `app/latex/templates/cv.tex.jinja` (D-71). The preamble is a template concern, not copied data.
- **Auto-falling back to the TeX Live image when Tectonic fails.** D-75 rejects this explicitly: the setting would silently override itself and the engine actually used would stop matching the configuration. Fail loudly with a documented rebuild.
- **Enabling `-Z shell-escape`.** Never. See §Security Domain.
- **Teaching the parser more macros "while we're here".** D-59 is bounded *deliberately*; every macro the parser silently guesses at is a fabricated CV fact waiting to happen. Report it instead.
- **Writing `cv.yaml` back from the tool.** `cv.yaml` is human-editable; the importer writes a **draft to a separate path** that a human reviews and moves (D-59's "import + explicit human curation"). An in-place rewrite destroys the review step and makes the unresolved-items report decorative.
- **Making the fact-equivalence predicate a fuzzy ratio.** D-70 rejects it and CV-R5 explains why: a high ratio over a long section hides exactly the dropped bullet the check exists to catch.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LaTeX → PDF | A `pdflatex` invocation wrapper, a retry-until-aux-converges loop, a package-installation step | **Tectonic** with `--only-cached` | Auto-reruns to convergence and auto-fetches packages; the "how many passes does this CV need?" problem and its cross-reference bugs are already solved. |
| LaTeX escaping | A per-template `|escape` filter chain, an HTML-escaper, a regex list maintained by hand in three files | **`finalize` + one `escape_tex`** (D-67) | One enforcement site; a template cannot bypass it; backslash-order and the `{}%&#_$~^` set are handled once. |
| YAML loading | A regex/hand parser for `cv.yaml`, or `yaml.load` with the default loader | **`pyyaml` + `yaml.safe_load`** + Pydantic | `safe_load` is the only safe loader; Pydantic gives the path-qualified failure D-66 requires. Hand-parsing YAML is a defect generator. |
| Path-qualified validation errors | A hand-rolled `if field not in data: raise` tree | **Pydantic v2 `ValidationError.errors()`** `loc` tuples joined with `.` | Pydantic already produces `loc` paths; joining them is one helper. Re-implementing it loses nested/index precision. |
| PDF text extraction | A PDF content-stream parser, an OCR fallback, `pdftotext` (a new binary dependency) | **`pypdf` 6.19.0 `page.extract_text()`** + `len(reader.pages)` | Pure Python, no native extension, already the STACK.md choice, and it "reads what is in the file" rather than guessing. |
| Ligature / whitespace folding for comparison | A fuzzy-ratio threshold to paper over extraction noise | **`unicodedata.normalize("NFKC", ...)` + explicit character folds** | D-70 rejects a ratio because it hides real loss. Normalisation is deterministic and auditable; a ratio is not. |
| Unicode normalisation | A hand-written ligature table (`ﬁ`→`fi`, `ﬄ`→`ffl`, …) | **`unicodedata.normalize("NFKC", ...)`** (stdlib) | NFKC applies the compatibility decomposition that expands the ligature presentation forms; a hand table will miss forms. |
| SHA256 for artefact identity | A custom hash, or a third-party hashing package | **`hashlib.sha256`** (stdlib) | Same digest the existing `listings.content_hash` path uses. |
| Subprocess argv construction | `shell=True`, an f-string command, `os.system` | **`asyncio.create_subprocess_exec(*argv)`** | `create_subprocess_exec` takes an argv list, so TeX content can never become shell syntax. |
| A TeX AST | A "full" LaTeX parser | **The bounded subset in Pattern P4** (escalate to TexSoup only if it fails) | See the Alternatives table: TexSoup parses syntax, not structure. The tractable trick here (learn `\newcommand` arity, read call sites) is app-specific. |
| Scheduler / retry / job store | Anything | **Nothing — out of scope** | Phase 8 owns scheduling. This phase compiles synchronously inside one call. |

**Key insight:** the entire deceptively-complex surface of this phase is *text transformation under an honesty constraint* — escape once, render deterministically, parse conservatively, compare strictly. Every one of those has a stdlib or already-installed answer, and each hand-rolled substitute trades a solved problem for an unsolved one on the path to a PDF the user may send to an employer.

## Runtime State Inventory

Phase 4 is not a rename or refactor, but it **changes the filesystem/volume layout** (`cv/` and `artifacts/` become mounted volumes; a Tectonic cache directory is created at build time). That change has the same "what outside git still encodes the old shape?" question, so the categories are answered explicitly rather than left blank.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | None. `cv_versions`/`cv_artifacts` are empty (no repository exists yet — verified: `app/db/repositories/` contains no `cv_repo.py`, and a repo-wide grep for `CvFacts`/`factstore`/`cv.yaml`/`escape_tex`/`RenderPlan` across `app/` and `tests/` returned **zero** matches). No existing row encodes a path or an engine choice. | None — schema already there (D-77) |
| **Live service config** | None in a UI or database. The one runtime-adjacent configuration is `compose.yml`, which is in git. | None |
| **OS-registered state** | None. No systemd unit, no launchd plist, no pm2 process, no Task Scheduler entry references this project's paths. | None — verified by repo scope |
| **Secrets / env vars** | No new secret. The new env passthroughs (`CV_DIR`, `ARTIFACTS_DIR`, `LATEX_ENGINE`, `TECTONIC_*`) are non-secret and must be added to `compose.yml` **and** `.env.example` following the existing `${VAR:-default}` pattern. The `.env` file is gitignored and contains only `OPENCODE_*` today. | Code edit: `compose.yml` + `.env.example` + `app/config.py`, all three, or a host override silently loses to the in-code default (the exact defect `compose.yml:23-27` documents for the Phase-2 knobs) |
| **Build artifacts / installed packages** | The Tectonic binary at `/usr/local/bin/tectonic` and its cache at `/opt/tectonic-cache` exist **only inside the image**, created by layers. `job_search_copilot.egg-info/` exists in the working tree (present but irrelevant to this phase). `.venv/` is built for **Python 3.14** (path `.venv/lib/python3.14/site-packages/`, `.pyc` files named `cpython-314`) while the image pins 3.13 — a local venv cannot be reused for the Tectonic lane. | Build-time only (D-73/D-74). The **volume mounts** are the real runtime-state change: `./cv` and `./artifacts` must exist on the host or Docker creates them root-owned; document that in the runbook. |
| **Git-ignore state** | `.gitignore` is 10 lines and has **no `cv/` and no `artifacts/` entry** (verified). Without the edit, the real CV would be committed by the first `git add -A`. | Code edit: `.gitignore` (D-58). A guard test asserting the entries exist is cheap and matches the repo's prose-as-test idiom. |

**The canonical question:** *after every file in the repo is updated, what runtime systems still have the old shape?* Answer: only the Docker image's layer cache and the host's `/cv` + `/artifacts` directories — both of which are created fresh by this phase, so there is no stale state to migrate. **No data migration is required in this phase.**

## Common Pitfalls

Each pitfall answers one of the phase's eight critical research questions, or a hazard found while doing so.

### Pitfall 1: Getting the Tectonic offline flag wrong (critical question 1)

**What goes wrong:** the plan writes `--no-network`, `--offline`, `--no-download`, or `TECTONIC_OFFLINE=1`. Tectonic rejects an unknown flag and the container's first render fails with an argument error rather than a useful message.

**The verified answer:** the flag is **`-C` / `--only-cached`**, described by Tectonic's own documentation as "Use only resource files cached locally" (V1 CLI reference) and "configure the engine to refuse to connect to the network when searching for support files" (V2 `build`/`compile`/`dump` pages). `-Z` unstable options are a separate namespace and are not needed.

**Second half of the question — the invocation form.** In 0.17.0 the **V1 CLI is the default**: the V2 interface is activated with a leading `-X`, V1 can be selected explicitly with `-Y`, and "the default is V1". So the correct argv is the V1 form:

```bash
tectonic --only-cached --untrusted --keep-logs --outdir <workdir> <file>.tex
```

**How to avoid:** use `--only-cached`; do not pass `-X`; assert the argv in a unit test with a fake engine; and record `tectonic --version` in the verdict doc (D-62) so the measured claim names the version it measured.

### Pitfall 2: The package cache does not survive into the runtime layer (critical question 1, part 2)

**What goes wrong:** the prime step runs in a builder stage, the runtime stage is a fresh `FROM python:3.13-slim`, and the cache at `/root/.cache/Tectonic` never arrives. Every runtime compile then needs the network — or fails under `--only-cached`.

**The facts:** Tectonic's cache location is OS-dependent and overridable with the **`TECTONIC_CACHE_DIR`** environment variable ("If you need to change the location of the cache, you can do that by setting the environment variable `TECTONIC_CACHE_DIR`"). On Linux the default is `~/.cache/Tectonic`; two independent Dockerfiles in the wild copy exactly that path between stages (`COPY --from=builder /root/.cache/Tectonic/ /root/.cache/Tectonic/`), which corroborates both the location and that a cross-stage `COPY` is the usual mechanism.

**How to avoid — prescribe both belts:**
1. Install Tectonic and prime the cache **inside the existing runtime stage** (the `Dockerfile` already has one runtime stage plus an assets stage, so this needs no new stage at all). A layer-order prime means no `COPY` and no path drift.
2. Also set `ENV TECTONIC_CACHE_DIR=/opt/tectonic-cache` **before** the prime `RUN`, and pass the same value from `app/config.py` at compile time. This makes the path deterministic and independent of `HOME` — which matters because Tectonic will create the cache directory if missing, and issue #1144 documents it attempting that with `0777` permissions when there is no home directory.

**Warning signs:** the build succeeds and the fixture compiles, then the first `docker compose run --rm app pytest -m latex` fails with a package-download error under `--only-cached`. That is the layer-boundary smell.

### Pitfall 3: `--untrusted` is not the same control as escaping (critical question 7, part 2)

**What goes wrong:** the plan treats escaping as the whole security story, and passes `-Z shell-escape` "for the packages that need it", or leaves the argv free of `--untrusted` on the grounds that escaping already sanitises content.

**Why it matters:** escaping makes *content* inert; it does nothing about *a preamble command* that shells out, and it cannot police a template. `--untrusted` is the engine-level control: "a new `--untrusted` argument to the V1 CLI … disables the use of shell-escape, and any other known-insecure features, **regardless of the presence of `-Z shell-escape` or any other options**", and `$TECTONIC_UNTRUSTED_MODE` (when non-empty) is equivalent. Tectonic's own `compile` docs list `--untrusted` as "Input is untrusted — disable all known-insecure features".

**How to avoid, in three layers:**
1. **Never** pass `-Z shell-escape` (STACK.md "What NOT to Use"; Docling's Tectonic integration exposes the equivalent knob and defaults it to `False`).
2. **Always** pass `--untrusted` on every compile argv.
3. **Also** set `TECTONIC_UNTRUSTED_MODE=1` in the image ENV, so a future argv edit cannot quietly undo the sandbox. This is the belt-and-braces the changelog explicitly describes.

### Pitfall 4: A font declared by symbolic name compiles in TeX Live and fails in Tectonic (critical question 1, part 3)

**What goes wrong:** the D-61 fixture follows the awesome-cv convention and writes `\setmainfont{TeX Gyre Pagella}` (or `Roboto`, or `Source Sans Pro`). TeX Live resolves it; Tectonic may not, and the failure is a `fontspec` "font-not-found" error that looks like a missing package.

**The evidence:** Tectonic's maintainer answered exactly this in issue #372: "at the moment Tectonic can only identify fonts based on their filenames, not their symbolic names. So if somewhere you specify a font as 'TeX Gyre Pagella', specifying it as `texgyrepagella-regular.otf` might work instead." Issue #1118 ("Fontspec cannot find fonts by name", opened 2023-11-18, **still open, no fix version, no linked PR**) confirms the same behaviour with the minimal repro. The 0.17.0 changelog mentions `\setmainfont` only in the context of a macOS SIGBUS fix — there is no entry adding symbolic-name lookup.

**Secondary hazard, same root:** on Linux, name-based lookups go through fontconfig, and `python:3.13-slim` ships no fonts and no fontconfig by default (the `dxjoke/tectonic-docker` image installs `libfontconfig1` explicitly for exactly this reason). Whether the musl static build retains a fontconfig path is **not something this research could verify** — no Tectonic binary is installed in this environment and the static-build notes list only `libgraphite2/libharfbuzz/libicu` as statically linked. Treat it as unresolved rather than assumed.

**How to avoid:** declare the font **by filename with an explicit face map**, which resolves in *both* engines — Tectonic searches its bundle, XeLaTeX searches kpathsea, and `tex-gyre` is a TeX Live package present in both:

```latex
\setmainfont{texgyrepagella}[
  Extension      = .otf,
  UprightFont    = *-regular,
  ItalicFont     = *-italic,
  BoldFont       = *-bold,
  BoldItalicFont = *-bolditalic,
]
```

Then make the spike answer the question *empirically* rather than by argument: include **both** forms in the fixture — the by-filename form as the active declaration and the by-name form inside a `% !SPIKE` block the spike script compiles once — and record which one Tectonic accepted. That is a measurement, and D-62's verdict doc is where it belongs.

**Warning signs:** `fontspec error: "font-not-found"` naming a human-readable family name rather than a file path.

### Pitfall 5: `app/latex/compile.py` cannot `import subprocess` (a hard build break)

**What goes wrong:** the first Tectonic task adds `import subprocess` to `app/latex/compile.py` and `tests/test_import_discipline.py` fails the whole build with `a process spawn outside app/llm is an RCE path outside the port`.

**The guard, verbatim:**

```python
# tests/test_import_discipline.py:134-148  (verbatim)
def test_no_module_outside_app_llm_imports_subprocess() -> None:
    offenders: dict[str, list[str]] = {}
    scanned = 0

    for path in _python_modules(APP_DIR):
        if LLM_DIR in path.parents:
            continue
        scanned += 1
        if _imports_of(path, "subprocess"):
            offenders[str(path.relative_to(PROJECT_ROOT))] = ["subprocess"]

    assert scanned > 0, "no modules were scanned — the guard is vacuous"
    assert offenders == {}, (
        f"a process spawn outside app/llm is an RCE path outside the port: {offenders}"
    )
```

This is a **global** rule over `app/` whose only named exception is `app/llm`. `app/latex/` is not exempt.

**How to avoid — widen the guard deliberately, and prove the widening is not an empty courtesy.** The repo already contains the pattern for exactly this situation: the httpx half of the same file is *scoped* to `LLM_CALL_PATH_DIRS` with an `EXCLUDED_HTTPX_DIRS = ("app/sources",)` carve-out, and two tests keep the exclusion honest —
`test_the_sources_exclusion_is_deliberate_not_accidental` asserts the excluded directory really does import httpx and really is outside the scanned directories, so "the exclusion cannot become an empty courtesy". Apply the identical shape:

```python
# recommended change to tests/test_import_discipline.py
#   SUBPROCESS_EXEMPT_DIRS = ("app/llm", "app/latex")
#   + a mirror test that app/latex genuinely imports subprocess
#   + a mirror test that app/latex is genuinely outside the guarded set
```

Rename the guard to say what it now means (`test_subprocess_is_confined_to_declared_process_hosts`) and record *why* `app/latex` is on the list — it is a second process host by design (D-76), not an accident. **Do not** move the compile call into `app/llm/` to satisfy the letter of the rule; `app/llm/` is the LLM port and the two port boundaries must not merge.

**Warning signs:** the plan's file list mentions `app/latex/compile.py` and `subprocess` but not `tests/test_import_discipline.py`.

### Pitfall 6: `schema_version` is an int in YAML and a `String(32)` in the database (critical question 5)

**What goes wrong:** `cv_repo.snapshot_version` is passed `facts.schema_version` (the int `1`) and SQLAlchemy/SQLite stores `"1"` anyway — because SQLite's type affinity coerces it — so the mistake is invisible until a Postgres migration, or until a comparison like `row.schema_version == facts.schema_version` fails (`"1" != 1`).

**The two definitions, verbatim:**

```python
# app/db/models.py:358-367  (verbatim)
class CvVersion(Base):
    __tablename__ = "cv_versions"

    id = Column(Integer, primary_key=True)
    label = Column(String(128))
    schema_version = Column(String(32))
    facts_json = Column(JSON)
    source = Column(String(16))
    created_at = Column(DateTime, nullable=False)
    is_current = Column(Boolean, nullable=False, default=False, server_default=text("0"))
```

against ARCHITECTURE §7.2's `schema_version: 1` (an int). Also note the columns are **nullable** (`created_at` is the only one with `nullable=False` and no server default), so the repository must supply `label`, `schema_version`, `source`, `facts_json` and `created_at` explicitly rather than relying on the schema to reject omissions.

**How to avoid:** store `str(facts.schema_version)`; read it back as `str` and compare as `str`; and add one test that inserts via the repository and reads the raw column through `sqlite3` to assert the stored value is the string `"1"`. Bounded `VARCHAR` is the repo's established style for enum-like columns (`server_version` in migration 0003 has an identical test that asserts `type.upper().startswith("VARCHAR")`).

### Pitfall 7: IDs drift between runs (D-64)

**What goes wrong:** the ID slug is derived from a mutable field (the bullet text, or `title_id`), so curating a bullet's wording silently renames an ID that is already embedded in a stored `structured_diff`. Every previously rendered PDF can no longer be explained from its fact-store revision.

**How to avoid:**
1. Derive the entry ID from **immutable identity only**: the org slug + start year. Never from a title, never from a bullet's text.
2. Derive the bullet ID from `<entry-id>/<index>` — safe precisely because the store is frozen (D-63).
3. Determinism: the slug function must not iterate a `dict` or a `set`. Normalise (casefold → strip diacritics → non-alphanumerics to `-` → collapse) and take the year from `start`.
4. **Collisions are recorded, not hidden:** a second `acme-2021` becomes `acme-2021-2` in source order, and the collision is listed in the import report. A silent suffix is a silent ID change.
5. A test that re-derives IDs from the same fixture twice and asserts equality; plus a test that asserts a **text edit produces a new bullet ID and retires the old one** (D-64's actual claim, which nothing else tests).

### Pitfall 8: `pypdf` loses spaces, so the naive predicate fails on a correct document (critical question 6)

**What goes wrong:** D-70 says "collapse whitespace, then assert each bullet's token-shingle is present". `pypdf` can extract `SeniorEngineer` for a PDF that renders "Senior Engineer" — a documented, long-standing class of bug (issues #17 and #1328; discussion #2038 summarises it as "inner-word spaces that often occur after the first letter of a word"). Collapsing whitespace does **not** restore a space that was never emitted, so a *correct* render fails the check and the golden test becomes a false alarm generator.

**Ligatures are the same shape of problem, from the other direction.** `pypdf`'s own extraction docs raise ligatures as an explicitly *open* question — "The Unicode symbol U+FB00 is a single symbol ﬀ for two lowercase letters 'f'. Should that be parsed as the Unicode symbol 'ﬀ' or as two ASCII symbols 'ff'?" — and unlike PyMuPDF it exposes no `-noligatures`-style option to decide it. Whether a given TeX-produced PDF yields `ﬁ` or `fi` depends on how the font's `ToUnicode` CMap maps the ligature glyph. D-70 already names this ("fold ligature characters"); the mechanism is NFKC.

**How to avoid — two normalised forms, one predicate:**
1. `normalise_for_compare(text)` — NFKC, then explicit folds: soft hyphen removed, hyphenated line-breaks joined, dashes unified, curly quotes unified, NBSP → space, whitespace collapsed.
2. `squash(text)` — `normalise_for_compare`, then lowercase and **remove all whitespace**. The shingle membership check runs on `squash(...)` of both sides, so a missing or inserted space cannot cause a false failure.
3. Keep the date/org checks on the whitespace-preserving form (a space inside a date is a real signal), and keep the **predicate** strict membership — never a ratio (D-70).

**Warning signs:** the mutation control (D-72) passes when it should fail, *or* the correct document fails while the mutation check is the only reason you notice. Both mean the normaliser is doing the wrong job.

### Pitfall 9: Nondeterminism creeping into the golden renderer (critical question 5)

**What goes wrong:** the byte-exact golden test passes locally and fails in the container; or passes for months and fails on the first commit that adds a `generated_at`. Common sources: `datetime.now()`, `uuid4()`, a `set` iteration for `\usepackage` order, `str(float)` for a weight, a CRLF checkout on Windows, and `Environment(auto_reload=True)` combined with a template whose whitespace control (`trim_blocks`, `lstrip_blocks`) was never pinned.

**How to avoid:**
- The render path has **no clock**: assert it with an AST scan over `app/latex/render.py` and `app/latex/env.py` for `datetime`, `time`, `random`, `uuid` — the same idiom `tests/test_config.py` uses for threshold literals.
- Pin the Environment: `autoescape=False`, `trim_blocks=True`, `lstrip_blocks=False`, `keep_trailing_newline=True`, `newline_sequence="\n"`, `auto_reload=False`, `cache_size=0`.
- Write bytes: `Path.write_bytes(text.encode("utf-8"))`, or `write_text(..., newline="\n")`. Never rely on `core.autocrlf`.
- Add a `.gitattributes` entry pinning `tests/golden/**` and `app/latex/templates/**` to `-text` (or `eol=lf`) so the committed golden bytes are the compared golden bytes on every platform. The repo currently has **no `.gitattributes`** (verified by directory listing) — this is the phase that needs one.
- Compare with `read_bytes()`, not `read_text()`. A text comparison hides encoding and line-ending differences that a real renderer would produce.

### Pitfall 10: `Dockerfile.texlive` uses `pdflatex` and cannot compile the fixture (critical question 8)

**What goes wrong:** the fallback image installs the "obvious" TeX Live packages and runs `pdflatex`, which cannot load `fontspec` at all — `fontspec` requires XeLaTeX or LuaLaTeX. The fallback is then "available" in name only, and criterion 3's claim is untrue.

**How to avoid:**
- The fallback engine is **`xelatex -interaction=nonstopmode -halt-on-error`**. `TexLiveEngine`'s argv differs from `TectonicEngine`'s only in the binary, the flags, and the fact that TeX Live does *not* need a cache prime.
- Build a **curated subset**, not `texlive-full` (~4.2 GB, 8–15 min). The fixture's needs, mapped to Debian packages, are roughly:

```
texlive-xetex texlive-latex-recommended texlive-latex-extra
texlive-fonts-recommended fonts-texgyre fonts-lmodern
```

`texlive-xetex` is non-negotiable (fontspec). `texlive-latex-extra` is the heavy one and supplies `paracol`/`titlesec`; it is the first thing to trim if the build is too slow. `fonts-texgyre` supplies the `.otf` files the by-filename declaration resolves against. Do **not** add `texlive-fonts-extra` (~GB-scale, and unnecessary). `biber`/`biblatex` are only needed if the CV has a bibliography — if it ever does, pin `biber` 2.17 for Tectonic's bundled `biblatex` control file v3.8 (STACK.md Q6 caveat 2; Debian's 2.18 is too new).
- **Make the measured-once claim cheap and true (D-76):** build the image by hand, run the fixture through it, and record in the verdict doc: the image size, the build duration, the compile argv, and the resulting `page_count`. The deliverable is the record, not the image.

**Warning signs:** the texlive fallback is described in prose but the verdict doc has no recorded compile result. That is exactly the "written intention" D-76 exists to replace.

### Pitfall 11: `cv/` and `artifacts/` enter git, or don't exist on the host

**What goes wrong (a):** `.gitignore` has no `cv/` entry and the real CV is committed by the first `git add -A`. D-58's whole point is that `cv/base.tex` and `cv/cv.yaml` are "in the same class as `.env`".

**The current file, verbatim (10 lines, no `cv/`, no `artifacts/`):**

```
.planning/research/.cache/
__pycache__/
.venv/
*.pyc
.env
data/
node_modules/
.pytest_cache/
pytest-of-*/
*.egg-info/
```

**How to avoid:** add `cv/` and `artifacts/` and add a guard test that reads `.gitignore` and asserts both entries — a prose requirement with a one-line test is the repo's established idiom (`tests/test_deploy_manifest.py` parses `compose.yml`; `tests/test_dependency_pins.py` reads both manifest files).

**What goes wrong (b):** the volume is added to `compose.yml` but the host directory does not exist, so Docker creates it root-owned and the container — if it ever drops privileges — cannot write. **How to avoid:** document `mkdir -p cv artifacts` in `docs/runbook-latex-compile.md`, and make the app's failure explicit rather than a mystery (a missing `cv.yaml` is a typed failure value with the resolved path in the message — D-66's "fails loudly" applies to a missing file too, not only a malformed one).

### Pitfall 12: Treating the spike's verdict as a measurement (the D-62 trap)

**What goes wrong:** the verdict doc reads "Tectonic compiles the CV" when what was actually compiled is a stand-in built from an assumed package set. That is the project's own ethical line applied to itself — and the Phase 1 probe doc establishes the precedent explicitly: "Presenting one run as a measurement is the measurement equivalent of a fabricated CV claim, and this project's ethical line applies to its own evidence."

**How to avoid:** copy the Phase 1 document's structure verbatim — a status marker (`PARTIAL`), a clearly separated "UNRESOLVED — blocked on the real document" section, and the exact re-runnable command. `docs/probes/README.md` already specifies the shape and can be extended with a LaTeX section rather than a second runbook.

### Pitfall 13: The parser guesses, and a fabricated fact enters the store

**What goes wrong:** eager to get a full `cv.yaml`, the importer emits a best-effort value for a macro it did not understand (a title positional it assumed, a date it parsed loosely). That value is now a CV fact that the LLM's patch schema enumerates and the verifier trusts.

**Why it is the worst failure in this phase:** every downstream honesty guarantee is *structural* — the schema has no free-text employer field, so fabrication is unrepresentable. A guessed import defeats that from the top: the enumerated value is wrong but indistinguishable from a real one.

**How to avoid:** the parser only emits what it fully understood. Anything else goes into `unresolved_macros` with a line number and a count. The draft `cv.yaml` is written to a **separate path** for human review (D-59's curation step); the fact store's validator additionally rejects an empty required field, so "unresolved" cannot masquerade as "empty". And D-66's no-default rule is the enforcement: a field the importer could not fill must be **absent and loud**, never defaulted.

### Pitfall 14: Compiling on the event loop, or blocking on PDF extraction (Pitfall M3 / D-22)

**What goes wrong:** the compile is awaited inline in a request handler, or `pypdf`'s extraction runs synchronously on the loop. The UI "feels dead" and `/health` takes seconds. PITFALLS M3 lists this as the *first* real scaling pain.

**How to avoid:** `asyncio.create_subprocess_exec` is already non-blocking for the child process; but (a) wrap any `pypdf` work in `asyncio.to_thread`, (b) never await a full render+compile inside a request handler — expose it through the pipeline and let the UI poll, and (c) add `tectonic` to `/health` as a *reported* key with its own short timeout, not as a blocking probe on every request.

## Code Examples

Verified patterns. Where a claim is tagged `[VERIFIED]`, the value was read from the named source this session and is quoted verbatim beside it.

### The LaTeX Jinja Environment and the escaping choke point (D-67)

```python
# app/latex/env.py
"""The LaTeX-safe Jinja environment. A SECOND Environment instance — the HTML one
in app/web/template_env.py is untouched (STACK.md Q6: "two environments, one process")."""
from __future__ import annotations

from markupsafe import Markup
import jinja2

from app.domain.tex import escape_tex

#: Delimiters are the Bradley Erickson convention adopted by STACK.md Q6.
#: KNOWN LIMITATION, state it in the module docstring: block_end_string is a single
#: "}", so a \BLOCK{ } BODY cannot contain a "}". Keep blocks pure control flow and
#: emit every brace through a separate \VAR{ } expression. Pick this convention and
#: never mix it with ((( )))/((* *)).
DELIMITERS: dict[str, object] = {
    "block_start_string": "\\BLOCK{",
    "block_end_string": "}",
    "variable_start_string": "\\VAR{",
    "variable_end_string": "}",
    "comment_start_string": "\\#{",
    "comment_end_string": "}",
    "line_statement_prefix": "%%",
    "line_comment_prefix": "%#",
    # Determinism (Pattern P5):
    "trim_blocks": True,
    "lstrip_blocks": False,
    "keep_trailing_newline": True,
    "newline_sequence": "\n",
    "auto_reload": False,
    "cache_size": 0,
    # NOT HTML. autoescape=True would emit &amp; and would not touch % _ # $ (D-67).
    "autoescape": False,
}


def _latex_finalize(value: object) -> object:
    """Escape every plain str; leave Markup and non-str values alone.

    Jinja's compiler wraps variable output as ``str(environment.finalize(<expr>))``
    when autoescape is False, and does NOT route literal template text through
    finalize — verified in the installed jinja2 3.1.6, compiler.py:1483-1487 and
    compiler.py:1470-1472. So this single function is the choke point for every
    interpolated value, and every literal brace/percent the template author typed
    is untouched.
    """
    if isinstance(value, Markup):
        return value                      # the explicit opt-out (D-67)
    if isinstance(value, str):
        return escape_tex(value)
    return value                          # ints, None, lists pass through unresolved


def make_latex_env(directory: str | "Path") -> jinja2.Environment:
    """The LaTeX Environment. Mirrors app.web.template_env.make_templates in shape."""
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(directory)), **DELIMITERS)
    env.finalize = _latex_finalize
    return env
```

Template (`app/latex/templates/cv.tex.jinja`) — note the braces: literal LaTeX `{`/`}` only, and every interpolated value is a separate `\VAR{}`:

```latex
\documentclass[11pt]{article}
\usepackage{fontspec}
\usepackage[margin=1.5cm]{geometry}
\usepackage{enumitem}
\setmainfont{texgyrepagella}[Extension=.otf, UprightFont=*-regular,
  ItalicFont=*-italic, BoldFont=*-bold, BoldItalicFont=*-bolditalic]
\begin{document}
\BLOCK{ for section in plan.sections }
\section*{\VAR{section.title}}
\BLOCK{ for entry in section.entries }
\textbf{\VAR{entry.org}}\hfill\VAR{entry.dates}\\
\VAR{entry.title}
\begin{itemize}[leftmargin=*]
\BLOCK{ for bullet in entry.bullets }
\item \VAR{bullet.text}
\BLOCK{ endfor }
\end{itemize}
\BLOCK{ endfor }
\BLOCK{ endfor }
\end{document}
```

### `escape_tex` — the exact escape set, backslash first (CV-06, critical question 3)

```python
# app/domain/tex.py
"""Pure TeX text transforms. House rules follow app/domain/sanitize.py:
pure, total, deterministic, config-free, and the report carries counts only."""

#: Order matters: the backslash MUST be replaced first or the replacement text of
#: every later escape is itself escaped (STACK.md Q6 states this explicitly).
_TEX_ESCAPES: tuple[tuple[str, str], ...] = (
    ("\\", r"\textbackslash{}"),
    ("{", r"\{"),
    ("}", r"\}"),
    ("$", r"\$"),
    ("&", r"\&"),
    ("#", r"\#"),
    ("%", r"\%"),
    ("_", r"\_"),
    ("~", r"\textasciitilde{}"),
    ("^", r"\textasciicircum{}"),
)


def escape_tex(value: str) -> str:
    """Escape the ten characters that can break or corrupt a LaTeX document.

    Total: "" -> "". Deterministic: no iteration over a set, no locale, no clock.
    Idempotence is deliberately NOT a claimed property — the function must be
    applied exactly once, which is why it lives inside the Jinja `finalize` choke
    point rather than being exposed as a filter a template could double-apply.
    """
    for old, new in _TEX_ESCAPES:
        value = value.replace(old, new)
    return value
```

**Notes that matter at the executor's `parse()`:**

- `\textbackslash{}` and `\textasciitilde{}` / `\textasciicircum{}` are the standard LaTeX commands for those characters; the trailing `{}` is required or the following space is swallowed.
- The set above is the STACK.md Q6 set, **reordered so backslash is first**. STACK.md's snippet has the same pairing but relies on the comment for the ordering rule; making the ordering structural (a tuple, backslash at index 0) is what stops a later edit from breaking it.
- **Unicode / ligatures are deliberately NOT escaped.** `escape_tex` handles *TeX-special ASCII*; non-ASCII text is passed through to XeTeX, which is fully Unicode-enabled. Escaping `é` would be wrong. The ligature problem in this phase is entirely on the **extraction** side (Pitfall 8), not the emission side.
- Add a test that every one of the ten characters appears escaped and that no unescaped `&`, `%`, `#`, `_`, `$`, `~`, `^`, `{`, `}` survives, plus a hostile-bullet end-to-end compile in the `latex` lane. `"R&D cut latency 20% on a C++ _p99_ job"` is the one-line fixture that exercises all of it.

### The fact store's comparison normalisation (CV-03, critical question 6)

```python
# app/domain/tex.py (continued)
import re
import unicodedata

_DE_HYPHENATE_RE = re.compile(r"(?<=\w)-\n(?=\w)")
_WHITESPACE_RE = re.compile(r"\s+")
_SQUASH_RE = re.compile(r"[\s\W_]+", re.UNICODE)   # non-word, for the shingle form

_CHAR_FOLDS: tuple[tuple[str, str], ...] = (
    ("\u00ad", ""),      # soft hyphen — an extractor artefact, never content
    ("\u2010", "-"), ("\u2011", "-"), ("\u2012", "-"),
    ("\u2013", "-"), ("\u2014", "-"), ("\u2212", "-"),
    ("\u2018", "'"), ("\u2019", "'"), ("\u201c", '"'), ("\u201d", '"'),
    ("\u00a0", " "), ("\u202f", " "), ("\u2009", " "),
)


def normalise_for_compare(text: str) -> str:
    """Fold extraction artefacts to a comparable form (D-70), preserving spaces.

    NFKC applies the compatibility decomposition that expands the ligature
    presentation forms (U+FB00-U+FB06) to their ASCII sequences, so "ﬁ" and "fi"
    compare equal without a hand-written ligature table.
    """
    value = unicodedata.normalize("NFKC", text)
    for old, new in _CHAR_FOLDS:
        value = value.replace(old, new)
    value = _DE_HYPHENATE_RE.sub("", value)   # join hyphenated line-breaks
    value = _WHITESPACE_RE.sub(" ", value)
    return value.strip()


def squash(text: str) -> str:
    """The whitespace-INSENSITIVE canonical form, for shingle membership only.

    pypdf can drop a space entirely (issues #17, #1328), so a membership check on
    the space-preserving form produces FALSE FAILURES on a correct document.
    Squashing both sides makes a missing or inserted space irrelevant while
    keeping the predicate a strict membership test — never a fuzzy ratio (D-70).
    """
    return _SQUASH_RE.sub("", normalise_for_compare(text).casefold())


def facts_present_in(facts: CvFacts, extracted_pdf_text: str) -> tuple[bool, list[str]]:
    """Every org, title, date and bullet token-shingle must be present. Counts facts
    compared, so the caller can assert a non-vacuous floor (D-72)."""
    haystack = normalise_for_compare(extracted_pdf_text)
    squashed = squash(extracted_pdf_text)
    missing: list[str] = []
    compared = 0
    for entry in facts.all_entries():
        for value in (entry.org_name, entry.title_name, entry.date_range_label):
            compared += 1
            if squash(value) not in squashed:
                missing.append(value)
        for bullet in entry.bullets:
            compared += 1
            if _shingle(bullet.text) not in squashed or _shingle(bullet.text) not in squash(bullet.text):
                missing.append(bullet.text)
    return (not missing), missing
```

**Where the token-shingle must come from:** the *source* bullet's shingles are computed from `cv.yaml`'s immutable `bullet.text`. Assert that each source shingle is present in the squashed PDF text. A dropped bullet has zero of its shingles present, which is exactly CV-R5's silent-condensing failure.

**One-line verification the executor should run before trusting the NFKC claim:** `unicodedata.normalize("NFKC", "\ufb01") == "fi"` must be `True`. (Tagged `[ASSUMED]` in the Assumptions Log — standard Unicode behaviour, but not executed in this research environment because the shell denies the interpreter.)

### The fact-store skeleton — no defaults, `extra="forbid"`, path-qualified failure (D-66)

```python
# app/domain/cv.py  — PURE. No yaml, no jinja2, no filesystem.
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError

SCHEMA_VERSION = 1


class _Forbid(BaseModel):
    # P5: every contract type forbids extras. On the CV models this is also a
    # correctness control: a typo'd key in a human-edited cv.yaml must FAIL, not
    # be silently dropped, or a fact disappears without a word.
    model_config = ConfigDict(extra="forbid")


class Bullet(_Forbid):
    id: str                       # bul/<entry-slug>/<index>
    text: str                     # IMMUTABLE source text
    evidence: str = "unrecorded"  # verbatim | grounded | unrecorded
    metrics: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class Entry(_Forbid):
    id: str                       # exp/<slug>-<start-year>
    org_id: str                   # enumerated, not free text (ARCHITECTURE §7.2 property 1)
    title_id: str
    start: str                    # "YYYY-MM"
    end: str | None = None       # null == present. NO default that fills a date (D-66).
    location: str | None = None
    bullets: list[Bullet]


class Section(_Forbid):
    id: str
    title: str                    # a resolved title (see Open Question O3 on title_key)
    order: int
    entries: list[Entry] = Field(default_factory=list)


class Meta(_Forbid):
    name: str | None = None
    max_pages: int = 2            # CV-R3's page budget; the PLAT-04 surface for it


class CvFacts(_Forbid):
    schema_version: int
    meta: Meta
    sections: list[Section]
    orgs: list[Org] = Field(default_factory=list)
    titles: list[Title] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)
```

```python
# app/cv/factstore.py — the I/O side, and the ONLY yaml import for cv.yaml.
import yaml
from pydantic import ValidationError

from app.domain.cv import CvFacts, SCHEMA_VERSION


class CvFactStoreError(Exception):
    """A path-qualified, loud failure. Never a partial load, never a default (D-66)."""


def _path_qualified(exc: ValidationError) -> str:
    """'sections.2.entries.0.bullets.3.text: Input should be a valid string'."""
    parts = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error["loc"])
        parts.append(f"{loc}: {error['msg']}")
    return "; ".join(parts)


def load_facts(path: Path) -> CvFacts:
    if not path.exists():
        raise CvFactStoreError(f"no CV fact store at {path}")   # a missing file is loud too
    # safe_load ONLY. yaml.load with the default loader can construct arbitrary
    # Python objects from document content.
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    try:
        facts = CvFacts.model_validate(raw)
    except ValidationError as exc:
        raise CvFactStoreError(f"{path}: {_path_qualified(exc)}") from exc
    if facts.schema_version != SCHEMA_VERSION:
        raise CvFactStoreError(
            f"{path}: schema_version {facts.schema_version} != {SCHEMA_VERSION}"
        )
    _assert_ids_unique(facts)      # D-63: an ID appears once, ever
    return facts
```

### Deterministic ID derivation (D-63, D-64)

```python
# app/domain/cv.py (continued)
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Deterministic, locale-free, diacritic-insensitive. No dict/set iteration."""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii").casefold()
    return _SLUG_STRIP_RE.sub("-", ascii_only).strip("-")


def derive_entry_id(org_name: str, start: str) -> str:
    """exp/<slug>-<start-year>. Identity fields only — never a title, never a
    bullet's text (Pitfall 7)."""
    year = start[:4]
    return f"exp/{slugify(org_name)}-{year}"


def qualify_entry_ids(entries: list[tuple[str, str]]) -> list[str]:
    """Collision rule, deterministic and recorded: the Nth duplicate gets -N in
    SOURCE ORDER. Return the ids so the caller can put collisions in the import
    report rather than hiding them."""
    seen: dict[str, int] = {}
    ids: list[str] = []
    for org_name, start in entries:
        base = derive_entry_id(org_name, start)
        seen[base] = seen.get(base, 0) + 1
        ids.append(base if seen[base] == 1 else f"{base}-{seen[base]}")
    return ids


def derive_bullet_id(entry_id: str, index: int) -> str:
    """bul/<entry-slug>/<index>. Safe only because the store is frozen: reordering
    is a RenderPlan concern (D-63), never a cv.yaml edit."""
    entry_slug = entry_id.split("/", 1)[1]
    return f"bul/{entry_slug}/{index}"
```

### Preamble sanitisation for pdfTeX-only primitives (CV-R7, critical question 7)

```python
# app/domain/tex.py (continued)
#: The pdfTeX primitives an XeTeX-derived engine rejects (Tectonic is XeTeX-derived;
#: STACK.md Q6 caveat 3, corroborated by R's own refman preamble which guards the
#: same three names behind \ifnum\pdfoutput>0).
_PDFTEX_PRIMITIVES: tuple[str, ...] = (
    "pdfcompresslevel", "pdfobjcompresslevel", "pdfminorversion", "pdfoutput",
    "pdfpagewidth", "pdfpageheight", "pdfimageresolution", "pdfdecimaldigits",
    "pdfadjustspacing", "pdfomitcharset", "pdfmovechars", "pdfappendkern",
    "pdfoptionpdfminorversion",
)
_PRIMITIVE_RE = re.compile(
    r"^[ \t]*(?P<cmd>\\(?:" + "|".join(_PDFTEX_PRIMITIVES) + r"))\b(?P<rest>.*)$",
    re.MULTILINE,
)


def sanitise_preamble(tex: str) -> tuple[str, list[str]]:
    """Comment out UNGUARDED pdfTeX-only primitives in the preamble only.

    Returns (tex, removed) where `removed` names every command taken out, so the
    compile log can say what was changed — silent sanitisation would hide a real
    difference between the human's document and the rendered one.

    GUARDED occurrences are left alone: most documents already wrap these in
    \ifx\pdfoutput\undefined ... \else ... \fi, and under XeTeX that branch is
    simply false. Acting on a guarded line is a needless divergence.
    """
    head, sep, body = tex.partition(r"\begin{document}")
    removed: list[str] = []

    def _comment(match: re.Match[str]) -> str:
        removed.append(match.group("cmd"))
        return "% [pdftex-only, commented by job-search-copilot] " + match.group(0).lstrip()

    head = _PRIMITIVE_RE.sub(_comment, head)
    return head + sep + body, removed
```

**Deliberately conservative:** it acts only inside the preamble, only on lines where the primitive is the first non-space token, and it *comments* rather than deletes. If the real document's preamble defeats it, the verdict doc records that (D-62) and the TeX Live fallback is the answer — not a more aggressive regex over content the tool does not understand.

### The engine seam and the Tectonic argv (D-76, critical questions 1 and 5)

```python
# app/latex/base.py — mirrors app/llm/base.py (Protocol, failure-as-value, extra="forbid")
@runtime_checkable
class LatexEngine(Protocol):
    """The ONLY surface the app depends on for compilation. Never raises."""

    async def compile(self, *, tex: str, workdir: Path) -> CompileResult:
        """Compile `tex` to PDF in `workdir`. Failure is a VALUE."""
        ...

    async def health(self) -> EngineProbe:
        """Binary availability + version. Never raises (mirrors ProbeOutcome)."""
        ...
```

```python
# app/latex/compile.py
class TectonicEngine:
    """The pinned Tectonic binary. No shell, no shell-escape, always untrusted mode."""

    def __init__(self, *, binary: str, cache_dir: str, offline: bool, timeout: float) -> None:
        self._binary, self._cache_dir = binary, cache_dir
        self._offline, self._timeout = offline, timeout

    def _argv(self, source: Path, outdir: Path) -> list[str]:
        argv = [self._binary]
        if self._offline:
            argv.append("--only-cached")     # verified flag; -C is the short form
        argv += [
            "--untrusted",                   # disables shell-escape AND other insecure features
            "--keep-logs",                   # so CompileResult.log has a real engine log
            "--outdir", str(outdir),
            str(source),
        ]
        return argv

    async def compile(self, *, tex: str, workdir: Path) -> CompileResult:
        # Stage -> compile in a temp dir inside the image -> copy artefacts out.
        # STACK.md Q6 caveat 2: Tectonic's VFS cannot re-open the primary input
        # after biber on a Docker bind mount. Compiling in a temp dir from day one
        # means never having to retrofit this. Only relevant if the CV has a
        # bibliography, but the shape is free now.
        ...
        env = {**os.environ, "TECTONIC_CACHE_DIR": self._cache_dir}
        proc = await asyncio.create_subprocess_exec(
            *argv, cwd=str(workdir), env=env,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        # bound it: a hung engine must not pin the single worker (PLAT-04)
        ...
        # page_count via pypdf, off the event loop (Pitfall 14)
        page_count = await asyncio.to_thread(_count_pages, pdf_path)
```

**TeXLliveEngine** is the same class with `[latex_xelatex_binary, "-interaction=nonstopmode", "-halt-on-error", "-output-directory", str(outdir), str(source)]` — and **no** cache prime.

### The `cv_versions` writer (D-77, Pitfall 6)

```python
# app/db/repositories/cv_repo.py — takes an AsyncSession, NEVER commits.
SOURCES: frozenset[str] = frozenset({"import_tex", "hand"})   # no CHECK on the column;
                                                              # the vocabulary is app-level


async def snapshot_version(
    session: AsyncSession, *, facts_json: dict[str, Any], schema_version: str,
    source: str, label: str | None = None, now: datetime | None = None,
) -> CvVersionRecord:
    if source not in SOURCES:
        raise ValueError(f"unknown source {source!r}; expected one of {sorted(SOURCES)}")

    previous = (
        await session.execute(select(CvVersion).where(CvVersion.is_current.is_(True)))
    ).scalars().all()
    for row in previous:
        row.is_current = False

    row = CvVersion(
        label=label,
        schema_version=schema_version,      # str(1) -> "1"; the column is String(32)
        facts_json=facts_json,
        source=source,
        created_at=now or datetime.now(UTC),  # nullable=False, NO server default
        is_current=True,
    )
    async with session.begin_nested():        # the house SAVEPOINT rule
        session.add(row)
        await session.flush()
    return _to_record(row)
```

### The Dockerfile additions (D-73, D-74) — single-line shell only (P10)

```dockerfile
# Install the pinned Tectonic binary and verify it in the SAME RUN (D-73).
# Mirrors the JobSpy SHA assertion: the checksum is not a separate layer that a
# cache could reuse while the download changed underneath it. Single-line shell,
# no heredoc — `docker compose build` can fall back to the classic builder.
ARG TECTONIC_VERSION=0.17.0
ARG TECTONIC_SHA256=8533d07f9ccbd7a65824b9e0459041bca34af1eb33daba48f59215593753a3b7
RUN cd /tmp && curl -fsSL -o tectonic.tar.gz "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-x86_64-unknown-linux-musl.tar.gz" && echo "${TECTONIC_SHA256}  tectonic.tar.gz" | sha256sum -c - && tar -xzf tectonic.tar.gz -C /usr/local/bin tectonic && rm -f tectonic.tar.gz && tectonic --version

# Deterministic, HOME-independent cache location; set BEFORE the prime (Pitfall 2).
ENV TECTONIC_CACHE_DIR=/opt/tectonic-cache TECTONIC_UNTRUSTED_MODE=1

# Prime the package cache AND prove the engine works, at build time (D-74).
# This layer is the reason the runtime can pass --only-cached. It is also the
# build-time proof that the engine actually runs, the same shape as the migration
# smoke below it.
RUN tectonic --outdir /tmp/prime /app/tests/fixtures/cv/awesomecv_standin.tex && test -f /tmp/prime/awesomecv_standin.pdf && rm -rf /tmp/prime
```

**The checksum value is verified** — see §Standard Stack "Version verification": `8533d07f9ccbd7a65824b9e0459041bca34af1eb33daba48f59215593753a3b7`, read from the Tectonic project's own GitHub Releases API payload for tag `tectonic@0.17.0` this session.

**Note the `--outdir /tmp/prime` + `test -f ... && rm -rf` structure:** the prime must produce a real PDF (that is the proof), and the PDF must not be left in the image. The `test -f` is what turns "the command exited 0" into "the engine produced an artefact".

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `TeX Live` apt packages | **Tectonic** with a primed cache | Ongoing; Tectonic 0.17.0 released 2026-07-27 | ~124 MB vs ~4.2 GB; auto-convergence removes the multi-pass problem. TeX Live remains the documented fallback. |
| Default Jinja2 delimiters in `.tex` | **`\VAR{}`/`\BLOCK{}` with a separate `Environment`** | Long-standing convention, re-affirmed by STACK.md Q6 | `{{ }}`/`{% %}` are unusable in LaTeX. Two Environments, one process. |
| Escaping as a filter templates must remember | **`finalize` as a non-bypassable choke point** | D-67 (this phase) | A template cannot forget to escape; the opt-out is explicit (`Markup`). |
| Parsing a PDF to recover CV facts | **Structured fact store as the addressing unit** | ARCHITECTURE §7; STACK.md Q6 | Fabrication becomes unrepresentable in the enumerated dimensions; the patch is its own audit trail. |
| `linkedin_api`-style scrapers / auto-appliers | JobSpy adapters + assisted apply (out of this phase) | Phase 1 | Not this phase's concern; recorded so the plan does not reach for a CV library. |
| Fuzzy-ratio text comparison for CV drift | **Normalise, then strict membership over enumerated facts** | D-70 | A ratio hides a dropped bullet in a long section; membership does not. |

**Deprecated / outdated — do not use:**

- **`-Z shell-escape`** — arbitrary code execution on machine-influenced content. There is no legitimate use in this project.
- **`Tectonic -X <subcommand>` for the compile path** — V2 is not the default in 0.17.0. The V1 form is the documented default and has `--only-cached`, `--untrusted` and `--keep-logs` directly.
- **`texlive-full`** — ~4.2 GB, 8–15 min builds, for one CV. Curated subset only.
- **`yaml.load` with the default loader** — arbitrary object construction from document content. `yaml.safe_load` only.
- **`jinja2.autoescape=True` for TeX** — emits HTML entities and does not escape `%`, `_`, `#`, `$` (D-67).
- **`pip install python-jobspy`** and **APScheduler 4.x** — unchanged from STACK.md; listed only so the plan does not drift.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Tectonic 0.17.0's default bundle (the TeX Live bundle, currently `texlive2023`) **covers** `fontspec`, `paracol`, `tabularx`, `enumitem`, `titlesec`, `hyperref`, `geometry` | §Standard Stack, Pitfall 4 | If a package is missing, the fixture does not compile offline and D-75's "fails loudly with a documented rebuild" fires. **Directly testable before implementation:** `tectonic -X bundle search enumitem` (and one search per package) prints the filenames the bundle holds. This is the concrete bundle-coverage check the ROADMAP's research flag asks for, and it costs one command — run it first. |
| A2 | Tectonic's bundle contains the **font files** (`tex-gyre`, `lm`) needed for a by-filename `\setmainfont` | Pitfall 4 | If absent, the by-filename declaration fails and the fixture needs a font installed in the image plus `fc-cache`. Testable: `tectonic -X bundle search texgyre` and `... search lmroman`. |
| A3 | The `x86_64-unknown-linux-musl` static build needs **no** runtime shared libraries | §Standard Stack, D-73 | If it needs `libfontconfig`/`libharfbuzz`, `python:3.13-slim` lacks them and every compile fails at exec. The static-build claim here is third-party (a community installer README listing `libgraphite2/libharfbuzz/libicu` as statically linked); Tectonic's own Cargo feature list contains no fontconfig feature, which is suggestive but not conclusive. **Mitigation, not verification:** keep the binary's `ldd` output and `tectonic --version` in the build log, and make `Dockerfile` fail the build if the binary does not execute (the `tectonic --version` in the install RUN does this). |
| A4 | Whether Tectonic resolves fonts through **fontconfig** on Linux at all | Pitfall 4 | If it does, `python:3.13-slim` has neither fontconfig nor fonts, so *any* name-based font fails. The by-filename recommendation makes this moot; do not rely on name resolution anywhere. |
| A5 | `unicodedata.normalize("NFKC", "\ufb01") == "fi"` (and the other U+FB0x ligature forms decompose) | Pitfall 8, Code Examples | If wrong, ligature folding needs an explicit table and the comparison can produce false failures. **Verifiable in one line** in the container: `python -c "import unicodedata; assert unicodedata.normalize('NFKC','\ufb01')=='fi'"`. Fold this assertion into the test suite so the dependency is pinned by a test rather than a comment. |
| A6 | `pypdf` 6.19.0's `extract_text()` returns the PDF's text with the ligature/space loss described in Pitfall 8 | Pitfall 8 | If 6.19.0 is materially better, the `squash()` form is harmless extra safety. The predicate design does not depend on the severity of the loss — only on membership being exact. |
| A7 | The real `.tex` will be decomposable by the bounded parser | Pitfall 13, D-62 | This is the phase's whole point and it is **deliberately unresolved** (ARCHITECTURE Open Question 1). The fallback is hand-authoring `cv.yaml` once (CV-R1), which is an acceptable one-off cost. STATE.md blocking unknown #1 stays open. |
| A8 | `cv_versions.source` values are `import_tex` / `hand` and there is no CHECK constraint on the column | Pattern P9, Pitfall 6 | Read from `app/db/models.py:358-367` this session: `source = Column(String(16))` with no `__table_args__` on the class, so the column is unconstrained. Low risk, but the vocabulary is therefore app-level and unenforced by the DB — a `ValueError` in the repository is the only guard. |
| A9 | The research-plan seam (`gsd_run query research-plan`) is unavailable in this runtime | §Sources | The seam could not be invoked (the tool was denied when writing the plan input outside the workspace, and `docker`/`python` invocations are policy-denied here). Per the seam's own guidance the fallback is direct web research, which is what was done; per-provider confidence tiers were still obtained from `classify-confidence` (`context7` MEDIUM, `websearch` MEDIUM, `webfetch` LOW). A planner relying on the per-question cache will find it empty for this phase. |

## Open Questions

1. **O1 — What exactly is the `cv.yaml` top-level shape: `sections[]` or flat section keys?**
   - What we know: D-65 says "adopts the researched §7.3 `cv.yaml` shape as written — `schema_version: 1`, meta (including `max_pages`), identity/contact, experience, education, skills, projects". But the document it points at (ARCHITECTURE §7.2, lines 625-655) has `schema_version`, `meta` (`name`, `contact`), a `sections:` **list** whose items carry `id`/`title_key`/`order`/`entries`/`skills`, then `orgs`, `titles`, `gaps`. There are no top-level `experience`/`education`/`skills`/`projects` keys in that shape.
   - What's unclear: whether D-65's prose is a paraphrase of the *section names* (in which case the list shape is authoritative) or a deliberate flatter contract.
   - **Recommendation:** adopt the ARCHITECTURE list shape (`meta` + `sections[]` + `orgs` + `titles` + `gaps`), because the renderer needs `order`, the template needs `title`, and the patch engine needs `section_id` for `ReorderSection` — none of which the flat form provides. Treat D-65's noun list as naming the *kinds of section*, and record the reading in the CV-SPEC or the module docstring so a future reader does not re-litigate it. **Flag to the user in the plan's first checkpoint** because D-65 is marked "costly to reverse".
2. **O2 — `title_key` vs resolved `title`: one shape or two?**
   - What we know: ARCHITECTURE §7.2 uses `title_key: sec.experience` and explains it as "a KEY, not free text → rendered from a translation map". D-65's prose says "identity/contact" without mentioning keys or a translation map.
   - What's unclear: whether this phase ships a translation map (more machinery, and there is no second locale) or stores the resolved title directly.
   - **Recommendation:** store the **resolved title string** (`title: "Experience"`) in `cv.yaml` for `schema_version: 1`, and skip the translation map — it is speculative machinery for a single-locale v1, and adding a key→string map later is a backward-compatible `schema_version` bump. If the user wants the key form, it is a rename plus a small dict, not a redesign. Record the decision either way.
3. **O3 — Does the identity patch belong in this phase, or only in Phase 6?**
   - What we know: ARCHITECTURE §7.4 defines `apply_patch(facts, patch) -> RenderPlan` as `app/domain/cv.py`, and CV-R2's golden test needs an "identity patch" to render the base CV from `cv.yaml`. D-65 commits the patch types now.
   - What's unclear: whether this phase implements the whole patch engine or only the identity path. The phase boundary says "the tailoring patch engine … (Phase 6)" is out of scope, yet the golden test cannot exist without *some* render plan.
   - **Recommendation:** implement `apply_patch` with the **identity/ordering subset only** — enough to build a `RenderPlan` from `CvFacts` unchanged — and leave the mutating ops (`DropBullet`, `BulletWeight`, `Suggestion`, `DemoteBullet`) as declared types with `ValidationError`-raising stubs or as types declared for Phase 6. The golden test only needs the identity path. Do **not** build the Phase 6 patch application here.
4. **O4 — Does `cv.yaml` exist in the repo at all, given the fixture?**
   - What we know: D-58 gitignores `cv/cv.yaml`. D-68's golden test needs a `cv.yaml` whose render is compared byte-exactly.
   - **Recommendation:** put the fixture's fact store at `tests/fixtures/cv/awesomecv_standin.yaml` (committed) and keep `cv/cv.yaml` purely the human's gitignored file. The golden test loads the committed fixture; the real run loads `settings.cv_dir/cv.yaml`. This keeps the test hermetic and the real CV out of git, which is exactly D-58's intent — and it means the golden fixture is not accidentally the user's real data.
5. **O5 — Is `tectonic --version` a sufficient health probe?**
   - What it answers: "the binary is present and executable". What it does not answer: "the cache holds the needed packages". **Recommendation:** keep `--version` for the `/health` key (cheap, no compile on every request) and let the build-time prime be the cache proof, with D-75's loud failure as the runtime detector. Do not add a compile to `/health`.
6. **O6 — Where do the compiled artefacts live for this phase?**
   - What we know: `artifacts/<id>/` is a volume and `cv_artifacts` has `tex_path`/`pdf_path`/`compile_status`. But Phase 7 owns `applications`, and Phase 6 owns the artifact rows.
   - **Recommendation:** the golden and spike compiles write into pytest `tmp_path` / a spike temp dir. **Do not write `cv_artifacts` rows in this phase** — `cv_artifacts.listing_id` is the link Phase 6 fills, and a synthetic row would be a fake artifact. D-77 gives `cv_versions` a producer, and that is the only table this phase writes.

## Environment Availability

Probed this session on the research host (`/workspace/job-search`). Note the two distinct kinds of "not available" below — an observed absence versus a policy-blocked probe — because they carry different weight.

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `tectonic` | CV-05 (compile), the `latex` lane | **✗** (probed: `command -v tectonic` produced no output) | — | Run the lane in the container: `docker compose run --rm app pytest -m latex` (D-69). This is exactly why D-69 exists. |
| `docker` / `docker compose` | the D-69 gate, the D-76 fallback build, the prime | **not observed** — the probe was *denied by the agent's shell policy*, so this is **no observation**, not a confirmed absence | — | The operator must confirm `docker compose version` on the deployment host. `scripts/compose-smoke.sh` already fails fast on a missing `docker compose v2`. |
| `pdflatex` / `xelatex` | the `Dockerfile.texlive` fallback | **✗** (probed: `command -v pdflatex` produced no output) | — | Expected — the fallback is measured **once, by hand** in the built image (D-76), never on the dev host. |
| Python **3.13** | P1 (the container's interpreter) | **✗ on this host** — the working venv is `.venv/lib/python3.14/site-packages` (`.pyc` files `cpython-314`); `.venv-host` also exists | 3.14 locally | The image pins `python:3.13-slim` (`Dockerfile:25`). `docs/probes/README.md` already documents the interpreter/platform mismatch hazard for the live lane ("A venv built inside a musl container … cannot be reused on a glibc host"), and D-69's container lane sidesteps it entirely. **A locally-run Tectonic/Python test on a 3.14 venv is not evidence about the shipped image.** |
| `pypdf` | CV-03 (PDF text + page count) | **✗** (absent from `.venv/lib/python3.14/site-packages`, verified by listing) | — | Install behind the `checkpoint:human-verify` (see the Legitimacy Audit). Unit-testable without it if the extraction step is behind a tiny helper the tests can stub. |
| `pyyaml` | CV-01 (`cv.yaml` load) | **✓** (`.venv/lib/python3.14/site-packages/pyyaml-6.0.3.dist-info`) | 6.0.3 | Runtime manifest promotion required (it is dev-only today). |
| `unicodedata`, `hashlib`, `subprocess`/`asyncio` | normalisation, hashes, the engine | **✓** (stdlib) | 3.13/3.14 | — |
| **Network at image build** | D-74's cache prime (fetching the bundle once) | assumed available on the operator's host | — | If the build host is offline, the prime cannot run and `--only-cached` cannot work. Document this as a build-time requirement in the runbook, and note that the runtime itself is offline thereafter. |

**Missing dependencies with no fallback:**
- **Docker on the deployment host** — the D-69 gate and the D-76 measurement are impossible without it, and there is no CI. The operator must confirm it before the phase's verification step is planned as executable.

**Missing dependencies with fallback:**
- `tectonic` on the dev host → the container lane (this is the planned path, not a workaround).
- `pypdf` → absent locally; install behind the checkpoint, and stub it in the hermetic lane.
- `xelatex`/`pdflatex` → the TeX Live fallback is measured in its own image, once.

## Validation Architecture

`workflow.nyquist_validation` is not set to `false` (no `.planning/config.json` override was supplied with this phase's scope and the workflow default treats absent as enabled), so this section is included.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` **9.1.1** + `pytest-asyncio` **1.4.0** (`pyproject.toml:38-39`), `asyncio_mode = "auto"` |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]` (lines 49-58) |
| Quick run command | `pytest -q -m 'not live'` (the `addopts` default; hermetic, no engine, no network) |
| Full suite command | `pytest -q` — identical today, because every non-default lane is excluded by a marker |
| Container lane (the real CV-05/03 gate) | `docker compose run --rm app pytest -m latex` (D-69) |
| New marker to register | `latex: compiles LaTeX through the engine; requires the container image, operator-run only` |
| Existing marker / default exclusion, verbatim | `addopts = "-m 'not live'"` and `markers = ["live: contacts a live third-party board or the opencode server; operator-run only, never in CI"]` (`pyproject.toml:55-58`) |

**Marker mechanics:** adding `latex` to `markers` is not enough — the default lane must also exclude it, or the hermetic `pytest` pass tries to spawn a missing binary on every dev machine. Change `addopts` to `-m 'not live and not latex'` and have the `latex` tests additionally carry a `pytest.mark.skipif(shutil.which(settings.tectonic_binary) is None, ...)` guard (belt and braces, as D-69 requires). Keep the guard's skip reason naming the real gate command so a skipped run tells the reader what to do.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| CV-01 | `cv.yaml` loads into validated structured data; malformed input raises a path-qualified error naming the field; unknown keys are rejected (`extra="forbid"`); a missing file is loud | unit | `pytest tests/cv/test_factstore.py -x` | ❌ Wave 0 |
| CV-01 | IDs are derived deterministically and are unique; a text edit yields a **new** bullet ID and retires the old; a collision gets a recorded `-N` suffix | unit | `pytest tests/domain/test_cv_ids.py -x` | ❌ Wave 0 |
| CV-02 | `cv/base.tex` bytes are byte-identical before and after a full import → validate → render → snapshot cycle | unit | `pytest tests/cv/test_factstore.py::test_base_tex_is_never_modified -x` | ❌ Wave 0 |
| CV-02 | `.gitignore` contains `cv/` and `artifacts/` (so the real CV can never be committed) | unit | `pytest tests/test_cv_hygiene.py -x` | ❌ Wave 0 |
| CV-03 | `render(fixture cv.yaml)` is byte-identical to `tests/golden/base.rendered.tex` | golden, hermetic | `pytest tests/golden/test_render_bytes.py -x` | ❌ Wave 0 |
| CV-03 | The compiled PDF is fact-equivalent: every org, title, date and bullet token-shingle is present; a fact-count floor is asserted | integration (`latex`) | `docker compose run --rm app pytest tests/latex/test_fact_equivalence.py -m latex -x` | ❌ Wave 0 |
| CV-03 | **The predicate can fail**: the identical check over a mutated deep copy must report inequality (D-72) | integration (`latex`) | same file, same command | ❌ Wave 0 |
| CV-04 | Rendering twice yields identical bytes; no clock/random/uuid is reachable from the render path (AST scan) | unit | `pytest tests/golden/test_render_bytes.py tests/test_render_determinism.py -x` | ❌ Wave 0 |
| CV-05 | The engine compiles the fixture to a real PDF with `page_count >= 1`, offline (`--only-cached`), with no shell-escape | integration (`latex`) + build | `docker compose run --rm app pytest -m latex`; the build-time prime RUN is the image-level proof | ❌ Wave 0 |
| CV-05 | The engine is selectable through `Settings` + `get_latex_engine()`, and a test overrides it via `app.dependency_overrides` | unit | `pytest tests/test_latex_engine_seam.py -x` | ❌ Wave 0 |
| CV-05 | `/health` reports a `tectonic` key and still answers HTTP 200 with the engine absent | unit | `pytest tests/api/test_health.py -x` (extend the existing file) | ✅ exists, extend |
| CV-06 | Every one of the ten TeX-special characters is escaped; backslash is escaped first; `""` is total; `Markup` is passed through unchanged by `finalize` | unit | `pytest tests/domain/test_tex_escape.py -x` | ❌ Wave 0 |
| CV-06 | A hostile bullet (`R&D`, `20%`, `_p99_`, `C++`, `#1`, `$5`, `~`, `^`, `{}`) compiles and its text survives extraction | integration (`latex`) | `docker compose run --rm app pytest -m latex -k hostile` | ❌ Wave 0 |
| CV-R7 | `sanitise_preamble` comments out unguarded `\pdf*` primitives, leaves guarded ones alone, and reports every removal | unit | `pytest tests/domain/test_tex_preamble.py -x` | ❌ Wave 0 |
| PLAT-04 | Every new ceiling is a `Settings` field, is environment-tunable, and no distinctive literal remains in `app/latex` or `app/cv` | unit | `pytest tests/test_config.py -x` (extend `REQUIRED_SETTINGS_FIELDS`, `LIMIT_FIELDS`, `SCANNED_DIRS`) | ✅ exists, extend |
| D-59 / D-60 | The bounded parser extracts sections/entries/bullets from the fixture, and reports every macro it did not understand with a count | unit | `pytest tests/cv/test_import_tex.py -x` | ❌ Wave 0 |
| D-77 | `snapshot_version` writes `schema_version` as the **string** `"1"`, clears the previous `is_current`, never commits, and leaves exactly one current row | integration (DB) | `pytest tests/db/test_cv_repo.py -x` | ❌ Wave 0 |
| P2 / Pitfall 5 | `subprocess` is confined to the declared process hosts and `app/latex` is a deliberate one | unit | `pytest tests/test_import_discipline.py -x` (extend) | ✅ exists, extend |
| Pitfall 10 | `TexLiveEngine`'s argv is `xelatex`, not `pdflatex` (a unit assertion on `_argv`) | unit | `pytest tests/test_latex_engine_seam.py -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest -q -m 'not live and not latex'` — under 30 seconds, no engine, no network, no DB writes outside `tmp_path`.
- **Per wave merge:** `pytest -q` (the full hermetic suite; still no `latex`/`live` lane).
- **Phase gate (before `/gsd-verify-work`):** hermetic suite green **and** `docker compose run --rm app pytest -m latex` green **and** the verdict doc at `docs/probes/2026-09-21-cv-tex-spike.md` written with its `PARTIAL` marker and its UNRESOLVED section (D-62). The texlive fallback's one hand-run is recorded there too (D-76).
- **Not sampled:** the live scraper lane (`-m live`) and any real-CV path. Both are operator-run and out of this phase's gate.

### Wave 0 Gaps

- [ ] `tests/fixtures/cv/awesomecv_standin.tex` — the D-61 fixture; **blocking for every `latex`-marked test and for the build-time prime (D-74)**
- [ ] `tests/fixtures/cv/awesomecv_standin.yaml` — its hand-curated fact store (Open Question O4)
- [ ] `tests/golden/base.rendered.tex` — the byte-exact baseline; generated once from a *reviewed* render, then committed (never auto-overwritten by the test)
- [ ] `tests/golden/__init__.py`, `tests/cv/__init__.py`, `tests/latex/__init__.py` — the repo's test packages all have `__init__.py`; keep the convention
- [ ] `pyproject.toml` — register the `latex` marker and change `addopts` to `-m 'not live and not latex'`
- [ ] `app/domain/tex.py`, `app/domain/cv.py` — the pure layer everything else imports
- [ ] `app/latex/base.py`, `app/latex/__init__.py`, `app/latex/env.py`, `app/latex/render.py`, `app/latex/compile.py`, `app/latex/templates/cv.tex.jinja`
- [ ] `app/cv/factstore.py`, `app/cv/import_tex.py`, `app/cv/__init__.py`
- [ ] `app/db/repositories/cv_repo.py` + `tests/db/test_cv_repo.py`
- [ ] Framework install: none — `pytest`/`pytest-asyncio` are already dev dependencies. **The two new runtime deps (`pypdf`, `pyyaml`) need the `checkpoint:human-verify` first** (Legitimacy Audit).
- [ ] `Dockerfile` Tectonic install + prime layers; `Dockerfile.texlive`; `compose.yml` volumes/passthroughs; `.gitignore` entries; `.gitattributes` line-ending pins

*(No existing test infrastructure covers any phase requirement: a repo-wide grep for `CvFacts`, `factstore`, `cv.yaml`, `base.tex`, `import_tex`, `escape_tex` and `RenderPlan` across `app/`, `tests/` and `docs/` returned **zero** matches this session. This phase's entire test surface is Wave 0.)*

## Security Domain

`security_enforcement` is enabled for this project (the Phase 3 notes in STATE.md record it as enabled and flag that `03-SECURITY.md` is missing). This phase is included.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth in v1 by decision; the `current_user` seam is untouched by this phase. |
| V3 Session Management | no | No sessions. |
| V4 Access Control | no | Single local user; no new route. `/health` keeps its existing dependency chain. |
| V5 Input Validation | **yes** | Pydantic `extra="forbid"` on every CV model with no default-filling (D-66); `yaml.safe_load` only; bounded TeX parsing (`tex_import_max_lines`/`_max_depth`); `escape_tex` at the Jinja `finalize` choke point (D-67). Two distinct boundaries: `cv.yaml` (semi-trusted, human-authored, local) and *the future* untrusted listing text flowing through the same renderer in Phase 6 — which is why the choke point must be non-bypassable **now**. |
| V6 Cryptography | **partly** | No cryptography is implemented. `hashlib.sha256` (stdlib) provides artefact identity only (`tex_hash`/`pdf_hash`), never a secret. **Never hand-roll a hash.** If a secret ever appears here, stop and plan it properly. |
| V12 File uploads / V14 Configuration | **yes (V14)** | The engine, its binary path, its cache path, its timeout and its offline mode are all `Settings` fields (PLAT-04), so the security-relevant configuration is inspectable and overridable without a code change. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| **LaTeX shell-escape RCE** — a preamble command (`\write18`, `\input{|...}`, `minted`) executes arbitrary code when the engine is invoked on a document that carries an untrusted fragment | Elevation of Privilege | Three layers, all mandatory: **never** pass `-Z shell-escape`; **always** pass `--untrusted` (disables shell-escape and other insecure features "regardless of the presence of `-Z shell-escape` or any other options"); **and** set `TECTONIC_UNTRUSTED_MODE=1` in the image so a future argv edit cannot undo it. Never render untrusted input with `shell=True` or an interpolated command string. |
| **YAML deserialisation RCE** — `yaml.load` with the default loader constructs arbitrary Python objects from `!!python/object` tags | Elevation of Privilege | `yaml.safe_load` **only**. Add a grep-style guard test if the codebase ever grows a second YAML reader. |
| **Subprocess argv injection** — building the compile command as a string, or passing document content into argv | Tampering / Elevation | `asyncio.create_subprocess_exec(*argv)` with a fixed argv list; the only variable in it is a path the tool itself derived from `settings.artifacts_dir` + an integer id. |
| **Path traversal through artefact paths** — a listing id or a user-supplied filename escaping the artefacts volume | Tampering | Derive every output path from the DB integer id + a constant filename, never from a request parameter. Assert the resolved path is inside `settings.artifacts_dir` before writing. |
| **Denial of service through a pathological document** — deep nesting, a million `\item`s, or an engine that never terminates | Denial of Service | `tex_import_max_lines` / `tex_import_max_depth` bounds (Settings); `tectonic_timeout_seconds` on the subprocess; never compile on the event loop (Pitfall 14). |
| **Resource exhaustion via the cache directory** — Tectonic creating its cache with `0777` when there is no home directory (issue #1144) | Elevation / DoS | Set `TECTONIC_CACHE_DIR` explicitly at build time to a root-owned path inside the image, so the fallback never engages; document the expected ownership in the runbook. |
| **Untrusted listing text reaching the PDF** — the Phase 6 concern that Phase 4 must make impossible in advance | Tampering | The `finalize` choke point (D-67) plus the structural no-free-text rule on the patch schema (ARCHITECTURE §7.3). Note the continuity: SRC-08 sanitises untrusted text at the *ingest* boundary; CV-06 escapes it at the *render* boundary. Both are needed — escaping is the last line, not the only one. |
| **Prompt injection through the fact store** — a CV fact that reaches an LLM prompt (Phase 5/6) carrying instructions | Spoofing | Out of this phase's implementation, but the ID scheme (D-63) is what makes it addressable: facts are enumerated ids, so "the model can only pick from an enumeration" (STACK.md Q6) rather than receiving free text. Do not add a free-text field to `cv.yaml` beyond `bullet.text`, which is itself immutable and human-authored. |
| **Accidental disclosure of the real CV** — the CV committed to git, or a listing/recruiter's PII written into the committed verdict doc | Information Disclosure | `.gitignore` gains `cv/` and `artifacts/` (D-58) with a guard test; the verdict doc carries **counts and package names only**, never CV content (the Phase 1 probe runbook's rule: "Never paste listing text into the document … the document is committed"). |

### Security-specific plan obligations

1. The `--untrusted` / `TECTONIC_UNTRUSTED_MODE` pair must be asserted by a **test** on `TectonicEngine._argv()` and by a `grep` assertion over the `Dockerfile`, not only stated in prose.
2. `-Z shell-escape` must be absent from the entire repo — a one-line guard test over `app/` and `Dockerfile*` makes the "never" mechanical (the same prose-as-test idiom as `tests/test_no_credentials.py`).
3. The verdict doc must be reviewed for content before commit: it names packages, versions, counts and commands — never CV text.

## Sources

### Primary (HIGH confidence)

- **Tectonic — V1 CLI reference** (`tectonic-typesetting.github.io/book/latest/ref/v1cli.html`) — the `-C | --only-cached` flag ("Use only resource files cached locally") and the full V1 option list. Read this session.
- **Tectonic — V2 CLI status** (`.../book/latest/ref/v2cli.html`, page dated 2026-07-31) — "The V1 interface is the default"; `-X` activates V2, `-Y` selects V1 explicitly. Read this session.
- **Tectonic — `-X compile` reference** (`.../book/latest/v2cli/compile.html`) — the `--only-cached` description ("refuse to connect to the network when searching for support files"), `--untrusted` ("Input is untrusted — disable all known-insecure features"), `--outdir`, `--keep-logs`, and the `TECTONIC_UNTRUSTED_MODE` environment variable. Read this session.
- **Tectonic — Build Your First Document** (`.../book/latest/getting-started/first-document.html`) — the cache section: `TECTONIC_CACHE_DIR` ("If you need to change the location of the cache, you can do that by setting the environment variable `TECTONIC_CACHE_DIR` to the path of a directory"). Read this session.
- **Tectonic — `-X bundle search`** (`.../book/latest/v2cli/bundle.html`) — "Print out the names of files in the current document's backing bundle, potentially with filtering"; example `tectonic -X bundle search minted` → `minted1.sty tcbminted.code.tex minted.4ht minted.sty`. This is the concrete bundle-coverage check for assumption A1/A2. Read this session.
- **Tectonic — GitHub Releases API, tag `tectonic@0.17.0`** — published `2026-07-27T01:00:41Z`; asset `tectonic-0.17.0-x86_64-unknown-linux-musl.tar.gz`, 10,151,914 bytes, sha256 `8533d07f9ccbd7a65824b9e0459041bca34af1eb33daba48f59215593753a3b7`. Fetched this session.
- **Tectonic — CHANGELOG 0.15.0** — "A new `--untrusted` argument to the V1 CLI and `tectonic -X build` disables the use of shell-escape, and any other known-insecure features, regardless of the presence of `-Z shell-escape` or any other options"; plus the `TECTONIC_UNTRUSTED_MODE` equivalence. Fetched this session.
- **Tectonic — CHANGELOG 0.17.0** — release contents (segfault fixes, Unicode-only cmap support, "Change bundle caching to only re-check remote once per week"); **no** symbolic-font-name fix. Fetched this session.
- **Tectonic — bundles README** (`github.com/tectonic-typesetting/tectonic/blob/master/bundles/README.md`) — the bundle is built from a TeX Live tarball; the available bundle is `texlive2023` (`texlive2023-20230313`); the `FILELIST`/`SEARCH` mechanism. Read this session.
- **Jinja2 3.1.6 — installed compiler source** (`.venv/lib/python3.14/site-packages/jinja2/compiler.py`), read this session: lines **1483-1487** (`if frame.eval_ctx.volatile: … elif frame.eval_ctx.autoescape: self.write("escape(") else: self.write("str(")`) and lines **1470-1472** (`# Template data doesn't go through finalize.` / `if isinstance(node, nodes.TemplateData): return str(const)`). This is the direct verification of D-67's mechanism.
- **Jinja2 API docs** (`jinja.palletsprojects.com/en/stable/api`) — `finalize`: "A callable that can be used to process the result of a variable expression before it is output. For example one can convert `None` implicitly into an empty string here."; `autoescape` defaults to `False`.
- **pypdf — PyPI JSON API** — latest 6.19.0, `requires_python >=3.9`, `license_expression` BSD-3-Clause, source `github.com/py-pdf/pypdf`. Fetched this session.
- **pypdf — Extract Text from a PDF** (`pypdf.readthedocs.io/en/latest/user/extract-text.html`, multiple versions 3.12–6.14) — the documented open question: "Ligatures: The Unicode symbol U+FB00 is a single symbol ﬀ for two lowercase letters 'f'. Should that be parsed as the Unicode symbol 'ﬀ' or as two ASCII symbols 'ff'?" and "Whitespaces: How many new lines should be extracted …". Read this session.
- **Repo files read this session** (all quotes verbatim in the sections above): `app/db/models.py` (lines 358-402), `app/config.py`, `app/llm/base.py`, `app/llm/__init__.py`, `app/api/health.py` (lines 106-112), `app/domain/sanitize.py`, `app/web/template_env.py`, `app/web/filters.py`, `app/pipeline/run.py`, `app/db/repositories/llm_call_repo.py`, `Dockerfile`, `compose.yml`, `.gitignore`, `.env.example`, `requirements.txt`, `pyproject.toml`, `tests/test_config.py` (lines 61-107), `tests/test_import_discipline.py` (lines 14-16, 134-148), `tests/test_dependency_pins.py`, `tests/conftest.py`, `tests/api/test_health.py`, `tests/db/test_migration_contract.py`, `docs/probes/README.md`, `docs/probes/2026-09-15-scraper-survival.md`, `scripts/compose-smoke.sh`, `04-CONTEXT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, `ARCHITECTURE.md` §3/§7/§10/§14.3/§16/§17, `STACK.md` Q6, `FEATURES.md` TS-11/TS-12, `PITFALLS.md` M1/M3.

### Secondary (MEDIUM confidence)

- **`gsd-tools query package-legitimacy check --ecosystem pypi pypdf pyyaml`** — returned `SUS` for both (`too-new`, `unknown-downloads`), plus registry existence, publish dates and repo URLs. Run this session. Its verdicts drive the `checkpoint:human-verify` requirement.
- **`gsd-tools query classify-confidence`** — `context7` MEDIUM (verified), `websearch` MEDIUM (verified), `webfetch` LOW. Run this session.
- **Tectonic issue #372** (`fontspec error: "font-not-found"`) — maintainer `pkgw`: "at the moment Tectonic can only identify fonts based on their filenames, not their symbolic names … specifying it as `texgyrepagella-regular.otf` might work instead", with a working `\setmainfont` face map. Fetched this session.
- **Tectonic issue #1118** (`Fontspec cannot find fonts by name`, open since 2023-11-18) — the minimal repro and the by-filename workaround; no fix version, no linked PR. Fetched this session.
- **Tectonic issue #1144** (`Make cache directory configurable/disableable`) — "even if there is no home directory, Tectonic will attempt to create the home directory, and will use `0777` permissions by default".
- **Tectonic issue #965** (`Feature: font packages`) — the bundle-vs-system-font architecture discussion, including the `tectonic -X bundle search NotoSans` workflow. MEDIUM.
- **`dxjoke/tectonic-docker` Dockerfile** — the cross-stage cache copy (`COPY --from=builder /root/.cache/Tectonic/ /root/.cache/Tectonic/`) and the runtime `libfontconfig1 libgraphite2-3 libharfbuzz0b libicu*` install set. Used as corroboration for the cache path and the fontconfig question, not as an authority.
- **`sjp/tectonic-feature` README** — "The musl builds are statically linked, so they have no runtime shared-library dependencies (e.g. libgraphite2, libharfbuzz, libicu) and run on slim base images." Community source; drives assumption A3, which is why A3 is flagged rather than trusted.
- **pypdf issues #17 and #1328, discussion #2038** — the missing-space class of extraction bug. MEDIUM.
- **TexSoup** — PyPI 0.3.3 (2026-04-05), BSD-3-Clause, `github.com/alvinwan/TexSoup`, ~325★, with an arXiv-benchmark claim (50/50 parsed vs plasTeX 11/50, LaTeXML 29/50). Listed as the documented escalation, not a recommendation.
- **R's `refman.top`** (SVN mirror, read via web search) — a real-world preamble guarding exactly `\pdfminorversion`, `\pdfcompresslevel`, `\pdfobjcompresslevel` behind `\ifnum\pdfoutput>0`. Corroborates both the primitive list and the "guarded occurrences are common, so leave them alone" design.

### Tertiary (LOW confidence)

- The exact behaviour of Tectonic's font lookup **on Linux with fontconfig** in 0.17.0 — unresolved (assumptions A3/A4). No binary is installed in this research environment, so this is deliberately left as an unmeasured question for the spike.
- Tectonic's default bundle **contents** for the specific six-package set — inferred from "the bundle is built from a TeX Live tarball (texlive2023)" plus the fact that each package is a standard TeX Live package. **Not verified by search**; assumption A1 carries the one-command verification.
- Whether `python:3.13-slim` ships fontconfig — inferred from the slim base and from the third-party image installing it explicitly. Not verified.

## Metadata

**Confidence breakdown:**

- **Standard stack: HIGH.** Tectonic's version, release date, asset name and SHA256 come from the project's own GitHub Releases API payload; the flag names come from the project's own book; the Jinja2 mechanism comes from reading the installed compiler source. `pypdf`/`pyyaml` versions come from PyPI. The only soft spot is the `SUS` legitimacy heuristic, which is a false-positive risk on a mature package and is handled by the mandated checkpoint rather than by a confidence downgrade.
- **Architecture: HIGH on mechanics, MEDIUM on the `.tex` decomposition.** The engine seam shape is copied from an existing in-repo pattern; the escaping choke point is verified against Jinja's compiler; the repository pattern is copied from `llm_call_repo`. The decomposition question (A7) is unmeasurable by design (D-62) and is reported as such rather than estimated.
- **Pitfalls: HIGH on the mechanical ones, MEDIUM on fonts.** The `subprocess` guard break, the `schema_version` type mismatch, the missing-space extraction loss, the offline flag and the cache-layer boundary are all verified against source. The font-resolution pitfall is well-evidenced but its precise 0.17.0 behaviour on Linux remains unmeasured — which is exactly why the recommendation is the engine-portable by-filename form plus a spike measurement rather than a claim.
- **Validation: HIGH.** The test map is built from existing repo idioms (`-m 'not live'` lanes, `skipif` guards, AST-scan guards, mutation controls that prove a guard can fail), so nothing in it is novel infrastructure.

**Research date:** 2026-09-21
**Valid until:** ~2026-10-21 for the repo-side and Jinja2 findings (stable). **Re-verify at implementation time, before pinning:** the Tectonic release asset SHA256 and the `pypdf` version — both are exactly the kind of value that moves, and both are pinned in a file where a stale value is a build break or a silent behaviour change. The Tectonic flag names (`--only-cached`, `--untrusted`) and the V1-is-default status should be confirmed with `tectonic --version` and `tectonic --help` in the built image, as D-75 already requires.

## RESEARCH COMPLETE

**Phase:** 4 — CV Fact Store + LaTeX Compile Spike
**Confidence:** MEDIUM-HIGH
**Primary recommendation:** Build the pure layer first (`app/domain/tex.py`, `app/domain/cv.py`), then the fact store and its two golden tests, then the engine seam and the container, then the real-document spike as a documented partial verdict plus trigger. Two things must not be missed: widen `tests/test_import_discipline.py` for `app/latex`'s legitimate `subprocess`, and declare the fixture's font by filename rather than by name.

### Key Findings

1. **`tests/test_import_discipline.py` is a global `subprocess` guard with a single `app/llm` exception.** `app/latex/compile.py` will fail the build on its first task unless the guard is deliberately widened — with the same "the exclusion is deliberate, not accidental" mirror test the `app/sources` httpx carve-out already carries.
2. **The open Tectonic questions are now closed by verified values:** the offline flag is `-C`/`--only-cached`; the V1 CLI is the default in 0.17.0; the cache is governed by `TECTONIC_CACHE_DIR` (~`/root/.cache/Tectonic` on Linux); the bundle can be inspected with `tectonic -X bundle search <term>`; and `--untrusted` + `TECTONIC_UNTRUSTED_MODE` are a stronger, argv-proof control than merely omitting `-Z shell-escape`.
3. **Fonts are the sharpest unmeasured edge.** Tectonic resolves fonts by filename, not by symbolic name (maintainer answer in #372; still-open #1118; no fix in the 0.17.0 changelog). Declaring the font by filename with an extension+face map works in Tectonic *and* XeLaTeX, which makes one fixture serve both engines. `python:3.13-slim` has no fonts and no fontconfig, so name-based resolution is the wrong bet regardless.
4. **D-67's choke point is verified, and better than assumed.** Jinja emits `str(environment.finalize(<expr>))` under `autoescape=False`, and literal template text never reaches `finalize` — so one `finalize` escapes every interpolated value and leaves the template's own LaTeX alone. The `Markup` opt-out is ours to implement inside `finalize`, not a Jinja feature.
5. **D-70's predicate needs one refinement to avoid false failures.** `pypdf` drops spaces and does not expand ligatures, so the shingle membership check must run on a whitespace-stripped canonical form (`squash`) after NFKC folding — otherwise a *correct* render fails. The predicate stays strict membership; it never becomes a ratio.
6. **Two small type/plumbing traps:** `cv_versions.schema_version` is `String(32)` while `cv.yaml` says `schema_version: 1` (store `str(...)`); and `.gitignore` currently has no `cv/` entry, so the phase's first `git add -A` would commit the user's real CV.

### Process note

The `research-plan` seam could not be invoked in this runtime (writing the plan input outside the workspace was denied; `docker`/`python` invocations are policy-denied here). Per the seam's own fallback guidance the research was done directly against primary sources, and `classify-confidence` was still used for provider tiers. A planner expecting a populated per-question research cache for this phase will find it empty.

### File Created

`.planning/phases/04-cv-fact-store-latex-compile-spike/04-RESEARCH.md`

### Open Questions

- **O1** the `cv.yaml` top-level shape (`sections[]` vs flat section keys — D-65's prose and the document it cites disagree); **O2** `title_key` vs a resolved `title` string; **O3** how much of `apply_patch` ships here (recommendation: the identity/ordering subset only); **O4** where the committed fixture's fact store lives (recommendation: `tests/fixtures/cv/`); **O5** `--version` as the `/health` probe (recommendation: yes, with no compile on the health path); **O6** no `cv_artifacts` rows this phase (recommendation: `cv_versions` only). O1 is the one worth a user checkpoint, because D-65 marks it costly to reverse.

### Ready for Planning

Research complete. The planner can now create PLAN.md files. The plan must contain, per the ROADMAP's research flag: a spike task on one section, the Tectonic bundle-coverage check (`tectonic -X bundle search <pkg>` per fixture package, plus `tectonic --help` for the flag confirmation), and a pdfTeX-primitive/bibliography check — all before Phase 6 is estimated.
