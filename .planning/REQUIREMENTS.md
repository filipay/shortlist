# Requirements: Job Search Copilot

**Defined:** 2026-09-15
**Core Value:** Every morning there is one ranked, explained, apply-ready queue of jobs worth considering — so the search→judge→tailor loop costs minutes instead of hours.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Sources (SRC)

- [x] **SRC-01**: User can run a search against LinkedIn and receive normalised listings
- [x] **SRC-02**: User can run a search against Indeed and receive normalised listings
- [x] **SRC-03**: Every source produces one normalised listing shape (title, company, location, salary, apply URL, description, posted date, source)
- [x] **SRC-04**: User can add a new job source by implementing one adapter interface and registering it, with no changes to the core pipeline
- [x] **SRC-05**: A failing or timing-out source returns a partial result instead of aborting the run
- [ ] **SRC-06**: The system reads public logged-out pages only — no credential path exists anywhere in the codebase
- [ ] **SRC-07**: User can see per-source health (last success, listings returned, field fill-rate) and a probe that detects silent breakage
- [ ] **SRC-08**: Untrusted listing text is sanitised at the ingest boundary so it cannot inject into prompts, templates, or the database
- [x] **SRC-09**: Each source declares its capabilities, so an unsupported filter is reported rather than silently ignored
- [ ] **SRC-10**: Third-party PII (e.g. recruiter emails) is stripped at the adapter boundary and never stored

### Queue (QUEUE)

- [x] **QUEUE-01**: User can browse a persisted queue of listings that survives restarts
- [x] **QUEUE-02**: Re-running a search never creates a duplicate row for the same listing on the same source
- [ ] **QUEUE-03**: The same job found on two sources is merged rather than double-listed, with a reversible audit record
- [ ] **QUEUE-04**: User can revert an incorrect merge
- [x] **QUEUE-05**: Every listing records first-seen and last-seen timestamps and a content hash
- [ ] **QUEUE-06**: User can full-text search the queue
- [ ] **QUEUE-07**: Queue shows which listings are new since last visit and which look stale
- [ ] **QUEUE-08**: User can save or hide a listing, and those actions are recorded as append-only events
- [ ] **QUEUE-09**: User can see the merge rate and the rows behind it, so dedup behaviour is auditable

### Criteria (CRIT)

- [ ] **CRIT-01**: User can create, edit, and delete named search criteria (keywords, location, remote, salary floor, seniority, exclusions)
- [ ] **CRIT-02**: Criteria are versioned so any past run is reproducible
- [ ] **CRIT-03**: User can enable or disable a saved search without deleting it

### Filtering (FILT)

- [ ] **FILT-01**: Deterministic rules reject listings before any LLM call is made
- [ ] **FILT-02**: Every rejection records which rule fired and why
- [ ] **FILT-03**: User can see why a specific listing was excluded
- [ ] **FILT-04**: User can tune filter rules from the UI without a code change

### Ranking (RANK)

- [ ] **RANK-01**: User gets each surviving listing scored against their CV using named, inspectable factors
- [ ] **RANK-02**: Every score stores its per-factor sub-scores, not just a single total
- [ ] **RANK-03**: The total score is computed in code from stored sub-scores and weights
- [ ] **RANK-04**: User can adjust factor weights and see rankings re-derive
- [ ] **RANK-05**: Each ranked listing shows a rationale grounded in stored evidence
- [ ] **RANK-06**: User sees a requirement-by-requirement fit breakdown with named gaps on the job detail view
- [ ] **RANK-07**: Scoring is absolute per listing and stable across repeated runs (never relative ranking of a batch)
- [ ] **RANK-08**: LLM spend is capped per run and per day, enforced before the call is made

### CV Pipeline (CV)

- [ ] **CV-01**: The CV is modelled as structured data with stable, enumerated IDs
- [ ] **CV-02**: The human-authored LaTeX CV stays canonical and is never modified by the tool
- [ ] **CV-03**: A golden reproduction test proves the structured CV renders back to a fact-equivalent base CV
- [ ] **CV-04**: The system renders LaTeX deterministically from structured data
- [ ] **CV-05**: The system compiles LaTeX to PDF inside the container
- [ ] **CV-06**: User content is escaped so it cannot break or corrupt the LaTeX document

### Tailoring (TAIL)

- [ ] **TAIL-01**: User can generate a CV tailored to a specific listing
- [ ] **TAIL-02**: Tailoring is expressed as a typed patch (move / reweight / demote / drop / reorder) over enumerated IDs, with no free-text field on the path to the PDF
- [ ] **TAIL-03**: The tool never rewrites or invents CV claims — bullet text is immutable
- [ ] **TAIL-04**: A verification gate checks the compiled PDF for any unsupported content
- [ ] **TAIL-05**: A CV that fails verification is blocked and cannot be downloaded or attached
- [ ] **TAIL-06**: Verification never auto-repairs content — it blocks
- [ ] **TAIL-07**: User can review the tailored CV and its change log before compiling
- [ ] **TAIL-08**: Anything dropped from the CV is listed explicitly with a reason

### Apply (APPLY)

- [ ] **APPLY-01**: User can open an apply package for a listing (verified PDF, apply link, drafted screening answers, gap checklist)
- [ ] **APPLY-02**: The tool never submits an application on the user's behalf
- [ ] **APPLY-03**: User can record an application with a status stage and notes
- [ ] **APPLY-04**: Every recorded application links to the exact CV version that was sent
- [ ] **APPLY-05**: Application status changes are recorded as append-only events
- [ ] **APPLY-06**: User can set a next action date or deadline on an application

### Runs (RUN)

- [x] **RUN-01**: User can trigger a search run manually from the UI
- [x] **RUN-02**: Runs execute in the background without freezing the UI
- [ ] **RUN-03**: Every run records what it did, what it found, and — when the queue is empty — why
- [ ] **RUN-04**: User can see run history
- [ ] **RUN-05**: User can schedule recurring runs
- [ ] **RUN-06**: User can see when the next scheduled run will happen
- [ ] **RUN-07**: User can check system and source health from a health endpoint surfaced in the UI

### Web UI (UI)

- [ ] **UI-01**: User can browse ranked jobs in a list
- [ ] **UI-02**: User can open a job detail showing the fit breakdown and ranking rationale
- [ ] **UI-03**: User can edit search criteria and ranking weights
- [ ] **UI-04**: User can view and manage the application tracker
- [ ] **UI-05**: User can preview and download the tailored CV PDF
- [ ] **UI-06**: The UI is usable from both a laptop and a phone browser
- [ ] **UI-07**: All UI assets are vendored locally with no CDN dependency

### Platform (PLAT)

- [ ] **PLAT-01**: The whole application runs locally via Docker Compose
- [ ] **PLAT-02**: The LLM is reached through opencode as a sibling service with no second provider key required
- [ ] **PLAT-03**: Every API route carries an auth seam so Authentik OIDC can be added later without rewriting routes
- [ ] **PLAT-04**: Limits, thresholds, and the LaTeX engine are configuration, not hard-coded constants
- [ ] **PLAT-05**: The opencode structured-output contract is covered by a test that fails loudly on an upgrade
- [ ] **PLAT-06**: Scheduled runs are single-worker safe and persist across restarts

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Sources

- **SRC-11**: User can add Adzuna (and further portals) as additional sources via the adapter interface
- **SRC-12**: User sees cross-source "also seen on…" links for a listing

### Ranking

- **RANK-09**: Ranking learns from the user's save/skip history
- **RANK-10**: User sees a listing-quality score (ghost/stale risk) separate from candidate fit
- **RANK-11**: User sees salary-market context for a role and location

### Tailoring

- **TAIL-09**: User can generate a grounded cover letter that reuses the same evidence IDs as the CV
- **TAIL-10**: User can run an ATS parse check against the tailored CV

### Apply

- **APPLY-07**: User can export applications and queue data
- **APPLY-08**: User receives batched notifications (digest, not per-listing)

### Platform

- **PLAT-07**: User can sign in via Authentik OIDC, and friends get their own isolated data
- **PLAT-08**: The tool is exposed as an MCP server so opencode can drive it conversationally
- **PLAT-09**: The tool is reachable beyond the local machine

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Unattended auto-apply / auto-submit | LinkedIn and Indeed ban automation; AIHawk's contributors were banned and it dropped LinkedIn entirely. User chose assisted apply. |
| Bulk "apply to all selected" | Same ban exposure plus the quality problem that makes mass applications self-defeating |
| CAPTCHA-solving or credentialed scraping | Converts a maintenance problem into a permanent account-ban problem. Hard architectural line — no credential path, ever. |
| Browser extension driving portals | Fragile, ToS-hostile, and duplicates the adapter layer |
| LLM emitting LaTeX or free prose into the CV | The primary fabrication vector; tailoring is a typed ID patch only |
| General PDF/DOCX résumé parsing | LaTeX is the source of truth; parsing binary formats is a different problem |
| Vector DB / embedding-based ranking | Independently measured as no better (+0.0000 NDCG@10) at 2.2× the runtime |
| Multi-user auth in v1 | Deferred by the user; the route seam ships now, auth later |
| MCP server | Deferred by the user to a future feature |
| Mobile app | Web-first; the responsive UI covers phone use |
| Real-time listing feeds | The use case is a daily queue, not a live ticker |
| A column per board-specific field on `listings` | Board extras go in a JSON column; a wide table couples core to boards |
| Per-listing notifications | Alert fatigue; at most a batched digest, and only if needed |
| A full job-search CRM | Beyond the tracker; scope creep against the Core Value |
| 100% ATS-match optimisation | Optimising for a parser over honesty contradicts the core ethical constraint |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SRC-01 | Phase 1 | Complete |
| SRC-02 | Phase 1 | Complete |
| SRC-03 | Phase 1 | Complete |
| SRC-04 | Phase 1 | Complete |
| SRC-05 | Phase 1 | Complete |
| SRC-06 | Phase 1 | Pending |
| SRC-07 | Phase 1 | Pending |
| SRC-08 | Phase 1 | Pending |
| SRC-09 | Phase 1 | Complete |
| SRC-10 | Phase 1 | Pending |
| QUEUE-01 | Phase 1 | Complete |
| QUEUE-02 | Phase 1 | Complete |
| QUEUE-03 | Phase 2 | Pending |
| QUEUE-04 | Phase 2 | Pending |
| QUEUE-05 | Phase 1 | Complete |
| QUEUE-06 | Phase 2 | Pending |
| QUEUE-07 | Phase 2 | Pending |
| QUEUE-08 | Phase 2 | Pending |
| QUEUE-09 | Phase 2 | Pending |
| CRIT-01 | Phase 2 | Pending |
| CRIT-02 | Phase 2 | Pending |
| CRIT-03 | Phase 2 | Pending |
| FILT-01 | Phase 2 | Pending |
| FILT-02 | Phase 2 | Pending |
| FILT-03 | Phase 2 | Pending |
| FILT-04 | Phase 2 | Pending |
| RANK-01 | Phase 5 | Pending |
| RANK-02 | Phase 5 | Pending |
| RANK-03 | Phase 5 | Pending |
| RANK-04 | Phase 5 | Pending |
| RANK-05 | Phase 5 | Pending |
| RANK-06 | Phase 5 | Pending |
| RANK-07 | Phase 5 | Pending |
| RANK-08 | Phase 5 | Pending |
| CV-01 | Phase 4 | Pending |
| CV-02 | Phase 4 | Pending |
| CV-03 | Phase 4 | Pending |
| CV-04 | Phase 4 | Pending |
| CV-05 | Phase 4 | Pending |
| CV-06 | Phase 4 | Pending |
| TAIL-01 | Phase 6 | Pending |
| TAIL-02 | Phase 6 | Pending |
| TAIL-03 | Phase 6 | Pending |
| TAIL-04 | Phase 6 | Pending |
| TAIL-05 | Phase 6 | Pending |
| TAIL-06 | Phase 6 | Pending |
| TAIL-07 | Phase 6 | Pending |
| TAIL-08 | Phase 6 | Pending |
| APPLY-01 | Phase 7 | Pending |
| APPLY-02 | Phase 7 | Pending |
| APPLY-03 | Phase 7 | Pending |
| APPLY-04 | Phase 7 | Pending |
| APPLY-05 | Phase 7 | Pending |
| APPLY-06 | Phase 7 | Pending |
| RUN-01 | Phase 1 | Complete |
| RUN-02 | Phase 1 | Complete |
| RUN-03 | Phase 2 | Pending |
| RUN-04 | Phase 2 | Pending |
| RUN-05 | Phase 8 | Pending |
| RUN-06 | Phase 8 | Pending |
| RUN-07 | Phase 8 | Pending |
| UI-01 | Phase 5 | Pending |
| UI-02 | Phase 5 | Pending |
| UI-03 | Phase 5 | Pending |
| UI-04 | Phase 7 | Pending |
| UI-05 | Phase 6 | Pending |
| UI-06 | Phase 8 | Pending |
| UI-07 | Phase 1 | Pending |
| PLAT-01 | Phase 1 | Pending |
| PLAT-02 | Phase 3 | Pending |
| PLAT-03 | Phase 1 | Pending |
| PLAT-04 | Phase 1 | Pending |
| PLAT-05 | Phase 3 | Pending |
| PLAT-06 | Phase 8 | Pending |

**Coverage:**

- v1 requirements: 74 total
- Mapped to phases: 74 ✓ (Phase 1: 19, Phase 2: 15, Phase 3: 2, Phase 4: 6, Phase 5: 11, Phase 6: 9, Phase 7: 7, Phase 8: 5)
- Unmapped: 0 ✓

---
*Requirements defined: 2026-09-15*
*Last updated: 2026-09-15 after roadmap creation — 74/74 v1 requirements mapped*
