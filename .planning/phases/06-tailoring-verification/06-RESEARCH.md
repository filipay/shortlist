# Phase 6: Tailoring + Verification - Research

**Researched:** 2026-09-24
**Domain:** Structured-CV tailoring (typed ID patch) + anti-fabrication verification gate + PDF artefact lifecycle
**Confidence:** HIGH on stack/architecture (all read from the tree this session); MEDIUM on the 10-check design (designed here, not sourced — the roadmap explicitly asks for it); MEDIUM on the exact similarity banding thresholds (design item, needs calibration).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Patch op semantics**
- **D-103:** `reweight_bullet` (weight 0.0–2.0) means **within-entry ordering** — a bullet's resolved position in its entry sorts by weight descending. The weight number is never printed. `move_bullet` (`before_id`) remains the explicit positional override.
- **D-104:** `demote_bullet` moves the bullet to the **end of its own entry's list** (lowest prominence), text unchanged, `reason` required and shown in the change log. It is distinct from `drop_bullet` (removed entirely) and from `move_bullet` (explicit position).
- **D-105:** `suggestion` and `gap_finding` are **advisory only** — persisted in `patch_json`/`change_log_json` and surfaced in the change log / requirement-coverage panel, but they never reach the renderer (no field becomes text in the PDF, §7.3). `gap_finding` additionally feeds verification check 6.
- **D-106:** An **invalid patch is rejected all-or-nothing** — any unknown/duplicate id, a section losing all entries, or a drop without a reason aborts the whole patch, writes no artifact, and surfaces the error. No partial apply, no auto-repair (§7.4 raise semantics).

**Tailoring flow**
- **D-107:** The flow is **two-step**: (1) *generate* — one `complete_structured` call returning `TailoringPatch`; (2) *compile* — an explicit user action that applies the patch, renders, compiles, verifies, and persists. Matches TAIL-07 and success criterion 2 ("review … before compiling").
- **D-108:** The pre-compile review shows an **HTML preview of the tailored CV** (final section/bullet order, dropped bullets visibly struck/annotated) **beside the change log** with per-item reasons. No LaTeX/PDF is produced before the user approves.
- **D-109:** The generated patch is **not persisted at generate time**. The review page round-trips it (hidden form field) together with the captured `base_cv_version_id` + fact-store hash. On compile, `apply_patch` re-validates every id and the fact store must still match the captured version/hash or the compile is refused. This **is** the `_verify_original_matches`-style optimistic concurrency guard on `apply_patch` and artifact persistence.
- **D-110:** Tailoring **requires an existing score**. The tailor affordance is only offered for listings that already have a stored requirement list (D-81); unscored listings show "rank first". Tailoring does not re-extract requirements and does not run on unscored listings.

**Verification gate**
- **D-111:** The gate runs **two layers**. Layer 1 is a deterministic **RenderPlan/patch pre-check** (id containment, bullet conservation, temporal consistency, requirement→evidence integrity) that short-circuits **before compiling**. Layer 2 is an **extracted-PDF-text post-check** (metric containment, structured-field entity containment, injection residue, page budget, layout/ATS, verbatim integrity) run after compile (§10.5). PDF text is read via `extract_pdf_text` reached through `asyncio.to_thread`.
- **D-112:** Check 2 "no new named entity" is **structured-field containment only** — every org / title / section-title string in the RenderPlan must resolve to a CvFacts `orgs` / `titles` / `SECTION_TITLES` entry. `bullet.text` is human-authored, immutable, and therefore **not scanned for proper nouns** (a proper noun inside it is real CV content, not fabrication). Deterministic, no NLP, no false positives.
- **D-113:** Check 4 metric containment is **region-scoped**: numeric tokens extracted from the PDF per region, excluding date-like numbers (the entry's `start`/`end` years and months) and layout/page-number artefacts; each remaining number must appear as a token in that region's source facts (`bullet.metrics` / `bullet.text`). Unmatched ⇒ fail. This is the `_novel_numbers`-equivalent with date-like-number exclusion named in the roadmap.
- **D-114:** **All 10 §10.3 checks ship.** Checks 1–7 and 10 are **hard fail** (block); checks 8 (page budget) and 9 (layout/ATS) are **warn-only and never block**. `VerificationResult.passed` = no `fail` check. Warn findings are surfaced but do not prevent download.
- **D-115:** On any fail a **blocked `cv_artifacts` row is written either way**: a Layer 1 fail stores `patch_json` / `change_log_json` / `verification_json` with `pdf_path`/`tex_path` empty; a Layer 2 fail additionally retains the compiled PDF for diagnosis. Neither is downloadable or linkable, and the pipeline **never auto-repairs** (TAIL-06, §10.4).

**Artifact lifecycle & UI**
- **D-116:** The tailoring UI is a **dedicated page** (`/listings/{id}/cv`) owning generate → review → preview → download; the listing detail page links to it. The PDF is served from a route nested under it, inline disposition for the preview embed and `?download=1` for attachment. Every route declares `user: User = Depends(current_user)` (auth seam).
- **D-117:** **Every compile inserts a new `cv_artifacts` row**; the page shows the most recent per listing; older rows are retained as history and never overwritten. Retention/pruning is deferred to Phase 8.
- **D-118:** The "blocked artifact cannot be downloaded or attached" rule is enforced **at the repository layer** (only `ok` artifacts are returned to download/link queries), with route-level refusal as well. Recovery is a **fresh tailor** (new LLM call); the §10.4 "drop this bullet and re-render" affordance is deferred.
- **D-119:** The tailor LLM call draws from the **same `llm_calls` ledger and the same per-run / rolling-24h ceilings** via the reserve-then-call lock (D-91/92/93) — no new counters — plus one new `tailoring_enabled` boolean mirroring `ranking_enabled`.

### the agent's Discretion

Left to the planner/implementer (not re-asked): the exact metric-token normalisation and date-like-number detector; the stop-list (if any) for the entity check; the mechanism that produces the fact-store version/hash carried by the review page; the exact PDF route path and filename scheme; the HTML preview template/markup; the `app/verify/` module layout and `verifier_version` string; the verifier Settings key names; the tailoring system-prompt wording; the exact `TailoringPatch` field ordering. No area was delegated "you decide".

### Deferred Ideas (OUT OF SCOPE)

- §10.4's one-click "drop this bullet and re-render" recovery affordance — deferred; Phase 6 recovery is a fresh tailor (D-118).
- Artifact retention/pruning / a cap on historical `cv_artifacts` rows — Phase 8 (Operations + Polish).
- `_GROUNDING_REVIEW_THRESHOLD`-style similarity banding for confidence tiers — planner to design, not implement speculatively here.
- Cover letter (v2 TAIL-09) and ATS parse check (v2 TAIL-10).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TAIL-01 | User can generate a CV tailored to a specific listing | §Design Q8/Q9 — the generate endpoint + one `complete_structured` call; D-110 precondition. |
| TAIL-02 | Tailoring is a typed patch (move/reweight/demote/drop/reorder) over enumerated IDs, no free-text on the path to the PDF | §Design Q6 — the `TailoringPatch` schema; §Design Q7 — `apply_patch`. |
| TAIL-03 | Never rewrites or invents CV claims — bullet text immutable | `Bullet.text` is immutable by type; the patch has no text field; the canary test in §Validation. |
| TAIL-04 | A verification gate checks the compiled PDF for unsupported content | §Design Q1/Q2/Q3/Q4 — the 10 checks, layered per D-111. |
| TAIL-05 | A CV that fails verification is blocked and cannot be downloaded or attached | §Design Q10 — `compile_status='blocked'` + `ok`-only repository selection + route refusal; the P14 failure-path test. |
| TAIL-06 | Verification never auto-repairs content — it blocks | §10.4 block-don't-repair; no repair code path exists; recovery is a fresh tailor (D-118). |
| TAIL-07 | User can review the tailored CV and its change log before compiling | §Design Q9 — the review page round-trip; `RenderPlan.changes` is the change log. |
| TAIL-08 | Anything dropped from the CV is listed explicitly with a reason | `DropBullet.reason` is required; `DemoteBullet.reason` required; both ride `RenderPlan.changes`. |
| UI-05 | User can preview and download the tailored CV PDF | §Design Q9/Q10 — `GET /listings/{id}/cv/pdf` inline + `?download=1`; blocked → 404. |
</phase_requirements>

## Summary

Phase 6 is the phase where the project's ethical hard line becomes load-bearing code.
The structural guarantee already exists and must not be weakened: the LLM returns a
**typed patch over enumerated IDs**, and there is **no field anywhere in that schema
that becomes text in the PDF** (`ARCHITECTURE.md` §7.3 L713). Phase 6 implements the
patch engine (`apply_patch` currently raises `UnsupportedPatchOp` for every op — a
deliberate stub), the single `TailoringPatch` LLM call, the two-layer verification
gate, the `cv_artifacts` writer with its blocked-row contract, and the dedicated
tailoring page.

The single most important finding for the planner: **almost all of the dangerous
machinery already exists and must be reused, not rebuilt.** `apply_patch`'s id-grounding
loop, `_identity_plan`, `RenderPlan.changes`, `render_plan_to_tex` (with the escape
choke point), `TectonicEngine.compile`, `extract_pdf_text`, `normalise_for_compare` /
`squash`, `INJECTION_PATTERNS`, `complete_structured`, the reserve-then-call lock, and
`cv_repo.snapshot_version`/`current_version` are all shipped. Phase 6 orchestrates them.

Two concrete corrections to the phase brief, verified against the tree this session:

1. **No migration is needed for blocked rows.** `cv_artifacts.tex_path` and `pdf_path`
   are already nullable in migration 0001 (`sa.Column("tex_path", sa.Text)` — no
   `nullable=False`), so a Layer 1 fail storing empty paths is a code-only change. The
   only reason to add migration 0005 would be a new column for the fact-store hash, and
   this research recommends **against** that (reuse the existing `base_cv_version_id`
   column plus `cv_versions.facts_json`).
2. **The D-119 "same ceilings" reuse has a concrete bug.** `llm_call_repo.rank_calls_since`
   filters `purpose == "rank"`, so reusing it verbatim would let tailoring calls escape
   the rolling-24h cap entirely. The ledger `PURPOSES` already contains `"tailor"`, and
   an interactive tailor call has no `run_id`, so the per-run ceiling has no meaning for
   it — see Open Question O1.

**Primary recommendation:** Build `app/verify/` as a pure, fixture-testable module
(Layer 1 on `(facts, plan, patch)`; Layer 2 on `(facts, plan, extracted_text)`), extend
`app/domain/cv.py` with the five-op `TailoringPatch` + the real `apply_patch`, add
`app/pipeline/tailor.py` reusing the ranking stage's spend machinery, add
`app/db/repositories/cv_artifact_repo.py` with an `ok`-only selection, and wire one
`app/api/tailoring.py` router. No new third-party packages.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Patch validation & `apply_patch` (pure) | Domain (`app/domain/cv.py`) | — | Pure projection over `CvFacts`; no I/O, no clock; already the home of `RenderPlan`/`_identity_plan`. |
| Tailoring LLM call | Pipeline (`app/pipeline/tailor.py`) | LLM port (`app/llm`) | Owns the one `complete_structured` call, the ledger row, and the reserve-then-call lock; the port owns the wire. |
| Verification Layer 1 (plan pre-check) | Verifier (`app/verify/`) | Domain | Pure predicate over `(facts, plan, patch)`; must run **before** compile (D-111). |
| Verification Layer 2 (PDF post-check) | Verifier (`app/verify/`) | LaTeX (`extract_pdf_text`) | Consumes extracted PDF text; the extractor stays the one PDF reader. |
| Render `.tex` + compile PDF | LaTeX (`app/latex/`) | — | Already shipped; Phase 6 calls `render_plan_to_tex` → `write_rendered` → `engine.compile`. |
| Fact-store concurrency guard | Domain (`facts_hash`) + Repository (`cv_repo`) | API route | Pure hash from facts; version identity from the repository; the route compares and refuses. |
| Artefact persistence + `ok`-only selection | Repository (`cv_artifact_repo`) | API route | D-118: the blocked-artefact rule is enforced at the repository layer, with route-level refusal too. |
| Review page round-trip | Web/API (`app/api/tailoring.py`) | Templates | Server-rendered HTML + hidden form fields; the patch is re-validated server-side on compile. |
| PDF preview/download | API route | Repository (selection) | `GET .../cv/pdf` inline vs `?download=1`; refuses a non-`ok` artefact. |

## Standard Stack

No new third-party packages are required. Every capability Phase 6 needs is already
pinned in `pyproject.toml`.

### Core (already installed — reuse)

| Library | Version | Purpose in Phase 6 | Why Standard |
|---------|---------|--------------------|--------------|
| `pydantic` | 2.13.5 | `TailoringPatch` discriminated union; `VerificationResult`/`CheckResult` | Already the contract layer; `Field(discriminator="op")` is verified v2 behaviour (`ARCHITECTURE.md` §7.3). |
| `rapidfuzz` | 3.14.6 | Check 6 similarity banding (`fuzz.token_set_ratio`) | Already in the stack for Tier-2 dedup; no new dependency. [VERIFIED: pyproject.toml:28] |
| `pypdf` | 6.19.0 | Layer 2 text extraction via the existing `extract_pdf_text` | The one PDF reader; never a second library. |
| `jinja2` | 3.1.6 | The HTML preview template (standard delimiters) | The LaTeX env is separate; the preview uses the HTML env. |
| `pyyaml` | 6.0.3 | Fact-store load (already in `app/cv/factstore.py`) | Unchanged. |

### Supporting (already installed — reuse)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sqlalchemy` | 2.0.53 | `cv_artifact_repo` writer/reader | The repository layer; no `create_all`. |
| `structlog` | 26.1.0 | Per-stage pipeline logs (`pipeline.tailor_*`) | Mirrors `rank.py`. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `rapidfuzz` token-set ratio for check 6 banding | `difflib.SequenceMatcher` (stdlib) | rapidfuzz is already a pinned dependency and is ~10× faster; stdlib would add nothing. Keep rapidfuzz. |
| Semantic facts hash (`model_dump_json` sha256) | Byte hash of `cv.yaml` | Byte hash invalidates on whitespace-only edits and on a file that is not in git; semantic hash invalidates only on real content change. Recommend semantic. |
| New `cv_artifacts.base_fact_store_hash` column | Store the hash in `verification_json` / reuse `base_cv_version_id` | No migration; the version row already stores `facts_json`, which pins the snapshot. |

**Installation:** none. Do not add a dependency for this phase.

**Version verification:** all versions above were read from `pyproject.toml` this
session; the phase installs nothing, so no registry lookup is required.

## Package Legitimacy Audit

**No external packages are installed by this phase.** Every import Phase 6 needs is
already a pinned runtime dependency in `pyproject.toml` (see Standard Stack). The
Package Legitimacy Gate is therefore vacuous for Phase 6 — there is no new package
name to verify against a registry, and no `postinstall` surface to inspect.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| *(none — no new installs)* | — | — | — | — | — | — |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none.

*If a future revision of this plan proposes a new dependency (e.g. a PDF-preview JS
library), it must go through the gate. Note UI-07 forbids CDN assets, so any preview
library must be vendored — and the `<iframe>`-to-PDF route needs no library at all.*

## Architecture Patterns

### System Architecture Diagram

```
 [USER] listing detail page  ──link──►  GET /listings/{id}/cv
                                              │  (reads: listing, score, latest artifact)
                                              │  score missing ⇒ "rank first" (D-110)
                                              ▼
                              ┌───────────────────────────────┐
                              │ POST /listings/{id}/cv/generate│
                              └───────────────┬───────────────┘
                                              │ reads FactStore (cv.yaml) + listing
                                              │ + stored requirement list (scores row)
                                              ▼
                              ┌───────────────────────────────┐
                              │ complete_structured            │  system = TAILOR_SYSTEM_PROMPT
                              │  schema = TailoringPatch       │  parts = [cv facts, listing,
                              │  purpose="tailor" → llm_calls  │           stored requirements]
                              └───────────────┬───────────────┘
                                              ▼  TailoringPatch (ids only, no free text)
                              ┌───────────────────────────────┐
                              │ apply_patch(facts, patch)      │  raises on unknown/duplicate id,
                              │  → RenderPlan + .changes       │  section emptied, drop w/o reason
                              └───────────────┬───────────────┘
                                              ▼  RenderPlan (ordered, resolved)
                              ┌───────────────────────────────┐
                              │ REVIEW PAGE (no PDF yet, D-108)│  HTML preview of the plan
                              │  hidden: patch_json,           │  + change log (drops + reasons)
                              │  base_cv_version_id, facts_hash│  + gaps + suggestions
                              └───────────────┬───────────────┘
                                              │ user clicks Compile
                                              ▼
                              ┌───────────────────────────────┐
                              │ POST /listings/{id}/cv/compile │  re-validate guard:
                              │  reload facts, recompute hash, │  hash/version mismatch ⇒ REFUSE
                              │  re-parse patch, apply_patch   │
                              └───────────────┬───────────────┘
                                              ▼
                              ┌───────────────────────────────┐
                              │ VERIFY LAYER 1 (plan pre-check)│  checks 1,2a,3,5,6
                              │  fail ⇒ blocked row, no PDF    │  ── short-circuits compile ──
                              └───────────────┬───────────────┘
                                              ▼ pass
                              ┌───────────────────────────────┐
                              │ render .tex → write → compile  │  render_plan_to_tex →
                              │  (asyncio.to_thread for pypdf) │  engine.compile → extract_pdf_text
                              └───────────────┬───────────────┘
                                              ▼
                              ┌───────────────────────────────┐
                              │ VERIFY LAYER 2 (PDF post-check)│  checks 2b,4,7,8w,9w,10
                              └───────┬───────────────┬───────┘
                                      │ PASS          │ FAIL
                                      ▼               ▼
                        cv_artifacts(ok)      cv_artifacts(blocked)
                        downloadable          PDF retained for diagnosis,
                        inline + ?download=1   NOT downloadable, NOT linkable
                                              (repository `ok`-only selection)
```

The direction that matters: **facts → patch → render → verify → artifact**. Nothing
re-parses a PDF to recover CV content, and no verify stage writes back into the patch.

### Recommended Project Structure

```
app/
├── domain/
│   ├── cv.py            # EXTEND: the 5 patch ops, PatchOp union, TailoringPatch,
│   │                    #   facts_hash(), real apply_patch() (replace the stub)
│   └── schemas/
│       └── ranking.py   # unchanged (precedent for a wire-facing schema)
├── verify/              # NEW package (pure, fixture-testable)
│   ├── __init__.py      #   exports verify_plan / verify_text / VERIFIER_VERSION
│   ├── base.py          #   CheckResult, VerificationResult, CheckStatus
│   ├── plan_checks.py   #   Layer 1: checks 1, 2a, 3, 5, 6
│   ├── text_checks.py   #   Layer 2: checks 2b, 4, 7, 8, 9, 10
│   ├── numbers.py       #   metric tokeniser + date-like-number detector (pure)
│   └── grounding.py     #   rapidfuzz banding for check 6 / confidence tiers
├── pipeline/
│   └── tailor.py        # NEW: tailor_listing() — the one structured call + ledger
├── db/repositories/
│   └── cv_artifact_repo.py  # NEW: insert + latest + ok-only selection
├── api/
│   └── tailoring.py     # NEW: the page, generate, compile, pdf routes
└── web/templates/html/
    ├── tailoring.html           # NEW: the dedicated page (D-116)
    ├── _tailoring_review.html   # NEW: the review fragment (preview + change log)
    └── _cv_findings.html        # NEW: the blocked-artefact findings fragment
tests/
├── verify/              # NEW: the deterministic fixtures (P13)
│   ├── fixtures.py
│   └── test_plan_checks.py · test_text_checks.py · test_numbers.py · test_grounding.py
└── fixtures/verify/     # NEW: committed extracted-text samples (*.txt)
```

### Pattern 1: A pure verifier with injected inputs (P13)

**What:** Both layers are pure functions of explicit inputs — no LLM, no compiler, no
network, no clock (except an injected `now` for the temporal check). `VerificationResult`
is a value.
**When to use:** Always; it is what makes the anti-fabrication checks unit-testable.
**Example:**
```python
# app/verify/base.py
class CheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    status: Literal["pass", "warn", "fail"]
    detail: str
    offending: list[str] = []

class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passed: bool
    checks: list[CheckResult]
    findings: list[str]
    extracted_text_hash: str
    page_count: int
    verifier_version: str
```

### Pattern 2: The discriminated-union patch (verified Pydantic v2)

**What:** One common `Literal` tag + `Field(discriminator="op")`, so validation targets
only the matched variant and produces `union_tag_invalid` rather than error proliferation
(`ARCHITECTURE.md` §7.3 L715).
**When to use:** The `PatchOp` union. Note the existing `BulletWeight`/`DropBullet` types
have **no** `op` field today — adding one is a required, small change (see Design Q6).

### Pattern 3: The round-tripped patch is untrusted input

**What:** The review page's hidden `patch_json` is client-controlled and must be
re-parsed with Pydantic and re-grounded server-side on compile. This is safe **by
construction**, not by trust: even a hand-crafted patch has no text field, so it cannot
fabricate.
**When to use:** The compile endpoint. Never deserialise the hidden field and pass it
straight to the renderer.

### Anti-Patterns to Avoid

- **A `suggestions: list[dict]` free-text bag.** §7.3's sketch uses `list[dict]`; that
  weakens the schema. Use the typed `Suggestion` that already exists. A `dict` field is
  exactly the "free text on the path" the phase exists to prevent.
- **Rendering the change log into the PDF.** `reason`, `requirement`, `rationale` are
  UI/audit-only. The renderer consumes only `RenderPlan`.
- **A similarity ratio as the gate.** Check 6's hard fail must be structural (evidence
  present + exists); the rapidfuzz band is advisory only. A fuzzy threshold on a block
  decision is a false-positive machine (mirrors D-70's rejection of a fuzzy ratio).
- **Reusing `facts_present_in` verbatim for Layer 2.** It requires *every* bullet present,
  so a declared drop would produce a false failure. The verifier must iterate the
  **RenderPlan's** surviving bullets instead.
- **Auto-repair / "drop and re-render" in this phase.** Deferred (D-118); any repair
  code path is the fabrication loop §10.4 forbids.
- **A new counter / new Settings ceilings unless O1 says so.** D-119 says reuse.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LaTeX escaping | A second escaper or an `| safe` path | `app/latex/env.py` `finalize` choke point + `escape_tex` | Already non-bypassable (D-67); a second escaper is a bypass. |
| PDF text extraction | A new extractor / OCR | `extract_pdf_text` (`app/latex/compile.py:66`) | The one PDF reader; a second library is forbidden. |
| Text normalisation for comparison | A hand-rolled folding table | `normalise_for_compare` / `squash` (`app/domain/tex.py`) | Already folds extractor artefacts and de-hyphenates. |
| Injection-marker detection | A new pattern list | `INJECTION_PATTERNS` (`app/domain/sanitize.py:83`) | One definition; re-minting would drift from ingest. |
| Structured LLM call + wire shape | A direct `httpx` call | `complete_structured` + `app/llm/builders.py` | Contract-pinned; `parts` is the only untrusted channel. |
| Spend accounting | A second ledger / counter | `llm_call_repo` + the reserve-then-call lock in `rank.py` | D-119: no new counters. |
| Version snapshotting | A new revision table | `cv_repo.snapshot_version` / `current_version` | Already the revision log (D-77). |
| Deterministic render | A new renderer | `render_plan_to_tex` + `write_rendered` | Byte-deterministic, clock-free, golden-tested. |
| Fact ID enumeration | A new ID walker | `iter_fact_ids` | The single grounding set. |

**Key insight:** Phase 6 is an *orchestration* phase. The fabrication-safety property is
already enforced by the type system and the escaping choke point; the verifier is
belt-and-braces over what those cannot see (renderer bugs, template leakage, reflow).

## Common Pitfalls

### Pitfall 1: The stub's `UnsupportedPatchOp` tests survive into the real engine
**What goes wrong:** `tests/domain/test_cv_ids.py:208-215` asserts `apply_patch` raises
`UnsupportedPatchOp` for `BulletWeight`/`DropBullet`. Implementing the ops makes those
tests fail; if they are deleted rather than rewritten, the new behaviour is untested.
**Why it happens:** The stub's loud refusal is deliberately pinned by tests.
**How to avoid:** Rewrite those nodes as the real-op assertions (ordering, demotion,
drop, all-or-nothing) and delete `UnsupportedPatchOp` from `cv.py` and `__all__`.
**Warning signs:** `UnsupportedPatchOp` still appears in `__all__` after the engine ships.

### Pitfall 2: `facts_present_in` false-fails on a declared drop
**What goes wrong:** Layer 2 bullet-presence using the full `CvFacts` flags a correctly
dropped bullet as "missing", blocking a valid tailoring.
**Why it happens:** `facts_present_in` iterates `facts.all_entries()` and requires every
bullet shingle present (`app/domain/tex.py:146-174`).
**How to avoid:** Iterate `RenderPlan` bullets (which already exclude declared drops).
**Warning sign:** a fixture with one declared drop fails check 10.

### Pitfall 3: Page numbers poison metric containment
**What goes wrong:** `\documentclass{article}` prints page numbers by default; pypdf
extracts "1", "2", which are not in any bullet's metrics ⇒ spurious check-4 fail.
**Why it happens:** the template sets no `\pagestyle{empty}`.
**How to avoid:** exclude a lone integer line whose value is ≤ `page_count` (documented
heuristic), and/or add `\pagestyle{empty}` (which changes the golden bytes — a deliberate
template change). See Design Q2.
**Warning sign:** every multi-page artifact fails check 4 on a bare "2".

### Pitfall 4: `rank_calls_since` is purpose-scoped
**What goes wrong:** reusing `rank_calls_since` for tailoring counts zero tailor calls,
so the 24h cap never fires for tailoring.
**Why it happens:** it filters `LlmCall.purpose == "rank"` (`llm_call_repo.py:239`).
**How to avoid:** generalise the read to take a `purpose` (or count `("rank","tailor")`);
see O1.

### Pitfall 5: Reflow warning treated as a block
**What goes wrong:** checks 8/9 block a valid CV, contradicting D-114 and CV-R3.
**How to avoid:** `VerificationResult.passed` = no `fail`; warn findings surface but do
not gate. Never auto-truncate to fit (`ARCHITECTURE.md` CV-R3).
**Warning sign:** a two-page CV on a `max_pages: 1` store cannot download.

### Pitfall 6: The fact-store guard compares the wrong thing
**What goes wrong:** the guard compares a byte hash and refuses a compile after a
whitespace-only edit; or it trusts the client's `base_cv_version_id` without re-reading.
**How to avoid:** recompute a **semantic** hash from the loaded `CvFacts`; compare both
hash and `cv_repo.current_version()`. See Design Q5.

## Design Decisions — the 12 questions the plan needs answered

> These are *design* answers, not sourced facts. They are grounded in the actual code
> (read this session) and `ARCHITECTURE.md` §10, and each carries a confidence tag. Where
> a decision is genuinely open it is flagged and cross-referenced to Open Questions.

### Q1 — The 10 checks, precisely

Layer assignment is D-111's. `VerificationResult.passed = no check has status "fail"`
(D-114). Inputs are `facts: CvFacts`, `plan: RenderPlan`, `patch: TailoringPatch`,
`text: str` (extracted), `page_count: int`, optional `now`.

| # | id (string) | Layer | Input | Predicate (exact) | Failure status | Fixture that proves it fails |
|---|-------------|-------|-------|-------------------|----------------|------------------------------|
| 1 | `id_containment` | 1 | facts, plan | Every id in `plan` (section/entry/bullet/skill) ∈ `set(iter_fact_ids(facts))`. | fail | a hand-built `RenderPlan` carrying `bul/ghost/1`. |
| 2a | `entity_resolvable` | 1 | facts, plan | Every `RenderedEntry.org` ∈ `{org.name}` ∪ `{org.aliases}`; every `RenderedEntry.title` ∈ `{title.name}`; every `RenderedSection.title` ∈ `SECTION_TITLES.values()`. | fail | a plan whose entry org is `"Globex"`. |
| 2b | `entity_present` | 2 | plan, text | Every resolved org/title/section-title string from the plan is `squash()`-present in `squash(text)`. | fail | a text missing the company name. |
| 3 | `bullet_conservation` | 1 | facts, plan, patch | `{b.id for plan bullets}` == `{b.id for facts bullets} − {declared drop ids}`, **both directions**. | fail | a plan missing a bullet with no `drop_bullet`; a plan retaining a declared drop. |
| 4 | `metric_containment` | 2 | facts, plan, text | Per region: every digit-core token in the region ∉ date-like/page-number excluded set must ∈ that region's allowed token set. | fail | a text whose bullet says `95%` where the fact says `40%`. |
| 5 | `temporal_consistency` | 1 | facts | For every entry: `end is None or end >= start`; no `end < start`; if `now` is supplied, no `start > now` and no `end > now`. | fail | an entry `start: "2024-01", end: "2023-01"`. |
| 6 | `requirement_evidence` | 1 | facts, patch | Every `GapFinding` with `status != "gap"` has ≥1 `evidence_id` ∈ `iter_fact_ids(facts)`; every `status == "gap"` has no resolvable evidence. | fail | a `direct` finding with `evidence_ids=[]`; a `direct` with a ghost id. |
| 7 | `injection_residue` | 2 | text | No `pattern.search(normalise_for_compare(text))` for any `pattern in INJECTION_PATTERNS`. | fail | a text containing "ignore previous instructions". |
| 8 | `page_budget` | 2 | facts, page_count | `page_count <= facts.meta.max_pages`. | **warn** | a 3-page extract against `max_pages: 2`. |
| 9 | `layout_ats` | 2 | facts, plan, text | Every section title present; every entry `date_range_label` present (parseable `YYYY-MM`); the template is single-column (a code assertion, not text). | **warn** | a text missing the `Skills` heading. |
| 10 | `verbatim_integrity` | 2 | plan, text | For every plan bullet with `evidence == "verbatim"`, `squash(bullet.text) in squash(text)`. | fail | a verbatim bullet reworded in the extract. |

Notes:
- Check 1 is belt-and-braces: `apply_patch` already raises `UnknownIdError` for an unknown
  id, so check 1 only fires on a renderer/plan-construction bug — which is the point.
- Check 3 is the CV-R5 silent-condensing catcher. "Both directions" is load-bearing: the
  reverse catches a declared drop that was *not* actually dropped.
- Check 5's `now` is **injected** so the default-lane fixtures stay clock-free; omit it in
  fixtures and only pass it from the pipeline.
- Check 7 reuses the ingest pattern list — one definition (`INJECTION_PATTERNS`,
  `app/domain/sanitize.py:83`, exported in `__all__` at L244). Because the CV is the
  user's own immutable text, a match is almost certainly listing-text leakage; a false
  positive is possible in principle but the phase's posture is block-and-review.
  Confidence: MEDIUM on false-positive rate (unmeasured; no real corpus).
- Check 9's "single column" cannot be asserted from text; assert it against the committed
  template (`app/latex/templates/cv.tex.jinja` uses no `multicols`/`paracol` columns) or
  skip it as a template invariant. Warn-only either way.

### Q2 — Metric containment (check 4, D-113)

**Algorithm (region-scoped, deterministic, pure):**

1. **Region segmentation.** In `squash(text)`, locate each plan entry's resolved
   `org` string in plan order. Region *i* = `[pos(org_i), pos(org_{i+1}))`, the last
   region running to end-of-text. An org that is not found is a check-2b failure, not a
   metric failure. This gives reliable regions without parsing LaTeX, because the
   template emits the org verbatim on the entry header line.
2. **Allowed token set per region.** The **digit cores** extracted from that entry's
   **surviving** bullets' `text` **and** `metrics`, plus the entry's `dates` label, plus
   the org/title strings. "Digit core" = a maximal `\d+(?:[.,]\d+)?` run with the decimal
   separator normalised to `.` and thousands separators removed.
3. **Excluded set.** Digit cores from every entry's `start`/`end` (date-like), plus any
   token that is a lone integer line with value `1..page_count` (page-number artefact),
   plus digit cores from the document's contact block only if they are not already allowed
   (they are allowed, being source facts).
4. **Candidate tokens.** Extract digit cores from the region's text, subtract the excluded
   set, and assert each remaining token ∈ the region's allowed set. Any surplus ⇒ `fail`,
   with the offending token(s) and region id in `offending`.

**Normalisation rules (the edge cases):**

| Case | Rule |
|------|------|
| `"5+"` vs `"5"` | digit core is `5` on both sides — a plus affix does not create a new token. |
| `"5-10"` (range) | two cores, `5` and `10`. |
| `"40%"` | core `40`. |
| `"0.5"` / `"1,200"` | core `0.5` / `1200`. |
| `"€50k"` / `"$1,200"` | core `50` / `1200`; magnitude suffix dropped (a `50k` claim and a `50000` claim are different strings and do not match — correct). |
| `"2021-03"` (date) | cores `2021`, `03` — both in the excluded set (date-like). |
| `"3rd"` | core `3`. |
| page number `"2"` | excluded when it is a lone integer line ≤ `page_count`. |

**Confidence:** MEDIUM. The segmentation and tokeniser are designed here, not sourced;
the fixture matrix in §Validation is what validates them. The digit-core choice is a
deliberate tradeoff: it tolerates extractor lossiness and affix differences, at the cost
of not distinguishing `50k` from `50000` (acceptable — they are different source strings
and would each have to appear in the source).

### Q3 — Entity containment (check 2, D-112)

- **Containment set (structured fields only):** `Org.name` ∪ `Org.aliases` (the `aliases`
  field exists: `app/domain/cv.py:178`), `Title.name`, `SECTION_TITLES.values()`.
  [VERIFIED: app/domain/cv.py:65-68 — `SECTION_TITLES: dict[str, str] = {"sec.experience": "Experience", "sec.skills": "Skills"}`]
- **Comparison function:** reuse `normalise_for_compare` + `squash` from
  `app/domain/tex.py`. Strict membership, never a ratio — the same D-70 rule the fact
  equivalence lane uses (`app/domain/tex.py:110-134`).
- **Stop-list:** **not needed.** D-112's narrowing to structured fields is precisely what
  removes the false-positive problem that a proper-noun scan over `bullet.text` would
  create. There is no NLP and no capitalisation heuristic. This directly supersedes
  §10.3's "any capitalised proper-noun sequence" wording — record that in the plan.
- **Layer split:** resolvability (2a) is Layer 1; presence (2b) is Layer 2.

### Q4 — Grounding confidence banding (check 6)

**Design (a design item, not existing code):**

- **Metric:** `rapidfuzz.fuzz.token_set_ratio(normalise_for_compare(requirement), normalise_for_compare(evidence_text))`, where `evidence_text` is the concatenation of the
  cited evidence bullets' `text`. Token-set handles word order and is robust to length.
- **Bands (two Settings thresholds):**
  - `grounded`: score ≥ `tailoring_grounding_threshold` (proposed default **80**)
  - `borderline`: `tailoring_grounding_review_threshold` ≤ score < `tailoring_grounding_threshold` (proposed default **55**)
  - `ungrounded`: score < `tailoring_grounding_review_threshold`
- **Mapping to hard-fail vs advisory:** the **hard fail is structural** and needs no
  similarity: a non-`gap` `GapFinding` with no resolvable `evidence_id` fails. The
  **band is advisory**: it rides the `CheckResult` as a `warn` (or a `detail` on a pass)
  and drives the UI's per-requirement confidence label and the "presenting adjacency as
  a direct match" surface. Rationale: a fuzzy threshold must not be load-bearing on a
  block decision — the same argument D-70 makes against a fuzzy membership ratio. A
  `direct` claim whose cited evidence bands `ungrounded` is exactly the case the human
  should see, but it is not provably fabricated, so it warns.
- **Where it lives:** `app/verify/grounding.py`; thresholds in `Settings` (PLAT-04).
- **Confidence:** LOW–MEDIUM on the exact threshold values. They are uncalibrated
  against a real CV/listing corpus; ship them as Settings and treat calibration as a
  follow-up (mirrors the dedup θ posture). Do not present 80/55 as measured.

### Q5 — Optimistic concurrency (D-109)

**What the review page carries (three hidden fields):**
- `patch_json` — the generated `TailoringPatch` as JSON.
- `base_cv_version_id` — the `cv_versions.id` captured at generate time from
  `cv_repo.current_version()` (or `snapshot_version`).
- `fact_store_hash` — the captured semantic hash (below).

**What produces the hash (there is no hash today — this designs it):**
Add a **pure** function to `app/domain/cv.py`:
```python
import hashlib

def facts_hash(facts: CvFacts) -> str:
    """Deterministic semantic hash of the fact store. Pydantic v2 dumps fields in
    declaration order, so two equal documents hash equal and a whitespace-only
    cv.yaml edit does not invalidate a patch."""
    return hashlib.sha256(facts.model_dump_json().encode("utf-8")).hexdigest()
```
`hashlib` is stdlib, so `app/domain/cv.py`'s purity contract (stdlib + pydantic only)
is preserved. A **semantic** hash is preferred over a byte hash of `cv.yaml`: a byte
hash refuses a compile after a comment or whitespace edit, which is a false refusal.

**How `apply_patch` re-validates at compile time (the guard):**
1. Reload `facts = load_facts(cv_dir / cv.yaml)` (loud `CvFactStoreError` on failure).
2. `facts_hash(facts) == captured_hash`? If not ⇒ refuse.
3. `cv_repo.current_version().id == captured_base_cv_version_id`? If not ⇒ refuse.
4. Re-parse `patch_json` into `TailoringPatch` (Pydantic) — client input is untrusted.
5. `apply_patch(facts, patch)` re-validates every id (raises `UnknownIdError` on drift).

**Persisted identity (no migration):** `cv_artifacts.base_cv_version_id` already exists
[VERIFIED: app/db/models.py:406], and `cv_versions.facts_json` stores the full snapshot
[VERIFIED: app/db/models.py:393], so the version row pins the exact facts. Store the
captured `fact_store_hash` inside `verification_json` for audit; do **not** add a column.
This answers Q10's nullability question as a side effect.

**Refusal path:** the compile endpoint returns a 409 HTML fragment with
`data-error="stale-patch"` and a sentence ("the CV fact store changed since this patch was
generated — generate a fresh tailoring"). **No artifact row is written.** Recovery is a
fresh tailor (D-118).

**Naming:** call the guard `verify_original_matches(facts, *, captured_hash,
captured_version_id, current_version_id) -> GuardResult` (a value, not an exception),
mirroring the `_verify_original_matches` pattern the roadmap names. Confidence: HIGH on
the mechanism; the exact field names are discretion.

### Q6 — `TailoringPatch` schema

**Location recommendation:** define the ops and `TailoringPatch` in **`app/domain/cv.py`**,
co-located with `Bullet`/`CvFacts`/`apply_patch`. §7.3 sketches `app/domain/schemas/patch.py`,
but `apply_patch` lives in `cv.py`; putting the schema in `schemas/` would force a
`cv.py ↔ schemas/patch.py` import cycle (the schema needs `CvFacts`; `apply_patch` needs
the schema). This is the same kind of documented correction Phase 4 made for the template
location. If a wire-namespace alias is wanted, `schemas/patch.py` can re-export
`TailoringPatch` — but there must be **one definition**.

**Field-by-field:**

| Type | Fields | Notes |
|------|--------|-------|
| `BulletMove` | `op: Literal["move_bullet"]`, `bullet_id: str`, `before_id: str \| None = None` | `before_id=None` ⇒ first in its entry. A `before_id` in a different entry is ill-formed — reject (Design Q7). |
| `BulletWeight` | `op: Literal["reweight_bullet"]`, `bullet_id: str`, `weight: Annotated[float, Field(ge=0.0, le=2.0)]` | **EXISTS without `op`** [VERIFIED: app/domain/cv.py:386-390] — add the tag. Weight is never printed (D-103). |
| `DemoteBullet` | `op: Literal["demote_bullet"]`, `bullet_id: str`, `reason: str` | `reason` required (D-104); shown in the change log; never rendered. |
| `DropBullet` | `op: Literal["drop_bullet"]`, `bullet_id: str`, `reason: str` | **EXISTS without `op`** [VERIFIED: app/domain/cv.py:393-397]. Reason required. |
| `ReorderSection` | `op: Literal["reorder_section"]`, `section_id: str`, `order: int` | Ties broken by declaration order, as `ordered_sections` does. |
| `GapFinding` | `requirement: str`, `status: Literal["direct","transferable","adjacent","gap"]`, `evidence_ids: list[str] = []` | Feeds check 6. `requirement` is UI-only. |
| `PatchOp` | `Annotated[BulletMove \| BulletWeight \| DemoteBullet \| DropBullet \| ReorderSection, Field(discriminator="op")]` | |
| `Suggestion` | `bullet_id: str`, `evidence_ids: list[str] = []`, `rationale: str` | **EXISTS** [VERIFIED: app/domain/cv.py:400-409]. Reuse it — do **not** follow §7.3's `suggestions: list[dict]`. |
| `TailoringPatch` | `listing_id: int`, `ops: list[PatchOp]`, `gaps: list[GapFinding]`, `suggestions: list[Suggestion] = []` | |

**No free-text field can become PDF text — confirmed.** The renderer consumes only
`RenderPlan`, whose values are all derived from `CvFacts` (org names, titles, bullet text,
dates, locations, skill labels). `reason`, `requirement`, `rationale` and `op`/`weight`/
`order` never enter `RenderPlan`. The load-bearing guarantee, verbatim from §7.3 L713:

> "There is **no field anywhere in this schema that becomes text in the PDF**. Every
> string is either an id (validated), a reason (UI-only), or a requirement (echoed from
> the listing, shown in the gap checklist)."

**`extra` policy — a real decision.** The domain convention is `extra="forbid"`
(`_Forbid`), while the wire-facing response schema `RankingResponse` uses
`extra="ignore"` for salvage tolerance. Recommendation: **`extra="forbid"` on the op
types and `TailoringPatch`.** Two reasons: (a) `extra="forbid"` emits
`additionalProperties: false` into `model_json_schema()`, which **constrains the model at
the wire** — the stronger fabrication-safety posture; (b) a malformed extra key should
fail the call (bounded retry), not be silently dropped from a stored contract. Note the
divergence from `ranking.py` in the plan. Confidence: MEDIUM — this is a judgement call
the planner should pin explicitly.

**`reason` non-empty:** Pydantic allows `reason=""`. Add `Field(min_length=1)` (or an
explicit `apply_patch` check) so a "drop with a reason" cannot be satisfied by an empty
string (D-106).

### Q7 — `apply_patch` algorithm

**Signature:** change to `apply_patch(facts: CvFacts, patch: TailoringPatch | None = None)
-> RenderPlan`. The `patch=None` form returns the identity plan, so the existing
no-op callers keep working [VERIFIED: tests/latex/test_fact_equivalence.py:141,
tests/golden/test_render_bytes.py:34, tests/cv/test_factstore.py:181 call `apply_patch(facts)`].

**Validation order (all-or-nothing; raise on the first violation):**
1. **Unknown id** — every id named by `ops`/`gaps` ∈ `set(iter_fact_ids(facts))`, else
   `UnknownIdError` (already implemented in the stub via `_referenced_ids`).
2. **Duplicate id** — no `bullet_id`/`section_id` targeted by two mutating ops, else
   `InvalidPatchError`. (A `reweight` + a `demote` on the same bullet is a conflict.)
3. **Section losing all entries** — no `reorder_section`/other op may leave a section with
   zero entries, else `InvalidPatchError`. (Dropping an entry is not a supported op, so
   this can only fire via a future op — keep the guard.)
4. **Drop/demote without a reason** — enforced by `min_length=1` at validation.
5. **Cross-entry move** — a `move_bullet` whose `before_id` is in a different entry than
   `bullet_id` is rejected (`InvalidPatchError`). Recommended; flag as a decision.
6. **Build the ordered plan** and attach `changes`.

**Ordering semantics (the precedence rules D-103/D-104 leave implicit):**
- Base within-entry order = declaration order, stable-sorted by `reweight` weight
  descending (ties keep declaration order).
- `demote_bullet` forces the bullet after all non-demoted bullets of its entry, in
  declaration order among demoted bullets (lowest prominence, D-104).
- `move_bullet` is the **explicit positional override**: applied after base ordering;
  `before_id=None` inserts first. If both a move and a reweight target the same entry,
  the move wins for its own bullet.
- `reorder_section` sets `order`; sections stable-sorted by `order` (declaration tie-break).

**`RenderPlan.changes` is the change log (D-108/TAIL-08).** One `ChangeRecord` per applied
op, in patch order:
`ChangeRecord(op="drop_bullet", target_id="bul/…/2", detail="<reason>")`. Drops and
demotions carry the model's `reason` in `detail`; reweights carry the weight; moves carry
the destination; section reorders carry the new order. `changes` is persisted as
`change_log_json`.

**`UnsupportedPatchOp` becomes:** **deleted.** It is the stub's placeholder; Phase 6
implements all five ops. Remove it from `app/domain/cv.py` and its `__all__`, and rewrite
`tests/domain/test_cv_ids.py:185-225` to assert the real semantics. `UnknownIdError`
stays; add `InvalidPatchError` for duplicate/empty-section/cross-entry cases (or reuse
`ValueError` — recommend a named type for a legible boundary).

### Q8 — The tailoring LLM call

- **Call:** `complete_structured(schema=TailoringPatch, system=TAILOR_SYSTEM_PROMPT,
  parts=build_tailoring_parts(facts, listing, score), model=settings.opencode_model,
  tools=(), retries=settings.opencode_max_retries)` — the same shape `rank_listing` uses.
- **`parts` (the only untrusted channel):** the CV fact store rendered with ids (reuse the
  shape of `rank._cv_facts_text`), the single listing (reuse `rank._listing_text`), and the
  **stored** requirement list from the `scores` row (D-81/D-110 — do not re-extract).
  `system` is a frozen constant with no interpolation.
- **Injection boundary:** listing description travels only in `parts`; the model returns
  ids, so even a successful injection cannot produce PDF text.
- **Ledger (D-119):** one `llm_call_repo.record_llm_call(session, purpose="tailor", …)` per
  call. `"tailor"` is already in `PURPOSES` [VERIFIED: app/db/repositories/llm_call_repo.py:41
  — `frozenset({"rank", "narrate", "tailor", "extract", "probe"})`]. Record `run_id=None`
  (tailoring is on-demand, not part of a run).
- **Spend cap — see O1.** The rolling-24h read must be purpose-aware; `rank_calls_since`
  is not. The per-run ceiling has no meaning for a call with no run. Recommended:
  generalise to `calls_since(session, *, purpose, now)` and reuse the **24h** ceiling
  value; do not invent a per-run tailoring cap. Reuse the reserve-then-call lock
  (`rank._reserve`/`_release`) — but note it is module-private and shared; the planner
  should decide whether to import it or hoist it to a shared spend module.
- **New Settings:** `tailoring_enabled: bool = True` (mirrors `ranking_enabled`,
  surface-only in `test_config.py`). Model: reuse `settings.opencode_model` for v1 and
  record `result.model` on the artifact row (`cv_artifacts.model` exists); a separate
  `tailoring_model` is a possible later knob (ARCHITECTURE §6.4 says the two pipelines
  *should* be able to differ — flag, do not build).

### Q9 — Two-step flow & review-page round-trip (D-107/108/109)

- **Generate** (`POST /listings/{id}/cv/generate`): precondition — a score row exists
  (`score_repo.read_score_for_listing`), else the page shows "rank first" (D-110). Load
  facts; call the LLM once; `apply_patch`; render the **HTML preview** from the
  `RenderPlan` (new `_tailoring_review.html`, standard HTML env) beside the change log
  (`RenderPlan.changes` + drops + suggestions + gaps). Return the review fragment carrying
  the three hidden fields (Q5). **No artifact row, no `.tex`, no PDF** (D-108/D-109).
- **Compile** (`POST /listings/{id}/cv/compile`): the five-step guard (Q5) → `apply_patch`
  → Layer 1 verify (short-circuit) → `render_plan_to_tex` → `write_rendered` to
  `artifacts/<listing_id>/cv.tex` → `engine.compile` → `extract_pdf_text` via
  `asyncio.to_thread` → Layer 2 verify → insert the `cv_artifacts` row → return the result
  fragment (download link on pass, findings on block).
- **Round-trip integrity:** the hidden `patch_json` is untrusted; re-parse + re-ground
  server-side. Safe by construction: no text field exists, so even a forged patch can only
  reorder/reweight/demote/drop/reorder.
- **Artifact directory:** `Settings.artifacts_dir` (default `/artifacts`) +
  `artifacts/<listing_id>/`; the filename scheme is discretion (proposed `cv.tex`/`cv.pdf`
  per artifact id to avoid collisions, e.g. `artifacts/<listing_id>/<artifact_id>/`).

### Q10 — `cv_artifacts` persistence & blocked rows (D-115/117/118)

- **Nullability: no migration needed.** `tex_path` and `pdf_path` are nullable in migration
  0001 [VERIFIED: alembic/versions/0001_initial_schema.py:245-246 — `sa.Column("tex_path",
  sa.Text)` / `sa.Column("pdf_path", sa.Text)`, no `nullable=False`] and in the model
  [VERIFIED: app/db/models.py:409-410]. Store `None` for a Layer 1 fail; set both for a
  Layer 2 fail (retained for diagnosis).
- **`compile_status` values** (existing CHECK) [VERIFIED: app/db/models.py:427-430 —
  `"compile_status IN ('ok','failed','blocked')"`]:
  - `ok` — Layer 1 + Layer 2 pass ⇒ downloadable.
  - `failed` — the engine failed (non-zero exit / timeout / no output). Verification never
    ran. Not downloadable.
  - `blocked` — a verification `fail` (either layer). Not downloadable, not linkable.
- **Row shape:** `patch_json` = the validated patch; `change_log_json` = `RenderPlan.changes`;
  `verification_json` = `VerificationResult.model_dump()` (+ the captured `fact_store_hash`);
  `page_count`; `ats_checks_json` = check 9's findings; `tex_hash`/`pdf_hash`; `compiled_at`;
  `compile_log`; `backend`/`provider`/`model`.
- **Repository (`app/db/repositories/cv_artifact_repo.py`):**
  - `insert_artifact(session, …)` — one row per compile (D-117), never commits (SAVEPOINT,
    house rule).
  - `latest_for_listing(session, listing_id, *, ok_only=True)` — newest by
    `(created_at, id)` desc; `ok_only` is the **D-118 repository-level enforcement**.
  - `read_for_download(session, artifact_id, *, ok_only=True)` — same predicate.
  - `history_for_listing(session, listing_id)` — for the retained history view.
- **Route-level refusal:** `GET /listings/{id}/cv/pdf` returns 404/403 when the selected
  artifact is not `ok`. The route uses the `ok`-only repository selection, so a blocked row
  is unreachable even by artifact id.
- **`cv_repo` extension:** none needed beyond what exists (`current_version`); the artifact
  repo is a new module so `cv_repo` keeps its single concern (D-77).

### Q11 — Verifier Settings keys & module layout

**Module layout:** see Recommended Project Structure. `app/verify/` is a **new package**
(pure; may import `rapidfuzz`, unlike `app/domain`). Do not put it under `app/domain`
(the import-discipline test scans `app/domain` and rapidfuzz would violate the "stdlib +
pydantic only" rule).

**`verifier_version`:** `VERIFIER_VERSION = "1.0.0"` in `app/verify/base.py`, copied into
`VerificationResult.verifier_version` and persisted, so "a change here explains a change
in outcomes" (§10.2). Bump on any check change.

**Proposed Settings keys:**
| Key | Type | Default | In `REQUIRED_SETTINGS_FIELDS`? | In `LIMIT_FIELDS`? |
|-----|------|---------|-------------------------------|--------------------|
| `tailoring_enabled` | bool | `True` | yes | **no** (boolean — same asymmetry as `ranking_enabled`) |
| `tailoring_grounding_threshold` | int | `80` | yes | yes (distinctive int ≥ 3) |
| `tailoring_grounding_review_threshold` | int | `55` | yes | yes |

`tests/test_config.py` updates (surface + absence contracts): add the three names to
`REQUIRED_SETTINGS_FIELDS`; add a `PHASE_SIX_CEILINGS` guard test mirroring
`test_the_phase_five_ceilings_are_guarded`; add an env-tunability test; add the two
thresholds to `LIMIT_FIELDS`; and assert `tailoring_enabled not in LIMIT_FIELDS`. The
`SCANNED_DIRS` tuple already covers `app/pipeline`, `app/latex`, `app/cv` — the new
`app/verify` and `app/pipeline/tailor.py` are covered by `app/pipeline` (tailor) but
**`app/verify` is not**; decide whether to add it to `SCANNED_DIRS` (recommend yes, so a
hard-coded similarity threshold in the verifier is caught). Note: `LIMIT_FIELDS` only
scans distinctive integer literals; the grounding thresholds (80/55) are new and collide
with no existing value.

### Q12 — Testing strategy

Per PITFALLS P13, the verifier must be testable with **no LLM, no compiler, no network**.

- **Fixture shape:** `tests/verify/fixtures.py` builds `(facts, plan, patch, text,
  page_count, expected: dict[check_id, "pass"|"warn"|"fail"])`. Facts come from
  `load_facts(tests/fixtures/cv/awesomecv_standin.yaml)`; plans come from
  `apply_patch(facts, patch)`; `text` is a committed `tests/fixtures/verify/*.txt` sample
  that mimics `pypdf` output for the stand-in (hand-written, so no engine is needed).
- **Mutation fixtures (one per hard-fail check):** an injected `95%` (check 4); a missing
  bullet with no drop (check 3); a retained declared drop (check 3 reverse); a reworded
  verbatim bullet (check 10); a missing company name (check 2b); a `direct` finding with no
  evidence (check 6); an `"ignore previous instructions"` line (check 7); a bad date range
  (check 5); a ghost plan id (check 1).
- **Warn-only fixtures:** a 3-page extract against `max_pages: 2` (check 8) asserts
  `status == "warn"` and `VerificationResult.passed is True` (D-114).
- **The load-bearing guarantee test:** build a patch whose `reason`/`requirement`/
  `rationale` are canary strings, render to `.tex`, assert the canaries are **absent** from
  the `.tex` (default lane, no engine) and from the fixture text. This pins §7.3 L713.
- **`apply_patch` unit tests:** unknown id; duplicate id; section losing all entries;
  drop without a reason; reweight ordering (stable, ties by declaration); demote ordering
  (after non-demoted); move precedence; cross-entry move rejection; identity when
  `patch=None`.
- **The P14 failure-path test:** insert a `blocked` `cv_artifacts` row, then assert
  `GET /listings/{id}/cv/pdf` returns 404/403, `latest_for_listing(ok_only=True)` excludes
  it, and `read_for_download(ok_only=True)` returns `None`. Also assert a `failed` row is
  excluded.
- **Endpoint tests:** generate with an overridden LLM stub returning a valid
  `TailoringPatch` (the default `OfflineLLMBackend` returns `ok=False`); compile with a
  mutated hash ⇒ 409 stale-patch and **no artifact row**; compile pass ⇒ `ok` row +
  downloadable PDF (this needs the engine — mark it `latex` and let it skip by default, or
  override `get_latex_engine` with a stub that writes a canned PDF).
- **Determinism:** same facts + patch ⇒ identical `RenderPlan` ⇒ identical `.tex`
  (mirrors `tests/test_render_determinism.py`).
- **Golden preview (optional):** the HTML review fragment for a known patch.

## Code Examples

Verified patterns from the actual tree (read this session).

### The patch ops already in the domain (add the `op` tag)
```python
# Source: app/domain/cv.py:386-409 (verbatim)
class BulletWeight(_Forbid):
    """Re-weight a bullet within its entry."""
    bullet_id: str
    weight: Annotated[float, Field(ge=0.0, le=2.0)]

class DropBullet(_Forbid):
    """Drop a bullet. The reason is REQUIRED so a structural drop is loud."""
    bullet_id: str
    reason: str

class Suggestion(_Forbid):
    """A human-approved suggestion. NEVER applied to a render."""
    bullet_id: str
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str
```

### The stub to replace
```python
# Source: app/domain/cv.py:465-492 (the loud placeholder Phase 6 replaces)
def apply_patch(facts: CvFacts, ops: Iterable[object] = ()) -> RenderPlan:
    ...
    for op in operations:
        raise UnsupportedPatchOp(
            f"{type(op).__name__} is declared but not implemented in this phase;"
            f" a silent no-op would be a fabrication path: {op!r}"
        )
    return _identity_plan(facts)
```

### The existing grounding set and change-log type
```python
# Source: app/domain/cv.py:306-321 / 338-343
def iter_fact_ids(facts: CvFacts) -> Iterator[str]: ...   # the grounding set

class ChangeRecord(_Forbid):
    op: str
    target_id: str
    detail: str = ""
```

### The extraction + normalisation pair the verifier reuses
```python
# Source: app/latex/compile.py:66 and app/domain/tex.py:125-134
def extract_pdf_text(pdf_path: Path) -> str: ...          # call via asyncio.to_thread
def squash(text: str) -> str: ...                          # whitespace-insensitive
def normalise_for_compare(text: str) -> str: ...           # preserves spaces
```

### The blocked-row CHECK and the nullable paths (no migration)
```python
# Source: alembic/versions/0001_initial_schema.py:245-250 / 261-264
sa.Column("tex_path", sa.Text),          # nullable
sa.Column("pdf_path", sa.Text),          # nullable
sa.Column("compile_status", sa.String(16), nullable=False),
sa.CheckConstraint("compile_status IN ('ok','failed','blocked')",
                   name="ck_cv_artifacts_compile_status"),
```

### The ranking call shape to mirror
```python
# Source: app/pipeline/rank.py:266-284
result = await backend.complete_structured(
    schema=RankingResponse, system=RANK_SYSTEM_PROMPT, parts=parts,
    model=settings.opencode_model, tools=(), retries=settings.opencode_max_retries,
)
await llm_call_repo.record_llm_call(session, purpose="rank", status=result.status,
                                    result=result, run_id=run_id, now=now)
```

### The reserve-then-call lock to reuse (note: module-private today)
```python
# Source: app/pipeline/rank.py:361-379
async def _reserve(day_total, run_total, *, cap_day, cap_run) -> bool: ...
async def _release() -> None: ...
```

## Runtime State Inventory

**Not applicable.** Phase 6 is not a rename/refactor/migration phase — no stored string,
collection name, OS registration, secret key or build artifact is renamed. The one
schema-adjacent question (blocked rows needing a migration) is answered in Design Q10:
**no migration is required**, because `tex_path`/`pdf_path` are already nullable.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | everything | ✓ (assumed — repo runs) | 3.13 target | — |
| `pytest` + `pytest-asyncio` | test lanes | ✓ (dev deps) | 9.1.1 / 1.4.0 | — |
| `rapidfuzz` | check 6 banding | ✓ (pinned) | 3.14.6 | stdlib `difflib` (not recommended) |
| `pypdf` | Layer 2 extraction | ✓ (pinned) | 6.19.0 | — |
| Tectonic | the compile step (integration only) | ✗ on a dry host by design | — | the `latex` lane is skipped by default (D-69); verifier fixtures need no engine |
| opencode server | the generate step (integration only) | ✗ in the default lane | — | `OfflineLLMBackend` + a test stub |

**Missing dependencies with no fallback:** none. The default test lane deliberately needs
neither an engine nor a server.

**Missing dependencies with fallback:**
- Tectonic / opencode are absent from the hermetic lane; the compile/LLM integration tests
  are marked `latex`/overridden respectively and must not gate the default suite.

## Validation Architecture

Phase 6 has `nyquist_validation` enabled (absent in `.planning/config.json` ⇒ enabled).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` 9.1.1 + `pytest-asyncio` 1.4.0 (`asyncio_mode = "auto"`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/verify tests/domain tests/api -q` |
| Full suite command | `pytest` (default lane; `addopts = "-m 'not live and not latex'"` [VERIFIED: pyproject.toml:61]) |
| Engine lane | `pytest -m latex` (container only, D-69) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TAIL-01 | generate returns a patch from one LLM call | integration (stub) | `pytest tests/api/test_tailoring_generate.py -x` | ❌ Wave 0 |
| TAIL-02 | typed patch; no free-text on the PDF path | unit | `pytest tests/domain/test_patch_ops.py -x` | ❌ Wave 0 |
| TAIL-03 | bullet text immutable; canary never reaches `.tex` | unit | `pytest tests/verify/test_no_free_text_path.py -x` | ❌ Wave 0 |
| TAIL-04 | the 10 checks, both layers | unit (fixtures) | `pytest tests/verify/ -x` | ❌ Wave 0 |
| TAIL-05 | blocked artifact not downloadable | unit + route | `pytest tests/api/test_cv_artifact_blocked.py -x` | ❌ Wave 0 |
| TAIL-06 | no repair path; fail ⇒ blocked | unit | `pytest tests/verify/test_block_no_repair.py -x` | ❌ Wave 0 |
| TAIL-07 | review page shows preview + change log before compile | route | `pytest tests/api/test_tailoring_review.py -x` | ❌ Wave 0 |
| TAIL-08 | drops listed with a reason | unit | `pytest tests/domain/test_patch_ops.py::test_drop_reason -x` | ❌ Wave 0 |
| UI-05 | PDF preview inline + download | route | `pytest tests/api/test_cv_pdf_route.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/verify tests/domain -q` (fast, no engine/server).
- **Per wave merge:** `pytest` (full hermetic suite).
- **Phase gate:** full suite green before `/gsd-verify-work`; `pytest -m latex` run
  explicitly in the container for the compile integration.

### Wave 0 Gaps
- [ ] `tests/verify/fixtures.py` — the `(facts, plan, patch, text, expected)` builder (P13).
- [ ] `tests/fixtures/verify/*.txt` — committed extracted-text samples (pass + one per fail).
- [ ] `tests/verify/test_plan_checks.py` / `test_text_checks.py` / `test_numbers.py` /
      `test_grounding.py`.
- [ ] `tests/domain/test_patch_ops.py` — the real `apply_patch` semantics (replacing
      `tests/domain/test_cv_ids.py:185-225`).
- [ ] `tests/api/test_cv_artifact_blocked.py` — the P14 blocked-artifact negative test.
- [ ] `tests/api/test_cv_pdf_route.py` — inline vs `?download=1`, 404 on blocked.
- [ ] `tests/api/test_tailoring_generate.py` / `test_tailoring_review.py` — with a stub LLM.
- [ ] `tests/verify/test_no_free_text_path.py` — the canary test (TAIL-02/03).
- [ ] No framework install needed — pytest + pytest-asyncio are present.

## Security Domain

`security_enforcement` is enabled (no explicit `false` in config).

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (v1) | The `Depends(current_user)` seam is present on every new route (PLAT-03); auth is deferred. |
| V3 Session Management | no (v1) | — |
| V4 Access Control | partial | Single local user; the route seam is the only control now; the `ok`-only repository selection is the artefact-access control. |
| V5 Input Validation | yes | Pydantic v2 on `TailoringPatch` (re-parsed from the hidden field), the route's `int` path param, and the guard fields. |
| V6 Cryptography | no | No crypto introduced; `hashlib.sha256` is used for a content hash, not for secrecy. |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via listing text | Tampering | Listing text travels only in `parts`; `system` is a frozen constant; the model returns ids only (`app/llm/base.py:124-137`). |
| Forged/edited hidden `patch_json` | Tampering | Re-parse with Pydantic + re-ground every id at compile; no text field exists, so forgery cannot fabricate. |
| LaTeX injection via CV content | Tampering | The Jinja `finalize` choke point escapes every interpolated string exactly once (`app/latex/env.py:56-74`); no `-Z shell-escape` (Tectonic `--untrusted`). |
| Path traversal via artifact path | Tampering | The path is built from `Settings.artifacts_dir` + the `int` listing/artifact ids; never from request text. |
| Stale-patch / TOCTOU on the fact store | Tampering | The `facts_hash` + `base_cv_version_id` guard refuses a compile on drift (D-109). |
| Unbounded LLM spend | Denial of service | The reserve-then-call cap before the request (D-92); see O1 for the purpose-scoping fix. |
| Downloading a blocked (unverified) artifact | Information disclosure / integrity | Repository-level `ok`-only selection + route refusal (D-118). |
| PII in logs / persisted JSON | Information disclosure | `verification_json` carries ids/reasons/counts only; never the PDF text or the listing description. |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Free-text CV rewriting by an LLM | Typed ID patch over an enumerated fact store | this project's design | Fabrication is structurally unrepresentable (P6: 96.7% baseline unsupported-claim rate). |
| Verify-then-repair loops | Block, don't repair | this project's design | "Repair pressure is fabrication pressure" (§10.4). |
| Byte-hash provenance | Semantic content hash | this research | A comment/whitespace edit no longer invalidates a patch. |

**Deprecated/outdated:**
- `UnsupportedPatchOp`: a Phase 4/5 placeholder; removed in Phase 6.
- §7.3's `app/domain/schemas/patch.py` path and `suggestions: list[dict]`: superseded
  (co-locate in `cv.py`; use the typed `Suggestion`).
- §10.3 check 2's "capitalised proper-noun sequence" wording: superseded by D-112's
  structured-field-only narrowing.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Grounding thresholds 80/55 are reasonable | Q4 | A wrong band mislabels confidence (advisory only — no block impact). Needs calibration. |
| A2 | Digit-core tokenisation is the right metric normalisation | Q2 | A missed edge case either false-fails or under-detects a metric. The fixture matrix is the mitigation. |
| A3 | Page-number exclusion by lone-integer-line ≤ `page_count` | Q2/Pitfall 3 | A legitimate bare number on its own line could be excluded; low risk on a CV. |
| A4 | `extra="forbid"` on the patch schema | Q6 | A model returning an extra key fails the call (bounded retry). Judgement call vs `ranking.py`'s `ignore`. |
| A5 | Cross-entry `move_bullet` should be rejected | Q7 | A model that emits a cross-entry move gets a refusal instead of a silent wrong order. |
| A6 | Tailoring reuses the 24h ranking ceiling; per-run does not apply | Q8/O1 | If the user wants a separate tailoring budget, the defaults may be too tight or too loose. |
| A7 | `app/verify` should join `SCANNED_DIRS` | Q11 | A hard-coded threshold in the verifier escapes the absence scan. |

**If this table is non-empty, the planner should confirm A1/A4/A6 with the user or pin
them explicitly in the plan.** A2/A3/A5/A7 are implementation decisions the planner can
lock.

## Open Questions

1. **O1 — Does the tailoring call share the ranking spend ceilings?** D-119 says "the same
   per-run / rolling-24h ceilings … no new counters — plus one new `tailoring_enabled`
   boolean". But (a) `rank_calls_since` filters `purpose == "rank"`, so reuse is a bug, and
   (b) an interactive tailor call has **no `run_id`**, so the per-run ceiling cannot apply.
   - What we know: the ledger and `PURPOSES` already include `"tailor"`; the reserve-then-call
     lock is reusable.
   - What's unclear: whether the 24h ceiling is the shared `ranking_max_calls_per_day` value
     or a new `tailoring_max_calls_per_day`.
   - **Recommendation:** reuse the 24h value via a purpose-aware read
     (`calls_since(session, *, purpose, now)`), record `run_id=None`, and drop the per-run
     ceiling for tailoring. Pin this in the plan; if the user wants an independent budget,
     add `tailoring_max_calls_per_day` and its `test_config.py` surface.
2. **O2 — Where does the `facts_hash` persist?** Recommendation: `verification_json` (no
   migration). Alternative: a new `cv_artifacts.base_fact_store_hash` column (migration
   0005 + head-pin updates in `tests/db/test_migration_contract.py:295` and
   `tests/db/test_skeleton_boot.py:76`). Recommend the no-migration option.
3. **O3 — A separate `tailoring_model`?** ARCHITECTURE §6.4 says the two pipelines *should*
   be able to use different models. Recommendation: reuse `settings.opencode_model` for v1
   (record `result.model` on the artifact), defer the knob.
4. **O4 — Does the template need `\pagestyle{empty}`?** Check 4's page-number heuristic
   handles it without a template change; adding it changes the golden bytes. Recommend the
   heuristic, defer the template change.

## Sources

### Primary (HIGH confidence — read from this repo this session)
- `app/domain/cv.py` — `Bullet`/`Entry`/`Section`/`CvFacts`, `iter_fact_ids`,
  `ChangeRecord`/`RenderPlan`/`_identity_plan`, the existing `BulletWeight`/`DropBullet`/
  `Suggestion`, the `apply_patch` stub, `SECTION_TITLES`.
- `app/domain/tex.py` — `escape_tex`, `normalise_for_compare`, `squash`,
  `facts_present_in`, `facts_compared`, `sanitise_preamble`.
- `app/domain/sanitize.py` — `INJECTION_PATTERNS` (L83, exported L244).
- `app/latex/` — `base.py`, `compile.py` (`extract_pdf_text` L66, `_count_pages`),
  `render.py`, `env.py`, `templates/cv.tex.jinja`.
- `app/cv/factstore.py` — `CvFactStoreError`, `load_facts`, `fact_store_report`.
- `app/db/models.py` (L399-431 `CvArtifact`, L351-384 `Score`) and
  `alembic/versions/0001_initial_schema.py` (L239-265) — nullability + CHECK.
- `app/db/repositories/cv_repo.py`, `score_repo.py`, `llm_call_repo.py`.
- `app/pipeline/rank.py`, `run.py`; `app/llm/base.py`, `builders.py`;
  `app/domain/schemas/ranking.py`; `app/api/listings.py`, `events.py`, `deps.py`;
  `app/config.py`; `tests/test_config.py`; `tests/conftest.py`; `pyproject.toml`;
  `cv/cv.yaml`; `tests/golden/base.rendered.tex`.
- `ARCHITECTURE.md` §4.2, §7.1–7.5, §9.1, §10; `PITFALLS.md` P6, P13, P14.

### Secondary (MEDIUM confidence)
- The 10-check design, the metric tokeniser, the region segmentation and the grounding
  banding — designed in this research against §10 and the code, not sourced.

### Tertiary (LOW confidence)
- The grounding threshold values (A1) and the metric edge-case coverage (A2) — uncalibrated.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every version read from `pyproject.toml`; no new dependency.
- Architecture: HIGH — the integration points, signatures, nullable columns and CHECK
  constraints were read from the tree this session.
- Verification design (the 10 checks / tokeniser / banding): MEDIUM — designed here per the
  roadmap's explicit instruction; the fixtures are what validate it.
- Pitfalls: HIGH for the code-grounded ones (stub tests, `facts_present_in`, purpose-scoped
  cap, nullable columns); MEDIUM for the page-number and false-positive rates.

**Research date:** 2026-09-24
**Valid until:** ~2026-10-24 for the stack (stable); re-check the design thresholds once a
real CV/listing corpus exists (STATE.md blocking unknown #1 remains open).



