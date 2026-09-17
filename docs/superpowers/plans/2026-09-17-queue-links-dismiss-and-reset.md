# Queue Posting Links, Dismiss, and the Guarded Data Reset — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user reach the actual job posting from a queue row, clear the queue in one action, and wipe the fetched corpus behind a type-to-confirm + automatic snapshot guard.

**Architecture:** Three additions that each extend an existing seam rather than adding a new one. (1) The queue row grows two precomputed fields — `url` and `source_links` — filled by the *existing* single batched `listing_sources` read in `queue_repo._enrich`, so nothing becomes N+1 and no template computes anything. (2) `Dismiss` appends one `hide` event per queued listing through `event_repo`, reusing the append-only event log the Save/Hide buttons already write, and mirrors `queue_mark_seen`'s read-after-write so the returned fragment already shows the empty queue. (3) A new `/settings` router owns a destructive reset that refuses unless every guard passes, snapshots the live database with `VACUUM INTO` *before* deleting anything, and then deletes in a fixed child-first order.

**Tech Stack:** Python 3.13 (image), FastAPI, SQLAlchemy 2.0 + SQLite (WAL, `foreign_keys=ON` at runtime), Alembic, Jinja2 + HTMX 2.x + Alpine 3.x + Tailwind CSS 4 (CLI build), pytest + httpx ASGI transport.

**Spec:** `docs/superpowers/specs/2026-09-17-queue-links-dismiss-and-reset-design.md`

## Global Constraints

- **No new runtime dependency.** The phase added exactly one (`rapidfuzz==3.14.6`); a reset uses stdlib `sqlite3` and `VACUUM INTO`, nothing else.
- **Do not write `data/`.** It is the operator's live production database. Every test runs against the pytest temp DB via the `client`/`session_factory` fixtures.
- **Every new route declares `user: User = Depends(current_user)`.** `tests/test_auth_seam.py` fails on any route in the dependency tree without it.
- **No new template class without a stylesheet rule.** `tests/test_stylesheet_coverage.py` requires every literal class token in every `class="..."` to match a rule in `static/vendor/app.css`, unless it is in the justified `EXEMPT_CLASSES` map. Adding a class therefore means editing `assets/tailwind/input.css` **and** rebuilding `static/vendor/app.css` (and committing it).
- **Tailwind rebuild command** (must be run and the output committed whenever `input.css` changes):
  `npm install --no-save --no-audit --no-fund htmx.org@2.0.10 alpinejs@3.17.3 tailwindcss@4.3.3 @tailwindcss/cli@4.3.3`
  then `./node_modules/.bin/tailwindcss -i ./assets/tailwind/input.css -o ./static/vendor/app.css --minify`
- **Test runner is `.venv/bin/python -m pytest -q`.** Never `.venv-host/bin/pytest` (stale shebang, gnu/musl-broken `pydantic_core`).
- **Lint is `.venv/bin/python -m ruff check app tests`.**
- **No `|safe`, no `Markup`, no `autoescape=False` in any template.** Jinja autoescape is the only escaping in play; listing text and company names are untrusted board data. Where a query string must ride on an action URL, it is passed as a plain context string exactly as `queue_list.html` already does with `queue_query`.
- **Repository functions never commit; the route owns the commit.** `read_queue`, `read_row`, `state_for_listings` and `hide_listings` all follow this.
- **Run everything from `/workspace/job-search`** — the agent's shell cwd may be a different project.
- Claimed in every commit: conventional-commit subject, e.g. `feat(queue): …`, `fix(ui): …`, `test(settings): …`.

---

### Task 1: Queue row provenance as data

**Lane:** @fixer

**Files:**
- Modify: `app/db/repositories/queue_repo.py` (constants block ~:82-115, `QueueRow` ~:165-179, `_enrich` ~:370-462, `__all__` ~:530-541)
- Test: `tests/db/test_queue_row_links.py` (create)

**Interfaces:**
- Consumes: `ListingSource` (already imported by `queue_repo`), `Listing.canonical_url`.
- Produces:
  - `queue_repo.SourceLink` — frozen dataclass `SourceLink(source: str, url: str, employer_url: str | None = None)`
  - `QueueRow.url: str | None` and `QueueRow.source_links: tuple[SourceLink, ...]`
  - `read_queue(...)` / `read_row(...)` populate both; `QueueRow.sources` stays the tuple of source names it is today.

- [ ] **Step 1: Write the failing test**

Create `tests/db/test_queue_row_links.py`:

```python
"""Provenance as data: every queue row carries the posting URL and its per-source links.

The queue row must never make the template do work, and the links must not cost a
second query per row. `employer_url` is populated ONLY when it differs from the board
URL — that single guard is what makes an Indeed row (where the two columns differ,
155/155 in the live corpus) offer the employer's own posting while a LinkedIn row
(where they are identical, 0/128) renders one link.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime

from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Listing, ListingSource, Source
from app.db.repositories.listing_repo import upsert_listing_source
from app.db.repositories.queue_repo import QueueQuery, SourceLink, read_queue
from app.pipeline.stages import normalise_listing
from app.sources.base import RawListing

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


@contextmanager
def _statements_matching(engine, needle: str) -> Iterator[list[str]]:
    """Record every statement whose SQL contains `needle`, for one block."""
    seen: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        if needle in statement:
            seen.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", _record)
    try:
        yield seen
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _record)


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
    source: str = "linkedin",
    index: int,
    title: str = "Backend Engineer",
    canonical_url: str | None = None,
    canonical_source_url: str | None = None,
) -> int:
    """Seed one listing through the real ingestion path, then pin the URL columns.

    Ingestion is used so every NOT NULL column and every normalised field is filled
    by the code that owns that mapping. The URL columns are then set explicitly,
    because this lane is about RENDERING provenance, not about how an adapter fills
    those columns (covered by `tests/db/test_two_key_upsert.py`).
    """
    raw = RawListing(
        source=source,  # type: ignore[arg-type]
        source_listing_id=f"{source}-{index}",
        source_url=f"https://{source}.example.com/jobs/{index}",
        direct_url=None,
        title=title,
        company_name="Acme",
        location_raw="Dublin, Ireland",
        description="Build the thing.",
        posted_at=date(2026, 9, 1),
    )
    norm = normalise_listing(raw)
    async with session_factory() as session:
        await upsert_listing_source(session, source=source, norm=norm, run_id=None, now=NOW)
        await session.commit()

    async with session_factory() as session:
        listing_id = int(
            await session.scalar(
                select(Listing.id).where(Listing.canonical_url == norm.canonical_url)
            )
        )
        if canonical_url is not None:
            listing = await session.get(Listing, listing_id)
            assert listing is not None
            listing.canonical_url = canonical_url
        if canonical_source_url is not None:
            link = await session.scalar(
                select(ListingSource).where(ListingSource.listing_id == listing_id)
            )
            assert link is not None
            link.canonical_source_url = canonical_source_url
        await session.commit()
    return listing_id


async def _read_one(
    session_factory: async_sessionmaker[AsyncSession], listing_id: int
):
    async with session_factory() as session:
        page = await read_queue(
            session,
            query=QueueQuery(),
            now=NOW,
            stale_after_days=14,
            watermark=None,
        )
    return next(row for row in page.rows if row.id == listing_id)


async def test_row_carries_the_canonical_url(session_factory) -> None:
    await _register_sources(session_factory, "linkedin")
    listing_id = await _seed_listing(
        session_factory, index=1, canonical_url="https://boards.example.com/job/1"
    )

    row = await _read_one(session_factory, listing_id)

    assert row.url == "https://boards.example.com/job/1"


async def test_a_listing_without_a_canonical_url_reports_none(session_factory) -> None:
    await _register_sources(session_factory, "linkedin")
    listing_id = await _seed_listing(session_factory, index=2, canonical_url="")

    row = await _read_one(session_factory, listing_id)

    assert row.url is None


async def test_one_link_per_source_with_the_board_url(session_factory) -> None:
    await _register_sources(session_factory, "linkedin")
    listing_id = await _seed_listing(session_factory, index=3)

    row = await _read_one(session_factory, listing_id)

    assert row.source_links == (
        SourceLink(source="linkedin", url="https://linkedin.example.com/jobs/3"),
    )
    assert row.sources == ("linkedin",)


async def test_employer_url_is_omitted_when_it_matches_the_board_url(
    session_factory,
) -> None:
    """The LinkedIn shape: both columns hold the same /jobs/view/<id> URL."""
    await _register_sources(session_factory, "linkedin")
    listing_id = await _seed_listing(
        session_factory,
        index=4,
        canonical_source_url="https://linkedin.example.com/jobs/4",
    )

    row = await _read_one(session_factory, listing_id)

    assert row.source_links[0].employer_url is None


async def test_employer_url_is_kept_when_it_differs(session_factory) -> None:
    """The Indeed shape: the board page and the employer's own posting both exist."""
    await _register_sources(session_factory, "indeed")
    listing_id = await _seed_listing(
        session_factory,
        source="indeed",
        index=5,
        canonical_source_url="https://employer.example.com/careers/5",
    )

    row = await _read_one(session_factory, listing_id)

    assert row.source_links == (
        SourceLink(
            source="indeed",
            url="https://indeed.example.com/jobs/5",
            employer_url="https://employer.example.com/careers/5",
        ),
    )


async def test_a_second_source_row_is_a_second_link(session_factory) -> None:
    await _register_sources(session_factory, "linkedin", "indeed")
    listing_id = await _seed_listing(session_factory, index=6)
    async with session_factory() as session:
        first = await session.scalar(
            select(ListingSource).where(ListingSource.listing_id == listing_id)
        )
        assert first is not None
        session.add(
            ListingSource(
                listing_id=listing_id,
                source="indeed",
                source_listing_id="indeed-6",
                source_url="https://indeed.example.com/jobs/6",
                canonical_source_url="https://employer.example.com/careers/6",
                first_seen_at=first.first_seen_at,
                last_seen_at=first.last_seen_at,
                raw_hash="hash-6",
            )
        )
        await session.commit()

    row = await _read_one(session_factory, listing_id)

    assert [link.source for link in row.source_links] == ["indeed", "linkedin"]
    assert row.sources == ("indeed", "linkedin")


async def test_the_page_reads_provenance_in_one_query(
    session_factory, db_engine
) -> None:
    await _register_sources(session_factory, "linkedin")
    for index in range(7, 12):
        await _seed_listing(session_factory, index=index)

    with _statements_matching(db_engine, "FROM listing_sources") as statements:
        async with session_factory() as session:
            await read_queue(
                session,
                query=QueueQuery(limit=25),
                now=NOW,
                stale_after_days=14,
                watermark=None,
            )

    assert len(statements) == 1, statements
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest -q tests/db/test_queue_row_links.py`

Expected: collection error — `ImportError: cannot import name 'SourceLink' from 'app.db.repositories.queue_repo'`.

- [ ] **Step 3: Add the dataclass and the two row fields**

In `app/db/repositories/queue_repo.py`, immediately after the `QueueRule` dataclass, add:

```python
@dataclass(frozen=True)
class SourceLink:
    """One board's provenance for a listing, as the row renders it.

    `url` is the board's own page for this posting (`listing_sources.source_url`).
    `employer_url` is the employer/ATS page (`listing_sources.canonical_source_url`)
    and is populated ONLY when it differs from `url`. That single guard is what makes
    the rendering correct with no source-specific branching: a LinkedIn row renders
    one link, an Indeed row renders the board page plus the employer's own posting.
    """

    source: str
    url: str
    employer_url: str | None = None
```

Extend `QueueRow` — add these two fields after `rules`, leaving every existing field untouched:

```python
    #: The posting page (`listings.canonical_url`), or None when the row has none.
    url: str | None = None
    #: One entry per `listing_sources` row, so a merge never hides half its provenance.
    source_links: tuple[SourceLink, ...] = ()
```

- [ ] **Step 4: Widen the existing batched read in `_enrich`**

Replace the source-name batch read in `_enrich` (the `grouped: dict[int, list[str]]` block) with:

```python
    grouped: dict[int, list[SourceLink]] = {}
    for listing_id, source, source_url, canonical_source_url in (
        await session.execute(
            select(
                ListingSource.listing_id,
                ListingSource.source,
                ListingSource.source_url,
                ListingSource.canonical_source_url,
            )
            .where(ListingSource.listing_id.in_(list(ids)))
            .order_by(ListingSource.listing_id, ListingSource.source)
        )
    ).all():
        board_url = str(source_url or "")
        employer_url = str(canonical_source_url or "")
        grouped.setdefault(int(listing_id), []).append(
            SourceLink(
                source=str(source),
                url=board_url,
                employer_url=(
                    employer_url
                    if employer_url and employer_url != board_url
                    else None
                ),
            )
        )
```

This stays **one** query for the whole page — the four columns come from the same row.

- [ ] **Step 5: Feed the new fields into the row**

In the `for listing_id in ids:` loop of `_enrich`, just before the `rows.append(` call, add:

```python
        links = tuple(grouped.get(listing_id, ()))
```

and change two keyword arguments inside that `QueueRow(...)` construction:

```python
                sources=tuple(link.source for link in links),
                url=listing.canonical_url or None,
                source_links=links,
```

(The existing `sources=tuple(grouped.get(listing_id, ()))` line is replaced by the `sources=` line above.)

- [ ] **Step 6: Export the dataclass**

Add `"SourceLink",` to `queue_repo.__all__` (alphabetically, after `"QueueRule",`).

- [ ] **Step 7: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q tests/db/test_queue_row_links.py`
Expected: `7 passed`.

- [ ] **Step 8: Run the surrounding lanes by hand-touch and then the full suite**

Run: `.venv/bin/python -m pytest -q tests/db tests/api`
Expected: all pass — `_enrich` is the shared path behind `read_queue` and `read_row`.

Run: `.venv/bin/python -m pytest -q`
Expected: full suite green (baseline 660 passed, 2 deselected).

- [ ] **Step 9: Lint and commit**

```bash
.venv/bin/python -m ruff check app tests
git add app/db/repositories/queue_repo.py tests/db/test_queue_row_links.py
git commit -m "feat(queue): carry the posting URL and per-source links on every row"
```

---

### Task 2: Render the posting links on the queue row

**Lane:** @designer (visual layer) — the repo work from Task 1 is already done.

**Files:**
- Modify: `app/web/templates/html/_listing_row.html` (title cell :22, source cell :38)
- Modify: `assets/tailwind/input.css` (append to the existing `@layer components` block)
- Modify: `static/vendor/app.css` (rebuilt, committed)
- Modify: `tests/pipeline/test_ingest_e2e.py:185,189` (broaden the pinned extraction)
- Test: `tests/api/test_queue_links.py` (create)

**Interfaces:**
- Consumes: `QueueRow.url`, `QueueRow.source_links`, `SourceLink.employer_url` from Task 1.
- Produces: nothing new for later tasks. The `listing-title` **cell class stays exactly as it is** (`<td class="listing-title">`) because a Phase-1 test reads it back.

- [ ] **Step 1: Write the failing tests**

Create `tests/api/test_queue_links.py`. It reuses the Task 1 seed helper shape, so paste it in rather than importing across test packages:

```python
"""The queue row reaches the posting: title anchor plus per-source links (QUEUE-06).

Two shapes are asserted, because they are what the live corpus actually contains:
an Indeed row whose employer URL differs from the board URL (155/155 differ) and a
LinkedIn row whose two URL columns are identical (0/128 differ).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Listing, ListingSource, Source
from app.db.repositories.listing_repo import upsert_listing_source
from app.pipeline.stages import normalise_listing
from app.sources.base import RawListing

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


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
    source: str = "linkedin",
    index: int,
    title: str = "Backend Engineer",
    canonical_url: str | None = None,
    canonical_source_url: str | None = None,
) -> int:
    raw = RawListing(
        source=source,  # type: ignore[arg-type]
        source_listing_id=f"{source}-{index}",
        source_url=f"https://{source}.example.com/jobs/{index}",
        direct_url=None,
        title=title,
        company_name="Acme",
        location_raw="Dublin, Ireland",
        description="Build the thing.",
        posted_at=date(2026, 9, 1),
    )
    norm = normalise_listing(raw)
    async with session_factory() as session:
        await upsert_listing_source(session, source=source, norm=norm, run_id=None, now=NOW)
        await session.commit()

    async with session_factory() as session:
        listing_id = int(
            await session.scalar(
                select(Listing.id).where(Listing.canonical_url == norm.canonical_url)
            )
        )
        if canonical_url is not None:
            listing = await session.get(Listing, listing_id)
            assert listing is not None
            listing.canonical_url = canonical_url
        if canonical_source_url is not None:
            link = await session.scalar(
                select(ListingSource).where(ListingSource.listing_id == listing_id)
            )
            assert link is not None
            link.canonical_source_url = canonical_source_url
        await session.commit()
    return listing_id


async def test_the_title_links_to_the_posting(client, session_factory) -> None:
    await _register_sources(session_factory, "linkedin")
    await _seed_listing(
        session_factory, index=1, canonical_url="https://boards.example.com/job/1"
    )

    response = await client.get("/")

    assert response.status_code == 200
    assert (
        '<a class="listing-title-link" href="https://boards.example.com/job/1"'
        ' target="_blank" rel="noopener noreferrer">Backend Engineer</a>' in response.text
    )


async def test_a_listing_without_a_url_renders_a_plain_title(
    client, session_factory
) -> None:
    await _register_sources(session_factory, "linkedin")
    await _seed_listing(session_factory, index=2, canonical_url="")

    response = await client.get("/")

    assert '<td class="listing-title">Backend Engineer</td>' in response.text


async def test_an_indeed_row_offers_the_board_and_the_employer_link(
    client, session_factory
) -> None:
    await _register_sources(session_factory, "indeed")
    await _seed_listing(
        session_factory,
        source="indeed",
        index=3,
        canonical_source_url="https://employer.example.com/careers/3",
    )

    response = await client.get("/")

    assert (
        '<a class="source-link" href="https://indeed.example.com/jobs/3"'
        ' target="_blank" rel="noopener noreferrer">indeed</a>' in response.text
    )
    assert (
        '<a class="source-apply" href="https://employer.example.com/careers/3"'
        ' target="_blank" rel="noopener noreferrer">Apply</a>' in response.text
    )


async def test_a_linkedin_row_renders_one_link_and_no_apply_link(
    client, session_factory
) -> None:
    await _register_sources(session_factory, "linkedin")
    await _seed_listing(
        session_factory,
        index=4,
        canonical_source_url="https://linkedin.example.com/jobs/4",
    )

    response = await client.get("/")

    assert 'class="source-apply"' not in response.text
    assert (
        '<a class="source-link" href="https://linkedin.example.com/jobs/4"'
        ' target="_blank" rel="noopener noreferrer">linkedin</a>' in response.text
    )


async def test_a_merged_listing_renders_each_source(client, session_factory) -> None:
    await _register_sources(session_factory, "linkedin", "indeed")
    listing_id = await _seed_listing(session_factory, index=5)
    async with session_factory() as session:
        first = await session.scalar(
            select(ListingSource).where(ListingSource.listing_id == listing_id)
        )
        assert first is not None
        session.add(
            ListingSource(
                listing_id=listing_id,
                source="indeed",
                source_listing_id="indeed-5",
                source_url="https://indeed.example.com/jobs/5",
                canonical_source_url="https://employer.example.com/careers/5",
                first_seen_at=first.first_seen_at,
                last_seen_at=first.last_seen_at,
                raw_hash="hash-5",
            )
        )
        await session.commit()

    response = await client.get("/")

    assert "https://linkedin.example.com/jobs/5" in response.text
    assert "https://indeed.example.com/jobs/5" in response.text
    assert "https://employer.example.com/careers/5" in response.text


async def test_every_external_link_is_target_blank_and_rel_noopener(
    client, session_factory
) -> None:
    await _register_sources(session_factory, "indeed")
    await _seed_listing(
        session_factory,
        source="indeed",
        index=6,
        canonical_url="https://boards.example.com/job/6",
        canonical_source_url="https://employer.example.com/careers/6",
    )

    response = await client.get("/")

    for anchor in re.findall(r"<a [^>]*href=\"https?://[^\"]+\"[^>]*>", response.text):
        assert 'target="_blank"' in anchor, anchor
        assert 'rel="noopener noreferrer"' in anchor, anchor
```

Add `import re` to that file's imports.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest -q tests/api/test_queue_links.py`
Expected: 6 failures, each `AssertionError` on a missing anchor — the template still renders `{{ row.title }}` and `{{ row.sources | join(", ") }}`.

- [ ] **Step 3: Render the title as a link, and the sources as links**

In `app/web/templates/html/_listing_row.html`, replace the title cell:

```html
  <td class="listing-title">{% if row.url %}<a class="listing-title-link" href="{{ row.url }}" target="_blank" rel="noopener noreferrer">{{ row.title }}</a>{% else %}{{ row.title }}{% endif %}</td>
```

and replace the source cell:

```html
  <td class="listing-source">
    {% for link in row.source_links %}<a class="source-link" href="{{ link.url }}" target="_blank" rel="noopener noreferrer">{{ link.source }}</a>{% if link.employer_url %} <a class="source-apply" href="{{ link.employer_url }}" target="_blank" rel="noopener noreferrer">Apply</a>{% endif %}{% if not loop.last %}, {% endif %}{% endfor %}
  </td>
```

Update that file's header comment to record the new contract: the title anchor and the source links come from the row's precomputed `url`/`source_links`; `rel="noopener noreferrer"` is mandatory on every external anchor because these URLs come from a job board; the `listing-title` cell class is unchanged because a Phase-1 determinism test reads it back.

- [ ] **Step 4: Add the three stylesheet rules and rebuild**

Append to the existing `@layer components` block in `assets/tailwind/input.css`:

```css
/* Queue row provenance links (2026-09-17). Tailwind's preflight sets
   `a { color: inherit; text-decoration: inherit }`, so without these rules the
   posting links would be indistinguishable from the text around them. */
.listing-title-link {
  color: var(--color-accent);
  text-decoration: none;
}
.listing-title-link:hover {
  text-decoration: underline;
}
.source-link {
  color: var(--color-accent);
  text-decoration: none;
}
.source-link:hover {
  text-decoration: underline;
}
.source-apply {
  display: inline-block;
  padding: 0.05rem 0.4rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 0.8rem;
  color: var(--color-accent);
  text-decoration: none;
}
.source-apply:hover {
  background-color: var(--color-surface);
}
```

Rebuild and commit the output:

```bash
npm install --no-save --no-audit --no-fund htmx.org@2.0.10 alpinejs@3.17.3 tailwindcss@4.3.3 @tailwindcss/cli@4.3.3
./node_modules/.bin/tailwindcss -i ./assets/tailwind/input.css -o ./static/vendor/app.css --minify
```

- [ ] **Step 5: Broaden the pinned title extraction**

`tests/pipeline/test_ingest_e2e.py` reads the queue back with
`re.findall(r'<td class="listing-title">([^<]+)</td>', ...)` at lines 185 and 189. The anchor makes that pattern fail. In **both** places change the pattern to tolerate an optional anchor while asserting exactly the same titles:

```python
    titles = re.findall(r'<td class="listing-title">(?:<a [^>]*>)?([^<]+)', first.text)
```

Add a one-line comment above the first occurrence: the cell now optionally wraps the title in the posting anchor, so the extraction tolerates the anchor rather than dropping it; the asserted titles are unchanged.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q tests/api/test_queue_links.py tests/pipeline/test_ingest_e2e.py tests/test_stylesheet_coverage.py`

Expected: all pass. If `test_stylesheet_coverage.py` reports an unmatched class, a rule from Step 4 is missing or misspelled — fix `input.css` and rebuild rather than adding an exemption.

- [ ] **Step 7: Full suite, lint, commit**

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check app tests
git add app/web/templates/html/_listing_row.html assets/tailwind/input.css \
        static/vendor/app.css tests/api/test_queue_links.py tests/pipeline/test_ingest_e2e.py
git commit -m "feat(ui): link each queue row to the posting and the employer page"
```

---

### Task 3: Dismiss the whole queue

**Lane:** @fixer

**Files:**
- Modify: `app/db/repositories/event_repo.py` (add `hide_listings`; extend `__all__`)
- Modify: `app/web/routes.py` (add `POST /queue/dismiss`; extend `__all__` if needed)
- Modify: `app/web/templates/html/queue_list.html` (the button beside `#queue-mark-seen`)
- Test: `tests/api/test_queue_dismiss.py` (create)

**Interfaces:**
- Consumes: `event_repo.append_event`, `event_repo.EVENT_TYPES`, `routes._read_queue_page`, `routes._queue_context`, `read_queue` from Task 1.
- Produces: `event_repo.hide_listings(session, *, listing_ids: Sequence[int], occurred_at: datetime) -> int` (returns the number of events appended); route `POST /queue/dismiss`.

- [ ] **Step 1: Write the failing tests**

Create `tests/api/test_queue_dismiss.py`:

```python
"""Dismiss the queue: one hide event per queued listing, and the fragment comes back empty.

Scope is "what the user sees with no filters applied" — NOT "every row in `listings`".
An already-hidden listing must not gain a second event, and an absorbed merge twin must
never be dismissed (it is not in the queue).
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Listing, ListingEvent, Source
from app.db.repositories.listing_repo import upsert_listing_source
from app.pipeline.stages import normalise_listing
from app.sources.base import RawListing

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


async def _register_sources(
    session_factory: async_sessionmaker[AsyncSession], *names: str
) -> None:
    async with session_factory() as session:
        for name in names:
            session.add(Source(name=name, display_name=name.title()))
        await session.commit()


async def _seed_listing(
    session_factory: async_sessionmaker[AsyncSession], *, index: int
) -> int:
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
    norm = normalise_listing(raw)
    async with session_factory() as session:
        await upsert_listing_source(
            session, source="linkedin", norm=norm, run_id=None, now=NOW
        )
        await session.commit()
    async with session_factory() as session:
        return int(
            await session.scalar(
                select(Listing.id).where(Listing.canonical_url == norm.canonical_url)
            )
        )


async def _hide_count(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(ListingEvent)
                .where(ListingEvent.event_type == "hide")
            )
            or 0
        )


async def test_dismiss_appends_one_hide_event_per_queued_listing(
    client, session_factory
) -> None:
    await _register_sources(session_factory, "linkedin")
    for index in (1, 2, 3):
        await _seed_listing(session_factory, index=index)

    response = await client.post("/queue/dismiss")

    assert response.status_code == 200
    assert await _hide_count(session_factory) == 3
    assert "No listings yet" in response.text


async def test_dismissed_listings_stay_hidden_on_a_re_read(client, session_factory) -> None:
    await _register_sources(session_factory, "linkedin")
    await _seed_listing(session_factory, index=4)

    await client.post("/queue/dismiss")
    re_read = await client.get("/queue/list")

    assert 'id="listing-row-' not in re_read.text


async def test_dismiss_covers_the_whole_queue_not_just_the_page(
    client, session_factory
) -> None:
    """The page size is 25; the queue here is 30. A page-scoped dismiss would leave 5."""
    await _register_sources(session_factory, "linkedin")
    for index in range(10, 40):
        await _seed_listing(session_factory, index=index)

    await client.post("/queue/dismiss")

    assert await _hide_count(session_factory) == 30


async def test_dismiss_ignores_the_text_filter_but_not_the_hidden_gate(
    client, session_factory
) -> None:
    """`?q=` must not narrow the dismissal; already-hidden rows must not be re-hidden."""
    await _register_sources(session_factory, "linkedin")
    first = await _seed_listing(session_factory, index=50)
    await _seed_listing(session_factory, index=51)

    # Hide one listing by hand, then dismiss with a text filter set.
    await client.post(f"/listings/{first}/events", data={"event_type": "hide"})
    assert await _hide_count(session_factory) == 1

    await client.post("/queue/dismiss?q=Backend")

    # The hand-hidden listing keeps exactly one event; the visible one gains one.
    assert await _hide_count(session_factory) == 2


async def test_an_empty_queue_is_a_no_op(client, session_factory) -> None:
    response = await client.post("/queue/dismiss")

    assert response.status_code == 200
    assert await _hide_count(session_factory) == 0


async def test_dismiss_does_not_touch_an_absorbed_twin(client, session_factory) -> None:
    """A twin absorbed by a merge is out of the queue and must never be dismissed."""
    await _register_sources(session_factory, "linkedin", "indeed")
    survivor = await _seed_listing(session_factory, index=60)
    twin = await _seed_listing(session_factory, index=61)
    async with session_factory() as session:
        session.add(
            ListingDupe(
                listing_id=survivor,
                dup_listing_id=twin,
                method="fuzzy",
                score=0.97,
                merged_at=NOW,
            )
        )
        await session.commit()

    await client.post("/queue/dismiss")

    assert await _hide_count(session_factory) == 1
```

Add `ListingDupe` to the model imports, and confirm the `ListingDupe` constructor's required columns against `app/db/models.py` (`:195`) before running — if it needs the run that merged the pair, pass `run_id=None` and let the nullable column carry it.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest -q tests/api/test_queue_dismiss.py`
Expected: 404 on every `POST /queue/dismiss`.

- [ ] **Step 3: Add `hide_listings` to the event repository**

In `app/db/repositories/event_repo.py`, after `append_event`, add:

```python
async def hide_listings(
    session: AsyncSession,
    *,
    listing_ids: Sequence[int],
    occurred_at: datetime,
) -> int:
    """Append one `hide` event per listing. Returns how many were appended.

    Reuses the existing `hide` event rather than minting a `dismiss` type: the
    projected `hidden` flag and the per-listing `Unhide` control already work, and a
    seventh event type would need a migration to widen
    `ck_listing_events_event_type`. The accepted cost is that a bulk dismissal is
    indistinguishable in the audit trail from hiding each listing by hand.

    One event per listing, so the log stays per-listing and `Unhide` can reverse a
    single row. The insert goes through `append_event`, so the SAVEPOINT, the
    allow-list check and the `occurred_at` contract all apply unchanged.
    """
    ids = sorted({int(listing_id) for listing_id in listing_ids})
    for listing_id in ids:
        await append_event(
            session, listing_id=listing_id, event_type="hide", now=occurred_at
        )
    return len(ids)
```

Add `"hide_listings",` to `event_repo.__all__`.

- [ ] **Step 4: Add the route**

In `app/web/routes.py`, after `queue_mark_seen`, add:

```python
@router.post("/queue/dismiss", response_class=HTMLResponse)
async def queue_dismiss(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Hide every listing the user can currently see, and return the empty fragment.

    Scope is the queue predicate with the free-text search dropped: what the user
    would see with an empty search box and no toggles. It is deliberately NOT "every
    row in `listings`" — an already-hidden listing must not gain a second event, and
    an absorbed merge twin must never be dismissed.

    The page is read AFTER the write, so the returned fragment already shows the empty
    queue; otherwise Dismiss would look like a no-op until the next reload.
    """
    now = datetime.now(UTC)
    page = await _read_queue_page(
        session,
        request.query_params,
        now=now,
        watermark=await state_repo.get_watermark(session),
    )
    if page.rows:
        await event_repo.hide_listings(
            session,
            listing_ids=[row.id for row in page.rows],
            occurred_at=now,
        )
        await session.commit()

    refreshed = await _read_queue_page(
        session,
        request.query_params,
        now=now,
        watermark=await state_repo.get_watermark(session),
    )
    return templates.TemplateResponse(request, LIST_TEMPLATE, _queue_context(refreshed))
```

The queue page size is 25, so `page.rows` is one page. To dismiss the queue rather than a page, build the id list from a *page-sized* read with the page limit raised to the queue total. Do that inside the route:

```python
    ids = await _queued_listing_ids(session, request.query_params, now=now)
```

and add, beside `_read_queue_page`:

```python
async def _queued_listing_ids(
    session: AsyncSession, params: Mapping[str, str], *, now: datetime
) -> list[int]:
    """Every id the current predicate matches, not just the first page.

    Dismiss is a whole-queue action, so it must not inherit the page limit the
    fragment uses. The predicate itself is the shared `parse_queue_query`, so this
    cannot drift from what the table shows; only the free-text search is dropped,
    because a dismissal scoped to typed text would be ambiguous.
    """
    query = parse_queue_query(params)
    page = await read_queue(
        session,
        query=replace(query, q=None, offset=0, limit=query.limit),
        now=now,
        stale_after_days=settings.stale_after_days,
        watermark=await state_repo.get_watermark(session),
    )
    return [row.id for row in page.rows]
```

Because `QueueQuery` is a frozen dataclass, `dataclasses.replace` is the way to raise the limit. Import `replace` from `dataclasses` and pass an explicit large limit rather than the page size:

```python
        query=replace(query, q=None, offset=0, limit=_DISMISS_LIMIT),
```

with a module constant near `LIST_TEMPLATE`:

```python
#: Dismiss reads the whole queue in one pass. Bounded so a pathological corpus cannot
#: build an unbounded IN list; 10_000 is far above any real queue and the queue's own
#: count is surfaced on the page.
_DISMISS_LIMIT = 10_000
```

Use `ids = await _queued_listing_ids(...)` in place of the first `_read_queue_page`, and guard on `if ids:`.

- [ ] **Step 5: Add the button**

In `app/web/templates/html/queue_list.html`, immediately after the `#queue-mark-seen` button, add:

```html
{# Dismiss is the whole-queue counterpart to Save/Hide: it appends one `hide` event per
   queued listing. It carries the current predicate set so the refreshed fragment keeps
   the user's filters, and it swaps the fragment's CONTENTS for the same reason
   Mark all as seen does — `#queue-list` lives in queue.html. #}
<button type="button"
        id="queue-dismiss"
        hx-post="/queue/dismiss?{{ page.query.query_string() }}"
        hx-target="#queue-list"
        hx-swap="innerHTML"
        hx-confirm="Dismiss every listing currently in the queue?">
  Dismiss all {{ count }} queued listings
</button>
```

No new class is introduced, so no stylesheet change is needed — the base `button` rule already covers it.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q tests/api/test_queue_dismiss.py`
Expected: `6 passed`.

- [ ] **Step 7: Full suite, lint, commit**

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check app tests
git add app/db/repositories/event_repo.py app/web/routes.py \
        app/web/templates/html/queue_list.html tests/api/test_queue_dismiss.py
git commit -m "feat(queue): dismiss the whole queue with one action"
```

---

### Task 4: The `/settings` page

**Lane:** @designer

**Files:**
- Create: `app/api/settings.py`
- Create: `app/web/templates/html/settings.html`
- Modify: `app/main.py` (import + `include_router`)
- Modify: `app/web/templates/html/base.html` (fifth nav link)
- Modify: `assets/tailwind/input.css` + `static/vendor/app.css` (rebuild)
- Test: `tests/api/test_settings_page.py` (create)

**Interfaces:**
- Consumes: `app.api.searches.read_form` (the stdlib urlencoded parser — `python-multipart` is deliberately not a dependency, so `request.form()` is unusable), `app.api.deps.current_user`, `app.db.session.get_session`, `app.web.template_env.make_templates`.
- Produces: `settings.router`; `GET /settings`; the module-level constants `RESET_DELETE_ORDER`, `RESET_KEPT_TABLES`, `RESET_CONFIRM_TOKEN`, `SETTINGS_TEMPLATE`; helper `_settings_context(session, *, banner=None, error=False)` returning the template context. Task 5 adds `POST /settings/reset` to this same router.

- [ ] **Step 1: Write the failing test**

Create `tests/api/test_settings_page.py`:

```python
"""The settings page exists, is reachable from the nav, and states what a reset does."""

from __future__ import annotations

from app.api.settings import RESET_CONFIRM_TOKEN, RESET_DELETE_ORDER, RESET_KEPT_TABLES


async def test_the_settings_page_renders(client) -> None:
    response = await client.get("/settings")

    assert response.status_code == 200
    assert "Reset queue data" in response.text
    assert 'id="danger-zone"' in response.text


async def test_the_nav_reaches_settings(client) -> None:
    response = await client.get("/settings")

    assert '<a class="nav-link nav-current" href="/settings"' in response.text


async def test_the_page_names_the_confirm_token(client) -> None:
    response = await client.get("/settings")

    assert RESET_CONFIRM_TOKEN in response.text
    assert 'name="confirm"' in response.text


async def test_the_page_states_what_is_deleted_and_kept(client) -> None:
    response = await client.get("/settings")

    for table in RESET_DELETE_ORDER:
        assert table in response.text, table
    for table in RESET_KEPT_TABLES:
        assert table in response.text, table
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest -q tests/api/test_settings_page.py`
Expected: `ModuleNotFoundError: No module named 'app.api.settings'`.

- [ ] **Step 3: Write the router**

Create `app/api/settings.py`:

```python
"""The settings surface and the guarded data reset.

The reset is the only destructive route in the application, so its guards are explicit
and ordered: confirm token, no run in flight, no tracked work, a snapshot on disk, and
only then the deletes. It refuses rather than improvises at every step.

No auth in v1 (D-21) means no CSRF token is available; the type-to-confirm token plus
the automatic snapshot are this route's specific mitigation, and `POST` is required so
a link or a prefetch can never trigger it.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.api.searches import read_form
from app.config import settings as app_settings
from app.db.models import Base
from app.db.session import get_session
from app.domain.models import User
from app.web.template_env import make_templates

log = structlog.get_logger(__name__)

router = APIRouter()

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "web" / "templates"
templates = make_templates(TEMPLATE_DIR)

SETTINGS_TEMPLATE = "html/settings.html"

#: The exact text the user must type. Case-sensitive on purpose: the point is a
#: deliberate act, not a habitual click.
RESET_CONFIRM_TOKEN = "DELETE"

#: Emptied by a reset, children first, so `foreign_keys=ON` holds at every step.
#: `companies` is here because it is derived from listings — leaving it behind only
#: creates orphans. `sources`, `searches`, `filter_rules` and `cv_versions` are
#: deliberately absent: `sources` is the board lookup the next run's upsert needs, and
#: the rest are the user's own configuration.
RESET_DELETE_ORDER: tuple[str, ...] = (
    "scores",
    "listing_exclusions",
    "listing_events",
    "listing_dupes",
    "listing_sources",
    "listings",
    "llm_calls",
    "source_request_log",
    "runs",
    "queue_state",
    "companies",
)

#: Shown on the page as kept.
RESET_KEPT_TABLES: tuple[str, ...] = ("searches", "filter_rules", "sources")

#: Tables that reference `listings` and are NOT deleted: a reset refuses while any of
#: them holds a row, so a later phase fails loudly instead of corrupting tracked work.
RESET_BLOCKING_TABLES: tuple[str, ...] = ("applications", "cv_artifacts")


async def _counts(session: AsyncSession) -> list[dict[str, Any]]:
    """Row counts for the page, one query per table (11 + 3, all trivial)."""
    rows: list[dict[str, Any]] = []
    for table in (*RESET_DELETE_ORDER, *RESET_KEPT_TABLES):
        count = await session.scalar(
            select(func.count()).select_from(Base.metadata.tables[table])
        )
        rows.append({"table": table, "count": int(count or 0)})
    return rows


async def _settings_context(
    session: AsyncSession,
    *,
    banner: str | None = None,
    error: bool = False,
) -> dict[str, Any]:
    backend = session.get_bind()
    database_path = Path(str(backend.url.database or ""))
    return {
        "banner": banner,
        "error": error,
        "counts": await _counts(session),
        "deleted_tables": RESET_DELETE_ORDER,
        "kept_tables": RESET_KEPT_TABLES,
        "backup_dir": str(database_path.parent / "reset-backups"),
        "confirm_token": RESET_CONFIRM_TOKEN,
    }


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """State exactly what a reset deletes, what it keeps, and how to recover."""
    return templates.TemplateResponse(
        request, SETTINGS_TEMPLATE, await _settings_context(session)
    )
```

- [ ] **Step 4: Write the template**

Create `app/web/templates/html/settings.html`:

```html
{% extends "html/base.html" %}

{# The only destructive surface in the application. The form is a PLAIN html form, not
   an htmx one: a reset is a full navigation, and a destructive action gains nothing
   from a partial swap. Jinja autoescape is the only escaping in play. #}

{% block title %}Settings — Job Search Copilot{% endblock %}

{% block content %}
<h2>Settings</h2>

{% if banner %}
<p class="settings-banner{% if error %} settings-banner-error{% endif %}" id="settings-banner">{{ banner }}</p>
{% endif %}

<section class="settings-card">
  <h3>Queue data</h3>
  <p class="settings-note">
    A reset deletes the fetched corpus and the run history. Your saved searches and
    their rules are kept, and so is the board list the next run needs to upsert into.
  </p>
  <ul class="settings-counts">
    {% for row in counts %}
    <li>{{ row.table }}: {{ row.count }}</li>
    {% endfor %}
  </ul>
</section>

<section class="danger-card" id="danger-zone">
  <h3>Danger zone</h3>
  <p class="settings-note">
    Deleted: {{ deleted_tables | join(", ") }}.
  </p>
  <p class="settings-note">
    Kept: {{ kept_tables | join(", ") }}.
  </p>
  <p class="settings-note">
    A snapshot is written to <code>{{ backup_dir }}</code> <strong>before</strong>
    anything is deleted. To recover, stop the container and replace the database file
    with that snapshot — there is deliberately no restore button, because a restore is
    a second destructive path.
  </p>
  <form method="post" action="/settings/reset">
    <div class="field">
      <label for="reset-confirm">Type {{ confirm_token }} to confirm <span class="field-note">case sensitive</span></label>
      <input type="text" id="reset-confirm" name="confirm" autocomplete="off" placeholder="{{ confirm_token }}">
    </div>
    <div class="form-actions">
      <button type="submit" id="reset-submit">Reset queue data</button>
    </div>
  </form>
</section>
{% endblock %}
```

The `.field`, `.field-note` and `.form-actions` classes already exist and are already styled — reuse them and add rules only for the new classes below.

- [ ] **Step 5: Register the router and add the nav link**

In `app/main.py`, add to the router imports:

```python
from app.api import settings as settings_routes
```

and to `create_app`, after `app.include_router(search_routes.router)`:

```python
    app.include_router(settings_routes.router)
```

In `app/web/templates/html/base.html`, add a fifth nav link after the Runs link:

```html
      <a class="nav-link{% if nav_path == '/settings' %} nav-current{% endif %}" href="/settings"{% if nav_path == '/settings' %} aria-current="page"{% endif %}>Settings</a>
```

- [ ] **Step 6: Add the stylesheet rules and rebuild**

Append to the `@layer components` block in `assets/tailwind/input.css`:

```css
/* Settings / danger zone (2026-09-17). */
.settings-banner {
  padding: 0.75rem 1rem;
  border: 1px solid var(--color-border);
  border-left: 4px solid var(--color-accent);
  border-radius: var(--radius-md);
  background-color: var(--color-surface);
}
.settings-banner-error {
  border-left-color: var(--color-danger);
}
.settings-card,
.danger-card {
  max-width: 52rem;
  padding: 1.25rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background-color: var(--color-surface);
  margin-bottom: 1.5rem;
}
.danger-card {
  border-color: var(--color-danger);
}
.settings-note {
  color: var(--color-muted);
}
.settings-counts {
  list-style: none;
  padding: 0;
  margin: 0;
  columns: 2;
}
```

If `--color-danger` does not exist in the `@theme` block, add it there (`--color-danger: #b3261e;`) rather than inventing a second palette.

Rebuild `app.css` exactly as in Task 2 Step 4.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q tests/api/test_settings_page.py tests/test_auth_seam.py tests/test_stylesheet_coverage.py`
Expected: all pass.

- [ ] **Step 8: Full suite, lint, commit**

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check app tests
git add app/api/settings.py app/web/templates/html/settings.html app/main.py \
        app/web/templates/html/base.html assets/tailwind/input.css \
        static/vendor/app.css tests/api/test_settings_page.py
git commit -m "feat(settings): add the settings page and its danger zone"
```

---

### Task 5: The guarded reset

**Lane:** @fixer

**Files:**
- Modify: `app/api/settings.py` (add snapshot helper, guards, `POST /settings/reset`)
- Modify: `tests/api/test_settings_page.py` (unchanged)
- Test: `tests/api/test_settings_reset.py` (create)
- Test: `tests/db/test_reset_coverage.py` (create)

**Interfaces:**
- Consumes: everything `POST /settings/reset` needs from Task 4 (`RESET_DELETE_ORDER`, `RESET_BLOCKING_TABLES`, `RESET_CONFIRM_TOKEN`, `_settings_context`, `read_form`), plus `app.pipeline.run.TERMINAL_STATUSES`.
- Produces: `settings.snapshot_database(*, db_path: Path, backups_dir: Path, moment: datetime) -> Path` and the route `POST /settings/reset`. Also `tests/db/test_reset_coverage.py::test_every_listing_child_is_deleted_or_declared`.

- [ ] **Step 1: Write the failing tests**

Create `tests/api/test_settings_reset.py`:

```python
"""The reset deletes the corpus and nothing else, and it refuses more than it allows."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.settings import RESET_DELETE_ORDER, RESET_KEPT_TABLES
from app.db.models import (
    Application,
    CvArtifact,
    CvVersion,
    Listing,
    Run,
    Search,
    Source,
)
from app.db.repositories.listing_repo import upsert_listing_source
from app.pipeline.stages import normalise_listing
from app.sources.base import RawListing

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


async def _seed_corpus(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, int]:
    async with session_factory() as session:
        session.add(Source(name="linkedin", display_name="LinkedIn"))
        session.add(
            Search(
                name="Dublin Python",
                enabled=True,
                is_default=False,
                criteria_json={"keywords": "python"},
                created_at=NOW,
                updated_at=NOW,
            )
        )
        run = Run(
            search_id=None,
            trigger="manual",
            status="done",
            started_at=NOW,
            finished_at=NOW,
            fetched_count=1,
        )
        session.add(run)
        await session.commit()
        run_id = int(run.id)

    raw = RawListing(
        source="linkedin",  # type: ignore[arg-type]
        source_listing_id="linkedin-1",
        source_url="https://linkedin.example.com/jobs/1",
        direct_url=None,
        title="Backend Engineer",
        company_name="Acme",
        location_raw="Dublin, Ireland",
        description="Build the thing.",
        posted_at=date(2026, 9, 1),
    )
    async with session_factory() as session:
        await upsert_listing_source(
            session,
            source="linkedin",
            norm=normalise_listing(raw),
            run_id=run_id,
            now=NOW,
        )
        await session.commit()

    return {"run_id": run_id}


async def _count(session_factory: async_sessionmaker[AsyncSession], table: str) -> int:
    from app.db.models import Base

    async with session_factory() as session:
        return int(
            await session.scalar(
                select(func.count()).select_from(Base.metadata.tables[table])
            )
            or 0
        )


async def test_a_wrong_confirm_token_changes_nothing(client, session_factory) -> None:
    await _seed_corpus(session_factory)
    before = await _count(session_factory, "listings")

    response = await client.post("/settings/reset", data={"confirm": "delete"})

    assert response.status_code == 400
    assert "must type" in response.text.lower() or "DELETE" in response.text
    assert await _count(session_factory, "listings") == before


async def test_a_correct_token_empties_the_corpus_and_keeps_configuration(
    client, session_factory
) -> None:
    await _seed_corpus(session_factory)

    response = await client.post("/settings/reset", data={"confirm": "DELETE"})

    assert response.status_code == 200
    for table in RESET_DELETE_ORDER:
        assert await _count(session_factory, table) == 0, table
    for table in RESET_KEPT_TABLES:
        assert await _count(session_factory, table) > 0, table


async def test_the_snapshot_holds_the_pre_reset_rows(client, session_factory) -> None:
    await _seed_corpus(session_factory)

    response = await client.post("/settings/reset", data={"confirm": "DELETE"})

    snapshots = sorted(Path(_database_path(session_factory)).parent.joinpath("reset-backups").glob("*.db"))
    assert len(snapshots) == 1
    assert snapshots[0].name in response.text

    connection = sqlite3.connect(f"file:{snapshots[0]}?mode=ro", uri=True)
    try:
        assert connection.execute("SELECT COUNT(*) FROM listings").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1
    finally:
        connection.close()


async def test_a_run_in_flight_blocks_the_reset(client, session_factory) -> None:
    await _seed_corpus(session_factory)
    async with session_factory() as session:
        session.add(
            Run(
                search_id=None,
                trigger="manual",
                status="running",
                started_at=NOW,
                fetched_count=0,
            )
        )
        await session.commit()

    response = await client.post("/settings/reset", data={"confirm": "DELETE"})

    assert response.status_code == 409
    assert await _count(session_factory, "listings") == 1


async def test_tracked_work_blocks_the_reset(client, session_factory) -> None:
    await _seed_corpus(session_factory)
    async with session_factory() as session:
        session.add(CvVersion(name="Base", latex_source="x", created_at=NOW))
        await session.commit()
    async with session_factory() as session:
        version = await session.scalar(select(CvVersion))
        listing = await session.scalar(select(Listing))
        assert version is not None and listing is not None
        session.add(
            CvArtifact(
                listing_id=listing.id,
                base_cv_version_id=version.id,
                created_at=NOW,
            )
        )
        await session.commit()

    response = await client.post("/settings/reset", data={"confirm": "DELETE"})

    assert response.status_code == 409
    assert await _count(session_factory, "cv_artifacts") == 1


async def test_a_terminal_run_does_not_block_the_reset(client, session_factory) -> None:
    await _seed_corpus(session_factory)

    response = await client.post("/settings/reset", data={"confirm": "DELETE"})

    assert response.status_code == 200
    assert await _count(session_factory, "runs") == 0
```

Add this helper (it reads the file path off the very session the route mutates, avoiding a hardcoded path):

```python
def _database_path(session_factory: async_sessionmaker[AsyncSession]) -> str:
    """The on-disk database file, read from the engine the app actually uses.

    `AsyncSession.get_bind()` returns the SYNC engine, whose `url.database` is the
    absolute path — verified against SQLAlchemy 2.0 + aiosqlite. In production that is
    `/data/jobsearch.db`; under pytest it is the temp copy, so the reset route needs no
    test-only override to find the file it must snapshot.
    """
    engine = session_factory.kw["bind"]
    return str(engine.sync_engine.url.database)
```

Confirm the `CvVersion` / `CvArtifact` / `Application` constructor fields against `app/db/models.py` (`:358`, `:370`, `:405`) before running — pass only the fields those tables actually require and let nullable columns default to `None`.

- [ ] **Step 2: Write the FK-coverage guard**

Create `tests/db/test_reset_coverage.py`:

```python
"""A future table that references `listings` must force a reset decision.

The reset deletes a fixed list of tables and refuses while another list holds rows. A
new child table would otherwise be silently orphaned (or silently block) — so this test
enumerates every child of `listings` from the live metadata and requires each to be in
exactly one of the two lists.
"""

from __future__ import annotations

from app.api.settings import RESET_BLOCKING_TABLES, RESET_DELETE_ORDER
from app.db.models import Base


def _children_of_listings() -> set[str]:
    children: set[str] = set()
    for table in Base.metadata.tables.values():
        for foreign_key in table.foreign_keys:
            if foreign_key.column.table.name == "listings":
                children.add(table.name)
    return children


def test_every_listing_child_is_deleted_or_declared() -> None:
    children = _children_of_listings()

    assert children, "the metadata has no children of `listings` — the scan is vacuous"
    undecided = children - set(RESET_DELETE_ORDER) - set(RESET_BLOCKING_TABLES)
    assert undecided == set(), (
        f"{sorted(undecided)} reference `listings` but the reset neither deletes them "
        "nor refuses while they hold rows; decide and add each to RESET_DELETE_ORDER "
        "or RESET_BLOCKING_TABLES"
    )


def test_the_two_lists_do_not_overlap() -> None:
    assert set(RESET_DELETE_ORDER) & set(RESET_BLOCKING_TABLES) == set()


def test_every_named_table_exists() -> None:
    for name in (*RESET_DELETE_ORDER, *RESET_BLOCKING_TABLES):
        assert name in Base.metadata.tables, name
```

- [ ] **Step 3: Run both to verify they fail**

Run: `.venv/bin/python -m pytest -q tests/api/test_settings_reset.py tests/db/test_reset_coverage.py`

Expected: `tests/api/test_settings_reset.py` fails with 405 (no `POST /settings/reset` yet); `tests/db/test_reset_coverage.py` fails on `application_events` (it references `applications`, not `listings`, so confirm the actual output) or passes — if it passes, keep it as the regression guard it is and note that in the commit body.

- [ ] **Step 4: Add the snapshot helper and the guards**

Append to `app/api/settings.py`:

```python
import asyncio
import sqlite3
from sqlalchemy import delete
from app.pipeline.run import TERMINAL_STATUSES


class ResetRefused(Exception):
    """A guard declined the reset. Nothing has been deleted."""


def snapshot_database(*, db_path: Path, backups_dir: Path, moment: datetime) -> Path:
    """Copy the live database with `VACUUM INTO`. Returns the snapshot path.

    Runs on a plain SYNC `sqlite3` connection in autocommit: `VACUUM` cannot run inside
    a transaction, and the async engine would wrap it in one. `VACUUM INTO` is a single
    statement, it is WAL-safe, and it needs no new dependency.

    The destination is written as an escaped SQL literal rather than a bound parameter:
    `VACUUM INTO` takes an expression, and a literal removes any doubt about how the
    statement is prepared. The path is ours — a database directory plus a generated
    filename — and single quotes are doubled anyway.
    """
    backups_dir.mkdir(parents=True, exist_ok=True)
    destination = backups_dir / f"jobsearch-{moment.strftime('%Y%m%dT%H%M%SZ')}.db"
    if destination.exists():
        raise ResetRefused(f"snapshot target already exists: {destination.name}")

    literal = str(destination).replace("'", "''")
    connection = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        connection.execute(f"VACUUM INTO '{literal}'")
    finally:
        connection.close()
    return destination


async def _running_run_id(session: AsyncSession) -> int | None:
    return await session.scalar(
        select(Run.id).where(Run.status.not_in(tuple(TERMINAL_STATUSES))).limit(1)
    )


async def _blocking_row(session: AsyncSession) -> str | None:
    """The first blocking table that holds a row, or None."""
    for table in RESET_BLOCKING_TABLES:
        count = await session.scalar(
            select(func.count()).select_from(Base.metadata.tables[table])
        )
        if int(count or 0):
            return table
    return None
```

- [ ] **Step 5: Add the route**

Append to `app/api/settings.py`:

```python
@router.post("/settings/reset", response_class=HTMLResponse)
async def reset_data(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Snapshot, then empty the corpus. Refuses at the first failed guard.

    The order is the whole safety property: every refusal happens before the first
    DELETE, and the snapshot happens before it too. A snapshot taken after the deletes
    would be worthless.
    """
    form = await read_form(request)
    confirm = str(form.get("confirm") or "").strip()
    if confirm != RESET_CONFIRM_TOKEN:
        return templates.TemplateResponse(
            request,
            SETTINGS_TEMPLATE,
            await _settings_context(
                session,
                banner=f"Nothing was deleted: type {RESET_CONFIRM_TOKEN} exactly to confirm.",
                error=True,
            ),
            status_code=400,
        )

    running_id = await _running_run_id(session)
    if running_id is not None:
        return templates.TemplateResponse(
            request,
            SETTINGS_TEMPLATE,
            await _settings_context(
                session,
                banner=f"Nothing was deleted: run {running_id} is still in flight.",
                error=True,
            ),
            status_code=409,
        )

    blocking = await _blocking_row(session)
    if blocking is not None:
        return templates.TemplateResponse(
            request,
            SETTINGS_TEMPLATE,
            await _settings_context(
                session,
                banner=(
                    f"Nothing was deleted: {blocking} holds tracked work. "
                    "Clear it in a later phase before resetting."
                ),
                error=True,
            ),
            status_code=409,
        )

    database_path = Path(str(session.get_bind().url.database or ""))
    try:
        snapshot = await asyncio.to_thread(
            snapshot_database,
            db_path=database_path,
            backups_dir=database_path.parent / "reset-backups",
            moment=datetime.now(UTC),
        )
    except (ResetRefused, sqlite3.Error, OSError) as exc:
        log.warning("reset.snapshot_failed", error=str(exc))
        return templates.TemplateResponse(
            request,
            SETTINGS_TEMPLATE,
            await _settings_context(
                session,
                banner=f"Nothing was deleted: the snapshot failed ({exc}).",
                error=True,
            ),
            status_code=500,
        )

    for table in RESET_DELETE_ORDER:
        await session.execute(delete(Base.metadata.tables[table]))
    await session.commit()

    log.info("reset.completed", snapshot=snapshot.name)
    return templates.TemplateResponse(
        request,
        SETTINGS_TEMPLATE,
        await _settings_context(
            session,
            banner=f"Queue data deleted. Snapshot: {snapshot.name}.",
        ),
    )
```

`Run` must be imported in `app/api/settings.py` (`from app.db.models import Base, Run`).

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q tests/api/test_settings_reset.py tests/db/test_reset_coverage.py`
Expected: all pass.

- [ ] **Step 7: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: green. Pay attention to `tests/test_auth_seam.py` (both new routes must resolve `current_user`) and `tests/db/test_orm_drift.py`.

- [ ] **Step 8: Lint and commit**

```bash
.venv/bin/python -m ruff check app tests
git add app/api/settings.py tests/api/test_settings_reset.py tests/db/test_reset_coverage.py
git commit -m "feat(settings): snapshot then reset the queue data behind explicit guards"
```

---

### Task 6: Apply live and record

**Lane:** orchestrator (this task is the SDD cycle's close-out, not an agent lane)

**Files:**
- Modify: `docs/implementation-notes.md` (append a dated section)

- [ ] **Step 1: Confirm the working tree and the suite**

Run: `git status --porcelain` — only the pre-existing untracked `.gsd/` and `.planning/milestone.lock` may remain.
Run: `.venv/bin/python -m pytest -q` and `.venv/bin/python -m ruff check app tests` — both green.

- [ ] **Step 2: Hand the operator the rebuild + verification steps**

Docker is unavailable in the agent sandbox, so the operator runs:

```bash
docker compose down && docker compose up -d --build --wait
```

Then, on the running instance:

1. `GET /settings` returns 200 and the nav shows **Settings** as the current page.
2. Click a queue row's title — it opens the posting in a new tab. A merged row shows one link per source and an **Apply** link where the employer URL differs.
3. Click **Dismiss all N queued listings** — the queue empties and stays empty on reload; **Unhide** on one listing brings exactly that row back.
4. On `/settings`, type `delete` (lowercase) and submit — the page reports nothing was deleted and the counts are unchanged.
5. Type `DELETE` and submit — the queue empties, `/searches` still lists the saved searches and their rules, and a `jobsearch-<timestamp>.db` snapshot exists under the mounted volume's `reset-backups/`.

- [ ] **Step 3: Record the change**

Append a dated section to `docs/implementation-notes.md` with: the three surfaces, the commits, the reset's delete order and refusal conditions, that `sources`/`searches`/`filter_rules` are preserved, that the snapshot lives at `<db_dir>/reset-backups/`, the recovery procedure (stop the container, replace the database file with the snapshot), and the deliberate omission of a restore button.

```bash
git add docs/implementation-notes.md
git commit -m "docs: record the queue links, dismiss and guarded reset"
```

---

## Self-Review

**Spec coverage.** Part 1 (queue row → posting): Task 1 supplies `url`/`source_links` from the existing single batched read, Task 2 renders the title anchor and the per-source links with the employer link gated on inequality — exactly the spec's "render only when it differs" rule, verified against the live counts (Indeed 155/155 differ, LinkedIn 0/128). Part 2 (Dismiss): Task 3 appends one `hide` event per listing through `append_event`, reuses the existing event type rather than minting a seventh, scopes to the queue predicate with the free-text search dropped, and reads after writing. Part 3 (`/settings` + guarded reset): Task 4 builds the page, the nav link and the router; Task 5 adds the six ordered steps — confirm token (400), running run (409), tracked work (409), snapshot before any delete (500 with nothing deleted), the fixed child-first delete order, and the success banner naming the snapshot. The spec's three testing lanes exist as `test_queue_links.py`, `test_queue_dismiss.py` and `test_settings_reset.py`, the FK enumeration is `test_reset_coverage.py`, the auth seam is covered by the existing `test_auth_seam.py` (both new routes declare `current_user`), and the class-has-a-rule guard is covered by the existing `test_stylesheet_coverage.py` (three new rules for the queue links, six for settings, plus the rebuild steps).

**Two deliberate deviations from the spec, both improvements, both recorded in code comments.** (1) The snapshot directory is derived from `session.get_bind().url.database` rather than from `settings.database_url_sync`: same intent — never hardcode `/data` — but strictly safer, because the snapshot must be of the database actually being mutated, and it needs no test-only override. (2) Dismiss computes its id list from a raised-limit `read_queue` rather than from the rendered page, because the page size is 25 and the queue is not; the spec's "the whole queue" requirement is what forced it.

**Placeholder scan.** No "TBD", no "add error handling", no "similar to Task N". Every code step carries the code. Two steps name a model file to read before running (`ListingDupe` in Task 3, `CvVersion`/`CvArtifact` in Task 5) because those constructors have more columns than the test needs; each says exactly what to confirm and what to do if it differs.

**Type consistency.** `SourceLink(source, url, employer_url)` is defined once in Task 1 and used unchanged in Task 2's template (`link.url`, `link.employer_url`, `link.source`) and tests. `QueueRow.url` / `QueueRow.source_links` are the only names used. `hide_listings(session, *, listing_ids, occurred_at)` is defined in Task 3 Step 3 and called with exactly those keywords in Step 4. `RESET_DELETE_ORDER`, `RESET_KEPT_TABLES`, `RESET_BLOCKING_TABLES` and `RESET_CONFIRM_TOKEN` are defined in Task 4 and consumed by Task 5's tests and route with those exact names. `_settings_context(session, *, banner, error)` is defined in Task 4 and called from Task 5 with those keywords. `snapshot_database(*, db_path, backups_dir, moment)` is defined and called in Task 5 with those keywords.

**One known collision, handled inside Task 2.** Wrapping the title in an anchor breaks the two `<td class="listing-title">([^<]+)</td>` extractions in `tests/pipeline/test_ingest_e2e.py`. Task 2 Step 5 broadens the pattern to tolerate the optional anchor while asserting the same titles — a deliberate relabel, nothing removed.
