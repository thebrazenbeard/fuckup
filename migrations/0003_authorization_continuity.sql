BEGIN;

CREATE FUNCTION fuckup_selector_valid(p_selector jsonb)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
STRICT
AS $selector$
    SELECT jsonb_typeof(p_selector) = 'object'
       AND p_selector <> '{}'::jsonb
       AND NOT EXISTS (
            SELECT 1
              FROM jsonb_each(p_selector) AS item(key, value)
             WHERE btrim(item.key) = ''
                OR jsonb_typeof(item.value) <> 'string'
                OR btrim(item.value #>> '{}') = ''
       );
$selector$;

CREATE FUNCTION fuckup_selector_within_scope(p_selector jsonb, p_scope jsonb)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
STRICT
AS $selector_scope$
    SELECT fuckup_selector_valid(p_selector)
       AND fuckup_selector_valid(p_scope)
       AND p_selector @> p_scope;
$selector_scope$;

CREATE TABLE authority_role_assignments (
    role_oid oid PRIMARY KEY,
    role_name name NOT NULL UNIQUE,
    authority_kind text NOT NULL CHECK (authority_kind IN ('RUNTIME', 'AUTHORIZER')),
    configured_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE promotion_authorizations (
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
    root_cause_supported boolean NOT NULL CHECK (root_cause_supported),
    ambiguous boolean NOT NULL CHECK (NOT ambiguous),
    irreversible_acknowledged boolean NOT NULL DEFAULT false,
    activation_scope jsonb NOT NULL CHECK (fuckup_selector_valid(activation_scope)),
    rollback_condition jsonb NOT NULL
        CHECK (jsonb_typeof(rollback_condition) = 'object' AND rollback_condition <> '{}'::jsonb),
    authorized_by text NOT NULL CHECK (btrim(authorized_by) <> ''),
    authorized_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (
        qualification_id,
        correction_id,
        correction_revision,
        exact_subject_digest,
        qualification_result
    )
        REFERENCES qualifications(
            id,
            correction_id,
            correction_revision,
            exact_subject_digest,
            result
        )
);

CREATE TRIGGER promotion_authorizations_append_only
    BEFORE UPDATE OR DELETE ON promotion_authorizations
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation();

ALTER TABLE promotions
    ADD COLUMN authorization_id uuid;

ALTER TABLE promotions
    ADD CONSTRAINT promotions_authorization_id_uq UNIQUE (authorization_id);

ALTER TABLE promotions
    ADD CONSTRAINT promotions_authorization_fk
    FOREIGN KEY (authorization_id)
    REFERENCES promotion_authorizations(id);

CREATE OR REPLACE FUNCTION validate_promotion_insert() RETURNS trigger AS $promotion_guard$
DECLARE
    current_revision integer;
    current_digest text;
    correction_status text;
    auth_record promotion_authorizations%ROWTYPE;
BEGIN
    IF NEW.authorization_id IS NULL THEN
        RAISE EXCEPTION 'promotion authorization artifact is required';
    END IF;

    SELECT *
      INTO auth_record
      FROM promotion_authorizations
     WHERE id = NEW.authorization_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown promotion authorization %', NEW.authorization_id;
    END IF;

    IF NEW.correction_id IS DISTINCT FROM auth_record.correction_id
       OR NEW.correction_revision IS DISTINCT FROM auth_record.correction_revision
       OR NEW.exact_subject_digest IS DISTINCT FROM auth_record.exact_subject_digest
       OR NEW.qualification_id IS DISTINCT FROM auth_record.qualification_id
       OR NEW.qualification_result IS DISTINCT FROM auth_record.qualification_result
       OR NEW.policy_name IS DISTINCT FROM auth_record.policy_name
       OR NEW.policy_version IS DISTINCT FROM auth_record.policy_version
       OR NEW.policy_decision IS DISTINCT FROM auth_record.policy_decision
       OR NEW.activation_scope IS DISTINCT FROM auth_record.activation_scope
       OR NEW.rollback_condition IS DISTINCT FROM auth_record.rollback_condition
       OR NEW.approved_by IS DISTINCT FROM auth_record.authorized_by THEN
        RAISE EXCEPTION 'promotion does not exactly match its authorization artifact';
    END IF;

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
$promotion_guard$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE FUNCTION authorize_and_promote(
    p_authorization_id uuid,
    p_promotion_id uuid,
    p_correction_id uuid,
    p_correction_revision integer,
    p_exact_subject_digest text,
    p_qualification_id uuid,
    p_policy_name text,
    p_policy_version text,
    p_policy_decision jsonb,
    p_activation_scope jsonb,
    p_rollback_condition jsonb,
    p_root_cause_supported boolean,
    p_ambiguous boolean,
    p_irreversible_acknowledged boolean DEFAULT false
)
RETURNS SETOF promotions AS $authorize$
DECLARE
    current_revision integer;
    correction_status text;
    correction_reversible boolean;
    qualification_result text;
    qualification_digest text;
    actor text;
BEGIN
    IF NOT fuckup_selector_valid(p_activation_scope) THEN
        RAISE EXCEPTION 'activation scope must be a non-empty string selector';
    END IF;

    IF jsonb_typeof(p_rollback_condition) <> 'object'
       OR p_rollback_condition = '{}'::jsonb THEN
        RAISE EXCEPTION 'rollback condition must be a non-empty object';
    END IF;

    IF jsonb_typeof(p_policy_decision) <> 'object'
       OR NOT (p_policy_decision @> '{"allow": true}'::jsonb) THEN
        RAISE EXCEPTION 'trusted authorizer policy decision must allow promotion';
    END IF;

    IF NOT p_root_cause_supported OR p_ambiguous THEN
        RAISE EXCEPTION 'promotion requires supported, non-ambiguous causal authorization';
    END IF;

    SELECT c.current_revision, c.status, cr.reversible
      INTO current_revision, correction_status, correction_reversible
      FROM corrections c
      JOIN correction_revisions cr
        ON cr.correction_id = c.id
       AND cr.revision = c.current_revision
     WHERE c.id = p_correction_id
     FOR UPDATE OF c;

    IF current_revision IS NULL THEN
        RAISE EXCEPTION 'unknown or revisionless correction %', p_correction_id;
    END IF;

    IF p_correction_revision <> current_revision THEN
        RAISE EXCEPTION 'authorization targets stale correction revision';
    END IF;

    IF correction_status IN ('SUPERSEDED', 'REVOKED', 'REJECTED') THEN
        RAISE EXCEPTION 'correction status % is not authorizable', correction_status;
    END IF;

    IF NOT correction_reversible AND NOT p_irreversible_acknowledged THEN
        RAISE EXCEPTION 'irreversible correction requires explicit acknowledgement';
    END IF;

    SELECT result, exact_subject_digest
      INTO qualification_result, qualification_digest
      FROM qualifications
     WHERE id = p_qualification_id
       AND correction_id = p_correction_id
       AND correction_revision = p_correction_revision;

    IF qualification_result IS DISTINCT FROM 'PASS'
       OR qualification_digest IS DISTINCT FROM p_exact_subject_digest THEN
        RAISE EXCEPTION 'authorization requires exact PASS qualification evidence';
    END IF;

    actor := NULLIF(pg_catalog.current_setting('role', true), 'none');
    IF actor IS NULL OR btrim(actor) = '' THEN
        actor := session_user;
    END IF;

    INSERT INTO promotion_authorizations(
        id,
        correction_id,
        correction_revision,
        exact_subject_digest,
        qualification_id,
        qualification_result,
        policy_name,
        policy_version,
        policy_decision,
        root_cause_supported,
        ambiguous,
        irreversible_acknowledged,
        activation_scope,
        rollback_condition,
        authorized_by
    )
    VALUES (
        p_authorization_id,
        p_correction_id,
        p_correction_revision,
        p_exact_subject_digest,
        p_qualification_id,
        'PASS',
        p_policy_name,
        p_policy_version,
        p_policy_decision,
        p_root_cause_supported,
        p_ambiguous,
        p_irreversible_acknowledged,
        p_activation_scope,
        p_rollback_condition,
        actor
    );

    RETURN QUERY
    INSERT INTO promotions(
        id,
        correction_id,
        correction_revision,
        exact_subject_digest,
        qualification_id,
        qualification_result,
        policy_name,
        policy_version,
        policy_decision,
        approved_by,
        activation_scope,
        rollback_condition,
        authorization_id
    )
    VALUES (
        p_promotion_id,
        p_correction_id,
        p_correction_revision,
        p_exact_subject_digest,
        p_qualification_id,
        'PASS',
        p_policy_name,
        p_policy_version,
        p_policy_decision,
        actor,
        p_activation_scope,
        p_rollback_condition,
        p_authorization_id
    )
    RETURNING *;
END;
$authorize$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE FUNCTION create_authorized_binding(
    p_binding_id uuid,
    p_promotion_id uuid,
    p_adapter text,
    p_selector jsonb,
    p_selector_digest text,
    p_priority integer DEFAULT 0,
    p_conflict_policy text DEFAULT 'FAIL_CLOSED',
    p_expires_at timestamptz DEFAULT NULL
)
RETURNS SETOF injection_bindings AS $binding$
DECLARE
    authorized_scope jsonb;
    promoted_revision integer;
    current_revision integer;
    correction_status text;
    promotion_revoked_at timestamptz;
BEGIN
    IF p_adapter IS NULL OR btrim(p_adapter) = '' THEN
        RAISE EXCEPTION 'adapter is required';
    END IF;

    IF p_selector_digest IS NULL OR btrim(p_selector_digest) = '' THEN
        RAISE EXCEPTION 'selector digest is required';
    END IF;

    IF p_conflict_policy IS NULL OR btrim(p_conflict_policy) = '' THEN
        RAISE EXCEPTION 'conflict policy is required';
    END IF;

    SELECT auth_record.activation_scope,
           promotion.correction_revision,
           correction.current_revision,
           correction.status,
           promotion.revoked_at
      INTO authorized_scope,
           promoted_revision,
           current_revision,
           correction_status,
           promotion_revoked_at
      FROM promotions promotion
      JOIN promotion_authorizations auth_record
        ON auth_record.id = promotion.authorization_id
      JOIN corrections correction
        ON correction.id = promotion.correction_id
     WHERE promotion.id = p_promotion_id
     FOR UPDATE OF promotion, correction;

    IF authorized_scope IS NULL THEN
        RAISE EXCEPTION 'promotion has no durable authorization artifact';
    END IF;

    IF promotion_revoked_at IS NOT NULL
       OR correction_status <> 'ACTIVE'
       OR promoted_revision <> current_revision THEN
        RAISE EXCEPTION 'promotion is not currently active';
    END IF;

    IF NOT fuckup_selector_within_scope(p_selector, authorized_scope) THEN
        RAISE EXCEPTION 'binding selector must be equal to or narrower than authorized activation scope';
    END IF;

    IF p_expires_at IS NOT NULL AND p_expires_at <= now() THEN
        RAISE EXCEPTION 'new binding expiry must be in the future';
    END IF;

    RETURN QUERY
    INSERT INTO injection_bindings(
        id,
        promotion_id,
        adapter,
        selector,
        selector_digest,
        priority,
        conflict_policy,
        expires_at,
        active
    )
    VALUES (
        p_binding_id,
        p_promotion_id,
        p_adapter,
        p_selector,
        p_selector_digest,
        p_priority,
        p_conflict_policy,
        p_expires_at,
        true
    )
    RETURNING *;
END;
$binding$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE FUNCTION restrict_injection_binding(
    p_binding_id uuid,
    p_deactivate boolean DEFAULT false,
    p_new_expires_at timestamptz DEFAULT NULL
)
RETURNS SETOF injection_bindings AS $restrict_binding$
DECLARE
    current_binding injection_bindings%ROWTYPE;
BEGIN
    SELECT *
      INTO current_binding
      FROM injection_bindings
     WHERE id = p_binding_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown injection binding %', p_binding_id;
    END IF;

    IF p_deactivate IS NULL THEN
        RAISE EXCEPTION 'deactivate flag must be explicit';
    END IF;

    IF NOT p_deactivate AND p_new_expires_at IS NULL THEN
        RAISE EXCEPTION 'binding restriction must deactivate or set an earlier expiry';
    END IF;

    IF p_new_expires_at IS NOT NULL
       AND current_binding.expires_at IS NOT NULL
       AND p_new_expires_at > current_binding.expires_at THEN
        RAISE EXCEPTION 'binding expiry may only move earlier';
    END IF;

    RETURN QUERY
    UPDATE injection_bindings
       SET active = CASE WHEN p_deactivate THEN false ELSE active END,
           expires_at = CASE
               WHEN p_new_expires_at IS NULL THEN expires_at
               ELSE p_new_expires_at
           END
     WHERE id = p_binding_id
     RETURNING *;
END;
$restrict_binding$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE FUNCTION revoke_authorized_promotion(
    p_promotion_id uuid,
    p_revoked_at timestamptz DEFAULT now()
)
RETURNS SETOF promotions AS $revoke_promotion$
BEGIN
    RETURN QUERY
    UPDATE promotions
       SET revoked_at = p_revoked_at
     WHERE id = p_promotion_id
       AND revoked_at IS NULL
     RETURNING *;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'promotion is unknown or already revoked';
    END IF;
END;
$revoke_promotion$ LANGUAGE plpgsql SECURITY DEFINER;

ALTER FUNCTION configure_fuckup_runtime_role(name)
    RENAME TO configure_fuckup_runtime_role_base_v2;

CREATE FUNCTION configure_fuckup_runtime_role(p_role name)
RETURNS void AS $runtime_config$
DECLARE
    s name := current_schema();
    v_role_oid oid;
    assigned_kind text;
BEGIN
    SELECT oid INTO v_role_oid
      FROM pg_catalog.pg_roles
     WHERE rolname = p_role;

    IF v_role_oid IS NULL THEN
        RAISE EXCEPTION 'runtime role % does not exist', p_role;
    END IF;

    SELECT authority_kind INTO assigned_kind
      FROM authority_role_assignments
     WHERE authority_role_assignments.role_oid = v_role_oid;

    IF assigned_kind IS NOT NULL AND assigned_kind <> 'RUNTIME' THEN
        RAISE EXCEPTION 'role % is already assigned as % authority', p_role, assigned_kind;
    END IF;

    PERFORM configure_fuckup_runtime_role_base_v2(p_role);

    -- Defense in depth: remove all direct promotion/binding authority even if
    -- an earlier migration or operator granted it.
    EXECUTE format('REVOKE ALL PRIVILEGES ON %I.promotions FROM %I', s, p_role);
    EXECUTE format('REVOKE ALL PRIVILEGES ON %I.injection_bindings FROM %I', s, p_role);
    EXECUTE format('GRANT SELECT ON %I.promotions TO %I', s, p_role);
    EXECUTE format('GRANT SELECT ON %I.injection_bindings TO %I', s, p_role);

    EXECUTE format(
        'REVOKE EXECUTE ON FUNCTION %I.authorize_and_promote(uuid,uuid,uuid,integer,text,uuid,text,text,jsonb,jsonb,jsonb,boolean,boolean,boolean) FROM %I',
        s, p_role
    );
    EXECUTE format(
        'REVOKE EXECUTE ON FUNCTION %I.create_authorized_binding(uuid,uuid,text,jsonb,text,integer,text,timestamptz) FROM %I',
        s, p_role
    );
    EXECUTE format(
        'REVOKE EXECUTE ON FUNCTION %I.revoke_authorized_promotion(uuid,timestamptz) FROM %I',
        s, p_role
    );
    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION %I.restrict_injection_binding(uuid,boolean,timestamptz) TO %I',
        s, p_role
    );

    IF pg_catalog.has_any_column_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'promotions'), 'INSERT'
       )
       OR pg_catalog.has_any_column_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'promotions'), 'UPDATE'
       )
       OR pg_catalog.has_any_column_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'injection_bindings'), 'INSERT'
       )
       OR pg_catalog.has_any_column_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'injection_bindings'), 'UPDATE'
       )
       OR pg_catalog.has_any_column_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'promotion_authorizations'), 'INSERT'
       )
       OR pg_catalog.has_any_column_privilege(
            p_role, pg_catalog.format('%I.%I', s, 'promotion_authorizations'), 'UPDATE'
       ) THEN
        RAISE EXCEPTION 'runtime role % retains protected promotion/binding DML authority', p_role;
    END IF;

    INSERT INTO authority_role_assignments(role_oid, role_name, authority_kind)
    VALUES (v_role_oid, p_role, 'RUNTIME')
    ON CONFLICT (role_oid) DO UPDATE
       SET role_name = EXCLUDED.role_name,
           authority_kind = EXCLUDED.authority_kind,
           configured_at = now();
END;
$runtime_config$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE FUNCTION configure_fuckup_authorizer_role(p_role name)
RETURNS void AS $authorizer_config$
DECLARE
    s name := current_schema();
    v_role_oid oid;
    role_superuser boolean;
    role_createrole boolean;
    role_createdb boolean;
    role_replication boolean;
    role_bypassrls boolean;
    assigned_kind text;
BEGIN
    SELECT oid, rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls
      INTO v_role_oid, role_superuser, role_createrole, role_createdb,
           role_replication, role_bypassrls
      FROM pg_catalog.pg_roles
     WHERE rolname = p_role;

    IF v_role_oid IS NULL THEN
        RAISE EXCEPTION 'authorizer role % does not exist', p_role;
    END IF;

    IF role_superuser OR role_createrole OR role_createdb OR role_replication OR role_bypassrls THEN
        RAISE EXCEPTION 'authorizer role % has forbidden administrative attributes', p_role;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_database
         WHERE datname = current_database()
           AND datdba = v_role_oid
    ) OR pg_catalog.has_database_privilege(p_role, current_database(), 'CREATE') THEN
        RAISE EXCEPTION 'authorizer role % has forbidden database authority', p_role;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members
         WHERE member = v_role_oid
    ) THEN
        RAISE EXCEPTION 'authorizer role % must not be a member of another role', p_role;
    END IF;

    SELECT authority_kind INTO assigned_kind
      FROM authority_role_assignments
     WHERE authority_role_assignments.role_oid = v_role_oid;

    IF assigned_kind IS NOT NULL AND assigned_kind <> 'AUTHORIZER' THEN
        RAISE EXCEPTION 'role % is already assigned as % authority', p_role, assigned_kind;
    END IF;

    EXECUTE format('REVOKE ALL PRIVILEGES ON SCHEMA %I FROM %I', s, p_role);
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO %I', s, p_role);
    EXECUTE format('REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA %I FROM %I', s, p_role);
    EXECUTE format('REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA %I FROM %I', s, p_role);
    EXECUTE format('REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA %I FROM %I', s, p_role);
    EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO %I', s, p_role);

    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION %I.authorize_and_promote(uuid,uuid,uuid,integer,text,uuid,text,text,jsonb,jsonb,jsonb,boolean,boolean,boolean) TO %I',
        s, p_role
    );
    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION %I.create_authorized_binding(uuid,uuid,text,jsonb,text,integer,text,timestamptz) TO %I',
        s, p_role
    );
    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION %I.revoke_authorized_promotion(uuid,timestamptz) TO %I',
        s, p_role
    );

    IF pg_catalog.has_schema_privilege(p_role, s, 'CREATE')
       OR EXISTS (
            SELECT 1
              FROM unnest(ARRAY[
                    'incidents',
                    'root_cause_candidates',
                    'corrections',
                    'correction_revisions',
                    'qualifications',
                    'promotion_authorizations',
                    'promotions',
                    'injection_bindings',
                    'worker_jobs',
                    'events',
                    'outbox'
              ]) AS protected_table(table_name)
             WHERE pg_catalog.has_table_privilege(
                       p_role,
                       pg_catalog.format('%I.%I', s, protected_table.table_name),
                       'INSERT, UPDATE, DELETE, TRUNCATE'
                   )
                OR pg_catalog.has_any_column_privilege(
                       p_role,
                       pg_catalog.format('%I.%I', s, protected_table.table_name),
                       'INSERT'
                   )
                OR pg_catalog.has_any_column_privilege(
                       p_role,
                       pg_catalog.format('%I.%I', s, protected_table.table_name),
                       'UPDATE'
                   )
          ) THEN
        RAISE EXCEPTION 'authorizer role % retains direct protected-table DML authority', p_role;
    END IF;

    INSERT INTO authority_role_assignments(role_oid, role_name, authority_kind)
    VALUES (v_role_oid, p_role, 'AUTHORIZER')
    ON CONFLICT (role_oid) DO UPDATE
       SET role_name = EXCLUDED.role_name,
           authority_kind = EXCLUDED.authority_kind,
           configured_at = now();
END;
$authorizer_config$ LANGUAGE plpgsql SECURITY DEFINER;

DO $secure_authorization_functions$
DECLARE
    s name := current_schema();
    signatures text[] := ARRAY[
        'validate_promotion_insert()',
        'authorize_and_promote(uuid,uuid,uuid,integer,text,uuid,text,text,jsonb,jsonb,jsonb,boolean,boolean,boolean)',
        'create_authorized_binding(uuid,uuid,text,jsonb,text,integer,text,timestamptz)',
        'restrict_injection_binding(uuid,boolean,timestamptz)',
        'revoke_authorized_promotion(uuid,timestamptz)',
        'configure_fuckup_runtime_role(name)',
        'configure_fuckup_runtime_role_base_v2(name)',
        'configure_fuckup_authorizer_role(name)'
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
$secure_authorization_functions$ LANGUAGE plpgsql;

COMMIT;
