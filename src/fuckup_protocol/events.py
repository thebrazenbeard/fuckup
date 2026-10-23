from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import re
from typing import Any, Mapping

from .provenance import ProvenanceKind, ProvenanceRef


EVENT_PREFIX = "org.fuckup"
_ACTION = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")


def _require_string_keys(value: Mapping[str, Any]) -> None:
    """Reject nested JSON key coercion/collision before emitting an event."""
    pending: list[Any] = [value]
    seen: set[int] = set()
    while pending:
        item = pending.pop()
        if isinstance(item, Mapping) or isinstance(item, list | tuple):
            if id(item) in seen:
                continue
            seen.add(id(item))
            if isinstance(item, Mapping):
                if any(not isinstance(key, str) for key in item):
                    raise ValueError("event data must use string keys at every level")
                pending.extend(item.values())
            else:
                pending.extend(item)


@dataclass(frozen=True, slots=True)
class FuckupEvent:
    id: str
    source: str
    type: str
    subject: str
    data: Mapping[str, Any]
    time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    specversion: str = "1.0"
    datacontenttype: str = "application/json"
    provenance: tuple[ProvenanceRef, ...] = field(default_factory=tuple)
    traceparent: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("event id is required")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("event source is required")
        if not isinstance(self.subject, str) or not self.subject.strip():
            raise ValueError("event subject is required")
        if not isinstance(self.type, str) or not self.type.startswith(EVENT_PREFIX + "."):
            raise ValueError(f"event type must start with {EVENT_PREFIX}.")
        if not _ACTION.fullmatch(self.type[len(EVENT_PREFIX) + 1:]):
            raise ValueError("event type must have a normalized lifecycle action")
        if self.specversion != "1.0":
            raise ValueError("only CloudEvents specversion 1.0 is supported")
        if self.datacontenttype != "application/json":
            raise ValueError("only application/json event data is supported")
        if not isinstance(self.time, datetime) or self.time.tzinfo is None or self.time.utcoffset() is None:
            raise ValueError("event time must be timezone-aware")
        if not isinstance(self.data, Mapping):
            raise ValueError("event data must be a JSON object with string keys")
        _require_string_keys(self.data)
        try:
            json.dumps(dict(self.data), allow_nan=False)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("event data must be JSON serializable") from exc
        if self.traceparent is not None and not isinstance(self.traceparent, str):
            raise ValueError("traceparent must be a string")
        # A caller may pass a mutable list despite the tuple annotation.
        # Copy it before validating so later appends cannot change egress.
        try:
            object.__setattr__(self, "provenance", tuple(self.provenance))
        except TypeError as exc:
            raise ValueError("provenance must be a sequence of references") from exc
        for ref in self.provenance:
            if not isinstance(ref, ProvenanceRef) or not isinstance(ref.kind, ProvenanceKind):
                raise ValueError("provenance requires typed references and kinds")
            if not isinstance(ref.ref, str) or not ref.ref.strip():
                raise ValueError("provenance ref must be a nonempty string")
            if any(value is not None and not isinstance(value, str)
                   for value in (ref.digest, ref.media_type, ref.source)):
                raise ValueError("provenance optional fields must be strings")

    def to_cloudevent(self) -> dict[str, Any]:
        # A fresh JSON value prevents callers mutating the emitted event through
        # references to nested input objects. The result is telemetry, not proof.
        # The input Mapping can still be mutated after construction; re-check
        # keys before JSON can silently coerce two distinct keys to one name.
        _require_string_keys(self.data)
        event: dict[str, Any] = {
            "specversion": self.specversion,
            "id": self.id,
            "source": self.source,
            "type": self.type,
            "subject": self.subject,
            "time": self.time.isoformat(),
            "datacontenttype": self.datacontenttype,
            "data": json.loads(json.dumps(dict(self.data), allow_nan=False)),
        }
        if self.traceparent:
            event["traceparent"] = self.traceparent
        if self.provenance:
            event["fuckupprovenance"] = [
                {
                    key: value
                    for key, value in asdict(ref).items()
                    if value is not None
                }
                for ref in self.provenance
            ]
        return event


def lifecycle_event_type(action: str) -> str:
    if not isinstance(action, str):
        raise ValueError("action must be a string")
    normalized = action.strip().lower().replace("_", ".")
    if not _ACTION.fullmatch(normalized) or normalized.startswith(EVENT_PREFIX + "."):
        raise ValueError("action must use normalized letter/digit segments")
    return f"{EVENT_PREFIX}.{normalized}"
