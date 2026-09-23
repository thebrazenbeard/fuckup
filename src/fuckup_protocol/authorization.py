from __future__ import annotations

from dataclasses import dataclass

from .models import CorrectionRevision, PolicyDecision, QualificationResult
from .policy import PromotionContext, PromotionPolicy, StrictPromotionPolicy
from .scope import SelectorScope
from .validation import ValidationReport


@dataclass(frozen=True, slots=True)
class PromotionAuthorization:
    validation: ValidationReport
    decision: PolicyDecision


def authorize_promotion(
    *,
    correction: CorrectionRevision,
    qualification: QualificationResult,
    root_cause_supported: bool,
    ambiguous: bool,
    activation_scope: SelectorScope | None,
    rollback_condition: str | None,
    irreversible_acknowledged: bool = False,
    policy: PromotionPolicy | None = None,
) -> PromotionAuthorization:
    """Recompute validation and policy at the authorization boundary.

    External adapters should call this function rather than constructing a
    ValidationReport or PolicyDecision and treating those objects as authority.
    """

    validation = ValidationReport.evaluate(correction, qualification)
    evaluator = policy or StrictPromotionPolicy()
    decision = evaluator.evaluate(
        PromotionContext(
            correction=correction,
            validation=validation,
            root_cause_supported=root_cause_supported,
            ambiguous=ambiguous,
            activation_scope=activation_scope,
            rollback_condition=rollback_condition,
            irreversible_acknowledged=irreversible_acknowledged,
        )
    )
    return PromotionAuthorization(validation=validation, decision=decision)
