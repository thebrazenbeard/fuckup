BEGIN;

CREATE TABLE incident_occurrences (
    id uuid PRIMARY KEY,
    incident_id uuid NOT NULL REFERENCES incidents(id),
    ordinal bigint NOT NULL CHECK (ordinal > 0),
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    payload_digest text NOT NULL CHECK (btrim(payload_digest) <> ''),
    observed_at timestamptz NOT NULL DEFAULT now(),
    source_ref text,
    UNIQUE (incident_id, ordinal)
);

CREATE TABLE effect_operations (
    id uuid PRIMARY KEY,
    idempotency_key text NOT NULL UNIQUE CHECK (btrim(idempotency_key) <> ''),
    target text NOT NULL CHECK (btrim(target) <> ''),
    operation_kind text NOT NULL CHECK (btrim(operation_kind) <> ''),
    effect_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    effect_digest text NOT NULL CHECK (btrim(effect_digest) <> ''),
    prepared_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE effect_operation_events (
    id bigserial PRIMARY KEY,
    operation_id uuid NOT NULL REFERENCES effect_operations(id),
    state text NOT NULL CHECK (state IN ('ATTEMPTED', 'AMBIGUOUS', 'VERIFIED', 'FAILED')),
    evidence_ref text,
    readback_digest text,
    observed_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        (state = 'VERIFIED' AND readback_digest IS NOT NULL AND btrim(readback_digest) <> '')
        OR state <> 'VERIFIED'
    )
);

CREATE FUNCTION record_incident_occurrence(
    p_id uuid,
    p_incident_id uuid,
    p_payload jsonb,
    p_payload_digest text,
    p_observed_at timestamptz DEFAULT now(),
    p_source_ref text DEFAULT NULL
)
RETURNS SETOF incident_occurrences AS $occurrence$
DECLARE
    next_ordinal bigint;
    occurrence_time timestamptz := COALESCE(p_observed_at, now());
BEGIN
    IF p_payload_digest IS NULL OR btrim(p_payload_digest) = '' THEN
        RAISE EXCEPTION 'payload digest is required';
    END IF;

    PERFORM 1 FROM incidents WHERE id = p_incident_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown incident %', p_incident_id;
    END IF;
    SELECT COALESCE(max(ordinal), 0) + 1
      INTO next_ordinal
      FROM incident_occurrences
     WHERE incident_id = p_incident_id;

    RETURN QUERY
    INSERT INTO incident_occurrences(
        id, incident_id, ordinal, payload, payload_digest, observed_at, source_ref
    )
    VALUES (
        p_id,
        p_incident_id,
        next_ordinal,
        COALESCE(p_payload, '{}'::jsonb),
        p_payload_digest,
        occurrence_time,
        p_source_ref
    )
    RETURNING *;

    UPDATE incidents
       SET occurrence_count = next_ordinal,
           last_seen_at = GREATEST(last_seen_at, occurrence_time)
     WHERE id = p_incident_id;
END;
$occurrence$ LANGUAGE plpgsql;

CREATE FUNCTION prepare_effect_operation(
    p_id uuid,
    p_idempotency_key text,
    p_target text,
    p_operation_kind text,
    p_effect_payload jsonb,
    p_effect_digest text,
    p_prepared_at timestamptz DEFAULT now()
)
RETURNS SETOF effect_operations AS $prepare$
DECLARE
    existing effect_operations%ROWTYPE;
BEGIN
    IF p_idempotency_key IS NULL OR btrim(p_idempotency_key) = ''
       OR p_target IS NULL OR btrim(p_target) = ''
       OR p_operation_kind IS NULL OR btrim(p_operation_kind) = ''
       OR p_effect_digest IS NULL OR btrim(p_effect_digest) = '' THEN
        RAISE EXCEPTION 'operation identity fields are required';
    END IF;

    SELECT * INTO existing
      FROM effect_operations
     WHERE idempotency_key = p_idempotency_key
     FOR SHARE;

    IF FOUND THEN
        IF existing.target IS DISTINCT FROM p_target
           OR existing.operation_kind IS DISTINCT FROM p_operation_kind
           OR existing.effect_payload IS DISTINCT FROM COALESCE(p_effect_payload, '{}'::jsonb)
           OR existing.effect_digest IS DISTINCT FROM p_effect_digest THEN
            RAISE EXCEPTION 'idempotency key collision for a different effect';
        END IF;
        RETURN NEXT existing;
        RETURN;
    END IF;

    BEGIN
        RETURN QUERY
        INSERT INTO effect_operations(
            id, idempotency_key, target, operation_kind,
            effect_payload, effect_digest, prepared_at
        )
        VALUES (
            p_id, p_idempotency_key, p_target, p_operation_kind,
            COALESCE(p_effect_payload, '{}'::jsonb), p_effect_digest,
            COALESCE(p_prepared_at, now())
        )
        RETURNING *;
        RETURN;
    EXCEPTION WHEN unique_violation THEN
        SELECT * INTO existing
          FROM effect_operations
         WHERE idempotency_key = p_idempotency_key
         FOR SHARE;

        IF existing.target IS DISTINCT FROM p_target
           OR existing.operation_kind IS DISTINCT FROM p_operation_kind
           OR existing.effect_payload IS DISTINCT FROM COALESCE(p_effect_payload, '{}'::jsonb)
           OR existing.effect_digest IS DISTINCT FROM p_effect_digest THEN
            RAISE EXCEPTION 'idempotency key collision for a different effect';
        END IF;
        RETURN NEXT existing;
        RETURN;
    END;
END;
$prepare$ LANGUAGE plpgsql;

CREATE FUNCTION record_effect_attempt(
    p_operation_id uuid,
    p_evidence_ref text DEFAULT NULL,
    p_observed_at timestamptz DEFAULT now()
)
RETURNS SETOF effect_operation_events AS $attempt$
DECLARE
    current_state text;
BEGIN
    PERFORM 1 FROM effect_operations WHERE id = p_operation_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown effect operation %', p_operation_id;
    END IF;

    SELECT state
      INTO current_state
      FROM effect_operation_events
     WHERE operation_id = p_operation_id
     ORDER BY id DESC
     LIMIT 1;

    IF current_state IS NOT NULL THEN
        RAISE EXCEPTION 'cannot attempt operation from state %', current_state;
    END IF;

    RETURN QUERY
    INSERT INTO effect_operation_events(
        operation_id, state, evidence_ref, observed_at
    )
    VALUES (
        p_operation_id, 'ATTEMPTED', p_evidence_ref, COALESCE(p_observed_at, now())
    )
    RETURNING *;
END;
$attempt$ LANGUAGE plpgsql;

CREATE FUNCTION reconcile_effect_operation(
    p_operation_id uuid,
    p_outcome text,
    p_evidence_ref text,
    p_readback_digest text DEFAULT NULL,
    p_observed_at timestamptz DEFAULT now()
)
RETURNS SETOF effect_operation_events AS $reconcile$
DECLARE
    current_state text;
    normalized_outcome text := upper(btrim(COALESCE(p_outcome, '')));
BEGIN
    PERFORM 1 FROM effect_operations WHERE id = p_operation_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown effect operation %', p_operation_id;
    END IF;

    SELECT state
      INTO current_state
      FROM effect_operation_events
     WHERE operation_id = p_operation_id
     ORDER BY id DESC
     LIMIT 1;
    IF p_evidence_ref IS NULL OR btrim(p_evidence_ref) = '' THEN
        RAISE EXCEPTION 'reconciliation evidence_ref is required';
    END IF;

    IF normalized_outcome = 'AMBIGUOUS' THEN
        IF current_state IS DISTINCT FROM 'ATTEMPTED' THEN
            RAISE EXCEPTION 'cannot mark operation ambiguous from state %', current_state;
        END IF;
    ELSIF normalized_outcome IN ('VERIFIED', 'FAILED') THEN
        IF current_state NOT IN ('ATTEMPTED', 'AMBIGUOUS') THEN
            RAISE EXCEPTION 'cannot reconcile operation from state %', current_state;
        END IF;
        IF normalized_outcome = 'VERIFIED'
           AND (p_readback_digest IS NULL OR btrim(p_readback_digest) = '') THEN
            RAISE EXCEPTION 'verified reconciliation requires readback digest';
        END IF;
    ELSE
        RAISE EXCEPTION 'reconciliation outcome must be AMBIGUOUS, VERIFIED, or FAILED';
    END IF;

    RETURN QUERY
    INSERT INTO effect_operation_events(
        operation_id, state, evidence_ref, readback_digest, observed_at
    )
    VALUES (
        p_operation_id, normalized_outcome, p_evidence_ref,
        p_readback_digest, COALESCE(p_observed_at, now())
    )
    RETURNING *;
END;
$reconcile$ LANGUAGE plpgsql;

CREATE TRIGGER incident_occurrences_append_only
    BEFORE UPDATE OR DELETE ON incident_occurrences
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation();

CREATE TRIGGER effect_operations_append_only
    BEFORE UPDATE OR DELETE ON effect_operations
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation();

CREATE TRIGGER effect_operation_events_append_only
    BEFORE UPDATE OR DELETE ON effect_operation_events
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation();

ALTER FUNCTION configure_fuckup_runtime_role(name)
    RENAME TO configure_fuckup_runtime_role_base_v3;

CREATE FUNCTION configure_fuckup_runtime_role(p_role name)
RETURNS void AS $runtime_config$
DECLARE
    s name := current_schema();
BEGIN
    PERFORM configure_fuckup_runtime_role_base_v3(p_role);

    EXECUTE format('REVOKE ALL PRIVILEGES ON %I.incident_occurrences FROM %I', s, p_role);
    EXECUTE format('REVOKE ALL PRIVILEGES ON %I.effect_operations FROM %I', s, p_role);
    EXECUTE format('REVOKE ALL PRIVILEGES ON %I.effect_operation_events FROM %I', s, p_role);
    EXECUTE format('GRANT SELECT ON %I.incident_occurrences TO %I', s, p_role);
    EXECUTE format('GRANT SELECT ON %I.effect_operations TO %I', s, p_role);
    EXECUTE format('GRANT SELECT ON %I.effect_operation_events TO %I', s, p_role);

    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION %I.record_incident_occurrence(uuid,uuid,jsonb,text,timestamptz,text) TO %I',
        s, p_role
    );
    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION %I.prepare_effect_operation(uuid,text,text,text,jsonb,text,timestamptz) TO %I',
        s, p_role
    );
    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION %I.record_effect_attempt(uuid,text,timestamptz) TO %I',
        s, p_role
    );
    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION %I.reconcile_effect_operation(uuid,text,text,text,timestamptz) TO %I',
        s, p_role
    );

    IF pg_catalog.has_table_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'incident_occurrences'),
            'INSERT, UPDATE, DELETE, TRUNCATE'
       )
       OR pg_catalog.has_table_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'effect_operations'),
            'INSERT, UPDATE, DELETE, TRUNCATE'
       )
       OR pg_catalog.has_table_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'effect_operation_events'),
            'INSERT, UPDATE, DELETE, TRUNCATE'
       )
       OR pg_catalog.has_any_column_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'incident_occurrences'), 'INSERT, UPDATE'
       )
       OR pg_catalog.has_any_column_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'effect_operations'), 'INSERT, UPDATE'
       )
       OR pg_catalog.has_any_column_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'effect_operation_events'), 'INSERT, UPDATE'
       ) THEN
        RAISE EXCEPTION 'runtime role % retains direct execution-integrity DML authority', p_role;
    END IF;
END;
$runtime_config$ LANGUAGE plpgsql SECURITY DEFINER;

DO $secure_execution_integrity_functions$
DECLARE
    s name := current_schema();
    signatures text[] := ARRAY[
        'record_incident_occurrence(uuid,uuid,jsonb,text,timestamptz,text)',
        'prepare_effect_operation(uuid,text,text,text,jsonb,text,timestamptz)',
        'record_effect_attempt(uuid,text,timestamptz)',
        'reconcile_effect_operation(uuid,text,text,text,timestamptz)',
        'configure_fuckup_runtime_role(name)',
        'configure_fuckup_runtime_role_base_v3(name)'
    ];
    sig text;
BEGIN
    FOREACH sig IN ARRAY signatures LOOP
        EXECUTE format('ALTER FUNCTION %I.%s SECURITY DEFINER', s, sig);
        EXECUTE format(
            'ALTER FUNCTION %I.%s SET search_path TO %I, pg_catalog, pg_temp',
            s, sig, s
        );
        EXECUTE format('REVOKE ALL ON FUNCTION %I.%s FROM PUBLIC', s, sig);
    END LOOP;
END;
$secure_execution_integrity_functions$ LANGUAGE plpgsql;

COMMIT;