"""APPLY-03 … APPLY-06 / UI-04 — the `/applications` tracker over HTTP.

Observable truths:

1. Zero applications renders the tracker empty state (`#application-empty`).
2. A recorded application appears in the tracker with its Stage badge and every
   column (applied date, next action, latest note).
3. A freshly recorded application always renders its one `created → <stage>` event
   in the inline history, never a blank history block.
4. A transition to `applied` requires an `ok` artefact and writes nothing otherwise.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Application, ApplicationEvent, Source
from app.db.repositories import cv_artifact_repo
from app.db.repositories.listing_repo import upsert_listing_source
from app.pipeline.stages import normalise_listing
from app.sources.base import RawListing

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _row_id(body: str) -> int:
    match = re.search(r'id="application-row-(\d+)"', body)
    assert match is not None, f"no tracker row in body: {body[:200]}"
    return int(match.group(1))


async def _seed_listing(
    session_factory: async_sessionmaker[AsyncSession], *, index: int = 1
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


async def _counts(session_factory: async_sessionmaker[AsyncSession]) -> tuple[int, int]:
    async with session_factory() as session:
        applications = await session.scalar(select(func.count()).select_from(Application))
        events = await session.scalar(select(func.count()).select_from(ApplicationEvent))
    return int(applications or 0), int(events or 0)


async def test_empty_tracker_renders_the_empty_state(client) -> None:
    response = await client.get("/applications")
    assert response.status_code == 200
    assert 'id="application-empty"' in response.text
    assert "No applications yet" in response.text


async def test_record_via_http_renders_the_row_and_its_created_event(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    listing_id = await _seed_listing(session_factory)

    response = await client.post(
        "/applications/record",
        data={"listing_id": str(listing_id), "status": "shortlisted", "notes": "Referred"},
    )
    assert response.status_code == 200
    assert 'id="application-row-' in response.text
    assert "Shortlisted" in response.text

    assert await _counts(session_factory) == (1, 1)

    page = await client.get("/applications")
    assert page.status_code == 200
    assert "Shortlisted" in page.text
    assert "Referred" in page.text

    row_id = _row_id(response.text)
    history = await client.get(f"/applications/{row_id}/history")
    assert history.status_code == 200
    assert "created" in history.text
    assert "Shortlisted" in history.text
    assert "No history recorded." not in history.text


async def test_record_refuses_an_applied_stage_without_an_ok_artifact(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    listing_id = await _seed_listing(session_factory)

    response = await client.post(
        "/applications/record",
        data={"listing_id": str(listing_id), "status": "applied"},
    )
    assert response.status_code == 409
    assert 'data-error="applied-needs-ok-artifact"' in response.text
    assert await _counts(session_factory) == (0, 0)


async def test_history_partial_renders_no_history_recorded_for_an_eventless_row(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    """A row inserted directly (no event) still renders an honest empty timeline."""
    listing_id = await _seed_listing(session_factory)
    async with session_factory() as session:
        row = Application(
            listing_id=listing_id,
            status="queued",
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(row)
        await session.commit()
        application_id = int(row.id)

    response = await client.get(f"/applications/{application_id}/history")
    assert response.status_code == 200
    assert "No history recorded." in response.text
    assert "History (0)" in response.text


async def test_applied_requires_ok_artifact(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    """D-118/D-129 over HTTP: a blocked artefact is a 4xx refusal that writes nothing; ok links."""
    listing_id = await _seed_listing(session_factory)
    recorded = await client.post(
        "/applications/record",
        data={"listing_id": str(listing_id), "status": "shortlisted"},
    )
    assert recorded.status_code == 200
    row_id = _row_id(recorded.text)

    blocked_id = await _seed_artifact(session_factory, listing_id, status="blocked")
    refused = await client.post(
        f"/applications/{row_id}/status",
        data={"status": "applied", "cv_artifact_id": str(blocked_id)},
    )
    assert refused.status_code == 409
    assert 'data-error="applied-needs-ok-artifact"' in refused.text
    assert f'id="application-row-{row_id}"' in refused.text
    assert await _counts(session_factory) == (1, 1), "a refusal writes no row and no event"

    ok_id = await _seed_artifact(session_factory, listing_id, status="ok")
    accepted = await client.post(
        f"/applications/{row_id}/status",
        data={"status": "applied", "cv_artifact_id": str(ok_id)},
    )
    assert accepted.status_code == 200
    assert "Applied" in accepted.text
    assert await _counts(session_factory) == (1, 2)


async def test_record_route_is_not_shadowed_by_the_dynamic_route(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    """`POST /applications/record` must reach the record handler, not 422 as an id."""
    listing_id = await _seed_listing(session_factory)
    response = await client.post(
        "/applications/record",
        data={"listing_id": str(listing_id), "status": "queued"},
    )
    assert response.status_code == 200, "the record route was shadowed by a dynamic route"
    assert await _counts(session_factory) == (1, 1)


async def test_notes_and_next_action_save_without_appending_an_event(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    listing_id = await _seed_listing(session_factory)
    recorded = await client.post(
        "/applications/record",
        data={"listing_id": str(listing_id), "status": "shortlisted"},
    )
    row_id = _row_id(recorded.text)

    saved = await client.post(
        f"/applications/{row_id}",
        data={"notes": "Follow up Friday", "next_action_at": "2026-10-09"},
    )
    assert saved.status_code == 200
    assert "Follow up Friday" in saved.text
    assert 'value="2026-10-09"' in saved.text
    assert await _counts(session_factory) == (1, 1), "editing notes appends no event"


async def test_clearing_the_next_action_field_clears_the_date(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    listing_id = await _seed_listing(session_factory)
    recorded = await client.post(
        "/applications/record",
        data={
            "listing_id": str(listing_id),
            "status": "queued",
            "next_action_at": "2026-10-09",
        },
    )
    row_id = _row_id(recorded.text)

    cleared = await client.post(
        f"/applications/{row_id}", data={"notes": "", "next_action_at": ""}
    )
    assert cleared.status_code == 200

    async with session_factory() as session:
        row = await session.get(Application, row_id)
    assert row is not None and row.next_action_at is None


async def test_history_partial_lists_all_events_in_order_and_count_matches(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    listing_id = await _seed_listing(session_factory)
    recorded = await client.post(
        "/applications/record",
        data={"listing_id": str(listing_id), "status": "shortlisted"},
    )
    row_id = _row_id(recorded.text)
    moved = await client.post(
        f"/applications/{row_id}/status",
        data={"status": "interviewing", "note": "Screen booked"},
    )
    assert moved.status_code == 200

    history = await client.get(f"/applications/{row_id}/history")
    assert history.status_code == 200
    assert "History (2)" in history.text
    assert history.text.count('class="stage-entry"') == 2
    assert "created" in history.text, "a NULL from_status renders as created"
    assert "Screen booked" in history.text


async def test_tracker_row_renders_the_transition_and_history_controls(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    listing_id = await _seed_listing(session_factory)
    recorded = await client.post(
        "/applications/record",
        data={"listing_id": str(listing_id), "status": "shortlisted"},
    )
    row_id = _row_id(recorded.text)

    page = await client.get("/applications")
    assert page.status_code == 200
    assert "Move to" in page.text
    assert f'hx-get="/applications/{row_id}/history"' in page.text
    assert "History (1)" in page.text


