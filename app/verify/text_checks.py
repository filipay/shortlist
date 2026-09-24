"""Layer 2 verification — the extracted-PDF-text post-checks (D-111..D-115).

This runs AFTER a successful compile, over the raw text ``pypdf`` extracts
(``app/latex/compile.py:extract_pdf_text``), and is the second line of defence
(ARCHITECTURE §10.5): Layer 1 checks the plan the renderer was handed; Layer 2 checks
what the PDF a human and an ATS actually read.

The six checks (D-112..D-114):

- ``entity_present`` (check 2b) — every STRUCTURED org/title/section-title string from
  the plan is present. ``bullet.text`` is human-authored and immutable and is never
  scanned for proper nouns (D-112).
- ``metric_containment`` (check 4) — per region, every surviving digit core must be
  one of that region's source tokens (D-113, ``app/verify/numbers.py``).
- ``injection_residue`` (check 7) — no ingest pattern matches. It reuses the single
  ``INJECTION_PATTERNS`` list; a second list must never be minted.
- ``page_budget`` (check 8) — WARN only, never fails (D-114): a two-page CV against a
  one-page budget still downloads.
- ``layout_ats`` (check 9) — WARN only. The single-column property is a template
  invariant asserted in code, not something extracted text can settle.
- ``verbatim_integrity`` (check 10) — every plan bullet whose ``evidence`` is
  ``"verbatim"`` is present byte-for-byte after normalisation.

``passed`` is ``no check has status "fail"`` — a value, never an exception. Checks 2b
and 10 iterate the RENDERPLAN's surviving bullets, never ``facts.all_entries()`` and
never ``facts_present_in`` verbatim: a declared drop is a correct absence (PITFALLS P2).

``patch`` and ``now`` are accepted for a signature symmetrical with ``verify_plan`` and
to keep the one pipeline call site identical across layers; neither influences a Layer-2
predicate (check 6's advisory band is Layer 1's).
"""

from __future__ import annotations

import hashlib
from datetime import datetime

from app.domain.cv import CvFacts, RenderPlan, TailoringPatch
from app.domain.sanitize import INJECTION_PATTERNS
from app.domain.tex import normalise_for_compare, squash
from app.verify.base import CheckResult, VerificationResult
from app.verify.numbers import region_token_report

#: The evidence label that makes a bullet's presence a hard requirement (check 10).
_VERBATIM = "verbatim"


def _fail(check_id: str, detail: str, offending: list[str]) -> CheckResult:
    return CheckResult(id=check_id, status="fail", detail=detail, offending=offending)


def _warn(check_id: str, detail: str, offending: list[str]) -> CheckResult:
    return CheckResult(id=check_id, status="warn", detail=detail, offending=offending)


def _pass(check_id: str, detail: str) -> CheckResult:
    return CheckResult(id=check_id, status="pass", detail=detail)


def check_entity_present(plan: RenderPlan, text: str) -> CheckResult:
    """Check 2b — every structured org/title/section-title is present (D-112).

    ``offending`` names fact ids only, never content.
    """
    squashed = squash(text)
    offending: list[str] = []
    for section in plan.sections:
        if squash(section.title) not in squashed:
            offending.append(section.id)
        for entry in section.entries:
            if squash(entry.org) not in squashed or squash(entry.title) not in squashed:
                offending.append(entry.id)
    if offending:
        return _fail(
            "entity_present",
            f"{len(offending)} structured string(s) are absent from the rendered text",
            sorted(set(offending)),
        )
    return _pass("entity_present", "every structured string is present in the rendered text")


def check_metric_containment(plan: RenderPlan, text: str, *, page_count: int) -> CheckResult:
    """Check 4 — every region's surviving digit core is one of its source tokens."""
    offending: list[str] = []
    for report in region_token_report(plan, text, page_count=page_count):
        if not report.found:
            # An absent org is an ``entity_present`` failure, not a metric failure.
            continue
        allowed = set(report.allowed)
        surplus = sorted({core for core in report.candidates if core not in allowed})
        offending.extend(f"{report.entry_id}:{core}" for core in surplus)
    if offending:
        return _fail(
            "metric_containment",
            f"{len(offending)} numeric token(s) are absent from their region's source facts",
            sorted(set(offending)),
        )
    return _pass("metric_containment", "every numeric token is grounded in its region's facts")


def check_injection_residue(text: str) -> CheckResult:
    """Check 7 — no ingest pattern matches the rendered text (D-38's list, reused)."""
    normalised = normalise_for_compare(text)
    matched = sorted(
        {pattern.pattern for pattern in INJECTION_PATTERNS if pattern.search(normalised)}
    )
    if matched:
        return _fail(
            "injection_residue",
            f"{len(matched)} ingest pattern(s) match the rendered text",
            matched,
        )
    return _pass("injection_residue", "no ingest pattern matches the rendered text")


def check_page_budget(facts: CvFacts, *, page_count: int) -> CheckResult:
    """Check 8 — ``page_count <= facts.meta.max_pages``. WARN only (D-114)."""
    limit = facts.meta.max_pages
    if page_count > limit:
        return _warn(
            "page_budget",
            f"the rendered CV is {page_count} page(s) against a budget of {limit}",
            [],
        )
    return _pass("page_budget", f"the rendered CV is within the {limit}-page budget")


def check_layout_ats(plan: RenderPlan, text: str) -> CheckResult:
    """Check 9 — section headings and entry date ranges present. WARN only.

    The single-column property is a CODE-level template invariant, not a text
    observable: the committed template defines no columns (it imports ``paracol`` but
    never opens a ``multicols``/``paracol`` environment), so there is nothing to read
    back from the extraction. This check therefore only reports what the text can
    settle, and it never blocks.
    """
    squashed = squash(text)
    offending: list[str] = []
    for section in plan.sections:
        if squash(section.title) not in squashed:
            offending.append(section.id)
        for entry in section.entries:
            if squash(entry.dates) not in squashed:
                offending.append(entry.id)
    if offending:
        return _warn(
            "layout_ats",
            f"{len(offending)} layout element(s) are absent from the rendered text",
            sorted(set(offending)),
        )
    return _pass("layout_ats", "every section heading and date range is present")


def check_verbatim_integrity(plan: RenderPlan, text: str) -> CheckResult:
    """Check 10 — every ``verbatim`` plan bullet is present, byte-for-byte (D-112/P2).

    Iterates the RenderPlan's SURVIVING bullets: a declared drop is a correct absence,
    not a missing bullet.
    """
    squashed = squash(text)
    offending: list[str] = []
    for section in plan.sections:
        for entry in section.entries:
            for bullet in entry.bullets:
                if bullet.evidence == _VERBATIM and squash(bullet.text) not in squashed:
                    offending.append(bullet.id)
    if offending:
        return _fail(
            "verbatim_integrity",
            f"{len(offending)} verbatim bullet(s) are absent from the rendered text",
            sorted(offending),
        )
    return _pass("verbatim_integrity", "every verbatim bullet is present")


def verify_text(
    facts: CvFacts,
    plan: RenderPlan,
    patch: TailoringPatch,
    text: str,
    *,
    page_count: int,
    now: datetime | None = None,
) -> VerificationResult:
    """Run every Layer-2 check and return the aggregate. ``passed`` iff none failed."""
    checks = [
        check_entity_present(plan, text),
        check_metric_containment(plan, text, page_count=page_count),
        check_injection_residue(text),
        check_page_budget(facts, page_count=page_count),
        check_layout_ats(plan, text),
        check_verbatim_integrity(plan, text),
    ]
    passed = all(check.status != "fail" for check in checks)
    return VerificationResult(
        passed=passed,
        checks=checks,
        # The hash ONLY — the extracted text is never persisted (T-06-11).
        extracted_text_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        page_count=page_count,
        verifier_version=VerificationResult.model_fields["verifier_version"].default,
    )


__all__ = [
    "check_entity_present",
    "check_injection_residue",
    "check_layout_ats",
    "check_metric_containment",
    "check_page_budget",
    "check_verbatim_integrity",
    "verify_text",
]
