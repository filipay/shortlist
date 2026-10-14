"""The walking skeleton's end-to-end path: migrate -> write -> read -> render."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Listing, ListingSource, Source
from app.db.repositories.listing_repo import upsert_listing_source

SEEDED_TITLE = "Senior Python Engineer"

EXPECTED_TABLES = (
    "sources",
    "companies",
    "listings",
    "listing_sources",
    "listing_dupes",
    "listing_events",
    "listing_exclusions",
    "searches",
    "runs",
    "scores",
    "cv_versions",
    "cv_artifacts",
    "applications",
    "application_events",
    "llm_calls",
    "source_request_log",
    # Migration 0002 (Phase 2): typed filter rules + the last-visit watermark.
    "filter_rules",
    "queue_state",
    "listing_fts",
    # Migration 0004 (Phase 5): the single-row global ranking weights document.
    "ranking_config",
    # Migration 0005: the live generated CV draft (one row per listing).
    "cv_drafts",
    # Migration 0006: the screening drafts + the single-row screening-question doc.
    "screening_drafts",
    "apply_config",
    # Migration 0008: the single-row schedule/retention document.
    "operations_config",
)


def _norm(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "canonical_url": "https://example.com/jobs/1",
        "source_listing_id": "abc123",
        "source_url": "https://example.com/jobs/1?utm_source=linkedin",
        "canonical_source_url": "https://example.com/jobs/1",
        "direct_url": "https://acme.example.com/jobs/1",
        "title": SEEDED_TITLE,
        "company_name": "Acme",
        "company_norm": "acme",
        "location_raw": "Dublin, Ireland",
        "description": "Build the thing.",
        "content_hash": "content-hash-1",
        "raw_hash": "raw-hash-1",
        "posted_at": datetime(2026, 9, 1, tzinfo=UTC),
    }
    base.update(overrides)
    return base


def test_migration_creates_every_table_at_latest_revision(migrated_db: Path) -> None:
    connection = sqlite3.connect(migrated_db)
    try:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        tables = {row[0] for row in rows}
        for table in EXPECTED_TABLES:
            assert table in tables, f"missing table: {table}"

        version = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchall()
        assert version == [("0008",)]
    finally:
        connection.close()


async def _register_source(
    session_factory: async_sessionmaker[AsyncSession], name: str
) -> None:
    async with session_factory() as session:
        session.add(Source(name=name, display_name=name.title()))
        await session.commit()


async def test_repository_write_is_rendered_by_get(
    session_factory: async_sessionmaker[AsyncSession],
    client,
) -> None:
    now = datetime.now(UTC)
    await _register_source(session_factory, "linkedin")

    async with session_factory() as session:
        outcome = await upsert_listing_source(
            session,
            source="linkedin",
            norm=_norm(),
            run_id=None,
            now=now,
        )
        await session.commit()

    assert outcome.kind == "created"

    async with session_factory() as session:
        persisted = await session.execute(
            Listing.__table__.select().where(
                Listing.canonical_url == "https://example.com/jobs/1"
            )
        )
        assert persisted.first() is not None

    response = await client.get("/")
    assert response.status_code == 200
    assert SEEDED_TITLE in response.text
    assert "1 listing" in response.text


async def test_empty_database_renders_empty_state(client) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert "No listings yet" in response.text
    assert "0 listings" in response.text


async def test_two_key_upsert_is_idempotent_on_repeat(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime.now(UTC)
    await _register_source(session_factory, "linkedin")

    async with session_factory() as session:
        await upsert_listing_source(
            session, source="linkedin", norm=_norm(), run_id=None, now=now
        )
        await session.commit()

    async with session_factory() as session:
        outcome = await upsert_listing_source(
            session, source="linkedin", norm=_norm(), run_id=None, now=now
        )
        await session.commit()
        count = await session.scalar(
            select(func.count()).select_from(ListingSource)
        )

    assert outcome.kind == "updated"
    assert count == 1
