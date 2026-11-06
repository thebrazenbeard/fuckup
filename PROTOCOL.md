# The F.U.C.K.U.P. Protocol

> **Find Unknowns, Calibrate Knowledge, Update Protocols**

F.U.C.K.U.P. is an iterative, evidence-bound correction method: find the discrepancy and the gaps in understanding, calibrate what can reasonably be known, and update the relevant protocols only after the change has been qualified. The acronym deliberately forms three two-stage pairs.

## The six-stage loop

1. **[F] Find** — Record the specific difference between expectation and observation. Preserve inputs, outputs, timeframe, source identity, and the affected subject. A surprising result does not by itself establish fault.
2. **[U] Unknowns** — Identify absent evidence, uncertain chronology, dependencies, competing hypotheses, and contradictions. Do not fill gaps with plausible stories.
3. **[C] Calibrate** — Correct immediate assumptions, stated confidence, and containment decisions to match the available evidence. Unresolved ambiguity may require a pause, not a forced answer.
4. **[K] Knowledge** — State the exact causal proposition being assessed. Bind supporting and opposing evidence, alternatives, scope, and a meaningful falsifier. A proposed or review-ready cause is not automatically established knowledge.
5. **[U] Update** — Define the smallest justified correction to a rule, expectation, behavior, or process. Preserve the previous revision and provenance; qualify supersession and rollback before activation. This is not deletion of history or automatic model-weight editing.
6. **[P] Protocols** — Create or refine tests, guardrails, monitoring, escalation, and recovery procedures. Distinguish proposed controls from qualified, active, and observed-effective controls. No control guarantees zero recurrence.

## The three paired phases

- **Find Unknowns** — Discover what differs and what remains unresolved.
- **Calibrate Knowledge** — Align confidence and causal claims with evidence.
- **Update Protocols** — Qualify a specific correction and measure its effect.

Repeat the loop when new evidence, contradiction, or recurrence requires revising the earlier conclusion. Corrections should preserve unaffected valid state.

## V0.1 schema compatibility

These are **user-facing labels**, not persisted field renames:

| Display stage | Historical stage | Existing schema key |
| --- | --- | --- |
| Find | Flag | `flag` |
| Unknowns | Understand | `understand` |
| Calibrate | Calibrate | `calibrate` |
| Knowledge | Know | `know` |
| Update | Unlearn | `unlearn` |
| Protocols | Prevent | `prevent` |

The exact keys remain required in `schema/fuckup-retrospective.schema.json` and `schema/fuckup-record.schema.json`. Current state-machine transitions, promotion authorization, effect journals, injectors, and runtime APIs are unchanged. Historic `Flag/Understand/Calibrate/Know/Unlearn/Prevent` records remain valid and must not be silently rewritten. See `docs/architecture/PRESENTATION_MAPPING_V1.md`.

## Usage and evidence ceiling

Use the protocol for incident retrospectives, model or agent correction, software defects, process failures, and organizational learning. An analysis, test, or source change is not an installed or effective correction. Activation needs the existing trusted authority and real readback; effectiveness needs subsequent observations. The evidence available at each step determines the strongest claim justified.
