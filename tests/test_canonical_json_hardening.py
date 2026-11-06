"""Isolated, no-network falsifiers for canonical JSON and effect identity."""

import hashlib
import json

import pytest

from fuckup_protocol._canonical_json import canonical_json_bytes
from fuckup_protocol.bindings import InjectionBinding, selector_digest
from fuckup_protocol.execution import (
    ExecutionCoordinator, InjectorReadback, ReadbackDisposition,
)
from fuckup_protocol.fingerprint import fingerprint_incident
from fuckup_protocol.ledger import InMemoryLedger, effect_digest, subject_digest
from fuckup_protocol.models import CorrectionRevision
from fuckup_protocol.operations import OperationJournal, OperationState, operation_effect_digest
from fuckup_protocol.plugins import HandlerFamily, HandlerSpec, PluginRegistry, SideEffectClass
from fuckup_protocol.postgres_execution import PostgresExecutionStore


def test_valid_v1_bytes_and_digest_have_no_migration():
    payload = {"unicode": "é", "nested": {"beta": [2, True, None], "alpha": 1.5}}
    original = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    assert canonical_json_bytes(payload) == original
    assert subject_digest(payload) == "sha256:" + hashlib.sha256(original).hexdigest()
    assert operation_effect_digest(target="host", operation_kind="write", effect_payload=payload) == (
        "sha256:" + hashlib.sha256(json.dumps(
            {"target": "host", "operation_kind": "write", "effect_payload": payload},
            ensure_ascii=False, separators=(",", ":"), sort_keys=True,
        ).encode("utf-8")).hexdigest()
    )


@pytest.mark.parametrize("malicious", [
    {1: "alias"},
    {1: "first", "1": "second"},
    {"nested": [{"key": {2: "alias"}}]},
    {"value": float("nan")},
    {"value": float("inf")},
    {"value": float("-inf")},
])
def test_all_digest_and_freeze_entrypoints_reject_ambiguous_json(malicious):
    with pytest.raises((TypeError, ValueError)):
        subject_digest(malicious)
    with pytest.raises((TypeError, ValueError)):
        effect_digest(incident_id="i", event_type="record", payload=malicious)
    with pytest.raises((TypeError, ValueError)):
        operation_effect_digest(target="t", operation_kind="k", effect_payload=malicious)
    with pytest.raises((TypeError, ValueError)):
        fingerprint_incident(malicious)
    with pytest.raises((TypeError, ValueError)):
        CorrectionRevision(correction_id="c", revision=1, subject_digest="d", payload=malicious)
    with pytest.raises((TypeError, ValueError)):
        OperationJournal().prepare(
            target="t", operation_kind="k", effect_payload=malicious, idempotency_key="same",
        )


def test_numeric_and_string_mapping_key_cannot_share_fingerprint_or_subject_digest():
    literal = {"1": "value"}
    assert subject_digest(literal).startswith("sha256:")
    assert fingerprint_incident(literal).startswith("fuckup-fingerprint-v1:")
    with pytest.raises(TypeError):
        subject_digest({1: "value"})
    with pytest.raises(TypeError):
        fingerprint_incident({1: "value"})
    with pytest.raises(TypeError):
        selector_digest({1: "value"})


def test_invalid_existing_incident_does_not_increment_occurrence_or_count():
    ledger = InMemoryLedger()
    initial, duplicate = ledger.submit_incident(
        fingerprint="fp", fingerprint_version="v1", payload={"ok": True}
    )
    assert not duplicate
    with pytest.raises(TypeError):
        ledger.submit_incident(
            fingerprint="fp", fingerprint_version="v1", payload={1: "ambiguous"}
        )
    assert initial.occurrence_count == 1
    assert len(ledger.occurrences(initial.id)) == 1


def test_invalid_postgres_effect_never_opens_a_connection():
    calls = []
    store = PostgresExecutionStore(lambda: calls.append("connected"))
    with pytest.raises(TypeError):
        store.prepare(target="t", operation_kind="k", effect_payload={1: "x"}, idempotency_key="idem")
    assert calls == []


def test_invalid_postgres_binding_context_never_opens_a_connection():
    calls = []
    store = PostgresExecutionStore(lambda: calls.append("connected"))
    with pytest.raises(TypeError):
        store.bindings_for_context({1: "alias"})
    assert calls == []


def test_invalid_execution_effect_rejected_before_binding_or_authorizer_callbacks():
    calls = []
    coordinator = ExecutionCoordinator(
        registry=PluginRegistry(), operations=OperationJournal(),
        binding_currentness_validator=lambda _: calls.append("current") or True,
        protected_effect_authorizer=lambda *_: calls.append("authority") or "ok",
    )
    with pytest.raises(TypeError):
        coordinator.execute(
            bindings=(), context={}, target="t", effect_payload={1: "x"},
            idempotency_key="idem",
        )
    assert calls == []


def test_invalid_execution_context_rejected_before_binding_or_authorizer_callbacks():
    calls = []
    coordinator = ExecutionCoordinator(
        registry=PluginRegistry(), operations=OperationJournal(),
        binding_currentness_validator=lambda _: calls.append("current") or True,
        protected_effect_authorizer=lambda *_: calls.append("authority") or "ok",
    )
    with pytest.raises(TypeError):
        coordinator.execute(
            bindings=(), context={1: "alias"}, target="t", effect_payload={},
            idempotency_key="idem",
        )
    assert calls == []


def test_invalid_verified_readback_is_ambiguous_not_stuck_attempted():
    journal = OperationJournal()
    operation, _ = journal.prepare(
        target="t", operation_kind="injector:demo@1", effect_payload={},
        idempotency_key="idem",
    )
    journal.attempt(operation.id)
    binding = InjectionBinding(
        id="b", correction_id="c", correction_revision=1,
        selector={"host": "lappy"}, activation_scope={"host": "lappy"},
        promotion_id="p", adapter="demo", adapter_version="1",
    )
    spec = HandlerSpec(
        name="demo", family=HandlerFamily.INJECTOR, version="1",
        side_effect=SideEffectClass.REVERSIBLE_WRITE, idempotent=True, retryable=False,
    )
    coordinator = ExecutionCoordinator(
        registry=PluginRegistry(), operations=journal,
        binding_currentness_validator=lambda _: True,
    )
    with pytest.raises(ValueError):
        coordinator._apply_readback(
            operation=operation, binding=binding, spec=spec, handler_result=None,
            readback=InjectorReadback(
                disposition=ReadbackDisposition.VERIFIED, evidence_ref="readback:1",
                observed={"value": float("nan")},
            ),
        )
    assert journal.state(operation.id) == OperationState.AMBIGUOUS


