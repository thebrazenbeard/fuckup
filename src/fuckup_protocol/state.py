from __future__ import annotations

from enum import StrEnum


class CorrectionState(StrEnum):
    DETECTED = "DETECTED"
    UNDER_ANALYSIS = "UNDER_ANALYSIS"
    AMBIGUOUS = "AMBIGUOUS"
    ROOT_CAUSE_PROPOSED = "ROOT_CAUSE_PROPOSED"
    CORRECTION_PROPOSED = "CORRECTION_PROPOSED"
    QUALIFYING = "QUALIFYING"
    QUALIFIED = "QUALIFIED"
    REJECTED = "REJECTED"
    BLOCKED_POLICY = "BLOCKED_POLICY"
    PROMOTED = "PROMOTED"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"
    DUPLICATE = "DUPLICATE"
    DEAD_LETTERED = "DEAD_LETTERED"
    STALE_QUALIFICATION = "STALE_QUALIFICATION"


_ALLOWED: dict[CorrectionState, frozenset[CorrectionState]] = {
    CorrectionState.DETECTED: frozenset({
        CorrectionState.UNDER_ANALYSIS,
        CorrectionState.DUPLICATE,
        CorrectionState.DEAD_LETTERED,
    }),
    CorrectionState.UNDER_ANALYSIS: frozenset({
        CorrectionState.AMBIGUOUS,
        CorrectionState.ROOT_CAUSE_PROPOSED,
        CorrectionState.DEAD_LETTERED,
    }),
    CorrectionState.AMBIGUOUS: frozenset({
        CorrectionState.UNDER_ANALYSIS,
        CorrectionState.REJECTED,
        CorrectionState.DEAD_LETTERED,
    }),
    CorrectionState.ROOT_CAUSE_PROPOSED: frozenset({
        CorrectionState.CORRECTION_PROPOSED,
        CorrectionState.AMBIGUOUS,
        CorrectionState.REJECTED,
    }),
    CorrectionState.CORRECTION_PROPOSED: frozenset({
        CorrectionState.QUALIFYING,
        CorrectionState.REJECTED,
    }),
    CorrectionState.QUALIFYING: frozenset({
        CorrectionState.QUALIFIED,
        CorrectionState.REJECTED,
        CorrectionState.STALE_QUALIFICATION,
        CorrectionState.DEAD_LETTERED,
    }),
    CorrectionState.STALE_QUALIFICATION: frozenset({
        CorrectionState.QUALIFYING,
        CorrectionState.REJECTED,
    }),
    CorrectionState.QUALIFIED: frozenset({
        CorrectionState.PROMOTED,
        CorrectionState.BLOCKED_POLICY,
        CorrectionState.STALE_QUALIFICATION,
        CorrectionState.REJECTED,
    }),
    CorrectionState.BLOCKED_POLICY: frozenset({
        CorrectionState.QUALIFIED,
        CorrectionState.REJECTED,
    }),
    CorrectionState.PROMOTED: frozenset({
        CorrectionState.ACTIVE,
        CorrectionState.REVOKED,
    }),
    CorrectionState.ACTIVE: frozenset({
        CorrectionState.SUPERSEDED,
        CorrectionState.REVOKED,
    }),
    CorrectionState.REJECTED: frozenset(),
    CorrectionState.SUPERSEDED: frozenset(),
    CorrectionState.REVOKED: frozenset(),
    CorrectionState.DUPLICATE: frozenset(),
    CorrectionState.DEAD_LETTERED: frozenset(),
}


class InvalidTransition(ValueError):
    pass


def can_transition(current: CorrectionState, target: CorrectionState) -> bool:
    return target in _ALLOWED[current]


def require_transition(current: CorrectionState, target: CorrectionState) -> None:
    if not can_transition(current, target):
        raise InvalidTransition(f"invalid correction transition: {current} -> {target}")
