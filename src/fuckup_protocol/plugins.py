from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, Mapping


class HandlerFamily(StrEnum):
    DETECTOR = "DETECTOR"
    NORMALIZER = "NORMALIZER"
    FINGERPRINTER = "FINGERPRINTER"
    ANALYZER = "ANALYZER"
    AMBIGUITY_RESOLVER = "AMBIGUITY_RESOLVER"
    ROOT_CAUSE_RESOLVER = "ROOT_CAUSE_RESOLVER"
    CORRECTION_GENERATOR = "CORRECTION_GENERATOR"
    QUALIFIER = "QUALIFIER"
    POLICY_GATE = "POLICY_GATE"
    INJECTOR = "INJECTOR"
    OBSERVER = "OBSERVER"
    STORAGE_ADAPTER = "STORAGE_ADAPTER"


class SideEffectClass(StrEnum):
    PURE = "PURE"
    READ_ONLY = "READ_ONLY"
    REVERSIBLE_WRITE = "REVERSIBLE_WRITE"
    PROTECTED_EFFECT = "PROTECTED_EFFECT"


@dataclass(frozen=True, slots=True)
class HandlerSpec:
    name: str
    family: HandlerFamily
    version: str
    side_effect: SideEffectClass
    idempotent: bool
    retryable: bool
    timeout_seconds: float | None = None
    input_schema_ref: str | None = None
    output_schema_ref: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("handler name is required")
        if not self.version:
            raise ValueError("handler version is required")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive when supplied")


HandlerCallable = Callable[[Mapping[str, Any]], Mapping[str, Any]]
InjectorReadbackCallable = Callable[[Mapping[str, Any], Mapping[str, Any] | None], Any]


class DuplicateHandlerError(ValueError):
    pass


class UnknownHandlerError(KeyError):
    pass


class MissingInjectorReadbackError(ValueError):
    pass


class PluginRegistry:
    """Named handler registry with explicit contracts and no implicit execution."""

    def __init__(self) -> None:
        self._entries: dict[tuple[HandlerFamily, str], tuple[HandlerSpec, HandlerCallable]] = {}
        self._injector_readbacks: dict[tuple[HandlerFamily, str], InjectorReadbackCallable] = {}

    def register(self, spec: HandlerSpec, handler: HandlerCallable) -> None:
        key = (spec.family, spec.name)
        if key in self._entries:
            raise DuplicateHandlerError(f"handler already registered: {spec.family}/{spec.name}")
        self._entries[key] = (spec, handler)

    def register_injector(
        self,
        spec: HandlerSpec,
        handler: HandlerCallable,
        readback: InjectorReadbackCallable,
    ) -> None:
        if spec.family != HandlerFamily.INJECTOR:
            raise ValueError("register_injector requires an INJECTOR handler spec")
        self.register(spec, handler)
        self._injector_readbacks[(spec.family, spec.name)] = readback

    def resolve(self, family: HandlerFamily, name: str) -> tuple[HandlerSpec, HandlerCallable]:
        try:
            return self._entries[(family, name)]
        except KeyError as exc:
            raise UnknownHandlerError(f"unknown handler: {family}/{name}") from exc

    def resolve_exact(
        self,
        family: HandlerFamily,
        name: str,
        version: str,
    ) -> tuple[HandlerSpec, HandlerCallable]:
        spec, handler = self.resolve(family, name)
        if spec.version != version:
            raise UnknownHandlerError(
                f"exact handler version unavailable: {family}/{name}@{version}; current is {spec.version}"
            )
        return spec, handler

    def resolve_injector(
        self,
        name: str,
        version: str,
    ) -> tuple[HandlerSpec, HandlerCallable, InjectorReadbackCallable]:
        spec, handler = self.resolve_exact(HandlerFamily.INJECTOR, name, version)
        try:
            readback = self._injector_readbacks[(HandlerFamily.INJECTOR, name)]
        except KeyError as exc:
            raise MissingInjectorReadbackError(
                f"injector has no registered readback: {name}@{version}"
            ) from exc
        return spec, handler, readback

    def specs(self, family: HandlerFamily | None = None) -> tuple[HandlerSpec, ...]:
        specs = [spec for spec, _handler in self._entries.values()]
        if family is not None:
            specs = [spec for spec in specs if spec.family == family]
        return tuple(sorted(specs, key=lambda spec: (spec.family.value, spec.name, spec.version)))