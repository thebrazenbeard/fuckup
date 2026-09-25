from pathlib import Path


MIGRATION = Path("migrations/0005_governed_injector_execution.sql")


def test_governed_injector_migration_exists():
    assert MIGRATION.exists()


def test_binding_persists_exact_adapter_version():
    sql = MIGRATION.read_text()
    assert "ADD COLUMN adapter_version text" in sql
    assert "CREATE FUNCTION create_versioned_authorized_binding(" in sql
    assert "p_adapter_version text" in sql
    assert "adapter_version = p_adapter_version" in sql
    assert "ib.adapter_version" in sql


def test_authorizer_can_create_versioned_binding_but_runtime_cannot():
    sql = MIGRATION.read_text()
    signature = (
        "create_versioned_authorized_binding("
        "uuid,uuid,text,text,jsonb,text,integer,text,timestamptz)"
    )
    assert f"GRANT EXECUTE ON FUNCTION %I.{signature} TO %I" in sql
    assert f"REVOKE EXECUTE ON FUNCTION %I.{signature} FROM %I" in sql
    assert "configure_fuckup_runtime_role_base_v4" in sql
    assert "configure_fuckup_authorizer_role_base_v1" in sql


def test_new_execution_binding_functions_are_security_definer_and_public_revoked():
    sql = MIGRATION.read_text()
    assert "SECURITY DEFINER" in sql
    assert "SET search_path TO %I, pg_catalog, pg_temp" in sql
    assert "REVOKE ALL ON FUNCTION" in sql