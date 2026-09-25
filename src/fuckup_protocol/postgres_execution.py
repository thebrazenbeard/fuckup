from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping
from uuid import uuid4

from .bindings import InjectionBinding
from .effectiveness import ObservationPhase, OutcomeObservation
from .operations import (
    OperationEvent,
    OperationIntent,
    OperationState,
    operation_effect_digest,
)


ConnectionFactory = Callable[[], Any]


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_plain(item) for item in value]
    if isinstance(value, set | frozenset):
        return sorted(_plain(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class DurableOutcomeRecord:
    id: str
    operation_id: str
    correction_id: str
    correction_revision: int
    promotion_id: str
    binding_id: str
    scope_digest: str
    effect_digest: str
    verification_evidence_ref: str
    failure_occurred: bool
    correction_triggered: bool
    prevented: bool
    regression: bool
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class DurableOperationStatus:
    intent: OperationIntent
    state: OperationState


class PostgresExecutionStore:
    """PostgreSQL-backed operation journal, binding reader, and outcome recorder.

    The connection factory must return a fresh context-managed connection whose
    search_path is already bound to the trusted F.U.C.K.U.P. schema.
    """

    def __init__(self, connection_factory: ConnectionFactory) -> None:
        self._connect = connection_factory

    def prepare(
        self,
        *,
        target: str,
        operation_kind: str,
        effect_payload: Mapping[str, Any],
        idempotency_key: str,
        prepared_at: datetime | None = None,
    ) -> tuple[OperationIntent, bool]:
        payload = _plain(effect_payload)
        digest = operation_effect_digest(
            target=target,
            operation_kind=operation_kind,
            effect_payload=payload,
        )
        with self._connect() as conn:
            existing = conn.execute(
                """
                SELECT id::text
                FROM effect_operations
                WHERE idempotency_key = %s
                """,
                (idempotency_key,),
            ).fetchone()
            row = conn.execute(
                """
                SELECT
                    id::text, idempotency_key, target, operation_kind,
                    effect_payload, effect_digest, prepared_at
                FROM prepare_effect_operation(
                    %s::uuid, %s, %s, %s, %s::jsonb, %s, %s
                )
                """,
                (
                    str(uuid4()),
                    idempotency_key,
                    target,
                    operation_kind,
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    digest,
                    prepared_at,
                ),
            ).fetchone()
        return self._intent_from_row(row), existing is not None

    def intent(self, operation_id: str) -> OperationIntent:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id::text, idempotency_key, target, operation_kind,
                    effect_payload, effect_digest, prepared_at
                FROM effect_operations
                WHERE id = %s::uuid
                """,
                (operation_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown operation: {operation_id}")
        return self._intent_from_row(row)

    def state(self, operation_id: str) -> OperationState:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT state
                FROM effect_operation_events
                WHERE operation_id = %s::uuid
                ORDER BY id DESC
                LIMIT 1
                """,
                (operation_id,),
            ).fetchone()
            if row is None:
                exists = conn.execute(
                    "SELECT 1 FROM effect_operations WHERE id = %s::uuid",
                    (operation_id,),
                ).fetchone()
                if exists is None:
                    raise KeyError(f"unknown operation: {operation_id}")
                return OperationState.PREPARED
        return OperationState(row[0])

    def events(self, operation_id: str) -> tuple[OperationEvent, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT operation_id::text, state, observed_at, evidence_ref, readback_digest
                FROM effect_operation_events
                WHERE operation_id = %s::uuid
                ORDER BY id
                """,
                (operation_id,),
            ).fetchall()
        return tuple(
            OperationEvent(
                operation_id=row[0],
                state=OperationState(row[1]),
                observed_at=row[2],
                evidence_ref=row[3],
                readback_digest=row[4],
            )
            for row in rows
        )
    def attempt(
        self,
        operation_id: str,
        *,
        evidence_ref: str | None = None,
        observed_at: datetime | None = None,
    ) -> OperationEvent:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT operation_id::text, state, observed_at, evidence_ref, readback_digest
                FROM record_effect_attempt(%s::uuid, %s, %s)
                """,
                (operation_id, evidence_ref, observed_at),
            ).fetchone()
        return self._event_from_row(row)

    def mark_ambiguous(
        self,
        operation_id: str,
        *,
        evidence_ref: str,
        observed_at: datetime | None = None,
    ) -> OperationEvent:
        return self._reconcile_event(
            operation_id,
            outcome="AMBIGUOUS",
            evidence_ref=evidence_ref,
            readback_digest=None,
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
        return self._reconcile_event(
            operation_id,
            outcome="VERIFIED" if verified else "FAILED",
            evidence_ref=evidence_ref,
            readback_digest=readback_digest,
            observed_at=observed_at,
        )

    def _reconcile_event(
        self,
        operation_id: str,
        *,
        outcome: str,
        evidence_ref: str,
        readback_digest: str | None,
        observed_at: datetime | None,
    ) -> OperationEvent:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT operation_id::text, state, observed_at, evidence_ref, readback_digest
                FROM reconcile_effect_operation(%s::uuid, %s, %s, %s, %s)
                """,
                (
                    operation_id,
                    outcome,
                    evidence_ref,
                    readback_digest,
                    observed_at,
                ),
            ).fetchone()
        return self._event_from_row(row)

    def bindings_for_context(
        self,
        context: Mapping[str, str],
    ) -> tuple[InjectionBinding, ...]:
        encoded = json.dumps(dict(context), sort_keys=True, separators=(",", ":"))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id::text,
                    correction_id::text,
                    correction_revision,
                    selector,
                    activation_scope,
                    priority,
                    promotion_id::text,
                    adapter,
                    adapter_version
                FROM active_injection_bindings
                WHERE adapter_version IS NOT NULL
                  AND %s::jsonb @> selector
                ORDER BY priority DESC, id
                """,
                (encoded,),
            ).fetchall()
        return tuple(
            InjectionBinding(
                id=row[0],
                correction_id=row[1],
                correction_revision=row[2],
                selector=row[3],
                activation_scope=row[4],
                priority=row[5],
                active=True,
                promotion_id=row[6],
                adapter=row[7],
                adapter_version=row[8],
            )
            for row in rows
        )

    def binding_is_current(self, binding: InjectionBinding) -> bool:
        if not binding.executable:
            return False
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM active_injection_bindings
                    WHERE id = %s::uuid
                      AND promotion_id = %s::uuid
                      AND correction_id = %s::uuid
                      AND correction_revision = %s
                      AND selector_digest = %s
                      AND adapter = %s
                      AND adapter_version = %s
                )
                """,
                (
                    binding.id,
                    binding.promotion_id,
                    binding.correction_id,
                    binding.correction_revision,
                    binding.selector_digest,
                    binding.adapter,
                    binding.adapter_version,
                ),
            ).fetchone()
        return bool(row[0])

    def record_outcome(self, observation: OutcomeObservation) -> DurableOutcomeRecord:
        if observation.phase != ObservationPhase.ACTIVE:
            raise ValueError("durable execution store records ACTIVE outcomes only")
        if observation.subject is None:
            raise ValueError("outcome subject is required")
        if (
            observation.operation_id is None
            or observation.effect_digest is None
            or observation.verification_evidence_ref is None
        ):
            raise ValueError("verified operation provenance is required")

        subject = observation.subject
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id::text,
                    operation_id::text,
                    correction_id::text,
                    correction_revision,
                    promotion_id::text,
                    binding_id::text,
                    scope_digest,
                    effect_digest,
                    verification_evidence_ref,
                    failure_occurred,
                    correction_triggered,
                    prevented,
                    regression,
                    observed_at
                FROM record_verified_outcome_observation(
                    %s::uuid, %s::uuid, %s::uuid, %s, %s::uuid, %s::uuid,
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    str(uuid4()),
                    observation.operation_id,
                    subject.correction_id,
                    subject.correction_revision,
                    subject.promotion_id,
                    subject.binding_id,
                    subject.scope_digest,
                    observation.effect_digest,
                    observation.verification_evidence_ref,
                    observation.failure_occurred,
                    observation.correction_triggered,
                    observation.prevented,
                    observation.regression,
                    None,
                ),
            ).fetchone()
        return self._outcome_from_row(row)
    def outcome_for_operation(self, operation_id: str) -> DurableOutcomeRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id::text,
                    operation_id::text,
                    correction_id::text,
                    correction_revision,
                    promotion_id::text,
                    binding_id::text,
                    scope_digest,
                    effect_digest,
                    verification_evidence_ref,
                    failure_occurred,
                    correction_triggered,
                    prevented,
                    regression,
                    observed_at
                FROM outcome_observations
                WHERE operation_id = %s::uuid
                """,
                (operation_id,),
            ).fetchone()
        return None if row is None else self._outcome_from_row(row)

    def recoverable_operations(self) -> tuple[DurableOperationStatus, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    op.id::text,
                    op.idempotency_key,
                    op.target,
                    op.operation_kind,
                    op.effect_payload,
                    op.effect_digest,
                    op.prepared_at,
                    COALESCE(latest.state, 'PREPARED')
                FROM effect_operations op
                LEFT JOIN LATERAL (
                    SELECT event.state
                    FROM effect_operation_events event
                    WHERE event.operation_id = op.id
                    ORDER BY event.id DESC
                    LIMIT 1
                ) latest ON true
                WHERE COALESCE(latest.state, 'PREPARED') IN (
                    'PREPARED', 'ATTEMPTED', 'AMBIGUOUS'
                )
                ORDER BY op.prepared_at, op.id
                """
            ).fetchall()
        return tuple(
            DurableOperationStatus(
                intent=self._intent_from_row(row[:7]),
                state=OperationState(row[7]),
            )
            for row in rows
        )

    def verified_outcome_gaps(self) -> tuple[str, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT op.id::text
                FROM effect_operations op
                JOIN LATERAL (
                    SELECT event.state
                    FROM effect_operation_events event
                    WHERE event.operation_id = op.id
                    ORDER BY event.id DESC
                    LIMIT 1
                ) latest ON true
                LEFT JOIN outcome_observations outcome
                  ON outcome.operation_id = op.id
                WHERE latest.state = 'VERIFIED'
                  AND outcome.operation_id IS NULL
                ORDER BY op.prepared_at, op.id
                """
            ).fetchall()
        return tuple(row[0] for row in rows)

    @staticmethod
    def _intent_from_row(row: Any) -> OperationIntent:
        if row is None:
            raise RuntimeError("database did not return an operation")
        return OperationIntent(
            id=str(row[0]),
            idempotency_key=row[1],
            target=row[2],
            operation_kind=row[3],
            effect_payload=row[4],
            effect_digest=row[5],
            prepared_at=row[6],
        )

    @staticmethod
    def _event_from_row(row: Any) -> OperationEvent:
        if row is None:
            raise RuntimeError("database did not return an operation event")
        return OperationEvent(
            operation_id=str(row[0]),
            state=OperationState(row[1]),
            observed_at=row[2],
            evidence_ref=row[3],
            readback_digest=row[4],
        )

    @staticmethod
    def _outcome_from_row(row: Any) -> DurableOutcomeRecord:
        if row is None:
            raise RuntimeError("database did not return an outcome observation")
        return DurableOutcomeRecord(
            id=str(row[0]),
            operation_id=str(row[1]),
            correction_id=str(row[2]),
            correction_revision=row[3],
            promotion_id=str(row[4]),
            binding_id=str(row[5]),
            scope_digest=row[6],
            effect_digest=row[7],
            verification_evidence_ref=row[8],
            failure_occurred=row[9],
            correction_triggered=row[10],
            prevented=row[11],
            regression=row[12],
            observed_at=row[13],
        )