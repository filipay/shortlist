"""The prune surface: form round-trip, refusals, the audit line (D-163..D-168).

The two steps are separate POSTs (D-166): a preview that deletes nothing and a
confirm that re-derives the count before destroying anything. This module pins the
round-trip, the refusal paths, the preview-equals-delete assertion, the post-commit
unlink, the audit line and the retention threshold persisted on the operations row.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import settings as settings_module
from app.config import settings
from app.db.models import CvArtifact, Listing, OperationsConfig
from app.db.repositories import cv_artifact_repo, operations_config_repo, retention_repo

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
OLD = NOW - timedelta(days=400)


@pytest.fixture(autouse=True)
def _artifacts_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the app's artifacts directory at a per-test temp dir."""
    root = tmp_path / "artifacts"
    root.mkdir()
    monkeypatch.setattr(settings, "artifacts_dir", str(root))
    return root


async def _seed_listing(
    session_factory: async_sessionmaker[AsyncSession], *, index: int = 1
) -> int:
    async with session_factory() as session:
        listing = Listing(
            canonical_url="https://example.com/jobs/" + str(index),
            title="Prune Role " + str(index),
            first_seen_at=NOW,
            last_seen_at=NOW,
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
    listing_id: int,
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


async def _seed_prunable_artifact(
    session_factory: async_sessionmaker[AsyncSession],
    artifacts_root: Path,
    *,
    index: int = 1,
) -> tuple[int, Path, Path]:
    """One newest-ok artifact plus one old artifact with real files on disk."""
    listing = await _seed_listing(session_factory, index=index)
    await _insert_artifact(session_factory, listing_id=listing, created_at=NOW)
    tex = artifacts_root / "old.tex"
    pdf = artifacts_root / "old.pdf"
    tex.write_bytes(b"x" * 10)
    pdf.write_bytes(b"x" * 20)
    old = await _insert_artifact(
        session_factory,
        listing_id=listing,
        created_at=OLD,
        tex_path=str(tex),
        pdf_path=str(pdf),
    )
    return old, tex, pdf


async def _artifact_ids(session_factory: async_sessionmaker[AsyncSession]) -> set[int]:
    async with session_factory() as session:
        return {int(row) for row in (await session.execute(select(CvArtifact.id))).scalars().all()}


# --- the form round-trip ------------------------------------------------------


async def test_the_preview_round_trips_and_offers_the_confirm(
    client: object, session_factory: async_sessionmaker[AsyncSession], _artifacts_dir: Path
) -> None:
    await _seed_prunable_artifact(session_factory, _artifacts_dir)

    response = await client.post(  # type: ignore[attr-defined]
        settings_module.PRUNE_PREVIEW_PATH, data={"category": "artifacts", "age_days": "30"}
    )

    assert response.status_code == 200
    assert 'id="prune-preview"' in response.text
    assert "This will delete 1 artifact" in response.text
    assert "30 B" in response.text
    assert 'id="prune-confirm-submit"' in response.text
    assert "This cannot be undone." in response.text
    # A preview deletes nothing.
    assert len(await _artifact_ids(session_factory)) == 2


async def test_a_zero_count_preview_renders_the_empty_copy_and_no_confirm(
    client: object, _artifacts_dir: Path
) -> None:
    response = await client.post(  # type: ignore[attr-defined]
        settings_module.PRUNE_PREVIEW_PATH, data={"category": "artifacts", "age_days": "30"}
    )

    assert response.status_code == 200
    assert "Nothing matches this threshold" in response.text
    assert 'id="prune-confirm-submit"' not in response.text


async def test_a_bad_category_returns_400_and_deletes_nothing(
    client: object, session_factory: async_sessionmaker[AsyncSession], _artifacts_dir: Path
) -> None:
    await _seed_prunable_artifact(session_factory, _artifacts_dir)

    response = await client.post(  # type: ignore[attr-defined]
        settings_module.PRUNE_PATH, data={"category": "nope", "age_days": "30"}
    )

    assert response.status_code == 400
    assert settings_module.PRUNE_INPUT_REFUSAL in response.text
    assert len(await _artifact_ids(session_factory)) == 2


@pytest.mark.parametrize("age_days", ["0", "-3", "abc", ""])
async def test_a_non_positive_or_non_numeric_age_returns_400_and_deletes_nothing(
    client: object,
    session_factory: async_sessionmaker[AsyncSession],
    _artifacts_dir: Path,
    age_days: str,
) -> None:
    await _seed_prunable_artifact(session_factory, _artifacts_dir)

    response = await client.post(  # type: ignore[attr-defined]
        settings_module.PRUNE_PATH, data={"category": "artifacts", "age_days": age_days}
    )

    assert response.status_code == 400
    assert len(await _artifact_ids(session_factory)) == 2


# --- the confirm: rows commit first, then the files are unlinked ---------------


async def test_the_confirm_deletes_the_rows_and_the_files_and_renders_the_audit(
    client: object, session_factory: async_sessionmaker[AsyncSession], _artifacts_dir: Path
) -> None:
    old, tex, pdf = await _seed_prunable_artifact(session_factory, _artifacts_dir)

    response = await client.post(  # type: ignore[attr-defined]
        settings_module.PRUNE_PATH, data={"category": "artifacts", "age_days": "30"}
    )

    assert response.status_code == 200
    assert "Deleted 1 artifact" in response.text
    assert "artifacts, older than 30 days" in response.text
    remaining = await _artifact_ids(session_factory)
    assert int(old) not in remaining
    assert not tex.exists()
    assert not pdf.exists()


async def test_a_path_outside_the_artifacts_directory_is_skipped_and_reported(
    client: object, session_factory: async_sessionmaker[AsyncSession], _artifacts_dir: Path
) -> None:
    outside = _artifacts_dir.parent / "outside.pdf"
    outside.write_bytes(b"x" * 5)
    listing = await _seed_listing(session_factory)
    await _insert_artifact(session_factory, listing_id=listing, created_at=NOW)
    await _insert_artifact(session_factory, listing_id=listing, created_at=OLD, pdf_path=str(outside))

    response = await client.post(  # type: ignore[attr-defined]
        settings_module.PRUNE_PATH, data={"category": "artifacts", "age_days": "30"}
    )

    assert response.status_code == 200
    assert "outside the artifacts directory were skipped" in response.text
    # The path traversal control: the file outside the root is untouched.
    assert outside.exists()


# --- the retention thresholds live on the operations row (D-168) --------------


async def test_the_chosen_threshold_is_persisted_and_survives_a_re_render(
    client: object, session_factory: async_sessionmaker[AsyncSession], _artifacts_dir: Path
) -> None:
    response = await client.post(  # type: ignore[attr-defined]
        settings_module.PRUNE_PREVIEW_PATH, data={"category": "artifacts", "age_days": "45"}
    )
    assert response.status_code == 200

    async with session_factory() as session:
        assert await operations_config_repo.read_retention(session) == {"artifacts": 45}

    # A plain page load (the re-render) neither loses nor rewrites the stored threshold.
    page = await client.get("/settings")  # type: ignore[attr-defined]
    assert page.status_code == 200
    assert "artifacts 45 days" in page.text

    async with session_factory() as session:
        assert await operations_config_repo.read_retention(session) == {"artifacts": 45}


async def test_a_first_retention_write_satisfies_both_not_null_columns(
    client: object, session_factory: async_sessionmaker[AsyncSession], _artifacts_dir: Path
) -> None:
    """A fresh install has no schedule document yet, and both payload columns are NOT NULL."""
    response = await client.post(  # type: ignore[attr-defined]
        settings_module.PRUNE_PREVIEW_PATH, data={"category": "artifacts", "age_days": "30"}
    )
    assert response.status_code == 200

    async with session_factory() as session:
        row = await session.get(OperationsConfig, operations_config_repo.SINGLETON_ID)
        assert row is not None
        assert isinstance(row.schedule_json, dict)
        assert row.retention_json == {"artifacts": 30}

    # A later schedule save must not clobber the stored retention payload.
    async with session_factory() as session:
        await operations_config_repo.write_schedule(
            session,
            operations_config_repo.ScheduleConfig(
                enabled=True, hour=6, minute=30, timezone="Europe/Dublin"
            ),
            now=NOW,
        )
        await session.commit()

    async with session_factory() as session:
        assert await operations_config_repo.read_retention(session) == {"artifacts": 30}


async def test_the_prune_card_offers_every_prune_category(client: object) -> None:
    response = await client.get("/settings")  # type: ignore[attr-defined]

    assert response.status_code == 200
    offered = {key for key, _label in settings_module.PRUNE_CATEGORY_LABELS}
    assert offered == retention_repo.PRUNE_CATEGORIES
    for key, label in settings_module.PRUNE_CATEGORY_LABELS:
        assert 'value="' + key + '"' in response.text
        assert label in response.text


async def test_the_protected_line_names_the_run_floor_actually_enforced(
    client: object, _artifacts_dir: Path
) -> None:
    response = await client.post(  # type: ignore[attr-defined]
        settings_module.PRUNE_PREVIEW_PATH, data={"category": "artifacts", "age_days": "30"}
    )

    assert response.status_code == 200
    protected = "Kept regardless: the last " + str(retention_repo.RUN_FLOOR) + " runs"
    assert protected in response.text
    assert "the LLM call ledger, CVs" in response.text
