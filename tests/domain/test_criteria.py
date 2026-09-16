"""FILT-01 / CRIT-01 — pure criteria assembly.

The two assemblers are the seam between a stored `criteria_json` blob / rule rows
and the pipeline's own types. These tests pin the contract the pipeline and the
criteria UI rely on: pass-through of documented keys, defaults for absent ones,
silence for unknown ones, a deterministic order across an unstable input order,
and equality across repeated calls.
"""

from __future__ import annotations

import ast
from pathlib import Path

from app.domain import criteria as criteria_module
from app.domain.criteria import rule_specs_from, search_query_from
from app.sources.base import SearchQuery

ROOT = Path(__file__).resolve().parents[2]
CRITERIA_PATH = ROOT / "app" / "domain" / "criteria.py"


def _imports(source: str) -> tuple[set[str], set[str]]:
    tree = ast.parse(source)
    modules: set[str] = set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)
            for alias in node.names:
                names.add(alias.name)
    return modules, names


# --- search_query_from --------------------------------------------------------
def test_a_full_criteria_mapping_round_trips_into_search_query_fields() -> None:
    query = search_query_from(
        {
            "keywords": "python engineer",
            "location": "Dublin",
            "distance_miles": 25,
            "remote_only": True,
            "salary_floor": 70000,
            "seniority": ["senior", "staff"],
            "hours_old": 168,
            "easy_apply": False,
            "results_wanted": 75,
        }
    )

    assert query.keywords == "python engineer"
    assert query.location == "Dublin"
    assert query.distance_miles == 25
    assert query.remote_only is True
    assert query.salary_floor == 70000
    assert query.seniority == ("senior", "staff")
    assert query.hours_old == 168
    assert query.easy_apply is False
    assert query.results_wanted == 75


def test_an_absent_key_falls_back_to_the_search_query_default() -> None:
    query = search_query_from({"keywords": "x"})

    assert query.location is None
    assert query.remote_only is None
    assert query.salary_floor is None
    assert query.seniority == ()
    assert query.offset == 0
    assert query.results_wanted == 50


def test_an_unknown_key_is_ignored_without_raising() -> None:
    query = search_query_from({"keywords": "x", "not_a_real_key": "surprise"})

    assert query.keywords == "x"
    assert not hasattr(query, "not_a_real_key")


def test_seniority_always_arrives_as_a_tuple() -> None:
    assert search_query_from({"keywords": "x", "seniority": "senior"}).seniority == ("senior",)
    assert search_query_from({"keywords": "x", "seniority": ["a", "b"]}).seniority == ("a", "b")
    assert search_query_from({"keywords": "x"}).seniority == ()


def test_missing_or_non_mapping_criteria_yields_empty_keywords() -> None:
    assert search_query_from(None) == SearchQuery(keywords="")
    assert search_query_from({"keywords": None}) == SearchQuery(keywords="")
    assert search_query_from({}) == SearchQuery(keywords="")  # type: ignore[arg-type]


# --- rule_specs_from ----------------------------------------------------------
def _rows() -> list[dict]:
    return [
        {
            "rule_id": "r-remote",
            "kind": "remote",
            "params": {"require": True},
            "position": 0,
            "enabled": True,
            "search_id": 1,
        },
        {
            "rule_id": "r-disabled",
            "kind": "location",
            "params_json": {"allow": ["dublin"]},
            "position": 1,
            "enabled": False,
            "search_id": 1,
        },
        {
            "rule_id": "r-unknown-kind",
            "kind": "not_a_kind",
            "params": {},
            "position": 2,
            "search_id": 1,
        },
        {
            "rule_id": "r-loaded-from-json",
            "kind": "company_blocklist",
            "params_json": {"companies": ["acme"]},
            "position": 0,
            "search_id": 0,
        },
    ]


def test_rule_specs_are_ordered_by_search_then_position() -> None:
    specs = rule_specs_from(_rows())

    assert [spec.rule_id for spec in specs] == ["r-loaded-from-json", "r-remote"]
    assert specs[1].params == {"require": True}
    assert specs[0].params == {"companies": ["acme"]}


def test_rule_specs_drop_disabled_and_unknown_kind_rows() -> None:
    ids = {spec.rule_id for spec in rule_specs_from(_rows())}

    assert "r-disabled" not in ids
    assert "r-unknown-kind" not in ids


def test_rule_specs_order_is_stable_under_an_unstable_input_order() -> None:
    rows = _rows()

    forward = [spec.rule_id for spec in rule_specs_from(rows)]
    backward = [spec.rule_id for spec in rule_specs_from(list(reversed(rows)))]

    assert forward == backward


def test_rule_specs_accept_a_raw_orm_row_id_and_params_json() -> None:
    specs = rule_specs_from(
        [
            {
                "id": 7,
                "kind": "salary_floor",
                "params_json": {"amount": 70000},
                "position": 3,
                "search_id": 2,
                "enabled": 1,
            }
        ]
    )

    assert len(specs) == 1
    assert specs[0].rule_id == "7"
    assert specs[0].params == {"amount": 70000}


def test_rule_specs_skip_non_mapping_rows_without_raising() -> None:
    assert rule_specs_from([None, "nonsense", 42]) == []  # type: ignore[list-item]
    assert rule_specs_from([]) == []


# --- pure-function idempotency (the CRIT-01 assumption) -----------------------
def test_repeated_calls_on_equal_input_return_equal_results() -> None:
    criteria = {"keywords": "python", "seniority": ["senior"], "results_wanted": 10}
    rows = _rows()

    assert search_query_from(criteria) == search_query_from(criteria)
    assert rule_specs_from(rows) == rule_specs_from(rows)


# --- module contracts ---------------------------------------------------------
def test_module_docstring_states_the_union_scope() -> None:
    doc = criteria_module.__doc__ or ""

    assert "union" in doc.casefold()
    assert "any enabled search's rule" in doc
    assert "removed from the queue" in doc


def test_module_does_not_import_settings_or_the_capability_compiler() -> None:
    modules, names = _imports(CRITERIA_PATH.read_text(encoding="utf-8"))

    assert all(not module.startswith("sqlalchemy") for module in modules)
    assert all(module != "app.config" for module in modules)
    assert "settings" not in names
    assert "compile_query_for_source" not in names
