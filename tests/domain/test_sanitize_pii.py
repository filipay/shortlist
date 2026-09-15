"""SRC-10 / T-01-23 — recruiter PII is dropped, never recorded, never hashed.

The control is behavioural and total (Pitfall 7): the removed literal must not
survive in the sanitised text, in the returned object, in the structlog event the
stage emits, or in the real captured log output. Two descriptions that differ only
in their PII sanitise *equal*, which is what makes `content_hash` stable across
PII variants of one listing rather than churning a "repost" on every run.

`caplog` alone cannot see structlog: with no explicit configuration structlog
writes through its own `PrintLogger` to stdout, so these tests assert against the
captured event payload (`capture_logs`) *and* against a stdlib-backed logger
injected into the stage (`caplog`), plus the true stdout via `capsys`.
"""

from __future__ import annotations

import ast
import hashlib
import logging
from pathlib import Path

import pytest
import structlog

from app.domain.listing import content_hash
from app.domain.sanitize import sanitize_text
from app.ingest import sanitize as sanitize_stage
from app.ingest.sanitize import sanitize_listing
from app.sources.base import RawListing

CANARY_EMAIL = "PII-CANARY-EMAIL-VALUE@example.com"
CANARY_PHONE = "+353 87 123 4567"
MAX_CHARS = 500


def _listing(description: str) -> RawListing:
    return RawListing(
        source="indeed",
        source_listing_id="canary-1",
        source_url="https://ie.indeed.com/viewjob?jk=canary-1",
        direct_url=None,
        title="Backend Engineer",
        company_name="Acme",
        location_raw="Dublin",
        description=description,
    )


def _description() -> str:
    return f"Great role. Reach the recruiter at {CANARY_EMAIL} or on {CANARY_PHONE}."


# --- removal ------------------------------------------------------------------


def test_email_and_phone_are_removed_from_the_text() -> None:
    result = sanitize_text(_description(), max_chars=MAX_CHARS)

    assert CANARY_EMAIL not in result.text
    assert CANARY_PHONE not in result.text
    assert result.report.emails_removed >= 1
    assert result.report.phones_removed >= 1


def test_a_plain_phone_shaped_run_is_removed() -> None:
    result = sanitize_text("Ring 01 234 5678 for details.", max_chars=MAX_CHARS)

    assert "01 234 5678" not in result.text
    assert result.report.phones_removed >= 1


def test_removed_values_never_appear_on_the_returned_object() -> None:
    result = sanitize_text(_description(), max_chars=MAX_CHARS)

    rendered = repr(result)
    assert CANARY_EMAIL not in rendered
    assert CANARY_PHONE not in rendered
    assert CANARY_EMAIL not in repr(result.report)


def test_removed_pii_is_never_hashed() -> None:
    """Dropped, not hashed — a digest of a phone number is still personal data."""
    result = sanitize_text(_description(), max_chars=MAX_CHARS)

    for digest in (
        hashlib.sha256(CANARY_EMAIL.encode()).hexdigest(),
        hashlib.sha256(CANARY_PHONE.encode()).hexdigest(),
    ):
        assert digest not in repr(result)


# --- logs ---------------------------------------------------------------------


async def test_the_stage_emits_a_count_and_never_the_removed_value() -> None:
    with structlog.testing.capture_logs() as events:
        _, report = await sanitize_listing(_listing(_description()))

    assert report.emails_removed >= 1 and report.phones_removed >= 1
    # Non-vacuity: the count event really was emitted.
    assert any(event.get("pii_removed", 0) >= 2 for event in events)
    assert CANARY_EMAIL not in repr(events)
    assert CANARY_PHONE not in repr(events)


async def test_the_removed_value_does_not_reach_captured_log_output(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same claim, asserted through the stdlib logging tree and capsys."""
    caplog.set_level(logging.INFO, logger="app.ingest.sanitize")
    monkeypatch.setattr(
        sanitize_stage,
        "log",
        structlog.wrap_logger(logging.getLogger("app.ingest.sanitize")),
    )

    await sanitize_listing(_listing(_description()))

    assert "ingest.sanitize" in caplog.text, "the stage did not log — assertion is vacuous"
    assert CANARY_EMAIL not in caplog.text
    assert CANARY_PHONE not in caplog.text


async def test_the_removed_value_does_not_reach_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    await sanitize_listing(_listing(_description()))

    captured = capsys.readouterr()
    assert CANARY_EMAIL not in captured.out + captured.err
    assert CANARY_PHONE not in captured.out + captured.err


# --- variant stability --------------------------------------------------------


def test_texts_differing_only_in_pii_sanitise_equal() -> None:
    with_pii = f"Build the thing. Contact {CANARY_EMAIL} or {CANARY_PHONE}."
    without_pii = "Build the thing. Contact or ."

    assert (
        sanitize_text(with_pii, max_chars=MAX_CHARS).text
        == sanitize_text(without_pii, max_chars=MAX_CHARS).text
    )


def test_content_hash_is_stable_across_pii_variants() -> None:
    fields = {"title": "Backend Engineer", "company_name": "Acme", "location_raw": "Dublin"}

    hashed_with_pii = content_hash(
        description=sanitize_text(_description(), max_chars=MAX_CHARS).text,
        **fields,
    )
    hashed_without_pii = content_hash(
        description=sanitize_text(
            "Great role. Reach the recruiter at  or on .", max_chars=MAX_CHARS
        ).text,
        **fields,
    )

    assert hashed_with_pii == hashed_without_pii


def test_content_hash_still_distinguishes_real_edits() -> None:
    """Non-vacuity: the stability above is not because every hash is equal."""
    common = {"title": "Backend Engineer", "company_name": "Acme", "location_raw": "Dublin"}

    assert content_hash(description="Build the thing.", **common) != content_hash(
        description="Build a different thing entirely.", **common
    )


# --- the stage is singular ----------------------------------------------------


def test_the_ingest_stage_is_named() -> None:
    assert sanitize_stage.STAGE_NAME == "sanitize"


def test_no_adapter_sanitises_independently() -> None:
    """One named stage — not a helper copied into each adapter, where two copies
    of the same GDPR/injection control would silently diverge."""
    sources_dir = Path(sanitize_stage.__file__).resolve().parents[1] / "sources"
    offenders: list[str] = []

    for path in sorted(sources_dir.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported = node.module or ""
                if imported.startswith(("app.domain.sanitize", "app.ingest.sanitize")):
                    offenders.append(path.name)
            elif isinstance(node, ast.Import):
                if any(
                    alias.name.startswith(("app.domain.sanitize", "app.ingest.sanitize"))
                    for alias in node.names
                ):
                    offenders.append(path.name)

    assert offenders == [], f"an adapter sanitises independently: {sorted(set(offenders))}"


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
