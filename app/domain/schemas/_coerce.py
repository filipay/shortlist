"""Shared, pure coercion for the model's list-typed wire fields (G-07-7).

The provider intermittently encodes a JSON array as a single-key wrapper object
``{"item": <value>}`` (and an empty array as ``""``). A ``Mapping`` is never a legal
``list[...]``, so unwrapping a single-key wrapper is an *invalid -> valid*
conversion — and it is the only conversion these helpers perform. Every OTHER shape
(a scalar, a multi-key mapping, an unknown key) is returned untouched and fails
loudly at pydantic (CONVENTIONS rules 1/2: fail closed, visibly).

**Purity.** stdlib plus ``collections.abc``/``typing`` only, no I/O — ``app/domain``
imports no I/O, enforced by ``tests/test_import_discipline.py`` (D-24).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def unwrap_single_key_mapping(value: Any) -> Any:
    """Unwrap a single-key wrapper Mapping, repeatedly; return anything else as-is.

    ``{"item": [...]}`` -> ``[...]`` and ``{"item": {"item": [...]}}`` -> ``[...]``.
    A Mapping with zero or 2+ keys, and any non-Mapping, is returned UNCHANGED
    (never partially unwrapped).
    """
    while isinstance(value, Mapping) and len(value) == 1:
        value = next(iter(value.values()))
    return value


def coerce_str_list(value: Any) -> Any:
    """Normalise the recorded non-list shapes of a ``list[str]`` field (G-07-2/G-07-7).

    A single-key wrapper is unwrapped first; then ``None`` -> ``[]``; a ``str`` ->
    comma-split, stripped, empties dropped; a ``list``/``tuple`` -> ``list(value)``.
    Every other shape is returned untouched so pydantic still fails loudly rather
    than laundering an unrecognised payload into a default.
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

    A single-key wrapper is unwrapped first; then ``None`` -> ``[]``; a ``Mapping``
    -> ``[value]`` (a single item-shaped object); a ``list``/``tuple`` ->
    ``list(value)``. Every other shape is returned untouched so pydantic still fails
    loudly.
    """
    value = unwrap_single_key_mapping(value)
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, (list, tuple)):
        return list(value)
    return value


__all__ = ["coerce_mapping_list", "coerce_str_list", "unwrap_single_key_mapping"]
