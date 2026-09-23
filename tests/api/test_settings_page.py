"""The settings page exists, is reachable from the nav, and states what a reset does."""

from __future__ import annotations

from pathlib import Path

from app.api.settings import RESET_CONFIRM_TOKEN, RESET_DELETE_ORDER, RESET_KEPT_TABLES
from app.config import settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "cv" / "awesomecv_standin.yaml"


async def test_the_settings_page_renders(client) -> None:
    response = await client.get("/settings")

    assert response.status_code == 200
    assert "Reset queue data" in response.text
    assert 'id="danger-zone"' in response.text


async def test_the_nav_reaches_settings(client) -> None:
    response = await client.get("/settings")

    assert '<a class="nav-link nav-current" href="/settings"' in response.text


async def test_the_page_names_the_confirm_token(client) -> None:
    response = await client.get("/settings")

    assert RESET_CONFIRM_TOKEN in response.text
    assert 'name="confirm"' in response.text


async def test_the_page_states_what_is_deleted_and_kept(client) -> None:
    response = await client.get("/settings")

    for table in RESET_DELETE_ORDER:
        assert table in response.text, table
    for table in RESET_KEPT_TABLES:
        assert table in response.text, table


# --- additions beyond the brief: the same facts, pinned so they cannot pass by luck ---


async def test_the_deleted_and_kept_lists_are_rendered_as_labelled_lines(client) -> None:
    """The brief's per-table scan is satisfiable by substrings of OTHER table names.

    `sources` (kept) is a substring of `listing_sources` (deleted), so a page that
    dropped the kept list entirely would still pass that scan. These assertions pin
    each list to its own labelled line in the fixed order.
    """
    response = await client.get("/settings")

    assert "Deleted: " + ", ".join(RESET_DELETE_ORDER) + "." in response.text
    assert "Kept: " + ", ".join(RESET_KEPT_TABLES) + "." in response.text


async def test_the_reset_form_is_a_plain_post_and_not_an_htmx_swap(client) -> None:
    """A destructive action is a full navigation; a partial swap gains nothing."""
    response = await client.get("/settings")

    assert '<form method="post" action="/settings/reset">' in response.text
    assert "hx-post" not in response.text


async def test_the_confirm_field_is_bound_to_its_label(client) -> None:
    response = await client.get("/settings")

    assert 'for="reset-confirm"' in response.text
    assert 'id="reset-confirm" name="confirm"' in response.text


async def test_the_nav_marks_settings_as_the_current_page(client) -> None:
    response = await client.get("/settings")

    assert (
        '<a class="nav-link nav-current" href="/settings" aria-current="page">'
        "Settings</a>" in response.text
    )


# --- the CV fact-store card (G-05-2 / RANK-08) ---------------------------------


async def test_the_cv_card_names_the_path_and_the_supply_steps(client) -> None:
    """The card names the loader's own path and the concrete way to supply a store.

    The path is asserted as the route computes it — `settings.cv_dir` + the
    fact-store filename — never a hardcoded `/cv/cv.yaml`, so this pin does not
    fix the container default.
    """
    response = await client.get("/settings")

    assert 'id="cv-fact-store"' in response.text
    assert str(Path(settings.cv_dir) / "cv.yaml") in response.text
    for token in ("cv/base.tex", "cv-tex-spike.sh", "cv/cv.yaml"):
        assert token in response.text, token


async def test_the_cv_card_reports_a_readable_store(
    client, tmp_path: Path, monkeypatch
) -> None:
    """A readable store renders the loaded sentence, not the skip sentence."""
    (tmp_path / "cv.yaml").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(settings, "cv_dir", str(tmp_path))

    response = await client.get("/settings")

    assert "A readable CV fact store is loaded from" in response.text
    assert "no readable CV fact store" not in response.text

