from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class InjectionBinding:
    id: str
    correction_id: str
    correction_revision: int
    selector: Mapping[str, str]
    priority: int = 0
    active: bool = True

    def __post_init__(self) -> None:
        if self.correction_revision < 1:
            raise ValueError("correction_revision must be >= 1")

    @property
    def specificity(self) -> int:
        return len(self.selector)

    def matches(self, context: Mapping[str, str]) -> bool:
        return self.active and all(context.get(key) == value for key, value in self.selector.items())


class BindingConflictError(ValueError):
    pass


def resolve_binding(bindings: tuple[InjectionBinding, ...], context: Mapping[str, str]) -> InjectionBinding | None:
    """Resolve one binding deterministically or fail closed on an unresolved tie.

    Precedence:
    1. highest explicit priority;
    2. narrowest/more-specific selector;
    3. newer revision only when candidates belong to the same correction family;
    4. otherwise fail closed rather than relying on input/retrieval order.
    """

    candidates = [binding for binding in bindings if binding.matches(context)]
    if not candidates:
        return None

    highest_priority = max(binding.priority for binding in candidates)
    candidates = [binding for binding in candidates if binding.priority == highest_priority]

    highest_specificity = max(binding.specificity for binding in candidates)
    candidates = [binding for binding in candidates if binding.specificity == highest_specificity]

    if len(candidates) == 1:
        return candidates[0]

    correction_ids = {binding.correction_id for binding in candidates}
    if len(correction_ids) == 1:
        newest_revision = max(binding.correction_revision for binding in candidates)
        newest = [binding for binding in candidates if binding.correction_revision == newest_revision]
        if len(newest) == 1:
            return newest[0]

    ids = ", ".join(sorted(binding.id for binding in candidates))
    raise BindingConflictError(f"unresolved active correction binding conflict: {ids}")
