"""Hostile path tests against a local, synthetic reference-file fixture."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
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


if __name__ == "__main__":
    unittest.main()
