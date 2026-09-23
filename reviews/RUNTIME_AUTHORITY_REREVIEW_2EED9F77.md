# F.U.C.K.U.P. Runtime Authority Re-Review — 2eed9f77

Reviewed exact head: `2eed9f77f65430938124bde7214374356d8ee77d`

Disposition: `CHANGES_REQUIRED_NARROWED_ONE_ROLE_ESCALATION_GAP`

## Confirmed fixed

The two prior source blockers are materially addressed:

1. Package exports are repaired:
   - `PromotionAuthorization` and `authorize_promotion` are imported from `.authorization`;
   - both are exported through `__all__`;
   - `tests/test_package_exports.py` verifies every declared root export is actually bound.

2. A real database authority layer now exists:
   - dedicated non-public trusted schema is required;
   - mutation-capable functions are converted to `SECURITY DEFINER`;
   - function `search_path` is pinned to trusted schema + `pg_catalog` + `pg_temp` last;
   - `PUBLIC` EXECUTE is revoked inside the migration transaction;
   - runtime role provisioning revokes broad direct table/sequence privileges and regrants a bounded surface;
   - runtime receives no direct UPDATE on `corrections.current_revision/status`;
   - direct runtime event/outbox writes and raw worker-state mutations are not granted;
   - guarded worker completion/failure functions exist;
   - the live PostgreSQL suite includes direct-currentness and direct-event-write denial checks.

The search-path/PUBLIC-execute design is consistent with PostgreSQL's documented SECURITY DEFINER hardening guidance.

## Remaining blocker — configurator only strips direct privileges, not privilege escalation through role membership

`configure_fuckup_runtime_role(p_role)` does this:

- REVOKE privileges granted directly to `p_role`;
- GRANT the intended bounded runtime privileges.

It does **not** reject or remove memberships where `p_role` itself is a member of another role.

PostgreSQL roles inherit privileges from roles they belong to when inheritance is enabled, and PostgreSQL roles default to inheritance. Membership can also permit later `SET ROLE` depending on the membership options.

Therefore this configuration is possible:

1. role `elevated` has `UPDATE` on `corrections`;
2. runtime role is a member of `elevated`;
3. `configure_fuckup_runtime_role(runtime)` revokes direct UPDATE from runtime;
4. runtime still has effective UPDATE through inherited membership, or can potentially assume the parent role through `SET ROLE`;
5. stale currentness can still be rewritten.

The live qualification currently creates a clean standalone runtime role, so it does not exercise this bypass.

## Required repair

The authority configurator should fail closed when the supplied runtime role is not actually isolated.

### 1. Reject administrative role attributes

Read `pg_catalog.pg_roles` for `p_role` and reject at minimum:

- `rolsuper`;
- `rolcreaterole`;
- `rolcreatedb`;
- `rolreplication`;
- `rolbypassrls`.

A least-privilege application role should not carry administrative escape hatches.

### 2. Reject parent-role memberships

Resolve the runtime role OID and reject if any row exists in `pg_catalog.pg_auth_members` with:

```text
member = runtime_role_oid
```

This intentionally rejects both inherited privilege paths and memberships that could later be assumed through SET ROLE. The safe contract is: the F.U.C.K.U.P. runtime role is a leaf role.

Do not silently revoke arbitrary memberships; fail closed and make the operator supply a clean role. Membership may belong to another system and destructive cleanup is not the configurator's job.

### 3. Verify effective postconditions after grants

After the revoke/grant sequence, use PostgreSQL's effective privilege checks and raise if any forbidden authority remains.

At minimum verify that the runtime role does **not** effectively have:

- CREATE on the trusted schema;
- UPDATE on `corrections`;
- INSERT/UPDATE/DELETE on `events`;
- INSERT/UPDATE/DELETE on `outbox`;
- UPDATE on worker state/lock/lease fields through table-wide UPDATE privilege.

Column-level privilege checks should remain consistent with the intended bounded grants.

This catches unexpected ownership/inherited privilege cases even if role metadata evolves.

## Required adversarial qualification

Add a live PostgreSQL case:

1. create `elevated_role`;
2. grant `UPDATE ON corrections` to it;
3. create `runtime_role`;
4. grant `elevated_role TO runtime_role`;
5. call `configure_fuckup_runtime_role(runtime_role)`;
6. expect the configurator to fail closed.

Also add a clean-role control proving normal configuration still succeeds.

A second useful case is a role with an administrative attribute such as `CREATEROLE`; configurator should reject it.

## Additional test blind spot

The authority document says runtime qualification should prove guarded claim/complete/fail worker operations. The current runtime-role live test proves:

- direct currentness update denied;
- direct event INSERT denied;
- guarded event helper succeeds.

It does not yet exercise `claim_worker_job`, `complete_worker_job`, and `fail_worker_job` while actually under the configured runtime role.

Add one runtime-role worker lifecycle case so the privilege model is proven usable as well as restrictive.

## Source-level result

The package export surface is source-clean.

The database authority design is close and the SECURITY DEFINER/search-path pattern is sound, but the runtime role isolation assumption is not yet enforced. Until unsafe memberships/admin attributes/effective forbidden privileges are rejected, the currentness bypass remains possible through privilege inheritance.

## Evidence ceiling

No live PostgreSQL migration/role qualification is claimed by this review. No GitHub workflow run is attached to the exact head.
