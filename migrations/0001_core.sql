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
    effect_digest text,
    occurred_at timestamptz,
    observed_at timestamptz NOT NULL DEFAULT now(),
    provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
    idempotency_key text,
    CHECK ((idempotency_key IS NULL) = (effect_digest IS NULL))
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
    current_revision integer NOT NULL DEFAULT 0 CHECK (current_revision >= 0),
    status text NOT NULL DEFAULT 'CORRECTION_PROPOSED'
        CHECK (status IN (
            'CORRECTION_PROPOSED', 'QUALIFYING', 'QUALIFIED', 'PROMOTED',
            'ACTIVE', 'SUPERSEDED', 'REVOKED', 'REJECTED'
        )),
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
    supersedes_correction_id uuid,
    supersedes_revision integer,
    created_from_root_cause_id uuid REFERENCES root_cause_candidates(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (correction_id, revision),
    UNIQUE (correction_id, revision, subject_digest),
    CHECK (
        (supersedes_correction_id IS NULL AND supersedes_revision IS NULL)
        OR
        (supersedes_correction_id IS NOT NULL AND supersedes_revision IS NOT NULL)
    ),
    FOREIGN KEY (supersedes_correction_id, supersedes_revision)
        REFERENCES correction_revisions(correction_id, revision)
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
    UNIQUE (id, correction_id, correction_revision, exact_subject_digest, result),
    FOREIGN KEY (correction_id, correction_revision, exact_subject_digest)
        REFERENCES correction_revisions(correction_id, revision, subject_digest)
);

CREATE TABLE promotions (
    id uuid PRIMARY KEY,
    correction_id uuid NOT NULL,
    correction_revision integer NOT NULL,
    exact_subject_digest text NOT NULL,
    qualification_id uuid NOT NULL,
    qualification_result text NOT NULL DEFAULT 'PASS' CHECK (qualification_result = 'PASS'),
    policy_name text NOT NULL CHECK (btrim(policy_name) <> ''),
    policy_version text NOT NULL CHECK (btrim(policy_version) <> ''),
    policy_decision jsonb NOT NULL
        CHECK (
            jsonb_typeof(policy_decision) = 'object'
            AND policy_decision @> '{"allow": true}'::jsonb
        ),
    approved_by text,
    activation_scope jsonb NOT NULL
        CHECK (jsonb_typeof(activation_scope) = 'object' AND activation_scope <> '{}'::jsonb),
    rollback_condition jsonb NOT NULL
        CHECK (jsonb_typeof(rollback_condition) = 'object' AND rollback_condition <> '{}'::jsonb),
    activated_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz,
    FOREIGN KEY (qualification_id, correction_id, correction_revision, exact_subject_digest, qualification_result)
        REFERENCES qualifications(id, correction_id, correction_revision, exact_subject_digest, result),
    UNIQUE (correction_id, correction_revision)
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
    effect_digest text,
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
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (attempts <= max_attempts),
    CHECK ((idempotency_key IS NULL) = (effect_digest IS NULL)),
    CHECK (
        (
            status = 'RUNNING'
            AND locked_by IS NOT NULL
            AND locked_at IS NOT NULL
            AND lease_expires_at IS NOT NULL
        )
        OR
        (
            status <> 'RUNNING'
            AND locked_by IS NULL
            AND locked_at IS NULL
            AND lease_expires_at IS NULL
        )
    )
);
CREATE UNIQUE INDEX worker_jobs_idempotency_uq ON worker_jobs(idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE UNIQUE INDEX worker_jobs_live_work_key_uq
    ON worker_jobs(work_key)
    WHERE work_key IS NOT NULL AND status IN ('PENDING', 'RUNNING', 'RETRY');

CREATE TABLE outbox (
    id bigserial PRIMARY KEY,
    aggregate_type text NOT NULL,
    aggregate_id text NOT NULL,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    effect_digest text NOT NULL,
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

CREATE FUNCTION record_event_idempotent(
    p_id uuid,
    p_incident_id uuid,
    p_event_type text,
    p_actor text,
    p_payload jsonb,
    p_payload_digest text,
    p_effect_digest text,
    p_occurred_at timestamptz,
    p_provenance jsonb,
    p_idempotency_key text
)
RETURNS SETOF events AS $$
DECLARE
    existing events%ROWTYPE;
BEGIN
    IF p_idempotency_key IS NULL THEN
        RETURN QUERY
        INSERT INTO events(
            id, incident_id, event_type, actor, payload, payload_digest,
            effect_digest, occurred_at, provenance, idempotency_key
        )
        VALUES (
            p_id, p_incident_id, p_event_type, p_actor, COALESCE(p_payload, '{}'::jsonb),
            p_payload_digest, NULL, p_occurred_at, COALESCE(p_provenance, '{}'::jsonb), NULL
        )
        RETURNING *;
        RETURN;
    END IF;

    IF p_effect_digest IS NULL OR btrim(p_effect_digest) = '' THEN
        RAISE EXCEPTION 'effect digest is required with an idempotency key';
    END IF;

    SELECT * INTO existing
      FROM events
     WHERE idempotency_key = p_idempotency_key
     FOR SHARE;

    IF FOUND THEN
        IF existing.effect_digest IS DISTINCT FROM p_effect_digest THEN
            RAISE EXCEPTION 'idempotency key collision for a different event effect';
        END IF;
        RETURN NEXT existing;
        RETURN;
    END IF;

    BEGIN
        RETURN QUERY
        INSERT INTO events(
            id, incident_id, event_type, actor, payload, payload_digest,
            effect_digest, occurred_at, provenance, idempotency_key
        )
        VALUES (
            p_id, p_incident_id, p_event_type, p_actor, COALESCE(p_payload, '{}'::jsonb),
            p_payload_digest, p_effect_digest, p_occurred_at,
            COALESCE(p_provenance, '{}'::jsonb), p_idempotency_key
        )
        RETURNING *;
        RETURN;
    EXCEPTION WHEN unique_violation THEN
        SELECT * INTO existing
          FROM events
         WHERE idempotency_key = p_idempotency_key
         FOR SHARE;

        IF existing.effect_digest IS DISTINCT FROM p_effect_digest THEN
            RAISE EXCEPTION 'idempotency key collision for a different event effect';
        END IF;
        RETURN NEXT existing;
        RETURN;
    END;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION validate_correction_revision_insert() RETURNS trigger AS $$
DECLARE
    correction_incident uuid;
    expected_revision integer;
    root_incident uuid;
    superseded_incident uuid;
    superseded_current_revision integer;
    cycle_found boolean;
BEGIN
    SELECT incident_id, current_revision + 1
      INTO correction_incident, expected_revision
      FROM corrections
     WHERE id = NEW.correction_id
     FOR UPDATE;

    IF correction_incident IS NULL THEN
        RAISE EXCEPTION 'unknown correction %', NEW.correction_id;
    END IF;

    IF NEW.revision <> expected_revision THEN
        RAISE EXCEPTION 'revision % is not next current revision % for correction %',
            NEW.revision, expected_revision, NEW.correction_id;
    END IF;

    IF NEW.created_from_root_cause_id IS NOT NULL THEN
        SELECT incident_id INTO root_incident
          FROM root_cause_candidates
         WHERE id = NEW.created_from_root_cause_id;
        IF root_incident IS DISTINCT FROM correction_incident THEN
            RAISE EXCEPTION 'root-cause candidate belongs to a different incident';
        END IF;
    END IF;

    IF NEW.supersedes_correction_id IS NOT NULL THEN
        IF NEW.supersedes_correction_id = NEW.correction_id THEN
            RAISE EXCEPTION 'a correction cannot supersede itself';
        END IF;

        SELECT incident_id, current_revision
          INTO superseded_incident, superseded_current_revision
          FROM corrections
         WHERE id = NEW.supersedes_correction_id
         FOR UPDATE;

        IF superseded_incident IS DISTINCT FROM correction_incident THEN
            RAISE EXCEPTION 'supersession must remain within one incident';
        END IF;

        IF NEW.supersedes_revision <> superseded_current_revision THEN
            RAISE EXCEPTION 'supersession must target current revision % of correction %',
                superseded_current_revision, NEW.supersedes_correction_id;
        END IF;

        WITH RECURSIVE chain(correction_id) AS (
            SELECT NEW.supersedes_correction_id
            UNION ALL
            SELECT cr.supersedes_correction_id
              FROM chain ch
              JOIN corrections c ON c.id = ch.correction_id
              JOIN correction_revisions cr
                ON cr.correction_id = c.id
               AND cr.revision = c.current_revision
             WHERE cr.supersedes_correction_id IS NOT NULL
        )
        SELECT EXISTS (
            SELECT 1 FROM chain WHERE correction_id = NEW.correction_id
        ) INTO cycle_found;

        IF cycle_found THEN
            RAISE EXCEPTION 'supersession cycle detected';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION apply_correction_revision_insert() RETURNS trigger AS $$
BEGIN
    UPDATE corrections
       SET current_revision = NEW.revision
     WHERE id = NEW.correction_id;

    IF NEW.supersedes_correction_id IS NOT NULL THEN
        UPDATE corrections
           SET status = 'SUPERSEDED'
         WHERE id = NEW.supersedes_correction_id;

        UPDATE injection_bindings ib
           SET active = false
          FROM promotions p
         WHERE ib.promotion_id = p.id
           AND p.correction_id = NEW.supersedes_correction_id
           AND p.correction_revision = NEW.supersedes_revision
           AND ib.active = true;

        INSERT INTO outbox(
            aggregate_type, aggregate_id, event_type, payload, effect_digest, idempotency_key
        )
        VALUES (
            'correction',
            NEW.supersedes_correction_id::text,
            'org.fuckup.learning.superseded',
            jsonb_build_object(
                'superseded_correction_id', NEW.supersedes_correction_id,
                'superseded_revision', NEW.supersedes_revision,
                'by_correction_id', NEW.correction_id,
                'by_revision', NEW.revision
            ),
            NEW.subject_digest,
            'correction-superseded:' || NEW.supersedes_correction_id::text || ':' || NEW.supersedes_revision::text
        );
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION validate_promotion_insert() RETURNS trigger AS $$
DECLARE
    current_revision integer;
    current_digest text;
    correction_status text;
BEGIN
    SELECT c.current_revision, cr.subject_digest, c.status
      INTO current_revision, current_digest, correction_status
      FROM corrections c
      JOIN correction_revisions cr
        ON cr.correction_id = c.id
       AND cr.revision = c.current_revision
     WHERE c.id = NEW.correction_id
     FOR UPDATE OF c;

    IF current_revision IS NULL THEN
        RAISE EXCEPTION 'correction % has no current revision', NEW.correction_id;
    END IF;

    IF NEW.correction_revision <> current_revision THEN
        RAISE EXCEPTION 'stale correction revision %; current is %',
            NEW.correction_revision, current_revision;
    END IF;

    IF NEW.exact_subject_digest <> current_digest THEN
        RAISE EXCEPTION 'promotion digest does not match current correction subject';
    END IF;

    IF correction_status IN ('SUPERSEDED', 'REVOKED', 'REJECTED') THEN
        RAISE EXCEPTION 'correction status % is not promotable', correction_status;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION protect_promotion_mutation() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'promotions are historical evidence and cannot be deleted';
    END IF;

    IF (to_jsonb(NEW) - 'revoked_at') IS DISTINCT FROM (to_jsonb(OLD) - 'revoked_at') THEN
        RAISE EXCEPTION 'promotion fields are immutable after activation';
    END IF;

    IF OLD.revoked_at IS NOT NULL OR NEW.revoked_at IS NULL THEN
        RAISE EXCEPTION 'revocation is monotonic and may occur only once';
    END IF;

    IF NEW.revoked_at < OLD.activated_at THEN
        RAISE EXCEPTION 'revocation cannot precede activation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION promotion_insert_effects() RETURNS trigger AS $$
BEGIN
    UPDATE corrections
       SET status = 'ACTIVE'
     WHERE id = NEW.correction_id;

    INSERT INTO outbox(
        aggregate_type, aggregate_id, event_type, payload, effect_digest, idempotency_key
    )
    VALUES (
        'promotion',
        NEW.id::text,
        'org.fuckup.learning.promoted',
        jsonb_build_object(
            'promotion_id', NEW.id,
            'correction_id', NEW.correction_id,
            'correction_revision', NEW.correction_revision,
            'exact_subject_digest', NEW.exact_subject_digest,
            'activation_scope', NEW.activation_scope
        ),
        NEW.exact_subject_digest,
        'promotion-created:' || NEW.id::text
    );

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION promotion_revocation_effects() RETURNS trigger AS $$
BEGIN
    UPDATE injection_bindings
       SET active = false
     WHERE promotion_id = NEW.id
       AND active = true;

    UPDATE corrections
       SET status = 'REVOKED'
     WHERE id = NEW.correction_id
       AND current_revision = NEW.correction_revision;

    INSERT INTO outbox(
        aggregate_type, aggregate_id, event_type, payload, effect_digest, idempotency_key
    )
    VALUES (
        'promotion',
        NEW.id::text,
        'org.fuckup.learning.revoked',
        jsonb_build_object(
            'promotion_id', NEW.id,
            'correction_id', NEW.correction_id,
            'correction_revision', NEW.correction_revision,
            'revoked_at', NEW.revoked_at
        ),
        NEW.exact_subject_digest,
        'promotion-revoked:' || NEW.id::text
    );

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION claim_worker_job(p_worker_id text, p_lease_seconds integer)
RETURNS SETOF worker_jobs AS $$
DECLARE
    claimed_id uuid;
BEGIN
    IF p_worker_id IS NULL OR btrim(p_worker_id) = '' THEN
        RAISE EXCEPTION 'worker id is required';
    END IF;

    IF p_lease_seconds IS NULL OR p_lease_seconds <= 0 OR p_lease_seconds > 86400 THEN
        RAISE EXCEPTION 'lease_seconds must be between 1 and 86400';
    END IF;

    UPDATE worker_jobs
       SET status = 'DEAD_LETTERED',
           locked_by = NULL,
           locked_at = NULL,
           lease_expires_at = NULL,
           updated_at = now(),
           last_error = COALESCE(last_error, '{"reason":"retry budget exhausted"}'::jsonb)
     WHERE attempts >= max_attempts
       AND (
            status IN ('PENDING', 'RETRY')
            OR (status = 'RUNNING' AND lease_expires_at <= now())
       );

    SELECT id
      INTO claimed_id
      FROM worker_jobs
     WHERE available_at <= now()
       AND attempts < max_attempts
       AND (
            status IN ('PENDING', 'RETRY')
            OR (status = 'RUNNING' AND lease_expires_at <= now())
       )
     ORDER BY available_at, created_at, id
     FOR UPDATE SKIP LOCKED
     LIMIT 1;

    IF claimed_id IS NULL THEN
        RETURN;
    END IF;

    RETURN QUERY
    UPDATE worker_jobs
       SET status = 'RUNNING',
           attempts = attempts + 1,
           locked_by = p_worker_id,
           locked_at = now(),
           lease_expires_at = now() + make_interval(secs => p_lease_seconds),
           updated_at = now()
     WHERE id = claimed_id
     RETURNING *;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER correction_revision_validate
    BEFORE INSERT ON correction_revisions
    FOR EACH ROW EXECUTE FUNCTION validate_correction_revision_insert();

CREATE TRIGGER correction_revision_apply
    AFTER INSERT ON correction_revisions
    FOR EACH ROW EXECUTE FUNCTION apply_correction_revision_insert();

CREATE TRIGGER promotion_validate
    BEFORE INSERT ON promotions
    FOR EACH ROW EXECUTE FUNCTION validate_promotion_insert();

CREATE TRIGGER promotion_insert_outbox
    AFTER INSERT ON promotions
    FOR EACH ROW EXECUTE FUNCTION promotion_insert_effects();

CREATE TRIGGER promotion_protect
    BEFORE UPDATE OR DELETE ON promotions
    FOR EACH ROW EXECUTE FUNCTION protect_promotion_mutation();

CREATE TRIGGER promotion_revoke_effects
    AFTER UPDATE OF revoked_at ON promotions
    FOR EACH ROW
    WHEN (OLD.revoked_at IS NULL AND NEW.revoked_at IS NOT NULL)
    EXECUTE FUNCTION promotion_revocation_effects();

CREATE TRIGGER events_append_only
    BEFORE UPDATE OR DELETE ON events
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation();

CREATE TRIGGER correction_revisions_append_only
    BEFORE UPDATE OR DELETE ON correction_revisions
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation();

CREATE TRIGGER qualifications_append_only
    BEFORE UPDATE OR DELETE ON qualifications
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation();

CREATE VIEW active_injection_bindings AS
SELECT
    ib.id,
    ib.promotion_id,
    ib.adapter,
    ib.selector,
    ib.selector_digest,
    ib.priority,
    ib.conflict_policy,
    ib.expires_at,
    ib.created_at,
    p.correction_id,
    p.correction_revision,
    p.exact_subject_digest,
    p.activation_scope,
    p.rollback_condition
FROM injection_bindings ib
JOIN promotions p ON p.id = ib.promotion_id
JOIN corrections c ON c.id = p.correction_id
WHERE ib.active = true
  AND p.revoked_at IS NULL
  AND (ib.expires_at IS NULL OR ib.expires_at > now())
  AND c.current_revision = p.correction_revision
  AND c.status = 'ACTIVE';

COMMIT;
