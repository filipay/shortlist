"""The 9-item ROADMAP migration-0001 acceptance checklist as executable assertions.

Every assertion introspects the database produced by **`alembic upgrade head`** on
a temp file — `PRAGMA table_info` / `PRAGMA index_list` / `PRAGMA index_info` /
`sqlite_master` — never the ORM metadata. The point is to prove the *migrated*
schema, not the model definitions: a model/DDL drift must fail here.

Why this file exists: migration 0001 is one-way (D-20). A checklist item that
lives only in prose gets deferred with "we'll add it when we need it", and the
omission describes the past and cannot be backfilled (PITFALLS P8/Pitfall 9).
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Introspection helpers. PRAGMA does not accept bound parameters, so table/index
# names are interpolated — they are trusted constants from our own migration and
# from `sqlite_master`, never external input.
REQUIRED_LISTING_TIMESTAMPS = ("first_seen_at", "last_seen_at", "content_hash")


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def _table_info(connection: sqlite3.Connection, table: str) -> dict[str, sqlite3.Row]:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"]: row for row in rows}


def _index_list(connection: sqlite3.Connection, table: str) -> dict[str, sqlite3.Row]:
    rows = connection.execute(f"PRAGMA index_list({table})").fetchall()
    return {row["name"]: row for row in rows}


def _index_columns(connection: sqlite3.Connection, index: str) -> list[str]:
    rows = connection.execute(f"PRAGMA index_info({index})").fetchall()
    return [row["name"] for row in rows]


def _master(connection: sqlite3.Connection, kind: str, name: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master WHERE type = ? AND name = ?",
        (kind, name),
    ).fetchone()
    assert row is not None, f"missing {kind}: {name}"
    return row


def _exists(connection: sqlite3.Connection, kind: str, name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = ? AND name = ?", (kind, name)
    ).fetchone()
    return row is not None


def _insert_listing(connection: sqlite3.Connection, url: str = "https://example.com/j/1") -> int:
    now = "2026-09-15 00:00:00"
    cursor = connection.execute(
        "INSERT INTO listings "
        "(canonical_url, title, first_seen_at, last_seen_at, content_hash, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (url, "Test Role", now, now, "hash-1", now, now),
    )
    return int(cursor.lastrowid or 0)


# --- Item 1 -------------------------------------------------------------------
def test_listings_timestamps_not_null(migrated_db: Path) -> None:
    connection = _connect(migrated_db)
    try:
        columns = _table_info(connection, "listings")

        for column in REQUIRED_LISTING_TIMESTAMPS:
            assert column in columns, f"listings.{column} is missing"
            assert columns[column]["notnull"] == 1, f"listings.{column} must be NOT NULL"

        # content_hash is a fixed-width digest, not a free-form blob.
        assert str(columns["content_hash"]["type"]).upper() == "VARCHAR(64)"

        # No insert path can omit the past-describing columns: an INSERT that
        # leaves them out must fail, so there is no nullable-by-omission window.
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO listings (canonical_url, title, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                ("https://example.com/omitted", "Omitted", "2026-09-15", "2026-09-15"),
            )
    finally:
        connection.close()


# --- Item 2 -------------------------------------------------------------------
def test_listing_events_append_only(migrated_db: Path) -> None:
    connection = _connect(migrated_db)
    try:
        assert _exists(connection, "table", "listing_events")
        assert _exists(connection, "trigger", "listing_events_no_update")
        assert _exists(connection, "trigger", "listing_events_no_delete")

        listing_id = _insert_listing(connection)
        connection.execute(
            "INSERT INTO listing_events (listing_id, event_type, occurred_at) VALUES (?, ?, ?)",
            (listing_id, "view", "2026-09-15 00:00:00"),
        )
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError) as update_error:
            connection.execute("UPDATE listing_events SET event_type = 'hide'")
        assert "append-only" in str(update_error.value)

        with pytest.raises(sqlite3.IntegrityError) as delete_error:
            connection.execute("DELETE FROM listing_events")
        assert "append-only" in str(delete_error.value)
    finally:
        connection.close()


# --- Item 3 -------------------------------------------------------------------
def test_scores_decomposition(migrated_db: Path) -> None:
    connection = _connect(migrated_db)
    try:
        columns = _table_info(connection, "scores")
    finally:
        connection.close()

    assert {"factor_scores_json", "weights_json", "criteria_version"} <= set(columns)


# --- Item 4 -------------------------------------------------------------------
def test_cv_artifacts_verification_and_blocked(migrated_db: Path) -> None:
    connection = _connect(migrated_db)
    try:
        columns = _table_info(connection, "cv_artifacts")
        assert "verification_json" in columns

        connection.execute(
            "INSERT INTO cv_artifacts (compile_status, created_at) VALUES ('blocked', ?)",
            ("2026-09-15 00:00:00",),
        )
        connection.commit()
        stored = connection.execute(
            "SELECT compile_status FROM cv_artifacts"
        ).fetchone()
        assert stored["compile_status"] == "blocked"

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO cv_artifacts (compile_status, created_at) VALUES ('unknown', ?)",
                ("2026-09-15 00:00:00",),
            )
    finally:
        connection.close()


# --- Item 5 -------------------------------------------------------------------
def test_applications_cv_artifact_id(migrated_db: Path) -> None:
    connection = _connect(migrated_db)
    try:
        columns = _table_info(connection, "applications")
        assert "cv_artifact_id" in columns
        assert columns["cv_artifact_id"]["notnull"] == 0, "cv_artifact_id must be nullable"

        foreign_keys = {
            row["from"]: row["table"]
            for row in connection.execute("PRAGMA foreign_key_list(applications)")
        }
        assert foreign_keys.get("cv_artifact_id") == "cv_artifacts", (
            "applications.cv_artifact_id must be a FK to cv_artifacts"
        )

        listing_id = _insert_listing(connection)
        connection.execute(
            "INSERT INTO applications "
            "(listing_id, status, cv_artifact_id, created_at, updated_at) "
            "VALUES (?, 'queued', NULL, ?, ?)",
            (listing_id, "2026-09-15 00:00:00", "2026-09-15 00:00:00"),
        )
        connection.commit()
        assert connection.execute(
            "SELECT cv_artifact_id FROM applications"
        ).fetchone()["cv_artifact_id"] is None
    finally:
        connection.close()


# --- Item 6 -------------------------------------------------------------------
def test_dedup_indexes(migrated_db: Path) -> None:
    connection = _connect(migrated_db)
    try:
        indexes = _index_list(connection, "listing_sources")

        sid_index = indexes.get("uq_listing_sources_source_sid")
        assert sid_index is not None, "missing uq_listing_sources_source_sid"
        assert sid_index["unique"] == 1
        assert sid_index["partial"] == 1, "the (source, source_listing_id) index must be partial"
        assert _index_columns(connection, "uq_listing_sources_source_sid") == [
            "source",
            "source_listing_id",
        ]
        sid_sql = _master(connection, "index", "uq_listing_sources_source_sid")["sql"]
        assert "WHERE" in sid_sql.upper()
        assert "source_listing_id IS NOT NULL" in sid_sql

        url_index = indexes.get("uq_listing_sources_source_url")
        assert url_index is not None, "missing uq_listing_sources_source_url"
        assert url_index["unique"] == 1
        assert url_index["partial"] == 0, "the canonical-URL index must be unconditional"
        assert _index_columns(connection, "uq_listing_sources_source_url") == [
            "source",
            "canonical_source_url",
        ]
        url_sql = _master(connection, "index", "uq_listing_sources_source_url")["sql"]
        assert "WHERE" not in url_sql.upper()
    finally:
        connection.close()


# --- Item 7 -------------------------------------------------------------------
def test_sources_capabilities_and_tos(migrated_db: Path) -> None:
    connection = _connect(migrated_db)
    try:
        columns = _table_info(connection, "sources")
    finally:
        connection.close()

    assert {"capabilities_json", "tos_audited_at"} <= set(columns)


# --- Item 8 -------------------------------------------------------------------
def test_blocking_key_indexed(migrated_db: Path) -> None:
    connection = _connect(migrated_db)
    try:
        assert "blocking_key" in _table_info(connection, "listings")
        covering = [
            name
            for name in _index_list(connection, "listings")
            if "blocking_key" in _index_columns(connection, name)
        ]
    finally:
        connection.close()

    assert covering, "listings.blocking_key is not covered by any index"


# --- Item 9 -------------------------------------------------------------------
def test_alembic_at_revision_0001(migrated_db: Path) -> None:
    connection = _connect(migrated_db)
    try:
        versions = [
            row["version_num"]
            for row in connection.execute("SELECT version_num FROM alembic_version")
        ]
    finally:
        connection.close()

    assert versions == ["0001"], "expected exactly one recorded revision: 0001"

    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    head_lines = [line for line in completed.stdout.splitlines() if "(head)" in line]
    assert len(head_lines) == 1, f"expected a single Alembic head, saw {head_lines}"
    assert head_lines[0].startswith("0001"), head_lines[0]

    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "alembic upgrade head" in dockerfile, (
        "acceptance item 9 requires the migration to be exercised in the container build"
    )
