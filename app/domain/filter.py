"""Pure filter-rule evaluation: the six `filter_rules.kind` evaluators.

No I/O, no settings, no `rapidfuzz` — every function here is deterministic and
unit-testable, so a rejection is decided by code rather than by a template. The
repository maps an ORM `FilterRule` row into a `RuleSpec`; the ORM row must never
be passed in (the import-discipline guard forbids `sqlalchemy` under `app.domain`).

Contract
--------
* One `RuleOutcome` is produced **per firing rule**. Two rules that both fire
  produce two separate outcomes, never one merged outcome — that is what makes a
  `GROUP BY rule_id` per-rule count correct downstream.
* Outcomes are ordered by `(position, rule_id)`. `rule_id` is unique, so the
  order is total and stable across runs (D-36: rules are re-evaluated from
  scratch every run, so this function is stateless).
* **An absent or unknown value is never a rejection reason.** `salary_floor`
  passes a listing with no known salary, `remote` passes an unknown remote flag,
  `seniority` passes an unknown seniority and `location` passes an unknown
  location. This is the resolved A2/A3 decision: JobSpy's description-derived
  salary extraction is USA-only, so excluding unknowns would empty most of an
  Irish corpus.
* An unknown `kind` is **skipped**, not evaluated and not treated as a
  pass-through exclusion.
* **Rule scope is the union of every enabled search's rules (A4):** a rejection
  by any enabled search's rule removes the listing from the queue. There is
  deliberately no column linking a listing to the search that retrieved it.

A skipped rule (unknown kind, non-mapping params, a missing or wrong-typed
required key) produces **no outcome**. The caller's stage log records the skip;
a skipped rule must never be silently treated as "passed and applied" (T-02-09).

Every `RuleOutcome.detail` mapping carries terms, field names, counts and numbers
only — never an excerpt of the listing's own text and never a removed value, so a
persisted exclusion cannot become a PII vector (T-02-07).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from app.domain.listing import annualise_salary

#: The typed rule vocabulary (D-34). Mirrored by the named `ck_filter_rules_kind`
#: CHECK added in migration 0002, so widening it later is a coordinated migration
#: plus a UI change — keep this the single in-code source of truth.
RULE_KINDS = (
    "salary_floor",
    "exclude_keyword",
    "location",
    "remote",
    "seniority",
    "company_blocklist",
)

#: The `ListingFacts` attributes an `exclude_keyword` rule may name. Using an
#: allow-list rather than a bare `getattr` keeps a hostile `fields` value from
#: reaching an attribute that is not a listing field.
LISTING_FACT_FIELDS = (
    "title",
    "title_norm",
    "description",
    "company_norm",
    "location_norm",
    "remote_flag",
    "seniority",
    "salary_min",
    "salary_max",
    "salary_interval",
)

#: The `exclude_keyword` default when `fields` is absent.
DEFAULT_KEYWORD_FIELDS = ("title", "description")

#: The intervals `annualise_salary` resolves to an annual figure. A comparison is
#: only meaningful between annual figures, so anything else is skipped.
_ANNUAL_INTERVALS = frozenset({"year", "yearly", "annual", "annually"})


@dataclass(frozen=True)
class RuleSpec:
    """One `filter_rules` row, mapped to a pure value.

    `params` is a `Mapping` and is treated strictly as data: this module never
    eval/execs it, never imports from it, and never does dynamic attribute access
    on its keys.
    """

    rule_id: str
    kind: str
    params: Mapping[str, Any]
    position: int = 0


@dataclass(frozen=True)
class ListingFacts:
    """The subset of a `listings` row a rule may read. Pure values, no ORM."""

    title: str = ""
    title_norm: str | None = None
    description: str | None = None
    company_norm: str | None = None
    location_norm: str | None = None
    remote_flag: bool | None = None
    seniority: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_interval: str | None = None


@dataclass(frozen=True)
class RuleOutcome:
    """Why one rule fired. `detail` is the FILT-02 evidence mapping."""

    excluded: bool
    rule_id: str
    rule_kind: str
    detail: dict[str, Any]


# --- total helpers ------------------------------------------------------------


def _as_mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _as_str_list(value: Any) -> list[str] | None:
    """A list of non-empty strings, or `None` when the value is not usable.

    A bare string is accepted as a one-element list. An empty container returns
    `[]`, which every caller treats as "this rule is misconfigured, skip it".
    """
    if value is None:
        return None
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set, frozenset)):
        return [str(item) for item in value if isinstance(item, str) and item]
    return None


def _as_bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _sort_key(spec: RuleSpec) -> tuple[int, str]:
    """Total, never-raising sort key: `(position, rule_id)`."""
    position = spec.position
    if not isinstance(position, int) or isinstance(position, bool):
        position = 0
    rule_id = spec.rule_id if isinstance(spec.rule_id, str) else str(spec.rule_id)
    return (position, rule_id)


# --- per-kind evaluators ------------------------------------------------------


def _eval_salary_floor(spec: RuleSpec, facts: ListingFacts) -> RuleOutcome | None:
    params = _as_mapping(spec.params)
    if params is None:
        return None

    amount = params.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return None

    if facts.salary_min is None and facts.salary_max is None:
        # No known figure — an absent value is never a rejection reason.
        return None

    currency = params.get("currency")
    currency = currency if isinstance(currency, str) else None

    annual_min, annual_max, interval, resolved_currency = annualise_salary(
        facts.salary_min, facts.salary_max, facts.salary_interval, currency
    )
    if not isinstance(interval, str) or interval.strip().casefold() not in _ANNUAL_INTERVALS:
        # `annualise_salary` passes an unrecognised interval through unchanged
        # rather than guessing, so a comparison would be between units. Skip.
        return None

    # Best case first: a role whose top of range could meet the floor is not
    # rejected. This is the anti-over-rejection bias of A2/A3 applied to a range.
    candidate = annual_max if annual_max is not None else annual_min
    if candidate is None or candidate >= float(amount):
        return None

    return RuleOutcome(
        excluded=True,
        rule_id=spec.rule_id,
        rule_kind=spec.kind,
        detail={
            "floor": float(amount),
            "salary_min": annual_min,
            "salary_max": annual_max,
            "interval": interval,
            "currency": resolved_currency,
        },
    )


def _eval_exclude_keyword(spec: RuleSpec, facts: ListingFacts) -> RuleOutcome | None:
    params = _as_mapping(spec.params)
    if params is None:
        return None

    terms = _as_str_list(params.get("terms"))
    if not terms:
        # An empty/missing term list is a misconfiguration, not "exclude all".
        return None

    fields = _as_str_list(params.get("fields")) or list(DEFAULT_KEYWORD_FIELDS)

    for term in terms:
        needle = term.casefold()
        if not needle:
            continue
        for field in fields:
            if field not in LISTING_FACT_FIELDS:
                continue
            value = getattr(facts, field)
            if not isinstance(value, str) or not value:
                continue
            count = value.casefold().count(needle)
            if count:
                # Terms, the field NAME and a count only — never the field text.
                return RuleOutcome(
                    excluded=True,
                    rule_id=spec.rule_id,
                    rule_kind=spec.kind,
                    detail={"term": term, "field": field, "count": count},
                )
    return None


def _eval_location(spec: RuleSpec, facts: ListingFacts) -> RuleOutcome | None:
    params = _as_mapping(spec.params)
    if params is None:
        return None

    allow = _as_str_list(params.get("allow"))
    if not allow:
        # An empty allow-list is a misconfiguration, not "exclude everything".
        return None

    if not facts.location_norm:
        return None

    haystack = facts.location_norm.casefold()
    # `mode` is documented as "substring"; it is read for forward compatibility
    # and any unrecognised value degrades to substring rather than raising.
    if any(term.casefold() in haystack for term in allow):
        return None

    return RuleOutcome(
        excluded=True,
        rule_id=spec.rule_id,
        rule_kind=spec.kind,
        detail={"location_norm": facts.location_norm, "allowed": list(allow)},
    )


def _eval_remote(spec: RuleSpec, facts: ListingFacts) -> RuleOutcome | None:
    params = _as_mapping(spec.params)
    if params is None:
        return None

    require = _as_bool(params.get("require"), True)
    if not require:
        return None

    if facts.remote_flag is False:
        return RuleOutcome(
            excluded=True,
            rule_id=spec.rule_id,
            rule_kind=spec.kind,
            detail={"remote_flag": False, "require": True},
        )
    return None


def _eval_seniority(spec: RuleSpec, facts: ListingFacts) -> RuleOutcome | None:
    params = _as_mapping(spec.params)
    if params is None:
        return None

    allow = _as_str_list(params.get("allow")) or []
    deny = _as_str_list(params.get("deny")) or []
    if not allow and not deny:
        return None
    unknown_passes = _as_bool(params.get("unknown_passes"), True)

    value = facts.seniority
    if not value:
        if unknown_passes:
            return None
        return RuleOutcome(
            excluded=True,
            rule_id=spec.rule_id,
            rule_kind=spec.kind,
            detail={"seniority": None, "allow": list(allow)},
        )

    lowered = value.casefold()
    if any(token.casefold() in lowered for token in deny):
        return RuleOutcome(
            excluded=True,
            rule_id=spec.rule_id,
            rule_kind=spec.kind,
            detail={"seniority": value, "allow": list(allow)},
        )
    if allow and not any(token.casefold() in lowered for token in allow):
        return RuleOutcome(
            excluded=True,
            rule_id=spec.rule_id,
            rule_kind=spec.kind,
            detail={"seniority": value, "allow": list(allow)},
        )
    return None


def _eval_company_blocklist(spec: RuleSpec, facts: ListingFacts) -> RuleOutcome | None:
    params = _as_mapping(spec.params)
    if params is None:
        return None

    companies = _as_str_list(params.get("companies"))
    if not companies:
        return None

    company_norm = facts.company_norm
    if not company_norm:
        # An unknown company is never a rejection reason.
        return None

    match = params.get("match")
    match = match if isinstance(match, str) else "norm_equals"

    haystack = company_norm.casefold()
    tokens = set(haystack.split())
    for entry in companies:
        candidate = entry.casefold().strip()
        if not candidate:
            continue
        if match == "token":
            matched = candidate in tokens
        else:
            # `norm_equals` is the default; an unrecognised mode degrades to
            # equality rather than raising.
            matched = haystack == candidate
        if matched:
            return RuleOutcome(
                excluded=True,
                rule_id=spec.rule_id,
                rule_kind=spec.kind,
                detail={"company_norm": company_norm, "matched": entry},
            )
    return None


_EVALUATORS: dict[str, Callable[[RuleSpec, ListingFacts], RuleOutcome | None]] = {
    "salary_floor": _eval_salary_floor,
    "exclude_keyword": _eval_exclude_keyword,
    "location": _eval_location,
    "remote": _eval_remote,
    "seniority": _eval_seniority,
    "company_blocklist": _eval_company_blocklist,
}


def evaluate(rules: Iterable[RuleSpec], facts: ListingFacts) -> list[RuleOutcome]:
    """Return only the rules that fired, ordered by `(position, rule_id)`.

    Total: an unknown kind, a non-mapping `params`, a missing required key or a
    wrong-typed value skips that rule without raising. A skipped rule is recorded
    by the caller's stage log — it is never reported as "applied".
    """
    ordered = sorted(rules or (), key=_sort_key)

    outcomes: list[RuleOutcome] = []
    for spec in ordered:
        if not isinstance(spec, RuleSpec):
            continue
        evaluator = _EVALUATORS.get(spec.kind)
        if evaluator is None:
            continue
        outcome = evaluator(spec, facts)
        if outcome is not None:
            outcomes.append(outcome)
    return outcomes


__all__ = [
    "LISTING_FACT_FIELDS",
    "ListingFacts",
    "RULE_KINDS",
    "RuleOutcome",
    "RuleSpec",
    "evaluate",
]
