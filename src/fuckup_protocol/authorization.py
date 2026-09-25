from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .models import CorrectionRevision, PolicyDecision, QualificationResult
from .policy import PromotionContext, PromotionPolicy, StrictPromotionPolicy
from .validation import ValidationReport


def _freeze_string_map(value: Mapping[str, str] | None, *, field: str) -> Mapping[str, str] | None:
    if value is None:
        return None
    normalized: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{field} keys must be non-empty strings")
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field} values must be non-empty strings")
        normalized[key] = item
    return MappingProxyType(normalized)


@dataclass(frozen=True, slots=True)
class PromotionAuthorization:
    validation: ValidationReport
    decision: PolicyDecision
    activation_scope: Mapping[str, str] | None
    rollback_condition: Mapping[str, str] | None

    def __post_init__(self) -> None:
        scope = _freeze_string_map(self.activation_scope, field="activation_scope")
        rollback = _freeze_string_map(self.rollback_condition, field="rollback_condition")
        object.__setattr__(self, "activation_scope", scope)
        object.__setattr__(self, "rollback_condition", rollback)
        if self.decision.allow and (not scope or not rollback):
            raise ValueError("allowed promotion authorization requires scope and rollback condition")


def authorize_promotion(
    *,
    correction: CorrectionRevision,
    qualification: QualificationResult,
    root_cause_supported: bool,
    ambiguous: bool,
    activation_scope: Mapping[str, str] | None,
    rollback_condition: Mapping[str, str] | None,
    irreversible_acknowledged: bool = False,
    policy: PromotionPolicy | None = None,
) -> PromotionAuthorization:
    """Recompute validation and policy and bind the exact authorized effect."""

    frozen_scope = _freeze_string_map(activation_scope, field="activation_scope")
    frozen_rollback = _freeze_string_map(rollback_condition, field="rollback_condition")
    validation = ValidationReport.evaluate(correction, qualification)
    evaluator = policy or StrictPromotionPolicy()
    decision = evaluator.evaluate(
        PromotionContext(
            correction=correction,
            validation=validation,
            root_cause_supported=root_cause_supported,
            ambiguous=ambiguous,
            activation_scope=frozen_scope,
            rollback_condition=frozen_rollback,
            irreversible_acknowledged=irreversible_acknowledged,
        )
    )
    return PromotionAuthorization(
        validation=validation,
        decision=decision,
        activation_scope=frozen_scope,
        rollback_condition=frozen_rollback,
    )
