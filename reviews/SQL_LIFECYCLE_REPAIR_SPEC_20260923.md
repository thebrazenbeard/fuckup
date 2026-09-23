# F.U.C.K.U.P. SQL Lifecycle Repair Specification — 2026-09-23

Reviewed integration subject: `build/fuckup-protocol-v1@3a267fa01f786467ecbee4853ede4075cbb08f8a`

This document turns the hostile SQL/lifecycle review into an implementation-ready contract. It does **not** modify the lead-owned migration, queue SQL, or Python core. It is a repair specification and adversarial test plan.

## Repair objective

Make the PostgreSQL durable contract enforce the same safety claims the Python reference layer is trying to enforce:

- only the current correction revision may be promoted;
- qualification evidence must bind to the exact revision digest;
- only a passing qualification may promote;
- promotion requires an explicit allow decision;
- revoked/expired/superseded corrections cannot remain effective through active injection bindings;
- expired worker leases are recoverable;
- retry budgets cannot be exceeded;
- idempotency collisions cannot silently alias different effects;
- historical evidence cannot be rewritten after activation.

## R1 — Bind qualification to exact revision digest

### Required DDL shape

Add a unique key on the exact correction subject:

```sql
ALTER TABLE correction_revisions
    ADD CONSTRAINT correction_revisions_exact_subject_uq
    UNIQUE (correction_id, revision, subject_digest);
```

Then bind qualification to all three values:

```sql
ALTER TABLE qualifications
    DROP CONSTRAINT qualifications_correction_id_correction_revision_fkey;

ALTER TABLE qualifications
    ADD CONSTRAINT qualifications_exact_subject_fk
    FOREIGN KEY (correction_id, correction_revision, exact_subject_digest)
    REFERENCES correction_revisions(correction_id, revision, subject_digest);
```

Expected effect: a qualification cannot claim digest B while pointing at revision whose canonical digest is A.

### Adversarial test

Insert revision `(c1, 1, digest-a)`. Attempt qualification `(c1, 1, digest-b)`. Expect FK rejection.

## R2 — Guard promotion atomically

A plain FK from promotion to qualification is insufficient. Promotion needs a single durable gate.

### Recommended mechanism

Use a `BEFORE INSERT` trigger or a security-definer function that performs all promotion checks while locking the correction family.

Required checks inside one transaction:

1. lock the correction row/family;
2. compute or read the current revision;
3. require requested revision == current revision;
4. load the referenced qualification;
5. require qualification correction/revision match;
6. require qualification digest match current revision digest;
7. require qualification result == `PASS`;
8. require `policy_decision ->> 'allow' = 'true'`;
9. require non-empty activation scope;
10. require non-empty rollback condition;
11. reject promotion if the correction is already superseded/revoked under the chosen lifecycle model.

### Minimal trigger skeleton

```sql
CREATE FUNCTION enforce_promotion_invariants() RETURNS trigger AS $$
DECLARE
    current_revision integer;
    canonical_digest text;
    qualification_result text;
BEGIN
    SELECT max(cr.revision)
      INTO current_revision
      FROM correction_revisions cr
     WHERE cr.correction_id = NEW.correction_id;

    IF current_revision IS NULL OR NEW.correction_revision <> current_revision THEN
        RAISE EXCEPTION 'promotion requires current correction revision';
    END IF;

    SELECT cr.subject_digest
      INTO canonical_digest
      FROM correction_revisions cr
     WHERE cr.correction_id = NEW.correction_id
       AND cr.revision = NEW.correction_revision;

    SELECT q.result
      INTO qualification_result
      FROM qualifications q
     WHERE q.id = NEW.qualification_id
       AND q.correction_id = NEW.correction_id
       AND q.correction_revision = NEW.correction_revision
       AND q.exact_subject_digest = canonical_digest;

    IF qualification_result IS DISTINCT FROM 'PASS' THEN
        RAISE EXCEPTION 'promotion requires current passing exact-subject qualification';
    END IF;

    IF coalesce((NEW.policy_decision ->> 'allow')::boolean, false) IS NOT TRUE THEN
        RAISE EXCEPTION 'promotion requires policy allow=true';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

This skeleton still needs final locking/currentness semantics before production use. It is included to make the required checks explicit, not as a claim of production readiness.

### Adversarial tests

Reject each independently:

- stale revision 1 after revision 2 exists;
- qualification for another correction;
- matching correction/revision but wrong digest;
- `FAIL` qualification;
- missing `allow`;
- `allow=false`;
- empty activation scope;
- empty rollback condition.

## R3 — Canonical effective-binding projection

Adapters should not invent their own currentness filters.

Create one canonical view/function that is the only supported read surface for effective injection bindings.

### Minimum eligibility

A binding is effective only when:

- `injection_bindings.active = true`;
- `expires_at IS NULL OR expires_at > now()`;
- linked promotion has `revoked_at IS NULL`;
- linked promotion still refers to the current correction revision;
- linked correction/promotion has not been superseded under the chosen lifecycle model.

Illustrative view:

```sql
CREATE VIEW active_injection_bindings AS
SELECT ib.*
FROM injection_bindings ib
JOIN promotions p ON p.id = ib.promotion_id
WHERE ib.active = true
  AND (ib.expires_at IS NULL OR ib.expires_at > now())
  AND p.revoked_at IS NULL
  AND p.correction_revision = (
      SELECT max(cr.revision)
      FROM correction_revisions cr
      WHERE cr.correction_id = p.correction_id
  );
```

If supersession is represented separately, join/filter that state here too.

### Adversarial tests

A binding disappears from the canonical read surface after:

- promotion revocation;
- binding expiry;
- `active=false`;
- creation of a newer revision when old-revision bindings are not permitted;
- supersession.

## R4 — Define supersession as an edge with invariants

The current `supersedes_correction_id` column is too weak for durable semantics.

Preferred model: explicit supersession relation carrying exact subject identity.

Example shape:

```text
correction_supersessions
- superseding_correction_id
- superseding_revision
- superseded_correction_id
- superseded_revision
- created_at
- reason/provenance
```

Required invariants:

- no self-edge to the same correction/revision;
- same-incident only unless an explicit transfer mode is recorded;
- no cycle;
- referenced revisions must exist;
- activation of superseding correction makes superseded bindings ineligible through the canonical active-binding read;
- historical rows remain intact.

### Adversarial tests

Reject:

- `c1:r1 -> c1:r1`;
- `c1 -> c2 -> c1` cycle;
- cross-incident edge without explicit transfer semantics;
- nonexistent revision.

## R5 — Make revocation monotonic and history-preserving

Historical promotion identity, correction reference, qualification reference, activation scope, rollback condition, and policy decision should not be mutable after insert.

Two acceptable models:

1. protect immutable columns with an update trigger and permit only `revoked_at: NULL -> timestamp`; or
2. make promotions fully append-only and create a separate append-only revocation table/event.

If using mutable `revoked_at`, enforce:

- cannot clear revocation;
- cannot change an existing revocation timestamp;
- cannot set revocation before activation time.

## R6 — Repair worker lease recovery

The current claimant cannot recover expired `RUNNING` jobs.

Do not overload claim logic ambiguously. Prefer an explicit recovery transition followed by normal claim.

### Recovery transaction

Conceptual behavior:

```sql
UPDATE worker_jobs
SET status = CASE
        WHEN attempts >= max_attempts THEN 'DEAD_LETTERED'
        ELSE 'RETRY'
    END,
    locked_by = NULL,
    locked_at = NULL,
    lease_expires_at = NULL,
    last_error = jsonb_build_object('kind', 'lease_expired'),
    updated_at = now()
WHERE status = 'RUNNING'
  AND lease_expires_at <= now();
```

Run this as a bounded/recoverable worker maintenance operation or fold the same semantics into a guarded claim procedure.

### Claim eligibility

Claim must require:

```sql
status IN ('PENDING', 'RETRY')
AND available_at <= now()
AND attempts < max_attempts
```

Then increment attempts atomically with the claim.

### Adversarial tests

- worker A claims job;
- lease expires;
- recovery converts it to RETRY if budget remains;
- worker B can claim it;
- final expired attempt at max budget becomes DEAD_LETTERED;
- DEAD_LETTERED job is never claimable.

## R7 — Add worker relational state constraints

At minimum:

```sql
CHECK (attempts <= max_attempts)
```

and state-dependent lock consistency.

One possible shape:

```sql
CHECK (
    (status = 'RUNNING'
      AND locked_by IS NOT NULL
      AND locked_at IS NOT NULL
      AND lease_expires_at IS NOT NULL)
 OR (status <> 'RUNNING'
      AND locked_by IS NULL
      AND locked_at IS NULL
      AND lease_expires_at IS NULL)
)
```

If a future state intentionally preserves lease metadata, encode that explicitly rather than weakening the invariant globally.

Validate `lease_seconds > 0` in the guarded claim function/procedure.

## R8 — Bind idempotency key to effect identity

A repeated idempotency key is valid only when it represents the same effect.

For events, calculate/store an effect digest over at least:

- incident id;
- event type;
- canonical payload digest;
- side-effect target where applicable.

Then use a uniqueness rule such as:

```text
idempotency_key -> exact effect digest
```

On duplicate key:

- same digest: return/read existing effect;
- different digest: raise `IDEMPOTENCY_COLLISION`.

Do the same for outbox/consequential jobs.

### Adversarial test

Submit key `K` for effect A, then key `K` for effect B. Expect hard collision, not duplicate success.

## R9 — Turn the outbox table into an invariant

For every state transition that requires external publication, the domain mutation and outbox insert must happen in the same database transaction.

Acceptance test must demonstrate:

- transaction rollback leaves neither domain mutation nor outbox row;
- successful transaction leaves both;
- publisher crash after commit leaves unpublished outbox row for retry;
- repeated publish uses outbox idempotency key and does not duplicate the external effect.

The mere presence of the table is not sufficient evidence.

## R10 — Same-incident provenance guard

If `created_from_root_cause_id` is intended to establish causal lineage, require its root-cause candidate to belong to the same incident as the correction family.

If cross-incident transfer is a feature, represent it as a different explicit relation with transfer provenance rather than silently accepting a cross-incident root-cause FK.

## Suggested database qualification suite

After source repair and when PostgreSQL is available, execute all of these against a real server:

1. migration applies from an empty database;
2. migration rollback/reapply behavior is documented;
3. exact-digest FK rejection;
4. stale-revision promotion rejection;
5. FAIL qualification promotion rejection;
6. policy allow=false rejection;
7. revocation removes binding from canonical effective view;
8. supersession removes prior binding from effective view without deleting history;
9. two concurrent workers claim distinct jobs under `SKIP LOCKED`;
10. one worker crash + lease expiry + recovery + second worker claim;
11. retry budget exhaustion -> DEAD_LETTERED;
12. zero/negative lease rejected;
13. idempotency same-key/same-effect succeeds idempotently;
14. same-key/different-effect hard-fails;
15. outbox state mutation and row creation are atomic;
16. promotion/revision/qualification historical mutation is rejected;
17. root-cause cross-incident lineage is rejected unless explicit transfer semantics are used.

## Integration order

Implement in this order to minimize transient contradictions:

1. exact-subject qualification FK;
2. promotion gate;
3. effective-binding projection;
4. revocation immutability/monotonicity;
5. worker constraints + recovery + retry budget;
6. supersession relation/currentness;
7. idempotency effect binding;
8. transactional outbox path;
9. same-incident provenance constraints;
10. live PostgreSQL qualification.

## Evidence ceiling

This repair specification is derived from exact source at `3a267fa01f786467ecbee4853ede4075cbb08f8a`. It is an implementation contract and test plan, not proof that any proposed SQL snippet has executed successfully on PostgreSQL.
