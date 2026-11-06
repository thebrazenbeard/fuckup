"""Additive display vocabulary for the F.U.C.K.U.P. protocol.

The approved public expansion is exactly:
    Find Unknowns, Calibrate Knowledge, Update Protocols

This module changes no persisted fields, schemas, lifecycle states, authority,
or operation behavior. Legacy keys remain the machine-readable contract.
"""

from __future__ import annotations

from dataclasses import dataclass


DISPLAY_EXPANSION = "Find Unknowns, Calibrate Knowledge, Update Protocols"
PRESENTATION_SCHEMA = "FUCKUP_STAGE_PRESENTATION_V1"


@dataclass(frozen=True, slots=True)
class StagePresentation:
    index: int
    pair_index: int
    display_word: str
    legacy_word: str
    schema_key: str
    objective: str


STAGES: tuple[StagePresentation, ...] = (
    StagePresentation(1, 1, "Find", "Flag", "flag",
                      "Identify a specific discrepancy and preserve what was observed."),
    StagePresentation(2, 1, "Unknowns", "Understand", "understand",
                      "Enumerate missing evidence, alternatives, and unresolved context."),
    StagePresentation(3, 2, "Calibrate", "Calibrate", "calibrate",
                      "Correct immediate assumptions and confidence to match evidence."),
    StagePresentation(4, 2, "Knowledge", "Know", "know",
                      "Assess bounded causal propositions, counterevidence, and falsifiers."),
    StagePresentation(5, 3, "Update", "Unlearn", "unlearn",
                      "Qualify versioned supersession without erasing historical records."),
    StagePresentation(6, 3, "Protocols", "Prevent", "prevent",
                      "Define scoped safeguards and observe their actual effectiveness."),
)

PAIRS: tuple[str, ...] = (
    "Find Unknowns",
    "Calibrate Knowledge",
    "Update Protocols",
)


def stage_for_schema_key(schema_key: str) -> StagePresentation:
    """Fail closed on unknown keys; never infer a schema migration."""
    for stage in STAGES:
        if stage.schema_key == schema_key:
            return stage
    raise KeyError(schema_key)


def schema_key_for_display_word(display_word: str) -> str:
    """Map exact public-stage wording to the unchanged V0.1 field name."""
    for stage in STAGES:
        if stage.display_word == display_word:
            return stage.schema_key
    raise KeyError(display_word)


def stages_for_pair(pair_index: int) -> tuple[StagePresentation, StagePresentation]:
    """One approved two-word pair comprises two ordered legacy stages."""
    if type(pair_index) is not int or pair_index not in (1, 2, 3):
        raise ValueError("pair_index must be 1, 2, or 3")
    return tuple(stage for stage in STAGES if stage.pair_index == pair_index)  # type: ignore[return-value]
