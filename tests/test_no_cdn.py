"""UI-07 / T-01-26 / Pitfall 12 — every UI asset is local and vendored.

A CDN reference makes the self-hosted tool break (or silently lose its styling)
on a machine that happens to be offline, and leaks usage to a third party. The
guard scans every template for a remote asset reference and asserts the three
vendored files exist, are non-empty, and are exactly the ones `base.html` links.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = PROJECT_ROOT / "app" / "web" / "templates"
VENDOR_DIR = PROJECT_ROOT / "static" / "vendor"

#: `href=`/`src=` pointing at an absolute or protocol-relative URL.
REMOTE_ASSET_RE = re.compile(
    r"""(?:href|src)\s*=\s*["'](?P<url>(?:https?:)?//[^"']+)["']""",
    re.IGNORECASE,
)

#: Any bare remote scheme anywhere in a template — catches a URL in an attribute
#: the first pattern does not model (`xlink:href`, a CSS `url(...)`, etc.).
REMOTE_SCHEME_RE = re.compile(r"https?://", re.IGNORECASE)

VENDORED_ASSETS = ("htmx.min.js", "alpine.min.js", "app.css")

BASE_TEMPLATE = TEMPLATES_DIR / "html" / "base.html"


def _template_files() -> list[Path]:
    return [path for path in sorted(TEMPLATES_DIR.rglob("*")) if path.is_file()]


def test_templates_exist_and_the_scan_is_not_vacuous() -> None:
    files = _template_files()

    assert files, "no templates were found — the CDN scan would pass vacuously"
    assert BASE_TEMPLATE in files


def test_no_template_references_a_remote_asset_origin() -> None:
    offenders: dict[str, list[str]] = {}

    for path in _template_files():
        text = path.read_text(encoding="utf-8")
        urls = [match.group("url") for match in REMOTE_ASSET_RE.finditer(text)]
        urls.extend(REMOTE_SCHEME_RE.findall(text))
        if urls:
            offenders[path.name] = sorted(set(urls))

    assert offenders == {}, f"a template references a remote asset origin: {offenders}"


def test_vendored_assets_exist_and_are_non_empty() -> None:
    for name in VENDORED_ASSETS:
        path = VENDOR_DIR / name
        assert path.is_file(), f"missing vendored asset: {path}"
        assert path.stat().st_size > 0, f"vendored asset is empty: {path}"


def test_base_template_links_the_three_vendored_assets() -> None:
    text = BASE_TEMPLATE.read_text(encoding="utf-8")

    for name in VENDORED_ASSETS:
        assert f"/static/vendor/{name}" in text, (
            f"base.html does not link /static/vendor/{name}"
        )


def test_the_vendored_file_set_is_exact() -> None:
    """A fourth asset appearing without an explicit decision is worth surfacing."""
    present = sorted(
        path.name for path in VENDOR_DIR.iterdir() if path.is_file()
    )

    assert present == sorted(VENDORED_ASSETS), (
        f"static/vendor contents drifted: {present}"
    )


def test_the_remote_asset_scan_flags_a_cdn_reference() -> None:
    """A guard that cannot fail is not a guard."""
    cdn = '<script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/dist/htmx.min.js"></script>'
    protocol_relative = '<link rel="stylesheet" href="//unpkg.com/tailwind.css">'

    assert [match.group("url") for match in REMOTE_ASSET_RE.finditer(cdn)] == [
        "https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/dist/htmx.min.js"
    ]
    assert [match.group("url") for match in REMOTE_ASSET_RE.finditer(protocol_relative)] == [
        "//unpkg.com/tailwind.css"
    ]


def test_the_remote_asset_scan_ignores_local_paths() -> None:
    local = (
        '<link rel="stylesheet" href="/static/vendor/app.css">'
        '<script src="/static/vendor/htmx.min.js" defer></script>'
    )

    assert REMOTE_ASSET_RE.findall(local) == []


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
