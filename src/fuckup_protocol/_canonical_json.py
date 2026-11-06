"""Strict JSON evidence boundary without changing valid-v1 digest encoding.

The protocol's v1 digests use Python JSON with sorted keys, compact separators,
and UTF-8. This module preserves those bytes for valid JSON-compatible inputs
while rejecting key coercion and non-finite numbers before identity is bound.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any


def validate_json_data(value: Any) -> None:
    """Reject values that can collapse JSON identities or encode non-JSON numbers.

    Lists, tuples, and sets are traversed, preserving existing callers' choices
    about whether to normalize sets. Unsupported objects remain the serializer's
    responsibility, as before.
    """
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("JSON evidence mapping keys must be strings")
            validate_json_data(item)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            validate_json_data(item)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite number is not valid JSON evidence")


def canonical_json_bytes(value: Any) -> bytes:
    """Return existing v1 canonical bytes for valid JSON; fail closed otherwise."""
    validate_json_data(value)
    return json.dumps(
        _json_plain(value), ensure_ascii=False, separators=(",", ":"),
        sort_keys=True, allow_nan=False,
    ).encode("utf-8")


def _json_plain(value: Any) -> Any:
    """Make frozen Mapping/tuple snapshots serializable without coercing keys."""
    if isinstance(value, Mapping):
        return {key: _json_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_plain(item) for item in value]
    return value


def deep_freeze_json(value: Any) -> Any:
    """Freeze nested payloads without silently stringifying dictionary keys."""
    validate_json_data(value)
    return _freeze(value)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    return value
