from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Callable, Mapping
from uuid import uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_deep_freeze(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(_deep_freeze(item) for item in value)
    return value


def operation_effect_digest(
    *,
    target: str,
    operation_kind: str,
    effect_payload: Mapping[str, Any],
) -> str:
    encoded = json.dumps(
        {
            "target": target,
            "operation_kind": operation_kind,
            "effect_payload": effect_payload,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class OperationState(StrEnum):
    PREPARED = "PREPARED"
    ATTEMPTED = "ATTEMPTED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True, slots=True)
class OperationIntent:
    id: str
    idempotency_key: str
    target: str
    operation_kind: str
    effect_payload: Mapping[str, Any]
    effect_digest: str
    prepared_at: datetime

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("operation id is required")
        if not self.idempotency_key:
            raise ValueError("idempotency_key is required")
        if not self.target:
            raise ValueError("target is required")
        if not self.operation_kind:
            raise ValueError("operation_kind is required")
        object.__setattr__(self, "effect_payload", _deep_freeze(self.effect_payload))


@dataclass(frozen=True, slots=True)
class OperationEvent:
    operation_id: str
    state: OperationState
    observed_at: datetime
    evidence_ref: str | None = None
    readback_digest: str | None = None


class IdempotencyCollisionError(ValueError):
    pass


class InvalidOperationTransition(ValueError):
    pass


@dataclass(slots=True)
class _OperationRecord:
    intent: OperationIntent
    events: list[OperationEvent] = field(default_factory=list)

    @property
    def state(self) -> OperationState:
        if not self.events:
            return OperationState.PREPARED
        return self.events[-1].state


class OperationJournal:
    """Reference semantics for effect attempts and readback reconciliation."""

    def __init__(self, *, id_factory: Callable[[], str] | None = None) -> None:
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._records: dict[str, _OperationRecord] = {}
        self._by_idempotency: dict[str, str] = {}

    def prepare(
        self,
        *,
        target: str,
        operation_kind: str,
        effect_payload: Mapping[str, Any],
        idempotency_key: str,
        prepared_at: datetime | None = None,
    ) -> tuple[OperationIntent, bool]:
        if not idempotency_key:
            raise ValueError("idempotency_key is required")
        digest = operation_effect_digest(
            target=target,
            operation_kind=operation_kind,
            effect_payload=effect_payload,
        )
        existing_id = self._by_idempotency.get(idempotency_key)
        if existing_id is not None:
            existing = self._records[existing_id].intent
            if existing.effect_digest != digest:
                raise IdempotencyCollisionError(
                    "idempotency key was reused for a different effect"
                )
            return existing, True

        intent = OperationIntent(
            id=self._id_factory(),
            idempotency_key=idempotency_key,
            target=target,
            operation_kind=operation_kind,
            effect_payload=effect_payload,
            effect_digest=digest,
            prepared_at=prepared_at or _utcnow(),
        )
        self._records[intent.id] = _OperationRecord(intent=intent)
        self._by_idempotency[idempotency_key] = intent.id
        return intent, False

    def intent(self, operation_id: str) -> OperationIntent:
        return self._records[operation_id].intent

    def state(self, operation_id: str) -> OperationState:
        return self._records[operation_id].state

    def events(self, operation_id: str) -> tuple[OperationEvent, ...]:
        return tuple(self._records[operation_id].events)

    def attempt(
        self,
        operation_id: str,
        *,
        evidence_ref: str | None = None,
        observed_at: datetime | None = None,
    ) -> OperationEvent:
        record = self._records[operation_id]
        if record.state != OperationState.PREPARED:
            raise InvalidOperationTransition(
                f"cannot attempt operation from {record.state}"
            )
        return self._append(
            record,
            OperationState.ATTEMPTED,
            evidence_ref=evidence_ref,
            observed_at=observed_at,
        )

    def mark_ambiguous(
        self,
        operation_id: str,
        *,
        evidence_ref: str,
        observed_at: datetime | None = None,
    ) -> OperationEvent:
        record = self._records[operation_id]
        if record.state != OperationState.ATTEMPTED:
            raise InvalidOperationTransition(
                f"cannot mark ambiguous from {record.state}"
            )
        if not evidence_ref:
            raise ValueError("evidence_ref is required")
        return self._append(
            record,
            OperationState.AMBIGUOUS,
            evidence_ref=evidence_ref,
            observed_at=observed_at,
        )

    def reconcile(
        self,
        operation_id: str,
        *,
        verified: bool,
        evidence_ref: str,
        readback_digest: str | None = None,
        observed_at: datetime | None = None,
    ) -> OperationEvent:
        record = self._records[operation_id]
        if record.state not in {OperationState.ATTEMPTED, OperationState.AMBIGUOUS}:
            raise InvalidOperationTransition(
                f"cannot reconcile operation from {record.state}"
            )
        if not evidence_ref:
            raise ValueError("evidence_ref is required")
        if verified and not readback_digest:
            raise ValueError("verified reconciliation requires readback_digest")
        return self._append(
            record,
            OperationState.VERIFIED if verified else OperationState.FAILED,
            evidence_ref=evidence_ref,
            readback_digest=readback_digest,
            observed_at=observed_at,
        )

    @staticmethod
    def _append(
        record: _OperationRecord,
        state: OperationState,
        *,
        evidence_ref: str | None = None,
        readback_digest: str | None = None,
        observed_at: datetime | None = None,
    ) -> OperationEvent:
        event = OperationEvent(
            operation_id=record.intent.id,
            state=state,
            observed_at=observed_at or _utcnow(),
            evidence_ref=evidence_ref,
            readback_digest=readback_digest,
        )
        record.events.append(event)
        return event