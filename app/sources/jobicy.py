"""Jobicy adapter — a seventh `JobSource` over its free public JSON API.

Jobicy is a remote/startup board with an official no-key API whose `geo=`
parameter narrows the feed toward Ireland (the API matches "Ireland" plus
broader European geos; the core's location rule is still what admits only
Ireland). Two extras make it the richest of the three API boards:

* `jobLevel` ("Entry Level" / "Mid Level" / "Senior" / "Director" / "Lead")
  maps into the listing's `seniority` bucket, so the pipeline's title
  heuristic has real data to work with — note this is LISTING enrichment,
  not a server-side seniority FILTER (the board has none, hence the usual
  capability warning when a search carries a seniority criterion);
* the list payload carries `jobDescription` HTML, so no detail pass is needed.

The API has no keyword search parameter, so relevance is emulated exactly
like Arbeitnow: every keyword token must appear in the title.

One request per `fetch`. Terms: Jobicy requires a direct link back to the
job URL and credit to Jobicy — `source_url` keeps their URL and the source
link names "jobicy".
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

NAME = "jobicy"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
API_URL = "https://jobicy.com/api/v2/remote-jobs"

CAPABILITIES = SourceCapabilities(
    # No machine-readable salary on every row; the display strings are skipped.
    supports_salary=False,
    supports_salary_min_filter=False,
    # Everything on Jobicy is remote; the board cannot express "on-site only".
    supports_remote_flag=False,
    # `jobLevel` enriches listings but the API exposes NO level FILTER param.
    supports_seniority=False,
    # `jobDescription` (HTML) ships with every list row (fallback: `jobExcerpt`).
    supports_full_description_in_search=True,
    requires_second_pass_for_description=False,
    supports_offset_paging=False,
    max_results_per_query=50,
    exclusive_filter_groups=(),
)

_TAG_RE = re.compile(r"<[^>]+>")

#: The board's `jobLevel` vocabulary collapsed to the pipeline's buckets.
#: Anything unmapped stays `None` (unknown), never a guess.
_LEVEL_TO_SENIORITY = {
    "entry level": "junior",
    "junior": "junior",
    "mid level": "mid",
    "mid": "mid",
    "senior": "senior",
    "staff": "senior",
    "director": "senior",
    "lead": "lead",
    "principal": "lead",
    "vp": "senior",
}


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    return _TAG_RE.sub(" ", value).strip() or None


def _as_posted(value: object) -> object | None:
    """`pubDate` is an ISO datetime with a zone ("2026-10-15T03:45:06+00:00")."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None


def _level_to_seniority(value: object) -> str | None:
    if not value:
        return None
    return _LEVEL_TO_SENIORITY.get(str(value).strip().casefold())


def keyword_match(title: str | None, keywords: str) -> bool:
    """Emulated board-side search: ANY keyword token in the title qualifies.

    Same OR semantics as the Arbeitnow adapter: the saved searches are broad
    buckets, and a title-level AND would reject natural matches ("Customer
    Success" for "customer support").
    """
    terms = [token for token in keywords.casefold().split() if token]
    if not terms:
        return True
    haystack = (title or "").casefold()
    return any(token in haystack for token in terms)


def map_job(row: dict, *, source: SourceName = NAME) -> RawListing:
    """One Jobicy `jobs[]` entry as a `RawListing`."""
    job_id = str(row.get("id") or "") or None
    url = str(row.get("url") or "")
    description = _strip_html(row.get("jobDescription")) or _strip_html(
        row.get("jobExcerpt")
    )
    job_type = row.get("jobType")
    return RawListing(
        source=source,
        source_listing_id=job_id,
        source_url=url,
        direct_url=None,
        title=str(row.get("jobTitle") or "").strip(),
        company_name=(str(row.get("companyName") or "").strip() or None),
        location_raw=(str(row.get("jobGeo") or "").strip() or None),
        description=description,
        is_remote=True,
        seniority=_level_to_seniority(row.get("jobLevel")),
        posted_at=_as_posted(row.get("pubDate")),
        job_type=tuple(str(t) for t in (job_type or []) if t),
        source_extras={
            "job_level": str(row.get("jobLevel") or ""),
            "industry": [str(t) for t in (row.get("jobIndustry") or []) if t],
        },
    )


class JobicyAdapter(JobSource):
    """One instance per board. Never touches the database, never dedups."""

    name: SourceName = NAME
    capabilities = CAPABILITIES

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        """One bounded GET with `geo=ireland`; keyword relevance in-adapter."""
        now = datetime.now(UTC)
        if budget.max_requests < 1 or now >= budget.deadline:
            return FetchResult(
                source=NAME,
                status="error",
                requests_used=0,
                error="pre-call budget check refused the request",
            )
        timeout = min(20.0, max(1.0, (budget.deadline - now).total_seconds()))
        params = {"count": str(min(query.results_wanted, 50)), "geo": "ireland"}
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

        matched = [row for row in rows if keyword_match(row.get("jobTitle"), query.keywords)]
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
        """Cheap liveness check that asserts a JSON payload with jobs."""
        try:
            async with httpx.AsyncClient(
                timeout=10.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}
            ) as client:
                response = await client.get(API_URL, params={"count": "1"})
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


__all__ = ["CAPABILITIES", "JobicyAdapter"]
