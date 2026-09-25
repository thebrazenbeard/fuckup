import os
from pathlib import Path
from uuid import uuid4

import pytest

DATABASE_URL = os.getenv("FUCKUP_TEST_DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("set FUCKUP_TEST_DATABASE_URL to run live PostgreSQL qualification", allow_module_level=True)

psycopg = pytest.importorskip("psycopg")
from psycopg import ClientCursor, sql  # noqa: E402


MIGRATIONS = (
    Path("migrations/0001_core.sql").read_text(),
    Path("migrations/0002_runtime_authority.sql").read_text(),
    Path("migrations/0003_authorization_continuity.sql").read_text(),
    Path("migrations/0004_execution_integrity.sql").read_text(),
    Path("migrations/0005_governed_injector_execution.sql").read_text(),
)


@pytest.fixture()
def db():
    schema = f"fuckup_q_{uuid4().hex}"
    conn = psycopg.connect(DATABASE_URL, autocommit=True, cursor_factory=ClientCursor)
    conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    conn.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
    for migration in MIGRATIONS:
        conn.execute(migration)
    try:
        yield conn, schema
    finally:
        conn.execute("SET search_path TO public")
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        conn.close()


def _ids():
    return tuple(str(uuid4()) for _ in range(8))


def _incident(conn, incident_id):
    conn.execute(
        "INSERT INTO incidents(id, fingerprint, fingerprint_version) VALUES (%s, %s, 'v1')",
        (incident_id, f"fp:{incident_id}"),
    )


def _correction(conn, incident_id, correction_id, *, digest="sha256:a", revision=1, supersedes=None, root_cause_id=None):
    if revision == 1:
        conn.execute(
            "INSERT INTO corrections(id, incident_id) VALUES (%s, %s)",
            (correction_id, incident_id),
        )
    conn.execute(
        """
        INSERT INTO correction_revisions(
            correction_id, revision, subject_digest, payload,
            supersedes_correction_id, supersedes_revision, created_from_root_cause_id
        )
        VALUES (%s, %s, %s, '{}'::jsonb, %s, %s, %s)
        """,
        (
            correction_id,
            revision,
            digest,
            supersedes[0] if supersedes else None,
            supersedes[1] if supersedes else None,
            root_cause_id,
        ),
    )


def _qualification(conn, qualification_id, correction_id, revision, digest, *, result="PASS"):
    conn.execute(
        """
        INSERT INTO qualifications(
            id, correction_id, correction_revision, suite_version,
            exact_subject_digest, result
        )
        VALUES (%s, %s, %s, 'suite-v1', %s, %s)
        """,
        (qualification_id, correction_id, revision, digest, result),
    )


def _promotion(conn, promotion_id, correction_id, revision, digest, qualification_id, *, allow=True):
    authorization_id = str(uuid4())
    conn.execute(
        """
        SELECT id
        FROM authorize_and_promote(
            %s, %s, %s, %s, %s, %s,
            'policy-v1', '1', %s::jsonb,
            '{"agent":"demo"}'::jsonb,
            '{"action":"revoke"}'::jsonb,
            true, false, false
        )
        """,
        (
            authorization_id,
            promotion_id,
            correction_id,
            revision,
            digest,
            qualification_id,
            '{"allow": true}' if allow else '{"allow": false}',
        ),
    ).fetchone()


def test_01_migration_applies(db):
    conn, _schema = db
    assert conn.execute("SELECT to_regclass('incidents')").fetchone()[0] == "incidents"


def test_03_exact_digest_fk_rejects_mismatch(db):
    conn, _ = db
    incident, correction, qualification, *_ = _ids()
    _incident(conn, incident)
    _correction(conn, incident, correction, digest="sha256:a")
    with pytest.raises(psycopg.Error):
        _qualification(conn, qualification, correction, 1, "sha256:b")


def test_04_stale_revision_promotion_rejected(db):
    conn, _ = db
    incident, correction, q1, promotion, *_ = _ids()
    _incident(conn, incident)
    _correction(conn, incident, correction, digest="sha256:r1")
    _qualification(conn, q1, correction, 1, "sha256:r1")
    _correction(conn, incident, correction, digest="sha256:r2", revision=2)
    with pytest.raises(psycopg.Error):
        _promotion(conn, promotion, correction, 1, "sha256:r1", q1)


def test_05_fail_qualification_cannot_promote(db):
    conn, _ = db
    incident, correction, qualification, promotion, *_ = _ids()
    _incident(conn, incident)
    _correction(conn, incident, correction)
    _qualification(conn, qualification, correction, 1, "sha256:a", result="FAIL")
    with pytest.raises(psycopg.Error):
        _promotion(conn, promotion, correction, 1, "sha256:a", qualification)


def test_06_policy_allow_false_rejected(db):
    conn, _ = db
    incident, correction, qualification, promotion, *_ = _ids()
    _incident(conn, incident)
    _correction(conn, incident, correction)
    _qualification(conn, qualification, correction, 1, "sha256:a")
    with pytest.raises(psycopg.Error):
        _promotion(conn, promotion, correction, 1, "sha256:a", qualification, allow=False)


def test_07_revocation_removes_binding_from_effective_view(db):
    conn, _ = db
    incident, correction, qualification, promotion, binding, *_ = _ids()
    _incident(conn, incident)
    _correction(conn, incident, correction)
    _qualification(conn, qualification, correction, 1, "sha256:a")
    _promotion(conn, promotion, correction, 1, "sha256:a", qualification)
    conn.execute(
        "INSERT INTO injection_bindings(id,promotion_id,adapter,selector,selector_digest) VALUES (%s,%s,'memory','{}'::jsonb,'sha256:s')",
        (binding, promotion),
    )
    assert conn.execute("SELECT count(*) FROM active_injection_bindings").fetchone()[0] == 1
    conn.execute("UPDATE promotions SET revoked_at = now() WHERE id = %s", (promotion,))
    assert conn.execute("SELECT count(*) FROM active_injection_bindings").fetchone()[0] == 0


def test_08_supersession_hides_prior_binding_without_deleting_history(db):
    conn, _ = db
    incident, old_c, old_q, old_p, binding, new_c, *_ = _ids()
    _incident(conn, incident)
    _correction(conn, incident, old_c)
    _qualification(conn, old_q, old_c, 1, "sha256:a")
    _promotion(conn, old_p, old_c, 1, "sha256:a", old_q)
    conn.execute(
        "INSERT INTO injection_bindings(id,promotion_id,adapter,selector,selector_digest) VALUES (%s,%s,'memory','{}'::jsonb,'sha256:s')",
        (binding, old_p),
    )
    _correction(conn, incident, new_c, digest="sha256:new", supersedes=(old_c, 1))
    assert conn.execute("SELECT count(*) FROM active_injection_bindings").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM corrections WHERE id = %s", (old_c,)).fetchone()[0] == 1


def test_09_two_workers_claim_distinct_jobs_under_lock_contention(db):
    conn, schema = db
    j1, j2, *_ = _ids()
    for jid in (j1, j2):
        conn.execute("INSERT INTO worker_jobs(id,job_type,payload) VALUES (%s,'q','{}'::jsonb)", (jid,))

    other = psycopg.connect(DATABASE_URL, autocommit=True, cursor_factory=ClientCursor)
    other.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
    conn.autocommit = False
    try:
        a = conn.execute("SELECT id FROM claim_worker_job('a',30)").fetchone()[0]
        # Worker A's transaction stays open, retaining its row lock. Worker B
        # must skip that locked row and claim the other eligible job.
        b = other.execute("SELECT id FROM claim_worker_job('b',30)").fetchone()[0]
        assert a != b
        conn.commit()
    finally:
        if not conn.autocommit:
            conn.rollback()
            conn.autocommit = True
        other.close()


def test_10_expired_lease_can_be_reclaimed(db):
    conn, _ = db
    job, *_ = _ids()
    conn.execute("INSERT INTO worker_jobs(id,job_type,payload,max_attempts) VALUES (%s,'q','{}'::jsonb,2)", (job,))
    assert str(conn.execute("SELECT id FROM claim_worker_job('a',30)").fetchone()[0]) == job
    conn.execute("UPDATE worker_jobs SET lease_expires_at = now() - interval '1 second' WHERE id = %s", (job,))
    assert str(conn.execute("SELECT id FROM claim_worker_job('b',30)").fetchone()[0]) == job
    assert conn.execute("SELECT attempts FROM worker_jobs WHERE id = %s", (job,)).fetchone()[0] == 2


def test_11_retry_exhaustion_dead_letters(db):
    conn, _ = db
    job, *_ = _ids()
    conn.execute("INSERT INTO worker_jobs(id,job_type,payload,max_attempts) VALUES (%s,'q','{}'::jsonb,1)", (job,))
    conn.execute("SELECT id FROM claim_worker_job('a',30)").fetchone()
    conn.execute("UPDATE worker_jobs SET lease_expires_at = now() - interval '1 second' WHERE id = %s", (job,))
    assert conn.execute("SELECT id FROM claim_worker_job('b',30)").fetchone() is None
    assert conn.execute("SELECT status FROM worker_jobs WHERE id = %s", (job,)).fetchone()[0] == "DEAD_LETTERED"


@pytest.mark.parametrize("lease", [0, -1])
def test_12_nonpositive_lease_rejected(db, lease):
    conn, _ = db
    with pytest.raises(psycopg.Error):
        conn.execute("SELECT * FROM claim_worker_job('a', %s)", (lease,)).fetchall()


def test_13_same_idempotency_key_same_effect_returns_existing(db):
    conn, _ = db
    incident, event1, event2, *_ = _ids()
    _incident(conn, incident)
    args = (incident, "org.fuckup.failure.flagged", "sha256:effect", "key-1")
    first = conn.execute(
        "SELECT id FROM record_event_idempotent(%s,%s,%s,NULL,'{}'::jsonb,NULL,%s,NULL,'{}'::jsonb,%s)",
        (event1, *args),
    ).fetchone()[0]
    second = conn.execute(
        "SELECT id FROM record_event_idempotent(%s,%s,%s,NULL,'{}'::jsonb,NULL,%s,NULL,'{}'::jsonb,%s)",
        (event2, *args),
    ).fetchone()[0]
    assert str(first) == str(second) == event1


def test_14_same_idempotency_key_different_effect_fails(db):
    conn, _ = db
    incident, event1, event2, *_ = _ids()
    _incident(conn, incident)
    conn.execute(
        "SELECT id FROM record_event_idempotent(%s,%s,'org.fuckup.failure.flagged',NULL,'{}'::jsonb,NULL,'sha256:a',NULL,'{}'::jsonb,'key-1')",
        (event1, incident),
    ).fetchone()
    with pytest.raises(psycopg.Error):
        conn.execute(
            "SELECT id FROM record_event_idempotent(%s,%s,'org.fuckup.failure.flagged',NULL,'{}'::jsonb,NULL,'sha256:b',NULL,'{}'::jsonb,'key-1')",
            (event2, incident),
        ).fetchone()


def test_15_promotion_and_outbox_rollback_together(db):
    conn, _ = db
    incident, correction, qualification, promotion, *_ = _ids()
    _incident(conn, incident)
    _correction(conn, incident, correction)
    _qualification(conn, qualification, correction, 1, "sha256:a")
    conn.execute("BEGIN")
    _promotion(conn, promotion, correction, 1, "sha256:a", qualification)
    assert conn.execute("SELECT count(*) FROM outbox WHERE aggregate_id = %s", (promotion,)).fetchone()[0] == 1
    conn.execute("ROLLBACK")
    assert conn.execute("SELECT count(*) FROM promotions WHERE id = %s", (promotion,)).fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM outbox WHERE aggregate_id = %s", (promotion,)).fetchone()[0] == 0


def test_16_historical_mutation_rejected(db):
    conn, _ = db
    incident, correction, qualification, promotion, *_ = _ids()
    _incident(conn, incident)
    _correction(conn, incident, correction)
    _qualification(conn, qualification, correction, 1, "sha256:a")
    _promotion(conn, promotion, correction, 1, "sha256:a", qualification)
    with pytest.raises(psycopg.Error):
        conn.execute("UPDATE promotions SET policy_version = '2' WHERE id = %s", (promotion,))


def test_17_cross_incident_root_cause_rejected(db):
    conn, _ = db
    incident_a, incident_b, root, correction, *_ = _ids()
    _incident(conn, incident_a)
    _incident(conn, incident_b)
    conn.execute(
        "INSERT INTO root_cause_candidates(id,incident_id,proposition,status) VALUES (%s,%s,'cause','SUPPORTED')",
        (root, incident_a),
    )
    conn.execute("INSERT INTO corrections(id,incident_id) VALUES (%s,%s)", (correction, incident_b))
    with pytest.raises(psycopg.Error):
        conn.execute(
            "INSERT INTO correction_revisions(correction_id,revision,subject_digest,payload,created_from_root_cause_id) VALUES (%s,1,'sha256:a','{}'::jsonb,%s)",
            (correction, root),
        )


def test_revocation_before_activation_rejected(db):
    conn, _ = db
    incident, correction, qualification, promotion, *_ = _ids()
    _incident(conn, incident)
    _correction(conn, incident, correction)
    _qualification(conn, qualification, correction, 1, "sha256:a")
    _promotion(conn, promotion, correction, 1, "sha256:a", qualification)
    with pytest.raises(psycopg.Error):
        conn.execute(
            "UPDATE promotions SET revoked_at = activated_at - interval '1 second' WHERE id = %s",
            (promotion,),
        )


def test_same_digest_reused_for_changed_event_effect_still_collides(db):
    conn, _ = db
    incident_a, incident_b, event1, event2, *_ = _ids()
    _incident(conn, incident_a)
    _incident(conn, incident_b)
    conn.execute(
        "SELECT id FROM record_event_idempotent(%s,%s,'org.fuckup.failure.flagged',NULL,'{\"value\":1}'::jsonb,NULL,'sha256:reused',NULL,'{}'::jsonb,'key-reused')",
        (event1, incident_a),
    ).fetchone()
    with pytest.raises(psycopg.Error):
        conn.execute(
            "SELECT id FROM record_event_idempotent(%s,%s,'org.fuckup.failure.flagged',NULL,'{\"value\":2}'::jsonb,NULL,'sha256:reused',NULL,'{}'::jsonb,'key-reused')",
            (event2, incident_b),
        ).fetchone()


def test_new_revision_resets_active_family_to_correction_proposed(db):
    conn, _ = db
    incident, correction, qualification, promotion, *_ = _ids()
    _incident(conn, incident)
    _correction(conn, incident, correction, digest="sha256:r1")
    _qualification(conn, qualification, correction, 1, "sha256:r1")
    _promotion(conn, promotion, correction, 1, "sha256:r1", qualification)
    assert conn.execute("SELECT status FROM corrections WHERE id = %s", (correction,)).fetchone()[0] == "ACTIVE"

    _correction(conn, incident, correction, digest="sha256:r2", revision=2)
    row = conn.execute(
        "SELECT current_revision, status FROM corrections WHERE id = %s",
        (correction,),
    ).fetchone()
    assert row == (2, "CORRECTION_PROPOSED")


def test_terminal_family_cannot_accept_new_revision(db):
    conn, _ = db
    incident, old_c, new_c, *_ = _ids()
    _incident(conn, incident)
    _correction(conn, incident, old_c, digest="sha256:old")
    _correction(conn, incident, new_c, digest="sha256:new", supersedes=(old_c, 1))
    assert conn.execute("SELECT status FROM corrections WHERE id = %s", (old_c,)).fetchone()[0] == "SUPERSEDED"

    with pytest.raises(psycopg.Error):
        _correction(conn, incident, old_c, digest="sha256:old-r2", revision=2)


def test_runtime_role_cannot_rewrite_authoritative_projection_or_bypass_event_guard(db):
    conn, schema = db
    privilege = conn.execute(
        """
        SELECT rolsuper OR rolcreaterole
        FROM pg_catalog.pg_roles
        WHERE rolname = current_user
        """
    ).fetchone()[0]
    if not privilege:
        pytest.skip("test database user needs SUPERUSER or CREATEROLE for runtime-role qualification")

    role = f"fuckup_runtime_{uuid4().hex[:16]}"
    current_user = conn.execute("SELECT current_user").fetchone()[0]
    incident, correction, event, *_ = _ids()

    try:
        conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
        conn.execute(
            sql.SQL("GRANT {} TO {}").format(
                sql.Identifier(role),
                sql.Identifier(current_user),
            )
        )
        conn.execute("SELECT configure_fuckup_runtime_role(%s::name)", (role,))

        _incident(conn, incident)
        _correction(conn, incident, correction, digest="sha256:a")

        conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "UPDATE corrections SET current_revision = 999, status = 'ACTIVE' WHERE id = %s",
                (correction,),
            )

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                """
                INSERT INTO events(
                    id, incident_id, event_type, payload, effect_digest, idempotency_key
                )
                VALUES (%s, %s, 'org.fuckup.failure.flagged', '{}'::jsonb, 'sha256:x', 'direct')
                """,
                (event, incident),
            )

        guarded = conn.execute(
            """
            SELECT id
            FROM record_event_idempotent(
                %s, %s, 'org.fuckup.failure.flagged', NULL,
                '{}'::jsonb, NULL, 'sha256:guarded', NULL, '{}'::jsonb, 'guarded'
            )
            """,
            (event, incident),
        ).fetchone()[0]
        assert str(guarded) == event
    finally:
        conn.execute("RESET ROLE")
        conn.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(role)))
        conn.execute(
            sql.SQL("REVOKE {} FROM {}").format(
                sql.Identifier(role),
                sql.Identifier(current_user),
            )
        )
        conn.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))


def test_runtime_role_with_parent_membership_is_rejected(db):
    conn, schema = db
    privilege = conn.execute(
        """
        SELECT rolsuper OR rolcreaterole
        FROM pg_catalog.pg_roles
        WHERE rolname = current_user
        """
    ).fetchone()[0]
    if not privilege:
        pytest.skip("test database user needs SUPERUSER or CREATEROLE for role qualification")

    parent = f"fuckup_parent_{uuid4().hex[:16]}"
    runtime = f"fuckup_runtime_{uuid4().hex[:16]}"

    try:
        conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(parent)))
        conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(runtime)))
        conn.execute(
            sql.SQL("GRANT UPDATE ON {}.corrections TO {}").format(
                sql.Identifier(schema),
                sql.Identifier(parent),
            )
        )
        conn.execute(
            sql.SQL("GRANT {} TO {}").format(
                sql.Identifier(parent),
                sql.Identifier(runtime),
            )
        )

        with pytest.raises(psycopg.Error, match="must not be a member of another role"):
            conn.execute("SELECT configure_fuckup_runtime_role(%s::name)", (runtime,))
    finally:
        conn.execute(
            sql.SQL("REVOKE {} FROM {}").format(
                sql.Identifier(parent),
                sql.Identifier(runtime),
            )
        )
        conn.execute(
            sql.SQL("REVOKE ALL PRIVILEGES ON {}.corrections FROM {}").format(
                sql.Identifier(schema),
                sql.Identifier(parent),
            )
        )
        conn.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(runtime)))
        conn.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(parent)))


def test_configured_runtime_role_can_use_guarded_worker_lifecycle(db):
    conn, _schema = db
    privilege = conn.execute(
        """
        SELECT rolsuper OR rolcreaterole
        FROM pg_catalog.pg_roles
        WHERE rolname = current_user
        """
    ).fetchone()[0]
    if not privilege:
        pytest.skip("test database user needs SUPERUSER or CREATEROLE for runtime-role qualification")

    runtime = f"fuckup_runtime_{uuid4().hex[:16]}"
    current_user = conn.execute("SELECT current_user").fetchone()[0]
    job_complete, job_fail, *_ = _ids()

    try:
        conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(runtime)))
        conn.execute("SELECT configure_fuckup_runtime_role(%s::name)", (runtime,))
        conn.execute(
            sql.SQL("GRANT {} TO {}").format(
                sql.Identifier(runtime),
                sql.Identifier(current_user),
            )
        )

        conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(runtime)))

        conn.execute(
            "INSERT INTO worker_jobs(id,job_type,payload,max_attempts) VALUES (%s,'q','{}'::jsonb,2)",
            (job_complete,),
        )
        assert str(conn.execute("SELECT id FROM claim_worker_job('worker-a',30)").fetchone()[0]) == job_complete
        assert str(conn.execute("SELECT id FROM complete_worker_job(%s,'worker-a')", (job_complete,)).fetchone()[0]) == job_complete

        conn.execute(
            "INSERT INTO worker_jobs(id,job_type,payload,max_attempts) VALUES (%s,'q','{}'::jsonb,1)",
            (job_fail,),
        )
        assert str(conn.execute("SELECT id FROM claim_worker_job('worker-b',30)").fetchone()[0]) == job_fail
        failed = conn.execute(
            "SELECT id,status FROM fail_worker_job(%s,'worker-b','{}'::jsonb,false,0)",
            (job_fail,),
        ).fetchone()
        assert (str(failed[0]), failed[1]) == (job_fail, "DEAD_LETTERED")
    finally:
        conn.execute("RESET ROLE")
        conn.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(runtime)))
        conn.execute(
            sql.SQL("REVOKE {} FROM {}").format(
                sql.Identifier(runtime),
                sql.Identifier(current_user),
            )
        )
        conn.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(runtime)))


def test_runtime_role_rejects_public_column_privilege_bypass(db):
    conn, schema = db
    privilege = conn.execute(
        """
        SELECT rolsuper OR rolcreaterole
        FROM pg_catalog.pg_roles
        WHERE rolname = current_user
        """
    ).fetchone()[0]
    if not privilege:
        pytest.skip("test database user needs SUPERUSER or CREATEROLE for role qualification")

    runtime = f"fuckup_runtime_{uuid4().hex[:16]}"

    try:
        conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(runtime)))
        conn.execute(
            sql.SQL("GRANT UPDATE (current_revision) ON {}.corrections TO PUBLIC").format(
                sql.Identifier(schema)
            )
        )

        with pytest.raises(psycopg.Error, match="retains forbidden effective privileges"):
            conn.execute("SELECT configure_fuckup_runtime_role(%s::name)", (runtime,))
    finally:
        conn.execute(
            sql.SQL("REVOKE UPDATE (current_revision) ON {}.corrections FROM PUBLIC").format(
                sql.Identifier(schema)
            )
        )
        conn.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(runtime)))


def test_runtime_role_rejects_public_table_insert_bypass(db):
    conn, schema = db
    privilege = conn.execute(
        """
        SELECT rolsuper OR rolcreaterole
        FROM pg_catalog.pg_roles
        WHERE rolname = current_user
        """
    ).fetchone()[0]
    if not privilege:
        pytest.skip("test database user needs SUPERUSER or CREATEROLE for role qualification")

    runtime = f"fuckup_runtime_{uuid4().hex[:16]}"

    try:
        conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(runtime)))
        conn.execute(
            sql.SQL("GRANT INSERT ON {}.worker_jobs TO PUBLIC").format(
                sql.Identifier(schema)
            )
        )

        with pytest.raises(psycopg.Error, match="retains forbidden effective privileges"):
            conn.execute("SELECT configure_fuckup_runtime_role(%s::name)", (runtime,))
    finally:
        conn.execute(
            sql.SQL("REVOKE INSERT ON {}.worker_jobs FROM PUBLIC").format(
                sql.Identifier(schema)
            )
        )
        conn.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(runtime)))


def test_runtime_role_rejects_public_sensitive_column_insert_bypass(db):
    conn, schema = db
    privilege = conn.execute(
        """
        SELECT rolsuper OR rolcreaterole
        FROM pg_catalog.pg_roles
        WHERE rolname = current_user
        """
    ).fetchone()[0]
    if not privilege:
        pytest.skip("test database user needs SUPERUSER or CREATEROLE for role qualification")

    runtime = f"fuckup_runtime_{uuid4().hex[:16]}"

    try:
        conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(runtime)))
        conn.execute(
            sql.SQL("GRANT INSERT (status) ON {}.worker_jobs TO PUBLIC").format(
                sql.Identifier(schema)
            )
        )

        with pytest.raises(psycopg.Error, match="retains forbidden effective privileges"):
            conn.execute("SELECT configure_fuckup_runtime_role(%s::name)", (runtime,))
    finally:
        conn.execute(
            sql.SQL("REVOKE INSERT (status) ON {}.worker_jobs FROM PUBLIC").format(
                sql.Identifier(schema)
            )
        )
        conn.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(runtime)))


def test_trusted_schema_is_not_writable_by_public(db):
    conn, schema = db
    assert not conn.execute(
        "SELECT pg_catalog.has_schema_privilege('public', %s, 'CREATE')",
        (schema,),
    ).fetchone()[0]


def test_runtime_role_rejects_database_create_privilege(db):
    conn, _schema = db
    can_grant = conn.execute(
        """
        SELECT pg_catalog.has_database_privilege(
            current_user,
            current_database(),
            'CREATE WITH GRANT OPTION'
        )
        """
    ).fetchone()[0]
    if not can_grant:
        pytest.skip("test database user needs CREATE WITH GRANT OPTION on the test database")

    runtime = f"fuckup_runtime_{uuid4().hex[:16]}"
    database = conn.execute("SELECT current_database()").fetchone()[0]

    try:
        conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(runtime)))
        conn.execute(
            sql.SQL("GRANT CREATE ON DATABASE {} TO {}").format(
                sql.Identifier(database),
                sql.Identifier(runtime),
            )
        )

        with pytest.raises(psycopg.Error, match="retains forbidden effective privileges"):
            conn.execute("SELECT configure_fuckup_runtime_role(%s::name)", (runtime,))
    finally:
        conn.execute(
            sql.SQL("REVOKE CREATE ON DATABASE {} FROM {}").format(
                sql.Identifier(database),
                sql.Identifier(runtime),
            )
        )
        conn.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(runtime)))


def test_runtime_cannot_fabricate_promotion_or_binding_authority(db):
    conn, schema = db
    privilege = conn.execute(
        """
        SELECT rolsuper OR rolcreaterole
        FROM pg_catalog.pg_roles
        WHERE rolname = current_user
        """
    ).fetchone()[0]
    if not privilege:
        pytest.skip("test database user needs SUPERUSER or CREATEROLE for authority-role qualification")

    runtime = f"fuckup_runtime_{uuid4().hex[:16]}"
    authorizer = f"fuckup_authorizer_{uuid4().hex[:16]}"
    current_user = conn.execute("SELECT current_user").fetchone()[0]
    incident, correction, qualification, promotion, binding, authorization, *_ = _ids()

    try:
        conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(runtime)))
        conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(authorizer)))
        conn.execute("SELECT configure_fuckup_runtime_role(%s::name)", (runtime,))
        conn.execute("SELECT configure_fuckup_authorizer_role(%s::name)", (authorizer,))
        conn.execute(
            sql.SQL("GRANT {}, {} TO {}").format(
                sql.Identifier(runtime),
                sql.Identifier(authorizer),
                sql.Identifier(current_user),
            )
        )

        _incident(conn, incident)
        _correction(conn, incident, correction, digest="sha256:a")
        _qualification(conn, qualification, correction, 1, "sha256:a")

        conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(runtime)))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                """
                INSERT INTO promotions(
                    id, correction_id, correction_revision, exact_subject_digest,
                    qualification_id, qualification_result, policy_name, policy_version,
                    policy_decision, activation_scope, rollback_condition
                )
                VALUES (
                    %s, %s, 1, 'sha256:a', %s, 'PASS', 'fake', '1',
                    '{"allow":true}'::jsonb, '{"agent":"demo"}'::jsonb,
                    '{"action":"revoke"}'::jsonb
                )
                """,
                (promotion, correction, qualification),
            )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                """
                SELECT * FROM authorize_and_promote(
                    %s,%s,%s,1,'sha256:a',%s,'fake','1',
                    '{"allow":true}'::jsonb,'{"agent":"demo"}'::jsonb,
                    '{"action":"revoke"}'::jsonb,true,false,false
                )
                """,
                (authorization, promotion, correction, qualification),
            ).fetchall()

        conn.execute("RESET ROLE")
        conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(authorizer)))
        created = conn.execute(
            """
            SELECT id
            FROM authorize_and_promote(
                %s,%s,%s,1,'sha256:a',%s,'policy-v1','1',
                '{"allow":true}'::jsonb,'{"agent":"demo"}'::jsonb,
                '{"action":"revoke"}'::jsonb,true,false,false
            )
            """,
            (authorization, promotion, correction, qualification),
        ).fetchone()[0]
        assert str(created) == promotion

        with pytest.raises(psycopg.Error, match="equal to or narrower"):
            conn.execute(
                """
                SELECT * FROM create_authorized_binding(
                    %s,%s,'memory','{"model":"other"}'::jsonb,
                    'sha256:broad',0,'FAIL_CLOSED',NULL
                )
                """,
                (binding, promotion),
            ).fetchall()

        created_binding = conn.execute(
            """
            SELECT id
            FROM create_authorized_binding(
                %s,%s,'memory','{"agent":"demo","task":"code"}'::jsonb,
                'sha256:narrow',0,'FAIL_CLOSED',now() + interval '2 hours'
            )
            """,
            (binding, promotion),
        ).fetchone()[0]
        assert str(created_binding) == binding

        conn.execute("RESET ROLE")
        conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(runtime)))

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                """
                INSERT INTO injection_bindings(
                    id,promotion_id,adapter,selector,selector_digest
                )
                VALUES (%s,%s,'memory','{"agent":"demo"}'::jsonb,'sha256:direct')
                """,
                (str(uuid4()), promotion),
            )

        narrowed_expiry = conn.execute(
            """
            SELECT expires_at
            FROM restrict_injection_binding(%s,false,now() + interval '1 hour')
            """,
            (binding,),
        ).fetchone()[0]
        assert narrowed_expiry is not None

        with pytest.raises(psycopg.Error, match="only move earlier"):
            conn.execute(
                """
                SELECT * FROM restrict_injection_binding(
                    %s,false,now() + interval '90 minutes'
                )
                """,
                (binding,),
            ).fetchall()

        conn.execute(
            "SELECT id FROM restrict_injection_binding(%s,true,NULL)",
            (binding,),
        ).fetchone()

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "UPDATE injection_bindings SET active = true WHERE id = %s",
                (binding,),
            )
    finally:
        conn.execute("RESET ROLE")
        for role in (runtime, authorizer):
            conn.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(role)))
        conn.execute(
            sql.SQL("REVOKE {}, {} FROM {}").format(
                sql.Identifier(runtime),
                sql.Identifier(authorizer),
                sql.Identifier(current_user),
            )
        )
        for role in (runtime, authorizer):
            conn.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))


def test_same_role_cannot_be_runtime_and_authorizer(db):
    conn, _schema = db
    privilege = conn.execute(
        """
        SELECT rolsuper OR rolcreaterole
        FROM pg_catalog.pg_roles
        WHERE rolname = current_user
        """
    ).fetchone()[0]
    if not privilege:
        pytest.skip("test database user needs SUPERUSER or CREATEROLE for authority-role qualification")

    role = f"fuckup_role_{uuid4().hex[:16]}"
    try:
        conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
        conn.execute("SELECT configure_fuckup_runtime_role(%s::name)", (role,))
        with pytest.raises(psycopg.Error, match="already assigned as RUNTIME authority"):
            conn.execute("SELECT configure_fuckup_authorizer_role(%s::name)", (role,))
    finally:
        conn.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(role)))
        conn.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))


def test_execution_integrity_journal_requires_reconciliation_before_redispatch(db):
    conn, _schema = db
    operation = str(uuid4())
    duplicate_id = str(uuid4())
    key = f"effect:{uuid4()}"

    created = conn.execute(
        """
        SELECT id FROM prepare_effect_operation(
            %s,%s,'provider:demo','publish',
            '{"artifact":"a"}'::jsonb,'sha256:a',now()
        )
        """,
        (operation, key),
    ).fetchone()[0]
    assert str(created) == operation

    duplicate = conn.execute(
        """
        SELECT id FROM prepare_effect_operation(
            %s,%s,'provider:demo','publish',
            '{"artifact":"a"}'::jsonb,'sha256:a',now()
        )
        """,
        (duplicate_id, key),
    ).fetchone()[0]
    assert str(duplicate) == operation

    with pytest.raises(psycopg.Error, match="idempotency key collision"):
        conn.execute(
            """
            SELECT * FROM prepare_effect_operation(
                %s,%s,'provider:demo','publish',
                '{"artifact":"different"}'::jsonb,'sha256:different',now()
            )
            """,
            (str(uuid4()), key),
        ).fetchall()

    attempted = conn.execute(
        "SELECT state FROM record_effect_attempt(%s,'attempt:1',now())",
        (operation,),
    ).fetchone()[0]
    assert attempted == "ATTEMPTED"

    with pytest.raises(psycopg.Error, match="cannot attempt operation from state"):
        conn.execute(
            "SELECT * FROM record_effect_attempt(%s,'attempt:2',now())",
            (operation,),
        ).fetchall()

    ambiguous = conn.execute(
        """
        SELECT state FROM reconcile_effect_operation(
            %s,'AMBIGUOUS','timeout:1',NULL,now()
        )
        """,
        (operation,),
    ).fetchone()[0]
    assert ambiguous == "AMBIGUOUS"

    with pytest.raises(psycopg.Error, match="cannot attempt operation from state"):
        conn.execute(
            "SELECT * FROM record_effect_attempt(%s,'attempt:3',now())",
            (operation,),
        ).fetchall()

    verified = conn.execute(
        """
        SELECT state FROM reconcile_effect_operation(
            %s,'VERIFIED','readback:1','sha256:observed',now()
        )
        """,
        (operation,),
    ).fetchone()[0]
    assert verified == "VERIFIED"

    with pytest.raises(psycopg.Error, match="cannot reconcile operation from state"):
        conn.execute(
            """
            SELECT * FROM reconcile_effect_operation(
                %s,'FAILED','late-readback',NULL,now()
            )
            """,
            (operation,),
        ).fetchall()


def test_incident_occurrence_preserves_duplicate_evidence(db):
    conn, _schema = db
    incident = str(uuid4())
    first_occurrence = str(uuid4())
    second_occurrence = str(uuid4())
    _incident(conn, incident)

    conn.execute(
        """
        SELECT id FROM record_incident_occurrence(
            %s,%s,'{"attempt":1}'::jsonb,'sha256:one',now(),'run:1'
        )
        """,
        (first_occurrence, incident),
    ).fetchone()
    conn.execute(
        """
        SELECT id FROM record_incident_occurrence(
            %s,%s,'{"attempt":2}'::jsonb,'sha256:two',now(),'run:2'
        )
        """,
        (second_occurrence, incident),
    ).fetchone()

    rows = conn.execute(
        """
        SELECT ordinal, payload_digest, source_ref
        FROM incident_occurrences
        WHERE incident_id = %s
        ORDER BY ordinal
        """,
        (incident,),
    ).fetchall()
    assert rows == [
        (1, "sha256:one", "run:1"),
        (2, "sha256:two", "run:2"),
    ]
    assert conn.execute(
        "SELECT occurrence_count FROM incidents WHERE id = %s",
        (incident,),
    ).fetchone()[0] == 2


def test_runtime_role_has_guarded_effect_journal_without_direct_dml(db):
    conn, schema = db
    privilege = conn.execute(
        """
        SELECT rolsuper OR rolcreaterole
        FROM pg_catalog.pg_roles
        WHERE rolname = current_user
        """
    ).fetchone()[0]
    if not privilege:
        pytest.skip("test database user needs SUPERUSER or CREATEROLE for runtime-role qualification")

    role = f"fuckup_runtime_{uuid4().hex[:16]}"
    current_user = conn.execute("SELECT current_user").fetchone()[0]
    operation = str(uuid4())
    key = f"effect:{uuid4()}"

    try:
        conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
        conn.execute(
            sql.SQL("GRANT {} TO {}").format(
                sql.Identifier(role),
                sql.Identifier(current_user),
            )
        )
        conn.execute("SELECT configure_fuckup_runtime_role(%s::name)", (role,))
        conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                """
                INSERT INTO effect_operations(
                    id,idempotency_key,target,operation_kind,
                    effect_payload,effect_digest
                )
                VALUES (
                    %s,%s,'provider:demo','publish',
                    '{}'::jsonb,'sha256:direct'
                )
                """,
                (str(uuid4()), f"direct:{uuid4()}"),
            )

        created = conn.execute(
            """
            SELECT id FROM prepare_effect_operation(
                %s,%s,'provider:demo','publish',
                '{"artifact":"a"}'::jsonb,'sha256:a',now()
            )
            """,
            (operation, key),
        ).fetchone()[0]
        assert str(created) == operation

        state = conn.execute(
            "SELECT state FROM record_effect_attempt(%s,'attempt:runtime',now())",
            (operation,),
        ).fetchone()[0]
        assert state == "ATTEMPTED"
    finally:
        conn.execute("RESET ROLE")
        conn.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(role)))
        conn.execute(
            sql.SQL("REVOKE {} FROM {}").format(
                sql.Identifier(role),
                sql.Identifier(current_user),
            )
        )
        conn.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))

def test_versioned_binding_is_authorizer_only_and_persists_exact_adapter_version(db):
    conn, schema = db
    privilege = conn.execute(
        """
        SELECT rolsuper OR rolcreaterole
        FROM pg_catalog.pg_roles
        WHERE rolname = current_user
        """
    ).fetchone()[0]
    if not privilege:
        pytest.skip("test database user needs SUPERUSER or CREATEROLE for authority-role qualification")

    authorizer = f"fuckup_authorizer_{uuid4().hex[:16]}"
    runtime = f"fuckup_runtime_{uuid4().hex[:16]}"
    current_user = conn.execute("SELECT current_user").fetchone()[0]
    incident, correction, qualification, promotion, binding, *_ = _ids()

    try:
        _incident(conn, incident)
        _correction(conn, incident, correction, digest="sha256:a")
        _qualification(conn, qualification, correction, 1, "sha256:a")
        _promotion(conn, promotion, correction, 1, "sha256:a", qualification)

        for role in (authorizer, runtime):
            conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
            conn.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(role),
                    sql.Identifier(current_user),
                )
            )

        conn.execute("SELECT configure_fuckup_authorizer_role(%s::name)", (authorizer,))
        conn.execute("SELECT configure_fuckup_runtime_role(%s::name)", (runtime,))

        conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(runtime)))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                """
                SELECT * FROM create_versioned_authorized_binding(
                    %s,%s,'memory-injector','1',
                    '{"agent":"demo","task":"code"}'::jsonb,
                    'sha256:selector',0,'FAIL_CLOSED',NULL
                )
                """,
                (binding, promotion),
            ).fetchall()

        conn.execute("RESET ROLE")
        conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(authorizer)))
        created = conn.execute(
            """
            SELECT id, adapter, adapter_version
            FROM create_versioned_authorized_binding(
                %s,%s,'memory-injector','1',
                '{"agent":"demo","task":"code"}'::jsonb,
                'sha256:selector',0,'FAIL_CLOSED',NULL
            )
            """,
            (binding, promotion),
        ).fetchone()
        assert (str(created[0]), created[1], created[2]) == (
            binding,
            "memory-injector",
            "1",
        )

        active = conn.execute(
            """
            SELECT id, promotion_id, adapter, adapter_version, correction_id, correction_revision
            FROM active_injection_bindings
            WHERE id = %s
            """,
            (binding,),
        ).fetchone()
        assert (
            str(active[0]),
            str(active[1]),
            active[2],
            active[3],
            str(active[4]),
            active[5],
        ) == (
            binding,
            promotion,
            "memory-injector",
            "1",
            correction,
            1,
        )
    finally:
        conn.execute("RESET ROLE")
        for role in (runtime, authorizer):
            conn.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(role)))
        conn.execute(
            sql.SQL("REVOKE {}, {} FROM {}").format(
                sql.Identifier(runtime),
                sql.Identifier(authorizer),
                sql.Identifier(current_user),
            )
        )
        for role in (runtime, authorizer):
            conn.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))