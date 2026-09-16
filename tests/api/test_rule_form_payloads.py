"""CRIT-03 regression guard: the criteria page's htmx requests must carry fields.

History (the bug this file exists for): the "Add rule" and "Save rule" buttons were
``type="button"`` elements that lived in a plain ``<div>`` — not a ``<form>`` — and
carried no ``hx-include``/``hx-vals``. htmx 2.0.10 resolves a non-GET request body
from ``getRelatedForm(elt)`` (``elt.form || closest(elt, 'form')``), which is
``null`` for those buttons, so ``getInputValues`` handed ``null`` to
``processInputValue`` and the button itself was rejected by ``shouldInclude``. The
POST went out with a **zero-parameter** urlencoded body, ``kind`` was absent, and
``create_rule_route`` / ``edit_rule_route`` answered **400** — the browser
rule-authoring surface was dead.

``_payload`` below re-implements the htmx 2.0.10 lookup order from
``node_modules/htmx.org/dist/htmx.js`` (``getRelatedForm`` :2853,
``getInputValues`` :3602, ``shouldInclude`` :3451, ``processInputValue`` :3521,
``findAttributeTargets`` :1354): related form first, then the element itself, then
the clicked button's own value, then every ``hx-include`` target (enclosing all
inputs within a matched non-input element). A template that drops the fields again
fails here, before a browser is ever opened.

The API lane then POSTs that exact computed body to the real routes, proving the
server accepts the six rule kinds rather than 400ing on an empty request.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from html.parser import HTMLParser
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import FilterRule, Search  # noqa: F401 — Search is a real table seed

# --- a tiny DOM, enough for htmx's form/include lookups -----------------------

_VOID_TAGS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)
# htmx's INPUT_SELECTOR (`htmx.js` :2226) — buttons are deliberately absent.
_INPUT_TAGS = frozenset({"input", "select", "textarea"})
_MUTATION_METHODS = ("post", "put", "patch", "delete")


class _Node:
    __slots__ = ("tag", "attrs", "parent", "children", "text_parts")

    def __init__(self, tag: str, attrs: list[tuple[str, str | None]], parent: _Node | None) -> None:
        self.tag = tag
        self.attrs = {name: (value or "") for name, value in attrs}
        self.parent = parent
        self.children: list[_Node] = []
        self.text_parts: list[str] = []


class _DomParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("#document", [], None)
        self._stack: list[_Node] = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Node(tag, attrs, self._stack[-1])
        self._stack[-1].children.append(node)
        if tag not in _VOID_TAGS:
            self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._stack[-1].children.append(_Node(tag, attrs, self._stack[-1]))

    def handle_endtag(self, tag: str) -> None:
        while len(self._stack) > 1:
            if self._stack[-1].tag == tag:
                self._stack.pop()
                return
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        self._stack[-1].text_parts.append(data)


def _parse(html: str) -> _Node:
    parser = _DomParser()
    parser.feed(html)
    return parser.root


def _walk(node: _Node) -> Iterator[_Node]:
    yield node
    for child in node.children:
        yield from _walk(child)


def _root(node: _Node) -> _Node:
    current = node
    while current.parent is not None:
        current = current.parent
    return current


def _text(node: _Node) -> str:
    return "".join(node.text_parts)


def _matches(node: _Node, selector: str) -> bool:
    """Only the selectors this project's templates use: tag, ``.class``, ``#id``."""
    if selector.startswith("."):
        return selector[1:] in (node.attrs.get("class") or "").split()
    if selector.startswith("#"):
        return node.attrs.get("id") == selector[1:]
    return node.tag == selector


def _closest(node: _Node | None, selector: str) -> _Node | None:
    current = node
    while current is not None and current.tag != "#document":
        if _matches(current, selector):
            return current
        current = current.parent
    return None


def _descendants(node: _Node, tags: frozenset[str]) -> list[_Node]:
    return [n for n in _walk(node) if n is not node and n.tag in tags]


def _in_disabled_fieldset(node: _Node) -> bool:
    current = node.parent
    while current is not None and current.tag != "#document":
        if current.tag == "fieldset" and "disabled" in current.attrs:
            return True
        current = current.parent
    return False


def _should_include(node: _Node) -> bool:
    """htmx ``shouldInclude`` (``htmx.js`` :3451)."""
    name = node.attrs.get("name")
    if not name or "disabled" in node.attrs or _in_disabled_fieldset(node):
        return False
    kind = (node.attrs.get("type") or "").lower()
    if kind in {"button", "submit"} or node.tag in {"image", "reset", "file"}:
        return False
    if kind in {"checkbox", "radio"}:
        return "checked" in node.attrs
    return True


def _value(node: _Node) -> str:
    """htmx ``getValueFromInput`` (``htmx.js`` :3502) for the shapes in use."""
    if node.tag == "select":
        options = [child for child in node.children if child.tag == "option"]
        if not options:
            return ""
        chosen = next((o for o in options if "selected" in o.attrs), options[0])
        return chosen.attrs.get("value", _text(chosen)).strip()
    if node.tag == "textarea":
        return _text(node)
    return node.attrs.get("value", "")


def _add(bucket: dict[str, list[str]], name: str, value: str) -> None:
    bucket.setdefault(name, []).append(value)


def _processed_add(bucket: dict[str, list[str]], node: _Node, processed: set[int]) -> None:
    """htmx ``processInputValue`` (``htmx.js`` :3521)."""
    if id(node) in processed:
        return
    processed.add(id(node))
    if _should_include(node):
        name = node.attrs.get("name")
        assert name is not None
        _add(bucket, name, _value(node))
    if node.tag == "form":
        for child in _descendants(node, _INPUT_TAGS):
            if id(child) not in processed:
                processed.add(id(child))
                if _should_include(child):
                    name = child.attrs.get("name")
                    assert name is not None
                    _add(bucket, name, _value(child))


def _related_form(node: _Node) -> _Node | None:
    """htmx ``getRelatedForm`` (``htmx.js`` :2853): ``elt.form || closest(elt,'form')``."""
    form_id = node.attrs.get("form")
    if form_id:
        for candidate in _walk(_root(node)):
            if candidate.attrs.get("id") == form_id:
                return candidate
    if node.tag == "form":
        return node
    return _closest(node, "form")


def _resolve_include(node: _Node, selector: str) -> list[_Node]:
    selector = selector.strip()
    if selector.startswith("closest "):
        found = _closest(node, selector[len("closest ") :].strip())
        return [found] if found is not None else []
    return [n for n in _walk(_root(node)) if n.tag != "#document" and _matches(n, selector)]


def _payload(node: _Node) -> dict[str, list[str]]:
    """The urlencoded body htmx 2.0.10 would POST for this element.

    Keys map to every value sent (repeated keys keep their order), mirroring
    ``getInputValues``' related-form / self / clicked-button / ``hx-include``
    order and its priority override.
    """
    processed: set[int] = set()
    regular: dict[str, list[str]] = {}
    priority: dict[str, list[str]] = {}

    related_form = _related_form(node)
    if related_form is not None:
        _processed_add(priority, related_form, processed)
    _processed_add(regular, node, processed)

    is_submit_input = node.tag == "input" and (node.attrs.get("type") or "").lower() == "submit"
    if node.tag == "button" or is_submit_input:
        name = node.attrs.get("name")
        if name:
            _add(priority, name, node.attrs.get("value", ""))

    include_value = node.attrs.get("hx-include")
    if include_value:
        for selector in (part.strip() for part in include_value.split(",")):
            if not selector:
                continue
            for matched in _resolve_include(node, selector):
                _processed_add(regular, matched, processed)
                if matched.tag != "form":
                    for descendant in _descendants(matched, _INPUT_TAGS):
                        _processed_add(regular, descendant, processed)

    final = {key: list(value) for key, value in regular.items() if key not in priority}
    final.update({key: list(value) for key, value in priority.items()})
    return final


def _mutation(node: _Node) -> tuple[str, str] | None:
    for method in _MUTATION_METHODS:
        url = node.attrs.get(f"hx-{method}")
        if url:
            return method, url
    return None


def _by_class(nodes: list[_Node], css_class: str) -> list[_Node]:
    return [n for n in nodes if css_class in (n.attrs.get("class") or "").split()]


# --- route requirements for the criteria page ---------------------------------

#: Routes on the criteria page that read a request body, and a required field.
#: `POST /searches` and `POST /searches/{id}` are real `<form>`s (they worked);
#: the two rule routes were the broken ones.
_BODY_ROUTES: tuple[tuple[re.Pattern[str], set[str]], ...] = (
    (re.compile(r"^/searches$"), {"name"}),
    (re.compile(r"^/searches/\d+$"), {"name"}),
    (re.compile(r"^/searches/\d+/rules$"), {"kind"}),
    (re.compile(r"^/searches/\d+/rules/\d+$"), {"position"}),
)
#: The mutating criteria routes that read the id from the path, never a body.
_NO_BODY_ROUTES: tuple[re.Pattern[str], ...] = (
    re.compile(r"^/searches/\d+/(toggle|delete|run)$"),
    re.compile(r"^/searches/\d+/rules/\d+/(toggle|delete)$"),
)

#: Every field the "Add rule" macro renders, per kind. The whole `.rule-form` is
#: one payload (htmx includes every enclosed input), so all of these must survive.
_ADD_KIND_FIELDS = {
    "salary_floor": {"salary_amount", "salary_currency", "salary_interval"},
    "exclude_keyword": {"keyword_terms", "keyword_fields"},
    "location": {"location_allow", "location_mode"},
    "remote": {"remote_require"},
    "seniority": {"seniority_allow", "seniority_deny", "seniority_unknown_passes"},
    "company_blocklist": {"company_companies", "company_match"},
}

#: The edit form carries only its own kind's fields plus `position`.
_EDIT_KIND_FIELDS = {
    "salary_floor": {"salary_amount", "salary_currency", "salary_interval"},
    "exclude_keyword": {"keyword_terms", "keyword_fields"},
    "location": {"location_allow", "location_mode"},
    "remote": {"remote_require"},
    "seniority": {"seniority_allow", "seniority_deny", "seniority_unknown_passes"},
    "company_blocklist": {"company_companies", "company_match"},
}

#: Meaningful values for the kind-specific fields of the add form's payload.
_VALUES: dict[str, dict[str, list[str]]] = {
    "salary_floor": {
        "salary_amount": ["60000"],
        "salary_currency": ["EUR"],
        "salary_interval": ["year"],
    },
    "exclude_keyword": {"keyword_terms": ["crypto, nft"]},
    "location": {"location_allow": ["Dublin, Remote"], "location_mode": ["substring"]},
    "remote": {"remote_require": ["1"]},
    "seniority": {
        "seniority_allow": ["senior, lead"],
        "seniority_deny": ["intern"],
        "seniority_unknown_passes": ["1"],
    },
    "company_blocklist": {
        "company_companies": ["Acme, Globex"],
        "company_match": ["norm_equals"],
    },
}

#: What `rule_params_from_form` + `validate_rule_params` must store for each kind.
_EXPECTED_PARAMS: dict[str, dict[str, Any]] = {
    "salary_floor": {"amount": 60000, "currency": "EUR", "interval": "year"},
    "exclude_keyword": {"terms": ["crypto", "nft"], "fields": ["title", "description"]},
    "location": {"allow": ["Dublin", "Remote"], "mode": "substring"},
    "remote": {"require": True},
    "seniority": {
        "allow": ["senior", "lead"],
        "deny": ["intern"],
        "unknown_passes": True,
    },
    "company_blocklist": {"companies": ["Acme", "Globex"], "match": "norm_equals"},
}


async def _only_search_id(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        rows = list((await session.execute(select(Search))).scalars().all())
    assert len(rows) == 1
    return int(rows[0].id)


async def _rule_rows(session_factory: async_sessionmaker[AsyncSession]) -> list[FilterRule]:
    async with session_factory() as session:
        return list((await session.execute(select(FilterRule))).scalars().all())


def _add_button(root: _Node) -> _Node:
    buttons = [
        n
        for n in _walk(root)
        if n.tag == "button" and "rule-submit" in (n.attrs.get("class") or "").split()
    ]
    assert len(buttons) == 1, "expected exactly one 'Add rule' button"
    return buttons[0]


def _edit_save_for(root: _Node, rule_id: int) -> _Node:
    matches = []
    for node in _walk(root):
        if node.tag != "button" or "rule-edit-save" not in (node.attrs.get("class") or "").split():
            continue
        wrapper = _closest(node, ".rule-edit")
        if wrapper is not None and wrapper.attrs.get("data-rule-id") == str(rule_id):
            matches.append(node)
    assert len(matches) == 1, f"expected exactly one 'Save rule' button for rule {rule_id}"
    return matches[0]


# --- the structural regression guard ------------------------------------------


async def test_every_criteria_htmx_request_sends_the_fields_its_route_reads(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Every mutating htmx element on `/searches` resolves the body its route needs.

    Before the fix, the two rule buttons computed an **empty** payload, so this
    fails at the first `assert payload` with the htmx-empty-body symptom.
    """
    await client.post("/searches", data={"name": "Dublin Python", "keywords": "python"})
    search_id = await _only_search_id(session_factory)

    for kind in _VALUES:
        body = {"kind": [kind], **_VALUES[kind]}
        created = await client.post(f"/searches/{search_id}/rules", data=body)
        assert created.status_code == 200, (kind, created.status_code)

    rules = await _rule_rows(session_factory)
    assert len(rules) == len(_VALUES)
    kind_by_rule = {int(rule.id): rule.kind for rule in rules}

    page = await client.get("/searches")
    assert page.status_code == 200
    root = _parse(page.text)

    mutating = [node for node in _walk(root) if node.tag != "#document" and _mutation(node)]
    assert mutating, "the DOM parser found no mutating htmx elements"

    for node in mutating:
        method, url = _mutation(node) or ("", "")
        required = next((req for pattern, req in _BODY_ROUTES if pattern.match(url)), None)
        is_body_route = required is not None
        is_no_body = any(pattern.match(url) for pattern in _NO_BODY_ROUTES)
        assert is_body_route or is_no_body, f"unaudited mutating htmx element: {method} {url}"
        if not is_body_route:
            continue

        payload = _payload(node)
        assert payload, f"htmx would send an empty body for {method} {url}"
        missing = required - set(payload)
        assert not missing, f"{method} {url} payload is missing {missing}: {payload}"

    # The "Add rule" button must carry every kind group of its `.rule-form`.
    add_payload = _payload(_add_button(root))
    assert add_payload.get("kind") == ["salary_floor"]
    for kind, fields in _ADD_KIND_FIELDS.items():
        assert fields <= set(add_payload), f"add payload lost {kind} fields: {add_payload}"

    # Each "Save rule" button must carry its own kind's fields + `position`.
    for rule_id, kind in kind_by_rule.items():
        edit_payload = _payload(_edit_save_for(root, rule_id))
        assert "position" in edit_payload, f"edit payload for {kind} lost position"
        missing = _EDIT_KIND_FIELDS[kind] - set(edit_payload)
        assert not missing, f"edit payload for {kind} is missing {missing}: {edit_payload}"


# --- the end-to-end API lane ---------------------------------------------------


@pytest.mark.parametrize("kind", sorted(_VALUES))
async def test_each_rule_kinds_rendered_body_is_accepted_and_editable(
    client, session_factory: async_sessionmaker[AsyncSession], kind: str
) -> None:
    """POST the exact body htmx would compute, for all six kinds, via real routes."""
    await client.post("/searches", data={"name": "Dublin Python"})
    search_id = await _only_search_id(session_factory)

    page = await client.get("/searches")
    assert page.status_code == 200
    root = _parse(page.text)

    # Start from the rendered "Add rule" form's payload, choose the kind, fill it.
    add_payload = _payload(_add_button(root))
    assert add_payload, "the 'Add rule' button sent an empty body"
    add_payload["kind"] = [kind]
    for field, values in _VALUES[kind].items():
        add_payload[field] = values

    created = await client.post(f"/searches/{search_id}/rules", data=add_payload)

    assert created.status_code == 200, created.text
    assert "Rule added." in created.text

    rules = await _rule_rows(session_factory)
    assert len(rules) == 1
    assert rules[0].kind == kind
    assert rules[0].params_json == _EXPECTED_PARAMS[kind]

    # The edit form is pre-filled from the stored rule; posting it back is a no-op.
    page = await client.get("/searches")
    root = _parse(page.text)
    edit_payload = _payload(_edit_save_for(root, int(rules[0].id)))
    for field, values in _VALUES[kind].items():
        edit_payload[field] = values

    saved = await client.post(f"/searches/{search_id}/rules/{rules[0].id}", data=edit_payload)

    assert saved.status_code == 200, saved.text
    assert "Rule saved." in saved.text
    rules = await _rule_rows(session_factory)
    assert rules[0].params_json == _EXPECTED_PARAMS[kind]


async def test_the_location_edit_form_round_trips_county_mode(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """A stored `county` mode is preselected in the edit form and survives a re-save."""
    await client.post("/searches", data={"name": "Dublin Python"})
    search_id = await _only_search_id(session_factory)
    created = await client.post(
        f"/searches/{search_id}/rules",
        data={"kind": "location", "location_allow": "Dublin", "location_mode": "county"},
    )
    assert created.status_code == 200, created.text

    rules = await _rule_rows(session_factory)
    assert len(rules) == 1

    page = await client.get("/searches")
    root = _parse(page.text)
    edit_payload = _payload(_edit_save_for(root, int(rules[0].id)))

    assert edit_payload["location_mode"] == ["county"]

    saved = await client.post(
        f"/searches/{search_id}/rules/{rules[0].id}", data=edit_payload
    )
    assert saved.status_code == 200, saved.text
    rules = await _rule_rows(session_factory)
    assert rules[0].params_json["mode"] == "county"
