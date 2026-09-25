import pytest

from fuckup_protocol.plugins import (
    DuplicateHandlerError,
    HandlerFamily,
    HandlerSpec,
    PluginRegistry,
    SideEffectClass,
    UnknownHandlerError,
)


def _echo(payload):
    return dict(payload)


def test_registry_requires_explicit_unique_family_name():
    registry = PluginRegistry()
    spec = HandlerSpec(
        name="default",
        family=HandlerFamily.ANALYZER,
        version="1",
        side_effect=SideEffectClass.PURE,
        idempotent=True,
        retryable=True,
    )
    registry.register(spec, _echo)
    with pytest.raises(DuplicateHandlerError):
        registry.register(spec, _echo)


def test_registry_resolves_without_executing_handler():
    registry = PluginRegistry()
    spec = HandlerSpec(
        name="memory-injector",
        family=HandlerFamily.INJECTOR,
        version="1",
        side_effect=SideEffectClass.REVERSIBLE_WRITE,
        idempotent=True,
        retryable=True,
    )
    registry.register(spec, _echo)
    resolved_spec, handler = registry.resolve(HandlerFamily.INJECTOR, "memory-injector")
    assert resolved_spec == spec
    assert handler({"x": 1}) == {"x": 1}


def test_unknown_handler_fails_closed():
    registry = PluginRegistry()
    with pytest.raises(UnknownHandlerError):
        registry.resolve(HandlerFamily.QUALIFIER, "missing")


def test_protected_effect_is_declared_not_authorized():
    spec = HandlerSpec(
        name="weight-updater",
        family=HandlerFamily.INJECTOR,
        version="1",
        side_effect=SideEffectClass.PROTECTED_EFFECT,
        idempotent=True,
        retryable=False,
    )
    assert spec.side_effect == SideEffectClass.PROTECTED_EFFECT
