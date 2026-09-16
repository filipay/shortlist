"""UI guard — every class a template uses must have a rule in the built CSS.

Why this test exists
--------------------
Every other UI test asserts class **strings** (``assert "badge-new" in
response.text``). A template can therefore be fully "green" while the committed
``static/vendor/app.css`` defines no rule for the class at all: the markup is
correct and the page is silently unstyled. This closes that gap by extracting
the literal class tokens from every ``class="..."`` attribute and requiring each
one to appear as a selector in the built stylesheet.

Jinja handling
--------------
``class="..."`` values are template source, not plain HTML. ``{% ... %}`` tags
and ``{{ ... }}`` expressions are *removed* before tokenising rather than
evaluated, so a purely dynamic token such as ``run-status-{{ run.status }}``
contributes no literal class. Literal text that sits between a conditional tag
pair — e.g. ``{% if row.is_stale %} listing-stale{% endif %}`` — is kept, because
that token is a real, statically-known class.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = PROJECT_ROOT / "app" / "web" / "templates" / "html"
STYLESHEET = PROJECT_ROOT / "static" / "vendor" / "app.css"

#: Classes deliberately not required to have a rule in the built stylesheet.
#: Keys are the exact class token; values state the reason, so that an exemption
#: is visible and reviewable rather than an implicit accident of the regex.
#: Every entry here is a *behavioural or structural hook* whose visual styling is
#: carried by a shared component class or a base-layer element rule — it is not
#: an unstyled class that slipped through.
EXEMPT_CLASSES: dict[str, str] = {
    # Wrapper <form> variants of `.listing-action`; the visual treatment lives on
    # `.listing-action` and on the child `.listing-save-button`/`.listing-hide-button`.
    "listing-action-save": "wrapper variant of .listing-action; child button carries the styling",
    "listing-action-hide": "wrapper variant of .listing-action; child button carries the styling",
    # Per-kind Alpine `x-show` toggle targets. The grid layout lives on the
    # `.rule-fields` class that every one of these is paired with.
    "rule-salary_floor": "Alpine x-show toggle target; layout carried by .rule-fields",
    "rule-exclude_keyword": "Alpine x-show toggle target; layout carried by .rule-fields",
    "rule-location": "Alpine x-show toggle target; layout carried by .rule-fields",
    "rule-remote": "Alpine x-show toggle target; layout carried by .rule-fields",
    "rule-seniority": "Alpine x-show toggle target; layout carried by .rule-fields",
    "rule-company_blocklist": "Alpine x-show toggle target; layout carried by .rule-fields",
    # Plain buttons/table cells already covered by base-layer element rules
    # (`button[type="submit"]`, `th, td`). The class is a hook for HTMX/selectors.
    "search-run-now": "plain submit button styled by the base-layer button element rule",
    "search-save": "plain submit button styled by the base-layer button element rule",
    "run-detail-slot": "table cell styled by the base-layer `th, td` element rule",
}

#: A `class="..."` (or `class='...'`) attribute and its raw value. The value may
#: contain the *other* quote character (e.g. `nav_path == '/'`), so each delimiter
#: is matched to itself rather than to a generic quote class.
_CLASS_ATTR_RE = re.compile(r"""class\s*=\s*(?:"([^"]*)"|'([^']*)')""")

#: A Jinja tag (`{% ... %}`) or expression (`{{ ... }}`), non-greedy.
_JINJA_RE = re.compile(r"\{[{%].*?[%}]\}", re.DOTALL)


def _template_files() -> list[Path]:
    return sorted(TEMPLATES_DIR.glob("*.html"))


def _literal_class_tokens(template: str) -> set[str]:
    """Return the statically-known class tokens in every ``class="..."`` value.

    Dynamic prefixes left dangling by a removed ``{{ ... }}`` (``run-status-``
    from ``run-status-{{ run.status }}``) are not class names, so a token ending
    in ``-`` is dropped.
    """
    tokens: set[str] = set()

    for match in _CLASS_ATTR_RE.finditer(template):
        attribute = match.group(1) or match.group(2) or ""
        without_jinja = _JINJA_RE.sub(" ", attribute)
        for token in without_jinja.split():
            if token.endswith("-"):
                continue
            tokens.add(token)

    return tokens


def _stylesheet_has_class(css: str, klass: str) -> bool:
    """True when ``css`` contains ``.klass`` as a selector.

    The trailing lookahead stops ``.badge`` from being satisfied by
    ``.badge-new``. A leading lookbehind is deliberately omitted so that a
    compound selector like ``.listing-hide-button.is-on`` counts for ``is-on``.
    """
    return (
        re.search(r"\." + re.escape(klass) + r"(?![\w-])", css) is not None
    )


def test_templates_exist_and_the_scan_is_not_vacuous() -> None:
    files = _template_files()

    assert files, "no templates were found — the coverage scan would pass vacuously"
    assert (TEMPLATES_DIR / "base.html") in files


def test_every_template_class_has_a_stylesheet_rule() -> None:
    css = STYLESHEET.read_text(encoding="utf-8")

    missing: dict[str, list[str]] = {}
    for path in _template_files():
        for klass in sorted(_literal_class_tokens(path.read_text(encoding="utf-8"))):
            if klass in EXEMPT_CLASSES:
                continue
            if not _stylesheet_has_class(css, klass):
                missing.setdefault(klass, []).append(path.name)

    assert missing == {}, (
        "these classes appear in a template but have no rule in "
        f"static/vendor/app.css: {missing}"
    )


def test_the_exemption_list_is_justified() -> None:
    """An empty reason would hide an unstyled class behind a bare exemption."""
    for klass, reason in EXEMPT_CLASSES.items():
        assert reason.strip(), f"exemption for {klass!r} has no stated reason"


def test_the_selection_check_flags_an_unstyled_class() -> None:
    """A guard that cannot fail is not a guard."""
    assert _stylesheet_has_class(".badge-new{color:red}", "badge-new")
    assert not _stylesheet_has_class(".badge-new{color:red}", "zz-sentinel-unstyled")
    # A shorter class must not be satisfied by a longer one.
    assert not _stylesheet_has_class(".badge-new{color:red}", "badge")


def test_the_jinja_tokeniser_keeps_literals_and_drops_dynamic_prefixes() -> None:
    source = (
        '<span class="listing-row{% if row.is_stale %} listing-stale{% endif %} '
        '{% if row.rules %} dimmed{% endif %}"></span>'
        '<span class="rule-chip rule-chip-{{ rule.kind }}"></span>'
    )

    assert _literal_class_tokens(source) == {
        "listing-row",
        "listing-stale",
        "dimmed",
        "rule-chip",
    }


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
