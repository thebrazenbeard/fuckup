# Know evidence preflight V1 — epistemic ceilings

Status: **opt-in structural preflight, not an installed ChatGPT behavior hook**.
The implementation is `src/fuckup_protocol/know_gate.py`, with synthetic
hostile regression tests in `tests/test_know_gate.py`.

## Why this exists

An assistant can correctly restate a reported fact, insert a plausible but
unsupplied participant or setting, then explain that invention as though it
were evidence. A verbal apology can correct a turn without establishing why
the model made the mistake or showing that it learned a lasting new behavior.

**Rule:** Preserve the speaker's actual account. Separate reported facts,
source/tool observations, inference, test results, and model review. A
plausible explanation is not a confirmed mechanism.

## Executable preflight

`assess_know_claim(ClaimProposal, tuple[EvidenceRef, ...])` checks:
- exact incident/subject binding for all cited refs;
- known, nonduplicate references, valid evidence kinds and nonempty claims;
- explicit atomic key/value match for reported/observed facts;
- conflicting attached fact values and stale/missing evidence;
- an alternative and a falsifier for proposed causal explanations;
- distinct support and falsification references backed by test/probe metadata;
- model review alone cannot stand in for an independently observed causal test.

`BLOCKED`: basic provenance/structure is missing or inconsistent.
`PROVENANCE_BOUND`: claim has matching references of the stated type, **not**
a guarantee of the statement's truth or that the source entails the wording.
`REVIEW_READY`: a root-cause proposal has the structural ingredients for
**independent** assessment, **not** a verified root cause.

The function never returns `KNOWN`, never calls
`authorize_promotion`, and never mutates corrections or model weights.

## What this gate cannot establish

A source ID can be fabricated. A declared TEST may not have run. An
atomic `fact_key` or `fact_value` could misrepresent the original
utterance. A repeated example can pass tests without generalizing.
The gate does not authenticate evidence providers, parse natural-language
entailment, adjudicate causal alternatives, or attest host execution.

A trusted host must preserve original source excerpts privately, derive
atomic facts faithfully, verify referenced tests and probes, commission
independent hostile review, and enforce the gate **before** it uses any
source-bound claim. This library does not transparently intercept a hosted
model's prose. The current promotion policy's
`root_cause_supported: bool` remains a caller-provided assertion; this
new preflight **does not remove that trust boundary**. Integrating verified
K-evidence into the trusted authorizer and database lifecycle is future work,
not an achievement of this PR.

## Example — synthetic, no personal data

Evidence: `participants=one`, `USER_REPORT`, bound to incident digest.
Permitted attribution: "The reporter says they spoke while alone."
Rejected structured assertion: `participants=multiple`, even if an LLM
can produce a fluent explanation involving another speaker.

A source-labeled account is not an independently proven event.
Without a reliable causal probe and falsification effort, the honest K
state is **unknown or hypothesized**, not confirmed.

## Verification

`python -m pytest -q tests/test_know_gate.py`
`python -m pytest -q`

The tests establish only the stated structural rules against those fixtures.
They do not establish a deployed guard, durable correction, generalization,
or proof that the same assistant will stop making the mistake.
