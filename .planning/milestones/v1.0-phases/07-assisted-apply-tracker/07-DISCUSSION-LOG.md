# Phase 7: Assisted Apply + Tracker - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-30
**Phase:** 07-assisted-apply-tracker
**Areas discussed:** Apply package surface & content, Screening-answer drafting & honesty, Status transitions & the applied gate, Tracker view & history management

---

## Apply package surface & content

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated `/listings/{id}/apply` page | Mirrors Phase 6's `/listings/{id}/cv`; owns assembly, artefact link, drafts, checklist | ✓ |
| Section on the listing detail page | Collapsible block on the detail page; detail already carries fit breakdown + tailoring links | |
| Tab in the detail page | Overview / Apply tabs, no new route | |

**User's choice:** Dedicated page.
**Notes:** Keeps the apply surface parallel to the tailoring surface the user already knows.

| Option | Description | Selected |
|--------|-------------|----------|
| Only when an `ok` cv_artifact exists | APPLY-01 names the verified PDF; D-118 exposes only `ok` artefacts. Else "tailor and verify first" linking to `/cv` | ✓ |
| Always, PDF slot empty until ok | Shows link/checklist before tailoring | |

**User's choice:** Gate on an `ok` artefact.

| Option | Description | Selected |
|--------|-------------|----------|
| Assembled on open from stored data | No LLM call until drafts are explicitly requested | ✓ |
| Explicit prepare action that also drafts | One action assembles + drafts | |

**User's choice:** Assembled on open.

| Option | Description | Selected |
|--------|-------------|----------|
| Read-only from stored ranking gaps | Renders D-81 gaps; nothing new persisted | ✓ |
| Tickable and persisted per application | New table/column + migration | |
| Tickable, session-only | Resets on reload | |

**User's choice:** Read-only.

---

## Screening-answer drafting & honesty

| Option | Description | Selected |
|--------|-------------|----------|
| Settings-defined set + ad-hoc add | Questions are not reliably in the listing; inferring them invents questions the form may never ask | ✓ |
| LLM infers questions from the listing | Cheap UX, invented questions | |
| User pastes questions from the form | Tool only drafts answers | |

**User's choice:** Settings list + ad-hoc add box.

| Option | Description | Selected |
|--------|-------------|----------|
| Grounded, evidence shown per answer | CvFacts + listing text only; unsupported claims warn | ✓ |
| Free prose with a disclaimer | No evidence trail | |

**User's choice:** Grounded with per-answer evidence.

| Option | Description | Selected |
|--------|-------------|----------|
| Persisted per listing | Survives reload; new table + migration from head 0005 | ✓ |
| Ephemeral, regenerate each time | No migration, re-spends an LLM call per visit | |

**User's choice:** Persisted.

| Option | Description | Selected |
|--------|-------------|----------|
| Copy-to-clipboard per answer | Never auto-inserted; consistent with APPLY-02 | ✓ |
| Editable textarea then copy | Local edits only | |

**User's choice:** Copy per answer.

---

## Status transitions & the applied gate

| Option | Description | Selected |
|--------|-------------|----------|
| Guided: user drives the outcome stages | `discovered`/`queued` tool-set; user drives the rest; the CHECK enum in 0001 carries all eight | ✓ |
| Free: any status to any status | No rules | |
| Guided subset of six | Leave two enum values unused in the UI | |

**User's choice:** Guided outcome stages.

| Option | Description | Selected |
|--------|-------------|----------|
| Require an ok artefact to record `applied` | APPLY-04 + D-118; ok-only picker defaults to latest | ✓ |
| Allow `applied` with no artefact | Flag the gap instead | |

**User's choice:** Required.

| Option | Description | Selected |
|--------|-------------|----------|
| Set `applied_at` automatically | Mirrors `event_repo`'s never-forge-a-time rule | ✓ |
| User-editable applied date | Allows backdating | |

**User's choice:** Automatic.

| Option | Description | Selected |
|--------|-------------|----------|
| Row holds status + append-only event per transition | `applications.status` is current; one `application_events` row in the same transaction | ✓ |
| Derive status from the event log only | Column becomes a projection/cache | |

**User's choice:** Row + event per transition.

---

## Tracker view & history management

| Option | Description | Selected |
|--------|-------------|----------|
| Table at `/applications` | Reuses queue table + HTMX partial patterns | ✓ |
| Kanban board by stage | Stronger visuals, heavier (Sortable.js), small volume | |
| Filter on the queue page | Mixes two jobs | |

**User's choice:** Table view.

| Option | Description | Selected |
|--------|-------------|----------|
| Stage filter + needs-action view + search | Overdue first, then upcoming `next_action_at`; text over company/title/notes | ✓ |
| Stage filter only | | |

**User's choice:** Full slicing.

| Option | Description | Selected |
|--------|-------------|----------|
| Expandable inline timeline per row | HTMX partial: from→to, timestamp, note | ✓ |
| Separate `/applications/{id}` detail page | | |
| Inline now, detail page deferred | | |

**User's choice:** Inline timeline.

| Option | Description | Selected |
|--------|-------------|----------|
| Notes editable; only status events immutable | `notes` and `next_action_at` are mutable columns | ✓ |
| Notes append-only too | Every note becomes an event; row notes becomes a projection | |

**User's choice:** Notes editable.

---

## the agent's Discretion

- Name/columns of the persisted screening-draft table (must be a new migration from head `0005_cv_drafts`).
- Exact Settings key names for the screening question list.
- Drafting prompt wording and how per-answer evidence is attached.
- Template file names and exact route/path naming for the apply page.
- Which HTMX partials are factored out; repository module name and layout.
- Tracker pagination approach (follow the queue's existing approach) and the model used for the drafting call.

## Deferred Ideas

- Separate `/applications/{id}` detail page — revisit if the tracker grows.
- Tickable, persisted gap checklist — needs a new table and a definition of what a tick means.
- Export applications/queue data (v2 APPLY-07); batched digest notifications (v2 APPLY-08).
- Browser-extension autofill (AF-9) — later milestone, not v1.
- Application retention/pruning and scheduled runs — Phase 8.
- Ghost-job / listing-quality score (v2 RANK-10, DF-10).
