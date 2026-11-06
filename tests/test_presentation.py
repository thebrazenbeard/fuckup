"""Regressions for display-only renaming; no database or host I/O."""

import unittest

from fuckup_protocol.presentation import (
    DISPLAY_EXPANSION, PAIRS, PRESENTATION_SCHEMA, STAGES,
    schema_key_for_display_word, stage_for_schema_key, stages_for_pair,
)


class PresentationTests(unittest.TestCase):
    def test_exact_three_paired_expansion(self):
        self.assertEqual(DISPLAY_EXPANSION,
                         "Find Unknowns, Calibrate Knowledge, Update Protocols")
        self.assertEqual(PAIRS, ("Find Unknowns", "Calibrate Knowledge",
                                 "Update Protocols"))
        self.assertEqual(PRESENTATION_SCHEMA, "FUCKUP_STAGE_PRESENTATION_V1")
        self.assertEqual(tuple(s.display_word for s in STAGES),
                         ("Find", "Unknowns", "Calibrate", "Knowledge",
                          "Update", "Protocols"))

    def test_legacy_fields_remain_exactly_unchanged(self):
        self.assertEqual(tuple(s.schema_key for s in STAGES),
                         ("flag", "understand", "calibrate", "know",
                          "unlearn", "prevent"))
        self.assertEqual(tuple(s.legacy_word for s in STAGES),
                         ("Flag", "Understand", "Calibrate", "Know",
                          "Unlearn", "Prevent"))

    def test_mapping_is_exact_bijective_and_pair_bounded(self):
        for stage in STAGES:
            self.assertEqual(stage_for_schema_key(stage.schema_key), stage)
            self.assertEqual(schema_key_for_display_word(stage.display_word),
                             stage.schema_key)
        for index, phrase in enumerate(PAIRS, start=1):
            pair = stages_for_pair(index)
            self.assertEqual(len(pair), 2)
            self.assertEqual(" ".join(s.display_word for s in pair), phrase)
            self.assertEqual(tuple(s.index for s in pair),
                             (index * 2 - 1, index * 2))

    def test_no_aliasing_into_persisted_keys(self):
        for invalid in ("find", "unknowns", "protocols", "Know", "Find "):
            with self.assertRaises(KeyError):
                stage_for_schema_key(invalid)
        for invalid in ("Flag", "Understand", "Unlearn", "Prevent", "FIND"):
            with self.assertRaises(KeyError):
                schema_key_for_display_word(invalid)
        for invalid in (0, 4, 1.0, True, "1"):
            with self.assertRaises(ValueError):
                stages_for_pair(invalid)

    def test_stage_metadata_is_immutable(self):
        with self.assertRaises((AttributeError, TypeError)):
            STAGES[0].schema_key = "find"


if __name__ == "__main__":
    unittest.main()
