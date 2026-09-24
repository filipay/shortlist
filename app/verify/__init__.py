"""The verification package (D-111..D-115).

Its OWN package, NOT under ``app/domain``: the verifier may import ``rapidfuzz``
(the advisory grounding band), and ``tests/test_import_discipline.py`` forbids that
under ``app/domain``. Layer 1 (the deterministic pre-check) lives in ``plan_checks``;
Layer 2 (the extracted-PDF-text post-checks, the metric tokeniser and the advisory
similarity band) lives in ``text_checks``, ``numbers`` and ``grounding``.
"""

from app.verify.base import (
    VERIFIER_VERSION,
    CheckResult,
    CheckStatus,
    VerificationResult,
)
from app.verify.grounding import GroundingBand, band_for, evidence_text_for
from app.verify.numbers import (
    RegionReport,
    date_like_cores_for_entry,
    digit_cores,
    is_page_number_line,
    region_token_report,
)
from app.verify.plan_checks import verify_plan
from app.verify.text_checks import verify_text

__all__ = [
    "VERIFIER_VERSION",
    "CheckResult",
    "CheckStatus",
    "GroundingBand",
    "RegionReport",
    "VerificationResult",
    "band_for",
    "date_like_cores_for_entry",
    "digit_cores",
    "evidence_text_for",
    "is_page_number_line",
    "region_token_report",
    "verify_plan",
    "verify_text",
]
