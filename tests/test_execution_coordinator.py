import pytest

from fuckup_protocol.bindings import BindingConflictError, InjectionBinding
from fuckup_protocol.execution import (
    ExecutionCoordinator,
    InjectorReadback,
    NoActiveBindingError,
    NonExecutableBindingError,
    ProtectedEffectDeniedError,
    ReadbackDisposition,
    StaleBindingError,
)
from fuckup_protocol.operations import InvalidOperationTransition, OperationJournal, OperationState
from fuckup_protocol.plugins import HandlerFamily, HandlerSpec, PluginRegistry, SideEffectClass


def _binding(
    binding_id="bind-1",
    *,
    correction_id="corr-1",
    revision=1,
    promotion_id="promo-1",
    adapter="memory-injector",
    adapter_version="1",
    active=True,
    priority=0,
):
    return InjectionBinding(
        binding_id,
        correction_id,
        revision,
        {"agent": "demo", "task": "code"},
        {"agent": "demo"},
        priority=priority,
        active=active,
        promotion_id=promotion_id,
        adapter=adapter,
        adapter_version=adapter_version,
    )


def _current(binding):
    return binding.active


def _registry(*, side_effect=SideEffectClass.REVERSIBLE_WRITE, execute=None, readback=None):
    registry = PluginRegistry()
    spec = HandlerSpec(
        name="memory-injector",
        family=HandlerFamily.INJECTOR,
        version="1",
        side_effect=side_effect,
        idempotent=True,
        retryable=True,
    )
    execute = execute or (lambda request: {"written": request["effect_payload"]["rule"]})
    readback = readback or (
        lambda request, result: InjectorReadback(
            ReadbackDisposition.VERIFIED,
            evidence_ref="readback:1",
            observed={"rule": request["effect_payload"]["rule"]},
            failure_occurred=False,
            prevented=True,
        )
    )
    registry.register_injector(spec, execute, readback)
    return registry


def test_verified_execution_flows_binding_to_exact_injector_and_bound_observation():
    journal = OperationJournal(id_factory=lambda: "op-1")
    states_seen = []

    def execute(request):
        states_seen.append(journal.state(request["operation_id"]))
        return {"written": request["effect_payload"]["rule"]}

    coordinator = ExecutionCoordinator(
        registry=_registry(execute=execute),
        operations=journal,
        binding_currentness_validator=_current,
    )
    result = coordinator.execute(
        bindings=(_binding(),),
        context={"agent": "demo", "task": "code"},
        target="memory:vera",
        effect_payload={"rule": "prefer exact evidence"},
        idempotency_key="inject:1",
    )

    assert states_seen == [OperationState.ATTEMPTED]
    assert result.binding.id == "bind-1"
    assert result.handler.name == "memory-injector"
    assert result.handler.version == "1"
    assert result.operation.id == "op-1"
    assert result.operation_state == OperationState.VERIFIED
    assert result.observation is not None
    assert result.observation.subject.correction_id == "corr-1"
    assert result.observation.subject.correction_revision == 1
    assert result.observation.subject.promotion_id == "promo-1"
    assert result.observation.subject.binding_id == "bind-1"
    assert result.observation.subject.scope_digest == result.binding.selector_digest
    assert result.observation.operation_id == "op-1"
    assert result.observation.effect_digest == result.operation.effect_digest
    assert result.observation.verification_evidence_ref == "readback:1"
    assert result.observation.prevented


def test_no_active_binding_fails_before_any_injector_execution():
    calls = []
    coordinator = ExecutionCoordinator(
        registry=_registry(execute=lambda request: calls.append(request) or {}),
        operations=OperationJournal(),
        binding_currentness_validator=_current,
    )

    with pytest.raises(NoActiveBindingError):
        coordinator.execute(
            bindings=(_binding(active=False),),
            context={"agent": "demo", "task": "code"},
            target="memory:vera",
            effect_payload={"rule": "x"},
            idempotency_key="inject:1",
        )

    assert calls == []


def test_binding_conflict_fails_closed_before_execution():
    calls = []
    coordinator = ExecutionCoordinator(
        registry=_registry(execute=lambda request: calls.append(request) or {}),
        operations=OperationJournal(),
        binding_currentness_validator=_current,
    )
    left = _binding("a", correction_id="c1")
    right = _binding("b", correction_id="c2")

    with pytest.raises(BindingConflictError):
        coordinator.execute(
            bindings=(left, right),
            context={"agent": "demo", "task": "code"},
            target="memory:vera",
            effect_payload={"rule": "x"},
            idempotency_key="inject:1",
        )

    assert calls == []


def test_legacy_binding_without_exact_execution_identity_is_not_executable():
    coordinator = ExecutionCoordinator(
        registry=_registry(),
        operations=OperationJournal(),
        binding_currentness_validator=_current,
    )
    legacy = InjectionBinding(
        "bind-legacy",
        "corr-1",
        1,
        {"agent": "demo"},
        {"agent": "demo"},
    )

    with pytest.raises(NonExecutableBindingError):
        coordinator.execute(
            bindings=(legacy,),
            context={"agent": "demo"},
            target="memory:vera",
            effect_payload={"rule": "x"},
            idempotency_key="inject:1",
        )


def test_adapter_version_mismatch_fails_before_operation_preparation():
    journal = OperationJournal()
    coordinator = ExecutionCoordinator(
        registry=_registry(),
        operations=journal,
        binding_currentness_validator=_current,
    )

    with pytest.raises(KeyError, match="exact handler version"):
        coordinator.execute(
            bindings=(_binding(adapter_version="2"),),
            context={"agent": "demo", "task": "code"},
            target="memory:vera",
            effect_payload={"rule": "x"},
            idempotency_key="inject:1",
        )


def test_protected_effect_requires_separate_exact_authority():
    calls = []
    coordinator = ExecutionCoordinator(
        registry=_registry(
            side_effect=SideEffectClass.PROTECTED_EFFECT,
            execute=lambda request: calls.append(request) or {},
        ),
        operations=OperationJournal(),
        binding_currentness_validator=_current,
    )

    with pytest.raises(ProtectedEffectDeniedError):
        coordinator.execute(
            bindings=(_binding(),),
            context={"agent": "demo", "task": "code"},
            target="weights:model",
            effect_payload={"delta": "x"},
            idempotency_key="inject:1",
        )

    assert calls == []


def test_ambiguous_readback_blocks_blind_retry_and_emits_no_effectiveness_observation():
    calls = []
    registry = _registry(
        execute=lambda request: calls.append(request) or {"accepted": True},
        readback=lambda request, result: InjectorReadback(
            ReadbackDisposition.AMBIGUOUS,
            evidence_ref="readback:timeout",
        ),
    )
    journal = OperationJournal(id_factory=lambda: "op-1")
    coordinator = ExecutionCoordinator(
        registry=registry,
        operations=journal,
        binding_currentness_validator=_current,
    )

    first = coordinator.execute(
        bindings=(_binding(),),
        context={"agent": "demo", "task": "code"},
        target="memory:vera",
        effect_payload={"rule": "x"},
        idempotency_key="inject:1",
    )
    assert first.operation_state == OperationState.AMBIGUOUS
    assert first.observation is None
    with pytest.raises(InvalidOperationTransition):
        coordinator.execute(
            bindings=(_binding(),),
            context={"agent": "demo", "task": "code"},
            target="memory:vera",
            effect_payload={"rule": "x"},
            idempotency_key="inject:1",
        )
    assert len(calls) == 1


def test_lost_execution_response_is_ambiguous_and_not_retried_blindly():
    calls = []

    def lost_response(request):
        calls.append(request)
        raise TimeoutError("response lost")

    journal = OperationJournal(id_factory=lambda: "op-1")
    coordinator = ExecutionCoordinator(
        registry=_registry(execute=lost_response),
        operations=journal,
        binding_currentness_validator=_current,
    )

    with pytest.raises(TimeoutError):
        coordinator.execute(
            bindings=(_binding(),),
            context={"agent": "demo", "task": "code"},
            target="memory:vera",
            effect_payload={"rule": "x"},
            idempotency_key="inject:1",
        )

    assert journal.state("op-1") == OperationState.AMBIGUOUS

    with pytest.raises(InvalidOperationTransition):
        coordinator.execute(
            bindings=(_binding(),),
            context={"agent": "demo", "task": "code"},
            target="memory:vera",
            effect_payload={"rule": "x"},
            idempotency_key="inject:1",
        )
    assert len(calls) == 1


def test_ambiguous_operation_can_later_reconcile_by_exact_adapter_readback():
    attempts = {"readback": 0}

    def readback(request, result):
        attempts["readback"] += 1
        if attempts["readback"] == 1:
            return InjectorReadback(
                ReadbackDisposition.AMBIGUOUS,
                evidence_ref="readback:timeout",
            )
        return InjectorReadback(
            ReadbackDisposition.VERIFIED,
            evidence_ref="readback:later",
            observed={"rule": request["effect_payload"]["rule"]},
            failure_occurred=False,
        )

    journal = OperationJournal(id_factory=lambda: "op-1")
    coordinator = ExecutionCoordinator(
        registry=_registry(readback=readback),
        operations=journal,
        binding_currentness_validator=_current,
    )
    initial = coordinator.execute(
        bindings=(_binding(),),
        context={"agent": "demo", "task": "code"},
        target="memory:vera",
        effect_payload={"rule": "x"},
        idempotency_key="inject:1",
    )
    assert initial.operation_state == OperationState.AMBIGUOUS

    reconciled = coordinator.reconcile("op-1")
    assert reconciled.operation_state == OperationState.VERIFIED
    assert reconciled.observation is not None
    assert reconciled.observation.operation_id == "op-1"
    assert reconciled.observation.verification_evidence_ref == "readback:later"


def test_stale_binding_currentness_fails_before_operation_or_execution():
    calls = []
    journal = OperationJournal()
    coordinator = ExecutionCoordinator(
        registry=_registry(execute=lambda request: calls.append(request) or {}),
        operations=journal,
        binding_currentness_validator=lambda binding: False,
    )

    with pytest.raises(StaleBindingError):
        coordinator.execute(
            bindings=(_binding(),),
            context={"agent": "demo", "task": "code"},
            target="memory:vera",
            effect_payload={"rule": "x"},
            idempotency_key="inject:stale",
        )

    assert calls == []


def test_verified_readback_requires_observed_target_state():
    with pytest.raises(ValueError, match="observed target state"):
        InjectorReadback(
            ReadbackDisposition.VERIFIED,
            evidence_ref="readback:label-only",
        )


def test_reconciliation_remains_allowed_after_binding_becomes_stale():
    current = {"value": True}
    attempts = {"readback": 0}

    def readback(request, result):
        attempts["readback"] += 1
        if attempts["readback"] == 1:
            return InjectorReadback(
                ReadbackDisposition.AMBIGUOUS,
                evidence_ref="readback:timeout",
            )
        return InjectorReadback(
            ReadbackDisposition.VERIFIED,
            evidence_ref="readback:after-revocation",
            observed={"rule": request["effect_payload"]["rule"]},
        )

    journal = OperationJournal(id_factory=lambda: "op-1")
    coordinator = ExecutionCoordinator(
        registry=_registry(readback=readback),
        operations=journal,
        binding_currentness_validator=lambda binding: current["value"],
    )
    first = coordinator.execute(
        bindings=(_binding(),),
        context={"agent": "demo", "task": "code"},
        target="memory:vera",
        effect_payload={"rule": "x"},
        idempotency_key="inject:reconcile-stale",
    )
    assert first.operation_state == OperationState.AMBIGUOUS

    current["value"] = False
    reconciled = coordinator.reconcile("op-1")
    assert reconciled.operation_state == OperationState.VERIFIED
    assert reconciled.observation is not None
    assert reconciled.observation.verification_evidence_ref == "readback:after-revocation"


def test_protected_effect_can_execute_only_when_exact_authority_seam_admits_it():
    seen = []

    def authorize(binding, spec, target, payload):
        seen.append((binding.id, spec.name, spec.version, target, dict(payload)))
        if binding.id == "bind-1" and target == "weights:model":
            return "authority:current-task"
        return None

    coordinator = ExecutionCoordinator(
        registry=_registry(side_effect=SideEffectClass.PROTECTED_EFFECT),
        operations=OperationJournal(id_factory=lambda: "op-1"),
        binding_currentness_validator=_current,
        protected_effect_authorizer=authorize,
    )
    result = coordinator.execute(
        bindings=(_binding(),),
        context={"agent": "demo", "task": "code"},
        target="weights:model",
        effect_payload={"rule": "x"},
        idempotency_key="inject:protected-authorized",
    )

    assert seen == [
        ("bind-1", "memory-injector", "1", "weights:model", {"rule": "x"})
    ]
    assert result.operation_state == OperationState.VERIFIED


def test_protected_effect_boolean_admission_without_evidence_reference_is_rejected():
    coordinator = ExecutionCoordinator(
        registry=_registry(side_effect=SideEffectClass.PROTECTED_EFFECT),
        operations=OperationJournal(),
        binding_currentness_validator=_current,
        protected_effect_authorizer=lambda binding, spec, target, payload: True,
    )

    with pytest.raises(ProtectedEffectDeniedError, match="authority evidence reference"):
        coordinator.execute(
            bindings=(_binding(),),
            context={"agent": "demo", "task": "code"},
            target="weights:model",
            effect_payload={"rule": "x"},
            idempotency_key="inject:protected-no-evidence",
        )

def test_verified_outcome_is_sent_to_durable_recorder():
    recorded = []
    coordinator = ExecutionCoordinator(
        registry=_registry(),
        operations=OperationJournal(id_factory=lambda: "op-1"),
        binding_currentness_validator=_current,
        outcome_recorder=recorded.append,
    )

    result = coordinator.execute(
        bindings=(_binding(),),
        context={"agent": "demo", "task": "code"},
        target="memory:vera",
        effect_payload={"rule": "x"},
        idempotency_key="inject:record-outcome",
    )

    assert result.operation_state == OperationState.VERIFIED
    assert recorded == [result.observation]


def test_verified_outcome_can_be_recovered_after_recorder_failure():
    journal = OperationJournal(id_factory=lambda: "op-1")
    calls = {"record": 0}
    recovered = []

    def flaky_recorder(observation):
        calls["record"] += 1
        if calls["record"] == 1:
            raise RuntimeError("durable outcome store unavailable")
        recovered.append(observation)

    coordinator = ExecutionCoordinator(
        registry=_registry(),
        operations=journal,
        binding_currentness_validator=_current,
        outcome_recorder=flaky_recorder,
    )

    with pytest.raises(RuntimeError, match="durable outcome store unavailable"):
        coordinator.execute(
            bindings=(_binding(),),
            context={"agent": "demo", "task": "code"},
            target="memory:vera",
            effect_payload={"rule": "x"},
            idempotency_key="inject:recover-outcome",
        )

    assert journal.state("op-1") == OperationState.VERIFIED

    result = coordinator.recover_outcome("op-1")
    assert result.operation_state == OperationState.VERIFIED
    assert recovered == [result.observation]