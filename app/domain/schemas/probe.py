"""The LLM-backend selftest schema (D-51).

Purpose-built and deliberately small: Phase 5 owns the ranking schema and this
module constrains nothing there. It exists so the tracer can prove the
constrained-output path with a shape whose success is unambiguous.

`extra="ignore"` (RESEARCH §V5): a model that returns an extra field is not a
failure — the wire-adjacent models stay `extra="forbid"`, but a schema-constrained
response is the one place a tolerant model is the honest choice.

**Every field has a default** (Pitfall P11): plan 03-03's salvage path uses
`PydanticUseDefault`, which only works on fields that declare a default. A
required field would silently become the marker object instead.
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
