BEGIN;

CREATE TABLE incidents (
    id uuid PRIMARY KEY,
    fingerprint text NOT NULL,
    fingerprint_version text NOT NULL,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    occurrence_count bigint NOT NULL DEFAULT 1 CHECK (occurrence_count > 0),
    severity text,
    source_type text,
    source_ref text,
    raw_input_digest text,
    normalized_summary text,
    status text NOT NULL DEFAULT 'DETECTED',
    UNIQUE (fingerprint_version, fingerprint)
);

CREATE TABLE events (
    id uuid PRIMARY KEY,
    incident_id uuid NOT NULL REFERENCES incidents(id),
    event_type text NOT NULL,
    actor text,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    payload_digest text,
    occurred_at timestamptz,
    observed_at timestamptz NOT NULL DEFAULT now(),
    provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
    idempotency_key text
);
CREATE UNIQUE INDEX events_idempotency_key_uq ON events(idempotency_key) WHERE idempotency_key IS NOT NULL;

CREATE TABLE root_cause_candidates (
    id uuid PRIMARY KEY,
    incident_id uuid NOT NULL REFERENCES incidents(id),
    proposition text NOT NULL,
    evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    counterevidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    confidence numeric(5,4) CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    scope jsonb NOT NULL DEFAULT '{}'::jsonb,
    competing_explanations jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL CHECK (status IN ('PROPOSED', 'SUPPORTED', 'AMBIGUOUS', 'REJECTED')),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE corrections (
    id uuid PRIMARY KEY,
    incident_id uuid NOT NULL REFERENCES incidents(id),
    status text NOT NULL DEFAULT 'CORRECTION_PROPOSED',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE correction_revisions (
    correction_id uuid NOT NULL REFERENCES corrections(id),
    revision integer NOT NULL CHECK (revision > 0),
    subject_digest text NOT NULL,
    correction_type text,
    target jsonb NOT NULL DEFAULT '{}'::jsonb,
    scope jsonb NOT NULL DEFAULT '{}'::jsonb,
    payload jsonb NOT NULL,
    reversible boolean NOT NULL DEFAULT true,
    supersedes_correction_id uuid REFERENCES corrections(id),
    created_from_root_cause_id uuid REFERENCES root_cause_candidates(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (correction_id, revision)
);

CREATE TABLE qualifications (
    id uuid PRIMARY KEY,
    correction_id uuid NOT NULL,
    correction_revision integer NOT NULL,
    suite_version text NOT NULL,
    exact_subject_digest text NOT NULL,
    result text NOT NULL CHECK (result IN ('PASS', 'FAIL')),
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    started_at timestamptz,
    finished_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, correction_id, correction_revision),
    FOREIGN KEY (correction_id, correction_revision)
        REFERENCES correction_revisions(correction_id, revision)
);

CREATE TABLE promotions (
    id uuid PRIMARY KEY,
    correction_id uuid NOT NULL,
    correction_revision integer NOT NULL,
    qualification_id uuid NOT NULL,
    policy_decision jsonb NOT NULL,
    approved_by text,
    activation_scope jsonb NOT NULL,
    rollback_condition jsonb NOT NULL,
    activated_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz,
    FOREIGN KEY (qualification_id, correction_id, correction_revision)
        REFERENCES qualifications(id, correction_id, correction_revision)
);

CREATE TABLE injection_bindings (
    id uuid PRIMARY KEY,
    promotion_id uuid NOT NULL REFERENCES promotions(id),
    adapter text NOT NULL,
    selector jsonb NOT NULL,
    selector_digest text NOT NULL,
    priority integer NOT NULL DEFAULT 0,
    conflict_policy text NOT NULL DEFAULT 'FAIL_CLOSED',
    expires_at timestamptz,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (promotion_id, adapter, selector_digest)
);

CREATE TABLE worker_jobs (
    id uuid PRIMARY KEY,
    job_type text NOT NULL,
    payload jsonb NOT NULL,
    status text NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'RUNNING', 'RETRY', 'COMPLETED', 'DEAD_LETTERED')),
    work_key text,
    idempotency_key text,
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts integer NOT NULL DEFAULT 5 CHECK (max_attempts > 0),
    available_at timestamptz NOT NULL DEFAULT now(),
    locked_by text,
    locked_at timestamptz,
    lease_expires_at timestamptz,
    last_error jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX worker_jobs_idempotency_uq ON worker_jobs(idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE UNIQUE INDEX worker_jobs_live_work_key_uq
    ON worker_jobs(work_key)
    WHERE work_key IS NOT NULL AND status IN ('PENDING', 'RUNNING', 'RETRY');

CREATE TABLE outbox (
    id uuid PRIMARY KEY,
    aggregate_type text NOT NULL,
    aggregate_id text NOT NULL,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    idempotency_key text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz,
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    last_error jsonb
);

CREATE FUNCTION reject_append_only_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION '% is append-only; mutation rejected', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER events_append_only
    BEFORE UPDATE OR DELETE ON events
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation();

CREATE TRIGGER correction_revisions_append_only
    BEFORE UPDATE OR DELETE ON correction_revisions
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation();

CREATE TRIGGER qualifications_append_only
    BEFORE UPDATE OR DELETE ON qualifications
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation();

COMMIT;
