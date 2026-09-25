# Execution Integrity V2 Design

Status: IMPLEMENTATION CANDIDATE
Base: `build/fuckup-protocol-v1@ff46bcf822a89701201e6153be923239814e5b61`
Working branch: `build/portfolio-integrity-v2-20260925`

## Problem

The current runtime already has strong correction-version qualification, policy gating, PostgreSQL authority separation, retry/DLQ mechanics, and scoped promotion. The next material weakness is what happens around repeated observations and consequential adapter effects.

Three failure classes remain under-specified:

1. duplicate incidents increment a counter but do not preserve every occurrence as durable evidence;
2. an adapter effect can become ambiguous after an attempt, but the core has no portable PREPARED/ATTEMPTED/VERIFIED journal that forbids blind redispatch;
3. effectiveness observations are not bound to one exact correction/promotion/binding subject, so unrelated observations can be accidentally aggregated.

## Design

### 1. Incident occurrences are append-only evidence

Every accepted incident submission emits an occurrence record, including duplicates. The incident remains the deduplicated aggregate keyed by fingerprint/version, while each occurrence preserves an immutable payload digest, observation time, optional source reference, and ordinal.

This keeps deduplication from becoming evidence erasure.

### 2. Consequential effects use an operation journal

Add an explicit operation identity with canonical effect digest and idempotency key. Operation history is append-only and transitions through:

`PREPARED -> ATTEMPTED -> VERIFIED | FAILED | AMBIGUOUS`

A PREPARED operation may be attempted once. An ATTEMPTED or AMBIGUOUS operation must be reconciled by readback before retry. VERIFIED and FAILED are terminal for that operation identity. Reusing an idempotency key for a different effect is a hard collision.

The journal records claims about attempts and verification. It does not pretend a receipt proves an external effect unless readback evidence is supplied.

### 3. Effectiveness is exact-subject bound

Outcome observations gain a subject identity containing correction id/revision, promotion id, binding id, and a canonical scope digest. Summarization rejects a mixed-subject observation set rather than producing a misleading aggregate.

Existing baseline/active rate logic remains intentionally simple; this change fixes attribution before adding statistical sophistication.

### 4. PostgreSQL mirrors the same semantics

Migration `0004_execution_integrity.sql` adds:

- `incident_occurrences` as append-only occurrence evidence;
- `effect_operations` for immutable operation identity/effect digest/idempotency;
- `effect_operation_events` for append-only lifecycle events;
- guarded functions for preparing, recording an attempt, and reconciling an operation;
- database constraints that reject illegal lifecycle sequences and idempotency collisions;
- runtime-role grants limited to guarded execution paths.

No deployment or live migration execution is implied by source presence.

### 5. Donor-mechanism discipline

This design reimplements mechanisms rather than copying donor code. Public portfolio concepts informing it include:

- WIP: effect ambiguity and prepare/attempt/readback recovery;
- Project Runner: exact operation identity, fencing/precondition discipline, and post-write verification;
- DriftGuard: exact-subject admission and fail-closed missing evidence;
- Roots / Temporal / Ingest: chronology, provenance, immutable evidence identity, and deterministic digests;
- Vera Mono: request/authority/attempt/effect/verification separation;
- CCB Base / VeraMesh: idempotency, receipt boundaries, leases, and transport-vs-authority separation.

The repository remains the semantic owner of corrective learning; donor systems do not become runtime dependencies.

## Non-goals

This slice does not add model-weight mutation, deployment automation, statistical causal inference, a universal orchestration framework, cross-repository execution, or a new transport protocol.

## Acceptance evidence

The slice is acceptable only if tests prove:

- every duplicate incident still creates a distinct immutable occurrence record;
- occurrence ordinals are monotonic per incident;
- one idempotency key cannot identify two effects;
- a prepared operation can become attempted and then verified;
- an attempted/ambiguous operation cannot be blindly attempted again;
- reconciliation can mark an ambiguous operation verified or failed with evidence;
- terminal operations cannot be reopened;
- mixed effectiveness subjects are rejected;
- PostgreSQL contract tests cover the new schema/functions and privilege boundary;
- the existing full qualification suite remains green.
