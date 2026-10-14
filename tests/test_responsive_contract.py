"""UI-06 / D-160 / D-162 — the phone card-reflow contract, asserted against the app.

Plan 08-02 shipped the responsive work with **shell greps** as its verify
(`grep -c data-label …`). Those die with the session, so nothing in the committed
suite failed if a `data-label` was dropped, a `<th>` reworded, an admin scroll
region removed or the reflow's wrap declaration deleted — a phone would simply
show an unlabelled or mis-headered value and every test would stay green.

This lane commits the same contract as tests.

Why a *matching* check, not a presence check: `content: attr(data-label)` is the
only header a phone ever sees (D-162 — a journey row restacks ALL its desktop
data). A cell whose label is absent or no longer equals its column header is the
failure class, so the assertion is that a rendered row's labels equal its table's
headers in order. (Rendered rows are used wherever a page can be produced offline;
the one conditional column and the two build/template facts use the source, with
the reason stated.)
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from html.parser import HTMLParser
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Source
from app.db.repositories.listing_repo import upsert_listing_source
from app.pipeline.stages import normalise_listing
from app.sources.base import RawListing

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app" / "web" / "templates" / "html"

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


class _JourneyTables(HTMLParser):
    """Collect each table's header texts and its rows' per-cell `data-label`s.

    Only what the contract needs: `<th>` text (thead) and each `<td>`'s
    `data-label` attribute (tbody). Cell *contents* are irrelevant here.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[dict[str, object]] = []
        self._table: dict[str, object] | None = None
        self._in_thead = False
        self._in_th = False
        self._th: list[str] = []
        self._row: list[str | None] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table" and self._table is None:
            self._table = {"class": attributes.get("class") or "", "headers": [], "rows": []}
        elif tag == "thead" and self._table is not None:
            self._in_thead = True
        elif tag == "th" and self._in_thead:
            self._in_th = True
            self._th = []
        elif tag == "tr" and self._table is not None and not self._in_thead:
            self._row = []
        elif tag == "td" and self._row is not None:
            self._row.append(attributes.get("data-label"))

    def handle_endtag(self, tag: str) -> None:
        if tag == "th" and self._in_th:
            self._in_th = False
            assert self._table is not None
            self._table["headers"].append("".join(self._th).strip())  # type: ignore[union-attr]
        elif tag == "thead":
            self._in_thead = False
        elif tag == "tr" and self._row is not None:
            assert self._table is not None
            self._table["rows"].append(self._row)  # type: ignore[union-attr]
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None

    def handle_data(self, data: str) -> None:
        if self._in_th:
            self._th.append(data)


def _tables(html: str) -> list[dict[str, object]]:
    parser = _JourneyTables()
    parser.feed(html)
    parser.close()
    return parser.tables


def _journey_tables(html: str) -> dict[str, dict[str, object]]:
    found = {
        str(table["class"]): table
        for table in _tables(html)
        if "queue-table" in str(table["class"]) or "health-table" in str(table["class"])
    }
    return found


def _assert_rows_restack_the_headers(table: dict[str, object], label: str) -> None:
    """The failure class: a cell whose label is absent or disagrees with its header."""
    headers = table["headers"]
    rows = table["rows"]
    assert headers, f"{label}: the table rendered with no header row"
    assert rows, f"{label}: the table rendered with no data rows — the check would be vacuous"
    for index, row in enumerate(rows):
        assert len(row) == len(headers), (
            f"{label} row {index}: {len(row)} cells against {len(headers)} headers — "
            "a phone would show a value under the wrong header, or none at all (D-162)"
        )
        assert row == headers, (
            f"{label} row {index}: cell labels {row} are not the desktop columns {headers} "
            "— the phone label no longer matches its column header (D-162)"
        )


async def _seed_queue_listing(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    index: int = 1,
    title: str = "Backend Engineer",
) -> int:
    """One source and one queued listing — enough for both journey tables to render."""
    async with session_factory() as session:
        session.add(Source(name="linkedin", display_name="LinkedIn"))
        await session.commit()

    raw = RawListing(
        source="linkedin",  # type: ignore[arg-type]
        source_listing_id=f"linkedin-{index}",
        source_url=f"https://linkedin.example.com/jobs/{index}",
        direct_url=None,
        title=title,
        company_name="Acme",
        location_raw="Dublin, Ireland",
        description="Build the thing.",
        posted_at=date(2026, 10, 1),
    )
    async with session_factory() as session:
        outcome = await upsert_listing_source(
            session, source="linkedin", norm=normalise_listing(raw), run_id=None, now=NOW
        )
        await session.commit()
    return int(outcome.listing_id)


# --- the journey tables restack every desktop column on a phone -----------------


async def test_the_queue_row_restacks_every_desktop_column(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_queue_listing(session_factory)

    response = await client.get("/")

    assert response.status_code == 200
    queue = _journey_tables(response.text)
    assert "queue-table" in queue, "the queue table did not render"
    _assert_rows_restack_the_headers(queue["queue-table"], "queue")


async def test_the_health_row_restacks_every_desktop_column(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_queue_listing(session_factory)

    response = await client.get("/")

    assert response.status_code == 200
    health = _journey_tables(response.text)
    assert "health-table" in health, "the source-health table did not render"
    _assert_rows_restack_the_headers(health["health-table"], "health")


async def test_the_tracker_row_restacks_every_desktop_column(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    listing_id = await _seed_queue_listing(session_factory)
    recorded = await client.post(
        "/applications/record",
        data={"listing_id": str(listing_id), "status": "shortlisted", "notes": "Referred"},
    )
    assert recorded.status_code in (200, 303), recorded.text[:200]

    response = await client.get("/applications")

    assert response.status_code == 200
    tracker = _journey_tables(response.text)
    assert "queue-table" in tracker, "the tracker table did not render"
    _assert_rows_restack_the_headers(tracker["queue-table"], "tracker")


def test_the_conditional_exclusion_column_has_a_matching_label_pair() -> None:
    """The `Excluded by` cell only renders when the queue's excluded predicate is on.

    Rendering it would require an excluded listing; the pair is asserted in the
    source instead, where the two halves live, so a reworded header or label fails.
    """
    row = (TEMPLATES / "_listing_row.html").read_text(encoding="utf-8")
    queue = (TEMPLATES / "queue_list.html").read_text(encoding="utf-8")

    assert 'data-label="Excluded by"' in row
    assert '<th scope="col">Excluded by</th>' in queue


# --- the reflow itself ----------------------------------------------------------


def test_the_phone_reflow_is_authored_in_the_build_input_and_survives_the_build() -> None:
    source = (ROOT / "assets" / "tailwind" / "input.css").read_text(encoding="utf-8")
    assert "@variant max-md" in source, "the phone reflow must be authored as a max-md variant"
    reflow = source[source.index("@variant max-md") :]

    assert ".queue-table" in reflow and ".health-table" in reflow, (
        "the reflow block must cover both journey tables"
    )
    assert "attr(data-label" in reflow, "the label line is what the phone reads"
    assert "overflow-wrap" in reflow, (
        "a long unbroken value must wrap inside its card, not widen the phone page"
    )

    built = (ROOT / "static" / "vendor" / "app.css").read_text(encoding="utf-8")
    assert "@media not all and (min-width:48rem)" in built, "the reflow did not reach the build"
    assert "content:attr(data-label)" in built, "the label rule did not reach the build"
    assert "overflow-wrap:anywhere" in built, "the wrap declaration did not reach the build"


# --- the rest of UI-06: scroll regions and the tap floor ------------------------


@pytest.mark.parametrize(
    ("template", "table_class"),
    [
        ("merges.html", "merges-table"),
        ("runs.html", "runs-table"),
        ("listing_detail.html", "factor-table"),
    ],
)
def test_every_admin_table_keeps_a_labelled_keyboard_scroll_region(
    template: str, table_class: str
) -> None:
    text = (TEMPLATES / template).read_text(encoding="utf-8")

    assert 'class="table-scroll"' in text
    assert 'role="region"' in text, "role=region requires the accessible name"
    assert 'tabindex="0"' in text, "tabindex=0 is what makes the region keyboard-scrollable"
    assert 'aria-label="' in text
    assert text.index('class="table-scroll"') < text.index(f'class="{table_class}"'), (
        "the scroll region must wrap the table, not sit beside it"
    )


def test_every_nav_link_carries_the_tap_floor() -> None:
    text = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    nav_links = [line for line in text.splitlines() if 'class="nav-link' in line]

    assert len(nav_links) == 7, f"expected the seven journey nav links, found {len(nav_links)}"
    assert all("touch-target" in line for line in nav_links)


@pytest.mark.parametrize(
    "template",
    [
        "queue_list.html",  # the queue pager
        "applications_list.html",  # the tracker pager
        "_application_row.html",  # the per-row history summary
        "_application_history.html",  # the shared history summary
        "_screening_drafts.html",  # the Copy-answer button
    ],
)
def test_the_compact_journey_controls_carry_the_tap_floor(template: str) -> None:
    assert "touch-target" in (TEMPLATES / template).read_text(encoding="utf-8")
