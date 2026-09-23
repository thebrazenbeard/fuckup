# Next Implementation Frontier

## Objective

Build one vertical slice proving that F.U.C.K.U.P. can receive a failure, preserve it durably, generate a correction candidate, qualify that exact candidate, promote it, and safely apply it to a future execution.

## Minimal slice

### Storage

PostgreSQL migrations for:

- incidents
- append-only events
- root-cause candidates
- corrections + revisions
- qualifications
- promotions
- injection bindings
- worker jobs / dead letter state or integration with a proven queue library

### Runtime contracts

Implement typed interfaces for:

- normalizer
- fingerprinter
- analyzer
- ambiguity resolver
- correction generator
- qualifier
- policy gate
- injector
- recurrence observer

### Worker semantics

Prove:

- two workers cannot process the same claimed job concurrently;
- duplicate submissions collapse under the intended idempotency/fingerprint rules;
- retryable and non-retryable failures are distinct;
- retry budget exhaustion dead-letters cleanly;
- a lost response after a successful side effect is safe to retry/read back;
- a stale qualification cannot promote a changed correction revision.

### Qualification

At minimum:

- replay the original failure;
- assert the correction changes the intended outcome;
- run regression examples around neighboring behavior;
- add a property-based test for schema/lifecycle invariants;
- test an ambiguous case;
- test an intentionally failing adapter and circuit/quarantine behavior.

### Promotion

Promotion should require:

- exact correction revision;
- current qualification for that revision;
- policy decision;
- activation scope;
- rollback condition;
- provenance.

### Injection

Start with one simple adapter, such as a retrieved instruction/rule injection interface. Do not make model-weight changes a prerequisite.

Record:

- what correction was injected;
- into which target;
- selector/scope;
- version/digest;
- result;
- recurrence evidence.

## Acceptance criteria

The vertical slice is not complete until a test demonstrates:

1. failure A is recorded;
2. duplicate A is deduplicated but occurrence count/evidence is preserved;
3. a correction candidate is created;
4. ambiguous root cause cannot silently promote;
5. exact correction revision passes qualification;
6. promotion creates an active injection binding;
7. replayed future execution uses the binding;
8. recurrence/result is recorded;
9. changing the correction makes the old qualification stale;
10. revocation stops future application without deleting the historical record.
