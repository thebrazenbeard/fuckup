> **License:** Source-visible, not open source. Original material is proprietary. Commercial use, redistribution, hosted-service use, and commercial derivative products require written permission. See [LICENSE](LICENSE) and [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md). Separately identified third-party components retain their own licenses.

# The F.U.C.K.U.P. Protocol

> **Find Unknowns, Calibrate Knowledge, Update Protocols**

Six words, three paired phases, one evidence-bound corrective-learning loop. F.U.C.K.U.P. is a vendor-neutral protocol and reference runtime for detecting discrepancies, making uncertainty explicit, qualifying corrections, and checking whether safeguards actually reduce recurrence.

## Semantic loop

1. **Find** — identify the exact gap between expected and observed behavior; preserve the original observation and its provenance.
2. **Unknowns** — enumerate missing evidence, ambiguous context, dependencies, counterexamples, and plausible competing explanations before choosing a cause.
3. **Calibrate** — adjust immediate assumptions, confidence, and containment to fit what the evidence presently supports.
4. **Knowledge** — assess an exact-subject causal proposition, its support and counterevidence, alternatives, falsifier, and current evidence ceiling.
5. **Update** — propose and qualify a versioned, reversible supersession of the affected rule, assumption, or behavior without erasing history.
6. **Protocols** — define scoped validation, policy, monitoring, and recovery controls; then observe whether they are effective.

The three pairs are **Find Unknowns** (recognize and bound the problem), **Calibrate Knowledge** (correct belief against evidence), and **Update Protocols** (qualify a change and monitor consequences).

“Update” is not a claim of destructive forgetting or direct model-weight editing. “Protocols” is not a guarantee that a failure can never recur: prevention claims stop at the scope and effectiveness supported by observed evidence.

### Backward-compatible machine vocabulary

The new words are **presentation labels**, not new runtime states or database fields. V0.1 JSON records, retrospective schemas, APIs, SQL, and existing persisted history continue to use the six canonical keys below.

| Paired phase | New stage | Existing V0.1 stage | Unchanged field |
| --- | --- | --- | --- |
| Find Unknowns | Find | Flag | `flag` |
| Find Unknowns | Unknowns | Understand | `understand` |
| Calibrate Knowledge | Calibrate | Calibrate | `calibrate` |
| Calibrate Knowledge | Knowledge | Know | `know` |
| Update Protocols | Update | Unlearn | `unlearn` |
| Update Protocols | Protocols | Prevent | `prevent` |

The source-only mapping lives in `src/fuckup_protocol/presentation.py`. Historic records retain their original labels and meaning. No automatic schema migration, memory admission, promotion authority, or deployment follows from this naming update. See [presentation mapping V1](docs/architecture/PRESENTATION_MAPPING_V1.md).

## Knowledge boundary (legacy Know) — evidence before explanation

**Know does not mean "the assistant produced a plausible explanation."** It means that a specific, falsifiable explanation has survived evidence checks and is reported within its actual verification limits. A user's report, model inference, source inspection, executed test, and independent review are distinct kinds of evidence; none silently substitutes for another. An unknown internal mechanism must remain unknown.

The opt-in Python `assess_know_claim` preflight in `src/fuckup_protocol/know_gate.py` rejects missing, stale, conflicting, or improperly classified provenance and requires separate causal support and falsification references before a root-cause candidate is **ready for review**. See [precise contract](docs/architecture/KNOW_EVIDENCE_GATE_V1.md) and [anonymized synthetic incident](docs/incidents/2026-11-04-ungrounded-context-assumption.md). These checks do **not** verify semantic entailment, authenticate external evidence, certify root causes, intercept ChatGPT responses, or activate a correction. Promoting or injecting a candidate requires separate trusted host authority and verification.

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

### Cross-repository event boundary

`FuckupEvent.to_cloudevent()` emits JSON-safe CloudEvents 1.0 telemetry in the
`org.fuckup.*` namespace. Event creation rejects malformed names, naive
timestamps, non-JSON data, non-string nested keys, and incompatible provenance
types before such assertions are serialized. This is a **producer-side
contract**, not an inbound trust validator, network publisher, message-bus
adapter, or evidence that another process received an event. Consumers must
validate inbound data independently. Provenance references and model-produced
claims are **assertions, not promotion authorization or proof of an effect**.
No Bus route, node registration, credentials, or protected effect is created
by this library API.

### DriftGuard CI-result consumption

`consume_driftguard_ci_result()` is a pure, read-only consumer for the exact
`DRIFTGUARD_CI_GATE_RESULT_V1` JSON emitted by `driftguard ci` (including
`result_digest`). It rejects duplicate keys, malformed fields, and a mismatch
between the supplied result digest and the independently recomputed canonical
SHA-256 digest. It also rejects impossible aggregate/metric combinations and
retains event data in an immutable JSON snapshot. It emits a neutral
`org.fuckup.admission.observed` event for
`PASS`, `WARN`, `BLOCK`, or `UNKNOWN`; it never flags an incident automatically.

The caller must supply the event ID, source, subject, and timezone-aware
observation time. Repeated identical results can therefore be represented as
distinct occurrences. The digest proves internal content consistency **only**;
it does not authenticate DriftGuard, the evaluator, or a run, and cannot grant
promotion or deployment authority. No network, database, publisher, or
protected-effect operation is performed. See
[the integration contract](docs/architecture/DRIFTGUARD_CI_CONSUMER_V1.md).

## Install and reference path

The Python reference package requires **Python 3.12+**. Install from an authorized local checkout for a source-verifiable evaluation:

Core library:

`python -m pip install -e .`

PostgreSQL-backed execution store (optional):

`python -m pip install -e ".[postgres]"`

For local source qualification, install `.[test]` and run `python -m pytest -q`. The project metadata defines these extras and the test command; the repository by itself does not establish availability of a published package on a third-party registry.

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

### Session-start correction bridge (host-controlled)

`load_reference_session_preflight()` can recover an exact approved correction
from a current PostgreSQL binding and a previously VERIFIED reference-file
effect on a **later session**. It rejects stale binding/revision, changed
effect content, missing verification history, and absent durable outcomes.
`verify_materialized_prompt()` checks that the actual outgoing model request
includes the exact instruction once in a trusted host-controlled message role.

The `fuckup-session-preflight` CLI emits a `PREPARED_NOT_MATERIALIZED` JSON
bundle for a host to inject. **Neither this CLI nor the library automatically
modifies ChatGPT's hosted sessions, proves provider delivery, or changes model
weights.** The host must control message assembly, call the verification gate,
and separately measure behavioral outcomes. See
[session preflight bridge V1](docs/architecture/SESSION_PREFLIGHT_BRIDGE_V1.md).

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
