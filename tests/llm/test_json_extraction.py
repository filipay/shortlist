"""GEN-2 — `_extract_json` tolerates fences and prose, and fails loud otherwise.

V2 `generate` returns plain model prose, so the JSON object may arrive wrapped in a
```json fence or preceded by a sentence. `_extract_json` takes the OUTERMOST brace
block (quoting-aware, so a `}` inside a string cannot close the block early), and
returns a genuinely brace-free body UNCHANGED — so `_salvage` still fails loudly on
non-JSON rather than the extractor inventing a value (D-141).
"""

from __future__ import annotations

import pytest

from app.llm.opencode_server import _extract_json


def test_a_bare_object_passes_through() -> None:
    text = '{"a": 1}'
    assert _extract_json(text) == text


def test_a_fenced_block_yields_the_object() -> None:
    text = '```json\n{"a": 1}\n```'
    assert _extract_json(text) == '{"a": 1}'


def test_leading_prose_and_trailing_text_are_stripped() -> None:
    text = 'Here is the result you asked for:\n{"a": 1}\nHope that helps!'
    assert _extract_json(text) == '{"a": 1}'


def test_the_outermost_brace_block_is_taken_when_braces_are_nested() -> None:
    text = '{"outer": {"inner": 1, "deeper": {"x": 2}}}'
    assert _extract_json(text) == text


def test_a_brace_inside_a_string_does_not_close_the_block() -> None:
    text = '{"a": "a } brace", "b": 2}'
    assert _extract_json(text) == text


def test_an_escaped_quote_inside_a_string_is_respected() -> None:
    text = '{"a": "he said \\"}\\"", "b": 2}'
    assert _extract_json(text) == text


# --- the guard can fail -------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "The model refused to answer.",
        "no braces here at all",
        "",
    ],
)
def test_a_brace_free_body_is_returned_unchanged(text: str) -> None:
    """A guard that cannot fail is not a guard: nothing is invented for non-JSON."""
    assert _extract_json(text) == text


def test_an_unterminated_block_is_returned_unchanged() -> None:
    """A truncated `{` block still reaches `_salvage` verbatim (allow_partial)."""
    text = '{"a": 1'
    assert _extract_json(text) == text


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
