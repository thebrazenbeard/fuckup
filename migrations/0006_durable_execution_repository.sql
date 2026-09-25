BEGIN;

CREATE TABLE outcome_observations (
    id uuid PRIMARY KEY,
    operation_id uuid NOT NULL UNIQUE REFERENCES effect_operations(id),
    correction_id uuid NOT NULL,
    correction_revision integer NOT NULL CHECK (correction_revision > 0),
    promotion_id uuid NOT NULL REFERENCES promotions(id),
    binding_id uuid NOT NULL REFERENCES injection_bindings(id),
    scope_digest text NOT NULL CHECK (btrim(scope_digest) <> ''),
    effect_digest text NOT NULL CHECK (btrim(effect_digest) <> ''),
    verification_evidence_ref text NOT NULL CHECK (btrim(verification_evidence_ref) <> ''),
    failure_occurred boolean NOT NULL,
    correction_triggered boolean NOT NULL,
    prevented boolean NOT NULL,
    regression boolean NOT NULL,
    observed_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (correction_id, correction_revision)
        REFERENCES correction_revisions(correction_id, revision)
);

CREATE FUNCTION record_verified_outcome_observation(
    p_id uuid,
    p_operation_id uuid,
    p_correction_id uuid,
    p_correction_revision integer,
    p_promotion_id uuid,
    p_binding_id uuid,
    p_scope_digest text,
    p_effect_digest text,
    p_verification_evidence_ref text,
    p_failure_occurred boolean,
    p_correction_triggered boolean,
    p_prevented boolean,
    p_regression boolean,
    p_observed_at timestamptz DEFAULT now()
)
RETURNS SETOF outcome_observations AS $outcome$
DECLARE
    op effect_operations%ROWTYPE;
    latest_event effect_operation_events%ROWTYPE;
    existing outcome_observations%ROWTYPE;
BEGIN
    SELECT * INTO op
      FROM effect_operations
     WHERE id = p_operation_id
     FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown effect operation %', p_operation_id;
    END IF;

    SELECT * INTO latest_event
      FROM effect_operation_events
     WHERE operation_id = p_operation_id
     ORDER BY id DESC
     LIMIT 1;

    IF latest_event.state IS DISTINCT FROM 'VERIFIED' THEN
        RAISE EXCEPTION 'outcome observation requires VERIFIED operation';
    END IF;

    IF op.effect_digest IS DISTINCT FROM p_effect_digest THEN
        RAISE EXCEPTION 'outcome effect digest does not match operation';
    END IF;

    IF op.effect_payload->>'correction_id' IS DISTINCT FROM p_correction_id::text
       OR (op.effect_payload->>'correction_revision')::integer IS DISTINCT FROM p_correction_revision
       OR op.effect_payload->>'promotion_id' IS DISTINCT FROM p_promotion_id::text
       OR op.effect_payload->>'binding_id' IS DISTINCT FROM p_binding_id::text
       OR op.effect_payload->>'selector_digest' IS DISTINCT FROM p_scope_digest THEN
        RAISE EXCEPTION 'outcome subject does not match operation provenance';
    END IF;

    IF latest_event.evidence_ref IS DISTINCT FROM p_verification_evidence_ref THEN
        RAISE EXCEPTION 'outcome verification evidence does not match VERIFIED event';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM injection_bindings binding
        JOIN promotions promotion
          ON promotion.id = binding.promotion_id
        WHERE binding.id = p_binding_id
          AND binding.promotion_id = p_promotion_id
          AND promotion.correction_id = p_correction_id
          AND promotion.correction_revision = p_correction_revision
          AND binding.selector_digest = p_scope_digest
          AND binding.adapter_version IS NOT NULL
          AND op.effect_payload->>'adapter' = binding.adapter
          AND op.effect_payload->>'adapter_version' = binding.adapter_version
          AND op.operation_kind = 'injector:' || binding.adapter || '@' || binding.adapter_version
    ) THEN
        RAISE EXCEPTION 'outcome binding lineage does not match operation';
    END IF;

    SELECT * INTO existing
      FROM outcome_observations
     WHERE operation_id = p_operation_id
     FOR SHARE;

    IF FOUND THEN
        IF existing.correction_id IS DISTINCT FROM p_correction_id
           OR existing.correction_revision IS DISTINCT FROM p_correction_revision
           OR existing.promotion_id IS DISTINCT FROM p_promotion_id
           OR existing.binding_id IS DISTINCT FROM p_binding_id
           OR existing.scope_digest IS DISTINCT FROM p_scope_digest
           OR existing.effect_digest IS DISTINCT FROM p_effect_digest
           OR existing.verification_evidence_ref IS DISTINCT FROM p_verification_evidence_ref
           OR existing.failure_occurred IS DISTINCT FROM p_failure_occurred
           OR existing.correction_triggered IS DISTINCT FROM p_correction_triggered
           OR existing.prevented IS DISTINCT FROM p_prevented
           OR existing.regression IS DISTINCT FROM p_regression THEN
            RAISE EXCEPTION 'outcome observation collision';
        END IF;
        RETURN NEXT existing;
        RETURN;
    END IF;
    BEGIN
        RETURN QUERY
        INSERT INTO outcome_observations(
            id,
            operation_id,
            correction_id,
            correction_revision,
            promotion_id,
            binding_id,
            scope_digest,
            effect_digest,
            verification_evidence_ref,
            failure_occurred,
            correction_triggered,
            prevented,
            regression,
            observed_at
        )
        VALUES (
            p_id,
            p_operation_id,
            p_correction_id,
            p_correction_revision,
            p_promotion_id,
            p_binding_id,
            p_scope_digest,
            p_effect_digest,
            p_verification_evidence_ref,
            p_failure_occurred,
            p_correction_triggered,
            p_prevented,
            p_regression,
            COALESCE(p_observed_at, now())
        )
        RETURNING *;
        RETURN;
    EXCEPTION WHEN unique_violation THEN
        SELECT * INTO existing
          FROM outcome_observations
         WHERE operation_id = p_operation_id
         FOR SHARE;

        IF existing.correction_id IS DISTINCT FROM p_correction_id
           OR existing.correction_revision IS DISTINCT FROM p_correction_revision
           OR existing.promotion_id IS DISTINCT FROM p_promotion_id
           OR existing.binding_id IS DISTINCT FROM p_binding_id
           OR existing.scope_digest IS DISTINCT FROM p_scope_digest
           OR existing.effect_digest IS DISTINCT FROM p_effect_digest
           OR existing.verification_evidence_ref IS DISTINCT FROM p_verification_evidence_ref
           OR existing.failure_occurred IS DISTINCT FROM p_failure_occurred
           OR existing.correction_triggered IS DISTINCT FROM p_correction_triggered
           OR existing.prevented IS DISTINCT FROM p_prevented
           OR existing.regression IS DISTINCT FROM p_regression THEN
            RAISE EXCEPTION 'outcome observation collision';
        END IF;
        RETURN NEXT existing;
        RETURN;
    END;
END;
$outcome$ LANGUAGE plpgsql;

CREATE TRIGGER outcome_observations_append_only
    BEFORE UPDATE OR DELETE ON outcome_observations
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation();

ALTER FUNCTION configure_fuckup_runtime_role(name)
    RENAME TO configure_fuckup_runtime_role_base_v5;

CREATE FUNCTION configure_fuckup_runtime_role(p_role name)
RETURNS void AS $runtime_config$
DECLARE
    s name := current_schema();
BEGIN
    PERFORM configure_fuckup_runtime_role_base_v5(p_role);

    EXECUTE format(
        'REVOKE ALL PRIVILEGES ON %I.outcome_observations FROM %I',
        s,
        p_role
    );
    EXECUTE format(
        'GRANT SELECT ON %I.outcome_observations TO %I',
        s,
        p_role
    );
    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION %I.record_verified_outcome_observation(uuid,uuid,uuid,integer,uuid,uuid,text,text,text,boolean,boolean,boolean,boolean,timestamptz) TO %I',
        s,
        p_role
    );

    IF pg_catalog.has_table_privilege(
            p_role,
            pg_catalog.format('%I.%I', s, 'outcome_observations'),
            'INSERT, UPDATE, DELETE, TRUNCATE'
       )
       OR pg_catalog.has_any_column_privilege(
            p_role,
            pg_catalog.format('%I.%I', s, 'outcome_observations'),
            'INSERT, UPDATE'
       ) THEN
        RAISE EXCEPTION 'runtime role % retains direct outcome-observation DML authority', p_role;
    END IF;
END;
$runtime_config$ LANGUAGE plpgsql SECURITY DEFINER;

DO $secure_durable_execution_functions$
DECLARE
    s name := current_schema();
    signatures text[] := ARRAY[
        'record_verified_outcome_observation(uuid,uuid,uuid,integer,uuid,uuid,text,text,text,boolean,boolean,boolean,boolean,timestamptz)',
        'configure_fuckup_runtime_role(name)',
        'configure_fuckup_runtime_role_base_v5(name)'
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
$secure_durable_execution_functions$ LANGUAGE plpgsql;

COMMIT;