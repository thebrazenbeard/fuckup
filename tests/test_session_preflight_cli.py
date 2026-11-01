"""CLI must fail closed before attempting a database connection."""

import os
import unittest
from unittest.mock import patch

from fuckup_protocol.session_preflight_cli import _context, main


class SessionPreflightCliTests(unittest.TestCase):
    def test_context_rejects_duplicate_or_malformed_selectors(self):
        for values in ([], ["missing"], ["=blank"], ["agent=ok", "agent=other"]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                _context(values)

    def test_unconfigured_cli_fails_closed(self):
        args = [
            "--reference-root", "/not-used",
            "--target", "reference-file:demo",
            "--operation-id", "no-op",
            "--session-id", "session-one",
            "--context", "agent=demo",
        ]
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(main(args), 2)


if __name__ == "__main__":
    unittest.main()
