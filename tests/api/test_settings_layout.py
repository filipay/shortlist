"""260930-lay — the settings layout picker: a plain POST that remembers one token.

The page shows a non-HTMX form inside the CV fact-store card; a valid POST writes the
one-token preference and reports it in the existing settings banner; an invalid or
missing token writes nothing.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.config import settings
from app.cv.layout import LAYOUT_FILENAME
from app.latex.render import LAYOUTS

SELECTED_RE = re.compile(r'<option value="([^"]+)"[^>]*selected')


@pytest.fixture
def cv_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    path = tmp_path / "cv"
    path.mkdir()
    monkeypatch.setattr(settings, "cv_dir", str(path))
    yield path


def _form(body: str) -> str:
    action = body.index('action="/settings/cv-layout"')
    start = body.rindex("<form", 0, action)
    end = body.index("</form>", action)
    return body[start:end]


async def test_the_settings_page_shows_the_picker_in_the_cv_card(
    client: AsyncClient, cv_dir: Path
) -> None:
    body = (await client.get("/settings")).text

    assert "CV layout" in body
    assert "Save layout" in body
    assert 'action="/settings/cv-layout"' in body
    assert 'name="layout"' in body
    for token in LAYOUTS:
        assert f'value="{token}"' in body
    assert "Classic (default)" in body
    assert "Modern" in body
    assert "Compact" in body
    for note in (
        "centred header, section rules under headings, skills in a table.",
        "left header with a rule, uppercase ruled headings, stacked skills.",
        "smaller type, tighter spacing, fewer dropped bullets per page.",
    ):
        assert note in body
    # Inside the CV fact-store card, after it opens.
    assert body.index('id="cv-fact-store"') < body.index('action="/settings/cv-layout"')


async def test_the_picker_form_is_a_plain_post_with_no_htmx(
    client: AsyncClient, cv_dir: Path
) -> None:
    body = (await client.get("/settings")).text

    form = _form(body)
    assert 'method="post"' in form
    assert "hx-post" not in form
    assert "hx-get" not in form
    assert "hx-" not in form


async def test_a_valid_token_is_saved_and_reported(client: AsyncClient, cv_dir: Path) -> None:
    response = await client.post("/settings/cv-layout", data={"layout": "modern"})

    assert response.status_code == 200
    assert "Layout set to Modern. The next tailored CV will use it." in response.text
    assert (cv_dir / LAYOUT_FILENAME).read_text(encoding="utf-8").strip() == "modern"
    # The re-rendered page selects the value that was just saved.
    assert SELECTED_RE.search(response.text).group(1) == "modern"


async def test_a_classic_save_is_reported_by_its_plain_name(
    client: AsyncClient, cv_dir: Path
) -> None:
    response = await client.post("/settings/cv-layout", data={"layout": "classic"})

    assert response.status_code == 200
    assert "Layout set to Classic. The next tailored CV will use it." in response.text
    assert (cv_dir / LAYOUT_FILENAME).read_text(encoding="utf-8").strip() == "classic"


@pytest.mark.parametrize("token", ["fancy", "", "MODERN", "modern "])
async def test_an_invalid_token_writes_nothing_and_is_reported(
    client: AsyncClient, cv_dir: Path, token: str
) -> None:
    response = await client.post("/settings/cv-layout", data={"layout": token})

    assert response.status_code == 400
    assert "Nothing was saved" in response.text
    assert not (cv_dir / LAYOUT_FILENAME).exists()


async def test_a_missing_token_writes_nothing(client: AsyncClient, cv_dir: Path) -> None:
    response = await client.post("/settings/cv-layout", data={})

    assert response.status_code == 400
    assert "Nothing was saved" in response.text
    assert not (cv_dir / LAYOUT_FILENAME).exists()


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
