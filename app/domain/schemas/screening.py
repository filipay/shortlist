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

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ScreeningAnswer(BaseModel):
    """One drafted answer and the CV fact ids it claims to be grounded in."""

    model_config = ConfigDict(extra="forbid")

    question: str
    answer: str
    evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def _coerce_evidence_ids(cls, value: Any) -> Any:
        """Tolerate the recorded non-list shapes, and only those (G-07-2).

        A ``None`` becomes an empty list; a bare id string becomes a one-element
        list (comma-separated parts, empties dropped); a ``list``/``tuple`` passes
        through. Every other shape is returned untouched so pydantic still fails
        loudly rather than laundering an unrecognised payload into defaults.
        """
        if value is None:
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        if isinstance(value, (list, tuple)):
            return list(value)
        return value


class ScreeningDraftResponse(BaseModel):
    """What the drafting call returns: one drafted answer per asked question."""

    model_config = ConfigDict(extra="forbid")

    answers: list[ScreeningAnswer] = Field(default_factory=list)

    @field_validator("answers", mode="before")
    @classmethod
    def _coerce_answers(cls, value: Any) -> Any:
        """Tolerate the recorded non-list shapes, and only those (G-07-2).

        A ``None`` becomes an empty list; a single answer-shaped mapping becomes a
        one-element list; a ``list``/``tuple`` passes through. A scalar (a bare
        string, an int, …) is returned untouched so pydantic still fails loudly —
        dropping the whole ``answers`` field to its default would silently discard
        every drafted answer (the M1 hazard).
        """
        if value is None:
            return []
        if isinstance(value, Mapping):
            return [value]
        if isinstance(value, (list, tuple)):
            return list(value)
        return value


__all__ = ["ScreeningAnswer", "ScreeningDraftResponse"]
