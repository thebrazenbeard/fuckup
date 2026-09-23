"""Executable core for the F.U.C.K.U.P. corrective-learning protocol."""

from .ambiguity import (
    AmbiguityAssessment,
    AmbiguityRoute,
    CausalHypothesis,
    assess_ambiguity,
    route_ambiguity,
)
from .authorization import PromotionAuthorization, authorize_promotion
from .bindings import BindingConflictError, InjectionBinding, resolve_binding
from .effectiveness import (
    EffectivenessState,
    EffectivenessSummary,
    ObservationPhase,
    OutcomeObservation,
    summarize_effectiveness,
)
from .events import FuckupEvent, lifecycle_event_type
from .experiment import (
    ExperimentCondition,
    ExperimentOutcome,
    FeedbackCondition,
    LabelCondition,
    ProtocolNameCondition,
    SerializationCondition,
    factorial_conditions,
)
from .fingerprint import fingerprint_incident
from .jobs import (
    InvalidJobTransition,
    JobState,
    JobStatus,
    claim,
    fail,
    recover_expired_lease,
    succeed,
)
from .ledger import (
    IdempotencyCollisionError,
    InMemoryLedger,
    PromotionRejectedError,
    StaleQualificationError,
    effect_digest,
    subject_digest,
)
from .models import CorrectionRevision, PolicyDecision, QualificationResult, TestResult
from .plugins import (
    DuplicateHandlerError,
    HandlerFamily,
    HandlerSpec,
    PluginRegistry,
    SideEffectClass,
    UnknownHandlerError,
)
from .policy import PromotionContext, PromotionPolicy, StrictPromotionPolicy
from .provenance import ProvenanceKind, ProvenanceRef
from .state import CorrectionState, InvalidTransition, can_transition, require_transition
from .validation import TestKind, ValidationReport

__all__ = [
    "AmbiguityAssessment",
    "AmbiguityRoute",
    "BindingConflictError",
    "CausalHypothesis",
    "CorrectionRevision",
    "CorrectionState",
    "DuplicateHandlerError",
    "EffectivenessState",
    "EffectivenessSummary",
    "ExperimentCondition",
    "ExperimentOutcome",
    "FeedbackCondition",
    "FuckupEvent",
    "HandlerFamily",
    "HandlerSpec",
    "IdempotencyCollisionError",
    "InMemoryLedger",
    "InjectionBinding",
    "InvalidJobTransition",
    "InvalidTransition",
    "JobState",
    "JobStatus",
    "LabelCondition",
    "ObservationPhase",
    "OutcomeObservation",
    "PluginRegistry",
    "PolicyDecision",
    "PromotionAuthorization",
    "PromotionContext",
    "PromotionPolicy",
    "PromotionRejectedError",
    "ProtocolNameCondition",
    "ProvenanceKind",
    "ProvenanceRef",
    "QualificationResult",
    "SerializationCondition",
    "SideEffectClass",
    "StaleQualificationError",
    "StrictPromotionPolicy",
    "TestKind",
    "TestResult",
    "UnknownHandlerError",
    "ValidationReport",
    "assess_ambiguity",
    "authorize_promotion",
    "can_transition",
    "claim",
    "effect_digest",
    "factorial_conditions",
    "fail",
    "fingerprint_incident",
    "lifecycle_event_type",
    "recover_expired_lease",
    "require_transition",
    "resolve_binding",
    "route_ambiguity",
    "subject_digest",
    "succeed",
    "summarize_effectiveness",
]
