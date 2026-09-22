"""The ranking rubric: six named factors in a pure, I/O-free module (RANK-01 / D-82).

**Purity.** Standard library only — no I/O, no `Settings`, no LLM, no database.
The same purity contract `app/domain/run_reason.py` states: the caller assembles
the inputs and passes them in, and this module never reaches for the world.

**The factor set is exactly six, in this order** (D-82): ``skills``,
``seniority``, ``domain``, ``location``, ``evidence``, ``compensation``. The
order is the contract — it is the enumeration order of the model's response
schema, the order the per-factor breakdown renders in, and the order the stored
``factor_scores_json`` is written in, so two runs are comparable byte for byte.
Protected attributes and their proxies (age, date of birth, gender, marital or
family status, nationality, ethnicity, religion, disability) are deliberately
**absent** from this set and must never be added: the factor set is the fairness
control (RANK-01).

**``evidence`` is the honest-fit factor.** It measures how well the listing's
stated requirements are actually supported by real CV bullets — not keyword
overlap between the listing text and the CV. It is the main reason a score here
is not just a keyword match.

**The total is computed in code, never by the model** (D-78). The model returns
per-factor sub-scores only; :func:`weighted_total` combines them with the weights
in force at read time, so changing weights re-derives rankings with **zero** new
LLM calls (D-100).

**A factor with no usable data is dropped, never scored as zero** (D-85). The
response schema's ``-1.0`` sentinel means "absent": :func:`present_factors`
excludes it and :func:`weighted_total` re-normalises over the remaining weights.
A board that omits salary must not read as a listing that pays badly.

**The rubric version is hand-bumped** (D-80). ``RUBRIC_VERSION`` is stamped onto
every written score row; a wording fix that changes the meaning of a factor bumps
it deliberately. A content-hash-derived version was rejected — it is opaque in
logs and churns every stored row on any wording fix.

**D-83 — the deferred user-supplied override.** This module deliberately exposes
**no** override parameter and no override is reachable from config or the UI: the
hook is designed and deferred, so the only rubric text sent to the model is the
committed prose in :data:`FACTOR_DEFINITIONS`. When the override lands it must
satisfy one constraint: the override text is untrusted free text and MUST travel
in the request's ``parts`` (the user turn), **never** ``system``, and must pass
through ``app.domain.sanitize`` exactly as listing content does (D-38). Do not
build the override now.
"""

from __future__ import annotations

from collections.abc import Mapping

#: The six factors, in their fixed order (D-82). This tuple is the enumeration:
#: the response schema, the per-factor breakdown and the stored JSON all follow it.
FACTORS: tuple[str, ...] = (
    "skills",
    "seniority",
    "domain",
    "location",
    "evidence",
    "compensation",
)

#: Display labels for the six factors. Presentation only — never sent to the model.
FACTOR_LABELS: dict[str, str] = {
    "skills": "Skills",
    "seniority": "Seniority",
    "domain": "Domain",
    "location": "Location",
    "evidence": "Evidence",
    "compensation": "Compensation",
}

#: The prose definition of each factor, sent to the model as untrusted user-turn
#: text (never ``system``). The ``evidence`` definition is the honest-fit control:
#: it must measure real CV-bullet support, not keyword overlap.
FACTOR_DEFINITIONS: dict[str, str] = {
    "skills": (
        "skills: how well the specific skills the listing asks for are matched by "
        "the candidate's demonstrated skills. Judge demonstrated use, not a list of "
        "keywords that happen to appear in both documents."
    ),
    "seniority": (
        "seniority: how well the level the listing targets matches the candidate's "
        "actual level and scope of responsibility. Judge the level of the work, not "
        "years of service alone."
    ),
    "domain": (
        "domain: how well the industry, product area and business domain of the "
        "listing match the candidate's real background."
    ),
    "location": (
        "location: how well the listing's location and working arrangement (on-site, "
        "hybrid, remote) match what the candidate can and will do."
    ),
    "evidence": (
        "evidence: how well the listing's stated requirements are actually supported "
        "by the candidate's real CV bullets. This measures concrete, demonstrated "
        "experience in the bullets provided — it is NOT keyword overlap between the "
        "listing text and the CV, and a requirement with no supporting bullet must "
        "lower this factor."
    ),
    "compensation": (
        "compensation: how well the salary the listing itself states matches the "
        "candidate's target. Score this ONLY from the listing's own stated salary "
        "fields; if the listing states no salary, omit this factor entirely rather "
        "than inferring a market rate."
    ),
}

#: Hand-bumped rubric version (D-80). Stamped onto every written score row.
RUBRIC_VERSION = "v1"

#: Equal starting weights. A dict (not a literal) so the values are explicitly
#: floats and the whole document can be copied and overridden without mutation.
DEFAULT_WEIGHTS: dict[str, float] = {factor: 1.0 for factor in FACTORS}


def present_factors(sub_scores: Mapping[str, float]) -> tuple[str, ...]:
    """The factors this listing actually has data for, in :data:`FACTORS` order.

    The response schema's ``-1.0`` sentinel means "the model had no usable data"
    (D-85); every other value, including exactly ``0.0``, is a real sub-score and
    is kept. A sub-score of ``0.0`` is therefore never conflated with an absent
    factor (RANK-02 boundary).
    """
    return tuple(
        factor
        for factor in FACTORS
        if float(sub_scores.get(factor, -1.0)) >= 0.0
    )


def weighted_total(
    sub_scores: Mapping[str, float], weights: Mapping[str, float]
) -> float | None:
    """The normalised weighted mean over the present factors (D-79).

    ``total = Σ(sub_i × w_i) / Σ(w_i over present factors)`` — a value in the
    inclusive range -1.0..1.0 that is comparable across any weight set and across
    runs because the denominator moves with the factors that are present.

    Returns ``None`` when the present-factor weight denominator is ``<= 0`` — an
    all-zero weight set or an empty sub-score mapping is an absent total, never a
    ``ZeroDivisionError`` and never a fabricated ``0.0`` (RANK-03 boundary).
    """
    total = 0.0
    weight_sum = 0.0
    for factor in present_factors(sub_scores):
        weight = float(weights.get(factor, 0.0))
        total += float(sub_scores[factor]) * weight
        weight_sum += weight
    if weight_sum <= 0.0:
        return None
    return total / weight_sum


def confidence_tier(sub_scores: Mapping[str, float]) -> str:
    """How much of the rubric this listing had data for (D-85).

    ``high`` when every factor is present, ``medium`` when at least four are, and
    ``low`` otherwise. Expressed as a comparison against the factor-count tuple
    rather than hard-coded thresholds, so widening the factor set does not silently
    move the boundary.
    """
    present = len(present_factors(sub_scores))
    if present == len(FACTORS):
        return "high"
    if present >= len(FACTORS) - 2:
        return "medium"
    return "low"


__all__ = [
    "DEFAULT_WEIGHTS",
    "FACTORS",
    "FACTOR_DEFINITIONS",
    "FACTOR_LABELS",
    "RUBRIC_VERSION",
    "confidence_tier",
    "present_factors",
    "weighted_total",
]
