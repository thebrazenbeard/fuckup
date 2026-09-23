from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import TypeAlias


SelectorScalar: TypeAlias = str | int | float | bool
SelectorScope: TypeAlias = Mapping[str, SelectorScalar]


def is_selector_scope(value: object) -> bool:
    """Return True for the deliberately small selector/scope contract.

    Scope semantics are conjunction-only: a mapping of non-empty string keys to
    JSON scalar values. Nested objects, arrays, null, NaN, and infinities are
    rejected so subset checks remain deterministic across Python/PostgreSQL.
    """

    if not isinstance(value, Mapping) or not value:
        return False

    for key, item in value.items():
        if not isinstance(key, str) or not key:
            return False
        if item is None or isinstance(item, (list, tuple, set, frozenset, Mapping)):
            return False
        if isinstance(item, bool):
            continue
        if isinstance(item, (int, str)):
            continue
        if isinstance(item, float) and isfinite(item):
            continue
        return False

    return True


def selector_within_scope(selector: object, activation_scope: object) -> bool:
    """A selector is equal to or narrower than its approved activation scope."""

    if not is_selector_scope(selector) or not is_selector_scope(activation_scope):
        return False

    selector_map = selector
    scope_map = activation_scope

    def scalar_equal(actual: SelectorScalar, expected: SelectorScalar) -> bool:
        # Python considers True == 1; JSON does not. Keep booleans distinct
        # while allowing normal numeric equality between ints and floats.
        if isinstance(actual, bool) or isinstance(expected, bool):
            return isinstance(actual, bool) and isinstance(expected, bool) and actual == expected
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            return actual == expected
        return isinstance(actual, str) and isinstance(expected, str) and actual == expected

    return all(
        key in selector_map and scalar_equal(selector_map[key], expected)
        for key, expected in scope_map.items()
    )
