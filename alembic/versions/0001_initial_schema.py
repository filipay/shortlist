"""initial schema — the one-way migration 0001

Revision ID: 0001
Revises:
Create Date: 2026-09-15

This is the phase's **one-way door** (D-20). It creates every table of the
canonical schema, both Tier-1 dedup indexes, explicitly named CHECK constraints,
the append-only `listing_events` triggers, and the FTS5 external-content index
with its three maintenance triggers. Nothing in this revision can be backfilled
after real rows exist, so the 9-item acceptance checklist
(`tests/db/test_migration_contract.py`) is the gate.

Raw DDL grouped first, then the CREATE TABLE calls, then the FTS5 objects, then
the indexes.

FTS5 remedy for any future migration that creates the index *after* rows exist:
    INSERT INTO listing_fts(listing_fts) VALUES('rebuild');
Creating the triggers does not copy pre-existing content rows into the index.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Tables
    # ------------------------------------------------------------------
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("transport", sa.String(32)),
        sa.Column("capabilities_json", sa.JSON),
        sa.Column("rate_limit_json", sa.JSON),
        sa.Column("quota_json", sa.JSON),
        sa.Column("last_probe_at", sa.DateTime),
        sa.Column("health", sa.String(16)),
        sa.Column("tos_audited_at", sa.DateTime),
        sa.Column("robots_policy_json", sa.JSON),
        sa.Column("field_fill_baseline_json", sa.JSON),
        sa.Column("baseline_recorded_at", sa.DateTime),
        sa.UniqueConstraint("name", name="uq_sources_name"),
        sa.CheckConstraint(
            "health IS NULL OR health IN ('ok','degraded','unreachable')",
            name="ck_sources_health",
        ),
    )

    op.create_table(
        "companies",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("name_norm", sa.String(255), nullable=False),
        sa.Column("aliases_json", sa.JSON),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("name_norm", name="uq_companies_name_norm"),
    )

    op.create_table(
        "searches",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("criteria_json", sa.JSON),
        sa.Column("schedule_cron", sa.String(64)),
        sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("last_run_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("search_id", sa.Integer, sa.ForeignKey("searches.id")),
        sa.Column("trigger", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("source_counts_json", sa.JSON),
        sa.Column("fetched_count", sa.Integer),
        sa.Column("deduped_count", sa.Integer),
        sa.Column("filtered_count", sa.Integer),
        sa.Column("ranked_count", sa.Integer),
        sa.Column("llm_calls", sa.Integer),
        sa.Column("llm_tokens", sa.Integer),
        sa.Column("errors_json", sa.JSON),
        sa.CheckConstraint("trigger IN ('manual','schedule')", name="ck_runs_trigger"),
        sa.CheckConstraint(
            "status IN ('running','done','failed','partial')", name="ck_runs_status"
        ),
    )

    op.create_table(
        "listings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("canonical_url", sa.Text, nullable=False),
        sa.Column("apply_url", sa.Text),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("title_norm", sa.String(512)),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id")),
        sa.Column("company_norm", sa.String(255)),
        sa.Column("location_raw", sa.String(512)),
        sa.Column("city", sa.String(128)),
        sa.Column("region", sa.String(128)),
        sa.Column("country_code", sa.String(2)),
        sa.Column("location_norm", sa.String(255)),
        sa.Column("remote_flag", sa.Boolean),
        sa.Column("seniority", sa.String(64)),
        sa.Column("description", sa.Text),
        sa.Column("description_hash", sa.String(64)),
        sa.Column("salary_min", sa.Float),
        sa.Column("salary_max", sa.Float),
        sa.Column("salary_interval", sa.String(32)),
        sa.Column("salary_currency", sa.String(8)),
        sa.Column("salary_source", sa.String(32)),
        sa.Column("posted_at", sa.DateTime),
        # D-20 item 1 — cannot be backfilled, all three NOT NULL.
        sa.Column("first_seen_at", sa.DateTime, nullable=False),
        sa.Column("last_seen_at", sa.DateTime, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("inactive_since", sa.DateTime),
        sa.Column("quality_signals_json", sa.JSON),
        sa.Column("source_extras_json", sa.JSON),
        sa.Column("blocking_key", sa.String(255)),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("canonical_url", name="uq_listings_canonical_url"),
    )

    op.create_table(
        "listing_sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("listing_id", sa.Integer, sa.ForeignKey("listings.id"), nullable=False),
        sa.Column("source", sa.String(32), sa.ForeignKey("sources.name"), nullable=False),
        # NULLABLE — verified JobSpy contract; this is why the unique index is partial.
        sa.Column("source_listing_id", sa.String(255)),
        sa.Column("source_url", sa.Text, nullable=False),
        sa.Column("canonical_source_url", sa.Text, nullable=False),
        sa.Column("direct_url", sa.Text),
        sa.Column("first_seen_at", sa.DateTime, nullable=False),
        sa.Column("last_seen_at", sa.DateTime, nullable=False),
        sa.Column("raw_hash", sa.String(64), nullable=False),
    )

    op.create_table(
        "listing_dupes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("listing_id", sa.Integer, sa.ForeignKey("listings.id"), nullable=False),
        sa.Column("dup_listing_id", sa.Integer, sa.ForeignKey("listings.id"), nullable=False),
        sa.Column("method", sa.String(32)),
        sa.Column("score", sa.Float),
        sa.Column("snapshot_json", sa.JSON),
        sa.Column("merged_at", sa.DateTime),
        sa.Column("reverted_at", sa.DateTime),
        sa.Column("reverted_by", sa.String(64)),
    )

    op.create_table(
        "listing_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("listing_id", sa.Integer, sa.ForeignKey("listings.id"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("occurred_at", sa.DateTime, nullable=False),
        sa.Column("context_json", sa.JSON),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("runs.id")),
        sa.CheckConstraint(
            "event_type IN ('save','unsave','hide','unhide','shortlist','view')",
            name="ck_listing_events_event_type",
        ),
    )

    op.create_table(
        "listing_exclusions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("listing_id", sa.Integer, sa.ForeignKey("listings.id"), nullable=False),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("runs.id")),
        sa.Column("rule_id", sa.String(64)),
        sa.Column("rule_kind", sa.String(32)),
        sa.Column("detail_json", sa.JSON),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "scores",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("listing_id", sa.Integer, sa.ForeignKey("listings.id"), nullable=False),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("search_id", sa.Integer, sa.ForeignKey("searches.id")),
        sa.Column("criteria_version", sa.Integer),
        sa.Column("rubric_version", sa.String(32)),
        sa.Column("backend", sa.String(32)),
        sa.Column("provider", sa.String(64)),
        sa.Column("model", sa.String(128)),
        sa.Column("factor_scores_json", sa.JSON),
        sa.Column("total_score", sa.Float),
        sa.Column("weights_json", sa.JSON),
        sa.Column("confidence_tier", sa.String(16)),
        sa.Column("rationale", sa.Text),
        sa.Column("strengths_json", sa.JSON),
        sa.Column("gaps_json", sa.JSON),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint(
            "listing_id", "run_id", "criteria_version",
            name="uq_scores_listing_run_criteria",
        ),
        sa.CheckConstraint(
            "confidence_tier IS NULL OR confidence_tier IN ('high','medium','low')",
            name="ck_scores_confidence_tier",
        ),
    )

    op.create_table(
        "cv_versions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("label", sa.String(128)),
        sa.Column("schema_version", sa.String(32)),
        sa.Column("facts_json", sa.JSON),
        sa.Column("source", sa.String(16)),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("is_current", sa.Boolean, nullable=False, server_default=sa.text("0")),
    )

    op.create_table(
        "cv_artifacts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("listing_id", sa.Integer, sa.ForeignKey("listings.id")),
        sa.Column("base_cv_version_id", sa.Integer, sa.ForeignKey("cv_versions.id")),
        sa.Column("patch_json", sa.JSON),
        sa.Column("change_log_json", sa.JSON),
        sa.Column("tex_path", sa.Text),
        sa.Column("pdf_path", sa.Text),
        sa.Column("tex_hash", sa.String(64)),
        sa.Column("pdf_hash", sa.String(64)),
        sa.Column("compiled_at", sa.DateTime),
        sa.Column("compile_status", sa.String(16), nullable=False),
        sa.Column("compile_log", sa.Text),
        sa.Column("verification_json", sa.JSON),
        sa.Column("page_count", sa.Integer),
        sa.Column("ats_checks_json", sa.JSON),
        sa.Column("backend", sa.String(32)),
        sa.Column("provider", sa.String(64)),
        sa.Column("model", sa.String(128)),
        sa.Column("created_at", sa.DateTime, nullable=False),
        # D-20 item 4 — explicitly NAMED so a later batch_alter_table recreation
        # does not silently drop it.
        sa.CheckConstraint(
            "compile_status IN ('ok','failed','blocked')",
            name="ck_cv_artifacts_compile_status",
        ),
    )

    op.create_table(
        "applications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("listing_id", sa.Integer, sa.ForeignKey("listings.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        # D-20 item 5 — the verified-artefact <-> outcome link.
        sa.Column("cv_artifact_id", sa.Integer, sa.ForeignKey("cv_artifacts.id")),
        sa.Column("applied_at", sa.DateTime),
        sa.Column("next_action_at", sa.DateTime),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.CheckConstraint(
            "status IN ('discovered','queued','shortlisted','applied',"
            "'interviewing','offer','rejected','withdrawn')",
            name="ck_applications_status",
        ),
    )

    op.create_table(
        "application_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "application_id", sa.Integer, sa.ForeignKey("applications.id"), nullable=False
        ),
        sa.Column("from_status", sa.String(16)),
        sa.Column("to_status", sa.String(16), nullable=False),
        sa.Column("occurred_at", sa.DateTime, nullable=False),
        sa.Column("note", sa.Text),
    )

    op.create_table(
        "llm_calls",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("runs.id")),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("backend", sa.String(16)),
        sa.Column("provider", sa.String(64)),
        sa.Column("model", sa.String(128)),
        sa.Column("agent", sa.String(64)),
        sa.Column("prompt_tokens", sa.Integer),
        sa.Column("completion_tokens", sa.Integer),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.CheckConstraint(
            "purpose IN ('rank','narrate','tailor','extract','probe')",
            name="ck_llm_calls_purpose",
        ),
        sa.CheckConstraint(
            "status IN ('ok','invalid','timeout','error')",
            name="ck_llm_calls_status",
        ),
    )

    op.create_table(
        "source_request_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source", sa.String(32), sa.ForeignKey("sources.name"), nullable=False),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("runs.id")),
        sa.Column("occurred_at", sa.DateTime, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status_code", sa.Integer),
        sa.Column("ok", sa.Boolean),
        sa.Column("note", sa.Text),
        sa.CheckConstraint(
            "kind IN ('search','detail')", name="ck_source_request_log_kind"
        ),
    )

    # ------------------------------------------------------------------
    # 2. Raw DDL — append-only enforcement, FTS5 virtual table + triggers
    # ------------------------------------------------------------------
    # listing_events is append-only (acceptance item 2): UPDATE and DELETE abort.
    op.execute(
        "CREATE TRIGGER listing_events_no_update BEFORE UPDATE ON listing_events "
        "BEGIN SELECT RAISE(ABORT, 'listing_events is append-only'); END;"
    )
    op.execute(
        "CREATE TRIGGER listing_events_no_delete BEFORE DELETE ON listing_events "
        "BEGIN SELECT RAISE(ABORT, 'listing_events is append-only'); END;"
    )

    # FTS5 external-content virtual table. Alembic/SQLAlchemy have no
    # first-class construct for a virtual table; the DDL is the correct tool,
    # and the three triggers MUST ship with it or the index silently diverges.
    op.execute(
        "CREATE VIRTUAL TABLE listing_fts USING fts5("
        "title, company_norm, description, "
        "content='listings', content_rowid='id', "
        "tokenize='porter unicode61');"
    )
    op.execute(
        "CREATE TRIGGER listings_ai AFTER INSERT ON listings BEGIN "
        "INSERT INTO listing_fts(rowid, title, company_norm, description) "
        "VALUES (new.id, new.title, new.company_norm, new.description); "
        "END;"
    )
    op.execute(
        "CREATE TRIGGER listings_ad AFTER DELETE ON listings BEGIN "
        "INSERT INTO listing_fts(listing_fts, rowid, title, company_norm, description) "
        "VALUES('delete', old.id, old.title, old.company_norm, old.description); "
        "END;"
    )
    op.execute(
        "CREATE TRIGGER listings_au AFTER UPDATE ON listings BEGIN "
        "INSERT INTO listing_fts(listing_fts, rowid, title, company_norm, description) "
        "VALUES('delete', old.id, old.title, old.company_norm, old.description); "
        "INSERT INTO listing_fts(rowid, title, company_norm, description) "
        "VALUES (new.id, new.title, new.company_norm, new.description); "
        "END;"
    )

    # ------------------------------------------------------------------
    # 3. Indexes
    # ------------------------------------------------------------------
    # Acceptance item 6 / D-19 — BOTH Tier-1 dedup indexes.
    # `sqlite_where=` is the Alembic dialect-kwarg form for a partial index.
    op.create_index(
        "uq_listing_sources_source_sid",
        "listing_sources",
        ["source", "source_listing_id"],
        unique=True,
        sqlite_where=sa.text("source_listing_id IS NOT NULL"),
    )
    op.create_index(
        "uq_listing_sources_source_url",
        "listing_sources",
        ["source", "canonical_source_url"],
        unique=True,
    )
    op.create_index(
        "ix_listing_sources_listing_id", "listing_sources", ["listing_id"]
    )
    # Acceptance item 8 — blocking_key exists and is indexed.
    op.create_index("ix_listings_blocking_key", "listings", ["blocking_key"])
    op.create_index(
        "ix_listings_is_active_first_seen", "listings", ["is_active", "first_seen_at"]
    )
    op.create_index(
        "ix_listings_company_norm_title_norm", "listings", ["company_norm", "title_norm"]
    )
    op.create_index(
        "ix_listing_events_listing_occurred", "listing_events", ["listing_id", "occurred_at"]
    )
    op.create_index("ix_scores_listing_total", "scores", ["listing_id", "total_score"])


def downgrade() -> None:
    # One-way migration (D-20): there is no safe downgrade that preserves the
    # past-describing columns. The downgrade exists only so Alembic's tooling
    # stays coherent in a throwaway database.
    op.execute("DROP TRIGGER IF EXISTS listings_au")
    op.execute("DROP TRIGGER IF EXISTS listings_ad")
    op.execute("DROP TRIGGER IF EXISTS listings_ai")
    op.execute("DROP TABLE IF EXISTS listing_fts")
    op.execute("DROP TRIGGER IF EXISTS listing_events_no_delete")
    op.execute("DROP TRIGGER IF EXISTS listing_events_no_update")

    for index_name, table_name in (
        ("ix_scores_listing_total", "scores"),
        ("ix_listing_events_listing_occurred", "listing_events"),
        ("ix_listings_company_norm_title_norm", "listings"),
        ("ix_listings_is_active_first_seen", "listings"),
        ("ix_listings_blocking_key", "listings"),
        ("ix_listing_sources_listing_id", "listing_sources"),
        ("uq_listing_sources_source_url", "listing_sources"),
        ("uq_listing_sources_source_sid", "listing_sources"),
    ):
        op.drop_index(index_name, table_name=table_name)

    for table_name in (
        "source_request_log",
        "llm_calls",
        "application_events",
        "applications",
        "cv_artifacts",
        "cv_versions",
        "scores",
        "listing_exclusions",
        "listing_events",
        "listing_dupes",
        "listing_sources",
        "listings",
        "runs",
        "searches",
        "companies",
        "sources",
    ):
        op.drop_table(table_name)
