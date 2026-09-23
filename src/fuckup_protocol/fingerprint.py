from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any


DEFAULT_VOLATILE_FIELDS = frozenset({
    "request_id",
    "trace_id",
    "span_id",
    "timestamp",
    "occurred_at",
    "observed_at",
})


def _canonicalize(value: Any, ignored_fields: frozenset[str]) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonicalize(item, ignored_fields)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in ignored_fields
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_canonicalize(item, ignored_fields) for item in value]
    return value


def fingerprint_incident(
    payload: Mapping[str, Any],
    *,
    algorithm_version: str = "fuckup-fingerprint-v1",
    ignored_fields: frozenset[str] = DEFAULT_VOLATILE_FIELDS,
) -> str:
    """Return a deterministic, versioned fingerprint for a normalized incident.

    The function intentionally performs only structural canonicalization. Domain-
    specific normalizers should remove or transform volatile values before this
    function is called rather than hiding semantics inside the hash function.
    """

    canonical = _canonicalize(payload, ignored_fields)
    serialized = json.dumps(
        {"algorithm": algorithm_version, "payload": canonical},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"{algorithm_version}:sha256:{hashlib.sha256(serialized).hexdigest()}"
