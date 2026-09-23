from pathlib import Path


AUTHORITY = Path("migrations/0003_promotion_authority.sql").read_text()


def test_runtime_cannot_mutate_published_promotion_or_binding_authority():
    assert "cannot create, broaden, revoke, or" in AUTHORITY
    assert "otherwise mutate published promotion/binding authority" in AUTHORITY
    runtime_body = AUTHORITY.split(
        "CREATE FUNCTION configure_fuckup_runtime_role(p_role name)", 1
    )[1].split("CREATE FUNCTION configure_fuckup_authorizer_role(p_role name)", 1)[0]
    assert "GRANT EXECUTE ON FUNCTION" not in runtime_body
    assert "retains protected promotion/binding DML authority" in runtime_body


def test_distinct_authorizer_role_is_source_controlled():
    for token in [
        "authority_role_assignments",
        "'runtime', 'authorizer'",
        "configure_fuckup_authorizer_role",
        "already bound to incompatible authority kind",
        "create_authorized_promotion",
        "create_injection_binding",
        "revoke_promotion",
        "restrict_injection_binding",
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
    assert "preexisting promotions require explicit authorization-continuity reconciliation" in AUTHORITY
    assert "ALTER COLUMN authorization_ref SET NOT NULL" in AUTHORITY
    assert "promotions_authorization_ref_format_ck" in AUTHORITY
    assert "promotions_authorization_ref_uq" in AUTHORITY
    assert "promotion authorization_ref must be a sha256 content digest" in AUTHORITY
    assert "approved_by is required at the authorizer boundary" in AUTHORITY


def test_new_authority_functions_are_security_definer_and_public_execute_revoked():
    assert "ALTER FUNCTION %I.%s SECURITY DEFINER" in AUTHORITY
    assert "SET search_path TO %I, pg_catalog, pg_temp" in AUTHORITY
    assert "REVOKE ALL ON FUNCTION %I.%s FROM PUBLIC" in AUTHORITY



def test_new_binding_requires_current_active_promotion():
    for token in [
        "p.correction_revision",
        "c.current_revision",
        "c.status",
        "promotion_revision <> current_revision OR correction_status <> 'ACTIVE'",
        "cannot create a binding for stale or inactive promotion",
    ]:
        assert token in AUTHORITY



def test_promotion_authority_plpgsql_delimiters_are_balanced():
    assert AUTHORITY.count("$$") % 2 == 0
    assert AUTHORITY.startswith("BEGIN;")
    assert AUTHORITY.rstrip().endswith("COMMIT;")
