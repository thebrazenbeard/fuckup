# Trust Boundaries

F.U.C.K.U.P. separates **data objects**, **policy evaluation**, and **durable
authorization authority**.

## Untrusted or externally supplied

Treat these as assertions until validated:

- incident payloads;
- feedback;
- proposed root causes;
- proposed corrections;
- serialized qualification results from another process;
- serialized policy decisions from another process;
- model-generated self-critiques;
- user- or agent-supplied provenance claims.

A JSON object containing `{"allow": true}` is not authorization by itself.

## Trusted policy evaluation

A `ValidationReport` or `PolicyDecision` is authoritative only when produced
inside a trusted authorizer process from the exact current correction revision,
qualification evidence, configured policy, and requested activation scope.

External adapters must not deserialize arbitrary JSON into those objects and
then use the result as permission to promote a correction.

Use:

`authorize_promotion(...)`

to recompute canonical validation and policy and bind the approved
selector-shaped activation scope plus rollback condition.

The Python `PromotionAuthorization` object is an in-process authorization
result. Crossing into durable shared state requires the separate database
authorization boundary below.

## Durable database authorization

PostgreSQL uses a distinct **authorizer role** rather than trusting the generic
runtime role.

The generic runtime can prepare incidents, root-cause candidates, correction
revisions, and qualifications. It cannot directly:

- insert or revoke promotions;
- issue promotion authorization artifacts;
- create injection bindings;
- reactivate bindings;
- extend or remove binding expiry.

The authorizer role can invoke guarded functions that atomically persist:

1. an append-only `promotion_authorizations` artifact; and
2. the promotion bound exactly to that artifact.

The database requires the promotion to match the durable authorization on:

- correction id;
- correction revision;
- exact subject digest;
- qualification id/result;
- policy name/version/decision;
- activation scope;
- rollback condition;
- approving actor.

The database therefore does not accept a free-standing runtime-supplied
`allow=true` assertion as promotion authority.

## Scope continuity

Activation scope is a flat, non-empty string selector such as:

`{"agent":"demo","task":"code"}`

A binding may be **equal to or narrower than** the authorized activation scope.
It may add additional selector constraints, but it may not omit or change any
authorized key/value pair.

A broader binding requires a fresh authorization.

Runtime can only restrict an existing binding:

- deactivate it;
- add an expiry;
- move an existing expiry earlier.

It cannot reactivate, extend expiry, or remove expiry through the runtime
authority surface.

## Authority-role separation

Runtime and authorizer roles are mutually exclusive durable assignments.
Administrative roles, parent-role memberships, database/schema creation
authority, and unexpected effective DML privileges are rejected by the role
configurators.

The migration owner remains a trusted administrative identity and can always
alter database objects. It must not be used as the application runtime or
authorizer identity.

## Qualification ceiling

Source-level authority controls do not prove live PostgreSQL behavior.

The opt-in qualification suite must still execute against PostgreSQL to prove:

- role permissions behave as designed;
- SECURITY DEFINER boundaries are effective;
- fabricated runtime promotion fails;
- broad binding under narrow authorization fails;
- direct binding reactivation fails;
- expiry extension fails;
- guarded authorizer promotion/binding succeeds;
- transactional lifecycle behavior remains correct.

Future cryptographic attestations can strengthen authorizer provenance, but the
core security invariant is already explicit: **the actor proposing or executing
ordinary runtime work is not the actor that grants durable behavioral
authority.**
