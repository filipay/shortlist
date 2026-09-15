"""The sanitise stage (D-23 / Pattern 3).

`sanitize` is a *named stage*, not a helper buried in an adapter: it has a name, a
log line and a counter. It is simultaneously the GDPR control, the injection
control and the PII control, and it sits at the single point between "raw
observation" and "anything persisted or prompted".

A helper inside each adapter would silently diverge across two adapters.
"""

from __future__ import annotations

from dataclasses import replace

import structlog

from app.config import settings
from app.domain.sanitize import SanitizeReport, sanitize_short_field, sanitize_text
from app.sources.base import FetchResult, RawListing

log = structlog.get_logger(__name__)

STAGE_NAME = "sanitize"

#: Short fields are sanitised but only bounded generously — truncating a company
#: name would corrupt the dedup anchor, and the schema already caps them.
SHORT_FIELD_MAX_CHARS = 512


async def sanitize_listing(
    listing: RawListing, *, max_chars: int | None = None
) -> tuple[RawListing, SanitizeReport]:
    """Sanitise one raw observation. Returns the sanitised copy and a report."""
    limit = settings.description_max_chars if max_chars is None else max_chars

    title = sanitize_short_field(listing.title, max_chars=SHORT_FIELD_MAX_CHARS)
    company = sanitize_short_field(listing.company_name, max_chars=SHORT_FIELD_MAX_CHARS)
    location = sanitize_short_field(listing.location_raw, max_chars=SHORT_FIELD_MAX_CHARS)
    description = sanitize_text(listing.description, max_chars=limit)

    report = (
        title.report.merge(company.report)
        .merge(location.report)
        .merge(description.report)
    )

    sanitised = replace(
        listing,
        title=title.text,
        company_name=company.text or None,
        location_raw=location.text or None,
        description=description.text,
    )

    # Counts only — the removed value is never logged (Pitfall 7). Echoing the
    # removed span into a log line *is* the persistence path this control exists
    # to close, so only the aggregate count crosses the boundary.
    removed_pii = report.emails_removed + report.phones_removed
    if removed_pii or report.truncated or report.instruction_like:
        log.info(
            "ingest.sanitize",
            stage=STAGE_NAME,
            source=listing.source,
            pii_removed=removed_pii,
            emails_removed=report.emails_removed,
            phones_removed=report.phones_removed,
            truncated=report.truncated,
            instruction_like=report.instruction_like,
        )

    return sanitised, report


async def sanitize_fetch_result(
    result: FetchResult, *, max_chars: int | None = None
) -> tuple[FetchResult, SanitizeReport]:
    """Sanitise every item of a fetch result, aggregating one report."""
    report = SanitizeReport()
    items: list[RawListing] = []
    for listing in result.items:
        sanitised, item_report = await sanitize_listing(listing, max_chars=max_chars)
        report = report.merge(item_report)
        items.append(sanitised)
    return replace(result, items=items), report


__all__ = ["STAGE_NAME", "sanitize_fetch_result", "sanitize_listing"]
