# Portfolio Architecture Audit — 2026-09-25

Status: CURRENT OBSERVATION FOR THIS BUILD
Purpose: identify reusable architecture for F.U.C.K.U.P. without turning the portfolio into implicit runtime dependencies.

## Inventory cut

The connected GitHub inventory for `thebrazenbeard` contains **70 repositories**: **52 public**, **18 private**, with **2 archived** at this observation cut.

This public repository records public-safe donor detail only. Private repositories were included in the audit but are intentionally not named or described here merely because they were visible to the audit.

The earlier Discovery census recorded 59 repositories on 2026-09-22, so that census is historical for currentness purposes.

## Audit method

Every accessible repository received metadata triage. Public repositories received README/source-orientation review where available. Repositories with plausible reusable mechanics received deeper source/contract inspection. A mechanism was considered for adoption only when it matched an existing F.U.C.K.U.P. gap; thematic similarity alone was not enough.

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

### Highest-value gaps

1. **Deduplication currently loses per-occurrence evidence.** The incident counter grows, but a repeated observation is not independently preserved.
2. **Effect ambiguity lacks a first-class portable journal.** Existing idempotency helps, but it does not itself encode PREPARED/ATTEMPTED/AMBIGUOUS/readback recovery.
3. **Effectiveness attribution is too weak.** Observations can be summarized without proving they belong to one exact correction/promotion/binding subject.
4. **The handoff/current docs lag implementation reality.** The branch has substantially outgrown the old “next frontier” wording.
5. **Portfolio provenance is not yet recorded in-repo for the current build.** The project has GitHub landscape research, but not this current portfolio-wide architecture cut.

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
