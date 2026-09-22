"""SRC-10 / T-01-09 — PII cannot be represented in the Phase 1 schema.

The control is *negative and structural*: `RawListing` has no `emails` field, and
the schema must give PII nowhere to land — no email/phone-shaped column on any
table, and no unaccounted-for free-form JSON blob that could carry a recruiter
identifier. This test fails if a later migration adds either.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

# A column whose (lower-cased) name contains any of these is treating a personal
# identifier as storable. `telephone`/`phone` are both listed because neither is
# a substring of the other; plurals are covered by substring matching.
FORBIDDEN_NAME_SUBSTRINGS = (
    "email",
    "e_mail",
    "phone",
    "telephone",
    "mobile",
    "contact_number",
)

# Documented allow-list of every JSON column in migration 0001, per table. A new
# free-form blob must be added here deliberately (and justified) or this fails.
EXPECTED_JSON_COLUMNS: dict[str, frozenset[str]] = {
    "sources": frozenset(
        {
            "capabilities_json",
            "rate_limit_json",
            "quota_json",
            "robots_policy_json",
            "field_fill_baseline_json",
        }
    ),
    "companies": frozenset({"aliases_json"}),
    "listings": frozenset({"quality_signals_json", "source_extras_json"}),
    "listing_dupes": frozenset({"snapshot_json"}),
    "listing_events": frozenset({"context_json"}),
    "listing_exclusions": frozenset({"detail_json"}),
    "searches": frozenset({"criteria_json"}),
    # 0002 adds filter_rules.params_json (rule vocabulary + params only — never
    # listing text) and the three new `runs` JSON columns. The one-row watermark
    # table has no JSON column at all, so it must NOT appear here.
    "filter_rules": frozenset({"params_json"}),
    "runs": frozenset(
        {
            "source_counts_json",
            "errors_json",
            "reason_counts_json",
            "stage_log_json",
            "criteria_snapshot_json",
        }
    ),
    "scores": frozenset(
        {"factor_scores_json", "weights_json", "strengths_json", "gaps_json"}
    ),
    # 0004 adds the single-row global weights document. It carries six floats and
    # nothing else — no listing text, no model prose, no identifier.
    "ranking_config": frozenset({"weights_json"}),
    "cv_versions": frozenset({"facts_json"}),
    "cv_artifacts": frozenset(
        {"patch_json", "change_log_json", "verification_json", "ats_checks_json"}
    ),
    "applications": frozenset(),
    "application_events": frozenset(),
    "llm_calls": frozenset(),
    "source_request_log": frozenset(),
}


def _tables(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    return [row["name"] for row in rows]


def _columns(connection: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    # PRAGMA does not accept bound parameters; the table name comes from our own
    # `sqlite_master`, never from external input.
    return connection.execute(f"PRAGMA table_info({table})").fetchall()


def test_no_email_or_phone_columns(migrated_db: Path) -> None:
    """Every table discovered from sqlite_master is scanned via PRAGMA table_info."""
    connection = sqlite3.connect(migrated_db)
    connection.row_factory = sqlite3.Row
    try:
        offenders: list[str] = []
        scanned = 0
        for table in _tables(connection):
            for column in _columns(connection, table):
                scanned += 1
                name = str(column["name"]).casefold()
                if any(token in name for token in FORBIDDEN_NAME_SUBSTRINGS):
                    offenders.append(f"{table}.{column['name']}")
        assert scanned > 0, "no columns were scanned — the discovered table list is empty"
        assert offenders == [], f"PII-shaped columns are storable: {offenders}"
    finally:
        connection.close()


def test_json_columns_are_allow_listed(migrated_db: Path) -> None:
    """A new JSON blob carrying recruiter PII would fail this test."""
    connection = sqlite3.connect(migrated_db)
    connection.row_factory = sqlite3.Row
    try:
        discovered: dict[str, list[str]] = {}
        for table in _tables(connection):
            json_columns = [
                column["name"]
                for column in _columns(connection, table)
                if str(column["type"]).upper() == "JSON"
            ]
            if json_columns:
                discovered[table] = sorted(json_columns)
    finally:
        connection.close()

    expected = {
        table: sorted(columns)
        for table, columns in EXPECTED_JSON_COLUMNS.items()
        if columns
    }
    assert discovered == expected, (
        "the JSON-column allow-list has drifted; add any new column deliberately "
        f"only after checking it cannot carry PII. discovered={discovered}"
    )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
