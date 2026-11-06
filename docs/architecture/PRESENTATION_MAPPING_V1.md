# F.U.C.K.U.P. presentation mapping V1

**Public expansion:** **Find Unknowns, Calibrate Knowledge, Update Protocols**.

This is an additive display/interpretation layer over the existing six-stage
corrective-learning protocol. Each of the three approved two-word pairs covers
two stages, in order. It is not a schema migration, a new incident state
machine, an authorization change, or evidence of a deployed prompt/runtime.

| Pair | Display stage | Legacy stage | Persisted JSON field | Operating question |
| --- | --- | --- | --- | --- |
| Find Unknowns | Find | Flag | `flag` | What specifically differs from what was expected? |
| Find Unknowns | Unknowns | Understand | `understand` | Which observations, causes, alternatives, or dependencies remain unresolved? |
| Calibrate Knowledge | Calibrate | Calibrate | `calibrate` | What assumptions, confidence, or immediate containment must change? |
| Calibrate Knowledge | Knowledge | Know | `know` | What conclusion is actually supported, bounded, and falsifiable? |
| Update Protocols | Update | Unlearn | `unlearn` | Which exact rule or behavior should be superseded after qualification? |
| Update Protocols | Protocols | Prevent | `prevent` | Which qualified safeguard can reduce recurrence, and how will effectiveness be measured? |

## Stable machine contract

The V0.1 `schema/fuckup-retrospective.schema.json` and
`schema/fuckup-record.schema.json` retain the required keys `flag`,
`understand`, `calibrate`, `know`, `unlearn`, `prevent`. The new `presentation`
module maps exact display words to these keys. No existing record, SQL column,
API payload, exported event, test fixture, or persisted history is rewritten.
Historic documentation using the old labels remains valid evidence of its
original era; do not silently replace quoted history with the new wording.

## Evidence and effects

- **Find** does not assume a discrepancy is necessarily the system's fault.
- **Unknowns** preserves competing explanations instead of forcing a cause.
- **Calibrate** may adjust confidence or containment without promotion.
- **Knowledge** does not imply certainty. A root cause can remain proposed,
  ambiguous, contradicted, or unqualified. Evidence must bind to exact subjects
  and should include counterevidence and a meaningful falsifier.
- **Update** means versioned, qualified supersession—not purging history,
  overwriting a model's weights, or retroactive consent.
- **Protocols** means tests, controls, monitoring, and review. They reduce
  observed recurrence within an evidenced scope; no absolute guarantee follows.

Correction state transitions, trusted-authorizer promotion, effect journals,
readbacks, session-preflight materialization, and actual behavioral effectiveness
remain governed by their existing contracts. This mapping grants no new effect.

## Adoption

New user-facing narratives may use the six new labels. Existing machine
schemas, APIs, and old retrospective documents continue to use the legacy
fields until an independently reviewed versioned migration is authorized.

The source-only mapping is in `src/fuckup_protocol/presentation.py`, with
regression tests in `tests/test_presentation.py`.
