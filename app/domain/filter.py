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

#: The `location` rule's `mode` values. `substring` (the default) matches a
#: casefolded term anywhere in `location_norm`. `county` keeps that rule and also
#: matches an Irish county when a term equals the county name or one of its
#: subdivision/plate codes, resolved from `location_norm` by `_county_from_location`.
#: Any unrecognised value degrades to `substring`.
LOCATION_MODES = ("substring", "county")

#: ISO 3166-2:IE subdivision code (lowercase, without the `ie-` prefix) -> county
#: name. Boards normalise an Irish location as `<area>, <code>, <country>`, so the
#: code segment arrives as `d`/`c`/`lk`/... (`blanchardstown, d, ie` is Dublin 15).
#: Source: ISO 3166-2:IE, the 26 counties (the former `IE-*` province codes are
#: not emitted by any board). Kept stdlib-only and pure like the rest of the module.
IE_COUNTY_NAME_BY_CODE: dict[str, str] = {
    "cw": "carlow",
    "cn": "cavan",
    "ce": "clare",
    "co": "cork",
    "dl": "donegal",
    "d": "dublin",
    "g": "galway",
    "ky": "kerry",
    "ke": "kildare",
    "kk": "kilkenny",
    "ls": "laois",
    "lm": "leitrim",
    "lk": "limerick",
    "ld": "longford",
    "lh": "louth",
    "mo": "mayo",
    "mh": "meath",
    "mn": "monaghan",
    "oy": "offaly",
    "rn": "roscommon",
    "so": "sligo",
    "ta": "tipperary",
    "wd": "waterford",
    "wh": "westmeath",
    "wx": "wexford",
    "ww": "wicklow",
}

#: Vehicle-registration-plate county codes that DIVERGE from the ISO 3166-2:IE code
#: for the same county. The boards emit plate codes on the code segment, not ISO
#: codes (verified against the live corpus: `midleton, c, ie` is Cork), while ISO
#: 3166-2:IE remains the documented reference. For *most* counties the two coincide
#: (`d`, `g`, `wd`, `ww`, `so`, `lk`, `ky`, ...), which is why Dublin appeared to
#: work; only the divergences are listed here. Strictly additive — the ISO table
#: above is never re-keyed or emptied, because a silent false *accept* (failing to
#: exclude a listing outside the allowed county) is this project's worst failure
#: mode. Widening only lets `county` mode resolve an area it previously could not.
IE_COUNTY_PLATE_CODE_BY_NAME: dict[str, tuple[str, ...]] = {
    # ISO `co`; Cork vehicles are registered `c`.
    "cork": ("c",),
    # ISO `ta`; Tipperary plates are `t` since 2014, older `tn` (North) / `ts` (South).
    "tipperary": ("t", "tn", "ts"),
    # ISO `lk`; Limerick plates are `l` since 2014.
    "limerick": ("l",),
}

#: Every code a location segment may carry -> county name: the ISO table plus the
#: divergent plate codes. No plate code collides with an ISO code, so this is a pure
#: widening of the ISO lookup rather than a redefinition of any existing key.
_COUNTY_NAME_BY_ANY_CODE: dict[str, str] = {
    **IE_COUNTY_NAME_BY_CODE,
    **{
        code: name
        for name, codes in IE_COUNTY_PLATE_CODE_BY_NAME.items()
        for code in codes
    },
}

#: The county names, so a `county <name>` segment (`county dublin`) resolves even
#: though only the name — never the qualifier — is a table key.
_COUNTY_NAMES: frozenset[str] = frozenset(IE_COUNTY_NAME_BY_CODE.values())

#: The inverse of `IE_COUNTY_NAME_BY_CODE` (the ISO mapping is a bijection), so
#: `county` mode can match a bare ISO code term without re-scanning the table.
#: Plate-only codes are intentionally not inverted here: they are resolved to a
#: county *name* by `_county_from_location`, and a bare plate term already matches
#: the raw location string via the substring branch.
_COUNTY_CODE_BY_NAME: dict[str, str] = {
    name: code for code, name in IE_COUNTY_NAME_BY_CODE.items()
}

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


def _county_from_location(location_norm: str | None) -> str | None:
    """Resolve an Irish county *name* from a normalised location string.

    The boards normalise as `<area>, <county-code>, <country>`, and the code is a
    vehicle-registration plate (`d` -> `dublin`), which is *not* always the ISO
    3166-2:IE code (`midleton, c, ie` is Cork, whose ISO code is `co`). A segment may
    instead name the county (`swords, county dublin, ireland`); the leading
    `county ` qualifier is stripped and the remainder matched against the county
    names. The country segment (`ireland` or `ie`) never resolves. Returns the county
    name for the first comma-separated segment that carries county evidence, or
    `None` when there is none — an absent county is never itself a rejection reason.
    """
    if not location_norm:
        return None
    for raw_segment in location_norm.split(","):
        segment = raw_segment.strip().casefold()
        if not segment:
            continue
        name = _COUNTY_NAME_BY_ANY_CODE.get(segment)
        if name is not None:
            return name
        if segment in _COUNTY_NAMES:
            return segment
        if segment.startswith("county "):
            candidate = segment[len("county ") :].strip()
            if candidate in _COUNTY_NAMES:
                return candidate
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
        # An unknown location is never a rejection reason.
        return None

    haystack = facts.location_norm.casefold()
    # `mode` is documented as "substring"; `county` is strictly more permissive
    # (it can only add matches), and any unrecognised value degrades to substring
    # rather than raising.
    if params.get("mode") == "county":
        county_name = _county_from_location(facts.location_norm)
        county_code = (
            _COUNTY_CODE_BY_NAME.get(county_name) if county_name is not None else None
        )
        matched = any(
            term.casefold() in haystack
            or (county_name is not None and term.casefold() == county_name)
            or (county_code is not None and term.casefold() == county_code)
            for term in allow
        )
    else:
        matched = any(term.casefold() in haystack for term in allow)

    if matched:
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
    "IE_COUNTY_NAME_BY_CODE",
    "LISTING_FACT_FIELDS",
    "LOCATION_MODES",
    "ListingFacts",
    "RULE_KINDS",
    "RuleOutcome",
    "RuleSpec",
    "evaluate",
]
