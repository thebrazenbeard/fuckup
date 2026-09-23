"""Executable core for the F.U.C.K.U.P. corrective-learning protocol."""

from .fingerprint import fingerprint_incident
from .models import CorrectionRevision, PolicyDecision, QualificationResult, TestResult
from .policy import PromotionContext, PromotionPolicy, StrictPromotionPolicy
from .state import CorrectionState, InvalidTransition, can_transition, require_transition
from .validation import TestKind, ValidationReport

__all__ = [
    "CorrectionRevision",
    "CorrectionState",
    "InvalidTransition",
    "PolicyDecision",
    "PromotionContext",
    "PromotionPolicy",
    "QualificationResult",
    "StrictPromotionPolicy",
    "TestKind",
    "TestResult",
    "ValidationReport",
    "can_transition",
    "fingerprint_incident",
    "require_transition",
]
