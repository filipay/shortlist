"""The ranking response schema — six top-level scalars and a requirement list.

Purpose-built for the ranking call (D-78 / D-81). The shape is **load-bearing**:

* **Top-level scalars, never a nested factor object.** ``app/llm/opencode_server.py``
  ``_tolerant_validator`` substitutes a field default only for errors whose ``loc``
  length is 1 and whose type is in ``TOLERATED_SCHEMA_ERRORS``. A nested object
  would make a truncated response unrecoverable and re-raise as ``invalid``, so a
  partial answer would cost the whole listing its score.
* **No ``total`` field.** The total is computed in code from the sub-scores and the
  weights in force (D-78), which is what makes a weight change re-derive rankings
  with zero new LLM calls (D-100).
* **``-1.0`` means absent.** Each factor defaults to ``-1.0``; ``0.0`` is a real
  sub-score and must never be read as "no data" (D-85). The ``ge``/``le`` bounds
  make an out-of-range value a validation failure rather than a clamped one
  (RANK-02 precision).
* **``extra="ignore"``** (RESEARCH §V5): a model that returns an unrecognised extra
  key is not a failure — the wire-adjacent models stay ``extra="forbid"``, but a
  schema-constrained response is the one place a tolerant model is honest. The
  extra key is dropped by pydantic and can never reach ``factor_scores_json``.
* **Every field has a default** (Pitfall P11): the salvage path removes an offending
  top-level field from a copy of the input and validates again, so a field that
  declares a default takes it rather than re-raising.

The requirement list is co-located with the sub-scores (D-81): one
``complete_structured`` response returns both, so the fit breakdown is guaranteed
to match the score that used it and Phase 6 reads the stored list instead of
re-extracting it.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ._coerce import coerce_mapping_list

#: A factor sub-score. ``-1.0`` is the absent sentinel; the bounds reject rather
#: than clamp an out-of-range value (RANK-02 precision).
_SubScore = Annotated[float, Field(ge=-1.0, le=1.0)]


class RequirementFit(BaseModel):
    """One requirement the listing states and how well the CV meets it.

    ``evidence_id`` names a fact in the loaded CV document, or is ``None`` for a
    gap. It is only ever a *claim* at this layer: the ranking stage grounds every
    id against ``app.domain.cv.iter_fact_ids`` **before** persisting, so a
    fabricated id can never reach a ``scores`` row (RANK-05 / the never-fabricate
    hard line).
    """

    model_config = ConfigDict(extra="ignore")

    text: str = ""
    verdict: Literal["met", "partial", "gap"] = "gap"
    evidence_id: str | None = None


class RankingResponse(BaseModel):
    """What the ranking call returns: six sub-scores, a rationale, and the fits."""

    model_config = ConfigDict(extra="ignore")

    skills: _SubScore = -1.0
    seniority: _SubScore = -1.0
    domain: _SubScore = -1.0
    location: _SubScore = -1.0
    evidence: _SubScore = -1.0
    compensation: _SubScore = -1.0
    rationale: str = ""
    requirements: list[RequirementFit] = Field(default_factory=list)

    @field_validator("requirements", mode="before")
    @classmethod
    def _coerce_requirements(cls, value: Any) -> Any:
        """Route the recorded wire shapes through the shared helper (G-07-7).

        A single-key wrapper ``{"item": [...]}`` is unwrapped; ``None`` -> ``[]``; a
        single requirement-shaped mapping -> ``[value]`` and a ``list``/``tuple``
        passes through. Any other shape is returned untouched and fails loudly.
        """
        return coerce_mapping_list(value)


__all__ = ["RankingResponse", "RequirementFit"]
