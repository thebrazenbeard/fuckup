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
