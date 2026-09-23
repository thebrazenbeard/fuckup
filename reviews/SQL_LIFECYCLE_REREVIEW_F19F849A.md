# F.U.C.K.U.P. Second-Pass Exact-Head Re-Review — f19f849a

Reviewed exact head: `f19f849a0e263c11142252d6e94b13b73286258a`

Disposition: `SOURCE_PASS_NEAR / TWO_RESIDUAL_INVARIANTS`

## Confirmed closed from prior review

At this exact head:

- the PL/pgSQL delimiter P0 is repaired with balanced valid `$$` delimiters;
- supersession locks the target correction family and requires its exact current revision;
- `sql/claim_job.sql` delegates to the guarded claim function;
- promotions are unique per correction revision;
- revocation cannot precede activation;
- ValidationReport carries correction id/revision/digest/suite identity;
- canonical required test kinds cannot be weakened;
- unknown test kinds fail closed;
- StrictPromotionPolicy rejects validation bound to another correction;
- InMemoryLedger recomputes canonical validation before promotion;
- correction payloads are deeply frozen;
- Python event idempotency distinguishes same-effect replay from different-effect collision;
- regression tests now cover deep immutability, validation identity, canonical-suite weakening, unknown kinds, ledger collision, and SQL source contracts.

The original broad hostile-review findings are therefore substantially remediated at source level.

## Residual 1 — PostgreSQL event idempotency trusts caller-supplied effect digest

`record_event_idempotent()` receives both the actual effect fields and a caller-supplied `p_effect_digest`.

When the idempotency key already exists, the function checks only:

```sql
existing.effect_digest IS DISTINCT FROM p_effect_digest
```

It does **not** compare the new incident id, event type, or payload with the existing event, and it does not compute the digest server-side.

Counterexample:

1. first call writes key K, effect A, digest X;
2. second call submits key K, different effect B, but also supplies digest X;
3. existing digest equals supplied digest;
4. the function returns the old event as an idempotent replay.

A buggy or untrusted caller can therefore alias a different event effect by reusing the prior digest.

### Required repair

Either compute the effect digest in PostgreSQL from the canonical effect fields, or compare the canonical effect fields directly when a key exists/races.

At minimum, same-key replay should require equality of:

- incident id;
- event type;
- canonical payload;
- any other fields that define effect identity.

The caller-supplied digest can remain as provenance/checksum, but it should not be the sole authority for semantic equality.

## Residual 2 — revision advance does not reset lifecycle status

`apply_correction_revision_insert()` currently performs:

```sql
UPDATE corrections
SET current_revision = NEW.revision
WHERE id = NEW.correction_id;
```

It does not update lifecycle `status`.

Counterexample:

1. correction C:r1 is `ACTIVE`;
2. r2 is inserted;
3. `current_revision` becomes 2;
4. correction status remains `ACTIVE`;
5. there is no promotion for r2 yet.

The canonical active-binding view remains fail-closed because the old promotion revision no longer matches current revision, so this is not an injection bypass. But durable status is now semantically false: the current revision is unqualified/unpromoted while the family claims `ACTIVE`.

The same issue applies to states such as `QUALIFIED`: a new revision makes prior qualification stale but leaves the family status `QUALIFIED`.

### Required repair

Define revision-creation lifecycle semantics explicitly. The simplest source-consistent rule is:

- on insertion of a new current revision, reset the correction family to `CORRECTION_PROPOSED` (or another explicit pre-qualification state);
- then promotion/qualification transitions may advance it again.

If terminal families (SUPERSEDED/REVOKED/REJECTED) must never be revised, reject revision insertion for those statuses instead of silently preserving the terminal label on a new revision.

Add tests for ACTIVE->new revision and QUALIFIED->new revision.

## Trust-boundary note — policy/report objects are assertions, not authorization by themselves

The Python API still permits callers to construct `PolicyDecision(allow=True)` and even manually instantiate ValidationReport.

The normal ledger path is now safer because it independently recomputes canonical validation, but root-cause support/ambiguity/scope policy remains external to the ledger.

This is acceptable only if the project explicitly treats policy/report objects as trusted internal assertions produced by a controlled policy layer. If they cross an untrusted boundary, they need stronger binding/provenance or server-side reevaluation.

This is an architecture trust-boundary note, not a new P0.

## Qualification ceiling

No GitHub workflow run is attached to this exact head, and this review environment still has no PostgreSQL runtime. Source-level review cannot establish that the migration executes or that concurrency semantics hold in a real PostgreSQL server.
