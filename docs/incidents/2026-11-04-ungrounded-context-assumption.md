# Anonymized correction case — unsupported conversational context

**Date:** 2026-11-04
**Evidence:** USER account and assistant messages in one chat, not public
source verification. This note intentionally excludes health details,
identifiers and private transcript material. The example is generalized.

## Flag
A speaker described making an utterance while alone. The assistant added
an imagined conversational context and reasoned from that unsupported premise.

## Understand
The assistant introduced an extra participant without evidence. This is an
observable **attribution and reasoning error**; an internal mechanistic
explanation for why the model did it is not verified.

Competing explanations include generic template completion, failure to
reconcile a local constraint, or overgeneralization from common dialogues.
These are hypotheses, not measurements of internal model state.

## Calibrate
Remove the invented participant. Keep the known facts scoped to the user's
report, and label any causal explanation as inference.

## Know — NOT QUALIFIED
The supported narrow conclusion is that a statement exceeded its evidence.
Root cause within the model is unknown. Falsifiers require controlled
counterexamples and comparisons across independent contexts.

## Unlearn / Prevent — candidate only
A source-bound fact assertion should fail structural preflight if it asserts
`participants=multiple` against evidence `participants=one`.
The new `know_gate` tests include that synthetic case.

This is **not** evidence that hosted ChatGPT learned or installed the rule.
The host must actually materialize a trusted instruction or guard in its
runtime, verify the exact outbound request, and observe new outcomes over time.
No such host deployment or recurrence reduction is claimed by this record.
