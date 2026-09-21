---
phase: 04-cv-fact-store-latex-compile-spike
verified: 2026-09-21T15:58:22Z
status: human_needed
score: 20/29 must-haves verified
covered_files:
  - .planning/REQUIREMENTS.md
  - .planning/phases/04-cv-fact-store-latex-compile-spike/04-01-PLAN.md
  - .planning/phases/04-cv-fact-store-latex-compile-spike/04-01-SUMMARY.md
  - .planning/phases/04-cv-fact-store-latex-compile-spike/04-02-PLAN.md
  - .planning/phases/04-cv-fact-store-latex-compile-spike/04-02-SUMMARY.md
  - .planning/phases/04-cv-fact-store-latex-compile-spike/04-03-PLAN.md
  - .planning/phases/04-cv-fact-store-latex-compile-spike/04-03-SUMMARY.md
  - .planning/phases/04-cv-fact-store-latex-compile-spike/04-04-PLAN.md
  - .planning/phases/04-cv-fact-store-latex-compile-spike/04-04-SUMMARY.md
  - .planning/phases/04-cv-fact-store-latex-compile-spike/04-05-PLAN.md
  - .planning/phases/04-cv-fact-store-latex-compile-spike/04-05-SUMMARY.md
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
  - Dockerfile
  - Dockerfile.texlive
  - .env.example
  - .gitattributes
  - .gitignore
  - pyproject.toml
  - requirements.txt
  - scripts/cv-tex-spike.sh
  - docs/runbook-latex-compile.md
  - docs/probes/2026-09-21-cv-tex-spike.md
  - docs/probes/README.md
  - tests/api/test_health.py
  - tests/cv/test_factstore.py
  - tests/cv/test_import_tex.py
  - tests/db/test_cv_repo.py
  - tests/domain/test_cv_ids.py
  - tests/domain/test_tex_escape.py
  - tests/domain/test_tex_preamble.py
  - tests/fixtures/cv/awesomecv_standin.tex
  - tests/fixtures/cv/awesomecv_standin.yaml
  - tests/golden/base.rendered.tex
  - tests/golden/test_render_bytes.py
  - tests/latex/test_compile.py
  - tests/latex/test_fact_equivalence.py
  - tests/test_config.py
  - tests/test_cv_hygiene.py
  - tests/test_cv_tex_spike_docs.py
  - tests/test_cv_tex_spike_script.py
  - tests/test_dependency_pins.py
  - tests/test_deploy_manifest.py
  - tests/test_import_discipline.py
  - tests/test_latex_engine_seam.py
  - tests/test_latex_lane_contract.py
  - tests/test_render_determinism.py
covered_digest: null # gsd-tools / verification.fingerprint unavailable in this environment — deliberately not hand-written (#4155)
behavior_unverified: 5
overrides_applied: 0
behavior_unverified_items:
  - truth: "The operator can get a real PDF out of one command: the committed `.tex` fixture compiles through Tectonic inside the image, the build-time prime proves the engine works and seeds the package cache, and the first runtime compile runs with the network refused."
    test: "docker compose run --rm app pytest -m latex -k fixture_compiles -x after a successful docker compose build"
    expected: "at least one passed test; a real %PDF artefact with page_count >= 1"
    why_human: "Docker and the Tectonic binary are absent in this environment; the 10 latex-marked nodes are collected and SKIPPED, never run. Presence of the Dockerfile install/prime RUN and the argv is not a compile."
  - truth: "`CompileResult` is a value, never an exception: a missing binary, a non-zero engine exit, a timeout, or a missing output file each produce `ok=False` with a named `error_kind`, and no compile path raises."
    test: "pytest -m latex tests/latex/test_compile.py::test_every_engine_failure_is_a_value_not_an_exception"
    expected: "not_found / non-zero-exit / timeout / no_output each returned as ok=False with the matching error_kind"
    why_human: "Only the `not_found` class is behaviourally exercised hermetically (tests/test_latex_engine_seam.py). The exit/timeout/no_output classes are asserted only by the skipped lane test; code inspection shows the branches but does not exercise them."
  - truth: "The artefact a human and an ATS actually read is the one the tool measured: the human's `.tex` fixture and the rendered `.tex` are each compiled, their extracted text is reduced to a canonical form, and every organisation, title, date and bullet token-shingle is proven present on both sides — with a floor proving a minimum number of facts were compared."
    test: "docker compose run --rm app pytest -m latex tests/latex/test_fact_equivalence.py"
    expected: "both compiles succeed; facts_present_in returns True for the human PDF and the rendered PDF; facts_compared >= 6"
    why_human: "No PDF is produced in this environment, so the extracted-text half of the golden pair has never run. The hermetic half (byte-exact renderer golden) is green but cannot substitute for it."
  - truth: "The reproduction check can fail: the identical comparison over a mutated deep copy of the facts reports inequality."
    test: "docker compose run --rm app pytest -m latex tests/latex/test_fact_equivalence.py::test_the_check_fails_on_a_mutated_fact_store"
    expected: "facts_present_in(facts, mutated_text) is False and the original bullet is named in `missing`"
    why_human: "The mutation control itself requires a compiled PDF; the pure predicate's discriminating power is proven at string level (tests/domain/test_tex_escape.py) but the end-to-end control is skipped."
  - truth: "A hostile bullet survives the round trip: content carrying &, %, _, #, $, ~, ^ and brace characters compiles and its text is still found in the extracted PDF text."
    test: "docker compose run --rm app pytest -m latex tests/latex/test_fact_equivalence.py::test_a_hostile_bullet_survives_the_engine_and_extraction"
    expected: "the compile succeeds and the hostile bullet is found in the extracted text"
    why_human: "Escaping is proven at the string and template level hermetically; the escape-through-the-engine-and-extraction invariant is not exercised without an engine."
human_verification:
  - test: "Run the container LaTeX lane: `docker compose run --rm app pytest -m latex`"
    expected: "The 10 latex-marked nodes run (not skipped) and report at least one passed with no failures; offline compile of the fixture produces a real PDF and both fact-equivalence compiles pass."
    why_human: "Docker and Tectonic are absent here; the lane is collected-and-skipped (10 skipped). An UNRUN check must not be recorded as passed."
  - test: "Confirm the installed engine's own option names (D-75): `docker compose run --rm app tectonic --help`"
    expected: "The help output contains `--only-cached` and `--untrusted`. If it does not, the argv in app/latex/compile.py is wrong and must be corrected, not the assertion relaxed."
    why_human: "The flag names are currently carried from the constants in compile.py; the installed binary has never been read in this environment."
  - test: "Bundle coverage per preamble package: `docker compose run --rm app tectonic -X bundle search <package>` for each of fontspec, geometry, tabularx, paracol, enumitem, titlesec, hyperref"
    expected: "Each package is reported as held by the bundle (or the missing ones are added to the build-time prime and the image rebuilt)."
    why_human: "Requires the pinned binary inside the image."
  - test: "Measure the TeX Live fallback (D-76) or leave it unclaimed: `docker build -f Dockerfile.texlive -t job-search-copilot:texlive .` then compile the fixture with `LATEX_ENGINE=texlive`"
    expected: "Image size, build duration, compile argv and page count recorded in docs/probes/2026-09-21-cv-tex-spike.md §5 — or §5 stays 'Not taken' and the fallback stays not-claimed (which is its current, honest state)."
    why_human: "Building a second multi-GB image is a one-off operator action; the verdict correctly records the measurement as NOT TAKEN rather than implying it."
  - test: "Take the real-document measurement that closes STATE blocking unknown #1: `mkdir -p cv artifacts`, place the real LaTeX CV at `cv/base.tex`, run `bash scripts/cv-tex-spike.sh`, then append the counts and unresolved names to docs/probes/2026-09-21-cv-tex-spike.md §4"
    expected: "Sections/entries/bullets/lines counts, unresolved macro names with counts and lines, the truncation flag, and per-package bundle coverage are recorded — or the document stays PARTIAL and the blocking unknown stays open. Counts/names only; never CV text."
    why_human: "The real document is deliberately not in this repository (D-58); every current number measures the synthetic stand-in. SC-4 is satisfied only as scoped by D-62 (partial verdict + trigger), so the real decomposition remains unproven."
  - test: "Attest the package-legitimacy decision (04-01 D6): confirm the human saw and approved `pypdf==6.19.0` (source https://github.com/py-pdf/pypdf, pure-Python wheel) and `pyyaml==6.0.3` before install"
    expected: "The approval is genuine and predates the manifest edits; the recorded string `approved: pypdf=6.19.0 pyyaml=6.0.3` reflects a real human decision."
    why_human: "Legitimacy checkpoints are never auto-approvable; the gate is an out-of-band human signal that no test can verify."
---

# Phase 04: CV Fact Store + LaTeX Compile Spike — Verification Report

**Phase Goal:** ``cv.yaml`` exists and reproduces the human's CV fact-for-fact, and Tectonic compiles the real `.tex` inside the container — retiring the project's largest unquantified cost.
**Verified:** 2026-09-21T15:58:22Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Method note (what this environment could not do)

Docker and the Tectonic binary are **absent**. The `latex` pytest lane was
collected and **SKIPPED** (10 nodes, reason names the gate command) — this is the
opposite of deselection and is itself asserted hermetically by
`tests/test_latex_lane_contract.py`, but a skipped node is **not** a pass. The
four operator-only checks in `04-VALIDATION.md` (`docker compose run --rm app
pytest -m latex`; `tectonic --help` for D-75; `tectonic -X bundle search`; the
`Dockerfile.texlive` build for D-76) are recorded **UNRUN**, not passed. The
hermetic default lane was re-run for this verification:
`.venv/bin/python -m pytest -q` → **961 passed, 14 deselected**.

The phase's own record is honest about this: `04-VALIDATION.md` marks rows
`04-02-01` and `04-04-01` as `⚠️ operator` and states "Do not read this map as
claiming those two are green." This report agrees.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 04-01.1 | `pypdf` pinned/importable; `pyyaml` promoted dev→runtime | ✓ VERIFIED | `.venv/bin/python` reports `pypdf 6.19.0`, `yaml 6.0.3`; `pyproject.toml:31,34`; `requirements.txt:22,26` |
| 04-01.2 | Both manifests mirror the two pins; `pyyaml` absent from `[dev]` | ✓ VERIFIED | `[project.optional-dependencies].dev` holds only pytest/pytest-asyncio/ruff; `test_pinned_package_is_declared_exactly` green |
| 04-01.3 | `latex` marker registered and excluded; default lane green | ✓ VERIFIED | `pyproject.toml:61-65` `-m 'not live and not latex'`; `test_the_latex_marker_is_registered_and_excluded`; 961 passed, 14 deselected |
| 04-01.4 | `app/latex/__init__.py` package marker existed before the wave-2 code | ✓ VERIFIED | `git show 320e2e2 --stat` created it as a 7-line docstring-only file; 04-02 later filled it (b4d3b42) |
| 04-01.5 | A human confirmed each SUS package's name/version/source before install | ? UNCERTAIN | Human gate (`checkpoint:human-verify`, D6); only the SUMMARY records `approved: pypdf=6.19.0 pyyaml=6.0.3` — not programmatically verifiable → human item |
| 04-01.6 | No package other than the two named was added/upgraded/removed | ✓ VERIFIED | `git show 320e2e2` touches only `pyproject.toml`/`requirements.txt` for deps; both manifests add exactly `pypdf` + `pyyaml` |
| 04-02.1 | One command yields a real offline PDF from inside the image | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Dockerfile install+`ENV`+prime committed and reads correctly (`Dockerfile:63-101`), but **UNRUN** — no container runtime/engine here |
| 04-02.2 | `CompileResult` is a value, never an exception (4 failure classes) | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | `_compile` branches for not_found/exit_*/timeout/no_output present (`compile.py:160-223`); hermetic seam exercises only `not_found`; the full test is skipped |
| 04-02.3 | The engine used matches `LATEX_ENGINE`; DI-overridable | ✓ VERIFIED | `get_latex_engine()` selects exactly one and never falls back (`app/latex/__init__.py:28-38`); `test_latex_engine_seam.py` green |
| 04-02.4 | `/health` reports `tectonic` and answers 200 in every case | ✓ VERIFIED | `_tectonic_report` mirrors `_opencode_report`; `tests/api/test_health.py:396,427-467` assert the key set, 200, and that a raising engine is reported not propagated |
| 04-02.5 | Every engine ceiling is a `Settings` field; no hard-coded ceiling literal | ? UNCERTAIN | The enumerated fields are all Settings (config.py:133-157). But `_HEALTH_TIMEOUT_SECONDS = 5.0` and `_LOG_TAIL_CHARS = 4000` remain module constants (`compile.py:48,50`) — see WR-03 |
| 04-02.6 | Fixed argv (shell-free), untrusted control on every compile, image env control | ✓ VERIFIED | `TectonicEngine._argv` is a `list[str]`, uses `create_subprocess_exec` (no shell); `--untrusted` always passed; `ENV TECTONIC_UNTRUSTED_MODE=1` in Dockerfile; seam test asserts each engine's own control |
| 04-03.1 | `cv.yaml` loads to `CvFacts` with stable IDs; 5 loud failure classes | ✓ VERIFIED | `app/cv/factstore.py`; `test_factstore.py`/`test_cv_ids.py` green (unknown key, missing field, dup ID, unmapped `title_key`, schema mismatch, missing file) |
| 04-03.2 | All C-1 fields present; closed `title_key` map; entries/skills/both | ✓ VERIFIED | `app/domain/cv.py:65-68,200-208`; `test_resolved_title_maps_a_known_key_and_the_map_is_closed`, `test_a_section_may_carry_entries_only_skills_only_or_both` green |
| 04-03.3 | Human's `base.tex` untouched; gitignore guard | ✓ VERIFIED | No write path to any `.tex` in `app/` (grep); `cv/`+`artifacts/` in `.gitignore` with `test_cv_hygiene.py` guard-can-fail. (Note: `test_a_full_load_and_identity_patch_leaves_base_tex_byte_identical` is weak — its temp `base.tex` is never read by any code — but the underlying property is grep-proven) |
| 04-03.4 | Same data → same bytes; committed golden fails on regression | ✓ VERIFIED | Re-rendered live: deterministic True, `matches golden: True` against `tests/golden/base.rendered.tex` (2277 bytes, non-ASCII em dashes); `test_render_bytes.py` + `test_render_determinism.py` green |
| 04-03.5 | Escaping is a non-bypassable `finalize` choke point, backslash-first | ✓ VERIFIED | `env.py:70-85` installs `_latex_finalize`, pops html escape filters; `tex.py:38-77`; hostile sample + `Markup` opt-out tests green |
| 04-03.6 | Bullet text immutable; every declared mutating op raises | ✓ VERIFIED | `apply_patch` is identity-only and raises `UnsupportedPatchOp`/`UnknownIdError` (`cv.py:465-492`); `test_each_mutating_operation_raises...` green. (Wording overclaim: the plan says "identity and ordering" but **no ordering operation exists** — see IN-A) |
| 04-04.1 | Two compiled PDFs reduced to facts; every org/title/date/bullet present; floor | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Predicate + floor implemented (`tests/latex/test_fact_equivalence.py`), but the two compiles are **UNRUN** (lane skipped) |
| 04-04.2 | The reproduction check can actually fail (mutation control) | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Mutation test present, **UNRUN**; pure predicate discrimination IS proven hermetically in `test_tex_escape.py` |
| 04-04.3 | A hostile bullet survives the engine round trip | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Test present, **UNRUN**; string/template escaping proven, engine round trip not |
| 04-04.4 | Revisions snapshot payload + string `schema_version` + source; one current row; writer never commits | ? UNCERTAIN | Happy path VERIFIED (`test_cv_repo.py` green, raw-column string read passes). But the flag-clear runs **outside** `begin_nested()` (`cv_repo.py:79-92`), so a failed insert leaves **zero** current rows — see WR-01 |
| 04-04.5 | No synthetic CV artefact row written | ✓ VERIFIED | No write to `cv_artifacts` anywhere in `app/` (grep: only the model and the settings reset list) |
| 04-05.1 | One re-runnable command yields a draft + report of what it could not resolve | ✓ VERIFIED | `scripts/cv-tex-spike.sh` + `parse_tex`; `test_cv_tex_spike_script.py` green (real run writes a loadable draft, source hash unchanged); default draft is `cv/cv.draft.yaml`, never `cv.yaml` |
| 04-05.2 | The parser only emits what it understood; nothing guessed; unresolved loud | ? UNCERTAIN | Unresolved macros reported by name/count/line; required entry fields absent→loud. But two silent-collapse paths exist: org/title slug collisions (WR-02, reproduced below) and always-empty `meta: {}` (IN-02) |
| 04-05.3 | Dated verdict carries PARTIAL + UNRESOLVED trigger; STATE blocker stays open | ✓ VERIFIED | `docs/probes/2026-09-21-cv-tex-spike.md` exactly one `PARTIAL` marker, `UNRESOLVED — blocked on the real document`, names `bash scripts/cv-tex-spike.sh`; `.planning/STATE.md:94` still OPEN pointing at the trigger; `test_cv_tex_spike_docs.py` green |
| 04-05.4 | TeX Live fallback is measured or explicitly declared unmeasured | ✓ VERIFIED | Verdict §5 "**Not taken**"; the fallback's "available" claim is explicitly **not** made — the honest state |
| 04-05.5 | Runbook documents gate, dirs, offline failure, D-75, fallback control/build | ✓ VERIFIED | `docs/runbook-latex-compile.md` present; gate string matches the lane skip reasons; `test_cv_tex_spike_docs.py` green |
| 04-05.6 | No real CV content reaches a committed file | ✓ VERIFIED | Tests assert no email/phone shape and no fixture content in the verdict; the fixture uses `.invalid` only; counts/names only |

**Score:** 20/29 truths verified (5 present-but-behavior-unverified, 4 uncertain)

### Roadmap Success Criteria (contract, not reducible by the plan)

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| SC1 | Structured data + golden reproduction test proves fact-equivalence | PARTIAL | Renderer golden byte-exact in the hermetic lane ✓; the **fact-equivalence over two compiled PDFs is UNRUN** |
| SC2 | LaTeX CV stays canonical; user content escaped | ✓ SATISFIED | No write path to `base.tex`; `finalize` choke point; hostile sample escaped |
| SC3 | Offline container compile via Tectonic; engine selectable; `Dockerfile.texlive` fallback | PARTIAL | Engine selectable ✓; Tectonic compile **UNRUN**; fallback present but **deliberately not claimed available** (unmeasured) |
| SC4 | Spike on the real `.tex` yields a written verdict on decomposition + bundle coverage, fallback recorded | PARTIAL (as scoped by D-62) | PARTIAL verdict + UNRESOLVED trigger shipped ✓; the **real-document** decomposition and bundle coverage remain unmeasured; STATE unknown #1 open |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/domain/tex.py` | `escape_tex`, comparison folds, `facts_present_in`, `sanitise_preamble` | ✓ VERIFIED | 253 lines; pure; `test_import_discipline.py` green |
| `app/domain/cv.py` | `CvFacts` family, ID derivation, `RenderPlan`, patch types | ✓ VERIFIED | 524 lines; extra="forbid"; validators |
| `app/cv/factstore.py` | The single loud `cv.yaml` reader | ✓ VERIFIED | `safe_load` only; path-qualified errors |
| `app/cv/import_tex.py` | Bounded importer + `ImportReport` | ✓ VERIFIED (with WR-02/IN-02 caveats) | 549 lines; bounded; read-only |
| `app/latex/base.py` | `LatexEngine` Protocol, `CompileResult`, `EngineProbe` | ✓ VERIFIED | runtime_checkable Protocol; extra="forbid" |
| `app/latex/compile.py` | `TectonicEngine`, `TexLiveEngine`, `_count_pages`, `extract_pdf_text` | ✓ VERIFIED (hermetic) | fixed argv, `create_subprocess_exec`, failure-as-value |
| `app/latex/env.py` | LaTeX Jinja env + finalize choke point | ✓ VERIFIED | two-env split; html filters removed |
| `app/latex/render.py` | Deterministic `RenderPlan`→`.tex` | ✓ VERIFIED | `write_bytes`; no clock/random |
| `app/latex/templates/cv.tex.jinja` | Committed app template (D-71) | ✓ VERIFIED | 76 lines; backslash delimiters |
| `app/db/repositories/cv_repo.py` | Revision-log SQL | ✓ VERIFIED (happy path) | no `commit()`; string schema; SAVEPOINT caveat WR-01 |
| `app/api/health.py` | `_tectonic_report` + `tectonic` key | ✓ VERIFIED | total function; 200 always |
| `Dockerfile` | Pinned Tectonic install + prime + cache ENV | EXISTS (UNRUN) | Checksum-verified same-layer install, `--version`, `--help`, prime with `test -f` |
| `Dockerfile.texlive` | Curated fallback image | EXISTS (UNRUN) | `shell_escape = f`, `-no-shell-escape`, `LATEX_ENGINE=texlive`; build not measured |
| `compose.yml` / `.env.example` | 10 engine keys + volumes | ✓ VERIFIED | All 10 in `${KEY:-default}` form + documented; `./cv:/cv`, `./artifacts:/artifacts` |
| `tests/fixtures/cv/awesomecv_standin.tex` | Committed synthetic document (D-61) | ✓ VERIFIED | 75 lines; macro-heavy; `.invalid` contacts only |
| `tests/fixtures/cv/awesomecv_standin.yaml` | Fixture fact store | ✓ VERIFIED | Loads; unique IDs; both enumerations |
| `tests/golden/base.rendered.tex` | Byte-exact baseline | ✓ VERIFIED | 2277 bytes; re-render matches |
| `scripts/cv-tex-spike.sh` | Re-runnable spike entry point (D-60) | ✓ VERIFIED | 88 lines; exec bit; dry-run/missing-source exit codes tested |
| `docs/probes/2026-09-21-cv-tex-spike.md` | PARTIAL verdict + trigger (D-62) | ✓ VERIFIED | One marker; UNRESOLVED section |
| `docs/runbook-latex-compile.md` | Operator runbook | ✓ VERIFIED | Gate, dirs, offline, D-75, fallback |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `app/cv/factstore.py` | `app/domain/cv.py` | `import` of models; `yaml.safe_load` runtime pin | WIRED |
| `app/latex/compile.py` | `pypdf` | `_count_pages` / `extract_pdf_text` use `PdfReader` (no second PDF lib) | WIRED |
| `pyproject.toml` `addopts` | `tests/latex/` | `not latex` deselection; explicit `-m latex` collects | WIRED |
| `app/latex/__init__.py:get_latex_engine` | `app/api/health.py` | `Depends(get_latex_engine)` → `_tectonic_report` | WIRED |
| `Dockerfile` prime | `tests/latex/test_compile.py` | Same fixture `awesomecv_standin.tex` compiled by both | WIRED |
| `Dockerfile` `ENV TECTONIC_CACHE_DIR` | `app/config.py` + `TectonicEngine` | `/opt/tectonic-cache` set **before** prime; passed as subprocess env | WIRED |
| `app/latex/env.py` | `app/domain/tex.py` | `escape_tex` installed as `Environment.finalize` | WIRED |
| `app/latex/render.py` | `app/latex/env.py` + `app/domain/cv.py` | `RenderPlan` → `make_latex_env` | WIRED |
| `tests/latex/test_fact_equivalence.py` | `facts_present_in` + `TectonicEngine` | predicate (pure) meets extraction (I/O) | WIRED (execution UNRUN) |
| `app/db/repositories/cv_repo.py` | consumers | imported by nothing in this phase (consumer is Phase 6) — as designed | WIRED (orphan by intent) |
| `scripts/cv-tex-spike.sh` | `app/cv/import_tex.py` | thin `python -c` entry point over `parse_tex`/`write_draft` | WIRED |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `app/latex/render.py` | `plan` | `load_facts(cv.yaml)` → `apply_patch` | Yes (fixture loads; live re-render matches golden) | ✓ FLOWING |
| `app/api/health.py` | `tectonic` | `engine.health()` → `_probe('--version')` subprocess | Yes (binary absent → `available:false`, code `not_found`) | ✓ FLOWING |
| `app/db/repositories/cv_repo.py` | `CvVersion` row | caller-supplied `facts_json` | Yes (round-trips via ORM + raw driver) | ✓ FLOWING |
| `app/cv/import_tex.py` | draft mapping | text of the read document | Yes (draft loads through `load_facts`) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Hermetic default lane | `.venv/bin/python -m pytest -q` | `961 passed, 14 deselected in 119.16s` | ✓ PASS |
| Latex lane is collected, not deselected | `pytest --collect-only -m latex tests/latex` | `10 tests collected` | ✓ PASS |
| Latex lane nodes skip loudly on a dry host | `pytest -m latex tests/latex -rs` | `10 skipped` (gate command in every reason) | ✓ PASS (coverage UNVERIFIED) |
| Renderer is deterministic and matches the committed golden | `.venv/bin/python -c "…render twice + compare bytes…"` | deterministic True; `matches golden: True` | ✓ PASS |
| Org/title slug collision is silent | `parse_tex` on two employers `Acme Ltd` / `Acme-Ltd` | one org `{id: org.acme-ltd, name: Acme Ltd}`; `entry_id_collisions: ()`; no unresolved entry | ✗ FAIL (WR-02, reproduced) |

### Probe Execution

| Probe | Command | Result | Status |
|-------|---------|--------|--------|
| `scripts/cv-tex-spike.sh` (D-60) | `bash scripts/cv-tex-spike.sh tests/fixtures/cv/awesomecv_standin.tex <tmp>` | Covered hermetically by `tests/test_cv_tex_spike_script.py` (real run writes a loadable draft, source hash unchanged) | PASS (stand-in only) |
| Real-document spike (D-62) | `bash scripts/cv-tex-spike.sh` against `cv/base.tex` | `cv/base.tex` absent by design; verdict §4 `UNRESOLVED` | MISSING_TRIGGER (UNRUN) |
| Container lane | `docker compose run --rm app pytest -m latex` | no Docker/engine | UNRUN |
| D-75 flag confirmation | `docker compose run --rm app tectonic --help` | no Docker/engine | UNRUN |
| Bundle coverage | `docker compose run --rm app tectonic -X bundle search <pkg>` | no Docker/engine | UNRUN |
| D-76 fallback measurement | `docker build -f Dockerfile.texlive …` | no Docker | UNRUN (verdict §5 "Not taken") |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| CV-01 | 04-01, 04-03, 04-04, 04-05 | CV modelled as structured data with stable enumerated IDs | ✓ SATISFIED | `app/domain/cv.py` models + `iter_fact_ids`/`derive_*`/`qualify_entry_ids`; `factstore.py`; tests green |
| CV-02 | 04-03, 04-05 | Human LaTeX CV stays canonical and is never modified | ✓ SATISFIED | No write path to any `.tex`; importer read-only (hash test); `.gitignore` guard |
| CV-03 | 04-01, 04-04 | Golden reproduction proves fact-equivalence | ◑ PARTIAL (UNRUN) | Byte-exact renderer golden ✓; PDF fact-equivalence lane implemented but **skipped/UNRUN** in this environment |
| CV-04 | 04-03 | LaTeX rendered deterministically from structured data | ✓ SATISFIED | `render.py`/`env.py`; determinism + AST guard tests green; live re-render matches golden |
| CV-05 | 04-01, 04-02, 04-04, 04-05 | LaTeX compiled to PDF inside the container | ◑ PARTIAL (UNRUN) | Engine port, selector, DI, `/health`, Dockerfile + fallback committed; **container compile never ran**; fallback availability not claimed |
| CV-06 | 04-03, 04-04 | User content escaped so it cannot break the document | ✓ SATISFIED (hermetic) | `finalize` choke point + hostile sample + `Markup` opt-out proven; escape-through-engine half of CV-03 UNRUN |

No orphaned phase requirements: `grep "Phase 4" REQUIREMENTS.md` returns exactly CV-01..CV-06, and all six appear in plan frontmatter (`requirements:` fields). The REQUIREMENTS.md checkboxes (`- [ ]`) and the `Pending` table are still unchecked — marking is the orchestrator's step, not a gap.

### Anti-Patterns Found

No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers in any phase file (scanned app/, tests/, Dockerfiles, compose, .env.example, scripts/, docs/). No missing/stub artifacts. Four warnings are carried forward from `04-REVIEW.md` (0 critical) and independently confirmed here; they are **warnings, not blockers**, because none prevents the phase goal.

| File | Location | Pattern | Severity | Impact |
|------|----------|---------|----------|--------|
| `app/db/repositories/cv_repo.py` | 79-92 | `UPDATE … is_current=False` runs **outside** `begin_nested()`; the docstring claims one SAVEPOINT | ⚠️ Warning (WR-01) | A failed insert leaves **zero** current rows, breaking the "exactly one current row" invariant. Read path (`current_version`) doesn't filter on the flag, so not user-visible yet. Regression test present only for the happy path |
| `app/cv/import_tex.py` | 275-280, 395-401, 498-499 | `orgs/titles.setdefault(slug, name)` silently merges distinct names whose slugs collide; `entry_id_collisions` covers entry IDs only | ⚠️ Warning (WR-02) | Reproduced: `Acme Ltd` + `Acme-Ltd` → one org named `Acme Ltd`, no collision reported. A wrong employer can reach a rendered CV — the silent-corruption class the phase exists to prevent |
| `app/latex/compile.py` | 48, 50 | `_HEALTH_TIMEOUT_SECONDS = 5.0`, `_LOG_TAIL_CHARS = 4000` hard-coded | ⚠️ Warning (WR-03) | Contradicts 04-02's "no distinctive ceiling literal survives hard-coded" claim; the PLAT-04 absence scan walks ints only, so `5.0` is invisible and `4000` is outside the derived set |
| `app/cv/import_tex.py` | 222 | `_flatten` strips all remaining braces after restoring only `\%\&\_\#\$`; `\{`/`\}` lose the brace and leave a bare backslash | ⚠️ Warning (WR-04) | A bullet containing escaped braces renders with a spurious `\textbackslash{}` |
| `app/domain/tex.py` | 208 | `sanitise_preamble` has no production caller | ℹ️ Info (IN-01) | The pdfTeX-primitive neutralisation is never applied on a real compile path; capability present but unwired |
| `app/cv/import_tex.py` | 494-501 | Draft always emits `meta: {}`; `Meta` defaults make a nameless CV load cleanly | ℹ️ Info (IN-02) | For `meta`, "unresolved" is indistinguishable from "empty", contradicting the importer's stated principle |
| `app/domain/cv.py` | 465-492 | Plan/docs say "identity and ordering"; only identity is implemented, no ordering op exists | ℹ️ Info (IN-A) | Wording overclaim; no behavioural gap (the declared mutating ops all raise) |

### Human Verification Required

1. **Container LaTeX lane** — `docker compose run --rm app pytest -m latex`; expect the 10 collected nodes to run and pass (not skip). This is the only path that turns CV-03/CV-05/CV-06's end-to-end halves from ⚠️ to ✓.
2. **D-75 flag confirmation** — `docker compose run --rm app tectonic --help`; expect `--only-cached` and `--untrusted`, else fix the argv, not the assertion.
3. **Bundle coverage** — `docker compose run --rm app tectonic -X bundle search <package>` for each of the 7 fixture packages.
4. **D-76 fallback measurement** — build `Dockerfile.texlive` by hand and record size/build-duration/argv/page-count **or** leave §5 "Not taken" and the fallback unclaimed (current honest state).
5. **Real-document spike** — place `cv/base.tex`, `mkdir -p cv artifacts`, run `bash scripts/cv-tex-spike.sh`, append counts/unresolved names to the verdict §4. Until then STATE blocking unknown #1 stays open and SC4 remains partial by design (D-62).
6. **Package-legitimacy attestation** — confirm the human-approved `pypdf==6.19.0` / `pyyaml==6.0.3` decision recorded for 04-01 D6 was real and predates the install.

### Gaps Summary

The phase's **machinery is built and its hermetic proofs are green**: the fact
store loads `cv.yaml` loudly, the renderer is byte-deterministic through a single
non-bypassable escaping choke point, the engine port and configuration seam are
wired and reported on `/health`, the revision log ships, and the bounded importer
plus spike script and PARTIAL verdict are committed. The hermetic lane is
**961 passed, 14 deselected** on re-run; the golden file is byte-exact against a
live re-render; the `.gitignore`/escaping/read-only controls are proven.

**What is not proven — and must not be reported as passed:**

1. **The container compile (CV-05, SC3).** Docker and Tectonic are absent. The
   `latex` lane is collected and **skipped** (10 nodes), and the four
   operator-only checks are UNRUN. The Dockerfile install, cache prime, untrusted
   control and `Dockerfile.texlive` all *exist* and read correctly, but "compiles
   LaTeX to PDF inside the container" has no executed evidence in this
   environment.
2. **The PDF fact-equivalence half of the golden reproduction (CV-03, SC1).** The
   byte-exact renderer golden runs hermetically; the test that reduces two
   *compiled PDFs* to facts and proves every org/title/date/bullet present — plus
   its mutation control and the hostile-bullet round trip (CV-06 end to end) —
   is skipped. A deterministic renderer can still deterministically drop a
   bullet, so this half is load-bearing and remains unverified.
3. **The real-document measurement (SC4, STATE unknown #1).** The verdict is an
   honest `PARTIAL` with an `UNRESOLVED` trigger, exactly as D-62 scoped it. The
   real `.tex` is absent by design, so decomposition cost and bundle coverage for
   the real document are unmeasured and the blocking unknown stays open.

**Warnings carried forward from `04-REVIEW.md` and independently confirmed** (not
phase-goal blockers, but real defects): WR-01 (revision-log SAVEPOINT does not
cover the current-flag clear; reproduced: a failed insert leaves zero current
rows), WR-02 (importer silently merges employer/title names with colliding slugs
— reproduced live above), WR-03 (two hard-coded ceilings contradict the "every
ceiling is a Settings field" truth), WR-04 (`\{`/`\}` lose their brace and leave
a stray backslash). These make truths 04-02.5, 04-04.4 and 04-05.2 UNCERTAIN
rather than VERIFIED.

**Verdict:** the phase goal is **substantially built and hermetically proven**,
but its two externally dependent halves — the in-container compile and the
real-document fact-equivalence/spike — are **UNRUN**. Status is therefore
`human_needed`, not `passed`, and there are no FAILED must-haves that would
justify blocking with `gaps_found`.

---

_Verified: 2026-09-21T15:58:22Z_
_Verifier: the agent (gsd-verifier)_
