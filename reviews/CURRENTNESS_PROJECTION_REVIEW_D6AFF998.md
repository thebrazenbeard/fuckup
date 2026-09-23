# F.U.C.K.U.P. Currentness Projection Hostile Review — d6aff998

Reviewed exact head: `d6aff998d1d51ca2af1f9a6d5cc053af3b136baa`

Disposition: `CHANGES_REQUIRED_ONE_DURABLE_AUTHORITY_GAP`

## Prior residuals are closed

At this exact head, the previously reported residuals are materially repaired and covered by committed qualification cases:

- PostgreSQL idempotent event replay now compares incident id, event type, payload, and effect digest before accepting same-key replay;
- a same-key/different-effect test with the same reused digest is committed;
- new correction revisions reset lifecycle state to `CORRECTION_PROPOSED`;
- terminal correction families cannot accept new revisions;
- live PostgreSQL tests cover both behaviors.

Those fixes are sound at source level.

## Remaining durable-authority gap — currentness projection fields are directly mutable

The runtime now relies on these columns as durable currentness authority:

```text
corrections.current_revision
corrections.status
```

They drive:

- promotion validation;
- supersession currentness;
- `active_injection_bindings`;
- revision insertion rules.

However, the migration defines no trigger preventing arbitrary UPDATE of those fields and no database role/privilege contract that removes direct UPDATE access from the application role.

### Concrete stale-binding reactivation

Assume correction C has:

- r1 promoted with an active binding;
- r2 later inserted, which correctly sets `current_revision=2` and `status='CORRECTION_PROPOSED'`.

The canonical view correctly hides the r1 binding because:

`c.current_revision != p.correction_revision`.

But any caller with ordinary UPDATE rights can issue conceptually:

```sql
UPDATE corrections
SET current_revision = 1,
    status = 'ACTIVE'
WHERE id = C;
```

Now the canonical `active_injection_bindings` predicate is true again for the stale r1 promotion.

This bypasses the revision insertion gate, stale-qualification protections, and the intended forward-only currentness model without modifying any append-only evidence.

The same class of direct mutation can also falsify `SUPERSEDED`, `REVOKED`, or `REJECTED` lifecycle state.

## Why this is different from ordinary internal mutation

The triggers themselves legitimately update `corrections.current_revision/status`.

That means the solution cannot simply make the whole table append-only.

The durable contract needs one of these explicit authority models:

### Option A — database privilege boundary

- application role cannot directly UPDATE `corrections.current_revision/status`;
- only guarded functions/triggers running under an authorized owner/security-definer path may mutate them;
- source controls GRANT/REVOKE expectations or installation SQL.

### Option B — protected mutation trigger

Add a trigger that rejects direct changes to derived currentness/status unless they originate from an explicit guarded transition mechanism.

This requires a safe, non-spoofable mechanism for authorized internal transitions.

### Option C — derive currentness rather than storing it publicly mutable

Derive current revision from append-only revision rows and derive effective lifecycle from immutable/append-only evidence where practical. This reduces mutable projection authority, though some materialized state may still need guarded writes.

## Related trust-boundary gap — canonical helper functions can be bypassed by direct table DML

The new `record_event_idempotent()` function has good semantics, but direct INSERT into `events` is still possible unless role privileges prohibit it.

Direct INSERT can provide an arbitrary `effect_digest` unrelated to payload. Unique idempotency key prevents duplicate-key aliasing after the fact, but the first stored semantic digest may still be false.

This is the same missing database authority boundary.

The source should explicitly say whether:
- application code is allowed direct table DML; or
- tables are internal persistence and writes must flow through guarded functions.

If guarded functions are the contract, enforce that in database privileges.

## Required regression/qualification cases

If using a restricted-role model, live qualification should create/use the intended application role and verify:

1. direct UPDATE of `corrections.current_revision` fails;
2. direct UPDATE of `corrections.status` fails;
3. guarded revision insertion still updates both fields correctly;
4. direct INSERT into guarded semantic tables such as `events` is denied if writes must use helper functions;
5. `record_event_idempotent()` remains callable by the application role;
6. stale binding cannot be reactivated through any permitted application-role mutation.

## Source-level status

All previously enumerated SQL/lifecycle semantic gaps are otherwise closed at this exact head.

I would mark the scoped source review PASS only after the database write-authority boundary is explicit and enforced, or after the project explicitly defines direct table mutation as trusted-internal-only and proves the runtime role cannot violate that assumption.

## Evidence ceiling

No live PostgreSQL execution is claimed here. This finding is visible from exact source: no GRANT/REVOKE/role setup or corrections projection mutation guard is present in the migration.
