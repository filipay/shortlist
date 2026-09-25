"""The metric tokeniser and the region segmentation for Layer-2 check 4 (D-113).

Pure, total, deterministic and clock-free — the house style of
``app/domain/sanitize.py``: a module-level compiled-regex catalogue, no I/O, no
locale, no NLP.

**Why digit cores, not numbers.** The PDF extractor is lossy (``pypdf`` can drop
spaces and does not expand ligatures), so a tokeniser that insisted on a real
numeric literal would false-fail on a correct document. The token that survives
is the **digit core**: a maximal ``\\d+(?:[.,]\\d+)*`` run with a thousands comma
removed and any decimal comma normalised to ``.``. A plus or percent affix does
not create a new token, ``5-10`` is two cores, and ``50k`` yields ``50`` (the
magnitude suffix is dropped). That tradeoff is deliberate and locked (A2): a
``50k`` claim and a ``50000`` claim are different source strings and must not
match each other.

**Why the region segmentation is line-based, not ``squash``-based.** The locked
assumption A3 needs ``2021-03`` to yield the date cores ``2021`` and ``03`` so
they can be excluded. ``squash`` removes the hyphen and would fuse the whole
date into ``202103``, defeating that exclusion. So an entry's region is located
on the entry's own HEADER line — the line carrying both ``squash(org)`` and
``squash(title)`` that is also gated by the entry's date-range needle on that
line or its immediate successor — and is then read from the ORIGINAL lines,
which preserve the date hyphen. ``squash`` remains the substrate for the
membership checks that genuinely need it (``entity_present``, ``verbatim_integrity``).

**Three region-LOCAL exclusions (GAP 1 / CR-01 and WR-03).** Region ``i``'s
candidate set is its digit cores minus:

1. **That entry's OWN date-like cores** — never a union of every entry's dates.
   A document-wide date union (the pre-GAP-1 behaviour, WR-03) silently excused a
   token in a region that does not contain that entry, a false negative in the
   exact check whose job is to catch a number the renderer introduced.
2. **Page-number lines inside the region** — a lone integer excuses that value
   only where the line physically is, never document-wide.
3. **The non-entry structured strings that physically appear in the region** —
   section titles, skill groups, skill labels and the identity block
   (``non_entry_structured_strings``). The template renders a section's skills
   table AFTER that section's last entry, so those strings land in the last
   entry's region and their digits would otherwise be surplus candidates for
   ordinary content (``AWS S3``, ``Python 3``). Excluding them **only where they
   appear** — rather than unioning them into every region or bounding the last
   region at a heading — keeps a genuinely novel metric inside an entry's own
   region a candidate. The accepted tradeoff: a digit that appears in a source
   skill label is treated as grounded content, not a fabrication.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.domain.cv import RenderedEntry, RenderPlan
from app.domain.tex import squash

#: A maximal digit run with any interior ``.``/``,`` groups. Only the groups are
#: captured, so ``5-10`` is two matches and ``50k`` is one (the ``k`` is dropped).
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")
#: A line that is nothing but an integer (the page-number artefact, A3).
_LONE_INTEGER_RE = re.compile(r"^[0-9]+$")


def _normalise_core(raw: str) -> str:
    """Normalise one matched run to its digit core.

    ``.`` is always a decimal point; a ``,`` is a thousands separator when every
    group after it is exactly three digits, otherwise it is a decimal comma
    (``0,5`` -> ``0.5``). A trailing magnitude suffix is never part of the match.
    """
    if "." in raw:
        return raw.replace(",", "")
    if "," in raw:
        groups = raw.split(",")
        if all(len(group) == 3 for group in groups[1:]):
            return "".join(groups)
        return groups[0] + "." + "".join(groups[1:])
    return raw


def digit_cores(text: str) -> list[str]:
    """The digit cores of ``text``, in order. Total: ``""`` and ``None``-like give ``[]``."""
    if not text:
        return []
    return [_normalise_core(match.group(0)) for match in _NUMBER_RE.finditer(text)]


def date_like_cores_for_entry(entry: RenderedEntry) -> set[str]:
    """The digit cores of an entry's rendered date label (year and month cores).

    The label is derived from the entry's ``start``/``end`` (``"2021-03 -- 2024-09"``),
    so its cores are exactly the year/month cores the date-like exclusion needs.
    """
    return set(digit_cores(entry.dates))


def is_page_number_line(line: str, *, page_count: int) -> bool:
    """True when ``line`` is a lone integer in ``1..page_count`` (the A3 heuristic).

    This is what stops ``\\documentclass{article}``'s default page numbers poisoning
    check 4. The template is deliberately NOT changed to ``\\pagestyle{empty}``: that
    would change the golden bytes. The heuristic is the answer.
    """
    stripped = line.strip()
    if not _LONE_INTEGER_RE.match(stripped):
        return False
    value = int(stripped)
    return 1 <= value <= page_count


@dataclass(frozen=True)
class RegionReport:
    """One plan entry's region: its candidate tokens and the tokens it may carry."""

    entry_id: str
    org: str
    found: bool
    candidates: list[str] = field(default_factory=list)
    allowed: list[str] = field(default_factory=list)


def _entry_lines(entries: list[RenderedEntry], lines: list[str]) -> list[int]:
    """The line index of each entry's own header line, in plan order (``-1`` when absent).

    Region ``i`` starts on a line gated by a structural discriminator a body bullet
    can never satisfy: the line must carry the entry's ``squash(org)`` AND
    ``squash(title)`` (the template emits both on one header line,
    ``cv.tex.jinja:58``), AND the entry's date-range needle ``squash(entry.dates)``
    must appear on that same line or on its immediately following line. The
    date-range adjacency is the discriminator — a bullet never carries the entry's
    own date-range on itself or its successor — so a bullet that merely names a
    later employer and title can no longer start that employer's region and cannot
    donate its digits to it (ESC-06-A / CR-01). Requiring org AND title also removes
    the substring-vs-word fragility of a short or common org name ("Meta" matching
    "metadata"). A cursor advances past a matched line so two entries at the same
    employer resolve to their own headers.

    All three needles must be non-empty: an empty ``squash`` needle would make the
    membership test vacuously true and silently restore a content-only match, so an
    entry with an empty org, title or dates is reported ``found=False``.

    Only how a region's START is found changes: ``region_token_report`` still ends a
    region at the next found start (or end-of-text for the last), so a section's
    skills table rendered AFTER its last entry stays inside that last region (the
    WR-03 / 06-05 property).

    Deliberate extraction-variation trade-off: if extraction splits an entry's org
    and title onto SEPARATE lines, or the entry's date-range does not land on the
    header or its immediate successor (a long header wraps), no structural start is
    found; the region is reported ``found=False`` and check 4 surfaces that as a
    visible ``warn`` naming the entry — never a silent skip and never a
    mis-location at a bullet. An org-only fallback is deliberately NOT added — that
    is exactly the CR-02 substring mis-location this fixes. The trade-off is pinned
    by ``test_a_split_header_entry_is_reported_not_found_not_mislocated`` and
    ``test_a_non_adjacent_date_range_is_not_a_region_start``.
    """
    squashed_lines = [squash(line) for line in lines]
    positions: list[int] = []
    cursor = 0
    for entry in entries:
        org_needle = squash(entry.org)
        title_needle = squash(entry.title)
        dates_needle = squash(entry.dates)
        found = -1
        if org_needle and title_needle and dates_needle:
            for index in range(cursor, len(lines)):
                line = squashed_lines[index]
                if org_needle not in line or title_needle not in line:
                    continue
                dates_adjacent = dates_needle in line or (
                    index + 1 < len(lines) and dates_needle in squashed_lines[index + 1]
                )
                if dates_adjacent:
                    found = index
                    break
        positions.append(found)
        if found >= 0:
            cursor = found + 1
    return positions


def _allowed_for_entry(entry: RenderedEntry) -> set[str]:
    """The digit cores a region may carry: every source token the region renders.

    That is the entry's ``dates``, ``org``, ``title``, ``location`` (the template
    emits it inside the region at ``cv.tex.jinja:59-60``) and each surviving
    bullet's ``text`` and ``metrics``. This adds only to that entry's OWN allowed
    set — never to ``excluded`` — so the digit stays a region candidate and is
    grounded by membership in ``allowed``.
    """
    allowed: set[str] = set(digit_cores(entry.dates))
    allowed |= set(digit_cores(entry.org))
    allowed |= set(digit_cores(entry.title))
    if entry.location:
        allowed |= set(digit_cores(entry.location))
    for bullet in entry.bullets:
        allowed |= set(digit_cores(bullet.text))
        for metric in bullet.metrics:
            allowed |= set(digit_cores(metric))
    return allowed


def non_entry_structured_strings(plan: RenderPlan) -> list[str]:
    """Every structured string the plan carries that no entry owns (GAP 1 / CR-01).

    The identity block (``name`` / ``contact_email`` / ``contact_links``), each
    section ``title``, and each ``skill.group`` / ``skill.label``. ``_allowed_for_entry``
    enumerates only an entry's own fields, so a digit in one of these strings would
    otherwise be a surplus candidate in the region the template renders it into
    (a section's skills table is emitted after its last entry). Empty values are
    skipped, so a ``None`` name or an empty label contributes nothing.
    """
    strings: list[str] = []
    if plan.name:
        strings.append(plan.name)
    if plan.contact_email:
        strings.append(plan.contact_email)
    strings.extend(link for link in plan.contact_links if link)
    for section in plan.sections:
        if section.title:
            strings.append(section.title)
        for skill in section.skills:
            if skill.group:
                strings.append(skill.group)
            if skill.label:
                strings.append(skill.label)
    return strings


def _region_structured_cores(plan: RenderPlan, region_text: str) -> set[str]:
    """The digit cores of the non-entry structured strings present in ``region_text``.

    Region-LOCAL on purpose (GAP 1 / CR-01 and WR-03): a structured token is
    excused only in the region whose extracted text physically CONTAINS that
    string, never document-wide. A global union would silence check 4 for a
    fabricated digit that happens to equal a skill label's digit — the same
    false-negative class WR-03 removes. A string absent from the region
    contributes nothing.
    """
    squashed = squash(region_text)
    if not squashed:
        return set()
    cores: set[str] = set()
    for value in non_entry_structured_strings(plan):
        needle = squash(value)
        if needle and needle in squashed:
            cores |= set(digit_cores(value))
    return cores


def region_token_report(plan: RenderPlan, text: str, *, page_count: int) -> list[RegionReport]:
    """Per-entry region reports over the extracted ``text`` (D-113).

    Region ``i`` runs from entry ``i``'s org line to the next entry's org line (the
    last to end-of-text). Candidate tokens are the region's digit cores minus the
    excluded set: that entry's OWN date-like cores, any lone-integer page-number
    line inside the region, and the digit cores of the non-entry structured strings
    that physically appear in the region. Nothing is excluded document-wide
    (WR-03): a token equal to another entry's year remains a candidate here. An
    entry whose header cannot be anchored is reported ``found=False`` with empty
    candidates; check 4 surfaces that as a visible ``warn`` naming the entry — it is
    not by itself an ``entity_present`` failure.
    """
    entries = [entry for section in plan.sections for entry in section.entries]
    lines = text.splitlines()
    positions = _entry_lines(entries, lines)

    reports: list[RegionReport] = []
    for index, entry in enumerate(entries):
        position = positions[index]
        if position < 0:
            # No region to locate; there is no region text to scope structured
            # content to, so that operand is empty (region-local still holds).
            allowed = _allowed_for_entry(entry) | _region_structured_cores(plan, "")
            reports.append(
                RegionReport(
                    entry_id=entry.id,
                    org=entry.org,
                    found=False,
                    candidates=[],
                    allowed=sorted(allowed),
                )
            )
            continue
        later = [candidate for candidate in positions if candidate > position]
        end = min(later) if later else len(lines)
        region_lines = lines[position:end]
        region_text = "\n".join(region_lines)
        structured_cores = _region_structured_cores(plan, region_text)
        excluded = date_like_cores_for_entry(entry) | structured_cores
        for line in region_lines:
            if is_page_number_line(line, page_count=page_count):
                excluded.add(line.strip())
        allowed = _allowed_for_entry(entry) | structured_cores
        candidates = [core for core in digit_cores(region_text) if core not in excluded]
        reports.append(
            RegionReport(
                entry_id=entry.id,
                org=entry.org,
                found=True,
                candidates=candidates,
                allowed=sorted(allowed),
            )
        )
    return reports


__all__ = [
    "RegionReport",
    "date_like_cores_for_entry",
    "digit_cores",
    "is_page_number_line",
    "non_entry_structured_strings",
    "region_token_report",
]
