"""The apply package page (D-120 … D-127) — the phase's protocol surface.

One read-only page and three explicit actions:

* ``GET /listings/{listing_id}/apply`` — assembles the package from STORED data
  only: the ``ok`` cv_artifact, ``listing.apply_url``, the requirement gaps the
  ranking call already stored (D-122/D-123) and the stored screening drafts
  (D-124/D-126). Opening the page makes NO LLM call; drafting is the explicit
  action below.
* ``POST /listings/{listing_id}/apply/draft`` — ONE guarded drafting call
  (``app.pipeline.draft``), persisted through ``screening_draft_repo``.
* ``POST /listings/{listing_id}/apply/question`` — append an ad-hoc question.
* ``POST /listings/{listing_id}/apply/draft/delete`` — remove ONE drafted answer,
  scoped to its listing.

The page route computes ONE ``package_state`` (``gated`` | ``ready``) and the
template branches on that only (no lookup, date arithmetic or settings read),
mirroring ``app/api/tailoring.py``'s page shape.

* ``gated`` (no ``ok`` cv_artifact, D-121): a ``.tailoring-empty`` panel with
  ``data-state="no-ok-artifact"`` and the ``/listings/{id}/cv`` CTA. The ready
  blocks are absent entirely, never empty shells.
* ``ready`` (an ``ok`` artefact exists): the no-submit reassurance, the outbound
  plain anchor, the verified-PDF block, the read-only gap checklist, the
  ``#apply-answers`` drafted-answers region and the ``Record application`` form.

Consumption is copy-only per answer (D-127): the outbound action is a plain
``<a rel="noopener noreferrer">`` — NEVER a form POST — and no submit path exists
anywhere (APPLY-02). Jinja autoescape is the only escaping: listing text and model
answers are untrusted and nothing here is ever marked safe, and an answer renders as
TEXT (never ``|safe``, never an input value) so it stays selectable with JS off.
Every route declares the identity seam.
"""

from __future__ import annotations

import html
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.api.searches import read_form
from app.config import settings
from app.cv.factstore import CvFactStoreError, load_facts
from app.db.models import Listing
from app.db.repositories import (
    application_repo,
    apply_config_repo,
    cv_artifact_repo,
    score_repo,
    screening_draft_repo,
)
from app.db.repositories.queue_repo import http_url
from app.db.repositories.screening_draft_repo import ScreeningDraftInput
from app.db.session import get_session
from app.domain.models import User
from app.llm import get_llm_backend
from app.llm.base import LLMBackend
from app.pipeline.draft import (
    DRAFT_SKIP_FACT_STORE,
    DRAFT_SKIP_LABELS,
    draft_screening_answers,
    drafting_skip_reason,
)
from app.pipeline.rank import CV_FILENAME
from app.web.template_env import make_templates

router = APIRouter()

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "web" / "templates"
templates = make_templates(TEMPLATE_DIR)

PAGE_TEMPLATE = "html/apply.html"
#: The `#apply-answers` region: the page includes it, and each action swaps it back in.
ANSWERS_TEMPLATE = "html/_screening_drafts.html"

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


def _answers_error(reason: str, message: str, status_code: int) -> HTMLResponse:
    """An error fragment targeting the answers region, so a swap never empties the DOM.

    Mirrors ``app/api/tailoring.py``'s ``_error_fragment`` but carries the
    ``#apply-answers`` id the region owns. Both values are escaped here.
    """
    return HTMLResponse(
        f'<div id="apply-answers" class="tailoring-empty" '
        f'data-error="{html.escape(reason)}">{html.escape(message)}</div>',
        status_code=status_code,
    )


def _int_or_none(value: Any) -> int | None:
    """A whole number, or ``None`` — never a raised conversion error."""
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _one_row(question: str, draft: Any) -> dict[str, Any]:
    """One rendered answer block: the question plus its stored draft, if any."""
    if draft is None:
        return {
            "question": question,
            "answer": None,
            "evidence": [],
            "unsupported": False,
            "draft_id": None,
        }
    evidence = draft.evidence_json
    return {
        "question": question,
        "answer": draft.answer_text,
        "evidence": list(evidence) if isinstance(evidence, list) else [],
        "unsupported": bool(draft.unsupported),
        "draft_id": int(draft.id),
    }


def _answer_rows(questions: Sequence[str], drafts: Sequence[Any]) -> list[dict[str, Any]]:
    """The merged question set, in saved order, ad-hoc drafts appended (D-124).

    The config list comes first, each matched to its stored draft by question text;
    any draft whose question is not in that list (an ad-hoc add) is appended after it,
    in draft order. A question with no row renders "Not yet drafted.".
    """
    by_question = {draft.question_text: draft for draft in drafts}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for question in questions:
        if question in seen:
            continue
        seen.add(question)
        rows.append(_one_row(question, by_question.get(question)))
    for draft in drafts:
        if draft.question_text in seen:
            continue
        seen.add(draft.question_text)
        rows.append(_one_row(draft.question_text, draft))
    return rows


async def _answers_context(session: AsyncSession, listing_id: int) -> dict[str, Any]:
    """The `#apply-answers` region context, shared by the page and every action.

    One read backs both surfaces, so the page's region and a swapped region cannot
    disagree. Opening/re-rendering makes no model call (D-122).
    """
    drafts = await screening_draft_repo.read_for_listing(session, listing_id)
    questions = await apply_config_repo.read_questions(session)
    return {"listing_id": int(listing_id), "answer_rows": _answer_rows(questions, drafts)}


async def _answers_response(
    request: Request, session: AsyncSession, listing_id: int
) -> HTMLResponse:
    """Re-render the `#apply-answers` region alone, for an HTMX swap."""
    return templates.TemplateResponse(
        request, ANSWERS_TEMPLATE, await _answers_context(session, listing_id)
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
    # (`application_repo.ok_artifacts_by_listing`), so the two surfaces cannot drift
    # and no second ok-only query is written.
    ok_artifacts = (
        await application_repo.ok_artifacts_by_listing(session, {int(listing.id)})
    ).get(int(listing.id), ())
    context: dict[str, Any] = {
        "listing_id": int(listing.id),
        "listing_title": listing.title,
        "package_state": PACKAGE_STATE_READY,
        # `listing.apply_url` is stored raw from untrusted scraper output and an
        # anchor's `javascript:`/`data:` scheme is NOT blocked by Jinja autoescape,
        # so it goes through the queue's existing http(s) scheme gate (CR-01).
        "apply_url": http_url(listing.apply_url),
        "gaps": gaps,
        "statuses": application_repo.APPLICATION_STATUSES,
        "ok_artifacts": ok_artifacts,
        "latest_artifact_id": artifact.id,
    }
    # The drafted-answers region (D-124/D-126): the merged question set and the stored
    # answers, read from stored rows only. No LLM call on open.
    context.update(await _answers_context(session, int(listing.id)))
    return templates.TemplateResponse(request, PAGE_TEMPLATE, context)


@router.post("/listings/{listing_id}/apply/draft", response_class=HTMLResponse)
async def draft_answers(
    listing_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    backend: LLMBackend = Depends(get_llm_backend),
) -> HTMLResponse:
    """Draft the merged question set with ONE guarded, audited model call (D-125).

    The operator switch is honoured BEFORE any model call: ``drafting_skip_reason()``
    reports a disabled switch or an absent fact store, which is returned as the shared
    skip vocabulary in a ``data-error`` fragment. A ``None`` result from the stage (a
    transport error, a cap refusal, or no usable response) is a 502 refusal that writes
    no draft rows — the stage has already written its one audit row, and it is
    committed here before the refusal so the attempt survives.
    """
    await read_form(request)

    listing = await session.get(Listing, listing_id)
    if listing is None:
        return _not_found()

    # WR-01: the same `ok` gate the page enforces (D-121), re-checked server-side.
    # The page-only gate is not an authorization boundary: a direct POST must not
    # spend a model call or persist rows for a listing with no verified CV.
    artifact = await cv_artifact_repo.latest_for_listing(session, listing_id, ok_only=True)
    if artifact is None:
        return _answers_error("no-ok-artifact", "Tailor and verify a CV first.", 409)

    skip = drafting_skip_reason()
    if skip is not None:
        return _answers_error(skip, DRAFT_SKIP_LABELS.get(skip, skip), 409)

    drafts = await screening_draft_repo.read_for_listing(session, listing_id)
    questions = await apply_config_repo.read_questions(session)
    questions += [
        draft.question_text for draft in drafts if draft.question_text not in questions
    ]

    try:
        facts = load_facts(Path(settings.cv_dir) / CV_FILENAME)
    except (CvFactStoreError, OSError):
        return _answers_error(
            DRAFT_SKIP_FACT_STORE,
            DRAFT_SKIP_LABELS.get(DRAFT_SKIP_FACT_STORE, "no readable CV fact store"),
            409,
        )

    verdicts = await draft_screening_answers(
        backend,
        session,
        listing=listing,
        facts=facts,
        questions=questions,
        now=datetime.now(UTC),
    )
    # Commit unconditionally: the stage already wrote its one audit row for this
    # ATTEMPT, and it must survive a refusal (mirrors the tailor generate route).
    await session.commit()
    # WR-03: `None` is a failed call; an empty list is a valid-but-useless response
    # (`ScreeningDraftResponse.answers` defaults to `[]`). Neither is a regeneration:
    # `replace_for_listing([])` would delete the user's stored answers with no warning.
    if not verdicts:
        return _answers_error(
            "drafting_empty",
            "The drafting call returned no answers. Your existing drafts were kept.",
            502,
        )

    await screening_draft_repo.replace_for_listing(
        session,
        listing_id=int(listing.id),
        drafts=[
            ScreeningDraftInput(
                question_text=verdict.question,
                answer_text=verdict.answer,
                evidence_json=verdict.grounded_evidence_ids,
                unsupported=verdict.unsupported,
            )
            for verdict in verdicts
        ],
        now=datetime.now(UTC),
    )
    await session.commit()
    return await _answers_response(request, session, int(listing.id))


@router.post("/listings/{listing_id}/apply/question", response_class=HTMLResponse)
async def add_question(
    listing_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Append one ad-hoc question for this listing (answer NULL), then re-render.

    The question is user input, never inferred from the listing text (D-124). A blank
    or already-known question changes nothing. Appending reuses ``replace_for_listing``
    (no new repository surface), preserving the existing rows and their order.
    """
    form = await read_form(request)

    listing = await session.get(Listing, listing_id)
    if listing is None:
        return _not_found()

    # WR-01: keep the package's actions consistent with the package's availability.
    artifact = await cv_artifact_repo.latest_for_listing(session, listing_id, ok_only=True)
    if artifact is None:
        return _answers_error("no-ok-artifact", "Tailor and verify a CV first.", 409)

    raw = form.get("question")
    question = raw.strip() if isinstance(raw, str) else ""
    if question:
        drafts = await screening_draft_repo.read_for_listing(session, listing_id)
        known = {draft.question_text for draft in drafts} | set(
            await apply_config_repo.read_questions(session)
        )
        if question not in known:
            inputs = [
                ScreeningDraftInput(
                    question_text=draft.question_text,
                    answer_text=draft.answer_text,
                    evidence_json=draft.evidence_json,
                    unsupported=draft.unsupported,
                )
                for draft in drafts
            ]
            inputs.append(ScreeningDraftInput(question_text=question))
            await screening_draft_repo.replace_for_listing(
                session, listing_id=int(listing.id), drafts=inputs, now=datetime.now(UTC)
            )
            await session.commit()

    return await _answers_response(request, session, int(listing.id))


@router.post("/listings/{listing_id}/apply/draft/delete", response_class=HTMLResponse)
async def delete_answer(
    listing_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Remove ONE drafted answer, scoped to this listing (the phase's only deletion).

    ``delete_draft`` is scoped by ``listing_id`` as well as ``draft_id``, so a
    foreign/absent id writes nothing and is a ``data-error`` refusal. The plain
    (non-HTMX) form posts here and the response is the re-rendered region.
    """
    form = await read_form(request)

    listing = await session.get(Listing, listing_id)
    if listing is None:
        return _not_found()

    # WR-01: keep the package's actions consistent with the package's availability.
    artifact = await cv_artifact_repo.latest_for_listing(session, listing_id, ok_only=True)
    if artifact is None:
        return _answers_error("no-ok-artifact", "Tailor and verify a CV first.", 409)

    draft_id = _int_or_none(form.get("draft_id"))
    if draft_id is None:
        return _answers_error("bad-draft-id", "No drafted answer was named.", 422)

    removed = await screening_draft_repo.delete_draft(
        session, listing_id=int(listing.id), draft_id=draft_id
    )
    await session.commit()
    if not removed:
        return _answers_error(
            "unknown-draft", "That drafted answer was not found for this listing.", 404
        )
    return await _answers_response(request, session, int(listing.id))


__all__ = ["router"]
