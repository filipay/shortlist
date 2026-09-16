"""CRIT-01 — a named search and its typed rules are created from the browser.

This is the write-surface lane: the form fields become `searches.criteria_json` and
`filter_rules.params_json`, validation rejects a bad shape before any insert, the
version moves to reflect a change, and user text is escaped on the way back out.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import FilterRule, Search, Source  # noqa: F401 — Source seeds FKs elsewhere

#: A name carrying a real HTML tag. The payload is asserted whole (not by tag name)
#: because `base.html` legitimately contains `<script src=...>`.
XSS_NAME = "<script>x</script> Senior Search"
ESCAPED_XSS_NAME = "&lt;script&gt;x&lt;/script&gt; Senior Search"


async def _search_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[Search]:
    async with session_factory() as session:
        return list(
            (await session.execute(select(Search).order_by(Search.id))).scalars().all()
        )


async def _only_search_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    rows = await _search_rows(session_factory)
    assert len(rows) == 1
    return int(rows[0].id)


async def _rule_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[FilterRule]:
    async with session_factory() as session:
        return list(
            (await session.execute(select(FilterRule).order_by(FilterRule.id)))
            .scalars()
            .all()
        )


async def test_post_searches_persists_a_version_one_enabled_search(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    response = await client.post(
        "/searches",
        data={"name": "Dublin Python", "keywords": "python", "location": "Dublin"},
    )

    assert response.status_code == 200
    assert "Dublin Python" in response.text

    rows = await _search_rows(session_factory)
    assert len(rows) == 1
    stored = rows[0]
    assert stored.name == "Dublin Python"
    assert stored.enabled is True
    assert stored.version == 1
    assert stored.criteria_json == {"keywords": "python", "location": "Dublin"}


async def test_post_searches_with_an_empty_name_writes_no_row(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    response = await client.post("/searches", data={"name": "   "})

    assert response.status_code == 200
    assert "needs a name" in response.text
    assert await _search_rows(session_factory) == []


async def test_a_negative_salary_floor_in_the_search_form_writes_no_row(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    response = await client.post(
        "/searches", data={"name": "Bad", "salary_floor": "-1"}
    )

    assert response.status_code == 200
    assert "negative" in response.text.lower()
    assert await _search_rows(session_factory) == []


async def test_post_rule_round_trips_and_bumps_the_owning_search_version(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await client.post("/searches", data={"name": "Dublin Python", "keywords": "python"})
    search_id = await _only_search_id(session_factory)

    response = await client.post(
        f"/searches/{search_id}/rules",
        data={
            "kind": "exclude_keyword",
            "keyword_terms": "crypto, nft",
            "keyword_fields": ["title", "description"],
        },
    )

    assert response.status_code == 200
    rules = await _rule_rows(session_factory)
    assert len(rules) == 1
    assert rules[0].kind == "exclude_keyword"
    assert rules[0].params_json == {
        "terms": ["crypto", "nft"],
        "fields": ["title", "description"],
    }
    assert rules[0].enabled is True

    async with session_factory() as session:
        stored = await session.get(Search, search_id)
    assert stored is not None
    assert stored.version == 2, "creating a rule is a criteria change"


async def test_a_negative_salary_floor_rule_is_rejected_and_writes_no_row(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await client.post("/searches", data={"name": "Dublin Python"})
    search_id = await _only_search_id(session_factory)

    response = await client.post(
        f"/searches/{search_id}/rules",
        data={"kind": "salary_floor", "salary_amount": "-5", "salary_currency": "EUR"},
    )

    assert response.status_code == 400
    assert "non-negative" in response.text
    assert await _rule_rows(session_factory) == []


async def test_an_unknown_rule_kind_is_rejected_and_writes_no_row(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await client.post("/searches", data={"name": "Dublin Python"})
    search_id = await _only_search_id(session_factory)

    response = await client.post(
        f"/searches/{search_id}/rules", data={"kind": "not_a_kind"}
    )

    assert response.status_code == 400
    assert "unknown rule kind" in response.text
    assert await _rule_rows(session_factory) == []


async def test_get_searches_lists_a_search_and_its_rule(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await client.post("/searches", data={"name": "Dublin Python", "keywords": "python"})
    search_id = await _only_search_id(session_factory)
    await client.post(
        f"/searches/{search_id}/rules",
        data={"kind": "exclude_keyword", "keyword_terms": "crypto"},
    )

    response = await client.get("/searches")

    assert response.status_code == 200
    assert 'id="criteria-list"' in response.text
    assert "Dublin Python" in response.text
    assert "exclude_keyword" in response.text
    assert "crypto" in response.text


async def test_the_criteria_routes_answer_rather_than_404(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The seam guard proves `current_user`; this proves the routes are mounted."""
    assert (await client.get("/searches")).status_code == 200
    assert (await client.post("/searches", data={"name": "One"})).status_code == 200
    search_id = await _only_search_id(session_factory)
    assert (
        await client.post(
            f"/searches/{search_id}/rules", data={"kind": "remote", "remote_require": "1"}
        )
    ).status_code == 200


async def test_a_search_name_containing_a_tag_is_escaped_on_the_page(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Jinja autoescape is the render-time guarantee, independent of the store-time sanitiser."""
    now = datetime(2026, 9, 1, tzinfo=UTC)
    async with session_factory() as session:
        session.add(
            Search(
                name=XSS_NAME,
                enabled=True,
                criteria_json={"keywords": "python"},
                version=1,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

    response = await client.get("/searches")

    assert response.status_code == 200
    assert ESCAPED_XSS_NAME in response.text
    assert XSS_NAME not in response.text
