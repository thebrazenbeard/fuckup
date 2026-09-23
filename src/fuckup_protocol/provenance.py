from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProvenanceKind(StrEnum):
    TRACE = "TRACE"
    SPAN = "SPAN"
    EVENT = "EVENT"
    FILE = "FILE"
    COMMIT = "COMMIT"
    RUN = "RUN"
    DATASET = "DATASET"
    ATTESTATION = "ATTESTATION"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class ProvenanceRef:
    kind: ProvenanceKind
    ref: str
    digest: str | None = None
    media_type: str | None = None
    source: str | None = None

    def __post_init__(self) -> None:
        if not self.ref:
            raise ValueError("provenance ref is required")
        if self.digest is not None and ":" not in self.digest:
            raise ValueError("digest should be algorithm-prefixed, e.g. sha256:...")
