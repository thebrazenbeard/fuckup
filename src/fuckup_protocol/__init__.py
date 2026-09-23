"""Executable core for the F.U.C.K.U.P. corrective-learning protocol."""

from .fingerprint import fingerprint_incident
from .jobs import InvalidJobTransition, JobState, JobStatus, claim, fail, recover_expired_lease, succeed
from .ledger import IdempotencyCollisionError, InMemoryLedger, PromotionRejectedError, StaleQualificationError, effect_digest, subject_digest
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
    "IdempotencyCollisionError",
    "InMemoryLedger",
    "InvalidJobTransition",
    "InvalidTransition",
    "JobState",
    "JobStatus",
    "PluginRegistry",
    "PolicyDecision",
    "PromotionAuthorization",
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
