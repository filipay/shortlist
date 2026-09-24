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
by matching ``squash(org)`` against each line's squash (the template emits the
org verbatim on the entry header line) and is then read from the ORIGINAL lines,
which preserve the date hyphen. ``squash`` remains the substrate for the
membership checks that genuinely need it (``entity_present``, ``verbatim_integrity``).
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
    """The line index of each entry's org, in plan order (``-1`` when absent).

    A cursor advances past a matched line so two entries at the same employer
    resolve to their own headers rather than both matching the first.
    """
    squashed_lines = [squash(line) for line in lines]
    positions: list[int] = []
    cursor = 0
    for entry in entries:
        needle = squash(entry.org)
        found = -1
        if needle:
            for index in range(cursor, len(lines)):
                if needle in squashed_lines[index]:
                    found = index
                    break
        positions.append(found)
        if found >= 0:
            cursor = found + 1
    return positions


def _allowed_for_entry(entry: RenderedEntry) -> set[str]:
    """The digit cores a region may carry: its surviving bullets, label and org/title."""
    allowed: set[str] = set(digit_cores(entry.dates))
    allowed |= set(digit_cores(entry.org))
    allowed |= set(digit_cores(entry.title))
    for bullet in entry.bullets:
        allowed |= set(digit_cores(bullet.text))
        for metric in bullet.metrics:
            allowed |= set(digit_cores(metric))
    return allowed


def region_token_report(plan: RenderPlan, text: str, *, page_count: int) -> list[RegionReport]:
    """Per-entry region reports over the extracted ``text`` (D-113).

    Region ``i`` runs from entry ``i``'s org line to the next entry's org line (the
    last to end-of-text). Candidate tokens are the region's digit cores minus the
    excluded set (that entry's date-like cores and any lone-integer page-number
    line). An org absent from the text is reported ``found=False`` — that is an
    ``entity_present`` failure, never a metric failure.
    """
    entries = [entry for section in plan.sections for entry in section.entries]
    lines = text.splitlines()
    positions = _entry_lines(entries, lines)

    excluded: set[str] = set()
    for entry in entries:
        excluded |= date_like_cores_for_entry(entry)
    for line in lines:
        if is_page_number_line(line, page_count=page_count):
            excluded.add(line.strip())

    reports: list[RegionReport] = []
    for index, entry in enumerate(entries):
        allowed = _allowed_for_entry(entry)
        position = positions[index]
        if position < 0:
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
        region_text = "\n".join(lines[position:end])
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
    "region_token_report",
]
