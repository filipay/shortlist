"""`llm_calls` write path — the cost + audit trail Phase 3 fills (D-12, D-50).

House rules, as everywhere in `app/db/repositories/`:

* repositories are the **only** place SQL lives;
* they take an `AsyncSession` explicitly and **never commit** — the caller owns
  the single commit;
* the INSERT is wrapped in a SAVEPOINT (`session.begin_nested()`) so a failure
  here cannot poison the caller's outer transaction;
* `now` is injectable so a caller (or a test) can pin the clock.

The vocabulary is validated against `PURPOSES` / `STATUSES` **before** any SQL is
issued, mirroring the CHECK constraints but raising a clear `ValueError` rather
than a raw `IntegrityError` (the `event_repo.append_event` pattern).

There is deliberately **no** function here that writes to `runs`. Writing the
run-level counters is Phase 5's caller through `_finish`; the selftest
structurally cannot create a synthetic run because `run_id` defaults to `None`
(D-50). `llm_totals_for_run` is the READ that caller will use — this module ships
the read only.

The reads are total: a half-written row (a NULL token count, for instance) is
summed as 0 rather than raising, exactly as `run_repo`'s tolerant accessors
default instead of raising, because a page must still render.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LlmCall
from app.llm.base import StructuredCallResult

#: Mirrors `ck_llm_calls_purpose` (migration 0001). Widening the vocabulary is a
#: coordinated migration plus a change here — a second vocabulary is never minted.
PURPOSES: frozenset[str] = frozenset({"rank", "narrate", "tailor", "extract", "probe"})

#: Mirrors `ck_llm_calls_status` (migration 0001).
STATUSES: frozenset[str] = frozenset({"ok", "invalid", "timeout", "error"})


@dataclass(frozen=True)
class LlmCallRecord:
    """One `llm_calls` row, ready to render. Frozen: nothing can be mutated back."""

    id: int
    purpose: str
    status: str
    backend: str | None
    provider: str | None
    model: str | None
    agent: str | None
    #: The opencode server version this call ran against (D-12 / M9), persisted by
    #: migration 0003 and read back from the row.
    server_version: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int | None
    attempts: int | None
    error: str | None
    created_at: datetime


async def record_llm_call(
    session: AsyncSession,
    *,
    purpose: str,
    status: str,
    result: StructuredCallResult | None = None,
    backend: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    agent: str | None = None,
    server_version: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    latency_ms: int | None = None,
    attempts: int | None = None,
    error: str | None = None,
    run_id: int | None = None,
    now: datetime | None = None,
) -> LlmCallRecord:
    """Insert exactly one audit row and return it. Never commits.

    When `result` is supplied its fields are mapped onto the columns, so a caller
    passes the port's value rather than re-deriving it. Explicit keyword arguments
    win over the mapped ones. `run_id` defaults to `None` so the selftest cannot
    create a `runs` row (D-50). `now` defaults to `datetime.now(UTC)`.
    """
    if purpose not in PURPOSES:
        raise ValueError(f"unknown purpose {purpose!r}; expected one of {sorted(PURPOSES)}")
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}; expected one of {sorted(STATUSES)}")

    if result is not None:
        provider = provider if provider is not None else result.provider
        model = model if model is not None else result.model
        agent = agent if agent is not None else result.agent
        server_version = server_version if server_version is not None else result.server_version
        latency_ms = latency_ms if latency_ms is not None else result.latency_ms
        attempts = attempts if attempts is not None else result.attempts
        error = error if error is not None else result.error
        if completion_tokens is None:
            # `provider_tokens` is the response's output-token count.
            completion_tokens = result.provider_tokens

    moment = now if now is not None else datetime.now(UTC)
    row = LlmCall(
        run_id=run_id,
        purpose=purpose,
        backend=backend,
        provider=provider,
        model=model,
        agent=agent,
        server_version=server_version,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency_ms,
        status=status,
        attempts=attempts,
        error=error,
        created_at=moment,
    )
    async with session.begin_nested():
        session.add(row)
        await session.flush()

    return _to_record(row)


def _to_record(row: LlmCall) -> LlmCallRecord:
    """One ORM row as its frozen read value. The single mapping, so write and read
    cannot disagree about a field."""
    return LlmCallRecord(
        id=int(row.id),
        purpose=row.purpose,
        status=row.status,
        backend=row.backend,
        provider=row.provider,
        model=row.model,
        agent=row.agent,
        server_version=row.server_version,
        prompt_tokens=row.prompt_tokens,
        completion_tokens=row.completion_tokens,
        latency_ms=row.latency_ms,
        attempts=row.attempts,
        error=row.error,
        created_at=row.created_at,
    )


def _tolerant_int(value: Any) -> int:
    """An int, or 0 for a NULL/unusable value — a half-written row still totals."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


async def latest_probe(session: AsyncSession) -> LlmCallRecord | None:
    """The most recent `purpose='probe'` row, or `None` on an empty table.

    Never commits and never raises (the module's house rules). Ordered by
    `(created_at, id)` descending: two selftests within one second share a
    `created_at`, so the unique `id` tie-break is what makes the read
    deterministic — the same rule `event_repo`'s projection uses.

    This is the read the `/settings` page renders D-52's detail from, and the one
    Phase 5 can share rather than minting a second query.
    """
    row = await session.scalar(
        select(LlmCall)
        .where(LlmCall.purpose == "probe")
        .order_by(LlmCall.created_at.desc(), LlmCall.id.desc())
        .limit(1)
    )
    return _to_record(row) if row is not None else None


async def llm_totals_for_run(session: AsyncSession, *, run_id: int) -> tuple[int, int]:
    """`(call_count, total_tokens)` for one run. Never commits, never raises.

    `total_tokens` sums `prompt_tokens + completion_tokens` with a NULL treated as
    0, so a half-written row still totals. The `run_id == run_id` predicate
    structurally excludes the `run_id IS NULL` selftest probes, so a probe can
    never inflate a run's recorded cost.

    Phase 5's `_finish` caller is the consumer; this plan ships only the read.
    """
    rows = (
        await session.execute(
            select(LlmCall.prompt_tokens, LlmCall.completion_tokens).where(
                LlmCall.run_id == run_id
            )
        )
    ).all()
    total = sum(
        _tolerant_int(prompt) + _tolerant_int(completion) for prompt, completion in rows
    )
    return len(rows), total


__all__ = [
    "PURPOSES",
    "STATUSES",
    "LlmCallRecord",
    "latest_probe",
    "llm_totals_for_run",
    "record_llm_call",
]
