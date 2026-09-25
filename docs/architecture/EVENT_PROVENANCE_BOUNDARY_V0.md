# Event and Provenance Boundary V0

F.U.C.K.U.P. owns corrective-learning semantics; it should not invent a transport envelope or duplicate telemetry.

## Event envelope

Lifecycle changes are represented as CloudEvents 1.0-compatible objects.

Namespace:

`org.fuckup.*`

Initial event families:

- `org.fuckup.failure.flagged`
- `org.fuckup.analysis.completed`
- `org.fuckup.correction.proposed`
- `org.fuckup.validation.passed`
- `org.fuckup.validation.failed`
- `org.fuckup.learning.promoted`
- `org.fuckup.learning.superseded`
- `org.fuckup.learning.revoked`
- `org.fuckup.rollback.executed`

The event `data` contains the F.U.C.K.U.P.-specific payload. The CloudEvents fields remain transport-neutral metadata.

## Provenance references

A correction record should reference source evidence rather than embedding complete trace/log/file payloads.

Supported provenance kinds begin with:

- TRACE / SPAN
- EVENT
- FILE / COMMIT
- RUN / DATASET
- ATTESTATION
- OTHER

Each reference may carry an algorithm-prefixed digest, media type, and source system.

OpenTelemetry/OpenInference trace identifiers should be bound by reference. in-toto/DSSE attestations can later be bound the same way.

## Invariant

A provenance reference proves only that an artifact was referenced and, when a digest is supplied, which exact content was intended. It does not by itself prove the artifact's claim is true.

Provenance is evidence plumbing, not epistemic authority.
