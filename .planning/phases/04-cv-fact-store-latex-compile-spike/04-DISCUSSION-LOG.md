# Phase 4: CV Fact Store + LaTeX Compile Spike - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-21
**Phase:** 4-CV Fact Store + LaTeX Compile Spike
**Areas discussed:** CV source & spike shape, Fact store & ID scheme, Golden test mechanics, Tectonic in image, cv_versions persistence

---

## CV source & spike shape

| Option | Description | Selected |
|--------|-------------|----------|
| Fixture + real-doc spike | Repo commits a synthetic `.tex` fixture; `cv/base.tex` and `cv/cv.yaml` are gitignored local files; the spike runs against the real CV | ✓ |
| Real document only | Operate on the real `.tex` directly; nothing synthetic | |
| Synthetic only this phase | Fixture only; defer the real document entirely | |

**User's choice:** Fixture + real-doc spike
**Notes:** Flagged that `.gitignore` has no `cv/` entry and `compose.yml` mounts only `./data` today.

| Option | Description | Selected |
|--------|-------------|----------|
| Bounded parser + curation | `app/cv/import_tex.py` parses the tractable subset into a draft `cv.yaml` plus an unresolved-items report; human curates the rest | ✓ |
| Hand-author once, no parser | No parsing code; convert by hand | |
| LLM-assisted conversion | Use the LLM backend to convert | |

**User's choice:** Bounded parser + curation
**Notes:** Bounded to one section of the real document in this phase; matches the human-reviewed file ARCHITECTURE.md already names.

| Option | Description | Selected |
|--------|-------------|----------|
| Script + verdict doc | Executable spike reporting counts, plus a written verdict like the Phase 1 scraper probe | ✓ |
| Written verdict only | A prose verdict with no re-runnable measurement | |
| Measurement only, verdict in STATE.md | Counts recorded, no separate doc | |

**User's choice:** Script + verdict doc

| Option | Description | Selected |
|--------|-------------|----------|
| awesome-cv-style stand-in | Package set of a popular modern template (`fontspec`, `paracol`/`tabularx`, `enumitem`, `titlesec`, `hyperref`, `geometry`) plus its own `\newcommand` macros | ✓ |
| Vendor a real template | Commit a third-party template verbatim | |
| Plain article fixture | Easy case: no custom macros | |

**User's choice:** awesome-cv-style stand-in
**Notes:** User's own words: "I don't have my .tex file yet, would it make sense to assume a template that's fairly popular? We can always extend the capabilities later right?" Told plainly that (a) assuming the macro-heavy kind keeps the measurement conservative, and (b) a stand-in cannot answer bundle coverage for a document nobody has seen, so criterion 4 cannot fully close this phase.

| Option | Description | Selected |
|--------|-------------|----------|
| Partial verdict + trigger | State what the stand-in proves, keep an explicit "UNRESOLVED — blocked on the real document" section naming the command to run; blocking unknown #1 stays open | ✓ |
| Resolved on stand-in evidence | Treat the fixture's result as closing criterion 4 | |
| Hold Phase 4 open | Do not ship until the real `.tex` exists | |

**User's choice:** Partial verdict + trigger (prompted by the user: "Settle criterion 4 now")

---

## Fact store & ID scheme

| Option | Description | Selected |
|--------|-------------|----------|
| Hierarchical slug + index | `exp/acme-2021`, `bul/acme-2021/3` — readable in prompts, diffs and logs | ✓ |
| Opaque prefixed keys | `exp_0003`, `bul_0017` | |
| UUID / ULID per item | Globally unique, unreadable | |

**User's choice:** Hierarchical slug + index
**Notes:** Positional suffix is safe because the fact store is frozen; reordering is a RenderPlan concern.

| Option | Description | Selected |
|--------|-------------|----------|
| Frozen; edits are new IDs | Assigned once at import, never reassigned; editing text retires the old ID | ✓ |
| IDs track the item | Re-derive the ID when text changes | |
| Advisory only | IDs are a convenience, not a contract | |

**User's choice:** Frozen; edits are new IDs
**Notes:** Keeps `cv_artifacts.structured_diff` a truthful audit trail.

| Option | Description | Selected |
|--------|-------------|----------|
| §7.3 shape + patch types | Adopt the researched `cv.yaml` shape and define `Suggestion`, `DropBullet`, `BulletWeight` now | ✓ |
| Minimum for CV-03 only | Only what the golden test needs | |
| §7.3 plus extra sections | Add publications/awards/languages/certifications | |

**User's choice:** §7.3 shape + patch types
**Notes:** Extra sections rejected as speculative; Phase 6 is written against the patch types, so deferring them means a `schema_version` bump.

| Option | Description | Selected |
|--------|-------------|----------|
| Pydantic, fail loudly | Single reader; malformed `cv.yaml` raises a path-qualified error; no default-filling, no partial load | ✓ |
| Tolerant defaults | Fill gaps with defaults so loading rarely fails | |
| Editor-time schema only | Validate in the editor, trust the file at runtime | |

**User's choice:** Pydantic, fail loudly
**Notes:** A default-supplied missing date is invented CV content — against the never-fabricate line.

| Option | Description | Selected |
|--------|-------------|----------|
| Escape at the choke point | Jinja `finalize` callback runs `escape_tex` on every plain `str`; `Markup` is the opt-out | ✓ |
| TexString newtype | Escaping as a type property, constructible only through `escape_tex` | |
| Convention + template scan | A test globs templates for unescaped `\VAR{}` | |

**User's choice:** Escape at the choke point
**Notes:** `autoescape=True` was ruled out in advance — `markupsafe`/`html.escape` emits HTML entities and does not escape `%`, `_`, `#`, `$`.

---

## Golden test mechanics

| Option | Description | Selected |
|--------|-------------|----------|
| Rendered-.tex golden + PDF fact check | Byte-exact renderer regression (hermetic) plus PDF text fact-equivalence (the CV-R2 artefact measure) | ✓ |
| PDF text only | Literal CV-R2, but needs Tectonic at test time and leaves no always-on renderer regression | |
| Fact-set via the parser | Compare `parse(base.tex)` against `cv.yaml`; circular — both sides can be wrong together | |

**User's choice:** Rendered-.tex golden + PDF fact check
**Notes:** Established with the user that `render(cv.yaml)` and `base.tex` can never be byte-comparable — different templates by design.

| Option | Description | Selected |
|--------|-------------|----------|
| Marked + run in the container | Own marker, skip-if-absent guard, gate is `docker compose run --rm app pytest -m latex` | ✓ |
| Defer the PDF half to Phase 6 | Cheapest, but leaves criterion 1 half-evidenced | |
| Unconditional requirement | Honest gate, breaks bare `pytest` on a host without the engine | |

**User's choice:** Marked + run in the container
**Notes:** Matches the D-53 precedent; the repo has no CI runner.

| Option | Description | Selected |
|--------|-------------|----------|
| Normalise, then membership assertions | Normalise extractor artefacts, then assert each fact and bullet token-shingle is present | ✓ |
| Exact normalised equality | Also catches reordering, but fails on every cosmetic template difference | |
| Fuzzy ratio threshold | Reuse `rapidfuzz`; a high ratio can hide a dropped bullet | |

**User's choice:** Normalise, then membership assertions

| Option | Description | Selected |
|--------|-------------|----------|
| In-test mutation | Deep-copy the fact store, mutate one field, assert the equivalence check fails | ✓ |
| Committed corruption fixture | A second golden pair reviewed in diffs | |
| Assertion-count floor only | Cheap, cannot catch a too-loose predicate | |

**User's choice:** In-test mutation
**Notes:** Mirrors the existing vacuity guard in `tests/test_config.py`; a fact-count floor rides along.

| Option | Description | Selected |
|--------|-------------|----------|
| Committed in app/latex/templates/ | Application code, versioned with the renderer; `cv/` stays the human's data | ✓ |
| In cv/templates/ on the data volume | User-restyleable without a rebuild, but rendering depends on an untracked file | |
| Derive from base.tex at import | Max fidelity, but re-couples the renderer to a document CV-R1 warns may not decompose | |

**User's choice:** Committed in app/latex/templates/
**Notes:** Recorded as a deliberate correction to ARCHITECTURE.md's volume listing, which puts templates in `cv/`.

---

## Tectonic in image

| Option | Description | Selected |
|--------|-------------|----------|
| Pinned tarball + checksum | Fetch the musl tarball, verify SHA256 in the same RUN, `ARG TECTONIC_VERSION`/`ARG TECTONIC_SHA256` | ✓ |
| Multi-stage copy from a builder image | No download logic, but reintroduces a floating external tag | |
| Vendor the binary in-repo | Fully reproducible, costs tens of MB in the repo | |

**User's choice:** Pinned tarball + checksum

| Option | Description | Selected |
|--------|-------------|----------|
| Compile the fixture at build | Packages land in an image layer; doubles as a build-time proof the engine works | ✓ |
| Prime from an explicit package manifest | Reviewable cached set, but can silently diverge from what the template loads | |
| Let the first compile populate it | Zero build cost, but the first compile needs network — contradicting "offline" | |

**User's choice:** Compile the fixture at build
**Notes:** Same shape as the existing migration smoke ("Acceptance item 9").

| Option | Description | Selected |
|--------|-------------|----------|
| Fail loudly + documented rebuild | Cached-only compile; missing package names itself and the fix (add it to the prime step, rebuild) | ✓ |
| Allow a one-off network warm-up | "Offline" holds only after warm-up; the fetch is invisible unless someone reads the artifact row | |
| Auto-fallback to the texlive image | Nothing fails, but the config value silently overrides itself | |

**User's choice:** Fail loudly + documented rebuild
**Notes:** Flagged that the exact cached-only flag must be verified against `tectonic --help`, not assumed.

| Option | Description | Selected |
|--------|-------------|----------|
| Port + both, texlive built once | `LatexEngine` Protocol + `TectonicEngine`, DI factory, `Dockerfile.texlive` committed and **actually built once** with the result in the verdict doc | ✓ |
| Port + committed-but-unbuilt Dockerfile.texlive | Saves the multi-GB build; "available" then rests on a file no one has run | |
| Single function branching on the setting | Fewest files; no test seam, no DI override | |

**User's choice:** Port + both, texlive built once
**Notes:** One slow build, once; turns criterion 3's "fallback available" into a measured fact.

---

## cv_versions persistence

| Option | Description | Selected |
|--------|-------------|----------|
| File canonical, DB snapshot per revision | `cv.yaml` stays canonical; every accepted revision snapshots into `cv_versions` via a new `cv_repo.py` | ✓ |
| Skip the DB this phase | Smallest diff; the frozen-ID audit story is unbacked until Phase 6 | |
| Import-only snapshot | One row at import; hand curation then drifts from it, so `base_cv_version_id` is confidently wrong | |

**User's choice:** File canonical, DB snapshot per revision
**Notes:** Ground truth verified during discussion: migration 0001 already ships `cv_versions` and `cv_artifacts`; no repository exists for either.

---

## the agent's Discretion

No area was delegated with an explicit "you decide". Left as implementation detail by the shape of the decisions above:

- the exact parser subset in `app/cv/import_tex.py`
- the shape of the unresolved-items report
- the Tectonic cached-only flag name (verify against `tectonic --help`)
- fixture and template file names, and the LaTeX setting names added to `app/config.py`

## Deferred Ideas

None — no idea raised during discussion fell outside Phase 4's scope.
