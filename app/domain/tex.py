"""Pure TeX text transforms.

House rules follow ``app/domain/sanitize.py``: pure, total, deterministic,
config-free, no I/O, no clock, no locale, no filesystem. Nothing here imports
``yaml``, ``jinja2`` or any I/O module — ``tests/test_import_discipline.py``
enforces that.

Three jobs live here:

1. **Escaping for emission** (:func:`escape_tex`) — the ten TeX-special ASCII
   characters, applied exactly once at the Jinja ``finalize`` choke point
   (``app/latex/env.py``). The escape is deliberately *not* offered as a filter,
   because a filter is opt-in and a template can forget it.
2. **Normalisation for comparison** (:func:`normalise_for_compare`,
   :func:`squash`, :func:`facts_present_in`, :func:`facts_compared`) — fold the
   PDF extractor's artefacts so a *strict membership* test can run over text
   extracted from a compiled document. Never a fuzzy ratio (D-70).
3. **Preamble sanitisation** (:func:`sanitise_preamble`) — comment out the
   pdfTeX-only primitives an XeTeX-derived engine rejects, conservatively and
   only where the human's own document leaves them unguarded.
"""

from __future__ import annotations

import re
import unicodedata

from app.domain.cv import CvFacts

# --- emission: the escape set -------------------------------------------------
#
# A TUPLE, not a dict or a set: the ordering is structural, not incidental. The
# backslash is handled first, or the replacement text of every later escape
# (``\&``, ``\%``, …) is itself escaped into a cascade.
#
# The trailing empty brace group in the three command forms is required or the
# following space is swallowed by TeX's control-word scanner.
_TEX_ESCAPES: tuple[tuple[str, str], ...] = (
    ("\\", r"\textbackslash{}"),
    ("{", r"\{"),
    ("}", r"\}"),
    ("$", r"\$"),
    ("&", r"\&"),
    ("#", r"\#"),
    ("%", r"\%"),
    ("_", r"\_"),
    ("~", r"\textasciitilde{}"),
    ("^", r"\textasciicircum{}"),
)

#: Backslash is *neutralised* into this sentinel first, then the sentinel is
#: replaced with the real command **last**. The command's own ``{}`` would
#: otherwise be escaped by the brace pass that runs after it, turning an input
#: ``\`` into ``\textbackslash\{\}``. A NUL byte cannot occur in a LaTeX document.
_BACKSLASH_SENTINEL = "\x00"


def escape_tex(value: str) -> str:
    """Escape the ten characters that can break or corrupt a LaTeX document.

    Total (``""`` -> ``""``), deterministic, and iterating a *tuple* — no set or
    dict order anywhere.

    Applied **exactly once**. Idempotence is deliberately NOT a claimed property:
    running it twice would escape the replacement text of the first pass. That is
    precisely why it lives inside the Jinja ``finalize`` choke point rather than
    being exposed as a filter a template could double-apply.

    Unicode is deliberately NOT escaped. The engine is Unicode-enabled, so an
    accented name or a Unicode punctuation mark must pass through untouched.
    Ligature folding belongs to the *comparison* normaliser below, never to the
    emitter.
    """
    value = value.replace(_TEX_ESCAPES[0][0], _BACKSLASH_SENTINEL)
    for old, new in _TEX_ESCAPES[1:]:
        value = value.replace(old, new)
    return value.replace(_BACKSLASH_SENTINEL, _TEX_ESCAPES[0][1])


# --- comparison: fold the extractor's artefacts -------------------------------
#
# These are extractor-artefact folds only — a soft hyphen the PDF extractor
# inserted, a dash family it spelled differently, curly quotes, and the space
# characters it substitutes. None of them is CV content.
_CHAR_FOLDS: tuple[tuple[str, str], ...] = (
    ("\u00ad", ""),  # soft hyphen — an extractor artefact, never content
    ("\u2010", "-"),
    ("\u2011", "-"),
    ("\u2012", "-"),
    ("\u2013", "-"),
    ("\u2014", "-"),
    ("\u2212", "-"),
    ("\u2018", "'"),
    ("\u2019", "'"),
    ("\u201c", '"'),
    ("\u201d", '"'),
    ("\u00a0", " "),
    ("\u202f", " "),
    ("\u2009", " "),
)

#: Joins a hyphenated line-break the extractor emitted mid-word.
_DE_HYPHENATE_RE = re.compile(r"(?<=\w)-\n(?=\w)")
#: Collapses a run of whitespace to one space (spaces are preserved).
_WHITESPACE_RE = re.compile(r"\s+")
#: Removes every non-word character for the whitespace-insensitive shingle form.
_SQUASH_RE = re.compile(r"[\s\W_]+", re.UNICODE)


def normalise_for_compare(text: str) -> str:
    """Fold extraction artefacts to a comparable form (D-70), *preserving* spaces.

    NFKC applies the compatibility decomposition that expands the ligature
    presentation forms (U+FB00-U+FB06) into their ASCII sequences, so ``ﬁ`` and
    ``fi`` compare equal without a hand-written ligature table.
    """
    value = unicodedata.normalize("NFKC", text)
    for old, new in _CHAR_FOLDS:
        value = value.replace(old, new)
    value = _DE_HYPHENATE_RE.sub("", value)
    value = _WHITESPACE_RE.sub(" ", value)
    return value.strip()


def squash(text: str) -> str:
    """The whitespace-INSENSITIVE canonical form, for shingle membership only.

    ``pypdf`` can drop a space entirely (issues #17, #1328), so a membership
    check on the space-preserving form produces **false failures on a correct
    document**. Squashing both sides makes a missing or inserted space irrelevant
    while keeping the predicate a strict membership test — never a fuzzy ratio
    (D-70).
    """
    return _SQUASH_RE.sub("", normalise_for_compare(text).casefold())


def facts_compared(facts: CvFacts) -> int:
    """How many facts :func:`facts_present_in` compares for ``facts``.

    The caller asserts a non-vacuous floor against this (D-72), so a predicate
    run over an empty extraction cannot pass.
    """
    return sum(3 + len(entry.bullets) for entry in facts.all_entries())


def facts_present_in(facts: CvFacts, extracted_text: str) -> tuple[bool, list[str]]:
    """Strict membership: every enumerated fact must be present in ``extracted_text``.

    Returns ``(all_present, missing)``. The shingles are computed from
    ``bullet.text`` — the *immutable source* — so a dropped bullet has **zero** of
    its shingles present, which is exactly the silent-condensing failure this
    exists to catch. Pair every call with :func:`facts_compared` for the floor.

    Membership is exact after normalisation. A fuzzy similarity ratio is never a
    substitute: a high ratio over a long section hides exactly the dropped bullet
    the check exists to catch.
    """
    squashed = squash(extracted_text)
    org_names = {org.id: org.name for org in facts.orgs}
    title_names = {title.id: title.name for title in facts.titles}

    missing: list[str] = []
    for entry in facts.all_entries():
        for value in (
            org_names.get(entry.org_id, entry.org_id),
            title_names.get(entry.title_id, entry.title_id),
            entry.date_range_label,
        ):
            if squash(value) not in squashed:
                missing.append(value)
        for bullet in entry.bullets:
            if squash(bullet.text) not in squashed:
                missing.append(bullet.text)
    return (not missing), missing


# --- preamble sanitisation ----------------------------------------------------
#
# The pdfTeX-only primitives an XeTeX-derived engine rejects. Tectonic is
# XeTeX-derived (STACK.md Q6 caveat 3); the same names are the ones a real
# document guards behind \ifnum\pdfoutput>0.
_PDFTEX_PRIMITIVES: tuple[str, ...] = (
    "pdfcompresslevel",
    "pdfobjcompresslevel",
    "pdfminorversion",
    "pdfoutput",
    "pdfpagewidth",
    "pdfpageheight",
    "pdfimageresolution",
    "pdfdecimaldigits",
    "pdfadjustspacing",
    "pdfomitcharset",
    "pdfmovechars",
    "pdfappendkern",
    "pdfoptionpdfminorversion",
)
_PRIMITIVE_RE = re.compile(
    r"^[ \t]*(?P<cmd>\\(?:" + "|".join(_PDFTEX_PRIMITIVES) + r"))\b(?P<rest>.*)$",
    re.MULTILINE,
)
#: A TeX conditional opener (``\if``, ``\ifx``, ``\ifnum`` …). Over-matching is
#: deliberately conservative: an unrecognised ``\iffoo`` leaves a later line
#: alone rather than commenting something inside a branch.
_CONDITIONAL_OPEN_RE = re.compile(r"\\if[a-zA-Z@]*")
_CONDITIONAL_CLOSE_RE = re.compile(r"\\fi\b")


def sanitise_preamble(tex: str) -> tuple[str, list[str]]:
    """Comment out UNGUARDED pdfTeX-only primitives in the preamble only.

    Returns ``(tex, removed)`` where ``removed`` names every command taken out,
    so the compile log can say what was changed — silent sanitisation would hide
    a real difference between the human's document and the rendered one.

    Deliberately conservative. It acts only on the preamble (before
    ``\\begin{document}``), only on a line whose first non-space token is the
    primitive, and it *comments* rather than deletes. A primitive already inside
    an ``\\if…``/``\\fi`` guard branch is left alone: most documents already wrap
    these, that branch is simply false under XeTeX, and acting on it would be a
    needless divergence. A document this defeats is answered by the fallback
    engine and a recorded verdict — never by a more aggressive regex over content
    the tool does not understand.
    """
    head, sep, body = tex.partition(r"\begin{document}")
    removed: list[str] = []
    guard_depth = 0
    out_lines: list[str] = []

    for line in head.splitlines(keepends=True):
        match = _PRIMITIVE_RE.match(line)
        if match is not None and guard_depth == 0:
            removed.append(match.group("cmd"))
            out_lines.append(
                "% [pdftex-only, commented by job-search-copilot] " + line.lstrip()
            )
        else:
            out_lines.append(line)
        guard_depth += len(_CONDITIONAL_OPEN_RE.findall(line))
        guard_depth -= len(_CONDITIONAL_CLOSE_RE.findall(line))
        if guard_depth < 0:
            guard_depth = 0

    return "".join(out_lines) + sep + body, removed


__all__ = [
    "escape_tex",
    "facts_compared",
    "facts_present_in",
    "normalise_for_compare",
    "sanitise_preamble",
    "squash",
]
