# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — MVP

**Shipped:** 2026-10-15
**Phases:** 9 (8 + inserted 07.1) | **Plans:** 82 | **Tasks:** 203
**Sessions:** not instrumented (see Cost Observations)

### What Was Built

- The whole spine: pluggable JobSpy/Adzuna ingest → exact + fuzzy dedup (reversible)
  → deterministic hard-rule filtering → FTS5-searchable, paginated queue with
  save/hide — the first three phases of the pipeline.
- Ranking, the Core Value: a pure six-factor rubric scored against the CV fact store
  with grounded evidence IDs, a detail page with per-factor sub-scores and named
  gaps, a read-time total, a weights editor that re-derives order with zero LLM
  calls, and reserve-then-call spend ceilings.
- CV-as-data: a validated `cv.yaml` with stable enumerated IDs, a byte-deterministic
  Jinja renderer behind one escape choke point, pinned Tectonic behind an engine
  port, and a golden baseline.
- Tailoring that cannot fabricate: a typed ID-based patch plus an 11-check two-layer
  verifier (region-anchored, fail-closed, region-local metric containment) that
  blocks rather than repairs.
- Assisted apply + tracker: an `ok`-artefact-gated package, screening-answer drafting
  under a deterministic grounding check, and an append-only tracker with stage
  filter/search/pager/needs-action.
- Operations + polish: the opencode V2 HTTP migration with dual-support detection, a
  daily APScheduler run with overlap-skip, a `/status` self-report, and a
  phone-breakpoint reflow with vendored assets.

### What Worked

- **The structural anti-fabrication design.** Modelling the CV as enumerated IDs and
  making the tailoring patch a typed operation over those IDs meant the highest-risk
  guarantee ("never invent") was enforced by the schema, not by prompt discipline.
- **Pin-then-guard on every external contract.** Pinning the opencode wire shape
  (later migrated wholesale to V2) and the Tectonic binary by version + SHA256 turned
  "an upgrade silently corrupts output" into "the build fails loudly".
- **Gap-closure rounds with a named verifier version.** The Phase 6 verifier went
  through five anchored revisions (`VERIFIER_VERSION` 1.0.0 → 1.0.5), each with a
  literal reproduction pinned as a test and an independent review owning the "closed"
  verdict — the failure class, not the instance, was the target.
- **Cost controls placed before the spend.** Hard-rule filtering and the
  reserve-then-call caps live on the path to the LLM, not after it.

### What Was Inefficient

- **Phase 6 took five gap-closure rounds.** The region-anchoring in the metric
  containment check was repeatedly tightened against newly-found false-fails and
  false-negatives. A single upfront adversarial fixture sweep (bullets embedding a
  *later* entry's org/title/dates) would likely have collapsed rounds 3–5.
- **A mid-milestone contract death (opencode 2.0.26).** The V1 HTTP API was retired
  upstream mid-build, requiring the inserted Phase 07.1 (V2 migration) and a
  correction back to "auth required in practice" after an earlier narrowing.
- **`input.css` / `app.css` drift.** Phase 07-11 hand-appended CSS because the
  Tailwind source had silently drifted from the built artefact since Phase 5;
  07-13 then had to backfill and regenerate. The build guard that now prevents it
  should have existed from the first hand-append.
- **Verification fingerprints go `stale` at the boundary.** Broad `covered_files`
  lists mean later phases' legitimate edits invalidate earlier phases' digests,
  forcing an override at close. Narrower coverage (or an explicit shared-file
  exclusion) would keep the signal meaningful.

### Patterns Established

- **Anchor structurally, never lexically** — region/section/entity boundaries come
  from a discriminator free text cannot accidentally satisfy (now CONVENTIONS rule 1).
- **Fail closed, visibly** — a check that cannot locate what it needs emits a visible
  `warn`; it never degrades to a silent skip.
- **The fix author does not certify closure** — a reviewer/verifier owns the "closed"
  verdict, with a scoped review after each gap-closure fix.
- **No false guarantees in prose** — docstrings claiming a guarantee the code does
  not deliver are removed; trade-offs become runtime-visible warnings.
- **Test the failure class** — parametrized mutation tests that embed other entities'
  identifiers, not just the literal instance.

### Key Lessons

1. The most dangerous failure mode for a "never invent" claim is a *silent* false
   negative in the detector — budget verification effort asymmetrically toward "does
   it accept valid input?", not only "does it catch the bad thing?".
2. Pin and test every external contract (LLM wire shape, LaTeX engine, built CSS)
   such that drift fails the build; the cost of a guard is trivial next to a
   mid-milestone upstream break.
3. Bring the real primary artefact (the real `.tex`) into the repo *before* the phase
   that depends on it — leaving it out turned a "measurement" into an open, carried
   blocking unknown.

### Cost Observations

- Model mix: **not instrumented** — session/model spend was not captured per phase,
  so this is recorded as a gap rather than estimated.
- Sessions: not instrumented.
- Notable: the dominant variable cost is LLM calls; the design deliberately caps them
  (hard-rule filtering + reserve-then-call ceilings), so cost control is a shipped
  feature, not an afterthought.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | not instrumented | 9 | First milestone — established the GSD phase/gap-closure/verifier-version workflow |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | ~48k lines of test code (`tests/`) | not instrumented | n/a (first milestone) |

### Top Lessons (Verified Across Milestones)

1. Structural enforcement beats discipline for safety guarantees (verified in v1.0
   across the CV-as-data, tailoring-patch, and artefact-gating designs).
2. Pin external contracts and let drift fail the build (verified in v1.0 across the
   opencode wire contract and the Tectonic binary).
