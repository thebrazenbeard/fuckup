# F.U.C.K.U.P. Runtime Handoff — 2026-09-23

## Subject

Repository: `thebrazenbeard/fuckup`

Base branch/head inspected: `main@e999607481ba706523209ce129955a5e3d2d6ef7`

Handoff branch: `handoff/runtime-mechanism-research-20260923`

This handoff converts the current two-file protocol stub into a concrete implementation frontier without changing `main`.

## Current-state audit

At the inspected base head, `main` contains only:

- `README.md`
- `PROTOCOL.md`

The README advertises three artifacts that were absent at the inspected base head:

- `templates/RETROSPECTIVE.md`
- `schema/fuckup-retrospective.schema.json`
- `.github/ISSUE_TEMPLATE/fuckup-retrospective.yml`

This branch adds those missing artifacts plus the architecture/research packet.

There are no runtime services, database migrations, tests, adapters, worker loops, model integrations, or execution engine on the inspected base head.

## Interpretation

The useful system-level interpretation is not merely "write a postmortem." It is a model-agnostic behavioral correction runtime:

`failure -> detect -> classify -> reconstruct -> resolve ambiguity -> propose correction -> qualify -> promote -> inject -> observe recurrence`

The six F.U.C.K.U.P. stages remain the semantic spine:

1. **Flag** — capture, normalize, fingerprint, deduplicate, and acknowledge the failure.
2. **Understand** — reconstruct events, context, provenance, dependencies, and competing explanations.
3. **Calibrate** — update immediate assumptions/parameters; route uncertain cases explicitly instead of bluffing certainty.
4. **Know** — isolate a supported root-cause hypothesis and state its evidence ceiling.
5. **Unlearn** — supersede a bad behavior/assumption with a versioned correction candidate; do not erase history.
6. **Prevent** — qualify and promote guardrails, tests, routing constraints, policy rules, or other controls; continue recurrence detection.

## Two protocol corrections before implementation

### Unlearn is supersession, not erasure

For AI/software systems, "purge the bad muscle memory" should not become destructive history deletion.

The implementation should preserve:

- the original failure;
- the prior rule/behavior/version;
- the proposed correction;
- evidence and provenance;
- qualification results;
- supersession links;
- rollback/revocation state.

A correction becomes active by promotion, not by pretending the old state never existed.

### Prevent is bounded prevention, not universal guarantee

The present prose says "guarantee the error cannot recur." That is generally too strong.

The implementation target should distinguish:

- **invariant-prevented**: a known path is mechanically impossible under an enforced invariant;
- **guarded**: a known path is blocked or requires escalation;
- **detected**: recurrence is recognized reliably;
- **contained**: recurrence cannot propagate beyond a defined boundary;
- **unproven**: mitigation exists but recurrence prevention is not established.

## Recommended implementation order

1. Typed retrospective/event schema.
2. Append-only event/correction ledger.
3. Fingerprinting and idempotency.
4. Explicit correction lifecycle/state machine.
5. Handler/plugin registry.
6. Ambiguity resolver and confidence representation.
7. Policy/consequence gates.
8. Qualification/replay harness.
9. Postgres worker queue with retry budget and DLQ.
10. Injection/adaptation adapters for downstream LLM/agent systems.
11. Recurrence telemetry and correction effectiveness scoring.

## Guardrails for the project handler

- Do not copy upstream code until its exact license and provenance are recorded.
- Prefer mechanism reimplementation when a reference implementation is useful conceptually but licensing or coupling is undesirable.
- Treat retries as at-least-once unless an exact-once property is actually proven.
- Make all consequential operations idempotent or read-back-verifiable.
- Ambiguity is a state, not an error to conceal.
- Route selection does not imply permission.
- A promoted correction is not automatically true globally; scope it.
- Every correction should be reversible or explicitly marked irreversible.
- Qualification must bind to the exact correction/version being promoted.
- Do not let a single incident silently become a universal rule.

## Next executable frontier

Implement the minimum vertical slice:

1. PostgreSQL schema/migrations for incidents, events, correction candidates, correction revisions, qualifications, promotions, and injection bindings.
2. A worker that atomically claims pending incidents/corrections.
3. A deterministic fingerprint/idempotency layer.
4. A state machine enforcing allowed lifecycle transitions.
5. A plugin interface for analyzers/resolvers/qualifiers/injectors.
6. Tests for duplicate submission, ambiguous classification, worker collision, retry exhaustion, supersession, stale qualification, and rollback.

No merge, deployment, installation, or runtime effect is authorized by this handoff.

## Continuation update — 2026-09-25

The 2026-09-23 frontier above is now historical. The current implementation work is on `build/portfolio-integrity-v2-20260925`, based on Draft PR #1 head `ff46bcf822a89701201e6153be923239814e5b61`.

Validated implementation cut:

`1fb9e190eeb5974fdfc9c37a5547004793ddd6f4`

That cut adds:

- append-only incident occurrence evidence for deduplicated failures;
- portable effect-operation journaling with exact effect digests and idempotency collision detection;
- `PREPARED -> ATTEMPTED -> AMBIGUOUS/VERIFIED/FAILED` recovery semantics;
- readback evidence requirements before verification;
- exact-subject effectiveness attribution;
- PostgreSQL execution-integrity tables/functions and runtime-role restrictions;
- live PostgreSQL hostile cases for collision, blind redispatch, terminal reopening, occurrence evidence, and direct-DML denial.

Local source qualification on the implementation cut: 112 tests passed; the live PostgreSQL module was skipped locally because `FUCKUP_TEST_DATABASE_URL` was not present. CI/live PostgreSQL remains the next verification layer.

The next implementation frontier is governed injector execution: resolve one active binding, prepare the effect before execution, invoke the injector, verify by adapter-specific readback, reconcile the operation, and record an exact-subject outcome.