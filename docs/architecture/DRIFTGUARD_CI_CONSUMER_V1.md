# DriftGuard CI result → F.U.C.K.U.P. observation V1

## Boundary and evidence class

This adapter accepts JSON text from the `driftguard ci` command, not a claim
that the command ran on a trusted machine. The authoritative source shape is
`CiGateResult.payload()` plus the CLI-added `result_digest` in DriftGuard's
`DRIFTGUARD_CI_GATE_RESULT_V1` contract. The policy, baseline, and candidate
digest strings are copied as producer assertions. No separate producer code or
runtime service is imported into F.U.C.K.U.P.

`consume_driftguard_ci_result()`:

1. Parses `str` or UTF-8 `bytes` as JSON, rejecting duplicate keys at **every
   nesting level**, malformed/nonfinite values, invalid schema or decisions,
   unexpected/missing fields, invalid metrics, and noncanonical digest strings.
   The aggregate decision and reason codes must also agree with the producer's
   metric-status precedence (`BLOCK` dominates; an unrepresentable regression
   is `UNKNOWN` ahead of missing-metric policy handling; missing metric
   evidence is `UNKNOWN` or policy-permitted `WARN`; all-pass metrics produce
   `PASS`). It validates the derivable per-metric consistency of missing values,
   regression presence, status, severity, and reason families. The V1 numeric
   hardening additions `regression_unrepresentable`,
   `one_or_more_regressions_unrepresentable`, and
   `regression_exceeds_limit_below_display_resolution` are recognized.
2. Canonicalizes the parsed object **excluding `result_digest`**, with
   `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False,
   allow_nan=False)` and compares its SHA-256 hex digest with the supplied
   `result_digest`.
3. Returns a `FuckupEvent` of type `org.fuckup.admission.observed` containing
   the exact validated gate-result metadata and a typed `EVENT` provenance
   reference to the result content digest. The event retains an immutable JSON
   snapshot: mutating a nested object obtained from `event.data` cannot change
   the later serialized result beneath the fixed digest. The event is not
   published or saved.

The four producer decisions remain distinct *admission evidence*: `PASS` and
`WARN` are not necessarily effectiveness, `BLOCK` does not by itself prove an
actual operational failure, and `UNKNOWN` reports insufficient or incompatible
evidence rather than an established failure. No outcome automatically emits
`org.fuckup.failure.flagged`. An authorized caller must separately apply a
policy and provide any additional evidence required to classify an incident.

## Example (caller-owned transport)

```python
from datetime import datetime, timezone
from pathlib import Path
from fuckup_protocol import consume_driftguard_ci_result

wire_json = Path("driftguard-result.json").read_text(encoding="utf-8")
event = consume_driftguard_ci_result(
    wire_json,
    event_id="run-123-observation-1",  # explicit occurrence identity
    source="urn:example:ci-observer",
    subject="agent/checkout-evaluator",
    observed_at=datetime.now(timezone.utc),
)
payload = event.to_cloudevent()  # in-memory JSON-safe telemetry only
```

Calling the function repeatedly with a different `event_id` preserves
distinct occurrences even if the DriftGuard result content digest is the
same. With the same explicit inputs, the adapter's resulting event is stable.

## Trust and non-effects

- An unkeyed digest detects accidental or unaccompanied tampering, **not** a
  malicious actor who can replace JSON and recalculate the digest. Origin
  authentication, trusted run identity, transport, replay control, and
  admission/incident policy all belong to an external caller.
- These checks reject internally impossible V1 status combinations but cannot
  reproduce the original evaluation without the exact policy and source
  reports. A forged, self-consistent result can still pass structural checks.
- Source result digests are untrusted references, not proof of evaluator
  correctness, workload coverage, causal drift, production impact, or a
  protected effect. Neither `PASS` nor `BLOCK` provides promotion authority.
- No network calls, database access, file writes, Bus delivery, deployment,
  incident creation, deduplication, or downstream state mutation occurs.
- Unsupported future result schemas fail closed until reviewed and supported
  explicitly. The consumer does not silently reinterpret changed semantics.
- Input bytes must be UTF-8 (not UTF-16/UTF-32 JSON auto-detection), and any
  invalid Unicode encountered during canonicalization fails with `ValueError`.

## Source binding and verification

- Consumer baseline: `thebrazenbeard/fuckup@850fe1ce40bd68992b9cf3a531af078200e0c7a0`
- Producer contract reviewed: `thebrazenbeard/driftguard@d59b0695a26ebeddbea2f3d8de3820b05d11f04b`, `src/driftguard/ci_gate.py` and `src/driftguard/cli.py`
- Numeric V1 compatibility inspected against the separately proposed
  `driftguard_agent2/src/driftguard/ci_gate.py` source candidate; this is a
  compatibility test target, not a claim that the producer patch is merged or
  deployed.
- Tests: `tests/test_driftguard_consumer.py` exercises all decisions, independent
  known digests, distinct occurrence IDs, content tampering, duplicate keys,
  nonfinite values, malformed types/digests, and timezone constraints.

Source-level tests qualify this parsing and event construction boundary only;
they do not establish any runtime connection between the two repositories.
