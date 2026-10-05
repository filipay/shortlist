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
    session_factory: async_sessionmaker[AsyncSession],
    *,
    index: int = 1,
    company: str = "Acme",
    title: str | None = None,
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
        title=title or f"Backend Engineer {index}",
        company_name=company,
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
    assert response.status_code == 303
    assert response.headers["location"] == "/applications"

    assert await _counts(session_factory) == (1, 1)

    page = await client.get("/applications")
    assert page.status_code == 200
    assert 'id="application-row-' in page.text
    assert "Shortlisted" in page.text
    assert "Referred" in page.text

    row_id = _row_id(page.text)
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
    assert recorded.status_code == 303
    assert recorded.headers["location"] == "/applications"
    row_id = _row_id((await client.get("/applications")).text)

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
    assert response.status_code == 303, "the record route was shadowed by a dynamic route"
    assert response.headers["location"] == "/applications"
    assert await _counts(session_factory) == (1, 1)


async def test_record_submit_lands_on_the_full_styled_tracker_page(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    """G-07-1: the plain-form record submit must not strand the user on a bare fragment.

    A followed record POST must yield a full document that extends the base layout
    (doctype + the stylesheet link) carrying the new row — not the stylesheet-less
    `applications_list.html` fragment the route used to return.
    """
    listing_id = await _seed_listing(session_factory)

    response = await client.post(
        "/applications/record",
        data={"listing_id": str(listing_id), "status": "shortlisted", "notes": "Referred"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert response.url.path == "/applications"
    body = response.text
    assert "<!doctype html>" in body.lower(), "the landing page is not a full document"
    assert 'href="/static/vendor/app.css"' in body, "the landing page has no stylesheet"
    assert 'id="application-list"' in body
    assert 'id="application-row-' in body
    assert "Shortlisted" in body
    assert "Referred" in body
    assert await _counts(session_factory) == (1, 1)


async def test_notes_and_next_action_save_without_appending_an_event(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    listing_id = await _seed_listing(session_factory)
    recorded = await client.post(
        "/applications/record",
        data={"listing_id": str(listing_id), "status": "shortlisted"},
    )
    assert recorded.status_code == 303
    assert recorded.headers["location"] == "/applications"
    row_id = _row_id((await client.get("/applications")).text)

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
    assert recorded.status_code == 303
    assert recorded.headers["location"] == "/applications"
    row_id = _row_id((await client.get("/applications")).text)

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
    assert recorded.status_code == 303
    assert recorded.headers["location"] == "/applications"
    row_id = _row_id((await client.get("/applications")).text)
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
    assert recorded.status_code == 303
    assert recorded.headers["location"] == "/applications"
    row_id = _row_id((await client.get("/applications")).text)

    page = await client.get("/applications")
    assert page.status_code == 200
    assert "Move to" in page.text
    assert f'hx-get="/applications/{row_id}/history"' in page.text
    assert "History (1)" in page.text


async def _record(
    client,
    listing_id: int,
    *,
    status: str = "queued",
    notes: str | None = None,
) -> str:
    """Submit the record form and return the followed tracker page.

    The route is Post/Redirect/Get (G-07-1), so a successful record is a 303 to
    `/applications`; the caller gets the full styled page after the follow-up GET.
    """
    data = {"listing_id": str(listing_id), "status": status}
    if notes:
        data["notes"] = notes
    response = await client.post("/applications/record", data=data)
    assert response.status_code == 303
    assert response.headers["location"] == "/applications"
    return (await client.get("/applications")).text


async def test_stage_filter_over_http(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    a = await _seed_listing(session_factory, index=1)
    b = await _seed_listing(session_factory, index=2)
    await _record(client, a, status="shortlisted")
    await _record(client, b, status="queued")

    shortlisted = await client.get("/applications/list?stage=shortlisted")
    assert shortlisted.status_code == 200
    assert "Backend Engineer 1" in shortlisted.text
    assert "Backend Engineer 2" not in shortlisted.text

    queued = await client.get("/applications/list?stage=queued")
    assert "Backend Engineer 2" in queued.text
    assert "Backend Engineer 1" not in queued.text


async def test_search_filter_over_http(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    """`q` matches company, title and notes (D-133)."""
    a = await _seed_listing(session_factory, index=1, company="Acme")
    b = await _seed_listing(session_factory, index=2, company="Globex", title="Data Scientist 2")
    await _record(client, a, notes="referred by a friend")
    await _record(client, b)

    by_company = await client.get("/applications/list?q=globex")
    assert "Data Scientist 2" in by_company.text
    assert "Backend Engineer 1" not in by_company.text

    by_title = await client.get("/applications/list?q=backend")
    assert "Backend Engineer 1" in by_title.text
    assert "Data Scientist 2" not in by_title.text

    by_notes = await client.get("/applications/list?q=referred")
    assert "Backend Engineer 1" in by_notes.text
    assert "Data Scientist 2" not in by_notes.text


async def test_filtered_to_nothing_renders_the_filtered_empty_state(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    a = await _seed_listing(session_factory, index=1)
    await _record(client, a)

    response = await client.get("/applications/list?q=nomatch")
    assert response.status_code == 200
    assert 'id="application-empty-filtered"' in response.text
    assert "Clear filters" in response.text
    assert 'id="application-empty"' not in response.text


async def test_filter_controls_emit_no_offset(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    """A predicate change resets the page index: no control but the pager carries offset."""
    a = await _seed_listing(session_factory, index=1)
    await _record(client, a)

    page = await client.get("/applications")
    assert page.status_code == 200
    assert 'id="application-search"' in page.text
    assert 'name="stage"' in page.text
    assert 'name="view"' in page.text
    assert 'id="queue-pager"' in page.text
    assert 'id="queue-page-position"' in page.text
    assert "/applications/list?offset" not in page.text


async def test_filter_controls_reset_when_a_predicate_is_set(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    """A predicate change still emits no offset, so the page restarts at 1."""
    a = await _seed_listing(session_factory, index=1)
    await _record(client, a)

    # The page carries the real filter form; its controls point at the unfiltered
    # fragment URL with no offset embedded, so changing a predicate restarts at page 1.
    page = await client.get("/applications?q=acme&offset=25")
    assert page.status_code == 200
    assert 'id="application-search"' in page.text
    assert 'hx-get="/applications/list"' in page.text
    assert "/applications/list?offset" not in page.text


async def test_needs_action_view_over_http(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    """`view=needs_action` surfaces dated rows and excludes terminal stages (D-133)."""
    overdue = await _seed_listing(session_factory, index=1)
    upcoming = await _seed_listing(session_factory, index=2, title="Data Scientist 2")
    terminal = await _seed_listing(session_factory, index=3)
    # Dates are far from the real clock so the read-time overdue flag is deterministic.
    await client.post(
        "/applications/record",
        data={"listing_id": str(overdue), "status": "shortlisted", "next_action_at": "2020-01-01"},
    )
    await client.post(
        "/applications/record",
        data={"listing_id": str(upcoming), "status": "shortlisted", "next_action_at": "2999-01-01"},
    )
    await client.post(
        "/applications/record",
        data={"listing_id": str(terminal), "status": "rejected", "next_action_at": "2020-01-01"},
    )

    response = await client.get("/applications?view=needs_action")
    assert response.status_code == 200
    assert "Backend Engineer 1" in response.text, "the overdue row is present"
    assert "Data Scientist 2" in response.text, "the upcoming row is present"
    assert "Backend Engineer 3" not in response.text, "a rejected row is excluded"
    assert 'id="application-toggle-needs-action"' in response.text


async def test_needs_action_view_renders_the_nothing_needs_action_copy(
    session_factory: async_sessionmaker[AsyncSession], client
) -> None:
    a = await _seed_listing(session_factory, index=1)
    await _record(client, a, status="rejected")

    response = await client.get("/applications/list?view=needs_action")
    assert response.status_code == 200
    assert 'id="application-empty-filtered"' in response.text
    assert "Nothing needs action" in response.text


