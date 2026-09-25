# Governed Injector Execution V1

Status: IMPLEMENTED SOURCE CANDIDATE
Base head: `ae2d8c4956fcf71e092e20ce5c9ad84a4f681e71`

## Contract

The execution boundary is:

`active binding -> exact injector -> prepared operation -> attempted execution -> adapter readback -> reconciliation -> bound outcome observation`

Each stage is evidence for that stage only. In particular:

- an active binding authorizes only its bounded correction application surface;
- handler resolution does not execute the handler;
- ATTEMPTED does not prove an external effect;
- a handler return does not prove the target consumed the effect;
- only adapter-specific readback may produce VERIFIED;
- only VERIFIED may produce an ACTIVE effectiveness observation;
- AMBIGUOUS blocks blind redispatch until reconciliation;
- a protected-effect handler is denied unless a separate host-provided authority seam explicitly admits it;
- binding currentness is revalidated immediately before each new execution;
- revocation/supersession blocks new execution but does not erase the duty to reconcile an already-attempted ambiguous effect.

## Exact execution identity

An executable `InjectionBinding` carries:

- correction id and revision;
- promotion id;
- selector and canonical selector digest;
- adapter name;
- adapter version.

Legacy bindings without all three execution-identity fields remain valid as historical/resolution records but are not executable by `ExecutionCoordinator`. New execution also requires a host-supplied currentness validator for the selected exact binding. That validator is an execution-time gate; it is intentionally not consulted when reconciling an operation that was already attempted.

`PluginRegistry.resolve_injector(name, version)` requires the exact registered version and an adapter-specific readback callable.

## Operation identity

Before handler execution, the coordinator prepares an `OperationIntent` whose digest covers:

- binding id;
- promotion id;
- correction id/revision;
- selector and selector digest;
- activation scope;
- adapter name/version;
- execution context;
- requested effect payload;
- target and injector operation kind.

The journal then records ATTEMPTED before the handler is invoked.

Reusing the same idempotency key for a different effect is a collision. Reusing it for an already ATTEMPTED or AMBIGUOUS operation cannot redispatch the handler.

## Readback and effectiveness

`InjectorReadback` classifies adapter evidence as VERIFIED, FAILED, or AMBIGUOUS.

VERIFIED requires non-null observed target state, from which the coordinator computes the readback digest. A label-only `VERIFIED` readback is rejected. The resulting `OutcomeObservation` is bound to correction revision, selector digest, promotion id, binding id, operation id, effect digest, and verification evidence reference.

FAILED is terminal for that operation and emits no effectiveness observation. AMBIGUOUS remains unresolved and emits no effectiveness observation.

## Durable binding continuity

`migrations/0005_governed_injector_execution.sql` adds nullable `adapter_version` for historical compatibility and an authorizer-only `create_versioned_authorized_binding(...)` path. The generic runtime role is explicitly denied that function.

The active-binding view exposes `adapter_version`. Old unversioned rows are not silently upgraded into exact execution subjects.

## Claim ceiling

This source implements and qualifies the reference execution boundary. It does not prove that a production adapter is installed, that a live target consumed an effect, that a protected effect is authorized, or that any correction is effective outside observed readback/outcome evidence.