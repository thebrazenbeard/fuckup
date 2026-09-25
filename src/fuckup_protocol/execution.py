from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Callable, Mapping

from .bindings import InjectionBinding, resolve_binding
from .effectiveness import EffectivenessSubject, ObservationPhase, OutcomeObservation
from .operations import OperationIntent, OperationJournal, OperationState
from .plugins import HandlerSpec, PluginRegistry, SideEffectClass


class ReadbackDisposition(StrEnum):
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True, slots=True)
class InjectorReadback:
    disposition: ReadbackDisposition
    evidence_ref: str
    observed: Mapping[str, Any] | None = None
    failure_occurred: bool = False
    prevented: bool = False
    regression: bool = False

    def __post_init__(self) -> None:
        if not self.evidence_ref:
            raise ValueError("readback evidence_ref is required")
        if self.disposition == ReadbackDisposition.VERIFIED and self.observed is None:
            raise ValueError("verified readback requires observed target state")
        if self.observed is not None:
            object.__setattr__(self, "observed", MappingProxyType(dict(self.observed)))


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    binding: InjectionBinding
    handler: HandlerSpec
    operation: OperationIntent
    operation_state: OperationState
    handler_result: Mapping[str, Any] | None
    readback: InjectorReadback | None
    observation: OutcomeObservation | None


class NoActiveBindingError(LookupError):
    pass


class NonExecutableBindingError(ValueError):
    pass


class ProtectedEffectDeniedError(PermissionError):
    pass


class StaleBindingError(PermissionError):
    pass


ProtectedEffectAuthorizer = Callable[[InjectionBinding, HandlerSpec, str, Mapping[str, Any]], str | None]
BindingCurrentnessValidator = Callable[[InjectionBinding], bool]
OutcomeRecorder = Callable[[OutcomeObservation], None]


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_plain(item) for item in value]
    if isinstance(value, set | frozenset):
        return sorted(_plain(item) for item in value)
    return value


def _payload_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        _plain(payload),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class ExecutionCoordinator:
    """Governed binding -> injector -> effect -> readback execution boundary."""

    def __init__(
        self,
        *,
        registry: PluginRegistry,
        operations: OperationJournal,
        binding_currentness_validator: BindingCurrentnessValidator,
        protected_effect_authorizer: ProtectedEffectAuthorizer | None = None,
        outcome_recorder: OutcomeRecorder | None = None,
    ) -> None:
        self._registry = registry
        self._operations = operations
        self._binding_currentness_validator = binding_currentness_validator
        self._protected_effect_authorizer = protected_effect_authorizer
        self._outcome_recorder = outcome_recorder

    def execute(
        self,
        *,
        bindings: tuple[InjectionBinding, ...],
        context: Mapping[str, str],
        target: str,
        effect_payload: Mapping[str, Any],
        idempotency_key: str,
    ) -> ExecutionResult:
        binding = resolve_binding(bindings, context)
        if binding is None:
            raise NoActiveBindingError("no active injection binding matches execution context")
        self._require_executable_binding(binding)
        if not self._binding_currentness_validator(binding):
            raise StaleBindingError(
                "selected injection binding is not current at execution time"
            )

        spec, handler, readback = self._registry.resolve_injector(
            binding.adapter,
            binding.adapter_version,
        )
        authority_ref = self._authorize_side_effect(
            binding=binding,
            spec=spec,
            target=target,
            effect_payload=effect_payload,
        )

        operation_payload = self._operation_payload(
            binding=binding,
            context=context,
            effect_payload=effect_payload,
            authority_ref=authority_ref,
        )
        operation, _duplicate = self._operations.prepare(
            target=target,
            operation_kind=f"injector:{spec.name}@{spec.version}",
            effect_payload=operation_payload,
            idempotency_key=idempotency_key,
        )
        self._operations.attempt(
            operation.id,
            evidence_ref=f"binding:{binding.id}",
        )

        invocation = self._invocation(operation)
        try:
            handler_result = handler(invocation)
        except Exception:
            self._operations.mark_ambiguous(
                operation.id,
                evidence_ref=f"execute-exception:{spec.name}@{spec.version}",
            )
            raise

        if not isinstance(handler_result, Mapping):
            self._operations.mark_ambiguous(
                operation.id,
                evidence_ref=f"invalid-execution-result:{spec.name}@{spec.version}",
            )
            raise TypeError("injector handler must return a mapping")

        try:
            readback_result = readback(invocation, handler_result)
        except Exception:
            self._operations.mark_ambiguous(
                operation.id,
                evidence_ref=f"readback-exception:{spec.name}@{spec.version}",
            )
            raise

        if not isinstance(readback_result, InjectorReadback):
            self._operations.mark_ambiguous(
                operation.id,
                evidence_ref=f"invalid-readback-result:{spec.name}@{spec.version}",
            )
            raise TypeError("injector readback must return InjectorReadback")

        return self._apply_readback(
            operation=operation,
            binding=binding,
            spec=spec,
            handler_result=dict(handler_result),
            readback=readback_result,
        )

    def reconcile(self, operation_id: str) -> ExecutionResult:
        operation = self._operations.intent(operation_id)
        binding = self._binding_from_operation(operation)
        self._require_executable_binding(binding)
        spec, _handler, readback = self._registry.resolve_injector(
            binding.adapter,
            binding.adapter_version,
        )
        invocation = self._invocation(operation)

        try:
            readback_result = readback(invocation, None)
        except Exception:
            if self._operations.state(operation_id) == OperationState.ATTEMPTED:
                self._operations.mark_ambiguous(
                    operation_id,
                    evidence_ref=f"readback-exception:{spec.name}@{spec.version}",
                )
            raise

        if not isinstance(readback_result, InjectorReadback):
            if self._operations.state(operation_id) == OperationState.ATTEMPTED:
                self._operations.mark_ambiguous(
                    operation_id,
                    evidence_ref=f"invalid-readback-result:{spec.name}@{spec.version}",
                )
            raise TypeError("injector readback must return InjectorReadback")

        return self._apply_readback(
            operation=operation,
            binding=binding,
            spec=spec,
            handler_result=None,
            readback=readback_result,
        )

    def recover_outcome(self, operation_id: str) -> ExecutionResult:
        if self._operations.state(operation_id) != OperationState.VERIFIED:
            raise ValueError("outcome recovery requires a VERIFIED operation")
        operation = self._operations.intent(operation_id)
        binding = self._binding_from_operation(operation)
        self._require_executable_binding(binding)
        spec, _handler, readback = self._registry.resolve_injector(
            binding.adapter,
            binding.adapter_version,
        )
        readback_result = readback(self._invocation(operation), None)
        if not isinstance(readback_result, InjectorReadback):
            raise TypeError("injector readback must return InjectorReadback")
        if readback_result.disposition != ReadbackDisposition.VERIFIED:
            raise ValueError("verified operation no longer has VERIFIED adapter readback")

        verified_events = [
            event
            for event in self._operations.events(operation_id)
            if event.state == OperationState.VERIFIED
        ]
        if not verified_events:
            raise ValueError("VERIFIED operation is missing verification event evidence")
        verification_event = verified_events[-1]
        observed_digest = _payload_digest(readback_result.observed or {})
        if verification_event.readback_digest != observed_digest:
            raise ValueError("verified target state changed since original verification")

        observation = self._build_observation(
            operation=operation,
            binding=binding,
            readback=readback_result,
            verification_evidence_ref=verification_event.evidence_ref,
        )
        self._record_outcome(observation)
        return ExecutionResult(
            binding=binding,
            handler=spec,
            operation=operation,
            operation_state=OperationState.VERIFIED,
            handler_result=None,
            readback=readback_result,
            observation=observation,
        )

    def _authorize_side_effect(
        self,
        *,
        binding: InjectionBinding,
        spec: HandlerSpec,
        target: str,
        effect_payload: Mapping[str, Any],
    ) -> str | None:
        if spec.side_effect != SideEffectClass.PROTECTED_EFFECT:
            return None
        if self._protected_effect_authorizer is None:
            raise ProtectedEffectDeniedError(
                "protected injector effect requires separate exact authority"
            )
        authority_ref = self._protected_effect_authorizer(
            binding,
            spec,
            target,
            effect_payload,
        )
        if not isinstance(authority_ref, str) or not authority_ref.strip():
            raise ProtectedEffectDeniedError(
                "protected injector effect requires an authority evidence reference"
            )
        return authority_ref

    @staticmethod
    def _require_executable_binding(binding: InjectionBinding) -> None:
        if not binding.executable:
            raise NonExecutableBindingError(
                "active binding lacks exact promotion/adapter/version execution identity"
            )

    @staticmethod
    def _operation_payload(
        *,
        binding: InjectionBinding,
        context: Mapping[str, str],
        effect_payload: Mapping[str, Any],
        authority_ref: str | None,
    ) -> dict[str, Any]:
        return {
            "binding_id": binding.id,
            "promotion_id": binding.promotion_id,
            "correction_id": binding.correction_id,
            "correction_revision": binding.correction_revision,
            "selector": dict(binding.selector),
            "selector_digest": binding.selector_digest,
            "activation_scope": dict(binding.activation_scope),
            "adapter": binding.adapter,
            "adapter_version": binding.adapter_version,
            "authority_ref": authority_ref,
            "context": dict(context),
            "effect_payload": _plain(effect_payload),
        }

    @staticmethod
    def _invocation(operation: OperationIntent) -> dict[str, Any]:
        payload = _plain(operation.effect_payload)
        return {
            **payload,
            "operation_id": operation.id,
            "effect_digest": operation.effect_digest,
            "target": operation.target,
        }

    def _apply_readback(
        self,
        *,
        operation: OperationIntent,
        binding: InjectionBinding,
        spec: HandlerSpec,
        handler_result: Mapping[str, Any] | None,
        readback: InjectorReadback,
    ) -> ExecutionResult:
        if readback.disposition == ReadbackDisposition.AMBIGUOUS:
            if self._operations.state(operation.id) == OperationState.ATTEMPTED:
                self._operations.mark_ambiguous(
                    operation.id,
                    evidence_ref=readback.evidence_ref,
                )
            return ExecutionResult(
                binding=binding,
                handler=spec,
                operation=operation,
                operation_state=self._operations.state(operation.id),
                handler_result=handler_result,
                readback=readback,
                observation=None,
            )

        if readback.disposition == ReadbackDisposition.FAILED:
            self._operations.reconcile(
                operation.id,
                verified=False,
                evidence_ref=readback.evidence_ref,
            )
            return ExecutionResult(
                binding=binding,
                handler=spec,
                operation=operation,
                operation_state=OperationState.FAILED,
                handler_result=handler_result,
                readback=readback,
                observation=None,
            )

        observed = readback.observed or {}
        observed_digest = _payload_digest(observed)
        self._operations.reconcile(
            operation.id,
            verified=True,
            evidence_ref=readback.evidence_ref,
            readback_digest=observed_digest,
        )
        observation = self._build_observation(
            operation=operation,
            binding=binding,
            readback=readback,
            verification_evidence_ref=readback.evidence_ref,
        )
        self._record_outcome(observation)
        return ExecutionResult(
            binding=binding,
            handler=spec,
            operation=operation,
            operation_state=OperationState.VERIFIED,
            handler_result=handler_result,
            readback=readback,
            observation=observation,
        )



    def _build_observation(
        self,
        *,
        operation: OperationIntent,
        binding: InjectionBinding,
        readback: InjectorReadback,
        verification_evidence_ref: str | None,
    ) -> OutcomeObservation:
        subject = EffectivenessSubject(
            correction_id=binding.correction_id,
            correction_revision=binding.correction_revision,
            scope_digest=binding.selector_digest,
            promotion_id=binding.promotion_id,
            binding_id=binding.id,
        )
        return OutcomeObservation(
            phase=ObservationPhase.ACTIVE,
            failure_occurred=readback.failure_occurred,
            correction_triggered=True,
            prevented=readback.prevented,
            regression=readback.regression,
            subject=subject,
            operation_id=operation.id,
            effect_digest=operation.effect_digest,
            verification_evidence_ref=verification_evidence_ref,
        )

    def _record_outcome(self, observation: OutcomeObservation) -> None:
        if self._outcome_recorder is not None:
            self._outcome_recorder(observation)


    @staticmethod
    def _binding_from_operation(operation: OperationIntent) -> InjectionBinding:
        payload = operation.effect_payload
        return InjectionBinding(
            id=str(payload["binding_id"]),
            correction_id=str(payload["correction_id"]),
            correction_revision=int(payload["correction_revision"]),
            selector=_plain(payload["selector"]),
            activation_scope=_plain(payload["activation_scope"]),
            promotion_id=str(payload["promotion_id"]),
            adapter=str(payload["adapter"]),
            adapter_version=str(payload["adapter_version"]),
        )