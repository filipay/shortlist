"""FILT-01 / FILT-02 — the six pure rule evaluators.

Direct function calls over frozen dataclasses: no DB, no fixtures beyond plain
values. Every test here is a property the filter stage (plan 02-05) relies on:
deterministic ordering, one outcome per firing rule, never a rejection on absent
data, never a raise on malformed input, and PII-free evidence.
"""

from __future__ import annotations

from app.domain.filter import (
    LISTING_FACT_FIELDS,
    RULE_KINDS,
    ListingFacts,
    RuleOutcome,
    RuleSpec,
    evaluate,
)

# --- helpers ------------------------------------------------------------------


def _spec(
    rule_id: str = "r1",
    kind: str = "remote",
    params: dict | None = None,
    position: int = 0,
) -> RuleSpec:
    return RuleSpec(rule_id=rule_id, kind=kind, params=params or {}, position=position)


def _facts(**overrides: object) -> ListingFacts:
    base: dict[str, object] = {
        "title": "Senior Python Engineer",
        "title_norm": "senior python engineer",
        "description": "Build the thing with Python.",
        "company_norm": "acme",
        "location_norm": "dublin, ireland",
        "remote_flag": True,
        "seniority": "senior",
        "salary_min": 70000.0,
        "salary_max": 90000.0,
        "salary_interval": "year",
    }
    base.update(overrides)
    return ListingFacts(**base)  # type: ignore[arg-type]


def _fire(kind: str, params: dict, facts: ListingFacts, rule_id: str = "r1") -> RuleOutcome:
    outcomes = evaluate([_spec(rule_id=rule_id, kind=kind, params=params)], facts)
    assert len(outcomes) == 1, f"{kind} did not fire exactly once: {outcomes}"
    return outcomes[0]


# --- vocabulary ---------------------------------------------------------------
def test_rule_kinds_is_the_six_kind_vocabulary() -> None:
    assert RULE_KINDS == (
        "salary_floor",
        "exclude_keyword",
        "location",
        "remote",
        "seniority",
        "company_blocklist",
    )
    assert set(RULE_KINDS) == {
        "salary_floor",
        "exclude_keyword",
        "location",
        "remote",
        "seniority",
        "company_blocklist",
    }


# --- salary_floor -------------------------------------------------------------
def test_salary_floor_excludes_below_the_floor() -> None:
    facts = _facts(salary_min=69000.0, salary_max=None)
    outcome = _fire("salary_floor", {"amount": 70000, "currency": "EUR"}, facts)

    assert outcome.excluded is True
    assert outcome.rule_kind == "salary_floor"


def test_salary_floor_passes_at_the_floor_and_above() -> None:
    params = {"amount": 70000, "currency": "EUR"}

    assert (
        evaluate(
            [_spec(kind="salary_floor", params=params)], _facts(salary_min=70000.0, salary_max=None)
        )
        == []
    )
    assert (
        evaluate(
            [_spec(kind="salary_floor", params=params)], _facts(salary_min=70001.0, salary_max=None)
        )
        == []
    )


def test_salary_floor_passes_when_it_could_meet_the_floor_at_the_top_of_range() -> None:
    """A range that straddles the floor is not rejected — best case is consulted."""
    params = {"amount": 70000, "currency": "EUR"}
    facts = _facts(salary_min=52000.0, salary_max=90000.0)

    assert evaluate([_spec(kind="salary_floor", params=params)], facts) == []


def test_salary_floor_annualises_across_intervals() -> None:
    params = {"amount": 70000, "currency": "EUR"}

    # 300/day * 260 = 78000/year -> passes.
    assert (
        evaluate(
            [_spec(kind="salary_floor", params=params)],
            _facts(salary_min=300.0, salary_max=None, salary_interval="day"),
        )
        == []
    )

    # 250/day * 260 = 65000/year -> excludes.
    outcome = _fire(
        "salary_floor",
        params,
        _facts(salary_min=250.0, salary_max=None, salary_interval="day"),
    )
    assert outcome.detail["interval"] == "year"
    assert outcome.detail["salary_min"] == 65000.0


def test_salary_floor_skips_an_unrecognised_interval() -> None:
    params = {"amount": 70000, "currency": "EUR"}

    assert (
        evaluate(
            [_spec(kind="salary_floor", params=params)],
            _facts(salary_min=100.0, salary_max=None, salary_interval="fortnight"),
        )
        == []
    )


# --- exclude_keyword ----------------------------------------------------------
def test_exclude_keyword_excludes_on_a_listed_field() -> None:
    outcome = _fire(
        "exclude_keyword",
        {"terms": ["crypto"], "fields": ["title", "description"]},
        _facts(title="Crypto Trader"),
    )

    assert outcome.detail["term"] == "crypto"
    assert outcome.detail["field"] == "title"
    assert outcome.detail["count"] == 1


def test_exclude_keyword_passes_when_no_term_matches() -> None:
    assert (
        evaluate(
            [_spec(kind="exclude_keyword", params={"terms": ["crypto"]})],
            _facts(),
        )
        == []
    )


def test_exclude_keyword_never_persists_the_field_text() -> None:
    secret = "Acme is hiring a crypto wizard"
    facts = _facts(title="Backend Engineer", description=secret)
    outcome = _fire(
        "exclude_keyword",
        {"terms": ["crypto"], "fields": ["description"]},
        facts,
    )

    assert set(outcome.detail) == {"term", "field", "count"}
    rendered = " ".join(str(value) for value in outcome.detail.values())
    assert "wizard" not in rendered
    assert secret not in rendered
    # The field NAME is allowed; the field's text is not.
    assert outcome.detail["field"] == "description"


# --- location -----------------------------------------------------------------
def test_location_excludes_when_not_allowed() -> None:
    outcome = _fire(
        "location", {"allow": ["dublin", "cork"]}, _facts(location_norm="galway, ireland")
    )

    assert outcome.detail["location_norm"] == "galway, ireland"
    assert outcome.detail["allowed"] == ["dublin", "cork"]


def test_location_passes_when_allowed_or_unknown() -> None:
    params = {"allow": ["dublin", "cork"]}

    assert (
        evaluate([_spec(kind="location", params=params)], _facts(location_norm="dublin, ireland"))
        == []
    )
    assert evaluate([_spec(kind="location", params=params)], _facts(location_norm=None)) == []


# --- remote -------------------------------------------------------------------
def test_remote_excludes_only_a_known_non_remote_flag() -> None:
    params = {"require": True}

    outcome = _fire("remote", params, _facts(remote_flag=False))
    assert outcome.detail == {"remote_flag": False, "require": True}

    assert evaluate([_spec(kind="remote", params=params)], _facts(remote_flag=True)) == []
    assert evaluate([_spec(kind="remote", params=params)], _facts(remote_flag=None)) == []


# --- seniority ----------------------------------------------------------------
def test_seniority_deny_matches_outright() -> None:
    outcome = _fire(
        "seniority",
        {"allow": ["senior", "staff"], "deny": ["junior"], "unknown_passes": True},
        _facts(seniority="Junior Developer"),
    )

    assert outcome.detail["seniority"] == "Junior Developer"


def test_seniority_excludes_when_known_and_not_allowed() -> None:
    outcome = _fire(
        "seniority",
        {"allow": ["senior", "staff"]},
        _facts(seniority="mid-level"),
    )

    assert outcome.detail["allow"] == ["senior", "staff"]


def test_seniority_unknown_policy_is_honoured() -> None:
    assert (
        evaluate(
            [_spec(kind="seniority", params={"allow": ["senior"], "unknown_passes": True})],
            _facts(seniority=None),
        )
        == []
    )

    outcomes = evaluate(
        [_spec(kind="seniority", params={"allow": ["senior"], "unknown_passes": False})],
        _facts(seniority=None),
    )
    assert len(outcomes) == 1
    assert outcomes[0].detail["seniority"] is None


# --- company_blocklist --------------------------------------------------------
def test_company_blocklist_excludes_on_exact_norm_and_token_match() -> None:
    outcome = _fire("company_blocklist", {"companies": ["acme"]}, _facts(company_norm="acme"))
    assert outcome.detail == {"company_norm": "acme", "matched": "acme"}

    token = _fire(
        "company_blocklist",
        {"companies": ["staffing"], "match": "token"},
        _facts(company_norm="acme staffing group"),
    )
    assert token.detail["matched"] == "staffing"


def test_company_blocklist_passes_a_different_or_unknown_company() -> None:
    params = {"companies": ["acme"]}

    assert (
        evaluate([_spec(kind="company_blocklist", params=params)], _facts(company_norm="globex"))
        == []
    )
    assert (
        evaluate([_spec(kind="company_blocklist", params=params)], _facts(company_norm=None)) == []
    )


# --- the unknown-value policy (A2/A3) -----------------------------------------
def test_unknown_values_are_never_a_rejection_reason() -> None:
    """All six kinds fire nothing when every unknown-able value is absent."""
    rules = [
        _spec("r-salary", "salary_floor", {"amount": 1000000, "currency": "EUR"}),
        _spec("r-keyword", "exclude_keyword", {"terms": ["crypto"]}),
        _spec("r-location", "location", {"allow": ["dublin"]}),
        _spec("r-remote", "remote", {"require": True}),
        _spec("r-seniority", "seniority", {"allow": ["senior"], "unknown_passes": True}),
        _spec("r-company", "company_blocklist", {"companies": ["acme"]}),
    ]
    facts = _facts(
        salary_min=None,
        salary_max=None,
        salary_interval=None,
        remote_flag=None,
        seniority=None,
        location_norm=None,
        company_norm=None,
    )

    assert evaluate(rules, facts) == []


# --- adjacency ----------------------------------------------------------------
def test_two_firing_rules_produce_two_separate_outcomes() -> None:
    rules = [
        _spec("r-title", "exclude_keyword", {"terms": ["python"], "fields": ["title"]}),
        _spec("r-desc", "exclude_keyword", {"terms": ["python"], "fields": ["description"]}),
    ]

    outcomes = evaluate(rules, _facts())

    # Two firing rules, two outcomes — never merged. Equal positions order by rule_id.
    assert [outcome.rule_id for outcome in outcomes] == ["r-desc", "r-title"]


# --- empty --------------------------------------------------------------------
def test_an_empty_rule_list_returns_no_outcomes() -> None:
    assert evaluate([], _facts()) == []


def test_empty_terms_and_empty_allow_lists_are_skipped() -> None:
    assert evaluate([_spec(kind="exclude_keyword", params={"terms": []})], _facts()) == []
    assert evaluate([_spec(kind="exclude_keyword", params={})], _facts()) == []
    assert (
        evaluate([_spec(kind="location", params={"allow": []})], _facts(location_norm="galway"))
        == []
    )
    assert evaluate([_spec(kind="company_blocklist", params={"companies": []})], _facts()) == []


# --- ordering -----------------------------------------------------------------
def test_outcomes_are_ordered_by_position_then_rule_id() -> None:
    rules = [
        _spec("b_rule", "remote", {"require": True}, position=5),
        _spec("a_rule", "remote", {"require": True}, position=5),
        _spec("z_rule", "remote", {"require": True}, position=1),
    ]

    outcomes = evaluate(rules, _facts(remote_flag=False))

    assert [outcome.rule_id for outcome in outcomes] == ["z_rule", "a_rule", "b_rule"]


def test_repeated_evaluation_is_identically_ordered() -> None:
    rules = [
        _spec("c", "remote", {"require": True}, position=2),
        _spec("a", "remote", {"require": True}, position=2),
        _spec("b", "remote", {"require": True}, position=1),
    ]
    facts = _facts(remote_flag=False)

    first = evaluate(rules, facts)
    second = evaluate(list(reversed(rules)), facts)

    assert [outcome.rule_id for outcome in first] == [outcome.rule_id for outcome in second]


# --- total functions / malformed input ----------------------------------------
def test_an_unknown_kind_is_skipped() -> None:
    assert evaluate([_spec(kind="not_a_kind", params={"anything": 1})], _facts()) == []


def test_a_non_mapping_params_is_skipped_without_raising() -> None:
    broken = RuleSpec(rule_id="r", kind="exclude_keyword", params=["not", "a", "mapping"])  # type: ignore[arg-type]

    assert evaluate([broken], _facts()) == []
    assert evaluate([_spec(kind="salary_floor", params={"amount": "70000"})], _facts()) == []


def test_detail_keys_are_exact_per_kind() -> None:
    expected = {
        "salary_floor": {"floor", "salary_min", "salary_max", "interval", "currency"},
        "exclude_keyword": {"term", "field", "count"},
        "location": {"location_norm", "allowed"},
        "remote": {"remote_flag", "require"},
        "seniority": {"seniority", "allow"},
        "company_blocklist": {"company_norm", "matched"},
    }
    firing = {
        "salary_floor": (
            _spec(kind="salary_floor", params={"amount": 80000, "currency": "EUR"}),
            _facts(salary_min=70000.0, salary_max=None),
        ),
        "exclude_keyword": (_spec(kind="exclude_keyword", params={"terms": ["python"]}), _facts()),
        "location": (
            _spec(kind="location", params={"allow": ["dublin"]}),
            _facts(location_norm="galway"),
        ),
        "remote": (_spec(kind="remote", params={"require": True}), _facts(remote_flag=False)),
        "seniority": (
            _spec(kind="seniority", params={"allow": ["staff"]}),
            _facts(seniority="mid"),
        ),
        "company_blocklist": (
            _spec(kind="company_blocklist", params={"companies": ["acme"]}),
            _facts(),
        ),
    }

    for kind, (spec, facts) in firing.items():
        outcomes = evaluate([spec], facts)
        assert len(outcomes) == 1, kind
        assert set(outcomes[0].detail) == expected[kind], kind


def test_listing_fact_fields_covers_every_listing_facts_attribute() -> None:
    assert {field for field in LISTING_FACT_FIELDS} == set(ListingFacts.__dataclass_fields__)
