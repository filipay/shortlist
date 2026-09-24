"""The verification result types (D-111..D-115).

This is its OWN package, NOT under ``app/domain``: the verifier may import
``rapidfuzz`` (06-02 does), and ``tests/test_import_discipline.py`` forbids that
under ``app/domain``. Layer 1 (``plan_checks``) is pure over
``(facts, plan, patch)`` and needs no threshold; the metric/similarity machinery
arrives in 06-02.

``extra="forbid"`` is the redaction control (T-06-07): NO field may carry the
extracted PDF text, the TeX body, or listing prose — only ids, counts, a short
detail sentence and hashes. ``passed`` is a value, never an exception (mirroring
``CompileResult``).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: Bump on ANY check change, so a change here explains a change in outcomes.
VERIFIER_VERSION = "1.0.0"

#: The three check outcomes. Only ``fail`` blocks a compile (D-114).
CheckStatus = Literal["pass", "warn", "fail"]


class CheckResult(BaseModel):
    """One check's outcome. ``offending`` names ids only, never content."""

    model_config = ConfigDict(extra="forbid")

    id: str
    status: CheckStatus
    detail: str
    offending: list[str] = Field(default_factory=list)


class VerificationResult(BaseModel):
    """The whole verification outcome. ``passed`` is a value, never an exception."""

    model_config = ConfigDict(extra="forbid")

    passed: bool
    checks: list[CheckResult] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    #: The Layer-2 extraction hash (empty until 06-02 posts checks over the PDF).
    extracted_text_hash: str = ""
    page_count: int = 0
    verifier_version: str = VERIFIER_VERSION


__all__ = ["VERIFIER_VERSION", "CheckResult", "CheckStatus", "VerificationResult"]
