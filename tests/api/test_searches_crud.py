"""CRIT-01 — a named search and its typed rules are created from the browser.

This is the write-surface lane: the form fields become `searches.criteria_json` and
`filter_rules.params_json`, validation rejects a bad shape before any insert, the
version moves to reflect a change, and user text is escaped on the way back out.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
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


async def test_a_malformed_salary_floor_is_reported_once(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """WR-04: the field name must not be prefixed onto an already-complete sentence."""
    response = await client.post(
        "/searches", data={"name": "Bad", "salary_floor": "abc"}
    )

    assert response.status_code == 200
    assert "Salary floor must be a whole number." in response.text
    assert "salary floor salary floor" not in response.text.lower(), (
        "the field name was duplicated onto the message"
    )
    assert await _search_rows(session_factory) == []


async def test_posting_a_rule_to_an_unknown_search_is_404_not_500(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """WR-06: the parent is resolved before writing, like every sibling route."""
    response = await client.post(
        "/searches/9999/rules", data={"kind": "remote", "remote_require": "1"}
    )

    assert response.status_code == 404
    assert "Unknown search" in response.text
    assert await _rule_rows(session_factory) == []


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


async def test_a_location_rule_round_trips_county_mode(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await client.post("/searches", data={"name": "Dublin Python"})
    search_id = await _only_search_id(session_factory)

    response = await client.post(
        f"/searches/{search_id}/rules",
        data={"kind": "location", "location_allow": "Dublin", "location_mode": "county"},
    )

    assert response.status_code == 200
    rules = await _rule_rows(session_factory)
    assert len(rules) == 1
    assert rules[0].kind == "location"
    assert rules[0].params_json["allow"] == ["Dublin"]
    assert rules[0].params_json["mode"] == "county"


async def test_a_location_rule_with_an_unknown_mode_is_rejected(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await client.post("/searches", data={"name": "Dublin Python"})
    search_id = await _only_search_id(session_factory)

    response = await client.post(
        f"/searches/{search_id}/rules",
        data={"kind": "location", "location_allow": "Dublin", "location_mode": "bogus"},
    )

    assert response.status_code == 400
    assert "county" in response.text
    assert await _rule_rows(session_factory) == []


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


# --- task 2: enable/disable, edit, delete, rule controls ----------------------


async def _stored_search(
    session_factory: async_sessionmaker[AsyncSession], search_id: int
) -> Search:
    async with session_factory() as session:
        row = await session.get(Search, search_id)
    assert row is not None
    return row


async def test_toggling_a_search_flips_enabled_without_moving_the_version(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await client.post("/searches", data={"name": "Dublin Python"})
    search_id = await _only_search_id(session_factory)

    response = await client.post(f"/searches/{search_id}/toggle")

    assert response.status_code == 200
    assert 'id="criteria-list"' in response.text
    stored = await _stored_search(session_factory, search_id)
    assert stored.enabled is False
    assert stored.version == 1

    await client.post(f"/searches/{search_id}/toggle")
    stored = await _stored_search(session_factory, search_id)
    assert stored.enabled is True
    assert stored.version == 1


async def test_editing_a_search_moves_the_version_on_a_real_change(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await client.post("/searches", data={"name": "Dublin Python", "keywords": "python"})
    search_id = await _only_search_id(session_factory)

    response = await client.post(
        f"/searches/{search_id}",
        data={"name": "Dublin Python", "keywords": "python", "location": "Dublin"},
    )

    assert response.status_code == 200
    stored = await _stored_search(session_factory, search_id)
    assert stored.version == 2
    assert stored.criteria_json == {"keywords": "python", "location": "Dublin"}

    # An identical re-submit must not churn the version.
    await client.post(
        f"/searches/{search_id}",
        data={"name": "Dublin Python", "keywords": "python", "location": "Dublin"},
    )
    assert (await _stored_search(session_factory, search_id)).version == 2


async def test_deleting_a_search_removes_it_and_its_rules(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await client.post("/searches", data={"name": "Dublin Python"})
    search_id = await _only_search_id(session_factory)
    await client.post(
        f"/searches/{search_id}/rules",
        data={"kind": "remote", "remote_require": "1"},
    )

    response = await client.post(f"/searches/{search_id}/delete")

    assert response.status_code == 200
    assert await _search_rows(session_factory) == []
    assert await _rule_rows(session_factory) == []


async def test_toggling_a_rule_moves_the_owning_searchs_version(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await client.post("/searches", data={"name": "Dublin Python"})
    search_id = await _only_search_id(session_factory)
    await client.post(
        f"/searches/{search_id}/rules",
        data={"kind": "remote", "remote_require": "1"},
    )
    rule_id = (await _rule_rows(session_factory))[0].id

    response = await client.post(f"/searches/{search_id}/rules/{rule_id}/toggle")

    assert response.status_code == 200
    rules = await _rule_rows(session_factory)
    assert rules[0].enabled is False
    assert (await _stored_search(session_factory, search_id)).version == 3


async def test_editing_a_rule_replaces_its_params(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await client.post("/searches", data={"name": "Dublin Python"})
    search_id = await _only_search_id(session_factory)
    await client.post(
        f"/searches/{search_id}/rules", data={"kind": "exclude_keyword", "keyword_terms": "crypto"}
    )
    rule_id = (await _rule_rows(session_factory))[0].id

    response = await client.post(
        f"/searches/{search_id}/rules/{rule_id}",
        data={
            "kind": "exclude_keyword",
            "keyword_terms": "crypto, nft",
            "keyword_fields": ["title"],
        },
    )

    assert response.status_code == 200
    rules = await _rule_rows(session_factory)
    assert rules[0].params_json == {"terms": ["crypto", "nft"], "fields": ["title"]}


async def test_deleting_a_rule_removes_it(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await client.post("/searches", data={"name": "Dublin Python"})
    search_id = await _only_search_id(session_factory)
    await client.post(
        f"/searches/{search_id}/rules",
        data={"kind": "remote", "remote_require": "1"},
    )
    rule_id = (await _rule_rows(session_factory))[0].id

    response = await client.post(f"/searches/{search_id}/rules/{rule_id}/delete")

    assert response.status_code == 200
    assert await _rule_rows(session_factory) == []
    assert (await _stored_search(session_factory, search_id)).version == 3


async def test_rule_routes_404_for_a_rule_that_belongs_to_another_search(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await client.post("/searches", data={"name": "One"})
    first_id = await _only_search_id(session_factory)
    await client.post(f"/searches/{first_id}/rules", data={"kind": "remote", "remote_require": "1"})
    rule_id = (await _rule_rows(session_factory))[0].id

    await client.post("/searches", data={"name": "Two"})
    other_id = [row.id for row in await _search_rows(session_factory)][1]

    response = await client.post(f"/searches/{other_id}/rules/{rule_id}/toggle")

    assert response.status_code == 404
    assert (await _rule_rows(session_factory))[0].enabled is True


# --- flagged assumptions this plan owns ---------------------------------------


async def test_two_identical_creates_produce_two_distinguishable_searches(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Recorded honestly: there is no unique constraint on `searches.name` (no idempotency)."""
    await client.post("/searches", data={"name": "Dup", "keywords": "python"})
    await client.post("/searches", data={"name": "Dup", "keywords": "python"})

    rows = await _search_rows(session_factory)
    assert len(rows) == 2
    assert rows[0].id != rows[1].id, "the second is distinguishable by its id"


@pytest.mark.parametrize("amount", ["-1", "1.5", "abc"])
async def test_a_non_integer_salary_floor_rule_is_rejected(
    client, session_factory: async_sessionmaker[AsyncSession], amount: str
) -> None:
    await client.post("/searches", data={"name": "Dublin Python"})
    search_id = await _only_search_id(session_factory)

    response = await client.post(
        f"/searches/{search_id}/rules",
        data={"kind": "salary_floor", "salary_amount": amount},
    )

    assert response.status_code == 400
    assert await _rule_rows(session_factory) == []


