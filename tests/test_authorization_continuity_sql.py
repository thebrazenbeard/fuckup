from pathlib import Path


RUNTIME_AUTHORITY = Path("migrations/0002_runtime_authority.sql").read_text()
AUTH_CONTINUITY = Path("migrations/0003_authorization_continuity.sql").read_text()


def test_generic_runtime_migration_no_longer_grants_promotion_or_binding_dml():
    assert "ON %I.promotions TO %I" not in RUNTIME_AUTHORITY
    assert "GRANT UPDATE (revoked_at) ON %I.promotions" not in RUNTIME_AUTHORITY
    assert "GRANT INSERT (id, promotion_id, adapter, selector" not in RUNTIME_AUTHORITY
    assert "GRANT UPDATE (active, expires_at) ON %I.injection_bindings" not in RUNTIME_AUTHORITY


def test_promotion_requires_durable_authorization_artifact():
    for token in [
        "CREATE TABLE promotion_authorizations",
        "ADD COLUMN authorization_id uuid",
        "promotion authorization artifact is required",
        "promotion does not exactly match its authorization artifact",
        "promotions_authorization_fk",
    ]:
        assert token in AUTH_CONTINUITY


def test_runtime_and_authorizer_roles_are_mutually_exclusive():
    assert "CREATE TABLE authority_role_assignments" in AUTH_CONTINUITY
    assert "authority_kind IN ('RUNTIME', 'AUTHORIZER')" in AUTH_CONTINUITY
    assert "already assigned as % authority" in AUTH_CONTINUITY


def test_authorizer_functions_are_distinct_from_runtime_functions():
    assert "CREATE FUNCTION authorize_and_promote(" in AUTH_CONTINUITY
    assert "CREATE FUNCTION create_authorized_binding(" in AUTH_CONTINUITY
    assert "CREATE FUNCTION revoke_authorized_promotion(" in AUTH_CONTINUITY
    assert "REVOKE EXECUTE ON FUNCTION %I.authorize_and_promote" in AUTH_CONTINUITY
    assert "GRANT EXECUTE ON FUNCTION %I.restrict_injection_binding" in AUTH_CONTINUITY
    assert "GRANT EXECUTE ON FUNCTION %I.authorize_and_promote" in AUTH_CONTINUITY


def test_activation_scope_is_selector_shaped_and_binding_must_be_narrower():
    for token in [
        "CREATE FUNCTION fuckup_selector_valid",
        "CREATE FUNCTION fuckup_selector_within_scope",
        "p_selector @> p_scope",
        "binding selector must be equal to or narrower than authorized activation scope",
    ]:
        assert token in AUTH_CONTINUITY


def test_binding_restriction_is_monotonic():
    assert "binding expiry may only move earlier" in AUTH_CONTINUITY
    assert "CASE WHEN p_deactivate THEN false ELSE active END" in AUTH_CONTINUITY
    assert "GRANT UPDATE (active, expires_at)" not in AUTH_CONTINUITY


def test_authorizer_has_no_direct_protected_table_dml():
    for token in [
        "authorizer role % retains direct protected-table DML authority",
        "'promotion_authorizations'), 'INSERT'",
        "'promotions'), 'INSERT'",
        "'injection_bindings'), 'INSERT'",
    ]:
        assert token in AUTH_CONTINUITY


def test_authorization_migration_security_definer_functions_are_hardened():
    assert AUTH_CONTINUITY.count("$") >= 2
    assert "SECURITY DEFINER" in AUTH_CONTINUITY
    assert "REVOKE ALL ON FUNCTION %I.%s FROM PUBLIC" in AUTH_CONTINUITY
    assert "SET search_path TO %I, pg_catalog, pg_temp" in AUTH_CONTINUITY
