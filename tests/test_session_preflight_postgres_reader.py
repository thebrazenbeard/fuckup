"""SQL reader binds correction material to an exact active promotion."""

import unittest

from fuckup_protocol import InjectionBinding, PostgresExecutionStore


class QueryConnection:
    def __init__(self, row):
        self.row = row
        self.sql = ""
        self.params = ()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        self.sql = sql
        self.params = params
        return self

    def fetchone(self):
        return self.row


class PostgresCorrectionReaderTests(unittest.TestCase):
    def setUp(self):
        self.binding = InjectionBinding(
            "bind-1", "corr-1", 2,
            {"agent": "demo"}, {"agent": "demo"},
            promotion_id="promo-1", adapter="reference-file", adapter_version="1",
        )

    def test_selects_only_exact_active_binding_revision(self):
        conn = QueryConnection(("sha256:abc", {"session_instruction": "Read the story"}, True))
        store = PostgresExecutionStore(lambda: conn)
        revision = store.correction_for_active_binding(self.binding)
        self.assertEqual(revision.correction_id, "corr-1")
        self.assertEqual(revision.revision, 2)
        self.assertEqual(revision.payload["session_instruction"], "Read the story")
        for fragment in (
            "active_injection_bindings", "JOIN correction_revisions",
            "ab.exact_subject_digest", "ab.selector_digest", "ab.adapter_version",
        ):
            self.assertIn(fragment, conn.sql)
        self.assertEqual(conn.params, (
            "bind-1", "promo-1", "corr-1", 2,
            self.binding.selector_digest, "reference-file", "1",
        ))

    def test_missing_or_revoked_binding_blocks(self):
        conn = QueryConnection(None)
        store = PostgresExecutionStore(lambda: conn)
        with self.assertRaises(PermissionError):
            store.correction_for_active_binding(self.binding)


if __name__ == "__main__":
    unittest.main()
