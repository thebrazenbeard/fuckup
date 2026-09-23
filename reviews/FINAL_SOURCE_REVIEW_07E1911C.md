# F.U.C.K.U.P. Final Source-Level Hostile Review — 07e1911c

Reviewed exact head: `07e1911c9f177536406079cc8ddde4afb1dfd8fa`

Disposition: `CHANGES_REQUIRED_TWO_SOURCE_BLOCKERS`

## Confirmed closed

This exact head materially closes the previously reported semantic residuals:

- PostgreSQL event idempotency compares canonical effect fields as well as digest;
- new correction revisions reset lifecycle status to `CORRECTION_PROPOSED`;
- terminal correction families cannot accept new revisions;
- validation reports bind exact correction identity;
- canonical validation cannot be weakened;
- unknown test kinds fail closed;
- correction payloads are deeply frozen;
- Python idempotency collisions are explicit;
- `authorize_promotion(...)` recomputes validation and policy at an explicit authorization boundary;
- trust-boundary documentation correctly distinguishes external assertions from trusted internal policy/validation outputs;
- opt-in PostgreSQL qualification cases exist for the previously identified residuals.

Those changes are source-level improvements.

## Blocker 1 — database currentness authority is still unenforced

The new `docs/architecture/TRUST_BOUNDARIES.md` documents the application-level policy boundary, but it does not establish a database write-authority boundary.

The exact migration still contains no:

- application/runtime role definition;
- `GRANT` / `REVOKE` contract;
- guarded currentness mutation function exposed instead of raw table UPDATE;
- trigger preventing direct mutation of `corrections.current_revision` or `corrections.status`.

Therefore the previously reported stale-currentness attack remains possible for any runtime role with ordinary UPDATE permission:

```sql
UPDATE corrections
SET current_revision = <old promoted revision>,
    status = 'ACTIVE'
WHERE id = <correction>;
```

Because `active_injection_bindings` trusts those fields, this can make an old binding effective again without changing append-only revision or qualification evidence.

The same authority gap means helper semantics such as `record_event_idempotent()` can be bypassed by direct table DML unless table permissions explicitly prohibit it.

### Required closure

Source-control one explicit database authority model and test it.

Preferred minimum:

1. define an application/runtime DB role;
2. revoke direct UPDATE of `corrections.current_revision/status`;
3. revoke direct INSERT/UPDATE on semantic tables whose invariants must flow through guarded functions;
4. grant only the required guarded functions/views;
5. live-test the restricted role:
   - direct currentness rewrite fails;
   - guarded revision insertion succeeds;
   - stale binding cannot be reactivated;
   - direct semantic event insert is denied if `record_event_idempotent()` is the canonical write path.

Documentation alone is insufficient because the durable currentness claims depend on actual database authority.

## Blocker 2 — package export surface lists an undefined symbol

Exact `src/fuckup_protocol/__init__.py` includes:

```python
__all__ = [
    ...
    "PromotionAuthorization",
    ...
]
```

but the module does not import:

```python
from .authorization import PromotionAuthorization, authorize_promotion
```

As a result:

- `fuckup_protocol.PromotionAuthorization` is not defined;
- `from fuckup_protocol import PromotionAuthorization` does not expose the advertised symbol;
- `from fuckup_protocol import *` may fail while iterating `__all__`;
- the newly introduced safe `authorize_promotion(...)` boundary is also not exported from the package root.

### Required closure

Import and export both safe-boundary symbols explicitly:

```python
from .authorization import PromotionAuthorization, authorize_promotion
```

and include `"authorize_promotion"` in `__all__`.

Add a package-surface regression test that imports both from `fuckup_protocol`.

## Qualification ceiling

There are still no GitHub workflow runs attached to this exact head and no live PostgreSQL qualification evidence in this review lane.

Even after the two source blockers above are repaired, runtime PASS must remain separate until the migration and restricted-role qualification suite actually execute against PostgreSQL.
