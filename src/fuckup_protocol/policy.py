from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import CorrectionRevision, PolicyDecision
from .scope import SelectorScope, is_selector_scope
from .validation import ValidationReport


@dataclass(frozen=True, slots=True)
class PromotionContext:
    correction: CorrectionRevision
    validation: ValidationReport
    root_cause_supported: bool
    ambiguous: bool
    activation_scope: SelectorScope | None
    rollback_condition: str | None
    irreversible_acknowledged: bool = False


class PromotionPolicy(Protocol):
    def evaluate(self, context: PromotionContext) -> PolicyDecision: ...


class StrictPromotionPolicy:
    """Fail-closed baseline policy for durable correction promotion."""

    def evaluate(self, context: PromotionContext) -> PolicyDecision:
        reasons: list[str] = []
        actions: list[str] = []

        if not context.validation.matches_correction(context.correction):
            reasons.append("validation report does not bind to this exact correction")
        if context.ambiguous:
            reasons.append("root cause remains materially ambiguous")
        if not context.root_cause_supported:
            reasons.append("root cause is not supported")
        if not context.validation.current:
            reasons.append("qualification is stale for this correction revision")
        if not context.validation.passed:
            reasons.append("required validation did not pass")
        if not is_selector_scope(context.activation_scope):
            reasons.append("activation scope must be a non-empty flat selector of JSON scalar values")
        if not context.rollback_condition:
            reasons.append("rollback/revocation condition is required")
        if not context.correction.reversible and not context.irreversible_acknowledged:
            reasons.append("irreversible correction requires explicit acknowledgement")
            actions.append("obtain explicit irreversible-effect approval")

        return PolicyDecision(
            allow=not reasons,
            reasons=tuple(reasons),
            required_actions=tuple(actions),
        )
