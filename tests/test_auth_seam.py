"""PLAT-03 / D-21 / T-01-27 / AP14 — the identity seam is universal and provable.

FastAPI 0.141.1 does not flatten `include_router(...)` into the parent's
`app.routes`: it appends a `_IncludedRouter` wrapper carrying no `.dependant` and
no `.path`. A naive `for route in app.routes` walk therefore inspects **zero**
`APIRoute`s, and "every route carries the seam" passes vacuously — a finding
recorded by plan 01-04. The walk here recurses through `original_router.routes`
and *proves* it reached the leaf routes before asserting anything about them.

The second half of D-21 is negative: v1 must not pre-add a speculative
`user_id`/`owner_id` column "for later auth" (AP14).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.routing import APIRoute

from app.api.deps import current_user
from app.main import create_app

#: Routes whose seam membership is asserted explicitly, so the walk's
#: non-vacuity claim covers them. A route added later *with* the seam still
#: passes the per-route assertion; one added without it fails.
EXPECTED_SEAM_ROUTES = frozenset(
    {
        "/",
        "/runs",
        "/runs/{run_id}/status",
        "/health",
        # Phase 5's job detail page (UI-02): a full page, so it goes through the
        # identity seam like every other server-rendered surface.
        "/listings/{listing_id}",
        # Phase 3's on-demand LLM backend selftest (D-48): it spends tokens, so it
        # must go through the identity seam like every other route.
        "/settings/llm-test",
        # Phase 6's dedicated tailoring page and actions (D-116). It generates,
        # compiles and serves a private artefact, so every route carries the seam.
        "/listings/{listing_id}/cv",
        "/listings/{listing_id}/cv/generate",
        "/listings/{listing_id}/cv/compile",
        "/listings/{listing_id}/cv/pdf",
        # Phase 7's application tracker (D-120): the tracker and its record/history
        # routes render and mutate private job-search data, so every route carries
        # the seam.
        "/applications",
        "/applications/list",
        "/applications/record",
        "/applications/{application_id}/history",
        "/applications/{application_id}/status",
        # Phase 7's apply package page (D-120): it renders the verified PDF and the
        # user's stored job-search data, so it goes through the identity seam. The
        # drafting/add-question/delete actions spend tokens or mutate stored drafts,
        # so every one carries the seam too.
        "/listings/{listing_id}/apply",
        "/listings/{listing_id}/apply/draft",
        "/listings/{listing_id}/apply/question",
        "/listings/{listing_id}/apply/draft/delete",
        # Phase 8's schedule form (D-151..D-153): it writes the user's own schedule
        # and re-configures the live scheduler, so it carries the seam like every
        # other settings route.
        "/settings/schedule",
        # Phase 8's health page (RUN-07 / D-155): the human-readable `/status`
        # surface. `/health` stays JSON; this page renders the user's own system
        # and source state, so it goes through the identity seam too.
        "/status",
        # Phase 8's retention prune (D-163..D-168, RUN-07): the preview and the
        # confirm are separate POSTs, and the confirm destroys rows and files, so
        # both carry the identity seam like every other settings route.
        "/settings/prune/preview",
        "/settings/prune",
    }
)

#: Speculative identity columns that must not exist in v1 (AP14).
FORBIDDEN_IDENTITY_COLUMNS = frozenset({"user_id", "user_uuid", "owner_id", "tenant_id"})


def _leaf_routes(routes: Iterable[Any]) -> Iterator[Any]:
    """Flatten FastAPI's `_IncludedRouter` wrappers into real route objects."""
    for route in routes:
        inner = getattr(route, "original_router", None)
        if inner is not None and hasattr(inner, "routes"):
            yield from _leaf_routes(inner.routes)
        else:
            yield route


def _depends_on(dependant: Any, target: Any) -> bool:
    """True when `target` appears anywhere in `dependant`'s dependency tree."""
    if dependant is None:
        return False
    if getattr(dependant, "call", None) is target:
        return True
    return any(
        _depends_on(sub, target)
        for sub in (getattr(dependant, "dependencies", None) or ())
    )


def _checked_routes() -> dict[str, Any]:
    """`{path: dependant}` for every leaf route that declares dependencies."""
    checked: dict[str, Any] = {}
    for route in _leaf_routes(create_app().routes):
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        checked[str(getattr(route, "path", repr(route)))] = dependant
    return checked


# --- the walk really reaches the routes ---------------------------------------


def test_the_walk_reaches_the_application_leaf_routes() -> None:
    """Without this, the seam assertion below inspects nothing and passes trivially."""
    paths = {getattr(route, "path", None) for route in _leaf_routes(create_app().routes)}

    assert EXPECTED_SEAM_ROUTES <= paths, (
        f"the flattened walk found {sorted(p for p in paths if p)} — "
        f"expected it to reach {sorted(EXPECTED_SEAM_ROUTES)}"
    )
    assert any(isinstance(route, APIRoute) for route in _leaf_routes(create_app().routes))


# --- every route declares the seam --------------------------------------------


def test_every_route_with_a_dependant_declares_current_user() -> None:
    checked = _checked_routes()

    assert EXPECTED_SEAM_ROUTES <= set(checked), (
        f"the walk inspected {sorted(checked)} — the expected seam routes are "
        "absent, so this assertion would be vacuous"
    )

    missing = sorted(
        path for path, dependant in checked.items() if not _depends_on(dependant, current_user)
    )
    assert missing == [], f"routes without current_user: {missing}"


def test_the_helper_recognises_the_seam_it_asserts() -> None:
    checked = _checked_routes()

    assert _depends_on(checked["/health"], current_user) is True


def test_the_helper_fails_a_route_without_the_seam() -> None:
    """A guard that cannot fail is not a guard."""
    bare = FastAPI()

    @bare.get("/bare")
    async def bare_route(request: Request) -> dict[str, str]:  # pragma: no cover
        return {}

    route = next(
        route
        for route in _leaf_routes(bare.routes)
        if getattr(route, "path", None) == "/bare"
    )

    assert _depends_on(route.dependant, current_user) is False


# --- AP14: no speculative identity column -------------------------------------


def test_no_speculative_identity_column_exists(migrated_db: Path) -> None:
    connection = sqlite3.connect(migrated_db)
    connection.row_factory = sqlite3.Row
    try:
        tables = [
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        ]
        offenders: list[str] = []
        scanned = 0
        for table in tables:
            for column in connection.execute(f"PRAGMA table_info({table})").fetchall():
                scanned += 1
                if str(column["name"]).casefold() in FORBIDDEN_IDENTITY_COLUMNS:
                    offenders.append(f"{table}.{column['name']}")
    finally:
        connection.close()

    assert scanned > 0, "no columns were scanned — the discovered table list is empty"
    assert offenders == [], (
        f"a speculative identity column exists in v1 (AP14): {offenders}"
    )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
