import json

import pytest

from fuckup_protocol.bindings import InjectionBinding
from fuckup_protocol.execution import ExecutionCoordinator
from fuckup_protocol.operations import OperationJournal, OperationState
from fuckup_protocol.plugins import PluginRegistry
from fuckup_protocol.reference_adapter import ReferenceFileInjector


def _binding():
    return InjectionBinding(
        "bind-1",
        "corr-1",
        1,
        {"agent": "demo"},
        {"agent": "demo"},
        promotion_id="promo-1",
        adapter="reference-file",
        adapter_version="1",
    )


def test_reference_file_injector_executes_and_verifies_real_reversible_state(tmp_path):
    registry = PluginRegistry()
    adapter = ReferenceFileInjector(tmp_path)
    adapter.register(registry)
    coordinator = ExecutionCoordinator(
        registry=registry,
        operations=OperationJournal(id_factory=lambda: "op-1"),
        binding_currentness_validator=lambda binding: True,
    )

    result = coordinator.execute(
        bindings=(_binding(),),
        context={"agent": "demo"},
        target="reference-file:demo",
        effect_payload={"rule": "prefer exact evidence"},
        idempotency_key="reference:1",
    )

    assert result.operation_state == OperationState.VERIFIED
    current = json.loads((tmp_path / "demo" / "current.json").read_text())
    assert current["effect_digest"] == result.operation.effect_digest
    assert current["operation_id"] == "op-1"
    assert result.readback.observed["payload"] == {"rule": "prefer exact evidence"}


def test_reference_file_injector_rejects_path_traversal(tmp_path):
    adapter = ReferenceFileInjector(tmp_path)

    with pytest.raises(ValueError, match="target"):
        adapter.execute(
            {
                "target": "reference-file:../escape",
                "operation_id": "op-1",
                "effect_digest": "sha256:x",
                "effect_payload": {"rule": "x"},
            }
        )


def test_reference_file_injector_exact_replay_is_idempotent(tmp_path):
    adapter = ReferenceFileInjector(tmp_path)
    request = {
        "target": "reference-file:demo",
        "operation_id": "op-1",
        "effect_digest": "sha256:x",
        "effect_payload": {"rule": "x"},
    }

    first = adapter.execute(request)
    second = adapter.execute(request)

    assert first["idempotent_replay"] is False
    assert second["idempotent_replay"] is True
    assert {k: v for k, v in second.items() if k != "idempotent_replay"} == {
        k: v for k, v in first.items() if k != "idempotent_replay"
    }


def test_reference_file_injector_rollback_restores_previous_verified_state(tmp_path):
    adapter = ReferenceFileInjector(tmp_path)
    first = {
        "target": "reference-file:demo",
        "operation_id": "op-1",
        "effect_digest": "sha256:first",
        "effect_payload": {"rule": "first"},
    }
    second = {
        "target": "reference-file:demo",
        "operation_id": "op-2",
        "effect_digest": "sha256:second",
        "effect_payload": {"rule": "second"},
    }
    adapter.execute(first)
    adapter.execute(second)

    rolled_back = adapter.rollback("reference-file:demo", "op-2")

    assert rolled_back["restored_effect_digest"] == "sha256:first"
    current = json.loads((tmp_path / "demo" / "current.json").read_text())
    assert current["effect_digest"] == "sha256:first"