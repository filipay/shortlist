"""G-07-3 — the drafted-answer region surfaces the specific grounding findings and band.

The ``.answer-warning`` line is no longer only a fixed generic caution: when the checker
recorded specifics, each is rendered naming its offender (the unknown evidence id, the
novel number token), and a non-default advisory ``band`` is surfaced as advisory. The two
must-haves that keep this honest:

* a flagged row with NO stored specifics still renders the generic caution (fail-closed);
* a fully grounded answer renders neither a warning nor a band.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import ScreeningDraft
from tests.api.test_apply_package import _seed_artifact, _seed_listing

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)

GENERIC_CAUTION = "may go beyond your CV"
ADVISORY_LINE = "Advisory match band:"


async def _seed_warned_drafts(
    session_factory: async_sessionmaker[AsyncSession],
    listing_id: int,
    rows: list[dict[str, Any]],
) -> list[int]:
    """Insert ``screening_drafts`` rows directly, including warnings_json and band."""
    ids: list[int] = []
    async with session_factory() as session:
        for row in rows:
            record = ScreeningDraft(
                listing_id=listing_id,
                question_text=row["question"],
                answer_text=row.get("answer"),
                evidence_json=row.get("evidence", []),
                warnings_json=row.get("warnings", []),
                band=row.get("band"),
                unsupported=row.get("unsupported", False),
                created_at=NOW,
            )
            session.add(record)
            await session.flush()
            ids.append(int(record.id))
        await session.commit()
    return ids


async def test_a_flagged_answer_names_each_specific_offender(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    listing_id = await _seed_listing(session_factory)
    await _seed_artifact(session_factory, listing_id, status="ok")
    await _seed_warned_drafts(
        session_factory,
        listing_id,
        [
            {
                "question": "Why this role?",
                "answer": "I shipped 97% of it.",
                "evidence": ["bul/northwind-labs-2021/1"],
                "unsupported": True,
                "warnings": [
                    "unsupported evidence id 'bul/missing/9': not a fact id in the candidate's CV",
                    "unsupported number '97': appears in neither the CV facts nor the listing",
                ],
                "band": "ungrounded",
            }
        ],
    )

    response = await client.get(f"/listings/{listing_id}/apply")

    assert response.status_code == 200
    # The generic caution survives alongside the specifics.
    assert GENERIC_CAUTION in response.text
    # Each offender the checker named is visible.
    assert "bul/missing/9" in response.text
    # Jinja autoescape turns the stored warning's quotes into entities; the offender
    # token is still visible in the rendered line.
    assert "unsupported number" in response.text
    assert "&#39;97&#39;" in response.text
    # The non-default band is surfaced, explicitly advisory.
    assert ADVISORY_LINE in response.text
    assert "ungrounded" in response.text
    assert "not a guarantee" in response.text


async def test_a_null_specifics_flagged_row_still_renders_the_generic_caution(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Fail-closed: an unsupported row with no stored specifics renders the old caution."""
    listing_id = await _seed_listing(session_factory)
    await _seed_artifact(session_factory, listing_id, status="ok")
    await _seed_warned_drafts(
        session_factory,
        listing_id,
        [{"question": "Why this role?", "answer": "I shipped 97% of it.", "unsupported": True}],
    )

    response = await client.get(f"/listings/{listing_id}/apply")

    assert response.status_code == 200
    assert GENERIC_CAUTION in response.text
    assert ADVISORY_LINE not in response.text


async def test_a_grounded_answer_renders_neither_warning_nor_band(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    listing_id = await _seed_listing(session_factory)
    await _seed_artifact(session_factory, listing_id, status="ok")
    await _seed_warned_drafts(
        session_factory,
        listing_id,
        [
            {
                "question": "Why this role?",
                "answer": "Because I build pipelines.",
                "evidence": ["bul/northwind-labs-2021/1"],
                "unsupported": False,
                "warnings": [],
                "band": "grounded",
            }
        ],
    )

    response = await client.get(f"/listings/{listing_id}/apply")

    assert response.status_code == 200
    assert "Because I build pipelines." in response.text
    assert 'class="answer-warning"' not in response.text
    assert ADVISORY_LINE not in response.text
