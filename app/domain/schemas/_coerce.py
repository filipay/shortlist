"""Shared, pure coercion for the model's list-typed wire fields (G-07-7).

The provider intermittently encodes a JSON array as a single-key wrapper object
``{"item": <value>}`` (and an empty array as ``""``). The wrapper is recognised by the
literal key :data:`WRAPPER_KEY` (``"item"``) and by nothing else: a ``Mapping`` whose
single key is anything else is returned untouched. A ``Mapping`` is never a legal
``list[...]``, so unwrapping a wrapper is an *invalid -> valid* conversion — the only
conversion these helpers perform. Every OTHER shape is returned untouched and fails
loudly at pydantic (CONVENTIONS rules 1/2: fail closed, visibly), by one of two
routes: a ``Mapping`` that reaches :func:`coerce_str_list` still unwrapped fails as
``list_type``, while one that reaches :func:`coerce_mapping_list` is treated as a
single item-shaped object and refused by that item model's ``extra="forbid"``.

**Purity.** stdlib plus ``collections.abc``/``typing`` only, no I/O — ``app/domain``
imports no I/O, enforced by ``tests/test_import_discipline.py`` (D-24).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

#: The literal provider wrapper key. Named once here; the unwrap recognises only this
#: key, so a single-key mapping with any other key is not treated as a wrapper.
WRAPPER_KEY = "item"


def unwrap_single_key_mapping(value: Any) -> Any:
    """Unwrap a single-key wrapper Mapping, repeatedly; return anything else as-is.

    Only a Mapping whose sole key is :data:`WRAPPER_KEY` (``"item"``) is unwrapped:
    ``{"item": [...]}`` -> ``[...]`` and ``{"item": {"item": [...]}}`` -> ``[...]``.
    A Mapping with zero keys, 2+ keys, or a single key that is not ``WRAPPER_KEY``,
    and any non-Mapping, is returned UNCHANGED (never partially unwrapped). The loop
    also stops when the inner value IS the outer Mapping, so a caller-constructed
    self-reference cannot hang the caller.
    """
    while isinstance(value, Mapping) and len(value) == 1:
        key, inner = next(iter(value.items()))
        if key != WRAPPER_KEY:
            break
        if inner is value:
            break
        value = inner
    return value


def coerce_str_list(value: Any) -> Any:
    """Normalise the recorded non-list shapes of a ``list[str]`` field (G-07-2/G-07-7).

    A single-key wrapper whose key is the literal ``WRAPPER_KEY`` is unwrapped first;
    then ``None`` -> ``[]``; a ``str`` -> comma-split, stripped, empties dropped; a
    ``list``/``tuple`` -> ``list(value)``. Every other shape — including a Mapping
    left untouched (an unknown key, or a multi-key mapping) — is returned untouched,
    and pydantic then fails it loudly as ``list_type`` rather than laundering an
    unrecognised payload into a default.
    """
    value = unwrap_single_key_mapping(value)
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple)):
        return list(value)
    return value


def coerce_mapping_list(value: Any) -> Any:
    """Normalise the recorded non-list shapes of a ``list[Mapping]`` field.

    A single-key wrapper whose key is the literal ``WRAPPER_KEY`` is unwrapped first;
    then ``None`` -> ``[]``; a ``Mapping`` -> ``[value]`` (validated as ONE
    item-shaped object, so its unknown keys are caught by that item model's
    ``extra="forbid"``); a ``list``/``tuple`` -> ``list(value)``. Every other shape is
    returned untouched so pydantic still fails loudly.
    """
    value = unwrap_single_key_mapping(value)
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, (list, tuple)):
        return list(value)
    return value


__all__ = [
    "WRAPPER_KEY",
    "coerce_mapping_list",
    "coerce_str_list",
    "unwrap_single_key_mapping",
]
