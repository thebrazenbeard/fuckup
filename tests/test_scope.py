from fuckup_protocol.scope import is_selector_scope, selector_within_scope


def test_selector_scope_accepts_flat_json_scalars():
    assert is_selector_scope({"agent": "demo", "priority": 2, "enabled": True, "ratio": 0.5})


def test_selector_scope_rejects_nested_or_non_finite_values():
    assert not is_selector_scope({})
    assert not is_selector_scope({"agent": {"name": "demo"}})
    assert not is_selector_scope({"agents": ["demo"]})
    assert not is_selector_scope({"ratio": float("nan")})


def test_selector_can_only_add_constraints_to_approved_scope():
    approved = {"agent": "demo"}
    assert selector_within_scope({"agent": "demo"}, approved)
    assert selector_within_scope({"agent": "demo", "model": "x"}, approved)
    assert not selector_within_scope({"agent": "other"}, approved)
    assert not selector_within_scope({"model": "x"}, approved)
