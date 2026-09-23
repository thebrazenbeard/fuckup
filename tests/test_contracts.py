import pytest

from fuckup_protocol.contracts import freeze_json_object, is_nonempty_json_object, thaw_json


def test_freeze_json_object_is_deeply_immutable_snapshot():
    source = {"action": "revoke", "conditions": ["regression"], "meta": {"severity": 2}}
    frozen = freeze_json_object(source, require_nonempty=True)
    source["conditions"].append("security")
    source["meta"]["severity"] = 9

    assert tuple(frozen["conditions"]) == ("regression",)
    assert frozen["meta"]["severity"] == 2
    assert thaw_json(frozen) == {
        "action": "revoke",
        "conditions": ["regression"],
        "meta": {"severity": 2},
    }


def test_json_object_contract_rejects_nonfinite_and_nonjson_values():
    assert not is_nonempty_json_object({})
    assert not is_nonempty_json_object({"ratio": float("nan")})
    assert not is_nonempty_json_object({"value": object()})

    with pytest.raises(ValueError):
        freeze_json_object({"ratio": float("inf")}, require_nonempty=True)
