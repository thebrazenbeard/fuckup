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
- **runtime role** — non-owner application identity that can create/qualify candidates and use guarded runtime functions;
- **authorizer role** — separate non-owner authority that can issue durable promotion authorizations and create bindings within the approved activation scope;
- optional future **publisher/admin roles** for outbox publication or other protected operational effects.

The runtime role must not own the F.U.C.K.U.P. schema or objects.

## Authority boundary

The runtime role receives:

- read access to the current data model;
- carefully scoped INSERT privileges for ordinary candidate facts;
- EXECUTE on guarded event and worker functions;
- EXECUTE on a monotonic binding-restriction function that can only deactivate a binding or move its expiry earlier.

It does **not** receive direct authority to:

- update `corrections.current_revision` or `corrections.status`;
- create, mutate, or revoke promotions directly;
- create or reactivate injection bindings directly;
- extend or remove binding expiry;
- directly insert/update/delete the protected event ledger;
- write the transactional outbox;
- rewrite correction revisions or qualifications;
- mutate worker state/locks/leases directly.

Those mutations occur through trigger-controlled or guarded functions owned by
the migration identity.

## SECURITY DEFINER

Guarded mutation functions are converted to `SECURITY DEFINER` in
`migrations/0002_runtime_authority.sql`.

Their `search_path` is pinned to:

1. the trusted installation schema;
2. `pg_catalog`;
3. `pg_temp` last.

`PUBLIC` execute is revoked before the migration transaction commits.

This follows PostgreSQL's security guidance for `SECURITY DEFINER`: use a
trusted search path and selectively grant execution rather than leaving the
default PUBLIC execute privilege.

## Runtime provisioning

The owner-only function:

`configure_fuckup_runtime_role(role_name)`

revokes broad table privileges and grants the bounded runtime contract.

The supplied `sql/configure_runtime_role.sql` wrapper is intended for a DBA or
migration operator. It also configures the role's database-local search path.

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


## Authorization continuity

Promotion is intentionally separated from generic runtime authority.

`migrations/0003_authorization_continuity.sql` adds:

- an append-only `promotion_authorizations` artifact;
- mutually exclusive `RUNTIME` and `AUTHORIZER` role assignments;
- `authorize_and_promote(...)`, executable only by the configured authorizer role;
- `create_authorized_binding(...)`, also authorizer-only;
- `restrict_injection_binding(...)`, available to runtime but monotonic only;
- `revoke_authorized_promotion(...)`, authorizer-only.

The database binds the promotion exactly to the authorization artifact:
correction id/revision/digest, qualification, policy name/version/decision,
activation scope, rollback condition, and approving actor must match.

The activation scope is a flat non-empty string selector. A binding selector
must contain every key/value in the authorization scope; it may add more
constraints, but it may not omit or change authorized constraints. In other
words, a binding may be equal to or narrower than the authorization scope, never
broader.

The generic runtime cannot fabricate `{"allow": true}` and insert a promotion:
it has neither table DML authority nor EXECUTE on the authorizer function.

Runtime binding restriction is monotonic:

- active may become false, never false -> true;
- an expiry may be added;
- an existing expiry may only move earlier;
- expiry cannot be removed or extended.

Any broader activation requires a fresh authorization artifact.


## Governed injector execution continuity

`migrations/0005_governed_injector_execution.sql` extends binding authority without silently rewriting historical rows.

It adds nullable `injection_bindings.adapter_version` so existing bindings remain legible as historical records, then adds an authorizer-only:

`create_versioned_authorized_binding(...)`

A new executable binding must therefore pin both adapter name and adapter version. The generic runtime role is explicitly denied this function; the configured authorizer role receives it through the same guarded authority boundary used for promotion/binding creation.

The `active_injection_bindings` view exposes adapter version together with promotion, correction revision, activation scope, selector digest, expiry, and currentness filtering. An unversioned historical row may still appear as active data, but the Python execution coordinator rejects it as non-executable rather than inventing a version.

Runtime execution currentness and reconciliation are deliberately different:

- new adapter execution must revalidate the exact binding as current immediately before effect preparation;
- revocation or supersession must block a new execution;
- a prior ATTEMPTED/AMBIGUOUS effect may still be read back and reconciled after later revocation, because current authority cannot erase uncertainty about an effect already attempted.

This migration does not install an adapter, authorize a protected effect, or prove a target consumed an effect.