"""D-111..D-115 / PITFALLS P2 — the six Layer-2 checks.

One fixture per check: a happy path over the committed extraction, then one
`tests/fixtures/verify/*.txt` sample per failure (or per warn-only) case. Warn-only
checks are asserted to leave `VerificationResult.passed is True`; the declared-drop
case proves a correct absence does not false-fail.
"""

from __future__ import annotations

from app.domain.cv import (
    DropBullet,
    RenderPlan,
    RenderedEntry,
    RenderedSection,
    TailoringPatch,
)
from app.verify import verify_text
from app.verify.base import VERIFIER_VERSION, CheckResult, VerificationResult
from app.verify.text_checks import check_metric_containment
from tests.verify.fixtures import (
    VerifyFixture,
    build_fixture,
    load_standin_facts,
    with_digit_location,
    with_digit_skill,
)

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


def test_a_digit_bearing_skill_label_still_passes_metric_containment() -> None:
    """CR-01: a valid CV whose Skills block carries an ordinary digit-bearing label passes.

    The digit is grounded in the region that renders the skill label, so it is not a
    surplus candidate. ``entity_present``/``layout_ats`` are asserted too: their
    org/title/date strings must still match the extraction, so a fixture typo cannot
    make this pass by accident.
    """
    facts = with_digit_skill(load_standin_facts())
    fixture = build_fixture(facts=facts, extract_name="digit_skill_extract.txt")

    result = verify_text(
        fixture.facts, fixture.plan, fixture.patch, fixture.text, page_count=fixture.page_count
    )

    assert _check(result, "metric_containment").status == "pass"
    assert _check(result, "entity_present").status == "pass"
    assert _check(result, "layout_ats").status == "pass"
    assert result.passed is True


def test_a_digit_bearing_location_still_passes_metric_containment() -> None:
    """CR-01: a valid CV whose entry location carries a digit passes every check.

    The location digit is grounded in the region that renders it, so check 4 does not
    false-fail. ``entity_present``/``layout_ats`` are asserted too so a fixture typo
    cannot make this pass by accident.
    """
    facts = with_digit_location(load_standin_facts())
    fixture = build_fixture(facts=facts, extract_name="digit_location_extract.txt")

    result = verify_text(
        fixture.facts, fixture.plan, fixture.patch, fixture.text, page_count=fixture.page_count
    )

    assert _check(result, "metric_containment").status == "pass"
    assert _check(result, "entity_present").status == "pass"
    assert _check(result, "layout_ats").status == "pass"
    assert result.passed is True


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


# --- ESC-06-B / WR-01: an unanchorable region fails closed ----------------------


def test_an_unanchorable_region_is_a_visible_warn_not_a_silent_skip() -> None:
    """A region the check cannot anchor must surface as a warn, never a silent pass.

    The empty/all-punctuation-title case makes ``squash(title)`` empty, so no
    structural start is found and the region has no candidates. A fabricated ``99``
    inside it must not disappear: it is named in the check's ``offending``.
    """
    entry = RenderedEntry(
        id="exp/acme-2020",
        org="Acme",
        title="",
        dates="2020-01 -- 2021-01",
        bullets=[],
    )
    plan = RenderPlan(
        sections=[
            RenderedSection(id="sec.experience", title="Experience", entries=[entry])
        ]
    )
    text = "Acme\n2020-01 -- 2021-01\nReduced latency 99%\n"

    check = check_metric_containment(plan, text, page_count=1)

    assert check.status == "warn"
    assert "exp/acme-2020" in check.offending


def test_a_fabricated_digit_in_an_unanchorable_region_is_not_reported_pass() -> None:
    """A wrapped org+title header is unanchorable, but a fabricated digit is visible.

    Both strings are document-wide, so ``entity_present`` passes; the header wraps
    across two extraction lines, so check 4 cannot anchor the region. The fabricated
    ``99`` must yield a ``warn`` (never ``pass``) and the entry must be named — while
    ``passed`` stays ``True`` because a warn never blocks.
    """
    entry = RenderedEntry(
        id="exp/acme-2020",
        org="Acme Corporation",
        title="Senior Software Engineer",
        dates="2020-01 -- 2021-01",
        bullets=[],
    )
    plan = RenderPlan(
        sections=[
            RenderedSection(id="sec.experience", title="Experience", entries=[entry])
        ]
    )
    text = (
        "Alex Example\n"
        "Experience\n"
        "Acme Corporation --- Senior\n"
        "Software Engineer\n"
        "2020-01 -- 2021-01\n"
        "Reduced latency 99%\n"
    )
    facts = load_standin_facts()
    patch = TailoringPatch(listing_id=1)

    result = verify_text(facts, plan, patch, text, page_count=1)

    assert _check(result, "entity_present").status == "pass"
    check = _check(result, "metric_containment")
    assert check.status == "warn"
    assert "exp/acme-2020" in check.offending
    assert result.passed is True


def test_an_unanchored_region_does_not_hide_an_anchored_surplus() -> None:
    """``fail`` wins over ``warn``: an anchored surplus still hard-fails check 4."""
    entry_a = RenderedEntry(
        id="exp/northwind-labs-2021",
        org="Northwind Labs",
        title="Senior Engineer",
        dates="2021-03 -- 2024-09",
        bullets=[],
    )
    entry_b = RenderedEntry(
        id="exp/acme-2019",
        org="Acme",
        title="",
        dates="2019-01 -- 2019-12",
        bullets=[],
    )
    plan = RenderPlan(
        sections=[
            RenderedSection(
                id="sec.experience",
                title="Experience",
                entries=[entry_a, entry_b],
            )
        ]
    )
    text = (
        "Northwind Labs --- Senior Engineer\n"
        "2021-03 -- 2024-09\n"
        "Reduced latency 99%\n"
        "Acme --- \n"
    )

    check = check_metric_containment(plan, text, page_count=1)

    assert check.status == "fail"
    assert "exp/northwind-labs-2021:99" in check.offending


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
