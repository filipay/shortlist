# Phase 2: Clean, Filtered, Queryable Queue - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-15
**Phase:** 2-clean-filtered-queryable-queue
**Areas discussed:** Merge policy & revert, Criteria & filter tunability, Queue browse signals, Run history & explainability

---

## Merge policy & revert

### Q1 — Merge automatically or wait for confirmation?

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-merge above θ, auditable + one-click revert | Run-time auto-merge of high-confidence matches; snapshot + audit view + revert | ✓ |
| Propose-and-confirm | Merge candidates await approval in a review queue | |
| Auto-merge, no review surface | Silent merge, revert only via manual DB/snapshot action | |

**User's choice:** High-confidence matches merge automatically. *"Do maintain a record of what the job listing was so that the user can inspect themselves. Maybe show it in the details of the job."*
**Notes:** The retained record must be human-inspectable from the job detail, not just a DB row.

### Q2 — Which source's fields does the surviving listing keep?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep first-seen canonical, fill blanks only | Original title/company/URL stay; only empty fields filled from the twin | ✓ |
| Configurable source priority, overwrite on merge | Ranked source order decides canonical fields; snapshot makes it reversible | |
| Per-field "best wins" | Longest description, real salary, direct URL, newest posted_at | |

**User's choice:** Keep first-seen canonical, fill blanks only.

### Q3 — What happens after you revert an incorrect merge?

| Option | Description | Selected |
|--------|-------------|----------|
| Full undo + remember "these are distinct" | Restore snapshot, un-hide twin, record the pair as not-a-duplicate | ✓ |
| Undo this merge only, no memory | Restore both rows; a later run may re-merge them | |
| Undo + a curated "never merge" list | Full undo plus a management screen of negative pairs | |

**User's choice:** Full undo + remember "these are distinct".

### Q4 — Where should merge visibility live (QUEUE-09)?

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated Merges audit view + rate stat | Page of every merge with rate, one-click revert; job detail shows "merged from N sources" | ✓ |
| Inline in job detail only | Per-job provenance + a merge-rate number on the queue header | |
| Run-history panel | Merge rate + pairs shown inside each run's report | |

**User's choice:** Dedicated Merges audit view + rate stat.

---

## Criteria & filter tunability

### Q1 — Should a named search carry its own filter rules, or is filtering a global layer?

| Option | Description | Selected |
|--------|-------------|----------|
| Unified named search: query + its own rules | One object per named search holds fetch query + exclusions | ✓ |
| Two layers: searches fetch, one global filter set | Named searches are fetch-only; one ruleset applies everywhere | |
| Global defaults + per-search overrides | Global ruleset with per-search add/remove/disable | |

**User's choice:** Unified named search: query + its own rules.

### Q2 — How is CRIT-02 reproducibility enforced?

| Option | Description | Selected |
|--------|-------------|----------|
| Snapshot the criteria onto each run, bump version | Immutable snapshot + `searches.version`; no history table | ✓ |
| Full version-history table with diff/rollback | `criteria_versions` table, diffs and rollback UI | |
| Snapshot only, version as a display counter | No defined version semantics | |

**User's choice:** Snapshot the criteria onto each run, bump version.

### Q3 — How are hard filter rules represented and tuned (FILT-01/04)?

| Option | Description | Selected |
|--------|-------------|----------|
| Typed rule rows, form-edited per kind | `filter_rules` table, typed kinds, per-kind form, pure evaluators | ✓ |
| JSON ruleset edited in a textarea | One JSON document per search with validation | |
| Config-only rules, no UI | Rules in settings (fails FILT-04) | |

**User's choice:** Typed rule rows, form-edited per kind.

### Q4 — Where does "why was this listing excluded" surface (FILT-03)?

| Option | Description | Selected |
|--------|-------------|----------|
| Inline "Show excluded" toggle with rule chips | Dimmed rejected rows with rule chips + per-rule counts | ✓ |
| Separate Excluded page grouped by rule/run | Dedicated rejection browser | |
| Run counts only, reason on detail page | Minimal surface | |

**User's choice:** Inline "Show excluded" toggle with rule chips.

---

## Queue browse signals

### Q1 — How is "new since last visit" tracked (QUEUE-07)?

| Option | Description | Selected |
|--------|-------------|----------|
| DB watermark updated on queue view | `last_queue_view_at` row + explicit "Mark all as seen" | ✓ |
| Append-only visit log, per-visit new counts | Every visit recorded; new measured against previous visit | |
| Browser cookie / localStorage | Client-side only | |

**User's choice:** DB watermark updated on queue view.

### Q2 — What makes a listing "stale" (QUEUE-07)?

| Option | Description | Selected |
|--------|-------------|----------|
| last_seen_at older than N days, or inactive | Configurable `stale_after_days` or `is_active=false`; badge only | ✓ |
| Absent from the latest run | Treat run absence as stale | |
| posted_at older than N days | Board-provided date drives staleness | |

**User's choice:** last_seen_at older than N days, or inactive.

### Q3 — How should save and hide behave (QUEUE-08)?

| Option | Description | Selected |
|--------|-------------|----------|
| Distinct Save + Hide, projected state, filters + undo | Separate append-only events; Saved/Hidden filters; one-tap undo | ✓ |
| One Dismiss action only | Single removal action | |
| Three states: saved / shortlisted / hidden | Three explicit states with their own views | |

**User's choice:** Distinct Save + Hide, projected state, filters + undo.

### Q4 — How should full-text queue search behave (QUEUE-06)?

| Option | Description | Selected |
|--------|-------------|----------|
| FTS on title+company+description, bm25 when searching | FTS5 MATCH, recency order with no query, Load more, bound params | ✓ |
| Title + company only | Narrower, higher precision, weaker recall | |
| Advanced search form + always relevance-ranked | Replaces recency ordering; adds a form | |

**User's choice:** FTS on title+company+description, bm25 when searching.

---

## Run history & explainability

### Q1 — Where does run history live, and what does a run record show (RUN-03/04)?

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated /runs page + last-run strip on the queue | One row per run, expandable detail, queue strip links there | ✓ |
| Panel on the queue page only | Collapsible history, no separate route | |
| API/JSON only, minimal UI | JSON surface + one-line status | |

**User's choice:** Dedicated /runs page + last-run strip on the queue.

### Q2 — How should a run explain an empty or thin queue (RUN-03)?

| Option | Description | Selected |
|--------|-------------|----------|
| Structured reason + counts + collapsible raw log | Reason enum + counts + rendered sentence + raw stage log | ✓ |
| Structured reason + counts only | No raw log surface | |
| Raw stage log only | structlog tail, no structured reason | |

**User's choice:** Structured reason + counts + collapsible raw log.

### Q3 — When you tune a filter rule, do previously-excluded listings get a second chance?

| Option | Description | Selected |
|--------|-------------|----------|
| Re-evaluate every run; exclusions are per-run observations | Retuning can bring a listing back; one exclusion row per run | ✓ |
| Permanent exclusion memory, manual restore only | Once rejected, always rejected | |
| Re-evaluate + flag listings that came back | Plus a derived "was excluded before" marker | |

**User's choice:** Re-evaluate every run; exclusions are per-run observations.

### Q4 — Now that named searches exist, what does "Run search now" run?

| Option | Description | Selected |
|--------|-------------|----------|
| Run all enabled searches; per-search run on the criteria page | One-tap trigger; per-search action for iteration | ✓ |
| Trigger opens a search picker | Checkboxes of enabled searches each time | |
| One active search at a time | Only the default search runs | |

**User's choice:** Run all enabled searches; per-search run on the criteria page.

---

## the agent's Discretion

- Dedup θ default + tuning procedure; fuzzy-score vs normalised-tuple gate; candidate blocking strategy.
- Merge stage placement within `run_pipeline()` and its interaction with `deduped_count`.
- The exact `_INJECTION_PATTERNS` catalogue and which identifiers are dropped vs hashed.
- The `runs`-row shape when multiple searches run; the "Run this one" route shape.
- Run-history retention/pruning, queue page size, and the default rule vocabulary shipped day one.
- Whether `Show excluded` lists excluded-but-merged rows and how `Load more` interacts with it.

## Deferred Ideas

- Cross-source "also seen on…" links (SRC-12) — v2.
- Adzuna adapter (SRC-11) — conditional at Phase 8.
- Ranking/scoring/rationale (Phase 5), CV store/tailoring (Phases 4/6), tracker (Phase 7), scheduling + phone pass (Phase 8).
- Criteria version-history table with diff/rollback — consciously deferred (snapshot design keeps it open).
