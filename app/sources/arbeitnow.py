"""Arbeitnow adapter — a fifth `JobSource` over its free public JSON API.

Arbeitnow is a European job board (startup/tech-heavy) that publishes a free
no-key API: one GET returns up to 300 fresh listings ordered by `created_at`
(hourly updates). Irish openings appear as free-text locations ("Dublin",
"Ireland"), so Ireland-ness is enforced by the core's location rule, not here.

The API has NO server-side search or keyword parameter, so relevance is
emulated the same way a board-side search would behave: a listing survives
only when every keyword token appears in its title (casefolded, order-free).
That is fetch-side relevance, not pipeline filtering (R5): without it the
adapter would ship every European trade job into a tech query.

One request per `fetch` (page 1). No credential path: public API only.

Terms: the API asks for a link back to arbeitnow.com — every listing keeps
its `url` as `source_url`, which the UI renders as the source link.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Literal

import httpx

from app.sources.base import (
    FetchBudget,
    FetchResult,
    JobSource,
    RawListing,
    SearchQuery,
    SourceCapabilities,
    SourceName,
    classify_response,
    classify_transport_error,
)

NAME = "arbeitnow"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
API_URL = "https://www.arbeitnow.com/api/job-board-api?page=1"

CAPABILITIES = SourceCapabilities(
    # The list payload carries no salary fields.
    supports_salary=False,
    supports_salary_min_filter=False,
    supports_remote_flag=True,
    supports_seniority=False,
    # `description` ships with every list row (HTML).
    supports_full_description_in_search=True,
    requires_second_pass_for_description=False,
    # `?page=` is page-based, not item-offset based; Phase 1 reads page 1 only.
    supports_offset_paging=False,
    max_results_per_query=300,
    exclusive_filter_groups=(),
)

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    return _TAG_RE.sub(" ", value).strip() or None


def _as_bool(value: object) -> bool | None:
    """The API serialises `remote` as the STRING "True"/"False"."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in ("true", "1", "yes"):
            return True
        if lowered in ("false", "0", "no"):
            return False
    return None


def _as_posted(value: object) -> object | None:
    """`created_at` is a unix-seconds STRING."""
    try:
        return datetime.fromtimestamp(int(str(value)), tz=UTC).date()
    except (TypeError, ValueError, OverflowError):
        return None


def keyword_match(title: str | None, keywords: str) -> bool:
    """Emulated board-side search: ANY keyword token in the title qualifies.

    Boards treat space-separated terms loosely (OR), and these saved searches
    are broad buckets ("customer support" must also match "Customer Service",
    "Customer Success"), so OR semantics is the closer analogue. Without it a
    European feed returns nothing for a natural query. This is fetch-side
    relevance, not pipeline filtering (R5).
    """
    terms = [token for token in keywords.casefold().split() if token]
    if not terms:
        return True
    haystack = (title or "").casefold()
    return any(token in haystack for token in terms)


def map_job(row: dict, *, source: SourceName = NAME) -> RawListing:
    """One Arbeitnow `data[]` entry as a `RawListing`."""
    slug = str(row.get("slug") or "") or None
    url = str(row.get("url") or "")
    return RawListing(
        source=source,
        source_listing_id=slug,
        source_url=url,
        direct_url=None,
        title=str(row.get("title") or "").strip(),
        company_name=(str(row.get("company_name") or "").strip() or None),
        location_raw=(str(row.get("location") or "").strip() or None),
        description=_strip_html(row.get("description")),
        is_remote=_as_bool(row.get("remote")),
        seniority=None,
        posted_at=_as_posted(row.get("created_at")),
        job_type=tuple(str(t) for t in (row.get("job_types") or []) if t),
        source_extras={"tags": [str(t) for t in (row.get("tags") or []) if t]},
    )


class ArbeitnowAdapter(JobSource):
    """One instance per board. Never touches the database, never dedups."""

    name: SourceName = NAME
    capabilities = CAPABILITIES

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        """One bounded GET, keyword relevance applied in-adapter."""
        now = datetime.now(UTC)
        if budget.max_requests < 1 or now >= budget.deadline:
            return FetchResult(
                source=NAME,
                status="error",
                requests_used=0,
                error="pre-call budget check refused the request",
            )
        timeout = min(20.0, max(1.0, (budget.deadline - now).total_seconds()))
        try:
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}
            ) as client:
                response = await client.get(API_URL)
        except Exception as exc:  # noqa: BLE001 — R1: a source failure never raises
            return FetchResult(
                source=NAME,
                status=classify_transport_error(exc),
                requests_used=1,
                error=str(exc),
            )

        try:
            payload = response.json()
            rows = payload.get("data") if isinstance(payload, dict) else None
        except Exception:  # noqa: BLE001 — a malformed body is a parse miss
            rows = None
        rows = [row for row in rows or [] if isinstance(row, dict)]

        matched = [row for row in rows if keyword_match(row.get("title"), query.keywords)]
        ok, note = classify_response(
            status_code=response.status_code, parsed_items=len(matched)
        )
        if not ok:
            status = (
                "rate_limited"
                if response.status_code == 429
                else "blocked"
                if response.status_code in (401, 403)
                else "error"
                if response.status_code >= 500
                else "partial"
            )
            return FetchResult(
                source=NAME, status=status, requests_used=1, error=note
            )
        return FetchResult(
            source=NAME,
            items=[map_job(row) for row in matched],
            status="ok",
            requests_used=1,
        )

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        """Cheap liveness check that asserts a JSON payload with rows."""
        try:
            async with httpx.AsyncClient(
                timeout=10.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}
            ) as client:
                response = await client.get(API_URL)
        except Exception:  # noqa: BLE001 — probe is total
            return "unreachable"
        if response.status_code != 200:
            return "unreachable"
        try:
            payload = response.json()
        except Exception:  # noqa: BLE001
            return "degraded"
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list) or not rows:
            return "degraded"
        return "ok"


__all__ = ["CAPABILITIES", "ArbeitnowAdapter"]
