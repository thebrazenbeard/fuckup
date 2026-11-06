"""Fail-closed session context bridge for a *previously verified* correction.

This module does not operate ChatGPT, alter model weights, or prove a model
obeyed instructions. The host must inject the message into a trusted message
role and call ``verify_materialized_prompt`` before dispatching to a model.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from .bindings import InjectionBinding, resolve_binding
from .execution import ReadbackDisposition
from .ledger import subject_digest
from .models import CorrectionRevision
from .operations import OperationEvent, OperationIntent, OperationState, operation_effect_digest
from .reference_adapter import ReferenceFileInjector


_SESSION_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class SessionPreflightError(RuntimeError):
    """A session must not start with an unverified or stale correction."""


class SessionExecutionStore(Protocol):
    """Subset supplied by the durable PostgresExecutionStore."""

    def bindings_for_context(self, context: Mapping[str, str]) -> tuple[InjectionBinding, ...]: ...

    def binding_is_current(self, binding: InjectionBinding) -> bool: ...

    def correction_for_active_binding(self, binding: InjectionBinding) -> CorrectionRevision: ...

    def intent(self, operation_id: str) -> OperationIntent: ...

    def state(self, operation_id: str) -> OperationState: ...

    def events(self, operation_id: str) -> tuple[OperationEvent, ...]: ...

    def outcome_for_operation(self, operation_id: str) -> Any: ...


@dataclass(frozen=True, slots=True)
class SessionPreflight:
    session_id: str
    binding_id: str
    promotion_id: str
    correction_id: str
    correction_revision: int
    effect_digest: str
    source_evidence_ref: str
    message: str
    message_digest: str


@dataclass(frozen=True, slots=True)
class ContextMaterialization:
    session_id: str
    message_digest: str
    trusted_message_role: str
    context_digest: str


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    return value


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def load_reference_session_preflight(
    *,
    store: SessionExecutionStore,
    adapter: ReferenceFileInjector,
    context: Mapping[str, str],
    expected_target: str,
    operation_id: str,
    session_id: str,
) -> SessionPreflight:
    """Recover a qualified instruction from durable state on a *new* session.

    The caller supplies host-authenticated context, a pinned target and exact
    operation ID. This method only reads; it cannot promote a correction.
    """
    if not isinstance(session_id, str) or not _SESSION_ID.fullmatch(session_id):
        raise SessionPreflightError("invalid host session ID")
    if not context or any(
        not isinstance(k, str) or not k or not isinstance(v, str) or not v
        for k, v in context.items()
    ):
        raise SessionPreflightError("host context must contain nonempty string selectors")

    binding = resolve_binding(store.bindings_for_context(context), context)
    if binding is None or not binding.executable:
        raise SessionPreflightError("no exact active executable correction binding")
    if binding.adapter != adapter.name or binding.adapter_version != adapter.version:
        raise SessionPreflightError("selected binding is not for the pinned reference adapter")
    if not store.binding_is_current(binding):
        raise SessionPreflightError("selected binding is stale or revoked")

    correction = store.correction_for_active_binding(binding)
    if (correction.correction_id, correction.revision) != (
        binding.correction_id, binding.correction_revision
    ):
        raise SessionPreflightError("correction does not match the exact binding revision")
    if subject_digest(_plain(correction.payload)) != correction.subject_digest:
        raise SessionPreflightError("authoritative correction payload digest mismatch")
    instruction = correction.payload.get("session_instruction")
    if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 10000:
        raise SessionPreflightError("correction lacks a bounded session_instruction")

    operation = store.intent(operation_id)
    if operation.target != expected_target:
        raise SessionPreflightError("operation target differs from host-pinned target")
    if operation.operation_kind != f"injector:{adapter.name}@{adapter.version}":
        raise SessionPreflightError("operation was not produced by the pinned injector")
    if store.state(operation_id) != OperationState.VERIFIED:
        raise SessionPreflightError("prior correction execution is not VERIFIED")

    payload = _plain(operation.effect_payload)
    expected_fields = {
        "binding_id": binding.id,
        "promotion_id": binding.promotion_id,
        "correction_id": binding.correction_id,
        "correction_revision": binding.correction_revision,
        "selector": dict(binding.selector),
        "selector_digest": binding.selector_digest,
        "activation_scope": dict(binding.activation_scope),
        "adapter": binding.adapter,
        "adapter_version": binding.adapter_version,
        "effect_payload": _plain(correction.payload),
    }
    if any(payload.get(key) != value for key, value in expected_fields.items()):
        raise SessionPreflightError("recorded effect does not match approved correction and binding")
    if payload.get("context") != dict(context):
        raise SessionPreflightError("recorded effect context is not this session's authorized context")
    recomputed = operation_effect_digest(
        target=operation.target,
        operation_kind=operation.operation_kind,
        effect_payload=payload,
    )
    if recomputed != operation.effect_digest:
        raise SessionPreflightError("operation effect digest mismatch")

    readback = adapter.readback(
        {
            "target": operation.target,
            "operation_id": operation.id,
            "effect_digest": operation.effect_digest,
        },
        None,
    )
    if readback.disposition != ReadbackDisposition.VERIFIED or readback.observed is None:
        raise SessionPreflightError("current correction file failed observed readback")
    observed = _plain(readback.observed)
    if any((
        observed.get("target") != operation.target,
        observed.get("operation_id") != operation.id,
        observed.get("effect_digest") != operation.effect_digest,
        observed.get("payload") != _plain(correction.payload),
    )):
        raise SessionPreflightError("current correction file differs from the verified operation")

    verified_events = [event for event in store.events(operation_id) if event.state == OperationState.VERIFIED]
    if len(verified_events) != 1:
        raise SessionPreflightError("exactly one durable verification event is required")
    event = verified_events[0]
    if event.readback_digest != _digest(observed) or event.evidence_ref != readback.evidence_ref:
        raise SessionPreflightError("fresh file readback differs from the recorded verification")
    outcome = store.outcome_for_operation(operation_id)
    if outcome is None or any((
        outcome.operation_id != operation.id,
        outcome.binding_id != binding.id,
        outcome.promotion_id != binding.promotion_id,
        outcome.correction_id != binding.correction_id,
        outcome.correction_revision != binding.correction_revision,
        outcome.scope_digest != binding.selector_digest,
        outcome.effect_digest != operation.effect_digest,
        outcome.verification_evidence_ref != event.evidence_ref,
    )):
        raise SessionPreflightError("verified operation lacks its exact durable outcome")
    if not store.binding_is_current(binding):
        raise SessionPreflightError("correction was revoked during preflight")

    message = (
        "F.U.C.K.U.P. / ACTIVE SESSION CORRECTION\n"
        f"Session: {session_id}\n"
        f"Correction: {binding.correction_id}@{binding.correction_revision}\n"
        f"Promotion: {binding.promotion_id}\n"
        f"Binding: {binding.id}\n"
        f"Verified effect: {operation.effect_digest}\n"
        "Apply this approved, scoped instruction during this task:\n"
        f"{instruction}\n"
        "Do not treat this instruction's presence as proof of compliance; verify task outcomes."
    )
    return SessionPreflight(
        session_id=session_id,
        binding_id=binding.id,
        promotion_id=binding.promotion_id or "",
        correction_id=binding.correction_id,
        correction_revision=binding.correction_revision,
        effect_digest=operation.effect_digest,
        source_evidence_ref=event.evidence_ref or "",
        message=message,
        message_digest=_digest(message),
    )


def verify_materialized_prompt(
    preflight: SessionPreflight,
    actual_model_messages: Sequence[Mapping[str, str]],
) -> ContextMaterialization:
    """Host-side readback: fail if the model request lacks the exact correction.

    The host must pass the actual request messages, not a planned prompt or a
    model-generated description of what it was shown. This is NOT proof that
    the remote ChatGPT service consumed or obeyed the request.
    """
    matches = [
        (role, text)
        for message in actual_model_messages
        if (role := message.get("role")) in {"system", "developer"}
        if isinstance((text := message.get("content")), str)
        if preflight.message in text
    ]
    occurrences = sum(content.count(preflight.message) for _role, content in matches) if preflight.message else 0
    if occurrences != 1 or _digest(preflight.message) != preflight.message_digest:
        raise SessionPreflightError("exact correction was not present once in a trusted model message")
    return ContextMaterialization(
        session_id=preflight.session_id,
        message_digest=preflight.message_digest,
        trusted_message_role=matches[0][0],
        context_digest=_digest(_plain(actual_model_messages)),
    )


def verify_dispatch_currentness(
    preflight: SessionPreflight,
    *,
    store: SessionExecutionStore,
    context: Mapping[str, str],
) -> None:
    """Host must call immediately before model dispatch, after prompt readback.

    This narrows, but cannot eliminate, the cross-system revocation race.
    """
    binding = resolve_binding(store.bindings_for_context(context), context)
    if binding is None or not binding.executable or not store.binding_is_current(binding):
        raise SessionPreflightError("correction was revoked before dispatch")
    if (
        binding.id != preflight.binding_id
        or binding.promotion_id != preflight.promotion_id
        or binding.correction_id != preflight.correction_id
        or binding.correction_revision != preflight.correction_revision
    ):
        raise SessionPreflightError("a different correction binding replaced the preflight")
