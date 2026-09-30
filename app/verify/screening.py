"""The deterministic screening-answer grounding check (D-125).

Two independent, purely deterministic checks over a drafted answer. No LLM, no
network, no clock — the house style of ``app/verify``.

1. **Structural evidence-id intersection.** Every id in an answer's
   ``evidence_ids`` is kept only when it appears byte-exact in
   ``app.domain.cv.iter_fact_ids`` for the loaded document. An id that is not a real
   fact is dropped from the grounded set and produces a warning naming it. This is
   an *enumerated* grounding question ("is this id one of the document's ids?"), not
   the different question ``grounding.evidence_text_for``/``facts_present_in``
   answers ("are all the document's facts present?") — reusing the latter would
   false-fail essentially every short answer, so it is deliberately not used here.
2. **Novel-digit containment.** The answer and the grounding sources (the CV facts
   text rendered exactly as the ranking/tailoring stage renders it for the model,
   plus the listing text) are tokenised with the SAME tokeniser,
   ``app.verify.numbers.digit_cores``. A digit core in the answer that appears in
   neither source is a warning naming the token. This is the metric-fabrication
   catch: an invented number ("97%") is normally absent from the sources.

An optional **advisory** lexical band (``app.verify.grounding.band_for``, the
existing uncalibrated ``tailoring_grounding_*`` thresholds) rides each verdict as a
label. It is advisory by construction and **never** flips the ``unsupported`` state
or the warnings — a fuzzy ratio on a block decision is a false-positive machine.

**Residuals, stated rather than hidden (CONVENTIONS rule 6).** This check is a
warning policy, not a guarantee. Two things it does NOT prove:

* A fabricated narrative that carries no novel digit (prose with no number, or a
  number already present in the sources) passes the numeric check clean. The
  mitigation is the phase's copy-only posture — the human reads and presses send —
  not this check.
* A *computed* number that is genuinely derived from the sources but never appears
  verbatim in them (a total, a difference) is conservatively flagged as novel. That
  is the false-positive direction, chosen deliberately: on a fabrication detector a
  silent miss is worse than a visible warning a human can dismiss.

Consequently this module makes **no absolute guarantee** that a clean verdict means
a fully-grounded answer.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.config import settings
from app.domain.cv import CvFacts, iter_fact_ids
from app.domain.schemas.screening import ScreeningDraftResponse

# The ranking stage's id-bearing CV renderer is the exact text the model is given,
# so the grounding corpus is tokenised from the same source the model saw. This is a
# deliberate cross-module private import (mirroring `app/pipeline/tailor.py`): a
# duplicated renderer would drift from the prompt silently.
from app.pipeline.rank import _cv_facts_text
from app.verify.grounding import GroundingBand, band_for
from app.verify.numbers import digit_cores


class ScreeningVerdict(BaseModel):
    """One answer's grounding outcome. ``unsupported`` is derived from ``warnings``."""

    model_config = ConfigDict(extra="forbid")

    question: str
    answer: str
    #: The answer's evidence ids that resolve byte-exact to a real CV fact id.
    grounded_evidence_ids: list[str] = Field(default_factory=list)
    #: True when any structural or numeric finding was raised (never silent).
    unsupported: bool = False
    #: One human sentence per finding, each naming its offending id or token.
    warnings: list[str] = Field(default_factory=list)
    #: Advisory only — never flips ``unsupported`` (D-125).
    band: GroundingBand = "grounded"


def _sources_text(facts: CvFacts, listing_text: str) -> str:
    """The grounding corpus: the model-visible CV facts text plus the listing text."""
    return "\n".join([_cv_facts_text(facts), listing_text or ""])


def ground_screening_answers(
    facts: CvFacts,
    listing_text: str,
    response: ScreeningDraftResponse,
) -> list[ScreeningVerdict]:
    """Ground every answer in ``response`` and return one verdict per answer.

    Total and deterministic: it never raises and it warns visibly rather than
    skipping. An unknown evidence id and a novel digit core each contribute a warning
    naming the offender; ``unsupported`` is true iff any warning was raised.
    """
    known_ids = set(iter_fact_ids(facts))
    corpus_cores = set(digit_cores(_sources_text(facts, listing_text)))
    grounded_at = settings.tailoring_grounding_threshold
    review_at = settings.tailoring_grounding_review_threshold

    verdicts: list[ScreeningVerdict] = []
    for answer in response.answers:
        warnings: list[str] = []
        grounded_ids: list[str] = []

        for evidence_id in answer.evidence_ids:
            if evidence_id in known_ids:
                grounded_ids.append(evidence_id)
            else:
                warnings.append(
                    f"unsupported evidence id {evidence_id!r}: "
                    "not a fact id in the candidate's CV"
                )

        novel = [
            core for core in digit_cores(answer.answer) if core not in corpus_cores
        ]
        for core in dict.fromkeys(novel):
            warnings.append(
                f"unsupported number {core!r}: "
                "appears in neither the CV facts nor the listing"
            )

        verdicts.append(
            ScreeningVerdict(
                question=answer.question,
                answer=answer.answer,
                grounded_evidence_ids=grounded_ids,
                unsupported=bool(warnings),
                warnings=warnings,
                band=band_for(
                    answer.answer,
                    _sources_text(facts, listing_text),
                    grounded_at=grounded_at,
                    review_at=review_at,
                ),
            )
        )
    return verdicts


__all__ = ["ScreeningVerdict", "ground_screening_answers"]
