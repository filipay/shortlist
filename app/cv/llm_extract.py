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

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

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
    "Copy each value's text contiguously: never insert a separator, punctuation or "
    "whitespace the document does not itself contain. "
    "An entry's org and its location are SEPARATE fields: copy each verbatim from its "
    "own argument. Never append the location to the org, and never join two source "
    "fragments with a comma. "
    "Map each section's naming entity into org and its descriptor into title even "
    "when the document gives them in one argument: for a WORK EXPERIENCE row org is "
    "the employer and title is the job title; for a PROJECTS row org is the project's "
    "own name and title is its tech stack or description; for an EDUCATION row org is "
    "the institution and title is the degree or programme; for a VOLUNTEERING row org "
    "is the organisation and title is the role. If a row names the employer or "
    "institution inside the title or in a parenthetical, still put that employer or "
    "institution in org and keep the qualification (a degree, a certificate) as title, "
    "copying both verbatim. Leave org empty only when the row genuinely names no such "
    "entity, and never fill org with a role, a degree or a tech stack. "
    "A section that is a flat list of skills or languages, with no employer, job title "
    "or dates, must be emitted as skills with no entries. "
    "Every skill is a {label, group} object: put the skill's own text in label, and "
    "in group copy the label the document itself uses for that skill's grouping, "
    "verbatim (for example Languages, Frameworks, Tools, Data). Do NOT invent a "
    "group: if the document gives no grouping at all, use a single group named "
    "'skills' for every skill in the section. "
    "Put the whole CV as a JSON document in the cv_json string field. "
    "Every list must be a JSON ARRAY: use [] for an empty list, never an empty string "
    "and never a bare string. "
    "Every date must be a JSON STRING, including a bare year: "
    'write "2026", never 2026. '
    "Use exactly this shape, where the values are examples only: "
    '{"meta": {"name": "Alex Example", "email": "alex@example.invalid", '
    '"phone": null, "location": null, "links": []}, '
    '"sections": [{"heading": "WORK EXPERIENCE", '
    '"entries": [{"org": "Globex Inc", "title": "Thing One", '
    '"dates": "2026 - present", "location": null, '
    '"bullets": ["What was actually done"]}], "skills": []}, '
    '{"heading": "SKILLS", "entries": [], "skills": '
    '[{"label": "Python", "group": "Languages"}, {"label": "Go", "group": "Languages"}]}]} '
    "Output only the requested JSON object with the cv_json field."
)


#: The honest fallback group for a skill the extractor cannot attach to a
#: document-grounded group. It is NOT a claim about the document: when the model
#: supplies no group (a bare-string skill) or an ungrounded one, this is the single
#: default the store uses and the renderer emits as the row label.
DEFAULT_SKILL_GROUP = "skills"


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


class _ExtractedSkill(BaseModel):
    """One skill plus the group the document itself groups it under.

    ``label`` is the skill's own text and ``group`` is the document's grouping
    label, both VERBATIM. A group not present in the source is rejected by the
    compile guard and falls back to :data:`DEFAULT_SKILL_GROUP`.
    """

    model_config = ConfigDict(extra="forbid")

    label: str
    group: str


class _ExtractedSection(BaseModel):
    """One document heading and what sits under it. ``heading`` is VERBATIM."""

    model_config = ConfigDict(extra="forbid")

    heading: str
    entries: list[_ExtractedEntry]
    skills: list[_ExtractedSkill]

    @field_validator("skills", mode="before")
    @classmethod
    def _coerce_bare_skill_labels(cls, value: object) -> object:
        """Accept the pre-grouping wire shape: a bare label string is an ungrouped skill.

        The schema asks for ``{label, group}`` objects, but a bare ``"Python"`` — an
        older payload, or a hand-written literal — must keep validating. It compiles
        to :data:`DEFAULT_SKILL_GROUP`. Non-list values are passed through untouched
        so the normal coercion/validation path still reports the shape error.
        """
        if not isinstance(value, list):
            return value
        return [
            {"label": item, "group": DEFAULT_SKILL_GROUP}
            if isinstance(item, str)
            else item
            for item in value
        ]


class _ExtractedCv(BaseModel):
    """The loose, model-facing document. There is deliberately no id field."""

    model_config = ConfigDict(extra="forbid")

    meta: _ExtractedMeta
    sections: list[_ExtractedSection]


class _ExtractedEnvelope(BaseModel):
    """The WIRE schema: one string field carrying the CV as a JSON document.

    The provider's schema-constrained call is reliable at "emit a string" and
    unreliable at a nested array shape — a live call returned ``""`` where a list
    was required and a bare year as a JSON number where a string was required. A
    single string field sidesteps the provider's own structured-shape coercion; the
    JSON inside it is parsed and normalised deterministically by this module, then
    validated against :class:`_ExtractedCv` exactly as before. No safety property
    is loosened: the grounding guard still runs on the compiled result.
    """

    model_config = ConfigDict(extra="forbid")

    cv_json: str


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
    """Casefold, neutralise the multiplication separators, collapse whitespace, strip.

    THE one normalisation for grounding. It is applied to BOTH source views and the
    model value, so folding identically on both sides keeps the comparison a literal
    substring test (never a fuzzy or token match).

    NFKC canonicalises compatibility forms; each multiplication glyph is then
    neutralised to a SPACE, because the source's own representation of that separator
    is whitespace — the spacing commands (``\\hfill`` and friends) drop to nothing
    and collapse to a single space, so the model's visible sign
    (``(1:1) × Level 9``) and the reduced view's space (``(1:1) Level 9``) must
    compare equal. A glyph only ever bridges whitespace that already exists inside
    one run; a separator between two macro arguments (which the reducer glues with
    NO space) is never rescued. Ordinary letters and digits are never folded.
    """
    text = unicodedata.normalize("NFKC", value)
    for glyph in _MULTIPLICATION_GLYPHS:
        text = text.replace(glyph, _MULTIPLICATION_NEUTRAL)
    return _WHITESPACE_RE.sub(" ", text.casefold()).strip()


#: The canonical form ``_normalise_latex`` emits for a ``\\times``/``\\texttimes``
#: separator, so the visible rendered text keeps its sign. The outer ``_normalise``
#: then neutralises this sign to a space like every other variant.
_MULTIPLICATION_CANONICAL = "\u00d7"  # × MULTIPLICATION SIGN
#: What `_normalise` neutralises each separator glyph TO: whitespace. The source's own
#: representation of that separator is whitespace (the spacing commands drop and
#: collapse to one space), so the model's sign and the reduced view must compare equal.
_MULTIPLICATION_NEUTRAL = " "
#: The separator glyphs a model (or a document) may use. NFKC maps ``＊`` U+FF0A to
#: ASCII ``*`` first, hence the ``*`` entry.
_MULTIPLICATION_GLYPHS: tuple[str, ...] = (
    "\u00d7",  # × MULTIPLICATION SIGN
    "\u2a2f",  # ⨯ VECTOR OR CROSS PRODUCT
    "\u2715",  # ✕ MULTIPLICATION X
    "\u2716",  # ✖ HEAVY MULTIPLICATION X
    "\u22c5",  # ⋅ DOT OPERATOR
    "\u00b7",  # · MIDDLE DOT
    "*",  # NFKC image of ＊ U+FF0A
)


#: The escape sequences that appear in real CVs and mean a plain character. Applied
#: after comment stripping so a literal ``\%`` is never read as a comment. ``\$`` is
#: handled separately (see :data:`_DOLLAR_SENTINEL`) so an escaped dollar is not read
#: as a math shift.
_LATEX_ESCAPE_DECODE: tuple[tuple[str, str], ...] = (
    (r"\&", "&"),
    (r"\%", "%"),
    (r"\_", "_"),
    (r"\#", "#"),
)
#: A ``\$`` (a literal dollar) is parked here before math shifts are stripped.
_DOLLAR_SENTINEL = "\x03"
#: Math-mode bar/pipe commands, mapped to a literal ``|``. A bare ``\command`` is
#: DROPPED by the generic rule below, which would delete the separator entirely.
_LATEX_MATH_BAR_RE = re.compile(r"\\(?:[lr]?vert|Vert|mid|textbar)(?![A-Za-z])")
#: Thin/medium math spacing; ``\!`` is negative (removed), the rest become a space.
_LATEX_MATH_SPACING_RE = re.compile(r"\\qquad|\\quad|\\[,;:]|\\!")
#: Escaped braces are parked on sentinels so the generic brace pass cannot eat them.
_LBRACE_SENTINEL = "\x01"
_RBRACE_SENTINEL = "\x02"
#: An UNESCAPED percent starts a comment.
_LATEX_COMMENT_RE = re.compile(r"(?<!\\)%.*")
#: ``\href{URL}{LABEL}`` -> the visible label, handled BEFORE generic commands.
_LATEX_HREF_RE = re.compile(r"\\href\s*\{[^{}]*\}\s*\{([^{}]*)\}")
_LATEX_TIMES_RE = re.compile(r"\\(?:text)?times(?![A-Za-z])")
#: A generic ``\command{...}`` whose (single-level) argument survives.
_LATEX_CMD_BRACE_RE = re.compile(r"\\[A-Za-z@]+\*?\s*\{([^{}]*)\}")
#: A bare ``\command`` with no argument — dropped entirely.
_LATEX_BARE_CMD_RE = re.compile(r"\\[A-Za-z@]+\*?")
_LATEX_LINEBREAK_RE = re.compile(r"\\\\")
#: Bounds the generic reduce loop: a document nested deeper than this keeps its
#: outer braces rather than scanning without limit (the BOUNDED-importer posture,
#: ``app/cv/import_tex.py``'s module docstring).
_LATEX_REDUCE_PASSES = 12


def _math_spacing(match: re.Match[str]) -> str:
    """``\\!`` (negative space) vanishes; every other thin/medium space becomes one."""
    return "" if match.group(0) == r"\!" else " "


def _normalise_latex(source: str) -> str:
    """A render-ish plain-text view of ``source``, for grounding only.

    The model returns what the document RENDERS to, so a value proved by the markup
    (``\\&`` for ``&``, ``\\texttimes`` for ``×``, an ``\\href`` label, or a math-mode
    pipe) is not a literal substring of the raw source. This reduces the markup to the
    rendered text so the guard can compare against what a reader would see. It is a
    bounded, single-purpose reduction — NOT a LaTeX parser:

    - ``%`` comments are stripped to end-of-line (an escaped ``\\%`` survives);
    - ``\\href{URL}{LABEL}`` becomes ``LABEL`` before any generic handling;
    - ``\\texttimes`` / ``\\times`` become ``×``;
    - math mode: a math shift ``$`` is removed, ``\\vert``/``\\mid``/``\\lvert``/
      ``\\rvert``/``\\Vert``/``\\|``/``\\textbar`` become a literal ``|``, and
      ``\\,``/``\\;``/``\\:``/``\\quad``/``\\qquad`` become a space (``\\!`` nothing);
    - ``\\&``/``\\%``/``\\_``/``\\#`` decode to their character and ``\\$`` to ``$``;
    - a generic ``\\command{...}`` keeps its argument, a bare ``\\command`` is dropped,
      and remaining ``{``/``}`` grouping is removed (nesting handled iteratively,
      bounded by :data:`_LATEX_REDUCE_PASSES`);
    - ``\\`` and ``~`` become spaces, then whitespace is collapsed.

    It never invents text: every surviving character came from the source, and the
    resulting view is only ever used as a SUBSTRING target, never as stored content.
    """
    text = _LATEX_COMMENT_RE.sub("", source)
    text = _LATEX_HREF_RE.sub(r"\1", text)
    text = _LATEX_TIMES_RE.sub(_MULTIPLICATION_CANONICAL, text)
    # Math mode. A bar command must be MAPPED (not merely stripped): the generic rule
    # drops a bare ``\command``, which would delete the separator and still fail.
    text = _LATEX_MATH_BAR_RE.sub("|", text)
    text = text.replace(r"\|", "|")
    text = _LATEX_MATH_SPACING_RE.sub(_math_spacing, text)
    # A math shift `$` is markup; an escaped `\$` is a literal, parked first.
    text = text.replace(r"\$", _DOLLAR_SENTINEL)
    text = text.replace("$", "")
    for markup, plain in _LATEX_ESCAPE_DECODE:
        text = text.replace(markup, plain)
    text = text.replace(r"\{", _LBRACE_SENTINEL)
    text = text.replace(r"\}", _RBRACE_SENTINEL)

    for _ in range(_LATEX_REDUCE_PASSES):
        reduced = _LATEX_CMD_BRACE_RE.sub(r"\1", text)
        reduced = _LATEX_BARE_CMD_RE.sub("", reduced)
        reduced = reduced.replace("{", "").replace("}", "")
        if reduced == text:
            break
        text = reduced

    text = text.replace(_LBRACE_SENTINEL, "{")
    text = text.replace(_RBRACE_SENTINEL, "}")
    text = text.replace(_DOLLAR_SENTINEL, "$")
    text = _LATEX_LINEBREAK_RE.sub(" ", text)
    text = text.replace("~", " ")
    return _WHITESPACE_RE.sub(" ", text).strip()


def _appears(grounded_source: str, rendered_source: str, value: str | None) -> bool:
    """True when ``value`` appears verbatim in EITHER source view.

    ``grounded_source`` is the raw source; ``rendered_source`` is
    :func:`_normalise_latex` reduced first. Both are already casefolded and
    whitespace-collapsed. Passing on either is still document-traceability — the
    value must exist in the document's markup or its rendered form — so this is
    strictly more permissive than the raw-only test without weakening the
    guarantee. A falsy value is still ``False``: a blank org/title must drop.
    """
    if not value:
        return False
    needle = _normalise(value)
    return needle in grounded_source or needle in rendered_source


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


# ---------------------------------------------------------------------------
# wire parsing: the model returns JSON text inside one string field
# ---------------------------------------------------------------------------

_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _strip_code_fence(text: str) -> str:
    """Remove a surrounding markdown code fence, if present."""
    match = _JSON_FENCE_RE.match(text)
    return match.group(1) if match is not None else text.strip()


def _outermost_json_object(text: str) -> str | None:
    """The first balanced ``{...}`` span, respecting braces inside JSON strings."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _loads_cv_json(raw: str) -> object:
    """Parse the model's JSON string, tolerating a fence or surrounding prose."""
    candidate = _strip_code_fence(raw)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    outer = _outermost_json_object(candidate)
    if outer is not None:
        try:
            return json.loads(outer)
        except json.JSONDecodeError:
            pass
    raise ExtractionError("the model's cv_json field was not valid JSON")


def _string_or_none(value: object) -> str | None:
    """A scalar rendered as a string; ``None`` for null/containers."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return None
    return str(value)


def _string_list(value: object) -> list[str]:
    """Coerce whatever shape the model produced into a list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        items = value
    elif isinstance(value, dict):
        items = list(value.values())
    else:
        items = [value]
    out: list[str] = []
    for item in items:
        if item is None:
            continue
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str):
                out.append(text)
        else:
            out.append(str(item))
    return out


def _normalise_skills(value: object) -> list[dict[str, str]]:
    """Coerce whatever skill shape the model produced into ``{label, group}`` dicts.

    Accepts a list (or single value) of bare label strings and/or ``{label, group}``
    objects. A missing or empty group defaults to :data:`DEFAULT_SKILL_GROUP`; the
    grounding guard in :func:`_to_facts_dict` decides what survives. An item with no
    usable ``label`` is dropped here — it names nothing.
    """
    if value is None:
        return []
    if isinstance(value, (str, dict)):
        items: list[object] = [value]
    elif isinstance(value, list):
        items = list(value)
    else:
        items = [value]
    out: list[dict[str, str]] = []
    for item in items:
        if isinstance(item, str):
            if item.strip():
                out.append({"label": item, "group": DEFAULT_SKILL_GROUP})
        elif isinstance(item, dict):
            label = item.get("label")
            if not isinstance(label, str):
                continue
            group = item.get("group")
            out.append(
                {
                    "label": label,
                    "group": group
                    if isinstance(group, str) and group
                    else DEFAULT_SKILL_GROUP,
                }
            )
    return out


def _normalise_entry(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "org": _string_or_none(item.get("org")) or "",
        "title": _string_or_none(item.get("title")) or "",
        "dates": _string_or_none(item.get("dates")) or "",
        "location": _string_or_none(item.get("location")),
        "bullets": _string_list(item.get("bullets")),
    }


def _normalise_entries(value: object) -> list[dict[str, Any]]:
    """A list of entry objects, tolerating ``""``/null/dict-by-key/one scalar."""
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    elif isinstance(value, dict):
        items = list(value.values())
    else:
        items = [value]
    out: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            out.append(_normalise_entry(item))
    return out


def _normalise_sections(value: object) -> list[dict[str, Any]]:
    """Sections as a list, or a dict keyed by heading (the key becomes ``heading``)."""
    if value is None:
        return []
    if isinstance(value, list):
        items: list[tuple[str | None, object]] = [(None, item) for item in value]
    elif isinstance(value, dict):
        items = list(value.items())
    else:
        items = [(None, value)]
    out: list[dict[str, Any]] = []
    for key, item in items:
        if not isinstance(item, dict):
            continue
        heading = item.get("heading")
        if not isinstance(heading, str) or not heading.strip():
            heading = key or ""
        out.append(
            {
                "heading": heading,
                "entries": _normalise_entries(item.get("entries")),
                "skills": _normalise_skills(item.get("skills")),
            }
        )
    return out


def _normalise_meta(value: object) -> dict[str, Any]:
    meta = value if isinstance(value, dict) else {}
    return {
        "name": _string_or_none(meta.get("name")),
        "email": _string_or_none(meta.get("email")),
        "phone": _string_or_none(meta.get("phone")),
        "location": _string_or_none(meta.get("location")),
        "links": _string_list(meta.get("links")),
    }


def _parse_extraction(raw_json: str) -> _ExtractedCv:
    """Parse + normalise the model's JSON string into the existing wire model.

    Any parse or validation failure is an :class:`ExtractionError`, never a bare
    exception. The normalisation only reshapes container types; it never invents a
    value, and the grounding guard still decides what reaches the store.
    """
    payload = _loads_cv_json(raw_json)
    if not isinstance(payload, dict):
        raise ExtractionError("the model's extracted CV was not a JSON object")
    normalised = {
        "meta": _normalise_meta(payload.get("meta")),
        "sections": _normalise_sections(payload.get("sections")),
    }
    try:
        return _ExtractedCv.model_validate(normalised)
    except ValidationError as exc:
        raise ExtractionError(
            f"the model's extracted CV did not match the expected shape: {exc}"
        ) from exc


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
    rendered = _normalise(_normalise_latex(tex_source))
    drops: list[str] = []

    # (e) meta. Every field is grounded the same way; nothing is invented.
    meta: dict[str, Any] = {"max_pages": 2}
    if extracted.meta.name:
        if _appears(grounded, rendered, extracted.meta.name):
            meta["name"] = extracted.meta.name
        else:
            drops.append(
                f"dropped meta.name {extracted.meta.name!r}: not found in the document"
            )
    if extracted.meta.location:
        if _appears(grounded, rendered, extracted.meta.location):
            meta["location"] = extracted.meta.location
        else:
            drops.append(
                f"dropped meta.location {extracted.meta.location!r}: "
                "not found in the document"
            )

    contact: dict[str, Any] = {}
    for field in ("email", "phone"):
        value = getattr(extracted.meta, field)
        if not value:
            continue
        if _appears(grounded, rendered, value):
            contact[field] = value
        else:
            drops.append(f"dropped meta.{field} {value!r}: not found in the document")
    links: list[str] = []
    for link in extracted.meta.links:
        if _appears(grounded, rendered, link):
            links.append(link)
        else:
            drops.append(f"dropped meta link {link!r}: not found in the document")
    if links:
        contact["links"] = links
    if contact:
        meta["contact"] = contact

    # (a) heading -> key, preserving first-seen document order; duplicate headings
    # mapping to the same key merge into one section.
    key_order: list[str] = []
    entries_by_key: dict[str, list[dict[str, Any]]] = {}
    skills_by_key: dict[str, list[dict[str, str]]] = {}
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
            # (b) grounding guard — org AND title must each be present in the raw
            # or rendered source. `_appears` keeps falsy->False, so an EMPTY org or
            # title still fails; the drop message NAMES the failing field(s) and
            # says explicitly when a field was left empty, so a report is
            # self-diagnosing.
            unmatched: list[str] = []
            if not entry.org or not entry.org.strip():
                unmatched.append(
                    "org was empty (no employer, institution or project named)"
                )
            elif not _appears(grounded, rendered, entry.org):
                unmatched.append(f"org {entry.org!r} not found in the document")
            if not entry.title or not entry.title.strip():
                unmatched.append("title was empty")
            elif not _appears(grounded, rendered, entry.title):
                unmatched.append(f"title {entry.title!r} not found in the document")
            if unmatched:
                drops.append(f"dropped entry: {', '.join(unmatched)}")
                continue
            # (c) dates — delegate to the importer's machinery plus the bare-year wrap.
            dates = _parse_dates(entry.dates)
            if dates is None:
                drops.append(
                    f"dropped entry {entry.org!r} — {entry.title!r}: "
                    f"unparseable dates {entry.dates!r}"
                )
                continue
            start, end, dates_location = dates

            # (c') location. `_ExtractedEntry.location` was previously DEAD here: the
            # schema and the prompt example carried it, but the compile never read it,
            # so a document with org and location in separate arguments (awesome-cv's
            # `\cventry` shape) left the model no field for the location and it glued
            # `org + ", " + location` instead — an invented string the guard then
            # (correctly) rejected. Prefer the model's own location, grounded exactly
            # like org/title. `Entry.location` is optional and not identity-bearing:
            # an ungrounded location is reported and the dates-suffix fallback applies,
            # NEVER a reason to drop the entry.
            location = dates_location
            if entry.location and entry.location.strip():
                if _appears(grounded, rendered, entry.location):
                    location = entry.location
                else:
                    drops.append(
                        f"dropped entry.location {entry.location!r}: "
                        "not found in the document"
                    )

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

        for skill in section.skills:
            label = skill.label
            if not (label and label.strip()):
                continue
            if any(existing["label"] == label for existing in skills_by_key[key]):
                continue
            # Ground the group exactly like org/title: a group the document does not
            # contain is dropped and reported, and the honest default takes its place.
            # The default itself is not a model claim, so it is never "dropped".
            group = skill.group
            if group != DEFAULT_SKILL_GROUP and not _appears(grounded, rendered, group):
                drops.append(
                    f"dropped skill.group {group!r} for skill {label!r}: "
                    "not found in the document"
                )
                group = DEFAULT_SKILL_GROUP
            skills_by_key[key].append({"label": label, "group": group})

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

    # (e) sections in document order. Each skill carries the document-grounded group
    # the extractor attached (an ungrounded group is dropped and replaced by the one
    # honest default) plus the neutral weight 1.0.
    sections: list[dict[str, Any]] = []
    seen_skill_ids: set[str] = set()
    for index, key in enumerate(key_order):
        entries = entries_by_key[key]
        skills: list[dict[str, Any]] = []
        for skill in skills_by_key[key]:
            label = skill["label"]
            skill_id = f"skill.{slugify(label)}"
            if skill_id in seen_skill_ids:
                drops.append(f"dropped duplicate skill {label!r}")
                continue
            seen_skill_ids.add(skill_id)
            skills.append(
                {"id": skill_id, "label": label, "group": skill["group"], "weight": 1.0}
            )
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
            schema=_ExtractedEnvelope,
            system=CV_EXTRACT_SYSTEM_PROMPT,
            parts=[tex_source],
            model=settings.opencode_model,
            tools=(),
            retries=settings.opencode_max_retries,
        )
    except Exception as exc:  # noqa: BLE001 — a raised transport error is a value here
        raise ExtractionError(f"the extraction call failed: {type(exc).__name__}") from exc

    if not result.ok or not isinstance(result.data, _ExtractedEnvelope):
        raise ExtractionError(
            "the extraction call did not return a usable CV"
            f" ({result.error or result.status})"
        )

    extracted = _parse_extraction(result.data.cv_json)
    try:
        facts, report = _to_facts_dict(extracted, tex_source, now)
    except ExtractionError:
        raise
    except ValidationError as exc:
        raise ExtractionError(f"the compiled fact store did not validate: {exc}") from exc
    return ExtractionResult(facts=facts, report=report)
