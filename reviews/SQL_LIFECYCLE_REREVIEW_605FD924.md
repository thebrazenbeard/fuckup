# F.U.C.K.U.P. SQL/Lifecycle Exact-Head Re-Review — 605fd924

Reviewed exact head: `605fd924849fc0b534a54bafc946e9d5329010fa`

Disposition: `BLOCKED_P0_MIGRATION_PARSE`

## Material improvements since f865f14b

The lead remediation closes the major residual SQL design issues from the prior re-review:

- `sql/claim_job.sql` now delegates to the guarded `claim_worker_job()` function;
- supersession locks the target correction and requires the target's current revision;
- promotions are unique per correction/revision, making correction-level revocation coherent;
- event idempotency now has explicit same-effect replay / different-effect collision semantics in the Python ledger;
- the Python ledger now independently evaluates the canonical qualification suite before promotion;
- SQL contract regression tests were added;
- the remediation map records the remaining live-PostgreSQL qualification ceiling.

## P0 — migration cannot parse as written

Exact source lines in `migrations/0001_core.sql` contain invalid/mismatched PL/pgSQL dollar quoting.

Observed at this exact head:

```text
line 212: RETURNS SETOF events AS $
...
line 273: $ LANGUAGE plpgsql;

line 275: CREATE FUNCTION validate_correction_revision_insert() RETURNS trigger AS $
...
line 350: $$ LANGUAGE plpgsql;
```

PostgreSQL dollar-quoted function bodies require a complete delimiter such as `$$ ... $$` or `$tag$ ... $tag$`. A lone `$` is not a valid matching dollar-quote delimiter.

The first function uses `$ ... $`; the second opens with `$` and closes with `$$`.

Therefore the migration is source-invalid before any behavioral qualification can begin.

### Why current tests miss it

`tests/test_sql_contract.py` performs substring assertions against the migration text. It does not parse or execute PostgreSQL SQL/PLpgSQL, so all static contract tests can pass while the migration itself is syntactically invalid.

### Required repair

Change both functions to consistent valid dollar quoting, e.g.:

```sql
RETURNS SETOF events AS $$
...
$$ LANGUAGE plpgsql;

CREATE FUNCTION validate_correction_revision_insert() RETURNS trigger AS $$
...
$$ LANGUAGE plpgsql;
```

Then add at least one qualification that actually parses/applies the migration against PostgreSQL when a runtime is available.

A source-level delimiter-balance regression test is useful as a cheap guard but is not a substitute for PostgreSQL execution.

## Remaining non-SQL-core findings

After the SQL delimiter repair, these earlier reference-layer issues still need disposition:

1. `ValidationReport.evaluate(... required_kinds=frozenset())` can be called with an empty required suite.
2. Unknown failed test kinds are ignored in `ValidationReport.evaluate()`.
3. `ValidationReport` does not itself carry correction id/revision/digest; standalone `StrictPromotionPolicy` can be given a report detached from the correction that produced it.
4. `CorrectionRevision` is frozen but its `payload` mapping remains mutable; payload can change without recomputing `subject_digest`.
5. `protect_promotion_mutation()` still does not require `revoked_at >= activated_at`.

The Python ledger now protects the normal promotion path from missing canonical tests by calling `ValidationReport.evaluate(current, qualification)` with default requirements, but unknown failing test kinds and payload mutability remain relevant even through that path.

## Evidence ceiling

This re-review is exact-source inspection. No PostgreSQL runtime was available here; the parse blocker is visible directly in the committed migration text.
