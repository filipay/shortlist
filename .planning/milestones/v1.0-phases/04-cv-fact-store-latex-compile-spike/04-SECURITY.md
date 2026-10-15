---
phase: "04"
slug: "cv-fact-store-latex-compile-spike"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-09-21"
---

# Phase 04 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Verification depth: **ASVS L1** (grep-level presence). Register was authored at plan time in all five PLAN files, so per the secure-phase short-circuit (threats_open: 0, register_authored_at_plan_time: true, asvs_level: 1) L1 presence verification is sufficient; no deep boundary trace was required.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| PyPI → interpreter / image | Third-party code fetched and executed in-process; the phase's new supply-chain surface | Package artefacts (`pypdf`, `pyyaml`, Tectonic tarball) |
| dependency manifests → build | `requirements.txt` is what the Dockerfile installs; `pyproject.toml` is the declared contract | Pin strings |
| document being compiled → engine process | Machine-influenced `.tex` content reaching a TeX process | LaTeX source |
| engine argv → shell | A string-built command would be a code-execution path | Process argv |
| build host → image | Tectonic tarball fetched over the network and executed | Release tarball |
| `cv.yaml` (human-authored) → fact store | Semi-trusted local input; a tolerated typo would become invented CV content | CV facts |
| `cv.yaml` values → rendered `.tex` | Every interpolated value crosses into a document a TeX engine executes | Escaped CV text |
| `.gitignore` → git | The only mechanism keeping the real CV out of a commit | Real CV / artefacts |
| compiled PDF → extractor | Extractor output is untrusted-shaped text; comparison must stay exact | Extracted PDF text |
| DB session → revision table | Repository must never commit, or a caller's transaction is silently split | `cv_versions` rows |
| human's real CV → importer | Semi-trusted local document the parser reads; must never be modified | `.tex` source |
| spike numbers → committed verdict | Committed verdict is a disclosure surface | Counts, package names |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-04-01 | Tampering (supply chain) | `pypdf` install | high | mitigate | Exact pin `pypdf==6.19.0` in `pyproject.toml:31` and `requirements.txt:22`; blocking human checkpoint cleared before install (`04-01-SUMMARY.md` D6, approval `pypdf=6.19.0 pyyaml=6.0.3`) | closed |
| T-04-02 | Tampering (supply chain) | `pyyaml` dev→runtime promotion | medium | mitigate | `pyyaml==6.0.3` declared exactly once in both manifests (`pyproject.toml:34`, `requirements.txt:26`); human-confirmed promotion; no new artefact fetched | closed |
| T-04-03 | Tampering | manifest drift pyproject ↔ requirements | medium | mitigate | `tests/test_dependency_pins.py:108-114` asserts both pins in both manifests; can-fail companion `:137-155` | closed |
| T-04-04 | Denial of Service (developer machine) | `addopts` exclusion + `latex` marker | low | mitigate | `pyproject.toml:61` `addopts = "-m 'not live and not latex'"` + marker registered `:62-65`; both halves asserted `tests/test_dependency_pins.py:125-134` | closed |
| T-04-SC (04-01) | Tampering | package installs in plan 04-01 | high | mitigate | Pin guard `tests/test_dependency_pins.py` (fails on an unpinned entry) + blocking human checkpoint for the single new `[SUS]` package and the promoted one | closed |
| T-04-05 | Elevation of Privilege | both engines' `_argv` + image config | high | mitigate | Tectonic argv always passes `--untrusted` (`app/latex/compile.py:244-252`); TeX Live argv passes `-no-shell-escape` (`:289-298`); images set `TECTONIC_UNTRUSTED_MODE=1` (`Dockerfile:83`) and `shell_escape = f` (`Dockerfile.texlive:77`); asserted `tests/test_latex_engine_seam.py:89` | closed |
| T-04-06 | Elevation of Privilege | `asyncio.create_subprocess_exec` building | high | mitigate | Fixed `list[str]` argv built in `compile.py:235-253`/`:289-298`; spawn is `create_subprocess_exec(*argv)` `:153`; no `shell=True`/`os.system`/interpolated string anywhere | closed |
| T-04-07 | Tampering | Tectonic release tarball | high | mitigate | `Dockerfile:63-70` `ARG TECTONIC_SHA256` verified with `sha256sum -c -` in the **same** RUN that downloads; ends with `tectonic --version` so a non-executable binary fails the build | closed |
| T-04-08 | Denial of Service (self-inflicted) | hung/pathological compile | medium | mitigate | `compile.py:160-172` bounded by `wait_for`, timeout is `error_kind='timeout'`; `_count_pages` via `asyncio.to_thread` `:195`; `/health` uses only the cheap `_probe` `:108-132` | closed |
| T-04-09 | Tampering / Denial of Service | Tectonic cache directory | low | mitigate | `Dockerfile:82` `ENV TECTONIC_CACHE_DIR=/opt/tectonic-cache` set before the prime `:99`; passed at compile `compile.py:264`; `compose.yml:48` and `app/config.py:139` match; asserted `tests/test_deploy_manifest.py:208` | closed |
| T-04-10 | Information Disclosure | local tool reaching network at runtime | medium | mitigate | `app/config.py:146` `tectonic_offline: bool = True`; `compile.py:244-245` appends `--only-cached` when offline; build-time prime is the only networked invocation (`Dockerfile:99`); flag name confirmed against installed binary `tests/latex/test_compile.py:81-98` | closed |
| T-04-11 | Spoofing | configured engine ≠ engine that ran | medium | mitigate | `app/latex/__init__.py:28-38` selects exactly one engine, never falls back; `tests/test_latex_engine_seam.py:42-70`; engine name recorded on every `CompileResult` (`compile.py` `engine=engine_name`) | closed |
| T-04-12 | Tampering | artefact / workdir path handling | medium | mitigate | `compile.py:147-152` output paths joined to caller-supplied `workdir`, never request input; engine writes only `cv.tex`/`cv.pdf` | closed |
| T-04-SC (04-02) | Tampering | package installs in plan 04-02 | low | accept | No new package installed; Tectonic is a checksum-pinned static binary; Python pins gated in 04-01. Documented in register and Accepted Risks Log | closed |
| T-04-13 | Tampering / Elevation of Privilege | `env.py` escaping callback + template | high | mitigate | Single non-bypassable choke point `app/latex/env.py:56-74`, installed `:82`; HTML escape filters removed `:83-84`; asserted `tests/test_render_determinism.py:135-165`; end-to-end hostile-bullet compile `tests/latex/test_fact_equivalence.py:235-247` | closed |
| T-04-14 | Elevation of Privilege | `factstore.py` YAML loading | high | mitigate | `app/cv/factstore.py:56` uses `yaml.safe_load` only, with the reason recorded `:60-61`; models forbid extras so a smuggled key fails (`:63-65`) | closed |
| T-04-15 | Information Disclosure | real CV entering git / committed artefact | high | mitigate | `.gitignore` carries `cv/` and `artifacts/`; guard + can-fail `tests/test_cv_hygiene.py:29-45`; fixture addresses restricted to `.invalid` and phone shapes banned `:48-66`; verdict carries counts only | closed |
| T-04-16 | Tampering / Repudiation | ID silently preserved across content edit | medium | mitigate | `tests/domain/test_cv_ids.py:117-134` — a text edit retires the old ID and introduces a new one | closed |
| T-04-17 | Repudiation | fabricated fact via a default | high | mitigate | No default-filling: missing required field raises (`tests/cv/test_factstore.py:134-140`), dotted path named (`:71-81`); extras forbidden (`tests/domain/test_cv_ids.py:153-172`) | closed |
| T-04-18 | Tampering | parser writing back into `cv.yaml` | medium | mitigate | `app/cv/import_tex.py:533-546` `write_draft` takes the destination as a parameter; byte-identity after parse+write `tests/cv/test_import_tex.py:263-271` | closed |
| T-04-19 | Tampering | template silently changing rendered bytes | medium | mitigate | Byte-exact golden `tests/golden/test_render_bytes.py:37-61` (bytes read, never written, mutation control can fail); `.gitattributes` pins LF for golden + templates | closed |
| T-04-20 | Denial of Service (self-inflicted) | non-unique IDs / lossy comparison | low | mitigate | Uniqueness asserted at load `app/cv/factstore.py:34-44` + `tests/cv/test_factstore.py:109-128`; fact-count floor `tests/latex/test_fact_equivalence.py:172,191,244`; fuzzy ratio explicitly rejected in `app/domain/tex.py:146-157` docstring | closed |
| T-04-SC (04-03) | Tampering | package installs in plan 04-03 | low | accept | No package installed; `pyyaml`, `jinja2`, `pydantic`, `markupsafe` pre-existing or gated in 04-01. Documented in Accepted Risks Log | closed |
| T-04-21 | Repudiation | vacuous reproduction check | high | mitigate | Minimum fact-count floor asserted on every predicate call (`tests/latex/test_fact_equivalence.py:172,184,195,225,244`); in-test mutation control must fail `:205-229`; skip guard names the exact gate command `:45-54` | closed |
| T-04-22 | Tampering | comparison relaxed into a similarity ratio | medium | mitigate | Exact membership after normalisation `app/domain/tex.py:146-174`; ratio explicitly rejected in the docstring; mutation control `tests/latex/test_fact_equivalence.py:205-229` | closed |
| T-04-23 | Tampering / Repudiation | `snapshot_version` + schema-version type | medium | mitigate | Vocabulary validated before SQL `app/db/repositories/cv_repo.py:71-77`; stringified deliberately with reason in docstring; raw-column driver read `tests/db/test_cv_repo.py:80-102` | closed |
| T-04-24 | Tampering | repository committing the caller's transaction | medium | mitigate | No commit call; write wrapped in SAVEPOINT `app/db/repositories/cv_repo.py:90-92`; non-committing caller leaves no row `tests/db/test_cv_repo.py:105-122` | closed |
| T-04-25 | Repudiation | synthetic artefact row invented | medium | mitigate | `cv_repo` writes only `CvVersion`; grep of `app/` finds no `CvArtifact` writer (model only, `app/db/models.py:370`) | closed |
| T-04-26 | Information Disclosure | fact payload persisted without bound | low | mitigate | `app/db/repositories/cv_repo.py:82-89` carries fixed fields only; no raw-response/unrelated blob field | closed |
| T-04-SC (04-04) | Tampering | package installs in plan 04-04 | low | accept | No package installed; PDF library gated in 04-01, DB driver pre-existing. Documented in Accepted Risks Log | closed |
| T-04-27 | Repudiation | importer guessing an unread value | high | mitigate | Report carries counts/names/line numbers only, no source text (`app/cv/import_tex.py:92-136`); draft to caller-chosen review path `:533-546`; load-then-fail-loudly `tests/cv/test_import_tex.py:244-257`; no-source-text `:287-300` | closed |
| T-04-28 | Information Disclosure | committed verdict + runbook | high | mitigate | `docs/probes/2026-09-21-cv-tex-spike.md` §7 and `docs/runbook-latex-compile.md` carry counts/names/commands only; no e-mail/phone shape present | closed |
| T-04-29 | Repudiation | verdict claiming more than measured | high | mitigate | Verdict `Status: PARTIAL`; proven (§2) vs unproven (§3) separated; D-75 flag confirmation and D-76 fallback explicitly `NOT TAKEN` | closed |
| T-04-30 | Tampering / Repudiation | importer writing over what it read | medium | mitigate | `write_draft` destination is a parameter, default is not the canonical file (`app/cv/import_tex.py:533-546`); source byte-identical `tests/cv/test_import_tex.py:263-271`; content-addressed cycle `tests/cv/test_factstore.py:146-166` | closed |
| T-04-31 | Denial of Service (self-inflicted) | pathological / very large document | medium | mitigate | Bounds in `app/config.py:156-157`; enforced by truncation flag and stopping, never recursion/raise (`app/cv/import_tex.py:160-185,290-295`); tests `tests/cv/test_import_tex.py:203-228` | closed |
| T-04-32 | Spoofing | runbook gate command drifting from lane skip reasons | low | mitigate | Runbook's gate command `docker compose run --rm app pytest -m latex` is byte-identical to the skip reasons in `tests/latex/test_compile.py:32-36` and `tests/latex/test_fact_equivalence.py:49-53` | closed |
| T-04-SC (04-05) | Tampering | package installs in plan 04-05 | low | accept | No package installed; the TexSoup escalation is documented and deliberately NOT installed. Documented in Accepted Risks Log | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on (`high`) count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

**Register hygiene note:** `T-04-SC` is declared once in each of the five PLAN files with a per-plan scope; there are 32 unique numbered threats (T-04-01…T-04-32) plus the five `T-04-SC` occurrences, i.e. 37 registered rows.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-04-01 | T-04-01 | Installing a third-party wheel confers trust in that project's maintainers. The gate reduces slopsquat risk; it does not audit the library source. Out of scope for ASVS L1 (residual risk recorded in 04-01-PLAN.md). | plan 04-01 (human checkpoint) | 2026-09-21 |
| AR-04-02 | T-04-SC (04-02) | Plan 04-02 installs no new package; Tectonic is a checksum-pinned static binary and the Python pins were gated in 04-01. | plan 04-02 | 2026-09-21 |
| AR-04-03 | T-04-SC (04-03) | Plan 04-03 installs no new package. | plan 04-03 | 2026-09-21 |
| AR-04-04 | T-04-SC (04-04) | Plan 04-04 installs no new package. | plan 04-04 | 2026-09-21 |
| AR-04-05 | T-04-SC (04-05) | Plan 04-05 installs no new package; the documented TexSoup parse-tree escalation is deliberately not installed. | plan 04-05 | 2026-09-21 |

*Accepted risks do not resurface in future audit runs.*

---

## Verification Notes (non-blocking)

The following **declared companion assertions** in the plan mitigation texts are not present in the repository. In each case the underlying control itself **is** present in the shipped code (verified above), so the threat is closed at ASVS L1; these are verification-depth gaps, not absent mitigations.

| Threat | Declared extra assertion | Status |
|--------|--------------------------|--------|
| T-04-14 | "asserted by a one-liner that the unsafe loader name is unreachable" | Not found — `safe_load` is used (`factstore.py:56`); no test asserts the loader choice |
| T-04-24 | "asserted by an inspection-based test" (no commit call) | Not found — SAVEPOINT/no-commit verified by runtime test only |
| T-04-28 | "a test asserts no e-mail-shaped and no phone-shaped string appears" in the verdict/runbook | Not found — docs are clean by inspection |
| T-04-29 | "a `PARTIAL` marker is asserted present and a false-finality string is asserted absent" | Not found — the verdict document content satisfies the control |
| T-04-32 | "the runbook test asserts the exact string is present" | Not found — the runbook and lane skip reasons do match byte-for-byte |

*Escalation note for a later hardening pass (not phase-04 blocking): add the four missing companion assertions.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-21 | 37 | 37 | 0 | gsd-security-auditor |

Hermetic evidence command: `.venv/bin/python -m pytest -q tests/test_dependency_pins.py tests/test_render_determinism.py tests/test_cv_hygiene.py tests/cv tests/db/test_cv_repo.py tests/golden tests/test_latex_engine_seam.py tests/domain/test_cv_ids.py tests/domain/test_tex_escape.py tests/domain/test_tex_preamble.py tests/test_deploy_manifest.py` → **114 passed**.

Container-only claims (Tectonic install+prime build, offline fixture compile, installed-binary flag names, `Dockerfile.texlive` fallback measurement) are recorded as **not run** in `04-02-SUMMARY.md` and the verdict document; their code-level controls are present and verified at L1.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-21
