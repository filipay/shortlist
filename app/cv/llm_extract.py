"""Model-assisted ``.tex`` -> fact-store extraction — the hybrid half of D-59.

The deterministic importer (:mod:`app.cv.import_tex`) parses one tractable LaTeX
subset and never guesses; a document outside that subset yields an unresolved field
and the fact store refuses it. The user's real CV is exactly that case: a title-first
``\\workentry`` macro, bullets in a custom environment passed as the macro's 4th
argument, headings outside the two-key vocabulary, and bare-year dates.

This module adds a second, model-assisted path without weakening the first:

1. The model is asked for a LOOSE, human-shaped reading of the document — verbatim
   strings only, no ids, no enum, no stored shape (:class:`_ExtractedCv`).
2. Everything that carries identity is then compiled DETERMINISTICALLY here: section
   keys, entry/org/title ids, dates, enumerations and ordering. The model never
   chooses an id and never emits the final stored shape.

The anti-fabrication control is the **grounding guard** in :func:`_to_facts_dict`: an
entry, a name or a contact value is kept only when the model's string appears
literally in the supplied ``.tex`` source. A value the model invented is, by
construction, not in the source, so it cannot reach the store.

The ``.tex`` is untrusted content and travels on the ``parts`` channel only; the
prompt constant below is the whole system instruction, with no interpolation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import settings
from app.cv.import_tex import _org_id, _parse_date_range, _title_id
from app.domain.cv import (
    SCHEMA_VERSION,
    SECTION_TITLES,
    CvFacts,
    derive_bullet_id,
    qualify_entry_ids,
    slugify,
)

#: The frozen system instruction. No f-string, no ``%``, no ``.format`` and no
#: request-derived value: the ``.tex`` is the sole ``parts`` entry. Every clause here
#: is an explicit anti-fabrication rule; the compile step enforces them structurally.
CV_EXTRACT_SYSTEM_PROMPT = (
    "You extract a candidate's CV from a LaTeX document. "
    "Extract ONLY what is literally present in the document. Never invent, infer, "
    "translate, expand, summarise or reformat an employer, job title, date, school, "
    "skill or bullet. Quote every string verbatim, in the document's own wording and "
    "spelling. If a field is absent, leave it null or empty — never guess. "
    "Copy dates exactly as written, including bare years such as '2026' and an open "
    "end written as 'present', 'now' or 'current'. "
    "Group the document's real headings into sections and emit each heading verbatim; "
    "do NOT map a heading to any other vocabulary. "
    "Each entry's org, title and dates must come from the SAME entry construct in the "
    "document — never pair one entry's date with another entry's employer. "
    "A section that is a flat list of skills or languages, with no employer, job title "
    "or dates, must be emitted as skills with no entries. "
    "Output only the requested JSON."
)


class _ExtractedMeta(BaseModel):
    """Identity and contact as the model read them — verbatim strings only."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    links: list[str] = Field(default_factory=list)


class _ExtractedEntry(BaseModel):
    """One entry construct. ``dates`` is VERBATIM as written in the source."""

    model_config = ConfigDict(extra="forbid")

    org: str
    title: str
    dates: str
    location: str | None = None
    bullets: list[str]


class _ExtractedSection(BaseModel):
    """One document heading and what sits under it. ``heading`` is VERBATIM."""

    model_config = ConfigDict(extra="forbid")

    heading: str
    entries: list[_ExtractedEntry]
    skills: list[str]


class _ExtractedCv(BaseModel):
    """The loose, model-facing document. There is deliberately no id field."""

    model_config = ConfigDict(extra="forbid")

    meta: _ExtractedMeta
    sections: list[_ExtractedSection]


class ExtractionError(Exception):
    """Raised when model-assisted extraction cannot produce a usable fact store."""


@dataclass(frozen=True)
class ExtractionResult:
    """A fully-formed fact-store dict plus short, UI-safe report lines."""

    facts: dict
    report: list[str]


# ---------------------------------------------------------------------------
# deterministic compile helpers
# ---------------------------------------------------------------------------

_WHITESPACE_RE = re.compile(r"\s+")

#: Heading synonyms, keyed by the NORMALISED heading (casefold + collapsed
#: whitespace). Seeded from ``SECTION_TITLES`` so the stored vocabulary can never
#: regress, then extended with the real-document vocabulary.
_HEADING_SYNONYMS: dict[str, str] = {
    title.casefold(): key for key, title in SECTION_TITLES.items()
}
_HEADING_SYNONYMS.update(
    {
        "work experience": "sec.experience",
        "professional experience": "sec.experience",
        "employment": "sec.experience",
        "work history": "sec.experience",
        "personal projects": "sec.projects",
        "selected projects": "sec.projects",
        "technical skills": "sec.skills",
        "coding proficiency": "sec.skills",
        "programming": "sec.skills",
        "languages": "sec.skills",
        "programming languages": "sec.skills",
        "technologies": "sec.skills",
        "volunteer": "sec.volunteering",
        "volunteer experience": "sec.volunteering",
        "volunteer work": "sec.volunteering",
    }
)

#: A bare-year range or open end: ``2021 - 2023``, ``2026 - present``. The single
#: hyphen is accepted here (unlike the MM forms, where it would be ambiguous).
_BARE_YEAR_RANGE_RE = re.compile(
    r"^\s*(\d{4})\s*(?:--|—|–|to|-)\s*(\d{4}|present|now|current)\s*(?:,\s*(.*?))?\s*$",
    re.IGNORECASE,
)
#: A single bare year, optionally followed by a location: ``2026``, ``2026, Dublin``.
_BARE_YEAR_RE = re.compile(r"^\s*(\d{4})\s*(?:,\s*(.*?))?\s*$")
_OPEN_END = frozenset({"present", "now", "current"})


def _normalise(value: str) -> str:
    """Casefold, collapse whitespace, strip — the one normalisation for grounding."""
    return _WHITESPACE_RE.sub(" ", value.casefold()).strip()


def _appears(grounded_source: str, value: str | None) -> bool:
    """True when ``value`` appears verbatim in the already-grounded source text."""
    if not value:
        return False
    return _normalise(value) in grounded_source


def _section_key(heading: str) -> str | None:
    """Map a verbatim heading onto a stored section key, or ``None`` if unmapped."""
    return _HEADING_SYNONYMS.get(_normalise(heading))


def _parse_dates(text: str) -> tuple[str, str | None, str | None] | None:
    """Wrap the importer's date parser to also accept bare years (D-59).

    Delegates first to :func:`app.cv.import_tex._parse_date_range` (full ``YYYY-MM``
    forms and their ranges, with an optional location). Only when that fails does it
    accept the real-document forms:

    - a bare year -> ``("2026-01", None, None)``;
    - a bare-year range -> ``("2021-01", "2023-01", None)``;
    - ``present`` / ``now`` / ``current`` as the end -> an open end (``None``);
    - the optional ``, <location>`` suffix.

    The only month ever synthesised is the documented ``-01`` for a bare year. A
    string that matches nothing returns ``None``; the caller DROPS the entry rather
    than guessing.
    """
    parsed = _parse_date_range(text)
    if parsed is not None:
        return parsed

    range_match = _BARE_YEAR_RANGE_RE.match(text)
    if range_match is not None:
        start, end, location = range_match.groups()
        end_value = None if end.casefold() in _OPEN_END else f"{end}-01"
        return f"{start}-01", end_value, (location.strip() if location else None)

    single_match = _BARE_YEAR_RE.match(text)
    if single_match is not None:
        start, location = single_match.groups()
        return f"{start}-01", None, (location.strip() if location else None)
    return None


def _to_facts_dict(
    extracted: _ExtractedCv, tex_source: str, now: datetime | None
) -> tuple[dict[str, Any], list[str]]:
    """Compile the loose extraction into the strict fact-store shape.

    Returns ``(facts, report)``. The model owns no identity here: section keys,
    enumerations, dates and every id are derived in this function. Raises
    :class:`ExtractionError` when nothing usable survives. ``now`` is accepted for
    the caller's clock; the compile is not date-relative today.

    (Rule letters below match the module's task spec.)
    """
    grounded = _normalise(tex_source)
    drops: list[str] = []

    # (e) meta. `Meta` has no location field, so a model-supplied location cannot be
    # stored — it is reported rather than silently discarded.
    meta: dict[str, Any] = {"max_pages": 2}
    if extracted.meta.name:
        if _appears(grounded, extracted.meta.name):
            meta["name"] = extracted.meta.name
        else:
            drops.append(
                f"dropped meta.name {extracted.meta.name!r}: not found verbatim in the source"
            )
    if extracted.meta.location:
        drops.append(
            f"dropped meta.location {extracted.meta.location!r}: "
            "the fact-store meta has no location field"
        )

    contact: dict[str, Any] = {}
    for field in ("email", "phone"):
        value = getattr(extracted.meta, field)
        if not value:
            continue
        if _appears(grounded, value):
            contact[field] = value
        else:
            drops.append(f"dropped meta.{field} {value!r}: not found verbatim in the source")
    links: list[str] = []
    for link in extracted.meta.links:
        if _appears(grounded, link):
            links.append(link)
        else:
            drops.append(f"dropped meta link {link!r}: not found verbatim in the source")
    if links:
        contact["links"] = links
    if contact:
        meta["contact"] = contact

    # (a) heading -> key, preserving first-seen document order; duplicate headings
    # mapping to the same key merge into one section.
    key_order: list[str] = []
    entries_by_key: dict[str, list[dict[str, Any]]] = {}
    skills_by_key: dict[str, list[str]] = {}
    for section in extracted.sections:
        key = _section_key(section.heading)
        if key is None:
            drops.append(
                f"dropped section {section.heading!r}: heading maps to no known section"
            )
            continue
        if key not in entries_by_key:
            key_order.append(key)
            entries_by_key[key] = []
            skills_by_key[key] = []

        for entry in section.entries:
            # (b) grounding guard — org AND title must both be present verbatim.
            unmatched = [
                value for value in (entry.org, entry.title) if not _appears(grounded, value)
            ]
            if unmatched:
                missing = ", ".join(
                    f"{value!r} not found verbatim in the source" for value in unmatched
                )
                drops.append(
                    f"dropped entry {entry.org!r} — {entry.title!r}: {missing}"
                )
                continue
            # (c) dates — delegate to the importer's machinery plus the bare-year wrap.
            dates = _parse_dates(entry.dates)
            if dates is None:
                drops.append(
                    f"dropped entry {entry.org!r} — {entry.title!r}: "
                    f"unparseable dates {entry.dates!r}"
                )
                continue
            start, end, location = dates
            entries_by_key[key].append(
                {
                    "org": entry.org,
                    "title": entry.title,
                    "start": start,
                    "end": end,
                    "location": location,
                    "bullets": [text for text in entry.bullets if text and text.strip()],
                }
            )

        for label in section.skills:
            if label and label.strip() and label not in skills_by_key[key]:
                skills_by_key[key].append(label)

    # (d) enumerations and ids, reusing the importer's helpers so bare-year IDs stay
    # stable and slug collisions are handled the same way.
    orgs: dict[str, str] = {}
    titles: dict[str, str] = {}
    all_entries = [entry for key in key_order for entry in entries_by_key[key]]
    entry_ids = qualify_entry_ids([(entry["org"], entry["start"]) for entry in all_entries])
    for entry, entry_id in zip(all_entries, entry_ids, strict=True):
        org_id = _org_id(entry["org"])
        if org_id in orgs and orgs[org_id] != entry["org"]:
            drops.append(f"org id collision {org_id!r}: keeping {orgs[org_id]!r}")
        else:
            orgs.setdefault(org_id, entry["org"])
        title_id = _title_id(entry["title"])
        if title_id in titles and titles[title_id] != entry["title"]:
            drops.append(f"title id collision {title_id!r}: keeping {titles[title_id]!r}")
        else:
            titles.setdefault(title_id, entry["title"])
        entry["id"] = entry_id
        entry["org_id"] = org_id
        entry["title_id"] = title_id
        entry["bullets"] = [
            {"id": derive_bullet_id(entry_id, index), "text": text}
            for index, text in enumerate(entry["bullets"], start=1)
        ]
        # The stored `Entry` shape has org_id/title_id, not the model's free strings.
        del entry["org"], entry["title"]

    # (e) sections in document order, with the fixture's skills shape. The model
    # schema carries bare labels only, so every skill gets the honest single default
    # group "skills" and the neutral weight 1.0.
    sections: list[dict[str, Any]] = []
    seen_skill_ids: set[str] = set()
    for index, key in enumerate(key_order):
        entries = entries_by_key[key]
        skills: list[dict[str, Any]] = []
        for label in skills_by_key[key]:
            skill_id = f"skill.{slugify(label)}"
            if skill_id in seen_skill_ids:
                drops.append(f"dropped duplicate skill {label!r}")
                continue
            seen_skill_ids.add(skill_id)
            skills.append({"id": skill_id, "label": label, "group": "skills", "weight": 1.0})
        if not entries and not skills:
            continue
        sections.append(
            {
                "id": key,
                "title_key": key,
                "order": (index + 1) * 10,
                "entries": entries,
                "skills": skills,
            }
        )

    entries_kept = sum(len(section["entries"]) for section in sections)
    if not sections:
        raise ExtractionError("no sections survived extraction")
    if not entries_kept:
        raise ExtractionError("no entries survived extraction")

    facts: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "meta": meta,
        "sections": sections,
        "orgs": [{"id": org_id, "name": name} for org_id, name in orgs.items()],
        "titles": [{"id": title_id, "name": name} for title_id, name in titles.items()],
        "gaps": [],
    }
    # (f) fail closed: a compile that cannot be loaded is a bug, not a published store.
    CvFacts.model_validate(facts)

    report = [
        "extracted from LaTeX with model assistance",
        *drops,
        f"kept {len(sections)} section(s), {entries_kept} entry/entries",
    ]
    return facts, report


async def extract_facts(
    backend: Any,
    *,
    tex_source: str,
    now: datetime | None = None,
) -> ExtractionResult:
    """Extract a fact store from ``tex_source`` with one model-assisted call.

    Raises :class:`ExtractionError` — never a bare exception — when the backend call
    fails, when the structured output does not validate, when the model emits no
    usable content, or when the deterministic compile cannot produce a store that
    :func:`app.cv.factstore.load_facts` accepts. ``now`` is reserved for a future
    date-relative rule and does not affect the compile today.
    """
    if not tex_source or not tex_source.strip():
        raise ExtractionError("no LaTeX source was supplied")

    try:
        result = await backend.complete_structured(
            schema=_ExtractedCv,
            system=CV_EXTRACT_SYSTEM_PROMPT,
            parts=[tex_source],
            model=settings.opencode_model,
            tools=(),
            retries=settings.opencode_max_retries,
        )
    except Exception as exc:  # noqa: BLE001 — a raised transport error is a value here
        raise ExtractionError(f"the extraction call failed: {type(exc).__name__}") from exc

    if not result.ok or not isinstance(result.data, _ExtractedCv):
        raise ExtractionError(
            "the extraction call did not return a usable CV"
            f" ({result.error or result.status})"
        )

    try:
        facts, report = _to_facts_dict(result.data, tex_source, now)
    except ExtractionError:
        raise
    except ValidationError as exc:
        raise ExtractionError(f"the compiled fact store did not validate: {exc}") from exc
    return ExtractionResult(facts=facts, report=report)
