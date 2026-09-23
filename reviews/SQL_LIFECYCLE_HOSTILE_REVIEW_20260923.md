# F.U.C.K.U.P. SQL / Lifecycle Hostile Review — 2026-09-23

Reviewed repository: `thebrazenbeard/fuckup`  
Exact subject: `eac03ec761c5252f889522b5bb5379e2820db808`  
Lead integration PR: #1  
Review lane: `review/sql-lifecycle-hostile-20260923`

This review is source-level only. PostgreSQL was not available in the current execution environment, so no migration or concurrency claim below is presented as live-database qualification.

## Disposition

`CHANGES_REQUIRED` for durable promotion/currentness and worker recovery semantics.

The design direction is sound, but the database contract currently permits states that the Python reference ledger rejects. The highest-risk issue is that "exact revision qualification" is enforced in Python but not by the PostgreSQL schema.

## P0 — PostgreSQL permits stale or mismatched qualification promotion

The `qualifications` table references `correction_revisions(correction_id, revision)`, but `exact_subject_digest` is an unconstrained text column. Nothing requires:

`qualifications.exact_subject_digest = correction_revisions.subject_digest`.

A row can therefore reference a real correction revision while claiming any digest.

The schema also has no current-revision pointer or constraint. After revision 2 exists, a qualification for revision 1 remains eligible for a promotion row because `promotions` only requires a matching qualification tuple.

This diverges from `InMemoryLedger.promote()`, which rejects promotion unless the requested revision equals `family.current.revision`.

### Required invariant

A database promotion must bind atomically to:
- the exact correction family;
- the current correction revision;
- the exact subject digest of that revision;
- a qualifying result that is allowed for promotion.

Do not rely on callers to reconstruct those invariants correctly.

## P0 — Database promotion does not require a passing qualification or allowed policy

`promotions` has foreign keys into `qualifications`, but no constraint requires `qualifications.result = 'PASS'`.

Likewise, `policy_decision` is arbitrary JSONB. The schema does not require an `allow=true` decision or a particular policy/version/provenance binding.

At the SQL contract level, a `FAIL` qualification can therefore be referenced by a promotion row, and `policy_decision` may be empty or contradictory.

### Required invariant

Promotion should be possible only through a guarded function/procedure or equivalent transaction that verifies qualification result, current revision, exact digest, policy decision, and activation/rollback requirements together.

## P0 — Revocation does not disable injection bindings

`promotions.revoked_at` can be set while related `injection_bindings.active` rows remain true.

The schema contains no trigger, check, view, or activation query proving that a revoked promotion cannot still be selected for injection.

This violates the handoff requirement that rollback/revocation state be preserved and operationally meaningful.

### Required invariant

The active-binding read contract must exclude:
- revoked promotions;
- expired bindings;
- inactive bindings;
- stale/superseded correction revisions.

Prefer a canonical active-binding projection/view or guarded query rather than requiring every adapter to remember all filters independently.

## P1 — Supersession relation is underconstrained

`correction_revisions.supersedes_correction_id` is a plain foreign key to `corrections(id)`.

The current schema permits:
- self-supersession;
- superseding a correction belonging to a different incident;
- arbitrary cycles between correction families;
- supersession without deactivating/revoking prior active promotion/bindings.

The architecture says supersession is not erasure, but it still needs deterministic operational semantics.

### Required invariant

At minimum define and enforce:
- whether supersession is same-incident only;
- whether self/cyclic supersession is forbidden;
- which exact prior revision/promotion is superseded;
- how active bindings from the superseded correction become ineligible.

## P1 — Worker lease recovery is absent from the SQL claimant

`sql/claim_job.sql` only selects:

`status IN ('PENDING', 'RETRY')`.

A worker that claims a job and dies leaves it in `RUNNING`. Even after `lease_expires_at`, that row is never selected by this query.

The Python job model contains `recover_expired_lease()`, so the source currently has two different queue semantics.

### Required invariant

Either:
1. make the claim transaction reclaim expired `RUNNING` rows safely, or
2. add a separate, source-controlled lease-reaper transition and prove the claimant composes with it.

## P1 — Retry budget is not enforced by PostgreSQL claim semantics

The claim query increments `attempts` but has no `attempts < max_attempts` condition.

The table checks `attempts >= 0` and `max_attempts > 0`, but does not check `attempts <= max_attempts`.

Therefore direct SQL state can exceed the configured retry budget even though the Python `JobState` rejects it.

### Required invariant

Database and Python retry semantics should agree. Exhausted work must become ineligible for claim and transition deterministically to `DEAD_LETTERED` or another explicit terminal state.

## P1 — Lease duration itself is not bounded

`:lease_seconds` is concatenated into an interval without a source-level positive-range guard.

Zero or negative leases create immediately expired or already-expired `RUNNING` jobs.

Validate lease duration before/inside the claim operation.

## P1 — Worker row state is not relationally consistent

The schema permits combinations such as:
- `RUNNING` with null `locked_by` or null `lease_expires_at`;
- `PENDING` with a non-null lock owner;
- terminal jobs with live leases.

If these columns drive recovery and currentness, encode the state-dependent constraints or funnel transitions through guarded functions.

## P1 — Event/job idempotency keys detect collisions but do not prove same effect

Unique indexes prevent duplicate keys, which is useful, but source semantics do not bind an idempotency key to an effect digest.

The in-memory ledger is even looser: same key with different incident/type/payload returns the original event as a duplicate.

For consequential operations, same key + different effect should be a hard collision, not silently accepted idempotency.

## P2 — Outbox table does not by itself establish a transactional outbox

The architecture requires an outbox or equivalent so state commit and external publish cannot silently diverge.

The migration creates an `outbox` table, but there is no trigger/procedure/application path in this exact source proving that relevant state transitions insert the outbox record in the same transaction.

The table is infrastructure, not yet the invariant.

## P2 — Append-only scope is partial

Append-only triggers protect:
- `events`;
- `correction_revisions`;
- `qualifications`.

But promotion identity/policy fields are freely mutable, not just `revoked_at`. A caller can rewrite the historical promotion record after activation.

If promotions are evidence-bearing historical facts, immutable fields should be protected and revocation should be monotonic (`NULL -> timestamp` only) or modeled as an append-only revocation event/table.

## P2 — Cross-incident provenance link is unconstrained

`created_from_root_cause_id` can point to a root-cause candidate from a different incident than the correction family.

If cross-incident correction transfer is desired, it should be explicit and provenance-bearing. If not, enforce same-incident lineage.

## Recommended repair order

1. Add regression/contract tests proving stale revision and mismatched digest cannot promote.
2. Add database promotion gate that requires current exact revision + exact digest + PASS qualification + allowed policy.
3. Define one canonical active-binding read contract that excludes revoked/expired/inactive/superseded state.
4. Repair expired-lease recovery and retry-budget enforcement in SQL.
5. Add state-dependent worker constraints or guarded transition functions.
6. Define supersession identity/acyclicity/currentness semantics.
7. Make promotion history immutable except for a monotonic revocation path.
8. Bind idempotency keys to effect identity/digest.
9. Wire actual state transitions to the transactional outbox in the same transaction.
10. Only then execute the migration against PostgreSQL and test real two-worker contention, crash/lease expiry, retry exhaustion, stale qualification, supersession, and revocation.

## Qualification ceiling

This review establishes source-level counterexamples and contract gaps only. It does not establish that PostgreSQL accepts the migration, that concurrent execution reproduces the predicted behavior, or that repaired SQL is correct. Those require a live PostgreSQL qualification run.
