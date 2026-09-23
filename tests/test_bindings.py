import pytest

from fuckup_protocol.bindings import (
    BindingConflictError,
    InjectionBinding,
    resolve_binding,
    selector_within_scope,
)


def _binding(binding_id, correction_id, revision, selector, *, scope=None, priority=0, active=True):
    return InjectionBinding(
        binding_id,
        correction_id,
        revision,
        selector,
        scope or {"model": "alpha"},
        priority=priority,
        active=active,
    )


def test_no_match_returns_none():
    binding = _binding("b1", "c1", 1, {"model": "alpha"})
    assert resolve_binding((binding,), {"model": "beta"}) is None


def test_priority_wins_before_specificity():
    broad_high = _binding("b1", "c1", 1, {"model": "alpha"}, priority=10)
    narrow_low = _binding("b2", "c2", 1, {"model": "alpha", "task": "code"}, priority=5)
    resolved = resolve_binding((narrow_low, broad_high), {"model": "alpha", "task": "code"})
    assert resolved == broad_high


def test_narrower_scope_wins_at_equal_priority():
    broad = _binding("b1", "c1", 1, {"model": "alpha"}, priority=5)
    narrow = _binding("b2", "c2", 1, {"model": "alpha", "task": "code"}, priority=5)
    resolved = resolve_binding((broad, narrow), {"model": "alpha", "task": "code"})
    assert resolved == narrow


def test_newer_revision_wins_only_within_same_correction_family():
    old = _binding("b1", "c1", 1, {"model": "alpha"}, priority=5)
    new = _binding("b2", "c1", 2, {"model": "alpha"}, priority=5)
    assert resolve_binding((old, new), {"model": "alpha"}) == new


def test_cross_correction_tie_fails_closed_independent_of_input_order():
    left = _binding("a", "c1", 3, {"model": "alpha"}, priority=5)
    right = _binding("b", "c2", 9, {"model": "alpha"}, priority=5)
    with pytest.raises(BindingConflictError):
        resolve_binding((left, right), {"model": "alpha"})
    with pytest.raises(BindingConflictError):
        resolve_binding((right, left), {"model": "alpha"})


def test_inactive_binding_does_not_participate():
    active = _binding("a", "c1", 1, {"model": "alpha"}, priority=1)
    inactive = _binding("b", "c2", 1, {"model": "alpha"}, priority=100, active=False)
    assert resolve_binding((inactive, active), {"model": "alpha"}) == active


def test_binding_selector_must_be_equal_to_or_narrower_than_activation_scope():
    assert selector_within_scope({"agent": "demo", "task": "code"}, {"agent": "demo"})
    with pytest.raises(ValueError):
        InjectionBinding("b1", "c1", 1, {"model": "alpha"}, {"agent": "demo"})


def test_binding_scope_and_selector_are_immutable_snapshots():
    selector = {"agent": "demo", "task": "code"}
    scope = {"agent": "demo"}
    binding = InjectionBinding("b1", "c1", 1, selector, scope)
    selector["task"] = "other"
    scope["agent"] = "other"
    assert dict(binding.selector) == {"agent": "demo", "task": "code"}
    assert dict(binding.activation_scope) == {"agent": "demo"}
