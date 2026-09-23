BEGIN;

-- Promotion and injection are protected effects. Generic runtime identities may
-- prepare/qualify candidates and may contract already-authorized effects for
-- safety, but they cannot create or broaden authorization.
CREATE TABLE authority_role_assignments (
    role_oid oid PRIMARY KEY,
    role_name name NOT NULL UNIQUE,
    role_kind text NOT NULL CHECK (role_kind IN ('runtime', 'authorizer')),
    assigned_at timestamptz NOT NULL DEFAULT now()
);

REVOKE ALL ON authority_role_assignments FROM PUBLIC;

ALTER TABLE promotions
    ADD COLUMN authorization_ref text;

CREATE FUNCTION selector_scope_is_valid(p_scope jsonb)
RETURNS boolean AS $$
BEGIN
    IF p_scope IS NULL
       OR jsonb_typeof(p_scope) <> 'object'
       OR p_scope = '{}'::jsonb THEN
        RETURN false;
    END IF;

    RETURN NOT EXISTS (
        SELECT 1
          FROM jsonb_each(p_scope) AS item(key, value)
         WHERE item.key = ''
            OR jsonb_typeof(item.value) NOT IN ('string', 'number', 'boolean')
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE FUNCTION validate_promotion_authority_shape()
RETURNS trigger AS $$
BEGIN
    IF NEW.authorization_ref IS NULL OR btrim(NEW.authorization_ref) = '' THEN
        RAISE EXCEPTION 'promotion authorization_ref is required';
    END IF;

    IF NOT selector_scope_is_valid(NEW.activation_scope) THEN
        RAISE EXCEPTION
            'activation_scope must be a non-empty flat selector of JSON scalar values';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER promotions_authority_shape_before_insert
BEFORE INSERT ON promotions
FOR EACH ROW EXECUTE FUNCTION validate_promotion_authority_shape();

CREATE FUNCTION validate_injection_binding_authority()
RETURNS trigger AS $
DECLARE
    approved_scope jsonb;
    promotion_revoked_at timestamptz;
    promotion_revision integer;
    current_revision integer;
    correction_status text;
BEGIN
    IF NOT selector_scope_is_valid(NEW.selector) THEN
        RAISE EXCEPTION
            'binding selector must be a non-empty flat selector of JSON scalar values';
    END IF;

    SELECT p.activation_scope, p.revoked_at, p.correction_revision,
           c.current_revision, c.status
      INTO approved_scope, promotion_revoked_at, promotion_revision,
           current_revision, correction_status
      FROM promotions p
      JOIN corrections c ON c.id = p.correction_id
     WHERE p.id = NEW.promotion_id
     FOR SHARE OF p, c;

    IF approved_scope IS NULL THEN
        RAISE EXCEPTION 'unknown promotion %', NEW.promotion_id;
    END IF;

    IF promotion_revoked_at IS NOT NULL THEN
        RAISE EXCEPTION 'cannot create a binding for revoked promotion %', NEW.promotion_id;
    END IF;

    IF promotion_revision <> current_revision OR correction_status <> 'ACTIVE' THEN
        RAISE EXCEPTION
            'cannot create a binding for stale or inactive promotion %',
            NEW.promotion_id;
    END IF;

    -- With the deliberately flat scalar selector contract, JSONB containment
    -- exactly means the binding preserves every approved scope constraint.
    -- Additional key/value constraints make the binding narrower.
    IF NOT (NEW.selector @> approved_scope) THEN
        RAISE EXCEPTION
            'binding selector is broader than promotion activation scope';
    END IF;

    RETURN NEW;
END;
$ LANGUAGE plpgsql;

CREATE TRIGGER injection_bindings_authority_before_insert
BEFORE INSERT ON injection_bindings
FOR EACH ROW EXECUTE FUNCTION validate_injection_binding_authority();

CREATE FUNCTION protect_injection_binding_restriction()
RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'injection bindings are historical evidence and cannot be deleted';
    END IF;

    IF (to_jsonb(NEW) - 'active' - 'expires_at')
       IS DISTINCT FROM
       (to_jsonb(OLD) - 'active' - 'expires_at') THEN
        RAISE EXCEPTION 'binding identity/scope fields are immutable after creation';
    END IF;

    IF NOT OLD.active AND NEW.active THEN
        RAISE EXCEPTION 'binding reactivation requires fresh authorization';
    END IF;

    IF OLD.expires_at IS NOT NULL
       AND (NEW.expires_at IS NULL OR NEW.expires_at > OLD.expires_at) THEN
        RAISE EXCEPTION 'binding expiry may only stay the same or become earlier';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER injection_bindings_restriction_before_update_delete
BEFORE UPDATE OR DELETE ON injection_bindings
FOR EACH ROW EXECUTE FUNCTION protect_injection_binding_restriction();

CREATE FUNCTION create_authorized_promotion(
    p_id uuid,
    p_correction_id uuid,
    p_correction_revision integer,
    p_exact_subject_digest text,
    p_qualification_id uuid,
    p_policy_name text,
    p_policy_version text,
    p_policy_decision jsonb,
    p_approved_by text,
    p_authorization_ref text,
    p_activation_scope jsonb,
    p_rollback_condition jsonb
)
RETURNS SETOF promotions AS $$
BEGIN
    IF p_approved_by IS NULL OR btrim(p_approved_by) = '' THEN
        RAISE EXCEPTION 'approved_by is required at the authorizer boundary';
    END IF;

    IF p_authorization_ref IS NULL OR btrim(p_authorization_ref) = '' THEN
        RAISE EXCEPTION 'authorization_ref is required at the authorizer boundary';
    END IF;

    RETURN QUERY
    INSERT INTO promotions(
        id, correction_id, correction_revision, exact_subject_digest,
        qualification_id, qualification_result, policy_name, policy_version,
        policy_decision, approved_by, authorization_ref,
        activation_scope, rollback_condition
    )
    VALUES (
        p_id, p_correction_id, p_correction_revision, p_exact_subject_digest,
        p_qualification_id, 'PASS', p_policy_name, p_policy_version,
        p_policy_decision, p_approved_by, p_authorization_ref,
        p_activation_scope, p_rollback_condition
    )
    RETURNING *;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION create_injection_binding(
    p_id uuid,
    p_promotion_id uuid,
    p_adapter text,
    p_selector jsonb,
    p_selector_digest text,
    p_priority integer DEFAULT 0,
    p_conflict_policy text DEFAULT 'FAIL_CLOSED',
    p_expires_at timestamptz DEFAULT NULL
)
RETURNS SETOF injection_bindings AS $$
BEGIN
    RETURN QUERY
    INSERT INTO injection_bindings(
        id, promotion_id, adapter, selector, selector_digest,
        priority, conflict_policy, expires_at
    )
    VALUES (
        p_id, p_promotion_id, p_adapter, p_selector, p_selector_digest,
        p_priority, p_conflict_policy, p_expires_at
    )
    RETURNING *;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION restrict_injection_binding(
    p_binding_id uuid,
    p_deactivate boolean DEFAULT false,
    p_expires_at timestamptz DEFAULT NULL
)
RETURNS SETOF injection_bindings AS $$
DECLARE
    current_row injection_bindings%ROWTYPE;
BEGIN
    IF NOT p_deactivate AND p_expires_at IS NULL THEN
        RAISE EXCEPTION 'restriction must deactivate the binding or set an expiry';
    END IF;

    SELECT * INTO current_row
      FROM injection_bindings
     WHERE id = p_binding_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown binding %', p_binding_id;
    END IF;

    IF p_expires_at IS NOT NULL
       AND current_row.expires_at IS NOT NULL
       AND p_expires_at > current_row.expires_at THEN
        RAISE EXCEPTION 'binding expiry extension requires fresh authorization';
    END IF;

    RETURN QUERY
    UPDATE injection_bindings
       SET active = CASE WHEN p_deactivate THEN false ELSE active END,
           expires_at = CASE
               WHEN p_expires_at IS NULL THEN expires_at
               WHEN expires_at IS NULL THEN p_expires_at
               ELSE LEAST(expires_at, p_expires_at)
           END
     WHERE id = p_binding_id
     RETURNING *;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION revoke_promotion(
    p_promotion_id uuid,
    p_revoked_at timestamptz DEFAULT now()
)
RETURNS SETOF promotions AS $$
BEGIN
    RETURN QUERY
    UPDATE promotions
       SET revoked_at = p_revoked_at
     WHERE id = p_promotion_id
     RETURNING *;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown promotion %', p_promotion_id;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION assert_fuckup_clean_role(p_role name, p_kind text)
RETURNS void AS $$
DECLARE
    s name := current_schema();
    target_oid oid;
    role_superuser boolean;
    role_createrole boolean;
    role_createdb boolean;
    role_replication boolean;
    role_bypassrls boolean;
BEGIN
    IF p_kind NOT IN ('runtime', 'authorizer') THEN
        RAISE EXCEPTION 'unknown F.U.C.K.U.P. role kind %', p_kind;
    END IF;

    SELECT oid, rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls
      INTO target_oid, role_superuser, role_createrole, role_createdb,
           role_replication, role_bypassrls
      FROM pg_catalog.pg_roles
     WHERE rolname = p_role;

    IF target_oid IS NULL THEN
        RAISE EXCEPTION '% role % does not exist', p_kind, p_role;
    END IF;

    IF role_superuser OR role_createrole OR role_createdb
       OR role_replication OR role_bypassrls THEN
        RAISE EXCEPTION '% role % has forbidden administrative attributes', p_kind, p_role;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_auth_members WHERE member = target_oid
    ) THEN
        RAISE EXCEPTION '% role % must not be a member of another role', p_kind, p_role;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_database
         WHERE datname = current_database()
           AND datdba = target_oid
    ) THEN
        RAISE EXCEPTION '% role % must not own database %', p_kind, p_role, current_database();
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_namespace
         WHERE nspname = s
           AND nspowner = target_oid
    ) THEN
        RAISE EXCEPTION '% role % must not own trusted schema %', p_kind, p_role, s;
    END IF;

    IF pg_catalog.has_database_privilege(p_role, current_database(), 'CREATE')
       OR pg_catalog.has_schema_privilege(p_role, s, 'CREATE') THEN
        RAISE EXCEPTION '% role % retains object-creation authority', p_kind, p_role;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION claim_fuckup_role_kind(p_role name, p_kind text)
RETURNS void AS $$
DECLARE
    target_oid oid;
    assigned authority_role_assignments%ROWTYPE;
BEGIN
    IF p_kind NOT IN ('runtime', 'authorizer') THEN
        RAISE EXCEPTION 'unknown F.U.C.K.U.P. role kind %', p_kind;
    END IF;

    SELECT oid INTO target_oid
      FROM pg_catalog.pg_roles
     WHERE rolname = p_role;

    IF target_oid IS NULL THEN
        RAISE EXCEPTION 'role % does not exist', p_role;
    END IF;

    SELECT * INTO assigned
      FROM authority_role_assignments
     WHERE role_oid = target_oid OR role_name = p_role
     LIMIT 1
     FOR UPDATE;

    IF FOUND THEN
        IF assigned.role_oid <> target_oid
           OR assigned.role_name <> p_role
           OR assigned.role_kind <> p_kind THEN
            RAISE EXCEPTION
                'role % is already bound to incompatible authority kind %',
                p_role, assigned.role_kind;
        END IF;
        RETURN;
    END IF;

    INSERT INTO authority_role_assignments(role_oid, role_name, role_kind)
    VALUES (target_oid, p_role, p_kind);
END;
$$ LANGUAGE plpgsql;

-- Preserve the already-reviewed runtime configurator as the low-level grant
-- recipe, then wrap it with role separation and protected-effect revocation.
ALTER FUNCTION configure_fuckup_runtime_role(name)
RENAME TO configure_fuckup_runtime_role_v2_base;

CREATE FUNCTION configure_fuckup_runtime_role(p_role name)
RETURNS void AS $$
DECLARE
    s name := current_schema();
BEGIN
    PERFORM assert_fuckup_clean_role(p_role, 'runtime');
    PERFORM claim_fuckup_role_kind(p_role, 'runtime');
    PERFORM configure_fuckup_runtime_role_v2_base(p_role);

    -- The v2 base granted promotion/binding column privileges. Remove them:
    -- runtime may prepare and qualify, but may not create/broaden protected effects.
    EXECUTE format(
        'REVOKE INSERT (id, correction_id, correction_revision, exact_subject_digest, qualification_id, qualification_result, policy_name, policy_version, policy_decision, approved_by, activation_scope, rollback_condition) ON %I.promotions FROM %I',
        s, p_role
    );
    EXECUTE format(
        'REVOKE UPDATE (revoked_at) ON %I.promotions FROM %I',
        s, p_role
    );
    EXECUTE format(
        'REVOKE INSERT (id, promotion_id, adapter, selector, selector_digest, priority, conflict_policy, expires_at) ON %I.injection_bindings FROM %I',
        s, p_role
    );
    EXECUTE format(
        'REVOKE UPDATE (active, expires_at) ON %I.injection_bindings FROM %I',
        s, p_role
    );

    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION %I.revoke_promotion(uuid,timestamptz) TO %I',
        s, p_role
    );
    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION %I.restrict_injection_binding(uuid,boolean,timestamptz) TO %I',
        s, p_role
    );

    IF pg_catalog.has_any_column_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'promotions'), 'INSERT, UPDATE'
       )
       OR pg_catalog.has_table_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'promotions'), 'DELETE, TRUNCATE'
       )
       OR pg_catalog.has_any_column_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'injection_bindings'), 'INSERT, UPDATE'
       )
       OR pg_catalog.has_table_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'injection_bindings'), 'DELETE, TRUNCATE'
       ) THEN
        RAISE EXCEPTION 'runtime role % retains protected promotion/binding DML authority', p_role;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION configure_fuckup_authorizer_role(p_role name)
RETURNS void AS $$
DECLARE
    s name := current_schema();
    t text;
BEGIN
    PERFORM assert_fuckup_clean_role(p_role, 'authorizer');
    PERFORM claim_fuckup_role_kind(p_role, 'authorizer');

    EXECUTE format('REVOKE ALL PRIVILEGES ON SCHEMA %I FROM %I', s, p_role);
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO %I', s, p_role);
    EXECUTE format('REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA %I FROM %I', s, p_role);
    EXECUTE format('REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA %I FROM %I', s, p_role);
    EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO %I', s, p_role);

    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION %I.create_authorized_promotion(uuid,uuid,integer,text,uuid,text,text,jsonb,text,text,jsonb,jsonb) TO %I',
        s, p_role
    );
    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION %I.create_injection_binding(uuid,uuid,text,jsonb,text,integer,text,timestamptz) TO %I',
        s, p_role
    );
    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION %I.revoke_promotion(uuid,timestamptz) TO %I',
        s, p_role
    );
    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION %I.restrict_injection_binding(uuid,boolean,timestamptz) TO %I',
        s, p_role
    );

    FOREACH t IN ARRAY ARRAY[
        'incidents', 'events', 'root_cause_candidates', 'corrections',
        'correction_revisions', 'qualifications', 'promotions',
        'injection_bindings', 'worker_jobs', 'outbox',
        'authority_role_assignments'
    ] LOOP
        IF pg_catalog.has_table_privilege(
                p_role, pg_catalog.format('%I.%I', s, t), 'INSERT, UPDATE, DELETE, TRUNCATE'
           )
           OR pg_catalog.has_any_column_privilege(
                p_role, pg_catalog.format('%I.%I', s, t), 'INSERT, UPDATE'
           ) THEN
            RAISE EXCEPTION 'authorizer role % retains direct DML on %', p_role, t;
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

DO $secure_promotion_authority$
DECLARE
    s name := current_schema();
    signatures text[] := ARRAY[
        'assert_fuckup_clean_role(name,text)',
        'claim_fuckup_role_kind(name,text)',
        'configure_fuckup_runtime_role(name)',
        'configure_fuckup_authorizer_role(name)',
        'create_authorized_promotion(uuid,uuid,integer,text,uuid,text,text,jsonb,text,text,jsonb,jsonb)',
        'create_injection_binding(uuid,uuid,text,jsonb,text,integer,text,timestamptz)',
        'revoke_promotion(uuid,timestamptz)',
        'restrict_injection_binding(uuid,boolean,timestamptz)'
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
$secure_promotion_authority$ LANGUAGE plpgsql;

COMMIT;
