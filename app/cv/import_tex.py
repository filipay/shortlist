"""A **bounded** `.tex` importer plus curation — not a LaTeX parser.

It parses one tractable subset of a human-authored LaTeX document and reports
everything else. It never guesses, because the worst failure in this phase is a
fabricated fact entering the store where nothing downstream can tell it from a
real one (Pitfall 13). A field the parser could not fill is **absent and loud**:
the draft is written to a caller-chosen path and the fact store's validator is the
single gate that either accepts it or fails naming the field.

The tractable subset is exactly:

- **sections** — ``\\section`` / ``\\section*`` and the subsection forms,
  optionally reached through a preamble-declared macro that wraps ``\\section``;
- **entry macros** — any macro the preamble declares via
  ``\\newcommand{\\name}[N]{body}`` whose body uses ``#1`` and at least one of
  ``#2``/``#3``. The parser learns ``N`` from the declaration and then captures
  exactly ``N`` balanced brace groups at each call site. *Learning arity from the
  declaration and reading call sites is the mechanism that makes a macro-heavy
  résumé tractable without a TeX engine*;
- **bullets** — ``\\item`` inside an ``itemize``/``enumerate`` environment, with
  balanced-brace capture and inline bold/emphasis flattened to plain text;
- **preamble packages** — every ``\\usepackage`` name, in source order;
- **comments** — ``%`` to end of line, honouring an escaped ``%``.

Everything else is reported by name, count and line reference. The report is
**counts, names and line numbers only** and carries no source text by construction.

**Bounds** (PLAT-04) come from ``Settings``: ``tex_import_max_lines`` stops the
scan and sets a truncation flag, and ``tex_import_max_depth`` bounds balanced-brace
capture. Neither raises: a pathological document cannot hang the single worker.

**Documented escalation — deliberately NOT installed.** If the real document
defeats this bounded subset, the fallback is a fault-tolerant LaTeX parse tree
(TexSoup, BSD-3-Clause). It is *not* imported and *not* installed speculatively:
adopting it would need its own package-legitimacy check and a human decision.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.config import settings
from app.domain.cv import (
    SCHEMA_VERSION,
    SECTION_TITLES,
    derive_bullet_id,
    derive_entry_id,
    qualify_entry_ids,
    slugify,
)

#: An UNESCAPED percent starts a comment; ``\%`` is a literal. Applied per line.
_LATEX_COMMENT_RE = re.compile(r"(?<!\\)%.*")
#: ``\newcommand{\name}[N]{body}`` (the ``[N]`` is optional; head-group form too).
_NEWCOMMAND_RE = re.compile(
    r"\\newcommand\s*\{?\s*\\(?P<name>[A-Za-z@]+)\s*\}?\s*(?:\[(?P<arity>\d+)\])?\s*\{"
)
_USEPACKAGE_RE = re.compile(r"\\usepackage\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")
_COMMAND_RE = re.compile(r"\\([A-Za-z@]+)")
#: The inline wrappers whose *content* survives flattening.
_INLINE_WRAP_RE = re.compile(
    r"\\(?:textbf|textit|emph|texttt|textsc|underline|textrm|textsf)\s*\{"
)
#: The escaped single characters that mean themselves in plain text.
_ESCAPE_RE = re.compile(r"\\([%&_#$])")
_WHITESPACE_RE = re.compile(r"\s+")
_DATE_RANGE_RE = re.compile(
    r"^\s*(\d{4}-\d{2})\s*(?:--|—|–|to)\s*(\d{4}-\d{2}|present)\s*(?:,\s*(.*?))?\s*$",
    re.IGNORECASE,
)
_SINGLE_DATE_RE = re.compile(r"^\s*(\d{4}-\d{2})\s*(?:,\s*(.*?))?\s*$")

#: The reverse of the closed title map: a heading the parser recognises maps to a
#: ``title_key`` the fact store accepts. An unrecognised heading is reported, never
#: written as free text (``Section.title_key`` is validated against a closed map).
_SECTION_KEY_BY_HEADING = {title: key for key, title in SECTION_TITLES.items()}

#: Commands the scanner handles structurally and therefore does not report.
_GLUE_COMMANDS = frozenset({"documentclass", "usepackage", "newcommand", "begin", "end"})
#: Environments whose ``\item`` rows the bullet rule understands.
_BULLET_ENVIRONMENTS = frozenset({"itemize", "enumerate"})
#: The one environment that is structural rather than content-bearing.
_STRUCTURAL_ENVIRONMENTS = frozenset({"document"})


@dataclass(frozen=True)
class ImportReport:
    """What the bounded parse understood, and what it did not.

    By construction there is no field able to carry document text: counts, names,
    line numbers and flags only. A name here is a LaTeX command or environment
    token, never CV content.
    """

    sections_parsed: int = 0
    entries_parsed: int = 0
    bullets_parsed: int = 0
    lines_scanned: int = 0
    packages_requested: tuple[str, ...] = ()
    unresolved_macros: dict[str, int] = field(default_factory=dict)
    unresolved_lines: dict[str, tuple[int, ...]] = field(default_factory=dict)
    unresolved_sections: int = 0
    entry_id_collisions: tuple[str, ...] = ()
    truncated: bool = False

    def summary(self) -> str:
        """A human-readable summary — counts, names and line numbers only."""
        lines = [
            f"sections parsed: {self.sections_parsed}",
            f"entries parsed: {self.entries_parsed}",
            f"bullets parsed: {self.bullets_parsed}",
            f"lines scanned: {self.lines_scanned}",
            f"packages requested: {', '.join(self.packages_requested) or '(none)'}",
            f"unresolved section headings: {self.unresolved_sections}",
            f"truncated: {'yes' if self.truncated else 'no'}",
        ]
        if self.entry_id_collisions:
            lines.append(
                "entry id collisions: " + ", ".join(self.entry_id_collisions)
            )
        if self.unresolved_macros:
            lines.append("unresolved macros:")
            for name in self.unresolved_macros:
                where = ",".join(
                    str(number) for number in self.unresolved_lines.get(name, ())
                )
                lines.append(
                    f"  {name}: {self.unresolved_macros[name]} (lines: {where})"
                )
        return "\n".join(lines)


@dataclass(frozen=True)
class _Macro:
    """One preamble declaration, as the scanner needs it."""

    arity: int
    is_entry: bool
    wraps_section: bool


def _declared_arity(raw: str | None) -> int:
    """The declared argument count: the ``[N]`` a declaration carries, else ``0``.

    Learned from the declaration rather than assumed at the call site — this is
    the whole trick that makes a macro-heavy résumé tractable without an engine.
    """
    if raw is None:
        return 0
    value = raw.strip()
    return int(value) if value.isdigit() else 0


def _capture_group(text: str, index: int, max_depth: int) -> tuple[str, int, bool]:
    """Read the balanced brace group starting at ``index``.

    Returns ``(content, end_index, ok)`` with the outer braces stripped. Nesting is
    respected; a group that nests past ``max_depth`` returns ``ok=False`` rather
    than recursing without limit. An escaped character (``\\{``, ``\\}``) is skipped.
    """
    if index >= len(text) or text[index] != "{":
        return "", index, False
    depth = 0
    cursor = index
    while cursor < len(text):
        char = text[cursor]
        if char == "\\":
            cursor += 2
            continue
        if char == "{":
            depth += 1
            if depth > max_depth:
                return "", cursor, False
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[index + 1 : cursor], cursor + 1, True
        cursor += 1
    return "", cursor, False


def _capture_groups(
    text: str, index: int, count: int, max_depth: int
) -> tuple[list[str], int, bool]:
    """Capture exactly ``count`` balanced brace groups, skipping intervening space."""
    args: list[str] = []
    cursor = index
    for _ in range(count):
        while cursor < len(text) and text[cursor] in " \t\r\n":
            cursor += 1
        if cursor >= len(text) or text[cursor] != "{":
            return args, cursor, False
        content, cursor, ok = _capture_group(text, cursor, max_depth)
        if not ok:
            return args, cursor, False
        args.append(content)
    return args, cursor, True


def _flatten(text: str, max_depth: int) -> str:
    """Reduce inline markup and escaped characters to plain text.

    ``\\textbf{X}`` / ``\\emph{X}`` become ``X``; a grouping brace is dropped;
    ``\\%``/``\\&``/``\\_``/``\\#``/``\\$`` mean themselves. Prose is otherwise
    preserved, whitespace collapsed.
    """
    value = text
    for _ in range(max_depth):
        match = _INLINE_WRAP_RE.search(value)
        if match is None:
            break
        content, end, ok = _capture_group(value, match.end() - 1, max_depth)
        if not ok:
            break
        value = value[: match.start()] + content + value[end:]
    value = value.replace("{", "").replace("}", "")
    value = _ESCAPE_RE.sub(r"\1", value)
    value = value.replace("~", " ")
    return _WHITESPACE_RE.sub(" ", value).strip()


def _parse_date_range(text: str) -> tuple[str, str | None, str | None] | None:
    """A strict date range or single date. Returns ``None`` when it does not parse.

    Never a best-effort guess: an unparseable date argument leaves the entry
    without a ``start``, which the fact store then refuses loudly.
    """
    range_match = _DATE_RANGE_RE.match(text)
    if range_match is not None:
        start, end, location = range_match.groups()
        end_value = None if end.lower() == "present" else end
        return start, end_value, (location.strip() if location else None)
    single_match = _SINGLE_DATE_RE.match(text)
    if single_match is not None:
        start, location = single_match.groups()
        return start, None, (location.strip() if location else None)
    return None


def _record(
    counts: dict[str, int], lines: dict[str, list[int]], name: str, lineno: int
) -> None:
    counts[name] = counts.get(name, 0) + 1
    lines.setdefault(name, []).append(lineno)


def _read_declarations(text: str, max_depth: int) -> tuple[dict[str, _Macro], tuple[str, ...]]:
    """Collect every ``\\usepackage`` name (source order) and ``\\newcommand``."""
    packages: list[str] = []
    for match in _USEPACKAGE_RE.finditer(text):
        for name in match.group(1).split(","):
            stripped = name.strip()
            if stripped:
                packages.append(stripped)

    macros: dict[str, _Macro] = {}
    for match in _NEWCOMMAND_RE.finditer(text):
        body, _end, ok = _capture_group(text, match.end() - 1, max_depth)
        if not ok:
            continue
        macros[match.group("name")] = _Macro(
            arity=_declared_arity(match.group("arity")),
            is_entry=("#1" in body and ("#2" in body or "#3" in body)),
            wraps_section="\\section" in body,
        )
    return macros, tuple(dict.fromkeys(packages))


def _org_id(name: str) -> str:
    return f"org.{slugify(name)}"


def _title_id(name: str) -> str:
    return f"title.{slugify(name)}"


def parse_tex(source: str) -> tuple[dict[str, Any], ImportReport]:
    """Parse the tractable subset of ``source`` into a draft plus a report.

    The draft is a plain mapping in the fact-store shape; it is deliberately NOT
    validated here — ``app/cv/factstore.py`` is the single validator, and a field
    the parser could not fill is left absent so that validator fails loudly.
    """
    max_lines = settings.tex_import_max_lines
    max_depth = settings.tex_import_max_depth

    raw_lines = source.splitlines()
    truncated = len(raw_lines) > max_lines
    scanned = raw_lines[:max_lines]
    text = "\n".join(_LATEX_COMMENT_RE.sub("", line) for line in scanned)

    newlines = [index for index, char in enumerate(text) if char == "\n"]

    def line_of(index: int) -> int:
        return bisect_right(newlines, index) + 1

    macros, packages = _read_declarations(text, max_depth)
    section_wrappers = {
        name for name, macro in macros.items() if macro.wraps_section and not macro.is_entry
    }

    sections: list[dict[str, Any]] = []
    section_keys: set[str] = set()
    orgs: dict[str, str] = {}
    titles: dict[str, str] = {}
    entry_meta: list[tuple[dict[str, Any], str | None, str | None]] = []
    unresolved_counts: dict[str, int] = {}
    unresolved_lines: dict[str, list[int]] = {}
    unresolved_sections = 0
    sections_parsed = 0
    bullets_parsed = 0

    current: dict[str, Any] | None = None
    last_entry: dict[str, Any] | None = None
    env_stack: list[str] = []

    def open_section(heading: str, lineno: int) -> dict[str, Any] | None:
        nonlocal current, last_entry, unresolved_sections, sections_parsed
        key = _SECTION_KEY_BY_HEADING.get(heading.strip())
        if key is None or key in section_keys:
            unresolved_sections += 1
            _record(unresolved_counts, unresolved_lines, "\\section", lineno)
            return None
        section: dict[str, Any] = {
            "id": key,
            "title_key": key,
            "order": (len(sections) + 1) * 10,
            "entries": [],
            "skills": [],
        }
        section_keys.add(key)
        sections.append(section)
        sections_parsed += 1
        current = section
        last_entry = None
        return section

    cursor = 0
    length = len(text)
    while cursor < length:
        if text[cursor] != "\\":
            cursor += 1
            continue
        match = _COMMAND_RE.match(text, cursor)
        if match is None:
            cursor += 1
            continue
        name = match.group(1)
        after = match.end()
        lineno = line_of(cursor)

        if name in ("section", "subsection", "subsubsection"):
            probe = after + 1 if after < length and text[after] == "*" else after
            heading, end, ok = _capture_group(text, probe, max_depth)
            if not ok:
                unresolved_sections += 1
                _record(unresolved_counts, unresolved_lines, "\\section", lineno)
                cursor = after
                continue
            open_section(heading, lineno)
            cursor = end
            continue

        if name in section_wrappers:
            args, end, ok = _capture_groups(text, after, macros[name].arity, max_depth)
            if ok and args:
                heading = _flatten(args[0], max_depth)
                open_section(heading, lineno)
            else:
                unresolved_sections += 1
                _record(unresolved_counts, unresolved_lines, name, lineno)
            cursor = end if ok else after
            continue

        if name in macros and macros[name].is_entry:
            args, end, ok = _capture_groups(text, after, macros[name].arity, max_depth)
            if not ok or current is None:
                _record(unresolved_counts, unresolved_lines, name, lineno)
                cursor = end if ok else after
                continue

            entry: dict[str, Any] = {"bullets": []}
            org_name: str | None = None
            start: str | None = None
            if len(args) > 0:
                org_name = _flatten(args[0], max_depth)
                if org_name:
                    orgs.setdefault(_org_id(org_name), org_name)
                    entry["org_id"] = _org_id(org_name)
            if len(args) > 1:
                title_name = _flatten(args[1], max_depth)
                if title_name:
                    titles.setdefault(_title_id(title_name), title_name)
                    entry["title_id"] = _title_id(title_name)
            if len(args) > 2:
                parsed = _parse_date_range(_flatten(args[2], max_depth))
                if parsed is not None:
                    start, end_date, location = parsed
                    entry["start"] = start
                    if end_date:
                        entry["end"] = end_date
                    if location:
                        entry["location"] = location

            if org_name is None or start is None:
                # Not fully understood: emit what parsed and report the call, so
                # the missing required field fails the fact store loudly.
                _record(unresolved_counts, unresolved_lines, name, lineno)
            current["entries"].append(entry)
            entry_meta.append((entry, org_name, start))
            last_entry = entry
            cursor = end
            continue

        if name == "item":
            if "itemize" in env_stack or "enumerate" in env_stack:
                body, end = _read_item_body(text, after, max_depth)
                value = _flatten(body, max_depth)
                if last_entry is not None and value:
                    last_entry["bullets"].append(value)
                    bullets_parsed += 1
                else:
                    _record(unresolved_counts, unresolved_lines, "item", lineno)
                cursor = end
                continue
            cursor = after
            continue

        if name in ("begin", "end"):
            environment, end, ok = _capture_group(text, after, max_depth)
            environment = environment.strip()
            if ok:
                if name == "begin":
                    if (
                        environment not in _STRUCTURAL_ENVIRONMENTS
                        and environment not in _BULLET_ENVIRONMENTS
                    ):
                        _record(
                            unresolved_counts,
                            unresolved_lines,
                            environment or "environment",
                            lineno,
                        )
                    env_stack.append(environment)
                elif environment in env_stack:
                    env_stack.reverse()
                    env_stack.remove(environment)
                    env_stack.reverse()
            cursor = end if ok else after
            continue

        if name in _GLUE_COMMANDS:
            cursor = after
            continue

        _record(unresolved_counts, unresolved_lines, name, lineno)
        cursor = after

    # IDs: derived from immutable identity only, with the collision rule applied.
    complete = [(entry, org, start) for entry, org, start in entry_meta if org and start]
    ids = qualify_entry_ids([(org, start) for (_entry, org, start) in complete])
    collisions: list[str] = []
    for (entry, org, start), fact_id in zip(complete, ids):
        entry["id"] = fact_id
        if fact_id != derive_entry_id(org or "", start or ""):
            collisions.append(fact_id)
        entry["bullets"] = [
            {"id": derive_bullet_id(fact_id, index), "text": value}
            for index, value in enumerate(entry["bullets"], start=1)
        ]

    for entry, _org, _start in entry_meta:
        if "id" not in entry:
            entry["bullets"] = [{"text": value} for value in entry["bullets"]]

    draft: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "meta": {},
        "sections": sections,
        "orgs": [{"id": org_id, "name": name} for org_id, name in orgs.items()],
        "titles": [{"id": title_id, "name": name} for title_id, name in titles.items()],
        "gaps": [],
    }

    report = ImportReport(
        sections_parsed=sections_parsed,
        entries_parsed=sum(1 for entry, _org, _start in entry_meta if "id" in entry),
        bullets_parsed=bullets_parsed,
        lines_scanned=len(scanned),
        packages_requested=packages,
        unresolved_macros=dict(unresolved_counts),
        unresolved_lines={name: tuple(values) for name, values in unresolved_lines.items()},
        unresolved_sections=unresolved_sections,
        entry_id_collisions=tuple(collisions),
        truncated=truncated,
    )
    return draft, report


def _read_item_body(text: str, index: int, max_depth: int) -> tuple[str, int]:
    """The rest of an ``\\item``: a braced group if present, else to end of line."""
    cursor = index
    while cursor < len(text) and text[cursor] in " \t":
        cursor += 1
    if cursor < len(text) and text[cursor] == "{":
        content, end, ok = _capture_group(text, cursor, max_depth)
        if ok:
            return content, end
    end = text.find("\n", index)
    if end == -1:
        end = len(text)
    return text[index:end], end


def write_draft(draft: dict[str, Any], destination: Path) -> Path:
    """Write ``draft`` to ``destination`` and return that path.

    The **caller** chooses the destination. The importer never writes back over the
    document it read and never writes over ``cv.yaml``: the human review step is the
    point, so the draft goes to a separate path a person inspects and then curates.
    """
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        yaml.safe_dump(draft, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return destination


__all__ = ["ImportReport", "parse_tex", "write_draft"]
