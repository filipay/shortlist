"""The apply package page (D-120 … D-123) — the phase's protocol surface.

One read-only route:

* ``GET /listings/{listing_id}/apply`` — assembles the package from STORED data
  only: the ``ok`` cv_artifact, ``listing.apply_url`` and the requirement gaps the
  ranking call already stored (D-122/D-123). Opening the page makes NO LLM call;
  drafting is the explicit action whose UI lands in a later plan.

The route computes ONE ``package_state`` (``gated`` | ``ready``) and the template
branches on that only (no lookup, date arithmetic or settings read), mirroring
``app/api/tailoring.py``'s page shape.

* ``gated`` (no ``ok`` cv_artifact, D-121): a ``.tailoring-empty`` panel with
  ``data-state="no-ok-artifact"`` and the ``/listings/{id}/cv`` CTA. The ready
  blocks are absent entirely, never empty shells.
* ``ready`` (an ``ok`` artefact exists): five blocks in order — the no-submit
  reassurance, the outbound plain anchor, the verified-PDF block (unreachable
  while gated), the read-only gap checklist and the ``Record application`` form
  posting to ``/applications/record`` (07-01).

The outbound action is a plain ``<a rel="noopener noreferrer">`` — NEVER a form
POST (APPLY-02 / D-127); no submit path exists anywhere. Every route declares the
identity seam. Jinja autoescape is the only escaping: listing text is untrusted
and nothing here is ever marked safe.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.models import Listing
from app.db.repositories import application_repo, cv_artifact_repo, score_repo
from app.db.session import get_session
from app.domain.models import User
from app.web.template_env import make_templates

router = APIRouter()

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "web" / "templates"
templates = make_templates(TEMPLATE_DIR)

PAGE_TEMPLATE = "html/apply.html"

#: The page's two states (D-121). `gated` is the absence of an `ok` artefact;
#: `ready` is its presence. Computed here, never in the template.
PACKAGE_STATE_GATED = "gated"
PACKAGE_STATE_READY = "ready"

#: The verdicts that read as a gap the CV does not show (D-123). The heading's
#: promise ("What this job asks for that your CV doesn't show") is the filter, so a
#: `met` requirement is deliberately excluded.
GAP_VERDICTS: frozenset[str] = frozenset({"gap", "partial"})


def _not_found() -> HTMLResponse:
    """A small HTML fragment, not a bare JSON 404 — the tailoring route's convention."""
    return HTMLResponse(
        '<div class="tailoring-empty" data-error="unknown-listing">Unknown listing.</div>',
        status_code=404,
    )


@router.get("/listings/{listing_id}/apply", response_class=HTMLResponse)
async def apply_package_page(
    listing_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """The apply package page, or the 404 fragment for an unknown id.

    The `ok` gate is `latest_for_listing(ok_only=True)`: the `compile_status == 'ok'`
    predicate is applied IN SQL (D-118), so a blocked/failed artefact is unreachable
    and the package is `gated`. Everything the ready page renders is read from stored
    rows — no LLM call is made here (D-122).
    """
    listing = await session.get(Listing, listing_id)
    if listing is None:
        return _not_found()

    artifact = await cv_artifact_repo.latest_for_listing(session, listing_id, ok_only=True)
    if artifact is None:
        return templates.TemplateResponse(
            request,
            PAGE_TEMPLATE,
            {
                "listing_id": int(listing.id),
                "listing_title": listing.title,
                "package_state": PACKAGE_STATE_GATED,
            },
        )

    score = await score_repo.read_score_for_listing(session, listing_id)
    requirements = list(score.requirements) if score is not None else []
    gaps = [entry for entry in requirements if entry.get("verdict") in GAP_VERDICTS]
    # The ok-only picker is the SAME SQL-level selection the tracker's picker uses
    # (`application_repo._ok_artifacts_by_listing`), so the two surfaces cannot drift
    # and no second ok-only query is written.
    ok_artifacts = (
        await application_repo._ok_artifacts_by_listing(session, {int(listing.id)})
    ).get(int(listing.id), ())
    return templates.TemplateResponse(
        request,
        PAGE_TEMPLATE,
        {
            "listing_id": int(listing.id),
            "listing_title": listing.title,
            "package_state": PACKAGE_STATE_READY,
            "apply_url": (listing.apply_url or "").strip(),
            "gaps": gaps,
            "statuses": application_repo.APPLICATION_STATUSES,
            "ok_artifacts": ok_artifacts,
            "latest_artifact_id": artifact.id,
        },
    )


__all__ = ["router"]
