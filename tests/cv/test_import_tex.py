"""D-59 — the bounded `.tex` importer: parse the tractable subset, report the rest.

Nothing is guessed. A field the parser could not fill is absent and loud, so a
draft either validates through the fact store or fails there naming the path —
"unresolved" can never masquerade as "empty". The report itself carries names,
counts, line numbers and flags only: never document text.

The committed stand-in is the only document the hermetic lane can measure; the
real document is deliberately not in this repository (D-58).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.config import settings
from app.cv import import_tex
from app.cv.factstore import CvFactStoreError, load_facts
from app.cv.import_tex import ImportReport, parse_tex, write_draft

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "cv" / "awesomecv_standin.tex"

#: A deliberately multi-argument entry macro: #1/#2/#3 arrive as separate
#: positional arguments, so a wrong arity consumes the wrong number of groups.
ENTRY_MACRO = "\\newcommand{\\cvrole}[3]{\\textbf{#1} --- \\textit{#2} \\hfill #3}\n"

ENTRY_CALL = "\\cvrole{Northwind Labs}{Senior Engineer}{2020-01 -- 2021-01}\n"


def _doc(body: str, *, preamble: str = "") -> str:
    return (
        "\\documentclass{article}\n"
        + preamble
        + "\\begin{document}\n"
        + body
        + "\\end{document}\n"
    )


# --- Test 1: the committed fixture parses -------------------------------------


def test_the_committed_fixture_parses_into_non_negative_counts() -> None:
    draft, report = parse_tex(FIXTURE.read_text(encoding="utf-8"))

    assert isinstance(report, ImportReport)
    assert report.sections_parsed >= 1
    assert report.entries_parsed >= 1
    assert report.bullets_parsed >= 1
    for count in (
        report.sections_parsed,
        report.entries_parsed,
        report.bullets_parsed,
        report.lines_scanned,
    ):
        assert isinstance(count, int) and count >= 0
    assert draft["schema_version"] == 1
    assert draft["sections"]


# --- Test 2: arity is learned from the declaration, then applied ---------------


def test_the_entry_macro_is_understood_by_arity_from_its_declaration() -> None:
    source = _doc("\\section{Experience}\n" + ENTRY_CALL, preamble=ENTRY_MACRO)

    draft, report = parse_tex(source)

    assert report.entries_parsed == 1
    entry = draft["sections"][0]["entries"][0]
    assert entry["start"] == "2020-01"
    assert entry["end"] == "2021-01"
    assert entry["org_id"] == "org.northwind-labs"
    assert entry["title_id"] == "title.senior-engineer"


def test_a_wrong_arity_would_report_a_different_entry_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard-can-fail companion: arity machinery must be load-bearing."""
    source = _doc("\\section{Experience}\n" + ENTRY_CALL, preamble=ENTRY_MACRO)

    _, correct = parse_tex(source)
    assert correct.entries_parsed == 1

    real = import_tex._declared_arity
    monkeypatch.setattr(
        import_tex, "_declared_arity", lambda raw: max(0, real(raw) - 1)
    )

    _, wrong = parse_tex(source)

    assert wrong.entries_parsed != correct.entries_parsed
    assert wrong.unresolved_macros.get("cvrole", 0) >= 1


# --- Test 3: an unknown macro degrades the report, not the parse --------------


def test_an_unknown_macro_degrades_the_report_but_not_the_parse() -> None:
    source = _doc(
        "\\section{Experience}\n" + "\\mystery{unparsed}\n" + ENTRY_CALL,
        preamble=ENTRY_MACRO,
    )

    _, report = parse_tex(source)

    assert report.unresolved_macros["mystery"] == 1
    assert report.unresolved_lines["mystery"] == (3,)
    assert report.sections_parsed == 1
    assert report.entries_parsed == 1


# --- Test 4: packages, in source order, deduplicated --------------------------


def test_the_package_list_is_source_ordered_and_deduplicated() -> None:
    source = _doc("", preamble="\\usepackage{b}\n\\usepackage{a}\n\\usepackage{b}\n")

    _, report = parse_tex(source)

    assert list(report.packages_requested) == ["b", "a"]


def test_the_fixture_package_list_names_every_preamble_package() -> None:
    _, report = parse_tex(FIXTURE.read_text(encoding="utf-8"))

    assert list(report.packages_requested) == [
        "fontspec",
        "geometry",
        "tabularx",
        "paracol",
        "enumitem",
        "titlesec",
        "hyperref",
    ]


# --- Test 5: inline emphasis is flattened to plain text ------------------------


def test_an_inline_bold_or_emphasised_span_is_flattened() -> None:
    source = _doc(
        "\\section{Experience}\n"
        + ENTRY_CALL
        + "\\begin{itemize}\n"
        + "\\item \\textbf{Bold} and \\emph{emphasised} text\n"
        + "\\end{itemize}\n",
        preamble=ENTRY_MACRO,
    )

    draft, report = parse_tex(source)

    bullet = draft["sections"][0]["entries"][0]["bullets"][0]
    assert bullet["text"] == "Bold and emphasised text"
    assert report.bullets_parsed == 1


# --- Test 6: the comment rule, asserted both ways ------------------------------


def test_an_escaped_percent_is_not_a_comment_and_an_unescaped_one_is() -> None:
    source = _doc(
        "\\section{Experience}\n"
        + ENTRY_CALL
        + "\\begin{itemize}\n"
        + "\\item 100\\% done\n"
        + "\\item done % trailing comment\n"
        + "\\end{itemize}\n",
        preamble=ENTRY_MACRO,
    )

    draft, report = parse_tex(source)

    texts = [bullet["text"] for bullet in draft["sections"][0]["entries"][0]["bullets"]]
    assert texts == ["100% done", "done"]
    assert report.bullets_parsed == 2


# --- Test 7: balanced-brace capture respects nesting ---------------------------


def test_balanced_brace_capture_survives_nesting() -> None:
    source = _doc(
        "\\section{Experience}\n"
        + "\\cvrole{Northwind {Labs} Ltd}{Senior Engineer}{2020-01 -- 2021-01}\n",
        preamble=ENTRY_MACRO,
    )

    draft, report = parse_tex(source)

    assert report.entries_parsed == 1
    assert draft["orgs"][0]["name"] == "Northwind Labs Ltd"


# --- Tests 8-9: both bounds report rather than raise ---------------------------


def test_exceeding_the_line_bound_truncates_rather_than_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "tex_import_max_lines", 3)
    source = "\n".join(f"% filler {n}" for n in range(20))

    _, report = parse_tex(source)

    assert report.truncated is True
    assert report.lines_scanned == 3


def test_exceeding_the_nesting_bound_is_reported_rather_than_recursing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "tex_import_max_depth", 2)
    source = _doc(
        "\\section{Experience}\n"
        + "\\cvrole{{{{Northwind}}}}{Senior Engineer}{2020-01 -- 2021-01}\n",
        preamble=ENTRY_MACRO,
    )

    _, report = parse_tex(source)

    assert report.entries_parsed == 0
    assert report.unresolved_macros.get("cvrole", 0) >= 1


# --- Test 10: the draft is loadable — and unresolved is not empty --------------


def test_the_emitted_draft_loads_through_the_fact_store(tmp_path: Path) -> None:
    draft, _ = parse_tex(FIXTURE.read_text(encoding="utf-8"))

    out = write_draft(draft, tmp_path / "draft.yaml")
    facts = load_facts(out)

    assert facts.sections
    assert facts.all_entries()


def test_an_unresolved_required_field_fails_the_load_loudly(tmp_path: Path) -> None:
    source = _doc(
        "\\section{Experience}\n"
        + "\\cvrole{Northwind Labs}{Senior Engineer}{not-a-date}\n",
        preamble=ENTRY_MACRO,
    )

    draft, _ = parse_tex(source)
    out = write_draft(draft, tmp_path / "draft.yaml")

    with pytest.raises(CvFactStoreError) as excinfo:
        load_facts(out)

    assert "sections.0.entries.0" in str(excinfo.value)


# --- Test 11: the importer never writes back over what it read -----------------


def test_the_importer_never_modifies_the_document_it_read(tmp_path: Path) -> None:
    before = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()

    draft, _ = parse_tex(FIXTURE.read_text(encoding="utf-8"))
    write_draft(draft, tmp_path / "rendered-draft.yaml")

    after = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert before == after
    assert not (FIXTURE.parent / "rendered-draft.yaml").exists()


def test_write_draft_writes_to_the_destination_it_is_given(tmp_path: Path) -> None:
    draft, _ = parse_tex(_doc("\\section{Skills}\n"))

    dest = tmp_path / "nested" / "draft.yaml"
    written = write_draft(draft, dest)

    assert written == dest
    assert dest.exists() and dest.stat().st_size > 0


# --- Test 12: the report carries no source text --------------------------------


def test_the_report_carries_no_source_text() -> None:
    source = FIXTURE.read_text(encoding="utf-8")

    blob = str(parse_tex(source)[1])

    for leaked in (
        "Northwind",
        "Senior Engineer",
        "Reduced p99",
        "Dublin",
        "example.invalid",
    ):
        assert leaked not in blob
    assert "Acme" not in blob and "acme" not in blob.lower()


# --- a section command reached through a preamble wrapper ----------------------


def test_a_preamble_macro_that_wraps_section_is_understood() -> None:
    source = _doc(
        "\\sectionheading{Experience}\n" + ENTRY_CALL,
        preamble="\\newcommand{\\sectionheading}[1]{\\section{#1}}\n" + ENTRY_MACRO,
    )

    draft, report = parse_tex(source)

    assert report.sections_parsed == 1
    assert draft["sections"][0]["title_key"] == "sec.experience"


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
