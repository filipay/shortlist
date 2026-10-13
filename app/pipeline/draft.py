"""The screening-drafting stage — one set of grounded answers for one listing (D-125).

**One call, one response** (D-86's shape applied to drafting): exactly ONE
``complete_structured`` call whose prompt carries the CV fact store, exactly one
listing and the user's question list, returning a
:class:`~app.domain.schemas.screening.ScreeningDraftResponse`. The response is then
grounded by the deterministic checker before it is returned.

**Grounding is a value, not a gate.** An unsupported answer still returns — with its
``unsupported`` flag and warnings attached — so the human sees exactly what the model
claimed and what the check could not confirm (D-125).

**Cost and audit** (D-119 / the accepted A2 trade-off): every attempt writes exactly
one ``llm_calls`` row with ``purpose="tailor"`` and ``run_id=None``. The row purpose
is deliberately reused rather than widening ``ck_llm_calls_purpose``: ``llm_calls``
has no stage column, so apply-drafting spend is indistinguishable from CV-tailoring
spend — an accepted small reporting imprecision, not an oversight. The rolling-24h
ceiling is read through the purpose-aware ``llm_call_repo.calls_since`` and a refusal
is decided BEFORE the request, so it costs nothing.

**Trust boundary** (T-07-03-01): ``DRAFT_SYSTEM_PROMPT`` is a frozen module constant
with no interpolation of any request-derived value; the CV facts, the listing text
and the question list travel only in ``parts``. ``tools=()`` is passed explicitly.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.cv.factstore import CvFactStoreError, load_facts
from app.db.repositories import llm_call_repo
from app.domain.cv import CvFacts
from app.domain.schemas.screening import ScreeningDraftResponse
from app.llm.base import LLMBackend
from app.pipeline import rank
from app.pipeline.rank import CV_FILENAME, _cv_facts_text, _listing_text
from app.pipeline.tailor import _CAP_RUN_UNBOUNDED
from app.verify.screening import ScreeningVerdict, ground_screening_answers

log = structlog.get_logger(__name__)

#: The skip-reason vocabulary, mirroring ``tailor.TAILOR_SKIP_*``. The route reads
#: these, so the vocabulary cannot drift.
DRAFT_SKIP_DISABLED = "drafting_disabled"
DRAFT_SKIP_FACT_STORE = "fact_store_absent"

#: One human sentence per skip reason.
DRAFT_SKIP_LABELS: dict[str, str] = {
    DRAFT_SKIP_DISABLED: "screening-answer drafting is turned off in Settings",
    DRAFT_SKIP_FACT_STORE: "no readable CV fact store",
}


def drafting_skip_reason() -> str | None:
    """The skip reason knowable WITHOUT a listing, or ``None``.

    Read-only and total: it never raises. It mirrors ``tailoring_skip_reason`` — the
    operator off switch is checked BEFORE the filesystem, so it costs nothing — and is
    the reader that makes ``apply_drafting_enabled`` a real switch rather than dead
    configuration. The route consumes this in 07-05.
    """
    if not settings.apply_drafting_enabled:
        return DRAFT_SKIP_DISABLED
    try:
        load_facts(Path(settings.cv_dir) / CV_FILENAME)
    except (CvFactStoreError, OSError):
        return DRAFT_SKIP_FACT_STORE
    return None


#: The frozen drafting system prompt (T-07-03-01).
#:
#: NO f-string, no percent-formatting and no concatenation of any request-derived
#: value: a constant only, so untrusted listing text, CV prose or user questions have
#: no path into ``system``. It instructs facts-only answers and id-bearing evidence.
DRAFT_SYSTEM_PROMPT = (
    "You draft answers to a candidate's job-application screening questions. You are "
    "given the candidate's CV fact store, one job listing, and a list of questions.\n"
    "\n"
    "For each question, write a short, honest first-person answer grounded ONLY in the "
    "candidate's CV facts and the listing text. Never invent an employer, a title, a "
    "date, a metric or a skill the facts do not support. If the facts do not support an "
    "answer, say so plainly instead of fabricating one; it is better to state a gap "
    "than to guess.\n"
    "\n"
    "Cite the CV fact identifiers your answer is grounded in as evidence_ids. Use only "
    "identifiers that appear verbatim in the CV fact store. An answer with no "
    "supporting fact carries an empty evidence_ids list.\n"
    "\n"
    "Never state a number that does not appear in the candidate's facts or the listing.\n"
    "\n"
    'Return a single JSON object whose only key is "answers"; its value is a JSON '
    'array with one object per asked question, and every answer object carries '
    '"question", "answer" and "evidence_ids" (a JSON array of strings).'
)


def _questions_text(questions: Sequence[str]) -> str:
    """The user's question list, as untrusted user-turn text."""
    lines: list[str] = ["QUESTIONS (answer each one, in order):"]
    for index, question in enumerate(questions, start=1):
        lines.append(f"{index}. {question}")
    return "\n".join(lines)


def build_screening_parts(
    facts: CvFacts,
    listing: Any,
    questions: Sequence[str],
) -> list[str]:
    """Assemble the user-turn ``parts`` for one drafting call (pure, no I/O).

    Everything that is data — the CV facts (with their ids), the single listing and
    the question list — travels here, never in ``system``.
    """
    return [
        _cv_facts_text(facts),
        _listing_text(listing),
        _questions_text(questions),
    ]


async def draft_screening_answers(
    backend: LLMBackend,
    session: AsyncSession,
    *,
    listing: Any,
    facts: CvFacts,
    questions: Sequence[str],
    now: datetime,
) -> list[ScreeningVerdict] | None:
    """Make exactly ONE structured call and write exactly one audit row per ATTEMPT.

    Commits the read-only preamble before the model call so no read transaction
    spans network I/O; the caller still owns the write transaction. Never raises — a
    model failure, a ``budget_exceeded`` refusal AND a raised transport error are all
    values. Every ATTEMPTED call writes exactly one row: a completed call records
    ``result.status``, while a raised ``complete_structured`` records
    ``status="error"`` with the exception CLASS NAME only (never its message).
    Returns the grounded verdicts, or ``None`` when the call did not produce a valid
    response, the rolling-24h ceiling refused it, or the transport raised.
    """
    day_total = await llm_call_repo.calls_since(session, purpose="tailor", now=now)
    cap_day = int(settings.ranking_max_calls_per_day)

    # `purpose="tailor"` reused rather than widening `ck_llm_calls_purpose`: `llm_calls`
    # has no stage column, so apply-drafting spend is indistinguishable from
    # CV-tailoring spend — the accepted A2 trade-off. `cap_run` is unbounded because an
    # interactive draft has no run, sharing the one rolling-24h ceiling (D-119).
    if not await rank._reserve(day_total, 0, cap_day=cap_day, cap_run=_CAP_RUN_UNBOUNDED):
        # Graceful refusal: no exception, nothing marked failed, one row records the
        # cap. `llm_calls` has no `error_kind` column, so the cap name is the text.
        await llm_call_repo.record_llm_call(
            session,
            purpose="tailor",
            status="error",
            error=f"{llm_call_repo.BUDGET_EXCEEDED_MARKER}: per_day",
            run_id=None,
            now=now,
        )
        log.info("pipeline.draft_refused", reason="per_day")
        return None

    # Commit the read-only preamble (`calls_since` above, plus the caller's earlier
    # reads) BEFORE the model call. A read transaction left open across the network
    # call would make the `record_llm_call` write below upgrade a stale snapshot —
    # which SQLite rejects with SQLITE_BUSY_SNAPSHOT ("database is locked").
    await session.commit()

    try:
        parts = build_screening_parts(facts, listing, questions)
        result = await backend.complete_structured(
            schema=ScreeningDraftResponse,
            system=DRAFT_SYSTEM_PROMPT,
            parts=parts,
            model=settings.opencode_model,
            tools=(),
            retries=settings.opencode_max_retries,
        )
        # Exactly one audit row per call, success or failure: the caps count these.
        # `run_id=None` is correct — an interactive draft has no run.
        await llm_call_repo.record_llm_call(
            session,
            purpose="tailor",
            status=result.status,
            result=result,
            run_id=None,
            now=now,
        )
    except Exception as exc:  # noqa: BLE001 — a raised transport error is a value, not a crash
        # The audit trail is the promise: an ATTEMPTED call is recorded even when
        # the transport raises. Class name only — `str(exc)` may echo request context.
        await llm_call_repo.record_llm_call(
            session,
            purpose="tailor",
            status="error",
            error=type(exc).__name__,
            run_id=None,
            now=now,
        )
        log.warning("pipeline.draft_transport_error", error=type(exc).__name__)
        return None
    finally:
        await rank._release()

    if not result.ok or not isinstance(result.data, ScreeningDraftResponse):
        return None
    return ground_screening_answers(
        facts, _listing_text(listing), questions, result.data
    )


__all__ = [
    "DRAFT_SKIP_DISABLED",
    "DRAFT_SKIP_FACT_STORE",
    "DRAFT_SKIP_LABELS",
    "DRAFT_SYSTEM_PROMPT",
    "build_screening_parts",
    "draft_screening_answers",
    "drafting_skip_reason",
]
