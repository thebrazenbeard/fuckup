# GitHub Protocol and Reusable-Code Landscape

Date: 2026-09-23
Status: research/adoption map
Target: F.U.C.K.U.P. corrective-learning protocol

## Purpose

F.U.C.K.U.P. should invent only the corrective-learning semantics it actually needs.

It should **not** invent a new agent transport, API description format, event envelope, trace model, policy language, provenance format, signature envelope, structured-output mechanism, or generic evaluation harness when mature open standards and implementations already exist.

This document records the highest-value public GitHub protocols and codebases found during a broad scan, and assigns each a disposition:

- **ADOPT** — design F.U.C.K.U.P. to interoperate with the protocol.
- **BORROW** — reuse or adapt implementation patterns/code subject to license and attribution.
- **ADAPTER** — keep the F.U.C.K.U.P. core independent, but provide a clean integration layer.
- **REFERENCE** — learn from it; do not make it a core dependency.
- **MONITOR** — relevant but not currently central enough to adopt.

## 1. Agent and tool protocol stack

### Model Context Protocol (MCP)

Repo: https://github.com/modelcontextprotocol/modelcontextprotocol
Disposition: **ADOPT + ADAPTER**
License: transition from MIT to Apache-2.0 for new code/spec contributions; documentation separately CC-BY-4.0.

Why it matters:
- MCP standardizes model/agent access to tools, resources, prompts, and other external context.
- The official repository publishes a TypeScript source schema and generated JSON Schema.
- F.U.C.K.U.P. should be exposable as MCP capabilities without making MCP part of the core state machine.

Candidate MCP surface:
- tool: `fuckup.flag`
- tool: `fuckup.analyze`
- tool: `fuckup.validate`
- resource: `fuckup://records/{id}`
- resource: `fuckup://rules/{id}`
- prompt/skill: run the six-stage protocol over a supplied incident.

Do not copy MCP transport logic into the project. Depend on an SDK or adapter.

### Agent2Agent (A2A)

Repo: https://github.com/a2aproject/A2A
Disposition: **ADOPT + ADAPTER**
License: Apache-2.0.

Why it matters:
- A2A is explicitly designed for interoperability between opaque agents built by different companies/frameworks.
- F.U.C.K.U.P. corrections may be produced, challenged, verified, or consumed by different agents.
- Correction artifacts should be transferable without assuming the same model family or runtime.

Candidate use:
- Advertise a `corrective-learning` / `fuckup-review` agent skill.
- Pass incident evidence and proposed corrections between agents.
- Allow an independent verifier agent to return a verdict without sharing internal implementation.

### Agent Client Protocol (ACP)

Repo: https://github.com/agentclientprotocol/agent-client-protocol
Disposition: **ADAPTER**
License: Apache-2.0.

Why it matters:
- ACP standardizes communication between code editors and coding agents.
- It has a negotiated wire protocol version and generated JSON Schema artifacts.
- If F.U.C.K.U.P. is used by coding agents, an ACP adapter lets corrections and verification results reach editor/agent workflows without inventing another coding-agent channel.

This is a different concern from A2A:
- A2A: agent-to-agent interoperability.
- ACP: coding-client/editor to coding-agent interoperability.

### AG-UI

Repo: https://github.com/ag-ui-protocol/ag-ui
Disposition: **ADAPTER / MONITOR**
License: MIT.

Why it matters:
- AG-UI is an event-based protocol for agent-to-user application interaction.
- The project describes itself as complementary to MCP and A2A.
- It is useful if F.U.C.K.U.P. exposes human review, approval, evidence inspection, or rollback controls through a UI.

Not core. A headless F.U.C.K.U.P. engine must work without it.

### Retired/fragmented ACP-style agent communication protocols

Repo example: https://github.com/i-am-bee/acp (archived)
Disposition: **REFERENCE ONLY**

Reason:
- The agent-protocol ecosystem is fragmented.
- Do not bind the core data model to a single transient agent-communication framework.
- Keep adapters at the boundary.

## 2. Core data contract and API description

### JSON Schema

Repo: https://github.com/json-schema-org/json-schema-spec
Disposition: **ADOPT**
License: BSD-style 3-clause terms in repository license.

Why it matters:
- JSON Schema is a mature vocabulary for validation and annotation of JSON documents.
- The canonical F.U.C.K.U.P. record should have a JSON Schema.
- YAML can remain the preferred human-readable serialization because YAML can represent the same underlying object model.

Rule:
**Semantic contract first; serialization second.**

Canonical validation should not depend on YAML quirks.

### OpenAPI

Repo: https://github.com/OAI/OpenAPI-Specification
Disposition: **ADOPT when exposing HTTP**
License: Apache-2.0.

Why it matters:
- Standard language-neutral description of HTTP services.
- Supports YAML or JSON descriptions.
- Enables client generation, API documentation, contract testing, and discoverability.

Use only if/when F.U.C.K.U.P. exposes an HTTP service.

### AsyncAPI

Repo: https://github.com/asyncapi/spec
Disposition: **ADOPT when exposing asynchronous/event APIs**
License: Apache-2.0.

Why it matters:
- F.U.C.K.U.P. is naturally eventful: failures are flagged, investigations begin, corrections are proposed, validations pass/fail, lessons are promoted, rules are superseded.
- AsyncAPI can describe those asynchronous channels instead of inventing custom event documentation.

## 3. Event envelope

### CloudEvents

Repo: https://github.com/cloudevents/spec
Disposition: **ADOPT**
License: Apache-2.0.

Why it matters:
- CloudEvents exists specifically because event producers otherwise invent incompatible event formats.
- It provides a standard event envelope across services/platforms.
- Core attributes include concepts such as `id`, `source`, `type`, and `specversion`.

Candidate F.U.C.K.U.P. event types:
- `org.fuckup.failure.flagged`
- `org.fuckup.analysis.completed`
- `org.fuckup.correction.proposed`
- `org.fuckup.validation.passed`
- `org.fuckup.validation.failed`
- `org.fuckup.learning.promoted`
- `org.fuckup.learning.superseded`
- `org.fuckup.rollback.executed`

The F.U.C.K.U.P. record belongs in the event data; CloudEvents should provide the transport-neutral envelope.

## 4. Observability and traces

### OpenTelemetry

Repo: https://github.com/open-telemetry/opentelemetry-specification
Related semantic-conventions repo: https://github.com/open-telemetry/semantic-conventions
Disposition: **ADOPT**
License: Apache-2.0.

Why it matters:
- A F.U.C.K.U.P. incident needs evidence of what actually happened, not reconstructed storytelling.
- OpenTelemetry provides cross-language traces, spans, metrics, and logs.
- Current OpenTelemetry work includes GenAI semantic conventions such as `gen_ai.*` attributes.

Design consequence:
A F.U.C.K.U.P. record should be able to bind to trace/span IDs. The protocol should not duplicate telemetry payloads inside the correction record.

### OpenInference

Repo: https://github.com/Arize-ai/openinference
Disposition: **ADAPTER / BORROW**
License: Apache-2.0.

Why it matters:
- OpenInference adds AI-specific tracing conventions on top of OpenTelemetry.
- Its span kinds include Agent, LLM, Tool, Guardrail, Evaluator, Retriever, Reranker, Embedding, Chain, and Prompt.
- Those categories map directly to locating where an AI failure occurred.

Candidate F.U.C.K.U.P. evidence fields:
- trace ID
- span ID
- failing span kind
- tool/model/provider metadata
- input/output hashes or references
- evaluator evidence.

### OpenLLMetry

Repo: https://github.com/traceloop/openllmetry
Disposition: **ADAPTER / BORROW**
License: Apache-2.0.

Why it matters:
- Provides OpenTelemetry-based instrumentation for LLM providers and vector databases.
- Useful as an instrumentation integration rather than as a F.U.C.K.U.P. dependency.

## 5. Lineage and provenance

### OpenLineage

Repo: https://github.com/OpenLineage/OpenLineage
Disposition: **ADOPT CONCEPTS + ADAPTER**
License: Apache-2.0.

Why it matters:
- Defines generic run/job/dataset lineage and extensible facets.
- A correction needs lineage: which failure, evidence, model/configuration, prompt/rule, tests, and previous lesson produced the new state.

Potential F.U.C.K.U.P. facets:
- failure facet
- correction facet
- evidence facet
- validation facet
- learning-state facet
- supersession facet.

Do not duplicate entire lineage graphs if an existing lineage backend is available; keep references.

### in-toto

Repo: https://github.com/in-toto/in-toto
Disposition: **BORROW / ADAPTER**
License: Apache-2.0.

Why it matters:
- in-toto models a planned sequence of steps, authorized actors, resulting artifacts, and signed evidence.
- Its `Link` object is explicitly evidence for a performed step/inspection.
- Verification checks expected steps, signatures/authorization, and material/product rules.

This maps unusually well to verified corrective learning.

Potential mapping:
- layout → allowed F.U.C.K.U.P. promotion workflow
- step → protocol stage or validation gate
- functionary → human/agent/verifier allowed to perform a step
- materials → evidence + prior rule/model state
- products → correction artifact + tests + replacement rule
- link → signed evidence that the step actually occurred.

### in-toto Attestation Framework

Repo: https://github.com/in-toto/attestation
Disposition: **ADOPT CONCEPT / POTENTIAL CUSTOM PREDICATE**
License: Apache-2.0.

Why it matters:
- Defines verifiable claims and extensible predicate types.
- Provides protobuf definitions and multiple language bindings.
- A future `FUCKUPCorrectionPredicate` could make a correction portable and cryptographically attestable.

### DSSE — Dead Simple Signing Envelope

Repo: https://github.com/secure-systems-lab/dsse
Disposition: **ADOPT for signed correction artifacts when needed**
License: Apache-2.0.

Why it matters:
- Signs arbitrary payloads while authenticating both payload and payload type.
- Designed to avoid fragile canonicalization.
- Already used by in-toto and Sigstore ecosystems.
- Python implementation exists in the repository; Go implementations also exist.

Candidate payload type:
`application/vnd.fuckup.correction+json`

Do not require signing for ordinary local experimentation. Make attestation optional but standardized.

### SLSA

Repo: https://github.com/slsa-framework/slsa
Disposition: **REFERENCE / BORROW PRINCIPLES**
License: Community Specification License 1.0 for the specification; not a generic source-code license.

Why it matters:
- Provides a vocabulary for increasing levels of supply-chain integrity and provenance.
- Useful conceptual precedent for defining **levels of learning assurance**.

Possible future analogy:
- F0: reflection only
- F1: structured correction record
- F2: external evidence bound
- F3: regression/contrast validation passed
- F4: independently verified + provenance/attestation

Do not copy SLSA specification text or present this analogy as SLSA compliance.

### Sigstore

Repo: https://github.com/sigstore/cosign
Disposition: **ADAPTER / OPTIONAL**
Use case:
- Signing/verifying promoted correction artifacts or model/adapter artifacts.
- Useful when corrections cross trust boundaries.

### C2PA

Repo: https://github.com/c2pa-org/specifications
Disposition: **REFERENCE / MONITOR**
Spec license: CC-BY-4.0.

Why it matters:
- Strong precedent for content credentials and provenance.
- More media/content-focused than F.U.C.K.U.P.'s immediate needs.
- Do not make it a core dependency.

## 6. Policy and learning gates

### Open Policy Agent (OPA)

Repo: https://github.com/open-policy-agent/opa
Disposition: **ADAPTER / BORROW**
License: Apache-2.0.

Why it matters:
- General-purpose context-aware policy engine.
- F.U.C.K.U.P. needs deterministic gates deciding whether a proposed lesson can be promoted to durable state.

Examples of policy questions:
- Is the correction externally verified?
- Does confidence exceed the threshold?
- Did the retain/regression set pass?
- Is the feedback source trusted enough for this scope?
- Is the proposed learning reversible?
- Does promotion require human approval?
- Is this correction allowed to update prompts/memory/adapter weights/model weights?

The core protocol should define policy inputs/outputs without requiring Rego. OPA should be one high-quality adapter.

## 7. Reflection and correction-loop implementations

### Reflexion

Repo: https://github.com/noahshinn/reflexion
Disposition: **BORROW**
License: MIT.

What to borrow:
- explicit reflection strategies
- last-attempt vs reflection memory separation
- episodic verbal reinforcement
- retry/trial loop patterns.

What not to inherit:
- the assumption that the same agent's reflection is sufficient evidence.
- provider-specific implementation details.

### Self-Refine

Repo: https://github.com/madaan/self-refine
Disposition: **BORROW**
License: Apache-2.0.

What to borrow:
- generate → feedback → refine iterative architecture
- task-specific scoring/refinement hooks
- loop termination patterns.

F.U.C.K.U.P. differs by requiring durable learning validation and provenance instead of only improving the current output.

## 8. Behavioral validation and regression

### CheckList

Repo: https://github.com/marcotcr/checklist
Disposition: **BORROW**
License: MIT.

What to borrow:
- behavioral test suites
- expectation functions
- perturbation-based invariance/directional tests
- test generation/template patterns.

This is a strong foundation for F.U.C.K.U.P. `Prevent`: every promoted correction should create tests around the failure class.

### Contrast Sets

Repo: https://github.com/allenai/contrast-sets
Disposition: **REFERENCE + BORROW DATA/EVAL PATTERN SUBJECT TO DATASET LICENSES**

What to borrow:
- minimally changed examples that should cause predictable output changes
- near-transfer evaluation
- robustness testing against local perturbations.

Repository-level code/data licensing must be checked per dataset before copying assets; no root `LICENSE` was found during this pass.

### Promptfoo

Repo: https://github.com/promptfoo/promptfoo
Disposition: **ADAPTER / BORROW**
License: MIT.

Why it matters:
- provider-agnostic prompt/model comparison
- automated evals
- CI/CD integration
- red teaming.

This is an excellent candidate test runner for vendor-neutral F.U.C.K.U.P. experiments across OpenAI, Anthropic, local models, and others.

### DeepEval

Repo: https://github.com/confident-ai/deepeval
Disposition: **ADAPTER / BORROW**
License: Apache-2.0.

Use:
- LLM evaluation primitives
- regression/evaluation suites
- CI integration.

Do not require one evaluation framework. Define a F.U.C.K.U.P. evaluator interface.

### OpenAI Evals

Repo: https://github.com/openai/evals
Disposition: **REFERENCE / ADAPTER AFTER LICENSE VERIFICATION**

The repository provides an LLM/system evaluation framework and custom eval registry, but a root license file was not found in this scan. Do not vendor code until licensing is verified.

## 9. Structured generation and validation

### Instructor

Repo: https://github.com/567-labs/instructor
Disposition: **BORROW / ADAPTER**
License: MIT.

Why it matters:
- provider-neutral structured outputs through typed models
- validation and retry behavior
- Pydantic integration.

Use as one implementation path for emitting validated F.U.C.K.U.P. records.

### Outlines

Repo: https://github.com/dottxt-ai/outlines
Disposition: **ADAPTER / BORROW**
License: Apache-2.0.

Why it matters:
- constrained structured generation at generation time rather than parsing malformed text afterward.
- Particularly relevant for local/open-weight models.

### Guardrails

Repo: https://github.com/guardrails-ai/guardrails
Disposition: **ADAPTER / BORROW**
License: Apache-2.0.

Why it matters:
- input/output validation and guard execution.
- Useful for validating corrections, evidence shape, and policy-related constraints.

Current project note:
The repository announces a 2026 move away from hosted remote validators toward standard installable PyPI validators. Prefer local/portable validators.

## 10. Memory and persistence

### Mem0

Repo: https://github.com/mem0ai/mem0
Disposition: **ADAPTER / BORROW**
License: Apache-2.0.

Why it matters:
- production-oriented memory layer.
- Current repository emphasizes selective, token-efficient memory rather than replaying all history.
- Useful as a persistence adapter, not as the definition of learning.

Important:
F.U.C.K.U.P. must distinguish:
- incident record
- proposed lesson
- validated durable lesson
- superseded/retired lesson.

Do not dump every incident into retrieval memory as an equally authoritative fact.

### Letta

Repos:
- https://github.com/letta-ai/letta
- active source now referenced from https://github.com/letta-ai/letta-code

Disposition: **REFERENCE / ADAPTER**
License of inspected `letta-ai/letta`: Apache-2.0.

Why it matters:
- stateful agents with memory and durable identity.
- Useful for studying how a validated F.U.C.K.U.P. lesson becomes operational agent state.

Do not couple the core to Letta's memory model.

## 11. Machine unlearning and retain testing

### Open-Unlearning / TOFU lineage

Repos:
- https://github.com/locuslab/open-unlearning
- legacy https://github.com/locuslab/tofu

Disposition: **REFERENCE + BORROW EVAL PATTERNS**
Legacy TOFU license: MIT.

Why it matters:
- explicit forget sets and retain sets.
- F.U.C.K.U.P. `Unlearn` must test that retiring a faulty behavior does not destroy neighboring valid behavior.

Use the conceptual split:
- **forget/correct set**
- **retain set**
- **generalization/transfer set**.

Do not equate successful suppression on the incident with genuine unlearning.

## 12. Recommended F.U.C.K.U.P. architecture after GitHub scan

### Core — own this

F.U.C.K.U.P. should own:
- six-stage state machine
- correction record semantics
- evidence requirements
- causal-hypothesis representation
- learning/promotion states
- supersession/rollback semantics
- validation gate requirements
- recurrence/transfer/retain metrics
- trust/provenance references.

### Standard interfaces — adopt, do not reinvent

- JSON Schema — record contract
- CloudEvents — event envelope
- OpenTelemetry — traces/metrics/log references
- OpenAPI — synchronous HTTP API description
- AsyncAPI — event/channel API description
- MCP — model/tool integration
- A2A — agent-to-agent integration
- ACP — coding-client/coding-agent integration
- AG-UI — optional human-facing realtime integration.

### Extension/adapters — support without coupling

- OpenInference / OpenLLMetry — AI observability
- OpenLineage — lineage
- OPA — policy gates
- in-toto / DSSE / Sigstore — attestations/signatures
- Promptfoo / DeepEval / CheckList — evaluation
- Instructor / Outlines / Guardrails — structured generation/validation
- Mem0 / Letta — memory/persistence
- Open-Unlearning / TOFU — unlearning and retain-set evaluation.

## 13. Candidate canonical record

The record should be JSON-Schema-valid regardless of whether represented as JSON or YAML.

Suggested top-level shape:

```yaml
protocol: FUCKUP
version: 0.1.0
record_id: uuid
state: flagged | investigating | correction_proposed | validating | learned | rejected | superseded | rolled_back

subject:
  kind: model | agent | human | process | organization | software
  id: string
  version: string|null

trigger:
  event_id: string
  source: string
  failure_class: string
  observed_at: timestamp

flag:
  observation: string
  expected: any
  actual: any

understand:
  sequence: []
  context: {}
  evidence_refs: []

calibrate:
  immediate_changes: []
  stabilized: boolean

know:
  causal_hypotheses:
    - proposition: string
      evidence_for: []
      evidence_against: []
      confidence: number
  contributing_factors: []

unlearn:
  target:
    layer: context | memory | prompt | policy | retrieval | adapter | weights | process
    identifier: string
  replacement: any
  rollback: any

prevent:
  controls: []
  regression_tests: []
  contrast_tests: []
  transfer_tests: []
  retain_tests: []

validation:
  evaluator_refs: []
  original_case_passed: boolean
  recurrence_passed: boolean
  transfer_passed: boolean
  retain_passed: boolean
  policy_passed: boolean

provenance:
  trace_refs: []
  lineage_refs: []
  attestation_refs: []
  parent_record_ids: []
  supersedes: []
```

## 14. Highest-value implementation order

1. JSON Schema for the canonical record.
2. Python reference library with deterministic state transitions.
3. Validation gate + policy interface.
4. Behavioral regression/contrast/retain test abstraction.
5. CloudEvents event mapping.
6. OpenTelemetry/OpenInference evidence binding.
7. Promptfoo adapter for multi-model experiments.
8. MCP adapter.
9. A2A adapter.
10. Memory adapter interface, then Mem0/Letta implementations.
11. Optional in-toto/DSSE attestation.
12. HTTP/OpenAPI and AsyncAPI service surfaces if a daemon/server is built.
13. ACP/AG-UI adapters where coding/UI workflows justify them.

## 15. Immediate code-adoption candidates

Most attractive codebases to inspect at function/class level before implementation:

1. `noahshinn/reflexion` — reflection/memory/trial-loop mechanics — MIT.
2. `madaan/self-refine` — feedback/refinement loop — Apache-2.0.
3. `marcotcr/checklist` — behavioral test abstractions — MIT.
4. `promptfoo/promptfoo` — provider-agnostic eval matrix + CI/red-team runner — MIT.
5. `confident-ai/deepeval` — reusable eval primitives — Apache-2.0.
6. `567-labs/instructor` — typed structured-output validation/retry — MIT.
7. `dottxt-ai/outlines` — constrained structured generation — Apache-2.0.
8. `open-policy-agent/opa` — deterministic promotion policy engine — Apache-2.0.
9. `in-toto/in-toto` + `secure-systems-lab/dsse` — evidence/attestation patterns — Apache-2.0.
10. `Arize-ai/openinference` — AI trace semantics — Apache-2.0.
11. `mem0ai/mem0` — selective memory persistence — Apache-2.0.
12. `locuslab/open-unlearning` / `tofu` — forget/retain evaluation architecture.

## 16. Architectural conclusion

The project should become a **corrective-learning protocol with adapters**, not an all-in-one agent framework.

The core value is:

`verified failure → causal analysis → bounded correction → validated unlearning/replacement → prevention tests → evidence-backed promotion → durable lesson`

The surrounding ecosystem already has mature solutions for transport, structure, policy, telemetry, provenance, memory, and evaluation. F.U.C.K.U.P. should compose them rather than compete with them.
