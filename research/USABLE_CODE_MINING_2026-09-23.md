# Usable Code Mining Notes

Date: 2026-09-23
Status: implementation-source triage
Parent landscape: `research/GITHUB_PROTOCOL_AND_CODE_LANDSCAPE_2026-09-23.md`

## Goal

Identify concrete implementation units from public GitHub repositories that are worth adapting into F.U.C.K.U.P., rather than merely naming adjacent projects.

The default rule is:
- depend on mature libraries when their job is generic;
- reimplement small protocol-specific ideas when coupling to an old research harness would be worse;
- preserve license/attribution obligations;
- never copy code whose license is unknown.

## 1. Reflexion — reflection memory mechanics

Repo: https://github.com/noahshinn/reflexion
License: MIT.
Inspected head during scan: `218cf0ef1df84b05ce379dd4a8e47f17766733a0`.

Useful code surfaces:
- `hotpotqa_runs/agents.py::ReflexionStrategy`
- `webshop_runs/generate_reflections.py::update_memory`
- `alfworld_runs/generate_reflections.py::update_memory`
- `webshop_runs/env_history.py::EnvironmentHistory`
- `alfworld_runs/env_history.py::EnvironmentHistory`

Observed design patterns:
- reflection strategy is explicit rather than implicit;
- last attempt and reflection are separable context channels;
- persistent memory can be toggled on/off for baseline comparison;
- environment history is reconstructed with a bounded memory window;
- some task loops cap injected memory to the last three entries.

Adopt:
- explicit correction-memory strategy enum;
- bounded retrieval/injection;
- baseline mode with correction memory disabled;
- separate raw attempt evidence from learned lesson.

Do not copy wholesale:
- provider-specific prompting;
- task-specific environment code;
- assumption that a generated reflection deserves persistence.

F.U.C.K.U.P. replacement:
`LearningContextPolicy = NONE | LAST_FAILURE | LAST_VALIDATED_LESSON | RELEVANT_VALIDATED_LESSONS`

Only validated lessons should enter the durable path.

## 2. Self-Refine — feedback/refinement loop

Repo: https://github.com/madaan/self-refine
License: Apache-2.0.
Inspected head during scan: `9a206d41e5d2d0c241bb441f41eeadb945afaa55`.

Useful code surfaces:
- task-specific `feedback.py` modules under `src/*/`
- repeated generate → feedback → improved-output pattern
- explicit delimiters/termination markers such as `### END`
- feedback and revised solution returned as distinct values.

Adopt:
- feedback as a first-class object, not just freeform commentary;
- correction loop with explicit termination conditions;
- task-specific evaluator/refiner adapters.

Change for F.U.C.K.U.P.:
- feedback must carry provenance;
- correction must not be promoted merely because the refiner produced it;
- validation is a separate stage from refinement;
- current-output improvement and durable-learning promotion are distinct outcomes.

## 3. CheckList — behavioral test taxonomy

Repo: https://github.com/marcotcr/checklist
License: MIT.
Inspected head during scan: `4e6e5e33a26f30c20ed602b2050f6c73e123cc23`.

Useful code surfaces:
- `checklist.expect.Expect.inv(tolerance=...)`
- test taxonomy exposed as MFT / INV / DIR:
  - MFT: Minimum Functionality Test
  - INV: Invariance Test
  - DIR: Directional Expectation Test
- template/perturbation test generation;
- test-suite aggregation.

This maps exceptionally well to F.U.C.K.U.P. validation.

Proposed mapping:
- **MFT** → the corrected system must pass the minimum behavior that originally failed.
- **INV** → unrelated/irrelevant changes must not alter valid behavior.
- **DIR** → controlled changes should move output/behavior in the expected direction.
- **Contrast test** → nearby perturbation of the original failure.
- **Retain test** → valid neighboring capability must remain intact.

Recommendation:
Implement a small native F.U.C.K.U.P. test abstraction inspired by this taxonomy; optionally provide a CheckList adapter rather than importing the entire older NLP-specific stack.

## 4. Instructor — schema validation and re-ask/retry

Repo: https://github.com/567-labs/instructor
License: MIT.
Inspected head during scan: `e12f8b49203b0c1f253d27c1e709d0a09b9fc5a8`.

Useful code surfaces:
- `instructor/v2/core/response_model.py::prepare_response_model`
- `instructor/v2/core/retry.py`
- provider-specific schema adapters;
- retry/re-ask based on validation failure;
- Pydantic response models.

Adopt by dependency/adapter, not vendoring:
- emit a typed `FuckupRecord`;
- validate before accepting generated protocol records;
- on structural validation failure, re-ask with deterministic validation errors;
- support OpenAI, Anthropic, Gemini and other provider adapters through one structured-output layer where practical.

Important distinction:
schema-valid does not mean epistemically valid. Instructor can validate the **shape**; F.U.C.K.U.P. validation must still validate the **claim/evidence**.

## 5. Promptfoo — multi-provider experimental/eval runner

Repo: https://github.com/promptfoo/promptfoo
License: MIT.

Useful patterns:
- declarative test cases and assertions;
- provider-agnostic side-by-side model evaluation;
- YAML configuration;
- automated evaluation and CI;
- red-team execution.

Adopt as an experimental adapter:
The semantic-salience experiment should be runnable through Promptfoo before we build a bespoke multi-provider harness.

Candidate experiment dimensions:
- protocol name;
- field names;
- serialization;
- model/provider;
- correction source;
- persistence mode.

Do not make Promptfoo the canonical data model.

## 6. Mem0 — persistence/retrieval boundary

Repo: https://github.com/mem0ai/mem0
License: Apache-2.0.
Inspected head during scan: `83b07b1537d688b9687bb116f8e0c6a9cabf2d95`.

Useful code surfaces:
- backend-neutral memory/vector-store interfaces;
- `search(..., top_k, filters)` pattern across vector-store backends;
- metadata-filtered retrieval.

Adopt as an adapter pattern:
F.U.C.K.U.P. retrieval must filter by:
- validation state;
- scope;
- subject/model;
- failure class;
- supersession status;
- confidence/trust;
- applicability window.

Do not copy the idea that all memories are equivalent. An incident is not automatically a lesson.

## 7. Open-Unlearning — forget/retain separation

Repo: https://github.com/locuslab/open-unlearning
Legacy benchmark: https://github.com/locuslab/tofu

Useful inspected surfaces:
- `configs/data/datasets/TOFU_QA_forget.yaml`
- `configs/data/datasets/TOFU_QA_retain.yaml`
- perturbed/retention evaluation datasets;
- explicit forget and retain splits.

Adopt conceptually:
Every F.U.C.K.U.P. `Unlearn` operation should define:
- **target set** — behavior/knowledge to change;
- **retain set** — neighboring behavior that must not change;
- **transfer set** — unseen related cases that should improve;
- **anti-trigger set** — cases where the correction must not activate.

This should exist even when "unlearning" occurs at prompt/memory/policy level instead of model weights.

## 8. in-toto — evidence object model

Repo: https://github.com/in-toto/in-toto
License: Apache-2.0.
Inspected head during scan: `e352b43ad7cb8915d84c36d791aa61346152a0a3`.

Useful code surfaces:
- `in_toto/models/link.py::Link` — evidence for a performed step/inspection;
- `in_toto/models/layout.py::Layout` — expected sequence and authorization;
- `in_toto/models/metadata.py` — DSSE-aware metadata abstraction;
- verification logic checks expected steps, signatures/authorization, artifacts and rules.

Recommendation:
Do not reimplement signing/attestation logic.
Create an optional adapter that translates a validated F.U.C.K.U.P. correction into an in-toto attestation/predicate.

## 9. DSSE — signed envelope

Repo: https://github.com/secure-systems-lab/dsse
License: Apache-2.0.
Inspected head during scan: `1d3370f62565bca041e97c8310b873ac340edc2e`.

Useful code surfaces:
- `implementation/signing_spec.py::Signer`
- protocol uses pre-authentication encoding to bind payload bytes to payload type before signing;
- repository includes a Python implementation;
- in-toto already integrates DSSE.

Recommendation:
Use existing DSSE/in-toto libraries for signed correction artifacts.
Do not invent canonicalization/signature rules.

## 10. CloudEvents — correction-event transport

Repo: https://github.com/cloudevents/spec
License: Apache-2.0.

Adopt protocol, use existing language SDKs.
F.U.C.K.U.P. should only define event `type` names and payload schemas.

Minimum binding:
- `id` = event UUID
- `source` = emitting agent/system
- `type` = F.U.C.K.U.P. lifecycle event
- `subject` = correction record ID or affected subject
- `data` = schema-valid F.U.C.K.U.P. event payload.

## 11. OpenTelemetry + OpenInference — incident evidence

Repos:
- https://github.com/open-telemetry/opentelemetry-specification
- https://github.com/open-telemetry/semantic-conventions
- https://github.com/Arize-ai/openinference

OpenInference inspected design:
span kinds include Chain, Retriever, Reranker, LLM, Embedding, Agent, Tool, Guardrail, Evaluator, and Prompt.

Recommendation:
F.U.C.K.U.P. records should reference trace/span evidence instead of embedding entire traces.

Potential failure-location vocabulary can reuse these categories.

## 12. OPA — promotion gate

Repo: https://github.com/open-policy-agent/opa
License: Apache-2.0.

Recommendation:
Define a generic `PromotionPolicy` interface in the core.
Provide OPA/Rego as one adapter.

Example policy input:
```json
{
  "record_state": "validating",
  "evidence_verified": true,
  "original_case_passed": true,
  "transfer_passed": true,
  "retain_passed": true,
  "feedback_trust": 0.9,
  "target_layer": "memory",
  "requires_human_approval": false
}
```

Example policy output:
```json
{
  "allow_promotion": true,
  "required_actions": []
}
```

## Code-adoption rule

Before any third-party implementation is copied rather than consumed as a dependency:
1. pin exact source commit;
2. confirm license at that commit;
3. record original path/function;
4. copy the smallest necessary unit;
5. preserve required copyright/license notice;
6. add local characterization tests;
7. document modifications;
8. maintain an upstream provenance record.

## Immediate implementation candidates

The next code work should be native and small:

1. `fuckup/schema/fuckup-record.schema.json`
2. `fuckup/core/state.py` or equivalent vendor-neutral state machine
3. `fuckup/core/models.py` typed record representation
4. `fuckup/core/validation.py` with MFT/INV/DIR/contrast/retain/transfer result types
5. `fuckup/core/policy.py` generic promotion-policy interface
6. `fuckup/adapters/promptfoo/` experimental evaluator adapter
7. `fuckup/adapters/otel/` trace-reference binding
8. `fuckup/adapters/mcp/` tool/resource exposure
9. optional `fuckup/adapters/intoto/` attestation adapter

This keeps the core tiny, inspectable, provider-neutral and testable while letting mature external ecosystems do the generic infrastructure work.
