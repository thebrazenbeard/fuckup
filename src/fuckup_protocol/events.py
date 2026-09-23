from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from .provenance import ProvenanceRef


EVENT_PREFIX = "org.fuckup"


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
        if not self.id:
            raise ValueError("event id is required")
        if not self.source:
            raise ValueError("event source is required")
        if not self.subject:
            raise ValueError("event subject is required")
        if not self.type.startswith(EVENT_PREFIX + "."):
            raise ValueError(f"event type must start with {EVENT_PREFIX}.")
        if self.specversion != "1.0":
            raise ValueError("only CloudEvents specversion 1.0 is supported")

    def to_cloudevent(self) -> dict[str, Any]:
        event: dict[str, Any] = {
            "specversion": self.specversion,
            "id": self.id,
            "source": self.source,
            "type": self.type,
            "subject": self.subject,
            "time": self.time.isoformat(),
            "datacontenttype": self.datacontenttype,
            "data": dict(self.data),
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
    normalized = action.strip().lower().replace("_", ".")
    if not normalized:
        raise ValueError("action is required")
    return f"{EVENT_PREFIX}.{normalized}"
