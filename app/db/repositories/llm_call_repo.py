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
(D-50).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

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
    #: Recorded from the caller's value, not read back — the column lands in
    #: migration 0003 (plan 03-04). Until then this is populated on the returned
    #: record but not persisted.
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

    return LlmCallRecord(
        id=int(row.id),
        purpose=row.purpose,
        status=row.status,
        backend=row.backend,
        provider=row.provider,
        model=row.model,
        agent=row.agent,
        server_version=server_version,
        prompt_tokens=row.prompt_tokens,
        completion_tokens=row.completion_tokens,
        latency_ms=row.latency_ms,
        attempts=row.attempts,
        error=row.error,
        created_at=row.created_at,
    )


__all__ = ["PURPOSES", "STATUSES", "LlmCallRecord", "record_llm_call"]
