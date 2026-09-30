"""APPLY-01 / APPLY-02 — the apply package page over HTTP.

Observable truths:

1. With no `ok` cv_artifact the page renders `gated`: a `.tailoring-empty` panel
   carrying `data-state="no-ok-artifact"` and the `/listings/{id}/cv` CTA, and the
   ready blocks are absent entirely (never empty shells). A blocked artefact is
   gated too — D-118/D-121.
2. With an `ok` artefact the page renders `ready`: the no-submit reassurance, the
   outbound plain anchor (`rel="noopener noreferrer"`), the verified-PDF block,
   the read-only gap checklist and the `Record application` form.
3. The gap checklist shows the stored ranking gaps (only what the CV does NOT
   show) and the documented empty copy when none are stored (D-123).
4. A missing `apply_url` renders the documented fallback text, never a dead anchor.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Application, Listing, Run, Source
from app.db.repositories import cv_artifact_repo, score_repo
from app.db.repositories.listing_repo import upsert_listing_source
from app.main import create_app
from app.pipeline.stages import normalise_listing
from app.sources.base import RawListing
from tests.conftest import OfflineLLMBackend

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)

_FORM_RE = re.compile(r"<form\b[^>]*>", re.IGNORECASE)
_ACTION_RE = re.compile(r'action\s*=\s*"([^"]*)"', re.IGNORECASE)


def _route_paths(routes: Any) -> list[str]:
    """Flatten FastAPI's `_IncludedRouter` wrappers into route path strings."""
    paths: list[str] = []
    for route in routes:
        inner = getattr(route, "original_router", None)
        if inner is not None and hasattr(inner, "routes"):
            paths.extend(_route_paths(inner.routes))
        else:
            paths.append(str(getattr(route, "path", "")))
    return paths

REQUIREMENTS = [
    {"text": "Python and SQL", "verdict": "met", "evidence_id": "skill.python"},
    {"text": "Kubernetes", "verdict": "partial", "evidence_id": None},
    {"text": "Team leadership", "verdict": "gap", "evidence_id": None},
]


async def _seed_listing(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    index: int = 1,
    clear_apply_url: bool = False,
) -> int:
    async with session_factory() as session:
        exists = await session.scalar(select(Source.id).where(Source.name == "linkedin"))
        if exists is None:
            session.add(Source(name="linkedin", display_name="LinkedIn"))
            await session.commit()

    raw = RawListing(
        source="linkedin",  # type: ignore[arg-type]
        source_listing_id=f"linkedin-{index}",
        source_url=f"https://linkedin.example.com/jobs/{index}",
        direct_url=None,
        title=f"Backend Engineer {index}",
        company_name="Acme",
        location_raw="Dublin, Ireland",
        description="Build the thing.",
        posted_at=date(2026, 9, 1),
    )
    async with session_factory() as session:
        outcome = await upsert_listing_source(
            session, source="linkedin", norm=normalise_listing(raw), run_id=None, now=NOW
        )
        listing_id = int(outcome.listing_id)
        if clear_apply_url:
            listing = await session.get(Listing, listing_id)
            assert listing is not None
            listing.apply_url = None
        await session.commit()
    return listing_id


async def _seed_artifact(
    session_factory: async_sessionmaker[AsyncSession], listing_id: int, *, status: str = "ok"
) -> int:
    async with session_factory() as session:
        record = await cv_artifact_repo.insert_artifact(
            session,
            listing_id=listing_id,
            base_cv_version_id=None,
            patch_json={},
            change_log_json=[],
            compile_status=status,
            verification_json={},
            page_count=1 if status == "ok" else None,
            now=NOW,
        )
        await session.commit()
    return record.id


async def _seed_score(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    listing_id: int,
    requirements: list[dict[str, object]] = REQUIREMENTS,
) -> None:
    async with session_factory() as session:
        run = Run(trigger="manual", status="done", started_at=NOW, finished_at=NOW)
        session.add(run)
        await session.flush()
        await score_repo.upsert_score(
            session,
            listing_id=listing_id,
            run_id=int(run.id),
            criteria_version=1,
            sub_scores={"skills": 1.0},
            weights={"skills": 1.0},
            rubric_version="v1",
            confidence_tier="medium",
            rationale="Grounded in the listing and the CV facts.",
            requirements=requirements,
            total_score=None,
            provider="opencode",
            model="minimax-m3",
            backend="opencode_server",
            now=NOW,
        )
        await session.commit()


async def test_gated_without_an_ok_artifact(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    listing_id = await _seed_listing(session_factory)

    response = await client.get(f"/listings/{listing_id}/apply")
    assert response.status_code == 200
    assert 'class="tailoring-empty"' in response.text
    assert 'data-state="no-ok-artifact"' in response.text
    assert "Tailor and verify a CV first" in response.text
    assert f'href="/listings/{listing_id}/cv"' in response.text
    # The ready blocks are absent entirely, never empty shells.
    assert "Open the application form" not in response.text
    assert "Your verified CV" not in response.text
    assert 'action="/applications/record"' not in response.text


async def test_a_blocked_artifact_is_gated_not_ready(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    """D-118/D-121: a blocked artefact must never open the ready package."""
    listing_id = await _seed_listing(session_factory)
    await _seed_artifact(session_factory, listing_id, status="blocked")

    response = await client.get(f"/listings/{listing_id}/apply")
    assert response.status_code == 200
    assert 'data-state="no-ok-artifact"' in response.text
    assert "Open the application form" not in response.text


async def test_ready_with_an_ok_artifact(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    listing_id = await _seed_listing(session_factory)
    await _seed_artifact(session_factory, listing_id, status="ok")

    response = await client.get(f"/listings/{listing_id}/apply")
    assert response.status_code == 200
    assert 'data-state="no-ok-artifact"' not in response.text
    # (1) no-submit reassurance, (2) outbound plain anchor, (3) verified PDF,
    # (5) the record form.
    assert "Copy each answer into the application form yourself" in response.text
    assert "Open the application form" in response.text
    assert 'rel="noopener noreferrer"' in response.text
    assert f'href="/listings/{listing_id}/cv/pdf"' in response.text
    assert f'href="/listings/{listing_id}/cv/pdf?download=1"' in response.text
    assert 'action="/applications/record"' in response.text
    assert 'name="cv_artifact_id"' in response.text


async def test_gap_checklist_renders_the_stored_gaps(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    listing_id = await _seed_listing(session_factory)
    await _seed_artifact(session_factory, listing_id, status="ok")
    await _seed_score(session_factory, listing_id=listing_id)

    response = await client.get(f"/listings/{listing_id}/apply")
    assert response.status_code == 200
    assert 'class="requirement-list"' in response.text
    assert 'class="req-gap"' in response.text
    assert 'class="req-partial"' in response.text
    assert "Team leadership" in response.text
    assert "Kubernetes" in response.text
    # A `met` requirement is not a gap and is excluded from this checklist.
    assert "Python and SQL" not in response.text


async def test_gap_checklist_empty_copy_when_no_gaps_stored(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    listing_id = await _seed_listing(session_factory)
    await _seed_artifact(session_factory, listing_id, status="ok")
    # No score at all → no stored ranking gaps.

    response = await client.get(f"/listings/{listing_id}/apply")
    assert response.status_code == 200
    assert "No requirement gaps were recorded when this job was ranked." in response.text
    assert 'class="requirement-list"' not in response.text


async def test_missing_apply_url_renders_the_fallback_text(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    listing_id = await _seed_listing(session_factory, clear_apply_url=True)
    await _seed_artifact(session_factory, listing_id, status="ok")

    response = await client.get(f"/listings/{listing_id}/apply")
    assert response.status_code == 200
    assert "No application link was recorded for this listing" in response.text
    assert "Open the application form" not in response.text
    assert 'class="apply-link"' not in response.text


async def test_unknown_listing_returns_a_404_fragment(client) -> None:
    response = await client.get("/listings/999999/apply")
    assert response.status_code == 404
    assert 'data-error="unknown-listing"' in response.text


async def test_no_submit_surface(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    """APPLY-02 / D-127: nothing here can submit to a portal.

    Every form on the page posts to a LOCAL path (never a host or `apply_url`), the
    outbound action is a plain anchor with the mandatory `rel`, and the app's route
    registry contains no URL-shaped path (nothing posts out of the app).
    """
    listing_id = await _seed_listing(session_factory)
    await _seed_artifact(session_factory, listing_id, status="ok")
    response = await client.get(f"/listings/{listing_id}/apply")
    body = response.text

    # The outbound action is a real anchor, not a form, and carries rel + target.
    anchor = re.search(r'<a[^>]*class="apply-link"[^>]*>', body)
    assert anchor is not None, "the ready page must carry the outbound apply anchor"
    tag = anchor.group(0)
    assert 'target="_blank"' in tag
    assert 'rel="noopener noreferrer"' in tag

    forms = _FORM_RE.findall(body)
    assert forms, "the ready page must carry the Record application form"
    for form in forms:
        match = _ACTION_RE.search(form)
        assert match is not None, f"a form has no action: {form}"
        action = match.group(1)
        assert action.startswith("/"), f"non-local form action: {action}"
        assert "://" not in action, f"a form posts to a host: {action}"
        assert action != "https://linkedin.example.com/jobs/1"

    # The route registry exposes no route that leaves the app.
    paths = _route_paths(create_app().routes)
    assert paths, "the route walk found nothing — the assertion would be vacuous"
    assert all(path.startswith("/") for path in paths)
    assert all("://" not in path for path in paths)
    assert not any("submit" in path for path in paths)


async def test_package_states_and_no_llm_call_on_open(
    session_factory: async_sessionmaker[AsyncSession], client, monkeypatch
) -> None:
    """D-122: opening the package assembles from stored data — zero LLM calls.

    The full page-state set is exercised (gated / blocked-gated / ready) while a
    counting backend proves no call is made on GET.
    """
    calls: list[dict[str, Any]] = []
    original = OfflineLLMBackend.complete_structured

    async def _counting(self: Any, **kwargs: Any) -> Any:
        calls.append(kwargs)
        return await original(self, **kwargs)

    monkeypatch.setattr(OfflineLLMBackend, "complete_structured", _counting)

    gated_listing = await _seed_listing(session_factory, index=1)
    blocked_listing = await _seed_listing(session_factory, index=2)
    await _seed_artifact(session_factory, blocked_listing, status="blocked")
    ready_listing = await _seed_listing(session_factory, index=3)
    await _seed_artifact(session_factory, ready_listing, status="ok")

    gated = await client.get(f"/listings/{gated_listing}/apply")
    assert 'data-state="no-ok-artifact"' in gated.text
    assert "Open the application form" not in gated.text

    blocked = await client.get(f"/listings/{blocked_listing}/apply")
    assert 'data-state="no-ok-artifact"' in blocked.text

    ready = await client.get(f"/listings/{ready_listing}/apply")
    assert "Open the application form" in ready.text

    assert calls == [], "opening the package must make no LLM call (D-122)"


async def test_record_from_the_package_links_the_ok_artifact(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    """The package's record form reaches the tracker, linked to the ok artefact."""
    listing_id = await _seed_listing(session_factory)
    ok_id = await _seed_artifact(session_factory, listing_id, status="ok")

    page = await client.get(f"/listings/{listing_id}/apply")
    assert 'action="/applications/record"' in page.text
    assert f'value="{listing_id}"' in page.text, "the form must carry the hidden listing id"
    assert f'<option value="{ok_id}"' in page.text, "the picker must offer the ok artefact"

    response = await client.post(
        "/applications/record",
        data={"listing_id": str(listing_id), "status": "applied", "cv_artifact_id": str(ok_id)},
    )
    assert response.status_code == 200
    assert "Applied" in response.text

    async with session_factory() as session:
        row = (
            await session.execute(
                select(Application).where(Application.listing_id == listing_id)
            )
        ).scalar_one()
    assert row.status == "applied"
    assert row.cv_artifact_id == ok_id
    assert row.applied_at is not None
