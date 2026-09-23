import pytest

from fuckup_protocol.bindings import BindingConflictError, InjectionBinding, resolve_binding


def test_no_match_returns_none():
    binding = InjectionBinding("b1", "c1", 1, {"model": "alpha"})
    assert resolve_binding((binding,), {"model": "beta"}) is None


def test_priority_wins_before_specificity():
    broad_high = InjectionBinding("b1", "c1", 1, {"model": "alpha"}, priority=10)
    narrow_low = InjectionBinding("b2", "c2", 1, {"model": "alpha", "task": "code"}, priority=5)
    resolved = resolve_binding((narrow_low, broad_high), {"model": "alpha", "task": "code"})
    assert resolved == broad_high


def test_narrower_scope_wins_at_equal_priority():
    broad = InjectionBinding("b1", "c1", 1, {"model": "alpha"}, priority=5)
    narrow = InjectionBinding("b2", "c2", 1, {"model": "alpha", "task": "code"}, priority=5)
    resolved = resolve_binding((broad, narrow), {"model": "alpha", "task": "code"})
    assert resolved == narrow


def test_newer_revision_wins_only_within_same_correction_family():
    old = InjectionBinding("b1", "c1", 1, {"model": "alpha"}, priority=5)
    new = InjectionBinding("b2", "c1", 2, {"model": "alpha"}, priority=5)
    assert resolve_binding((old, new), {"model": "alpha"}) == new


def test_cross_correction_tie_fails_closed_independent_of_input_order():
    left = InjectionBinding("a", "c1", 3, {"model": "alpha"}, priority=5)
    right = InjectionBinding("b", "c2", 9, {"model": "alpha"}, priority=5)
    with pytest.raises(BindingConflictError):
        resolve_binding((left, right), {"model": "alpha"})
    with pytest.raises(BindingConflictError):
        resolve_binding((right, left), {"model": "alpha"})


def test_inactive_binding_does_not_participate():
    active = InjectionBinding("a", "c1", 1, {"model": "alpha"}, priority=1)
    inactive = InjectionBinding("b", "c2", 1, {"model": "alpha"}, priority=100, active=False)
    assert resolve_binding((inactive, active), {"model": "alpha"}) == active


def test_binding_selector_is_frozen_after_construction():
    raw = {"model": "alpha"}
    binding = InjectionBinding("b1", "c1", 1, raw)
    raw["model"] = "beta"
    assert binding.matches({"model": "alpha"})
    assert not binding.matches({"model": "beta"})


def test_boolean_selector_does_not_match_numeric_context():
    binding = InjectionBinding("b1", "c1", 1, {"enabled": True})
    assert binding.matches({"enabled": True})
    assert not binding.matches({"enabled": 1})
