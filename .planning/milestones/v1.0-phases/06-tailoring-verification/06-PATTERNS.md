# Phase 6: Tailoring + Verification - Pattern Map

**Mapped:** 2026-09-24
**Files analyzed:** 22 (13 new, 9 modified)
**Analogs found:** 13 / 13 new-or-extended source files · 9 / 9 test files

> Every analog below was confirmed **git-tracked** with `git ls-files -- <path>`
> (all non-empty). No gitignored mirror path is named. All Phase 6 target files
> were confirmed **absent on disk**, so this phase is greenfield plus surgical
> extension of existing modules — not a refactor.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/domain/cv.py` (MODIFY) | domain model | transform (pure) | self — `BulletWeight`/`DropBullet`/`apply_patch` stub | exact (extend) |
| `app/pipeline/tailor.py` | service/pipeline | request-response + LLM | `app/pipeline/rank.py` | exact |
| `app/verify/base.py` | domain contract | transform (pure) | `app/latex/base.py` + `app/llm/base.py` | role-match |
| `app/verify/plan_checks.py` | validator (pure) | transform | `app/domain/tex.py` (`facts_present_in`) | role-match |
| `app/verify/text_checks.py` | validator (pure) | transform | `app/domain/tex.py` (`normalise_for_compare`) | role-match |
| `app/verify/numbers.py` | utility (pure) | transform | `app/domain/sanitize.py` (regex catalogue) | partial |
| `app/verify/grounding.py` | utility (pure) | transform (similarity) | `app/domain/dedup.py` (`fuzz`) | role-match |
| `app/verify/__init__.py` | package barrel | — | `app/domain/schemas/__init__.py` | role-match |
| `app/db/repositories/cv_artifact_repo.py` | repository | CRUD | `app/db/repositories/cv_repo.py` + `score_repo.py` | exact |
| `app/db/repositories/llm_call_repo.py` (MODIFY) | repository | CRUD | self — `rank_calls_since` | exact (extend) |
| `app/api/tailoring.py` | controller/route | request-response | `app/api/listings.py` + `app/api/events.py` | exact |
| `app/web/templates/html/tailoring.html` | view | render | `listing_detail.html` | role-match |
| `app/web/templates/html/_tailoring_review.html` | view fragment | render | `_detail_actions.html` | role-match |
| `app/web/templates/html/_cv_findings.html` | view fragment | render | `_detail_actions.html` | role-match |
| `app/config.py` (MODIFY) | config | — | Phase-5 ranking block (L172-191) | exact |
| `app/main.py` (MODIFY) | config/wiring | — | existing `include_router` block (L58-64) | exact |
| `tests/test_config.py` (MODIFY) | test | — | `PHASE_FIVE_CEILINGS` guards | exact |
| `tests/domain/test_patch_ops.py` | test | — | `tests/domain/test_cv_ids.py:185-225` | exact (replace) |
| `tests/verify/` (`fixtures.py` + 4 test files) | test | — | `tests/pipeline/test_rank_stage.py` + `tests/fixtures/cv/*` | role-match |
| `tests/api/test_cv_artifact_blocked.py` | test | — | `tests/db/test_cv_repo.py` + `tests/api/test_listing_detail.py` | role-match |
| `tests/api/test_cv_pdf_route.py` | test | — | `tests/api/test_listing_detail.py` | role-match |
| `tests/api/test_tailoring_generate.py` / `_review.py` | test | — | `tests/api/test_listing_detail.py` + `StubBackend` in `tests/pipeline/test_rank_stage.py` | role-match |
| `tests/verify/test_no_free_text_path.py` | test | — | `tests/golden/test_render_bytes.py` + `tests/latex/test_fact_equivalence.py` | role-match |

---

## Pattern Assignments

### `app/domain/cv.py` (domain model, pure transform) — MODIFY

**Analog:** itself. The stub, the grounding set, the change-log type and the ID walker already exist; Phase 6 replaces only the `apply_patch` body and adds the op types.

**The `_Forbid` base every contract type inherits** (L71-79):
```python
class _Forbid(BaseModel):
    """Every contract type forbids extras. ... on these models extra="forbid"
    is also a correctness control: a typo'd key ... must fail."""
    model_config = ConfigDict(extra="forbid")
```

**The two ops that EXIST today without an `op` tag** (L386-397) — add the tag:
```python
class BulletWeight(_Forbid):
    """Re-weight a bullet within its entry."""
    bullet_id: str
    weight: Annotated[float, Field(ge=0.0, le=2.0)]

class DropBullet(_Forbid):
    """Drop a bullet. The reason is REQUIRED so a structural drop is loud."""
    bullet_id: str
    reason: str
```

**`Suggestion` already exists — reuse verbatim, do NOT follow §7.3's `list[dict]`** (L400-409):
```python
class Suggestion(_Forbid):
    """A human-approved suggestion. NEVER applied to a render."""
    bullet_id: str
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str
```

**The grounding set the real `apply_patch` validates against** (L306-321):
```python
def iter_fact_ids(facts: CvFacts) -> Iterator[str]:
    """Every ID in the document, in a deterministic order."""
    for section in facts.sections:
        yield section.id
        for entry in section.entries:
            yield entry.id
            for bullet in entry.bullets:
                yield bullet.id
        for skill in section.skills:
            yield skill.id
    ...
```

**The change-log type `RenderPlan.changes` already carries** (L338-343):
```python
class ChangeRecord(_Forbid):
    """One entry in the change log the render plan carries (ARCHITECTURE §7.4)."""
    op: str
    target_id: str
    detail: str = ""
```

**The stub to replace + the already-correct unknown-id guard** (L420-492):
```python
def _referenced_ids(op: object) -> list[str]:
    """Every fact ID an operation names, whatever its shape."""
    ids: list[str] = []
    for attribute in ("bullet_id", "section_id", "entry_id", "org_id", "title_id"):
        value = getattr(op, attribute, None)
        if isinstance(value, str):
            ids.append(value)
    evidence_ids = getattr(op, "evidence_ids", None)
    ...
    return ids

def apply_patch(facts: CvFacts, ops: Iterable[object] = ()) -> RenderPlan:
    ...
    for op in operations:
        for referenced in _referenced_ids(op):
            if referenced not in known_ids:
                raise UnknownIdError(...)          # KEEP this loop
    for op in operations:
        raise UnsupportedPatchOp(...)               # REPLACE this loop
    return _identity_plan(facts)
```

**`_identity_plan` (L433-462) is the base-order projection to extend**, and `__all__` (L495-524) must drop `UnsupportedPatchOp`, add the new op types + `facts_hash` + `InvalidPatchError`.

**Pattern notes:**
- New signature `apply_patch(facts, patch: TailoringPatch | None = None)`; `patch=None` must still return the identity plan — three existing callers rely on it (`tests/latex/test_fact_equivalence.py:141`, `tests/golden/test_render_bytes.py:34`, `tests/cv/test_factstore.py:181`).
- `facts_hash` is a pure function in this module; `hashlib` is stdlib so the purity contract (`tests/test_import_discipline.py` scans `app/domain`) is preserved.
- `reason` must be non-empty: use `Field(min_length=1)` (D-106 forbids an empty reason satisfying a drop).

---

### `app/pipeline/tailor.py` (service, request-response + LLM) — NEW

**Analog:** `app/pipeline/rank.py` — the closest match in the tree: one structured call, reserve-then-call spend lock, fact-store load, skip-reason vocabulary, frozen system prompt, grounding loop.

**Import block / module shape** (`rank.py` L42-70):
```python
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.cv.factstore import CvFactStoreError, load_facts
from app.db.repositories import llm_call_repo, score_repo
from app.domain.cv import CvFacts, iter_fact_ids
from app.llm import get_llm_backend
from app.llm.base import LLMBackend

log = structlog.get_logger(__name__)
CV_FILENAME = "cv.yaml"
```

**Skip-reason vocabulary pattern to mirror** (`rank.py` L86-112) — the tailoring `tailoring_disabled` / `fact_store_absent` / `no_score` guards should mint a matching closed vocabulary so the UI strip cannot drift:
```python
RANK_SKIP_DISABLED = "ranking_disabled"
RANK_SKIP_FACT_STORE = "fact_store_absent"
...
def ranking_skip_reason() -> str | None:
    if not settings.ranking_enabled:
        return RANK_SKIP_DISABLED
    try:
        load_facts(Path(settings.cv_dir) / CV_FILENAME)
    except (CvFactStoreError, OSError):
        return RANK_SKIP_FACT_STORE
    return None
```

**The one-call shape to copy verbatim** (`rank.py` L247-284):
```python
async def rank_listing(backend, session, *, listing, facts, run_id, criteria_version, now):
    weights = await ranking_config_repo.read_weights(session)
    parts = build_ranking_parts(facts, listing, weights)
    result = await backend.complete_structured(
        schema=RankingResponse,
        system=RANK_SYSTEM_PROMPT,
        parts=parts,
        model=settings.opencode_model,
        tools=(),
        retries=settings.opencode_max_retries,
    )
    await llm_call_repo.record_llm_call(
        session, purpose="rank", status=result.status,
        result=result, run_id=run_id, now=now,
    )
    if not result.ok or not isinstance(result.data, RankingResponse):
        return None
    ...
```
Tailoring mirrors this with `schema=TailoringPatch`, `system=TAILOR_SYSTEM_PROMPT`, `purpose="tailor"`, `run_id=None`.

**The pure `parts` builders to mirror** (`rank.py` L147-225) — `_cv_facts_text` renders ids so they can be cited; `_listing_text` labels the listing untrusted; `build_ranking_parts` returns a `list[str]`:
```python
def build_ranking_parts(facts, listing, weights) -> list[str]:
    return [
        _cv_facts_text(facts),
        _listing_text(listing),
        _rubric_text(weights, include_compensation=_listing_has_salary(listing)),
    ]
```
`build_tailoring_parts(facts, listing, score)` follows this exactly, adding the **stored** requirement list from the `scores` row (D-110 — never re-extract).

**Frozen system prompt rule** (`rank.py` L114-144) — a plain literal, no f-string, no `%`. Pinned by `tests/pipeline/test_rank_stage.py::test_the_system_prompt_is_a_frozen_constant_with_no_interpolation` (L139-148); mirror that test for `TAILOR_SYSTEM_PROMPT`.

**The reserve-then-call lock to reuse/hosit** (`rank.py` L334-379) — note `_reserve`/`_release` are module-private:
```python
_reserve_lock = asyncio.Lock()
_in_flight = 0

def _cap_hit(day_total, run_total, *, cap_day, cap_run) -> str | None:
    if run_total + _in_flight >= cap_run:
        return "per_run"
    if day_total + _in_flight >= cap_day:
        return "per_day"
    return None

async def _reserve(day_total, run_total, *, cap_day, cap_run) -> bool: ...
async def _release() -> None: ...
```
**Pitfall (RESEARCH O1):** `rank_calls_since` filters `purpose == "rank"` (`llm_call_repo.py:239`), so reusing it verbatim lets tailoring escape the 24h cap. Tailoring has no `run_id`; drop the per-run ceiling and use a purpose-aware 24h read (see `llm_call_repo` modify below).

**The failure-is-a-value / isolated-failure shape** (`rank.py` L473-499) — a per-call `try/except Exception` with `_release()` in `finally`.

---

### `app/verify/base.py` (domain contract, pure) — NEW

**Analogs:** `app/latex/base.py` (`CompileResult`, L18-42) and `app/llm/base.py` (`StructuredCallResult`, L59-99). Both establish the result-value contract `CheckResult`/`VerificationResult` must follow.

**Result-value contract pattern** (`app/latex/base.py` L18-42):
```python
class CompileResult(BaseModel):
    """The outcome of one compile — a value, never an exception.

    `extra="forbid"` is the redaction control ... a future contributor cannot
    quietly attach the TeX body or a raw PDF byte string and have it persisted
    against a CV artefact row.
    """
    model_config = ConfigDict(extra="forbid")

    ok: bool
    engine: str
    pdf_path: str | None = None
    ...
    error: str | None = None
    error_kind: str | None = None
```

**Mirror for the verifier** (RESEARCH Q1/§Pattern 1): `CheckResult(id, status: Literal["pass","warn","fail"], detail, offending)` and `VerificationResult(passed, checks, findings, extracted_text_hash, page_count, verifier_version)`, both `ConfigDict(extra="forbid")`. `VERIFIER_VERSION = "1.0.0"` lives here, copied into the result and persisted (§10.2). Import **nothing** from `app/domain` except `CvFacts`/`RenderPlan` types as needed — this package may import `rapidfuzz` (unlike `app/domain`), so it must **not** live under `app/domain` (`tests/test_import_discipline.py` scans it, L65-83).

---

### `app/verify/plan_checks.py` (Layer 1, pure) — NEW

**Analog:** `app/domain/tex.py` — the strict-membership predicate and its non-vacuity companion.

**The predicate shape to mirror** (`tex.py` L137-174):
```python
def facts_compared(facts: CvFacts) -> int:
    """How many facts :func:`facts_present_in` compares ...
    The caller asserts a non-vacuous floor against this (D-72)."""
    return sum(3 + len(entry.bullets) for entry in facts.all_entries())


def facts_present_in(facts: CvFacts, extracted_text: str) -> tuple[bool, list[str]]:
    """Strict membership ... Membership is exact after normalisation.
    A fuzzy similarity ratio is never a substitute."""
    squashed = squash(extracted_text)
    ...
    return (not missing), missing
```

**Pitfall (PITFALLS P2):** do **not** call `facts_present_in` for Layer 2 bullet-presence — it iterates `facts.all_entries()` and requires every bullet, so a declared drop false-fails. The verifier iterates the **`RenderPlan`'s** surviving bullets instead. Layer 1 checks (id containment, bullet conservation both directions, temporal consistency, requirement→evidence integrity) are pure predicates over `(facts, plan, patch)`; mirror the `(bool, list)` / value-not-exception shape.

---

### `app/verify/text_checks.py` (Layer 2, pure) — NEW

**Analog:** `app/domain/tex.py` normaliser pair (L110-134):
```python
def normalise_for_compare(text: str) -> str:
    """Fold extraction artefacts to a comparable form (D-70), *preserving* spaces."""
    value = unicodedata.normalize("NFKC", text)
    for old, new in _CHAR_FOLDS:
        value = value.replace(old, new)
    value = _DE_HYPHENATE_RE.sub("", value)
    value = _WHITESPACE_RE.sub(" ", value)
    return value.strip()


def squash(text: str) -> str:
    """The whitespace-INSENSITIVE canonical form, for shingle membership only."""
    return _SQUASH_RE.sub("", normalise_for_compare(text).casefold())
```

**Injection-residue check (check 7) reuses the ONE pattern list** — `app/domain/sanitize.py` L83-95:
```python
INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"disregard\s+(all\s+)?above",
        ...
    )
)
```
Never mint a second pattern list (RESEARCH "Don't Hand-Roll"). Check 7: `pattern.search(normalise_for_compare(text))` over `INJECTION_PATTERNS`.

---

### `app/verify/numbers.py` (pure utility) — NEW

**Analog:** `app/domain/sanitize.py` regex-catalogue idiom (L83-95) and `app/domain/tex.py` fold tables (L85-107). No direct metric-token analog exists; this is the closest *style* match — a pure, total, module-level compiled-regex catalogue with no I/O, no clock.

**Pattern notes:** digit-core tokeniser + date-like-number detector, region segmentation by resolved `org` positions in `squash(text)`. Pure and total; no NLP. Exclude lone-integer-lines ≤ `page_count` (Pitfall 3).

---

### `app/verify/grounding.py` (pure utility, similarity) — NEW

**Analog:** `app/domain/dedup.py` — the only existing `rapidfuzz` consumer.

**Pattern to mirror** (`dedup.py` L37, L148-150, L182, L200):
```python
from rapidfuzz import fuzz
...
fuzz.token_sort_ratio(company_a, company_b)
...
score = fuzz.token_sort_ratio(...)
```
RESEARCH Q4 specifies `fuzz.token_set_ratio` over `normalise_for_compare`d requirement/evidence text, with thresholds from `Settings`. **The band is advisory only** — the hard fail (check 6) is structural: a non-`gap` `GapFinding` with no resolvable `evidence_id`. Mirror dedup's written-down rule that a fuzzy ratio sits on the advisory side only (`dedup.py` L16, L41, L109): a fuzzy ratio must never be load-bearing on a block decision.

---

### `app/db/repositories/cv_artifact_repo.py` (repository, CRUD) — NEW

**Analogs:** `app/db/repositories/cv_repo.py` (house rules, frozen record, SAVEPOINT write) and `score_repo.py` (newest-row ordering, tolerant reads).

**House rules to repeat in the module docstring** (`cv_repo.py` L3-18):
```python
"""... House rules, as everywhere in `app/db/repositories/`:

* repositories are the **only** place SQL lives;
* they take an `AsyncSession` explicitly and **never commit** — the caller owns
  the single commit;
* the write is wrapped in a SAVEPOINT (`session.begin_nested()`) so a failure
  here cannot poison the caller's outer transaction;
* the clock is injectable so a caller (or a test) can pin it.
"""
```

**Frozen read record + single mapping** (`cv_repo.py` L37-47, L119-129):
```python
@dataclass(frozen=True)
class CvVersionRecord:
    id: int
    label: str | None
    ...
    is_current: bool


def _to_record(row: CvVersion) -> CvVersionRecord:
    """One ORM row as its frozen read value — the single mapping, so the write and
    the read cannot disagree about a field."""
    return CvVersionRecord(...)
```

**The SAVEPOINT insert** (`cv_repo.py` L91-98):
```python
async with session.begin_nested():
    session.add(row)
    await session.flush()
```

**The newest-row read rule to copy for `latest_for_listing`** (`score_repo.py` L278-295):
```python
row = (await session.execute(
    select(Score)
    .where(Score.listing_id.in_(ids))
    .order_by(Score.listing_id, Score.run_id.desc(), Score.id.desc())
)).scalars().all()
...
def read_score_for_listing(...):
    row = (await session.execute(
        select(Score)
        .where(Score.listing_id == int(listing_id))
        .order_by(Score.run_id.desc(), Score.id.desc())
        .limit(1)
    )).scalar_one_or_none()
    return _to_record(row) if row is not None else None
```
`cv_artifact_repo.latest_for_listing(session, listing_id, *, ok_only=True)` and `read_for_download(session, artifact_id, *, ok_only=True)` must apply the D-118 `compile_status == "ok"` predicate **in SQL** — the repository is the artefact-access control, with route-level refusal as a second layer.

**Model columns to write** (`app/db/models.py` L399-431): `patch_json`, `change_log_json`, `tex_path`/`pdf_path` (nullable — **no migration**), `tex_hash`/`pdf_hash`, `compiled_at`, `compile_status` (CHECK: `ok`/`failed`/`blocked`), `compile_log`, `verification_json`, `page_count`, `ats_checks_json`, `backend`/`provider`/`model`, `created_at`. Never `create_all`; schema only via `alembic upgrade head`.

---

### `app/db/repositories/llm_call_repo.py` (repository) — MODIFY

**Analog:** itself. `rank_calls_since` (L221-241) is the read to generalise per RESEARCH O1/Pitfall 4:
```python
async def rank_calls_since(session: AsyncSession, *, now: datetime | None = None) -> int:
    moment = now if now is not None else datetime.now(UTC)
    cutoff = _naive(moment) - RANK_CALL_WINDOW
    count = await session.scalar(
        select(func.count())
        .select_from(LlmCall)
        .where(LlmCall.purpose == "rank", LlmCall.created_at >= cutoff)
    )
    return int(count or 0)
```
Add `calls_since(session, *, purpose, now)` (or count `("rank","tailor")`) so the tailoring 24h cap actually fires. `PURPOSES` already contains `"tailor"` (L41). Do not add an index (L228-232 explains the deliberate full scan); keep the `_naive` cutoff rule (L216-218).

---

### `app/api/tailoring.py` (controller, request-response) — NEW

**Analogs:** `app/api/listings.py` (page route + `Depends` + 404 fragment) and `app/api/events.py` (POST handler, form parse, allow-listed `surface`, error fragment).

**Router + shared templates pattern** (`listings.py` L52-59):
```python
router = APIRouter()

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "web" / "templates"
templates = make_templates(TEMPLATE_DIR)

DETAIL_TEMPLATE = "html/listing_detail.html"
```

**The universal auth + session seam** (`listings.py` L75-81):
```python
@router.get("/listings/{listing_id}", response_class=HTMLResponse)
async def listing_detail(
    listing_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
```
Every tailoring route (`GET /listings/{id}/cv`, `POST .../generate`, `POST .../compile`, `GET .../cv/pdf`) must declare `user: User = Depends(current_user)` (D-116) and be added to `EXPECTED_SEAM_ROUTES` in `tests/test_auth_seam.py` (L31-44) or the seam guard fails.

**The HTML-fragment error convention** (`listings.py` L67-72):
```python
def _not_found() -> HTMLResponse:
    """A small HTML fragment, not a bare JSON 404 — the events route's convention."""
    return HTMLResponse(
        '<div class="detail-empty" data-error="unknown-listing">Unknown listing.</div>',
        status_code=404,
    )
```
The compile stale-patch refusal returns a fragment with `data-error="stale-patch"` (RESEARCH Q5); the blocked-PDF refusal returns 404/403 (D-118).

**Form parsing without `python-multipart` + allow-listing** (`events.py` L129-144):
```python
form = await read_form(request)
event_type = str(form.get("event_type") or "").strip()
surface = str(form.get("surface") or "").strip()
if surface not in ACTION_SURFACES:
    surface = DEFAULT_SURFACE
```
`read_form` is imported from `app.api.searches` (L120-127) — reuse it; never add `python-multipart`. The hidden `patch_json` is untrusted: re-parse with Pydantic and re-ground server-side (D-109).

**Route ordering note:** `GET /listings/{listing_id}` is registered in `listings.py`; the nested `/listings/{id}/cv/...` routes are more specific and coexist fine, but register the new router in `app/main.py` (see below).

---

### `app/web/templates/html/tailoring.html` (view) — NEW

**Analog:** `app/web/templates/html/listing_detail.html`.

**Structure to copy** (L1-30, L99-100): `{% extends "html/base.html" %}`, a `{% block title %}`, a `{% block content %}`, and the route precomputes every flag so the template does no date arithmetic, settings read or lookup (L7-8). Jinja autoescape is the **only** escaping — nothing is marked `|safe` (L4-5). The page links back to the listing detail.

**Fragment-swap posture** (`_detail_actions.html` L20-27) — the review/compile fragments are their own swap roots:
```html
<section id="detail-actions" aria-live="polite">
  ...
  {% set target_id = "detail-actions" %}
  {% set surface = "detail" %}
  {% include "html/_action_forms.html" %}
</section>
```

---

### `app/web/templates/html/_tailoring_review.html` and `_cv_findings.html` (view fragments) — NEW

**Analog:** `app/web/templates/html/_detail_actions.html` (L1-29). Same contract: a self-contained fragment returned by the POST and embedded by the page, `aria-live="polite"`, no `|safe`, no new class token beyond existing badge/`req-*` classes. The review fragment shows the HTML preview beside the change log with per-item `reason` (D-108); `_cv_findings.html` renders `CheckResult`s (pass/warn/fail) with the warn findings visibly non-blocking (D-114).

---

### `app/config.py` (config) — MODIFY

**Analog:** the Phase-5 ranking block (L172-191):
```python
    # --- Phase 5 ranking spend caps (RANK-08 / D-91 / D-92) --------------------
    ranking_max_calls_per_run: int = 40
    ranking_max_calls_per_day: int = 400
    #: D-94's operator off switch. ... Deliberately NOT in LIMIT_FIELDS ...
    ranking_enabled: bool = True
```
Add a `# --- Phase 6 tailoring (D-119) ---` block with `tailoring_enabled: bool = True`, `tailoring_grounding_threshold: int = 80`, `tailoring_grounding_review_threshold: int = 55` (RESEARCH Q11). Reuse the 24h cap value; do **not** invent a per-run tailoring cap unless O1 is resolved to add one. The existing `artifacts_dir` (L162) is the path root for artifacts.

---

### `app/main.py` (wiring) — MODIFY

**Analog:** the registration block (L58-64):
```python
    app.include_router(web_routes.router)
    app.include_router(run_routes.router)
    ...
    app.include_router(listing_routes.router)
```
Add `from app.api import tailoring as tailoring_routes` and `app.include_router(tailoring_routes.router)`.

---

### `tests/test_config.py` (test) — MODIFY

**Analog:** the Phase-5 guards, exactly.

- `REQUIRED_SETTINGS_FIELDS` (L32-82) — add the three Phase-6 names.
- `LIMIT_FIELDS` (L85-124) — add the two int thresholds; **not** `tailoring_enabled` (boolean, L119-121 explains the asymmetry).
- New `PHASE_SIX_CEILINGS` tuple modeled on `PHASE_FIVE_CEILINGS` (L152-155) + a `test_the_phase_six_ceilings_are_guarded` mirroring L235-250, including the negative `assert "tailoring_enabled" not in LIMIT_FIELDS`.
- An env-tunability test mirroring `test_the_phase_five_ceilings_are_environment_tunable` (L253-266).
- `SCANNED_DIRS` (L184) — add `"app/verify"` (RESEARCH Q11/A7) so a hard-coded similarity threshold is caught by `test_no_distinctive_threshold_literal_remains_in_probe_or_pipeline`. `app/pipeline` already covers `tailor.py`.

---

### `tests/domain/test_patch_ops.py` (test) — NEW (replaces `test_cv_ids.py:185-225`)

**Analog:** the nodes to rewrite, `tests/domain/test_cv_ids.py` L188-225:
```python
def test_apply_patch_with_no_operations_is_an_exact_identity() -> None: ...
def test_each_mutating_operation_raises_rather_than_being_ignored() -> None:
    with pytest.raises(UnsupportedPatchOp):
        apply_patch(facts, [BulletWeight(bullet_id="bul/northwind-labs-2021/1", weight=1.5)])
    ...
def test_an_operation_referencing_an_unknown_id_raises() -> None:
    with pytest.raises(UnknownIdError):
        apply_patch(facts, [BulletWeight(bullet_id="bul/does-not-exist/1", weight=1.0)])
```
Rewrite the middle node as real-op assertions (reweight ordering stable + declaration tie-break, demote after non-demoted, drop, all-or-nothing, cross-entry rejection); keep the identity and unknown-id nodes. **Delete `UnsupportedPatchOp`** from `cv.py` and its `__all__` (Pitfall 1) — a leftover `__all__` entry is the warning sign.

---

### `tests/verify/` (test package) — NEW

**Analogs:** `tests/pipeline/test_rank_stage.py` (fixture authoring + in-memory stub backend) and `tests/fixtures/cv/awesomecv_standin.yaml`.

**Fixture facts source** — `tests/fixtures/cv/awesomecv_standin.yaml` (committed, synthetic; `bul/northwind-labs-2021/1` text `"Reduced p99 latency 40% by rewriting the ingest path"` with `metrics: ["40%", "p99"]`). Load with `load_facts(FIXTURE)` as `test_rank_stage.py` L132-133 does.

**Stub-backend pattern for the endpoint tests** (`test_rank_stage.py` L34-82):
```python
class StubBackend:
    """A fixed structured response that records the calls it received."""
    def __init__(self, response=None, *, fail_marker=None): ...
    async def complete_structured(self, *, schema, system, parts, model=None,
                                   agent=None, tools=(), retries=None):
        text = "\n".join(parts)
        self.calls.append({"system": system, "text": text, "tools": tuple(tools)})
        ...
        return StructuredCallResult(ok=True, status="ok", data=self._response, ...)
```

**Test discipline** (PITFALLS P13): fixtures of `(facts, plan, patch, text, page_count, expected)` with **no LLM, no compiler, no network**; one mutation fixture per hard-fail check; warn-only fixtures assert `status == "warn"` and `passed is True`. The canary test (`test_no_free_text_path.py`) renders a patch whose `reason`/`requirement`/`rationale` are canary strings and asserts they are absent from the `.tex` — this pins §7.3 L713. Compare against `tests/latex/test_fact_equivalence.py` and `tests/golden/test_render_bytes.py` for the render-without-engine default-lane shape.

**Temporal check `now` is injected** so default-lane fixtures stay clock-free.

---

### `tests/api/test_cv_artifact_blocked.py` / `test_cv_pdf_route.py` / `test_tailoring_generate.py` / `test_tailoring_review.py` — NEW

**Analogs:** `tests/api/test_listing_detail.py` (seed helpers, `client` fixture, XSS/escape assertions, 404 fragment assertion) and `tests/db/test_cv_repo.py` (frozen-record + never-commits + guard-can-fail style).

**Seeding a listing/score to satisfy D-110** — mirror `_seed_scored_listing` (`test_listing_detail.py` L118-181) which calls `score_repo.upsert_score(...)` directly. The `client` fixture (`tests/conftest.py` L248-276) already overrides `get_session`, `get_session_factory`, and `get_llm_backend` with `OfflineLLMBackend`, so override the backend per-test for generate.

**P14 failure-path test:** insert a `blocked` `cv_artifacts` row, then assert `GET /listings/{id}/cv/pdf` returns 404/403, `latest_for_listing(ok_only=True)` excludes it, and `read_for_download(ok_only=True)` returns `None`; also assert a `failed` row is excluded. Mirror the negative-assertion style in `test_cv_repo.py::test_the_writer_never_commits_the_callers_transaction` (L105-122).

**Compile endpoint tests** that need the engine: mark `latex` (the default lane runs `-m 'not live and not latex'`) or override `get_latex_engine` with a stub that writes a canned PDF — the DI seam is `app/latex/__init__.py::get_latex_engine` (L12-38), overridable exactly like `get_llm_backend`.

---

## Shared Patterns

### Repository house rules
**Source:** `app/db/repositories/cv_repo.py` L3-18 · `score_repo.py` L1-30 · `llm_call_repo.py` L1-25
**Apply to:** `cv_artifact_repo.py` (new), `llm_call_repo.py` (modify)
Repositories are the only place SQL lives; take `AsyncSession`; **never commit**; wrap writes in `session.begin_nested()`; inject `now`; reads are total (degrade to empty/`None`, never raise).

### Dependency-injection seam + `app.dependency_overrides` in tests
**Source:** `app/llm/__init__.py::get_llm_backend` (L13-20) · `app/latex/__init__.py::get_latex_engine` (L12-38) · `tests/conftest.py` (L268-270)
**Apply to:** any new verifier/artifact seam, and the tailoring route's LLM/engine use.
A function built per request, never a module instance; tests override it.

### Result-value contracts (`extra="forbid"`, never raise)
**Source:** `app/latex/base.py` L18-42 · `app/llm/base.py` L59-99
**Apply to:** `app/verify/base.py`, the `cv_artifact_repo` read records.
A failure is a value, not an exception, at a port/verify boundary. `extra="forbid"` is the redaction control — no field may carry raw PDF text, the TeX body, or listing prose.

### Pure, total, deterministic helpers
**Source:** `app/domain/tex.py` L1-27 · `app/domain/sanitize.py` L59-95 · `app/domain/cv.py` L1-46
**Apply to:** `app/verify/*` (except the deliberate `rapidfuzz` allowance), the new `app/domain/cv.py` additions.
No I/O, no clock, no locale, no `set`/`dict` iteration for ordered output. `app/domain` may import only stdlib + pydantic (`tests/test_import_discipline.py` L65-83) — hence `app/verify/` is its own package.

### Frozen constants for prompts and system text
**Source:** `app/pipeline/rank.py` L114-144 + `tests/pipeline/test_rank_stage.py` L139-148
**Apply to:** `TAILOR_SYSTEM_PROMPT` in `app/pipeline/tailor.py`.
A module-level plain literal, no f-string/`%`/concatenation; listing text and CV prose travel only in `parts`. `tools=()` explicitly.

### Blocking calls behind `asyncio.to_thread`
**Source:** `app/latex/compile.py` L57-85, L214 (`await asyncio.to_thread(_count_pages, pdf_path)`)
**Apply to:** Layer 2's `extract_pdf_text` call in `app/pipeline/tailor.py`.
`pypdf` is synchronous; every event-loop caller reaches it through `asyncio.to_thread` or it stalls the single worker.

### Universal auth seam
**Source:** `app/api/deps.py` L16-22 · `tests/test_auth_seam.py` L31-44, L100-111
**Apply to:** every new route in `app/api/tailoring.py`; add the paths to `EXPECTED_SEAM_ROUTES`.
`user: User = Depends(current_user)` on every route; the flattened-walk test fails a route without it.

### The "no field becomes text in the PDF" guarantee (verbatim, §7.3)
**Source:** `app/domain/cv.py` L86-88 (`Bullet.text` IMMUTABLE) · `app/latex/render.py` (renderer consumes only `RenderPlan`) · `app/latex/env.py` (escape choke point L56-74)
**Apply to:** every new `TailoringPatch` field.
Any new field must be id-, enum-, or UI-only. `reason`/`requirement`/`rationale`/`op`/`weight`/`order` never enter `RenderPlan`. The canary test (`tests/verify/test_no_free_text_path.py`) is the regression gate.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `app/verify/plan_checks.py` | validator | transform | No verifier package exists. Closest *style* analog is `app/domain/tex.py`; the check logic is designed in 06-RESEARCH Q1 and validated by fixtures, not copied. |
| `app/verify/text_checks.py` | validator | transform | Same — no existing PDF-text containment stage. Layer 2 is net-new; reuse only `extract_pdf_text`, `normalise_for_compare`, `squash`, `INJECTION_PATTERNS`. |
| `app/verify/numbers.py` | utility | transform | No metric-tokeniser analog in the tree (RESEARCH Q2 designs it). `app/domain/dedup.py` is the fuzzy analog, not a numeric one. |
| `app/verify/grounding.py` | utility | transform | No similarity-banding helper exists; `rapidfuzz` usage itself is analogous to `dedup.py`. Thresholds are uncalibrated (RESEARCH Q4, LOW–MEDIUM). |
| `app/pipeline/tailor.py` orchestration (generate→compile→verify) | service | request-response | The *stage* shape mirrors `rank.py`, but the two-step generate/compile orchestration and the verify-gate call sequence have no existing analog. Designed in 06-RESEARCH Q9. |

---

## Metadata

**Analog search scope:** `app/domain`, `app/pipeline`, `app/latex`, `app/cv`, `app/db/repositories`, `app/api`, `app/llm`, `app/web/templates/html`, `tests/{domain,pipeline,api,db,latex,golden,cv}`, `tests/fixtures`.
**Files scanned:** 24 read in full or targeted ranges; 13 analog source files + 9 test/fixture files named above.
**Tracked-source gate:** all named analogs verified via `git ls-files -- <path>` (non-empty). All Phase 6 target paths confirmed absent on disk. No gitignored mirror path emitted.
**Pattern extraction date:** 2026-09-24.
