# SQL / Lifecycle Hostile Review Remediation — 2026-09-23

Source review artifact:
`review/sql-lifecycle-hostile-20260923@7e4fa91ee59a3093bb21e8c5b3f9ab3e3a5793d9`

Lead repair branch:
`build/fuckup-protocol-v1`

This document records source-level remediation only. It does not claim live PostgreSQL qualification.

## Finding-to-repair map

### 1. Stale/mismatched qualification could promote — repaired in source

- `correction_revisions` now has a unique exact tuple:
  `(correction_id, revision, subject_digest)`.
- `qualifications` now foreign-keys:
  `(correction_id, correction_revision, exact_subject_digest)`
  to that exact tuple.
- `corrections.current_revision` is maintained by guarded revision insertion.
- promotion validation locks the correction row and rejects non-current revision or mismatched digest.

### 2. FAIL qualification / arbitrary policy could promote — repaired in source

- promotion FK binds to qualification result and requires `qualification_result='PASS'`.
- `policy_decision` must be a JSON object containing `{"allow": true}`.
- policy name/version are persisted with the promotion.
- Python reference ledger independently evaluates the qualification suite before promotion.

### 3. Revoked promotion could remain injectable — repaired in source

- revocation is monotonic.
- revocation trigger deactivates associated bindings transactionally.
- canonical `active_injection_bindings` view excludes revoked, inactive, expired, stale-revision, and non-ACTIVE corrections.

### 4. Supersession underconstrained — repaired in source

- supersession now targets an exact correction revision.
- self-supersession is rejected.
- cross-incident supersession is rejected.
- target must be the superseded correction's current revision.
- recursive cycle detection rejects supersession cycles.
- supersession marks the prior correction SUPERSEDED and deactivates its exact active bindings.
- an outbox event is emitted in the same transaction.

### 5. Expired RUNNING lease unrecoverable — repaired in source

- `claim_worker_job()` can claim expired RUNNING work.
- `sql/claim_job.sql` is now only a thin invocation of the guarded function.

### 6. Retry budget not enforced — repaired in source

- row constraint enforces `attempts <= max_attempts`.
- claim path requires `attempts < max_attempts`.
- exhausted pending/retry/expired-running work is deterministically dead-lettered before claim.

### 7. Lease duration unbounded — repaired in source

- guarded claim rejects null, zero, negative, and >86400-second leases.

### 8. Worker lock/state combinations inconsistent — repaired in source

- RUNNING requires non-null owner, lock timestamp, and lease.
- all non-RUNNING states require those fields to be null.

### 9. Idempotency key not bound to effect — repaired in reference semantics / schema contract

- events and worker jobs pair idempotency key presence with effect digest presence.
- Python ledger computes an effect digest over incident + event type + payload.
- same key + same effect returns the existing event.
- same key + different effect raises `IdempotencyCollisionError`.

A future PostgreSQL helper should provide the same convenient "same effect returns existing row" behavior instead of relying only on unique-key collision at raw INSERT level.

### 10. Outbox existed without atomic path — repaired for key lifecycle effects

Transactional triggers now write outbox records for:
- promotion;
- revocation;
- supersession.

This establishes the invariant for the consequential lifecycle effects implemented so far. Future external-effect transitions must use the same pattern or an equivalent transactional path.

### 11. Promotion history mutable — repaired in source

- promotion DELETE is rejected.
- all fields except `revoked_at` are immutable after activation.
- revocation is `NULL -> timestamp` only and can occur once.

### 12. Cross-incident root-cause provenance allowed — repaired in source

Correction revision insertion rejects a `created_from_root_cause_id` whose incident differs from the correction family's incident.

## Added regression coverage

- `tests/test_ledger.py`
  - same-effect idempotency replay;
  - different-effect idempotency collision;
  - failed qualification cannot promote despite an allow policy.
- `tests/test_sql_contract.py`
  - exact-digest FK contract;
  - PASS + allowed-policy promotion gate;
  - canonical active-binding filtering;
  - supersession constraints;
  - expired-lease/retry-budget semantics;
  - worker state/lock consistency;
  - effect-bound idempotency fields;
  - immutable/monotonic promotion history;
  - transactional lifecycle outbox hooks;
  - same-incident root-cause provenance.

## Qualification ceiling

Still unproven until a live PostgreSQL run:
- migration parses/executes on the target PostgreSQL version;
- trigger/function behavior is accepted exactly as written;
- two-worker contention behaves as intended;
- worker crash + lease expiry is safely reclaimed;
- retry exhaustion dead-letters correctly under contention;
- stale qualification and mismatched digest are rejected by the live database;
- revocation/supersession immediately disappear from the active-binding projection;
- outbox writes are atomic with lifecycle mutation.

The hostile-review lane should re-review the exact repaired head before this remediation is considered source-level closed.
