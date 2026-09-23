import pytest

from fuckup_protocol.state import CorrectionState, InvalidTransition, can_transition, require_transition


def test_happy_path_transitions_are_explicit():
    path = [
        CorrectionState.DETECTED,
        CorrectionState.UNDER_ANALYSIS,
        CorrectionState.ROOT_CAUSE_PROPOSED,
        CorrectionState.CORRECTION_PROPOSED,
        CorrectionState.QUALIFYING,
        CorrectionState.QUALIFIED,
        CorrectionState.PROMOTED,
        CorrectionState.ACTIVE,
        CorrectionState.SUPERSEDED,
    ]
    for current, target in zip(path, path[1:]):
        assert can_transition(current, target)


def test_ambiguous_root_cause_cannot_silently_promote():
    assert not can_transition(CorrectionState.AMBIGUOUS, CorrectionState.PROMOTED)
    with pytest.raises(InvalidTransition):
        require_transition(CorrectionState.AMBIGUOUS, CorrectionState.PROMOTED)


def test_active_can_revoke_without_erasing_history():
    assert can_transition(CorrectionState.ACTIVE, CorrectionState.REVOKED)
