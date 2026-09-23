# F.U.C.K.U.P. Runtime Architecture V0

Status: handoff proposal / not implemented

## Core principle

The runtime turns a failure into a bounded, provenance-bearing correction that can affect future behavior only after qualification and policy checks.

```text
INPUT / EXECUTION
      |
      v
 [Failure/Event]
      |
      v
 [FLAG]
 normalize -> fingerprint -> dedupe -> record
      |
      v
 [UNDERSTAND]
 trace -> context -> dependencies -> competing explanations
      |
      v
 [CALIBRATE]
 confidence -> ambiguity state -> route/escalate
      |
      v
 [KNOW]
 root-cause candidate -> evidence/support -> scope
      |
      v
 [UNLEARN]
 versioned correction candidate -> supersession relationship
      |
      v
 [QUALIFY]
 replay -> property/adversarial tests -> policy checks
      |
      v
 [PREVENT]
 promote guards/rules/injection binding
      |
      v
 [OBSERVE]
 recurrence + regressions + effectiveness
```

## Non-negotiable separations

- failure record != root-cause conclusion
- route selection != authorization
- confidence != truth
- correction candidate != promoted correction
- promoted correction != global rule
- source/build/install/runtime/effectiveness are distinct
- retry != proof the first attempt failed
- supersession != erasure

## Suggested correction lifecycle

`DETECTED`
-> `UNDER_ANALYSIS`
-> `AMBIGUOUS` or `ROOT_CAUSE_PROPOSED`
-> `CORRECTION_PROPOSED`
-> `QUALIFYING`
-> `QUALIFIED` or `REJECTED`
-> `PROMOTED`
-> `ACTIVE`
-> `SUPERSEDED` / `REVOKED`

Additional terminal/exception states:

- `DUPLICATE`
- `DEAD_LETTERED`
- `BLOCKED_POLICY`
- `STALE_QUALIFICATION`

Transitions should be explicit and validated in code/database constraints where practical.

## Data model sketch

### incident

- id
- fingerprint
- first_seen_at
- last_seen_at
- occurrence_count
- severity
- source_type
- source_ref
- raw_input_digest
- normalized_summary
- status

### event

Append-only.

- id
- incident_id
- event_type
- actor/producer
- payload
- payload_digest
- occurred_at
- observed_at
- provenance
- idempotency_key

### root_cause_candidate

- id
- incident_id
- proposition
- evidence_refs
- confidence/support representation
- scope
- competing_explanations
- status

### correction

- id
- incident_id
- revision
- correction_type
- target
- scope
- payload
- supersedes_correction_id
- reversible
- status
- created_from_root_cause_id

### qualification

- id
- correction_id
- correction_revision
- suite/version
- exact_subject_digest
- result
- evidence
- started_at
- finished_at

A changed correction invalidates prior qualification unless the qualification explicitly covers the new exact subject.

### promotion

- id
- correction_id
- correction_revision
- policy_decision
- approved_by
- activated_at
- revoked_at
- activation_scope

### injection_binding

- id
- promoted_correction_id
- adapter
- selector
- priority
- conflict_policy
- expiry
- active

## Fingerprinting

Fingerprinting should normalize volatile values while retaining enough structural context to avoid grouping unrelated failures.

Possible inputs:

- exception/error class;
- normalized message template;
- operation/handler;
- call-site or stage;
- model/provider/tool;
- violated invariant;
- route;
- relevant schema/version.

Fingerprint algorithms must be versioned.

## Ambiguity

Ambiguity must be explicit. Suggested representation:

- top candidate;
- alternative candidates;
- support/confidence per candidate;
- decision margin;
- ambiguity reason;
- required missing evidence;
- resolver policy.

If uncertainty is material, route to clarification, additional evidence collection, human review, or bounded fallback. Do not silently choose a winner.

## Queue/concurrency model

For PostgreSQL-backed workers:

- claim work atomically;
- use `FOR UPDATE SKIP LOCKED` or a proven equivalent;
- keep lease/heartbeat semantics explicit if tasks can outlive transactions;
- use idempotency keys for externally visible effects;
- bound retry count;
- exponential/jittered backoff where appropriate;
- DLQ after exhaustion;
- isolate serialized work using a stable correction/fingerprint key when needed.

## Event/outbox model

Canonical correction history should be append-only.

For effects that must accompany state transitions, use a transactional outbox or equivalent so "DB commit succeeded, external publish failed" does not produce silent divergence.

## Handler/plugin contracts

Suggested families:

```text
Detector
Normalizer
Fingerprinter
Analyzer
AmbiguityResolver
RootCauseResolver
CorrectionGenerator
Qualifier
PolicyGate
Injector
Observer
StorageAdapter
```

Each should declare accepted input schema, output schema, side-effect class, idempotency behavior, retryability, timeout, provenance, and failure mode.

## Injection/adaptation targets

A correction may adapt future behavior without changing base model weights. Candidate activation surfaces:

- retrieved instruction/rule;
- prompt/context injection;
- negative example / positive exemplar;
- router preference;
- tool constraint;
- policy rule;
- handler selection;
- schema/validator;
- memory entry with provenance;
- evaluation gate;
- generated regression test.

The system should record which surface was used and measure recurrence after activation.

## Conflict handling

Multiple active corrections may conflict.

Require deterministic resolution using one or more of:

- explicit priority;
- narrower scope wins;
- newer superseding revision wins;
- policy arbitration;
- mark conflict and fail closed.

Never rely on incidental retrieval order.

## Recurrence/effectiveness

Track at minimum:

- recurrence count before/after activation;
- false-positive grouping;
- false-negative recurrence;
- correction-trigger rate;
- prevented/blocked attempts;
- regressions caused by correction;
- rollback/revocation events;
- stale corrections;
- unresolved ambiguity.

Do not call a correction "learned" merely because it was stored. Behavioral effect must be observed or qualified separately.
