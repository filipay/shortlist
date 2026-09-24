# Phase 6: Tailoring + Verification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-24
**Phase:** 6-Tailoring + Verification
**Areas discussed:** Patch op semantics, Tailor→review→compile flow, Verification gate mechanics, Artifact lifecycle & preview UI

---

## Patch op semantics

### `reweight_bullet` concrete effect

| Option | Description | Selected |
|--------|-------------|----------|
| Order within the entry | Weight sorts bullets within their entry; number never printed | ✓ |
| Metadata only | Weight stored but never affects layout | |
| Order + visual emphasis | Weight also changes visual prominence | |

**User's choice:** Order within the entry
**Notes:** `move_bullet` (`before_id`) remains the explicit positional override.

### `demote_bullet` concrete effect

| Option | Description | Selected |
|--------|-------------|----------|
| To end of its entry | Lowest prominence within its own entry; text unchanged | ✓ |
| To a trailing section | Moved to a separate demoted section | |
| Weight floor (0.0) | Expressed purely as a weight | |

**User's choice:** To end of its entry
**Notes:** Reason required; distinct from drop (removed entirely) and move (explicit position).

### `suggestion` / `gap_finding` surface

| Option | Description | Selected |
|--------|-------------|----------|
| Advisory only, never rendered | Persisted + shown in change log/coverage panel; never reach renderer | ✓ |
| Gap findings render a coverage block | Gaps appear in the PDF | |
| Not persisted | Transient | |

**User's choice:** Advisory only, never rendered
**Notes:** `gap_finding` additionally feeds verification check 6.

### Invalid patch handling

| Option | Description | Selected |
|--------|-------------|----------|
| All-or-nothing rejection | Whole patch aborts, no artifact written | ✓ |
| Best-effort partial apply | Valid ops applied, invalid dropped | |
| Auto-repair | Tool silently fixes the patch | |

**User's choice:** All-or-nothing rejection

---

## Tailor→review→compile flow

### End-to-end flow shape

| Option | Description | Selected |
|--------|-------------|----------|
| Two-step: generate → review → compile | LLM call, then explicit user-approved compile | ✓ |
| One-shot detached task | Generate+compile in background | |
| One-shot synchronous | Generate+compile in the request | |

**User's choice:** Two-step: generate → review → compile

### Pre-compile review content

| Option | Description | Selected |
|--------|-------------|----------|
| HTML preview of the tailored CV + change log | Final order, drops annotated, per-item reasons | ✓ |
| Change log only | No visual preview | |
| Draft PDF | Compile before approval | |

**User's choice:** HTML preview of the tailored CV + change log

### Patch lifetime between generate and compile

| Option | Description | Selected |
|--------|-------------|----------|
| Stateless round-trip + version guard | Patch in hidden form field + captured version/hash; refuse if fact store changed | ✓ |
| Persisted draft artifact row | Draft row in DB | |
| Session state | Stored server-side in session | |

**User's choice:** Stateless round-trip + version guard
**Notes:** This is the `_verify_original_matches`-style optimistic concurrency guard.

### Listing with no score yet

| Option | Description | Selected |
|--------|-------------|----------|
| Require an existing score | Affordance only offered when requirements are stored; unscored show "rank first" | ✓ |
| Tailor call reuses or re-extracts requirements | Tailoring does its own requirement extraction | |

**User's choice:** Require an existing score

---

## Verification gate mechanics

### Gate layers

| Option | Description | Selected |
|--------|-------------|----------|
| Both: plan pre-check + PDF post-check | Layer 1 short-circuits before compile; Layer 2 after | ✓ |
| Post-compile PDF text only | Single layer after compile | |
| RenderPlan only | Single layer before compile | |

**User's choice:** Both: plan pre-check + PDF post-check

### Check 2 — no new named entity

| Option | Description | Selected |
|--------|-------------|----------|
| Structured-field containment only | Org/title/section strings vs CvFacts; bullet text trusted | ✓ |
| Structured fields + PDF proper-noun scan | Also scan extracted text for proper nouns | |
| Both, PDF scan as warn | Structured fail, PDF scan warn | |

**User's choice:** Structured-field containment only
**Notes:** `bullet.text` is human-authored and immutable, so it is not scanned.

### Check 4 — metric containment

| Option | Description | Selected |
|--------|-------------|----------|
| Region-scoped, date+layout excluded | Per-region numeric tokens minus date-like/layout numbers; unmatched ⇒ fail | ✓ |
| Global containment | Any number anywhere in facts | |
| Declared-metrics allow-list | Only numbers in `metrics` fields | |

**User's choice:** Region-scoped, date+layout excluded
**Notes:** The `_novel_numbers`-equivalent with date-like-number exclusion.

### Verification failure persistence

| Option | Description | Selected |
|--------|-------------|----------|
| Blocked artifact either way | Plan-fail stores JSON only; PDF-fail retains PDF; neither downloadable | ✓ |
| No row on plan-fail | Layer 1 failure writes nothing | |
| Never persist failures | Failures not stored | |

**User's choice:** Blocked artifact either way
**Notes:** No auto-repair (TAIL-06).

---

## Artifact lifecycle & preview UI

### Tailoring UI location + PDF route

| Option | Description | Selected |
|--------|-------------|----------|
| Inline on listing detail + nested artifact route | Everything on the detail page | |
| Separate tailoring page | Dedicated `/listings/{id}/cv` page owns the flow; detail page links to it | ✓ |
| Detail page + flat artifact route | UI on detail, flat artifact URL | |

**User's choice:** Separate tailoring page

### Artifact row creation across repeated tailoring

| Option | Description | Selected |
|--------|-------------|----------|
| New row per compile, latest shown | History retained; page shows most recent | ✓ |
| Upsert one row per listing | Single mutable row | |
| New row only on content change | Dedupe identical compiles | |

**User's choice:** New row per compile, latest shown
**Notes:** Retention bound deferred to Phase 8.

### Blocked-artifact enforcement + recovery

| Option | Description | Selected |
|--------|-------------|----------|
| Repo-enforced; recovery = re-tailor | Only `ok` artifacts returned by download/link queries; fresh tailor to recover | ✓ |
| Repo-enforced + explicit drop-and-re-render | Adds §10.4's one-click affordance | |

**User's choice:** Repo-enforced; recovery = re-tailor
**Notes:** §10.4 drop-and-re-render affordance deferred.

### Cost guard for the tailor call

| Option | Description | Selected |
|--------|-------------|----------|
| Share ledger + caps; add a toggle | Same `llm_calls` ledger and per-run/24h ceilings + `tailoring_enabled` | ✓ |
| Dedicated tailoring ceilings | Separate counters | |
| No guard | Ungated | |

**User's choice:** Share ledger + caps; add a toggle

---

## the agent's Discretion

No area was delegated "you decide". Implementation details left open to the planner/implementer: metric-token normalisation and the date-like-number detector; entity-check stop-list (if any); the fact-store version/hash mechanism carried by the review page; the PDF route path/filename scheme; the HTML preview markup; the `app/verify/` module layout and `verifier_version`; verifier Settings key names; the tailoring system-prompt wording; `TailoringPatch` field ordering.

## Deferred Ideas

- §10.4's one-click "drop this bullet and re-render" affordance.
- Artifact retention/pruning / cap on historical `cv_artifacts` rows — Phase 8.
- `_GROUNDING_REVIEW_THRESHOLD`-style similarity banding for confidence tiers — planner to design.
- Cover letter (v2 TAIL-09) and ATS parse check (v2 TAIL-10).
