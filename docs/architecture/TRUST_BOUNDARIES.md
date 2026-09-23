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

The lower-level ledger `promote(...)` method is an internal apply primitive.
It requires the exact `PromotionAuthorization` artifact returned by
`authorize_promotion(...)`; it no longer accepts a free-floating
`PolicyDecision`. The authorization artifact binds validation, policy result,
activation scope, and rollback contract together.

## Database boundary

PostgreSQL independently enforces durable minimum invariants:

- exact correction revision and digest;
- PASS qualification;
- `allow=true` policy assertion;
- currentness;
- non-terminal lifecycle state;
- non-empty activation and rollback contracts.

The database does not treat a generic runtime assertion as policy authority.
The generic runtime role cannot INSERT promotions or injection bindings.
Promotion and binding creation are reserved for a separate trusted policy/admin
authority until a durable authorization artifact or attestation scheme is
source-controlled.

PostgreSQL then carries that authority forward: binding selectors must be equal
to or narrower than the promotion activation scope, and runtime binding updates
may only reduce effect through deactivation or earlier expiry.

Future cryptographic policy attestations may allow independently verifiable
promotion creation without granting the generic runtime policy authority.
