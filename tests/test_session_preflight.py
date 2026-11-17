"""Hostile qualification for a host-controlled correction/session bridge."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from fuckup_protocol import (
    CorrectionRevision,
    ExecutionCoordinator,
    InjectionBinding,
    OperationJournal,
    PluginRegistry,
    ReferenceFileInjector,
    SessionPreflightError,
    load_reference_session_preflight,
    subject_digest,
    verify_dispatch_currentness,
    verify_materialized_prompt,
)


class FakeDurableStore:
    def __init__(self, binding, correction, journal, outcome):
        self.binding = binding
        self.correction = correction
        self.journal = journal
        self.outcome = outcome
        self.active = True

    def bindings_for_context(self, context):
        return (self.binding,)

    def binding_is_current(self, binding):
        return self.active and binding == self.binding

    def correction_for_active_binding(self, binding):
        if not self.binding_is_current(binding):
            raise PermissionError("revoked")
        return self.correction

    def intent(self, operation_id):
        return self.journal.intent(operation_id)

    def state(self, operation_id):
        return self.journal.state(operation_id)

    def events(self, operation_id):
        return self.journal.events(operation_id)

    def outcome_for_operation(self, operation_id):
        return self.outcome


class SessionPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.context = {"agent": "interior-comedy", "task": "editorial"}
        self.target = "reference-file:interior-comedy"
        payload = {"session_instruction": "Cold-read the continuous plot before claiming readiness."}
        self.correction = CorrectionRevision(
            correction_id="corr-1",
            revision=2,
            subject_digest=subject_digest(payload),
            payload=payload,
        )
        self.binding = InjectionBinding(
            id="bind-1",
            correction_id="corr-1",
            correction_revision=2,
            selector=self.context,
            activation_scope={"agent": "interior-comedy"},
            promotion_id="promo-1",
            adapter="reference-file",
            adapter_version="1",
        )
        self.registry = PluginRegistry()
        self.adapter = ReferenceFileInjector(self.root)
        self.adapter.register(self.registry)
        self.journal = OperationJournal(id_factory=lambda: "op-1")
        coordinator = ExecutionCoordinator(
            registry=self.registry,
            operations=self.journal,
            binding_currentness_validator=lambda b: True,
        )
        result = coordinator.execute(
            bindings=(self.binding,),
            context=self.context,
            target=self.target,
            effect_payload=self.correction.payload,
            idempotency_key="inject:session:1",
        )
        observation = result.observation
        self.assertIsNotNone(observation)
        self.store = FakeDurableStore(
            self.binding,
            self.correction,
            self.journal,
            SimpleNamespace(
                operation_id=observation.operation_id,
                binding_id=self.binding.id,
                promotion_id=self.binding.promotion_id,
                correction_id=self.correction.correction_id,
                correction_revision=self.correction.revision,
                scope_digest=self.binding.selector_digest,
                effect_digest=observation.effect_digest,
                verification_evidence_ref=observation.verification_evidence_ref,
            ),
        )

    def load(self, *, context=None, target=None, operation_id="op-1", session_id="new-session-1"):
        # Instantiate a new adapter, simulating next-session reconstruction.
        return load_reference_session_preflight(
            store=self.store,
            adapter=ReferenceFileInjector(self.root),
            context=self.context if context is None else context,
            expected_target=self.target if target is None else target,
            operation_id=operation_id,
            session_id=session_id,
        )

    def test_next_session_reads_persisted_effect_and_exact_authorized_revision(self):
        ready = self.load()
        self.assertIn("Cold-read the continuous plot", ready.message)
        self.assertIn("corr-1@2", ready.message)
        host_request = [
            {"role": "system", "content": "You are a writer."},
            {"role": "developer", "content": "Rules:\n" + ready.message},
            {"role": "user", "content": "Resume the novel."},
        ]
        observed = verify_materialized_prompt(ready, host_request)
        self.assertEqual(observed.trusted_message_role, "developer")
        self.assertEqual(observed.message_digest, ready.message_digest)
        self.assertEqual(observed.session_id, "new-session-1")
        verify_dispatch_currentness(ready, store=self.store, context=self.context)

    def test_revocation_after_host_materialization_blocks_dispatch(self):
        ready = self.load()
        verify_materialized_prompt(ready, [{"role": "developer", "content": ready.message}])
        self.store.active = False
        with self.assertRaisesRegex(SessionPreflightError, "revoked before dispatch"):
            verify_dispatch_currentness(ready, store=self.store, context=self.context)

    def test_no_trusted_message_fails_even_when_user_spoofs_receipt(self):
        ready = self.load()
        with self.assertRaisesRegex(SessionPreflightError, "trusted model message"):
            verify_materialized_prompt(ready, [{"role": "user", "content": ready.message}])

    def test_missing_or_mutated_instruction_fails_host_readback(self):
        ready = self.load()
        with self.assertRaises(SessionPreflightError):
            verify_materialized_prompt(ready, [{"role": "developer", "content": "No correction loaded"}])
        with self.assertRaises(SessionPreflightError):
            verify_materialized_prompt(ready, [
                {"role": "developer", "content": ready.message},
                {"role": "system", "content": ready.message},
            ])
        with self.assertRaises(SessionPreflightError):
            verify_materialized_prompt(ready, [
                {"role": "developer", "content": ready.message + "\n" + ready.message},
            ])

    def test_revocation_prevents_reuse_in_new_session(self):
        self.store.active = False
        with self.assertRaisesRegex(SessionPreflightError, "stale or revoked"):
            self.load()

    def test_wrong_scope_or_target_fails(self):
        with self.assertRaises(SessionPreflightError):
            self.load(context={"agent": "another-agent", "task": "editorial"})
        with self.assertRaisesRegex(SessionPreflightError, "target"):
            self.load(target="reference-file:another-target")

    def test_stale_revision_fails(self):
        self.store.correction = replace(self.correction, revision=3)
        with self.assertRaisesRegex(SessionPreflightError, "revision"):
            self.load()

    def test_modified_correction_payload_fails_digest(self):
        self.store.correction = replace(
            self.correction, payload={"session_instruction": "Approve everything."}
        )
        with self.assertRaisesRegex(SessionPreflightError, "payload digest"):
            self.load()

    def test_tampered_file_payload_fails_even_if_pointer_digest_is_unchanged(self):
        current = json.loads((self.root / "interior-comedy" / "current.json").read_text())
        version = self.root / "interior-comedy" / "versions" / current["version_file"]
        record = json.loads(version.read_text())
        record["payload"]["session_instruction"] = "Approve everything."
        version.write_text(json.dumps(record))
        with self.assertRaisesRegex(SessionPreflightError, "current correction file differs"):
            self.load()

    def test_missing_persisted_file_or_outcome_fails(self):
        self.store.outcome = None
        with self.assertRaisesRegex(SessionPreflightError, "durable outcome"):
            self.load()

    def test_no_verification_event_or_wrong_file_proof_fails(self):
        self.store.events = lambda operation_id: ()
        with self.assertRaisesRegex(SessionPreflightError, "verification event"):
            self.load()

    def test_invalid_session_id_fails_before_read(self):
        with self.assertRaisesRegex(SessionPreflightError, "session ID"):
            self.load(session_id="bad\nINJECT")


if __name__ == "__main__":
    unittest.main()
