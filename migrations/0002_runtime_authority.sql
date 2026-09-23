BEGIN;

-- This authority layer MUST be installed in a dedicated trusted schema.
-- Do not install it in public: SECURITY DEFINER functions deliberately bind
-- their search_path to the installation schema.
DO $authority_check$
BEGIN
    IF current_schema() = 'public' THEN
        RAISE EXCEPTION
            'F.U.C.K.U.P. runtime authority must be installed in a dedicated trusted schema, not public';
    END IF;
END;
$authority_check$ LANGUAGE plpgsql;

CREATE FUNCTION complete_worker_job(p_job_id uuid, p_worker_id text)
RETURNS SETOF worker_jobs AS $$
BEGIN
    IF p_worker_id IS NULL OR btrim(p_worker_id) = '' THEN
        RAISE EXCEPTION 'worker id is required';
    END IF;

    RETURN QUERY
    UPDATE worker_jobs
       SET status = 'COMPLETED',
           locked_by = NULL,
           locked_at = NULL,
           lease_expires_at = NULL,
           last_error = NULL,
           updated_at = now()
     WHERE id = p_job_id
       AND status = 'RUNNING'
       AND locked_by = p_worker_id
     RETURNING *;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'job is not RUNNING under worker %', p_worker_id;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION fail_worker_job(
    p_job_id uuid,
    p_worker_id text,
    p_error jsonb,
    p_retryable boolean,
    p_delay_seconds integer DEFAULT 0
)
RETURNS SETOF worker_jobs AS $$
DECLARE
    job_attempts integer;
    job_max_attempts integer;
BEGIN
    IF p_worker_id IS NULL OR btrim(p_worker_id) = '' THEN
        RAISE EXCEPTION 'worker id is required';
    END IF;

    IF p_delay_seconds IS NULL OR p_delay_seconds < 0 OR p_delay_seconds > 86400 THEN
        RAISE EXCEPTION 'delay_seconds must be between 0 and 86400';
    END IF;

    SELECT attempts, max_attempts
      INTO job_attempts, job_max_attempts
      FROM worker_jobs
     WHERE id = p_job_id
       AND status = 'RUNNING'
       AND locked_by = p_worker_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'job is not RUNNING under worker %', p_worker_id;
    END IF;

    RETURN QUERY
    UPDATE worker_jobs
       SET status = CASE
               WHEN p_retryable AND job_attempts < job_max_attempts THEN 'RETRY'
               ELSE 'DEAD_LETTERED'
           END,
           available_at = CASE
               WHEN p_retryable AND job_attempts < job_max_attempts
                   THEN now() + make_interval(secs => p_delay_seconds)
               ELSE available_at
           END,
           locked_by = NULL,
           locked_at = NULL,
           lease_expires_at = NULL,
           last_error = COALESCE(p_error, '{}'::jsonb),
           updated_at = now()
     WHERE id = p_job_id
     RETURNING *;
END;
$$ LANGUAGE plpgsql;

-- Convert all mutation-capable guard functions to SECURITY DEFINER and pin
-- search_path to the trusted installation schema, with pg_temp last.
DO $secure_functions$
DECLARE
    s name := current_schema();
    signatures text[] := ARRAY[
        'record_event_idempotent(uuid,uuid,text,text,jsonb,text,text,timestamptz,jsonb,text)',
        'validate_correction_revision_insert()',
        'apply_correction_revision_insert()',
        'validate_promotion_insert()',
        'promotion_insert_effects()',
        'promotion_revocation_effects()',
        'claim_worker_job(text,integer)',
        'complete_worker_job(uuid,text)',
        'fail_worker_job(uuid,text,jsonb,boolean,integer)'
    ];
    sig text;
BEGIN
    FOREACH sig IN ARRAY signatures LOOP
        EXECUTE format(
            'ALTER FUNCTION %I.%s SECURITY DEFINER',
            s,
            sig
        );
        EXECUTE format(
            'ALTER FUNCTION %I.%s SET search_path TO %I, pg_catalog, pg_temp',
            s,
            sig,
            s
        );
        EXECUTE format(
            'REVOKE ALL ON FUNCTION %I.%s FROM PUBLIC',
            s,
            sig
        );
    END LOOP;
END;
$secure_functions$ LANGUAGE plpgsql;

-- Owner-only helper for provisioning a least-privilege application role.
-- The role must already exist. This function does not CREATE ROLE and is not
-- executable by PUBLIC.
CREATE FUNCTION configure_fuckup_runtime_role(p_role name)
RETURNS void AS $$
DECLARE
    s name := current_schema();
    runtime_oid oid;
    runtime_superuser boolean;
    runtime_createrole boolean;
    runtime_createdb boolean;
    runtime_replication boolean;
    runtime_bypassrls boolean;
BEGIN
    SELECT oid, rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls
      INTO runtime_oid, runtime_superuser, runtime_createrole, runtime_createdb,
           runtime_replication, runtime_bypassrls
      FROM pg_catalog.pg_roles
     WHERE rolname = p_role;

    IF runtime_oid IS NULL THEN
        RAISE EXCEPTION 'runtime role % does not exist', p_role;
    END IF;

    IF runtime_superuser
       OR runtime_createrole
       OR runtime_createdb
       OR runtime_replication
       OR runtime_bypassrls THEN
        RAISE EXCEPTION 'runtime role % has forbidden administrative attributes', p_role;
    END IF;

    -- The runtime identity must be a leaf role. Direct REVOKE statements do
    -- not neutralize privileges inherited from parent roles or roles that can
    -- later be assumed through SET ROLE.
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members
         WHERE member = runtime_oid
    ) THEN
        RAISE EXCEPTION 'runtime role % must not be a member of another role', p_role;
    END IF;

    EXECUTE format('REVOKE ALL PRIVILEGES ON SCHEMA %I FROM %I', s, p_role);
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO %I', s, p_role);

    EXECUTE format('REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA %I FROM %I', s, p_role);
    EXECUTE format('REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA %I FROM %I', s, p_role);
    EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO %I', s, p_role);

    EXECUTE format(
        'GRANT INSERT (id, fingerprint, fingerprint_version, severity, source_type, source_ref, raw_input_digest, normalized_summary) ON %I.incidents TO %I',
        s, p_role
    );

    EXECUTE format(
        'GRANT INSERT (id, incident_id, proposition, evidence_refs, counterevidence_refs, confidence, scope, competing_explanations, status) ON %I.root_cause_candidates TO %I',
        s, p_role
    );
    EXECUTE format(
        'GRANT UPDATE (proposition, evidence_refs, counterevidence_refs, confidence, scope, competing_explanations, status) ON %I.root_cause_candidates TO %I',
        s, p_role
    );

    -- current_revision/status are projection authority owned only by guarded
    -- trigger functions; runtime gets no UPDATE privilege on corrections.
    EXECUTE format(
        'GRANT INSERT (id, incident_id) ON %I.corrections TO %I',
        s, p_role
    );

    EXECUTE format(
        'GRANT INSERT (correction_id, revision, subject_digest, correction_type, target, scope, payload, reversible, supersedes_correction_id, supersedes_revision, created_from_root_cause_id) ON %I.correction_revisions TO %I',
        s, p_role
    );

    EXECUTE format(
        'GRANT INSERT (id, correction_id, correction_revision, suite_version, exact_subject_digest, result, evidence, started_at) ON %I.qualifications TO %I',
        s, p_role
    );

    EXECUTE format(
        'GRANT INSERT (id, correction_id, correction_revision, exact_subject_digest, qualification_id, qualification_result, policy_name, policy_version, policy_decision, approved_by, activation_scope, rollback_condition) ON %I.promotions TO %I',
        s, p_role
    );
    EXECUTE format(
        'GRANT UPDATE (revoked_at) ON %I.promotions TO %I',
        s, p_role
    );

    EXECUTE format(
        'GRANT INSERT (id, promotion_id, adapter, selector, selector_digest, priority, conflict_policy, expires_at) ON %I.injection_bindings TO %I',
        s, p_role
    );
    EXECUTE format(
        'GRANT UPDATE (active, expires_at) ON %I.injection_bindings TO %I',
        s, p_role
    );

    EXECUTE format(
        'GRANT INSERT (id, job_type, payload, effect_digest, work_key, idempotency_key, max_attempts, available_at) ON %I.worker_jobs TO %I',
        s, p_role
    );

    -- No direct INSERT/UPDATE/DELETE on events, outbox, correction projection
    -- fields, job state/lease fields, correction revisions, or qualifications.
    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION %I.record_event_idempotent(uuid,uuid,text,text,jsonb,text,text,timestamptz,jsonb,text) TO %I',
        s, p_role
    );
    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION %I.claim_worker_job(text,integer) TO %I',
        s, p_role
    );
    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION %I.complete_worker_job(uuid,text) TO %I',
        s, p_role
    );
    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION %I.fail_worker_job(uuid,text,jsonb,boolean,integer) TO %I',
        s, p_role
    );

    -- Verify effective privileges, not merely direct grants. This catches
    -- ownership or unexpected privilege inheritance that would defeat the
    -- least-privilege contract.
    IF pg_catalog.has_schema_privilege(p_role, s, 'CREATE')
       OR pg_catalog.has_table_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'corrections'), 'UPDATE'
          )
       OR pg_catalog.has_table_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'events'), 'INSERT'
          )
       OR pg_catalog.has_table_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'events'), 'UPDATE'
          )
       OR pg_catalog.has_table_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'events'), 'DELETE'
          )
       OR pg_catalog.has_table_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'outbox'), 'INSERT'
          )
       OR pg_catalog.has_table_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'outbox'), 'UPDATE'
          )
       OR pg_catalog.has_table_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'outbox'), 'DELETE'
          )
       OR pg_catalog.has_table_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'worker_jobs'), 'UPDATE'
          ) THEN
        RAISE EXCEPTION 'runtime role % retains forbidden effective privileges', p_role;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DO $secure_config$
DECLARE
    s name := current_schema();
BEGIN
    EXECUTE format(
        'ALTER FUNCTION %I.configure_fuckup_runtime_role(name) SET search_path TO %I, pg_catalog, pg_temp',
        s, s
    );
    EXECUTE format(
        'REVOKE ALL ON FUNCTION %I.configure_fuckup_runtime_role(name) FROM PUBLIC',
        s
    );
END;
$secure_config$ LANGUAGE plpgsql;

COMMIT;
