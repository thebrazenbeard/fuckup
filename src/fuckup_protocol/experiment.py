from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProtocolNameCondition(StrEnum):
    FUCKUP = "FUCKUP"
    NEUTRAL_NAME = "NEUTRAL_NAME"
    ARBITRARY_NAME = "ARBITRARY_NAME"


class LabelCondition(StrEnum):
    SEMANTIC = "SEMANTIC"
    OPAQUE = "OPAQUE"


class SerializationCondition(StrEnum):
    YAML = "YAML"
    JSON = "JSON"
    MARKDOWN = "MARKDOWN"
    PROSE = "PROSE"


class FeedbackCondition(StrEnum):
    SELF_REFLECTION = "SELF_REFLECTION"
    VERIFIED_EXTERNAL = "VERIFIED_EXTERNAL"


@dataclass(frozen=True, slots=True)
class ExperimentCondition:
    id: str
    protocol_name: ProtocolNameCondition
    labels: LabelCondition
    serialization: SerializationCondition
    feedback: FeedbackCondition

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("condition id is required")


@dataclass(frozen=True, slots=True)
class ExperimentOutcome:
    condition_id: str
    model_id: str
    task_id: str
    initial_correct: bool
    correction_applied: bool
    exact_recurrence_passed: bool
    near_transfer_passed: bool
    far_transfer_passed: bool
    retain_passed: bool
    anti_trigger_passed: bool
    schema_valid: bool
    introduced_error: bool
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None

    @property
    def durable_correction_success(self) -> bool:
        return (
            self.correction_applied
            and self.exact_recurrence_passed
            and self.near_transfer_passed
            and self.retain_passed
            and self.anti_trigger_passed
            and not self.introduced_error
        )


def factorial_conditions() -> tuple[ExperimentCondition, ...]:
    """Return the core fully crossed condition set.

    This intentionally crosses factors instead of comparing one bundled
    F.U.C.K.U.P. condition against one bundled control. That lets experiments
    distinguish name salience, semantic labels, serialization, and feedback
    grounding rather than confounding them.
    """

    conditions: list[ExperimentCondition] = []
    index = 1
    for protocol_name in ProtocolNameCondition:
        for labels in LabelCondition:
            for serialization in SerializationCondition:
                for feedback in FeedbackCondition:
                    conditions.append(
                        ExperimentCondition(
                            id=f"c{index:03d}",
                            protocol_name=protocol_name,
                            labels=labels,
                            serialization=serialization,
                            feedback=feedback,
                        )
                    )
                    index += 1
    return tuple(conditions)
