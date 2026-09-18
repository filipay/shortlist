"""The LLM-backend selftest schema (D-51).

Purpose-built and deliberately small: Phase 5 owns the ranking schema and this
module constrains nothing there. It exists so the tracer can prove the
constrained-output path with a shape whose success is unambiguous.

`extra="ignore"` (RESEARCH §V5): a model that returns an extra field is not a
failure — the wire-adjacent models stay `extra="forbid"`, but a schema-constrained
response is the one place a tolerant model is the honest choice.

**Every field has a default** (Pitfall P11): plan 03-03's salvage path removes
the offending field from a copy of the input and validates again, so a field
that declares a default takes it. A required field would re-raise instead of
receiving a value the model never supplied.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ProbeResult(BaseModel):
    """What the selftest asks the model to acknowledge."""

    model_config = ConfigDict(extra="ignore")

    acknowledged: bool = False
    instruction_detected: bool = False
    echo: str = ""


__all__ = ["ProbeResult"]
