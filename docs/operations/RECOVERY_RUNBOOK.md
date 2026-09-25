# Execution Recovery Runbook

Status: V0.1 LAUNCH CANDIDATE

This runbook applies to governed injector execution backed by `PostgresExecutionStore`.

## Recovery rule

Never infer an external effect from an exception, timeout, handler return, or process restart.

- **PREPARED** — no attempt is recorded. Resume only with the same exact idempotency key/effect through normal governed execution.
- **ATTEMPTED** — an attempt started. Do not execute again; call `ExecutionCoordinator.reconcile(operation_id)`.
- **AMBIGUOUS** — the attempt may have taken effect. Do not execute again; use adapter-specific readback via `reconcile()`.
- **VERIFIED** — do not execute again. If outcome persistence is missing, use `recover_outcome(operation_id)`.
- **FAILED** — terminal for that operation identity. Any later retry is a new operation and must pass current binding/authority checks.

## Startup procedure

1. Construct `PostgresExecutionStore` with connections bound to the trusted schema and configured runtime role.
2. Call `recoverable_operations()`.
3. Resume PREPARED operations only through their original governed request and idempotency key.
4. Reconcile ATTEMPTED and AMBIGUOUS operations; never redispatch their handlers.
5. Call `verified_outcome_gaps()`.
6. Recover each gap with `recover_outcome()`, which requires observed state to match the original VERIFIED readback digest.
7. Escalate any unavailable exact adapter/version or readback disagreement instead of guessing.

## Revocation during recovery

Currentness gates new execution, not historical readback. Revocation, expiry, or supersession blocks new attempts but does not erase the duty to reconcile effects already attempted.

## Reference-file adapter

`ReferenceFileInjector` is a qualification/example adapter, not a production memory system. It confines targets to `reference-file:<safe-key>`, rejects traversal, writes immutable versions and operation receipts, swaps the current pointer atomically, detects exact replay, verifies by readback, and can restore the immediately prior pointer when no newer effect supersedes it.

A rollback is itself an external write in a real host and must be governed separately.

## Stop conditions

Stop automatic recovery when the exact adapter/version is unavailable, a verified-state digest changes, an idempotency collision occurs, protected-effect authority evidence is absent, currentness cannot be checked, or trusted-schema/role assumptions cannot be verified.