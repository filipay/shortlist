# Phase 7: Assisted Apply + Tracker — Research

**Researched:** 2026-09-30
**Domain:** Python/FastAPI/SQLite append-only event history; grounded LLM drafting; HTMX page + partial patterns
**Confidence:** HIGH (every claim below is read from this repo this session; cited file:line)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-120:** The apply package is a **dedicated page** at `/listings/{id}/apply`, mirroring Phase 6's `/listings/{id}/cv` page; the listing detail page links to it. Every route declares the `user: User = Depends(current_user)` auth seam (PLAT-03).
- **D-121:** A package is available **only when an `ok` `cv_artifact` exists** for the listing. Otherwise the page shows a "tailor and verify first" state linking to the tailoring page. APPLY-01 names the verified PDF as package content, and D-118 exposes only `ok` artefacts to download/link.
- **D-122:** The package is **assembled on open from stored data** (ok artefact, `listing.apply_url`, stored ranking gaps, stored drafts). Opening the page makes no LLM call; drafting is an explicit user action.
- **D-123:** The gap checklist is **read-only**, rendered from the requirement gaps the ranking call already stores (D-81). Nothing new is persisted and no tick state exists.
- **D-124:** Questions come from a **user-defined list in Settings** plus an ad-hoc "add a question" box on the package page. The tool does **not** infer questions from the listing text — application-form questions are not reliably in a job description, and inferring them invents questions the real form may never ask.
- **D-125:** Drafted answers are **grounded in stored `CvFacts` + the listing text only**, and each answer carries the evidence it used. An answer containing an unsupported claim surfaces a **warning** rather than shipping silently. — **Reversibility:** costly — the drafted-answer record (answer + evidence) is a stored shape consumed by the package UI and any future export (v2 APPLY-07); loosening the contract invalidates stored drafts and erodes the phase's honesty guarantee.
- **D-126:** Drafts **persist per listing** in a new table (migration from head `0005_cv_drafts`), one row per question, so they survive reload and are visible in the package. — **Reversibility:** one-way — undo requires a migration and would drop stored drafts.
- **D-127:** Consumption is **copy-to-clipboard per answer**. Nothing is auto-inserted into a portal and **no submit path exists anywhere** (APPLY-02, PROJECT.md hard line).
- **D-128:** Transitions are **guided**: `discovered` / `queued` are tool-set; the user drives `shortlisted → applied → interviewing → offer` / `rejected` / `withdrawn`. The eight-value vocabulary is already frozen by `ck_applications_status` in migration `0001`. — **Reversibility:** costly — changing or adding a stage means a migration against a CHECK constraint, and the recorded history uses the old names.
- **D-129:** Moving to `applied` **requires selecting an `ok` artefact** from an ok-only picker (defaulting to the latest), satisfying APPLY-04 and D-118. — **Reversibility:** costly — the application→artefact link is the phase's core integrity contract; relaxing it strands rows with no link and breaks the "exact CV sent" guarantee.
- **D-130:** `applied_at` is **stamped by the transition**, never typed — mirroring `event_repo`'s rule that append helpers never forge a time.
- **D-131:** `applications.status` holds the **current value on the row**, and exactly one `application_events` row (`from_status`, `to_status`, `occurred_at`, `note`) is appended **in the same transaction**. The event table is insert-only, trigger-enforced, mirroring `listing_events` (ARCHITECTURE L1160; PITFALLS L247/L255 name the "status column with no history" anti-pattern this avoids). — **Reversibility:** costly — switching to a status derived purely from the log later would need the NOT NULL CHECK column relaxed and every read rewritten.
- **D-132:** The tracker is a **table view at `/applications`**: listing/company, current stage, applied date, next action, latest note. It reuses the existing queue table markup and HTMX partial-swap pattern.
- **D-133:** The user can slice it by **stage filter**, a **needs-action view** (overdue first, then upcoming `next_action_at`), and **free-text search** over company/title/notes (UI-04 "view and manage").
- **D-134:** The append-only history renders as an **expandable inline timeline per row** (HTMX partial): `from → to`, timestamp, note. No separate `/applications/{id}` detail page in v1.
- **D-135:** **Notes and `next_action_at` are ordinary mutable columns**; only status changes are append-only events.

### the agent's Discretion

Left to the planner/implementer (not re-asked): the new draft table's name and columns; the exact Settings key names for the screening question list; the drafting prompt wording and how evidence is attached per answer; the template file names and the exact apply-page URL/path naming; which HTMX partials are factored out; the repository module name and layout (`app/db/repositories/`); tracker pagination (follow the queue's existing approach); the model used for the drafting call. No area was delegated "you decide" on a product question.

### Deferred Ideas (OUT OF SCOPE)

- A separate `/applications/{id}` detail page — D-134 keeps the inline timeline in v1; revisit if the tracker grows.
- A tickable, persisted gap checklist — D-123 keeps it read-only; needs a new table and a decision about what a tick means.
- Export applications and queue data (v2 APPLY-07) and batched digest notifications (v2 APPLY-08).
- Browser-extension autofill (FEATURES AF-9) — the legitimate form of prefill, but a second runtime and not a v1 build.
- Application retention/pruning and scheduled runs — Phase 8 (Operations + Polish).
- Ghost-job / listing-quality score separate from candidate fit (v2 RANK-10, FEATURES DF-10).
</user_constraints>

## Summary

Phase 7 is almost entirely an **assembly and integrity** phase, not a new-technology phase. Three of its four pillars already exist in the tree and only need a code layer over them:

1. **The schema already exists.** `applications` and `application_events` ship in migration `0001` with a frozen status vocabulary (`ck_applications_status`), a nullable `applications.cv_artifact_id` FK, and `applied_at`/`next_action_at`/`notes`. Nothing references them yet. `listings.apply_url` also already exists.
2. **The append-only pattern already exists** and is battle-tested: `listing_events` carries two `BEFORE UPDATE/DELETE` triggers that `RAISE(ABORT, 'listing_events is append-only')` [VERIFIED: alembic/versions/0001_initial_schema.py:343-350], and `event_repo.append_event` is the INSERT-only writer with a SAVEPOINT, an allow-list check, and a never-forge-the-clock contract [VERIFIED: app/db/repositories/event_repo.py:148-185]. The `application_events` mirror is a copy of that contract, not a new design.
3. **The page + action + HTMX-partial pattern already exists**: `app/api/tailoring.py` (page / generate / compile / pdf) and `tailoring.html` / `_tailoring_review.html` are the template to mirror for `/listings/{id}/apply`; `app/api/events.py` + `_listing_row.html` are the template to mirror for the tracker's row swap and inline history.

The only genuinely new persisted state is the **screening-draft table** (D-126) and two **triggers on the existing `application_events` table**. The only genuinely new logic is the **grounding check for drafted answers** (D-125), which belongs beside the existing anti-fabrication checks and is governed by `.planning/CONVENTIONS.md` (anchor structurally, fail closed visibly, no false guarantees).

**Primary recommendation:** Build a thin `app/db/repositories/application_repo.py` + `app/db/repositories/screening_draft_repo.py`, a `app/verify/screening.py` grounding checker, a `app/pipeline/draft.py` one-call drafter, one migration `0006` (new `screening_drafts` table + two `application_events` triggers), and `app/api/apply.py` + `app/api/applications.py` routes mirroring `app/api/tailoring.py`. **Reuse `purpose="tailor"` for the drafting `llm_calls` row** — widening `ck_llm_calls_purpose` is a batch-table-recreation risk for zero phase value.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| APPLY-01 | User can open an apply package for a listing (verified PDF, apply link, drafted screening answers, gap checklist) | Q1 (page pattern), Q2 (drafts), `latest_for_listing(ok_only=True)` gate [VERIFIED: cv_artifact_repo.py:163-177], `listings.apply_url` [VERIFIED: models.py:147], `score_repo` stored gaps [VERIFIED: score_repo.py:298-311] |
| APPLY-02 | The tool never submits an application on the user's behalf | No submit route is planned; `/listings/{id}/apply` is read-only + a local draft action. D-127. Enforced structurally: no outbound POST form to a portal exists anywhere. |
| APPLY-03 | User can record an application with a status stage and notes | Q3 (`apps` insert), Q4 (tracker), `applications.notes`/`status` exist [VERIFIED: models.py:462-483] |
| APPLY-04 | Every recorded application links to the exact CV version that was sent | Q3 (ok-only attach gate mirroring D-118), `applications.cv_artifact_id` [VERIFIED: models.py:470], `read_for_download(ok_only=True)` [VERIFIED: cv_artifact_repo.py:180-194] |
| APPLY-05 | Application status changes are recorded as append-only events | Q1 (`application_events` triggers + `append_event`), D-131 |
| APPLY-06 | User can set a next action date or deadline on an application | Q4 (needs-action query), `applications.next_action_at` [VERIFIED: models.py:472] |
| UI-04 | User can view and manage the application tracker | Q4 (tracker table + filters + inline timeline), Q5 (Settings surface for the question list) |

## Project Constraints (from AGENTS.md)

Binding directives extracted from `AGENTS.md` (the GSD project block) that this phase must honour:

- **Tech stack**: Python-first backend; LaTeX for the CV; local-only; Docker; no second provider key. Phase 7 adds **no new third-party package**.
- **Auth**: none in v1, but the code must not architecturally block Authentik later — every new route declares `user: User = Depends(current_user)`; no `user_id`/`owner_id` column may be added (`tests/test_auth_seam.py`).
- **Legal/ToS hard line**: applying is assisted-only; no unattended submit, no bulk apply, no CAPTCHA/credential path. The phase must not create any route that posts to a portal.
- **Privacy**: CVs and personal data stay local; everything runs locally for v1.
- **Cost**: LLM calls are the dominant variable cost; the drafting call must draw from the existing `llm_calls` ledger and the shared reserve-then-call ceiling (D-119), with **no new numeric ceiling** (mirrors tailoring's O1).
- **`.planning/CONVENTIONS.md`** (binding for any check comparing model-produced free text against structured data — explicitly includes "anything added later"): anchor structurally never lexically; fail closed visibly; add a fixture with the literal repro string; test the failure class; no false guarantees in prose; symmetric verification pressure (test "does it accept valid input?", not only "does it catch the bad thing?").
- **`.planning/CONVENTIONS.md` / ROADMAP**: new persisted state arrives as a NEW table with a NEW migration (never a widened column with a CHECK, never `create_all`); `tests/db/test_migration_contract.py` pins the head.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Apply package assembly (page render) | API / Backend (`app/api/apply.py`) | Templates (Jinja) | Reads stored artefact + `apply_url` + stored gaps + stored drafts; no LLM on open (D-122). Mirrors `app/api/tailoring.py:390-443`. |
| Screening-answer drafting | Backend pipeline (`app/pipeline/draft.py`) | LLM port (`LLMBackend.complete_structured`) | Explicit user action; one call; audit row via `llm_call_repo`; never on page open. |
| Draft grounding / anti-fabrication check | Verify package (`app/verify/screening.py`) | Domain (`app/domain/tex.py`, `app/verify/numbers.py`) | Same class as the existing fabrication checks; owns `rapidfuzz` if an advisory band is used (forbidden under `app/domain`). |
| Draft persistence | Repository (`app/db/repositories/screening_draft_repo.py`) | Database (new `screening_drafts` table) | Only place SQL lives; one SAVEPOINT write; never commits. |
| Status transition + applied gate | Repository (`application_repo.py`) | Database (row + `application_events`) | The integrity contract: current state on the row, history appended in the same transaction (D-131). |
| Append-only enforcement | Database (triggers) | Repository (INSERT-only API) | The current state/history split is a schema-level invariant, not a convention. |
| Tracker list / filters / inline history | API (`app/api/applications.py`) | Templates + small HTMX partial | Join `applications`→`listings`→`companies`; needs-action order in SQL; history as an expandable partial (D-134). |
| Screening question list (user-editable) | API + Settings page | Database single-row/row store | `Settings` is env-static and cannot be edited in the UI; mirror `ranking_config`'s user-editable-doc precedent. |

## Standard Stack

**No new external packages.** Phase 7 reuses what is already pinned in `pyproject.toml`:

| Library | Version | Purpose | Why standard here |
|---------|---------|---------|-------------------|
| `pydantic` | 2.13.5 | The drafting contract (`extra="forbid"`) | Every contract type in this repo is a Pydantic model; `extra="forbid"` constrains the wire. |
| `sqlalchemy` | 2.0.53 | ORM model + `begin_nested()` SAVEPOINT writes | The repository house style. |
| `alembic` | 1.20.0 | Migration `0006` | The only schema-change mechanism. |
| `rapidfuzz` | 3.14.6 | Advisory lexical band for a drafted answer | Already used by `app/verify/grounding.py:24-53`; confined to `app/verify` (forbidden under `app/domain`). |
| `jinja2` | 3.1.6 | Templates + `_UrlForm`-parsed forms | The rendering surface. |
| `structlog` | 26.1.0 | Per-action logs | The pipeline logging convention. |

### Package Legitimacy Audit

**No packages are installed in this phase.** No `npm view` / `pip index versions` check is required, and no supply-chain gate applies. All code is standard-library + already-pinned dependencies.

## Findings — the eight research questions

### Q1 — The append-only pattern: exact trigger DDL, the `event_repo` contract, and what `application_events` should mirror

**The precedent, read verbatim.** Migration `0001` creates the table and then two raw-DDL triggers:

```sql
CREATE TRIGGER listing_events_no_update BEFORE UPDATE ON listing_events
BEGIN SELECT RAISE(ABORT, 'listing_events is append-only'); END;
CREATE TRIGGER listing_events_no_delete BEFORE DELETE ON listing_events
BEGIN SELECT RAISE(ABORT, 'listing_events is append-only'); END;
```
[VERIFIED: alembic/versions/0001_initial_schema.py:343-350]

There is also an explicitly **named** CHECK constraining the event vocabulary (`ck_listing_events_event_type`) [VERIFIED: models.py:266-272], and an index `ix_listing_events_listing_occurred` on `(listing_id, occurred_at)` [VERIFIED: 0001_initial_schema.py:411-413].

**The repository contract.** `event_repo.append_event` is the only writer and is INSERT-only:

```python
if event_type not in EVENT_TYPES:
    raise ValueError(...)
event = ListingEvent(listing_id=..., event_type=..., occurred_at=now, ...)
async with session.begin_nested():
    session.add(event)
    await session.flush()
return event
```
[VERIFIED: app/db/repositories/event_repo.py:148-185]

Three contract properties to mirror exactly:
1. `now` is supplied by the caller and stored **as-is** — the helper never forges a time [VERIFIED: event_repo.py:157-160, 175-181].
2. The write is wrapped in `session.begin_nested()` (a real SAVEPOINT because the engine issues an explicit `BEGIN`) so a failure cannot poison the caller's outer transaction [VERIFIED: app/db/session.py:45-70, event_repo.py:182-184].
3. The vocabulary is validated **before any SQL**, so an unknown value is a clear `ValueError`, not a raw `IntegrityError` [VERIFIED: event_repo.py:170-173].

**What `application_events` needs.** The table already exists with `id`, `application_id` FK, `from_status` (nullable — the first event), `to_status` (NOT NULL), `occurred_at` (NOT NULL), `note` [VERIFIED: models.py:486-494; 0001_initial_schema.py:286-296]. It has **no triggers and no CHECK** today. Migration `0006` must add the two triggers, verbatim in shape:

```sql
CREATE TRIGGER application_events_no_update BEFORE UPDATE ON application_events
BEGIN SELECT RAISE(ABORT, 'application_events is append-only'); END;
CREATE TRIGGER application_events_no_delete BEFORE DELETE ON application_events
BEGIN SELECT RAISE(ABORT, 'application_events is append-only'); END;
```

**Do NOT add a CHECK on `to_status`/`from_status`.** Adding a CHECK to an existing SQLite table requires a full table recreation (`batch_alter_table`), and `application_events` is a child of `applications` — the exact FK/batch hazard `test_upgrade_populated_0001_to_head` exists to catch [VERIFIED: tests/conftest.py:71-81, tests/db/test_migration_contract.py:583-600]. Instead, validate the status vocabulary in the repository against a Python constant that mirrors `ck_applications_status` (the `event_repo.EVENT_TYPES` pattern), and leave the table shape untouched. (`applications.status` already carries the CHECK [VERIFIED: models.py:478-482].)

**The reset interaction — read carefully, it does not break.** The guarded reset in `app/api/settings.py` suspends exactly one trigger before it deletes:

```python
_APPEND_ONLY_TRIGGER = "listing_events_no_delete"
```
[VERIFIED: app/api/settings.py:591; `_suspend_append_only_trigger` 594-612; `_restore...` 615-627]

`applications` is a **blocking** table — the reset refuses (409) while it holds any row:

```python
RESET_BLOCKING_TABLES: tuple[str, ...] = ("applications",)
```
[VERIFIED: app/api/settings.py:173; enforced at 674-688]

Because `application_events.application_id` is NOT NULL with an FK to `applications.id`, an `application_events` row cannot exist without an `applications` row — so a reset that proceeds has **zero** application events to delete and never needs to suspend the new triggers. The existing fixture contract is therefore safe **as long as `applications` stays in `RESET_BLOCKING_TABLES`**. Two latent hazards to record:
- If the planner ever moves `applications` into `RESET_DELETE_ORDER`, it **must** extend `_suspend_append_only_trigger` to also drop/re-create `application_events_no_delete` and add a re-arm test, exactly as `tests/api/test_settings_reset.py:369-397` does for `listing_events`.
- The new `screening_drafts` table **is** a child of `listings` and must be declared. `test_every_listing_child_is_deleted_or_declared` enumerates children from live metadata and fails otherwise [VERIFIED: tests/db/test_reset_coverage.py:27-36]. Since drafts are regenerable, add `screening_drafts` to `RESET_DELETE_ORDER` **before `listings`** (and the delete-order test requires child-before-parent [VERIFIED: test_reset_coverage.py:66-78]).

**Recommended repository shape** — `app/db/repositories/application_repo.py`:

```python
#: Mirrors `ck_applications_status` (migration 0001) exactly.
APPLICATION_STATUSES: tuple[str, ...] = (
    "discovered", "queued", "shortlisted", "applied",
    "interviewing", "offer", "rejected", "withdrawn",
)

async def append_event(session, *, application_id, from_status, to_status, note, now):
    if to_status not in APPLICATION_STATUSES:
        raise ValueError(...)
    event = ApplicationEvent(application_id=int(application_id), from_status=from_status,
                             to_status=to_status, occurred_at=now, note=note)
    async with session.begin_nested():
        session.add(event); await session.flush()
    return event
```

**Rejected alternative:** deriving `applications.status` from the event log alone (no status column). D-131 locks "current value on the row, history in the event table"; the `status` column is NOT NULL with a CHECK, so relaxing it is a migration. The row+log split is also the ARCHITECTURE pattern the phase is meant to implement [VERIFIED: .planning/research/ARCHITECTURE.md:1158-1162].

---

### Q2 — Grounding the drafted screening answers: the deterministic check

**The hard requirement.** D-125: answers are grounded in stored `CvFacts` + listing text only, each answer carries the evidence it used, and an unsupported claim **surfaces a warning** (not a block). `.planning/CONVENTIONS.md` governance applies because this compares model-produced free text against structured project data (the scope clause names "anything added later"): anchor structurally, fail closed visibly, no false guarantees.

**Chosen approach — two independent signals, one home.**

1. **Structural grounding of the cited evidence ids (the primary, byte-exact check).** The drafting contract makes the model return `evidence_ids` per answer; the checker intersects them with `iter_fact_ids(facts)` **byte-exact** — the exact rule `rank.py` uses for requirement evidence [VERIFIED: app/pipeline/rank.py:384-398] and `_validate_patch` uses for patch ops [VERIFIED: app/domain/cv.py:659-700]. An unknown id is dropped and the answer is flagged. This is the "anchor structurally" half.
2. **Novel-number containment (the fabrication-of-metrics detector).** Tokenise the answer's digit cores with `app/verify/numbers.digit_cores` [VERIFIED: app/verify/numbers.py:102-106] and subtract the digit cores of the source corpus (the CV-facts text built by `_cv_facts_text` [VERIFIED: app/pipeline/rank.py:149-168] plus the listing text). A residual core means the answer states a number that appears nowhere in the grounded sources → `unsupported=True` + a visible warning naming the token. This is exactly the class of check `app/verify/numbers.py` already implements for the compiled PDF's `metric_containment`; reusing `digit_cores` gives one tokeniser and its documented `50k`→`50` trade-off [VERIFIED: numbers.py:69-106].
3. **Optional advisory lexical band, mirroring `band_for`.** If a soft "how well does the answer overlap its cited evidence" label is wanted, reuse `app/verify/grounding.band_for`'s `fuzz.token_set_ratio` shape [VERIFIED: app/verify/grounding.py:33-53]. It must stay **advisory only** and never flip the warning state — the same D-70/A1 rule that governs the CV check. Because it imports `rapidfuzz`, this module must live in `app/verify/` (the import-discipline test forbids `rapidfuzz`-adjacent I/O and the package docstring records the `app/domain` rule) [VERIFIED: app/verify/__init__.py:1-8, tests/test_import_discipline.py:14-16].

**Where it lives.** A new pure module `app/verify/screening.py` exposing something like `ground_screening_answers(facts, listing_text, response) -> list[ScreeningVerdict]`, where each verdict carries `{question, answer, grounded_evidence_ids, unsupported, warnings}`. It imports `app.domain.cv.iter_fact_ids`, `app.domain.tex.normalise_for_compare`/`squash`, and `app.verify.numbers.digit_cores` — all already-pure code.

**Why NOT reuse `facts_present_in`.** `facts_present_in` asks "is EVERY enumerable fact present in the extracted text?" [VERIFIED: app/domain/tex.py:146-174]. That is the correct direction for a full-document render (CV-03), and the **wrong** direction for a single short answer: an answer that legitimately cites one bullet would fail because it does not contain every fact. Reusing it would false-fail essentially every answer — the dangerous false-positive direction CONVENTIONS rule 7 warns about. Use `squash`/`normalise_for_compare` as the normalisation *substrate* (they already fold PDF/pypdf artefacts and Unicode [VERIFIED: tex.py:110-134]), not the `facts_present_in` predicate.

**Residual shapes, stated honestly (CONVENTIONS rule 6 — no false guarantees):**
- **False positive:** an answer that legitimately computes a number not literally in the sources (e.g. "three roles", "5 years" where the source says `5 yrs` → digit core `5` is present, so fine; but "4 years" derived from two date ranges would be flagged). The check is deliberately conservative: a flagged metric is a warning the user reads, never a block.
- **False negative:** fabricated *prose* with no novel digit (e.g. "led a team of engineers" absent from the CV) passes the numeric check. The structural `evidence_ids` grounding catches invented *citations*, not invented *narrative*. This residual cannot be closed by a deterministic check without a fuzzy classifier, which D-70 forbids as load-bearing; it is mitigated by the copy-to-clipboard-only posture (D-127) and must be stated as a runtime-visible warning policy, never asserted as a guarantee in a docstring.

**Test shape (no LLM):** construct a `ScreeningDraftResponse` fixture with (a) a fully grounded answer, (b) an answer with an unknown evidence id, (c) an answer containing a fabricated metric digit, (d) an answer that is a legitimate paraphrase containing a known digit — and assert (a)/(d) pass clean, (b)/(c) warn with the offending id/token named. This is the CONVENTIONS rule-3/rule-4 pair: the literal repro plus the failure-class mutation.

---

### Q3 — The `applied` gate and artefact-linkage integrity

**The gate (attach time).** `cv_artifact_repo.read_for_download(session, artifact_id, ok_only=True)` applies `compile_status == "ok"` **in SQL**, so a blocked/failed row is unreachable even by id [VERIFIED: app/db/repositories/cv_artifact_repo.py:180-194]. The transition to `applied` must call exactly this and refuse when it returns `None`:

```python
record = await cv_artifact_repo.read_for_download(session, artifact_id, ok_only=True)
if record is None:
    return None  # typed refusal; write nothing
```

This is D-118/D-129's contract, and the phase-6 SUMMARY records it explicitly: "`read_for_download` mirrors `latest_for_listing`: the `compile_status='ok'` predicate is applied IN SQL, so a blocked or failed artifact is unreachable even by id — the D-118 contract Phase 7's attach path consumes" [VERIFIED: .planning/phases/06-*/06-CONTEXT.md:70 cites D-118; code at cv_artifact_repo.py:180-194].

**Enforce in the repository, not a DB trigger.** D-118 says the control lives at the repository layer (ARCHITECTURE L943: "Enforced in the repository layer") [VERIFIED: .planning/research/ARCHITECTURE.md:940-943]. A FK alone cannot check `compile_status`; a `BEFORE INSERT/UPDATE` trigger on `applications` that queries `cv_artifacts.compile_status` would be stronger but is inconsistent with the locked D-118 decision and adds migration surface. Recommend repository-layer enforcement plus a test.

**The subtle second rule — display must NOT filter on `ok`.** The ok-only predicate is an **attach-time access control**; it must never gate the *historical* read. If the tracker joined `cv_artifacts` with `compile_status='ok'`, then an artefact that later became blocked (or a future re-verification path) would make the exact CV the user sent vanish from the tracker — directly breaking APPLY-04 ("the exact CV version that was sent"). So:
- **Attach-time:** `read_for_download(..., ok_only=True)` — refuse a non-`ok` id.
- **Display-time:** read the linked artefact **by id, unfiltered**, and render its id (and, if its status is not `ok`, an honest note). A stored link is an immutable historical fact.

**Name the failure mode:** *a stored application→artefact link that is silently dropped or hidden because the artefact's status changed.* The pin test: insert an `ok` artefact, create the application through the gated repository, then insert a *blocked* artefact row and assert (i) the repository refuses to attach it, and (ii) the tracker read still returns the original link and renders its id. Note there is currently **no update path** for `cv_artifacts` (each compile inserts a new row [VERIFIED: cv_artifact_repo.py:1-28, 104-160]), so status cannot actually flip today — the test defends the read contract against a future re-verification path, which is why it must exist now.

**The `applied_at` stamp (D-130).** The transition sets `applied_at = now`; the route never reads a timestamp from the form — mirroring `event_repo`'s "occurred_at is server-side" rule [VERIFIED: event_repo.py:157-160] and the events route's comment that a supplied time "cannot be forged" [VERIFIED: app/api/events.py:18-20].

---

### Q4 — Needs-action query design and indexing

**Schema facts.** `applications.next_action_at` is a nullable `DateTime` [VERIFIED: models.py:472]; the only index on `applications` is the implicit PK — there is no index on `status` or `next_action_at` [VERIFIED: 0001_initial_schema.py:267-284; confirmed no `op.create_index` for `applications` in 0001].

**The ordering.** "Overdue first, then upcoming" with correct NULL handling is:

```sql
SELECT ... FROM applications
ORDER BY (next_action_at IS NULL), next_action_at ASC
```

In SQLite `next_action_at IS NULL` yields `0` for a non-null value (sorts first) and `1` for null (sorts last), so all dated rows come before undated rows, and dated rows are ascending by date (oldest/overdue first). `overdue = next_action_at < :now` is a derived render flag (computed in Python at read time, never stored). The repository returns a frozen record with `next_action_at`, `is_overdue`, and the tracker template branches on the flag.

**The index question.** At 1–5 users the tracker holds tens of rows; a full scan is acceptable and matches the precedent set for the rolling-24h ranking cap ("`llm_calls.created_at` is NOT indexed, so this is a full table scan. That is accepted deliberately at this row count … do **not** add an index migration" [VERIFIED: app/db/repositories/llm_call_repo.py:236-240]). **Recommendation: no index migration.** Document the ceiling with a `ponytail:` comment naming the upgrade path (an index on `applications(next_action_at)` if the tracker ever grows). This keeps migration `0006` to exactly the new table + two triggers.

**Free-text search (D-133/UI-04).** The tracker's searchable fields are `listings.title`, `companies.name`, and `applications.notes`. `listings_fts` indexes `title, company_norm, description` but **not** `applications.notes` [VERIFIED: 0001_initial_schema.py:355-360], and the queue's `LIKE '%term%'` is forbidden for the corpus-scale queue. For the tiny tracker, the simplest correct approach is a bounded scan joined to `listings`/`companies` and a Python-side casefold filter over company/title/notes — mirroring the already-accepted "score ordering is a Python-side sort over a bounded scan" decision [VERIFIED: .planning/STATE.md:123]. Document the bound and the ceiling.

**Stage filter.** `status = :stage` validated against `APPLICATION_STATUSES` before SQL (the allow-list pattern), so an unknown stage is a `ValueError`, not an empty result.

---

### Q5 — Settings surface: the question list, the drafting switch, and the `test_config.py` scans

**What `tests/test_config.py` actually enforces.** Three controls, and a new Settings field must respect all of them:
1. **Surface:** `REQUIRED_SETTINGS_FIELDS` asserts the field exists on `Settings` [VERIFIED: tests/test_config.py:32-90, 215-218].
2. **`LIMIT_FIELDS`:** every entry must also be in `REQUIRED_SETTINGS_FIELDS` **and** have a numeric (non-bool) default — `test_every_limit_field_is_a_required_numeric_ceiling` [VERIFIED: tests/test_config.py:366-375]. A boolean or a list may **not** enter `LIMIT_FIELDS`.
3. **Absence scan:** `SCANNED_DIRS = ("app/probe", "app/pipeline", "app/latex", "app/cv", "app/verify")` — any distinctive integer literal from `LIMIT_FIELDS` found in those trees fails [VERIFIED: tests/test_config.py:209, 553-594]. `_distinctive_thresholds()` reads `getattr(Settings(), field)` and only collects `isinstance(default, int)` [VERIFIED: test_config.py:553-559], so a list/str field is harmlessly skipped.

**Required new keys:**

| Key | Type | Default | Guard tier | Rationale |
|-----|------|---------|-----------|-----------|
| `apply_drafting_enabled` | `bool` | `True` | `REQUIRED_SETTINGS_FIELDS` only — **not** `LIMIT_FIELDS` | The operator off switch, exactly mirroring `tailoring_enabled` [VERIFIED: app/config.py:199-207; test_config.py:355-363]. Must never enter `LIMIT_FIELDS` (boolean fails the numeric-ceiling assertion). |

**Do NOT add a new numeric ceiling.** D-119 shares the rolling-24h budget and the Phase-6 precedent is explicit: "There is deliberately NO per-run tailoring ceiling and NO new numeric ceiling (O1) … the rolling-24h `ranking_max_calls_per_day` value is shared" [VERIFIED: app/config.py:199-206]. The drafting call reuses that value via `calls_since`. If a question-count cap is later wanted to bound output size, it would be a numeric field joining **both** `REQUIRED_SETTINGS_FIELDS` and `LIMIT_FIELDS` — but it is not needed for v1 and adds scan surface.

**The question LIST — represent it as a user-editable DB document, not a `Settings` field.** This is the one place the CONTEXT's shorthand ("a user-defined list in Settings") and the repo's mechanics pull apart, and it is worth being precise:
- `Settings` is environment-driven (`BaseSettings`, `.env`, `extra="ignore"`) [VERIFIED: app/config.py:30-38]. A `list[str]` field is technically representable (pydantic-settings JSON-parses complex types) and would satisfy the surface scan, but it **cannot be edited from the `/settings` page** and would require an env edit + restart — contradicting D-124's "user-defined" and D-133's "view and manage".
- The established precedent for a user-editable list on the `/settings` page is **DB-backed**, not a config field: the ranking weights are edited on `/settings` but persisted in the `ranking_config` single-row table [VERIFIED: app/api/settings.py:291-329; models.py:111-137], and the CV layout preference is persisted as a file beside `cv.yaml` [VERIFIED: app/api/settings.py:488-539].
- **Recommendation:** persist the screening question list as a new DB document mirroring `ranking_config`. Two acceptable shapes: (a) a single-row `apply_config(id=1, questions_json, updated_at)` with a `ck_apply_config_singleton` CHECK (copy the `ck_ranking_config_singleton` pattern [VERIFIED: models.py:135-137]), or (b) an ordered row table `screening_questions(id, position, text, created_at)` mirroring `filter_rules` [VERIFIED: models.py:68-94]. Shape (b) avoids adding a JSON column to the `test_no_pii_columns.py` allow-list; shape (a) is fewer moving parts. Either is defensible; the planner should pick one and justify it.
- The default question list is a code-level constant (a seed), so a fresh install is usable with no config. The `/settings` page gains an editor for it (plain full-page POST, like the weights card).

**The one new `Settings` key is therefore only the off switch** (`apply_drafting_enabled`). Add it to `REQUIRED_SETTINGS_FIELDS` with a comment, add a `test_the_apply_switch_is_not_a_ceiling`-style assertion (mirroring `test_the_tailoring_switch_is_not_a_ceiling` [VERIFIED: test_config.py:355-363]), and a `test_apply_drafting_enabled_is_environment_tunable` test.

---

### Q6 — The drafting LLM call through `complete_structured`

**The call shape.** One `complete_structured` call per drafting request, returning all answers in one response — mirroring D-86's "one call, one listing" fairness/cost control [VERIFIED: app/pipeline/rank.py:1-8] and `tailor_listing`'s "exactly ONE call" contract [VERIFIED: app/pipeline/tailor.py:190-281]. The contract type is a Pydantic model with `extra="forbid"` (the repo-wide rule for contract types [VERIFIED: app/domain/cv.py:75-83; app/llm/base.py:28-40]):

```python
class ScreeningAnswer(_Forbid):
    question: str
    answer: str
    evidence_ids: list[str] = Field(default_factory=list)

class ScreeningDraftResponse(_Forbid):
    answers: list[ScreeningAnswer] = Field(default_factory=list)
```

Lives in `app/domain/schemas/screening.py` (pure; pydantic only), beside `probe.py`/`ranking.py`.

**The call.** Mirror `tailor_listing` line-for-line [VERIFIED: app/pipeline/tailor.py:242-281]:
- `system` is a frozen module constant with **no interpolation** — the trust boundary; listing text and CV facts travel only in `parts` [VERIFIED: tailor.py:111-138, 175-187]. Reuse `_cv_facts_text` and the listing-text builder [VERIFIED: app/pipeline/rank.py:149-168, 178-201] and add a fourth part carrying the question list.
- `tools=()` and `model=settings.opencode_model` [VERIFIED: tailor.py:244-251].
- Wrap the call; a raised transport error is a **value**, recorded as one `llm_calls` row with the exception **class name only** [VERIFIED: tailor.py:262-275].
- Commit the read-only preamble (`calls_since`) **before** the network call, or SQLite raises `SQLITE_BUSY_SNAPSHOT` [VERIFIED: tailor.py:233-240].
- Reserve through the ranking stage's shared lock: `_reserve(day_total, 0, cap_day=cap_day, cap_run=_CAP_RUN_UNBOUNDED)` and release in `finally` [VERIFIED: app/pipeline/tailor.py:219-231, 276-277; `_reserve`/`_release` at rank.py:446-464].
- Refusal writes one `budget_exceeded` row and returns `None` (never raises) [VERIFIED: tailor.py:219-231; `BUDGET_EXCEEDED_MARKER` at llm_call_repo.py:49].

**The `llm_calls.purpose` value — reuse `"tailor"`.** The vocabulary is frozen by `ck_llm_calls_purpose IN ('rank','narrate','tailor','extract','probe')` [VERIFIED: alembic/versions/0001_initial_schema.py:314-317; app/db/repositories/llm_call_repo.py:41]. Adding a new purpose (e.g. `"draft"`) requires a CHECK change → `batch_alter_table` recreation of `llm_calls`, which has an FK to `runs` and is seeded by the populated-upgrade fixture [VERIFIED: tests/conftest.py:136-140]. That is real migration risk for zero phase value. Reuse `purpose="tailor"`, documented as "apply-drafting is tailoring-adjacent and shares the 24h budget". **Flag the trade-off:** `llm_calls` has no stage column, so drafting spend is indistinguishable from CV-tailoring spend in the ledger audit (PITFALLS P4's "attribute spend by stage" is slightly weakened). If per-stage attribution later matters, widen the CHECK in a dedicated migration with the populated-upgrade test extended.

**Test faking.** The drafting call is exercised with a scripted stub backend injected through the existing dependency override, exactly as `TailoringStubBackend` does [VERIFIED: tests/api/test_tailoring_generate.py:54-84; `OfflineLLMBackend` at tests/conftest.py:33-54]. The stub returns a fixed `ScreeningDraftResponse`; the route is hit through `client`; assertions read the persisted `screening_drafts` rows and the `llm_calls` row. No network, no opencode, no key.

---

### Q7 — Migration mechanics for `0006`

**Shape.** A new `alembic/versions/0006_screening_drafts.py` following `0005_cv_drafts.py` [VERIFIED: alembic/versions/0005_cv_drafts.py:1-63]:

```python
revision = "0006"
down_revision = "0005"

def upgrade() -> None:
    op.create_table(
        "screening_drafts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("listing_id", sa.Integer, sa.ForeignKey("listings.id"), nullable=False),
        sa.Column("question_text", sa.Text, nullable=False),
        sa.Column("answer_text", sa.Text),
        sa.Column("evidence_json", sa.JSON),
        sa.Column("unsupported", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.execute("CREATE TRIGGER application_events_no_update BEFORE UPDATE ON application_events "
               "BEGIN SELECT RAISE(ABORT, 'application_events is append-only'); END;")
    op.execute("CREATE TRIGGER application_events_no_delete BEFORE DELETE ON application_events "
               "BEGIN SELECT RAISE(ABORT, 'application_events is append-only'); END;")

def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS application_events_no_delete")
    op.execute("DROP TRIGGER IF EXISTS application_events_no_update")
    op.drop_table("screening_drafts")
```

**Triggers need nothing beyond `op.execute`.** Raw DDL is the established tool for triggers and FTS in this repo [VERIFIED: 0001_initial_schema.py:343-380]. `CREATE TRIGGER` does **not** recreate the target table, so no batch mode is needed. Mirror 0001's symmetric `DROP TRIGGER IF EXISTS` in `downgrade` [VERIFIED: 0001_initial_schema.py:421-426].

**Every pinned head must be updated in the same change:**
- `tests/db/test_migration_contract.py:295` — `assert versions == ["0005"]` → `["0006"]`.
- `tests/db/test_migration_contract.py:306` — `assert head_lines[0].startswith("0005")` → `"0006"`.
- `tests/db/test_migration_contract.py:606` — the populated-upgrade test's `assert versions == ["0005"]` → `["0006"]`.
- `tests/db/test_skeleton_boot.py:78` — `assert version == [("0005",)]` → `[("0006",)]`.
- Add a new contract item (item 17) asserting the `screening_drafts` table + `application_events` triggers exist and that the triggers abort UPDATE/DELETE (mirror `test_listing_events_append_only` [VERIFIED: test_migration_contract.py:132-154]).

**Three more guards fire on a new table, and all must be satisfied:**
1. `tests/db/test_orm_drift.py` — the ORM (`app/db/models.py`) and the migrated schema must agree on the table set and per-table column names [VERIFIED: test_orm_drift.py:60-104]. So add a matching ORM model.
2. `tests/db/test_no_pii_columns.py` — the new table's JSON column (`evidence_json`) must be added to `EXPECTED_JSON_COLUMNS` with a justification comment [VERIFIED: test_no_pii_columns.py:30-77, 112-137]. (`applications`/`application_events` are already listed with empty frozensets [VERIFIED: test_no_pii_columns.py:73-74].)
3. `tests/db/test_reset_coverage.py` — `screening_drafts` is a child of `listings` and must appear in `RESET_DELETE_ORDER` (derived/regenerable) before `listings` [VERIFIED: test_reset_coverage.py:27-36, 66-78; app/api/settings.py:142-156].

---

### Q8 — Anti-patterns to avoid (PITFALLS L247, L255, L286, L776)

- **PITFALLS L247 — "`applications` with a status column but no `application_events` history."** [VERIFIED: .planning/research/PITFALLS.md:247] This is the exact anti-pattern D-131 exists to prevent: every status transition must append exactly one `application_events` row **in the same transaction** as the status update. Do not update `applications.status` without appending the event; do not append the event separately (a crash between the two would strand the history).
- **PITFALLS L255 — "Never overwrite state that has analytic value — status transitions append to `application_events`, they do not just update a column."** [VERIFIED: PITFALLS.md:255] Concretely: do not add a computed "response rate" or "days in stage" value to the `applications` row; derive any such view from the event log at read time. `notes` and `next_action_at` are ordinary mutable columns (D-135) — they carry no analytic history; status does.
- **PITFALLS L286 — the `next_action_at` nudge.** [VERIFIED: PITFALLS.md:286] "Add a follow-up nudge (`next_action_at = applied_at + N days`) so the tracker becomes a reason to return, not just a record." Research question 5/Q4 handles the surface; note the phase must at minimum let the user set it and surface overdue items first (D-133). Whether a default `+ N days` is auto-suggested is a product choice within the user's discretion — if implemented, `N` is a numeric Settings ceiling and joins both guards, or it is simply left to the user to type.
- **PITFALLS L776 — the P8 verification checklist.** [VERIFIED: PITFALLS.md:776] "Verify `applications.cv_artifact_id` is set, `application_events` is append-only, and `next_action_at` is computed." These three become the phase's acceptance backbone, each with a test (see Validation Architecture).

**Additional anti-patterns this phase must avoid (from the same corpus and the locked decisions):**
- Never create a submit route; never POST to a portal; never auto-fill (APPLY-02, D-127, FEATURES DF-12 "drafts an answer you can preview, then insert, copy, or cancel" [VERIFIED: .planning/research/FEATURES.md:73]).
- Never auto-insert a drafted answer into a portal or a form (D-127).
- Never render a preview/HTML fragment built in Python with `|safe` where untrusted text could reach it — the repo's one escaping choke point is Jinja autoescape; `_tailoring_review.html` is a Jinja template precisely to avoid a Python-built HTML string [VERIFIED: .planning/STATE.md:150; app/api/tailoring.py:317-340 builds strings but escapes each interpolation with `html.escape`].
- Never let the tracker's read filter the linked artefact on `compile_status='ok'` (see Q3).

## Architecture Patterns

### System architecture (data flow)

```
                    ┌──────────────────────────────────────────────┐
   /listings/{id}   │ listing_detail.html                          │
   (existing page)──┼──► link "Apply package" ──► /listings/{id}/apply
                    └──────────────────────────────────────────────┘
                                   │
             GET /listings/{id}/apply  (NO LLM — D-122)
                                   ▼
        ┌───────────────────────────────────────────────────────────┐
        │ apply package assembler (route reads stored data only)    │
        │  • cv_artifact_repo.latest_for_listing(ok_only=True)      │
        │  • listing.apply_url                                      │
        │  • score_repo.read_score_for_listing().requirements       │
        │  • screening_draft_repo.read_for_listing()                │
        └───────────────┬───────────────────────────┬───────────────┘
                        │                           │
      POST .../apply/draft (explicit action)   copy-to-clipboard only (D-127)
                        ▼                           ▲
        ┌───────────────────────────────┐           │
        │ pipeline/draft.py             │           │
        │  one complete_structured call │           │
        │  purpose="tailor" + reserve   │           │
        └───────┬───────────────┬───────┘           │
                ▼               ▼                   │
        llm_calls ledger   app/verify/screening.py  │
        (audit + cap)      ground ids + digit cores │
                                │                   │
                                ▼                   │
                     screening_drafts table ────────┘

   POST /applications/{listing_id}/stage  (guided transition)
        │
        ▼
   application_repo.transition_application()
        │  if to_status == "applied": require read_for_download(ok_only=True)
        ├─ UPDATE applications (status, applied_at, cv_artifact_id, next_action_at, notes)
        └─ INSERT application_events (from_status, to_status, occurred_at, note)   ← same transaction
                                │
                                ▼
   /applications tracker ── table: stage filter + needs-action (overdue first) + search
                          └─ inline history partial (HTMX): from → to, timestamp, note
```

### Recommended project structure (additions only)

```
app/
├── api/
│   ├── apply.py                 # /listings/{id}/apply page + draft action (mirrors tailoring.py)
│   └── applications.py          # /applications tracker + stage transition + history partial
├── db/
│   ├── models.py                # add ScreeningDraft (and ApplicationEvent triggers note)
│   └── repositories/
│       ├── application_repo.py  # applications + application_events (Q1/Q3)
│       └── screening_draft_repo.py  # screening_drafts (Q7)
├── domain/
│   └── schemas/screening.py     # ScreeningAnswer / ScreeningDraftResponse (pure)
├── pipeline/
│   └── draft.py                 # draft_screening_answers() one-call stage (Q6)
└── verify/
    └── screening.py             # ground_screening_answers() (Q2, CONVENTIONS-governed)
alembic/versions/0006_screening_drafts.py
app/web/templates/html/
├── apply.html                   # package page
├── _screening_drafts.html       # drafts partial
├── applications.html            # tracker shell
├── _application_rows.html       # tracker table body (fragment)
└── _application_history.html    # inline timeline (fragment)
```

### Pattern 1 — Page + action + fragment (mirror `tailoring.py`)

**What:** one page route that precomputes all state, POST actions returning HTML fragments that swap in place, refusal fragments carrying `data-error`.
**When to use:** the apply page's draft action and the tracker's stage transition + history expansion.
**Example:** the tailoring page/generate/compile routes and `_error_fragment` [VERIFIED: app/api/tailoring.py:253-259, 390-443, 446-534]. Note the `base.html` `htmx:beforeSwap` hook forces non-2xx HTML bodies to swap, so a refusal fragment lands where the user is looking [VERIFIED: app/web/templates/html/base.html:47-55].

### Pattern 2 — Current state on the row, history appended in the same transaction

**What:** `applications.status` is the current value; exactly one `application_events` row is appended each transition, both inside the caller's single commit.
**When to use:** every status transition (D-131).
**Example:** the `listing_events` projection documents the same split ("current state lives on the row, history in the event table") [VERIFIED: app/db/repositories/event_repo.py:8-13; ARCHITECTURE.md:1158-1162].

### Pattern 3 — One call, typed contract, audit row, reserve-then-call

**What:** one `complete_structured` per drafting request, `extra="forbid"` contract, one `llm_calls` row per attempt, shared 24h cap.
**Example:** `tailor_listing` [VERIFIED: app/pipeline/tailor.py:190-281].

### Anti-patterns to avoid

- **A status column with no event history** (PITFALLS L247).
- **Storing a derived analytic value on `applications`** instead of deriving it from events (PITFALLS L255).
- **Applying `ok`-only at display time** on the artefact link (breaks APPLY-04; see Q3).
- **Python-built HTML for untrusted answers** — use a Jinja template so autoescape is the one choke point.
- **Adding a new `llm_calls.purpose`** — batch-recreation risk for no phase value (Q6).
- **Adding an index/`LIKE` for the tracker** — a bounded Python scan is the accepted pattern at this scale (Q4).
- **Making the drafting call on page open** (D-122 forbids it; the page is a stored-data read).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Append-only enforcement | A Python convention or a repository-only rule | SQLite `BEFORE UPDATE/DELETE` triggers, as in 0001 | A convention is bypassable by any future writer; the trigger is the invariant (mirrors `listing_events`). |
| The event writer | A second INSERT path | `event_repo.append_event`'s exact contract in a sibling `append_event` | SAVEPOINT + allow-list + call-supplied clock; one shape, no drift. |
| ok-only artefact selection | A new query filtering `compile_status` in Python | `cv_artifact_repo.read_for_download(ok_only=True)` | The predicate is already in SQL and is the D-118 access control. |
| Grounding a cited fact id | A fuzzy match or casefold compare | Byte-exact `iter_fact_ids` intersection (`rank.py`/`_validate_patch` shape) | Ids are the ASCII slug identity; fuzzy matching on a block is a false-positive machine (D-70). |
| Novel-number detection | A new number tokeniser | `app/verify/numbers.digit_cores` | One tokeniser, one documented `50k`→`50` trade-off, already tested. |
| Normalisation for text compare | New `.lower().strip()` | `app/domain/tex.normalise_for_compare` / `squash` | Already folds PDF/pypdf artefacts, ligatures and Unicode; D-70 rules. |
| Form parsing | `request.form()` / `python-multipart` | `read_form(...)` (`_UrlForm` with `getlist`) | The project deliberately has no multipart dependency [VERIFIED: app/api/searches.py:79-127]. |
| The applied-gate test | A mock of the repository | A real migrated temp DB (the `client`/`session_factory` fixtures) and a real blocked row | Mocks of the thing under test were the Phase-6 lesson. |

## Common Pitfalls

### Pitfall 1 — Updating `status` without appending the event (or in two transactions)

**What goes wrong:** the tracker shows a stage with no history entry, or a crash between the update and the insert leaves them inconsistent.
**Why it happens:** the update is the obvious write; the event feels like bookkeeping.
**How to avoid:** one repository function per transition that performs both writes and leaves the single commit to the route; the `application_events` triggers only prevent *edit/delete*, not a *missing* insert, so the repository is the only guard.
**Warning signs:** an `applications` row whose `status` has no matching latest `application_events.to_status`.

### Pitfall 2 — The tracker's link read filters on `ok`

**What goes wrong:** an application's "exact CV sent" disappears from the tracker if the artefact stops being `ok`.
**Why it happens:** reusing `read_for_download(ok_only=True)` for the display read.
**How to avoid:** attach-time ok-only; display-time by-id unfiltered (Q3).
**Warning signs:** a tracker row with a null CV link where `applications.cv_artifact_id` is non-null.

### Pitfall 3 — A new table silently breaks the reset guards

**What goes wrong:** the test suite fails on `test_reset_coverage` (listings child undeclared), `test_orm_drift` (ORM/migration disagree), or `test_no_pii_columns` (unlisted JSON column).
**Why it happens:** a migration was written without updating the guard tests that enumerate live metadata.
**How to avoid:** the Q7 checklist — model + migration + `RESET_DELETE_ORDER` + JSON allow-list + pinned-head constants, all in the same change.
**Warning signs:** a green new-table test file but a red suite.

### Pitfall 4 — `applied_at`/`occurred_at` read from the form

**What goes wrong:** a client can forge the time an application was recorded.
**Why it happens:** the form carries a date input for `next_action_at`, and it is easy to read the wrong field.
**How to avoid:** `applied_at` and `occurred_at` are always `datetime.now(UTC)` server-side (D-130; the events route's rule); only `next_action_at` is user-supplied, and it is validated as a date.
**Warning signs:** a transition endpoint whose handler accepts a `now`/`applied_at` form field.

### Pitfall 5 — Grounding check false-fails a legitimate answer

**What goes wrong:** every answer warns because the check demands the answer contain every fact (the `facts_present_in` shape) or because a computed number is flagged.
**Why it happens:** reusing a completeness predicate for a containment question.
**How to avoid:** use `iter_fact_ids` intersection + digit-core containment; keep any lexical band advisory; treat a warning as a prompt to review, not a block. Test the valid-input direction (CONVENTIONS rule 7).

### Pitfall 6 — A new template class with no CSS rule

**What goes wrong:** `tests/test_stylesheet_coverage.py` fails because every literal `class="..."` token must appear as a selector in `static/vendor/app.css` (or be listed in `EXEMPT_CLASSES` with a reason).
**Why it happens:** new templates introduce new class names.
**How to avoid:** reuse existing queue/tailoring classes where possible; add a stylesheet rule or an `EXEMPT_CLASSES` entry when a new hook is needed [VERIFIED: tests/test_stylesheet_coverage.py:33-55].

### Pitfall 7 — A new route without the auth seam

**What goes wrong:** `tests/test_auth_seam.py` fails; PLAT-03 is violated.
**How to avoid:** every new route declares `user: User = Depends(current_user)`, and (recommended) the new paths join `EXPECTED_SEAM_ROUTES` [VERIFIED: tests/test_auth_seam.py:28-49].

## Code Examples

### The append-only trigger (verbatim from migration 0001, to copy for `application_events`)
```python
op.execute(
    "CREATE TRIGGER listing_events_no_update BEFORE UPDATE ON listing_events "
    "BEGIN SELECT RAISE(ABORT, 'listing_events is append-only'); END;"
)
op.execute(
    "CREATE TRIGGER listing_events_no_delete BEFORE DELETE ON listing_events "
    "BEGIN SELECT RAISE(ABORT, 'listing_events is append-only'); END;"
)
```
[VERIFIED: alembic/versions/0001_initial_schema.py:343-350]

### The INSERT-only writer contract (to mirror in `application_repo.append_event`)
```python
if event_type not in EVENT_TYPES:
    raise ValueError(
        f"unknown event_type {event_type!r}; expected one of {list(EVENT_TYPES)}"
    )
event = ListingEvent(listing_id=int(listing_id), event_type=event_type,
                     occurred_at=now, context_json=..., run_id=run_id)
async with session.begin_nested():
    session.add(event)
    await session.flush()
return event
```
[VERIFIED: app/db/repositories/event_repo.py:170-185]

### The ok-only access control (the `applied` gate)
```python
statement = select(CvArtifact).where(CvArtifact.id == int(artifact_id))
if ok_only:
    statement = statement.where(CvArtifact.compile_status == "ok")
row = await session.scalar(statement)
return _to_record(row) if row is not None else None
```
[VERIFIED: app/db/repositories/cv_artifact_repo.py:190-194]

### The frozen status vocabulary (mirror in the repository)
```python
CheckConstraint(
    "status IN ('discovered','queued','shortlisted','applied',"
    "'interviewing','offer','rejected','withdrawn')",
    name="ck_applications_status",
)
```
[VERIFIED: app/db/models.py:478-482; identical DDL at alembic/versions/0001_initial_schema.py:279-283]

### DIGIT-core tokenisation (reuse for novel-number containment)
```python
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")

def digit_cores(text: str) -> list[str]:
    if not text:
        return []
    return [_normalise_core(match.group(0)) for match in _NUMBER_RE.finditer(text)]
```
[VERIFIED: app/verify/numbers.py:59, 102-106]

### Replace-all-drafts atomically (mirror for `screening_draft_repo`)
```python
async with session.begin_nested():
    await session.execute(delete(CvDraft).where(CvDraft.listing_id == listing_id))
    row = CvDraft(listing_id=listing_id, ..., created_at=moment)
    session.add(row)
    await session.flush()
return _to_record(row)
```
[VERIFIED: app/db/repositories/cv_draft_repo.py:81-95]

### Needs-action ordering (SQLite NULL-last idiom)
```sql
SELECT ... FROM applications
ORDER BY (next_action_at IS NULL), next_action_at ASC
```

## State of the Art

| Old approach | Current approach in this repo | When changed | Impact |
|--------------|-------------------------------|--------------|--------|
| A `status` column with no history | Current state on the row + an append-only event table (trigger-enforced) | migration 0001 for `listing_events`; Phase 7 for `application_events` | Response-rate analytics later are trustworthy (PITFALLS L255). |
| The LLM writes free text that ships | Typed contract with `extra="forbid"`; free text grounded/checked, warnings surfaced | Phase 4/6 (CV), Phase 7 (screening) | Fabrication becomes structurally hard and auditable. |
| A generated CV discarded on reload | A persisted live draft per listing (migration 0005) | 2026-09-28 | The reload-persistence precedent Phase 7 mirrors for drafts. |
| A React SPA for a CRUD queue | Jinja2 + HTMX + Alpine, server-rendered fragments | Phase 1–6 | New surfaces reuse the page + fragment pattern; no build step. |

**Deprecated/outdated:** none introduced by this phase. The phase intentionally does **not** touch `ck_llm_calls_purpose`, `cv_artifacts.compile_status`, or `ck_applications_status`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The screening question list should be persisted as a user-editable DB document (mirroring `ranking_config`) rather than a `Settings` field, because `Settings` is env-static and cannot be edited from `/settings`. | Q5 | If the user specifically wants a static env-configured list, the editor UI is unnecessary — but D-124/D-133 ("user-defined", "manage") read as runtime-editable. Planner should confirm the persistence shape. |
| A2 | Reusing `purpose="tailor"` for the drafting `llm_calls` row is acceptable (no separate stage attribution). | Q6 | If per-stage cost attribution matters, a dedicated `"draft"` purpose needs a batch-recreation migration of `llm_calls`. |
| A3 | `applications` is one-per-listing (no unique constraint exists, and none is proposed). | Q4 | If a user can legitimately apply twice to one listing, the tracker and transition keying need a second key. No requirement states multi-apply. |
| A4 | The tracker is small enough that a bounded Python scan for search/needs-action is acceptable (no index, no FTS). | Q4 | At a few hundred applications, an index on `applications(next_action_at)` may be warranted. |
| A5 | No default `next_action_at = applied_at + N days` is auto-set unless the user types one. | Q8 | PITFALLS L286 suggests a nudge is desirable; whether it is automatic is a product choice within discretion. |

**If this table is not empty:** the planner should confirm A1 (question-list persistence shape) and A2 (llm_calls purpose) with a checkpoint or a recorded decision, since both are cheap to get wrong and expensive to change.

## Open Questions (RESOLVED)

1. **Question-list persistence shape (row table vs single-row JSON doc).**
   - What we know: it must be user-editable from `/settings`; `ranking_config` and `filter_rules` are the two precedents.
   - What's unclear: whether the planner prefers one document or ordered rows.
   - Recommendation: pick ordered rows (`screening_questions(id, position, text, created_at)`) to avoid adding to the JSON allow-list, or the singleton doc for fewer parts. Either is acceptable; record the choice.
   - **RESOLVED (planner, 2026-09-30):** the **singleton `apply_config` document** (`id=1`, `questions_json`, `updated_at`, `ck_apply_config_singleton`) mirroring `ranking_config`, created in migration 0006 with a code-level `DEFAULT_QUESTIONS` seed when no row exists. Fewer moving parts than ordered rows; the one `questions_json` entry is added to `EXPECTED_JSON_COLUMNS` with a justification comment. Built in 07-05 Task 1.

2. **Whether a question-count/length ceiling is wanted.**
   - What we know: D-119 says no new numeric ceiling; the drafting call reuses the shared 24h cap.
   - What's unclear: whether an oversized question list could produce an oversized response.
   - Recommendation: no new ceiling in v1; the `max_tokens`-style bound (if any) rides the model call, not a new Settings field.
   - **RESOLVED (planner, 2026-09-30):** **no new ceiling.** 07-03 introduces only the boolean `apply_drafting_enabled` off switch (surface-guarded, never in `LIMIT_FIELDS`); the shared rolling-24h `ranking_max_calls_per_day` is reused.

3. **Whether to extend `EXPECTED_SEAM_ROUTES` with the new paths.**
   - What we know: new routes must carry the seam; the test enumerates routes explicitly for non-vacuity.
   - Recommendation: add the apply page, the draft action, the tracker page, and the stage transition to `EXPECTED_SEAM_ROUTES`.
   - **RESOLVED (planner, 2026-09-30):** yes — every new route joins `EXPECTED_SEAM_ROUTES`: the tracker page/list/record/history/status (07-01), the apply page (07-02), and the draft/question/delete actions (07-05).

## Environment Availability

Step 2.6: **SKIPPED (no new external dependencies).** The phase runs in the existing Python/Docker stack; the drafting call goes through the already-wired opencode backend (or the offline stub in tests). No new binary, service, or package is required.

## Validation Architecture

> `workflow.nyquist_validation` is explicitly `true` in `.planning/config.json`.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest==9.1.1` + `pytest-asyncio==1.4.0` (`asyncio_mode = "auto"`) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `pythonpath = ["."]`) |
| Quick run command | `pytest tests/db/test_application_repo.py tests/verify/test_screening.py -x` |
| Full suite command | `pytest` (default lane is `-m 'not live and not latex'` [VERIFIED: pyproject.toml `addopts`]) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| APPLY-01 | Apply page renders ok artefact, apply link, stored gaps, stored drafts; no LLM on open | API | `pytest tests/api/test_apply_package.py -x` | ❌ Wave 0 |
| APPLY-01 | Page shows "tailor first" when no `ok` artefact | API | same file | ❌ Wave 0 |
| APPLY-02 | No submit route exists; no outbound POST form to a portal | Static/API | `pytest tests/api/test_apply_package.py::test_no_submit_surface -x` | ❌ Wave 0 |
| APPLY-03 | Record application with stage + notes | Repository + API | `pytest tests/db/test_application_repo.py tests/api/test_applications_tracker.py -x` | ❌ Wave 0 |
| APPLY-04 | `applied` transition refuses a non-`ok` artefact; stores `cv_artifact_id`; display read does not filter on `ok` | Repository | `pytest tests/db/test_application_repo.py::test_applied_requires_ok_artifact -x` | ❌ Wave 0 |
| APPLY-05 | Every status change appends exactly one event in the same transaction; triggers abort UPDATE/DELETE | Repository + migration | `pytest tests/db/test_application_events.py tests/db/test_migration_contract.py -x` | ❌ Wave 0 |
| APPLY-06 | Set/clear `next_action_at`; needs-action view orders overdue first then upcoming, nulls last | Repository + API | `pytest tests/db/test_application_repo.py::test_needs_action_ordering -x` | ❌ Wave 0 |
| UI-04 | Tracker table renders; stage filter, needs-action view, search; inline history partial | API | `pytest tests/api/test_applications_tracker.py -x` | ❌ Wave 0 |
| D-125 | Drafted answers grounded; unknown evidence id warns; fabricated metric digit warns; valid paraphrase passes | Unit (pure) | `pytest tests/verify/test_screening.py -x` | ❌ Wave 0 |
| D-126/Q7 | Migration 0006 creates `screening_drafts` + triggers; head pinned | Migration | `pytest tests/db/test_migration_contract.py tests/db/test_orm_drift.py tests/db/test_no_pii_columns.py tests/db/test_reset_coverage.py -x` | ✅ exists (extend) |
| D-119/Q6 | Drafting call writes one `llm_calls` row; refuses at cap before the call; transport error is a value | Unit/pipeline | `pytest tests/pipeline/test_draft_stage.py -x` | ❌ Wave 0 |
| PLAT-03 | Every new route carries the auth seam | Static | `pytest tests/test_auth_seam.py -x` | ✅ exists (extend) |
| UI guard | Every new template class has a CSS rule | Static | `pytest tests/test_stylesheet_coverage.py -x` | ✅ exists (extend) |

### Sampling Rate
- **Per task commit:** the narrow file(s) for the changed unit, `-x`.
- **Per wave merge:** `pytest` (default hermetic lane).
- **Phase gate:** full default lane green before `/gsd-verify-work`; the `latex` lane is container-only and not required for this phase (no LaTeX work is added).

### Wave 0 Gaps

- [ ] `tests/db/test_application_repo.py` — insert, transition, applied gate, needs-action ordering, tracker read.
- [ ] `tests/db/test_application_events.py` — append-only: exactly one event per transition, same transaction; direct UPDATE/DELETE abort (mirror `test_listing_events.py:124-163`).
- [ ] `tests/db/test_screening_draft_repo.py` — replace-all per listing in one SAVEPOINT; unknown listing; empty list clears.
- [ ] `tests/verify/test_screening.py` — grounding: grounded passes; unknown id warns; fabricated digit warns; valid paraphrase passes; property test mutating other entities' identifiers (CONVENTIONS rule 4).
- [ ] `tests/pipeline/test_draft_stage.py` — stub backend; one call; one `llm_calls` row; cap refusal before the call; transport error records the class name only.
- [ ] `tests/api/test_apply_package.py` — page states (ok/gated/no-artefact); draft action persists rows; no LLM on GET; no submit surface.
- [ ] `tests/api/test_applications_tracker.py` — tracker table, stage filter, needs-action order, search, inline history partial, stage transition refusals.
- [ ] `tests/db/test_migration_contract.py` — new item 17 for `screening_drafts` + `application_events` triggers; head → `0006`.
- [ ] Extend `tests/db/test_orm_drift.py` (automatic once the ORM model exists), `tests/db/test_no_pii_columns.py` (JSON allow-list), `tests/db/test_reset_coverage.py` (via `RESET_DELETE_ORDER`), `tests/db/test_skeleton_boot.py` (head), `tests/test_auth_seam.py`, `tests/test_config.py` (new switch).

## Security Domain

> `security_enforcement` is absent = enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No (v1 has none) | The `current_user` seam is the forward-compatible placeholder [VERIFIED: app/api/deps.py:1-22]. |
| V3 Session Management | No | No sessions in v1. |
| V4 Access Control | Yes | The ok-only artefact predicate is the artefact-access control (D-118); the auth seam is on every route. |
| V5 Input Validation | Yes | Validate status against `APPLICATION_STATUSES`; validate `next_action_at` as a date; parse forms via `read_form`; never trust a form clock. |
| V6 Cryptography | No | No new cryptography; hashing is unchanged. |
| — CSRF | Deferred | `app/api/settings.py:12-16` records that the reset becomes a CSRF hole once session auth lands; the same applies to new POST routes and must be revisited with Authentik [VERIFIED: app/api/settings.py:11-16]. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection in listing text → invented screening answers | Tampering | Untrusted text travels only in `parts`; `system` is a frozen constant; the output is grounded and warned (D-125). |
| Forged `applied_at`/`occurred_at` | Spoofing | Server-side clock only (D-130); the form never supplies it. |
| Attaching a blocked CV | Tampering | `read_for_download(ok_only=True)` in SQL (D-118). |
| Untrusted answer text reaching the DOM | XSS | Jinja autoescape is the one choke point; no `|safe` on untrusted values. |
| Editing/deleting history | Tampering | Database triggers `RAISE(ABORT)` on UPDATE/DELETE. |
| A submit/auto-fill path appearing | Elevation / legal | No such route exists; the phase's tests assert the absence (APPLY-02). |
| PII landing in a new JSON column | Info disclosure | `test_no_pii_columns.py` allow-list; the draft table's JSON holds fact ids only. |

## Sources

### Primary (HIGH confidence — read from this repository this session)
- `app/db/models.py` — `Application` (L462-483), `ApplicationEvent` (L486-494), `ListingEvent` (L254-272), `CvArtifact` (L399-431), `CvDraft` (L434-459), `RankingConfig` (L111-137).
- `alembic/versions/0001_initial_schema.py` — `applications`/`application_events` DDL (L267-296), append-only triggers (L343-350), `llm_calls` CHECKs (L314-321).
- `alembic/versions/0005_cv_drafts.py` — the migration shape to follow.
- `app/db/repositories/event_repo.py` — the append-only contract (L1-322).
- `app/db/repositories/cv_artifact_repo.py` — ok-only selection (L163-194).
- `app/db/repositories/cv_draft_repo.py` — the replace-all SAVEPOINT write (L65-95).
- `app/db/repositories/llm_call_repo.py` — `PURPOSES` (L41), `calls_since` (L221-250).
- `app/db/session.py` — PRAGMAs + transactional DDL (L23-70).
- `app/api/settings.py` — `RESET_DELETE_ORDER` (L142-156), `RESET_BLOCKING_TABLES` (L173), trigger suspend/restore (L589-627).
- `app/api/tailoring.py` — the page/action/fragment pattern (L253-685).
- `app/api/events.py` — the row-swap + server-clock pattern (L102-207).
- `app/api/listings.py` — the detail page pattern (L75-140).
- `app/api/searches.py` — `_UrlForm` / `read_form` (L79-127).
- `app/pipeline/rank.py` — `_cv_facts_text` (L149-168), reserve/release (L446-464), RANK-05 grounding (L384-398).
- `app/pipeline/tailor.py` — the one-call stage (L190-281).
- `app/domain/cv.py` — `iter_fact_ids` (L308-323), `extra="forbid"` contract rule (L75-83).
- `app/domain/tex.py` — `normalise_for_compare` (L110-122), `squash` (L125-134), `facts_present_in` (L146-174).
- `app/verify/numbers.py` — `digit_cores` (L102-106).
- `app/verify/grounding.py` — `band_for`/`evidence_text_for` (L33-69).
- `app/config.py` — `tailoring_enabled` (L207), ceilings (L188-217).
- `app/llm/base.py` — `complete_structured` (L113-138).
- `tests/conftest.py` — fixtures + `OfflineLLMBackend` (L33-290).
- `tests/db/test_migration_contract.py` — pinned head (L295-311), append-only test (L132-154).
- `tests/db/test_orm_drift.py`, `tests/db/test_no_pii_columns.py`, `tests/db/test_reset_coverage.py`, `tests/db/test_skeleton_boot.py`, `tests/test_config.py`, `tests/test_auth_seam.py`, `tests/test_stylesheet_coverage.py`, `tests/api/test_settings_reset.py`, `tests/api/test_tailoring_generate.py`.
- `.planning/phases/07-assisted-apply-tracker/07-CONTEXT.md` — locked decisions.
- `.planning/research/ARCHITECTURE.md` — C14 (L108), the package flow (L320-333), the `applications` sketch (L945-956), append-only pattern (L1158-1162).
- `.planning/research/PITFALLS.md` — L247, L255, L286, L776.
- `.planning/research/FEATURES.md` — DF-12 (L73), L245, L255.
- `.planning/CONVENTIONS.md` — the verification-check rules.

### Secondary (MEDIUM confidence)
- `.planning/STATE.md` — Phase-6 decision notes (the D-118 attach-path contract, the Jinja-not-Python-fragment rule).

### Tertiary (LOW confidence)
- The question-list persistence recommendation (A1) and the `llm_calls` purpose reuse (A2) are reasoned from precedent, not from an explicit decision; both are flagged in the Assumptions Log.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; every dependency is already pinned and read.
- Architecture: HIGH — every pattern (append-only triggers, SAVEPOINT repositories, page+fragment routes, ok-only selection) is present in the tree and cited.
- Pitfalls: HIGH — anchored to PITFALLS L247/L255/L286/L776 and to the guard tests that will fail if the migration is incomplete.

**Research date:** 2026-09-30
**Valid until:** 2026-10-30 (stable; the schema and patterns change only by migration).
