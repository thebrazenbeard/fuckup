BEGIN;

ALTER TABLE injection_bindings
    ADD COLUMN adapter_version text
        CHECK (adapter_version IS NULL OR btrim(adapter_version) <> '');

CREATE FUNCTION create_versioned_authorized_binding(
    p_binding_id uuid,
    p_promotion_id uuid,
    p_adapter text,
    p_adapter_version text,
    p_selector jsonb,
    p_selector_digest text,
    p_priority integer DEFAULT 0,
    p_conflict_policy text DEFAULT 'FAIL_CLOSED',
    p_expires_at timestamptz DEFAULT NULL
)
RETURNS SETOF injection_bindings AS $binding$
BEGIN
    IF p_adapter_version IS NULL OR btrim(p_adapter_version) = '' THEN
        RAISE EXCEPTION 'adapter version is required';
    END IF;

    PERFORM *
      FROM create_authorized_binding(
        p_binding_id,
        p_promotion_id,
        p_adapter,
        p_selector,
        p_selector_digest,
        p_priority,
        p_conflict_policy,
        p_expires_at
      );

    RETURN QUERY
    UPDATE injection_bindings
       SET adapter_version = p_adapter_version
     WHERE id = p_binding_id
       AND promotion_id = p_promotion_id
       AND adapter = p_adapter
    RETURNING *;
END;
$binding$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE VIEW active_injection_bindings AS
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
    p.rollback_condition,
    ib.adapter_version
FROM injection_bindings ib
JOIN promotions p ON p.id = ib.promotion_id
JOIN corrections c ON c.id = p.correction_id
WHERE ib.active = true
  AND p.revoked_at IS NULL
  AND (ib.expires_at IS NULL OR ib.expires_at > now())
  AND c.current_revision = p.correction_revision
  AND c.status = 'ACTIVE';

ALTER FUNCTION configure_fuckup_runtime_role(name)
    RENAME TO configure_fuckup_runtime_role_base_v4;

CREATE FUNCTION configure_fuckup_runtime_role(p_role name)
RETURNS void AS $runtime_config$
DECLARE
    s name := current_schema();
BEGIN
    PERFORM configure_fuckup_runtime_role_base_v4(p_role);

    EXECUTE format(
        'REVOKE EXECUTE ON FUNCTION %I.create_versioned_authorized_binding(uuid,uuid,text,text,jsonb,text,integer,text,timestamptz) FROM %I',
        s,
        p_role
    );
END;
$runtime_config$ LANGUAGE plpgsql SECURITY DEFINER;
ALTER FUNCTION configure_fuckup_authorizer_role(name)
    RENAME TO configure_fuckup_authorizer_role_base_v1;

CREATE FUNCTION configure_fuckup_authorizer_role(p_role name)
RETURNS void AS $authorizer_config$
DECLARE
    s name := current_schema();
BEGIN
    PERFORM configure_fuckup_authorizer_role_base_v1(p_role);

    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION %I.create_versioned_authorized_binding(uuid,uuid,text,text,jsonb,text,integer,text,timestamptz) TO %I',
        s,
        p_role
    );
END;
$authorizer_config$ LANGUAGE plpgsql SECURITY DEFINER;

DO $secure_governed_execution_functions$
DECLARE
    s name := current_schema();
    signatures text[] := ARRAY[
        'create_versioned_authorized_binding(uuid,uuid,text,text,jsonb,text,integer,text,timestamptz)',
        'configure_fuckup_runtime_role(name)',
        'configure_fuckup_runtime_role_base_v4(name)',
        'configure_fuckup_authorizer_role(name)',
        'configure_fuckup_authorizer_role_base_v1(name)'
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
$secure_governed_execution_functions$ LANGUAGE plpgsql;

COMMIT;