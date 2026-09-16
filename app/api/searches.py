"""The criteria CRUD surface (CRIT-01 / CRIT-03 / FILT-04).

This is the write surface the phase's criteria layer was built for: named searches
with their own typed rules, created / edited / enabled / disabled / deleted from the
browser, plus the pre-run capability report and a per-search run action.

Design rules this module keeps:

* Every route declares `user: User = Depends(current_user)` — the auth seam
  `tests/test_auth_seam.py` guards.
* The route owns the commit; the repository (`app.db.repositories.search_repo`)
  never commits and never lets an ORM row escape.
* Every mutating POST returns the **`#criteria-list` fragment** so an `hx-post` can
  swap the list in place. The fragment markup lives in a macro in `criteria.html`,
  so the page and the swap render from one definition and cannot drift.
* Rule parameters come from **purpose-built form fields**, never a raw-JSON textarea,
  and the stored shape is validated by `search_repo.validate_rule_params` before any
  insert (T-02-31).
* No filter semantic is evaluated in a template (D-34). This module maps rows to a
  plain view model; the template only renders it.

Route families:

* `GET /searches` — the page: every search, its rules, and (task 3) the per-board
  capability warnings.
* `POST /searches` — create.
* `POST /searches/{id}` / `/toggle` / `/delete` — edit, enable/disable, delete.
* `POST /searches/{id}/rules` and `.../{rule_id}[/toggle|/delete]` — rule CRUD.
* `POST /searches/{id}/run` — run one search without touching the one-tap trigger.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.repositories import search_repo
from app.db.session import get_session
from app.domain.models import User

log = structlog.get_logger(__name__)

router = APIRouter()

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "web" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

CRITERIA_TEMPLATE = "html/criteria.html"
CRITERIA_ROOT_ID = "criteria-list"

#: Strong references to in-flight per-search run tasks, mirroring `app/api/runs.py`:
#: a fire-and-forget pipeline must not be garbage-collected before it finishes.
_BACKGROUND_TASKS: set[Any] = set()

#: Split a comma- or newline-separated free-text list into non-empty entries.
_TERM_SPLIT_RE = re.compile(r"[,\n]")


# --- form parsing helpers -----------------------------------------------------


class _UrlForm(Mapping[str, str]):
    """A minimal urlencoded-form view with `.get` / `.getlist`.

    htmx posts `application/x-www-form-urlencoded` (its default), and this project
    deliberately does not depend on `python-multipart`, which Starlette's
    `request.form()` requires for *any* form parsing. Parsing the urlencoded body
    with the standard library keeps the dependency out and is exactly the shape the
    browser sends. Repeated keys (`keyword_fields`, one per checkbox) become a list
    via `getlist`, mirroring Starlette's `FormData`.
    """

    __slots__ = ("_pairs",)

    def __init__(self, pairs: Sequence[tuple[str, str]]) -> None:
        self._pairs = list(pairs)

    def __getitem__(self, key: str) -> str:
        for name, value in self._pairs:
            if name == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        seen: dict[str, None] = {}
        for name, _value in self._pairs:
            seen.setdefault(name, None)
        return iter(seen)

    def __len__(self) -> int:
        return len(self._pairs)

    def get(self, name: str, default: Any = None) -> Any:
        for key, value in self._pairs:
            if key == name:
                return value
        return default

    def getlist(self, name: str) -> list[str]:
        return [value for key, value in self._pairs if key == name]


async def read_form(request: Request) -> _UrlForm:
    """Parse the request body as a urlencoded form, without python-multipart."""
    body = await request.body()
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:  # pragma: no cover — a malformed encoding must not 500
        text = body.decode("latin-1")
    return _UrlForm(parse_qsl(text, keep_blank_values=True))


def _field(form: Mapping[str, Any], name: str) -> str:
    value = form.get(name)
    return value.strip() if isinstance(value, str) else ""


def _checkbox(form: Mapping[str, Any], name: str) -> bool:
    value = form.get(name)
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() not in {"", "0", "false", "no", "off"}


def _split_terms(value: str) -> list[str]:
    return [part.strip() for part in _TERM_SPLIT_RE.split(value) if part.strip()]


def _int_field(form: Mapping[str, Any], name: str) -> tuple[int | None, str | None]:
    """An optional non-negative integer field: `(value, error)`."""
    raw = _field(form, name)
    if not raw:
        return None, None
    try:
        parsed = int(raw)
    except ValueError:
        return None, f"{name.replace('_', ' ')} must be a whole number."
    if parsed < 0:
        return None, f"{name.replace('_', ' ')} must not be negative."
    return parsed, None


def criteria_from_form(form: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Build the persisted `criteria_json` from the search form fields.

    Only the fetch-side keys this phase's contract names are read; anything else in
    the form is ignored rather than stored. A salary floor is validated here because
    the form accepts free text (the pure `search_query_from` would simply drop a
    wrong-typed value, which would be a silent no-op rather than a visible error).
    """
    criteria: dict[str, Any] = {}
    errors: list[str] = []

    keywords = _field(form, "keywords")
    if keywords:
        criteria["keywords"] = keywords

    location = _field(form, "location")
    if location:
        criteria["location"] = location

    if _checkbox(form, "remote_only"):
        criteria["remote_only"] = True

    salary_floor, salary_error = _int_field(form, "salary_floor")
    if salary_error:
        errors.append("Salary floor " + salary_error[0].lower() + salary_error[1:])
    elif salary_floor is not None:
        criteria["salary_floor"] = salary_floor

    seniority = _split_terms(_field(form, "seniority"))
    if seniority:
        criteria["seniority"] = seniority

    return criteria, errors


def rule_params_from_form(form: Any, kind: str) -> dict[str, Any]:
    """Build one rule's `params_json` from the fields of its own kind's form.

    Field names are namespaced per kind (`salary_amount`, `keyword_terms`,
    `location_allow`, ...) so a hidden group from another kind can never bleed into
    the submitted one. The resulting mapping is validated by
    `search_repo.validate_rule_params` before any insert.
    """
    if kind == "salary_floor":
        params: dict[str, Any] = {}
        amount, _error = _int_field(form, "salary_amount")
        if amount is not None:
            params["amount"] = amount
        currency = _field(form, "salary_currency")
        if currency:
            params["currency"] = currency
        interval = _field(form, "salary_interval")
        if interval:
            params["interval"] = interval
        return params

    if kind == "exclude_keyword":
        params = {"terms": _split_terms(_field(form, "keyword_terms"))}
        fields = [str(item) for item in form.getlist("keyword_fields")]
        if fields:
            params["fields"] = fields
        return params

    if kind == "location":
        params = {"allow": _split_terms(_field(form, "location_allow"))}
        mode = _field(form, "location_mode")
        if mode:
            params["mode"] = mode
        return params

    if kind == "remote":
        return {"require": _checkbox(form, "remote_require")}

    if kind == "seniority":
        return {
            "allow": _split_terms(_field(form, "seniority_allow")),
            "deny": _split_terms(_field(form, "seniority_deny")),
            "unknown_passes": _checkbox(form, "seniority_unknown_passes"),
        }

    if kind == "company_blocklist":
        params = {"companies": _split_terms(_field(form, "company_companies"))}
        match = _field(form, "company_match")
        if match:
            params["match"] = match
        return params

    # An unknown kind carries no fields; validate_rule_params rejects it by name.
    return {}


def describe_rule(kind: str, params: Mapping[str, Any] | None) -> str:
    """A human-readable one-line summary of a stored rule's parameters.

    Presentation only: it formats the stored values, it does not decide anything
    about a listing. Keeping it here (and not in the template) is the point of D-34.
    """
    data: Mapping[str, Any] = params if isinstance(params, Mapping) else {}
    if kind == "salary_floor":
        amount = data.get("amount")
        currency = data.get("currency") or "EUR"
        interval = data.get("interval") or "year"
        return f"below {amount} {currency}/{interval}"
    if kind == "exclude_keyword":
        terms = ", ".join(str(item) for item in (data.get("terms") or []))
        fields = ", ".join(str(item) for item in (data.get("fields") or [])) or "title, description"
        return f"any of [{terms}] in {fields}"
    if kind == "location":
        allowed = ", ".join(str(item) for item in (data.get("allow") or []))
        return f"outside [{allowed}]"
    if kind == "remote":
        return "not remote" if data.get("require", True) else "remote flag ignored"
    if kind == "seniority":
        allow = ", ".join(str(item) for item in (data.get("allow") or []))
        deny = ", ".join(str(item) for item in (data.get("deny") or []))
        parts = []
        if allow:
            parts.append(f"not in [{allow}]")
        if deny:
            parts.append(f"matching [{deny}]")
        return "; ".join(parts) or "no seniority terms"
    if kind == "company_blocklist":
        companies = ", ".join(str(item) for item in (data.get("companies") or []))
        return f"company in [{companies}]"
    return ""


# --- view model ---------------------------------------------------------------


def _rule_view(record: search_repo.RuleRecord) -> dict[str, Any]:
    return {
        "id": record.rule_id,
        "kind": record.kind,
        "params": dict(record.params_json or {}),
        "enabled": record.enabled,
        "position": record.position,
        "summary": describe_rule(record.kind, record.params_json),
    }


def _search_view(
    record: search_repo.SearchRecord,
    rules: Sequence[search_repo.RuleRecord],
    warnings: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "enabled": record.enabled,
        "version": record.version,
        "is_default": record.is_default,
        "last_run_at": record.last_run_at,
        "criteria": dict(record.criteria_json or {}),
        "rules": [_rule_view(rule) for rule in rules],
        "warnings": [dict(warning) for warning in warnings],
    }


async def build_search_views(
    session: AsyncSession,
    *,
    warnings_by_search: Mapping[int, Sequence[Mapping[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    """Every search, with its rules and any pre-computed capability warnings."""
    records = await search_repo.all_searches(session)
    warnings = warnings_by_search or {}
    views: list[dict[str, Any]] = []
    for record in records:
        rules = await search_repo.rules_for_search(session, record.id)
        views.append(_search_view(record, rules, warnings.get(record.id, ())))
    return views


def render_criteria_list(
    searches: Sequence[Mapping[str, Any]],
    *,
    errors: Sequence[str] | None = None,
    note: str | None = None,
) -> str:
    """Render the `#criteria-list` fragment from the macro in `criteria.html`.

    Jinja's `make_module` obtains the template's macros; for an extending template
    it also runs the page body (the `content` block), which is why the same
    `searches`/`errors`/`note` values are passed to it. One definition of the list
    markup serves the page and every `hx-post` swap.
    """
    module = templates.get_template(CRITERIA_TEMPLATE).make_module(
        {"searches": searches, "errors": errors, "note": note}
    )
    return str(module.criteria_list(searches=searches, errors=errors, note=note))


async def _render_list(
    request: Request,
    session: AsyncSession,
    *,
    errors: Sequence[str] | None = None,
    note: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    searches = await build_search_views(session)
    return HTMLResponse(
        render_criteria_list(searches, errors=errors, note=note),
        status_code=status_code,
    )


# --- routes -------------------------------------------------------------------


@router.get("/searches", response_class=HTMLResponse)
async def criteria_page(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """The criteria page: every search (enabled and disabled) with its rules."""
    searches = await build_search_views(session)
    return templates.TemplateResponse(
        request,
        CRITERIA_TEMPLATE,
        {"searches": searches, "errors": None, "note": None, "user": user},
    )


@router.post("/searches", response_class=HTMLResponse)
async def create_search_route(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Create a named search from the form; on error, no row is written."""
    form = await read_form(request)
    errors: list[str] = []

    name = _field(form, "name")
    if not name:
        errors.append("A search needs a name.")

    criteria, criteria_errors = criteria_from_form(form)
    errors.extend(criteria_errors)

    if not errors:
        try:
            created = await search_repo.create_search(
                session, name=name, criteria=criteria, now=datetime.now(UTC)
            )
        except ValueError as exc:
            errors.append(str(exc))
        else:
            await session.commit()
            return await _render_list(
                request, session, note=f"Saved search “{created.name}”."
            )

    return await _render_list(request, session, errors=errors)


@router.post("/searches/{search_id}/rules", response_class=HTMLResponse)
async def create_rule_route(
    search_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Create one rule of the selected kind from that kind's form fields."""
    form = await read_form(request)
    kind = _field(form, "kind")
    params = rule_params_from_form(form, kind)

    errors = search_repo.validate_rule_params(kind, params)
    if errors:
        return await _render_list(request, session, errors=errors, status_code=400)

    try:
        await search_repo.create_rule(
            session,
            search_id=search_id,
            kind=kind,
            params=params,
            position=0,
            now=datetime.now(UTC),
        )
    except ValueError as exc:
        return await _render_list(request, session, errors=[str(exc)], status_code=400)

    await session.commit()
    return await _render_list(request, session, note="Rule added.")


__all__ = [
    "CRITERIA_ROOT_ID",
    "build_search_views",
    "criteria_from_form",
    "describe_rule",
    "render_criteria_list",
    "router",
    "rule_params_from_form",
]
