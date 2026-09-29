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
    DEFAULT_SKILL_GROUP,
    ExtractionError,
    _appears,
    _ExtractedCv,
    _ExtractedEntry,
    _ExtractedEnvelope,
    _ExtractedMeta,
    _ExtractedSection,
    _ExtractedSkill,
    _normalise,
    _normalise_latex,
    extract_facts,
)
from app.domain.cv import iter_fact_ids
from app.llm.base import DiscoveryResult, ProbeOutcome, StructuredCallResult

# ---------------------------------------------------------------------------
# a canned document mirroring the user's real shape
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

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
    # A bare-string skill (the pre-grouping literal shape) still validates and
    # compiles to the one honest default group.
    assert {
        skill.group for section in facts.sections for skill in section.skills
    } == {DEFAULT_SKILL_GROUP}
    # The model chose no ids: every entry id is derived from org + start year.
    assert all(entry.id.startswith("exp/") for entry in facts.all_entries())
    assert result.report[0] == "extracted from LaTeX with model assistance"
    assert any("kept 5 section(s), 5 entry/entries" in line for line in result.report)


# --- 1b. skills carry a document-derived group --------------------------------


#: A document whose skills are grouped with the document's own labels (Languages,
#: Databases), so a grounded group is available to attach.
_GROUPED_TEX = (
    "Alex Example\n"
    "\\section*{WORK EXPERIENCE}\n"
    "\\workentry{Senior Backend Engineer}{Northwind Labs}{2021 - 2023}"
    "{Built the ingest path}\n"
    "\\section*{CODING PROFICIENCY}\n"
    "Languages: Python, Go\n"
    "Databases: SQL\n"
)


async def test_a_document_group_reaches_the_store_and_an_ungrounded_one_falls_back(
    tmp_path: Path,
) -> None:
    """The group the model emits is grounded; a group the document lacks is dropped."""
    extraction = _ExtractedCv(
        meta=_ExtractedMeta(name="Alex Example"),
        sections=[
            _ExtractedSection(
                heading="WORK EXPERIENCE",
                entries=[
                    _ExtractedEntry(
                        org="Northwind Labs",
                        title="Senior Backend Engineer",
                        dates="2021 - 2023",
                        bullets=["Built the ingest path"],
                    )
                ],
                skills=[],
            ),
            _ExtractedSection(
                heading="CODING PROFICIENCY",
                entries=[],
                skills=[
                    _ExtractedSkill(label="Python", group="Languages"),
                    _ExtractedSkill(label="Go", group="Languages"),
                    _ExtractedSkill(label="SQL", group="Invented Group"),
                ],
            ),
        ],
    )

    result = await extract_facts(StubBackend(extraction), tex_source=_GROUPED_TEX)
    facts = _write_and_load(result.facts, tmp_path)

    groups = {
        skill.label: skill.group for section in facts.sections for skill in section.skills
    }
    assert groups == {
        "Python": "Languages",
        "Go": "Languages",
        "SQL": DEFAULT_SKILL_GROUP,
    }
    # The invented group is named in the report; the grounded one is not.
    assert any(
        "dropped skill.group 'Invented Group'" in line for line in result.report
    ), result.report
    assert not any(
        "dropped skill.group 'Languages'" in line for line in result.report
    ), result.report


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


# --- 9. grounding against the RENDERED source view (macro-heavy) ---------------

MACRO_TEX = (
    PROJECT_ROOT / "tests" / "fixtures" / "cv" / "macro_heavy_standin.tex"
).read_text(encoding="utf-8")


def _macro_extraction() -> _ExtractedCv:
    """The values a model returns for `MACRO_TEX`, in rendered form."""
    return _ExtractedCv(
        meta=_ExtractedMeta(name="Alex Example", email="alex.example@example.invalid"),
        sections=[
            _ExtractedSection(
                heading="WORK EXPERIENCE",
                entries=[
                    _ExtractedEntry(
                        org="Globex & Sons",
                        title="Operations Analyst & Co-Founder",
                        dates="2021 - 2023",
                        bullets=["Ran the fake operations desk"],
                    ),
                    _ExtractedEntry(
                        org="Initech",
                        title="Thing One | github/example-lab",
                        dates="2026 - present",
                        bullets=["Maintained the synthetic lab"],
                    ),
                ],
                skills=[],
            ),
            _ExtractedSection(
                heading="PROJECTS",
                entries=[
                    _ExtractedEntry(
                        org="Widget Kit",
                        title="MSc in Data Analytics (1:1) × Level 9",
                        dates="2026",
                        bullets=["Shipped a synthetic widget"],
                    ),
                    # Section-aware rule: the project's own name is the org and the
                    # tech stack is the title (both verbatim from the source).
                    _ExtractedEntry(
                        org="Thing One Dashboards",
                        title="Python, Go",
                        dates="2027",
                        bullets=["Built a synthetic dashboard"],
                    ),
                ],
                skills=[],
            ),
            _ExtractedSection(
                heading="EDUCATION",
                entries=[
                    _ExtractedEntry(
                        org="Example University",
                        title="BSc Example Studies",
                        dates="2024",
                        bullets=["Imaginary degree"],
                    ),
                    # awesome-cv shape: org and location in SEPARATE source args.
                    _ExtractedEntry(
                        org="Northgate Institute of Technology",
                        title="Research Assistant",
                        dates="2023",
                        location="Exampleland",
                        bullets=["Assisted with synthetic research"],
                    ),
                ],
                skills=[],
            ),
            _ExtractedSection(
                heading="VOLUNTEERING",
                entries=[
                    _ExtractedEntry(
                        org="Example Code Club",
                        title="Mentor",
                        dates="2021 - 2023",
                        bullets=["Mentored imaginary people"],
                    )
                ],
                skills=[],
            ),
            _ExtractedSection(
                heading="CODING PROFICIENCY", entries=[], skills=["Python", "Go", "SQL"]
            ),
        ],
    )


def test_normalise_latex_reduces_markup_to_rendered_text() -> None:
    assert _normalise_latex(r"\href{https://example.invalid/x}{label}") == "label"
    assert _normalise_latex(r"\&") == "&"
    assert _normalise_latex(r"\texttimes") == "×"
    assert _normalise_latex(r"\times") == "×"
    assert _normalise_latex(r"\{x\}") == "{x}"
    assert _normalise_latex("alpha % a comment\nbeta") == "alpha beta"
    assert _normalise_latex(r"\textbf{bold} text") == "bold text"


async def test_href_times_and_ampersand_values_are_grounded_and_stored(
    tmp_path: Path,
) -> None:
    result = await extract_facts(StubBackend(_macro_extraction()), tex_source=MACRO_TEX)
    facts = _write_and_load(result.facts, tmp_path)

    assert not any("dropped entry" in line for line in result.report), result.report
    assert len(facts.sections) == 5
    assert len(facts.all_entries()) == 7
    org_names = {org.name for org in facts.orgs}
    title_names = {title.name for title in facts.titles}
    assert "Globex & Sons" in org_names
    assert "Operations Analyst & Co-Founder" in title_names
    assert "Thing One | github/example-lab" in title_names
    assert "MSc in Data Analytics (1:1) × Level 9" in title_names
    assert len({section.title_key for section in facts.sections}) == 5


async def test_a_value_absent_from_both_views_is_still_dropped_and_named(
    tmp_path: Path,
) -> None:
    """The guard was not weakened: an invented org is dropped and reported."""
    extraction = _macro_extraction()
    # Append a fabricated org whose string is nowhere in the document.
    extraction.sections[0].entries.append(
        _ExtractedEntry(
            org="Nonesuch Fabricated Ltd",
            title="Operations Analyst & Co-Founder",
            dates="2021 - 2023",
            bullets=[],
        )
    )

    result = await extract_facts(StubBackend(extraction), tex_source=MACRO_TEX)
    facts = _write_and_load(result.facts, tmp_path)

    assert "Nonesuch Fabricated Ltd" not in {org.name for org in facts.orgs}
    assert any("Nonesuch Fabricated Ltd" in line for line in result.report), result.report
    assert any("dropped entry" in line for line in result.report)


async def test_the_drop_message_names_the_failing_field(tmp_path: Path) -> None:
    extraction = _macro_extraction()
    extraction.sections[0].entries.append(
        _ExtractedEntry(
            org="Globex & Sons",
            title="Chief Wizard of Nowhere",
            dates="2021 - 2023",
            bullets=[],
        )
    )

    result = await extract_facts(StubBackend(extraction), tex_source=MACRO_TEX)

    assert any(
        line.startswith("dropped entry:") and "title 'Chief Wizard of Nowhere'" in line
        for line in result.report
    ), result.report
    # `org` is grounded, so it must NOT be named as the failure.
    assert not any(
        "org 'Globex & Sons'" in line for line in result.report
    ), result.report


async def test_every_kept_entity_appears_in_the_raw_or_rendered_source(
    tmp_path: Path,
) -> None:
    raw = _normalise(MACRO_TEX)
    rendered = _normalise(_normalise_latex(MACRO_TEX))

    result = await extract_facts(StubBackend(_macro_extraction()), tex_source=MACRO_TEX)
    facts = _write_and_load(result.facts, tmp_path)

    org_names = {org.id: org.name for org in facts.orgs}
    title_names = {title.id: title.name for title in facts.titles}
    for entry in facts.all_entries():
        for value in (org_names[entry.org_id], title_names[entry.title_id]):
            needle = _normalise(value)
            assert needle in raw or needle in rendered, value
        # A stored location must satisfy the SAME invariant.
        if entry.location:
            assert _appears(raw, rendered, entry.location), entry.location

    # Mutation control: an absent location must not be stored.
    mutated = _macro_extraction()
    mutated.sections[2].entries[0].location = "Nonesuchville"
    mutated_result = await extract_facts(StubBackend(mutated), tex_source=MACRO_TEX)
    mutated_facts = _write_and_load(mutated_result.facts, tmp_path)
    assert all(
        entry.location != "Nonesuchville" for entry in mutated_facts.all_entries()
    )


async def test_a_separate_location_argument_is_stored_not_glued(
    tmp_path: Path,
) -> None:
    """The dead `location` field is wired: org and location stay separate.

    The awesome-cv `\\cventry` entry carries org and location in separate source
    arguments, so the glued `'org, location'` string is nowhere in the document.
    """
    result = await extract_facts(StubBackend(_macro_extraction()), tex_source=MACRO_TEX)
    facts = _write_and_load(result.facts, tmp_path)

    entry = facts.entry_by_id("exp/northgate-institute-of-technology-2023")
    assert entry is not None
    assert entry.location == "Exampleland"
    org_names = {org.name for org in facts.orgs}
    assert "Northgate Institute of Technology" in org_names
    glued = "Northgate Institute of Technology, Exampleland"
    assert glued not in org_names
    assert glued not in {title.name for title in facts.titles}
    assert "Exampleland" not in org_names


async def test_a_model_location_on_a_bare_year_is_stored(tmp_path: Path) -> None:
    """The model can put a location in its own field, independent of `dates`."""
    tex = (
        "\\section*{EDUCATION}\n"
        "\\workentry{BSc Example Studies}{Example University}{2024}{Example City}\n"
    )
    extraction = _ExtractedCv(
        meta=_ExtractedMeta(),
        sections=[
            _ExtractedSection(
                heading="EDUCATION",
                entries=[
                    _ExtractedEntry(
                        org="Example University",
                        title="BSc Example Studies",
                        dates="2024",
                        location="Example City",
                        bullets=[],
                    )
                ],
                skills=[],
            )
        ],
    )

    result = await extract_facts(StubBackend(extraction), tex_source=tex)
    facts = _write_and_load(result.facts, tmp_path)

    entry = facts.entry_by_id("exp/example-university-2024")
    assert entry is not None
    assert entry.location == "Example City"
    assert entry.start == "2024-01"


async def test_an_ungrounded_location_is_dropped_but_the_entry_survives(
    tmp_path: Path,
) -> None:
    """Location is optional and not identity-bearing: never drop the entry for it."""
    extraction = _macro_extraction()
    # The BSc entry has `dates="2024"` with no location suffix, so the fallback is None.
    extraction.sections[2].entries[0].location = "Nonesuchville"

    result = await extract_facts(StubBackend(extraction), tex_source=MACRO_TEX)
    facts = _write_and_load(result.facts, tmp_path)

    entry = facts.entry_by_id("exp/example-university-2024")
    assert entry is not None, "the entry must survive an ungrounded location"
    assert entry.location is None
    assert any("Nonesuchville" in line for line in result.report), result.report
    assert any(
        "dropped entry.location 'Nonesuchville'" in line for line in result.report
    ), result.report


async def test_a_grounded_location_prefers_the_model_field_over_the_dates_suffix(
    tmp_path: Path,
) -> None:
    """A separate grounded location wins over a `dates`-suffix fallback."""
    tex = (
        "\\section*{EDUCATION}\n"
        "\\workentry{BSc Example Studies}{Example University}{2024, Testville}{Sampletown}\n"
    )
    extraction = _ExtractedCv(
        meta=_ExtractedMeta(),
        sections=[
            _ExtractedSection(
                heading="EDUCATION",
                entries=[
                    _ExtractedEntry(
                        org="Example University",
                        title="BSc Example Studies",
                        dates="2024, Testville",
                        location="Sampletown",
                        bullets=[],
                    )
                ],
                skills=[],
            )
        ],
    )

    result = await extract_facts(StubBackend(extraction), tex_source=tex)
    facts = _write_and_load(result.facts, tmp_path)

    entry = facts.entry_by_id("exp/example-university-2024")
    assert entry is not None
    # The dates suffix (`Testville`) is the fallback; the grounded model field wins.
    assert entry.location == "Sampletown"


async def test_a_joined_value_still_drops_as_a_named_residual() -> None:
    """TASK 3 residual: a value JOINED from separate source fragments still drops.

    Neither the raw nor the rendered view contains `'Globex & Sons, Initech'` as a
    contiguous string — the join exists only in the model's output. Token-level or
    order-insensitive matching would accept it and weaken anti-fabrication, so it
    is deliberately left dropping.
    """
    extraction = _macro_extraction()
    joined_org = "Globex & Sons, Initech"
    extraction.sections[0].entries.append(
        _ExtractedEntry(
            org=joined_org,
            title="Operations Analyst & Co-Founder",
            dates="2021 - 2023",
            bullets=[],
        )
    )

    result = await extract_facts(StubBackend(extraction), tex_source=MACRO_TEX)

    assert any(joined_org in line for line in result.report), result.report
    assert any("dropped entry" in line for line in result.report)


# --- 10. meta.location is grounded and stored ----------------------------------

_LOCATION_TEX = (
    "Alex Example\n"
    "Exampleville, Exampleland\n"
    "\\section*{WORK EXPERIENCE}\n"
    "\\workentry{Senior Backend Engineer}{Northwind Labs}{2021 - 2023}{Built the ingest path}\n"
)


def _location_extraction(location: str | None) -> _ExtractedCv:
    return _ExtractedCv(
        meta=_ExtractedMeta(name="Alex Example", location=location),
        sections=[
            _ExtractedSection(
                heading="WORK EXPERIENCE",
                entries=[
                    _ExtractedEntry(
                        org="Northwind Labs",
                        title="Senior Backend Engineer",
                        dates="2021 - 2023",
                        bullets=["Built the ingest path"],
                    )
                ],
                skills=[],
            )
        ],
    )


async def test_a_grounded_meta_location_is_stored(tmp_path: Path) -> None:
    result = await extract_facts(
        StubBackend(_location_extraction("Exampleville, Exampleland")),
        tex_source=_LOCATION_TEX,
    )
    facts = _write_and_load(result.facts, tmp_path)

    assert facts.meta.location == "Exampleville, Exampleland"
    assert facts.meta.name == "Alex Example"
    assert facts.all_entries(), "the entry behaviour is unchanged"
    assert not any("dropped meta.location" in line for line in result.report)


async def test_an_ungrounded_meta_location_is_dropped_and_named(tmp_path: Path) -> None:
    result = await extract_facts(
        StubBackend(_location_extraction("Atlantis")),
        tex_source=_LOCATION_TEX,
    )
    facts = _write_and_load(result.facts, tmp_path)

    assert facts.meta.location is None
    assert any("dropped meta.location 'Atlantis'" in line for line in result.report)
    assert any("not found in the document" in line for line in result.report)
    # The grounded fields and the entry are unaffected by the location drop.
    assert facts.meta.name == "Alex Example"
    assert facts.all_entries()


# --- 11. section-aware org rule, multiplication glyphs, empty-org message -------


async def test_a_project_row_uses_the_project_name_as_org(tmp_path: Path) -> None:
    """The section-aware rule: project name -> org, tech stack -> title."""
    result = await extract_facts(StubBackend(_macro_extraction()), tex_source=MACRO_TEX)
    facts = _write_and_load(result.facts, tmp_path)

    entry = facts.entry_by_id("exp/thing-one-dashboards-2027")
    assert entry is not None, "the project row must survive"
    orgs = {org.id: org.name for org in facts.orgs}
    titles = {title.id: title.name for title in facts.titles}
    assert orgs[entry.org_id] == "Thing One Dashboards"
    assert titles[entry.title_id] == "Python, Go"
    # The tech stack is not in org and the project name is not in title.
    assert "Python, Go" not in orgs.values()
    assert "Thing One Dashboards" not in titles.values()
    # The location stays in its own (here absent) field, never glued onto the org.
    assert entry.location is None
    assert not any(
        "Thing One Dashboards" in line and line.startswith("dropped entry")
        for line in result.report
    ), result.report


def test_normalise_neutralises_the_multiplication_glyph_class_to_whitespace() -> None:
    for variant in (
        "\u00d7",  # ×
        "\u2a2f",  # ⨯
        "\u2715",  # ✕
        "\u2716",  # ✖
        "\u22c5",  # ⋅
        "\u00b7",  # ·
        "\uff0a",  # ＊ (NFKC -> *)
    ):
        assert _normalise(f"a {variant} b") == "a b", repr(variant)
    # Ordinary letters and digits are never folded.
    assert _normalise("Level 9") == "level 9"
    assert _normalise("Cats") == "cats"
    # `_normalise_latex` still emits the VISIBLE canonical token for both commands;
    # the outer `_normalise` then neutralises it to whitespace like any other variant.
    assert _normalise_latex(r"\texttimes") == "\u00d7"
    assert _normalise_latex(r"\times") == "\u00d7"
    assert _normalise(_normalise_latex(r"\texttimes")) == ""


async def test_a_model_multiplication_glyph_variant_still_grounds(
    tmp_path: Path,
) -> None:
    """Task 2 (i): the source's `\\texttimes` and the model's U+2A2F now agree."""
    extraction = _macro_extraction()
    variant_title = "MSc in Data Analytics (1:1) \u2a2f Level 9"
    extraction.sections[1].entries[0].title = variant_title

    result = await extract_facts(StubBackend(extraction), tex_source=MACRO_TEX)
    facts = _write_and_load(result.facts, tmp_path)

    assert not any(
        "MSc in Data Analytics" in line and line.startswith("dropped entry")
        for line in result.report
    ), result.report
    # The model's string is stored verbatim; only the COMPARISON is folded.
    assert variant_title in {title.name for title in facts.titles}


_INSERTED_SEPARATOR_TEX = (
    "\\section*{EDUCATION}\n"
    "\\workentry{BSc Example Studies}{Example University}{2024}{Level 8}\n"
    "\\workentry{MSc Example Studies}{Northgate Institute of Technology}{2025}{Level 9}\n"
)


async def test_a_model_inserted_separator_still_drops() -> None:
    """Task 3 (ii): a separator present in no source view cannot be fixed by folding.

    The two runs exist in the document, but the model joined them with a glyph that
    is nowhere in the source; the joined string is not a contiguous substring of
    either view, so it is deliberately left dropping (no window/fuzzy matching).
    """
    joined_title = "BSc Example Studies \u2a2f Level 8"
    extraction = _ExtractedCv(
        meta=_ExtractedMeta(),
        sections=[
            _ExtractedSection(
                heading="EDUCATION",
                entries=[
                    _ExtractedEntry(
                        org="Example University",
                        title=joined_title,
                        dates="2024",
                        bullets=[],
                    ),
                    _ExtractedEntry(
                        org="Northgate Institute of Technology",
                        title="MSc Example Studies",
                        dates="2025",
                        bullets=[],
                    ),
                ],
                skills=[],
            )
        ],
    )

    result = await extract_facts(
        StubBackend(extraction), tex_source=_INSERTED_SEPARATOR_TEX
    )

    assert any(joined_title in line for line in result.report), result.report
    assert any("dropped entry" in line for line in result.report), result.report


async def test_an_empty_org_drops_with_a_self_explanatory_message() -> None:
    """An empty org says so explicitly, instead of 'org '' not found'."""
    extraction = _macro_extraction()
    # The project row's org is left empty (the real PROJECTS failure shape).
    extraction.sections[1].entries[1].org = ""

    result = await extract_facts(StubBackend(extraction), tex_source=MACRO_TEX)

    assert any(
        "org was empty (no employer, institution or project named)" in line
        for line in result.report
    ), result.report
    assert any("dropped entry" in line for line in result.report), result.report


# --- 12. the separator fold: accept inside a run, reject across a boundary ------

_MULTIPLICATION_VARIANTS = (
    "\u00d7",  # ×
    "\u2a2f",  # ⨯
    "\u2715",  # ✕
    "\u2716",  # ✖
    "\u22c5",  # ⋅
    "\u00b7",  # ·
    "\uff0a",  # ＊ (NFKC -> *)
)

#: A cventry-shaped row whose title carries a course, a grade, a `\hfill` and a level
#: token — the reported degree-row shape. The source's own separator is the spacing
#: command, which the reducer drops and collapses to a single space.
_GLYPH_TITLE_TEX = (
    "\\section*{EDUCATION}\n"
    "\\cventry{MSc in Data Analytics (1:1) \\hfill Level 9}"
    "{Northgate Institute of Technology}{Exampleland}{2024}{%\n"
    "\\begin{highlights}\n"
    "  \\item Synthetic study\n"
    "\\end{highlights}}\n"
)


@pytest.mark.parametrize(
    "glyph", [*_MULTIPLICATION_VARIANTS, None], ids=lambda glyph: repr(glyph)
)
async def test_a_title_separator_inside_one_run_is_stored(
    tmp_path: Path, glyph: str | None
) -> None:
    """The reported drop: a model-inserted separator inside one run now grounds."""
    separator = " " if glyph is None else f" {glyph} "
    title = f"MSc in Data Analytics (1:1){separator}Level 9"
    extraction = _ExtractedCv(
        meta=_ExtractedMeta(),
        sections=[
            _ExtractedSection(
                heading="EDUCATION",
                entries=[
                    _ExtractedEntry(
                        org="Northgate Institute of Technology",
                        title=title,
                        dates="2024",
                        location="Exampleland",
                        bullets=["Synthetic study"],
                    )
                ],
                skills=[],
            )
        ],
    )

    result = await extract_facts(StubBackend(extraction), tex_source=_GLYPH_TITLE_TEX)
    facts = _write_and_load(result.facts, tmp_path)

    entry = facts.entry_by_id("exp/northgate-institute-of-technology-2024")
    assert entry is not None, "the degree row must survive"
    assert title in {candidate.name for candidate in facts.titles}
    assert not any(
        title in line and line.startswith("dropped entry") for line in result.report
    ), result.report


@pytest.mark.parametrize(
    "joiner", [*_MULTIPLICATION_VARIANTS, " "], ids=lambda joiner: repr(joiner)
)
async def test_a_cross_entity_join_is_rejected_for_every_joiner(
    tmp_path: Path, joiner: str
) -> None:
    """Every joiner the fold touches must still reject two glued employers."""
    joined = f"Globex & Sons{joiner}Initech"
    extraction = _macro_extraction()
    extraction.sections[0].entries.append(
        _ExtractedEntry(
            org=joined,
            title="Operations Analyst & Co-Founder",
            dates="2021 - 2023",
            bullets=[],
        )
    )

    result = await extract_facts(StubBackend(extraction), tex_source=MACRO_TEX)
    facts = _write_and_load(result.facts, tmp_path)

    assert joined not in {org.name for org in facts.orgs}
    assert any(joined in line for line in result.report), result.report
    assert any("dropped entry" in line for line in result.report), result.report


def test_the_separator_fold_never_bridges_a_cross_argument_boundary() -> None:
    """Two brace groups are glued with NO space, so a glyph cannot rescue a join."""
    source = "\\section*{WORK EXPERIENCE}\n\\workentry{Alpha}{Beta}{2024}{}\n"
    grounded = _normalise(source)
    rendered = _normalise(_normalise_latex(source))

    for value in ("Alpha Beta", "Alpha \u00d7 Beta", "Alpha\u2a2fBeta", "Alpha \u2a2f Beta"):
        assert not _appears(grounded, rendered, value), value


# --- 13. math-mode pipes, and the parenthetical-institution shape ---------------

#: Every separator spelling the reducer maps to a literal `|`.
_MATH_PIPE_SPELLINGS = (
    "$|$",
    "$\\vert$",
    "$\\mid$",
    "$\\lvert$",
    "$\\rvert$",
    "$\\Vert$",
    "$\\|$",
    "$\\textbar$",
    "\\vert{}",
    "\\mid",
    "\\Vert",
    "\\|",
    "\\textbar{}",
    "|",
)


@pytest.mark.parametrize("spelling", _MATH_PIPE_SPELLINGS, ids=lambda s: repr(s))
async def test_a_math_mode_pipe_before_an_href_grounds(
    tmp_path: Path, spelling: str
) -> None:
    """The reported project shape: a tech-stack arg with a math pipe and an href."""
    tex = (
        "\\section*{PROJECTS}\n"
        "\\workentry{Thing One Dashboards}"
        "{Python, Docker " + spelling
        + " \\href{https://example.invalid/repo-a}{github/example-repo-a}}"
        "{2027}{%\n"
        "\\begin{highlights}\n"
        "  \\item Shipped a synthetic dashboard\n"
        "\\end{highlights}}\n"
    )
    title = "Python, Docker | github/example-repo-a"
    extraction = _ExtractedCv(
        meta=_ExtractedMeta(),
        sections=[
            _ExtractedSection(
                heading="PROJECTS",
                entries=[
                    _ExtractedEntry(
                        org="Thing One Dashboards",
                        title=title,
                        dates="2027",
                        bullets=["Shipped a synthetic dashboard"],
                    )
                ],
                skills=[],
            )
        ],
    )

    result = await extract_facts(StubBackend(extraction), tex_source=tex)
    facts = _write_and_load(result.facts, tmp_path)

    assert title in {candidate.name for candidate in facts.titles}
    assert not any(
        title in line and line.startswith("dropped entry") for line in result.report
    ), result.report
    assert facts.entry_by_id("exp/thing-one-dashboards-2027") is not None


def test_the_reduced_view_keeps_a_literal_math_pipe() -> None:
    assert _normalise_latex(r"Docker $|$ github/repo") == "Docker | github/repo"
    assert _normalise_latex(r"Docker $\vert$ github/repo") == "Docker | github/repo"
    assert _normalise_latex(r"Docker \mid{} github/repo") == "Docker | github/repo"
    assert _normalise_latex(r"Docker \,|\, github/repo") == "Docker | github/repo"
    # An escaped dollar stays a literal; math shifts vanish.
    assert _normalise_latex(r"Cost \$5, not $x$") == "Cost $5, not x"
    # `|` is NOT folded in the comparison normaliser (the cross-entity control needs it).
    assert _normalise("a | b") == "a | b"


async def test_a_pipe_join_of_two_entities_still_drops(tmp_path: Path) -> None:
    """The math-pipe reduction must not weaken the cross-entity control."""
    joined = "Globex & Sons | Initech"
    extraction = _macro_extraction()
    extraction.sections[0].entries.append(
        _ExtractedEntry(
            org=joined,
            title="Operations Analyst & Co-Founder",
            dates="2021 - 2023",
            bullets=[],
        )
    )

    result = await extract_facts(StubBackend(extraction), tex_source=MACRO_TEX)
    facts = _write_and_load(result.facts, tmp_path)

    assert joined not in {org.name for org in facts.orgs}
    assert any(joined in line for line in result.report), result.report
    assert any("dropped entry" in line for line in result.report), result.report


_PARENTHETICAL_ORG_TEX = (
    "\\section*{EDUCATION}\n"
    "\\cventry{Certificate in Software Engineering "
    "(Northgate Institute of Technology \\& Widget Co)}{2024}{}{}{}\n"
)


async def test_an_institution_inside_a_title_parenthetical_grounds_when_split(
    tmp_path: Path,
) -> None:
    """The prompt puts the parenthetical institution in org; the compile accepts it."""
    extraction = _ExtractedCv(
        meta=_ExtractedMeta(),
        sections=[
            _ExtractedSection(
                heading="EDUCATION",
                entries=[
                    _ExtractedEntry(
                        org="Northgate Institute of Technology",
                        title="Certificate in Software Engineering",
                        dates="2024",
                        bullets=[],
                    )
                ],
                skills=[],
            )
        ],
    )

    result = await extract_facts(
        StubBackend(extraction), tex_source=_PARENTHETICAL_ORG_TEX
    )
    facts = _write_and_load(result.facts, tmp_path)

    entry = facts.entry_by_id("exp/northgate-institute-of-technology-2024")
    assert entry is not None, "the certificate row must survive"
    assert "Northgate Institute of Technology" in {org.name for org in facts.orgs}
    assert "Certificate in Software Engineering" in {t.name for t in facts.titles}
