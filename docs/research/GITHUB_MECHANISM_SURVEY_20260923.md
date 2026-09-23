# GitHub Mechanism Survey — 2026-09-23

## Goal

Find reusable implementation mechanisms for F.U.C.K.U.P. rather than search for projects with the same branding or vocabulary.

Seed concepts included: gate, handler, resolver, ambiguity, router, PostgreSQL/Postgres, inject.

Expanded mechanism vocabulary:

- idempotency
- deduplication
- fingerprinting
- confidence calibration
- fallback threshold
- retry budget
- dead-letter queue / DLQ
- `FOR UPDATE SKIP LOCKED`
- advisory locks
- optimistic concurrency
- transactional outbox
- event sourcing
- state machine
- command handler
- middleware pipeline
- hook/plugin registry
- provenance
- append-only audit log
- checkpoint/replay/rollback
- supersession
- saga / compensating transaction
- human-in-the-loop
- policy engine
- fail-closed
- schema validation
- property-based testing
- fault injection / chaos testing
- invariant checking
- error taxonomy
- circuit breaker

## Strong reference mechanisms

### pg-boss — PostgreSQL-native job semantics

Repository: `timgit/pg-boss`

Inspected search snapshot included commit `909f4f505f40e811cae311013776a1b68b9d5872`.

Useful mechanisms observed:

- retry delay/backoff;
- dead-letter routing;
- keyed/singleton work semantics;
- dependency blocking;
- database-backed coordination.

Potential F.U.C.K.U.P. use: worker claiming, retry policy, DLQ, correction-qualification jobs, serialized work per fingerprint/correction key.

### River — uniqueness/advisory-lock patterns

Repository: `riverqueue/river`

Inspected search snapshot included commit `7931f7d161cc50d17901c6c972be5a6ea4c0cc86`.

Useful mechanisms observed:

- advisory-lock configuration;
- unique-job insertion semantics;
- explicit job state.

Potential use: incident/correction deduplication and collision control.

### OpenAI Agents Python — resumable human-in-the-loop approval

Repository: `openai/openai-agents-python`

Inspected search snapshot included commit `32edd3c3ecde37a7fb6bf4b082f35f1d8f7f086b`.

Useful mechanisms observed:

- `needs_approval`;
- run-wide interruptions;
- saved/resumable `RunState`;
- consume-once handling of pending decisions.

Potential use: consequence gates, manual promotion gates, protected injection/install decisions, resumable correction workflows.

### pluggy — explicit hook specifications and handler registration

Repository: `pytest-dev/pluggy`

Inspected search snapshot included commit `080b7d31074f773540c9e66f9d4c00a47159a35f`.

Useful mechanisms observed:

- `PluginManager`;
- explicit hook specifications;
- named registration;
- multiple implementations against one contract.

Potential use: analyzers, routers, root-cause resolvers, qualifiers, injectors, storage adapters, model/platform adapters.

### Open Policy Agent — policy/execution separation

Repository: `open-policy-agent/opa`

Inspected search snapshot included commit `a83674f1bf26bdcea87125e87c39f8b9e01d7399`.

Useful mechanisms observed:

- decisions separated from execution;
- decisions can be richer than allow/deny;
- policy can combine multiple JSON/YAML data sources/context.

Potential use: fail-closed consequence gates, correction-promotion policy, injection scope policy, environment-specific activation policy.

### Opossum — circuit breaker

Repository: `nodeshift/opossum`

Inspected search snapshot included commit `decbedf63d7815049233e544dcb351590ff0c84e`.

Useful mechanisms observed:

- circuit state;
- error thresholds;
- reset timeout;
- fallback path;
- observable transition events.

Potential use: stop repeated failing correction/injection paths, quarantine broken adapters, bounded recovery probes.

## Additional high-value candidates from the research pass

These are mechanism references to inspect before implementation; reverify exact source/license before copying literal code.

- `RasaHQ/rasa` / historical Rasa fallback machinery: confidence thresholding, ambiguity/fallback and rephrasing/confirmation flows.
- `BerriAI/litellm`: routing, fallback, provider cooldown/retry semantics; also useful as a source of failure cases around fallback graphs and bounded retries.
- `temporalio/*`: durable workflows, activity retries, idempotency, resumable orchestration.
- `getsentry/sentry`: error grouping/fingerprinting and normalization.
- `guardrails-ai/guardrails`: validate/fix/re-ask/refrain output-repair patterns.
- `confident-ai/deepeval`: agent/trajectory qualification patterns.
- `HypothesisWorks/hypothesis`: property-based testing and shrinking to minimal repros.
- `Shopify/toxiproxy`: deterministic failure/latency injection for resilience qualification.
- PostgreSQL event-sourcing examples: append-only events, optimistic concurrency, projections, replay, outbox.

## What not to cargo-cult

Do not import an entire framework just because one mechanism is useful.

F.U.C.K.U.P. should own its semantics:

- incident identity;
- evidence/provenance;
- correction lifecycle;
- ambiguity state;
- promotion state;
- injection scope;
- recurrence/effectiveness measures.

External libraries may implement queueing, hooks, schema validation, policy evaluation, or testing, but they should not become the canonical source of F.U.C.K.U.P.'s behavioral meaning.

## License/provenance rule

This survey records mechanisms, not permission to copy.

Before literal upstream code is imported:

1. bind the exact upstream repository + commit/blob;
2. read the exact license covering that file;
3. record attribution/notice requirements;
4. prefer small clean-room adaptation when practical;
5. add tests proving local semantics rather than assuming upstream semantics match.
