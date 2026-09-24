"""The verification package (D-111..D-115).

Its OWN package, NOT under ``app/domain``: the verifier may import ``rapidfuzz``
(06-02 does), and ``tests/test_import_discipline.py`` forbids that under
``app/domain``. Layer 1 (the deterministic pre-check) lives in ``plan_checks``;
Layer 2 (the PDF-text post-checks, the metric tokeniser and the advisory
similarity band) follows in 06-02.
"""

from app.verify.base import (
    VERIFIER_VERSION,
    CheckResult,
    CheckStatus,
    VerificationResult,
)
from app.verify.plan_checks import verify_plan

__all__ = [
    "VERIFIER_VERSION",
    "CheckResult",
    "CheckStatus",
    "VerificationResult",
    "verify_plan",
]
