# F.U.C.K.U.P. SQL/Lifecycle Exact-Head Re-Review — f865f14b

Reviewed subject: `build/fuckup-protocol-v1@f865f14baa9844eedfdff47eaa9f04243ad96f7c`

Prior review artifact: `reviews/SQL_LIFECYCLE_HOSTILE_REVIEW_20260923.md`

Repair specification: `reviews/SQL_LIFECYCLE_REPAIR_SPEC_20260923.md`

## Summary

The hardening commit materially improves the durable PostgreSQL contract. The broad original finding set is reduced, but the exact head is not yet clear.

Disposition: `CHANGES_REQUIRED_NARROWED`.

## Closed or substantially closed

The following prior findings are materially repaired in the migration:

- qualification digest is now bound to the exact correction revision through a composite FK;
- promotion requires a PASS qualification row through the FK/result tuple;
- promotion policy JSON must contain `allow: true`;
- promotion requires non-empty activation scope and rollback condition;
- promotion validates the current correction revision and exact digest;
- correction revision insertion is serialized per correction family and must advance by one revision;
- root-cause lineage is checked to remain on the same incident;
- self-supersession and detected supersession cycles are rejected;
- revocation is monotonic at the promotion row and historical promotion fields are otherwise immutable;
- revocation deactivates bindings and the canonical `active_injection_bindings` view excludes revoked/expired/non-current/superseded state;
- worker rows now enforce `attempts <= max_attempts` and RUNNING lock/lease consistency;
- `claim_worker_job()` validates worker ID and positive bounded lease duration, recovers expired RUNNING jobs, respects retry budget, and dead-letters exhausted work;
- promotion/supersession/revocation now emit outbox rows in the same transaction as the domain mutation.

These are real improvements, not cosmetic changes.

## Residual blocker 1 — stale supersession revision can retire the whole current family

`validate_correction_revision_insert()` confirms that the referenced `supersedes_correction_id/supersedes_revision` exists and belongs to the same incident, but it does **not** require `supersedes_revision` to equal the superseded correction family's current revision.

Then `apply_correction_revision_insert()` marks the entire superseded correction row:

```sql
UPDATE corrections
SET status = 'SUPERSEDED'
WHERE id = NEW.supersedes_correction_id;
```

Therefore:

1. correction B has revisions 1 and 2, with revision 2 current/active;
2. correction A inserts a revision declaring it supersedes `B:r1`;
3. the trigger accepts the stale revision reference;
4. the entire B correction family becomes `SUPERSEDED`;
5. the canonical active-binding view hides B:r2 as well.

That is a stale-reference family kill switch.

### Required repair

Either:

- require `NEW.supersedes_revision = corrections.current_revision` for the target family at supersession time, while locking that target correction row; or
- redefine supersession explicitly as revision-scoped and stop marking the entire correction family superseded.

Add an adversarial test where B:r2 is current and A attempts to supersede B:r1.

## Residual blocker 2 — two contradictory worker claim APIs remain shipped

The migration introduces the safer `claim_worker_job(p_worker_id, p_lease_seconds)` function.

However `sql/claim_job.sql` remains byte-for-byte the old query. It still:

- selects only PENDING/RETRY, never expired RUNNING;
- does not pre-dead-letter exhausted jobs;
- does not check `attempts < max_attempts`;
- does not validate positive/bounded lease duration.

The new table constraint prevents attempts from exceeding max, but the old script can now fail with a constraint violation rather than performing the intended deterministic DLQ transition.

This leaves two source-controlled claim semantics, one safe and one stale.

### Required repair

Make `sql/claim_job.sql` invoke the canonical function, or replace its contents with the same guarded semantics. Prefer one authoritative claim path.

Add a source test asserting the shipped helper cannot drift from the canonical database function.

## Residual blocker 3 — supersession target currentness is not locked

The revision insert trigger locks the **new/superseding** correction row:

```sql
FROM corrections
WHERE id = NEW.correction_id
FOR UPDATE;
```

It reads the superseded correction row without locking it.

Even after adding a current-revision equality check, that target row should be locked while validating/applying supersession, otherwise a concurrent revision of the target can change currentness between validation and the AFTER trigger.

Required: lock the target correction row during supersession validation and use the locked current revision/status for the decision.

## Residual blocker 4 — multiple promotions make correction-level REVOKED ambiguous

The schema allows multiple promotion rows for the same correction revision; there is no uniqueness constraint preventing them.

On revoking **one** promotion, `promotion_revocation_effects()` sets the whole correction status to `REVOKED` when that revision is current:

```sql
UPDATE corrections
SET status = 'REVOKED'
WHERE id = NEW.correction_id
  AND current_revision = NEW.correction_revision;
```

The canonical binding view excludes corrections with status REVOKED, so revoking one scoped promotion can disable unrelated non-revoked promotions for the same correction revision.

Choose one model explicitly:

- **single promotion per correction revision**: enforce uniqueness, making correction-level REVOKED coherent; or
- **multiple scoped promotions**: correction status must remain ACTIVE while any eligible non-revoked promotion remains, and revocation should only remove the revoked promotion's bindings.

Add a two-promotion/one-revoked adversarial test.

## Residual blocker 5 — revocation timestamp is monotonic but not temporally valid

`protect_promotion_mutation()` allows a first non-null `revoked_at`, but does not require:

`NEW.revoked_at >= OLD.activated_at`.

A promotion can therefore be recorded as revoked before it was activated.

This is mainly provenance integrity rather than an activation bypass, but it should be constrained.

## Residual blocker 6 — original Python promotion/validation bypasses remain unchanged

The hardening commit changes only `migrations/0001_core.sql`. These exact source blobs remain unchanged:

- `src/fuckup_protocol/models.py@2789baaa...`
- `src/fuckup_protocol/validation.py@6030d281...`
- `src/fuckup_protocol/policy.py@9e8d7d54...`
- `src/fuckup_protocol/ledger.py@fe5640de...`

Therefore earlier exact-source findings remain live in the reference/runtime API:

1. `ValidationReport` does not carry correction id/revision/digest, so a passing report can be paired with another correction in `PromotionContext`.
2. callers may pass `required_kinds=frozenset()`, producing a passing report without the canonical suite.
3. unknown failing test kinds are ignored rather than failing closed.
4. `InMemoryLedger.promote()` trusts a caller-supplied `PolicyDecision(allow=True)` and does not itself verify canonical validation.
5. frozen correction dataclasses contain mutable mapping payloads, so content can change after digest computation.
6. in-memory event idempotency still returns an existing event for same key + different payload without collision detection.

The database is now stricter than the reference layer. That split should not be left implicit.

## Residual blocker 7 — no tests were added for the SQL hardening commit

The exact commit from `3a267fa...` to `f865f14b...` changes only `migrations/0001_core.sql`.

No PostgreSQL contract tests, migration tests, or static regression tests were added in that commit, and no live PostgreSQL execution evidence is available in this review environment.

The migration may be directionally correct while still containing syntax, trigger-order, or concurrency defects that source inspection cannot prove away.

## Partial findings

### Idempotency

The migration now requires idempotency key and effect digest to appear together for events/jobs and keeps unique idempotency keys. This is safer than before.

It does not yet provide a canonical "same key + same effect = return existing; same key + different effect = named collision" database operation. Direct duplicate inserts fail uniquely regardless of whether the effect matches.

The Python ledger still silently aliases same key + different event payload.

### Transactional outbox

Promotion, supersession, and revocation now write outbox rows transactionally through triggers. That closes the specific "table only" gap for those transitions.

Other future externally published transitions still need to use the same invariant rather than treating the outbox table as globally sufficient.

### corrections.current_revision/status mutability

The migration relies on `corrections.current_revision` and `corrections.status` for durable currentness, but ordinary UPDATE protection for those columns is not defined.

If application roles have unrestricted table UPDATE, direct writes can corrupt currentness/state. A later privilege model or guarded mutation API should make these derived fields non-publicly mutable.

## Re-review acceptance criteria

Before this review lane can mark the SQL/lifecycle surface clear:

1. supersession must bind to the target family's locked current revision, or become explicitly revision-scoped;
2. stale `sql/claim_job.sql` must be removed/deprecated/repointed to the canonical claim function;
3. multiple-promotion revocation semantics must be made deterministic;
4. revocation timestamp must not precede activation;
5. Python reference promotion/validation/idempotency invariants must be reconciled with the stricter database contract;
6. tests must cover the new durable invariants;
7. live PostgreSQL qualification should execute the migration and concurrency cases when a PostgreSQL runtime is available.

## Evidence ceiling

This is an exact-source re-review of `f865f14baa9844eedfdff47eaa9f04243ad96f7c`. It does not claim the migration has executed successfully on PostgreSQL.
