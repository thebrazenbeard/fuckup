"""Hostile regressions for combined display mapping and Know evidence gate.

This source-only test does not authenticate external evidence or promotion.
"""

import unittest

from fuckup_protocol.presentation import schema_key_for_display_word
from fuckup_protocol.know_gate import (
    ClaimKind, ClaimProposal, EvidenceKind, EvidenceRef, GateState,
    assess_know_claim,
)


class PresentationKnowIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.subject = "sha256:synthetic-exact-subject"
        self.support = EvidenceRef("support-test-001", self.subject, EvidenceKind.TEST)
        self.falsification = EvidenceRef("falsification-test-002", self.subject,
                                         EvidenceKind.TEST)

    def test_knowledge_label_never_promotes_review_ready_to_known(self):
        self.assertEqual(schema_key_for_display_word("Knowledge"), "know")
        claim = ClaimProposal(
            subject_digest=self.subject, statement="Synthetic causal candidate",
            kind=ClaimKind.ROOT_CAUSE, support_refs=(self.support.ref_id,),
            falsifier="A counterexample would defeat this candidate",
            falsification_refs=(self.falsification.ref_id,),
            alternatives=("Synthetic competing cause",),
        )
        result = assess_know_claim(claim, (self.support, self.falsification))
        self.assertEqual(result.state, GateState.REVIEW_READY)
        self.assertTrue(result.review_ready)
        self.assertNotIn("KNOWN", {state.value for state in GateState})
        self.assertNotIn("PROMOTED", {state.value for state in GateState})

    def test_one_source_cannot_double_as_support_and_falsifier(self):
        claim = ClaimProposal(
            subject_digest=self.subject, statement="Synthetic causal candidate",
            kind=ClaimKind.ROOT_CAUSE, support_refs=(self.support.ref_id,),
            falsifier="A counterexample would defeat this candidate",
            falsification_refs=(self.support.ref_id,),
            alternatives=("Synthetic competing cause",),
        )
        result = assess_know_claim(claim, (self.support,))
        self.assertEqual(result.state, GateState.BLOCKED)
        self.assertIn("support_falsification_overlap", result.reasons)

    def test_stale_subject_does_not_gain_authority_from_new_label(self):
        claim = ClaimProposal(
            subject_digest="sha256:different-subject",
            statement="Synthetic fact candidate", kind=ClaimKind.HYPOTHESIS,
            support_refs=(self.support.ref_id,),
            alternatives=("Synthetic competing cause",),
        )
        result = assess_know_claim(claim, (self.support,))
        self.assertEqual(result.state, GateState.BLOCKED)
        self.assertIn("stale_or_unrelated_subject", result.reasons)


if __name__ == "__main__":
    unittest.main()
