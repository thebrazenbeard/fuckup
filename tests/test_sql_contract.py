from pathlib import Path


MIGRATION = Path("migrations/0001_core.sql").read_text()
CLAIM = Path("sql/claim_job.sql").read_text()


def test_qualification_digest_is_foreign_keyed_to_exact_revision():
    assert "FOREIGN KEY (correction_id, correction_revision, exact_subject_digest)" in MIGRATION
    assert "REFERENCES correction_revisions(correction_id, revision, subject_digest)" in MIGRATION


def test_promotion_requires_pass_and_allowed_policy():
    assert "qualification_result text NOT NULL DEFAULT 'PASS' CHECK (qualification_result = 'PASS')" in MIGRATION
    assert "policy_decision @> '{\"allow\": true}'::jsonb" in MIGRATION
    assert "CREATE FUNCTION validate_promotion_insert()" in MIGRATION
    assert "NEW.correction_revision <> current_revision" in MIGRATION
    assert "NEW.exact_subject_digest <> current_digest" in MIGRATION


def test_active_binding_projection_filters_revocation_expiry_currentness_and_status():
    assert "CREATE VIEW active_injection_bindings AS" in MIGRATION
    assert "p.revoked_at IS NULL" in MIGRATION
    assert "ib.expires_at IS NULL OR ib.expires_at > now()" in MIGRATION
    assert "c.current_revision = p.correction_revision" in MIGRATION
    assert "c.status = 'ACTIVE'" in MIGRATION


def test_supersession_is_same_incident_non_self_current_and_cycle_checked():
    assert "a correction cannot supersede itself" in MIGRATION
    assert "supersession must remain within one incident" in MIGRATION
    assert "supersession must target current revision" in MIGRATION
    assert "WITH RECURSIVE chain" in MIGRATION
    assert "supersession cycle detected" in MIGRATION


def test_claim_function_recovers_expired_running_and_enforces_budget():
    assert "CREATE FUNCTION claim_worker_job" in MIGRATION
    assert "status = 'RUNNING' AND lease_expires_at <= now()" in MIGRATION
    assert "attempts < max_attempts" in MIGRATION
    assert "CHECK (attempts <= max_attempts)" in MIGRATION
    assert "lease_seconds must be between 1 and 86400" in MIGRATION
    assert "SELECT *" in CLAIM and "claim_worker_job(:worker_id, :lease_seconds)" in CLAIM


def test_worker_state_lock_fields_are_constrained():
    assert "status = 'RUNNING'" in MIGRATION
    assert "locked_by IS NOT NULL" in MIGRATION
    assert "status <> 'RUNNING'" in MIGRATION
    assert "locked_by IS NULL" in MIGRATION


def test_idempotency_is_bound_to_effect_digest():
    assert "CHECK ((idempotency_key IS NULL) = (effect_digest IS NULL))" in MIGRATION
    assert "effect_digest text NOT NULL" in MIGRATION
    assert "CREATE FUNCTION record_event_idempotent(" in MIGRATION
    assert "idempotency key collision for a different event effect" in MIGRATION


def test_promotion_history_is_immutable_except_monotonic_revocation():
    assert "CREATE FUNCTION protect_promotion_mutation()" in MIGRATION
    assert "promotion fields are immutable after activation" in MIGRATION
    assert "revocation is monotonic and may occur only once" in MIGRATION


def test_promotion_revocation_and_supersession_write_outbox_atomically():
    assert "CREATE FUNCTION promotion_insert_effects()" in MIGRATION
    assert "CREATE FUNCTION promotion_revocation_effects()" in MIGRATION
    assert "org.fuckup.learning.promoted" in MIGRATION
    assert "org.fuckup.learning.revoked" in MIGRATION
    assert "org.fuckup.learning.superseded" in MIGRATION


def test_cross_incident_root_cause_link_is_rejected():
    assert "root-cause candidate belongs to a different incident" in MIGRATION


def test_revocation_cannot_precede_activation():
    assert "revocation cannot precede activation" in MIGRATION
    assert "NEW.revoked_at < OLD.activated_at" in MIGRATION


def test_plpgsql_function_delimiters_are_balanced():
    assert MIGRATION.count("$") % 2 == 0
    assert "RETURNS SETOF events AS $" in MIGRATION
    assert "validate_correction_revision_insert() RETURNS trigger AS $" in MIGRATION
    assert "jsonb_is_nonempty_string_map(p_value jsonb)" in MIGRATION
    assert "STRICT\nAS $" in MIGRATION
    assert "validate_injection_binding_insert() RETURNS trigger AS $" in MIGRATION
    assert "protect_injection_binding_mutation() RETURNS trigger AS $" in MIGRATION


def test_postgres_idempotency_compares_effect_fields_not_digest_only():
    assert "existing.incident_id IS DISTINCT FROM p_incident_id" in MIGRATION
    assert "existing.event_type IS DISTINCT FROM p_event_type" in MIGRATION
    assert "existing.payload IS DISTINCT FROM COALESCE(p_payload, '{}'::jsonb)" in MIGRATION


def test_new_revision_resets_lifecycle_and_terminal_families_cannot_revise():
    assert "status = 'CORRECTION_PROPOSED'" in MIGRATION
    assert "terminal correction status % cannot accept a new revision" in MIGRATION


def test_activation_scope_and_binding_selector_are_flat_nonempty_string_maps():
    assert "jsonb_is_nonempty_string_map(activation_scope)" in MIGRATION
    assert "jsonb_is_nonempty_string_map(rollback_condition)" in MIGRATION
    assert "jsonb_is_nonempty_string_map(selector)" in MIGRATION


def test_binding_insert_is_scope_and_currentness_guarded():
    for token in [
        "validate_injection_binding_insert",
        "NEW.selector @> authorized_scope",
        "binding cannot target a revoked promotion",
        "binding requires the current ACTIVE correction revision",
    ]:
        assert token in MIGRATION


def test_binding_mutation_can_only_narrow_effect():
    for token in [
        "protect_injection_binding_mutation",
        "binding reactivation requires fresh authorization",
        "binding expiry may only stay the same or move earlier",
        "binding identity and scope are immutable after creation",
    ]:
        assert token in MIGRATION
