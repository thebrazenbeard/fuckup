from pathlib import Path


AUTHORITY = Path("migrations/0002_runtime_authority.sql").read_text()


def test_authority_layer_refuses_public_schema():
    assert "must be installed in a dedicated trusted schema, not public" in AUTHORITY


def test_guarded_mutation_functions_are_security_definer_and_public_execute_is_revoked():
    assert "SECURITY DEFINER" in AUTHORITY
    assert "REVOKE ALL ON FUNCTION" in AUTHORITY
    for name in [
        "record_event_idempotent",
        "validate_correction_revision_insert",
        "apply_correction_revision_insert",
        "validate_promotion_insert",
        "promotion_insert_effects",
        "promotion_revocation_effects",
        "claim_worker_job",
        "complete_worker_job",
        "fail_worker_job",
    ]:
        assert name in AUTHORITY


def test_runtime_role_has_no_direct_correction_projection_write():
    assert "runtime gets no UPDATE privilege on corrections" in AUTHORITY
    assert "GRANT INSERT (id, incident_id) ON %I.corrections" in AUTHORITY
    assert "GRANT UPDATE (current_revision" not in AUTHORITY
    assert "GRANT UPDATE (status" not in AUTHORITY


def test_runtime_role_cannot_directly_write_events_or_outbox():
    assert "No direct INSERT/UPDATE/DELETE on events, outbox" in AUTHORITY
    assert "GRANT INSERT" in AUTHORITY
    assert "ON %I.events TO %I" not in AUTHORITY
    assert "ON %I.outbox TO %I" not in AUTHORITY


def test_runtime_role_uses_guarded_worker_functions():
    for signature in [
        "claim_worker_job(text,integer)",
        "complete_worker_job(uuid,text)",
        "fail_worker_job(uuid,text,jsonb,boolean,integer)",
    ]:
        assert signature in AUTHORITY


def test_security_definer_search_path_pins_trusted_schema_and_pg_temp_last():
    assert "SET search_path TO %I, pg_catalog, pg_temp" in AUTHORITY


def test_runtime_role_must_be_isolated_leaf_without_admin_escape_hatches():
    for token in [
        "rolsuper",
        "rolcreaterole",
        "rolcreatedb",
        "rolreplication",
        "rolbypassrls",
        "pg_catalog.pg_auth_members",
        "must not be a member of another role",
        "forbidden administrative attributes",
    ]:
        assert token in AUTHORITY


def test_runtime_role_effective_forbidden_privileges_are_verified():
    assert "pg_catalog.has_schema_privilege" in AUTHORITY
    assert "pg_catalog.has_table_privilege" in AUTHORITY
    assert "retains forbidden effective privileges" in AUTHORITY


def test_authority_plpgsql_delimiters_are_balanced():
    assert AUTHORITY.count("$"+"$") % 2 == 0
    assert "configure_fuckup_runtime_role(p_role name)\nRETURNS void AS $"+"$" in AUTHORITY

