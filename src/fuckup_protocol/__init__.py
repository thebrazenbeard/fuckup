"""Executable core for the F.U.C.K.U.P. corrective-learning protocol."""

from .fingerprint import fingerprint_incident
from .ledger import InMemoryLedger, PromotionRejectedError, StaleQualificationError, subject_digest
from .models import CorrectionRevision, PolicyDecision, QualificationResult, TestResult
from .policy import PromotionContext, PromotionPolicy, StrictPromotionPolicy
from .state import CorrectionState, InvalidTransition, can_transition, require_transition
from .validation import TestKind, ValidationReport

__all__ = [
    "CorrectionRevision",
    "CorrectionState",
    "InMemoryLedger",
    "InvalidTransition",
    "PolicyDecision",
    "PromotionContext",
    "PromotionPolicy",
    "PromotionRejectedError",
    "QualificationResult",
    "StaleQualificationError",
    "StrictPromotionPolicy",
    "TestKind",
    "TestResult",
    "ValidationReport",
    "can_transition",
    "fingerprint_incident",
    "require_transition",
    "subject_digest",
]
