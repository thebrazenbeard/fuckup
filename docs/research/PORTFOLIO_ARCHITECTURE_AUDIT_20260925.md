# Portfolio Architecture Audit — 2026-09-25

Status: CURRENT OBSERVATION FOR THIS BUILD
Purpose: identify reusable architecture for F.U.C.K.U.P. without turning the portfolio into implicit runtime dependencies.

## Inventory cut

The connected GitHub inventory for `thebrazenbeard` contains **70 repositories**: **52 public**, **18 private**, with **2 archived** at this observation cut.

This public repository records public-safe donor detail only. Private repositories were included in the audit but are intentionally not named or described here merely because they were visible to the audit.

The earlier Discovery census recorded 59 repositories on 2026-09-22, so that census is historical for currentness purposes.

## Audit method

Every accessible repository received metadata triage. Public and private repositories received README/source-orientation review where available; private names/details are not published here merely because the audit could read them. Repositories with plausible reusable mechanics received deeper source/contract inspection. A mechanism was considered for adoption only when it matched an existing F.U.C.K.U.P. gap; thematic similarity alone was not enough. The private-repository pass reinforced the same durable-event, exact-frontier, recovery, authority, and evidence-boundary patterns and did not justify adding a private repository as a F.U.C.K.U.P. runtime dependency.

## Public portfolio disposition

### Directly useful to this build

- `wip` — crash recovery, effect ambiguity, prepare/attempt/readback discipline.
- `project-runner` — exact work identity, durable fencing/leases, expected-head preconditions, readback verification.
- `driftguard` — exact-subject deterministic admission and fail-closed missing evidence.
- `roots` — temporally ordered provenance and correction/supersession lineage.
- `temporal` — chronology without semantic overclaiming.
- `ingest` — immutable evidence identity, deterministic hashing, duplicate-vs-conflict separation.
- `vera-mono` — explicit REQUEST/AUTHORITY/ATTEMPT/EFFECT/VERIFICATION separation and recovery/currentness boundaries.
- `ccb-core` — deterministic deduplication, durable accounting, DLQ/routing boundaries.
- `vera-mesh` — receipt is not completion; transport is not authorization; replay/freshness protection.
- `intranel` — operation identity distinct from packet identity; receipts do not self-verify effects.
- `bugops` — incident evidence separated from lifecycle tracking and closure evidence.
- `RepairTracker` — repair lifecycle, portfolio discovery, specialist integration without authority leakage.
- `project-achilles` — consequence/effect classification without permission paralysis.
- `masamune` and `voss` — exact-subject hostile review and review-currentness discipline.
- `world-zero`, `mosaic`, and `vera_model_training` — preregistration, holdouts, exact run identity, and qualification ceilings.

### Useful boundary/negative-control projects

`Attune`, `on-theo`, `testament`, `semanticatlas`, `spm`, `unvtrslr`, `abil`, `sql-connectome`, `meso-crct`, `noema`, and the cognitive-architecture repositories demonstrate that shared mechanics must not flatten domain semantics, evidence classes, ontology, scientific validity, or authority.

### Mostly project-specific or currently scaffold/reference surfaces

The remaining public repositories were reviewed as architecture context but did not justify new F.U.C.K.U.P. dependencies for this slice. Their value is primarily identity/domain specialization, packaging, device/product scaffolding, historical lineage, or independent experimentation.

## Main findings

### What F.U.C.K.U.P. already does well

At the inspected Draft PR #1 head it already has:

- exact correction revision/digest qualification;
- canonical validation-suite enforcement;
- explicit ambiguity and correction lifecycle states;
- effect-bound event idempotency;
- worker claim/reclaim/retry/DLQ mechanics;
- transactional outbox hooks;
- trusted-schema PostgreSQL authority;
- runtime/authorizer role separation;
- append-only promotion authorization artifacts;
- narrow activation scopes and monotonic binding restriction;
- hostile tests for fabricated authority and privilege bypass.

### Highest-value gaps at audit start

1. **Deduplication lost per-occurrence evidence.** The incident counter grew, but a repeated observation was not independently preserved.
2. **Effect ambiguity lacked a first-class portable journal.** Existing idempotency did not itself encode PREPARED/ATTEMPTED/AMBIGUOUS/readback recovery.
3. **Effectiveness attribution was too weak.** Observations could be summarized without proving they belonged to one exact correction/promotion/binding subject.
4. **The handoff/current docs lagged implementation reality.**
5. **Portfolio provenance was not recorded in-repo for the current build.**

### Resolution in this build

Implementation cut `1fb9e190eeb5974fdfc9c37a5547004793ddd6f4` resolves gaps 1–3 at source level and adds PostgreSQL contracts/live-test cases for the same invariants. This audit plus the refreshed README/handoff resolves gaps 4–5 at repository-documentation level. None of those source changes by themselves establish deployment, live database installation, runtime consumption, or production effectiveness.

## Adopt / defer decisions

Adopt now:
- append-only occurrence evidence;
- effect-operation journal and reconciliation gate;
- exact-subject effectiveness identity;
- PostgreSQL mirror and hostile tests;
- this portfolio audit as provenance.

Defer:
- generalized cross-repo orchestration;
- statistical significance/causal claims for effectiveness;
- distributed transport;
- model-weight updates;
- automatic rollback/deployment;
- universal donor abstraction.

The guiding rule is simple: reuse mechanics that close a demonstrated gap; do not build a museum of every clever thing in the portfolio.