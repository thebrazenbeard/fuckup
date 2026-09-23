from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .models import CorrectionRevision, PolicyDecision, QualificationResult
from .policy import PromotionContext, PromotionPolicy, StrictPromotionPolicy
from .scope import SelectorScope, freeze_selector_scope, is_selector_scope
from .validation import ValidationReport


@dataclass(frozen=True, slots=True)
class PromotionAuthorization:
    validation: ValidationReport
    decision: PolicyDecision
    activation_scope: SelectorScope | None
    rollback_condition: str | None
    authorization_ref: str | None


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

    frozen_scope = freeze_selector_scope(activation_scope) if is_selector_scope(activation_scope) else None
    authorization_ref: str | None = None
    if decision.allow:
        if frozen_scope is None:
            raise RuntimeError("allowing policy returned without a valid selector-shaped activation scope")
        artifact = {
            "correction_id": correction.correction_id,
            "correction_revision": correction.revision,
            "exact_subject_digest": correction.subject_digest,
            "qualification": {
                "suite_version": qualification.suite_version,
                "tests": sorted(
                    (
                        {
                            "kind": test.kind,
                            "name": test.name,
                            "passed": test.passed,
                            "evidence_ref": test.evidence_ref,
                            "detail": test.detail,
                        }
                        for test in qualification.tests
                    ),
                    key=lambda item: (
                        item["kind"],
                        item["name"],
                        item["evidence_ref"] or "",
                        item["detail"] or "",
                    ),
                ),
            },
            "policy": {
                "implementation": f"{evaluator.__class__.__module__}.{evaluator.__class__.__qualname__}",
                "allow": decision.allow,
                "reasons": list(decision.reasons),
                "required_actions": list(decision.required_actions),
                "root_cause_supported": root_cause_supported,
                "ambiguous": ambiguous,
                "irreversible_acknowledged": irreversible_acknowledged,
            },
            "activation_scope": dict(frozen_scope),
            "rollback_condition": rollback_condition,
        }
        encoded = json.dumps(
            artifact,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        authorization_ref = f"sha256:{hashlib.sha256(encoded).hexdigest()}"

    return PromotionAuthorization(
        validation=validation,
        decision=decision,
        activation_scope=frozen_scope,
        rollback_condition=rollback_condition,
        authorization_ref=authorization_ref,
    )
