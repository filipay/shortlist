"""The machine-canonical CV document: models, stable IDs, and the render projection.

**Purity.** This module imports the standard library plus ``pydantic`` only. No
``yaml``, no ``jinja2``, no filesystem, no clock. ``app/cv/factstore.py`` is the
single reader of ``cv.yaml``; this module is what makes the value it returns
representable and addressable.

**"Source of truth" is never used unqualified** (ARCHITECTURE §0 A1).
``cv/base.tex`` is canonical *for the human*; ``cv.yaml`` is canonical *for the
machine*; a rendered ``.tex`` is a derivative.

**Citation correction.** The researched ``cv.yaml`` shape this module implements
lives in ``ARCHITECTURE.md §7.2`` ("Decomposition"). ``§7.3`` is the *patch* the
LLM returns. An earlier draft of this phase plan cited §7.3 for the shape; the
shape is §7.2.

**C-1 clarifications this module is written to.** 7.2 is adopted as written, which
settles three things:

- ``meta`` carries ``name``, a ``contact`` block and ``max_pages``.
- ``sections`` is a list of id-bearing items carrying ``title_key`` and ``order``
  plus the ``entries``/``skills`` alternation — a section may carry either or both.
- ``orgs`` and ``titles`` are enumerations **carried in the document**, and
  ``gaps`` is a separate collection (unmet requirements never live in bullets).

``title_key`` is the *section-heading field*: it resolves through the closed
code-side map :data:`SECTION_TITLES`, and is never stored as free text. The
earlier draft's preference for a resolved ``title`` string is superseded by C-1;
:attr:`Section.resolved_title` is now an accessor rather than a stored field.

**Two deliberate spelling deviations from 7.2**, recorded here rather than left
silent, because in each case 7.2 names a resolver the document does not carry:

- ``meta.contact`` stores the **actual** values (``email``/``phone``/``links``)
  rather than 7.2's ``email_id``/``phone_id``. 7.2 enumerates ``orgs`` and
  ``titles`` but carries no ``contacts`` collection, so an id would have nothing
  to resolve against and the rendered CV could show no address at all. The
  property that matters — an employer or a title cannot be invented, because it
  must name an enumerated entry — is preserved exactly where it is real.
- :class:`Skill` stores the **display label** rather than 7.2's ``label_key``.
  Skills are an open set, so a code-side key map would need a new source entry per
  technology while buying nothing in a single-locale v1. Section titles are the
  opposite case and **do** use the key form.

Both deviations are reversible behind a ``schema_version`` bump.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Iterator
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

#: The fact-store format version. The YAML value is the int ``1``; the revision
#: column that stores it (``cv_versions.schema_version``) is ``String(32)``, so the
#: two representations must never be compared directly.
SCHEMA_VERSION = 1

#: The closed map from a section ``title_key`` to its display heading. A heading
#: that silently fell back to its own key would put an unvetted string into the
#: document, so an unknown key is a loud validation error at load, never a render.
SECTION_TITLES: dict[str, str] = {
    "sec.experience": "Experience",
    "sec.skills": "Skills",
}


class _Forbid(BaseModel):
    """Every contract type forbids extras.

    On these models ``extra="forbid"`` is also a **correctness control**: a typo'd
    key in a human-edited ``cv.yaml`` must fail, not be silently dropped, or a fact
    disappears without a word.
    """

    model_config = ConfigDict(extra="forbid")


class Bullet(_Forbid):
    """One bullet. ``text`` is the IMMUTABLE source string."""

    id: str
    #: IMMUTABLE. The patch engine may reorder, re-weight, demote and drop a
    #: bullet; it can never rewrite this string (ARCHITECTURE §7.2 property 2).
    text: str
    #: verbatim | grounded | unrecorded
    evidence: str = "unrecorded"
    metrics: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class Entry(_Forbid):
    """One experience entry inside a section."""

    id: str
    #: An enumerated employer or title must name a real :class:`Org`/:class:`Title`
    #: — a fabricated employer is unrepresentable, not merely discouraged.
    org_id: str
    title_id: str
    #: ``"YYYY-MM"``.
    start: str
    #: ``None`` means *present*. There is deliberately NO default that fills a
    #: date: a missing date quietly supplied by a default is invented CV content
    #: (D-66).
    end: str | None = None
    location: str | None = None
    bullets: list[Bullet]

    @property
    def date_range_label(self) -> str:
        """The human-readable date range the renderer and comparison both use."""
        if self.end:
            return f"{self.start} -- {self.end}"
        return f"{self.start} -- present"


class Skill(_Forbid):
    """One skill. Stored by its display ``label`` (see the module docstring)."""

    id: str
    label: str
    group: str
    #: Bounded the way a bullet weight is: a weight outside 0.0-2.0 is a mistake.
    weight: Annotated[float, Field(ge=0.0, le=2.0)] = 1.0


class Section(_Forbid):
    """One section. A section may carry ``entries``, ``skills``, or both."""

    id: str
    title_key: str
    order: int
    entries: list[Entry] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)

    @field_validator("title_key")
    @classmethod
    def _title_key_is_known(cls, value: str) -> str:
        if value not in SECTION_TITLES:
            raise ValueError(
                f"unknown section title_key {value!r};"
                f" known keys: {sorted(SECTION_TITLES)}"
            )
        return value

    @property
    def resolved_title(self) -> str:
        """The display heading for this section's ``title_key``."""
        return SECTION_TITLES[self.title_key]


class Contact(_Forbid):
    """The contact block. Every field is optional — a CV without a phone number
    is not a load failure."""

    email: str | None = None
    phone: str | None = None
    links: list[str] = Field(default_factory=list)


class Meta(_Forbid):
    name: str | None = None
    contact: Contact | None = None
    #: THIS IS the PLAT-04 configuration surface for the page budget (CV-R3). It
    #: lives here as *data*, not as a second `Settings` field, because two sources
    #: for one limit is a defect.
    max_pages: int = 2


class Org(_Forbid):
    """An enumerated employer."""

    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)


class Title(_Forbid):
    """An enumerated job title."""

    id: str
    name: str


class Gap(_Forbid):
    """An unmet requirement, living in its own collection.

    Gaps never live in bullets: that closes the backdoor where an ATS miss becomes
    an invented bullet (ARCHITECTURE §7.2 property 3).
    """

    id: str
    requirement: str
    status: str = "gap"


class CvFacts(_Forbid):
    """The validated machine-canonical document."""

    schema_version: int
    meta: Meta
    sections: list[Section]
    orgs: list[Org] = Field(default_factory=list)
    titles: list[Title] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)

    def ordered_sections(self) -> list[Section]:
        """Sections in their explicit ``order``; ties keep declaration order."""
        return sorted(self.sections, key=lambda section: section.order)

    def all_entries(self) -> list[Entry]:
        """Every entry, sections in ``order`` and entries in declaration order."""
        return [
            entry
            for section in self.ordered_sections()
            for entry in section.entries
        ]

    def entry_by_id(self, entry_id: str) -> Entry | None:
        """The entry with ``entry_id``, or ``None``. Total — never raises."""
        for entry in self.all_entries():
            if entry.id == entry_id:
                return entry
        return None

    @model_validator(mode="after")
    def _references_resolve(self) -> CvFacts:
        """Every entry's ``org_id``/``title_id`` must name a carried enumeration."""
        org_ids = {org.id for org in self.orgs}
        title_ids = {title.id for title in self.titles}
        for section in self.sections:
            for entry in section.entries:
                if entry.org_id not in org_ids:
                    raise ValueError(
                        f"entry {entry.id!r} names org_id {entry.org_id!r}"
                        f" which is not in `orgs`"
                    )
                if entry.title_id not in title_ids:
                    raise ValueError(
                        f"entry {entry.id!r} names title_id {entry.title_id!r}"
                        f" which is not in `titles`"
                    )
        return self

    @model_validator(mode="after")
    def _ids_are_unique(self) -> CvFacts:
        """An ID appears once, ever (D-63)."""
        duplicates = find_duplicate_ids(self)
        if duplicates:
            raise ValueError(f"duplicate fact id(s): {', '.join(duplicates)}")
        return self


# --- stable IDs (D-63, D-64) --------------------------------------------------

_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Deterministic, locale-free, diacritic-insensitive. No dict/set iteration."""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii").casefold()
    return _SLUG_STRIP_RE.sub("-", ascii_only).strip("-")


def derive_entry_id(org_name: str, start: str) -> str:
    """``exp/<slug>-<start-year>``. Identity fields only — never a title, never a
    bullet's text, so re-running an import on unchanged input yields the same ID
    and editing a bullet cannot rename an entry (Pitfall 7)."""
    year = start[:4]
    return f"exp/{slugify(org_name)}-{year}"


def derive_bullet_id(entry_id: str, index: int) -> str:
    """``bul/<entry-slug>/<index>``.

    The positional suffix is safe *only* because the fact store is frozen:
    reordering is a ``RenderPlan`` concern (D-63), never a ``cv.yaml`` edit, and
    the renderer must never renumber.
    """
    entry_slug = entry_id.split("/", 1)[1]
    return f"bul/{entry_slug}/{index}"


def qualify_entry_ids(entries: list[tuple[str, str]]) -> list[str]:
    """Assign entry IDs with the collision rule, deterministically.

    ``entries`` is a list of ``(org_name, start)`` pairs in **source order**. If
    two entries produce the same ``<slug>-<year>``, the second gains ``-2``, the
    third ``-3``, … The IDs are **returned** so the caller can record collisions
    in the import report rather than hiding them — a silent suffix is a silent ID
    change.
    """
    seen: dict[str, int] = {}
    ids: list[str] = []
    for org_name, start in entries:
        base = derive_entry_id(org_name, start)
        seen[base] = seen.get(base, 0) + 1
        ids.append(base if seen[base] == 1 else f"{base}-{seen[base]}")
    return ids


def iter_fact_ids(facts: CvFacts) -> Iterator[str]:
    """Every ID in the document, in a deterministic order."""
    for section in facts.sections:
        yield section.id
        for entry in section.entries:
            yield entry.id
            for bullet in entry.bullets:
                yield bullet.id
        for skill in section.skills:
            yield skill.id
    for org in facts.orgs:
        yield org.id
    for title in facts.titles:
        yield title.id
    for gap in facts.gaps:
        yield gap.id


def find_duplicate_ids(facts: CvFacts) -> list[str]:
    """The duplicated fact IDs, in first-seen order. Empty when all are unique."""
    seen: set[str] = set()
    duplicates: list[str] = []
    for fact_id in iter_fact_ids(facts):
        if fact_id in seen and fact_id not in duplicates:
            duplicates.append(fact_id)
        seen.add(fact_id)
    return duplicates


# --- the render projection ----------------------------------------------------


class ChangeRecord(_Forbid):
    """One entry in the change log the render plan carries (ARCHITECTURE §7.4)."""

    op: str
    target_id: str
    detail: str = ""


class RenderedEntry(_Forbid):
    """An entry resolved against the enumerations, ready to emit."""

    id: str
    org: str
    title: str
    dates: str
    location: str | None = None
    bullets: list[Bullet] = Field(default_factory=list)


class RenderedSection(_Forbid):
    """A section resolved to its display heading, ready to emit."""

    id: str
    title: str
    entries: list[RenderedEntry] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)


class RenderPlan(_Forbid):
    """A pure ordered projection of the fact store.

    ``sections`` are ordered by :attr:`Section.order` and their entries and bullets
    stay in declaration order. ``changes`` *is* the change log Phase 6 renders —
    the patch is the audit trail, so no separate bookkeeping is needed.
    """

    sections: list[RenderedSection]
    changes: list[ChangeRecord] = Field(default_factory=list)
    #: The identity block, carried on the plan so the renderer needs nothing but a
    #: ``RenderPlan`` (and therefore cannot reach the fact store or a clock).
    name: str | None = None
    contact_email: str | None = None
    contact_links: list[str] = Field(default_factory=list)


# --- the declared patch types (CV-R4/R5/R6, D-65) -----------------------------


class BulletWeight(_Forbid):
    """Re-weight a bullet within its entry."""

    bullet_id: str
    weight: Annotated[float, Field(ge=0.0, le=2.0)]


class DropBullet(_Forbid):
    """Drop a bullet. The reason is REQUIRED so a structural drop is loud."""

    bullet_id: str
    reason: str


class Suggestion(_Forbid):
    """A human-approved suggestion. NEVER applied to a render.

    Keeping it out of the applied path is what keeps free-text suggestion content
    off the road to the PDF.
    """

    bullet_id: str
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str


class UnsupportedPatchOp(Exception):
    """A mutating patch operation this phase deliberately does not implement."""


class UnknownIdError(Exception):
    """A patch operation references an ID the fact store does not carry."""


def _referenced_ids(op: object) -> list[str]:
    """Every fact ID an operation names, whatever its shape."""
    ids: list[str] = []
    for attribute in ("bullet_id", "section_id", "entry_id", "org_id", "title_id"):
        value = getattr(op, attribute, None)
        if isinstance(value, str):
            ids.append(value)
    evidence_ids = getattr(op, "evidence_ids", None)
    if isinstance(evidence_ids, list):
        ids.extend(item for item in evidence_ids if isinstance(item, str))
    return ids


def _identity_plan(facts: CvFacts) -> RenderPlan:
    org_names = {org.id: org.name for org in facts.orgs}
    title_names = {title.id: title.name for title in facts.titles}
    sections = [
        RenderedSection(
            id=section.id,
            title=section.resolved_title,
            entries=[
                RenderedEntry(
                    id=entry.id,
                    org=org_names.get(entry.org_id, entry.org_id),
                    title=title_names.get(entry.title_id, entry.title_id),
                    dates=entry.date_range_label,
                    location=entry.location,
                    bullets=list(entry.bullets),
                )
                for entry in section.entries
            ],
            skills=list(section.skills),
        )
        for section in facts.ordered_sections()
    ]
    contact = facts.meta.contact
    return RenderPlan(
        sections=sections,
        changes=[],
        name=facts.meta.name,
        contact_email=contact.email if contact else None,
        contact_links=list(contact.links) if contact else [],
    )


def apply_patch(facts: CvFacts, ops: Iterable[object] = ()) -> RenderPlan:
    """Project ``facts`` to a :class:`RenderPlan`, applying ``ops``.

    Every ID an operation names must exist in the fact store. Only *identity* and
    ordering are implemented today.

    Silently ignoring a drop or a re-weight would be a fabrication path, so each
    declared mutating operation raises :class:`UnsupportedPatchOp` naming itself.
    That loud refusal is deliberate: Phase 6 replaces it with a real
    implementation rather than this plan guessing one.
    """
    operations = list(ops) if ops is not None else []
    known_ids = set(iter_fact_ids(facts))

    for op in operations:
        for referenced in _referenced_ids(op):
            if referenced not in known_ids:
                raise UnknownIdError(
                    f"patch operation references unknown id {referenced!r}: {op!r}"
                )

    for op in operations:
        raise UnsupportedPatchOp(
            f"{type(op).__name__} is declared but not implemented in this phase;"
            f" a silent no-op would be a fabrication path: {op!r}"
        )

    return _identity_plan(facts)


__all__ = [
    "SECTION_TITLES",
    "SCHEMA_VERSION",
    "Bullet",
    "BulletWeight",
    "ChangeRecord",
    "Contact",
    "CvFacts",
    "DropBullet",
    "Entry",
    "Gap",
    "Meta",
    "Org",
    "RenderPlan",
    "RenderedEntry",
    "RenderedSection",
    "Section",
    "Skill",
    "Suggestion",
    "Title",
    "UnknownIdError",
    "UnsupportedPatchOp",
    "apply_patch",
    "derive_bullet_id",
    "derive_entry_id",
    "find_duplicate_ids",
    "iter_fact_ids",
    "qualify_entry_ids",
    "slugify",
]
