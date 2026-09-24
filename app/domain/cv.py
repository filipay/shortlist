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

import hashlib
import re
import unicodedata
from collections.abc import Iterator
from typing import Annotated, Literal

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
#
# ``extra="forbid"`` (pinned A4) deliberately diverges from ``RankingResponse``'s
# ``extra="ignore"``: ``forbid`` emits ``additionalProperties: false`` into
# ``model_json_schema()`` and so constrains the model AT THE WIRE — the stronger
# fabrication-safety posture. A malformed extra key must fail the call (bounded
# retry), never be silently dropped from a stored contract.
#
# NO field on any op becomes text in the PDF. Every field is an enumerated id, a
# closed enum, a bounded number, or UI/audit-only text (``reason``,
# ``requirement``, ``rationale``). The renderer consumes only a ``RenderPlan``,
# whose strings all derive from the fact store.


class BulletMove(_Forbid):
    """Move a bullet within its entry. ``before_id=None`` means first."""

    op: Literal["move_bullet"] = "move_bullet"
    bullet_id: str
    #: The bullet it is placed before within the SAME entry, or ``None`` for the
    #: first position. A ``before_id`` resolving into another entry is an
    #: ``InvalidPatchError`` (A5, locked): a cross-entry move would silently change
    #: the facts an entry states.
    before_id: str | None = None


class BulletWeight(_Forbid):
    """Re-weight a bullet within its entry. The weight is never printed."""

    op: Literal["reweight_bullet"] = "reweight_bullet"
    bullet_id: str
    weight: Annotated[float, Field(ge=0.0, le=2.0)]


class DemoteBullet(_Forbid):
    """Demote a bullet to the lowest prominence in its entry (D-104).

    ``reason`` is REQUIRED and non-empty (``min_length=1``), so a demotion cannot be
    recorded without a stated cause. The reason is audit/UI-only and never rendered.
    """

    op: Literal["demote_bullet"] = "demote_bullet"
    bullet_id: str
    reason: Annotated[str, Field(min_length=1)]


class DropBullet(_Forbid):
    """Drop a bullet. The reason is REQUIRED and non-empty so a drop is loud."""

    op: Literal["drop_bullet"] = "drop_bullet"
    bullet_id: str
    reason: Annotated[str, Field(min_length=1)]


class ReorderSection(_Forbid):
    """Re-order a section. Ties keep declaration order (mirrors ``ordered_sections``)."""

    op: Literal["reorder_section"] = "reorder_section"
    section_id: str
    order: int


class Suggestion(_Forbid):
    """A human-approved suggestion. NEVER applied to a render.

    Keeping it out of the applied path is what keeps free-text suggestion content
    off the road to the PDF.
    """

    bullet_id: str
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str


class GapFinding(_Forbid):
    """One requirement the listing states and the CV's honest relationship to it.

    ``requirement`` is UI/audit-only and NEVER reaches a render. ``status`` is a
    closed enum; a non-``gap`` finding must name the real facts that support it (the
    structural half of Layer-1 check 6), and a ``gap`` must not.
    """

    requirement: str
    status: Literal["direct", "transferable", "adjacent", "gap"] = "gap"
    evidence_ids: list[str] = Field(default_factory=list)


#: The patch operation union, discriminated on ``op``. New operations are added by
#: adding a member here and a branch in ``_build_plan`` — never by widening an
#: existing member with a field that becomes PDF text.
PatchOp = Annotated[
    BulletMove | BulletWeight | DemoteBullet | DropBullet | ReorderSection,
    Field(discriminator="op"),
]


class TailoringPatch(_Forbid):
    """The typed tailoring patch: an operation set over enumerated fact IDs.

    Carries NO free-text field that can become PDF text. ``ops`` reorder, re-weight,
    demote, drop and re-order EXISTING facts; ``gaps`` and ``suggestions`` are
    UI/audit-only. ``listing_id`` binds the patch to the listing it was generated
    for. An empty patch (all three lists empty) is valid and is the identity plan.
    """

    listing_id: int
    ops: list[PatchOp] = Field(default_factory=list)
    gaps: list[GapFinding] = Field(default_factory=list)
    suggestions: list[Suggestion] = Field(default_factory=list)


class UnknownIdError(Exception):
    """A patch operation references an ID the fact store does not carry."""


class InvalidPatchError(Exception):
    """A patch is structurally invalid (duplicate target, emptied section, cross-entry move)."""


def _referenced_ids(op: object) -> list[str]:
    """Every fact ID an operation names, whatever its shape.

    ``before_id`` is included: it names a bullet and must be grounded exactly like
    ``bullet_id``. A ``None`` ``before_id`` is skipped (it is not a string).
    """
    ids: list[str] = []
    for attribute in (
        "bullet_id",
        "section_id",
        "entry_id",
        "org_id",
        "title_id",
        "before_id",
    ):
        value = getattr(op, attribute, None)
        if isinstance(value, str):
            ids.append(value)
    evidence_ids = getattr(op, "evidence_ids", None)
    if isinstance(evidence_ids, list):
        ids.extend(item for item in evidence_ids if isinstance(item, str))
    return ids


def facts_hash(facts: CvFacts) -> str:
    """The SEMANTIC hash of a fact store: sha256 over its canonical JSON.

    ``hashlib`` is stdlib, so the ``app/domain`` purity contract holds. The hash is
    semantic because it is taken over the VALIDATED model, not the raw file: a
    whitespace-only ``cv.yaml`` edit cannot invalidate a patch.
    """
    return hashlib.sha256(facts.model_dump_json().encode("utf-8")).hexdigest()


class GuardResult(_Forbid):
    """The optimistic-concurrency guard's outcome — a value, never an exception."""

    ok: bool
    reason: str | None = None


def verify_original_matches(
    facts: CvFacts,
    *,
    captured_hash: str | None,
    captured_version_id: int | None,
    current_version_id: int | None,
) -> GuardResult:
    """D-109's guard: has the fact store moved since the patch was captured?

    Returns a value that NAMES which check failed rather than raising, so the route
    can render the stale-patch fragment. The fact-store check runs first: a changed
    store invalidates the patch regardless of which revision it was captured against.
    """
    if facts_hash(facts) != captured_hash:
        return GuardResult(ok=False, reason="fact_store_changed")
    if current_version_id != captured_version_id:
        return GuardResult(ok=False, reason="cv_version_changed")
    return GuardResult(ok=True)


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


def _patch_is_empty(patch: TailoringPatch) -> bool:
    """An empty patch is the identity plan — never an error, never an invented change."""
    return not patch.ops and not patch.gaps and not patch.suggestions


def _validate_patch(facts: CvFacts, patch: TailoringPatch) -> None:
    """All-or-nothing validation (D-106): raise on the FIRST violation, never repair.

    IDs are compared BYTE-EXACT against the grounding set of the op's own family — a
    bullet-targeting op resolves against the bullet-id set, a gap/suggestion
    reference against the full fact-id set. No casefold, no Unicode normalisation,
    no fuzzy ratio. The ASCII slug ids ARE the identity. Grounding a bullet op
    against the full fact-id set would let a skill/section/entry/org/title/gap id
    validate, no-op in ``_build_plan`` and still emit a ``ChangeRecord`` — the
    phantom change WR-02.
    """
    known_ids = set(iter_fact_ids(facts))
    #: A bullet-targeting op must resolve against the bullet-id set, not the full
    #: fact-id set (WR-02).
    bullet_ids = {bullet.id for entry in facts.all_entries() for bullet in entry.bullets}

    # 1. Unknown id — per op family, against that family's own id set. A bullet op
    #    must not be satisfied by an id of another kind.
    for op in patch.ops:
        if isinstance(op, (BulletMove, BulletWeight, DemoteBullet, DropBullet)):
            grounding = bullet_ids
        else:
            grounding = known_ids
        for referenced in sorted(set(_referenced_ids(op))):
            if referenced not in grounding:
                raise UnknownIdError(
                    f"patch operation references unknown id {referenced!r}: {op!r}"
                )
    for gap in patch.gaps:
        for referenced in gap.evidence_ids:
            if referenced not in known_ids:
                raise UnknownIdError(
                    f"gap finding references unknown evidence id {referenced!r}"
                )
    for suggestion in patch.suggestions:
        for referenced in _referenced_ids(suggestion):
            if referenced not in known_ids:
                raise UnknownIdError(
                    f"suggestion references unknown id {referenced!r}: {suggestion!r}"
                )

    # 2. Duplicate target — no bullet_id/section_id named by two mutating ops. A
    #    reweight + a demote on the same bullet is a conflict, not a silent merge.
    seen_bullets: set[str] = set()
    seen_sections: set[str] = set()
    for op in patch.ops:
        bullet_id = getattr(op, "bullet_id", None)
        if isinstance(bullet_id, str):
            if bullet_id in seen_bullets:
                raise InvalidPatchError(f"two operations target bullet {bullet_id!r}")
            seen_bullets.add(bullet_id)
        section_id = getattr(op, "section_id", None)
        if isinstance(section_id, str):
            if section_id in seen_sections:
                raise InvalidPatchError(f"two operations target section {section_id!r}")
            seen_sections.add(section_id)

    # 3. Cross-entry move (A5, locked): a move_bullet whose before_id resolves into a
    #    different entry than its bullet_id is rejected rather than re-ordered.
    entry_of_bullet = {
        bullet.id: entry.id
        for entry in facts.all_entries()
        for bullet in entry.bullets
    }
    for op in patch.ops:
        if isinstance(op, BulletMove) and op.before_id is not None:
            source = entry_of_bullet.get(op.bullet_id)
            destination = entry_of_bullet.get(op.before_id)
            if source is not None and destination is not None and source != destination:
                raise InvalidPatchError(
                    f"move_bullet {op.bullet_id!r} before {op.before_id!r} crosses "
                    f"entries ({source!r} != {destination!r})"
                )

    # 4. A drop/demote without a reason is IMPOSSIBLE by type (`min_length=1`), so the
    #    invariant is asserted here rather than re-checked.
    # 5. A section losing all its entries is checked against the BUILT plan below.
    #    Dropping an entry is not a supported op, so it can only fire via a future
    #    op — the guard is kept so the invariant is enforced where it is decided.


def _ordered_bullets(
    entry: Entry,
    *,
    weights: dict[str, float],
    demoted: set[str],
    dropped: set[str],
    moves: list[tuple[str, str | None]],
) -> list[Bullet]:
    """The bullets of one entry, dropped-filtered and ordered (D-103/D-104).

    Every returned ``Bullet`` is a carried-through source object: this never rebuilds
    ``Bullet.text``, it only re-sequences.
    """
    survivors = [bullet for bullet in entry.bullets if bullet.id not in dropped]
    # Base within-entry order: declaration order, stable-sorted by reweight weight
    # DESCENDING. A bullet with no reweight keeps the neutral default 1.0 (the same
    # default `Skill.weight` uses), so an unreweighted bullet sits between one
    # reweighted up and one reweighted down; ties keep declaration order.
    ordered = sorted(survivors, key=lambda bullet: weights.get(bullet.id, 1.0), reverse=True)

    # Demote (D-104): every demoted bullet falls after every non-demoted bullet of
    # its OWN entry, and the demoted bullets keep DECLARATION order among themselves.
    if demoted:
        promoted = [bullet for bullet in ordered if bullet.id not in demoted]
        tail = [
            bullet
            for bullet in entry.bullets
            if bullet.id in demoted and bullet.id not in dropped
        ]
        ordered = promoted + tail

    # Moves are the explicit positional override, applied AFTER base ordering, in
    # patch order. A move for a bullet in another entry is skipped here (validation
    # already rejected a cross-entry destination).
    for bullet_id, before_id in moves:
        if before_id == bullet_id:
            continue  # a move before itself is a no-op
        moving = next((bullet for bullet in ordered if bullet.id == bullet_id), None)
        if moving is None:
            continue
        ordered = [bullet for bullet in ordered if bullet.id != bullet_id]
        if before_id is None:
            ordered.insert(0, moving)
        else:
            index = next(
                (i for i, bullet in enumerate(ordered) if bullet.id == before_id),
                len(ordered),
            )
            ordered.insert(index, moving)
    return ordered


def _change_for(op: PatchOp) -> ChangeRecord:
    """One ChangeRecord per applied op — the change log D-108/TAIL-08 persists.

    ``detail`` carries the model's reason for a drop/demote, the weight for a
    reweight, the destination for a move and the new order for a section reorder.
    It is audit/UI-only and is never rendered.
    """
    if isinstance(op, (DropBullet, DemoteBullet)):
        return ChangeRecord(op=op.op, target_id=op.bullet_id, detail=op.reason)
    if isinstance(op, BulletWeight):
        return ChangeRecord(op=op.op, target_id=op.bullet_id, detail=f"{op.weight}")
    if isinstance(op, BulletMove):
        return ChangeRecord(op=op.op, target_id=op.bullet_id, detail=op.before_id or "first")
    return ChangeRecord(op=op.op, target_id=op.section_id, detail=str(op.order))


def _build_plan(facts: CvFacts, patch: TailoringPatch) -> RenderPlan:
    """Project ``facts`` through the validated ``patch``. Pure and deterministic."""
    weights = {op.bullet_id: op.weight for op in patch.ops if isinstance(op, BulletWeight)}
    demoted = {op.bullet_id for op in patch.ops if isinstance(op, DemoteBullet)}
    dropped = {op.bullet_id for op in patch.ops if isinstance(op, DropBullet)}
    moves = [
        (op.bullet_id, op.before_id) for op in patch.ops if isinstance(op, BulletMove)
    ]
    section_orders = {
        op.section_id: op.order for op in patch.ops if isinstance(op, ReorderSection)
    }

    org_names = {org.id: org.name for org in facts.orgs}
    title_names = {title.id: title.name for title in facts.titles}

    # Sections stable-sorted by the effective order (a reorder overrides the stored
    # order); declaration order is the tie-break, mirroring `CvFacts.ordered_sections`.
    sections: list[RenderedSection] = []
    for section in sorted(
        facts.sections, key=lambda item: section_orders.get(item.id, item.order)
    ):
        entries = [
            RenderedEntry(
                id=entry.id,
                org=org_names.get(entry.org_id, entry.org_id),
                title=title_names.get(entry.title_id, entry.title_id),
                dates=entry.date_range_label,
                location=entry.location,
                bullets=_ordered_bullets(
                    entry,
                    weights=weights,
                    demoted=demoted,
                    dropped=dropped,
                    moves=moves,
                ),
            )
            for entry in section.entries
        ]
        if section.entries and not entries:  # pragma: no cover — see _validate_patch
            raise InvalidPatchError(f"section {section.id!r} lost all its entries")
        sections.append(
            RenderedSection(
                id=section.id,
                title=section.resolved_title,
                entries=entries,
                skills=list(section.skills),
            )
        )

    contact = facts.meta.contact
    return RenderPlan(
        sections=sections,
        changes=[_change_for(op) for op in patch.ops],
        name=facts.meta.name,
        contact_email=contact.email if contact else None,
        contact_links=list(contact.links) if contact else [],
    )


def apply_patch(facts: CvFacts, patch: TailoringPatch | None = None) -> RenderPlan:
    """Project ``facts`` to a :class:`RenderPlan`, applying the typed ``patch``.

    ``patch=None`` (and an empty patch) returns the identity plan with an empty
    ``changes`` list, so the shipped no-argument callers keep their exact behaviour.

    Every ID the patch names must exist in the fact store, every validation is
    all-or-nothing (D-106), and every emitted ``Bullet`` is a carried-through source
    object: ``Bullet.text`` is never rebuilt.
    """
    if patch is None or _patch_is_empty(patch):
        return _identity_plan(facts)
    _validate_patch(facts, patch)
    return _build_plan(facts, patch)


__all__ = [
    "SECTION_TITLES",
    "SCHEMA_VERSION",
    "Bullet",
    "BulletMove",
    "BulletWeight",
    "ChangeRecord",
    "Contact",
    "CvFacts",
    "DemoteBullet",
    "DropBullet",
    "Entry",
    "Gap",
    "GapFinding",
    "GuardResult",
    "InvalidPatchError",
    "Meta",
    "Org",
    "PatchOp",
    "RenderPlan",
    "RenderedEntry",
    "RenderedSection",
    "ReorderSection",
    "Section",
    "Skill",
    "Suggestion",
    "TailoringPatch",
    "Title",
    "UnknownIdError",
    "apply_patch",
    "derive_bullet_id",
    "derive_entry_id",
    "facts_hash",
    "find_duplicate_ids",
    "iter_fact_ids",
    "qualify_entry_ids",
    "slugify",
    "verify_original_matches",
]
