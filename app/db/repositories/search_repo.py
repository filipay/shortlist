"""Search/rule/listing access — the read side *and* the write side of criteria.

**A4 union semantics (resolved user decision).** The queue is the **union of every
enabled search**. Rules are loaded from every enabled search, and a listing removed
by **any** enabled search's rule leaves the queue. There is deliberately no column
linking a listing to the search that retrieved it: a rule is a property of the
search that owns it, and the queue is their union.

This module is the only place the criteria/rules/listing SQL lives. It maps ORM
rows into frozen records so the pure layer (`app.domain.filter`,
`app.domain.criteria`) never sees a SQLAlchemy object — the dependency runs
repository -> domain, never the reverse.

Every function takes `session: AsyncSession` first, never commits (the caller owns
the commit) and leaves the flush to the caller, matching `source_repo.py`.

**The version contract (D-33).** A run stores its own criteria snapshot, so
`searches.version` is the reference that snapshot points at. A write that changes a
*stored criteria field* bumps `version` by exactly one; a write that does not is a
no-op for the version:

* `create_search` starts at `version == 1`; `update_search` bumps only when a
  supplied field actually differs from what is stored (an identical re-submit must
  not churn the version).
* `create_rule` / `update_rule` / `delete_rule` bump the **owning search's** version,
  because which rules exist and what they say is part of the effective criteria.
* `set_search_enabled` deliberately does **not** bump `version`: enabling or
  disabling a search is a scheduling decision, not a criteria change, and bumping
  on a toggle would make the version meaningless.

**FILT-04 boundary (a decision, not a gap).** "Tune filter rules from the UI without
a code change" is satisfied for the six `RULE_KINDS` and their documented
parameters. Adding a *new* kind is deliberately a coordinated change — the
migration's `ck_filter_rules_kind` CHECK, `RULE_KINDS`, the pure evaluator and the
per-kind form — because a typed row is what makes a rule safe to apply unattended.

**Write methods and the DB lane.** The write functions below are synchronous with
respect to correctness and are exercised by the manual-session DB lane
(`tests/db/test_search_repo_writes.py`), which owns the explicit commits. They are
here, not in `app/domain`, because validating a rule's *storage shape* is a
storage-boundary concern; the pure evaluator already degrades gracefully if a bad
row ever appears.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FilterRule, Listing, ListingDupe, Run, Search
from app.domain.filter import RULE_KINDS, ListingFacts
from app.domain.sanitize import sanitize_short_field


@dataclass(frozen=True)
class SearchRecord:
    """One `searches` row, as a pure value.

    The write functions return this shape, so it carries the fields the criteria
    page renders that a run does not need (`enabled`, `last_run_at`) as well as the
    ones the run snapshot reads (`name`, `criteria_json`, `version`).
    """

    id: int
    name: str
    criteria_json: Mapping[str, Any] | None
    version: int
    is_default: bool
    enabled: bool = True
    last_run_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class RuleRecord:
    """One `filter_rules` row.

    `rule_id` is the row id rendered as a string: `listing_exclusions.rule_id` is a
    `String(64)` column, and a stable string keeps the persisted evidence
    JSON-friendly and comparable across runs.

    `enabled` defaults to `True` so the run-side read (`rules_for_searches`) is
    unchanged; the criteria page reads rows of both states to render its inline
    toggle, and `as_mapping` then carries the real value so the run assembler drops
    a disabled rule.
    """

    search_id: int
    rule_id: str
    kind: str
    params_json: Mapping[str, Any] | None
    position: int
    enabled: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def as_mapping(self) -> dict[str, Any]:
        """The mapping `app.domain.criteria.rule_specs_from` consumes."""
        return {
            "search_id": self.search_id,
            "rule_id": self.rule_id,
            "kind": self.kind,
            "params_json": self.params_json,
            "position": self.position,
            "enabled": self.enabled,
        }


@dataclass(frozen=True)
class ListingRecord:
    """One listing this run touched, carrying exactly the `ListingFacts` fields."""

    id: int
    title: str
    title_norm: str | None
    description: str | None
    company_norm: str | None
    location_norm: str | None
    remote_flag: bool | None
    seniority: str | None
    salary_min: float | None
    salary_max: float | None
    salary_interval: str | None
    first_seen_at: datetime
    last_seen_at: datetime

    def as_facts(self) -> ListingFacts:
        """The pure evaluator input. The ORM row never crosses this boundary."""
        return ListingFacts(
            title=self.title or "",
            title_norm=self.title_norm,
            description=self.description,
            company_norm=self.company_norm,
            location_norm=self.location_norm,
            remote_flag=self.remote_flag,
            seniority=self.seniority,
            salary_min=self.salary_min,
            salary_max=self.salary_max,
            salary_interval=self.salary_interval,
        )


def _as_mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _search_record(row: Search) -> SearchRecord:
    """Map a `Search` row to the frozen record. The ORM row never escapes."""
    return SearchRecord(
        id=int(row.id),
        name=row.name or "",
        criteria_json=_as_mapping(row.criteria_json),
        version=int(row.version or 1),
        is_default=bool(row.is_default),
        enabled=bool(row.enabled),
        last_run_at=row.last_run_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _rule_record(row: FilterRule) -> RuleRecord:
    """Map a `FilterRule` row to the frozen record."""
    return RuleRecord(
        search_id=int(row.search_id),
        rule_id=str(row.id),
        kind=row.kind or "",
        params_json=_as_mapping(row.params_json),
        position=int(row.position or 0),
        enabled=bool(row.enabled),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def enabled_searches(session: AsyncSession) -> list[SearchRecord]:
    """Every enabled `searches` row, ordered by id (the union's group order)."""
    rows = (
        (await session.execute(select(Search).where(Search.enabled.is_(True)).order_by(Search.id)))
        .scalars()
        .all()
    )
    return [_search_record(row) for row in rows]


async def all_searches(session: AsyncSession) -> list[SearchRecord]:
    """Every `searches` row, enabled or not, ordered by id.

    The criteria page lists the disabled ones too: a disabled search is a saved
    intention the user expects to still see and re-enable, not a deleted one.
    """
    rows = (
        (await session.execute(select(Search).order_by(Search.id))).scalars().all()
    )
    return [_search_record(row) for row in rows]


async def search_by_id(session: AsyncSession, search_id: int) -> SearchRecord | None:
    """One search by id, whatever its `enabled` state, or `None`.

    The single-search run uses this rather than `enabled_searches`: "Run this one"
    is an explicit action on the search the user pointed at, so a disabled search
    is still runnable when asked for by id.
    """
    row = await session.get(Search, int(search_id))
    return _search_record(row) if row is not None else None


async def rules_for_searches(session: AsyncSession, search_ids: Iterable[int]) -> list[RuleRecord]:
    """Every enabled rule of the given searches, ordered `(search_id, position, id)`.

    The ordering is what makes the union's evaluation order deterministic: the same
    rows produce the same `RuleSpec` order on every run, so what a run recorded is
    reproducible (CRIT-02).
    """
    ids = [int(search_id) for search_id in (search_ids or ())]
    if not ids:
        return []

    rows = (
        (
            await session.execute(
                select(FilterRule)
                .where(FilterRule.search_id.in_(ids), FilterRule.enabled.is_(True))
                .order_by(FilterRule.search_id, FilterRule.position, FilterRule.id)
            )
        )
        .scalars()
        .all()
    )

    return [
        RuleRecord(
            search_id=int(row.search_id),
            rule_id=str(row.id),
            kind=row.kind or "",
            params_json=_as_mapping(row.params_json),
            position=int(row.position or 0),
            enabled=bool(row.enabled),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


async def rules_for_search(session: AsyncSession, search_id: int) -> list[RuleRecord]:
    """Every rule of one search, **enabled or disabled**, ordered `(position, id)`.

    The criteria page needs the disabled rows too: it renders their inline toggle,
    and an edit must be able to flip one back on. The run-side read
    (`rules_for_searches`) stays enabled-only; this read is for the UI.
    """
    rows = (
        (
            await session.execute(
                select(FilterRule)
                .where(FilterRule.search_id == int(search_id))
                .order_by(FilterRule.position, FilterRule.id)
            )
        )
        .scalars()
        .all()
    )
    return [_rule_record(row) for row in rows]


async def rule_by_id(session: AsyncSession, rule_id: int) -> RuleRecord | None:
    """One rule by id, or `None`. The route needs its kind to parse an edit form."""
    row = await session.get(FilterRule, int(rule_id))
    return _rule_record(row) if row is not None else None


async def active_listings(session: AsyncSession, *, run_id: int) -> list[ListingRecord]:
    """The listings this run touched, excluding absorbed twins, ordered by id.

    "Touched by this run" reuses the Phase-1 convention (`last_seen_at >=
    run.started_at`, the same window `source_repo.get_source_health` uses) rather
    than inventing a `listings.run_id` column — `listings` has no run association by
    design, and the pipeline stamps every row it touches with the run's own clock.

    An **absorbed twin** is skipped: a listing that appears as `dup_listing_id` in an
    un-reverted `listing_dupes` row is not visible in the queue, so it is not a
    candidate for its own exclusion row. Its own exclusion evidence belongs to the
    survivor's story, and plan 02-07 owns the read-side visibility predicate.
    """
    run = await session.get(Run, run_id)
    if run is None or run.started_at is None:
        return []

    absorbed = (
        (
            await session.execute(
                select(ListingDupe.dup_listing_id).where(ListingDupe.reverted_at.is_(None))
            )
        )
        .scalars()
        .all()
    )
    absorbed_ids = {int(listing_id) for listing_id in absorbed}

    rows = (
        (
            await session.execute(
                select(Listing)
                .where(
                    Listing.is_active.is_(True),
                    Listing.last_seen_at >= run.started_at,
                )
                .order_by(Listing.id)
            )
        )
        .scalars()
        .all()
    )

    return [
        ListingRecord(
            id=int(row.id),
            title=row.title or "",
            title_norm=row.title_norm,
            description=row.description,
            company_norm=row.company_norm,
            location_norm=row.location_norm,
            remote_flag=row.remote_flag,
            seniority=row.seniority,
            salary_min=row.salary_min,
            salary_max=row.salary_max,
            salary_interval=row.salary_interval,
            first_seen_at=row.first_seen_at,
            last_seen_at=row.last_seen_at,
        )
        for row in rows
        if int(row.id) not in absorbed_ids
    ]


# --- the write half (D-32 / CRIT-01 / FILT-04) --------------------------------
#
# Every write below is wrapped in a SAVEPOINT (`session.begin_nested()`), matching
# `source_repo`'s fallible-write idiom, so one bad statement cannot poison a wider
# transaction the caller may have opened. The caller still owns the commit.

#: The longest a stored search name may be, in Python characters.
SEARCH_NAME_MAX_CHARS = 255

#: The longest a stored free-text criteria value / rule term may be. A term is
#: user input rendered back into a page, so it is bounded exactly like a name.
SEARCH_TERM_MAX_CHARS = 256

#: The fetch-side `criteria_json` keys that carry free text. Only these are
#: sanitised; the numeric/boolean keys are validated, not rewritten.
_CRITERIA_TEXT_KEYS = ("keywords", "location")

#: The `exclude_keyword.fields` allow-list (mirrors `app.domain.filter`).
_KEYWORD_FIELD_CHOICES = ("title", "description")


def _as_str_list(value: Any) -> list[str] | None:
    """A list of non-empty strings, or `None` when the value is not usable.

    A bare string is accepted as a one-element list so a form and a direct API
    caller can both be validated by the same function.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set, frozenset)):
        return [str(item) for item in value if isinstance(item, str) and item]
    return None


def _sanitise_text(value: str) -> str:
    return sanitize_short_field(value, max_chars=SEARCH_TERM_MAX_CHARS).text


def _sanitise_value(value: Any) -> Any:
    """Recursively sanitise the string leaves of a stored JSON value.

    Only `str` leaves are touched (and lists/mappings are rebuilt around them), so
    an `int` amount or a `bool` flag is never coerced. A name, keyword or term is
    user text rendered back into a page, so it passes the same sanitiser at the
    storage boundary — autoescape stays the render-time guarantee, this is the
    store-time one.
    """
    if isinstance(value, str):
        return _sanitise_text(value)
    if isinstance(value, (list, tuple)):
        return [_sanitise_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _sanitise_value(item) for key, item in value.items()}
    return value


def _sanitise_criteria(criteria: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """The stored `criteria_json`: free-text keys sanitised, the rest as supplied."""
    if not isinstance(criteria, Mapping):
        return None
    cleaned = {str(key): value for key, value in criteria.items()}
    for key in _CRITERIA_TEXT_KEYS:
        value = cleaned.get(key)
        if isinstance(value, str):
            cleaned[key] = _sanitise_text(value)
    seniority = cleaned.get("seniority")
    if isinstance(seniority, (list, tuple)):
        cleaned["seniority"] = [_sanitise_text(item) for item in seniority if isinstance(item, str)]
    return cleaned


def validate_rule_params(kind: str, params: Mapping[str, Any] | None) -> list[str]:
    """Human-readable errors for one rule's `(kind, params)`; empty means valid.

    This is the storage-boundary guard for T-02-31: the form is not the only way a
    rule can be written, so the *shape* is validated here before any insert. It is
    deliberately per-kind and strict about the required keys, because the pure
    evaluator degrades a malformed rule to a silent skip — which is safe but
    invisible — whereas this reports the misconfiguration to the person who made it.

    An unknown `kind` is a single error naming `RULE_KINDS`, never a partial pass.
    """
    if kind not in RULE_KINDS:
        return [f"unknown rule kind {kind!r}; expected one of {sorted(RULE_KINDS)}"]

    data: Mapping[str, Any] = params if isinstance(params, Mapping) else {}
    errors: list[str] = []

    if kind == "salary_floor":
        amount = data.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            errors.append("salary_floor.amount must be a non-negative integer")
        for key in ("currency", "interval"):
            value = data.get(key)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                errors.append(f"salary_floor.{key} must be a non-empty string")

    elif kind == "exclude_keyword":
        if not _as_str_list(data.get("terms")):
            errors.append(
                "exclude_keyword.terms must be a non-empty list of non-empty strings"
            )
        fields = data.get("fields")
        # An absent or empty `fields` is valid: the evaluator defaults it to
        # `title, description`. Only a *populated* list is checked for bad entries.
        if fields:
            listed = _as_str_list(fields)
            if listed is None or any(item not in _KEYWORD_FIELD_CHOICES for item in listed):
                errors.append(
                    "exclude_keyword.fields must be a list drawn from "
                    + ", ".join(_KEYWORD_FIELD_CHOICES)
                )

    elif kind == "location":
        if not _as_str_list(data.get("allow")):
            errors.append("location.allow must be a non-empty list")

    elif kind == "remote":
        if not isinstance(data.get("require"), bool):
            errors.append("remote.require must be a boolean")

    elif kind == "seniority":
        for key in ("allow", "deny"):
            value = data.get(key)
            if value is not None and _as_str_list(value) is None:
                errors.append(f"seniority.{key} must be a list of strings")
        if not isinstance(data.get("unknown_passes"), bool):
            errors.append("seniority.unknown_passes must be a boolean")

    elif kind == "company_blocklist":
        if not _as_str_list(data.get("companies")):
            errors.append("company_blocklist.companies must be a non-empty list")

    return errors


async def _bump_search_version(session: AsyncSession, search_id: int, now: datetime) -> None:
    """Increment the owning search's `version` and stamp `updated_at`."""
    row = await session.get(Search, int(search_id))
    if row is None:
        return
    row.version = int(row.version or 1) + 1
    row.updated_at = now


async def create_search(
    session: AsyncSession,
    *,
    name: str,
    criteria: Mapping[str, Any] | None,
    now: datetime,
    is_default: bool = False,
) -> SearchRecord:
    """Insert a search with `enabled=True` and `version == 1`.

    The name is sanitised before it is stored (it is user text rendered back into
    the criteria page). An empty name is rejected rather than persisted: a
    nameless search cannot be identified in the list or in a run snapshot.
    """
    clean_name = sanitize_short_field(name, max_chars=SEARCH_NAME_MAX_CHARS).text
    if not clean_name.strip():
        raise ValueError("a search needs a name")

    async with session.begin_nested():
        row = Search(
            name=clean_name,
            enabled=True,
            is_default=bool(is_default),
            criteria_json=_sanitise_criteria(criteria),
            version=1,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.flush()
    return _search_record(row)


async def update_search(
    session: AsyncSession,
    *,
    search_id: int,
    name: str | None = None,
    criteria: Mapping[str, Any] | None = None,
    now: datetime,
) -> SearchRecord | None:
    """Change only the fields supplied; bump `version` only on a real change.

    An identical re-submit (the same criteria mapping) must **not** churn the
    version: a run's snapshot points at a version number, and inflating it on every
    keystroke-and-save would make that reference meaningless (T-02-33). A supplied
    field that differs from what is stored bumps the version by exactly one.
    """
    row = await session.get(Search, int(search_id))
    if row is None:
        return None

    changed = False
    if name is not None:
        clean_name = sanitize_short_field(name, max_chars=SEARCH_NAME_MAX_CHARS).text
        if not clean_name.strip():
            raise ValueError("a search needs a name")
        if clean_name != row.name:
            row.name = clean_name
            changed = True

    if criteria is not None:
        clean_criteria = _sanitise_criteria(criteria)
        if dict(row.criteria_json or {}) != dict(clean_criteria or {}):
            row.criteria_json = clean_criteria
            changed = True

    if changed:
        async with session.begin_nested():
            row.version = int(row.version or 1) + 1
            row.updated_at = now
            await session.flush()
    return _search_record(row)


async def set_search_enabled(
    session: AsyncSession,
    *,
    search_id: int,
    enabled: bool,
    now: datetime,
) -> SearchRecord | None:
    """Write `enabled` and `updated_at` **only**.

    `version` is deliberately not bumped. Enabling or disabling a search is a
    scheduling decision about *whether* its criteria run, not a change to *what*
    the criteria are; a run's snapshot records the criteria, and which searches
    contributed is recorded by the run's own snapshot set. Bumping the version on a
    toggle would make the version a counter of clicks rather than of criteria states
    (D-33 / T-02-33 / this plan's flagged assumptions).
    """
    row = await session.get(Search, int(search_id))
    if row is None:
        return None

    if bool(row.enabled) != bool(enabled):
        async with session.begin_nested():
            row.enabled = bool(enabled)
            row.updated_at = now
            await session.flush()
    return _search_record(row)


async def delete_search(session: AsyncSession, *, search_id: int) -> bool:
    """Delete a search and its rules, touching nothing else. Returns whether a row went.

    Listings, `listing_exclusions`, `listing_dupes` and every other `runs` row are
    untouched: a completed run keeps its own `criteria_snapshot_json`, which is
    exactly why D-33 chose a snapshot over a foreign-key join. The one concession
    the schema forces: `runs.search_id` is a plain FK with no `ON DELETE SET NULL`
    and `PRAGMA foreign_keys=ON` is enforced, so deleting a search that a run points
    at must first clear that nullable pointer. The run row survives with its
    snapshot; only the dangling id is released.
    """
    row = await session.get(Search, int(search_id))
    if row is None:
        return False

    async with session.begin_nested():
        await session.execute(
            update(Run).where(Run.search_id == int(search_id)).values(search_id=None)
        )
        await session.execute(
            delete(FilterRule).where(FilterRule.search_id == int(search_id))
        )
        await session.delete(row)
        await session.flush()
    return True


async def create_rule(
    session: AsyncSession,
    *,
    search_id: int,
    kind: str,
    params: Mapping[str, Any] | None,
    position: int,
    now: datetime,
) -> RuleRecord:
    """Insert one enabled rule and bump the owning search's version.

    The params are validated and sanitised before any insert: an invalid rule is
    never persisted (T-02-31). A rule edit is a criteria change, so the version must
    move — that is what makes a run's snapshot point at the rule set it actually
    used.
    """
    clean_params = _sanitise_value(params) if isinstance(params, Mapping) else params
    errors = validate_rule_params(kind, clean_params)
    if errors:
        raise ValueError("; ".join(errors))

    async with session.begin_nested():
        row = FilterRule(
            search_id=int(search_id),
            kind=kind,
            params_json=clean_params,
            enabled=True,
            position=int(position),
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.flush()
        await _bump_search_version(session, search_id, now)
        await session.flush()
    return _rule_record(row)


async def update_rule(
    session: AsyncSession,
    *,
    rule_id: int,
    params: Mapping[str, Any] | None = None,
    enabled: bool | None = None,
    position: int | None = None,
    now: datetime,
) -> RuleRecord | None:
    """Change only the supplied fields of one rule, bumping the search on a change.

    A toggle of a *rule* bumps the owning search's version, unlike a toggle of a
    whole search (`set_search_enabled`): which rules are enabled is part of the
    effective criteria, so it belongs in the snapshot the version references; whether
    a search is scheduled at all is not.
    """
    row = await session.get(FilterRule, int(rule_id))
    if row is None:
        return None

    changed = False
    if params is not None:
        clean_params = _sanitise_value(params)
        errors = validate_rule_params(row.kind or "", clean_params)
        if errors:
            raise ValueError("; ".join(errors))
        if dict(row.params_json or {}) != dict(clean_params or {}):
            row.params_json = clean_params
            changed = True

    if enabled is not None and bool(row.enabled) != bool(enabled):
        row.enabled = bool(enabled)
        changed = True

    if position is not None and int(row.position or 0) != int(position):
        row.position = int(position)
        changed = True

    if changed:
        async with session.begin_nested():
            row.updated_at = now
            await session.flush()
            await _bump_search_version(session, row.search_id, now)
            await session.flush()
    return _rule_record(row)


async def delete_rule(session: AsyncSession, *, rule_id: int) -> bool:
    """Delete one rule and bump the owning search's version. A second delete is `False`."""
    row = await session.get(FilterRule, int(rule_id))
    if row is None:
        return False

    search_id = int(row.search_id)
    now = datetime.now(UTC)
    async with session.begin_nested():
        await session.delete(row)
        await session.flush()
        await _bump_search_version(session, search_id, now)
        await session.flush()
    return True


__all__ = [
    "ListingRecord",
    "RuleRecord",
    "SEARCH_NAME_MAX_CHARS",
    "SEARCH_TERM_MAX_CHARS",
    "SearchRecord",
    "active_listings",
    "all_searches",
    "create_rule",
    "create_search",
    "delete_rule",
    "delete_search",
    "enabled_searches",
    "rule_by_id",
    "rules_for_search",
    "rules_for_searches",
    "search_by_id",
    "set_search_enabled",
    "update_rule",
    "update_search",
    "validate_rule_params",
]
