"""The screening-question document — the only place its SQL lives (D-124).

Mirrors ``ranking_config_repo``: one row (``id = 1``, enforced by
``ck_apply_config_singleton``), a JSON ``questions_json`` column, and the house
repository rules — it takes an ``AsyncSession``, **never commits**, and wraps its
write in a SAVEPOINT so a failure cannot poison the caller's outer transaction.
``now`` is injectable so a caller (or a test) can pin the clock.

The read is **total**: an absent row falls back to the code-level
:data:`DEFAULT_QUESTIONS`, so a fresh install has a usable list with no migration
and no seed row. A row that exists but holds an empty list is the explicit
"no questions" state and is returned as-is — the fallback is only for the ABSENT
row. Questions come only from this list plus the package page's ad-hoc box (D-124);
they are never inferred from listing text.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApplyConfig

#: The pinned singleton row id (mirrors ``ck_apply_config_singleton``).
SINGLETON_ID = 1

#: The fresh-install question list. Used only when no ``apply_config`` row exists;
#: the user edits it from ``/settings`` and their list replaces it.
DEFAULT_QUESTIONS: tuple[str, ...] = (
    "Why are you interested in this role?",
    "What is your notice period?",
    "What are your salary expectations?",
    "Do you have the right to work in this location?",
)


def _clean(questions: Iterable[str]) -> list[str]:
    """Trim each question, drop blanks, preserve order."""
    return [str(item).strip() for item in questions if str(item).strip()]


async def read_questions(session: AsyncSession) -> list[str]:
    """The stored question list, or ``DEFAULT_QUESTIONS`` when no row exists.

    An explicit empty list stored by the user is returned unchanged (so "no
    questions" is expressible); only an ABSENT row falls back to the defaults.
    Never commits, never raises.
    """
    row = await session.get(ApplyConfig, SINGLETON_ID)
    stored = row.questions_json if row is not None else None
    if isinstance(stored, list):
        return _clean(stored)
    return list(DEFAULT_QUESTIONS)


async def write_questions(
    session: AsyncSession,
    questions: Iterable[str],
    *,
    now: datetime | None = None,
) -> list[str]:
    """Upsert the one question row and return the stored list. Never commits.

    An empty ``questions`` stores an explicit empty list rather than falling back to
    the defaults, so the caller can express "no questions". The order is preserved.
    """
    cleaned = _clean(questions)
    moment = now if now is not None else datetime.now(UTC)
    statement = (
        sqlite_insert(ApplyConfig)
        .values(id=SINGLETON_ID, questions_json=cleaned, updated_at=moment)
        .on_conflict_do_update(
            index_elements=["id"],
            set_={"questions_json": cleaned, "updated_at": moment},
        )
    )
    async with session.begin_nested():
        await session.execute(statement)
        await session.flush()
    return cleaned


__all__ = ["DEFAULT_QUESTIONS", "SINGLETON_ID", "read_questions", "write_questions"]
