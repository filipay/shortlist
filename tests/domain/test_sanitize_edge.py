"""SRC-08 backstops — empty, boundary, multi-byte and determinism.

These are the cases a regex-only sanitiser gets wrong. `None`/empty must be total
and deterministic. Truncation must be *exactly* `max_chars` **Python characters** —
not bytes (a byte slice splits a multi-byte character and raises) and not fewer
(the contract is the limit, not an approximation). Sanitising the same input twice
must produce equal output: no dict ordering, no locale, no timestamp.
"""

from __future__ import annotations

import pytest

from app.domain.sanitize import sanitize_text

MAX_CHARS = 20


@pytest.mark.parametrize("value", [None, "", "   ", "\n\t "])
def test_null_and_empty_descriptions_sanitise_to_an_empty_string(
    value: str | None,
) -> None:
    result = sanitize_text(value, max_chars=MAX_CHARS)

    assert result.text == ""
    assert result.report.truncated is False


def test_one_under_the_limit_is_unchanged() -> None:
    text = "c" * (MAX_CHARS - 1)

    result = sanitize_text(text, max_chars=MAX_CHARS)

    assert result.text == text
    assert result.report.truncated is False


def test_exactly_at_the_limit_is_unchanged() -> None:
    text = "a" * MAX_CHARS

    result = sanitize_text(text, max_chars=MAX_CHARS)

    assert result.text == text
    assert len(result.text) == MAX_CHARS
    assert result.report.truncated is False


def test_one_over_the_limit_is_truncated_to_exactly_the_limit() -> None:
    text = "b" * (MAX_CHARS + 1)

    result = sanitize_text(text, max_chars=MAX_CHARS)

    assert len(result.text) == MAX_CHARS
    assert result.text == "b" * MAX_CHARS
    assert result.report.truncated is True


def test_truncation_keeps_exactly_the_limit_even_at_a_space() -> None:
    """`.rstrip()` after slicing would return fewer than the documented limit."""
    text = ("d" * (MAX_CHARS - 1)) + "  trailing"

    result = sanitize_text(text, max_chars=MAX_CHARS)

    assert len(result.text) == MAX_CHARS


def test_multibyte_text_truncates_by_characters_not_bytes() -> None:
    """CJK: three UTF-8 bytes per character, so a byte slice would raise."""
    text = "日" * (MAX_CHARS + 1)

    result = sanitize_text(text, max_chars=MAX_CHARS)

    assert len(result.text) == MAX_CHARS
    assert result.text == "日" * MAX_CHARS
    # The unit is characters, not bytes: the encoding exceeds the character limit.
    assert len(result.text.encode("utf-8")) == MAX_CHARS * 3


def test_accented_text_at_the_boundary_does_not_raise() -> None:
    text = "café " * (MAX_CHARS + 5)

    result = sanitize_text(text, max_chars=MAX_CHARS)

    assert len(result.text) == MAX_CHARS
    result.text.encode("utf-8")  # must be a whole, encodable string


def test_sanitising_the_same_input_twice_is_identical() -> None:
    raw = "<p>  Senior   Engineer &amp; Team Lead  </p>"

    first = sanitize_text(raw, max_chars=MAX_CHARS)
    second = sanitize_text(raw, max_chars=MAX_CHARS)

    assert first == second
    assert first.text == second.text
    assert first.report == second.report


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
