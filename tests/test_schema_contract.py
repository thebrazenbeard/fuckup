import json
from pathlib import Path

from jsonschema import Draft202012Validator


def _schema():
    return json.loads(Path("schema/fuckup-record.schema.json").read_text())


def _minimal_record():
    return {
        "protocol": "FUCKUP",
        "version": "0.1.0",
        "record_id": "rec-1",
        "state": "DETECTED",
        "subject": {"kind": "agent", "id": "agent-1", "version": None},
        "trigger": {},
        "flag": {},
        "understand": {},
        "calibrate": {},
        "know": {},
        "unlearn": {
            "target": {"layer": "memory", "identifier": "rule-1"},
            "replacement": {"rule": "replacement"},
            "rollback": {"action": "revoke"},
        },
        "prevent": {},
        "validation": {},
        "provenance": {},
    }


def test_runtime_schema_is_valid_draft_2020_12():
    Draft202012Validator.check_schema(_schema())


def test_minimal_runtime_record_validates():
    Draft202012Validator(_schema()).validate(_minimal_record())
