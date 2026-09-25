# The F.U.C.K.U.P. Protocol

> **F**lag • **U**nderstand • **C**alibrate • **K**now • **U**nlearn • **P**revent

A vendor-neutral corrective-learning protocol and reference runtime for turning failures into bounded, testable, reversible prevention mechanisms.

## Semantic loop

1. **Flag** — capture the failure without deflection or evidence loss.
2. **Understand** — reconstruct context, provenance, dependencies, and competing explanations.
3. **Calibrate** — correct immediate assumptions and expose ambiguity instead of hiding it.
4. **Know** — isolate a supported root-cause proposition with an explicit evidence ceiling.
5. **Unlearn** — supersede the bad behavior or assumption without erasing history.
6. **Prevent** — qualify and scope a guardrail, then observe whether it actually helps.

“Unlearn” means versioned supersession, not destructive forgetting. “Prevent” means the strongest prevention state the evidence supports; it is not a magic guarantee that a class of failure can never recur.

## Runtime candidate

The current review branch expands the protocol into an executable corrective-learning core with:

- immutable/versioned correction records and exact-revision qualification;
- ambiguity, validation, policy, promotion, binding, and revocation semantics;
- append-only incident occurrence evidence even when incidents deduplicate;
- effect-bound idempotency and a `PREPARED -> ATTEMPTED -> VERIFIED | FAILED | AMBIGUOUS` operation journal;
- readback-gated reconciliation so ambiguous effects are not blindly redispatched;
- exact-subject recurrence/effectiveness attribution;
- PostgreSQL worker retry/DLQ and transactional outbox mechanics;
- trusted-schema runtime/authorizer role separation and guarded promotion authority;
- hostile tests for stale evidence, fabricated authority, privilege escape, collisions, and illegal lifecycle transitions.

Source presence and passing tests do not establish installation, deployment, runtime consumption, or effectiveness in a production system.

## Repository map

- `PROTOCOL.md` — canonical six-stage protocol text.
- `src/fuckup_protocol/` — Python reference semantics.
- `migrations/` — PostgreSQL persistence and authority layers.
- `tests/` — unit, contract, hostile, and optional live PostgreSQL qualification.
- `schema/` — machine-readable record/event contracts.
- `templates/RETROSPECTIVE.md` — fillable six-stage review.
- `docs/architecture/` — runtime, trust, event/provenance, and database boundaries.
- `docs/research/` — mechanism and portfolio research.
- `docs/plans/` and `docs/implementation/` — implementation state and next frontier.

## Qualification

Run the source suite with:

`python -m pytest -q`

Live PostgreSQL qualification additionally requires `FUCKUP_TEST_DATABASE_URL`.

The default branch remains authoritative only after an authorized merge. Draft/review branches are implementation candidates, not deployment.