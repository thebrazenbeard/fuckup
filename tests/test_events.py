from datetime import datetime, timezone
import json
import math
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from fuckup_protocol.events import FuckupEvent, lifecycle_event_type
from fuckup_protocol.provenance import ProvenanceKind, ProvenanceRef


def test_lifecycle_event_type_is_namespaced():
    assert lifecycle_event_type("validation_passed") == "org.fuckup.validation.passed"


def test_event_serializes_cloudevents_core_and_provenance():
    event = FuckupEvent(
        id="evt-1",
        source="agent://demo",
        type="org.fuckup.failure.flagged",
        subject="record/rec-1",
        data={"record_id": "rec-1"},
        provenance=(
            ProvenanceRef(
                kind=ProvenanceKind.TRACE,
                ref="trace-123",
                digest="sha256:abc",
                source="otel",
            ),
        ),
        traceparent="00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01",
    )
    payload = event.to_cloudevent()
    assert payload["specversion"] == "1.0"
    assert payload["source"] == "agent://demo"
    assert payload["data"]["record_id"] == "rec-1"
    assert payload["fuckupprovenance"][0]["ref"] == "trace-123"
    assert payload["traceparent"].startswith("00-")


def test_non_fuckup_event_type_is_rejected():
    try:
        FuckupEvent(
            id="evt-1",
            source="agent://demo",
            type="com.example.other",
            subject="record/rec-1",
            data={},
        )
    except ValueError as exc:
        assert "org.fuckup" in str(exc)
    else:
        raise AssertionError("expected ValueError")


@pytest.mark.parametrize(
    "bad_fields, match",
    [
        ({"datacontenttype": "text/plain"}, "application/json"),
        ({"time": datetime(2026, 10, 23, 12, 0)}, "timezone-aware"),
        ({"data": ["not an object"]}, "JSON object"),
        ({"data": {"result": {1, 2}}}, "JSON serializable"),
        ({"data": {"rate": math.nan}}, "JSON serializable"),
        ({"data": {1: "non-string key"}}, "string keys"),
        ({"data": {"nested": [{"1": "safe", 1: "collision"}]}}, "string keys"),
        ({"traceparent": 42}, "traceparent"),
        ({"provenance": (ProvenanceRef(kind="UNTRUSTED", ref="claim"),)}, "provenance"),
        ({"provenance": (ProvenanceRef(kind=ProvenanceKind.TRACE, ref=42),)}, "provenance ref"),
        ({"provenance": (ProvenanceRef(kind=ProvenanceKind.TRACE, ref="trace-1", source=42),)}, "provenance optional"),
    ],
)
def test_transport_invalid_events_are_rejected_at_creation(bad_fields, match):
    payload = dict(
        id="evt-1",
        source="agent://unit-test",
        type="org.fuckup.failure.flagged",
        subject="record/1",
        data={"ok": True},
        time=datetime(2026, 10, 23, tzinfo=timezone.utc),
    )
    payload.update(bad_fields)
    with pytest.raises(ValueError, match=match):
        FuckupEvent(**payload)


def test_export_is_json_serializable_and_detached_from_nested_input():
    original_data = {"sequence": ["first"]}
    event = FuckupEvent(
        id="evt-1",
        source="agent://unit-test",
        type="org.fuckup.failure.flagged",
        subject="record/1",
        data=original_data,
        time=datetime(2026, 10, 23, tzinfo=timezone.utc),
    )
    export = event.to_cloudevent()
    json.dumps(export, allow_nan=False)
    export["data"]["sequence"].append("external mutation")
    assert original_data["sequence"] == ["first"]


def test_input_mutated_after_creation_cannot_silently_coerce_nested_keys():
    source = {"nested": {"1": "first"}}
    event = FuckupEvent(
        id="evt-later-mutation",
        source="agent://unit-test",
        type="org.fuckup.failure.flagged",
        subject="record/1",
        data=source,
    )
    source["nested"][1] = "collision"
    with pytest.raises(ValueError, match="string keys"):
        event.to_cloudevent()


def test_mutating_supplied_provenance_list_does_not_change_export():
    refs = [ProvenanceRef(kind=ProvenanceKind.TRACE, ref="trace-1")]
    event = FuckupEvent(
        id="evt-immutable-provenance",
        source="agent://unit-test",
        type="org.fuckup.failure.flagged",
        subject="record/1",
        data={},
        provenance=refs,
    )
    refs.append(ProvenanceRef(kind=ProvenanceKind.EVENT, ref="event-2"))
    assert len(event.to_cloudevent()["fuckupprovenance"]) == 1


def test_circular_data_is_rejected_without_recursive_key_scan_hanging():
    cyclic_data = {"events": []}
    cyclic_data["events"].append(cyclic_data)
    with pytest.raises(ValueError, match="JSON serializable"):
        FuckupEvent(
            id="evt-cycle",
            source="agent://unit-test",
            type="org.fuckup.failure.flagged",
            subject="record/1",
            data=cyclic_data,
        )


def test_normal_nested_json_payload_and_provenance_remain_supported():
    event = FuckupEvent(
        id="evt-nested",
        source="agent://unit-test",
        type="org.fuckup.learning.promoted",
        subject="correction/1",
        data={"revision": 1, "evidence": [{"ref": "trace-1"}]},
        provenance=(ProvenanceRef(kind=ProvenanceKind.TRACE, ref="trace-1"),),
    )
    payload = json.loads(json.dumps(event.to_cloudevent()))
    assert payload["data"]["evidence"][0]["ref"] == "trace-1"
    schema = json.loads((Path(__file__).parents[1] / "schema" / "fuckup-event.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
    assert payload["time"].endswith("+00:00")


@pytest.mark.parametrize("action", ["", "validation passed", "..", "failure/flagged", "x..y", "org.fuckup.failure.flagged"])
def test_malformed_or_double_namespaced_actions_rejected(action):
    with pytest.raises(ValueError):
        lifecycle_event_type(action)
