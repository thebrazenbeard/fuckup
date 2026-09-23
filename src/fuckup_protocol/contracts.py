from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from types import MappingProxyType
from typing import TypeAlias


JsonObject: TypeAlias = Mapping[str, object]


def _freeze_json(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("JSON numbers must be finite")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON object keys must be strings")
            frozen[key] = _freeze_json(item)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    raise ValueError(f"value of type {type(value).__name__} is not JSON-compatible")


def freeze_json_object(value: object, *, require_nonempty: bool = False) -> JsonObject:
    if not isinstance(value, Mapping):
        raise ValueError("value must be a JSON object")
    if require_nonempty and not value:
        raise ValueError("JSON object must not be empty")
    frozen = _freeze_json(value)
    assert isinstance(frozen, Mapping)
    return frozen


def is_nonempty_json_object(value: object) -> bool:
    try:
        freeze_json_object(value, require_nonempty=True)
    except ValueError:
        return False
    return True


def thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value
