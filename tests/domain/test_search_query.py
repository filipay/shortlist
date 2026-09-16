"""QUEUE-06 / T-02-26 — the FTS5 safety transform, proven against the real parser.

A string comparison against an expected expression would pass while the database
still raised, so the decisive assertions here run every produced expression through
a real `MATCH` against the migrated temp database. The raw-input cases at the bottom
prove the transform is not vacuous: those inputs raise when passed through unchecked.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Listing
from app.domain.search_query import build_match_expression

#: The eight ordinary inputs RESEARCH §Q3 recorded raising against the real
#: `listing_fts` when passed through raw.
HOSTILE_INPUTS = (
    "-",
    "a AND",
    '"unbalanced',
    "OR",
    "*",
    "NEAR(",
    "runner-up",
    "it's",
)

#: The subset asserted to raise when UNTRANSFORMED. Kept explicit rather than
#: derived so a future SQLite relaxing one of them is a visible test change and not
#: a silently weakened non-vacuity check.
RAW_RAISES = ("-", '"unbalanced', "OR", "*", "NEAR(", "runner-up", "it's")


def _listing(title: str, description: str = "Build the thing.") -> Listing:
    now = datetime(2026, 9, 15, tzinfo=UTC)
    return Listing(
        canonical_url=f"https://example.com/jobs/{title}",
        title=title,
        company_norm="acme",
        description=description,
        first_seen_at=now,
        last_seen_at=now,
        content_hash=f"hash-{title}",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


async def _match(session: AsyncSession, expression: str) -> list[int]:
    """A real `MATCH`, with the expression as a BOUND parameter."""
    result = await session.execute(
        text("SELECT rowid FROM listing_fts WHERE listing_fts MATCH :term"),
        {"term": expression},
    )
    return [row[0] for row in result.all()]


async def _seeded(session_factory: async_sessionmaker[AsyncSession]) -> AsyncSession:
    async with session_factory() as session:
        session.add_all(
            [
                _listing("Senior Python Engineer"),
                _listing("Quantum Manager", description="managing a small team"),
                _listing("Café Barista"),
            ]
        )
        await session.commit()
    return session


# --- the required property: the parser accepts every transformed input ----------


async def test_every_hostile_input_becomes_an_expression_the_real_parser_accepts(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    session = await _seeded(session_factory)
    async with session:
        for raw in HOSTILE_INPUTS:
            expression = build_match_expression(raw)
            assert expression is not None, f"{raw!r} produced no expression"
            assert expression.startswith('"'), f"{raw!r} was not quoted: {expression}"
            await _match(session, expression)  # must not raise


async def test_the_raw_inputs_really_do_raise_untransformed(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Non-vacuity: if raw text were safe, the transform would be pointless."""
    session = await _seeded(session_factory)
    async with session:
        for raw in RAW_RAISES:
            with pytest.raises(OperationalError):
                await _match(session, raw)


# --- the no-query branch ------------------------------------------------------


@pytest.mark.parametrize("raw", [None, "", "   ", "\t\n "])
def test_an_absent_or_blank_query_returns_none(raw: str | None) -> None:
    """`None` is the D-42 branch: the caller skips the FTS join, never `MATCH ''`."""
    assert build_match_expression(raw) is None


# --- tokenisation -------------------------------------------------------------


def test_a_single_token_is_quoted_and_prefixed() -> None:
    assert build_match_expression("engineer") == '"engineer"*'


def test_tokens_are_joined_with_AND_and_only_the_last_is_prefixed() -> None:
    assert build_match_expression("senior python") == '"senior" AND "python"*'


def test_prefixing_can_be_switched_off() -> None:
    assert build_match_expression("senior python", prefix_last=False) == (
        '"senior" AND "python"'
    )


def test_extra_whitespace_is_collapsed() -> None:
    assert build_match_expression("  senior   python  ") == '"senior" AND "python"*'


def test_an_internal_double_quote_is_doubled() -> None:
    """FTS5's own escape for a literal quote inside a quoted string."""
    assert build_match_expression('say "hi"') == '"say" AND """hi"""*'


async def test_a_query_containing_a_double_quote_still_parses(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    session = await _seeded(session_factory)
    async with session:
        expression = build_match_expression('"')
        assert expression is not None
        await _match(session, expression)


def test_a_non_ascii_token_is_quoted_like_any_other() -> None:
    """No second normaliser: `porter unicode61` does the tokenising, not this module."""
    assert build_match_expression("café") == '"café"*'


async def test_a_non_ascii_query_matches_the_real_table(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """`Café` is seeded; the transform must not mangle it into a syntax error."""
    session = await _seeded(session_factory)
    async with session:
        expression = build_match_expression("café")
        assert expression is not None
        found = await _match(session, expression)
    assert found, "the seeded Café row must be reachable"


# --- totality -----------------------------------------------------------------


def test_the_function_is_total_for_a_long_adversarial_string() -> None:
    adversarial = (
        'NEAR( ^ : * " unbalanced \' quote ) AND OR NOT ("a" OR "b") - '
        "MANAGING runner-up it's 100% [x] {y} café \\ / ; drop table listings;--"
    )

    expression = build_match_expression(adversarial)

    assert expression is not None
    assert expression.count('"') % 2 == 0, "every quote must be balanced"

    # Strip every quoted literal: what remains must be only `AND` separators and the
    # trailing prefix `*`. That is the structural form of "no operator survived
    # unquoted" — `NEAR(`, `:`, `^`, `*` and `-` are all inert once inside quotes.
    remainder = re.sub(r'"(?:[^"]|"")*"', "", expression)
    assert remainder.replace(" AND ", " ").replace("*", " ").strip() == "", (
        f"an unquoted token survived: {remainder!r}"
    )


async def test_the_adversarial_expression_parses_against_the_real_table(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    session = await _seeded(session_factory)
    async with session:
        expression = build_match_expression(
            'NEAR( ^ : * " unbalanced ) AND OR NOT - it\'s runner-up 100% café'
        )
        assert expression is not None
        await _match(session, expression)
