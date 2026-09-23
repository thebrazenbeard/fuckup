import pytest

from fuckup_protocol.models import CorrectionRevision


def test_correction_payload_is_deeply_immutable_after_construction():
    source = {"rule": {"steps": ["a", "b"]}}
    correction = CorrectionRevision("corr-1", 1, "sha256:abc", source)

    source["rule"]["steps"].append("c")
    assert correction.payload["rule"]["steps"] == ("a", "b")

    with pytest.raises(TypeError):
        correction.payload["new"] = "value"


def test_nested_mapping_is_immutable():
    correction = CorrectionRevision("corr-1", 1, "sha256:abc", {"nested": {"x": 1}})
    with pytest.raises(TypeError):
        correction.payload["nested"]["x"] = 2
