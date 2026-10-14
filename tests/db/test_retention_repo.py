"""Retention pruning — the guard suite (D-163..D-168, RUN-07).

The properties this module pins, all from the plan's `must_haves`:

* the preview and the delete run ONE predicate, so the count shown before
  destruction cannot disagree with the number removed;
* the D-165 guards are the queries' own conditions — an application-linked artifact
  and each listing's newest successful artifact are never selected, whatever the
  threshold;
* sizes come from disk (`stat().st_size`), and a stored path that is missing or that
  resolves outside the artifacts directory contributes zero and is reported, never
  raised (T-08-23);
* a bad category or a non-positive age is refused before any SQL.

Each guard is asserted as a *selection* result, never as a caught exception: a guard
implemented as an error path would surface only at the operator's confirm step.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.exc import DatabaseError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import settings as settings_module
from app.db.models import (
    Application,
    CvArtifact,
    Listing,
    ListingDupe,
    ListingEvent,
    ListingExclusion,
    LlmCall,
    Run,
    Score,
    Source,
    SourceRequestLog,
)
from app.db.repositories import cv_artifact_repo, retention_repo
from app.db.repositories.retention_repo import (
    PRUNE_CATEGORIES,
    RUN_FLOOR,
    TRIGGER_CARVE_OUT_CATEGORIES,
    PrunePreview,
    delete,
    preview,
)

NOW = datetime.now(UTC).replace(microsecond=0)
#: Comfortably older than any threshold used below.
OLD = NOW - timedelta(days=400)


@pytest.fixture
def artifacts_root(tmp_path: Path) -> Path:
    """A per-test artifacts directory, so `stat()` and containment are real."""
    root = tmp_path / "artifacts"
    root.mkdir()
    return root


def _write_file(root: Path, name: str, size: int) -> Path:
    path = root / name
    path.write_bytes(b"x" * size)
    return path


async def _seed_listing(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    index: int = 1,
    last_seen_at: datetime = NOW,
) -> int:
    async with session_factory() as session:
        listing = Listing(
            canonical_url="https://example.com/jobs/" + str(index),
            title="Prune Role " + str(index),
            first_seen_at=NOW,
            last_seen_at=last_seen_at,
            content_hash="prune-hash-" + str(index),
            created_at=NOW,
            updated_at=NOW,
            is_active=True,
        )
        session.add(listing)
        await session.commit()
        return int(listing.id)


async def _insert_artifact(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    listing_id: int | None,
    created_at: datetime,
    status: str = "ok",
    tex_path: str | None = None,
    pdf_path: str | None = None,
) -> int:
    async with session_factory() as session:
        record = await cv_artifact_repo.insert_artifact(
            session,
            listing_id=listing_id,
            base_cv_version_id=None,
            patch_json={},
            change_log_json=[],
            compile_status=status,
            verification_json={"passed": status == "ok"},
            page_count=1 if status == "ok" else None,
            tex_path=tex_path,
            pdf_path=pdf_path,
            now=created_at,
        )
        await session.commit()
        return record.id


async def _artifact_ids(session_factory: async_sessionmaker[AsyncSession]) -> set[int]:
    async with session_factory() as session:
        return {int(row) for row in (await session.execute(select(CvArtifact.id))).scalars().all()}


async def _count(session_factory: async_sessionmaker[AsyncSession], table: str) -> int:
    from app.db.models import Base

    async with session_factory() as session:
        return int(
            await session.scalar(select(func.count()).select_from(Base.metadata.tables[table])) or 0
        )


async def _seed_source(
    session_factory: async_sessionmaker[AsyncSession], name: str = "linkedin"
) -> None:
    """`source_request_log.source` carries a FK to `sources.name`; seed it once."""
    async with session_factory() as session:
        if await session.scalar(select(Source.id).where(Source.name == name)) is None:
            session.add(Source(name=name, display_name=name.title()))
            await session.commit()


async def _seed_runs(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    count: int,
    started_at: datetime = OLD,
) -> list[int]:
    """`count` finished manual runs, all at `started_at`, in ascending id order."""
    async with session_factory() as session:
        runs = [
            Run(
                search_id=None,
                trigger="manual",
                status="done",
                started_at=started_at,
                finished_at=started_at,
                fetched_count=0,
            )
            for _ in range(count)
        ]
        session.add_all(runs)
        await session.commit()
        return [int(run.id) for run in runs]


async def _run_ids(session_factory: async_sessionmaker[AsyncSession]) -> set[int]:
    async with session_factory() as session:
        return {int(row) for row in (await session.execute(select(Run.id))).scalars().all()}


# --- the artifact category: one predicate, two statements ---------------------


async def test_an_old_unreferenced_non_newest_artifact_is_previewed_and_deleted(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    listing = await _seed_listing(session_factory)
    newest = await _insert_artifact(session_factory, listing_id=listing, created_at=NOW)
    tex = _write_file(artifacts_root, "old.tex", 10)
    pdf = _write_file(artifacts_root, "old.pdf", 20)
    old = await _insert_artifact(
        session_factory,
        listing_id=listing,
        created_at=OLD,
        tex_path=str(tex),
        pdf_path=str(pdf),
    )

    async with session_factory() as session:
        result = await preview(
            session, category="artifacts", age_days=30, artifacts_root=artifacts_root
        )
        assert isinstance(result, PrunePreview)
        assert result.count == 1
        assert result.noun == "artifact"
        assert result.size_bytes == 30
        assert result.size_display == "30 B"
        count, paths = await delete(session, category="artifacts", age_days=30)
        await session.commit()

    # One predicate, two statements: the preview's count IS the delete's count.
    assert count == result.count
    assert sorted(path.name for path in paths) == ["old.pdf", "old.tex"]
    remaining = await _artifact_ids(session_factory)
    assert int(newest) in remaining
    assert int(old) not in remaining


async def test_the_newest_successful_artifact_is_never_selected(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    """The negative control: the newest survives while an OLDER one is still eligible."""
    listing = await _seed_listing(session_factory)
    newest = await _insert_artifact(session_factory, listing_id=listing, created_at=OLD)
    older = await _insert_artifact(
        session_factory, listing_id=listing, created_at=OLD - timedelta(days=100)
    )

    async with session_factory() as session:
        result = await preview(
            session, category="artifacts", age_days=30, artifacts_root=artifacts_root
        )
        assert result.count == 1
        count, _paths = await delete(session, category="artifacts", age_days=30)
        await session.commit()

    assert count == 1
    remaining = await _artifact_ids(session_factory)
    assert int(newest) in remaining
    assert int(older) not in remaining


async def test_a_listings_only_successful_artifact_survives_an_aggressive_threshold(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    listing = await _seed_listing(session_factory)
    await _insert_artifact(session_factory, listing_id=listing, created_at=OLD)

    async with session_factory() as session:
        result = await preview(
            session, category="artifacts", age_days=1, artifacts_root=artifacts_root
        )

    assert result.count == 0


async def test_an_artifact_referenced_by_an_application_is_never_selected(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    listing = await _seed_listing(session_factory)
    # A newer ok artifact exists, so guard 4 does not hide the target; guard 3 must.
    await _insert_artifact(session_factory, listing_id=listing, created_at=NOW)
    target = await _insert_artifact(session_factory, listing_id=listing, created_at=OLD)

    async with session_factory() as session:
        session.add(
            Application(
                listing_id=listing,
                status="applied",
                cv_artifact_id=target,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        await session.commit()

    async with session_factory() as session:
        result = await preview(
            session, category="artifacts", age_days=30, artifacts_root=artifacts_root
        )

    assert result.count == 0


async def test_a_blocked_artifact_is_eligible(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    """Guard 4 guards the newest *successful* artifact — a blocked row is neither."""
    listing = await _seed_listing(session_factory)
    await _insert_artifact(session_factory, listing_id=listing, created_at=NOW)
    blocked = await _insert_artifact(
        session_factory, listing_id=listing, created_at=OLD, status="blocked"
    )

    async with session_factory() as session:
        count, _paths = await delete(session, category="artifacts", age_days=30)
        await session.commit()

    assert count == 1
    assert int(blocked) not in await _artifact_ids(session_factory)


# --- sizes come from disk, and a bad path is reported, never fatal -------------


async def test_a_missing_file_contributes_zero_and_is_reported(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    listing = await _seed_listing(session_factory)
    await _insert_artifact(session_factory, listing_id=listing, created_at=NOW)
    gone = artifacts_root / "gone.pdf"
    await _insert_artifact(
        session_factory, listing_id=listing, created_at=OLD, tex_path=None, pdf_path=str(gone)
    )

    async with session_factory() as session:
        result = await preview(
            session, category="artifacts", age_days=30, artifacts_root=artifacts_root
        )

    assert result.count == 1
    assert result.size_bytes == 0
    assert result.missing_files == 1


async def test_a_stored_path_outside_the_artifacts_directory_is_not_measured(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "secret.txt"
    outside.write_bytes(b"x" * 4096)
    listing = await _seed_listing(session_factory)
    await _insert_artifact(session_factory, listing_id=listing, created_at=NOW)
    await _insert_artifact(
        session_factory, listing_id=listing, created_at=OLD, pdf_path=str(outside)
    )

    async with session_factory() as session:
        result = await preview(
            session, category="artifacts", age_days=30, artifacts_root=artifacts_root
        )

    assert result.count == 1
    assert result.size_bytes == 0
    assert result.missing_files == 1
    assert outside.read_bytes() == b"x" * 4096


# --- validation happens before any SQL ----------------------------------------


@pytest.mark.parametrize(
    ("category", "age_days"),
    [
        ("nope", 30),
        ("", 30),
        ("artifacts", 0),
        ("artifacts", -1),
        ("artifacts", "abc"),
    ],
)
async def test_a_bad_category_or_non_positive_age_is_refused(
    session_factory: async_sessionmaker[AsyncSession],
    artifacts_root: Path,
    category: str,
    age_days: object,
) -> None:
    async with session_factory() as session:
        with pytest.raises(ValueError):
            await preview(
                session, category=category, age_days=age_days, artifacts_root=artifacts_root
            )
        with pytest.raises(ValueError):
            await delete(session, category=category, age_days=age_days)


# --- the runs category: the floor, the events exclusion, the ledger ------------


async def test_the_floor_protects_the_newest_runs_whatever_their_age(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    await _seed_runs(session_factory, count=3)

    async with session_factory() as session:
        result = await preview(session, category="runs", age_days=1, artifacts_root=artifacts_root)

    assert result.count == 0


async def test_the_floor_protects_inside_runs_while_an_outer_run_is_selected(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    ids = await _seed_runs(session_factory, count=RUN_FLOOR + 5)

    async with session_factory() as session:
        result = await preview(session, category="runs", age_days=1, artifacts_root=artifacts_root)
        assert result.count == 5
        count, _paths = await delete(session, category="runs", age_days=1)
        await session.commit()

    assert count == result.count
    remaining = await _run_ids(session_factory)
    assert set(ids[:5]).isdisjoint(remaining)
    assert set(ids[5:]) <= remaining


async def test_a_run_with_undeletable_listing_events_is_excluded_from_the_selection(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    """The guard is a condition, not an error path — assert the selection, not a raise."""
    ids = await _seed_runs(session_factory, count=RUN_FLOOR + 5)
    listing = await _seed_listing(session_factory, index=9)
    async with session_factory() as session:
        session.add(
            ListingEvent(listing_id=listing, event_type="view", occurred_at=NOW, run_id=ids[0])
        )
        await session.commit()

    async with session_factory() as session:
        result = await preview(session, category="runs", age_days=1, artifacts_root=artifacts_root)
        assert result.count == 4
        count, _paths = await delete(session, category="runs", age_days=1)
        await session.commit()

    assert count == 4
    assert ids[0] in await _run_ids(session_factory)


async def test_the_ledger_rows_survive_with_a_nulled_run_reference(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    ids = await _seed_runs(session_factory, count=RUN_FLOOR + 1)
    pruned, retained = ids[0], ids[-1]
    async with session_factory() as session:
        session.add_all(
            [
                LlmCall(run_id=pruned, purpose="rank", status="ok", created_at=NOW),
                LlmCall(run_id=retained, purpose="rank", status="ok", created_at=NOW),
            ]
        )
        await session.commit()

    async with session_factory() as session:
        count, _paths = await delete(session, category="runs", age_days=1)
        await session.commit()

    assert count == 1
    assert await _count(session_factory, "llm_calls") == 2
    async with session_factory() as session:
        references = {
            None if value is None else int(value)
            for value in (await session.execute(select(LlmCall.run_id))).scalars().all()
        }
    assert None in references  # the pruned run's reference was NULLed, not deleted
    assert retained in references


async def test_the_runs_ordering_deletes_children_before_parents(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    """A naive `DELETE FROM runs` fails: `scores.run_id` is NOT NULL."""
    ids = await _seed_runs(session_factory, count=RUN_FLOOR + 1)
    pruned = ids[0]
    listing = await _seed_listing(session_factory, index=7)
    await _seed_source(session_factory)
    async with session_factory() as session:
        session.add(Score(listing_id=listing, run_id=pruned, criteria_version=1, created_at=NOW))
        session.add(
            ListingExclusion(
                listing_id=listing, run_id=pruned, rule_kind="location", created_at=NOW
            )
        )
        session.add(
            SourceRequestLog(
                source="linkedin", run_id=pruned, occurred_at=OLD, kind="search", ok=True
            )
        )
        await session.commit()

    async with session_factory() as session:
        count, _paths = await delete(session, category="runs", age_days=1)
        await session.commit()

    assert count == 1
    assert await _count(session_factory, "scores") == 0
    assert await _count(session_factory, "listing_exclusions") == 0
    assert await _count(session_factory, "source_request_log") == 0


# --- the source request log: its own floor (a verdict input survives) ---------


async def test_a_source_log_row_of_a_retained_run_survives_and_an_orphan_row_is_selected(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    ids = await _seed_runs(session_factory, count=RUN_FLOOR)
    retained = ids[-1]
    await _seed_source(session_factory)
    async with session_factory() as session:
        session.add_all(
            [
                SourceRequestLog(
                    source="linkedin", run_id=retained, occurred_at=OLD, kind="search", ok=True
                ),
                SourceRequestLog(
                    source="linkedin", run_id=None, occurred_at=OLD, kind="search", ok=True
                ),
            ]
        )
        await session.commit()

    async with session_factory() as session:
        result = await preview(
            session, category="source_request_log", age_days=1, artifacts_root=artifacts_root
        )
        assert result.count == 1
        count, _paths = await delete(session, category="source_request_log", age_days=1)
        await session.commit()

    assert count == result.count == 1
    assert await _count(session_factory, "source_request_log") == 1


async def test_preview_and_delete_agree_for_runs_and_the_request_log(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    await _seed_runs(session_factory, count=RUN_FLOOR + 3)

    async with session_factory() as session:
        pairs: dict[str, tuple[int, int]] = {}
        for category in ("runs", "source_request_log"):
            result = await preview(
                session, category=category, age_days=1, artifacts_root=artifacts_root
            )
            count, _paths = await delete(session, category=category, age_days=1)
            pairs[category] = (result.count, count)
        await session.commit()

    assert pairs == {"runs": (3, 3), "source_request_log": (0, 0)}


# --- the listings category: the carve-out, the snapshot's trigger re-arm -------


async def _delete_as_the_route_does(
    session: AsyncSession, *, category: str, age_days: int = 1
) -> tuple[int, list[Path]]:
    """The route's orchestration, reproduced for a repository-level test.

    The carve-out categories need the append-only trigger suspended around the delete;
    the route owns that (in one transaction), and this helper does the same with the
    SAME shared functions, so a repository test exercises the real sequence.
    """
    if category in TRIGGER_CARVE_OUT_CATEGORIES:
        ddl = await settings_module._suspend_append_only_trigger(session)
        result = await delete(session, category=category, age_days=age_days)
        await settings_module._restore_append_only_trigger(session, ddl)
        return result
    return await delete(session, category=category, age_days=age_days)


async def _seed_listings_corpus(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> dict[str, int]:
    """One listing per guard, plus the two the carve-out deliberately allows."""
    clean = await _seed_listing(session_factory, index=20, last_seen_at=OLD)
    eventful = await _seed_listing(session_factory, index=21, last_seen_at=OLD)
    applied = await _seed_listing(session_factory, index=22, last_seen_at=OLD)
    artefacted = await _seed_listing(session_factory, index=23, last_seen_at=OLD)
    dupe_a = await _seed_listing(session_factory, index=24, last_seen_at=OLD)
    dupe_b = await _seed_listing(session_factory, index=25, last_seen_at=OLD)
    fresh = await _seed_listing(session_factory, index=26, last_seen_at=NOW)
    await _insert_artifact(session_factory, listing_id=artefacted, created_at=OLD)
    async with session_factory() as session:
        session.add(ListingEvent(listing_id=eventful, event_type="view", occurred_at=OLD))
        session.add(
            Application(listing_id=applied, status="queued", created_at=NOW, updated_at=NOW)
        )
        session.add(ListingDupe(listing_id=dupe_a, dup_listing_id=dupe_b, merged_at=OLD))
        await session.commit()
    return {
        "clean": clean,
        "eventful": eventful,
        "applied": applied,
        "artefacted": artefacted,
        "dupe_a": dupe_a,
        "dupe_b": dupe_b,
        "fresh": fresh,
    }


async def _listing_ids(session_factory: async_sessionmaker[AsyncSession]) -> set[int]:
    async with session_factory() as session:
        return {int(row) for row in (await session.execute(select(Listing.id))).scalars().all()}


async def test_the_listing_selection_excludes_applications_artifacts_and_both_dupe_sides(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    corpus = await _seed_listings_corpus(session_factory, artifacts_root)

    async with session_factory() as session:
        result = await preview(
            session, category="listings", age_days=1, artifacts_root=artifacts_root
        )
        selected = await retention_repo._select_ids(
            session, "listings", retention_repo._cutoff(1, None)
        )

    # `clean` and `eventful` only: the eventful one is NOT excluded, which is the
    # carve-out; the application, the artifact and BOTH dupe sides are. Asserting the
    # identities (not just the count) is what the test name claims.
    assert set(selected) == {corpus["clean"], corpus["eventful"]}
    assert result.count == 2


async def test_an_ok_artifact_with_a_null_listing_id_is_prunable(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    """IN-02: `NULL = NULL` is NULL in SQL, so guard 4 never fired on an orphan.

    An `ok` artifact with a NULL `listing_id` has no listing to protect; without the
    explicit `listing_id.is_(None)` disjunct it was never selected and leaked forever.
    """
    await _insert_artifact(session_factory, listing_id=None, created_at=OLD)

    async with session_factory() as session:
        result = await preview(
            session, category="artifacts", age_days=30, artifacts_root=artifacts_root
        )

    assert result.count == 1


async def test_a_stale_listing_prune_deletes_its_children_and_its_events(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    corpus = await _seed_listings_corpus(session_factory, artifacts_root)
    listing = corpus["clean"]
    run_id = (await _seed_runs(session_factory, count=1))[0]
    await _seed_source(session_factory)
    tex = artifacts_root / "child.tex"
    tex.write_bytes(b"x" * 4)
    async with session_factory() as session:
        session.add(Score(listing_id=listing, run_id=run_id, criteria_version=1, created_at=NOW))
        await session.commit()

    async with session_factory() as session:
        count, paths = await _delete_as_the_route_does(session, category="listings")
        await session.commit()

    # `clean` and `eventful` both qualify, so both go — with everything hanging off them.
    assert count == 2
    remaining = await _listing_ids(session_factory)
    assert listing not in remaining
    assert corpus["eventful"] not in remaining
    assert corpus["applied"] in remaining
    assert corpus["artefacted"] in remaining
    assert corpus["dupe_a"] in remaining and corpus["dupe_b"] in remaining
    assert corpus["fresh"] in remaining
    assert await _count(session_factory, "listing_events") == 0
    assert await _count(session_factory, "listing_dupes") == 1
    assert paths == []  # the only child artifact belonged to `artefacted`, which is kept


async def test_a_listing_with_an_artifact_is_never_selected_and_yields_no_paths(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    """The artifact guard also protects the files: a listing with an artifact is excluded.

    `retention_repo` still returns the child artifact paths for this category (so a
    future relaxation of the guard has a place to hand them over), but today the guard
    makes that list empty by construction — asserted here so the coupling is visible.
    """
    listing = await _seed_listing(session_factory, index=30, last_seen_at=OLD)
    tex = artifacts_root / "kept.tex"
    tex.write_bytes(b"x" * 1)
    await _insert_artifact(session_factory, listing_id=listing, created_at=OLD, tex_path=str(tex))

    async with session_factory() as session:
        result = await preview(
            session, category="listings", age_days=1, artifacts_root=artifacts_root
        )
        assert result.count == 0
        count, paths = await _delete_as_the_route_does(session, category="listings")
        await session.commit()

    assert count == 0
    assert paths == []
    assert tex.exists()


async def test_the_listing_prune_leaves_the_append_only_trigger_armed_with_its_negative_control(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    """The re-arm assertion the reset itself lacks, plus a control proving it can fail."""
    stale = await _seed_listing(session_factory, index=40, last_seen_at=OLD)
    other = await _seed_listing(session_factory, index=41, last_seen_at=NOW)
    async with session_factory() as session:
        session.add(ListingEvent(listing_id=stale, event_type="view", occurred_at=OLD))
        session.add(ListingEvent(listing_id=other, event_type="view", occurred_at=NOW))
        await session.commit()

    async with session_factory() as session:
        count, _paths = await _delete_as_the_route_does(session, category="listings")
        await session.commit()
    assert count == 1

    # 1) The database's OWN catalog proves the trigger is armed again after the commit.
    database = str(session_factory.kw["bind"].sync_engine.url.database)
    connection = sqlite3.connect(database)
    try:
        armed = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'trigger' AND name = ?",
            (settings_module._APPEND_ONLY_TRIGGER,),
        ).fetchone()[0]
    finally:
        connection.close()
    assert armed == 1

    # 2) An ordinary delete of a listing event is refused again (the trigger is live).
    with pytest.raises(DatabaseError):
        async with session_factory() as session:
            await session.execute(sa_delete(ListingEvent).where(ListingEvent.listing_id == other))
            await session.commit()

    # Negative control: with the trigger suspended the same delete SUCCEEDS, so the
    # assertion above can genuinely fail rather than passing vacuously.
    async with session_factory() as session:
        ddl = await settings_module._suspend_append_only_trigger(session)
        await session.execute(sa_delete(ListingEvent).where(ListingEvent.listing_id == other))
        await settings_module._restore_append_only_trigger(session, ddl)
        await session.commit()
    assert await _count(session_factory, "listing_events") == 0


# --- the four guards, parametrized over all four categories (a failure class) --


async def _seed_guard_corpus(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> dict[str, object]:
    """One corpus that exercises all four guards, for every category's prune."""
    await _seed_source(session_factory)
    runs = await _seed_runs(session_factory, count=RUN_FLOOR + 5)
    async with session_factory() as session:
        session.add_all(
            [LlmCall(run_id=run_id, purpose="rank", status="ok", created_at=NOW) for run_id in runs]
        )
        await session.commit()

    listing = await _seed_listing(session_factory, index=11, last_seen_at=OLD)
    newest = await _insert_artifact(session_factory, listing_id=listing, created_at=OLD)
    older = await _insert_artifact(
        session_factory, listing_id=listing, created_at=OLD - timedelta(days=10)
    )
    async with session_factory() as session:
        session.add(
            Application(
                listing_id=listing,
                status="applied",
                cv_artifact_id=older,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        await session.commit()

    eventful = await _seed_listing(session_factory, index=12, last_seen_at=OLD)
    async with session_factory() as session:
        session.add(ListingEvent(listing_id=eventful, event_type="view", occurred_at=OLD))
        await session.commit()

    return {
        "runs": runs,
        # The newest RUN_FLOOR runs are inside the floor's window and must survive.
        "protected_runs": set(runs[len(runs) - RUN_FLOOR :]),
        "newest": newest,
        "older": older,
    }


@pytest.mark.parametrize("category", sorted(PRUNE_CATEGORIES))
async def test_the_floor_guard_holds_for_every_category(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path, category: str
) -> None:
    corpus = await _seed_guard_corpus(session_factory, artifacts_root)

    async with session_factory() as session:
        await _delete_as_the_route_does(session, category=category)
        await session.commit()

    remaining = await _run_ids(session_factory)
    assert corpus["protected_runs"] <= remaining  # type: ignore[operator]


@pytest.mark.parametrize("category", sorted(PRUNE_CATEGORIES))
async def test_the_ledger_guard_holds_for_every_category(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path, category: str
) -> None:
    await _seed_guard_corpus(session_factory, artifacts_root)
    before = await _count(session_factory, "llm_calls")

    async with session_factory() as session:
        await _delete_as_the_route_does(session, category=category)
        await session.commit()

    assert await _count(session_factory, "llm_calls") == before


@pytest.mark.parametrize("category", sorted(PRUNE_CATEGORIES))
async def test_the_application_link_guard_holds_for_every_category(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path, category: str
) -> None:
    corpus = await _seed_guard_corpus(session_factory, artifacts_root)

    async with session_factory() as session:
        await _delete_as_the_route_does(session, category=category)
        await session.commit()

    assert corpus["older"] in await _artifact_ids(session_factory)


@pytest.mark.parametrize("category", sorted(PRUNE_CATEGORIES))
async def test_the_newest_successful_artifact_guard_holds_for_every_category(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path, category: str
) -> None:
    corpus = await _seed_guard_corpus(session_factory, artifacts_root)

    async with session_factory() as session:
        await _delete_as_the_route_does(session, category=category)
        await session.commit()

    assert corpus["newest"] in await _artifact_ids(session_factory)
