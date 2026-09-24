"""The dedicated tailoring page and its actions (D-116).

One path, four routes:

* ``GET /listings/{id}/cv`` — the page shell: generate control (or the ``rank first``
  state), and the latest artifact's state.
* ``POST /listings/{id}/cv/generate`` — one tailoring call; returns the review
  fragment carrying the patch as a hidden ``patch_json`` field. NO artifact row, NO
  ``.tex``, NO PDF (D-108/D-109).
* ``POST /listings/{id}/cv/compile`` — re-parses the client's ``patch_json`` with
  Pydantic, re-grounds it and compiles. A Layer-1 fail short-circuits to a blocked
  row (D-111/D-115).
* ``GET /listings/{id}/cv/pdf`` — serves the latest ``ok`` artifact's PDF inline
  (``?download=1`` sets an attachment disposition). A blocked/failed artifact is
  unreachable because the repository selection is ``ok``-only (D-118).

Every route declares the identity seam (the `user` dependency from `app.api.deps`)
and a request-scoped session. The engine and backend are dependencies so a test can
override them and the default lane never needs a binary or a socket. The PDF path is
built from ``Settings.artifacts_dir`` plus integer ids, NEVER from request text
(T-06-05). Jinja autoescape is the only escaping in the page template.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.api.searches import read_form
from app.config import settings
from app.cv.factstore import CvFactStoreError, load_facts
from app.db.models import Listing
from app.db.repositories import cv_artifact_repo, cv_repo, score_repo
from app.db.session import get_session
from app.domain.cv import InvalidPatchError, TailoringPatch, UnknownIdError, apply_patch, facts_hash
from app.domain.models import User
from app.latex import get_latex_engine
from app.llm import get_llm_backend
from app.pipeline.tailor import (
    CV_FILENAME,
    TAILOR_SKIP_DISABLED,
    TAILOR_SKIP_FACT_STORE,
    TAILOR_SKIP_LABELS,
    TAILOR_SKIP_NO_SCORE,
    compile_tailored,
    tailor_listing,
    tailoring_skip_reason,
)
from app.web.template_env import make_templates

router = APIRouter()

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "web" / "templates"
templates = make_templates(TEMPLATE_DIR)

#: The dedicated page shell (D-116).
PAGE_TEMPLATE = "html/tailoring.html"


def _flag(value: str | None) -> bool:
    """A checkbox-style parameter. Absent, empty and `"0"` are all false."""
    return value is not None and value.strip().casefold() not in {"", "0", "false", "no"}


def _optional_int(value: Any) -> int | None:
    """A whole number, or `None` — never a raised conversion error."""
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _not_found() -> HTMLResponse:
    """A small HTML fragment, not a bare JSON 404 — the events route's convention."""
    return HTMLResponse(
        '<div class="tailoring-empty" data-error="unknown-listing">Unknown listing.</div>',
        status_code=404,
    )


def _error_fragment(reason: str, message: str, status_code: int) -> HTMLResponse:
    """An error fragment targeting the review region, so a swap never empties the DOM."""
    return HTMLResponse(
        f'<div id="tailoring-review" class="tailoring-empty" '
        f'data-error="{html.escape(reason)}">{html.escape(message)}</div>',
        status_code=status_code,
    )


def _review_fragment(
    *,
    listing_id: int,
    patch: TailoringPatch,
    plan: Any,
    base_cv_version_id: int | None,
    fact_store_hash: str,
) -> HTMLResponse:
    """The review fragment: the proposed change log plus the round-trip hidden fields.

    The patch is HTML-escaped into the attribute; the browser restores it verbatim.
    The route never renders a reason as text — it is audit-only (D-108).
    """
    patch_json = html.escape(patch.model_dump_json())
    version_value = "" if base_cv_version_id is None else str(base_cv_version_id)
    items = "".join(
        f"<li><code>{html.escape(change.op)}</code> "
        f"<code>{html.escape(change.target_id)}</code></li>"
        for change in plan.changes
    )
    return HTMLResponse(
        '<div id="tailoring-review" class="tailoring-review">'
        f'<p class="tailoring-review-summary">Proposed changes: {len(plan.changes)}.</p>'
        f'<ul class="change-log">{items}</ul>'
        f'<form method="post" action="/listings/{listing_id}/cv/compile" '
        f'hx-post="/listings/{listing_id}/cv/compile" hx-target="#tailoring-review">'
        f'<input type="hidden" name="patch_json" value="{patch_json}">'
        f'<input type="hidden" name="base_cv_version_id" value="{version_value}">'
        f'<input type="hidden" name="fact_store_hash" value="{html.escape(fact_store_hash)}">'
        '<button type="submit" class="cv-compile">Compile PDF</button>'
        "</form>"
        "</div>"
    )


def _download_fragment(listing_id: int) -> str:
    return (
        '<div id="tailoring-review" class="tailoring-result" data-status="ok">'
        "<p>Compiled.</p>"
        f'<a class="cv-download" href="/listings/{listing_id}/cv/pdf">Download PDF</a>'
        "</div>"
    )


def _findings_fragment(record: cv_artifact_repo.CvArtifactRecord) -> str:
    verification = record.verification_json or {}
    checks = verification.get("checks") or []
    items = "".join(
        f"<li><code>{html.escape(str(check.get('id', '')))}</code> "
        f"<strong>{html.escape(str(check.get('status', '')))}</strong> — "
        f"{html.escape(str(check.get('detail', '')))}</li>"
        for check in checks
        if isinstance(check, dict) and check.get("status") == "fail"
    )
    status = html.escape(record.compile_status)
    return (
        f'<div id="tailoring-review" class="tailoring-result" data-status="{status}">'
        f"<p>Not compiled — {status}.</p>"
        f'<ul class="verification-findings">{items}</ul>'
        "</div>"
    )


@router.get("/listings/{listing_id}/cv", response_class=HTMLResponse)
async def tailoring_page(
    listing_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """The tailoring page shell, or the 404 fragment for an unknown id."""
    listing = await session.get(Listing, listing_id)
    if listing is None:
        return _not_found()

    score = await score_repo.read_score_for_listing(session, listing_id)
    skip_reason = tailoring_skip_reason()
    latest = await cv_artifact_repo.latest_for_listing(session, listing_id, ok_only=False)

    return templates.TemplateResponse(
        request,
        PAGE_TEMPLATE,
        {
            "listing_id": listing_id,
            "listing_title": listing.title,
            "has_score": score is not None,
            "skip_reason": skip_reason,
            "skip_label": TAILOR_SKIP_LABELS.get(skip_reason or "", ""),
            "latest": latest,
        },
    )


@router.post("/listings/{listing_id}/cv/generate", response_class=HTMLResponse)
async def generate_tailored_cv(
    listing_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    backend: Any = Depends(get_llm_backend),
) -> HTMLResponse:
    """Generate exactly one patch; return the review fragment. No artifact row (D-108)."""
    # Parse the body the standard way. The generate form carries no field this plan
    # consumes; it is parsed so a form POST is never left unread.
    await read_form(request)

    listing = await session.get(Listing, listing_id)
    if listing is None:
        return _not_found()
    if not settings.tailoring_enabled:
        return _error_fragment(
            TAILOR_SKIP_DISABLED, TAILOR_SKIP_LABELS[TAILOR_SKIP_DISABLED], 409
        )

    score = await score_repo.read_score_for_listing(session, listing_id)
    if score is None:
        return _error_fragment(
            TAILOR_SKIP_NO_SCORE, TAILOR_SKIP_LABELS[TAILOR_SKIP_NO_SCORE], 422
        )

    try:
        facts = load_facts(Path(settings.cv_dir) / CV_FILENAME)
    except (CvFactStoreError, OSError):
        return _error_fragment(
            TAILOR_SKIP_FACT_STORE, TAILOR_SKIP_LABELS[TAILOR_SKIP_FACT_STORE], 409
        )

    patch = await tailor_listing(
        backend,
        session,
        listing=listing,
        facts=facts,
        requirements=score.requirements,
        now=datetime.now(UTC),
    )
    await session.commit()
    if patch is None:
        return _error_fragment(
            "tailoring_failed",
            "The tailoring call did not return a usable patch. Try again.",
            502,
        )

    try:
        plan = apply_patch(facts, patch)
    except (UnknownIdError, InvalidPatchError) as exc:
        return _error_fragment(
            "invalid-patch",
            f"The model proposed an invalid change ({type(exc).__name__}).",
            502,
        )

    version = await cv_repo.current_version(session)
    return _review_fragment(
        listing_id=listing_id,
        patch=patch,
        plan=plan,
        base_cv_version_id=version.id if version is not None else None,
        fact_store_hash=facts_hash(facts),
    )


@router.post("/listings/{listing_id}/cv/compile", response_class=HTMLResponse)
async def compile_tailored_cv(
    listing_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    engine: Any = Depends(get_latex_engine),
) -> HTMLResponse:
    """Re-parse the client's patch, compile it, persist one artifact row."""
    form = await read_form(request)

    listing = await session.get(Listing, listing_id)
    if listing is None:
        return _not_found()

    raw_patch = form.get("patch_json")
    if not isinstance(raw_patch, str) or not raw_patch.strip():
        return _error_fragment("invalid-patch", "No patch was supplied.", 422)
    try:
        patch = TailoringPatch.model_validate_json(raw_patch)
    except ValidationError:
        return _error_fragment("invalid-patch", "The patch could not be parsed.", 422)

    try:
        facts = load_facts(Path(settings.cv_dir) / CV_FILENAME)
    except (CvFactStoreError, OSError):
        return _error_fragment(
            TAILOR_SKIP_FACT_STORE, TAILOR_SKIP_LABELS[TAILOR_SKIP_FACT_STORE], 409
        )

    record = await compile_tailored(
        session,
        listing=listing,
        facts=facts,
        patch=patch,
        base_cv_version_id=_optional_int(form.get("base_cv_version_id")),
        engine=engine,
        artifacts_dir=Path(settings.artifacts_dir),
        now=datetime.now(UTC),
    )
    await session.commit()

    if record.compile_status == "ok":
        return HTMLResponse(_download_fragment(listing_id))
    return HTMLResponse(_findings_fragment(record))


@router.get("/listings/{listing_id}/cv/pdf")
async def tailored_cv_pdf(
    listing_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Serve the latest `ok` artifact's PDF. A blocked/failed artifact is unreachable."""
    record = await cv_artifact_repo.latest_for_listing(session, listing_id, ok_only=True)
    if record is None or not record.pdf_path:
        return _error_fragment("no-artifact", "No compiled CV for this listing.", 404)

    root = Path(settings.artifacts_dir).resolve()
    path = Path(record.pdf_path).resolve()
    try:
        path.relative_to(root)
    except ValueError:  # pragma: no cover — the path was built from settings + ints
        return _error_fragment("no-artifact", "No compiled CV for this listing.", 404)
    if not path.is_file():
        return _error_fragment("no-artifact", "No compiled CV for this listing.", 404)

    disposition = "attachment" if _flag(request.query_params.get("download")) else "inline"
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{path.name}"'},
    )


__all__ = ["router"]
