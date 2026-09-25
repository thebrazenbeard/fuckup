import pytest

from fuckup_protocol.operations import (
    IdempotencyCollisionError,
    InvalidOperationTransition,
    OperationJournal,
    OperationState,
)


def test_prepare_is_idempotent_for_the_same_exact_effect():
    journal = OperationJournal(id_factory=lambda: "op-1")
    first, duplicate = journal.prepare(
        target="memory:vera",
        operation_kind="write",
        effect_payload={"key": "value"},
        idempotency_key="idem-1",
    )
    second, duplicate2 = journal.prepare(
        target="memory:vera",
        operation_kind="write",
        effect_payload={"key": "value"},
        idempotency_key="idem-1",
    )

    assert not duplicate
    assert duplicate2
    assert first == second
    assert journal.state(first.id) == OperationState.PREPARED


def test_idempotency_key_collision_rejects_a_different_effect():
    journal = OperationJournal(id_factory=lambda: "op-1")
    journal.prepare(
        target="memory:vera",
        operation_kind="write",
        effect_payload={"key": "value"},
        idempotency_key="idem-1",
    )

    with pytest.raises(IdempotencyCollisionError):
        journal.prepare(
            target="memory:vera",
            operation_kind="write",
            effect_payload={"key": "different"},
            idempotency_key="idem-1",
        )


def test_attempt_then_verified_requires_reconciliation_evidence():
    journal = OperationJournal(id_factory=lambda: "op-1")
    intent, _ = journal.prepare(
        target="provider:demo",
        operation_kind="publish",
        effect_payload={"artifact": "a"},
        idempotency_key="idem-1",
    )

    attempted = journal.attempt(intent.id, evidence_ref="attempt:1")
    verified = journal.reconcile(
        intent.id,
        verified=True,
        evidence_ref="readback:1",
        readback_digest="sha256:observed",
    )

    assert attempted.state == OperationState.ATTEMPTED
    assert verified.state == OperationState.VERIFIED
    assert journal.state(intent.id) == OperationState.VERIFIED


def test_attempted_or_ambiguous_operation_cannot_be_blindly_attempted_again():
    journal = OperationJournal(id_factory=lambda: "op-1")
    intent, _ = journal.prepare(
        target="provider:demo",
        operation_kind="publish",
        effect_payload={"artifact": "a"},
        idempotency_key="idem-1",
    )
    journal.attempt(intent.id, evidence_ref="attempt:1")

    with pytest.raises(InvalidOperationTransition):
        journal.attempt(intent.id, evidence_ref="attempt:2")

    journal.mark_ambiguous(intent.id, evidence_ref="timeout:1")

    with pytest.raises(InvalidOperationTransition):
        journal.attempt(intent.id, evidence_ref="attempt:3")


def test_ambiguous_operation_can_reconcile_failed_but_not_reopen():
    journal = OperationJournal(id_factory=lambda: "op-1")
    intent, _ = journal.prepare(
        target="provider:demo",
        operation_kind="publish",
        effect_payload={"artifact": "a"},
        idempotency_key="idem-1",
    )
    journal.attempt(intent.id, evidence_ref="attempt:1")
    journal.mark_ambiguous(intent.id, evidence_ref="timeout:1")

    failed = journal.reconcile(
        intent.id,
        verified=False,
        evidence_ref="readback:not-found",
    )
    assert failed.state == OperationState.FAILED

    with pytest.raises(InvalidOperationTransition):
        journal.reconcile(
            intent.id,
            verified=True,
            evidence_ref="late-readback",
            readback_digest="sha256:late",
        )


def test_verified_reconciliation_requires_readback_digest():
    journal = OperationJournal(id_factory=lambda: "op-1")
    intent, _ = journal.prepare(
        target="provider:demo",
        operation_kind="publish",
        effect_payload={"artifact": "a"},
        idempotency_key="idem-1",
    )
    journal.attempt(intent.id, evidence_ref="attempt:1")

    with pytest.raises(ValueError):
        journal.reconcile(intent.id, verified=True, evidence_ref="readback:1")


def test_prepared_effect_payload_is_deeply_immutable():
    payload = {"outer": {"items": [1, 2]}}
    journal = OperationJournal(id_factory=lambda: "op-1")
    intent, _ = journal.prepare(
        target="provider:demo",
        operation_kind="publish",
        effect_payload=payload,
        idempotency_key="idem-1",
    )

    payload["outer"]["items"].append(3)
    assert intent.effect_payload["outer"]["items"] == (1, 2)