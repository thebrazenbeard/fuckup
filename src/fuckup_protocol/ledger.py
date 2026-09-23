from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from uuid import uuid4

from .authorization import PromotionAuthorization
from .contracts import JsonObject, freeze_json_object
from .models import CorrectionRevision, PolicyDecision, QualificationResult
from .scope import SelectorScope, freeze_selector_scope
from .validation import ValidationReport


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def subject_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def effect_digest(*, incident_id: str, event_type: str, payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        {
            "incident_id": incident_id,
            "event_type": event_type,
            "payload": payload,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


@dataclass(slots=True)
class IncidentRecord:
    id: str
    fingerprint: str
    fingerprint_version: str
    payload: Mapping[str, Any]
    first_seen_at: datetime
    last_seen_at: datetime
    occurrence_count: int = 1


@dataclass(frozen=True, slots=True)
class EventRecord:
    id: str
    incident_id: str
    event_type: str
    payload: Mapping[str, Any]
    effect_digest: str
    idempotency_key: str | None
    observed_at: datetime


@dataclass(slots=True)
class CorrectionFamily:
    id: str
    incident_id: str
    revisions: list[CorrectionRevision] = field(default_factory=list)

    @property
    def current(self) -> CorrectionRevision:
        if not self.revisions:
            raise RuntimeError("correction family has no revisions")
        return self.revisions[-1]


@dataclass(frozen=True, slots=True)
class PromotionRecord:
    id: str
    correction_id: str
    correction_revision: int
    qualification_id: str
    activation_scope: SelectorScope
    rollback_condition: JsonObject
    policy_decision: PolicyDecision
    policy_name: str
    policy_version: str
    authorization_ref: str
    activated_at: datetime
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "activation_scope", freeze_selector_scope(self.activation_scope))
        object.__setattr__(
            self,
            "rollback_condition",
            freeze_json_object(self.rollback_condition, require_nonempty=True),
        )


class StaleQualificationError(ValueError):
    pass


class PromotionRejectedError(ValueError):
    pass


class IdempotencyCollisionError(ValueError):
    pass


class InMemoryLedger:
    """Reference semantics for the append-only/versioned core.

    This is deliberately small and is not intended as the production store.
    PostgreSQL is the durable target. The in-memory ledger exists so protocol
    invariants can be executed and tested independently of a database runtime.
    """

    def __init__(self, *, id_factory: Callable[[], str] | None = None) -> None:
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._incidents: dict[str, IncidentRecord] = {}
        self._incident_by_fingerprint: dict[tuple[str, str], str] = {}
        self._events: list[EventRecord] = []
        self._event_by_idempotency: dict[str, EventRecord] = {}
        self._corrections: dict[str, CorrectionFamily] = {}
        self._qualifications: dict[str, QualificationResult] = {}
        self._promotions: dict[str, PromotionRecord] = {}

    def submit_incident(
        self,
        *,
        fingerprint: str,
        fingerprint_version: str,
        payload: Mapping[str, Any],
        observed_at: datetime | None = None,
    ) -> tuple[IncidentRecord, bool]:
        now = observed_at or _utcnow()
        key = (fingerprint_version, fingerprint)
        existing_id = self._incident_by_fingerprint.get(key)
        if existing_id is not None:
            incident = self._incidents[existing_id]
            incident.last_seen_at = now
            incident.occurrence_count += 1
            return incident, True

        incident = IncidentRecord(
            id=self._id_factory(),
            fingerprint=fingerprint,
            fingerprint_version=fingerprint_version,
            payload=dict(payload),
            first_seen_at=now,
            last_seen_at=now,
        )
        self._incidents[incident.id] = incident
        self._incident_by_fingerprint[key] = incident.id
        return incident, False

    def append_event(
        self,
        *,
        incident_id: str,
        event_type: str,
        payload: Mapping[str, Any],
        idempotency_key: str | None = None,
        observed_at: datetime | None = None,
    ) -> tuple[EventRecord, bool]:
        if incident_id not in self._incidents:
            raise KeyError(f"unknown incident: {incident_id}")

        digest = effect_digest(
            incident_id=incident_id,
            event_type=event_type,
            payload=payload,
        )

        if idempotency_key and idempotency_key in self._event_by_idempotency:
            existing = self._event_by_idempotency[idempotency_key]
            if existing.effect_digest != digest:
                raise IdempotencyCollisionError(
                    "idempotency key was reused for a different event effect"
                )
            return existing, True

        event = EventRecord(
            id=self._id_factory(),
            incident_id=incident_id,
            event_type=event_type,
            payload=dict(payload),
            effect_digest=digest,
            idempotency_key=idempotency_key,
            observed_at=observed_at or _utcnow(),
        )
        self._events.append(event)
        if idempotency_key:
            self._event_by_idempotency[idempotency_key] = event
        return event, False

    def create_correction(
        self,
        *,
        incident_id: str,
        payload: Mapping[str, Any],
        reversible: bool = True,
        correction_id: str | None = None,
    ) -> CorrectionRevision:
        if incident_id not in self._incidents:
            raise KeyError(f"unknown incident: {incident_id}")
        cid = correction_id or self._id_factory()
        if cid in self._corrections:
            raise ValueError(f"correction already exists: {cid}")
        revision = CorrectionRevision(
            correction_id=cid,
            revision=1,
            subject_digest=subject_digest(payload),
            payload=dict(payload),
            reversible=reversible,
        )
        self._corrections[cid] = CorrectionFamily(id=cid, incident_id=incident_id, revisions=[revision])
        return revision

    def revise_correction(
        self,
        correction_id: str,
        *,
        payload: Mapping[str, Any],
        reversible: bool | None = None,
    ) -> CorrectionRevision:
        family = self._corrections[correction_id]
        previous = family.current
        revision = CorrectionRevision(
            correction_id=correction_id,
            revision=previous.revision + 1,
            subject_digest=subject_digest(payload),
            payload=dict(payload),
            reversible=previous.reversible if reversible is None else reversible,
        )
        family.revisions.append(revision)
        return revision

    def record_qualification(self, qualification_id: str, result: QualificationResult) -> None:
        if qualification_id in self._qualifications:
            raise ValueError(f"qualification already exists: {qualification_id}")
        family = self._corrections[result.correction_id]
        known = {revision.revision: revision for revision in family.revisions}
        revision = known.get(result.correction_revision)
        if revision is None:
            raise KeyError("qualification references unknown correction revision")
        if result.exact_subject_digest != revision.subject_digest:
            raise StaleQualificationError("qualification digest does not match referenced correction revision")
        self._qualifications[qualification_id] = result

    def promote(
        self,
        *,
        correction_id: str,
        correction_revision: int,
        qualification_id: str,
        authorization: PromotionAuthorization,
    ) -> PromotionRecord:
        if not authorization.decision.allow or authorization.authorization_ref is None:
            raise PromotionRejectedError("promotion authorization was not granted")
        if authorization.activation_scope is None or authorization.rollback_condition is None:
            raise PromotionRejectedError("promotion authorization is missing bound effect contracts")

        family = self._corrections[correction_id]
        current = family.current
        if current.revision != correction_revision:
            raise StaleQualificationError("only the current correction revision may be promoted")

        qualification = self._qualifications[qualification_id]
        if not qualification.matches(current):
            raise StaleQualificationError("qualification is stale for the current correction revision")

        expected_validation = ValidationReport.evaluate(current, qualification)
        if not expected_validation.passed:
            raise PromotionRejectedError("qualification did not pass required validation")
        if authorization.validation != expected_validation:
            raise PromotionRejectedError(
                "promotion authorization is not bound to the recorded qualification"
            )

        promotion = PromotionRecord(
            id=self._id_factory(),
            correction_id=correction_id,
            correction_revision=correction_revision,
            qualification_id=qualification_id,
            activation_scope=authorization.activation_scope,
            rollback_condition=authorization.rollback_condition,
            policy_decision=authorization.decision,
            policy_name=authorization.policy_name,
            policy_version=authorization.policy_version,
            authorization_ref=authorization.authorization_ref,
            activated_at=_utcnow(),
        )
        self._promotions[promotion.id] = promotion
        return promotion

    def revoke(self, promotion_id: str, *, revoked_at: datetime | None = None) -> PromotionRecord:
        current = self._promotions[promotion_id]
        if current.revoked_at is not None:
            return current
        revoked = PromotionRecord(
            id=current.id,
            correction_id=current.correction_id,
            correction_revision=current.correction_revision,
            qualification_id=current.qualification_id,
            activation_scope=current.activation_scope,
            rollback_condition=current.rollback_condition,
            policy_decision=current.policy_decision,
            policy_name=current.policy_name,
            policy_version=current.policy_version,
            authorization_ref=current.authorization_ref,
            activated_at=current.activated_at,
            revoked_at=revoked_at or _utcnow(),
        )
        self._promotions[promotion_id] = revoked
        return revoked
