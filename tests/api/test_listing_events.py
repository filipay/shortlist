"""QUEUE-08 / D-41 / T-02-37 / T-02-39 — one click saves or hides, and the row says which.

Save and Hide are DISTINCT actions: a test below hides a listing and asserts its `saved`
flag is untouched, and the row renders two separately-labelled controls with the inverse
action on an already-applied one, so the user can always tell what they did.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import ListingEvent, Source
from app.db.repositories.listing_repo import upsert_listing_source
from app.pipeline.stages import normalise_listing
from app.sources.base import RawListing

ROW_ID_RE = re.compile(r'<tr id="listing-row-(\d+)"')

XSS_TITLE = "<script>x</script> Senior Engineer"
ESCAPED_XSS_TITLE = "&lt;script&gt;x&lt;/script&gt; Senior Engineer"


def _ids(body: str) -> list[int]:
    return [int(value) for value in ROW_ID_RE.findall(body)]


async def _register_sources(
    session_factory: async_sessionmaker[AsyncSession], *names: str
) -> None:
    async with session_factory() as session:
        for name in names:
            session.add(Source(name=name, display_name=name.title()))
        await session.commit()


async def _seed_listing(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    title: str,
    index: int,
) -> int:
    raw = RawListing(
        source="linkedin",  # type: ignore[arg-type]
        source_listing_id=f"linkedin-{index}",
        source_url=f"https://linkedin.example.com/jobs/{index}",
        direct_url=None,
        title=title,
        company_name="Acme",
        location_raw="Dublin, Ireland",
        description="Build the thing.",
        posted_at=date(2026, 9, 1),
    )
    async with session_factory() as session:
        outcome = await upsert_listing_source(
            session,
            source="linkedin",
            norm=normalise_listing(raw),
            run_id=None,
            now=datetime.now(UTC),
        )
        listing_id = int(outcome.listing_id)
        await session.commit()
    return listing_id


async def _events(
    session_factory: async_sessionmaker[AsyncSession], listing_id: int
) -> list[ListingEvent]:
    async with session_factory() as session:
        return (
            (
                await session.execute(
                    select(ListingEvent)
                    .where(ListingEvent.listing_id == listing_id)
                    .order_by(ListingEvent.id)
                )
            )
            .scalars()
            .all()
        )


async def _seed(session_factory: async_sessionmaker[AsyncSession], *, title: str = "Engineer"):
    await _register_sources(session_factory, "linkedin")
    return await _seed_listing(session_factory, title=title, index=1)


# --- save ---------------------------------------------------------------------


async def test_posting_save_appends_one_event_and_the_row_reads_saved(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    listing_id = await _seed(session_factory)

    response = await client.post(f"/listings/{listing_id}/events", data={"event_type": "save"})

    assert response.status_code == 200
    assert f'id="listing-row-{listing_id}"' in response.text, "the swap target comes back"
    assert 'data-saved="1"' in response.text
    assert "badge-saved" in response.text
    assert "Unsave" in response.text, "the control now offers the inverse action"

    events = await _events(session_factory, listing_id)
    assert [event.event_type for event in events] == ["save"]


async def test_save_twice_appends_two_events_and_still_reads_saved(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Idempotent IN EFFECT, not in the log: the appended history is the record."""
    listing_id = await _seed(session_factory)

    await client.post(f"/listings/{listing_id}/events", data={"event_type": "save"})
    second = await client.post(f"/listings/{listing_id}/events", data={"event_type": "save"})

    assert second.status_code == 200
    assert 'data-saved="1"' in second.text
    events = await _events(session_factory, listing_id)
    assert [event.event_type for event in events] == ["save", "save"]


async def test_save_then_unsave_appends_two_events_and_reads_unsaved(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    listing_id = await _seed(session_factory)

    await client.post(f"/listings/{listing_id}/events", data={"event_type": "save"})
    response = await client.post(
        f"/listings/{listing_id}/events", data={"event_type": "unsave"}
    )

    assert response.status_code == 200
    assert 'data-saved="0"' in response.text
    assert "badge-saved" not in response.text
    # The control's action flipped back: pressing it again would `save`, not `unsave`.
    assert 'name="event_type" value="save"' in response.text
    assert 'name="event_type" value="unsave"' not in response.text
    events = await _events(session_factory, listing_id)
    assert [event.event_type for event in events] == ["save", "unsave"]


# --- hide ---------------------------------------------------------------------


async def test_hiding_removes_the_listing_from_the_queue_and_the_control_becomes_undo(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    listing_id = await _seed(session_factory)
    assert "Engineer" in (await client.get("/")).text

    response = await client.post(f"/listings/{listing_id}/events", data={"event_type": "hide"})

    assert response.status_code == 200
    assert 'data-hidden="1"' in response.text
    assert "Unhide" in response.text, "the control reads as a one-tap undo"

    default = await client.get("/")
    assert "Engineer" not in default.text, "a hidden listing leaves the default queue"
    assert _ids(default.text) == []

    revealed = await client.get("/", params={"hidden": "1"})
    assert "Engineer" in revealed.text, "the Hidden filter reaches it"
    assert _ids(revealed.text) == [listing_id]

    events = await _events(session_factory, listing_id)
    assert [event.event_type for event in events] == ["hide"]


async def test_hiding_leaves_the_saved_flag_untouched_and_vice_versa(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """D-41: the two actions are distinct and never imply one another."""
    listing_id = await _seed(session_factory)

    await client.post(f"/listings/{listing_id}/events", data={"event_type": "save"})
    hidden = await client.post(f"/listings/{listing_id}/events", data={"event_type": "hide"})

    assert 'data-saved="1"' in hidden.text, "hiding must not unsave"
    assert 'data-hidden="1"' in hidden.text

    unhidden = await client.post(
        f"/listings/{listing_id}/events", data={"event_type": "unhide"}
    )
    assert 'data-saved="1"' in unhidden.text, "unhiding must not unsave"
    assert 'data-hidden="0"' in unhidden.text


async def test_a_view_after_a_hide_leaves_the_listing_hidden(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """`view` records that the listing was looked at; it never re-shows it."""
    listing_id = await _seed(session_factory)

    await client.post(f"/listings/{listing_id}/events", data={"event_type": "hide"})
    viewed = await client.post(f"/listings/{listing_id}/events", data={"event_type": "view"})

    assert viewed.status_code == 200
    assert 'data-hidden="1"' in viewed.text
    # A `view` is not a queue action the row renders, so it swaps the same row back.
    assert "Engineer" not in (await client.get("/")).text

    events = await _events(session_factory, listing_id)
    assert [event.event_type for event in events] == ["hide", "view"]


# --- rejections ---------------------------------------------------------------


async def test_an_event_type_outside_the_vocabulary_is_422_and_writes_nothing(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    listing_id = await _seed(session_factory)

    for bad in ("delete", "promote", "", "SAVE"):
        response = await client.post(
            f"/listings/{listing_id}/events", data={"event_type": bad}
        )
        assert response.status_code == 422, f"{bad!r} must be rejected"

    assert await _events(session_factory, listing_id) == []


async def test_an_unknown_listing_is_404_and_writes_nothing(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _register_sources(session_factory, "linkedin")

    response = await client.post("/listings/9999/events", data={"event_type": "save"})

    assert response.status_code == 404
    assert await _events(session_factory, 9999) == []


async def test_a_caller_supplied_timestamp_is_ignored(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """T-02-37: `occurred_at` is server-side, so an event's time cannot be forged."""
    listing_id = await _seed(session_factory)
    forged = datetime(2030, 1, 1, tzinfo=UTC)
    before = datetime.now(UTC) - timedelta(minutes=1)

    response = await client.post(
        f"/listings/{listing_id}/events",
        data={"event_type": "save", "occurred_at": forged.isoformat()},
    )

    assert response.status_code == 200
    events = await _events(session_factory, listing_id)
    assert len(events) == 1
    stored = events[0].occurred_at
    assert stored is not None
    naive = stored.replace(tzinfo=None) if stored.tzinfo else stored
    assert naive != forged.replace(tzinfo=None)
    assert before.replace(tzinfo=None) <= naive <= datetime.now(UTC).replace(tzinfo=None)


# --- the fragment is the same rendering path ----------------------------------


async def test_the_swapped_fragment_escapes_listing_text(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """T-02-38: one rendering path, so one escaping rule."""
    listing_id = await _seed(session_factory, title=XSS_TITLE)

    response = await client.post(f"/listings/{listing_id}/events", data={"event_type": "save"})

    assert response.status_code == 200
    assert ESCAPED_XSS_TITLE in response.text
    assert XSS_TITLE not in response.text
    assert "|safe" not in response.text


async def test_the_fragment_reports_an_unknown_listing_without_markup_injection(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _register_sources(session_factory, "linkedin")

    response = await client.post("/listings/4242/events", data={"event_type": "hide"})

    assert response.status_code == 404
    assert 'id="listing-row-4242"' in response.text
