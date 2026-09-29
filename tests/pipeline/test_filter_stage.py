"""FILT-01 / FILT-02 — a stored rule rejects a listing and the run records why.

End to end: two boards persist their rows, the hard-filter stage loads the enabled
search's rules, evaluates them against the persisted listings, writes one
`listing_exclusions` row per firing rule, and the run reports the count. No model
call is made anywhere on this path.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import (
    FilterRule,
    Listing,
    ListingExclusion,
    LlmCall,
    Run,
    Search,
    Source,
)
from app.domain.run_reason import REASONS
from app.pipeline.run import NO_SOURCES_REASON, run_pipeline
from app.sources.base import (
    FetchBudget,
    FetchResult,
    JobSource,
    RawListing,
    SearchQuery,
    SourceCapabilities,
)

CRYPTO_TERM = "crypto"
SEARCH_VERSION = 3
SALARY_FLOOR = 70000

CAPABILITIES = SourceCapabilities(
    supports_salary=False,
    supports_salary_min_filter=True,
    supports_remote_flag=True,
    supports_seniority=False,
    supports_full_description_in_search=False,
    requires_second_pass_for_description=False,
    supports_offset_paging=True,
    max_results_per_query=1000,
)


class OneListingAdapter(JobSource):
    """A total adapter returning one scripted `RawListing` for its own board."""

    capabilities = CAPABILITIES

    def __init__(self, name: str, item: RawListing) -> None:
        self.name = name  # type: ignore[assignment]
        self._item = item

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "ok"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        return FetchResult(source=self.name, items=[self._item], status="ok", requests_used=1)  # type: ignore[arg-type]


def _raw(
    source: str,
    *,
    title: str,
    company: str,
    description: str,
    is_remote: bool | None = None,
) -> RawListing:
    return RawListing(
        source=source,  # type: ignore[arg-type]
        source_listing_id=f"{source}-1",
        source_url=f"https://{source}.example.com/jobs/1",
        direct_url=None,
        title=title,
        company_name=company,
        location_raw="Dublin, Ireland",
        description=description,
        is_remote=is_remote,
        posted_at=date(2026, 9, 1),
        # Deliberately NO salary on either listing: the salary_floor rule must not
        # reject an unknown (A2/A3).
        salary_min=None,
        salary_max=None,
        salary_interval=None,
    )


async def _register_sources(session_factory: async_sessionmaker[AsyncSession], *names: str) -> None:
    async with session_factory() as session:
        for name in names:
            session.add(Source(name=name, display_name=name.title()))
        await session.commit()


async def _seed_search(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """One enabled search carrying a keyword rule and a salary-floor rule."""
    now = datetime(2026, 9, 1, tzinfo=UTC)
    async with session_factory() as session:
        search = Search(
            name="Dublin Python",
            enabled=True,
            is_default=True,
            criteria_json={
                "keywords": "python",
                "location": "Dublin",
                "salary_floor": SALARY_FLOOR,
            },
            version=SEARCH_VERSION,
            created_at=now,
            updated_at=now,
        )
        session.add(search)
        await session.flush()
        session.add_all(
            [
                FilterRule(
                    search_id=search.id,
                    kind="exclude_keyword",
                    params_json={"terms": [CRYPTO_TERM], "fields": ["description"]},
                    enabled=True,
                    position=0,
                    created_at=now,
                    updated_at=now,
                ),
                FilterRule(
                    search_id=search.id,
                    kind="salary_floor",
                    params_json={"amount": SALARY_FLOOR, "currency": "EUR"},
                    enabled=True,
                    position=1,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        await session.commit()
        return int(search.id)


async def _count(session_factory: async_sessionmaker[AsyncSession], table: type) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(table)) or 0


async def test_a_stored_rule_rejects_a_listing_and_the_run_records_why(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _register_sources(session_factory, "linkedin", "indeed")
    await _seed_search(session_factory)
    linkedin = OneListingAdapter(
        "linkedin",
        _raw(
            "linkedin",
            title="Backend Engineer",
            company="Acme",
            description=f"We are building a {CRYPTO_TERM} trading desk.",
        ),
    )
    indeed = OneListingAdapter(
        "indeed",
        _raw(
            "indeed",
            title="Platform Engineer",
            company="Globex",
            description="Build the deployment platform.",
        ),
    )

    run_id = await run_pipeline("manual", None, session_factory, adapters=[linkedin, indeed])

    async with session_factory() as session:
        run = await session.get(Run, run_id)
        exclusions = (await session.execute(select(ListingExclusion))).scalars().all()
        listings = (await session.execute(select(Listing).order_by(Listing.id))).scalars().all()

    assert run is not None
    # --- exactly one rejection, with all five fields --------------------------
    assert len(exclusions) == 1
    exclusion = exclusions[0]
    assert exclusion.rule_kind == "exclude_keyword"
    assert exclusion.rule_id is not None and exclusion.rule_id.isdigit()
    assert exclusion.detail_json == {"term": CRYPTO_TERM, "field": "description", "count": 1}
    assert exclusion.run_id == run_id
    assert exclusion.criteria_version == SEARCH_VERSION

    # The exclusion is against the listing that carried the term.
    by_id = {listing.id: listing for listing in listings}
    assert by_id[exclusion.listing_id].company_norm == "acme"

    # --- the unknown salary was NOT a rejection reason (A2/A3) ----------------
    assert all(exclusion.rule_kind != "salary_floor" for exclusion in exclusions)
    assert len(exclusions) == 1, "the salary_floor rule must not fire on an unknown salary"

    # --- the run reports the exclusion, and made no model call ----------------
    # D-102: this zero is the D-94 optional-ranking posture (no fact store in the
    # hermetic lane), NOT "the pipeline wires no LLM caller". A full run reaches the
    # detached ranking task; ranking is optional and skips, so it writes zero
    # `llm_calls` rows. Do not restore D-49's wording here.
    assert run.filtered_count == 1
    assert await _count(session_factory, LlmCall) == 0

    # --- the exclusion evidence carries no listing prose ----------------------
    assert "trading desk" not in str(exclusion.detail_json)


async def test_each_exclusion_row_carries_its_own_searchs_criteria_version(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """WR-05: with rules from two searches, each row records its OWN search's version.

    A listing rejected by two enabled searches' rules (the A4 union scope) must not
    stamp search B's row with search A's `criteria_version`.
    """
    await _register_sources(session_factory, "linkedin")
    now = datetime(2026, 9, 1, tzinfo=UTC)
    async with session_factory() as session:
        first = Search(
            name="First",
            enabled=True,
            criteria_json={"keywords": "python"},
            version=3,
            created_at=now,
            updated_at=now,
        )
        second = Search(
            name="Second",
            enabled=True,
            criteria_json={"keywords": "python"},
            version=7,
            created_at=now,
            updated_at=now,
        )
        session.add_all([first, second])
        await session.flush()
        first_rule = FilterRule(
            search_id=first.id,
            kind="exclude_keyword",
            params_json={"terms": ["crypto"], "fields": ["description"]},
            enabled=True,
            position=0,
            created_at=now,
            updated_at=now,
        )
        second_rule = FilterRule(
            search_id=second.id,
            kind="exclude_keyword",
            params_json={"terms": ["nft"], "fields": ["description"]},
            enabled=True,
            position=0,
            created_at=now,
            updated_at=now,
        )
        session.add_all([first_rule, second_rule])
        await session.commit()
        first_rule_id = int(first_rule.id)
        second_rule_id = int(second_rule.id)

    linkedin = OneListingAdapter(
        "linkedin",
        _raw(
            "linkedin",
            title="Backend Engineer",
            company="Acme",
            description="crypto and nft both appear in this description.",
        ),
    )

    await run_pipeline("manual", None, session_factory, adapters=[linkedin])

    async with session_factory() as session:
        rows = (await session.execute(select(ListingExclusion))).scalars().all()

    versions = {row.rule_id: row.criteria_version for row in rows}
    assert versions == {str(first_rule_id): 3, str(second_rule_id): 7}, (
        "each exclusion row must carry its own owning search's criteria_version"
    )


async def test_two_identical_runs_append_one_exclusion_row_each(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """D-36: per-run observations, append-only — never an update of the prior row."""
    await _register_sources(session_factory, "linkedin", "indeed")
    await _seed_search(session_factory)
    linkedin = OneListingAdapter(
        "linkedin",
        _raw(
            "linkedin",
            title="Backend Engineer",
            company="Acme",
            description=f"We are building a {CRYPTO_TERM} trading desk.",
        ),
    )
    indeed = OneListingAdapter(
        "indeed",
        _raw(
            "indeed",
            title="Platform Engineer",
            company="Globex",
            description="Build the deployment platform.",
        ),
    )

    first_run = await run_pipeline("manual", None, session_factory, adapters=[linkedin, indeed])
    second_run = await run_pipeline("manual", None, session_factory, adapters=[linkedin, indeed])

    async with session_factory() as session:
        exclusions = (
            (await session.execute(select(ListingExclusion).order_by(ListingExclusion.run_id)))
            .scalars()
            .all()
        )

    assert len(exclusions) == 2, "one exclusion row per run, never an update"
    assert [exclusion.run_id for exclusion in exclusions] == [first_run, second_run]
    assert all(exclusion.rule_kind == "exclude_keyword" for exclusion in exclusions)


async def test_no_enabled_search_means_no_filtering(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """An empty enabled-search set is not `no_sources_enabled` — the run still works."""
    await _register_sources(session_factory, "linkedin")
    linkedin = OneListingAdapter(
        "linkedin",
        _raw(
            "linkedin",
            title="Backend Engineer",
            company="Acme",
            description=f"We are building a {CRYPTO_TERM} trading desk.",
        ),
    )

    run_id = await run_pipeline("manual", None, session_factory, adapters=[linkedin])

    async with session_factory() as session:
        run = await session.get(Run, run_id)

    assert run is not None
    assert run.filtered_count == 0
    assert await _count(session_factory, ListingExclusion) == 0


# --- RUN-03 / D-44: the reason is persisted on every run -----------------------


async def test_a_run_with_zero_resolved_adapters_is_no_sources_enabled(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The empty-corpus boundary recognises the existing `NO_SOURCES_REASON`.

    No second vocabulary is minted: the machine-readable enum value names exactly
    the condition the Phase-1 error record already describes.
    """
    run_id = await run_pipeline("manual", None, session_factory, adapters=[])

    async with session_factory() as session:
        run = await session.get(Run, run_id)

    assert run is not None
    assert run.reason == "no_sources_enabled"
    assert isinstance(run.reason_counts_json, dict)
    assert run.reason_counts_json["adapters_resolved"] == 0
    assert any(
        entry.get("error") == NO_SOURCES_REASON for entry in (run.errors_json or [])
    ), "the Phase-1 no-sources record must still be present"


async def test_the_run_persists_a_reason_and_its_counts_on_every_run(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Even a healthy run explains itself — the history page renders it unconditionally."""
    await _register_sources(session_factory, "indeed")
    await _seed_search(session_factory)
    indeed = OneListingAdapter(
        "indeed",
        _raw(
            "indeed",
            title="Platform Engineer",
            company="Globex",
            description="Build the deployment platform.",
        ),
    )

    run_id = await run_pipeline("manual", None, session_factory, adapters=[indeed])

    async with session_factory() as session:
        run = await session.get(Run, run_id)

    assert run is not None
    assert run.reason in REASONS
    counts = run.reason_counts_json
    assert isinstance(counts, dict)
    for key in (
        "adapters_resolved",
        "sources",
        "excluded_by_rule",
        "survivors",
        "duplicates_already_seen",
        "capability_warnings",
    ):
        assert key in counts, f"reason_counts_json is missing {key!r}"
    assert counts["adapters_resolved"] == 1
    assert counts["survivors"] == 1
    assert counts["excluded_by_rule"] == {}
    assert isinstance(counts["duplicates_already_seen"], int)
    assert counts["sources"]["indeed"]["fetched"] == 1
    # Plain values only: the counts round-trip through JSON unchanged.
    assert json.loads(json.dumps(counts)) == counts


async def test_a_run_whose_every_listing_was_filtered_is_all_filtered(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """`all_filtered` is decidable because exclusions were actually recorded."""
    await _register_sources(session_factory, "linkedin")
    await _seed_search(session_factory)
    linkedin = OneListingAdapter(
        "linkedin",
        _raw(
            "linkedin",
            title="Backend Engineer",
            company="Acme",
            description=f"We are building a {CRYPTO_TERM} trading desk.",
        ),
    )

    run_id = await run_pipeline("manual", None, session_factory, adapters=[linkedin])

    async with session_factory() as session:
        run = await session.get(Run, run_id)

    assert run is not None
    assert run.reason == "all_filtered"
    counts = run.reason_counts_json
    assert counts["survivors"] == 0
    assert sum(counts["excluded_by_rule"].values()) == 1
    assert counts["sources"]["linkedin"]["fetched"] == 1


# --- the search's own seniority criterion (implicit rule) ----------------------


async def _seed_seniority_search(
    session_factory: async_sessionmaker[AsyncSession], seniority: list[str]
) -> int:
    """One enabled search whose only filter is its fetch-side seniority criterion."""
    now = datetime(2026, 9, 1, tzinfo=UTC)
    async with session_factory() as session:
        search = Search(
            name="Junior roles",
            enabled=True,
            criteria_json={"keywords": "python", "seniority": seniority},
            version=5,
            created_at=now,
            updated_at=now,
        )
        session.add(search)
        await session.commit()
        return int(search.id)


async def test_a_searchs_own_seniority_criterion_excludes_only_known_mismatches(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The saved criterion is enforced with no re-save, no FilterRule and no migration.

    A known `senior` listing is excluded; a `junior` listing and an unknown-`None`
    listing both pass (the default unknown-passes policy).
    """
    await _register_sources(session_factory, "linkedin", "indeed", "adzuna")
    search_id = await _seed_seniority_search(session_factory, ["junior", "graduate"])
    senior = OneListingAdapter(
        "linkedin",
        _raw(
            "linkedin",
            title="Senior Backend Engineer",
            company="Acme",
            description="Build things.",
        ),
    )
    junior = OneListingAdapter(
        "indeed",
        _raw(
            "indeed",
            title="Junior Backend Engineer",
            company="Globex",
            description="Learn things.",
        ),
    )
    unknown = OneListingAdapter(
        "adzuna",
        _raw("adzuna", title="Backend Engineer", company="Initech", description="Ship things."),
    )

    run_id = await run_pipeline("manual", None, session_factory, adapters=[senior, junior, unknown])

    async with session_factory() as session:
        run = await session.get(Run, run_id)
        exclusions = (await session.execute(select(ListingExclusion))).scalars().all()
        listings = (await session.execute(select(Listing).order_by(Listing.id))).scalars().all()

    assert run is not None
    assert run.filtered_count == 1, "only the known senior listing is excluded"
    assert len(exclusions) == 1
    exclusion = exclusions[0]
    assert exclusion.rule_kind == "seniority"
    assert exclusion.rule_id == f"search:{search_id}:seniority"
    assert exclusion.criteria_version == 5, "the implicit rule stamps its search's version"
    assert exclusion.detail_json["allow"] == ["junior", "graduate"]

    excluded_listing = next(listing for listing in listings if listing.id == exclusion.listing_id)
    assert excluded_listing.company_norm == "acme", "the senior listing is the one excluded"
    assert run.reason_counts_json["survivors"] == 2
    assert run.reason_counts_json["excluded_by_rule"] == {
        f"search:{search_id}:seniority": 1
    }


async def test_a_graduate_criterion_matches_a_listing_stored_as_junior(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """`graduate` is normalised to the stored vocabulary, so it is no longer dead weight.

    A listing titled "Graduate ..." is stored as `junior` by the ingest heuristic; a
    criterion of `["graduate"]` must keep it and exclude a `senior` listing.
    """
    await _register_sources(session_factory, "linkedin", "indeed")
    search_id = await _seed_seniority_search(session_factory, ["graduate"])
    senior = OneListingAdapter(
        "linkedin",
        _raw(
            "linkedin",
            title="Senior Backend Engineer",
            company="Acme",
            description="Build things.",
        ),
    )
    graduate = OneListingAdapter(
        "indeed",
        _raw(
            "indeed",
            title="Graduate Backend Engineer",
            company="Globex",
            description="Learn things.",
        ),
    )

    run_id = await run_pipeline("manual", None, session_factory, adapters=[senior, graduate])

    async with session_factory() as session:
        run = await session.get(Run, run_id)
        exclusions = (await session.execute(select(ListingExclusion))).scalars().all()
        listings = (await session.execute(select(Listing).order_by(Listing.id))).scalars().all()

    assert run is not None
    assert run.filtered_count == 1, "only the senior listing is excluded"
    assert len(exclusions) == 1
    assert exclusions[0].rule_id == f"search:{search_id}:seniority"
    excluded_listing = next(
        listing for listing in listings if listing.id == exclusions[0].listing_id
    )
    assert excluded_listing.company_norm == "acme"



# --- the search's own work mode (implicit hard filter) -------------------------


async def _seed_work_mode_search(
    session_factory: async_sessionmaker[AsyncSession], work_mode: str
) -> int:
    """One enabled search whose only criterion is a work mode."""
    now = datetime(2026, 9, 1, tzinfo=UTC)
    async with session_factory() as session:
        search = Search(
            name=f"{work_mode} roles",
            enabled=True,
            criteria_json={"keywords": "python", "work_mode": work_mode},
            version=6,
            created_at=now,
            updated_at=now,
        )
        session.add(search)
        await session.commit()
        return int(search.id)


async def _run_work_mode(
    session_factory: async_sessionmaker[AsyncSession], work_mode: str
) -> tuple[int, list[str]]:
    """Seed `remote`/`onsite`/`hybrid`/`any`, fetch one listing per flag, return ids excluded."""
    await _register_sources(session_factory, "linkedin", "indeed", "adzuna")
    await _seed_work_mode_search(session_factory, work_mode)
    adapters = [
        OneListingAdapter(
            "linkedin",
            _raw(
                "linkedin",
                title="Remote Role",
                company="Acme",
                description="Remote.",
                is_remote=True,
            ),
        ),
        OneListingAdapter(
            "indeed",
            _raw(
                "indeed",
                title="Onsite Role",
                company="Globex",
                description="Onsite.",
                is_remote=False,
            ),
        ),
        OneListingAdapter(
            "adzuna",
            _raw("adzuna", title="Unknown Role", company="Initech", description="?"),
        ),
    ]
    run_id = await run_pipeline("manual", None, session_factory, adapters=adapters)
    async with session_factory() as session:
        exclusions = (await session.execute(select(ListingExclusion))).scalars().all()
        listings = (await session.execute(select(Listing).order_by(Listing.id))).scalars().all()
    by_id = {listing.id: listing for listing in listings}
    excluded = sorted(by_id[row.listing_id].company_norm for row in exclusions)
    return run_id, excluded


async def test_work_mode_remote_excludes_only_a_known_non_remote_listing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id, excluded = await _run_work_mode(session_factory, "remote")

    assert excluded == ["globex"], "only the remote=False listing is excluded"

    async with session_factory() as session:
        run = await session.get(Run, run_id)
        rows = (await session.execute(select(ListingExclusion))).scalars().all()

    assert run is not None and run.filtered_count == 1
    assert len(rows) == 1
    assert rows[0].rule_kind == "remote"
    assert rows[0].detail_json == {"remote_flag": False, "require": True}
    assert rows[0].criteria_version == 6


async def test_work_mode_onsite_excludes_only_a_known_remote_listing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id, excluded = await _run_work_mode(session_factory, "onsite")

    assert excluded == ["acme"], "only the remote=True listing is excluded"

    async with session_factory() as session:
        run = await session.get(Run, run_id)
        rows = (await session.execute(select(ListingExclusion))).scalars().all()

    assert run is not None and run.filtered_count == 1
    assert rows[0].detail_json == {"remote_flag": True, "require": True}


async def test_work_mode_hybrid_filters_nothing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id, excluded = await _run_work_mode(session_factory, "hybrid")

    assert excluded == [], "hybrid is a ranking hint, never a filter"
    async with session_factory() as session:
        run = await session.get(Run, run_id)
    assert run is not None and run.filtered_count == 0


async def test_work_mode_any_is_a_no_op(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id, excluded = await _run_work_mode(session_factory, "any")

    assert excluded == [], "any filters nothing"
    async with session_factory() as session:
        run = await session.get(Run, run_id)
    assert run is not None and run.filtered_count == 0

