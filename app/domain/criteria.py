"""Pure criteria assembly: a named search's criteria -> a `SearchQuery` + rule specs.

Two decisions this module encodes in one place:

* **D-32** — one unified named search carries both the fetch query *and* its own
  exclusion rules. Enabling the search adds both to the run.
* **A4 (union scope)** — the queue is the **union of every enabled search**. Every
  enabled search contributes its rules, and a listing is **removed from the queue
  when any enabled search's rule fires**. There is deliberately no column linking
  a listing to the search that retrieved it; a rule is a property of the search
  that owns it, and the queue is the union.

No settings, no I/O: the caller (the pipeline, or the criteria UI) supplies the
values, so this module is testable in isolation. `compile_query_for_source` is
deliberately **not** called here — capability compilation happens in the pipeline
against the resolved adapter, where the `SourceCapabilities` are actually known.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.domain.filter import RULE_KINDS, RuleSpec
from app.sources.base import SearchQuery

#: The `criteria_json` keys this assembler understands. Anything else is an
#: unrecognised key and is ignored rather than raising — an old criteria blob
#: must never break a run.
_QUERY_INT_KEYS = ("distance_miles", "salary_floor", "hours_old", "results_wanted")
_QUERY_BOOL_KEYS = ("remote_only", "easy_apply")

#: The user's work-mode preference. `remote`/`onsite` are HARD filters the
#: normalise stage's `remote_flag` can prove; `hybrid` is a RANKING hint only
#: because no board or listing carries a hybrid signal; `any` filters nothing. A
#: missing or unrecognised value means `any`, so an existing saved search is
#: unchanged.
WORK_MODES = ("any", "remote", "hybrid", "onsite")
DEFAULT_WORK_MODE = "any"


def work_mode_from(criteria: Mapping[str, Any] | None) -> str:
    """The stored work mode, or `any` when absent/unrecognised.

    Total like the rest of this module: a wrong-typed or unknown value degrades to
    `any` rather than raising, so a blob written by a different build cannot break a
    run.
    """
    data = criteria if isinstance(criteria, Mapping) else {}
    value = data.get("work_mode")
    return value if isinstance(value, str) and value in WORK_MODES else DEFAULT_WORK_MODE



def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _as_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _as_seniority(value: Any) -> tuple[str, ...] | None:
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(str(item) for item in value if isinstance(item, str) and item)
    return None


def search_query_from(criteria: Mapping[str, Any] | None) -> SearchQuery:
    """Assemble the pipeline's `SearchQuery` from a `criteria_json` mapping.

    Only keys with the expected type are passed through to `SearchQuery`; an
    absent **or wrong-typed** key is omitted so the `SearchQuery` default applies.
    `keywords` is required by `SearchQuery`, so a missing or empty value yields an
    **empty-string** keyword list rather than a crash — that choice is deliberate:
    the caller decides whether an empty-keyword search should run at all, and this
    pure module holds no keyword literal of its own.
    """
    data: Mapping[str, Any] = criteria if isinstance(criteria, Mapping) else {}

    keywords = data.get("keywords")
    kwargs: dict[str, Any] = {"keywords": keywords if isinstance(keywords, str) else ""}

    location = data.get("location")
    if isinstance(location, str):
        kwargs["location"] = location

    for key in _QUERY_INT_KEYS:
        parsed = _as_int(data.get(key))
        if parsed is not None:
            kwargs[key] = parsed

    for key in _QUERY_BOOL_KEYS:
        parsed_bool = _as_bool(data.get(key))
        if parsed_bool is not None:
            kwargs[key] = parsed_bool

    seniority = _as_seniority(data.get("seniority"))
    if seniority is not None:
        kwargs["seniority"] = seniority

    # `remote` is the one work mode a board can partly honour, so it also sets the
    # fetch-side `remote_only` hint. A legacy stored `remote_only` key (written
    # before the work-mode select existed) is still honoured unchanged by
    # `_QUERY_BOOL_KEYS`; the form no longer writes it. An explicit `remote` work
    # mode wins over a stale legacy value.
    if work_mode_from(data) == "remote":
        kwargs["remote_only"] = True

    return SearchQuery(**kwargs)


def rule_specs_from(rows: Iterable[Mapping[str, Any]]) -> list[RuleSpec]:
    """Map rule rows into `RuleSpec`s, ordered by `(search_id, position, rule_id)`.

    The ordering is what makes the union across several searches deterministic
    regardless of the caller's iteration order. Rows whose `enabled` is
    **explicitly falsey**, whose `kind` is outside `RULE_KINDS`, or which carry no
    identifier are dropped rather than crashing the run: a row written before a
    vocabulary change must degrade, not break ingestion.

    Both `params` and `params_json` are accepted, so the repository may pass a
    domain mapping or a raw row dict without a second adapter. The identifier is
    read from `rule_id` with `id` as the raw-ORM-row fallback.
    """
    keyed: list[tuple[int, int, str, RuleSpec]] = []

    for row in rows or ():
        if not isinstance(row, Mapping):
            continue
        if "enabled" in row and not row["enabled"]:
            continue

        kind = row.get("kind")
        if not isinstance(kind, str) or kind not in RULE_KINDS:
            continue

        rule_id = row.get("rule_id")
        if rule_id is None:
            rule_id = row.get("id")
        if rule_id is None:
            continue

        params = row.get("params")
        if params is None:
            params = row.get("params_json")
        if not isinstance(params, Mapping):
            params = {}

        position = _as_int(row.get("position"))
        if position is None:
            position = 0
        search_id = _as_int(row.get("search_id"))
        if search_id is None:
            search_id = 0

        spec = RuleSpec(
            rule_id=str(rule_id),
            kind=kind,
            params=params,
            position=position,
        )
        keyed.append((search_id, position, spec.rule_id, spec))

    keyed.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in keyed]


__all__ = [
    "DEFAULT_WORK_MODE",
    "WORK_MODES",
    "rule_specs_from",
    "search_query_from",
    "work_mode_from",
]
