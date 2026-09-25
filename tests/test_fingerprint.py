from fuckup_protocol.fingerprint import fingerprint_incident


def test_key_order_does_not_change_fingerprint():
    assert fingerprint_incident({"b": 2, "a": 1}) == fingerprint_incident({"a": 1, "b": 2})


def test_default_volatile_fields_do_not_change_fingerprint():
    left = {"error": "boom", "request_id": "one", "trace_id": "trace-a"}
    right = {"error": "boom", "request_id": "two", "trace_id": "trace-b"}
    assert fingerprint_incident(left) == fingerprint_incident(right)


def test_semantic_change_changes_fingerprint():
    assert fingerprint_incident({"error": "boom"}) != fingerprint_incident({"error": "bang"})
