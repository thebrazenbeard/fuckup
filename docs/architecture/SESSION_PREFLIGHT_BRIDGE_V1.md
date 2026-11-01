# Session preflight bridge V1 — external correction, not weight mutation

Status: **source implementation + local unit qualification**. No hosted ChatGPT
session hook, deployed PostgreSQL bridge, third-party provider readback, or
cross-session behavioral effectiveness has been demonstrated.

## Host integration contract

A model host that controls its own request assembly can use
`load_reference_session_preflight()` at the beginning of **each** relevant
session or task, then `verify_materialized_prompt()` on the **actual outgoing
model request** immediately before dispatch.

1. The correction must already have been qualified, promoted by the trusted
   authorizer, and bound through the version-pinned `reference-file@1` injector.
   A plain retrospective or arbitrary JSON cannot create such a binding.
2. The host supplies an authenticated selector context, a pinned `reference-file`
   target, a known verified operation ID, and a unique host session ID.
3. The preflight reads the active binding and exact correction revision from
   PostgreSQL, checks binding currentness, then recovers the prior VERIFIED
   operation, original verification event and exact durable outcome.
4. The preflight freshly reads the persisted reference-file effect and checks
   its identity, payload, operation digest and historical readback digest.
   Stale, missing, conflicting, fabricated or revoked records block the load.
5. It returns a `SessionPreflight.message` plus content digest. **This is only
   PREPARED, not yet injected.**
6. The host includes that message **once** in a `system` or `developer` message,
   then calls `verify_materialized_prompt(preflight, actual_model_messages)`.
   The verifier refuses to accept text that appears only in a `user` message,
   a planned request, or an agent's self-report.
7. Call `verify_dispatch_currentness()` immediately before dispatch. This
   narrows (but cannot eliminate) the revocation race between preflight and
   a remote provider call.
8. The caller must not dispatch the model request if any gate fails. It
   should log preflight and materialization evidence separately and evaluate
   **actual behavior** afterward; the two gates cannot prove compliance.

This bridge is fail-closed with respect to the requested correction. It is **not**
an authorization for model-provider effects or a replacement for host-level
message integrity. The model itself can still ignore or misunderstand an
injected correction. Host request assembly is the strongest evidenced point.

## Operator entry point (read-only)

Install with `pip install -e ".[postgres]"` from an authorized checkout. The
host must configure its trusted `FUCKUP_DATABASE_URL` and `FUCKUP_SCHEMA` as
environment variables; do not put credentials on a command line or in logs.

```sh
fuckup-session-preflight \
  --reference-root /srv/fuckup/reference-state \
  --target reference-file:manuscript-editor \
  --operation-id VALID-PREVIOUS-OPERATION-UUID \
  --session-id session-20261101-001 \
  --context agent=manuscript-editor \
  --context task=editorial
```

Output is JSON with `status: PREPARED_NOT_MATERIALIZED`, the exact instruction
and source identities. It intentionally does not say "activated in ChatGPT".
Run the Python host-side materialization verifier before actually sending any
model request. Avoid logging the instruction text if the correction is private.

## Example host usage

```python
from fuckup_protocol import (
    PostgresExecutionStore, ReferenceFileInjector,
    load_reference_session_preflight, verify_materialized_prompt,
    verify_dispatch_currentness,
)

# Use a trusted connection factory that pins the authorized PostgreSQL schema.
store = PostgresExecutionStore(trusted_connection_factory)
preflight = load_reference_session_preflight(
    store=store,
    adapter=ReferenceFileInjector("/srv/fuckup/reference-state"),
    context={"agent": "manuscript-editor", "task": "editorial"},
    expected_target="reference-file:manuscript-editor",
    operation_id=verified_operation_id,
    session_id=host_generated_session_id,
)
actual_request = [
    {"role": "developer", "content": preflight.message},
    {"role": "user", "content": current_user_message},
]
receipt = verify_materialized_prompt(preflight, actual_request)
verify_dispatch_currentness(preflight, store=store,
                            context={"agent": "manuscript-editor", "task": "editorial"})
# Only now may a host that controls dispatch send this exact request.
```

## Failure boundaries

> **Hostile challenge:** A local fixture can fabricate a convincing prompt
> assembly. Tests of this bridge do not prove that the closed ChatGPT web UI
> exposed a `developer` message slot, that its server received the request,
> or that the model followed the correction.

> **Hostile challenge:** A previously VERIFIED file may outlive its promotion.
> The bridge must revalidate the current binding on every session; no local
> receipt or cached prompt is perpetual authority.

> **Hostile challenge:** A host that is itself malicious or compromised could
> lie about the `actual_model_messages`. Host-controlled assembly readback is
> not provider-side attestation, and the bridge does not claim otherwise.

No automatic cross-repository rollout is included. A real ChatGPT-facing
integration must expose an authorized retrieval surface, obtain consent to
route the relevant sessions through it, independently verify provider/context
delivery where feasible, and add outcome-based recurrence testing.
