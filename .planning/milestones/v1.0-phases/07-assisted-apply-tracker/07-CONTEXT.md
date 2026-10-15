# Phase 7: Assisted Apply + Tracker - Context

**Gathered:** 2026-09-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver the apply half of the core loop: an **apply package** per listing — the verified PDF, the outbound apply link, drafted screening answers, and a read-only gap checklist — plus an **application tracker** where the user records applications, moves them through stages, keeps notes and a next-action date, and sees each status change as append-only history, every application pointing at the exact verified CV artefact that was sent.

In scope: the `/listings/{id}/apply` package page and its route, the `/applications` tracker (list, filters, needs-action view, inline history), an `app/db/repositories` layer over the already-existing `applications` / `application_events` tables, the persisted screening-draft store (+ migration from head `0005`), the screening-drafting LLM call, the Settings keys it needs, and the status-transition endpoint.

**Not this phase:** the tool submitting anything (APPLY-02 — no submit route exists, ever); bulk apply-to-all (AF-14); browser-extension autofill (AF-9, later milestone); export (v2 APPLY-07); batched notifications (v2 APPLY-08); application retention/pruning and scheduling (Phase 8); cover letters (v2 TAIL-09); ghost-job/listing-quality scoring (v2 RANK-10).

**Schema note:** `applications` and `application_events` already exist in `app/db/models.py` and migration `0001_initial_schema.py` (the status vocabulary is frozen by `ck_applications_status`). Nothing references them yet — no repository, route, or template. Phase 7 builds the code layer over this fixed schema; renaming or adding a stage is a migration, not an edit.

</domain>

<decisions>
## Implementation Decisions

### Apply package surface & content
- **D-120:** The apply package is a **dedicated page** at `/listings/{id}/apply`, mirroring Phase 6's `/listings/{id}/cv` page; the listing detail page links to it. Every route declares the `user: User = Depends(current_user)` auth seam (PLAT-03).
- **D-121:** A package is available **only when an `ok` `cv_artifact` exists** for the listing. Otherwise the page shows a "tailor and verify first" state linking to the tailoring page. APPLY-01 names the verified PDF as package content, and D-118 exposes only `ok` artefacts to download/link.
- **D-122:** The package is **assembled on open from stored data** (ok artefact, `listing.apply_url`, stored ranking gaps, stored drafts). Opening the page makes no LLM call; drafting is an explicit user action.
- **D-123:** The gap checklist is **read-only**, rendered from the requirement gaps the ranking call already stores (D-81). Nothing new is persisted and no tick state exists.

### Screening-answer drafting & honesty
- **D-124:** Questions come from a **user-defined list in Settings** plus an ad-hoc "add a question" box on the package page. The tool does **not** infer questions from the listing text — application-form questions are not reliably in a job description, and inferring them invents questions the real form may never ask.
- **D-125:** Drafted answers are **grounded in stored `CvFacts` + the listing text only**, and each answer carries the evidence it used. An answer containing an unsupported claim surfaces a **warning** rather than shipping silently. — **Reversibility:** costly — the drafted-answer record (answer + evidence) is a stored shape consumed by the package UI and any future export (v2 APPLY-07); loosening the contract invalidates stored drafts and erodes the phase's honesty guarantee.
- **D-126:** Drafts **persist per listing** in a new table (migration from head `0005_cv_drafts`), one row per question, so they survive reload and are visible in the package. — **Reversibility:** one-way — undo requires a migration and would drop stored drafts.
- **D-127:** Consumption is **copy-to-clipboard per answer**. Nothing is auto-inserted into a portal and **no submit path exists anywhere** (APPLY-02, PROJECT.md hard line).

### Status transitions & the applied gate
- **D-128:** Transitions are **guided**: `discovered` / `queued` are tool-set; the user drives `shortlisted → applied → interviewing → offer` / `rejected` / `withdrawn`. The eight-value vocabulary is already frozen by `ck_applications_status` in migration `0001`. — **Reversibility:** costly — changing or adding a stage means a migration against a CHECK constraint, and the recorded history uses the old names.
- **D-129:** Moving to `applied` **requires selecting an `ok` artefact** from an ok-only picker (defaulting to the latest), satisfying APPLY-04 and D-118. — **Reversibility:** costly — the application→artefact link is the phase's core integrity contract; relaxing it strands rows with no link and breaks the "exact CV sent" guarantee.
- **D-130:** `applied_at` is **stamped by the transition**, never typed — mirroring `event_repo`'s rule that append helpers never forge a time.
- **D-131:** `applications.status` holds the **current value on the row**, and exactly one `application_events` row (`from_status`, `to_status`, `occurred_at`, `note`) is appended **in the same transaction**. The event table is insert-only, trigger-enforced, mirroring `listing_events` (ARCHITECTURE L1160; PITFALLS L247/L255 name the "status column with no history" anti-pattern this avoids). — **Reversibility:** costly — switching to a status derived purely from the log later would need the NOT NULL CHECK column relaxed and every read rewritten.

### Tracker view & history management
- **D-132:** The tracker is a **table view at `/applications`**: listing/company, current stage, applied date, next action, latest note. It reuses the existing queue table markup and HTMX partial-swap pattern.
- **D-133:** The user can slice it by **stage filter**, a **needs-action view** (overdue first, then upcoming `next_action_at`), and **free-text search** over company/title/notes (UI-04 "view and manage").
- **D-134:** The append-only history renders as an **expandable inline timeline per row** (HTMX partial): `from → to`, timestamp, note. No separate `/applications/{id}` detail page in v1.
- **D-135:** **Notes and `next_action_at` are ordinary mutable columns**; only status changes are append-only events.

### the agent's Discretion
Left to the planner/implementer (not re-asked): the new draft table's name and columns; the exact Settings key names for the screening question list; the drafting prompt wording and how evidence is attached per answer; the template file names and the exact apply-page URL/path naming; which HTMX partials are factored out; the repository module name and layout (`app/db/repositories/`); tracker pagination (follow the queue's existing approach); the model used for the drafting call. No area was delegated "you decide" on a product question.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase definition
- `.planning/ROADMAP.md` §Phase 7 (L314–329) — goal, success criteria 1–4, requirements APPLY-01..06 + UI-04, UI hint.
- `.planning/REQUIREMENTS.md` — APPLY-01..APPLY-06 (L81–86), UI-04 (L103); out-of-scope rows (unattended auto-apply, bulk apply-to-all, CAPTCHA/credentialed scraping, browser extension driving portals); v2 APPLY-07 export, APPLY-08 batched digest.
- `.planning/PROJECT.md` — the ethical hard line and the assisted-only posture ("the human presses submit").

### Architecture & research
- `.planning/research/ARCHITECTURE.md` §C14 (L108) — the Application/assist component and its boundary ("Submitting anything" is explicitly out).
- `.planning/research/ARCHITECTURE.md` L320–330 — the application-package flow and the `applications(...)` write.
- `.planning/research/ARCHITECTURE.md` L943–989 — the `applications` sketch, the not-linkable blocked-artefact rule, and `applications.cv_artifact_id` existence.
- `.planning/research/ARCHITECTURE.md` L1068 (block-don't-repair, blocked artefacts never linkable) and **L1160** (the insert-only `listing_events` / `application_events` rule: current state on the row, history in the event table).
- `.planning/research/PITFALLS.md` L247 (anti-pattern: a status column with no event history), L255 ("never overwrite state that has analytic value"), L286 (the `next_action_at` follow-up nudge makes the tracker a reason to return), **L776 (P8 verification checklist: `cv_artifact_id` set, `application_events` append-only, `next_action_at` computed)**.
- `.planning/research/FEATURES.md` **DF-12** (L73, the assisted-apply package) and L245/L255 (the draft-only posture — "never sends anything, the final click is always yours" — is the mainstream safe design, not a compromise); AF-1 (no unattended submit) and AF-14 (no bulk apply).

### Prior phase context (binding decisions)
- `.planning/phases/06-tailoring-verification/06-CONTEXT.md` — **D-115** (the blocked-artefact contract is consumed by Phase 7's attach path), **D-118** (only `ok` artefacts are returned to download/link queries, enforced at the repository layer), **D-119** (the tailor LLM call draws from the same `llm_calls` ledger and reserve-then-call ceilings — reuse for the drafting call).
- `.planning/phases/05-ranking-core-value/05-CONTEXT.md` — **D-81** (requirement gaps + evidence ids are stored by the ranking call — the gap-checklist source), D-91/92/93 (spend caps, reserve-then-call lock), D-96 (`GET /listings/{id}` detail page).

### Code anchors
- `app/db/models.py` — `Application` (L462–483, incl. `ck_applications_status` and the nullable `cv_artifact_id`), `ApplicationEvent` (L486–494), `ListingEvent` (L254–272, the append-only precedent), `CvArtifact` (L399–431), `CvDraft` (L434–459, the new-table-over-new-column precedent).
- `app/db/repositories/event_repo.py` — the append-only repository contract to mirror: INSERT-only `append_event`, `EVENT_TYPES` validation, projection folding, and the rule that the helper never forges a time.
- `app/db/repositories/cv_artifact_repo.py` — `CvArtifactRecord` and the `ok`-only selection contract (D-118).
- `app/db/repositories/score_repo.py` — `read_score_for_listing` / `latest_for_listings` for the stored requirement gaps.
- `app/api/tailoring.py`, `app/api/listings.py` — route shape, auth-seam dependency, and the generate/compile action pattern to mirror.
- `app/web/templates/html/tailoring.html`, `_tailoring_review.html`, `listing_detail.html`, `queue.html`, `_listing_row.html` — page + HTMX partial patterns to reuse.
- `app/config.py` + `tests/test_config.py` — the one `Settings` surface, `REQUIRED_SETTINGS_FIELDS` / `LIMIT_FIELDS` / `SCANNED_DIRS` scans that any new key must join.
- `app/llm/base.py` (`complete_structured`, `parts` is the only untrusted channel), `app/llm/builders.py`; `tests/conftest.py` (`OfflineLLMBackend`).
- `alembic/versions/0005_cv_drafts.py` — the current migration head the new draft table must follow; `tests/db/test_migration_contract.py` pins the head.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Application` / `ApplicationEvent` models — already defined and migrated; Phase 7 needs repositories and routes, not schema design (beyond the new draft table).
- `event_repo` — the working append-only log + projection implementation, including the trigger-backed insert-only rule and `append_event`'s time handling. Copy the contract, not the table.
- `cv_artifact_repo` — supplies the `ok`-only artefact selection the package and the `applied` gate require.
- `score_repo.read_score_for_listing` — the stored requirement gaps backing the read-only checklist (D-123).
- `app/api/tailoring.py` + `tailoring.html` / `_tailoring_review.html` — the page + action + partial pattern to mirror for `/listings/{id}/apply`.
- `queue.html` / `_listing_row.html` — table markup and HTMX swap pattern for the tracker list and its inline history partial.
- The spend-cap machinery from the ranking/tailoring stages (`llm_calls` ledger, reserve-then-call) — reused for the drafting call (D-119).

### Established Patterns
- Repositories are the only place SQL lives, take an `AsyncSession`, and never commit — the caller owns the transaction.
- `app.domain.*` stays pure (no httpx/sqlalchemy/jobspy/jinja2/subprocess); contract types are `extra="forbid"`; failures are values at the port boundary.
- Append-only tables carry a CHECK on the event type and BEFORE UPDATE/DELETE triggers that `RAISE(ABORT)`; current state lives on the row, history in the event table.
- New persisted state arrives as a NEW table with a new Alembic migration (never a widened column with a CHECK, never `create_all`); `tests/db/test_migration_contract.py` pins the head.
- Every numeric ceiling and gate is a `Settings` field, with the `tests/test_config.py` surface + absence scans updated in the same change.
- Route-level auth seam on every route; tests use `app.dependency_overrides` for the port seams (`get_llm_backend`).

### Integration Points
- `app/main.py` — router registration for the new apply/tracker routes (alongside `tailoring_routes`).
- `app/api/` (new module) — the apply package page actions and the status-transition endpoint.
- `app/db/repositories/` (new module) — `applications` + `application_events` writes and reads, and the draft store.
- `app/pipeline/` (new or extended) — the screening-drafting call, if it is staged rather than route-immediate.
- `app/web/templates/html/` — apply page, tracker page, history partial.
- `app/config.py` + `tests/test_config.py` — the screening question list and any new ceiling.

</code_context>

<specifics>
## Specific Ideas

- **The tracker must be a reason to return, not just a record** (PITFALLS L286): `next_action_at` should drive an overdue-first emphasis in the needs-action view.
- The P8 verification checklist (PITFALLS L776) is the acceptance backbone: `applications.cv_artifact_id` is set, `application_events` is append-only, `next_action_at` is computed and surfaced.
- The draft-only interaction model is ResuMorph's "drafts an answer you can preview, then insert, copy, or cancel" (FEATURES DF-12) — copy-and-paste, never auto-fill.
- The drafting call must be testable without an LLM or network, following the PITFALLS P13 fixture style already used by `app/verify`.
- The blocked-artefact rule (D-115/D-118) has to hold on the *apply* path too: a blocked artefact must never be selectable as the thing that was sent.

</specifics>

<deferred>
## Deferred Ideas

- A separate `/applications/{id}` detail page — D-134 keeps the inline timeline in v1; revisit if the tracker grows.
- A tickable, persisted gap checklist — D-123 keeps it read-only; needs a new table and a decision about what a tick means.
- Export applications and queue data (v2 APPLY-07) and batched digest notifications (v2 APPLY-08).
- Browser-extension autofill (FEATURES AF-9) — the legitimate form of prefill, but a second runtime and not a v1 build.
- Application retention/pruning and scheduled runs — Phase 8 (Operations + Polish).
- Ghost-job / listing-quality score separate from candidate fit (v2 RANK-10, FEATURES DF-10).

</deferred>

---

*Phase: 7-Assisted Apply + Tracker*
*Context gathered: 2026-09-30*
