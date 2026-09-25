import fuckup_protocol


def test_every_declared_root_export_is_bound():
    missing = [name for name in fuckup_protocol.__all__ if not hasattr(fuckup_protocol, name)]
    assert missing == []


def test_critical_root_exports_are_available():
    for name in [
        "authorize_promotion",
        "PromotionAuthorization",
        "FuckupEvent",
        "ProvenanceRef",
        "resolve_binding",
        "summarize_effectiveness",
        "factorial_conditions",
        "assess_ambiguity",
        "OperationJournal",
        "OperationState",
        "EffectivenessSubject",
        "IncidentOccurrenceRecord",
        "ExecutionCoordinator",
        "InjectorReadback",
        "ReadbackDisposition",
        "selector_digest",
    ]:
        assert hasattr(fuckup_protocol, name)