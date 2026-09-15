"""The politeness ledger — one `source_request_log` row per outbound request.

This is the transport layer's ledger (D-03's second recording place), and it lives
next to `_jobspy_transport.py` rather than inside it for a concrete reason: that
module imports `jobspy` at the top, and `jobspy` loads a native TLS library. If the
ledger lived there, no unit test could write one and the pipeline could not import
it without the scraper's toolchain — the ledger would be untestable exactly when it
matters most. `app/sources/_jobspy_transport.py` re-exports everything here, so the
documented "transport writes the ledger" link still holds for a reader.

The verdict document is derived from these rows, so a request that is not recorded
is a measurement that does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SourceRequestLog
from app.sources.base import classify_response


@dataclass(frozen=True)
class RequestOutcome:
    """One outbound request's ledger record — S5's input and the politeness proof."""

    kind: str
    status_code: int | None
    ok: bool
    note: str


async def record_source_request(
    session: AsyncSession,
    *,
    source: str,
    kind: str,
    status_code: int | None = None,
    ok: bool | None = None,
    note: str | None = None,
    run_id: int | None = None,
    occurred_at: datetime | None = None,
) -> SourceRequestLog:
    """Append one row to the politeness/quota ledger (D-03(b)).

    The probe verdict must be derivable from these rows, so every outbound request
    is recorded — success, block or error.
    """
    row = SourceRequestLog(
        source=source,
        run_id=run_id,
        occurred_at=occurred_at or datetime.now(UTC),
        kind=kind,
        status_code=status_code,
        ok=ok,
        note=note,
    )
    session.add(row)
    await session.flush()
    return row


async def record_fetch_outcome(
    session: AsyncSession,
    *,
    source: str,
    run_id: int | None,
    result_status: str,
    parsed_items: int,
    kind: str = "search",
    now: datetime | None = None,
) -> RequestOutcome:
    """Write ONE `source_request_log` row for one outbound request.

    Called by the pipeline, which is the layer that owns a session and the run id,
    on the transport's behalf. Classifies fetch-side versus parse-side so a block
    and a parse miss are distinguishable later (S5).
    """
    stop_signal = result_status if result_status in ("blocked", "rate_limited") else None
    ok, note = classify_response(
        status_code=None, parsed_items=parsed_items, stop_signal=stop_signal
    )
    await record_source_request(
        session,
        source=source,
        kind=kind,
        status_code=None,
        ok=ok,
        note=note,
        run_id=run_id,
        occurred_at=now,
    )
    return RequestOutcome(kind=kind, status_code=None, ok=ok, note=note)


__all__ = ["RequestOutcome", "record_fetch_outcome", "record_source_request"]
