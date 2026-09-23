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
- non-empty activation and rollback contracts.

The database cannot prove that an arbitrary JSON policy assertion was generated
by the intended policy engine. Applications crossing an untrusted boundary must
re-evaluate policy before inserting a promotion.

Future cryptographic policy attestations may strengthen that boundary, but are
not required for the core protocol.
