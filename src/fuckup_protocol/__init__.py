"""Executable core for the F.U.C.K.U.P. corrective-learning protocol."""

from .fingerprint import fingerprint_incident
from .jobs import InvalidJobTransition, JobState, JobStatus, claim, fail, recover_expired_lease, succeed
from .ledger import InMemoryLedger, PromotionRejectedError, StaleQualificationError, subject_digest
from .models import CorrectionRevision, PolicyDecision, QualificationResult, TestResult
from .plugins import DuplicateHandlerError, HandlerFamily, HandlerSpec, PluginRegistry, SideEffectClass, UnknownHandlerError
from .policy import PromotionContext, PromotionPolicy, StrictPromotionPolicy
from .state import CorrectionState, InvalidTransition, can_transition, require_transition
from .validation import TestKind, ValidationReport

__all__ = [
    "CorrectionRevision",
    "CorrectionState",
    "DuplicateHandlerError",
    "HandlerFamily",
    "HandlerSpec",
    "InMemoryLedger",
    "InvalidJobTransition",
    "InvalidTransition",
    "JobState",
    "JobStatus",
    "PluginRegistry",
    "PolicyDecision",
    "PromotionContext",
    "PromotionPolicy",
    "PromotionRejectedError",
    "QualificationResult",
    "SideEffectClass",
    "StaleQualificationError",
    "StrictPromotionPolicy",
    "TestKind",
    "TestResult",
    "UnknownHandlerError",
    "ValidationReport",
    "can_transition",
    "claim",
    "fail",
    "fingerprint_incident",
    "recover_expired_lease",
    "require_transition",
    "subject_digest",
    "succeed",
]
