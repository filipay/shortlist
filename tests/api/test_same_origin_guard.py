"""CR-01 — a cross-site state-changing POST is refused; a same-origin one is not.

The literal repro from the finding is a plain form on any page the user's browser
loads:

    <form method="post" action="http://127.0.0.1:8000/settings/reset">
      <input name="confirm" value="DELETE">
    </form><script>f.submit()</script>

`RESET_CONFIRM_TOKEN` is a published source constant, so the "type DELETE to
confirm" affordance is not a secret. With no authentication (D-21) every
cross-origin request is fully authorised, so the guard in `app/main.py` is the
only thing standing between that form and the corpus. It must refuse a request
whose fetch metadata names another origin, and must NOT refuse a header-less
caller (curl, the test client) or a same-origin one.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.api import settings as settings_module

#: Every state-changing settings route the finding enumerates. A parametrised
#: class, not the single instance, so a new mutating route cannot be added without
#: inheriting the guard (CONVENTIONS rule 4).
STATE_CHANGING_PATHS = (
    settings_module.WEIGHTS_PATH,
    settings_module.SCREENING_QUESTIONS_PATH,
    settings_module.SCHEDULE_PATH,
    settings_module.CV_UPLOAD_PATH,
    settings_module.CV_LAYOUT_PATH,
    settings_module.LLM_TEST_PATH,
    settings_module.PRUNE_PREVIEW_PATH,
    settings_module.PRUNE_PATH,
    "/settings/reset",
)

CROSS_SITE_ORIGIN = "https://evil.example"
REFUSAL = "cross-origin request refused"


@pytest.mark.parametrize("path", STATE_CHANGING_PATHS)
async def test_a_cross_site_origin_post_is_refused(client: AsyncClient, path: str) -> None:
    response = await client.post(
        path, data={"confirm": "DELETE"}, headers={"Origin": CROSS_SITE_ORIGIN}
    )

    assert response.status_code == 403
    assert REFUSAL in response.text


@pytest.mark.parametrize("path", STATE_CHANGING_PATHS)
async def test_a_cross_site_sec_fetch_site_post_is_refused(client: AsyncClient, path: str) -> None:
    response = await client.post(
        path, data={"confirm": "DELETE"}, headers={"Sec-Fetch-Site": "cross-site"}
    )

    assert response.status_code == 403
    assert REFUSAL in response.text


async def test_the_literal_reset_form_is_refused_and_the_corpus_survives(
    client: AsyncClient,
) -> None:
    """The exact repro: a cross-site form POSTing `confirm=DELETE` to the reset."""
    response = await client.post(
        "/settings/reset",
        data={"confirm": "DELETE"},
        headers={"Origin": CROSS_SITE_ORIGIN},
    )

    assert response.status_code == 403
    # The route never ran: the page banner is absent and nothing was reset.
    assert "Nothing was deleted" not in response.text


async def test_a_same_origin_post_still_succeeds(client: AsyncClient) -> None:
    response = await client.post(
        "/settings/reset",
        data={"confirm": "DELETE"},
        headers={"Origin": "http://test"},
    )

    assert response.status_code == 200
    assert REFUSAL not in response.text


async def test_a_header_less_post_still_succeeds(client: AsyncClient) -> None:
    """curl and the test client send neither header; the guard must not break them."""
    response = await client.post("/settings/reset", data={"confirm": "DELETE"})

    assert response.status_code == 200
    assert REFUSAL not in response.text


async def test_a_same_origin_sec_fetch_site_post_still_succeeds(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/settings/weights",
        data={"skill_match": "1"},
        headers={"Sec-Fetch-Site": "same-origin"},
    )

    assert response.status_code != 403
    assert REFUSAL not in response.text


async def test_a_cross_site_get_is_allowed(client: AsyncClient) -> None:
    """The guard is scoped to state-changing methods; a GET has no side effect."""
    response = await client.get("/settings", headers={"Origin": CROSS_SITE_ORIGIN})

    assert response.status_code == 200
