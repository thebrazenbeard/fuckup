import itertools

import pytest

from fuckup_protocol.authorization import PromotionAuthorization
from fuckup_protocol.ledger import IdempotencyCollisionError, InMemoryLedger, PromotionRejectedError, StaleQualificationError
from fuckup_protocol.models import PolicyDecision, QualificationResult, TestResult
from fuckup_protocol.validation import TestKind, ValidationReport


def _ids():
    counter = itertools.count(1)
    return lambda: f"id-{next(counter)}"


def _passing_qualification(correction):
    tests = tuple(
        TestResult(kind=kind.value, name=kind.value.lower(), passed=True)
        for kind in [TestKind.MFT, TestKind.CONTRAST, TestKind.TRANSFER, TestKind.RETAIN, TestKind.ANTI_TRIGGER]
    )
    return QualificationResult(
        correction_id=correction.correction_id,
        correction_revision=correction.revision,
        exact_subject_digest=correction.subject_digest,
        suite_version="suite-v1",
        tests=tests,
    )


def _authorization(correction, qualification, *, allow=True):
    return PromotionAuthorization(
        validation=ValidationReport.evaluate(correction, qualification),
        decision=PolicyDecision(allow=allow),
        activation_scope={"agent": "demo"},
        rollback_condition={"action": "revoke_on_regression"},
    )


def test_duplicate_incident_collapses_but_preserves_occurrence_count():
    ledger = InMemoryLedger(id_factory=_ids())
    first, duplicate = ledger.submit_incident(fingerprint="fp", fingerprint_version="v1", payload={"error": "boom"})
    second, duplicate2 = ledger.submit_incident(fingerprint="fp", fingerprint_version="v1", payload={"error": "boom"})

    assert not duplicate
    assert duplicate2
    assert first.id == second.id
    assert second.occurrence_count == 2


def test_event_idempotency_returns_existing_event_for_same_effect():
    ledger = InMemoryLedger(id_factory=_ids())
    incident, _ = ledger.submit_incident(fingerprint="fp", fingerprint_version="v1", payload={})
    first, duplicate = ledger.append_event(
        incident_id=incident.id,
        event_type="flagged",
        payload={"value": 1},
        idempotency_key="evt-1",
    )
    second, duplicate2 = ledger.append_event(
        incident_id=incident.id,
        event_type="flagged",
        payload={"value": 1},
        idempotency_key="evt-1",
    )

    assert not duplicate
    assert duplicate2
    assert first == second


def test_event_idempotency_reuse_for_different_effect_is_collision():
    ledger = InMemoryLedger(id_factory=_ids())
    incident, _ = ledger.submit_incident(fingerprint="fp", fingerprint_version="v1", payload={})
    ledger.append_event(
        incident_id=incident.id,
        event_type="flagged",
        payload={"value": 1},
        idempotency_key="evt-1",
    )

    with pytest.raises(IdempotencyCollisionError):
        ledger.append_event(
            incident_id=incident.id,
            event_type="flagged",
            payload={"value": 2},
            idempotency_key="evt-1",
        )


def test_old_qualification_becomes_stale_after_revision_change():
    ledger = InMemoryLedger(id_factory=_ids())
    incident, _ = ledger.submit_incident(fingerprint="fp", fingerprint_version="v1", payload={})
    correction = ledger.create_correction(incident_id=incident.id, payload={"rule": "v1"})
    qualification = _passing_qualification(correction)
    ledger.record_qualification("q-1", qualification)
    ledger.revise_correction(correction.correction_id, payload={"rule": "v2"})

    with pytest.raises(StaleQualificationError):
        ledger.promote(
            correction_id=correction.correction_id,
            correction_revision=1,
            qualification_id="q-1",
            authorization=_authorization(correction, qualification),
        )


def test_policy_rejection_blocks_promotion():
    ledger = InMemoryLedger(id_factory=_ids())
    incident, _ = ledger.submit_incident(fingerprint="fp", fingerprint_version="v1", payload={})
    correction = ledger.create_correction(incident_id=incident.id, payload={"rule": "v1"})
    ledger.record_qualification("q-1", _passing_qualification(correction))

    with pytest.raises(PromotionRejectedError):
        ledger.promote(
            correction_id=correction.correction_id,
            correction_revision=1,
            qualification_id="q-1",
            authorization=_authorization(correction, _passing_qualification(correction), allow=False),
        )


def test_revocation_preserves_promotion_identity_and_history_reference():
    ledger = InMemoryLedger(id_factory=_ids())
    incident, _ = ledger.submit_incident(fingerprint="fp", fingerprint_version="v1", payload={})
    correction = ledger.create_correction(incident_id=incident.id, payload={"rule": "v1"})
    ledger.record_qualification("q-1", _passing_qualification(correction))
    promotion = ledger.promote(
        correction_id=correction.correction_id,
        correction_revision=1,
        qualification_id="q-1",
        authorization=_authorization(correction, _passing_qualification(correction)),
    )
    revoked = ledger.revoke(promotion.id)

    assert revoked.id == promotion.id
    assert revoked.correction_id == promotion.correction_id
    assert revoked.revoked_at is not None


def test_failed_qualification_cannot_promote_even_with_allow_policy():
    ledger = InMemoryLedger(id_factory=_ids())
    incident, _ = ledger.submit_incident(fingerprint="fp", fingerprint_version="v1", payload={})
    correction = ledger.create_correction(incident_id=incident.id, payload={"rule": "v1"})
    tests = tuple(
        TestResult(
            kind=kind.value,
            name=kind.value.lower(),
            passed=kind != TestKind.RETAIN,
        )
        for kind in [TestKind.MFT, TestKind.CONTRAST, TestKind.TRANSFER, TestKind.RETAIN, TestKind.ANTI_TRIGGER]
    )
    qualification = QualificationResult(
        correction_id=correction.correction_id,
        correction_revision=correction.revision,
        exact_subject_digest=correction.subject_digest,
        suite_version="suite-v1",
        tests=tests,
    )
    ledger.record_qualification("q-fail", qualification)

    with pytest.raises(PromotionRejectedError):
        ledger.promote(
            correction_id=correction.correction_id,
            correction_revision=correction.revision,
            qualification_id="q-fail",
            authorization=_authorization(correction, qualification),
        )
