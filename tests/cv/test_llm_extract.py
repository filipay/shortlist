"""The hybrid `.tex` -> fact-store extraction: loose model output, strict compile.

The model is a stub returning a canned `_ExtractedCv`; every assertion is on the
compiled, loadable fact store (through `load_facts`) and on the report. The grounding
guard, the date wrapper and the heading map are each exercised with teeth.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.cv.factstore import load_facts
from app.cv.llm_extract import (
    ExtractionError,
    _ExtractedCv,
    _ExtractedEntry,
    _ExtractedEnvelope,
    _ExtractedMeta,
    _ExtractedSection,
    extract_facts,
)
from app.domain.cv import iter_fact_ids
from app.llm.base import DiscoveryResult, ProbeOutcome, StructuredCallResult

# ---------------------------------------------------------------------------
# a canned document mirroring the user's real shape
# ---------------------------------------------------------------------------

REAL_TEX = r"""\documentclass{article}
\newcommand{\workentry}[4]{\textbf{#1} \textit{#2} \hfill #3 #4}
\begin{document}
\begin{center}{\LARGE Alex Example}\\ alex@example.invalid\\ https://example.invalid/alex\end{center}
\section*{WORK EXPERIENCE}
\workentry{Senior Backend Engineer}{Northwind Labs}{2021 - 2023}{%
\begin{highlights}\item Built the ingest path\item Cut p99 latency\end{highlights}}
\workentry{Platform Engineer}{Acme Corp}{2026 - present}{%
\begin{highlights}\item Owned the deploy pipeline\end{highlights}}
\section*{PROJECTS}
\workentry{Lead Developer}{Widget Kit}{2026}{%
\begin{highlights}\item Shipped v1\end{highlights}}
\section*{EDUCATION}
\workentry{BSc Computer Science}{Trinity College}{2024}{%
\begin{highlights}\item First class honours\end{highlights}}
\section*{VOLUNTEERING}
\workentry{Mentor}{Code Club}{2021 - 2023}{%
\begin{highlights}\item Mentored students\end{highlights}}
\section*{CODING PROFICIENCY}
Python, Go, SQL
\end{document}
"""


def _real_extraction() -> _ExtractedCv:
    """Title-first entries, highlights bullets, real headings, bare/open dates."""
    return _ExtractedCv(
        meta=_ExtractedMeta(
            name="Alex Example",
            email="alex@example.invalid",
            links=["https://example.invalid/alex"],
        ),
        sections=[
            _ExtractedSection(
                heading="WORK EXPERIENCE",
                entries=[
                    _ExtractedEntry(
                        org="Northwind Labs",
                        title="Senior Backend Engineer",
                        dates="2021 - 2023",
                        bullets=["Built the ingest path", "Cut p99 latency"],
                    ),
                    _ExtractedEntry(
                        org="Acme Corp",
                        title="Platform Engineer",
                        dates="2026 - present",
                        bullets=["Owned the deploy pipeline"],
                    ),
                ],
                skills=[],
            ),
            _ExtractedSection(
                heading="PROJECTS",
                entries=[
                    _ExtractedEntry(
                        org="Widget Kit",
                        title="Lead Developer",
                        dates="2026",
                        bullets=["Shipped v1"],
                    )
                ],
                skills=[],
            ),
            _ExtractedSection(
                heading="EDUCATION",
                entries=[
                    _ExtractedEntry(
                        org="Trinity College",
                        title="BSc Computer Science",
                        dates="2024",
                        bullets=["First class honours"],
                    )
                ],
                skills=[],
            ),
            _ExtractedSection(
                heading="VOLUNTEERING",
                entries=[
                    _ExtractedEntry(
                        org="Code Club",
                        title="Mentor",
                        dates="2021 - 2023",
                        bullets=["Mentored students"],
                    )
                ],
                skills=[],
            ),
            _ExtractedSection(
                heading="CODING PROFICIENCY", entries=[], skills=["Python", "Go", "SQL"]
            ),
        ],
    )


class StubBackend:
    """Returns a canned structured result and records the call shape.

    The wire schema is a single string field (``_ExtractedEnvelope``). A canned
    ``_ExtractedCv`` is serialised into that string; ``cv_json`` supplies a raw
    string directly for the malformed-shape tests.
    """

    def __init__(
        self,
        extracted: _ExtractedCv | None = None,
        *,
        cv_json: str | None = None,
        ok: bool = True,
        error: str | None = None,
        raise_on_call: bool = False,
    ) -> None:
        self._extracted = extracted
        self._cv_json = cv_json
        self._ok = ok
        self._error = error
        self._raise = raise_on_call
        self.calls: list[dict[str, Any]] = []

    async def health(self) -> ProbeOutcome:
        return ProbeOutcome(reachable=True)

    async def discover_models(self) -> DiscoveryResult:
        return DiscoveryResult(reachable=True)

    async def complete_structured(
        self,
        *,
        schema: type,
        system: str,
        parts: list[str],
        model: str | None = None,
        agent: str | None = None,
        tools: tuple[str, ...] = (),
        retries: int | None = None,
    ) -> StructuredCallResult:
        self.calls.append({"schema": schema, "system": system, "parts": list(parts)})
        if self._raise:
            raise RuntimeError("transport down")
        if not self._ok:
            return StructuredCallResult(ok=False, status="invalid", error=self._error)
        raw = (
            self._cv_json
            if self._cv_json is not None
            else json.dumps(self._extracted.model_dump())
        )
        return StructuredCallResult(
            ok=True, status="ok", data=_ExtractedEnvelope(cv_json=raw)
        )


def _write_and_load(facts: dict, tmp_path: Path):
    """Assert the dict is a real fact store by loading it from disk."""
    path = tmp_path / "cv.yaml"
    path.write_text(
        yaml.safe_dump(facts, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return load_facts(path)


def _grounded(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold())


# --- 1. the real shape compiles into a loadable store -------------------------


async def test_a_real_shaped_document_compiles_into_a_loadable_store(
    tmp_path: Path,
) -> None:
    backend = StubBackend(_real_extraction())

    result = await extract_facts(backend, tex_source=REAL_TEX)

    # The call carries the whole `.tex` as the only part, under the frozen prompt.
    assert backend.calls[0]["parts"] == [REAL_TEX]
    assert backend.calls[0]["system"]
    assert "never invent" in backend.calls[0]["system"].lower()

    facts = _write_and_load(result.facts, tmp_path)
    assert {section.title_key for section in facts.sections} == {
        "sec.experience",
        "sec.projects",
        "sec.education",
        "sec.volunteering",
        "sec.skills",
    }
    assert len(facts.all_entries()) == 5
    all_ids = list(iter_fact_ids(facts))
    assert len(all_ids) == len(set(all_ids)), "ids must be unique across the store"
    assert {skill.label for section in facts.sections for skill in section.skills} == {
        "Python",
        "Go",
        "SQL",
    }
    # The model chose no ids: every entry id is derived from org + start year.
    assert all(entry.id.startswith("exp/") for entry in facts.all_entries())
    assert result.report[0] == "extracted from LaTeX with model assistance"
    assert any("kept 5 section(s), 5 entry/entries" in line for line in result.report)


# --- 2. the grounding guard fails closed ---------------------------------------


def _two_entry_extraction(
    *, bad_org: str | None = None, bad_title: str | None = None, name: str = "Alex Example"
) -> _ExtractedCv:
    good = _ExtractedEntry(
        org="Northwind Labs",
        title="Senior Backend Engineer",
        dates="2021 - 2023",
        bullets=[],
    )
    bad = _ExtractedEntry(
        org=bad_org or "Acme Corp",
        title=bad_title or "Platform Engineer",
        dates="2026 - present",
        bullets=[],
    )
    return _ExtractedCv(
        meta=_ExtractedMeta(name=name),
        sections=[
            _ExtractedSection(heading="WORK EXPERIENCE", entries=[good, bad], skills=[])
        ],
    )


@pytest.mark.parametrize("case", ["org", "title", "name"])
async def test_the_grounding_guard_drops_values_absent_from_the_source(
    tmp_path: Path, case: str
) -> None:
    if case == "org":
        extraction = _two_entry_extraction(bad_org="Ghost Corp")
        invented, surfaced = "Ghost Corp", "Ghost Corp"
    elif case == "title":
        extraction = _two_entry_extraction(bad_title="Chief Wizard")
        invented, surfaced = "Chief Wizard", "Chief Wizard"
    else:
        extraction = _two_entry_extraction(name="Jane Fabricated")
        invented, surfaced = "Jane Fabricated", "Jane Fabricated"

    result = await extract_facts(StubBackend(extraction), tex_source=REAL_TEX)
    facts = _write_and_load(result.facts, tmp_path)

    org_names = {org.name for org in facts.orgs}
    title_names = {title.name for title in facts.titles}
    assert invented not in org_names
    assert invented not in title_names
    assert facts.meta.name != invented
    assert any(surfaced in line for line in result.report), result.report
    # The guard drops only the offending entry; the grounded one survives.
    if case in ("org", "title"):
        assert "Northwind Labs" in org_names


# --- 3. dates ------------------------------------------------------------------


_DATES_TEX = (
    "Alex Example\n"
    "Alpha Ltd\nRole One\n2026\n"
    "Beta Ltd\nRole Two\n2026 - present\n"
    "Gamma Ltd\nRole Three\n2021 - 2023\n"
    "Delta Ltd\nRole Four\nwhenever\n"
)


def _dates_extraction() -> _ExtractedCv:
    entries = [
        _ExtractedEntry(org="Alpha Ltd", title="Role One", dates="2026", bullets=[]),
        _ExtractedEntry(org="Beta Ltd", title="Role Two", dates="2026 - present", bullets=[]),
        _ExtractedEntry(org="Gamma Ltd", title="Role Three", dates="2021 - 2023", bullets=[]),
        _ExtractedEntry(org="Delta Ltd", title="Role Four", dates="whenever", bullets=[]),
    ]
    return _ExtractedCv(
        meta=_ExtractedMeta(name="Alex Example"),
        sections=[_ExtractedSection(heading="EXPERIENCE", entries=entries, skills=[])],
    )


async def test_bare_years_and_open_ends_are_parsed_without_inventing_months(
    tmp_path: Path,
) -> None:
    result = await extract_facts(StubBackend(_dates_extraction()), tex_source=_DATES_TEX)
    facts = _write_and_load(result.facts, tmp_path)

    single = facts.all_entries()
    # `whenever` is unparseable and is dropped, not guessed.
    assert len(single) == 3
    assert any("whenever" in line for line in result.report)

    starts = {entry.id: (entry.start, entry.end) for entry in single}
    assert starts["exp/alpha-ltd-2026"] == ("2026-01", None)
    assert starts["exp/beta-ltd-2026"] == ("2026-01", None)
    assert starts["exp/gamma-ltd-2021"] == ("2021-01", "2023-01")
    # The ONLY synthesised month is -01.
    for entry in single:
        assert entry.start.endswith("-01")
        assert entry.end is None or entry.end.endswith("-01")


# --- 4. heading mapping --------------------------------------------------------


_HEADINGS_TEX = (
    "WORK EXPERIENCE\nPROJECTS\nEDUCATION\nVOLUNTEERING\nCODING PROFICIENCY\n"
    "INTERESTS\n"
    "Org A\nRole A\n2026\nOrg B\nRole B\n2026\nOrg C\nRole C\n2026\n"
    "Org D\nRole D\n2026\nOrg E\nRole E\n2026\nHobby Corp\nHobbyist\n2026\n"
)


def _headings_extraction() -> _ExtractedCv:
    def entry(org: str, title: str) -> _ExtractedEntry:
        return _ExtractedEntry(org=org, title=title, dates="2026", bullets=[])

    def section(heading: str, org: str, title: str) -> _ExtractedSection:
        return _ExtractedSection(heading=heading, entries=[entry(org, title)], skills=[])

    return _ExtractedCv(
        meta=_ExtractedMeta(name="Alex Example"),
        sections=[
            section("WORK EXPERIENCE", "Org A", "Role A"),
            section("PROJECTS", "Org B", "Role B"),
            section("EDUCATION", "Org C", "Role C"),
            section("VOLUNTEERING", "Org D", "Role D"),
            _ExtractedSection(heading="CODING PROFICIENCY", entries=[], skills=["Python"]),
            section("INTERESTS", "Hobby Corp", "Hobbyist"),
        ],
    )


async def test_each_real_heading_maps_to_its_key_and_an_unknown_heading_is_dropped(
    tmp_path: Path,
) -> None:
    result = await extract_facts(StubBackend(_headings_extraction()), tex_source=_HEADINGS_TEX)
    facts = _write_and_load(result.facts, tmp_path)

    assert {section.title_key for section in facts.sections} == {
        "sec.experience",
        "sec.projects",
        "sec.education",
        "sec.volunteering",
        "sec.skills",
    }
    # The unknown heading and its entry are dropped, and the drop is named.
    assert "Hobby Corp" not in {org.name for org in facts.orgs}
    assert any("INTERESTS" in line for line in result.report), result.report


# --- 5. nothing usable survives ------------------------------------------------


async def test_zero_usable_entries_raises_extraction_error() -> None:
    # The only entry's org is absent from the source, so grounding drops it.
    extraction = _ExtractedCv(
        meta=_ExtractedMeta(),
        sections=[
            _ExtractedSection(
                heading="WORK EXPERIENCE",
                entries=[
                    _ExtractedEntry(
                        org="Ghost Corp", title="Senior Backend Engineer", dates="2026", bullets=[]
                    )
                ],
                skills=[],
            )
        ],
    )
    with pytest.raises(ExtractionError):
        await extract_facts(StubBackend(extraction), tex_source=REAL_TEX)


async def test_no_known_sections_raises_extraction_error() -> None:
    extraction = _ExtractedCv(
        meta=_ExtractedMeta(),
        sections=[
            _ExtractedSection(
                heading="HOBBIES",
                entries=[
                    _ExtractedEntry(
                        org="Northwind Labs",
                        title="Senior Backend Engineer",
                        dates="2026",
                        bullets=[],
                    )
                ],
                skills=[],
            )
        ],
    )
    with pytest.raises(ExtractionError):
        await extract_facts(StubBackend(extraction), tex_source=REAL_TEX)


# --- 6. backend failure --------------------------------------------------------


@pytest.mark.parametrize("mode", ["invalid", "raise"])
async def test_a_backend_failure_is_an_extraction_error(mode: str) -> None:
    backend = (
        StubBackend(ok=False, error="schema invalid")
        if mode == "invalid"
        else StubBackend(raise_on_call=True)
    )
    with pytest.raises(ExtractionError):
        await extract_facts(backend, tex_source=REAL_TEX)


async def test_empty_source_is_an_extraction_error() -> None:
    with pytest.raises(ExtractionError):
        await extract_facts(StubBackend(_real_extraction()), tex_source="   \n ")


# --- 7. the grounding invariant is structural ----------------------------------


async def test_every_stored_entity_is_a_substring_of_the_grounded_source() -> None:
    grounded = _grounded(REAL_TEX)
    mutations = [
        _real_extraction(),
        _two_entry_extraction(bad_org="Ghost Corp"),
        _two_entry_extraction(bad_title="Chief Wizard"),
        _two_entry_extraction(name="Jane Fabricated"),
    ]

    for extraction in mutations:
        result = await extract_facts(StubBackend(extraction), tex_source=REAL_TEX)
        for org in result.facts["orgs"]:
            assert _grounded(org["name"]) in grounded, org
        for title in result.facts["titles"]:
            assert _grounded(title["name"]) in grounded, title
        name = result.facts["meta"].get("name")
        if name:
            assert _grounded(name) in grounded


# --- 8. the actual captured wire shapes are normalised -------------------------


def _captured_payload() -> dict:
    """The exact malformed shape a live call returned (2026-09-28).

    ``entries``/``skills`` came back as ``""`` where a list was required, and a
    bare year came back as the JSON number ``2026`` where a string was required.
    """
    payload = _real_extraction().model_dump()
    payload["sections"][0]["skills"] = ""  # entries-only section: empty string
    payload["sections"][4]["entries"] = ""  # skills-only section: empty string
    payload["sections"][1]["entries"][0]["dates"] = 2026  # bare year as int
    return payload


async def test_the_live_failure_shape_is_normalised_and_loads(tmp_path: Path) -> None:
    backend = StubBackend(cv_json=json.dumps(_captured_payload()))

    result = await extract_facts(backend, tex_source=REAL_TEX)
    facts = _write_and_load(result.facts, tmp_path)

    assert len(facts.sections) == 5
    assert len(facts.all_entries()) == 5
    # The JSON number 2026 became the string "2026" and then the bare-year month.
    widget = facts.entry_by_id("exp/widget-kit-2026")
    assert widget is not None
    assert widget.start == "2026-01"
    assert widget.end is None


@pytest.mark.parametrize(
    "wrap",
    [
        lambda body: f"```json\n{body}\n```",
        lambda body: f"```\n{body}\n```",
        lambda body: f"Here is the CV:\n{body}\nDone.",
    ],
)
async def test_a_fenced_or_prose_wrapped_json_document_is_parsed(
    tmp_path: Path, wrap
) -> None:
    body = json.dumps(_real_extraction().model_dump())
    backend = StubBackend(cv_json=wrap(body))

    result = await extract_facts(backend, tex_source=REAL_TEX)
    facts = _write_and_load(result.facts, tmp_path)

    assert len(facts.all_entries()) == 5


async def test_sections_as_an_object_keyed_by_heading_become_a_list(
    tmp_path: Path,
) -> None:
    payload = {
        "meta": {"name": "Alex Example"},
        "sections": {
            "WORK EXPERIENCE": {
                "entries": [
                    {
                        "org": "Northwind Labs",
                        "title": "Senior Backend Engineer",
                        "dates": "2021 - 2023",
                        "bullets": ["Built the ingest path"],
                    }
                ],
                "skills": [],
            },
            "CODING PROFICIENCY": {"entries": [], "skills": ["Python"]},
        },
    }

    result = await extract_facts(
        StubBackend(cv_json=json.dumps(payload)), tex_source=REAL_TEX
    )
    facts = _write_and_load(result.facts, tmp_path)

    assert {section.title_key for section in facts.sections} == {
        "sec.experience",
        "sec.skills",
    }
    assert facts.all_entries(), "the keyed heading must become the section heading"


async def test_a_string_bullets_field_becomes_a_one_element_list(tmp_path: Path) -> None:
    payload = {
        "meta": {"name": "Alex Example"},
        "sections": [
            {
                "heading": "WORK EXPERIENCE",
                "entries": [
                    {
                        "org": "Northwind Labs",
                        "title": "Senior Backend Engineer",
                        "dates": "2021 - 2023",
                        "bullets": "Built the ingest path",
                    }
                ],
                "skills": [],
            }
        ],
    }

    result = await extract_facts(
        StubBackend(cv_json=json.dumps(payload)), tex_source=REAL_TEX
    )
    facts = _write_and_load(result.facts, tmp_path)

    assert [bullet.text for bullet in facts.all_entries()[0].bullets] == [
        "Built the ingest path"
    ]


async def test_a_null_meta_becomes_an_empty_meta(tmp_path: Path) -> None:
    payload = {
        "meta": None,
        "sections": [
            {
                "heading": "WORK EXPERIENCE",
                "entries": [
                    {
                        "org": "Northwind Labs",
                        "title": "Senior Backend Engineer",
                        "dates": "2021 - 2023",
                        "bullets": [],
                    }
                ],
                "skills": [],
            }
        ],
    }

    result = await extract_facts(
        StubBackend(cv_json=json.dumps(payload)), tex_source=REAL_TEX
    )
    facts = _write_and_load(result.facts, tmp_path)

    assert facts.meta.name is None
    assert facts.all_entries()


@pytest.mark.parametrize("raw", ["not json at all", "{ broken", "[1, 2, 3]"])
async def test_a_non_json_or_non_object_cv_string_raises_extraction_error(
    raw: str,
) -> None:
    with pytest.raises(ExtractionError):
        await extract_facts(StubBackend(cv_json=raw), tex_source=REAL_TEX)
