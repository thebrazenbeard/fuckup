# Execution Integrity V2 Implementation Plan

> **For agentic workers:** Use the host's available task-by-task implementation workflow. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add crash-safe effect journaling, append-only incident occurrence evidence, and exact-subject effectiveness attribution to the existing F.U.C.K.U.P. runtime.

**Architecture:** Extend the existing Python reference semantics and PostgreSQL authority model without replacing current correction/promotion behavior. New records are append-only where history matters; guarded functions enforce operation transitions and runtime privileges.

**Tech Stack:** Python 3.11+, pytest, Hypothesis where useful, PostgreSQL 16 SQL migrations, GitHub Actions.

## Global Constraints

- Base implementation is `build/fuckup-protocol-v1@ff46bcf822a89701201e6153be923239814e5b61`.
- Preserve exact-revision qualification, authorizer/runtime role separation, and current test behavior.
- No donor repository becomes a runtime dependency.
- No merge, deploy, install, provider mutation, or live database migration is part of this plan.
- External effect claims require readback evidence; retry after ambiguity must be reconciliation-driven.

---

### Task 1: Add effect-operation journal semantics

**Files:**
- Create: `src/fuckup_protocol/operations.py`
- Create: `tests/test_operations.py`
- Modify: `src/fuckup_protocol/__init__.py`

**Interfaces:**
- Produces: `OperationState`, `OperationIntent`, `OperationEvent`, `OperationJournal`, collision/transition exceptions.
- Operation identity is a canonical SHA-256 digest over target, operation kind, and effect payload.

- [ ] Add tests for prepare, idempotent same-effect prepare, collision on reused idempotency key, attempt, ambiguous state, reconcile-to-verified/failed, and terminal-state rejection.
- [ ] Run `python -m pytest -q tests/test_operations.py`; expect import/missing-symbol failure.
- [ ] Implement immutable intents plus append-only lifecycle events and fail-closed transition checks.
- [ ] Re-run focused tests; expect pass.
- [ ] Run `python -m pytest -q tests/test_operations.py tests/test_ledger.py tests/test_jobs.py`; expect pass.
- [ ] Commit the passing deliverable.

### Task 2: Preserve duplicate occurrence evidence and bind effectiveness subjects

**Files:**
- Modify: `src/fuckup_protocol/ledger.py`
- Modify: `src/fuckup_protocol/effectiveness.py`
- Modify: `tests/test_ledger.py`
- Modify: `tests/test_effectiveness.py`

**Interfaces:**
- Produces: immutable `IncidentOccurrenceRecord` and ledger occurrence query.
- Produces: `EffectivenessSubject`; `OutcomeObservation` carries one subject; summarization rejects mixed subjects.

- [ ] Add failing tests proving every duplicate submission creates a distinct occurrence with monotonic ordinal and payload digest.
- [ ] Add failing tests proving mixed correction/promotion/binding subjects cannot be aggregated.
- [ ] Run focused ledger/effectiveness tests; expect failures for missing behavior.
- [ ] Implement the minimum records, digests, and subject checks.
- [ ] Run focused tests; expect pass.
- [ ] Run `python -m pytest -q tests/test_ledger.py tests/test_effectiveness.py tests/test_validation_gate.py`; expect pass.
- [ ] Commit the passing deliverable.

### Task 3: Mirror execution integrity in PostgreSQL

**Files:**
- Create: `migrations/0004_execution_integrity.sql`
- Modify: `tests/test_db_authority_contract.py`
- Modify: `tests/postgres/test_live_qualification.py`
- Modify: `docs/architecture/DATABASE_AUTHORITY.md`

**Interfaces:**
- Tables: `incident_occurrences`, `effect_operations`, `effect_operation_events`.
- Guarded functions: `prepare_effect_operation`, `record_effect_attempt`, `reconcile_effect_operation`.
- Runtime role receives only the bounded function/table access needed by this contract.

- [ ] Add SQL-contract tests for table/function presence, append-only history, and privilege declarations.
- [ ] Add live PostgreSQL hostile cases for idempotency collision, illegal redispatch, and terminal reopening.
- [ ] Run `python -m pytest -q tests/test_db_authority_contract.py tests/postgres/test_live_qualification.py`; expect relevant failures or live-test skip without database URL.
- [ ] Implement migration with canonical effect digests supplied by caller and verified identity/idempotency semantics.
- [ ] Re-run focused tests; expect source-contract pass and live pass when PostgreSQL is available.
- [ ] Commit the passing deliverable.

### Task 4: Reconcile documentation and full qualification

**Files:**
- Modify: `docs/implementation/NEXT_FRONTIER.md`
- Modify: `docs/handoff/FUCKUP_RUNTIME_HANDOFF_20260923.md`
- Keep: `docs/research/PORTFOLIO_ARCHITECTURE_AUDIT_20260925.md`
- Keep: `docs/specs/2026-09-25-execution-integrity-v2-design.md`

**Interfaces:**
- Documentation must distinguish source implementation from deployment/runtime effect.
- Handoff must name the exact branch/head after implementation and the next unimplemented frontier.

- [ ] Update stale “first vertical slice” wording to distinguish completed mechanisms from remaining work.
- [ ] Run `python -m pytest -q`; expect full pass.
- [ ] Run `git diff --check` and confirm a clean generated-artifact state.
- [ ] Read back the exact branch head and changed files.
- [ ] Commit the documentation reconciliation.

## Unresolved product decisions

None required for this bounded slice. Automatic retry policy, statistical confidence thresholds, and automatic rollback remain intentionally outside scope rather than silently chosen.
