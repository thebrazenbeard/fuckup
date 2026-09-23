from pathlib import Path


AUTHORITY = Path("migrations/0003_promotion_authority.sql").read_text()


def test_runtime_cannot_directly_create_or_broaden_protected_effects():
    assert "runtime may prepare and qualify, but may not create/broaden protected effects" in AUTHORITY
    assert "REVOKE INSERT (id, correction_id" in AUTHORITY
    assert "REVOKE INSERT (id, promotion_id" in AUTHORITY
    assert "retains protected promotion/binding DML authority" in AUTHORITY


def test_distinct_authorizer_role_is_source_controlled():
    for token in [
        "authority_role_assignments",
        "'runtime', 'authorizer'",
        "configure_fuckup_authorizer_role",
        "already bound to incompatible authority kind",
        "create_authorized_promotion",
        "create_injection_binding",
    ]:
        assert token in AUTHORITY


def test_scope_contract_is_flat_scalar_and_binding_must_be_narrower():
    for token in [
        "selector_scope_is_valid",
        "jsonb_typeof(item.value) NOT IN ('string', 'number', 'boolean')",
        "NEW.selector @> approved_scope",
        "binding selector is broader than promotion activation scope",
    ]:
        assert token in AUTHORITY


def test_binding_restrictions_are_monotonic():
    for token in [
        "binding reactivation requires fresh authorization",
        "binding expiry may only stay the same or become earlier",
        "binding expiry extension requires fresh authorization",
        "injection bindings are historical evidence and cannot be deleted",
    ]:
        assert token in AUTHORITY


def test_authorized_promotion_requires_provenance_reference():
    assert "ADD COLUMN authorization_ref text" in AUTHORITY
    assert "promotion authorization_ref is required" in AUTHORITY
    assert "approved_by is required at the authorizer boundary" in AUTHORITY


def test_new_authority_functions_are_security_definer_and_public_execute_revoked():
    assert "ALTER FUNCTION %I.%s SECURITY DEFINER" in AUTHORITY
    assert "SET search_path TO %I, pg_catalog, pg_temp" in AUTHORITY
    assert "REVOKE ALL ON FUNCTION %I.%s FROM PUBLIC" in AUTHORITY
