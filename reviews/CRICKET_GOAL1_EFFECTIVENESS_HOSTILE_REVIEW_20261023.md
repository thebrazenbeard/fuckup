# Cricket hostile review — F.U.C.K.U.P. effectiveness and Vera Goal 1

**Date:** 2026-10-23  
**Role:** Instruction-layer Cricket Conscience review selected by the user; not a separately executing or independently attesting host.  
**Reviewed base:** `fuckup/main@a100e7d77bca83af2a998e37c0819e4e36cc5923`  
**Owned candidate:** `hardening/effectiveness-reference-completeness-20261023`  
**Question:** What can an observed reduction in failures legitimately establish about Vera's feedback-caused learning?

## Cricket — CHALLENGE

> Lovely. Five anonymous failures followed by five anonymous nonfailures earns `IMPROVEMENT_OBSERVED`. That is a description of numbers, not a testimonial from the laws of causality. Counting receipts was never the same as having a learner.

**Disposition: ACCEPTED, scoped.** The existing public `summarize_effectiveness()` is explicitly observational, with legacy tests requiring anonymous input support. The state name means rates improved *within supplied data*, not that a particular model consumed feedback or changed its decision policy.

**Narrow action:** Introduce opt-in `require_reference_completeness`. Under this mode, each sample must have the same exact versioned correction subject (already enforced), a nonempty distinct `operation_id`, and every ACTIVE sample must have nonempty `effect_digest` and `verification_evidence_ref`. Absence fails closed. Default behavior does not change.

> **Cricket — CHALLENGE:** A malicious caller can mint impressive-looking SHA strings and `verified:trust-me-bro` references. You have checked that fields exist. You have **not** authenticated who issued them, established a dispatch, verified an actual QVR consumer, or locked hidden evaluation answers.

**Disposition: ACCEPTED.** Explicit regression demonstrates that fabricated/nonexistent but syntactically populated refs *still* result in `IMPROVEMENT_OBSERVED`, not any new `CAUSAL_LEARNING_QUALIFIED` state. That is expected and deliberate: the flag is a completeness screen, not a truth screen or certification. API documentation says so. Do **not** use it as a standalone promotion, deployment, model-learning, or canonical-memory authority.

> **Cricket — CHALLENGE:** Mandatory fields everywhere would break the reference runtime's existing anonymous observational API. A badly named "strict verified" mode would merely polish the same unsupported claim.

**Disposition: ACCEPTED.** Mode is opt-in, labeled `reference_completeness` and bounded to mechanical checks. No reclassification of old observations.

## Executed controls

- Test-only candidate RED against original main: three new tests rejected because the argument did not exist; 11 earlier tests passed.
- Exact patch head after the source change, GitHub blob readback verified. Physical Lappy Windows Python 3.12 and VN1 Windows Python each ran **14/14** focused tests GREEN in separate isolated, SHA-checked temporary source environments.
- VN2 Linux independently generated a separate Granite local-model critique: fabricated refs can pass a presence test (output SHA-256 `7ccc9fbf6687cb9869d909b2f0f63319fd8124c5b3142848ea039837c9e7a094`); its output is not an execution test.
- Lappy Qwen3 4B independently criticized backwards-compatibility/claim inflation (output SHA-256 `6282ee094c8c9100f9d3b4952584b8cc1292bfc5947a5701fd56b5c59898ff87`). Its objection that an *opt-in* flag itself breaks compatibility is **rejected**; concern about potentially misleading causal claims is **accepted**.
- VN1 Qwen3 1.7B inference attempt was logged as `OUTCOME_UNKNOWN` and excluded from model-vote claims, not silently retried. VN1 focused source tests are separate evidence.

## Remaining causal qualification boundary

A positive rate observation — even with complete references — cannot establish:

1. evaluator-custodied pre-feedback predictions and controlled release of hidden truth;
2. real local-model invocation with witnessed exact prompt/response and dispatch identity;
3. observed consumption of the exact approved correction revision by selected QVR;
4. comparable frozen, revised, placebo and shuffled-feedback controls;
5. held-out gains that survive negative transfer, regression probes and actual cold process restart; or
6. independent evaluator scoring.

Those belong in the existing Vera Mono Goal 1 learner/evaluator and QVR ownership lanes (#86, #87, #82). F.U.C.K.U.P. must remain a self-contained reference semantics donor. Neither an artifact stored in F.U.C.K.U.P. nor the Cricket persona upgrades source into runtime consumption or effects.

**Concluding claim ceiling:** `SOURCE GUARD IMPLEMENTED → TARGETED TESTED`; no empirical feedback-caused behavioral learning demonstrated here. Full GitHub CI and merge verification are separately required.
