---
id: SEED-002
status: dormant
planted: 2026-10-01
planted_during: Phase 7 — Assisted Apply + Tracker
trigger_when: when planning CV intake or fact-store expansion, or any phase about onboarding or multi-source authoring
scope: medium-large
audit_acknowledged:
  milestone: v1.0
  at: 2026-10-15
  status: dormant
---

# SEED-002: Fill the fact store from more than one source (personal site, LinkedIn, …)

## Why This Matters

Recorded verbatim during the Phase 7 code-review cycle: *"user could potentially provide
multiple sources to fill the fact store, like their website or linkedin"*.

Today the fact store has exactly one intake path: the operator supplies a CV document through
`POST /settings/cv`, and facts are read from a single configured location by
`app/cv/factstore.py:load_facts`. Everything downstream — ranking context, tailoring, and now
grounded screening drafts — reads that one store.

The appeal is obvious: a CV is a lossy, years-stale summary. A personal site and a LinkedIn
profile carry the same facts in more detail, plus projects and history the CV omits. Pulling
them in makes the "one ranked, explained, apply-ready queue" better at its job, because the
grounding set the LLM may draw on gets richer.

## When to Surface

**Trigger:** when planning CV intake / fact-store expansion, or any phase about onboarding or
multi-source authoring. It is an intake-layer feature: no ingest, filtering, or ranking change
is required.

## Scope Estimate

**Medium-large** — and almost none of the cost is in fetching the remote source. The crux is
**fact-id stability**.

## Design tensions to resolve when this is planned

1. **Fact-id stability is load-bearing.** Evidence ids are intersected byte-exact against
   `iter_fact_ids` by the screening grounding check (`app/verify/screening.py`), and stored
   `screening_drafts` plus `cv_artifacts.structured_diff` reference those ids. A second source
   must normalise INTO the same id scheme with deterministic, stable ids. If ids shift when a
   source is re-imported or reordered, every stored draft and artifact silently orphans — which
   is exactly the failure class Phase 7's WR-04 finding was about.
2. **Import must stay extractive, never generative.** "Never fabricate" still holds. The user
   authored their own site/profile, so importing is legitimate — but an importer that *infers*
   facts (a skill implied by a job title, a date the page implies but never states) breaks the
   hard line. Extraction should be user-confirmed, like the existing CV intake.
3. **Provenance is wanted; third-party PII is not.** It is genuinely useful to record which
   source a fact came from, so the user can audit what the tool believes about them. That is
   distinct from persisting recruiter or colleague names/emails scraped off a page — the
   existing no-PII columns guard must keep holding.
4. **Remote content is still untrusted input.** A user's own website is user-controlled but
   third-party-hosted: it is an injection surface. The project's existing rule — listing-driven
   content never reaches a system prompt and sessions are tool-restricted — should extend to any
   imported page. No LLM call may treat page content as instructions; see ARCHITECTURE/STACK
   prompt-injection guidance.
5. **Cross-source dedup.** The same role/skill will appear in the CV and on the site. The
   existing tier-2 fuzzy dedup (`rapidfuzz`) is listing-shaped, not fact-shaped; a fact-level
   merge needs its own answer, and a false merge is worse than a duplicate.
6. **LinkedIn specifically is scraping.** LinkedIn's terms prohibit automated collection and the
   project already rejected unattended automation for exactly this reason. The low-risk path is
   user-exported data (LinkedIn's own "Save to PDF"/data export) re-imported locally, not a
   scraper. Decide this explicitly rather than defaulting to a fetch.

## Breadcrumbs

- `app/cv/factstore.py` — `load_facts`, `_assert_ids_unique`, `fact_store_report`: the single
  source load path, and where a second source would have to converge.
- `app/domain/cv.py` — the `CvFacts` model: the normalised shape any new source must produce.
- `app/api/settings.py` — `CV_UPLOAD_PATH = "/settings/cv"` (~line 79) and its handler
  (~line 393; note `cv_tex`, not a multipart upload): the existing intake UI/precedent, and the
  natural home for a "Add a source" control.
- `app/verify/screening.py` — `iter_fact_ids` and the byte-exact evidence-id grounding: the
  constraint that makes id stability non-negotiable.
- `app/api/apply.py`, `app/api/tailoring.py` — the `load_facts` consumers; any change to id
  assignment ripples into stored drafts and artifacts.
- `.planning/phases/07-assisted-apply-tracker/07-03-SUMMARY.md` — the grounded drafting contract
  that consumes fact ids.
- `.planning/phases/07-assisted-apply-tracker/07-REVIEW.md` (WR-04) — the closest prior instance
  of "identity must be structural, not lexical".
