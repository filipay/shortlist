"""Layer 1 verification — the deterministic pre-check over ``(facts, plan, patch)``.

This runs BEFORE any compile (D-111) and short-circuits on a ``fail`` (D-114). It is
pure and clock-free unless a ``now`` is injected (the temporal check), so the
default-lane fixtures stay reproducible.

The five checks (D-112) are:

1. ``id_containment`` — every id in the plan is a fact id.
2. ``entity_resolvable`` — every rendered org/title/section heading resolves through
   the enumerations or the closed ``SECTION_TITLES`` map.
3. ``bullet_conservation`` — the plan's bullets equal the facts' bullets MINUS the
   declared drops, checked in BOTH directions (the reverse catches a declared drop
   that was not actually dropped — the CV-R5 silent-condensing catcher).
4. ``temporal_consistency`` — every entry ``end >= start``; with an injected ``now``,
   no start or end is in the future.
5. ``requirement_evidence`` — the STRUCTURAL half of check 6 only: every non-``gap``
   ``GapFinding`` names at least one resolvable evidence id, and every ``gap`` names
   none. The FAIL predicate is structural and unchanged by the advisory band: a
   similarity ratio must never be load-bearing on a block decision (the rule D-70
   sets). The band is attached to a passing result's ``detail`` (via
   ``app/verify/grounding.py``) for the UI's per-requirement confidence label; it
   never changes ``passed``.
"""

from __future__ import annotations

from datetime import datetime

from app.config import settings
from app.domain.cv import (
    SECTION_TITLES,
    CvFacts,
    DropBullet,
    RenderPlan,
    TailoringPatch,
    iter_fact_ids,
)
from app.verify.base import CheckResult, VerificationResult
from app.verify.grounding import band_for, evidence_text_for

#: The month form an entry's ``start``/``end`` uses (``"YYYY-MM"``), which also makes
#: a plain lexicographic comparison a chronological one.
_MONTH_FORM = "%Y-%m"


def _fail(check_id: str, detail: str, offending: list[str]) -> CheckResult:
    return CheckResult(id=check_id, status="fail", detail=detail, offending=offending)


def _pass(check_id: str, detail: str) -> CheckResult:
    return CheckResult(id=check_id, status="pass", detail=detail)


def check_id_containment(facts: CvFacts, plan: RenderPlan) -> CheckResult:
    """Every section/entry/bullet/skill id in the plan is a fact id."""
    known = set(iter_fact_ids(facts))
    offending: list[str] = []
    for section in plan.sections:
        if section.id not in known:
            offending.append(section.id)
        for entry in section.entries:
            if entry.id not in known:
                offending.append(entry.id)
            for bullet in entry.bullets:
                if bullet.id not in known:
                    offending.append(bullet.id)
        for skill in section.skills:
            if skill.id not in known:
                offending.append(skill.id)
    if offending:
        return _fail(
            "id_containment",
            f"{len(offending)} plan id(s) are not fact ids",
            sorted(set(offending)),
        )
    return _pass("id_containment", "every plan id is a fact id")


def check_entity_resolvable(facts: CvFacts, plan: RenderPlan) -> CheckResult:
    """Every rendered org/title/section heading resolves through an enumeration."""
    org_names = {org.name for org in facts.orgs}
    org_names |= {alias for org in facts.orgs for alias in org.aliases}
    title_names = {title.name for title in facts.titles}
    section_titles = set(SECTION_TITLES.values())

    offending: list[str] = []
    for section in plan.sections:
        if section.title not in section_titles:
            offending.append(section.title)
        for entry in section.entries:
            if entry.org not in org_names:
                offending.append(entry.org)
            if entry.title not in title_names:
                offending.append(entry.title)
    if offending:
        return _fail(
            "entity_resolvable",
            f"{len(offending)} rendered value(s) do not resolve",
            sorted(set(offending)),
        )
    return _pass("entity_resolvable", "every rendered value resolves")


def check_bullet_conservation(
    facts: CvFacts, plan: RenderPlan, patch: TailoringPatch
) -> CheckResult:
    """The plan's bullets equal the facts' bullets minus the declared drops, both ways."""
    fact_ids = {bullet.id for entry in facts.all_entries() for bullet in entry.bullets}
    plan_ids = {
        bullet.id
        for section in plan.sections
        for entry in section.entries
        for bullet in entry.bullets
    }
    drops = {op.bullet_id for op in patch.ops if isinstance(op, DropBullet)}

    # A fact bullet that vanished with no declared drop.
    vanished = fact_ids - drops - plan_ids
    # A declared drop that was NOT actually dropped (the reverse direction).
    retained = plan_ids & drops
    offending = sorted(vanished | retained)
    if offending:
        return _fail(
            "bullet_conservation",
            f"{len(vanished)} bullet(s) vanished without a drop and "
            f"{len(retained)} declared drop(s) were retained",
            offending,
        )
    return _pass("bullet_conservation", "bullets are conserved minus the declared drops")


def check_temporal_consistency(
    facts: CvFacts, *, now: datetime | None = None
) -> CheckResult:
    """Every entry has ``end >= start``; with ``now``, no date is in the future."""
    offending: list[str] = []
    current = now.strftime(_MONTH_FORM) if now is not None else None
    for entry in facts.all_entries():
        if entry.end is not None and entry.end < entry.start:
            offending.append(entry.id)
        if current is not None:
            if entry.start > current or (entry.end is not None and entry.end > current):
                offending.append(entry.id)
    if offending:
        return _fail(
            "temporal_consistency",
            f"{len(offending)} entry/entries have an inconsistent date range",
            sorted(set(offending)),
        )
    return _pass("temporal_consistency", "every entry's date range is consistent")


def check_requirement_evidence(
    facts: CvFacts,
    patch: TailoringPatch,
    *,
    grounded_at: int | None = None,
    review_at: int | None = None,
) -> CheckResult:
    """The structural half of check 6, with the ADVISORY band attached (A1).

    The fail predicate is exactly ``06-01``'s: a non-``gap`` finding with no resolvable
    evidence, or a ``gap`` with resolvable evidence. The band is computed ONLY for a
    non-``gap`` finding that already passes structurally and is emitted on a passing
    ``detail`` as a machine-readable label. It cannot flip ``passed``.
    """
    known = set(iter_fact_ids(facts))
    offending: list[str] = []
    bands: list[str] = []
    for index, finding in enumerate(patch.gaps):
        resolvable = [item for item in finding.evidence_ids if item in known]
        if finding.status != "gap":
            if not resolvable:
                # Index, never the requirement text: verification_json is persisted
                # and must not carry listing prose (T-06-07).
                offending.append(f"gap[{index}]")
                continue
            band = band_for(
                finding.requirement,
                evidence_text_for(facts, finding),
                grounded_at=(
                    settings.tailoring_grounding_threshold
                    if grounded_at is None
                    else grounded_at
                ),
                review_at=(
                    settings.tailoring_grounding_review_threshold
                    if review_at is None
                    else review_at
                ),
            )
            bands.append(f"gap[{index}]:{band}")
        elif resolvable:
            offending.append(f"gap[{index}]")
    if offending:
        return _fail(
            "requirement_evidence",
            f"{len(offending)} finding(s) have evidence inconsistent with their status",
            offending,
        )
    detail = "requirement evidence is consistent with status"
    if bands:
        # The band LABEL only — never the requirement or the evidence text.
        detail = f"{detail}; bands: {', '.join(bands)}"
    return _pass("requirement_evidence", detail)


def verify_plan(
    facts: CvFacts,
    plan: RenderPlan,
    patch: TailoringPatch,
    *,
    now: datetime | None = None,
) -> VerificationResult:
    """Run every Layer-1 check and return the aggregate. ``passed`` iff none failed."""
    checks = [
        check_id_containment(facts, plan),
        check_entity_resolvable(facts, plan),
        check_bullet_conservation(facts, plan, patch),
        check_temporal_consistency(facts, now=now),
        check_requirement_evidence(facts, patch),
    ]
    passed = all(check.status != "fail" for check in checks)
    return VerificationResult(passed=passed, checks=checks)


__all__ = [
    "check_bullet_conservation",
    "check_entity_resolvable",
    "check_id_containment",
    "check_requirement_evidence",
    "check_temporal_consistency",
    "verify_plan",
]
