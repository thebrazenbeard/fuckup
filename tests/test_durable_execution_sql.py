from pathlib import Path


MIGRATION = Path("migrations/0006_durable_execution_repository.sql")


def _sql() -> str:
    return MIGRATION.read_text()


def test_durable_execution_migration_exists():
    assert MIGRATION.exists()


def test_verified_outcomes_are_append_only_and_operation_unique():
    sql = _sql()
    assert "CREATE TABLE outcome_observations" in sql
    assert "operation_id uuid NOT NULL UNIQUE" in sql
    assert "BEFORE UPDATE OR DELETE ON outcome_observations" in sql
    assert "reject_append_only_mutation()" in sql


def test_verified_outcome_function_checks_exact_operation_provenance():
    sql = _sql()
    assert "CREATE FUNCTION record_verified_outcome_observation(" in sql
    assert "latest_event.state IS DISTINCT FROM 'VERIFIED'" in sql
    assert "op.effect_digest IS DISTINCT FROM p_effect_digest" in sql
    assert "op.effect_payload->>'binding_id'" in sql
    assert "op.effect_payload->>'promotion_id'" in sql
    assert "op.effect_payload->>'selector_digest'" in sql
    assert "outcome observation collision" in sql


def test_runtime_has_guarded_outcome_recording_without_direct_dml():
    sql = _sql()
    assert "configure_fuckup_runtime_role_base_v5" in sql
    assert "REVOKE ALL PRIVILEGES ON %I.outcome_observations FROM %I" in sql
    assert "GRANT SELECT ON %I.outcome_observations TO %I" in sql
    assert "record_verified_outcome_observation(" in sql
    assert "retains direct outcome-observation DML authority" in sql


def test_durable_execution_functions_pin_search_path_and_revoke_public():
    sql = _sql()
    assert "SECURITY DEFINER" in sql
    assert "SET search_path TO %I, pg_catalog, pg_temp" in sql
    assert "REVOKE ALL ON FUNCTION" in sql


def test_verified_outcome_checks_binding_promotion_correction_lineage():
    sql = _sql()
    assert "outcome binding lineage does not match operation" in sql
    assert "binding.promotion_id = p_promotion_id" in sql
    assert "promotion.correction_id = p_correction_id" in sql
    assert "promotion.correction_revision = p_correction_revision" in sql
    assert "binding.selector_digest = p_scope_digest" in sql
    assert "op.operation_kind = 'injector:' || binding.adapter || '@' || binding.adapter_version" in sql