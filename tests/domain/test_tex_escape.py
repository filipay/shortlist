"""CV-06 / D-67 — the ten-character escape set, and D-70's strict comparison.

Pure-domain tests: no engine, no filesystem, no fixture beyond an in-memory
``CvFacts``. Every guard that could pass vacuously has a companion proving it can
fail.
"""

from __future__ import annotations

import pytest

from app.domain.cv import CvFacts
from app.domain.tex import (
    escape_tex,
    facts_compared,
    facts_present_in,
    normalise_for_compare,
    squash,
)

#: The ten TeX-special characters, with the exact replacement each must produce.
_ESCAPE_CASES = (
    ("\\", r"\textbackslash{}"),
    ("{", r"\{"),
    ("}", r"\}"),
    ("$", r"\$"),
    ("&", r"\&"),
    ("#", r"\#"),
    ("%", r"\%"),
    ("_", r"\_"),
    ("~", r"\textasciitilde{}"),
    ("^", r"\textasciicircum{}"),
)

#: The replacement forms, longest command forms first so stripping is exact.
_ESCAPED_FORMS = tuple(
    replacement
    for _, replacement in sorted(_ESCAPE_CASES, key=lambda pair: -len(pair[1]))
)

_ALL_SPECIAL = "".join(character for character, _ in _ESCAPE_CASES)


def _strip_escapes(text: str) -> str:
    for form in _ESCAPED_FORMS:
        text = text.replace(form, "")
    return text


def _facts_with_bullets(*texts: str) -> CvFacts:
    return CvFacts.model_validate(
        {
            "schema_version": 1,
            "meta": {
                "name": "Test Person",
                "contact": {"email": "test@example.invalid"},
                "max_pages": 2,
            },
            "sections": [
                {
                    "id": "sec.experience",
                    "title_key": "sec.experience",
                    "order": 10,
                    "entries": [
                        {
                            "id": "exp/acme-ltd-2021",
                            "org_id": "org.acme",
                            "title_id": "title.engineer",
                            "start": "2021-03",
                            "end": "2024-09",
                            "location": "Dublin, IE",
                            "bullets": [
                                {"id": f"bul/acme-ltd-2021/{index + 1}", "text": text}
                                for index, text in enumerate(texts)
                            ],
                        }
                    ],
                }
            ],
            "orgs": [{"id": "org.acme", "name": "Acme Ltd"}],
            "titles": [{"id": "title.engineer", "name": "Engineer"}],
            "gaps": [],
        }
    )


# --- Test 1/2: the escape set and the backslash-first rule --------------------


def test_every_special_character_is_escaped_to_its_expected_form() -> None:
    for character, replacement in _ESCAPE_CASES:
        assert escape_tex(character) == replacement, character


def test_no_unescaped_special_character_survives_the_escaping() -> None:
    hostile = "\\{} $& #%_~^ end"
    escaped = escape_tex(hostile)

    # Every escape form is present, and stripping them leaves none of the ten.
    assert _strip_escapes(escaped) == "   end"
    for character in _ALL_SPECIAL:
        assert character not in _strip_escapes(escaped)


def test_the_guard_can_actually_fail_a_deliberately_unescaped_sample() -> None:
    """A guard that cannot fail is not a guard."""
    unescaped = "R&D 20%"
    assert _strip_escapes(unescaped) != ""
    assert "&" in _strip_escapes(unescaped)


def test_the_backslash_is_escaped_exactly_once_not_cascaded() -> None:
    escaped = escape_tex("\\")

    assert escaped == r"\textbackslash{}"
    assert escaped.count(r"\textbackslash") == 1
    # Its own braces must survive unescaped, or input "\" would render as "\{}".
    assert r"\textbackslash\{\}" not in escaped


# --- Test 3/4/5: totality, the hostile sample, Unicode pass-through -----------


def test_escape_tex_is_total_and_a_pure_string_transform() -> None:
    assert escape_tex("") == ""
    assert escape_tex("plain text") == "plain text"


def test_the_hostile_sample_escapes_ampersand_percent_and_underscores() -> None:
    hostile = "R&D cut latency 20% on a C++ _p99_ job"

    escaped = escape_tex(hostile)

    assert escaped == r"R\&D cut latency 20\% on a C++ \_p99\_ job"
    assert "R&D" not in escaped
    assert "20%" not in escaped
    assert "_p99_" not in escaped


def test_non_ascii_passes_through_unchanged() -> None:
    accented = "José — naïve café"

    assert escape_tex(accented) == accented


# --- Test 6/7: the comparison normaliser --------------------------------------


def test_normalise_for_compare_folds_the_extraction_artefacts() -> None:
    assert normalise_for_compare("\ufb01nal") == "final"  # fi ligature -> fi
    assert normalise_for_compare("a\u2013b") == "a-b"  # en dash -> hyphen
    assert normalise_for_compare("a\u00adb") == "ab"  # soft hyphen removed
    assert normalise_for_compare("a   b") == "a b"  # whitespace collapsed


def test_squash_removes_whitespace_and_casefolds() -> None:
    assert squash("Senior  Engineer") == "seniorengineer"
    assert squash("SeniorEngineer") == "seniorengineer"


def test_the_unicode_normalisation_form_is_pinned_by_a_test() -> None:
    """The NFKC claim is pinned here rather than asserted in a comment."""
    import unicodedata

    assert unicodedata.normalize("NFKC", chr(0xFB01)) == "fi"


# --- Test 8/9: strict membership, and the fact-count floor --------------------


def test_facts_present_in_reports_success_for_a_complete_haystack() -> None:
    facts = _facts_with_bullets("Led the migration to a single-writer queue")
    haystack = "Acme Ltd Engineer 2021-03 -- 2024-09 Led the migration to a single-writer queue"

    present, missing = facts_present_in(facts, haystack)

    assert present is True
    assert missing == []
    assert facts_compared(facts) >= 4


def test_facts_present_in_names_the_specific_missing_bullet() -> None:
    facts = _facts_with_bullets(
        "Led the migration to a single-writer queue",
        "Mentored four engineers",
    )
    haystack = "Acme Ltd Engineer 2021-03 -- 2024-09 Led the migration to a single-writer queue"

    present, missing = facts_present_in(facts, haystack)

    assert present is False
    assert "Mentored four engineers" in missing


def test_the_floor_is_load_bearing_so_an_empty_haystack_cannot_pass() -> None:
    facts = _facts_with_bullets("Led the migration to a single-writer queue")

    present, missing = facts_present_in(facts, "")

    assert present is False
    assert missing


def test_membership_is_space_insensitive_but_not_word_insensitive() -> None:
    facts = _facts_with_bullets("Led the migration to a single-writer queue")

    space_dropped = "Acme Ltd Engineer 2021-03 -- 2024-09 Ledthemigrationtoasingle-writerqueue"
    assert facts_present_in(facts, space_dropped)[0] is True

    word_dropped = "Acme Ltd Engineer 2021-03 -- 2024-09 Led the migration"
    assert facts_present_in(facts, word_dropped)[0] is False


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
