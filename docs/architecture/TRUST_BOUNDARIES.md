# Trust Boundaries

F.U.C.K.U.P. separates **data objects** from **authorization authority**.

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

## Trusted internal outputs

A `ValidationReport` or `PolicyDecision` is authoritative only when produced
inside the current trusted runtime from the exact current correction revision,
qualification evidence, and configured policy.

External adapters must not deserialize arbitrary JSON into those objects and
then use the result as permission to promote a correction.

Use:

`authorize_promotion(...)`

at the authorization boundary. It recomputes the canonical validation report and
policy decision from the supplied correction and qualification.

The lower-level ledger `promote(...)` method is an internal apply primitive. It
still rechecks current revision and canonical qualification, but its
`PolicyDecision` argument is assumed to have come from a trusted policy
evaluation boundary.

## Database boundary

PostgreSQL independently enforces durable minimum invariants:

- exact correction revision and digest;
- PASS qualification;
- `allow=true` policy assertion;
- currentness;
- non-terminal lifecycle state;
- selector-shaped activation scope;
- binding scope no broader than the approved activation scope;
- monotonic binding restriction.

The generic runtime cannot insert promotions or bindings. Promotion/binding
creation is routed through guarded functions executable only by a separately
configured authorizer role, and each authority role is durably bound to exactly
one role kind.

This role separation does not make arbitrary policy JSON magically true. The
authorizer is the trusted boundary that must call `authorize_promotion(...)` (or
an equivalently controlled policy engine) before invoking the database creation
function. Each promotion also carries a non-empty `authorization_ref` for
provenance. A future cryptographic attestation can replace that trust assumption
without changing the runtime/authorizer separation.
