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
