# F.U.C.K.U.P. PostgreSQL Qualification Harness Re-Review — 7348091c

Reviewed exact head: `7348091cde837b9562cc7eeac387a163a8e1ccd6`

Disposition: `HARNESS_GOOD / SOURCE_RESIDUALS_UNCHANGED`

## What this head adds

This head adds an opt-in live PostgreSQL qualification harness:

- optional dependency group `postgres-test`;
- `tests/postgres/test_live_qualification.py`;
- isolated per-test schema creation/drop;
- migration application;
- exact digest / stale revision / FAIL qualification / policy rejection cases;
- binding visibility after revocation/supersession;
- two-connection `SKIP LOCKED` contention;
- lease recovery and retry exhaustion;
- lease bound rejection;
- event idempotency replay/collision;
- outbox rollback atomicity;
- historical promotion mutation rejection;
- cross-incident root-cause rejection;
- revocation-time validity.

The harness is correctly dormant unless `FUCKUP_TEST_DATABASE_URL` is explicitly supplied.

No workflow run is attached to this exact head, so the harness exists but has not been executed by GitHub Actions evidence.

## Residual 1 remains — same key + different effect + reused digest is not tested or blocked

The exact migration blob is unchanged from the prior reviewed source.

`record_event_idempotent()` still treats caller-provided `p_effect_digest` as the sole semantic equality proof on replay.

The new live test `test_14_same_idempotency_key_different_effect_fails` changes the supplied digest from `sha256:a` to `sha256:b`. That proves "same key, different supplied digest" fails.

It does **not** prove "same key, different actual effect, same reused supplied digest" fails.

Adversarial case still accepted by source:

1. write key K with effect A and supplied digest X;
2. call again with key K and a different incident/type/payload B;
3. deliberately or accidentally reuse supplied digest X;
4. function sees `existing.effect_digest = p_effect_digest`;
5. function returns the old event instead of detecting the semantic collision.

### Required repair

Do not trust caller-provided digest as the sole authority for effect identity.

Either:
- compute canonical effect identity inside PostgreSQL from authoritative effect fields; or
- compare authoritative effect fields directly against the stored event before accepting replay.

### Required test

Hold the supplied digest constant while changing at least one canonical effect field:

```text
call 1: key=K, payload={"value":1}, digest=X
call 2: key=K, payload={"value":2}, digest=X
expected: hard collision
```

## Residual 2 remains — revision advance can preserve stale lifecycle state

The migration remains unchanged here.

`apply_correction_revision_insert()` advances `current_revision` but does not reset `corrections.status`.

Counterexample:

1. C:r1 is ACTIVE;
2. insert C:r2;
3. current_revision becomes 2;
4. status remains ACTIVE;
5. r2 has no qualification or promotion.

The active-binding view remains fail-closed because the old promotion revision no longer equals current revision, but durable family state is semantically false.

The same issue applies to QUALIFIED and other revision-sensitive lifecycle states.

### Required repair

Define revision insertion semantics explicitly.

A coherent baseline is:

- reject new revisions of terminal families (SUPERSEDED/REVOKED/REJECTED), unless a different explicit recovery contract exists;
- on a valid new revision, atomically set:
  - `current_revision = NEW.revision`;
  - `status = 'CORRECTION_PROPOSED'`.

### Required tests

- ACTIVE r1 -> insert r2 -> status must no longer be ACTIVE;
- QUALIFIED r1 -> insert r2 -> status must no longer be QUALIFIED;
- revision of terminal families -> explicit rejection or documented recovery behavior.

## Harness quality note

The two-connection contention test is materially better than static string checks and is the right direction. The main remaining qualification gap is execution, not test existence.

## Evidence ceiling

This is source-level exact-head review. The PostgreSQL harness has not been executed in this review environment, and no GitHub workflow run is attached to the exact head.
