-- Atomically claim one available job without colliding with another worker.
-- The caller supplies :worker_id and :lease_seconds.
WITH candidate AS (
    SELECT id
    FROM worker_jobs
    WHERE status IN ('PENDING', 'RETRY')
      AND available_at <= now()
      AND (lease_expires_at IS NULL OR lease_expires_at <= now())
    ORDER BY available_at, created_at, id
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
UPDATE worker_jobs AS job
SET status = 'RUNNING',
    attempts = attempts + 1,
    locked_by = :worker_id,
    locked_at = now(),
    lease_expires_at = now() + (:lease_seconds || ' seconds')::interval,
    updated_at = now()
FROM candidate
WHERE job.id = candidate.id
RETURNING job.*;
