"""D-111..D-115 / PITFALLS P2 — the six Layer-2 checks.

One fixture per check: a happy path over the committed extraction, then one
`tests/fixtures/verify/*.txt` sample per failure (or per warn-only) case. Warn-only
checks are asserted to leave `VerificationResult.passed is True`; the declared-drop
case proves a correct absence does not false-fail.
"""

from __future__ import annotations

from app.domain.cv import DropBullet, TailoringPatch
from app.verify import verify_text
from app.verify.base import VERIFIER_VERSION, CheckResult, VerificationResult
from tests.verify.fixtures import VerifyFixture, build_fixture

BULLET3 = "bul/northwind-labs-2021/3"


def _verify(
    extract_name: str = "base_extract.txt",
    *,
    page_count: int = 1,
    patch: TailoringPatch | None = None,
) -> tuple[VerifyFixture, VerificationResult]:
    fixture = build_fixture(patch, extract_name=extract_name, page_count=page_count)
    result = verify_text(
        fixture.facts, fixture.plan, fixture.patch, fixture.text, page_count=fixture.page_count
    )
    return fixture, result


def _check(result: VerificationResult, check_id: str) -> CheckResult:
    return next(check for check in result.checks if check.id == check_id)


# --- happy path ----------------------------------------------------------------


def test_a_valid_extraction_passes_every_layer_two_check() -> None:
    _, result = _verify()

    assert result.passed is True
    assert [check.id for check in result.checks] == [
        "entity_present",
        "metric_containment",
        "injection_residue",
        "page_budget",
        "layout_ats",
        "verbatim_integrity",
    ]
    assert all(check.status == "pass" for check in result.checks)
    assert result.verifier_version == VERIFIER_VERSION
    assert len(result.extracted_text_hash) == 64, "the text is stored as a hash only"
    assert result.page_count == 1


# --- check 2b: entity_present --------------------------------------------------


def test_a_missing_company_name_fails_entity_present() -> None:
    _, result = _verify("missing_entity_extract.txt")

    assert result.passed is False
    assert _check(result, "entity_present").status == "fail"


# --- check 4: metric_containment -----------------------------------------------


def test_a_novel_metric_token_fails_metric_containment() -> None:
    _, result = _verify("novel_metric_extract.txt")

    check = _check(result, "metric_containment")
    assert check.status == "fail"
    assert "exp/northwind-labs-2021:3.12" in check.offending


def test_a_date_core_does_not_fail_metric_containment() -> None:
    _, result = _verify()

    assert _check(result, "metric_containment").status == "pass"


# --- check 7: injection_residue ------------------------------------------------


def test_injection_residue_fails_on_a_matching_line() -> None:
    _, result = _verify("injection_residue_extract.txt")

    assert _check(result, "injection_residue").status == "fail"
    assert result.passed is False


# --- check 8: page_budget (WARN only) ------------------------------------------


def test_a_three_page_extract_only_warns() -> None:
    _, result = _verify("three_page_extract.txt", page_count=3)

    check = _check(result, "page_budget")
    assert check.status == "warn"
    assert result.passed is True


# --- check 9: layout_ats (WARN only) -------------------------------------------


def test_a_missing_heading_warns_for_layout() -> None:
    _, result = _verify("missing_heading_extract.txt")

    assert _check(result, "layout_ats").status == "warn"


# --- check 10: verbatim_integrity ----------------------------------------------


def test_a_reworded_verbatim_bullet_fails_verbatim_integrity() -> None:
    _, result = _verify("reworded_verbatim_extract.txt")

    assert _check(result, "verbatim_integrity").status == "fail"
    assert result.passed is False


# --- P2: a declared drop is a correct absence ----------------------------------


def test_a_declared_drop_is_not_a_missing_bullet() -> None:
    patch = TailoringPatch(
        listing_id=1,
        ops=[DropBullet(op="drop_bullet", bullet_id=BULLET3, reason="not relevant here")],
    )

    _, result = _verify(patch=patch)

    assert result.passed is True
    assert _check(result, "entity_present").status == "pass"
    assert _check(result, "verbatim_integrity").status == "pass"


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
