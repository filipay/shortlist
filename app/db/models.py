"""SQLAlchemy declarative models for the migration 0001 schema.

Status columns use ``sa.String`` plus **explicitly named** ``CheckConstraint``s —
never ``sa.Enum``, which emits an *unnamed* CHECK on SQLite and is silently
dropped by a later ``batch_alter_table`` table recreation (RESEARCH Mechanics 3).
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)

from app.db.base import Base


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True)
    name = Column(String(32), nullable=False)
    display_name = Column(String(128), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, server_default=text("1"))
    transport = Column(String(32))
    capabilities_json = Column(JSON)
    rate_limit_json = Column(JSON)
    quota_json = Column(JSON)
    last_probe_at = Column(DateTime)
    health = Column(String(16))
    tos_audited_at = Column(DateTime)
    robots_policy_json = Column(JSON)
    field_fill_baseline_json = Column(JSON)
    baseline_recorded_at = Column(DateTime)

    __table_args__ = (
        UniqueConstraint("name", name="uq_sources_name"),
        CheckConstraint(
            "health IS NULL OR health IN ('ok','degraded','unreachable')",
            name="ck_sources_health",
        ),
    )


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    name_norm = Column(String(255), nullable=False)
    aliases_json = Column(JSON)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (UniqueConstraint("name_norm", name="uq_companies_name_norm"),)


class FilterRule(Base):
    """A typed, ordered filter rule belonging to one search (D-34 / CRIT-01).

    ``kind`` is constrained by the explicitly named ``ck_filter_rules_kind``, so
    an unknown rule vocabulary cannot be persisted. The evaluators are pure
    functions in ``app/domain/filter.py``; this row is only its storage.
    """

    __tablename__ = "filter_rules"

    id = Column(Integer, primary_key=True)
    search_id = Column(Integer, ForeignKey("searches.id"), nullable=False)
    kind = Column(String(32), nullable=False)
    params_json = Column(JSON)
    enabled = Column(Boolean, nullable=False, default=True, server_default=text("1"))
    position = Column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "kind IN ('salary_floor','exclude_keyword','location','remote',"
            "'seniority','company_blocklist')",
            name="ck_filter_rules_kind",
        ),
        Index("ix_filter_rules_search_position", "search_id", "position"),
    )


class QueueState(Base):
    """The single-row last-visit watermark (D-39).

    ``last_queue_view_at`` is NULLABLE: ``NULL`` means "never viewed", so every
    listing is new until the queue is first opened.
    """

    __tablename__ = "queue_state"

    id = Column(Integer, primary_key=True)
    last_queue_view_at = Column(DateTime)
    updated_at = Column(DateTime, nullable=False)


class Listing(Base):
    """The canonical, deduped job."""

    __tablename__ = "listings"

    id = Column(Integer, primary_key=True)
    canonical_url = Column(Text, nullable=False)
    apply_url = Column(Text)
    title = Column(String(512), nullable=False)
    title_norm = Column(String(512))
    company_id = Column(Integer, ForeignKey("companies.id"))
    company_norm = Column(String(255))
    location_raw = Column(String(512))
    city = Column(String(128))
    region = Column(String(128))
    country_code = Column(String(2))
    location_norm = Column(String(255))
    remote_flag = Column(Boolean)
    seniority = Column(String(64))
    description = Column(Text)
    description_hash = Column(String(64))
    salary_min = Column(Float)
    salary_max = Column(Float)
    salary_interval = Column(String(32))
    salary_currency = Column(String(8))
    salary_source = Column(String(32))
    posted_at = Column(DateTime)
    # Cannot be backfilled (TS-2 / D-20 item 1) — all three are NOT NULL.
    first_seen_at = Column(DateTime, nullable=False)
    last_seen_at = Column(DateTime, nullable=False)
    content_hash = Column(String(64), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("1"))
    inactive_since = Column(DateTime)
    quality_signals_json = Column(JSON)
    source_extras_json = Column(JSON)
    blocking_key = Column(String(255))
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("canonical_url", name="uq_listings_canonical_url"),
        Index("ix_listings_blocking_key", "blocking_key"),
        Index("ix_listings_is_active_first_seen", "is_active", "first_seen_at"),
        Index("ix_listings_company_norm_title_norm", "company_norm", "title_norm"),
    )


class ListingSource(Base):
    """Many sources -> one listing. The payoff of pluggable adapters."""

    __tablename__ = "listing_sources"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    source = Column(String(32), ForeignKey("sources.name"), nullable=False)
    # NULLABLE — verified JobSpy contract (`id: str | None`). This is exactly why
    # the unique index below is PARTIAL.
    source_listing_id = Column(String(255))
    source_url = Column(Text, nullable=False)
    canonical_source_url = Column(Text, nullable=False)
    direct_url = Column(Text)
    first_seen_at = Column(DateTime, nullable=False)
    last_seen_at = Column(DateTime, nullable=False)
    raw_hash = Column(String(64), nullable=False)

    __table_args__ = (
        # Acceptance item 6 / D-19 — BOTH indexes; neither alone is sufficient.
        Index(
            "uq_listing_sources_source_sid",
            "source",
            "source_listing_id",
            unique=True,
            sqlite_where=text("source_listing_id IS NOT NULL"),
        ),
        Index(
            "uq_listing_sources_source_url",
            "source",
            "canonical_source_url",
            unique=True,
        ),
        Index("ix_listing_sources_listing_id", "listing_id"),
    )


class ListingDupe(Base):
    """Audit + reversibility for Tier-2 merges (logic lands in Phase 2)."""

    __tablename__ = "listing_dupes"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    dup_listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    method = Column(String(32))
    score = Column(Float)
    snapshot_json = Column(JSON)
    merged_at = Column(DateTime)
    reverted_at = Column(DateTime)
    reverted_by = Column(String(64))

    __table_args__ = (
        # Stops a same-orientation re-insert of an already-merged/reverted pair.
        # It does NOT stop the reversed pair — the dedup stage still needs the
        # either-orientation negative-memory pre-check (plan 02-04).
        Index(
            "uq_listing_dupes_pair",
            "listing_id",
            "dup_listing_id",
            unique=True,
        ),
        # Makes the either-orientation negative-memory lookup index-usable.
        Index("ix_listing_dupes_dup_listing_id", "dup_listing_id"),
    )


class ListingEvent(Base):
    """APPEND-ONLY event log (acceptance item 2). Enforced by DB triggers."""

    __tablename__ = "listing_events"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    event_type = Column(String(32), nullable=False)
    occurred_at = Column(DateTime, nullable=False)
    context_json = Column(JSON)
    run_id = Column(Integer, ForeignKey("runs.id"))

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('save','unsave','hide','unhide','shortlist','view')",
            name="ck_listing_events_event_type",
        ),
        Index("ix_listing_events_listing_occurred", "listing_id", "occurred_at"),
    )


class ListingExclusion(Base):
    """"Why is this NOT in my queue?" (Phase 2 writes it; the home ships now)."""

    __tablename__ = "listing_exclusions"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    run_id = Column(Integer, ForeignKey("runs.id"))
    rule_id = Column(String(64))
    rule_kind = Column(String(32))
    detail_json = Column(JSON)
    created_at = Column(DateTime, nullable=False)
    # D-33 — the criteria version this rejection was observed against.
    criteria_version = Column(Integer)


class Search(Base):
    """A saved criteria set. Per-search `last_run_at` — never a global."""

    __tablename__ = "searches"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, server_default=text("1"))
    is_default = Column(Boolean, nullable=False, default=False, server_default=text("0"))
    criteria_json = Column(JSON)
    schedule_cron = Column(String(64))
    version = Column(Integer, nullable=False, default=1, server_default=text("1"))
    last_run_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class Run(Base):
    """One row per pipeline run — makes "why is the queue empty today?" answerable."""

    __tablename__ = "runs"

    id = Column(Integer, primary_key=True)
    search_id = Column(Integer, ForeignKey("searches.id"))
    trigger = Column(String(16), nullable=False)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    status = Column(String(16), nullable=False)
    source_counts_json = Column(JSON)
    fetched_count = Column(Integer)
    deduped_count = Column(Integer)
    filtered_count = Column(Integer)
    ranked_count = Column(Integer)
    llm_calls = Column(Integer)
    llm_tokens = Column(Integer)
    errors_json = Column(JSON)
    # D-44 / RUN-03 — NULL reason legitimately means "the queue was not empty".
    reason = Column(String(32))
    reason_counts_json = Column(JSON)
    stage_log_json = Column(JSON)
    # D-33 — the exact query + rules this run used.
    criteria_snapshot_json = Column(JSON)

    __table_args__ = (
        CheckConstraint(
            "trigger IN ('manual','schedule')",
            name="ck_runs_trigger",
        ),
        CheckConstraint(
            "status IN ('running','done','failed','partial')",
            name="ck_runs_status",
        ),
        CheckConstraint(
            "reason IS NULL OR reason IN ('no_sources_enabled','all_sources_failed',"
            "'zero_fetched','all_filtered','nothing_new','mixed')",
            name="ck_runs_reason",
        ),
    )


class Score(Base):
    """DF-3: per-factor decomposition, never one opaque number."""

    __tablename__ = "scores"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False)
    search_id = Column(Integer, ForeignKey("searches.id"))
    criteria_version = Column(Integer)
    rubric_version = Column(String(32))
    backend = Column(String(32))
    provider = Column(String(64))
    model = Column(String(128))
    factor_scores_json = Column(JSON)
    total_score = Column(Float)
    weights_json = Column(JSON)
    confidence_tier = Column(String(16))
    rationale = Column(Text)
    strengths_json = Column(JSON)
    gaps_json = Column(JSON)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "listing_id", "run_id", "criteria_version",
            name="uq_scores_listing_run_criteria",
        ),
        CheckConstraint(
            "confidence_tier IS NULL OR confidence_tier IN ('high','medium','low')",
            name="ck_scores_confidence_tier",
        ),
        Index("ix_scores_listing_total", "listing_id", "total_score"),
    )


class CvVersion(Base):
    __tablename__ = "cv_versions"

    id = Column(Integer, primary_key=True)
    label = Column(String(128))
    schema_version = Column(String(32))
    facts_json = Column(JSON)
    source = Column(String(16))
    created_at = Column(DateTime, nullable=False)
    is_current = Column(Boolean, nullable=False, default=False, server_default=text("0"))


class CvArtifact(Base):
    """Acceptance item 4: `verification_json` + a `compile_status` that can be 'blocked'."""

    __tablename__ = "cv_artifacts"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("listings.id"))
    base_cv_version_id = Column(Integer, ForeignKey("cv_versions.id"))
    patch_json = Column(JSON)
    change_log_json = Column(JSON)
    tex_path = Column(Text)
    pdf_path = Column(Text)
    tex_hash = Column(String(64))
    pdf_hash = Column(String(64))
    compiled_at = Column(DateTime)
    compile_status = Column(String(16), nullable=False)
    compile_log = Column(Text)
    verification_json = Column(JSON)
    page_count = Column(Integer)
    ats_checks_json = Column(JSON)
    backend = Column(String(32))
    provider = Column(String(64))
    model = Column(String(128))
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        # Explicitly NAMED — an unnamed CHECK would be dropped by a later
        # batch_alter_table recreation (RESEARCH Mechanics 3).
        CheckConstraint(
            "compile_status IN ('ok','failed','blocked')",
            name="ck_cv_artifacts_compile_status",
        ),
    )


class Application(Base):
    """Acceptance item 5: `cv_artifact_id` — the exact artefact that was sent."""

    __tablename__ = "applications"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    status = Column(String(16), nullable=False)
    cv_artifact_id = Column(Integer, ForeignKey("cv_artifacts.id"))
    applied_at = Column(DateTime)
    next_action_at = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('discovered','queued','shortlisted','applied',"
            "'interviewing','offer','rejected','withdrawn')",
            name="ck_applications_status",
        ),
    )


class ApplicationEvent(Base):
    __tablename__ = "application_events"

    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    from_status = Column(String(16))
    to_status = Column(String(16), nullable=False)
    occurred_at = Column(DateTime, nullable=False)
    note = Column(Text)


class LlmCall(Base):
    """Cost + audit. Phase 3 fills it; the table ships in 0001."""

    __tablename__ = "llm_calls"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id"))
    purpose = Column(String(16), nullable=False)
    backend = Column(String(16))
    provider = Column(String(64))
    model = Column(String(128))
    agent = Column(String(64))
    #: D-12 / PITFALLS M9 — the opencode server version this call ran against,
    #: read from `GET /global/health` (never `/doc`'s static spec version, P12).
    #: Migration 0003 adds it; nullable because older rows have no recorded value.
    server_version = Column(String(32))
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    latency_ms = Column(Integer)
    status = Column(String(16), nullable=False)
    attempts = Column(Integer)
    error = Column(Text)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "purpose IN ('rank','narrate','tailor','extract','probe')",
            name="ck_llm_calls_purpose",
        ),
        CheckConstraint(
            "status IN ('ok','invalid','timeout','error')",
            name="ck_llm_calls_status",
        ),
    )


class SourceRequestLog(Base):
    """Politeness + quota ledger — the evidence the probe verdict derives from."""

    __tablename__ = "source_request_log"

    id = Column(Integer, primary_key=True)
    source = Column(String(32), ForeignKey("sources.name"), nullable=False)
    run_id = Column(Integer, ForeignKey("runs.id"))
    occurred_at = Column(DateTime, nullable=False)
    kind = Column(String(16), nullable=False)
    status_code = Column(Integer)
    ok = Column(Boolean)
    note = Column(Text)

    __table_args__ = (
        CheckConstraint("kind IN ('search','detail')", name="ck_source_request_log_kind"),
    )
