"""Hostile path tests against a local, synthetic reference-file fixture."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest

from fuckup_protocol.reference_adapter import ReferenceFileInjector
from fuckup_protocol.execution import ReadbackDisposition


class ReferencePathSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "inside" / "root"
        self.root.mkdir(parents=True)
        self.outside = self.base / "outside"
        self.outside.mkdir()
        self.adapter = ReferenceFileInjector(self.root)

    @staticmethod
    def request(target="reference-file:demo", operation_id="op1"):
        return {"target": target, "operation_id": operation_id,
                "effect_digest": "sha256:abc", "effect_payload": {"canary": "SAFE_SYNTHETIC"}}

    def link(self, source, destination):
        try:
            source.symlink_to(destination, target_is_directory=destination.is_dir())
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink unavailable: {exc}")

    def test_dotdot_target_rejected_before_external_write(self):
        with self.assertRaises(ValueError):
            self.adapter.execute(self.request("reference-file:.."))
        self.assertFalse((self.root.parent / "versions").exists())
        self.assertFalse((self.root.parent / "operations").exists())

    def test_dot_target_rejected_before_root_write(self):
        with self.assertRaises(ValueError):
            self.adapter.execute(self.request("reference-file:."))
        self.assertFalse((self.root / "current.json").exists())

    def test_symlink_target_dir_rejected(self):
        self.link(self.root / "demo", self.outside)
        with self.assertRaises(ValueError):
            self.adapter.execute(self.request())
        self.assertFalse((self.outside / "versions").exists())

    def test_symlink_versions_dir_rejected(self):
        target = self.root / "demo"
        target.mkdir()
        self.link(target / "versions", self.outside)
        with self.assertRaises(ValueError):
            self.adapter.execute(self.request())
        self.assertEqual(list(self.outside.iterdir()), [])

    def test_readback_rejects_symlink_current_path(self):
        target = self.root / "demo"
        target.mkdir()
        outside_current = self.outside / "current.json"
        outside_current.write_text(json.dumps({"target": "reference-file:demo", "effect_digest": "sha256:abc"}))
        self.link(target / "current.json", outside_current)
        with self.assertRaises(ValueError):
            self.adapter.readback(self.request(), None)

    def test_readback_rejects_tampered_version_pointer_traversal(self):
        target = self.root / "demo"
        target.mkdir()
        (target / "current.json").write_text(json.dumps({
            "target": "reference-file:demo", "operation_id": "op1",
            "effect_digest": "sha256:abc", "version_file": "../../private.json"
        }))
        with self.assertRaises(ValueError):
            self.adapter.readback(self.request(), None)

    def test_root_symlink_rejected(self):
        link = self.base / "trusted-root-link"
        self.link(link, self.outside)
        adapter = ReferenceFileInjector(link)
        with self.assertRaises(ValueError):
            adapter.execute(self.request())
        self.assertEqual(list(self.outside.iterdir()), [])

    def test_normal_execute_readback_rollback(self):
        request = self.request()
        self.adapter.execute(request)
        self.assertEqual(self.adapter.readback(request, None).disposition, ReadbackDisposition.VERIFIED)
        result = self.adapter.rollback("reference-file:demo", "op1")
        self.assertEqual(result["rolled_back_effect_digest"], "sha256:abc")
        self.assertFalse((self.root / "demo" / "current.json").exists())

    def test_same_digest_other_operation_cannot_overwrite_immutable_version(self):
        first = self.request()
        self.adapter.execute(first)
        version = self.root / "demo" / "versions" / "sha256_abc.json"
        current = self.root / "demo" / "current.json"
        original_version = version.read_bytes()
        original_current = current.read_bytes()
        second = {**first, "operation_id": "op2", "effect_payload": {"canary": "DIFFERENT"}}
        with self.assertRaisesRegex(RuntimeError, "digest already has"):
            self.adapter.execute(second)
        self.assertEqual(version.read_bytes(), original_version)
        self.assertEqual(current.read_bytes(), original_current)
        self.assertFalse((self.root / "demo" / "operations" / "op2.json").exists())

    def test_existing_operation_same_digest_changed_payload_rejected(self):
        request = self.request()
        self.adapter.execute(request)
        changed = {**request, "effect_payload": {"canary": "DIFFERENT"}}
        with self.assertRaisesRegex(ValueError, "replay payload"):
            self.adapter.execute(changed)
        self.assertEqual(self.adapter.readback(request, None).disposition, ReadbackDisposition.VERIFIED)

    def test_mutated_version_payload_not_verified_for_original_request(self):
        request = self.request()
        self.adapter.execute(request)
        version = self.root / "demo" / "versions" / "sha256_abc.json"
        record = json.loads(version.read_text())
        record["payload"] = {"canary": "MUTATED"}
        version.write_text(json.dumps(record))
        self.assertEqual(
            self.adapter.readback(request, None).disposition,
            ReadbackDisposition.AMBIGUOUS,
        )

    def test_missing_expected_payload_never_qualifies_readback(self):
        request = self.request()
        self.adapter.execute(request)
        payload_unbound = {key: value for key, value in request.items() if key != "effect_payload"}
        report = self.adapter.readback(payload_unbound, None)
        self.assertEqual(report.disposition, ReadbackDisposition.AMBIGUOUS)

    def test_noncanonical_version_pointer_does_not_qualify_same_bytes(self):
        request = self.request()
        self.adapter.execute(request)
        target = self.root / "demo"
        current_path = target / "current.json"
        current = json.loads(current_path.read_text())
        original = target / "versions" / current["version_file"]
        (target / "versions" / "alternate-valid.json").write_bytes(original.read_bytes())
        current["version_file"] = "alternate-valid.json"
        current_path.write_text(json.dumps(current))
        report = self.adapter.readback(request, None)
        self.assertEqual(report.disposition, ReadbackDisposition.AMBIGUOUS)

    def test_concurrent_same_digest_distinct_operations_only_one_commits(self):
        reached_reservation = Barrier(2, timeout=5)

        class ContendingInjector(ReferenceFileInjector):
            def _create_immutable_json(self, path, value):
                reached_reservation.wait()
                return super()._create_immutable_json(path, value)

        first = self.request(operation_id="op1")
        second = {**self.request(operation_id="op2"), "effect_payload": {"canary": "OTHER"}}

        def attempt(request):
            try:
                return ("success", ContendingInjector(self.root).execute(request))
            except RuntimeError as error:
                return ("rejected", str(error))

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, (first, second)))

        self.assertEqual([state for state, _ in outcomes].count("success"), 1)
        self.assertEqual([state for state, _ in outcomes].count("rejected"), 1)
        target = self.root / "demo"
        current = json.loads((target / "current.json").read_text())
        version = json.loads((target / "versions" / current["version_file"]).read_text())
        self.assertEqual(version["operation_id"], current["operation_id"])
        self.assertEqual(len(list((target / "operations").glob("*.json"))), 1)
        for request in (first, second):
            expected = ReadbackDisposition.VERIFIED if request["operation_id"] == current["operation_id"] else ReadbackDisposition.FAILED
            self.assertEqual(self.adapter.readback(request, None).disposition, expected)

    def test_old_operation_cannot_claim_or_rollback_new_current_with_same_digest(self):
        request = self.request()
        self.adapter.execute(request)
        current = self.root / "demo" / "current.json"
        forged = json.loads(current.read_text())
        forged["operation_id"] = "op2"
        current.write_text(json.dumps(forged))
        self.assertEqual(self.adapter.readback(request, None).disposition, ReadbackDisposition.FAILED)
        with self.assertRaisesRegex(RuntimeError, "not current"):
            self.adapter.execute(request)
        with self.assertRaisesRegex(RuntimeError, "newer or missing"):
            self.adapter.rollback("reference-file:demo", "op1")
        self.assertTrue(current.exists())


if __name__ == "__main__":
    unittest.main()
