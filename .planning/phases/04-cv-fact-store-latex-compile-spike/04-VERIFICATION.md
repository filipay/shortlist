---
phase: 04-cv-fact-store-latex-compile-spike
verified: 2026-09-21T17:13:40Z
status: passed
score: 29/29 must-haves verified
covered_files:
  - .planning/REQUIREMENTS.md
  - .planning/ROADMAP.md
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
  - .planning/phases/04-cv-fact-store-latex-compile-spike/04-UAT.md
  - .planning/phases/04-cv-fact-store-latex-compile-spike/04-VALIDATION.md
  - .planning/phases/04-cv-fact-store-latex-compile-spike/04-REVIEW.md
  - .planning/phases/04-cv-fact-store-latex-compile-spike/04-SECURITY.md
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
covered_digest: "v1:sha256:c8000b74668f8fba9d02a8b27bd14d3378a0d38563a8e23b23d25bc8b889a58e"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 26/29
  gaps_closed:
    - "04-04.4 / WR-01 (`6dabe66`): the current-row clear now runs INSIDE `begin_nested()` with the insert, so a failed insert rolls back both and the previous revision remains the single current row. Guard: `tests/db/test_cv_repo.py::test_a_failed_insert_leaves_the_previous_revision_current`."
    - "04-02.5 / WR-03 (`2665764`): `_HEALTH_TIMEOUT_SECONDS` / `_LOG_TAIL_CHARS` promoted to `Settings.latex_probe_timeout_seconds` (5.0) and `Settings.latex_log_tail_chars` (4000), resolved at call time; forwarded through `compose.yml` / `.env.example` and covered by the phase-four ceiling guards."
    - "04-05.2 / WR-02 + IN-02 (`8711cbb`): distinct org/title names that slugify to one ID are reported via `ImportReport.org_id_collisions` / `title_id_collisions` (and the summary) instead of being silently dropped; a missing identity name is surfaced as `ImportReport.unresolved_fields == (\"meta.name\",)`."
    - "Container lane (operator, recorded in 04-UAT.md): image builds healthy; `docker compose run --rm app pytest -m latex` -> 10 passed, 968 deselected; D-75 confirmed against the installed binary."
  gaps_remaining: []
  regressions: []
---

# Phase 04: CV Fact Store + LaTeX Compile Spike — Verification Report

**Phase Goal:** ``cv.yaml`` exists and reproduces the human's CV fact-for-fact, and Tectonic compiles the real `.tex` inside the container — retiring the project's largest unquantified cost.
**Verified:** 2026-09-21T17:13:40Z
**Status:** passed
**Re-verification:** Yes — the three previously-UNCERTAIN must-haves are now fixed and re-verified against current HEAD

## Method note (what this environment could and could not do)

- **Hermetic suite re-run at current HEAD (b618134):**
  `.venv/bin/python -m pytest -q` → **971 passed, 14 deselected in 136.81s**.
- **Docker is absent and was not attempted.** The `latex` pytest lane is still
  collected-and-**skipped** here (10 nodes; the gate command is in every skip
  reason). It is never counted as coverage in this report. The operator ran it
  in-container (recorded in `04-UAT.md`): **10 passed, 968 deselected**.
- Every must-have below was checked against the **current code and guards**, not
  against the plan/summary prose. The three fixes were read in the source and
  their regression guards were executed here (targeted subset: 75 passed).

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 04-01.1 | `pypdf` pinned/importable; `pyyaml` promoted dev→runtime | ✓ VERIFIED | `.venv/bin/python`: `pypdf 6.19.0`, `yaml 6.0.3`; `pyproject.toml:31,34`; `requirements.txt:22,26` |
| 04-01.2 | Both manifests mirror the two pins; `pyyaml` absent from `[dev]` | ✓ VERIFIED | dev group holds only pytest/pytest-asyncio/ruff; `test_pinned_package_is_declared_exactly` green |
| 04-01.3 | `latex` marker registered and excluded; default lane green | ✓ VERIFIED | `pyproject.toml:61-65`; 971 passed, 14 deselected; lane collected-and-skipped (10), never deselected (`test_latex_lane_contract.py`) |
| 04-01.4 | `app/latex/__init__.py` marker existed before the wave-2 code | ✓ VERIFIED | `git show 320e2e2` created it docstring-only; 04-02 filled it (b4d3b42) |
| 04-01.5 | A human confirmed each SUS package's name/version/source before install | ✓ VERIFIED | UAT item 6 PASSED — checkpoint presented with PyPI metadata/wheel type/source and answered before either manifest edit |
| 04-01.6 | No package other than the two named was added/upgraded/removed | ✓ VERIFIED | `git show 320e2e2` dep diff is exactly `pypdf` + `pyyaml` |
| 04-02.1 | One command yields a real offline PDF from inside the image | ✓ VERIFIED (operator) | Image builds healthy; `docker compose run --rm app pytest -m latex` → 10 passed; Dockerfile install+ENV+prime + outdir fix `0edde77` |
| 04-02.2 | `CompileResult` is a value, never an exception (4 failure classes) | ✓ VERIFIED (operator) | `test_every_engine_failure_is_a_value_not_an_exception` passes in-container; the staging-`FileNotFoundError` misreport is fixed by `a8a5321` |
| 04-02.3 | The engine used matches `LATEX_ENGINE`; DI-overridable | ✓ VERIFIED | `get_latex_engine()` selects exactly one, never falls back (`app/latex/__init__.py:28-38`); seam test green |
| 04-02.4 | `/health` reports `tectonic` and answers 200 in every case | ✓ VERIFIED | `tests/api/test_health.py:396,427-467` assert key set, 200, raising-engine reported not propagated |
| 04-02.5 | Every engine ceiling is a `Settings` field; no hard-coded ceiling literal | ✓ VERIFIED (fixed `2665764`) | `Settings.latex_probe_timeout_seconds: float = 5.0` / `latex_log_tail_chars: int = 4000` (`config.py:151,155`); `compile.py:92-94,112-118` resolve at call time; compose.yml:51-52 + .env.example:67,71 forward both; call-time guards at `tests/test_config.py:291,306` pass |
| 04-02.6 | Fixed argv (shell-free), untrusted control every compile, image env control | ✓ VERIFIED | `_argv` list + `create_subprocess_exec` (no shell); `--untrusted` always; `ENV TECTONIC_UNTRUSTED_MODE=1`; seam test asserts each engine's own control |
| 04-03.1 | `cv.yaml` loads to `CvFacts` with stable IDs; 5 loud failure classes | ✓ VERIFIED | `factstore.py`; `test_factstore.py`/`test_cv_ids.py` green |
| 04-03.2 | All C-1 fields present; closed `title_key` map; entries/skills/both | ✓ VERIFIED | `cv.py:65-68,200-208`; targeted tests green |
| 04-03.3 | Human's `base.tex` untouched; gitignore guard | ✓ VERIFIED | No write path to any `.tex` in `app/`; `cv/`+`artifacts/` in `.gitignore` with a guard-can-fail test |
| 04-03.4 | Same data → same bytes; committed golden fails on regression | ✓ VERIFIED | Live re-render deterministic and `matches golden: True` (2277 bytes); `test_render_bytes.py`/`test_render_determinism.py` green |
| 04-03.5 | Escaping is a non-bypassable `finalize` choke point, backslash-first | ✓ VERIFIED | `env.py:70-85` installs `_latex_finalize`, pops html escape filters; `tex.py:38-77`; hostile sample + `Markup` opt-out tests green |
| 04-03.6 | Bullet text immutable; every declared mutating op raises | ✓ VERIFIED | `apply_patch` identity-only, raises `UnsupportedPatchOp`/`UnknownIdError` (`cv.py:465-492`); test green (IN-A: "ordering" is not itself implemented — wording note only, no behavioural gap) |
| 04-04.1 | Two compiled PDFs reduced to facts; every org/title/date/bullet present; floor | ✓ VERIFIED (operator) | `tests/latex/test_fact_equivalence.py` 7 passed in-container; `facts_compared >= 6` floor asserted so an empty extraction cannot pass |
| 04-04.2 | The reproduction check can actually fail (mutation control) | ✓ VERIFIED (operator) | Mutation test passes in-container (it must fail the predicate to pass the test) |
| 04-04.3 | A hostile bullet survives the engine round trip | ✓ VERIFIED (operator) | Hostile-bullet compile+extraction test passes in-container |
| 04-04.4 | Revisions snapshot payload + string `schema_version` + source; one current row; writer never commits | ✓ VERIFIED (fixed `6dabe66`) | `cv_repo.py:87-98`: BOTH the clear and the insert run inside `begin_nested()`, so a failed insert rolls back both; guard `test_a_failed_insert_leaves_the_previous_revision_current` green; string-column raw read + no-commit tests green |
| 04-04.5 | No synthetic CV artefact row written | ✓ VERIFIED | No write to `cv_artifacts` anywhere in `app/` |
| 04-05.1 | One re-runnable command yields a draft + report of what it could not resolve | ✓ VERIFIED | `scripts/cv-tex-spike.sh` + `parse_tex`; script tests green; default draft `cv/cv.draft.yaml`, never `cv.yaml` |
| 04-05.2 | The parser only emits what it understood; nothing guessed; unresolved loud | ✓ VERIFIED (fixed `8711cbb`) | `import_tex.py:408-431` appends colliding org/title IDs to `org_collisions`/`title_collisions` (reported by derived ID, never raw CV text); `import_tex.py:539-541` emits `unresolved_fields == ("meta.name",)` when no identity name; guards `test_import_tex.py` org-collision + no-collision + meta.name tests green; report carries no source text |
| 04-05.3 | Dated verdict carries PARTIAL + UNRESOLVED trigger; STATE blocker stays open | ✓ VERIFIED | `docs/probes/2026-09-21-cv-tex-spike.md` exactly one `PARTIAL` marker, `UNRESOLVED` naming `bash scripts/cv-tex-spike.sh`; STATE #1 OPEN; `test_cv_tex_spike_docs.py` green |
| 04-05.4 | TeX Live fallback is measured or explicitly declared unmeasured | ✓ VERIFIED | Verdict §5 "**Not taken**"; the fallback is explicitly **not** claimed available |
| 04-05.5 | Runbook documents gate, dirs, offline failure, D-75, fallback control/build | ✓ VERIFIED | `docs/runbook-latex-compile.md`; gate string matches lane skip reasons; test green |
| 04-05.6 | No real CV content reaches a committed file | ✓ VERIFIED | Tests assert no email/phone shape and no fixture content in the verdict; `.invalid` only |

**Score:** 29/29 truths verified (0 present-but-behavior-unverified; 0 uncertain)

### Roadmap Success Criteria (contract, not reducible by the plan)

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| SC1 | Structured data + golden reproduction test proves fact-equivalence | ✓ SATISFIED | Byte-exact golden hermetic; two-PDF fact-equivalence lane (orgs/titles/dates/bullet shingles + fact-count floor + mutation control) passes in-container |
| SC2 | LaTeX CV stays canonical; user content escaped | ✓ SATISFIED | No write path to `base.tex`; `finalize` choke point; hostile bullet escapes and survives the engine round trip (operator) |
| SC3 | Offline container compile via Tectonic; engine selectable; `Dockerfile.texlive` fallback | ✓ SATISFIED | Engine selectable and non-substituting ✓; offline container compile proven (image build + lane) ✓; `Dockerfile.texlive` exists and selects itself — its "available" claim is deliberately unmeasured per D-76, which is an explicitly permitted outcome |
| SC4 | Spike on the real `.tex` yields a written verdict on decomposition + bundle coverage, fallback recorded | ✓ SATISFIED as scoped by D-62 | PARTIAL verdict + proven/unproven split + UNRESOLVED trigger delivered and asserted; the real-document measurement is the open STATE unknown #1 (a trigger, not a phase deliverable) |

### Fixed since the previous verification (all guarded, all green here)

| Warning | Must-have | Commit | Guard (passes) |
|---------|-----------|--------|----------------|
| WR-01 (SAVEPOINT placement) | 04-04.4 | `6dabe66` | `tests/db/test_cv_repo.py::test_a_failed_insert_leaves_the_previous_revision_current` |
| WR-03 (hard-coded ceilings) | 04-02.5 | `2665764` | `tests/test_config.py::test_the_engine_log_tail_bound_comes_from_settings_at_call_time`, `::test_the_probe_timeout_comes_from_settings_at_call_time`, plus the ceiling guards |
| WR-02 + IN-02 (silent slug collision / empty meta) | 04-05.2 | `8711cbb` | `tests/cv/test_import_tex.py` org-collision, no-collision and `meta.name` tests |
| (earlier) Dockerfile prime outdir | 04-02.1 | `0edde77` | `tests/test_deploy_manifest.py::test_dockerfile_creates_every_outdir_it_hands_to_an_engine` |
| (earlier) staging workdir | 04-02.2 | `a8a5321` | `tests/test_latex_engine_seam.py::test_compile_creates_the_workdir_it_stages_into` |

`04-REVIEW.md` §"Fix dispositions" (`b618134`) records the same dispositions.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/domain/tex.py` | `escape_tex`, comparison folds, `facts_present_in`, `sanitise_preamble` | ✓ VERIFIED | 253 lines; pure; import-discipline guard green |
| `app/domain/cv.py` | `CvFacts` family, ID derivation, `RenderPlan`, patch types | ✓ VERIFIED | 524 lines; extra="forbid"; validators |
| `app/cv/factstore.py` | The single loud `cv.yaml` reader | ✓ VERIFIED | `safe_load` only; path-qualified errors |
| `app/cv/import_tex.py` | Bounded importer + `ImportReport` (incl. collision/unresolved reporting) | ✓ VERIFIED | 592 lines; bounded; read-only |
| `app/latex/base.py` | `LatexEngine` Protocol, `CompileResult`, `EngineProbe` | ✓ VERIFIED | runtime_checkable; extra="forbid" |
| `app/latex/compile.py` | Engines, `_count_pages`, `extract_pdf_text`, workdir creation, Settings-resolved ceilings | ✓ VERIFIED | fixed argv; failure-as-value; no hard-coded probe/log ceilings |
| `app/latex/env.py` | LaTeX Jinja env + finalize choke point | ✓ VERIFIED | two-env split; html filters removed |
| `app/latex/render.py` | Deterministic `RenderPlan`→`.tex` | ✓ VERIFIED | `write_bytes`; no clock/random |
| `app/latex/templates/cv.tex.jinja` | Committed app template (D-71) | ✓ VERIFIED | 76 lines; backslash delimiters |
| `app/db/repositories/cv_repo.py` | Revision-log SQL | ✓ VERIFIED | both statements inside the SAVEPOINT; no `commit()`; string schema |
| `app/api/health.py` | `_tectonic_report` + `tectonic` key | ✓ VERIFIED | total function; 200 always |
| `app/config.py` | 12 LaTeX settings incl. probe timeout + log-tail bound | ✓ VERIFIED | `config.py:133-157` |
| `Dockerfile` | Pinned Tectonic install + prime + cache ENV | ✓ VERIFIED (operator) | Checksum-verified; `mkdir -p /tmp/prime`; build succeeds |
| `Dockerfile.texlive` | Curated fallback image | EXISTS (not measured) | `shell_escape = f`, `-no-shell-escape`, `LATEX_ENGINE=texlive`; D-76 unclaimed |
| `compose.yml` / `.env.example` | 12 engine keys + volumes | ✓ VERIFIED | All forwarded in `${KEY:-default}` + documented; `./cv:/cv`, `./artifacts:/artifacts` |
| `tests/fixtures/cv/awesomecv_standin.tex` | Committed synthetic document (D-61) | ✓ VERIFIED | 75 lines; macro-heavy; `.invalid` only |
| `tests/fixtures/cv/awesomecv_standin.yaml` | Fixture fact store | ✓ VERIFIED | Loads; unique IDs; both enumerations |
| `tests/golden/base.rendered.tex` | Byte-exact baseline | ✓ VERIFIED | 2277 bytes; live re-render matches |
| `scripts/cv-tex-spike.sh` | Re-runnable spike entry point (D-60) | ✓ VERIFIED | 88 lines; exec bit; exit codes tested |
| `docs/probes/2026-09-21-cv-tex-spike.md` | PARTIAL verdict + trigger (D-62) | ✓ VERIFIED | One marker; UNRESOLVED section |
| `docs/runbook-latex-compile.md` | Operator runbook | ✓ VERIFIED | Gate, dirs, offline, D-75, fallback |
| `04-UAT.md` | Operator UAT record | ✓ VERIFIED | 3 passed, 3 pending (all outside the must-have contract), 0 failed |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `app/cv/factstore.py` | `app/domain/cv.py` | model import; `yaml.safe_load` runtime pin | WIRED |
| `app/latex/compile.py` | `pypdf` | `_count_pages` / `extract_pdf_text` (no second PDF lib) | WIRED |
| `pyproject.toml` `addopts` | `tests/latex/` | `not latex` deselection; explicit `-m latex` collects | WIRED |
| `app/latex/__init__.py:get_latex_engine` | `app/api/health.py` | `Depends(get_latex_engine)` → `_tectonic_report` | WIRED |
| `Dockerfile` prime | `tests/latex/test_compile.py` | same fixture compiled by both | WIRED |
| `Dockerfile` `ENV TECTONIC_CACHE_DIR` | `app/config.py` + `TectonicEngine` | set **before** prime; passed as subprocess env | WIRED |
| `app/config.py` `latex_probe_timeout_seconds` / `latex_log_tail_chars` | `app/latex/compile.py` `_probe`/`_tail` | resolved at call time (WR-03 fix) | WIRED |
| `app/latex/env.py` | `app/domain/tex.py` | `escape_tex` installed as `Environment.finalize` | WIRED |
| `app/latex/render.py` | `app/latex/env.py` + `app/domain/cv.py` | `RenderPlan` → `make_latex_env` | WIRED |
| `tests/latex/test_fact_equivalence.py` | `facts_present_in` + `TectonicEngine` | predicate meets extraction; executed in-container | WIRED |
| `app/db/repositories/cv_repo.py` | Phase 6 | imported by nothing this phase — by design | WIRED (orphan by intent) |
| `scripts/cv-tex-spike.sh` | `app/cv/import_tex.py` | thin entry point over `parse_tex`/`write_draft` | WIRED |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `app/latex/render.py` | `plan` | `load_facts(cv.yaml)` → `apply_patch` | Yes (fixture loads; live re-render matches golden) | ✓ FLOWING |
| `app/api/health.py` | `tectonic` | `engine.health()` → `_probe('--version')` | Yes (in-container: available/version reported) | ✓ FLOWING |
| `app/db/repositories/cv_repo.py` | `CvVersion` row | caller-supplied `facts_json` | Yes (round-trips via ORM + raw driver) | ✓ FLOWING |
| `app/cv/import_tex.py` | draft mapping + report | text of the read document | Yes (draft loads through `load_facts`; collisions reported) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Hermetic default lane | `.venv/bin/python -m pytest -q` | `971 passed, 14 deselected in 136.81s` | ✓ PASS |
| Fix guards + core CV subset | `pytest tests/db/test_cv_repo.py tests/cv/test_import_tex.py tests/test_config.py tests/domain/test_tex_escape.py tests/test_latex_engine_seam.py tests/golden/test_render_bytes.py` | `75 passed` | ✓ PASS |
| Latex lane collected, not deselected | `pytest --collect-only -m latex tests/latex` | `10 tests collected` | ✓ PASS |
| Latex lane loud skip on a dry host | `pytest -m latex tests/latex -rs` | `10 skipped` (gate in every reason) | ✓ PASS (coverage from operator evidence) |
| Renderer deterministic + golden match | `.venv/bin/python -c "…render twice + compare bytes…"` | deterministic True; `matches golden: True` | ✓ PASS |
| Container latex lane (operator) | `docker compose run --rm app pytest -m latex` | `10 passed, 968 deselected in 9.75s` | ✓ PASS (operator-executed) |
| D-75 flag names (operator) | `docker compose run --rm app tectonic --help` | `-C, --only-cached` and `--untrusted` present | ✓ PASS (operator-executed) |

### Probe Execution

| Probe | Command | Result | Status |
|-------|---------|--------|--------|
| `scripts/cv-tex-spike.sh` (D-60) | `bash scripts/cv-tex-spike.sh <fixture> <tmp>` | Hermetic script tests green (real run writes a loadable draft; source hash unchanged) | PASS (stand-in only) |
| Container latex lane | `docker compose run --rm app pytest -m latex` | `10 passed` per operator UAT | PASS (operator) |
| D-75 flag confirmation | `docker compose run --rm app tectonic --help` | both flags present per operator UAT | PASS (operator) |
| Bundle coverage | `docker compose run --rm app tectonic -X bundle search <pkg>` | not run | UNRUN (outside the must-have contract; open real-preamble question) |
| D-76 fallback measurement | `docker build -f Dockerfile.texlive …` | not run; verdict §5 "Not taken" | UNRUN (optional; explicitly permitted to stay unclaimed) |
| Real-document spike | `bash scripts/cv-tex-spike.sh` against `cv/base.tex` | absent by design; verdict §4 `UNRESOLVED` | UNRUN (open STATE blocking unknown #1) |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| CV-01 | 04-01, 04-03, 04-04, 04-05 | CV modelled as structured data with stable enumerated IDs | ✓ SATISFIED | Models + `iter_fact_ids`/`derive_*`/`qualify_entry_ids`; `factstore.py`; importer emits stable IDs; tests green |
| CV-02 | 04-03, 04-05 | Human LaTeX CV stays canonical and is never modified | ✓ SATISFIED | No write path to any `.tex`; importer read-only (hash test); `.gitignore` guard |
| CV-03 | 04-01, 04-04 | Golden reproduction proves fact-equivalence | ✓ SATISFIED | Byte-exact renderer golden hermetic; two-PDF fact-equivalence lane passes in-container |
| CV-04 | 04-03 | LaTeX rendered deterministically from structured data | ✓ SATISFIED | determinism + AST guard tests green; live re-render matches golden |
| CV-05 | 04-01, 04-02, 04-04, 04-05 | LaTeX compiled to PDF inside the container | ✓ SATISFIED | Engine port/selector/DI/health hermetically; image builds and offline lane passes in-container; fallback image exists and is selectable |
| CV-06 | 04-03, 04-04 | User content escaped so it cannot break the document | ✓ SATISFIED | `finalize` choke point + hostile sample hermetic; hostile-bullet engine round trip passes in-container |

No orphaned phase requirements: `grep "Phase 4" REQUIREMENTS.md` returns exactly CV-01..CV-06, and all six appear in plan frontmatter. The REQUIREMENTS.md checkboxes remain unchecked — marking is the orchestrator's step, not a gap.

### Anti-Patterns Found

No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers in any phase file. No missing/stub artifacts. All four `04-REVIEW.md` warnings and the two UAT-caught defects are now **fixed and guarded** (`6dabe66`, `2665764`, `8711cbb`, `0edde77`, `a8a5321`). No blocker remains.

| File | Location | Pattern | Severity | Impact |
|------|----------|---------|----------|--------|
| `app/cv/import_tex.py` | 408-431 | Slug-collision first-wins is kept in the draft, but the collision is now reported by derived ID | ℹ️ Info | The human review step resolves it; the report stays free of raw CV text by design. No longer silent |
| `app/domain/tex.py` | 208 | `sanitise_preamble` has no production caller | ℹ️ Info | Neutralisation present but unwired in this phase; documented, not misleading |
| `app/cv/import_tex.py` | 222 | `_flatten` strips `\{`/`\}` leaving a bare backslash (WR-04) | ℹ️ Info | Escaped braces in a bullet render with a spurious `\textbackslash{}`; narrow, non-blocking, not tied to a must-have truth |
| `app/domain/cv.py` | 465-492 | Plan/docs say "identity and ordering"; only identity exists | ℹ️ Info | Wording overclaim; declared mutating ops all raise, so there is no behavioural gap |
| `app/db/repositories/cv_repo.py` | 97-110 | `current_version` does not filter on `is_current` | ℹ️ Info | The flag is an audit marker for Phase 6; the id tie-break makes the read deterministic |

### Carried-forward open unknowns (outside this phase's must-have contract)

These are recorded so nothing is rounded up, but none of them corresponds to an
unmet or uncertain must-have, and none blocks phase completion:

1. **Per-package bundle coverage for the real preamble** (UAT 3) — UNRUN. It
   depends on the real document and is part of the same open question below; the
   committed stand-in's assumed package set already compiles in-container.
2. **TeX Live fallback measurement** (UAT 4, D-76) — UNRUN, and explicitly
   permitted to stay unclaimed; must-have 04-05.4 is satisfied by the "Not taken"
   record.
3. **Real-document spike** (UAT 5) — the real `.tex` is deliberately absent
   (D-58). Must-have 04-05.3 (the partial verdict + trigger) is delivered and
   verified; the measurement itself is STATE blocking unknown #1, which stays
   OPEN and named for Phase 6 estimation.

### Gaps Summary

The phase goal is achieved as scoped by D-58/D-62, and every must-have is now
verified against the current code. The final three UNCERTAIN items from the
previous report — the code-review warnings WR-01, WR-02/IN-02 and WR-03 — are
fixed, guarded, and re-verified here: the revision log keeps exactly one current
row even when an insert fails; the LaTeX probe timeout and log-tail bound come
from `Settings` at call time and are forwarded through compose/.env; and the
importer now reports slug collisions and a missing identity name instead of
dropping them silently. Each fix was read in the source and its regression guard
was executed. The hermetic suite is **971 passed, 14 deselected**; the container
lane is operator-executed at **10 passed**; the golden renderer baseline is
byte-exact against a live re-render.

**No must-have is FAILED. No must-have is UNCERTAIN.** The only unverified items
are the three operator follow-ups listed above, which lie outside the phase's
must-have contract (two of them explicitly optional/deferred by D-62/D-76). The
human-verification section is therefore empty and the verdict is `passed`.

---

_Verified: 2026-09-21T17:13:40Z_
_Verifier: the agent (gsd-verifier)_
