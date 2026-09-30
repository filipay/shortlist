"""The screening-drafting response schema (D-125).

Purpose-built and small, beside ``probe.py`` and ``ranking.py``. The shape is
**load-bearing** for the fabrication boundary:

* ``extra="forbid"`` (A4): the repo-wide contract rule for wire-adjacent models, so
  an unrecognised key fails the call rather than being silently dropped. This is the
  stronger fabrication posture — the model cannot smuggle an extra field past the
  persisted contract.
* ``ScreeningAnswer.evidence_ids`` names the CV fact ids the answer used. The ids
  are a *claim* at this layer: ``app.verify.screening`` re-grounds every id
  byte-exact against ``app.domain.cv.iter_fact_ids`` before anything is persisted, so
  a fabricated id can never reach a ``screening_drafts`` row.

``answers`` defaults to an empty list so a model that returns no answers is a valid
(if useless) response, not a re-raise — mirroring the tolerant-default rule the
ranking schema documents (Pitfall P11).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ScreeningAnswer(BaseModel):
    """One drafted answer and the CV fact ids it claims to be grounded in."""

    model_config = ConfigDict(extra="forbid")

    question: str
    answer: str
    evidence_ids: list[str] = Field(default_factory=list)


class ScreeningDraftResponse(BaseModel):
    """What the drafting call returns: one drafted answer per asked question."""

    model_config = ConfigDict(extra="forbid")

    answers: list[ScreeningAnswer] = Field(default_factory=list)


__all__ = ["ScreeningAnswer", "ScreeningDraftResponse"]
