from pathlib import Path


MIGRATION = Path("migrations/0004_execution_integrity.sql")


def _text() -> str:
    return MIGRATION.read_text()


def test_execution_integrity_migration_exists():
    assert MIGRATION.exists()


def test_execution_integrity_tables_are_append_only():
    sql = _text()
    for table in [
        "incident_occurrences",
        "effect_operations",
        "effect_operation_events",
    ]:
        assert f"CREATE TABLE {table}" in sql
        assert f"BEFORE UPDATE OR DELETE ON {table}" in sql
        assert "reject_append_only_mutation()" in sql


def test_guarded_effect_functions_cover_prepare_attempt_and_reconciliation():
    sql = _text()
    for signature in [
        "prepare_effect_operation(",
        "record_effect_attempt(",
        "reconcile_effect_operation(",
        "record_incident_occurrence(",
    ]:
        assert f"CREATE FUNCTION {signature}" in sql

    assert "idempotency key collision for a different effect" in sql
    assert "cannot attempt operation from state" in sql
    assert "verified reconciliation requires readback digest" in sql


def test_runtime_role_uses_functions_without_direct_integrity_table_dml():
    sql = _text()
    assert "configure_fuckup_runtime_role_base_v3" in sql
    for table in [
        "incident_occurrences",
        "effect_operations",
        "effect_operation_events",
    ]:
        assert f"REVOKE ALL PRIVILEGES ON %I.{table} FROM %I" in sql


    for signature in [
        "record_incident_occurrence(uuid,uuid,jsonb,text,timestamptz,text)",
        "prepare_effect_operation(uuid,text,text,text,jsonb,text,timestamptz)",
        "record_effect_attempt(uuid,text,timestamptz)",
        "reconcile_effect_operation(uuid,text,text,text,timestamptz)",
    ]:
        assert signature in sql

    assert "retains direct execution-integrity DML authority" in sql


def test_execution_integrity_security_definer_search_path_is_pinned():
    sql = _text()
    assert "SECURITY DEFINER" in sql
    assert "SET search_path TO %I, pg_catalog, pg_temp" in sql
    assert "REVOKE ALL ON FUNCTION" in sql