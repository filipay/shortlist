"""The LaTeX-safe Jinja environment: a SECOND ``Environment`` instance.

The HTML environment in ``app/web/template_env.py`` is untouched (STACK.md Q6:
"two environments, one process").

**Delimiter convention, and its one known limitation.** This is the
backslash-VAR / backslash-BLOCK convention. ``block_end_string`` is a single
closing brace, so a BLOCK **body cannot contain a brace**: blocks stay pure
control flow and every literal brace is ordinary template text outside the block
tag. Pick this convention once and never mix it with the alternative triple-paren
form.

**Why not the HTML escaper.** ``autoescape=True`` emits HTML entities and never
touches ``%``, ``_``, ``#`` or ``$`` — the wrong tool for TeX. Escaping is
enforced at the ``finalize`` choke point instead (D-67): every interpolated plain
string is escaped exactly once, and a template cannot bypass it.
"""

from __future__ import annotations

from pathlib import Path

import jinja2
from markupsafe import Markup

from app.domain.tex import escape_tex

#: The delimiter and determinism pins. `autoescape=False` is deliberate — see the
#: module docstring. `auto_reload` and `cache_size` are pinned so no environment
#: setting can introduce a surprise between two renders of the same input.
DELIMITERS: dict[str, object] = {
    "block_start_string": "\\BLOCK{",
    "block_end_string": "}",
    "variable_start_string": "\\VAR{",
    "variable_end_string": "}",
    "comment_start_string": "\\#{",
    "comment_end_string": "}",
    "line_statement_prefix": "%%",
    "line_comment_prefix": "%#",
    "trim_blocks": True,
    "lstrip_blocks": False,
    "keep_trailing_newline": True,
    "newline_sequence": "\n",
    "auto_reload": False,
    "cache_size": 0,
    "autoescape": False,
}

#: Filters removed from the environment. The HTML escapers are the wrong tool for
#: TeX: they emit HTML entities and never touch the TeX-special ASCII. Removing
#: them means a template author cannot reach one, so ``Markup`` is the only
#: opt-out of escaping (D-67).
_HTML_ESCAPE_FILTERS = ("escape", "forceescape", "e")


def _latex_finalize(value: object) -> object:
    """Escape every plain ``str``; leave ``Markup`` and non-``str`` values alone.

    Verified against the installed Jinja 3.1.6 (``compiler.py:1483-1487`` and
    ``compiler.py:1470-1472``): with ``autoescape`` off, Jinja's compiler wraps
    variable output as ``str(environment.finalize(<expr>))``, and literal template
    text does **not** go through ``finalize`` at all. So this single function
    escapes every interpolated value while leaving every literal brace, percent
    and backslash the template author typed untouched — which is what makes one
    ``finalize`` a complete choke point.

    ``Markup`` is the explicit opt-out. Ints, ``None`` and lists pass through
    unchanged and are the template's responsibility.
    """
    if isinstance(value, Markup):
        return value
    if isinstance(value, str):
        return escape_tex(value)
    return value


def make_latex_env(directory: str | Path) -> jinja2.Environment:
    """Build the LaTeX ``Environment``. Mirrors ``make_templates`` in shape."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(directory)), **DELIMITERS
    )
    env.finalize = _latex_finalize
    for name in _HTML_ESCAPE_FILTERS:
        env.filters.pop(name, None)
    return env


__all__ = ["DELIMITERS", "make_latex_env"]
