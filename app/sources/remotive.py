"""Remotive adapter — a sixth `JobSource` over its free public JSON API.

Remotive is a remote-work board with a startup-heavy catalogue and an official
no-key API that supports a SERVER-SIDE `search=` parameter, so keyword
relevance is the board's own, not emulated here. Every job is remote by
construction; `candidate_required_location` carries the geo hint ("Ireland",
"Worldwide", "USA", …) and the core's location rule decides Ireland-ness.

Rate discipline (their documented guidance, honoured here): a couple of GETs
per day is plenty — one request per `fetch`, i.e. three per daily run for the
three saved searches. No credential path: public API only.

Terms: listings must link back to the Remotive job URL and credit Remotive as
the source — `source_url` keeps their URL and the source link names "remotive".
Their catalogue is delayed ~24h by design.
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

NAME = "remotive"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
API_URL = "https://remotive.com/api/remote-jobs"

CAPABILITIES = SourceCapabilities(
    # `salary` is a display string ("$35,3k- $52k") — never parsed into numbers.
    supports_salary=False,
    supports_salary_min_filter=False,
    # Everything on Remotive is remote; the board cannot express "on-site only".
    supports_remote_flag=False,
    supports_seniority=False,
    # `description` (HTML) ships with every list row.
    supports_full_description_in_search=True,
    requires_second_pass_for_description=False,
    supports_offset_paging=False,
    max_results_per_query=50,
    exclusive_filter_groups=(),
)

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    return _TAG_RE.sub(" ", value).strip() or None


def _as_posted(value: object) -> object | None:
    """`publication_date` is an ISO datetime without a zone ("2026-10-11T20:17:27")."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None


def map_job(row: dict, *, source: SourceName = NAME) -> RawListing:
    """One Remotive `jobs[]` entry as a `RawListing`."""
    job_id = str(row.get("id") or "") or None
    url = str(row.get("url") or "")
    location = str(row.get("candidate_required_location") or "").strip() or None
    job_type = row.get("job_type")
    return RawListing(
        source=source,
        source_listing_id=job_id,
        source_url=url,
        direct_url=None,
        title=str(row.get("title") or "").strip(),
        company_name=(str(row.get("company_name") or "").strip() or None),
        location_raw=location,
        description=_strip_html(row.get("description")),
        is_remote=True,
        seniority=None,
        posted_at=_as_posted(row.get("publication_date")),
        job_type=(str(job_type),) if job_type else (),
        source_extras={
            "category": str(row.get("category") or ""),
            "tags": [str(t) for t in (row.get("tags") or []) if t],
        },
    )


class RemotiveAdapter(JobSource):
    """One instance per board. Never touches the database, never dedups."""

    name: SourceName = NAME
    capabilities = CAPABILITIES

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        """One bounded GET; the keyword term rides as the board's `search=`."""
        now = datetime.now(UTC)
        if budget.max_requests < 1 or now >= budget.deadline:
            return FetchResult(
                source=NAME,
                status="error",
                requests_used=0,
                error="pre-call budget check refused the request",
            )
        timeout = min(20.0, max(1.0, (budget.deadline - now).total_seconds()))
        params: dict[str, str] = {"limit": str(min(query.results_wanted, 50))}
        if query.keywords.strip():
            params["search"] = query.keywords.strip()
        try:
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}
            ) as client:
                response = await client.get(API_URL, params=params)
        except Exception as exc:  # noqa: BLE001 — R1: a source failure never raises
            return FetchResult(
                source=NAME,
                status=classify_transport_error(exc),
                requests_used=1,
                error=str(exc),
            )

        try:
            payload = response.json()
            rows = payload.get("jobs") if isinstance(payload, dict) else None
        except Exception:  # noqa: BLE001 — a malformed body is a parse miss
            rows = None
        rows = [row for row in rows or [] if isinstance(row, dict)]

        ok, note = classify_response(
            status_code=response.status_code, parsed_items=len(rows)
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
            items=[map_job(row) for row in rows],
            status="ok",
            requests_used=1,
        )

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        """Cheap liveness check that asserts a JSON payload with jobs."""
        try:
            async with httpx.AsyncClient(
                timeout=10.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}
            ) as client:
                response = await client.get(API_URL, params={"limit": "1"})
        except Exception:  # noqa: BLE001 — probe is total
            return "unreachable"
        if response.status_code != 200:
            return "unreachable"
        try:
            payload = response.json()
        except Exception:  # noqa: BLE001
            return "degraded"
        rows = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(rows, list) or not rows:
            return "degraded"
        return "ok"


__all__ = ["CAPABILITIES", "RemotiveAdapter"]
