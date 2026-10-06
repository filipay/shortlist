"""The extended ROADMAP migration acceptance checklist as executable assertions.

Items 1-9 are the original migration-0001 checklist; items 10-13 are the
migration-0002 additions (`filter_rules`, the last-visit watermark, the four new
`runs` columns and the `listing_dupes` uniqueness index); item 14 is the
migration-0003 addition (`llm_calls.server_version`, D-12 / PITFALLS M9). Every
assertion introspects the database produced by **`alembic upgrade head`** on a temp file —
`PRAGMA table_info` / `PRAGMA index_list` / `PRAGMA index_info` / `sqlite_master`
— never the ORM metadata. The point is to prove the *migrated* schema, not the
model definitions: a model/DDL drift must fail here.

Why this file exists: migrations are one-way (D-20). A checklist item that lives
only in prose gets deferred with "we'll add it when we need it", and the omission
describes the past and cannot be backfilled (PITFALLS P8/Pitfall 9).
"""

from __future__ import annotations

import os
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


def _alembic_upgrade(db_path: Path, revision: str = "head") -> None:
    """Drive the real migration against `db_path` (same pattern as conftest).

    A non-zero exit is re-raised with Alembic's stderr inline: the regression
    this test guards against is a subprocess abort, so its message (the
    ``DROP TABLE runs`` / ``FOREIGN KEY constraint failed`` trace) must be
    visible in the test report rather than swallowed by ``capture_output``.
    """
    env = {**os.environ, "DATABASE_URL_SYNC": f"sqlite:///{db_path}"}
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"alembic upgrade {revision} failed (rc={completed.returncode}):\n"
            f"{completed.stderr}"
        )


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
def test_alembic_at_latest_revision(migrated_db: Path) -> None:
    connection = _connect(migrated_db)
    try:
        versions = [
            row["version_num"]
            for row in connection.execute("SELECT version_num FROM alembic_version")
        ]
    finally:
        connection.close()

    assert versions == ["0007"], "expected exactly one recorded revision: 0007"

    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    head_lines = [line for line in completed.stdout.splitlines() if "(head)" in line]
    assert len(head_lines) == 1, f"expected a single Alembic head, saw {head_lines}"
    assert head_lines[0].startswith("0007"), head_lines[0]

    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "alembic upgrade head" in dockerfile, (
        "acceptance item 9 requires the migration to be exercised in the container build"
    )


# --- Item 10 (0002) — filter_rules + its named kind CHECK ---------------------
def test_filter_rules_table_and_kind_check(migrated_db: Path) -> None:
    connection = _connect(migrated_db)
    try:
        assert _exists(connection, "table", "filter_rules")

        columns = _table_info(connection, "filter_rules")
        assert {
            "search_id",
            "kind",
            "params_json",
            "enabled",
            "position",
            "created_at",
            "updated_at",
        } <= set(columns)
        assert columns["search_id"]["notnull"] == 1
        assert columns["kind"]["notnull"] == 1

        # The (search_id, position) index makes the ordered read index-usable.
        assert "ix_filter_rules_search_position" in _index_list(connection, "filter_rules")
        assert _index_columns(connection, "ix_filter_rules_search_position") == [
            "search_id",
            "position",
        ]

        connection.execute(
            "INSERT INTO searches (name, created_at, updated_at) VALUES (?, ?, ?)",
            ("Dublin Python", "2026-09-16 00:00:00", "2026-09-16 00:00:00"),
        )
        search_id = int(
            connection.execute("SELECT id FROM searches").fetchone()["id"]
        )

        # A valid kind persists, and the server defaults fill enabled/position.
        connection.execute(
            "INSERT INTO filter_rules (search_id, kind, created_at, updated_at) "
            "VALUES (?, 'salary_floor', ?, ?)",
            (search_id, "2026-09-16 00:00:00", "2026-09-16 00:00:00"),
        )
        connection.commit()
        stored = connection.execute(
            "SELECT enabled, position FROM filter_rules"
        ).fetchone()
        assert stored["enabled"] == 1
        assert stored["position"] == 0

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO filter_rules (search_id, kind, created_at, updated_at) "
                "VALUES (?, 'not_a_kind', ?, ?)",
                (search_id, "2026-09-16 00:00:00", "2026-09-16 00:00:00"),
            )
    finally:
        connection.close()


# --- Item 11 (0002) — queue_state with a nullable watermark -------------------
def test_queue_state_watermark_is_nullable(migrated_db: Path) -> None:
    connection = _connect(migrated_db)
    try:
        assert _exists(connection, "table", "queue_state")

        columns = _table_info(connection, "queue_state")
        assert "last_queue_view_at" in columns
        assert columns["last_queue_view_at"]["notnull"] == 0, (
            "last_queue_view_at must be nullable — NULL means 'never viewed'"
        )
        assert columns["updated_at"]["notnull"] == 1

        connection.execute(
            "INSERT INTO queue_state (last_queue_view_at, updated_at) VALUES (NULL, ?)",
            ("2026-09-16 00:00:00",),
        )
        connection.commit()
        stored = connection.execute(
            "SELECT last_queue_view_at FROM queue_state"
        ).fetchone()
        assert stored["last_queue_view_at"] is None
    finally:
        connection.close()


# --- Item 12 (0002) — the four runs columns + the reason enum CHECK ----------
def test_runs_reason_columns_and_enum_check(migrated_db: Path) -> None:
    connection = _connect(migrated_db)
    try:
        columns = _table_info(connection, "runs")
        assert {
            "reason",
            "reason_counts_json",
            "stage_log_json",
            "criteria_snapshot_json",
        } <= set(columns)

        # The named ck_runs_reason must actually be in the migrated DDL, and the
        # batch recreation must have preserved the pre-existing named CHECKs.
        runs_sql = _master(connection, "table", "runs")["sql"]
        assert "ck_runs_reason" in runs_sql
        assert "ck_runs_trigger" in runs_sql
        assert "ck_runs_status" in runs_sql

        # A valid reason persists; NULL is legitimate and also allowed.
        connection.execute(
            "INSERT INTO runs (trigger, status, reason) VALUES ('manual', 'done', 'mixed')"
        )
        connection.execute(
            "INSERT INTO runs (trigger, status, reason) VALUES ('manual', 'done', NULL)"
        )
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO runs (trigger, status, reason) "
                "VALUES ('manual', 'done', 'not_a_reason')"
            )

        # The batch recreation must have preserved the pre-existing NAMED CHECKs.
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO runs (trigger, status, reason) "
                "VALUES ('not_a_trigger', 'done', NULL)"
            )
    finally:
        connection.close()


# --- Item 13 (0002) — criteria_version + the listing_dupes unique index ------
def test_criteria_version_and_dupes_unique_index(migrated_db: Path) -> None:
    connection = _connect(migrated_db)
    try:
        exclusion_columns = _table_info(connection, "listing_exclusions")
        assert "criteria_version" in exclusion_columns
        assert exclusion_columns["criteria_version"]["notnull"] == 0

        indexes = _index_list(connection, "listing_dupes")
        unique_index = indexes.get("uq_listing_dupes_pair")
        assert unique_index is not None, "missing uq_listing_dupes_pair"
        assert unique_index["unique"] == 1
        assert _index_columns(connection, "uq_listing_dupes_pair") == [
            "listing_id",
            "dup_listing_id",
        ]
        assert _index_columns(connection, "ix_listing_dupes_dup_listing_id") == [
            "dup_listing_id"
        ]

        first = _insert_listing(connection, "https://example.com/j/first")
        second = _insert_listing(connection, "https://example.com/j/second")
        connection.execute(
            "INSERT INTO listing_dupes (listing_id, dup_listing_id) VALUES (?, ?)",
            (first, second),
        )
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO listing_dupes (listing_id, dup_listing_id) VALUES (?, ?)",
                (first, second),
            )
    finally:
        connection.close()


# --- Item 14 (0003) — llm_calls.server_version (D-12 / PITFALLS M9) -----------
def test_llm_calls_server_version_column_is_nullable(migrated_db: Path) -> None:
    connection = _connect(migrated_db)
    try:
        columns = _table_info(connection, "llm_calls")
        assert "server_version" in columns, (
            "migration 0003 must add llm_calls.server_version"
        )
        assert columns["server_version"]["notnull"] == 0, (
            "server_version must be nullable — rows written before 0003 have no value"
        )
        assert columns["server_version"]["type"].upper().startswith("VARCHAR"), (
            f"expected a bounded VARCHAR, saw {columns['server_version']['type']}"
        )

        # A row with no recorded version still persists (the column is optional).
        connection.execute(
            "INSERT INTO llm_calls (purpose, status, created_at) VALUES ('probe', 'ok', ?)",
            ("2026-09-17 00:00:00",),
        )
        connection.commit()
        stored = connection.execute("SELECT server_version FROM llm_calls").fetchone()
        assert stored["server_version"] is None
    finally:
        connection.close()


# --- Item 15 (0004) — ranking_config, the single-row weights document ----------
def test_ranking_config_table_and_singleton_check(migrated_db: Path) -> None:
    """D-99/D-100: the global weights document is one row keyed id = 1."""
    connection = _connect(migrated_db)
    try:
        assert _exists(connection, "table", "ranking_config")

        columns = _table_info(connection, "ranking_config")
        assert {"id", "weights_json", "updated_at"} <= set(columns)
        assert columns["weights_json"]["notnull"] == 1
        assert columns["updated_at"]["notnull"] == 1

        # The named singleton CHECK must be in the migrated DDL and enforced.
        table_sql = _master(connection, "table", "ranking_config")["sql"]
        assert "ck_ranking_config_singleton" in table_sql

        connection.execute(
            "INSERT INTO ranking_config (id, weights_json, updated_at) "
            "VALUES (1, '{}', ?)",
            ("2026-09-22 00:00:00",),
        )
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO ranking_config (id, weights_json, updated_at) "
                "VALUES (2, '{}', ?)",
                ("2026-09-22 00:00:00",),
            )
    finally:
        connection.close()


# --- Item 16 (0005) — cv_drafts, the one live generated draft per listing --------
def test_cv_drafts_table_and_unique_listing(migrated_db: Path) -> None:
    """D-108 superseded: the generated CV is kept per listing, one live row each.

    The named ``uq_cv_drafts_listing`` constraint is what makes a regenerate replace
    rather than accumulate, so it is asserted in the migrated DDL and enforced.
    """
    connection = _connect(migrated_db)
    try:
        assert _exists(connection, "table", "cv_drafts")

        columns = _table_info(connection, "cv_drafts")
        assert {
            "id",
            "listing_id",
            "base_cv_version_id",
            "patch_json",
            "fact_store_hash",
            "created_at",
        } <= set(columns)
        assert columns["listing_id"]["notnull"] == 1
        assert columns["patch_json"]["notnull"] == 1

        # The (single-column) UNIQUE on listing_id is present and named in the DDL
        # (a table-level constraint yields SQLite's implicit autoindex, so the name is
        # asserted on the CREATE TABLE text, not via PRAGMA index_list).
        table_sql = _master(connection, "table", "cv_drafts")["sql"]
        assert "uq_cv_drafts_listing" in table_sql, "missing uq_cv_drafts_listing"

        listing_id = _insert_listing(connection)
        connection.execute(
            "INSERT INTO cv_drafts (listing_id, patch_json, created_at) VALUES (?, '{}', ?)",
            (listing_id, "2026-09-28 00:00:00"),
        )
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO cv_drafts (listing_id, patch_json, created_at) VALUES (?, '{}', ?)",
                (listing_id, "2026-09-28 00:00:00"),
            )
    finally:
        connection.close()


# --- Item 17 (0006) — screening_drafts + apply_config + the two triggers -------
def test_screening_drafts_apply_config_and_application_events_append_only(
    migrated_db: Path,
) -> None:
    """D-126 / D-131: two new tables, and the history table is trigger-enforced.

    The append-only guarantee is asserted against the **migrated** DDL (not the ORM),
    mirroring ``test_listing_events_append_only``: a migration that dropped the new
    triggers fails here even though the models would still look correct.
    """
    connection = _connect(migrated_db)
    try:
        assert _exists(connection, "table", "screening_drafts")
        assert _exists(connection, "table", "apply_config")
        assert _exists(connection, "trigger", "application_events_no_update")
        assert _exists(connection, "trigger", "application_events_no_delete")

        draft_columns = _table_info(connection, "screening_drafts")
        assert {
            "id",
            "listing_id",
            "question_text",
            "answer_text",
            "evidence_json",
            "unsupported",
            "created_at",
        } <= set(draft_columns)
        assert draft_columns["listing_id"]["notnull"] == 1
        assert draft_columns["question_text"]["notnull"] == 1
        assert draft_columns["unsupported"]["notnull"] == 1

        config_columns = _table_info(connection, "apply_config")
        assert {"id", "questions_json", "updated_at"} <= set(config_columns)
        assert config_columns["questions_json"]["notnull"] == 1
        config_sql = _master(connection, "table", "apply_config")["sql"]
        assert "ck_apply_config_singleton" in config_sql

        listing_id = _insert_listing(connection)
        connection.execute(
            "INSERT INTO applications (listing_id, status, created_at, updated_at) "
            "VALUES (?, 'queued', ?, ?)",
            (listing_id, "2026-09-30 00:00:00", "2026-09-30 00:00:00"),
        )
        application_id = int(
            connection.execute("SELECT id FROM applications").fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO application_events "
            "(application_id, from_status, to_status, occurred_at) "
            "VALUES (?, NULL, 'queued', ?)",
            (application_id, "2026-09-30 00:00:00"),
        )
        connection.execute(
            "INSERT INTO apply_config (id, questions_json, updated_at) "
            "VALUES (1, '{}', ?)",
            ("2026-09-30 00:00:00",),
        )
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError) as update_error:
            connection.execute("UPDATE application_events SET to_status = 'applied'")
        assert "append-only" in str(update_error.value)

        with pytest.raises(sqlite3.IntegrityError) as delete_error:
            connection.execute("DELETE FROM application_events")
        assert "append-only" in str(delete_error.value)

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO apply_config (id, questions_json, updated_at) "
                "VALUES (2, '{}', ?)",
                ("2026-09-30 00:00:00",),
            )
    finally:
        connection.close()


# --- Item 18 (0007) — screening_drafts.warnings_json + band --------------------
def test_screening_draft_warnings_and_band_columns(migrated_db: Path) -> None:
    """G-07-3: the checker's specific findings and the advisory band are persisted.

    Both columns are asserted nullable: a row written before 0007 (or seeded directly)
    has no specifics and must still load, degrading to the generic-caution fallback.
    """
    connection = _connect(migrated_db)
    try:
        columns = _table_info(connection, "screening_drafts")
        assert "warnings_json" in columns, "0007 must add screening_drafts.warnings_json"
        assert "band" in columns, "0007 must add screening_drafts.band"
        assert columns["warnings_json"]["notnull"] == 0
        assert columns["band"]["notnull"] == 0

        listing_id = _insert_listing(connection)
        connection.execute(
            "INSERT INTO screening_drafts "
            "(listing_id, question_text, answer_text, evidence_json, warnings_json, band, "
            "unsupported, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                listing_id,
                "Why this role?",
                "I shipped 97% of it.",
                "[]",
                '["unsupported number \'97\': appears in neither the CV facts nor the listing"]',
                "ungrounded",
                1,
                "2026-10-06 00:00:00",
            ),
        )
        connection.commit()
        stored = connection.execute(
            "SELECT warnings_json, band FROM screening_drafts"
        ).fetchone()
        assert "97" in stored["warnings_json"]
        assert stored["band"] == "ungrounded"

        # A legacy row with no specifics still persists (both columns nullable).
        connection.execute(
            "INSERT INTO screening_drafts "
            "(listing_id, question_text, unsupported, created_at) VALUES (?, ?, ?, ?)",
            (listing_id, "Legacy?", 1, "2026-10-06 00:00:00"),
        )
        connection.commit()
        legacy = connection.execute(
            "SELECT warnings_json, band FROM screening_drafts ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert legacy["warnings_json"] is None
        assert legacy["band"] is None
    finally:
        connection.close()


# --- Regression — upgrading a *populated* 0001 must not abort ------------------
def test_upgrade_populated_0001_to_head(populated_0001: tuple[Path, dict[str, int]]) -> None:
    """A populated 0001 database upgrades to head without an FK/batch abort.

    The batch recreation of ``runs`` performs ``DROP TABLE runs``; with
    ``foreign_keys=ON`` that fails while ``listing_events``,
    ``listing_exclusions``, ``scores``, ``llm_calls`` and ``source_request_log``
    hold rows referencing ``runs.id``. Fresh-database tests never reproduce it,
    so this fixture seeds a child row per referencing table first. If
    ``alembic upgrade head`` (and therefore the real ``alembic/env.py``) is
    correct, the upgrade completes and every seeded row survives.
    """
    db_path, seeded_counts = populated_0001

    _alembic_upgrade(db_path)

    connection = _connect(db_path)
    try:
        # 1. The upgrade actually reached the one recorded revision.
        versions = [
            row["version_num"]
            for row in connection.execute("SELECT version_num FROM alembic_version")
        ]
        assert versions == ["0007"], f"expected exactly 0007, saw {versions}"

        # 2. No data loss: every seeded row count is preserved.
        for table, expected in seeded_counts.items():
            actual = int(
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            )
            assert actual == expected, (
                f"{table}: {actual} rows after upgrade, expected {expected}"
            )

        # 3. The two new 0002 tables exist.
        assert _exists(connection, "table", "filter_rules")
        assert _exists(connection, "table", "queue_state")

        # 4. The four new runs columns and listing_exclusions.criteria_version.
        assert {
            "reason",
            "reason_counts_json",
            "stage_log_json",
            "criteria_snapshot_json",
        } <= set(_table_info(connection, "runs"))
        assert "criteria_version" in _table_info(connection, "listing_exclusions")

        # 5. The new named CHECK is present and the pre-existing named CHECKs
        #    survived the batch recreation; the constraints are enforced.
        runs_sql = _master(connection, "table", "runs")["sql"]
        assert "ck_runs_reason" in runs_sql
        assert "ck_runs_trigger" in runs_sql
        assert "ck_runs_status" in runs_sql

        connection.execute(
            "INSERT INTO runs (trigger, status, reason) VALUES ('manual', 'done', 'mixed')"
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO runs (trigger, status, reason) "
                "VALUES ('manual', 'done', 'invalid_reason')"
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO runs (trigger, status, reason) "
                "VALUES ('not_a_trigger', 'done', NULL)"
            )

        # 6. The 0002 listing_dupes indexes exist.
        dupes_indexes = _index_list(connection, "listing_dupes")
        assert dupes_indexes.get("uq_listing_dupes_pair") is not None
        assert dupes_indexes.get("ix_listing_dupes_dup_listing_id") is not None
    finally:
        connection.close()

