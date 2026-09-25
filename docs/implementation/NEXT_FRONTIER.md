# Next Implementation Frontier

Status: UPDATED AFTER EXECUTION-INTEGRITY V2
Validated implementation cut: `1fb9e190eeb5974fdfc9c37a5547004793ddd6f4`

## What is now implemented

The review branch already contains the original vertical-slice foundations: incident/correction ledgers, fingerprinting/idempotency, explicit lifecycle states, ambiguity handling, qualification, policy gates, scoped promotion/bindings, worker retry/DLQ behavior, PostgreSQL authority separation, and recurrence summaries.

Execution Integrity V2 additionally adds:

- append-only per-occurrence evidence for deduplicated incidents;
- canonical effect-operation identity and idempotency collision detection;
- `PREPARED -> ATTEMPTED -> AMBIGUOUS/VERIFIED/FAILED` effect history;
- mandatory readback evidence before an ambiguous attempt can become verified;
- exact correction/scope/promotion/binding attribution for effectiveness observations;
- PostgreSQL persistence, guarded functions, runtime-role restrictions, and live qualification cases for those rules.

## Next bounded frontier: governed injector execution

The next useful slice is not another storage abstraction. It is the missing seam between an active injection binding and an actual adapter call.

Build one `ExecutionCoordinator`-style boundary that:

1. resolves exactly one active binding for a supplied selector;
2. resolves the registered injector without executing it implicitly;
3. creates an effect operation before any reversible/protected write;
4. executes only effects permitted by the caller's already-established authority;
5. records the attempt;
6. verifies the adapter result through an adapter-specific readback seam;
7. reconciles the operation to `VERIFIED`, `FAILED`, or `AMBIGUOUS`;
8. records an exact-subject outcome observation;
9. refuses blind retry when the prior attempt is ambiguous.

## Acceptance criteria

A testable end-to-end reference path should prove:

1. an active binding selects one injector deterministically;
2. no binding or conflicting bindings fail closed;
3. a pure/read-only handler does not manufacture write authority;
4. a reversible write is prepared before execution and verified afterward;
5. a simulated lost response leaves the operation ambiguous;
6. retry is blocked until readback reconciliation;
7. successful readback produces a bound effectiveness observation;
8. revocation or supersession prevents later application;
9. a changed correction revision cannot reuse stale qualification/binding evidence;
10. the full existing suite remains green.

## Deferred deliberately

Statistical causal claims, distributed transport, model-weight mutation, automatic deployment, automatic rollback, and cross-repository orchestration remain outside this frontier. They should be added only when a concrete consumer forces the requirement.