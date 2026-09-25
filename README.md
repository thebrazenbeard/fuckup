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

## Runtime

V0.1 provides an executable corrective-learning core with:

- immutable/versioned correction records and exact-revision qualification;
- ambiguity, validation, policy, promotion, binding, and revocation semantics;
- append-only incident occurrence evidence even when incidents deduplicate;
- effect-bound idempotency and a `PREPARED -> ATTEMPTED -> VERIFIED | FAILED | AMBIGUOUS` operation journal;
- readback-gated reconciliation so ambiguous effects are not blindly redispatched;
- exact-subject recurrence/effectiveness attribution;
- governed injector execution from exact active binding through adapter-specific readback and bound outcome observation;
- exact adapter-version pinning for executable bindings, with legacy unversioned bindings rejected by the execution coordinator;
- `PostgresExecutionStore` for durable bindings, operation recovery, verified-outcome persistence, and restart gap detection;
- a reversible `ReferenceFileInjector` that performs real filesystem write/readback/rollback qualification without path traversal;
- PostgreSQL worker retry/DLQ and transactional outbox mechanics;
- trusted-schema runtime/authorizer role separation and guarded promotion authority;
- hostile tests for stale evidence, fabricated authority, privilege escape, collisions, and illegal lifecycle transitions.

Source presence and passing tests do not establish installation, deployment, runtime consumption, or effectiveness in a production system.

## Install and reference path

V0.1 is qualified on Python 3.12+.

Core library:

`python -m pip install fuckup-protocol`

PostgreSQL-backed execution store:

`python -m pip install "fuckup-protocol[postgres]"`

A minimal reversible reference path is:

```python
from pathlib import Path
from fuckup_protocol import (
    ExecutionCoordinator,
    OperationJournal,
    PluginRegistry,
    ReferenceFileInjector,
)

registry = PluginRegistry()
adapter = ReferenceFileInjector(Path("./fuckup-state"))
adapter.register(registry)

# Supply an exact active InjectionBinding and a host currentness validator.
# Protected effects additionally require an authority evidence reference.
```

The filesystem adapter is for qualification/examples. Production adapters must supply their own readback and authority integration.

## Licensing

Original repository material is source-visible proprietary material under `LICENSE`. Noncommercial evaluation/research permissions are limited; commercial use requires a separate written license under `COMMERCIAL_LICENSE.md`. Contributions are governed by `CONTRIBUTING.md` and `CLA.md`. Third-party dependencies retain their own licenses; see `THIRD_PARTY_NOTICES.md`.

## Repository map

- `PROTOCOL.md` — canonical six-stage protocol text.
- `src/fuckup_protocol/` — Python reference semantics.
- `migrations/` — PostgreSQL persistence and authority layers.
- `tests/` — unit, contract, hostile, and optional live PostgreSQL qualification.
- `schema/` — machine-readable record/event contracts.
- `templates/RETROSPECTIVE.md` — fillable six-stage review.
- `docs/architecture/` — runtime, trust, event/provenance, and database boundaries.
- `docs/operations/RECOVERY_RUNBOOK.md` — restart/reconciliation procedure for PREPARED, ATTEMPTED, AMBIGUOUS, and VERIFIED-gap states.
- `docs/LAUNCH_READINESS.md` — V0.1 release scope and launch gates.
- `docs/research/` — mechanism and portfolio research.
- `docs/plans/` and `docs/implementation/` — implementation state and next frontier.

## Qualification

Run the source suite with:

`python -m pytest -q`

Live PostgreSQL qualification additionally requires `FUCKUP_TEST_DATABASE_URL`.

`main` is the authoritative source branch. The `v0.1.0` tag and GitHub release identify the first launched reference-runtime cut; later `main` commits may contain post-release maintenance or release tooling.