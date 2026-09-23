from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


def _freeze_selector(value: Mapping[str, str], *, field: str) -> Mapping[str, str]:
    normalized: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{field} keys must be non-empty strings")
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field} values must be non-empty strings")
        normalized[key] = item
    if not normalized:
        raise ValueError(f"{field} must not be empty")
    return MappingProxyType(normalized)


def selector_within_scope(selector: Mapping[str, str], activation_scope: Mapping[str, str]) -> bool:
    """Return True when selector is equal to or narrower than authorization scope."""
    return bool(activation_scope) and all(selector.get(key) == value for key, value in activation_scope.items())


@dataclass(frozen=True, slots=True)
class InjectionBinding:
    id: str
    correction_id: str
    correction_revision: int
    selector: Mapping[str, str]
    activation_scope: Mapping[str, str]
    priority: int = 0
    active: bool = True

    def __post_init__(self) -> None:
        if self.correction_revision < 1:
            raise ValueError("correction_revision must be >= 1")
        selector = _freeze_selector(self.selector, field="selector")
        scope = _freeze_selector(self.activation_scope, field="activation_scope")
        if not selector_within_scope(selector, scope):
            raise ValueError("binding selector must be equal to or narrower than activation scope")
        object.__setattr__(self, "selector", selector)
        object.__setattr__(self, "activation_scope", scope)

    @property
    def specificity(self) -> int:
        return len(self.selector)

    def matches(self, context: Mapping[str, str]) -> bool:
        return self.active and all(context.get(key) == value for key, value in self.selector.items())


class BindingConflictError(ValueError):
    pass


def resolve_binding(bindings: tuple[InjectionBinding, ...], context: Mapping[str, str]) -> InjectionBinding | None:
    """Resolve one binding deterministically or fail closed on an unresolved tie."""

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
