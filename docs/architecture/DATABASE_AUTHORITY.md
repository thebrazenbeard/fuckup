# PostgreSQL Runtime Authority

F.U.C.K.U.P. treats database authority as part of the corrective-learning safety
model. A runtime that can rewrite durable currentness fields directly can bypass
the very invariants the protocol is intended to preserve.

## Deployment model

Install the database migrations into a dedicated trusted PostgreSQL schema.

Do not install the runtime authority layer in `public`. The migration identity
must own the trusted schema. The authority migration revokes `CREATE` on that
schema from `PUBLIC` and verifies that the PUBLIC pseudo-role cannot create
objects there. It also revokes default PUBLIC execution for future functions
created by that migration owner in the trusted schema.

Use separate identities:

- **migration owner** — owns the schema/tables/functions and applies migrations;
- **runtime role** — non-owner application identity with least privilege;
- **authorizer role** — distinct trusted identity for promotion and binding
  creation; it is forbidden from being the runtime role;
- optional future **publisher/admin roles** for outbox publication.

The runtime role must not own the F.U.C.K.U.P. schema or objects.

## Authority boundary

The runtime role receives:

- read access to the current data model;
- carefully scoped INSERT privileges for ordinary domain facts;
- EXECUTE on guarded event and worker functions;
- guarded authority to *contract* an existing effect by revoking a promotion,
  deactivating a binding, or shortening its expiry.

Promotion and binding creation are protected effects. The runtime role receives
no direct INSERT/UPDATE authority on `promotions` or `injection_bindings`.

It does **not** receive direct authority to:

- update `corrections.current_revision`;
- update `corrections.status`;
- directly insert/update/delete the protected event ledger;
- write the transactional outbox;
- rewrite correction revisions or qualifications;
- mutate worker state/locks/leases directly;
- fabricate a promotion by supplying its own `{"allow": true}` JSON;
- create an injection binding or broaden an approved binding scope;
- reactivate a disabled binding or extend/remove an existing expiry.

Those mutations occur through trigger-controlled or guarded functions owned by
the migration identity. Promotion/binding creation additionally requires the
separately configured authorizer role.

## SECURITY DEFINER

Guarded mutation functions are converted to `SECURITY DEFINER` in
`migrations/0002_runtime_authority.sql` and
`migrations/0003_promotion_authority.sql`.

Their `search_path` is pinned to:

1. the trusted installation schema;
2. `pg_catalog`;
3. `pg_temp` last.

`PUBLIC` execute is revoked before the migration transaction commits.

This follows PostgreSQL's security guidance for `SECURITY DEFINER`: use a
trusted search path and selectively grant execution rather than leaving the
default PUBLIC execute privilege.

## Runtime and authorizer provisioning

The owner-only functions:

- `configure_fuckup_runtime_role(role_name)`;
- `configure_fuckup_authorizer_role(role_name)`.

bind each clean leaf role to exactly one authority kind. The same role cannot be
configured as both runtime and authorizer.

The runtime configurator removes promotion/binding DML left by the earlier
authority layer and grants only monotonic contraction helpers. The authorizer
receives SELECT plus EXECUTE on guarded promotion/binding creation functions; it
does not receive direct table DML.

## Qualification requirement

Source-level privilege declarations are not enough.

The live PostgreSQL suite must prove that a configured runtime role:

- cannot rewrite correction currentness/status;
- cannot insert directly into the protected event ledger;
- can call `record_event_idempotent()`;
- can claim/complete/fail work through guarded functions;
- cannot bypass promotion/revision lifecycle protections.

The test remains opt-in through `FUCKUP_TEST_DATABASE_URL`.


## Runtime role isolation

The runtime role must be a clean leaf role, not merely a role whose direct
grants happen to look narrow.

`configure_fuckup_runtime_role(...)` fails closed when the supplied role:

- has administrative attributes such as SUPERUSER, CREATEROLE, CREATEDB,
  REPLICATION, or BYPASSRLS;
- is itself a member of any parent role;
- retains forbidden effective privileges after provisioning.

The configurator intentionally does not revoke arbitrary role memberships.
Memberships may belong to another system; operators must supply a dedicated
runtime identity whose privilege graph is already isolated.

Live qualification includes an inherited-parent-role attack case and proves the
configured runtime can still claim, complete, and fail jobs through the guarded
worker functions.


The runtime identity must also not own the database or hold database-level
`CREATE`. PostgreSQL explicitly treats database ownership as incompatible with
a secure untrusted-schema model; the configurator therefore rejects that
authority rather than trying to compensate for it.


## Promotion/binding scope contract

`activation_scope` and binding `selector` use one deliberately small contract:
a non-empty flat JSON object whose values are strings, numbers, or booleans.
Nested objects, arrays, and null are rejected.

A binding selector must contain every key/value constraint in the promotion's
activation scope. It may add constraints, making the binding narrower, but may
not remove or change an approved constraint.

Binding authority is monotonic after creation: identity/scope fields are
immutable, inactive bindings cannot be reactivated, existing expiries cannot be
extended or removed, and bindings cannot be deleted as a way to erase history.
