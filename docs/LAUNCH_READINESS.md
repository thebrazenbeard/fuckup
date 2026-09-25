# V0.1 Launch Readiness

Status: CANDIDATE — launch means release of the reference runtime, not autonomous production activation.

## Launch scope

V0.1 is intended as a vendor-neutral corrective-learning reference runtime and library. It does not qualify model-weight mutation, autonomous deployment/rollback, production-provider changes, credentials/permissions/trust-root changes, arbitrary third-party adapters, or causal-effect claims beyond observed evidence.

## Required gates

- full Python qualification passes;
- exact binding selection and injector versioning fail closed;
- new execution revalidates binding currentness;
- PREPARED precedes ATTEMPTED;
- ATTEMPTED/AMBIGUOUS cannot be blindly redispatched;
- VERIFIED requires adapter-specific observed target state;
- verified outcomes are exact-subject, idempotent, durable, and recoverable;
- protected effects require an authority evidence reference embedded in operation identity;
- migrations apply cleanly in order on PostgreSQL 16;
- runtime role cannot directly mutate protected operation/outcome tables;
- restart recovery is proven for PREPARED, ATTEMPTED, and AMBIGUOUS;
- verified-outcome gaps are detectable and repairable without re-execution;
- the reversible reference adapter rejects traversal, verifies state, supports exact replay, and rolls back safely;
- Python support is bounded to the qualified 3.12+ floor;
- the `postgres` install extra provides psycopg without dragging in the test framework;
- wheel build, clean-environment install, and import smoke test pass;
- README, trust boundaries, database authority, execution spec, and recovery runbook agree on claim ceiling.

## V0.1 non-blockers

Production adapters, automatic deployment, model-weight mutation, statistical causal inference, and cross-repository orchestration are deliberately outside V0.1.

## Protected-effect boundary

A green launch-readiness result authorizes nothing by itself. Merge to `main`, publication, installation, database migration, deployment, activation, credentials, and provider mutation remain separate effects requiring their own authority and verification.